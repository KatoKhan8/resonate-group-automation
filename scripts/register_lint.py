"""Check the problem register for duplicate issue IDs.

Run:
    python scripts/register_lint.py

Exits 0 if every ISSUE-xxx / REFUTED-xxx heading is unique.
Exits 1 with a diagnostic for each duplicate found.

The register's own rule: "Numbers are not reused." This script catches
the exact failure mode that produced ISSUE-034 being taken twice in one
evening (2026-09-24).
"""

import re
import sys
from collections import Counter
from pathlib import Path

REGISTER_PATH = Path(__file__).resolve().parent.parent / "docs" / "state" / "PROBLEM-REGISTER.md"

HEADING_RE = re.compile(r"^### ((?:ISSUE|REFUTED)-\d+)", re.MULTILINE)


def find_duplicate_ids(text: str) -> list[tuple[str, int]]:
    """Return a list of (id, count) for every heading ID that appears more than once."""
    ids = HEADING_RE.findall(text)
    counts = Counter(ids)
    return [(id_, n) for id_, n in sorted(counts.items()) if n > 1]


def main() -> int:
    if not REGISTER_PATH.exists():
        print(f"ERROR: register not found at {REGISTER_PATH}", file=sys.stderr)
        return 1

    text = REGISTER_PATH.read_text(encoding="utf-8")
    dupes = find_duplicate_ids(text)

    if not dupes:
        total = len(HEADING_RE.findall(text))
        print(f"OK: {total} issue headings, no duplicates.")
        return 0

    print(f"FAIL: {len(dupes)} duplicate ID(s) found:", file=sys.stderr)
    for id_, count in dupes:
        print(f"  {id_} appears {count} times", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
