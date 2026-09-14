#!/usr/bin/env python3
"""Put the canonical credential file into every Qwen worktree.

WHY THIS EXISTS. Qwen is the primary workforce, and a worker that cannot
reach the configured model cannot regenerate copy, cannot generate variants
and cannot measure a prompt change. Before 2026-09-14 the Qwen worktrees had
no `config/.env` at all, so `py -3 -m src.generate --live` could not run in
them and three whole classes of task had to come back to Claude.

WHAT IT DOES NOT DO. It does not put a secret into git. `config/.env` is
matched by `.gitignore` line 5 in every worktree, because every worktree
shares master's `.gitignore`. This script verifies that before it writes
anything, and refuses if the protection is missing.

IT NEVER PRINTS A VALUE. Only names and AVAILABLE/MISSING. A credential that
reaches a terminal log has reached a place nobody is auditing.

  python scripts/sync_worker_env.py            report what each worktree has
  python scripts/sync_worker_env.py --write    copy the canonical file out

ROTATION. Re-run with `--write`. The copies are plain files, not links, so a
rotated canonical file does not propagate on its own - that is the trade for
a mechanism with no Windows symlink or admin dependency.
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANONICAL = os.path.join(ROOT, "config", ".env")
REL = os.path.join("config", ".env")


def worktrees():
    """Every worktree git knows about, except this one."""
    out = subprocess.run(["git", "worktree", "list", "--porcelain"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    paths = [l.split(" ", 1)[1].strip()
             for l in out.splitlines() if l.startswith("worktree ")]
    here = os.path.normcase(os.path.abspath(ROOT))
    return [p for p in paths if os.path.normcase(os.path.abspath(p)) != here]


def names_in(path):
    """The VARIABLE NAMES in an env file. Never the values."""
    if not os.path.exists(path):
        return []
    found = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if value.strip():
                found.append(name.strip())
    return found


def protected(worktree):
    """Does git in THIS worktree ignore `config/.env`? Refuse if not."""
    r = subprocess.run(["git", "check-ignore", "-q", REL],
                       cwd=worktree, capture_output=True)
    return r.returncode == 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="sync_worker_env")
    p.add_argument("--write", action="store_true",
                   help="copy the canonical file into each worktree")
    args = p.parse_args(argv)

    if not os.path.exists(CANONICAL):
        print(f"no canonical credential file at {REL} - nothing to sync")
        return 1

    canonical_names = names_in(CANONICAL)
    print(f"canonical {REL}: {len(canonical_names)} variables with values")
    for name in sorted(canonical_names):
        print(f"   {name}: AVAILABLE")

    body = None
    if args.write:
        with open(CANONICAL, "rb") as fh:
            body = fh.read()

    failures = 0
    for tree in worktrees():
        target = os.path.join(tree, REL)
        label = os.path.basename(tree.rstrip("\\/"))
        if not protected(tree):
            print(f"\n{label}: REFUSED - git here does not ignore {REL}")
            failures += 1
            continue
        if args.write:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as fh:
                fh.write(body)
        have = names_in(target)
        missing = sorted(set(canonical_names) - set(have))
        print(f"\n{label}: {len(have)} of {len(canonical_names)} variables")
        if missing:
            for name in missing:
                print(f"   {name}: MISSING")
            failures += 1
        else:
            print("   all AVAILABLE")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
