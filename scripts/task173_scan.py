#!/usr/bin/env python3
"""Three-way task visibility report.

## The disagreement this exposes

On 2026-09-16 three artefacts disagreed about every task:

    master's TODO/       said a task was available
    _claimed_on_a_branch said a worker had already moved it
    TASK-REGISTRY.json   said it was QUEUED

All three were right about different things. This script prints all three
answers per task, names the disagreement, and counts it.

## What UNINTEGRATED means

A task whose file is in TODO or RUNNING on master, but in REVIEW or DONE on
at least one remote branch, is UNINTEGRATED. The work exists; it has been
pushed; master has not absorbed it. The registry cannot see it because the
registry reads master's directories alone.

## Usage

    py -3 scripts/task173_scan.py                  # full report
    py -3 scripts/task173_scan.py --unintegrated    # only the disagreeing set
    py -3 scripts/task173_scan.py --prune           # safe-to-prune branches
"""

import json
import os
import re
import subprocess
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(ROOT, "docs", "qwen-tasks")
STAGES = ("TODO", "RUNNING", "REVIEW", "REWORK", "BLOCKED", "BLOCKED_QUOTA", "DONE")


def git(*args, timeout=120):
    try:
        r = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def task_id(filename):
    m = re.match(r"(TASK-\d+)", filename)
    return m.group(1) if m else filename


def master_task_map():
    """Build a map of task_id -> (stage, filename) from master's working tree."""
    result = {}
    for stage in STAGES:
        d = os.path.join(TASKS, stage)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.startswith("TASK-") and fn.endswith(".md"):
                tid = task_id(fn)
                result[tid] = (stage, fn)
    return result


def branch_task_map(ref):
    """For one branch ref, get task_id -> (stage, filepath).
    ONE ls-tree call per branch, not per task."""
    tree = git("ls-tree", "-r", "--name-only", ref, "docs/qwen-tasks/")
    result = {}
    if not tree:
        return result
    for line in tree.splitlines():
        path = line.strip().replace("\\", "/")
        if not path or not path.endswith(".md"):
            continue
        base = os.path.basename(path)
        if not base.startswith("TASK-"):
            continue
        tid = task_id(base)
        parts = path.split("/")
        stage = None
        for p in parts:
            if p in STAGES:
                stage = p
                break
        result[tid] = (stage or "UNKNOWN", path)
    return result


def read_file_at_ref(ref, filepath):
    """Read a file's content at a specific git ref."""
    return git("show", "%s:%s" % (ref, filepath))


def extract_result_status(content):
    """Extract STATUS from a RESULT BLOCK or RESULT section, or None.
    Some tasks write '## RESULT BLOCK', others write '## RESULT' - both
    are result sections and both carry a STATUS line."""
    if not content:
        return None
    if "RESULT BLOCK" not in content and "## RESULT" not in content:
        return None
    m = re.search(r"STATUS:?\s*\**\s*([A-Z_][A-Z_ ]*)", content)
    return m.group(1).strip() if m else "REPORTED"


def get_remote_refs():
    """Get all remote-tracking refs, excluding master and HEAD."""
    refs = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/")
    out = []
    for ref in refs.splitlines():
        ref = ref.strip()
        if not ref or ref in ("origin/master", "origin/HEAD") or ref.endswith("/HEAD"):
            continue
        out.append(ref)
    return out


def full_scan():
    """Scan all branches efficiently.
    Returns: master_map, {ref: branch_map}, all_task_ids"""
    master_map = master_task_map()
    refs = get_remote_refs()

    # Collect all task IDs from master
    all_tids = set(master_map.keys())

    # Scan each branch - one ls-tree per branch
    branch_maps = {}
    for ref in refs:
        bmap = branch_task_map(ref)
        branch_maps[ref] = bmap
        all_tids.update(bmap.keys())

    return master_map, branch_maps, sorted(all_tids)


CODE_DIRS = ("src/", "scripts/", "tests/")


def code_already_on_master(ref):
    """Does this branch carry any CODE that master does not already have?

    ## WHY THIS EXISTS, AND IT IS THE DIFFERENCE BETWEEN A REPORT AND A
    ## REGRESSION

    Everything above compares the TASK FILE'S STAGE - TODO on master, DONE on
    a branch - and never looks at the code. A task whose work is already
    integrated therefore still reports UNINTEGRATED, and the obvious response
    to that report is to merge the branch.

    Measured 2026-09-21: SIX of twelve reported tasks were already
    integrated. TASK-229's three files are byte-identical on master and on
    its branch, and merging it would have deleted 12,487 lines of later work.
    TASK-232 was worse than that - its branch carries an older
    `stoppedcause.py` that classifies from the events feed, while master
    carries a newer one with the `NEVER_CONTACTED` outcome that actually
    answers the question. Merging on this report's word would have deleted
    the classification that works and restored the one that provably cannot.

    So a branch whose every code blob already matches master is INTEGRATED,
    whatever its task file says. Compared by blob hash rather than by diff:
    two files are the same file when git says they are the same object, and
    a diff against a merge base answers a different question.

    A branch that cannot be read answers False - unknown is not integrated,
    and the fail-closed direction here is to keep reporting it.
    """
    try:
        out = git("diff", "--name-only", "master...%s" % ref)
    except Exception:
        return False
    paths = [f.strip() for f in out.splitlines()
             if f.strip() and f.strip().startswith(CODE_DIRS)]
    if not paths:
        return True                      # task file only: nothing to integrate
    for path in paths:
        try:
            on_master = git("rev-parse", "master:%s" % path)
            on_branch = git("rev-parse", "%s:%s" % (ref, path))
        except Exception:
            return False
        if not on_master or on_master != on_branch:
            return False
    return True


def check_result_blocks(master_map, branch_maps, unintegrated_tids):
    """For unintegrated tasks only, read the file content on the relevant
    branches to check result blocks. Minimises git show calls."""
    results = {}  # (tid, ref) -> (has_result, status)
    for tid in unintegrated_tids:
        for ref, bmap in branch_maps.items():
            if tid not in bmap:
                continue
            stage, filepath = bmap[tid]
            if stage not in ("REVIEW", "DONE"):
                continue
            content = read_file_at_ref(ref, filepath)
            has_result = content and ("RESULT BLOCK" in content or "## RESULT" in content)
            status = extract_result_status(content)
            results[(tid, ref)] = (has_result, status)
    return results


def full_report(unintegrated_only=False):
    """Print the three-way report."""
    master_map, branch_maps, all_tids = full_scan()

    # Build per-task branch locations
    task_branches = defaultdict(dict)  # tid -> {ref: stage}
    for ref, bmap in branch_maps.items():
        for tid, (stage, _path) in bmap.items():
            task_branches[tid][ref] = stage

    # Determine unintegrated set
    unintegrated_tids = set()
    integrated_anyway = {}
    for tid in all_tids:
        master_stage = master_map.get(tid, (None,))[0]
        if master_stage in ("TODO", "RUNNING", None):
            for ref, stage in task_branches.get(tid, {}).items():
                if stage in ("REVIEW", "DONE"):
                    # THE CODE DECIDES, NOT THE TASK FILE. See
                    # `code_already_on_master`.
                    if code_already_on_master(ref):
                        integrated_anyway.setdefault(tid, ref)
                        continue
                    unintegrated_tids.add(tid)
                    break

    # Check result blocks only for unintegrated tasks
    result_blocks = check_result_blocks(master_map, branch_maps, unintegrated_tids)

    # Print report
    print("=" * 78)
    print("THREE-WAY TASK VISIBILITY REPORT")
    print("=" * 78)
    print("Master HEAD: %s" % git("rev-parse", "--short", "master"))
    print("Remote branches scanned: %d" % len(branch_maps))
    print("Total tasks known (master + all branches): %d" % len(all_tids))
    master_todo = sum(1 for s, _ in master_map.values() if s == "TODO")
    print("Tasks in master TODO: %d" % master_todo)
    print("UNINTEGRATED tasks: %d" % len(unintegrated_tids))
    if integrated_anyway:
        print("ALREADY INTEGRATED despite the task file saying otherwise: %d"
              % len(integrated_anyway))
        for tid, ref in sorted(integrated_anyway.items()):
            print("  %s  every code blob matches master (%s)"
                  % (tid, ref.replace("origin/", "")))
        print("  Move the task file to DONE. DO NOT MERGE these - the branch "
              "is older than master.")
    print()

    if unintegrated_only:
        tids_to_show = sorted(unintegrated_tids)
        print("--- UNINTEGRATED TASKS ONLY ---")
        print()
    else:
        tids_to_show = all_tids

    for tid in tids_to_show:
        master_stage = master_map.get(tid, (None, None))[0] or "ABSENT"
        branches = task_branches.get(tid, {})
        is_unint = tid in unintegrated_tids

        print("  %s" % tid)
        print("    master: %s" % master_stage)
        if branches:
            for bref in sorted(branches):
                stage = branches[bref]
                result_tag = ""
                key = (tid, bref)
                if key in result_blocks:
                    has_res, res_status = result_blocks[key]
                    if has_res:
                        result_tag = " [RESULT: %s]" % (res_status or "?")
                print("    %-45s -> %s%s" % (bref, stage, result_tag))
        else:
            print("    (no branch has this task)")
        if is_unint:
            print("    >>> UNINTEGRATED <<<")
        print()

    if not unintegrated_only:
        print("=" * 78)
        print("SUMMARY")
        print("=" * 78)

    if unintegrated_tids:
        print("UNINTEGRATED work exists. These tasks are finished on branches")
        print("but master still shows them as available:")
        for tid in sorted(unintegrated_tids):
            master_stage = master_map.get(tid, (None,))[0] or "ABSENT"
            finished = [b for b, s in task_branches.get(tid, {}).items()
                        if s in ("REVIEW", "DONE")]
            print("  %s (master: %s, finished on: %s)"
                  % (tid, master_stage, ", ".join(sorted(finished))))
    else:
        print("No unintegrated work detected. All branches agree with master.")

    return sorted(unintegrated_tids)


def ancestry_proof(branch_ref):
    """Prove whether every commit on branch_ref is reachable from master.
    Uses git merge-base --is-ancestor as the task requires."""
    ahead = git("rev-list", "--count", "master..%s" % branch_ref)
    try:
        ahead_n = int(ahead) if ahead else 0
    except ValueError:
        ahead_n = -1

    # Verify with merge-base --is-ancestor
    r = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch_ref, "master"],
        cwd=ROOT, capture_output=True, text=True, timeout=30)
    is_ancestor = r.returncode == 0

    return {
        "commits_ahead_of_master": ahead_n,
        "all_commits_reachable_from_master": ahead_n == 0,
        "is_ancestor_of_master": is_ancestor,
        "safe_to_prune": ahead_n == 0 and is_ancestor,
    }


def prune_report():
    """List branches safe to prune, with ancestry proof per branch."""
    refs = get_remote_refs()
    safe = []
    unsafe = []

    for ref in refs:
        proof = ancestry_proof(ref)
        entry = {"branch": ref, "proof": proof}

        if proof["safe_to_prune"]:
            safe.append(entry)
        else:
            # Check if it carries unmerged work in non-TODO stages
            bmap = branch_task_map(ref)
            has_non_todo = any(s in ("REVIEW", "DONE", "RUNNING", "REWORK")
                               for s, _ in bmap.values())
            entry["carries_non_todo_work"] = has_non_todo
            # Name the tasks it carries
            non_todo_tasks = [tid for tid, (s, _) in bmap.items()
                              if s in ("REVIEW", "DONE", "RUNNING", "REWORK")]
            entry["unmerged_tasks"] = sorted(non_todo_tasks)
            unsafe.append(entry)

    print("=" * 78)
    print("BRANCH PRUNE REPORT")
    print("=" * 78)
    print("Master HEAD: %s" % git("rev-parse", "--short", "master"))
    print()
    print("SAFE TO PRUNE (%d branches):" % len(safe))
    print("Every commit on these branches is reachable from master.")
    print("Proof: git merge-base --is-ancestor <branch> master => true")
    print()
    for entry in sorted(safe, key=lambda e: e["branch"]):
        p = entry["proof"]
        print("  %-45s  ahead=%d  ancestor=yes"
              % (entry["branch"], p["commits_ahead_of_master"]))

    print()
    print("NOT SAFE TO PRUNE (%d branches):" % len(unsafe))
    print("These carry commits NOT reachable from master.")
    print()
    for entry in sorted(unsafe, key=lambda e: e["branch"]):
        p = entry["proof"]
        carries = entry.get("carries_non_todo_work", False)
        flag = " [HAS UNMERGED WORK]" if carries else ""
        tasks = entry.get("unmerged_tasks", [])
        task_info = " tasks: %s" % ", ".join(tasks) if tasks else ""
        print("  %-45s  ahead=%d  ancestor=no%s%s"
              % (entry["branch"], p["commits_ahead_of_master"], flag, task_info))

    return safe, unsafe


def main():
    if "--prune" in sys.argv:
        prune_report()
        return 0
    unintegrated_only = "--unintegrated" in sys.argv
    unintegrated = full_report(unintegrated_only=unintegrated_only)
    return 1 if unintegrated else 0


if __name__ == "__main__":
    sys.exit(main())
