#!/usr/bin/env python3
"""Who is working on what, across EVERY branch. Read-only.

    py -3 scripts/task_registry_scan.py
    py -3 scripts/task_registry_scan.py --conflicts   # only the dangerous rows

## Why this exists

**The task registry is a set of files inside the repository, so it is
PER BRANCH.** `docs/qwen-tasks/{TODO,RUNNING,DONE}/` on `master` is a
different registry from the one on `infra`, which is different again from the
one on every worker branch. There are 219 local branches, so there are up to
219 registries, and each is correct about itself and blind to the rest.

That is not a bug in anyone's code. It is what happens when claim state -
which is runtime state, changing minute by minute - is stored in the same
place as the code, which is versioned and branched deliberately.

Measured 2026-09-22:

    master                     RUNNING: TASK-192
    infra                      RUNNING: TASK-192, TASK-262
    qwen-worker-2-task-261     RUNNING: TASK-192, TASK-261
    qwen-worker-4-task-263     RUNNING: TASK-192, TASK-262, TASK-263

The Slack agent reads the production worktree, so it reports "ready queue
empty, only TASK-192 in flight". **That is true of master and false of the
system**: four other tasks were in flight at that moment.

## What it already cost

TASK-250 was claimed on `qwen-worker-r57` and left in that branch's RUNNING/
when its worker died. `master`'s registry still showed it in TODO. The infra
session read master's view, treated it as unstarted, merged the stalled work,
and regressed the suite by 41 failures before reverting. **One registry would
have shown it as claimed.**

## What this script is and is not

It is the READ side, and it works today with no change to anything: it scans
every branch and reports the union, flagging any task claimed in more than one
place and any task whose state differs between branches.

**It is not the fix.** A scanner makes the truth discoverable; it does not
make it single. The fix is a claim ledger outside the versioned tree - see
`docs/TASK-REGISTRY-IS-PER-BRANCH-2026-09-22.md`.
"""
import argparse
import collections
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGES = ("TODO", "RUNNING", "REVIEW", "REWORK", "BLOCKED", "DONE")
TASK = re.compile(r"(TASK-\d+)")

# Branches that are certainly stale are still scanned: a stale branch holding
# a task in RUNNING is EXACTLY the case that caused the TASK-250 regression,
# so hiding it would defeat the purpose.


def git(*args):
    out = subprocess.run(("git", "-C", ROOT) + args,
                         capture_output=True, text=True)
    return out.stdout


def branches():
    return [b.strip() for b in
            git("branch", "--format=%(refname:short)").splitlines() if b.strip()]


def registry(branch):
    """{task_id: stage} as that branch sees it."""
    out = {}
    listing = git("ls-tree", "-r", "--name-only", branch, "docs/qwen-tasks/")
    for path in listing.splitlines():
        parts = path.split("/")
        # docs / qwen-tasks / <STAGE> / TASK-nnn-....md  -> the stage is [2].
        if len(parts) < 4 or parts[2] not in STAGES:
            continue
        found = TASK.search(parts[-1])
        if found:
            out[found.group(1)] = parts[2]
    return out


def scan():
    seen = collections.defaultdict(dict)      # task -> {branch: stage}
    for branch in branches():
        for task, stage in registry(branch).items():
            seen[task][branch] = stage
    return seen


def conflicts(seen):
    """Tasks whose stage is not the same everywhere it appears.

    A task in RUNNING on one branch and TODO on another is the dangerous
    shape: the second branch will dispatch it. A task in DONE somewhere and
    TODO elsewhere is the same hazard one step later.
    """
    out = {}
    for task, where in seen.items():
        stages = set(where.values())
        if len(stages) > 1 and ("RUNNING" in stages or "DONE" in stages):
            out[task] = where
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--conflicts", action="store_true",
                        help="only tasks whose stage differs between branches")
    parser.add_argument("--running", action="store_true",
                        help="only tasks RUNNING somewhere")
    args = parser.parse_args(argv)

    seen = scan()
    bad = conflicts(seen)

    if args.conflicts:
        rows = bad
    elif args.running:
        rows = {t: w for t, w in seen.items() if "RUNNING" in w.values()}
    else:
        rows = seen

    for task in sorted(rows, key=lambda t: int(t.split("-")[1])):
        where = rows[task]
        stages = collections.Counter(where.values())
        flag = "  <-- DISAGREES" if task in bad else ""
        print(f"{task}  {dict(stages)}{flag}")
        if task in bad or args.running:
            for branch, stage in sorted(where.items()):
                if stage in ("RUNNING",) or task in bad:
                    print(f"      {stage:<8} {branch}")

    print(f"\n{len(seen)} tasks across {len(branches())} branches; "
          f"{len(bad)} disagree between branches.")
    if bad:
        print("A task claimed in one branch and TODO in another WILL be "
              "dispatched twice. That has already happened once (TASK-250).")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
