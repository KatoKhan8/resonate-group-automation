"""webapp/0410 step 3 - RE-DATE the comma-split-quote class under the
persisted instrument (branch tip, 0400), and print four verdicts.

The instrument is NOT modified: safe_dating.uniqueness_precheck, date_needle
and classify_commit are the committed bytes.  This file adds only (1) the
disambiguation ladder, (2) the SUBJECT-IDENTITY check 0390 built after its own
ladder produced two wrong greens, and (3) the verdict mapping.

LADDER DEFECT FOUND BY THE KNOWN-ANSWER CONTROL, 2026-10-17, and fixed here.
The first version of this file took the FIRST unique candidate in document
order as the winner and then subject-identity-checked it.  For row 8 that was
`#   64 files, not 2,502` at :832 - a COMMENT - so a dating whose published
figure is correct came back PERMANENTLY-AMBIGUOUS.  That is 0390's defect 1
reproduced by its successor: the ladder's `winner` is NECESSARY, never
SUFFICIENT, and a driver that picks one candidate and then tests it is testing
its own choice rather than the question.  The repair is not to relax the
subject-identity check - it is to stop choosing: every candidate is scored,
subject-identity SELECTS among the unique ones, and if two survive they must
date identically or the row is refused.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from safe_dating import date_needle, uniqueness_precheck, git  # noqa: E402
from step6_corrections import PUBLISHED, ESTATE, CONTESTED     # noqa: E402

LANE = r"C:\Users\Zvonimir\Desktop\resonate-ops\LANE-webapp.md"


def lane_text():
    return open(LANE, "rb").read().decode("utf-8")


def known_answer_from_lane():
    """Load 0390's confirmed value for the row-8 needle OUT OF the lane file.
    Never retyped: the 40-hex sha is read from 0390's own verdict block."""
    t = lane_text()
    i = t.index("#3  64 files, not 2,502            RE-DATED-UNCHANGED")
    m = re.search(r"\b([0-9a-f]{40})\b", t[i:i + 400])
    return m.group(1), i


def tip_from_lane():
    """Load the 0400 persistence tip sha OUT OF the lane file."""
    t = lane_text()
    i = t.index("    tip     ")
    m = re.search(r"\b([0-9a-f]{40})\b", t[i:i + 120])
    return m.group(1)


def blob_of(ref):
    sha = git(ESTATE, ["rev-parse", "%s:%s" % (ref, CONTESTED)])[0].decode().strip()
    return sha, git(ESTATE, ["cat-file", "blob", sha])[0]


def sites(data, needle_b):
    """1-indexed line numbers of every line containing the needle."""
    return [n for n, line in enumerate(data.split(b"\n"), 1) if needle_b in line]


def extend(data, needle_b, span):
    """Rung (a): widen the needle leftwards and rightwards on its own line."""
    cands = []
    for n, line in enumerate(data.split(b"\n"), 1):
        i = line.find(needle_b)
        while i != -1:
            lo = max(0, i - span)
            hi = min(len(line), i + len(needle_b) + span)
            cands.append((n, line[lo:hi].strip()))
            i = line.find(needle_b, i + 1)
    return cands


def run_row(row_no, label, needle_b, published, source, subject_locator,
            ref, ref_sha, data, known=None):
    print("#" * 78)
    print("# ROW %d  %s" % (row_no, label))
    print("#" * 78)
    n = needle_b.decode("utf-8")
    print("needle           %r  (%d B)" % (n, len(needle_b)))
    print("published dating %s" % published)
    print("source           %s" % source)
    print("reference        %s  blob %s  (%d B, CR=%d)"
          % (ref, ref_sha, len(data), data.count(b"\r")))

    print("-" * 78)
    print("SUBJECT LOCATOR  %r" % subject_locator.decode("utf-8"))
    subj = sites(data, subject_locator)
    print("SUBJECT SITES AT REFERENCE BLOB: %d  %s" % (len(subj), subj or "ABSENT"))

    prechecks = []
    print("-" * 78)
    print("PRECHECK 1 - bare needle, through the instrument's own uniqueness_precheck")
    v, cnt = uniqueness_precheck(ESTATE, CONTESTED, needle_b, ref)
    prechecks.append(("bare needle", n, v, cnt))

    verdict = None
    chosen = []
    if v == "UNIQUE-AT-REF":
        chosen = [(needle_b, sites(data, needle_b))]
        print("  bare needle is unique - no ladder needed.")
    else:
        print("-" * 78)
        print("LADDER - the bare needle was REFUSED, so disambiguation is")
        print("attempted.  EVERY candidate is scored; none is pre-selected.")
        tried = set()
        uniques, offsubject = [], []
        for span in (6, 12, 24, 40):
            for ln, cand in extend(data, needle_b, span):
                if cand in tried:
                    continue
                tried.add(cand)
                c = data.count(cand)
                pv = ("UNIQUE-AT-REF" if c == 1 else
                      "NEEDLE-ABSENT-AT-REF" if c == 0 else "AMBIGUOUS-NEEDLE")
                s = sites(data, cand)
                on = (s == subj) and bool(subj)
                print("  (a) EXTEND span=%-3d line %-5d count=%-3d %-21s "
                      "subject-identical=%-5s %r"
                      % (span, ln, c, pv, on, cand.decode("utf-8")[:62]))
                prechecks.append(("EXTEND span=%d" % span,
                                  cand.decode("utf-8"), pv, c))
                if c == 1:
                    (uniques if on else offsubject).append((cand, s))
        print("-" * 78)
        print("  UNIQUE candidates             : %d" % (len(uniques) + len(offsubject)))
        print("  of those SUBJECT-IDENTICAL    : %d" % len(uniques))
        print("  of those OFF-SUBJECT (refused): %d" % len(offsubject))
        for cand, s in offsubject:
            print("      REFUSED (unique, wrong text, line %s): %r"
                  % (s, cand.decode("utf-8")[:62]))
        chosen = uniques

    print("-" * 78)
    if not subj:
        print("SUBJECT-IDENTITY: FAIL - the subject does not exist at the "
              "reference blob, so no candidate can be it.")
        verdict = "PERMANENTLY-AMBIGUOUS"
    elif not chosen:
        print("SUBJECT-IDENTITY: FAIL - no unique candidate names the subject.")
        verdict = "PERMANENTLY-AMBIGUOUS"
    else:
        print("SUBJECT-IDENTITY: PASS for %d candidate(s)" % len(chosen))
        answers = []
        for cand, s in chosen:
            print()
            print("  DATING with %r  (sites %s)" % (cand.decode("utf-8")[:62], s))
            res = date_needle(ESTATE, CONTESTED, cand, ref=ref)
            answers.append((cand, tuple(res["confirmed"]), res["naive"]))
        uniq_answers = set(a for _c, a, _nv in answers)
        print("  NEEDLE-CHOICE-INDEPENDENCE: %d distinct answer(s) from %d "
              "subject-identical needles" % (len(uniq_answers), len(answers)))
        if len(uniq_answers) != 1:
            print("  -> the answer depends on which needle was chosen. REFUSE.")
            verdict = "PERMANENTLY-AMBIGUOUS"
        else:
            ci = list(uniq_answers)[0]
            naive = answers[0][2]
            print("  CONFIRMED-INTRODUCTIONS: %s" % (list(ci) or "NONE"))
            print("  NAIVE-OLDEST-HIT       : %s" % naive)
            if len(ci) == 1 and ci[0] == published:
                verdict = "UNCHANGED"
            elif len(ci) == 1:
                verdict = "MOVED"
            else:
                verdict = "PERMANENTLY-AMBIGUOUS"
            if ci and naive != ci[0]:
                print("  NOTE: naive and safe DISAGREE on this needle - "
                      "naive=%s safe=%s" % (naive, ci[0]))

    print("-" * 78)
    print("PRECHECKS RUN FOR THIS DATING: %d" % len(prechecks))
    for i, (which, text, pv, c) in enumerate(prechecks, 1):
        print("   %2d. %-16s count=%-3s %-22s %r" % (i, which, c, pv, text[:58]))
    print()
    print("ROW %d VERDICT: %s   (published %s)" % (row_no, verdict, published))
    if known is not None:
        ok = (verdict == "UNCHANGED" and published == known)
        print("KNOWN-ANSWER CONTROL: expected %s -> %s"
              % (known, "PASS" if ok else "FAIL"))
        if not ok:
            raise SystemExit("KNOWN-ANSWER CONTROL FAILED - STOP")
    print()
    return verdict, prechecks


def main():
    print("#" * 78)
    print("# webapp/0410 STEP 3 - RE-DATING THE COMMA-SPLIT QUOTE CLASS")
    print("#" * 78)
    tip = tip_from_lane()
    print("instrument tip (loaded from LANE-webapp.md, not retyped): %s" % tip)
    print("  git cat-file -t -> %s"
          % git(ESTATE, ["cat-file", "-t", tip])[0].decode().strip())
    known, at = known_answer_from_lane()
    print("known-answer sha (loaded from 0390 verdict block at byte %d): %s"
          % (at, known))
    ref_sha, data = blob_of("HEAD")
    print("reference blob    %s" % ref_sha)
    print("HEAD              %s"
          % git(ESTATE, ["rev-parse", "HEAD"])[0].decode().strip())
    print()

    SUBJ = {
        2: b'"now": "`master` is a different ref and diverged on 2026-10-15"',
        4: b'"now": "`master` is a different ref and diverged on 2026-10-15"',
        8: b'"defect": (r"64 files, not 2,502"',
        9: b'"defect": r"it now holds 64 files"',
    }
    ORDER = [(8, known), (9, None), (2, None), (4, None)]

    results = {}
    for row_no, kn in ORDER:
        label, needle_b, published, source = PUBLISHED[row_no - 1]
        v, pc = run_row(row_no, label, needle_b, published, source,
                        SUBJ[row_no], "HEAD", ref_sha, data, known=kn)
        results[row_no] = (v, len(pc), published)

    # DECLARED METHOD EXTENSION, 0390's shape: row 9's subject does not exist
    # at HEAD.  Re-run the SAME precheck and the SAME rule at the latest blob
    # that still holds it.  Named, not slipped in.
    print("#" * 78)
    print("# DECLARED METHOD EXTENSION - ROW 9 AT A REFERENCE WHERE ITS")
    print("# SUBJECT EXISTS.  This is NOT the brief's reference and does NOT")
    print("# change row 9's verdict above.")
    print("#" * 78)
    alt = None
    tl = list(reversed(git(ESTATE, ["log", "--format=%H", "--", CONTESTED])[0]
                       .decode().split()))
    for sha in reversed(tl):
        s, d = blob_of(sha)
        if sites(d, SUBJ[9]):
            alt = (sha, s, d)
            break
    if alt is None:
        print("  no commit in the timeline holds the subject - UNKNOWN")
    else:
        sha, s, d = alt
        print("  latest blob holding the subject: %s  blob %s" % (sha, s))
        label, needle_b, published, source = PUBLISHED[8]
        run_row(9, label + "  [ALT REF %s]" % sha[:9], needle_b, published,
                source, SUBJ[9], sha, s, d)

    print("#" * 78)
    print("# VERDICT TABLE (at the brief's reference only)")
    print("#" * 78)
    for row_no, (v, npc, published) in sorted(results.items()):
        print("  ROW %-2d  %-24s prechecks=%d  published %s"
              % (row_no, v, npc, published))


if __name__ == "__main__":
    main()
