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
import hashlib
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

#: Branch stages that mean a RESULT EXISTS rather than work is in progress.
#: A task whose branch copy sits in one of these must not be implemented again,
#: even though nothing is running - that is an integration job, not a dispatch.
#: Every other stage (RUNNING, REWORK, BLOCKED_QUOTA, ...) is non-terminal: with
#: no claim behind it, it is a dead run and the task is recoverable.
TERMINAL_BRANCH_STAGES = ("REVIEW", "DONE")

#: Bumped when the cached classification's SHAPE changes. The refs fingerprint
#: alone cannot catch that: refs may be identical while the cache on disk was
#: written by the previous two-value format, which would be read back as the
#: wrong thing entirely.
CACHE_SCHEMA = 2


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
    """DISABLED BY DEFAULT, and the reason is worth reading.

    The pid in a claim is the pid of the process that WROTE the claim. Claude
    claims on a worker's behalf before launching it, so that process has
    already exited by the time the worker starts real work. Every claim
    therefore looks dead to a pid check, and an automatic reap would release
    all eight claims while all eight workers were running - handing every task
    to a second worker and reproducing the exact collision this module exists
    to prevent, with more confidence.

    Releasing a claim is consequently an EXPLICIT, per-task act:

        py -3 scripts/claim_task.py --release TASK-099

    The pool loop releases each claim when its own dispatch subshell exits,
    which is the one place that genuinely knows the worker has finished.
    """
    print("REFUSED: --reap is disabled. The recorded pid belongs to the "
          "claiming process, not the worker, so a pid check would report every "
          "live claim as dead and release all of them.")
    print("Release one deliberately: --release TASK-NNN")
    for c in held_claims():
        print("  held: %-10s by %-22s since %s"
              % (c.get("task"), c.get("worker"), c.get("claimed_at")))
    return CLAIM_ERROR


def _git(args, timeout=30):
    """Run a git command in MAIN_REPO. Returns stdout or empty string on any
    failure. Every git call in this module goes through here so that a missing
    ref, a detached HEAD, a branch with no commits or a reset worktree - all
    four have happened in production - returns empty rather than throwing."""
    import subprocess
    try:
        r = subprocess.run(
            ["git", "-C", MAIN_REPO] + args,
            capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            return ""
        return r.stdout
    except Exception:
        return ""


def _all_branches():
    """Every branch ref except master and HEAD pointers. Scans both local and
    remote-tracking refs: pool.sh's `checkout -B` destroys local refs when a
    worker is reused, and the pushed copy in refs/remotes/origin/ is the only
    record of the finished work (measured 2026-09-15, TASK-139 through 143)."""
    out = _git(["for-each-ref", "--format=%(refname:short)",
                "refs/heads/", "refs/remotes/"], timeout=60)
    if not out:
        return []
    return [r for r in out.split()
            if r not in ("master", "origin/master") and not r.endswith("/HEAD")]


def _task_files_on(ref):
    """{task_id: (stage, full_path)} for every TASK-* file visible on *ref*.

    Returns empty dict on any failure. The stage is the directory name
    (TODO, RUNNING, REVIEW, DONE, REWORK, BLOCKED, BLOCKED_QUOTA)."""
    out = _git(["ls-tree", "-r", "--name-only", ref, "docs/qwen-tasks/"])
    result = {}
    for line in out.splitlines():
        line = line.strip()
        if not line or not line.endswith(".md"):
            continue
        base = os.path.basename(line)
        if not base.startswith("TASK-"):
            continue
        parts = line.replace("\\", "/").split("/")
        stage = parts[-2] if len(parts) >= 2 else "UNKNOWN"
        task_id = "-".join(base.split("-")[:2])
        result[task_id] = (stage, line)
    return result


def _last_touch_ts(ref, filepath):
    """Commit timestamp (epoch seconds) of the last commit that touched
    *filepath* on *ref*. Returns 0 if the file does not exist or the command
    fails. Zero is safe: it loses every comparison, so a missing timestamp
    is treated as 'this side never moved the file'."""
    out = _git(["log", "-1", "--format=%ct", ref, "--", filepath])
    try:
        return int(out.strip())
    except (ValueError, AttributeError):
        return 0


def _branch_cache_path():
    return os.path.join(MAIN_REPO, "work", ".claim-branch-cache.json")


def _refs_fingerprint():
    """One git call: every ref and the commit it points at.

    If this string is unchanged, no branch has moved, so the classification
    below cannot have changed either. That makes it a sound cache key rather
    than a time-based guess.
    """
    out = _git(["for-each-ref", "--format=%(refname:short) %(objectname)",
                "refs/heads/", "refs/remotes/"], timeout=60)
    return hashlib.sha256((out or "").encode("utf-8")).hexdigest()


def _classify_branch_tasks():
    """Cached wrapper. See _classify_branch_tasks_uncached for the logic.

    WHY A CACHE IS NOT A SHORTCUT HERE. The uncached classification runs one
    `ls-tree` per ref plus one `log -1` per task per ref, and this repository
    has 270 refs, 187 of them unmerged. Measured 2026-09-16: 100 SECONDS per
    call on Windows. `pool.sh` calls `--status` once per worker in `busy()`
    and again in `next_ready()`, so a single eight-worker sweep paid that cost
    about sixteen times and never finished.

    The key is the exact ref->commit mapping, so a stale answer is impossible:
    any branch moving anywhere changes the fingerprint and invalidates the
    entry. That is a different and stronger guarantee than a TTL, which would
    have to choose between being slow and being wrong.
    """
    fp = _refs_fingerprint()
    path = _branch_cache_path()
    try:
        with open(path, encoding="utf-8") as fh:
            cached = json.load(fh)
        if (cached.get("fingerprint") == fp
                and cached.get("schema") == CACHE_SCHEMA):
            return (cached["awaiting"], cached["recoverable"], cached["stale"])
    except Exception:
        pass
    awaiting, recoverable, stale = _classify_branch_tasks_uncached()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"fingerprint": fp, "schema": CACHE_SCHEMA,
                       "awaiting": awaiting, "recoverable": recoverable,
                       "stale": stale}, fh)
        os.replace(tmp, path)
    except Exception:
        pass       # a cache that cannot be written must not break a dispatch
    return awaiting, recoverable, stale


def _stage_and_task(path):
    """('REVIEW', 'TASK-158') from a docs/qwen-tasks path, or (None, None).

    The stage is the directory, so the path alone answers what a tree listing
    was being spawned per-ref to answer."""
    p = path.replace("\\", "/").strip()
    if not p.endswith(".md"):
        return None, None
    parts = p.split("/")
    base = parts[-1]
    if not base.startswith("TASK-") or len(parts) < 2:
        return None, None
    return parts[-2], "-".join(base.split("-")[:2])


def _master_touch_times():
    """{path: last commit timestamp on master} for every task file path.

    One `git log --name-only`. Walking newest-first means the FIRST time a
    path appears is its latest touch, so `setdefault` is the whole algorithm.
    """
    out = _git(["log", "--format=@%ct", "--name-only", "master",
                "--", "docs/qwen-tasks/"], timeout=120)
    times, ts = {}, 0
    for line in (out or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("@"):
            try:
                ts = int(line[1:])
            except ValueError:
                ts = 0
        elif ts:
            times.setdefault(line, ts)
    return times


def _branch_touch_times():
    """{task_id: {ref: (stage, timestamp)}} for commits NOT in master.

    One `git log --all --not master --source`, which names the ref each commit
    was reached from. `--not master` is what makes this cheap AND correct: a
    commit already in master tells us nothing a branch did that master has not
    got, and those are the overwhelming majority.

    Newest-first again, so the first sighting of a (ref, task) pair is that
    branch's most recent word on it - which is exactly the stage the branch
    currently believes, without listing its tree.
    """
    # `%S` is the source-ref placeholder. `--source` alone only decorates
    # git's DEFAULT format, so with a custom --format the ref silently
    # vanished and every commit was skipped - the whole scan returned empty
    # and every historical regression test went red at once.
    out = _git(["log", "--all", "--not", "master", "--source",
                "--format=@%ct %S", "--name-only", "--",
                "docs/qwen-tasks/"], timeout=180)
    result = {}
    ts, ref = 0, ""
    for line in (out or "").splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("@"):
            # "@1726...\trefs/heads/qwen-worker-2-r30" - --source appends the
            # ref to the format line, separated by whitespace.
            head = line[1:].split(None, 1)
            try:
                ts = int(head[0])
            except (ValueError, IndexError):
                ts = 0
            ref = head[1].strip() if len(head) > 1 else ""
            for prefix in ("refs/remotes/", "refs/heads/"):
                if ref.startswith(prefix):
                    ref = ref[len(prefix):]
                    break
            continue
        if not ts or not ref or ref in ("master", "origin/master"):
            continue
        stage, task_id = _stage_and_task(line.strip())
        if not task_id:
            continue
        result.setdefault(task_id, {}).setdefault(ref, (stage, ts))
    return result


def _classify_branch_tasks_uncached():
    """Separate the two questions the old code conflated.

    Question 1 - IS A WORKER RUNNING ON THIS TASK?
        Answered by claims (held_claims) AND by finding branches that have
        moved a task file PAST what master shows, with a NEWER commit. A
        branch whose file is in a different stage than master's, touched more
        recently on the branch, has produced real work that must not be
        dispatched again. This is the TASK-139-through-143 protection.

    Question 2 - HAS A BRANCH PRODUCED A RESULT NOBODY INTEGRATED?
        Same mechanism, reported separately. A task in TODO on master whose
        branch copy is in DONE or REVIEW with a newer timestamp is finished
        work waiting for Claude. The pool must not dispatch it again.

    What changed from the old _claimed_on_a_branch
    -------------------------------------------------
    The old code asked "is this file NOT in TODO on some branch?" and that
    hid tasks: five branches forked from a BLOCKED master all inherited
    BLOCKED, and when master moved the task to TODO the branches still said
    BLOCKED - which the old code read as 'not in TODO, therefore worked on'
    and hid the task permanently. (TASK-183, measured 2026-09-16.)

    The new code compares each branch against master's CURRENT stage for the
    same task. A branch that has the file in the SAME stage master has it in
    has done nothing. A branch in a DIFFERENT stage is then resolved by
    commit timestamp: whoever touched the file more recently moved it. Master
    moved TASK-183 from BLOCKED to TODO; its timestamp is newer; the branches
    are stale and the task is available again.

    Re-queue rule
    -------------
    When master moves a task backwards - BLOCKED to TODO, REVIEW to REWORK -
    every existing branch is stale about it. The commit timestamp on master's
    new path is newer than any branch's timestamp for the old path, so the
    branch loses the comparison and the task becomes available. A timestamp
    is the right signal here because it is the only ordering that survives a
    force-free workflow: branches cannot rewrite master's history, and
    master's move is always a new commit with a later timestamp than the
    branch's inherited copy.

    Returns (active, stale_reports):
        active: set of task_ids with real work on a branch (do not dispatch)
        stale_reports: list of dicts describing tasks hidden by stale branches
    """
    master_files = _task_files_on("master")
    if not master_files:
        return {}, {}, []

    awaiting = {}
    recoverable = {}
    stale = {}

    # TWO GIT CALLS, NOT TENS OF THOUSANDS.
    #
    # The straightforward shape of this loop - for every branch, for every
    # task, ask git when each side last touched the file - ran one `ls-tree`
    # per ref and two `log` calls per (branch, task) pair. With 270 refs and
    # ~190 tasks that is tens of thousands of subprocesses: measured
    # 2026-09-16 at over 100 seconds for ONE call, against a `pool.sh` sweep
    # that calls `--status` about sixteen times. Sweeps stopped finishing.
    #
    # `_master_touch_times` and `_branch_touch_times` get the same facts in
    # one `git log` each. The stage is read off the PATH rather than from a
    # tree listing, because `docs/qwen-tasks/<STAGE>/TASK-nnn-*.md` already
    # carries it - so no `ls-tree` per ref is needed at all.
    master_ts_by_path = _master_touch_times()
    branch_latest = _branch_touch_times()

    for task_id, (master_stage, master_path) in master_files.items():
        master_ts = master_ts_by_path.get(master_path, 0)
        for branch, (branch_stage, branch_ts) in sorted(
                branch_latest.get(task_id, {}).items()):
            if branch_stage == master_stage:
                continue
            if branch_ts > master_ts:
                if branch_stage in TERMINAL_BRANCH_STAGES:
                    awaiting.setdefault(task_id, [branch, branch_stage])
                else:
                    recoverable.setdefault(task_id, [branch, branch_stage])
            elif master_ts > 0:
                if task_id not in stale:
                    stale[task_id] = {
                        "master_stage": master_stage, "branches": []}
                stale[task_id]["branches"].append((branch, branch_stage))

    # AWAITING WINS OVER RECOVERABLE. A task can have one branch in REVIEW and
    # another still in RUNNING - the overnight double dispatches produced
    # exactly that. If ANY branch holds a finished result, the implementation
    # must not be handed out again, whatever another branch's stage says.
    for task_id in list(recoverable):
        if task_id in awaiting:
            del recoverable[task_id]

    stale_list = []
    for task_id in sorted(stale):
        info = stale[task_id]
        stale_list.append({
            "task": task_id,
            "master_stage": info["master_stage"],
            "branches": info["branches"],
        })
    return awaiting, recoverable, stale_list


def _claimed_on_a_branch():
    """The task_ids a branch may legitimately hide: a finished RESULT exists.

    SEMANTICS CHANGED 2026-09-27, and the change is the point. This used to
    return every task any branch had moved past master, which conflated "a
    worker is working on this" with "a branch from three weeks ago still has an
    old copy". Measured that morning: 134 of 143 TODO tasks were excluded this
    way, 114 of them because a branch held a finished REVIEW or DONE result and
    only 13 because a branch said RUNNING - and the pool reported ZERO ready
    tasks for hours while twelve workers polled an empty queue.

    Branch state is an ARTIFACT, never liveness. A held claim is the only
    positive evidence that work is active, and `ready_tasks` applies that
    separately. So this now returns ONLY the awaiting-integration set: tasks
    whose result already exists and must not be implemented twice. A branch
    saying RUNNING with no claim behind it is a dead run, and its task is
    recoverable rather than hidden.

    The name is kept because pool.sh references it in comments and
    task_registry.py may call it. Do not remove."""
    awaiting, _recoverable, _stale = _classify_branch_tasks()
    return set(awaiting)


def classification():
    """(awaiting, recoverable, stale) for callers that want the whole picture.

    `--status` uses this so the integration backlog is visible rather than
    silently subtracted. 114 finished results nobody has merged is the single
    biggest fact about this pool's throughput, and the old report never said it.
    """
    return _classify_branch_tasks()


def _parse_task_header(filepath):
    """Parse structured fields from a task file's header.

    Returns a dict of the fields found. Recognised fields:
        STATUS: BLOCKED          -> {"status": "BLOCKED"}
        ABSORBED_BY: TASK-nnn    -> {"absorbed_by": "TASK-nnn"}

    Only the leading block of KEY: VALUE lines before the first blank line
    or heading is parsed. A task file without these fields is unaffected -
    the dict is simply empty. Prose is never interpreted as a field."""
    result = {}
    try:
        with open(filepath, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    break
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip().upper().replace("-", "_")
                    value = value.strip()
                    if key == "STATUS" and value:
                        result["status"] = value.upper()
                    elif key == "ABSORBED_BY" and value:
                        result["absorbed_by"] = value.strip()
    except Exception:
        pass
    return result


def _done_task_ids():
    """Set of task IDs currently in the DONE directory."""
    done_dir = os.path.join(MAIN_REPO, "docs", "qwen-tasks", "DONE")
    if not os.path.isdir(done_dir):
        return set()
    return {f.split("-")[0] + "-" + f.split("-")[1]
            for f in os.listdir(done_dir) if f.startswith("TASK-")}


def ready_tasks(active_on_branch=None):
    """READY = in TODO, no held claim, no finished result on a branch, deps met,
    not self-blocked, not absorbed by a finished task.
    Sorted by the registry's priority (P0 first), then by task id.

    THE ONLY LIVENESS AUTHORITY HERE IS A HELD CLAIM. A branch that says
    RUNNING proves nothing about whether a worker exists: the overnight runs
    that died left RUNNING behind on their branches, and treating that as
    "someone is working on it" is what held 134 of 143 tasks out of the queue.
    A branch can still legitimately hide a task, but only by holding a finished
    RESULT (REVIEW or DONE) that would be duplicated if the task were handed
    out again - and that is an integration job, not a dispatch.

    *active_on_branch* is that awaiting-integration set (from
    `_classify_branch_tasks`, or `_claimed_on_a_branch()` when None). Callers
    that also need the recoverable and stale reports should call
    `classification()` once and pass the awaiting set in, so the branch scan
    runs once rather than twice."""
    todo_dir = os.path.join(MAIN_REPO, "docs", "qwen-tasks", "TODO")
    if not os.path.isdir(todo_dir):
        return []
    if active_on_branch is None:
        active_on_branch = _claimed_on_a_branch()
    claimed = {c["task"] for c in held_claims()} | active_on_branch
    reg = {}
    if os.path.exists(REGISTRY):
        try:
            with open(REGISTRY, encoding="utf-8") as fh:
                reg = {t["task"]: t for t in json.load(fh).get("tasks", [])}
        except Exception:
            reg = {}
    done = _done_task_ids()

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
        header = _parse_task_header(os.path.join(todo_dir, fn))
        if header.get("status") == "BLOCKED":
            continue
        absorbed = header.get("absorbed_by")
        if absorbed and absorbed in done:
            continue
        out.append((meta.get("priority", "P4"), tid, fn))
    out.sort()
    return out


def _format_stale_report(stale_reports):
    """Human-readable lines describing tasks hidden by stale branches.

    Silence is what cost a night (TASK-183). Every stale task gets a line
    that names it, says what master has, what the branches have, and how
    many branches are stale."""
    if not stale_reports:
        return []
    lines = ["stale branches hiding available tasks: %d" % len(stale_reports)]
    for report in stale_reports:
        tid = report["task"]
        master_stage = report["master_stage"]
        branches = report["branches"]
        stage_counts = {}
        for _br, stage in branches:
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        stage_parts = ", ".join("%s on %d branch%s" % (s, n, "es" if n != 1 else "")
                                for s, n in sorted(stage_counts.items()))
        lines.append("  %s is %s on master; %s (stale)"
                      % (tid, master_stage, stage_parts))
    return lines


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
        awaiting, _recoverable, _stale = _classify_branch_tasks()
        for _prio, tid, fn in ready_tasks(active_on_branch=set(awaiting)):
            if claim(tid, a.worker) == CLAIM_OK:
                print("FILE %s" % fn)
                return CLAIM_OK
        print("NO READY TASK")
        return CLAIM_TAKEN
    if a.status or True:
        # OUTPUT ORDER AND INDENTATION ARE A CONTRACT, not cosmetics. pool.sh
        # and pool_watchdog.sh parse this text: `busy()` and `busy_count()`
        # grep the whole output for " <worker> ", `next_ready()` awk-matches
        # `^  P[0-4]` after the first line starting with "ready",
        # `release_stale_claims` reads `^  TASK-` immediately after
        # "claims held" and stops at the first line that is not, and two
        # callers grep the exact string "ready (unclaimed, deps met): N".
        # So: claims first with two-space indent, then the ready block, then
        # everything new AFTER it at four-space indent, and no worker name is
        # ever printed outside the claims block.
        cl = held_claims()
        print("claims held: %d" % len(cl))
        for c in cl:
            print("  %-10s %-12s pid=%-7s %s"
                  % (c.get("task"), c.get("worker"), c.get("pid"), c.get("claimed_at")))
        awaiting, recoverable, stale_reports = _classify_branch_tasks()
        rd = ready_tasks(active_on_branch=set(awaiting))
        print("ready (unclaimed, deps met): %d" % len(rd))
        ready_ids = {tid for _p, tid, _f in rd}
        for prio, tid, _fn in rd:
            print("  %-4s %s" % (prio, tid))
        print("awaiting integration (a result exists on a branch): %d"
              % len(awaiting))
        for tid in sorted(awaiting):
            branch, stage = awaiting[tid][0], awaiting[tid][1]
            print("    %s %s on %s" % (tid, stage, branch))
        recovered_now = sorted(t for t in recoverable if t in ready_ids)
        print("recoverable (branch stage with no live claim): %d" % len(recoverable))
        for tid in sorted(recoverable):
            branch, stage = recoverable[tid][0], recoverable[tid][1]
            mark = "" if tid in ready_ids else "  (still held back, see above)"
            print("    %s %s on %s%s" % (tid, stage, branch, mark))
        print("recovered into the ready queue: %d" % len(recovered_now))
        for line in _format_stale_report(stale_reports):
            print(line)
        return CLAIM_OK


if __name__ == "__main__":
    sys.exit(main())
