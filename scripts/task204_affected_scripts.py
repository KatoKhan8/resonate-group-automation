"""Audit every script that reads work/queue.snapshot.jsonl.

For each, reports:
- Whether it reads the stamp too (stamp-aware vs stamp-blind)
- Whether its finding is known to be affected by staleness
- Whether it can be repointed at live state or the manifest

This is a static audit. It does not run the scripts.

Usage:
    python scripts/task204_affected_scripts.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
TESTS_DIR = os.path.join(ROOT, "tests")

SNAPSHOT_RE = re.compile(r"queue\.snapshot\.jsonl")
STAMP_RE = re.compile(r"queue\.snapshot\.STAMP")

KNOWN_AFFECTED_TASKS = {
    "task194_analysis.py": (
        "TASK-194: measured '143 contacts held by insufficient_confirmations' "
        "from the snapshot. TASK-196 showed the real figure was 159 contacts "
        "with no verification evidence at all, and exactly 1 that Deliverable "
        "would help. The 143 number is WRONG."
    ),
}

TASK_PREFIX_RE = re.compile(r"task(\d+)_")


def scan_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    has_snapshot = bool(SNAPSHOT_RE.search(content))
    has_stamp = bool(STAMP_RE.search(content))
    return has_snapshot, has_stamp


def main():
    snapshot_readers = []
    for directory in [SCRIPTS_DIR, TESTS_DIR]:
        if not os.path.isdir(directory):
            continue
        for fn in sorted(os.listdir(directory)):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(directory, fn)
            has_snap, has_stamp = scan_file(path)
            if has_snap:
                snapshot_readers.append((fn, has_stamp))

    print(f"{'Script':<50} {'Stamp-aware':<14} {'Affected?'}")
    print("-" * 90)

    affected_count = 0
    for fn, has_stamp in snapshot_readers:
        stamp_str = "YES" if has_stamp else "NO"
        affected = KNOWN_AFFECTED_TASKS.get(fn, "")
        if affected:
            affected_count += 1
            affected_str = "YES - " + affected[:60]
        else:
            affected_str = "not known"
        print(f"{fn:<50} {stamp_str:<14} {affected_str}")

    print()
    print(f"Total scripts reading snapshot: {len(snapshot_readers)}")
    print(f"Stamp-aware (also read STAMP):  {sum(1 for _, s in snapshot_readers if s)}")
    print(f"Stamp-blind (data only):        {sum(1 for _, s in snapshot_readers if not s)}")
    print(f"Known wrong findings:           {affected_count}")
    print()
    print("RECOMMENDATION: All scripts are one-off analysis scripts that have")
    print("already run. Their findings are recorded in task result blocks and")
    print("docs/ files. The scripts themselves do not need repointing - they")
    print("are historical artifacts. What needs to change is that NEW tasks")
    print("should read live state (work/queue.jsonl via src.store) or the")
    print("sanitized manifest (docs/state/QUEUE-MANIFEST.json), not the snapshot.")


if __name__ == "__main__":
    main()
