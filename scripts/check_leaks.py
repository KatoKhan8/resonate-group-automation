#!/usr/bin/env python3
"""Pre-commit check: report what would leak before a file is tracked.

Runs the same forbidden-token list the hygiene guard uses, plus every known
record id from the snapshot, against all tracked text files.  A worker runs
this BEFORE writing a report rather than discovering the leak in a test run.

    py -3 scripts/check_leaks.py                scan every tracked file
    py -3 scripts/check_leaks.py path/to/file   scan one file

Exit 0 when nothing would leak, exit 1 when something would.

The forbidden tokens come from tests/test_fixture_hygiene.py (one source of
truth).  The record ids come from work/queue.snapshot.jsonl (the read-only
copy of the production queue).
"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.redact import _forbidden_tokens, _load_record_ids

TEXT_SUFFIXES = (".py", ".json", ".jsonl", ".csv", ".txt", ".md", ".yaml",
                 ".yml", ".cfg", ".ini", ".toml", ".html", ".js", ".css")

SELF = os.path.join("scripts", "check_leaks.py")
REDACT_MODULE = os.path.join("src", "redact.py")
REDACT_TEST = os.path.join("tests", "test_redact.py")
HYGIENE_TEST = os.path.join("tests", "test_fixture_hygiene.py")
EXCLUDED = {SELF, REDACT_MODULE, REDACT_TEST, HYGIENE_TEST}


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT,
        capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.split("\0")
            if p and p.endswith(TEXT_SUFFIXES) and p not in EXCLUDED]


def scan(path, tokens, record_ids):
    full = os.path.join(ROOT, path)
    try:
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except (OSError, IOError):
        return [], []

    low = text.lower()
    forbidden_hits = []
    for token in tokens:
        if token in low:
            forbidden_hits.append(token)

    rid_hits = []
    for rid in record_ids:
        if rid in low:
            rid_hits.append(rid)

    return sorted(set(forbidden_hits)), sorted(set(rid_hits))


def main():
    if len(sys.argv) > 1:
        files = [os.path.relpath(os.path.abspath(a), ROOT).replace(os.sep, "/")
                 for a in sys.argv[1:]]
    else:
        files = tracked_files()

    tokens = _forbidden_tokens()
    record_ids = _load_record_ids()

    total_forbidden = 0
    total_rids = 0
    for path in files:
        fb, rids = scan(path, tokens, record_ids)
        if fb:
            print(f"FORBIDDEN  {path}: {', '.join(fb)}")
            total_forbidden += len(fb)
        if rids:
            print(f"RECORD-ID  {path}: {', '.join(rids[:5])}"
                  + ("..." if len(rids) > 5 else ""))
            total_rids += len(rids)

    if total_forbidden or total_rids:
        print(f"\n{total_forbidden} forbidden token(s), "
              f"{total_rids} record id(s) would leak")
        return 1

    print(f"clean ({len(files)} file(s) checked, "
          f"{len(record_ids)} record id(s) known)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
