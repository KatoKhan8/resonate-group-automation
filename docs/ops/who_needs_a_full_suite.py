#!/usr/bin/env python3
"""TASK 0150, Q3 - how many of today's commits genuinely need a FULL suite
reference, and how many could be served by a module-scoped one?

READ-ONLY, offline, no lock. The authority is git in THIS clone
(C:\\Users\\Zvonimir\\qwc), which already holds every lane branch pushed today -
no fetch is performed, so this is what the clone knows, named as such.

THE RULE BEING APPLIED is the operator's, 2026-10-02, quoted in CLAUDE.md:
"A change under `src/` or under `tests/` ALWAYS gets a new reference, with no
exception." Everything else may use the bounded alternative, and only if no
module under src/ imports the changed file.
"""
import collections
import subprocess
import sys

SINCE = "2026-10-15 00:00"
UNTIL = "2026-10-16 00:00"


def git(*args):
    out = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    if out.returncode != 0:
        sys.stderr.write(out.stderr)
        raise SystemExit("git failed: " + " ".join(args))
    return out.stdout


def main():
    shas = git("log", "--all", "--since", SINCE, "--until", UNTIL,
               "--pretty=%H").split()
    # de-duplicate: --all walks every ref, a commit on two refs appears once
    # already (git log dedups), but be explicit about the count.
    rows = []
    for sha in shas:
        files = [f for f in git("show", "--pretty=", "--name-only", sha).split("\n")
                 if f.strip()]
        subj = git("show", "-s", "--pretty=%s", sha).strip()
        src = sorted({f for f in files if f.startswith("src/")})
        tst = sorted({f for f in files if f.startswith("tests/")})
        other = sorted({f for f in files
                        if not f.startswith(("src/", "tests/"))})
        rows.append(dict(sha=sha[:9], subj=subj, files=files, src=src,
                         tst=tst, other=other))

    needs_full = [r for r in rows if r["src"] or r["tst"]]
    no_code = [r for r in rows if not (r["src"] or r["tst"])]

    print("=" * 79)
    print("TODAY'S COMMITS, ACROSS EVERY REF THIS CLONE HOLDS")
    print("=" * 79)
    print("  commits today                         %4d" % len(rows))
    print("  touch src/ or tests/  -> FULL, no exception   %4d   %5.1f%%"
          % (len(needs_full), 100.0 * len(needs_full) / len(rows)))
    print("  touch neither         -> bounded alternative  %4d   %5.1f%%"
          % (len(no_code), 100.0 * len(no_code) / len(rows)))

    print()
    print("=" * 79)
    print("THE ONES THAT NEED A FULL REFERENCE: HOW WIDE IS THE CHANGE?")
    print("=" * 79)
    hist = collections.Counter()
    print("%-11s%5s%5s%6s  %s" % ("sha", "src", "tst", "other", "subject"))
    for r in sorted(needs_full, key=lambda r: len(r["src"]) + len(r["tst"])):
        n = len(r["src"]) + len(r["tst"])
        hist[min(n, 6)] += 1
        print("%-11s%5d%5d%6d  %s"
              % (r["sha"], len(r["src"]), len(r["tst"]), len(r["other"]),
                 r["subj"][:46]))
    print("-" * 79)
    print("  code files touched per commit (src/ + tests/):")
    for k in sorted(hist):
        label = "%d" % k if k < 6 else "6+"
        print("    %-4s %3d commits" % (label, hist[k]))
    small = sum(v for k, v in hist.items() if k <= 2)
    print("  commits touching <= 2 code files: %d of %d (%.1f%%)"
          % (small, len(needs_full), 100.0 * small / len(needs_full)))

    print()
    print("=" * 79)
    print("WHAT A MODULE-SCOPED REFERENCE WOULD HAVE TO COVER")
    print("=" * 79)
    print("  A module-scoped reference is only sound if NOTHING a test reads can")
    print("  observe the delta outside the named modules. Measured below: how many")
    print("  tests/ modules import, name or walk each changed src/ module. Not an")
    print("  argument from the kind of file - a measurement.")
    changed_src = sorted({f for r in needs_full for f in r["src"]})
    print("\n  distinct src/ files changed today: %d" % len(changed_src))
    for f in changed_src:
        mod = f[len("src/"):].rsplit(".", 1)[0].replace("/", ".")
        base = mod.rsplit(".", 1)[-1]
        hits = git("grep", "-l", "-e", base, "--", "tests/").split()
        print("    %-34s named in %3d of the tests/ modules" % (f, len(hits)))


if __name__ == "__main__":
    main()
