#!/usr/bin/env python3
"""One command, one picture of the pool.

## What this answers

Every status report needs: workers running, tasks running, tasks queued, and
the reason for any idle worker. Before this script, that was assembled by hand
from `claim_task.py --status`, `git log`/`git status` across twelve worktrees,
and reading pool-logs by eye. Slow, and only as accurate as the person doing
it remembered to check.

## What it reports

    workers         For each of the 12 known worktrees: idle or busy, current
                    task id (if busy), current branch, whether its HEAD matches
                    origin/master (a worker whose branch is NOT cleanly based
                    on origin/master is a finding, not silence).
    glm_tasks       Currently-running or recently-completed GLM verification
                    and checkpoint tasks, identified by filename pattern, with
                    their disposition (PASS/FAIL/pending) if finished.
    queue           Ready count, ready task ids with priority, and the gap
                    between idle workers and ready tasks.
    idle_reasons    For each idle worker: no ready task, worktree locked, or
                    stale state.
    stale_branches  Count and summary from claim_task.py's stale-branch
                    detector, not the full dump.

## Design choices

- Read-only. No writes to any task file, no claims taken, no provider calls.
- Does not invent a new status vocabulary: reads from the existing
  TODO/RUNNING/REVIEW/DONE/REWORK/BLOCKED states and the registry.
- GLM tasks are identified by filename pattern: any task file containing
  "glm" in its name. This covers both `glm-verify-task-*` and
  `glm-checkpoint-*` naming conventions without a separate registry field.
- Worktree list is the same 12 names pool.sh dispatches to, hardcoded.
  Reading them from a config would add a dependency for no gain: the pool
  and this script must agree on the set, and pool.sh is the authority.

## Usage

    py -3 scripts/pool_status.py            # JSON to stdout
    py -3 scripts/pool_status.py --human    # readable text
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_REPO = os.path.join(os.path.dirname(ROOT), "resonate-group-automation")
if not os.path.isdir(os.path.join(MAIN_REPO, ".git")):
    MAIN_REPO = ROOT

sys.path.insert(0, os.path.join(ROOT, "scripts"))

try:
    import claim_task as _claim_task
    # claim_task resolves its MAIN_REPO from __file__, which points at THIS
    # worktree. Claims live in the MAIN worktree's work/claims/ (the one
    # pool.sh writes to), so we must read from there directly.
    _CLAIMS_DIR = os.path.join(MAIN_REPO, "work", "claims")

    def held_claims():
        if not os.path.isdir(_CLAIMS_DIR):
            return []
        out = []
        for fn in sorted(os.listdir(_CLAIMS_DIR)):
            if not fn.endswith(".claim"):
                continue
            try:
                with open(os.path.join(_CLAIMS_DIR, fn), encoding="utf-8") as fh:
                    out.append(json.load(fh))
            except Exception:
                out.append({"task": fn[:-6], "worker": "?", "unreadable": True})
        return out

    # classification() and ready_tasks() call held_claims() internally.
    # Patch the module's reference so they read from the correct claims dir.
    _claim_task.held_claims = held_claims
    classification = _claim_task.classification
    ready_tasks = _claim_task.ready_tasks
except ImportError:
    held_claims = classification = ready_tasks = None

WORKERS = [
    "resonate-qwen-worker",
    "resonate-qwen-2", "resonate-qwen-3", "resonate-qwen-4",
    "resonate-qwen-5", "resonate-qwen-6", "resonate-qwen-7",
    "resonate-qwen-8", "resonate-qwen-9", "resonate-qwen-10",
    "resonate-qwen-11", "resonate-qwen-12",
]

DESKTOP = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "Desktop")
TASKS_DIR = os.path.join(ROOT, "docs", "qwen-tasks")
LOCKS_DIR = os.path.join(MAIN_REPO, "work", "worktree-locks")


def _git(cwd, args, timeout=15):
    try:
        r = subprocess.run(
            ["git"] + args, cwd=cwd,
            capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _worktree_path(name):
    return os.path.join(DESKTOP, name)


def _worktree_branch(wt_path):
    return _git(wt_path, ["rev-parse", "--abbrev-ref", "HEAD"]) or None


def _worktree_head(wt_path):
    return _git(wt_path, ["rev-parse", "HEAD"]) or None


def _origin_master_sha(wt_path):
    _git(wt_path, ["fetch", "-q", "origin", "master"])
    return _git(wt_path, ["rev-parse", "origin/master"]) or None


def _is_locked(name):
    return os.path.isdir(os.path.join(LOCKS_DIR, name))


def _claims_by_worker():
    if held_claims is None:
        return {}
    out = {}
    for c in held_claims():
        w = c.get("worker")
        if w:
            out[w] = c
    return out


def _scan_worktree_running_tasks(wt_path):
    running_dir = os.path.join(wt_path, "docs", "qwen-tasks", "RUNNING")
    if not os.path.isdir(running_dir):
        return []
    tasks = []
    for fn in sorted(os.listdir(running_dir)):
        if fn.startswith("TASK-") and fn.endswith(".md"):
            tid = "-".join(fn.split("-")[:2])
            tasks.append(tid)
    return tasks


def _worker_status(name, claims_map):
    wt_path = _worktree_path(name)
    info = {
        "worker": name,
        "exists": os.path.isdir(wt_path) or os.path.isfile(os.path.join(wt_path, ".git")),
        "state": "missing",
        "branch": None,
        "task_id": None,
        "on_origin_master": None,
    }
    if not info["exists"]:
        return info

    branch = _worktree_branch(wt_path)
    info["branch"] = branch

    locked = _is_locked(name)
    claim = claims_map.get(name)
    running_tasks = _scan_worktree_running_tasks(wt_path)

    if claim:
        info["state"] = "busy"
        info["task_id"] = claim.get("task")
    elif locked:
        info["state"] = "busy"
        if running_tasks:
            info["task_id"] = running_tasks[0]
    elif running_tasks:
        info["state"] = "busy"
        info["task_id"] = running_tasks[0]
    else:
        info["state"] = "idle"

    head = _worktree_head(wt_path)
    origin_master = _origin_master_sha(wt_path)
    if head and origin_master:
        info["on_origin_master"] = (head == origin_master)

    return info


def _idle_reason(worker_info, ready_count):
    if worker_info["state"] != "idle":
        return None
    if not worker_info["exists"]:
        return "worktree missing"
    if _is_locked(worker_info["worker"]):
        return "worktree locked"
    if ready_count == 0:
        return "no ready task"
    return "awaiting dispatch"


def _scan_glm_tasks():
    glm_tasks = []
    stages = ["TODO", "RUNNING", "REVIEW", "DONE", "REWORK", "BLOCKED"]
    for stage in stages:
        d = os.path.join(TASKS_DIR, stage)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.startswith("TASK-") or not fn.endswith(".md"):
                continue
            if "glm" not in fn.lower():
                continue
            tid = "-".join(fn.split("-")[:2])
            entry = {
                "task": tid,
                "stage": stage,
                "file": fn,
            }
            if stage in ("DONE", "REVIEW", "BLOCKED"):
                entry["disposition"] = _read_glm_disposition(
                    os.path.join(d, fn), stage)
            elif stage == "RUNNING":
                entry["disposition"] = "pending"
            glm_tasks.append(entry)
    return glm_tasks


def _read_glm_disposition(filepath, stage):
    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            text = fh.read(8192)
    except OSError:
        return "unknown"
    if stage == "BLOCKED":
        return "BLOCKED"
    if stage == "DONE":
        return "DONE"
    for line in text.splitlines()[:30]:
        stripped = line.strip().upper()
        if stripped.startswith("STATUS:") or stripped.startswith("VERDICT:"):
            val = line.split(":", 1)[1].strip().upper()
            if "PASS" in val:
                return "PASS"
            if "FAIL" in val:
                return "FAIL"
            if "BLOCKED" in val:
                return "BLOCKED"
    return "pending"


def _queue_info():
    if ready_tasks is None:
        return {"ready_count": 0, "ready_tasks": []}
    awaiting, _recoverable, _stale = classification()
    rd = ready_tasks(active_on_branch=set(awaiting))
    return {
        "ready_count": len(rd),
        "ready_tasks": [
            {"priority": p, "task": tid} for p, tid, _fn in rd
        ],
    }


def _stale_branch_summary():
    if classification is None:
        return {"count": 0, "tasks": []}
    _awaiting, _recoverable, stale_reports = classification()
    return {
        "count": len(stale_reports),
        "tasks": [
            {
                "task": r["task"],
                "master_stage": r["master_stage"],
                "branch_count": len(r["branches"]),
            }
            for r in stale_reports
        ],
    }


def collect_status():
    claims_map = _claims_by_worker()
    queue = _queue_info()
    ready_count = queue["ready_count"]

    workers = []
    for name in WORKERS:
        w = _worker_status(name, claims_map)
        workers.append(w)

    idle_reasons = {}
    for w in workers:
        reason = _idle_reason(w, ready_count)
        if reason:
            idle_reasons[w["worker"]] = reason

    idle_count = sum(1 for w in workers if w["state"] == "idle")
    busy_count = sum(1 for w in workers if w["state"] == "busy")
    stale_branches_not_on_master = sum(
        1 for w in workers
        if w["state"] != "missing" and w.get("on_origin_master") is False
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workers": {
            "total": len(WORKERS),
            "busy": busy_count,
            "idle": idle_count,
            "missing": sum(1 for w in workers if w["state"] == "missing"),
            "stale_branch": stale_branches_not_on_master,
            "details": workers,
        },
        "glm_tasks": _scan_glm_tasks(),
        "queue": queue,
        "idle_reasons": idle_reasons,
        "stale_branches": _stale_branch_summary(),
        "refill_gap": max(0, ready_count - idle_count),
    }


def _format_human(status):
    lines = []
    w = status["workers"]
    lines.append("=== POOL STATUS ===")
    lines.append("generated: %s" % status["generated_at"])
    lines.append("")
    lines.append("workers: %d total, %d busy, %d idle, %d missing, %d stale branch" % (
        w["total"], w["busy"], w["idle"], w["missing"], w["stale_branch"]))
    lines.append("")

    lines.append("--- worker details ---")
    for d in w["details"]:
        task_str = " task=%s" % d["task_id"] if d["task_id"] else ""
        branch_str = " branch=%s" % d["branch"] if d["branch"] else ""
        master_str = ""
        if d.get("on_origin_master") is False:
            master_str = " NOT_ON_ORIGIN_MASTER"
        elif d.get("on_origin_master") is True:
            master_str = " on_origin_master"
        lines.append("  %-26s %-6s%s%s%s" % (
            d["worker"], d["state"], branch_str, task_str, master_str))
    lines.append("")

    lines.append("--- queue ---")
    q = status["queue"]
    lines.append("ready: %d tasks" % q["ready_count"])
    for t in q["ready_tasks"][:20]:
        lines.append("  %-4s %s" % (t["priority"], t["task"]))
    if len(q["ready_tasks"]) > 20:
        lines.append("  ... and %d more" % (len(q["ready_tasks"]) - 20))
    lines.append("refill gap (ready - idle): %d" % status["refill_gap"])
    lines.append("")

    lines.append("--- idle reasons ---")
    if status["idle_reasons"]:
        for worker, reason in sorted(status["idle_reasons"].items()):
            lines.append("  %-26s %s" % (worker, reason))
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("--- GLM tasks ---")
    glm = status["glm_tasks"]
    if glm:
        running = [t for t in glm if t["stage"] == "RUNNING"]
        recent = [t for t in glm if t["stage"] in ("REVIEW", "DONE", "BLOCKED")]
        queued = [t for t in glm if t["stage"] == "TODO"]
        if running:
            lines.append("  running: %d" % len(running))
            for t in running:
                lines.append("    %s" % t["task"])
        if recent:
            lines.append("  completed/blocked: %d" % len(recent))
            for t in recent[:10]:
                lines.append("    %-10s %-8s %s" % (
                    t["task"], t.get("disposition", "?"), t["stage"]))
            if len(recent) > 10:
                lines.append("    ... and %d more" % (len(recent) - 10))
        lines.append("  queued: %d" % len(queued))
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("--- stale branches ---")
    sb = status["stale_branches"]
    lines.append("count: %d" % sb["count"])
    for t in sb["tasks"][:10]:
        lines.append("  %s is %s on master; %d stale branch(es)" % (
            t["task"], t["master_stage"], t["branch_count"]))
    if len(sb["tasks"]) > 10:
        lines.append("  ... and %d more" % (len(sb["tasks"]) - 10))

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Pool status: one command, one picture")
    p.add_argument("--human", action="store_true",
                   help="Human-readable output instead of JSON")
    a = p.parse_args()

    status = collect_status()

    if a.human:
        print(_format_human(status))
    else:
        print(json.dumps(status, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
