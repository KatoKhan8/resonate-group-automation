#!/usr/bin/env python3
"""Pre-commit PII check: report what would leak before the file is written.

Runs src.piiredact.scan over one or more files (or stdin) and prints every
token that would be redacted, with file, line, and category.  Exits non-zero
when at least one leak is found, so a CI step or a worker's pre-write check
can gate on it.

Usage:
    py -3 scripts/check_pii.py path/to/report.md
    py -3 scripts/check_pii.py src/*.py tests/*.py
    echo "some text" | py -3 scripts/check_pii.py -

The check is deliberately read-only: it reports, it does not modify.  A worker
who sees a hit rewrites the source text to use a pseudonym or calls
piiredact.redact() before writing.
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.piiredact import scan


def check_text(text, label="<stdin>"):
    hits = scan(text)
    lines = text.split("\n")
    for token, category, start, end in hits:
        line_no = text[:start].count("\n") + 1
        line_text = lines[line_no - 1].strip()
        print(f"  {label}:{line_no}  [{category}] {token!r}")
        if line_text:
            print(f"    | {line_text[:120]}")
    return len(hits)


def check_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        print(f"  {path}: {e}", file=sys.stderr)
        return 0
    return check_text(text, label=path)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="py -3 scripts/check_pii.py",
        description="Report PII tokens that would fail test_fixture_hygiene.")
    p.add_argument("files", nargs="*", default=["-"],
                   help="Files to scan. Use - for stdin.")
    p.add_argument("--quiet", "-q", action="store_true",
                   help="Only print the summary count.")
    a = p.parse_args(argv)

    total = 0
    for path in a.files:
        if path == "-":
            text = sys.stdin.read()
            if not a.quiet:
                n = check_text(text)
            else:
                n = len(scan(text))
        else:
            if not a.quiet:
                n = check_file(path)
            else:
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        n = len(scan(f.read()))
                except OSError:
                    n = 0
        total += n

    if total:
        print(f"\n{total} leak(s) found.")
        return 1
    if not a.quiet:
        print("No leaks found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
