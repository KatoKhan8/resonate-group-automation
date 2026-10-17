"""webapp/0380 step 6 - the OPERATOR correction list, measured.

Every needle this lane's 0330 and 0360 record actually SEARCHED or published a
dating against is run through the safe instrument.  The output is a LIST: what
the naive oldest-hit says, what the safe rule says, and whether the published
dating would move.  Nothing is applied - correcting a published entry and any
registry edit is the operator's decision.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from safe_dating import date_needle, git  # noqa: E402


def _resolve_estate(argv):
    """Resolve the estate worktree this instrument READS.  webapp/0420.

    0400 persisted this as a hardcoded absolute path, and recorded the
    consequence as a finding: when that one worktree goes away, arm (a) and the
    whole of step 6 stop working.  Resolution order now:

      1. an explicit `--estate <path>` argument, which always wins;
      2. otherwise the nearest ancestor of THIS FILE that is a git work tree -
         the zero-config answer when the instrument is checked out at
         tools/safe_dating_check/ inside the estate it reads;
      3. otherwise REFUSE, loudly, naming the argument and the directory walked.

    A path that is not a git work tree is a refusal too.  There is no fallback
    to the cwd: an instrument that dates commits must never guess which
    repository it is dating.
    """
    path = None
    if "--estate" in argv:
        i = argv.index("--estate")
        if i + 1 >= len(argv):
            raise SystemExit("REFUSED: --estate needs a path argument.")
        path = argv[i + 1]
    else:
        probe = HERE
        while True:
            if os.path.exists(os.path.join(probe, ".git")):
                path = probe
                break
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
    if path is None:
        raise SystemExit(
            "REFUSED: cannot resolve the estate worktree.  No ancestor of\n"
            "  %s\n"
            "contains a .git, so this instrument is not checked out inside the\n"
            "repository it reads.  Pass it explicitly:\n"
            "  py -3 -B %s --estate <path-to-estate-worktree>"
            % (HERE, os.path.basename(os.path.abspath(__file__))))
    path = os.path.abspath(path)
    if not os.path.isdir(path) or not os.path.exists(os.path.join(path, ".git")):
        raise SystemExit(
            "REFUSED: %r is not a git work tree - no .git there, so no commit\n"
            "in it can be read.  Arm (a) and step 6 read REAL history from the\n"
            "estate; they do not invent one, and they do not silently fall back\n"
            "to the current directory." % path)
    return path


ESTATE = _resolve_estate(sys.argv[1:])
CONTESTED = "src/contested.py"

# (label, needle, the dating the lane PUBLISHED against it, source entry)
PUBLISHED = [
    ("0360 substitute needle #1 (the one 0360 switched TO)",
     b'"path": "CONTINUITY.md"',
     "3a623688973cbcc61ec53d235f3da14b32c72ae7",
     "0360: 'both -> 3a6236889, and only that commit'"),

    ("0360 substitute needle #2",
     b"is a different ref and diverged on",
     "3a623688973cbcc61ec53d235f3da14b32c72ae7",
     "0360: 'both -> 3a6236889, and only that commit'"),

    ("0360's named-defective needle: the also-place filename",
     b"DECISIONS-OPEN-2026-10-16.md",
     "3a623688973cbcc61ec53d235f3da14b32c72ae7",
     "0360: 'has the same defect ... the filename sits in entry #2's "
     "`change` prose at :657 of 3a6236889'"),

    ("the coupled needle itself (entry #2's defect clause, bare)",
     b"diverged on 2026",
     "3a623688973cbcc61ec53d235f3da14b32c72ae7",
     "0360: the naive answer it refused to use; AROSE-AT is 608e46ea5"),

    ("entry #2's defect clause, disambiguated by its key",
     b'"defect": r"diverged on 2026"',
     "608e46ea599526668ce0fe83782a90047b06c6af",
     "0360: AROSE-AT-608e46ea5"),

    ("entry #2's also place, disambiguated by its key",
     b'"also": ("DECISIONS-OPEN-2026-10-16.md",)',
     "608e46ea599526668ce0fe83782a90047b06c6af",
     "0360: 'the `also` place ... was introduced by that same commit'"),

    ("entry #1's defect clause, bare",
     b"Nobody has yet explained the local divergence",
     "608e46ea599526668ce0fe83782a90047b06c6af",
     "0360: #1 INDEPENDENT, first arising 608e46ea5"),

    ("entry #3's defect clause 1 at HEAD, bare",
     b"64 files, not 2,502",
     "f55fc043a6f6e73231bc123638628f6d0f077ca1",
     "0360: #3 INDEPENDENT, first arising f55fc043a"),

    ("entry #3's PRE-0310 single defect clause, bare",
     b"it now holds 64 files",
     "608e46ea599526668ce0fe83782a90047b06c6af",
     "0360: #3 FATAL-DIRECTION arose 608e46ea5 (clause == needle)"),

    ("the `defect` key itself (0360's '0 times in that whole blob')",
     b'"defect":',
     "608e46ea599526668ce0fe83782a90047b06c6af",
     "0360: '\"defect\":\" occurs 0 times in that whole blob' at 3a6236889"),
]


def main():
    print("#" * 78)
    print("# webapp/0380 STEP 6 - OPERATOR CORRECTION LIST (LISTED, NOT APPLIED)")
    print("#" * 78)
    print()
    print("estate repo  : %s" % ESTATE)
    print("HEAD         : %s" % git(ESTATE, ["rev-parse", "HEAD"])[0].decode().strip())
    print("origin/master: %s" % git(ESTATE, ["rev-parse", "origin/master"])[0].decode().strip())
    print("path         : %s" % CONTESTED)
    print("needles      : %d" % len(PUBLISHED))
    print()

    rows = []
    for label, needle, published, source in PUBLISHED:
        print("#" * 78)
        print("# %s" % label)
        print("#   published dating : %s" % published)
        print("#   published where  : %s" % source)
        print("#" * 78)
        res = date_needle(ESTATE, CONTESTED, needle, ref="HEAD")
        naive = res["naive"]
        safe = res["confirmed"]
        pre = res["precheck"]

        if pre != "UNIQUE-AT-REF":
            status = "REFUSED-BY-PRECHECK"
        elif safe == [published]:
            status = "UNCHANGED"
        elif len(safe) == 1:
            status = "WOULD-MOVE"
        else:
            status = "AMBIGUOUS-RESULT"

        naive_agrees = (naive == published)
        rows.append((label, published, naive, safe, pre, status, naive_agrees))

    print("#" * 78)
    print("# THE LIST")
    print("#" * 78)
    print()
    hdr = ("%-58s %-10s %-10s %-10s %-20s %s"
           % ("needle", "published", "naive", "safe", "precheck", "status"))
    print(hdr)
    print("-" * len(hdr))
    counts = {}
    for label, published, naive, safe, pre, status, naive_agrees in rows:
        print("%-58s %-10s %-10s %-10s %-20s %s" % (
            label[:58],
            published[:9],
            (naive or "NONE")[:9],
            (safe[0][:9] if len(safe) == 1 else ("NONE" if not safe else "MULTI")),
            pre,
            status,
        ))
        counts[status] = counts.get(status, 0) + 1
    print()
    print("DENOMINATOR: %d published datings examined" % len(rows))
    for k in sorted(counts):
        print("   %-22s %d of %d" % (k, counts[k], len(rows)))
    print()
    print("CORRECTIONS THE SAFE RULE WOULD MAKE (operator's to apply):")
    any_corr = False
    for label, published, naive, safe, pre, status, naive_agrees in rows:
        if status == "WOULD-MOVE":
            print("   MOVE  %s" % label)
            print("         published %s  ->  safe %s" % (published, safe[0]))
            any_corr = True
        elif status == "REFUSED-BY-PRECHECK":
            print("   REFUSE %s" % label)
            print("          precheck %s; the published %s is NOT derivable from"
                  % (pre, published[:9]))
            print("          this needle and must be re-derived from a unique one.")
            any_corr = True
    if not any_corr:
        print("   NONE")
    print()
    print("NAIVE-vs-SAFE DISAGREEMENTS (where the old instrument differs):")
    n_dis = 0
    for label, published, naive, safe, pre, status, naive_agrees in rows:
        if len(safe) == 1 and naive != safe[0]:
            print("   %s: naive %s  safe %s" % (label[:56], naive[:9], safe[0][:9]))
            n_dis += 1
        elif pre != "UNIQUE-AT-REF":
            print("   %s: naive %s  safe REFUSES (%s)" % (label[:56], (naive or "NONE")[:9], pre))
            n_dis += 1
    print("   disagreements: %d of %d" % (n_dis, len(rows)))


if __name__ == "__main__":
    main()
