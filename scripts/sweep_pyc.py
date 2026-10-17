"""Scoped .pyc sweeper: delete every .pyc under exactly ONE named root.

Why this exists (two rules it serves):

1. THE PYC RULE (qwen/0176, estate-wide): Python validates timestamp-based
   bytecode against the source's mtime IN WHOLE SECONDS and its size, so a
   revert that lands in the same second at the same byte count keeps importing
   the OLD module. Every write of a .py file must be followed by deleting its
   .pyc - after new code AND after any revert.

2. THE SCOPE BUG (disclosed 2026-10-17, task-qwen-coder-20261017-135706): a
   final pyc sweep written too broadly deleted 4,369 historical .pyc files
   across OTHER lanes' __pycache__ dirs. Regenerable caches only, no source or
   artefact bytes touched - but a sweeper that cannot be run safely from any
   lane at any time is not a sweeper the pyc rule can rely on.

Contract:

- One positional argument: the root. The walk starts there and nowhere else.
  Nothing outside the root is read, written or deleted.
- os.walk runs with its default followlinks=False, so a symlink/junction
  inside the root that points OUTSIDE the root is not descended into: the
  scope holds even against a link that tries to leave it.
- A root that does not exist (or is not a directory) is REFUSED: exit 2 and a
  stderr message naming the path. A failed sweep and an empty sweep are
  distinguishable - refusal is never silent success.
- Success prints one DELETED line per path (a name-set, not just a count),
  then a SWEPT summary line. Sweeping an already-clean root deletes 0 and
  says so explicitly.

Usage:  py -3 scripts/sweep_pyc.py <one-worktree-root>
"""
from __future__ import annotations

import argparse
import os
import sys


def sweep(root: str) -> list[str]:
    """Delete every .pyc under `root`; return the sorted name-set of deleted paths.

    Raises FileNotFoundError if `root` does not exist or is not a directory,
    so a caller can never confuse a failed sweep with an empty one.
    """
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        raise FileNotFoundError(root)
    deleted: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        # followlinks stays False (os.walk default): a junction inside the
        # root pointing at another tree is never descended into.
        for name in filenames:
            if name.endswith(".pyc"):
                path = os.path.join(dirpath, name)
                os.unlink(path)
                deleted.append(path)
    return sorted(deleted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Delete every .pyc under ONE named root; refuse a root that does not exist."
    )
    parser.add_argument(
        "root",
        help="the single worktree root to sweep; nothing outside it is touched",
    )
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        deleted = sweep(root)
    except FileNotFoundError:
        print(f"REFUSED: root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2
    for path in deleted:
        print(f"DELETED {path}")
    if deleted:
        print(f"SWEPT {len(deleted)} of {len(deleted)} .pyc under {root}")
    else:
        print(f"SWEPT 0 .pyc under {root} (already clean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
