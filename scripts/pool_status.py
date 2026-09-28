#!/usr/bin/env python3
"""Machine-derived pool status: one command, one picture.

## What this replaces

Before this script, a status report was assembled by hand from three sources:
`claim_task.py --status`, `git log`/`git status` across twelve worktrees, and
reading pool-logs by eye. Slow, and only as accurate as the person doing it
remembered to check. OPERATING-MODE §30 requires this to be machine-derived.

## What it answers

    workers        For each of the 12 known worktrees: idle or busy, current
                   task id (if busy), current branch, whether its HEAD matches
                   origin/master (a mismatch is a finding, not silence).
    glm_tasks      Currently-running or recently-completed GLM verification
                   tasks (identified by filename containing "glm"), with their
                   stage directory and disposition if finished.
    queue          Ready count, ready task ids with priority, and the ratio of
                   idle workers to ready tasks (the number the standing order's
                   "refill before the queue drops below one ready task per idle
                   worker" rule needs).
    idle_reasons   For each idle worker, WHY: no ready task, worktree locked,
                   or a stale state.
    stale_branches Reuse claim_task.py's stale-branch detector, summarised as
                   a count plus the per-task detail.

## Design decisions

- GLM tasks are identified by filename pattern ("glm" in the task filename),
  not a registry field. The registry has no GLM-specific field, and adding one
  would mean every future GLM task has to remember to set it. A filename
  pattern is what a human reads and what the standing backlog template
  generates, so it is the natural signal.
- Read-only. No writes to any task file, no claims taken, no provider calls.
- Does not invent a new task-status vocabulary: reads from the existing
  TODO/RUNNING/REVIEW/DONE/REWORK/BLOCKED states and the registry.
"""

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import claim_task

#: The 12 known worker worktrees, matching pool.sh's WORKERS array.
WORKERS = [
    "resonate-qwen-worker",
    "resonate-qwen-2", "resonate-qwen-3", "resonate-qwen-4",
    "resonate-qwen-5", "resonate-qwen-6", "resonate-qwen-7",
    "resonate-qwen-8", "resonate-qwen-9", "resonate-qwen-10",
    "resonate-qwen-11", "resonate-qwen-12",
]

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
TASKS_DIR = os.path.join(ROOT, "docs", "qwen-tasks")
LOCKS_DIR = os.path.join(ROOT, "work", "worktree-locks")


def _git_in(cwd, *args, timeout=15):
    """Run a git command in a specific directory. Returns stdout or empty."""
    try:
        r = subprocess.run(
            ["git", "-C", cwd] + list(args),
            capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _worktree_path(worker):
    return os.path.join(DESKTOP, worker)


def _worktree_branch(wt_path):
    """Current branch name in a worktree, or empty string."""
    return _git_in(wt_path, "rev-parse", "--abbrev-ref", "HEAD")


def _worktree_head(wt_path):
    """Current HEAD SHA (short), or empty string."""
    return _git_in(wt_path, "rev-parse", "--short", "HEAD")


def _origin_master_sha():
    """origin/master SHA (short), cached per call."""
    return _git_in(ROOT, "rev-parse", "--short", "origin/master")


def _is_locked(worker):
    """True if the worktree lock directory exists."""
    return os.path.isdir(os.path.join(LOCKS_DIR, worker))


def _claims_by_worker():
    """{worker_name: [claim_dict, ...]} from held_claims()."""
    out = {}
    for c in claim_task.held_claims():
        w = c.get("worker", "")
        out.setdefault(w, []).append(c)
    return out


def _scan_glm_tasks():
    """Find all tasks with 'glm' in the filename across all stage directories.

    Returns a list of dicts: {task, stage, filename, result_status}.
    result_status is extracted from the task file's RESULT BLOCK if present.
    """
    out = []
    for stage in ("TODO", "RUNNING", "REVIEW", "DONE", "REWORK",
                  "BLOCKED", "BLOCKED_QUOTA"):
        d = os.path.join(TASKS_DIR, stage)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.startswith("TASK-") or not fn.endswith(".md"):
                continue
            if "glm" not in fn.lower():
                continue
            tid = "-".join(fn.split("-")[:2])
            result_status = None
            if stage in ("DONE", "REVIEW", "BLOCKED"):
                result_status = _read_result_status(os.path.join(d, fn))
            out.append({
                "task": tid,
                "stage": stage,
                "filename": fn,
                "result_status": result_status,
            })
    return out


def _read_result_status(filepath):
    """Extract STATUS from a task file's RESULT BLOCK, or None."""
    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None
    if "RESULT BLOCK" not in text and "RESULT\n" not in text:
        return None
    import re
    m = re.search(r"STATUS:?\s*\**\s*([A-Z_][A-Z_ ]*)", text)
    return m.group(1).strip() if m else "REPORTED"


def _ready_tasks_list():
    """[(priority, task_id), ...] from claim_task.ready_tasks()."""
    awaiting, _recoverable, _stale = claim_task.classification()
    rd = claim_task.ready_tasks(active_on_branch=set(awaiting))
    return [(prio, tid) for prio, tid, _fn in rd]


def _stale_branch_summary():
    """(count, details_list) from claim_task.classification()."""
    _awaiting, _recoverable, stale = claim_task.classification()
    return len(stale), stale


def collect():
    """Build the full status document. Returns a dict."""
    claims_by_w = _claims_by_worker()
    origin_master = _origin_master_sha()
    ready = _ready_tasks_list()
    ready_ids = [tid for _p, tid in ready]
    stale_count, stale_details = _stale_branch_summary()
    glm_tasks = _scan_glm_tasks()

    workers = []
    idle_workers = []
    for w in WORKERS:
        wt_path = _worktree_path(w)
        exists = os.path.isdir(wt_path) and (
            os.path.isdir(os.path.join(wt_path, ".git"))
            or os.path.isfile(os.path.join(wt_path, ".git"))
        )
        locked = _is_locked(w) if exists else False
        w_claims = claims_by_w.get(w, [])
        busy = locked or bool(w_claims)
        task_id = w_claims[0].get("task") if w_claims else None
        branch = _worktree_branch(wt_path) if exists else ""
        head = _worktree_head(wt_path) if exists else ""
        on_master = (head == origin_master) if (head and origin_master) else None

        info = {
            "worker": w,
            "exists": exists,
            "status": "busy" if busy else "idle",
            "task": task_id,
            "branch": branch,
            "head": head,
            "on_master": on_master,
            "locked": locked,
        }
        workers.append(info)
        if not busy:
            idle_workers.append(info)

    idle_reasons = []
    for info in idle_workers:
        w = info["worker"]
        if not info["exists"]:
            reason = "worktree missing"
        elif info["locked"]:
            reason = "worktree locked"
        elif not ready:
            reason = "no ready task"
        else:
            reason = "not dispatched (pool sweep needed)"
        idle_reasons.append({"worker": w, "reason": reason})

    glm_active = [t for t in glm_tasks if t["stage"] in ("TODO", "RUNNING")]
    glm_finished = [t for t in glm_tasks
                    if t["stage"] in ("DONE", "REVIEW", "BLOCKED")]

    return {
        "workers": workers,
        "busy_count": sum(1 for w in workers if w["status"] == "busy"),
        "idle_count": len(idle_workers),
        "glm_tasks": {
            "active": glm_active,
            "finished": glm_finished,
            "total": len(glm_tasks),
        },
        "queue": {
            "ready_count": len(ready),
            "ready": [{"priority": p, "task": t} for p, t in ready],
            "idle_workers": len(idle_workers),
            "ratio": (len(ready) / len(idle_workers)
                      if idle_workers else len(ready)),
        },
        "idle_reasons": idle_reasons,
        "stale_branches": {
            "count": stale_count,
            "details": stale_details,
        },
    }


def format_human(doc):
    """Human-readable output."""
    lines = []
    lines.append("=== POOL STATUS ===")
    lines.append("")

    lines.append("workers: %d busy, %d idle (of %d)"
                 % (doc["busy_count"], doc["idle_count"], len(doc["workers"])))
    for w in doc["workers"]:
        mark = "BUSY" if w["status"] == "busy" else "idle"
        task = w["task"] or "-"
        branch = w["branch"] or "?"
        master_mark = ""
        if w["on_master"] is False:
            master_mark = "  ** NOT on origin/master **"
        elif w["on_master"] is None and w["exists"]:
            master_mark = "  (cannot determine)"
        elif not w["exists"]:
            mark = "MISSING"
        lines.append("  %-26s %-7s task=%-10s branch=%-30s%s"
                     % (w["worker"], mark, task, branch, master_mark))
    lines.append("")

    glm = doc["glm_tasks"]
    lines.append("glm_tasks: %d total (%d active, %d finished)"
                 % (glm["total"], len(glm["active"]), len(glm["finished"])))
    for t in glm["active"]:
        lines.append("  %-10s %-8s %s" % (t["task"], t["stage"], t["filename"]))
    for t in glm["finished"]:
        verdict = t["result_status"] or "no result block"
        lines.append("  %-10s %-8s verdict=%s" % (t["task"], t["stage"], verdict))
    lines.append("")

    q = doc["queue"]
    lines.append("queue: %d ready, %d idle workers, ratio=%.1f ready/idle"
                 % (q["ready_count"], q["idle_workers"], q["ratio"]))
    for item in q["ready"][:24]:
        lines.append("  %-4s %s" % (item["priority"], item["task"]))
    if len(q["ready"]) > 24:
        lines.append("  ... and %d more" % (len(q["ready"]) - 24))
    lines.append("")

    if doc["idle_reasons"]:
        lines.append("idle_reasons:")
        for ir in doc["idle_reasons"]:
            lines.append("  %-26s %s" % (ir["worker"], ir["reason"]))
    else:
        lines.append("idle_reasons: (all workers busy)")
    lines.append("")

    sb = doc["stale_branches"]
    lines.append("stale_branches: %d" % sb["count"])
    for detail in sb["details"][:10]:
        tid = detail["task"]
        ms = detail["master_stage"]
        branches = detail["branches"]
        parts = []
        for br, st in branches[:3]:
            parts.append("%s=%s" % (br, st))
        suffix = "..." if len(branches) > 3 else ""
        lines.append("  %s is %s on master; %s%s"
                     % (tid, ms, ", ".join(parts), suffix))
    if len(sb["details"]) > 10:
        lines.append("  ... and %d more" % (len(sb["details"]) - 10))

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(
        description="Machine-derived pool status (OPERATING-MODE §30)")
    p.add_argument("--human", action="store_true",
                   help="Human-readable output (default is JSON)")
    p.add_argument("--json", action="store_true",
                   help="JSON output (the default)")
    a = p.parse_args()

    doc = collect()

    if a.human:
        print(format_human(doc))
    else:
        print(json.dumps(doc, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
