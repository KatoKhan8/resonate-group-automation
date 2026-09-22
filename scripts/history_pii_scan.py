#!/usr/bin/env python3
"""Is a real identifier still in GIT HISTORY? The working tree is a different question.

    py -3 scripts/history_pii_scan.py .            # full report, JSON
    py -3 scripts/history_pii_scan.py . --summary  # the six numbers

`tests/test_fixture_hygiene.py` answers "is it in the tree". This answers "is
it in any blob any commit can still reach", which is what a history rewrite
has to drive to zero and what a tree-level guard structurally cannot see.
Written for `docs/GIT-HISTORY-REWRITE-RUNBOOK-2026-09-22.md`, section 6.

PRINTS NO REAL VALUE, EVER. Every identifier is reported as `px-<12 hex>`,
produced by the same salt and the same truncation `scripts/task189_scrub_pii.py`
uses, so one entity reads identically here, in the redacted documents and in
the replacement file the rewrite is driven from. That is deliberate: a report
that has to be handled carefully is a report nobody pastes into the issue, and
this one is meant to be pasted.

The values come from the guard itself rather than a copy, for the reason
`task189_scrub_pii.py` already gives: a second list is a second thing that can
disagree, and hardcoding them here would make this script trip the scanner it
exists to serve.

WHY IT SCANS BLOBS RATHER THAN COMMITS. A file unchanged across 200 commits is
one blob. Walking commits re-reads it 200 times; walking blobs reads it once
and then attributes it. On this repository that is 6,128 reads instead of
several hundred thousand.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import subprocess
import sys

SALT = "resonate-pii-salt-2026-09-16"      # as scripts/task189_scrub_pii.py

# The guard file holds every forbidden value in clear, by design - it is the
# list the scanner scans for. It is in every commit, so counting it makes
# every commit look like a leak and hides the real distribution. It is
# reported separately rather than silently skipped: "the identifiers are all
# in one tracked file" is a finding, not noise.
GUARD = "tests/test_fixture_hygiene.py"

SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".zip", ".woff",
            ".woff2", ".ttf", ".docx", ".xlsx", ".xls", ".pyc")

MAX_BLOB = 2_000_000


def px(value):
    return "px-" + hashlib.sha256((SALT + value).encode()).hexdigest()[:12]


def matchers(root):
    """(value, kind, compiled) for every value the guard forbids."""
    sys.path.insert(0, os.path.join(root, "tests"))
    from test_fixture_hygiene import (FORBIDDEN_DOMAINS, FORBIDDEN_NAMES,
                                      FORBIDDEN_FIGURES)
    out = []
    # A NAME IS MATCHED ON A WORD BOUNDARY AND A DOMAIN IS NOT. The shortest
    # forbidden name is four characters and matches inside ordinary English
    # otherwise, which would report every commit as carrying it and make the
    # number meaningless. A domain is already distinctive, and a figure is a
    # literal string that may contain punctuation.
    for value in FORBIDDEN_NAMES:
        out.append((value, "name", re.compile(
            r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])",
            re.I)))
    for value in FORBIDDEN_DOMAINS:
        out.append((value, "domain", re.compile(re.escape(value), re.I)))
    for value in FORBIDDEN_FIGURES:
        out.append((value, "figure", re.compile(re.escape(value), re.I)))
    out.sort(key=lambda row: len(row[0]), reverse=True)
    return out


def git(root, *args):
    done = subprocess.run(("git", "-C", root) + args, capture_output=True)
    return done.stdout.decode("utf-8", "replace")


def scan_blobs(root, rules):
    """sha -> {px: {"kind", "n"}} for every blob carrying a forbidden value."""
    sizes = {}
    for line in git(root, "cat-file", "--batch-all-objects",
                    "--batch-check=%(objectname) %(objecttype) %(objectsize)"
                    ).splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob":
            sizes[parts[0]] = int(parts[2])

    hits, scanned = {}, 0
    proc = subprocess.Popen(("git", "-C", root, "cat-file", "--batch"),
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for sha, size in sizes.items():
            if size > MAX_BLOB:
                continue
            proc.stdin.write((sha + "\n").encode())
            proc.stdin.flush()
            length = int(proc.stdout.readline().split()[2])
            body = proc.stdout.read(length)
            proc.stdout.read(1)                     # the trailing newline
            scanned += 1
            if b"\x00" in body[:2048]:              # binary; not text we can read
                continue
            text = body.decode("utf-8", "replace")
            found = {}
            for value, kind, matcher in rules:
                n = len(matcher.findall(text))
                if n:
                    found[px(value)] = {"kind": kind, "n": n}
            if found:
                hits[sha] = found
    finally:
        proc.stdin.close()
        proc.wait()
    return len(sizes), scanned, hits


def attribute(root, hits):
    """Which paths, in which commits, carry a flagged blob."""
    meta = {}
    for line in git(root, "log", "--all", "--format=%H|%ad|%s",
                    "--date=short").splitlines():
        sha, date, subject = line.split("|", 2)
        meta[sha] = (date, subject)

    per_commit = {}
    for sha in meta:
        carried = {}
        for row in git(root, "ls-tree", "-r", sha).splitlines():
            try:
                info, path = row.split("\t", 1)
                blob = info.split()[2]
            except (ValueError, IndexError):
                continue
            if os.path.splitext(path)[1].lower() in SKIP_EXT:
                continue
            if blob in hits:
                carried.setdefault(path, {}).update(hits[blob])
        if carried:
            per_commit[sha] = carried
    return meta, per_commit


def report(root, cutoff):
    rules = matchers(root)
    total, scanned, hits = scan_blobs(root, rules)
    meta, per_commit = attribute(root, hits)
    order = git(root, "rev-list", "--first-parent", "--reverse",
                "master").split()

    paths = collections.Counter()
    path_px = collections.defaultdict(set)
    before = after = 0
    for sha in order:
        carried = {k: v for k, v in per_commit.get(sha, {}).items()
                   if k != GUARD}
        if not carried:
            continue
        if meta.get(sha, ("", ""))[0] < cutoff:
            before += 1
        else:
            after += 1
        for path, found in carried.items():
            paths[path] += 1
            path_px[path].update(found)

    every = set()
    for found in path_px.values():
        every |= found

    carrying = [sha for sha in order if sha in per_commit]
    dates = [meta[sha][0] for sha in carrying]
    return {
        "cutoff": cutoff,
        "blobs_total": total,
        "blobs_scanned": scanned,
        "blobs_carrying": len(hits),
        "commits_first_parent": len(order),
        "guard_file": GUARD,
        "guard_file_identifiers": len(
            set().union(*[per_commit[s][GUARD] for s in per_commit
                          if GUARD in per_commit[s]]) or set()),
        "commits_carrying_excluding_guard": before + after,
        "before_cutoff": before,
        "at_or_after_cutoff": after,
        "earliest_carrying": min(dates) if dates else None,
        "latest_carrying": max(dates) if dates else None,
        "distinct_paths": len(paths),
        "distinct_identifiers": len(every),
        "paths": [{"path": p, "commits": paths[p],
                   "identifiers": sorted(path_px[p])}
                  for p in sorted(paths, key=lambda k: -paths[k])],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--summary", action="store_true",
                        help="the six numbers rather than the full JSON")
    parser.add_argument("--cutoff", default="2026-09-15",
                        help="date the before/after split is taken at")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    data = report(root, args.cutoff)

    if not args.summary:
        print(json.dumps(data, indent=2))
        return 0 if data["blobs_carrying"] == 0 else 1

    print(f"  blobs scanned                        {data['blobs_scanned']:>7,}")
    print(f"  blobs carrying at least one value    {data['blobs_carrying']:>7,}")
    print(f"  commits carrying (excl. guard file)  "
          f"{data['commits_carrying_excluding_guard']:>7,}")
    print(f"    before {data['cutoff']}                  "
          f"{data['before_cutoff']:>7,}")
    print(f"    on or after                        {data['at_or_after_cutoff']:>7,}")
    print(f"  distinct identifiers                 "
          f"{data['distinct_identifiers']:>7,}")
    print(f"  earliest / latest carrying commit    "
          f"{data['earliest_carrying']} / {data['latest_carrying']}")
    print(f"  {GUARD} carries          "
          f"{data['guard_file_identifiers']:>7,} in clear, in every commit")
    if data["blobs_carrying"]:
        print("\n  NOT CLEAN. A rewrite must drive 'blobs carrying' to 0.")
        return 1
    print("\n  CLEAN - no blob reachable in this repository carries a "
          "forbidden value.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
