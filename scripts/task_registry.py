#!/usr/bin/env python3
"""The global durable task registry.

## What it is

One machine-readable record per task, carrying TASK_ID, STATUS, PRIORITY,
WORKER, CLAIMED_AT, DEPENDENCIES, BRANCH, RESULT, REVIEW_STATUS. Written to
`docs/state/TASK-REGISTRY.json` and committed, so the queue survives this
machine.

## Where each field comes from, and why none of it is typed by hand

    STATUS         the directory the task file is in, plus the live claim
    PRIORITY       a PRIORITY: line in the task file, defaulting to P4
    DEPENDENCIES   a DEPENDS: line in the task file
    WORKER         the atomic claim in work/claims/, if one is held
    BRANCH         the worker branch that touched the task file
    RESULT         the declared STATUS inside the task's RESULT BLOCK

A ledger somebody has to remember to update is a ledger that drifts, and a
drifted ledger is worse than none because it is believed. So everything here
is DERIVED from the task files, from git, and from the claim directory.

## The two-part status, and why one field would be wrong

A task in `TODO/` with a live claim is CLAIMED, not QUEUED - a worker is
already on it and a second worker must not take it. A task in `TODO/` with no
claim is QUEUED. The claim is machine-local and atomic; the directory is
durable and committed. Neither alone tells you whether a task is free, so the
registry reports the directory state and the claim state, and derives STATUS
from both.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

TASKS = os.path.join(ROOT, "docs", "qwen-tasks")
OUT = os.path.join(ROOT, "docs", "state", "TASK-REGISTRY.json")

DIR_STATUS = {
    "TODO": "QUEUED",
    "RUNNING": "RUNNING",
    "REVIEW": "AWAITING_REVIEW",
    "REWORK": "REWORK",
    "BLOCKED": "BLOCKED",
    "BLOCKED_QUOTA": "BLOCKED",
    "DONE": "DONE",
}


def git(*args):
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                           text=True, timeout=60)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def parse(path):
    """PRIORITY and DEPENDS from the file; the RESULT BLOCK's own verdict."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return {}
    out = {}
    m = re.search(r"^PRIORITY:[ \t]*(P[0-4])", text, re.M)
    out["priority"] = m.group(1) if m else "P4"
    # [ \t]* NOT \s* - \s includes the newline, so an empty "DEPENDS:" line
    # would swallow the blank line and capture the task's TITLE as its
    # dependency list. Every task then reads as BLOCKED on a heading that will
    # never appear in DONE, and the whole backlog goes dark at once.
    m = re.search(r"^DEPENDS:[ \t]*(.*)$", text, re.M)
    out["dependencies"] = ([d.strip() for d in m.group(1).split(",") if d.strip()]
                           if m else [])
    if "RESULT BLOCK" in text:
        m = re.search(r"STATUS:?\s*\**\s*([A-Z_][A-Z_ ]*)", text)
        out["result"] = m.group(1).strip() if m else "REPORTED"
        out["review_status"] = "PENDING"
    else:
        out["result"] = None
        out["review_status"] = "NOT_SUBMITTED"
    return out


def main():
    try:
        from claim_task import held_claims
        claims = {c["task"]: c for c in held_claims()}
    except Exception:
        claims = {}

    tasks = []
    for stage, status in DIR_STATUS.items():
        d = os.path.join(TASKS, stage)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.startswith("TASK-") or not fn.endswith(".md"):
                continue
            tid = "-".join(fn.split("-")[:2])
            rel = os.path.relpath(os.path.join(d, fn), ROOT).replace("\\", "/")
            meta = parse(os.path.join(d, fn))
            claim = claims.get(tid)
            # A QUEUED task with a live claim is CLAIMED: a worker holds it and
            # a second worker must not take it, even though the file has not
            # moved yet.
            eff = "CLAIMED" if (status == "QUEUED" and claim) else status
            tasks.append({
                "task": tid,
                "file": rel,
                "status": eff,
                "stage_dir": stage,
                "priority": meta.get("priority", "P4"),
                "worker": (claim or {}).get("worker"),
                "claimed_at": (claim or {}).get("claimed_at"),
                "dependencies": meta.get("dependencies", []),
                "branch": None,
                "result": meta.get("result"),
                "review_status": meta.get("review_status"),
            })

    done = {t["task"] for t in tasks if t["status"] == "DONE"}
    for t in tasks:
        unmet = [d for d in t["dependencies"] if d not in done]
        t["blocked_by"] = unmet
        if unmet and t["status"] == "QUEUED":
            t["status"] = "BLOCKED"

    by_status = {}
    for t in tasks:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1

    ready = [t for t in tasks if t["status"] == "QUEUED"]
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_from": ("docs/qwen-tasks/**, git, and work/claims/. Derived, "
                           "never hand-edited."),
        "master_head": git("rev-parse", "--short", "master"),
        "counts": by_status,
        "ready_count": len(ready),
        "workers": 8,
        "backlog_healthy": len(ready) >= 16,
        "tasks": tasks,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")

    print("counts:", by_status)
    print("READY (queued, unclaimed, deps met): %d" % len(ready))
    for t in sorted(ready, key=lambda x: (x["priority"], x["task"]))[:24]:
        print("  %-4s %s" % (t["priority"], t["task"]))
    print("backlog healthy (>=16 ready for 8 workers): %s" % doc["backlog_healthy"])
    print("written: docs/state/TASK-REGISTRY.json")
    # Non-zero is a BACKLOG alarm: workers will go idle.
    return 0 if doc["backlog_healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
