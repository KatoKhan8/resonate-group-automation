#!/usr/bin/env python3
"""Regenerate the durable execution state that survives this machine.

## Why this exists

On 2026-09-15 the laptop shut down mid-run. Two completed results -
TASK-059's estate outcomes report and TASK-037's result block - existed only
as uncommitted files in a worktree. They were recovered by hand. The next
shutdown may not be recoverable, and a fresh session on a different computer
has no terminal history to read.

So the durable state is DERIVED, never hand-maintained. A ledger somebody has
to remember to update is a ledger that drifts, and a drifted ledger is worse
than none because it is believed. Everything here is read from the task files
on disk and from git, which are the two things that actually survive.

## What it writes

    docs/state/LEDGER.json          every task: status, owner, branch, SHA,
                                    review state, production state
    docs/state/QUEUE-MANIFEST.json  enough to reconstruct WHAT work exists
                                    without the PII that work/ holds
    docs/state/CHECKPOINT-latest.md written by Claude, not by this script

## The queue problem, and the deliberate compromise

`work/` is gitignored and must stay that way - `work/queue.jsonl` is 300 real
companies and 92 real contacts somebody paid for. But a durable queue is
required to reconstruct work after a crash.

The manifest is the resolution: per-record STAGE and COUNTS, with every
identifier SHA-256 hashed and truncated. It answers "how much work is in
which state, and did the estate change" without carrying a single real
domain. It does NOT let you rebuild the prospect list - that is what the
provider and the source CSV are for, and both outlive this repository.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(ROOT, "docs", "qwen-tasks")
STATE = os.path.join(ROOT, "docs", "state")
STAGES = ("TODO", "RUNNING", "REVIEW", "REWORK", "BLOCKED", "BLOCKED_QUOTA", "DONE")


def git(*args, cwd=ROOT):
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                             text=True, timeout=60)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def short_hash(value):
    """Stable, non-reversible identifier. Truncated deliberately: this is a
    change-detector, not a lookup key."""
    if not value:
        return ""
    return hashlib.sha256(str(value).strip().lower().encode("utf-8")).hexdigest()[:12]


def task_id(name):
    m = re.match(r"(TASK-\d+)", name)
    return m.group(1) if m else name


def read_result_block(path):
    """A task file records its own outcome. An absent block means it never
    reported, which is different from failing and must not be flattened."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return {}
    if "RESULT BLOCK" not in text and "STATUS:" not in text:
        return {"reported": False}
    block = {"reported": True}
    m = re.search(r"STATUS:?\s*\**\s*([A-Z_][A-Z_ ]*)", text)
    if m:
        block["declared_status"] = m.group(1).strip()
    m = re.search(r"COMMIT SHA:?\s*\**\s*([0-9a-f]{7,40})", text)
    if m:
        block["commit_sha"] = m.group(1).strip()
    return block


def collect_tasks():
    ledger = []
    for stage in STAGES:
        d = os.path.join(TASKS, stage)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(d, fn), ROOT).replace("\\", "/")
            entry = {
                "task": task_id(fn),
                "file": rel,
                "stage": stage,
                "last_commit": git("log", "-1", "--format=%h", "--", rel),
                "last_commit_at": git("log", "-1", "--format=%cI", "--", rel),
            }
            entry.update(read_result_block(os.path.join(d, fn)))
            ledger.append(entry)
    return ledger


def collect_branches():
    """A worker's branch is where its work actually lives. Unpushed-with-work
    is the dangerous state - that is precisely what nearly lost TASK-059."""
    out = []
    for b in git("for-each-ref", "--format=%(refname:short)", "refs/heads/").splitlines():
        if not b:
            continue
        local = git("rev-parse", "--short", b)
        remote = git("rev-parse", "--short", "origin/" + b)
        out.append({
            "branch": b,
            "head": local,
            "commits_ahead_of_master": int(git("rev-list", "--count", "master.." + b) or 0),
            "pushed": bool(remote) and remote == local,
            "remote_head": remote or None,
            "last_commit_at": git("log", "-1", "--format=%cI", b),
        })
    return out


def collect_worktrees():
    out, cur = [], {}
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            if cur:
                out.append(cur)
            cur = {"path": line.split(" ", 1)[1]}
        elif line.startswith("branch "):
            cur["branch"] = line.rsplit("/", 1)[-1]
        elif line.startswith("HEAD "):
            cur["head"] = line.split(" ", 1)[1][:7]
    if cur:
        out.append(cur)
    for w in out:
        st = git("status", "--porcelain", cwd=w["path"])
        w["uncommitted_files"] = len([x for x in st.splitlines() if x.strip()])
        w["clean"] = w["uncommitted_files"] == 0
    return out


def queue_manifest():
    """Sanitised. See the module docstring for why this shape and not the rows."""
    qp = os.path.join(ROOT, "work", "queue.jsonl")
    man = {"queue_path": "work/queue.jsonl", "gitignored": True,
           "present": os.path.exists(qp)}
    if not man["present"]:
        man["note"] = ("Queue absent on this machine. Rebuild from the source CSV "
                       "and the provider; this manifest states only its shape.")
        return man
    records = contacts = bad = dropped = 0
    clients, stages = {}, {}
    digest = hashlib.sha256()
    with open(qp, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records += 1
            try:
                r = json.loads(line)
            except Exception:
                bad += 1
                continue
            digest.update(short_hash(r.get("domain") or r.get("id") or "").encode())
            clients[r.get("client")] = clients.get(r.get("client"), 0) + 1
            # `state` AND `drop_reason` ARE THE FIELD NAMES, measured against
            # the live queue on 2026-09-17. This read `status`/`stage`/`dropped`
            # - three names no record has ever carried - so it wrote
            # `stages: {"unset": 550}` and `dropped: 0` over a manifest that
            # had said verified 65 / held 32 / dropped 126 / queued 315 /
            # drafted 12. `dropped: 0` is the exact failure this repository
            # keeps: a count nobody could compute, published as a count of
            # none. 126 records really are dropped.
            st = r.get("state") or "unset"
            stages[st] = stages.get(st, 0) + 1
            if r.get("drop_reason"):
                dropped += 1
            c = r.get("contacts")
            contacts += len(c) if isinstance(c, (dict, list)) else 0
    man.update({
        "records": records,
        "unparseable": bad,
        "contacts": contacts,
        "dropped": dropped,
        "clients": clients,
        "stages": stages,
        # Changes if and only if the record SET changes. Lets a fresh session
        # tell "same estate" from "different estate" with no PII in the file.
        "estate_fingerprint": digest.hexdigest()[:16],
        "mtime": datetime.fromtimestamp(os.path.getmtime(qp), timezone.utc).isoformat(),
    })
    # THE SILENT VERSION OF THIS BUG IS THE REASON FOR THE LOUD ONE. Reading a
    # field no record carries does not fail - it produces a confident,
    # well-formed manifest in which every record is "unset" and nothing is
    # dropped, and the next session believes it. If the schema moves again,
    # say so IN the file rather than publishing a shape derived from nothing.
    parsed = records - bad
    if parsed and stages.get("unset", 0) == parsed:
        man["stages_unreadable"] = (
            "every record fell through to `unset`: the field this manifest "
            "reads is not the field records carry. The stage counts and the "
            "dropped count below are NOT derived from state and mean UNKNOWN, "
            "not zero.")
    return man


def main():
    os.makedirs(STATE, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # BRANCH-BLINDNESS WARNING.
    # This script derives task state from master's directories alone.
    # Tasks finished on worker branches but not yet integrated appear in
    # their master stage (usually TODO), not in the stage the branch has
    # moved them to. The LEDGER therefore under-reports DONE/REVIEW and
    # over-reports TODO whenever unintegrated work exists.
    # Run scripts/task173_scan.py to see the full picture across branches.
    branch_blindness_note = (
        "Task stages in this ledger reflect master only. Tasks finished on "
        "worker branches but not yet integrated into master appear in their "
        "master stage (often TODO), not the stage the branch has moved them "
        "to. Run scripts/task173_scan.py --unintegrated for the cross-branch "
        "view."
    )

    ledger = {
        "generated_at": now,
        "generated_from": "docs/qwen-tasks/** and git. Derived, never hand-edited.",
        "branch_blindness": branch_blindness_note,
        "master_head": git("rev-parse", "--short", "master"),
        "origin_master_head": git("rev-parse", "--short", "origin/master"),
        "master_pushed": git("rev-parse", "master") == git("rev-parse", "origin/master"),
        "tasks": collect_tasks(),
        "branches": collect_branches(),
        "worktrees": collect_worktrees(),
    }
    counts = {}
    for t in ledger["tasks"]:
        counts[t["stage"]] = counts.get(t["stage"], 0) + 1
    ledger["stage_counts"] = counts

    with open(os.path.join(STATE, "LEDGER.json"), "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2)
        fh.write("\n")
    with open(os.path.join(STATE, "QUEUE-MANIFEST.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(generated_at=now, **queue_manifest()), fh, indent=2)
        fh.write("\n")

    unpushed = [b["branch"] for b in ledger["branches"]
                if not b["pushed"] and b["commits_ahead_of_master"] > 0]
    dirty = [w["path"] for w in ledger["worktrees"] if not w["clean"]]
    print("master %s pushed=%s" % (ledger["master_head"], ledger["master_pushed"]))
    print("stages:", counts)
    print("unpushed branches with work: %d" % len(unpushed))
    for b in unpushed:
        print("   UNPUSHED", b)
    print("dirty worktrees: %d" % len(dirty))
    for d in dirty:
        print("   DIRTY", d)
    # Non-zero is a DURABILITY alarm, not a crash. Work exists that a shutdown
    # would destroy. Intended as a pre-checkpoint gate.
    return 1 if (unpushed or dirty) else 0


if __name__ == "__main__":
    sys.exit(main())
