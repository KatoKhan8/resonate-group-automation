#!/usr/bin/env python3
"""Pre-commit-style PII leak check.

Scans files for tokens that would trip tests/test_fixture_hygiene.py, and
for record-id-shaped tokens that the hygiene guard does not cover. Runs as
a single command so a worker can check BEFORE writing a file rather than
discovering the leak in a test run afterwards.

  py -3 scripts/check_pii.py path/to/file.md
  py -3 scripts/check_pii.py path/to/dir/
  py -3 scripts/check_pii.py --staged

Exit 0 if nothing would leak. Exit 1 with a report of what would.

Read only: nothing here writes to any file or touches the queue.
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.redact import find_leaks

TEXT_SUFFIXES = (".py", ".json", ".jsonl", ".csv", ".txt", ".md", ".yaml",
                 ".yml", ".cfg", ".ini", ".toml", ".html", ".js", ".css")


def staged_files():
    """Files in the git index that have text suffixes."""
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=ROOT, capture_output=True, text=True).stdout
    return [p for p in out.strip().splitlines()
            if p and any(p.endswith(s) for s in TEXT_SUFFIXES)]


def collect_files(paths):
    """Expand directories and filter to text files."""
    result = []
    for p in paths:
        full = os.path.join(ROOT, p) if not os.path.isabs(p) else p
        if os.path.isdir(full):
            for dirpath, _, filenames in os.walk(full):
                for fn in filenames:
                    if any(fn.endswith(s) for s in TEXT_SUFFIXES):
                        result.append(os.path.relpath(
                            os.path.join(dirpath, fn), ROOT))
        elif os.path.isfile(full):
            result.append(os.path.relpath(full, ROOT))
    return result


def check(path):
    """Return list of (token, category) for one file."""
    full = os.path.join(ROOT, path)
    try:
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except (OSError, IOError):
        return []
    return find_leaks(text)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check files for PII leaks before committing")
    parser.add_argument("paths", nargs="*",
                        help="Files or directories to check")
    parser.add_argument("--staged", action="store_true",
                        help="Check files in the git staging area")
    args = parser.parse_args(argv)

    if args.staged:
        files = staged_files()
    elif args.paths:
        files = collect_files(args.paths)
    else:
        parser.error("provide file paths or --staged")
        return 2

    if not files:
        print("No text files to check.")
        return 0

    total_leaks = 0
    for path in sorted(files):
        leaks = check(path)
        if leaks:
            for token, category in leaks:
                print(f"  LEAK  {path}: {token!r} ({category})")
                total_leaks += 1

    if total_leaks:
        print(f"\n{total_leaks} leak(s) found. "
              f"Use src.redact.redact() to sanitise before writing.")
        return 1

    print(f"Checked {len(files)} file(s): clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
