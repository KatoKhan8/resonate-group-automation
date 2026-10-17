"""webapp/0410 step 2 - classify every published dating against the
COMMA-SPLIT QUOTE PREDICATE.

Nothing is retyped.  The 10 published datings are IMPORTED from the persisted
`step6_corrections.PUBLISHED`; the quote needles are computed by applying
`now.split(",")[0]` to RECOMMENDATIONS exec'd out of each commit's blob.
"""
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from step6_corrections import PUBLISHED, ESTATE, CONTESTED  # noqa: E402
from census_q import registry_at, timeline, git             # noqa: E402


def main():
    print("#" * 78)
    print("# webapp/0410 STEP 2 - CLASS MEMBERSHIP, MECHANICAL")
    print("#" * 78)
    print()
    src = open(os.path.join(HERE, "step6_corrections.py"), "rb").read()
    print("PUBLISHED list imported from step6_corrections.py  %d B sha256 %s"
          % (len(src), hashlib.sha256(src).hexdigest()))
    print("M (published datings in the list) = %d" % len(PUBLISHED))
    print()

    tl = timeline()
    # the predicate's output set, and the full `now` values, per commit
    qset = {}      # needle -> list of (sha, idx)
    nowset = {}    # now value -> list of (sha, idx)
    for sha in tl:
        recs, _lit, _b = registry_at(sha)
        for k, e in enumerate(recs, 1):
            qset.setdefault(e["now"].split(",")[0], []).append((sha, k))
            nowset.setdefault(e["now"], []).append((sha, k))
    print("Q = predicate output set, |Q| = %d" % len(qset))
    for q in sorted(qset):
        print("    %r" % q)
    print()

    rows = []
    for i, (label, needle_b, published, source) in enumerate(PUBLISHED, 1):
        n = needle_b.decode("utf-8")
        a = n in qset                       # IS the predicate's output
        # inside some entry's full `now` VALUE?
        in_now = [(v, w) for v, w in nowset.items() if n in v]
        # inside the TRUNCATED needle of that same entry?
        b_only = []
        for v, w in in_now:
            trunc = v.split(",")[0]
            if n not in trunc:
                b_only.append((v, w))
        # a hand-made SUBSTRING of a predicate output (0360 chose it by judgement)
        sub_of_q = [q for q in qset if n != q and n in q]
        if a:
            cls = "A  PREDICATE-OUTPUT"
        elif b_only:
            cls = "B  COMMA-SPLIT-DEPENDENT"
        elif sub_of_q:
            cls = "C  SUBSTRING-OF-A-PREDICATE-OUTPUT (hand-chosen)"
        elif in_now:
            cls = "D  inside a `now` and inside its truncation too"
        else:
            cls = "E  OUTSIDE every `now` - predicate irrelevant"
        rows.append((i, label, n, published, cls, a, bool(b_only), sub_of_q, in_now))
        print("-" * 78)
        print("ROW %2d  %s" % (i, label))
        print("   needle    %r  (%d B)" % (n, len(needle_b)))
        print("   published %s" % published)
        print("   == a predicate output ?            %s" % a)
        print("   inside some entry's full `now` ?   %s" % ([w for _v, w in in_now] or "no"))
        print("   inside that entry's TRUNCATION ?   %s"
              % ("no -> the containment is created by what follows the comma"
                 if b_only else ("yes" if in_now else "n/a")))
        print("   substring of a predicate output ?  %s" % (sub_of_q or "no"))
        print("   CLASS     %s" % cls)
    print("-" * 78)
    print()
    for key, name in (("A", "A  PREDICATE-OUTPUT"),
                      ("B", "B  COMMA-SPLIT-DEPENDENT"),
                      ("C", "C  SUBSTRING-OF-A-PREDICATE-OUTPUT (hand-chosen)"),
                      ("D", "D  inside a `now` and inside its truncation too"),
                      ("E", "E  OUTSIDE every `now` - predicate irrelevant")):
        hits = [r[0] for r in rows if r[4] == name]
        print("CLASS %s : %d of %d   rows %s" % (key, len(hits), len(PUBLISHED), hits or "-"))
    print()
    print("THE CLASS THE BRIEF NAMES, strict reading  (A)        : %d of %d"
          % (len([r for r in rows if r[4].startswith("A")]), len(PUBLISHED)))
    print("THE CLASS 0380's COUPLING FINDING NAMES    (A + B)    : %d of %d"
          % (len([r for r in rows if r[4][0] in "AB"]), len(PUBLISHED)))


if __name__ == "__main__":
    main()
