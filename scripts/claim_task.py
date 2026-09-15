#!/usr/bin/env python3
"""Atomic task claiming across eight worker worktrees.

## The failure this prevents

On 2026-09-15 six of eight workers independently selected the SAME task off
`docs/qwen-tasks/TODO/` and four produced the same answer. Five workers wasted.
The prompt had named one task per worker; `QWEN.md` outranked it by saying
"take the task Claude named, OR the highest-priority file in TODO".

Wording was the first fix and it is not enough on its own. Two workers that
both READ a TODO directory a millisecond apart will both see the task as free,
because reading a directory is not claiming anything. **The claim has to be an
atomic write that exactly one racer can win.**

## How the claim works

`os.open(path, O_CREAT | O_EXCL)` - the one primitive that is atomic on both
Windows and POSIX. The first worker to create `work/claims/<TASK_ID>.claim`
owns the task; every other worker gets `FileExistsError` and is told to pick
another. There is no read-then-write window for two workers to fit inside.

Claims live in the MAIN worktree's `work/claims/`, by absolute path, because
the eight worktrees each have their own `docs/` and `work/` and a claim
written into a worker's own tree coordinates nothing. `work/` is gitignored,
so claims are machine-local by design: they are a mutual-exclusion primitive,
not durable state. Claude syncs the outcome into the committed registry.

## Why a stale claim is not silently reclaimed

A claim carries the pid and an ISO timestamp. `--reap` will release claims
whose process is gone, but it is a SEPARATE, EXPLICIT action and it says what
it released. A crashed worker's claim looks exactly like a working worker's
claim, and quietly reclaiming on a timer is how two workers end up on one task
again - by a slower route.

## Usage

    py -3 scripts/claim_task.py --claim TASK-098 --worker qwen-3
    py -3 scripts/claim_task.py --release TASK-098
    py -3 scripts/claim_task.py --status
    py -3 scripts/claim_task.py --next --worker qwen-3      # claim best free task
    py -3 scripts/claim_task.py --reap                      # release dead pids

Exit 0 on a successful claim, 3 when the task was already claimed. A worker
script can branch on that without parsing output.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Resolved from THIS file, so every worktree points at the same directory.
# A relative path would make each worker claim against its own tree, which is
# the bug this module exists to prevent.
MAIN_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAIMS = os.path.join(MAIN_REPO, "work", "claims")
REGISTRY = os.path.join(MAIN_REPO, "docs", "state", "TASK-REGISTRY.json")

CLAIM_OK, CLAIM_TAKEN, CLAIM_ERROR = 0, 3, 2


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def claim(task_id, worker):
    """Atomic. Exactly one caller can win, however many race."""
    os.makedirs(CLAIMS, exist_ok=True)
    path = os.path.join(CLAIMS, "%s.claim" % task_id)
    payload = json.dumps({
        "task": task_id, "worker": worker,
        "pid": os.getpid(), "claimed_at": _now(),
    })
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            with open(path, encoding="utf-8") as fh:
                held = json.load(fh)
        except Exception:
            held = {}
        print("ALREADY CLAIMED %s by %s at %s"
              % (task_id, held.get("worker", "?"), held.get("claimed_at", "?")))
        return CLAIM_TAKEN
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(payload)
    print("CLAIMED %s for %s" % (task_id, worker))
    return CLAIM_OK


def release(task_id):
    path = os.path.join(CLAIMS, "%s.claim" % task_id)
    if os.path.exists(path):
        os.remove(path)
        print("RELEASED %s" % task_id)
    else:
        print("NOT CLAIMED %s" % task_id)
    return CLAIM_OK


def held_claims():
    if not os.path.isdir(CLAIMS):
        return []
    out = []
    for fn in sorted(os.listdir(CLAIMS)):
        if not fn.endswith(".claim"):
            continue
        try:
            with open(os.path.join(CLAIMS, fn), encoding="utf-8") as fh:
                out.append(json.load(fh))
        except Exception:
            out.append({"task": fn[:-6], "worker": "?", "unreadable": True})
    return out


def _alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        import subprocess
        try:
            r = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid],
                               capture_output=True, text=True, timeout=30)
            return str(pid) in r.stdout
        except Exception:
            # Cannot tell. Treat as alive: a false "dead" hands one task to two
            # workers, which is the exact failure being prevented.
            return True
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def reap():
    freed = []
    for c in held_claims():
        if not _alive(c.get("pid")):
            release(c["task"])
            freed.append(c["task"])
    print("reaped %d stale claim(s): %s" % (len(freed), ", ".join(freed) or "none"))
    return CLAIM_OK


def ready_tasks():
    """READY = in TODO, not claimed, dependencies satisfied. Sorted by the
    registry's priority (P0 first), then by task id."""
    todo_dir = os.path.join(MAIN_REPO, "docs", "qwen-tasks", "TODO")
    if not os.path.isdir(todo_dir):
        return []
    claimed = {c["task"] for c in held_claims()}
    reg = {}
    if os.path.exists(REGISTRY):
        try:
            with open(REGISTRY, encoding="utf-8") as fh:
                reg = {t["task"]: t for t in json.load(fh).get("tasks", [])}
        except Exception:
            reg = {}
    done = set()
    done_dir = os.path.join(MAIN_REPO, "docs", "qwen-tasks", "DONE")
    if os.path.isdir(done_dir):
        done = {f.split("-")[0] + "-" + f.split("-")[1] for f in os.listdir(done_dir)
                if f.startswith("TASK-")}

    out = []
    for fn in sorted(os.listdir(todo_dir)):
        if not fn.startswith("TASK-") or not fn.endswith(".md"):
            continue
        tid = "-".join(fn.split("-")[:2])
        if tid in claimed:
            continue
        meta = reg.get(tid, {})
        deps = meta.get("dependencies") or []
        if any(d not in done for d in deps):
            continue
        out.append((meta.get("priority", "P4"), tid, fn))
    out.sort()
    return out


def main():
    p = argparse.ArgumentParser(description="Atomic task claiming across worktrees")
    p.add_argument("--claim")
    p.add_argument("--release")
    p.add_argument("--worker", default="unknown")
    p.add_argument("--status", action="store_true")
    p.add_argument("--next", action="store_true")
    p.add_argument("--reap", action="store_true")
    a = p.parse_args()

    if a.claim:
        return claim(a.claim, a.worker)
    if a.release:
        return release(a.release)
    if a.reap:
        return reap()
    if a.next:
        for _prio, tid, fn in ready_tasks():
            if claim(tid, a.worker) == CLAIM_OK:
                print("FILE %s" % fn)
                return CLAIM_OK
        print("NO READY TASK")
        return CLAIM_TAKEN
    if a.status or True:
        cl = held_claims()
        print("claims held: %d" % len(cl))
        for c in cl:
            print("  %-10s %-12s pid=%-7s %s"
                  % (c.get("task"), c.get("worker"), c.get("pid"), c.get("claimed_at")))
        rd = ready_tasks()
        print("ready (unclaimed, deps met): %d" % len(rd))
        for prio, tid, _fn in rd:
            print("  %-4s %s" % (prio, tid))
        return CLAIM_OK


if __name__ == "__main__":
    sys.exit(main())
