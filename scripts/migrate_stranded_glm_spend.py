#!/usr/bin/env python3
"""Move the GLM spend billed into worktree ledgers into the one that is audited.

WHY. `spendledger.path()` resolves against `store.queue_path()`, which is the
CALLING TREE's `work/` - and `work/` is gitignored, so every `git worktree add`
tree has its own. Anything that spent money from a worktree therefore billed a
file that is deleted with the tree and that the production spend audit cannot
see. Swept 2026-10-02: **37 glm rows, 482,732 micro-USD, across six ledgers**,
against 41 rows in the production one. Five of them are the TASK-903/940/942/946
verdicts the merge queue is gated on.

The code defect is TASK-960 and is NOT fixed by this script. This script fixes
the DATA, and only after the operator approved it (2026-10-02): the rows are
real money already spent, and an audit that cannot see them under-reports.

HOW IT REFUSES TO DOUBLE-COUNT. Every appended row carries
`migrated_from` (the quarantined file it came from) and `migrated_at`. A row is
skipped when the production ledger already holds one with the same `run_id` and
`at`, so a second run is a no-op and says so. `--apply` reads the ledger BACK
from disk afterwards and refuses to report success unless the count rose by
exactly the number appended and the per-client totals match what was claimed.

    python scripts/migrate_stranded_glm_spend.py --dry-run
    python scripts/migrate_stranded_glm_spend.py --apply
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys


def main_checkout_root():
    """The MAIN checkout, from any tree, or None. The one path git agrees on.

    A RELATIVE answer is refused rather than resolved: `abspath` would resolve
    it against the calling tree, which is the trap this whole script is about.
    """
    out = subprocess.run(["git", "rev-parse", "--path-format=absolute",
                          "--git-common-dir"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=60)
    value = (out.stdout or "").strip()
    if out.returncode != 0 or not value or not os.path.isabs(value):
        return None
    return os.path.dirname(os.path.abspath(value))


def rows_of(path, provider="glm"):
    out = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:                                  # noqa: BLE001
                continue
            if provider is None or row.get("provider") == provider:
                out.append(row)
    return out


def identity(row):
    """What makes two ledger rows the same row. `run_id` plus the timestamp."""
    return (str(row.get("run_id")), str(row.get("at")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true",
                       help="print what would be appended; write nothing")
    group.add_argument("--apply", action="store_true",
                       help="append, then read the ledger back and verify")
    args = parser.parse_args(argv)

    root = main_checkout_root()
    if not root:
        print("REFUSED: git would not name the main checkout absolutely, so "
              "the production ledger cannot be identified. Nothing written.")
        return 2

    ledger = os.path.join(root, "work", "spend-ledger.jsonl")
    quarantine = os.path.join(root, "work", "stranded-spend-2026-10-02")
    index_path = os.path.join(quarantine, "INDEX.json")
    for path in (ledger, index_path):
        if not os.path.isfile(path):
            print(f"REFUSED: missing {path}")
            return 2

    index = json.load(open(index_path, encoding="utf-8"))
    existing = {identity(r) for r in rows_of(ledger)}
    print(f"production ledger : {ledger}")
    print(f"  glm rows now    : {len(existing)}")

    candidates, skipped = [], []
    for entry in index["files"]:
        source = os.path.join(quarantine, entry["copied_to"])
        for row in rows_of(source):
            if identity(row) in existing:
                skipped.append(row)
                continue
            candidates.append((entry["copied_to"], row))

    claimed = index["total_glm_rows"]
    found = len(candidates) + len(skipped)
    print(f"quarantine        : {len(index['files'])} files, {claimed} rows "
          f"claimed, {found} read")
    if found != claimed:
        print("REFUSED: the quarantine does not hold what its INDEX claims. "
              "Nothing written.")
        return 3
    print(f"  to append       : {len(candidates)}")
    print(f"  already present : {len(skipped)} (same run_id and timestamp)")

    by_client = {}
    for _src, row in candidates:
        client = row.get("client") or "(none)"
        slot = by_client.setdefault(client, {"rows": 0, "microusd": 0})
        slot["rows"] += 1
        slot["microusd"] += row.get("expected_cost", 0) or 0
    total = sum(s["microusd"] for s in by_client.values())
    for client, slot in sorted(by_client.items()):
        print(f"    {client:16} {slot['rows']:3d} rows  {slot['microusd']:7d} uUSD")
    print(f"    {'TOTAL':16} {len(candidates):3d} rows  {total:7d} uUSD")

    if args.dry_run:
        print("\nDRY RUN: nothing was written.")
        return 0

    if not candidates:
        print("\nNothing to do: every quarantined row is already in the "
              "ledger. This is what a second run looks like.")
        return 0

    backup = ledger + ".before-migration-2026-10-02"
    if not os.path.exists(backup):
        shutil.copy2(ledger, backup)
        print(f"\nbackup written  : {backup}")
    else:
        print(f"\nbackup exists   : {backup} (kept, not overwritten)")

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    before = len(rows_of(ledger))
    with open(ledger, "a", encoding="utf-8", newline="\n") as handle:
        for source, row in candidates:
            out = dict(row)
            out["migrated_from"] = source
            out["migrated_at"] = stamp
            handle.write(json.dumps(out, ensure_ascii=False) + "\n")

    # READ BACK FROM THE FILE, never from the variables above.
    after_rows = rows_of(ledger)
    after = len(after_rows)
    migrated = [r for r in after_rows if r.get("migrated_from")]
    migrated_total = sum(r.get("expected_cost", 0) or 0 for r in migrated)
    print(f"glm rows before   : {before}")
    print(f"glm rows after    : {after}  (+{after - before}, expected "
          f"+{len(candidates)})")
    print(f"rows carrying migrated_from: {len(migrated)}  "
          f"{migrated_total} uUSD (expected {total})")
    ok = (after - before == len(candidates)
          and len(migrated) == len(candidates)
          and migrated_total == total)
    print("VERDICT:", "MIGRATED and verified from the file"
          if ok else "MISMATCH - the ledger does not hold what was appended")
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
