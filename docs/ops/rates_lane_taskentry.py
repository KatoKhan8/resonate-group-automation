#!/usr/bin/env python3
"""rates_lane_taskentry.py - the hand validation, and the C4 self-check.

It writes lane_taskentry_handvalidation.tsv (every verdict with the reason it
rests on) and then reports the false-positive and false-negative rates of
Find-LaneTaskEntry over the seven real lane files.

C4, AND WHY IT IS HERE. "A rule that reports zero errors from an unexercised
matcher is the B7 shape this estate has hit twice." So this script REFUSES to
print a rate unless all three controls have been observed in BOTH of their
states, read from artifacts on disk rather than asserted in prose:

  C1  lane_taskentry_test.out.txt  shows U1 PASS (a MATCH) and U2 PASS (a
                                   NO_MATCH) - the matcher said both words.
  C2  lane_taskentry_mutants.out.txt
                                   shows two mutants, each killing a named,
                                   non-empty, DIFFERENT set.
  C3  this file's own tables       contain at least one hand-validated error
                                   in EACH direction. A validation that found
                                   no false positive and no false negative has
                                   not been shown to be able to find one.

If any of those is unmet the script prints UNVALIDATED and exits non-zero, and
the rule is to be reported as written-and-unvalidated rather than landed.

THE GROUND TRUTH IS HAND-MADE AND THE REASONS ARE IN THE TABLE. Not "I looked
and it was fine" - every row names what was read. The three classes of true
negative below are each a measurement someone can repeat:

  NEVER-RAN    the queue's DONE folder holds no record of that task id, so no
               entry could exist yet.
  RAN-FAILED   the only DONE record is exit1 / exit-1, a provider refusal or
               an error; the standing rules do not expect an entry.
  RAN-NO-ENTRY the task exited 0 and the lane file itself says, in words, that
               no entry was written - or the entry is demonstrably absent.
"""
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MEASURE = os.path.join(HERE, "lane_taskentry_measurement.tsv")
TESTLOG = os.path.join(HERE, "lane_taskentry_test.out.txt")
MUTLOG = os.path.join(HERE, "lane_taskentry_mutants.out.txt")
OUT = os.path.join(HERE, "lane_taskentry_handvalidation.tsv")

# ---------------------------------------------------------------- C3 tables
#
# THE FALSE-NEGATIVE CENSUS IS COMPLETE, NOT SAMPLED. All 26 rule-C NO_MATCH
# rows were read by hand. A census beats a sample where the population is this
# small, and the false-negative direction is the one that matters: it is the
# direction in which a skip-based rule would have lost work.
FN_CENSUS = {
    # (lane, id): (verdict, reason)
    ("glm", "0040"): ("TN", "RAN-NO-ENTRY: LANE-glm.md:1263 says in words 'No lane entry exists for 0040'"),
    ("glm", "0055"): ("TN", "RAN-NO-ENTRY: the record was lost, not the work - _STANDING-RULES.md records this; only commit-message quotations at :1353 and :1501"),
    ("glm", "0063"): ("FN", "ENTRY EXISTS UNDER ANOTHER TASK'S NUMBER: 0063's deliverable was 0060's entry and it is filed as 0060 (:1122 'TASK 0063 ordered this close', :1323 names lane-entry-0060.md)"),
    ("glm", "0078"): ("TN", "RAN-FAILED: both DONE records are exit1"),
    ("glm", "0079"): ("TN", "RAN-FAILED: the only DONE record is exit1"),
    ("glm", "0080"): ("TN", "NEVER-RAN: no DONE record"),
    ("glm-b", "0040"): ("TN", "RAN-NO-ENTRY: 709 bytes, no lane growth - LANE-glm-b.md:269 records it; this task is why the NOWORK guard exists"),
    ("glm-b", "0050"): ("TN", "RAN-NO-ENTRY: 2,112 bytes of plan prose, no lane growth - LANE-glm-b.md:270"),
    ("glm-b", "0145"): ("FN", "ENTRY EXISTS UNDER A DIFFERENT HEADING FORM: LANE-glm-b.md:1470 '## 2026-10-15 23:55 - glm-b/0145 SAVE SWEEP' - lane/NNNN, no TASK keyword. Operationally harmless: a save sweep is exempt from the check"),
    ("glm-b", "0171"): ("TN", "NEVER-RAN: no DONE record"),
    ("glm-b", "0181"): ("TN", "RAN-FAILED: the only DONE record is exit1"),
    ("glm-b", "0200"): ("TN", "NEVER-RAN: no DONE record"),
    ("glm-c", "0110"): ("FN", "ENTRY EXISTS UNDER ANOTHER TASK'S NUMBER: LANE-glm-c.md:405 is headed TASK 0100 and says 'ENTRY WRITTEN BY THE 0110 RUN'"),
    ("pilotcaps", "0241"): ("TN", "RAN-FAILED: the only DONE record is exit-1"),
    ("pilotcaps", "0250"): ("TN", "NEVER-RAN: in RUNNING now, no DONE record"),
    ("pilotcaps", "0251"): ("TN", "NEVER-RAN: no DONE record"),
    ("pilotcaps", "0252"): ("TN", "NEVER-RAN: no DONE record"),
    ("qwen", "0010"): ("TN", "RAN-NO-ENTRY: LANE-qwen.md:359 'wrote to stdout only' and :1235 'no TASK-labelled entry exists for either'"),
    ("qwen", "0020"): ("TN", "RAN-NO-ENTRY: same two lines; the single 0020 mention at :861 is pilotcaps' task 0020, another lane's number"),
    ("qwen", "0178"): ("TN", "NEVER-RAN: this task, in RUNNING now"),
    ("qwen", "0195"): ("TN", "NEVER-RAN: no DONE record"),
    ("qwen", "0230"): ("TN", "NEVER-RAN: no DONE record"),
    ("suppression", "0400"): ("TN", "NEVER-RAN: no DONE record"),
    ("webapp", "0260"): ("TN", "NEVER-RAN: in RUNNING now; the only mention is `TASK-0260`'s own run inside another entry's prose at :7737"),
    ("webapp", "0270"): ("TN", "NEVER-RAN: no DONE record; the only mention is a path, logs\\TASK-0270\\measure-0270.py:82, at :7450"),
    ("webapp", "0280"): ("TN", "NEVER-RAN: no DONE record"),
}

# THE FALSE-POSITIVE SAMPLE IS TWO PARTS, and the first part is not random.
#
#   PART 1, IN FULL: every rule-C MATCH whose brief is PENDING IN THE QUEUE
#   RIGHT NOW. These are not a sample of anything - they are the exact
#   annotations the next seven dispatches would emit, so a false positive here
#   is a note a session actually reads. All 9 were read by hand.
#
#   PART 2, SEEDED RANDOM: 30 of the remaining 193, random.seed(178),
#   random.sample over the rows sorted as the measurement emitted them.
FP_SAMPLE = {
    # part 1 - the pending briefs, in full
    ("glm-c", "0163"): ("TP", "PENDING: ':2456 ## TASK 0163 (GLM-C): the brake proof that could not run'"),
    ("glm-c", "0164"): ("TP", "PENDING: ':2726 TASK 0164 - get the brake ready to ship - PARTIAL ENTRY'"),
    ("glm-c", "0230"): ("TP", "PENDING: ':2130 TASK 0230: the write ledger names the step'"),
    ("glm-c", "0240"): ("TP", "PENDING: ':2263 TASK 0240 ... DONE, commit c05a37520 (pushed)'"),
    ("qwen", "0180"): ("TP", "PENDING: ':5554 # TASK 0180 - rotate a lane without killing its work'"),
    ("qwen", "0190"): ("TP", "PENDING: ':6256 # TASK 0190 - the ruleset is real, so the push hole is closed'"),
    ("qwen", "0200"): ("TP", "PENDING: ':6739 # TASK 0200 - THE ORPHAN RESOLVER IS BUILT AND PROVEN'"),
    ("qwen", "0210"): ("TP", "PENDING: ':7016 # TASK 0210 - THE LAUNCHER NOW CHECKS'"),
    ("qwen", "0220"): ("TP", "PENDING: ':7254 # TASK 0220 - THE DESKTOP IS FINISHED'"),
    # part 2 - the seeded random 30
    ("glm-b", "0020"): ("TP", "entry heading, 'TASK 0020 closed (whole-queue copylint, by name)'"),
    ("glm-b", "0080"): ("TP", "entry heading, 'TASK 0080 - D3: the pause row that denies a provider stop'"),
    ("glm-b", "0120"): ("TP", "entry heading"),
    ("glm-b", "0130"): ("TP", "entry heading, 'finish 0110: the derivation lands'"),
    ("glm-b", "0140"): ("TP", "entry heading"),
    ("glm-c", "0070"): ("FP", "THE ONLY LINE IS ':397 2026-10-15 - TASK 0070 STARTED'. A start marker is not a record of work. Counted against the rule, though the note's own wording sends a reader to the line, which says STARTED"),
    ("glm-c", "0090"): ("TP", "entry, 'TASK 0090 - DONE, SKELETON BUILT'"),
    ("glm-c", "0130"): ("TP", "entry heading, 'DONE, commit 8473d61ec (pushed)'"),
    ("glm-c", "0200"): ("TP", "entry heading, 'DONE, commit 0c687f813 (pushed)'"),
    ("pilotcaps", "0020"): ("TP", "entry heading, 'RECOVERED AND APPENDED LATE (by 0070)'"),
    ("pilotcaps", "0030"): ("TP", "entry heading, 'the write-path fix, PROPOSED'"),
    ("pilotcaps", "0090"): ("TP", "entry heading, 'GATE UNMET, THE SIX CHECKS NOT RE-RUN' - a stop on an unmet gate IS an entry, per the standing rules"),
    ("pilotcaps", "0120"): ("TP", "entry heading, 'SHEET VERIFIED, no commit'"),
    ("pilotcaps", "0140"): ("TP", "entry heading"),
    ("pilotcaps", "0233"): ("TP", "entry heading, 'BOTH CLAIMS MEASURED'"),
    ("pilotcaps", "0246"): ("TP", "entry heading"),
    ("qwen", "0040"): ("TP", "entry heading, 'pricing the two real boundaries'"),
    ("qwen", "0150"): ("TP", "entry heading"),
    ("qwen", "0175"): ("TP", "entry heading"),
    ("suppression", "0020"): ("TP", "entry heading"),
    ("suppression", "0070"): ("TP", "entry heading"),
    ("suppression", "0110"): ("TP", "entry heading"),
    ("suppression", "0180"): ("TP", "entry heading, TASK-0180 hyphen form"),
    ("suppression", "0190"): ("TP", "entry heading, TASK-0190 hyphen form"),
    ("suppression", "0396"): ("TP", "entry heading, 'preconditions measured; the measurement phase is UNFINISHED' - a partial entry is still an entry"),
    ("webapp", "0110"): ("TP", "entry heading"),
    ("webapp", "0190"): ("TP", "entry heading, TASK-0190 hyphen form"),
    ("webapp", "0200"): ("TP", "entry heading"),
    ("webapp", "0220"): ("TP", "entry heading"),
    ("webapp", "0235"): ("TP", "entry heading, 'PUSHED. bad54f516 IS ON ORIGIN'"),
}


def load_measurement():
    with open(MEASURE, encoding="utf-8", errors="replace") as fh:
        return [r for r in csv.DictReader(fh, delimiter="\t") if r.get("ID") and r["ID"] != "NOID"]


def c1_ok():
    """The matcher printed MATCH and printed NO MATCH, in the test log."""
    if not os.path.exists(TESTLOG):
        return False, "missing " + TESTLOG
    txt = open(TESTLOG, encoding="utf-8", errors="replace").read()
    m = "PASS  U1 known entry MATCH" in txt and "state=MATCH" in txt
    n = "PASS  U2 invented id NO_MATCH" in txt and "state=NO_MATCH" in txt
    if m and n:
        return True, "U1 printed a MATCH at a named line, U2 printed a NO_MATCH"
    return False, "U1 match=%s U2 nomatch=%s" % (m, n)


def c2_ok():
    """Two mutants, each killing a named, non-empty, different set."""
    if not os.path.exists(MUTLOG):
        return False, "missing " + MUTLOG
    txt = open(MUTLOG, encoding="utf-8", errors="replace").read()
    sets = {}
    cur = None
    for line in txt.splitlines():
        m = re.match(r"=== mutant (\S+) =", line)
        if m:
            cur = m.group(1)
        m = re.match(r"\s+killed (\d+): (.*)$", line)
        if m and cur:
            sets[cur] = set(x.strip() for x in m.group(2).split(",") if x.strip() and x.strip() != "NOTHING")
    if len(sets) < 2:
        return False, "fewer than two mutants in the log"
    names = sorted(sets)
    for n in names:
        if not sets[n]:
            return False, "mutant %s killed NOTHING - reportable" % n
    if sets[names[0]] == sets[names[1]]:
        return False, "both mutants killed the same set"
    return True, "; ".join("%s killed %d {%s}" % (n, len(sets[n]), ",".join(sorted(sets[n]))) for n in names)


def main():
    rows = load_measurement()
    by_key = {(r["LANE"], r["ID"]): r for r in rows}

    # The tables must describe the population they claim to describe.
    nomatch = {k for k, r in by_key.items() if r["C_shipped"] == "NO_MATCH"}
    match = {k for k, r in by_key.items() if r["C_shipped"] == "MATCH"}
    stale = []
    if set(FN_CENSUS) != nomatch:
        stale.append("the FN census does not equal the current NO_MATCH set: "
                     "only-in-table %s ; only-in-measurement %s"
                     % (sorted(set(FN_CENSUS) - nomatch), sorted(nomatch - set(FN_CENSUS))))
    if not set(FP_SAMPLE) <= match:
        stale.append("the FP sample contains rows that are not MATCH now: %s"
                     % sorted(set(FP_SAMPLE) - match))

    with open(OUT, "w", encoding="ascii", newline="\n") as fh:
        fh.write("LANE\tID\tRULE_C\tVERDICT\tREASON\n")
        for tbl in (FN_CENSUS, FP_SAMPLE):
            for (lane, tid), (v, why) in sorted(tbl.items()):
                st = by_key.get((lane, tid), {}).get("C_shipped", "GONE")
                fh.write("%s\t%s\t%s\t%s\t%s\n" % (lane, tid, st, v, why))

    fp = [k for k, v in FP_SAMPLE.items() if v[0] == "FP"]
    fn = [k for k, v in FN_CENSUS.items() if v[0] == "FN"]

    c1, c1why = c1_ok()
    c2, c2why = c2_ok()
    c3 = bool(fp) and bool(fn)
    c3why = ("%d false positive(s) and %d false negative(s) found by hand - the "
             "validation is capable of finding both" % (len(fp), len(fn)))
    if not c3:
        c3why = ("the hand validation found %d FP and %d FN. A direction with zero "
                 "found errors has not been shown to be measurable." % (len(fp), len(fn)))

    print("=== C4 self-check ==========================================")
    print("  C1 matcher printed both states : %s   %s" % ("YES" if c1 else "NO ", c1why))
    print("  C2 paired mutants              : %s   %s" % ("YES" if c2 else "NO ", c2why))
    print("  C3 both error kinds found      : %s   %s" % ("YES" if c3 else "NO ", c3why))
    for s in stale:
        print("  STALE: " + s)
    if not (c1 and c2 and c3) or stale:
        print("")
        print("  UNVALIDATED. No rate is reported. Per the task's fail-closed clause the")
        print("  rule is written-and-unvalidated and must not be landed on these numbers.")
        return 1

    print("")
    print("=== rates, Find-LaneTaskEntry over the seven real lane files ===")
    print("  population            %d distinct (lane, task) pairs" % len(rows))
    print("  rule C said MATCH     %d" % len(match))
    print("  rule C said NO_MATCH  %d" % len(nomatch))
    print("")
    print("  FALSE POSITIVES  %d / %d hand-validated MATCH rows = %.1f%%"
          % (len(fp), len(FP_SAMPLE), 100.0 * len(fp) / len(FP_SAMPLE)))
    for k in sorted(fp):
        print("      %s/%s  %s" % (k[0], k[1], FP_SAMPLE[k][1]))
    print("")
    print("  FALSE NEGATIVES  %d / %d NO_MATCH rows (FULL CENSUS, not a sample) = %.1f%%"
          % (len(fn), len(FN_CENSUS), 100.0 * len(fn) / len(FN_CENSUS)))
    for k in sorted(fn):
        print("      %s/%s  %s" % (k[0], k[1], FN_CENSUS[k][1]))
    print("")
    print("  hand-validated %d of %d pairs (%.0f%%)"
          % (len(FP_SAMPLE) + len(FN_CENSUS), len(rows),
             100.0 * (len(FP_SAMPLE) + len(FN_CENSUS)) / len(rows)))
    print("  table written: " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
