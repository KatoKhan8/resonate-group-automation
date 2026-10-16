# TASK-0090 -- stage runner.
#
#   --stage reach      run 0080's UNCHANGED extract.py over LANE-pilotcaps.md
#                      and report what it can and cannot see: the foreign-
#                      corpus reach of the home instrument.  A line-level
#                      verdict census (independent of any unit grammar)
#                      names every verdict-shaped line neither instrument
#                      covers -- that is the measured recall boundary.
#   --stage classify   adapted extraction (extract_pilotcaps.py) + 0080's
#                      UNCHANGED classify.py over the same file; print the
#                      pre-gate table with exclusion marks.
#   --stage controls   C1: two synthetic records written as pilotcaps-dialect
#                      TEXT through the adapter -- the size-identical
#                      same-second revert must print AFFECTED, the named
#                      kill with a stated signature must print SAFE; both
#                      printed.  C2: a kill whose reason is described but
#                      never named, with no size/second/pyc/load-proof fact
#                      -- must print UNKNOWN.  C3: re-run 0080's own
#                      extract+classify over LANE-glm.md and reproduce the
#                      verdicts 0080 recorded, row by row, five of them
#                      printed, plus a full distribution drift check (55
#                      kept / SAFE 30 / UNKNOWN 19 / AFFECTED 6, 71 records
#                      0 unparsed).  Any drift is an implementation defect
#                      and is fixed in the adapter, never in the rule.
#                      C4 gate: THE table is printed only if C1 shows both
#                      states, C2 prints UNKNOWN, and C3 reproduces -- and
#                      an all-clear-shaped table (UNKNOWN==0 or AFFECTED==0)
#                      is refused outright.
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODEX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CODEX, "0080"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import extract                     # noqa: E402  0080's, UNCHANGED
import extract_pilotcaps           # noqa: E402  the adapter
from classify import classify_records, tally   # noqa: E402  UNCHANGED
import run_0080                    # noqa: E402  for EXCLUSIONS provenance

LANE_PILOTCAPS = r"C:\Users\Zvonimir\Desktop\resonate-ops\LANE-pilotcaps.md"
LANE_GLM = r"C:\Users\Zvonimir\Desktop\resonate-ops\LANE-glm.md"

# 0080's recorded output (LANE-glm.md L4297-4319), the C3 authority.
REF_0080_TOTAL = 71          # records before exclusions, 0 unparsed
REF_0080_KEPT = 55
REF_0080_TALLY = {"SAFE": 30, "UNKNOWN": 19, "AFFECTED": 6}
REF_AFFECTED_LINES = [3284, 3911, 3915, 4085, 4125, 4127]
REF_UNKNOWN_LINES = {56: 2, 165: 5, 186: 1, 759: 1, 764: 1, 1181: 1,
                     1183: 1, 1186: 1, 1194: 1, 1198: 1, 1925: 1,
                     1929: 1, 1933: 1, 2557: 1}
C3_PRINTED = [3284, 4085, 1181, 2557]      # + first SAFE in 3060-3211

# pilotcaps exclusions -- DOCUMENTED per line, filled only after the
# pre-gate table and a read-back of each region (0080's discipline).
# Every false-vocabulary product of the dialect extension is excluded HERE,
# per line, with the read-back evidence -- the patterns stay because each
# also has at least one genuine product.
EXCLUSIONS = {
    # ---- barrier-holds / fixture tables whose **YES**/**no** is a column,
    #      not a verdict (V1 readback correction, header note in the adapter)
    862: "barrier-holds table row: '**YES**' is the prospect column, not a kill verdict",
    863: "barrier-holds table row: '**YES**' is the prospect column, not a kill verdict",
    868: "barrier-holds table row: '**YES**' is the prospect column, not a kill verdict",
    869: "barrier-holds table row: '**YES**' is the prospect column, not a kill verdict",
    870: "barrier-holds table row: '**YES**' is the prospect column, not a kill verdict",
    871: "barrier-holds table row: '**YES**' is the prospect column, not a kill verdict",
    872: "barrier-holds table row: '**YES**' is the prospect column, not a kill verdict",
    1178: "same barrier table (web resume row): trailing '**YES**' is the prospect column",
    15248: "terminator fixture table: '**no**' = 'load does not see it', not a kill verdict",
    # ---- suite tallies and prose where FAILED/survives/caught is not about
    #      a mutant (uniform teeth-proof-vs-baseline line; 0080 L3103 class)
    1852: "copy-contract check row: FAILED is the envelope check (BODY_1 = 89), not a mutant kill",
    1923: "prose: 'how much survives without the operator's machine' -- offline runnability, not a mutant",
    1971: "instrument-fault prose: 'caught' = the control catching a miscount, not a mutant",
    2509: "process near-miss: 'caught it at the staging step' (git status catching CRLF noise)",
    2973: "prose: 'no '-m unittest' process of mine survives'",
    3938: "prose: 'no subprocess of mine survives' (closing-state paragraph)",
    4132: "lint wording correction: 'the block survives it' -- prose about a sign-off regex",
    6921: "BEFORE/AFTER suite baselines: FAILED is the standing red baseline, not a mutant kill",
    6922: "BEFORE/AFTER suite baselines: FAILED is the standing red baseline, not a mutant kill",
    7065: "own-test defect narrative: 'caught' = the test swallowing an exception, not a mutant",
    7156: "criteria re-measure table row (THE NINE): FAILED is the fix-absent criterion state, not a mutant kill",
    7340: "criteria-status row in a NOT-MET section ('test_no_new_write_bypasses_the_door T1 FAILED'): fix-absent defect baseline at a named SHA, same class as L7156",
    7373: "commentary restating P5/P4 kept at L7369-7370",
    7619: "restates 0210's planted-brake-path outcome already recorded at L7487's entry",
    7650: "commentary restating M2 kept at L7646",
    7843: "suite-run tally: FAILED (failures=197...) is the standing red baseline, not a mutant kill",
    7866: "instrument-fault prose: 'its own arithmetic caught it'",
    8007: "instrument fault: the FAILED is a quoted test docstring the suite-waiter regex tripped on",
    8295: "commentary restating P2's re-run kept at L8290",
    8368: "harness-defect narrative; the P3 re-run it ends with is the table kept at L8483-8485",
    8502: "commentary on the void-plant branch; 'caught' = the harness branch, not a test kill",
    8890: "NEXT recommendation prose: 'a verdict that survives integration' is about criterion 9, not a mutant",
    8973: "collision re-measure tally: Ran 61 FAILED (errors=5) is the standing red, not a mutant kill",
    9045: "write-bypass standing-red tally (Ran 10 FAILED failures=2), not a mutant kill",
    9149: "requirements table: 'P10 the brake's proof survives integration | NOT MET' -- requirement phrasing, not mutant survival",
    9258: "same NEXT recommendation restated -- 'survives integration' is requirement phrasing",
    9632: "collision re-measure tally: standing red (same class as L8973)",
    9729: "collision re-produce tally: 'the same five names' -- standing red, not a mutant kill",
    10104: "commentary restating M3 kept at L10096",
    10233: "NEXT prose: 'still red' names the write-bypass standing baseline, not a mutant",
    10648: "NEXT prose: same carried-forward 'still red' item, not a mutant",
    10688: "standing five-error tally (Ran 46 FAILED errors=5), not a mutant kill",
    10802: "standing five-error tally ('the same five names'), not a mutant kill",
    10928: "NEXT carried-forward prose naming the still-red write-bypass baseline",
    11005: "'with the repair reverted' Ran 61 FAILED (errors=5): fix-absent defect baseline, 0080's L3103 class",
    11046: "prose: 'every number in my 0232 entry survives re-derivation'",
    11218: "NEXT carried-forward prose ('still red'), not a mutant",
    11545: "NEXT carried-forward prose ('still red' item CLOSED by this entry), not a mutant",
    12086: "revert-cleanliness claim: 'No plant survives anywhere' is about restoration, not a mutant verdict",
    12716: "ratio-derivation prose: 'caught' = the self-check catching a meaningless ratio, not a mutant",
    12919: "denominator-definition line: 'KILLED' is a filename pattern inside the denominator regex, not a verdict",
    13601: "scope prose: 'survives' is a verdict file outliving a redirect, not a mutant",
    14520: "instrument-fault narrative: harness 'caught itself planting nowhere' -- anchor check, not a test kill",
    14929: "control-defect row: 'FAILED AS FIRST WRITTEN' is the control's own defect, not a mutant kill",
    15669: "token-enumeration prose: the FAIL is one of six unittest tokens in a list; the genuine family-1 survivor proof ('every one printed MET -- 6 of 6') is in a verdict word the rule has no vocabulary for (named in report)",
    15773: "method summary: controls 'caught' defects in the method itself, not mutants",
    16369: "0242 claim re-verification: **SURVIVED** rows are verdicts about claims, not mutation plants",
    16370: "0242 claim re-verification: **SURVIVED** rows are verdicts about claims, not mutation plants",
    16371: "0242 claim re-verification: **SURVIVED** rows are verdicts about claims, not mutation plants",
    17368: "premise-verification prose: 'The premise survived' is a claim, not a mutant",
    17607: "BEFORE (unrepaired bytes) baseline: FAILED is the defect's own red before repair (0080's L3103 class)",
    17791: "control-collision correction: the FAILED that fires is the control's own by-design red ('which is the control working'); the re-anchored verdicts ('kill sets then {3}, {1}, {1}') are in a plural form the rule does not read (named in report)",
    18094: "AFTER suite tally: the 12 failing names are the standing red baseline",
    18281: "instrument-gap narrative: the walker's UNKNOWN verdict 'caught' pass-through gaps",
    18369: "BEFORE suite tally (Ran 8, FAILED failures=4): the defect's own red, not a mutant kill",
    18451: "REFERENCE name-set tally: the 14 failures are the standing red baseline",
    18452: "WITH-CHANGE name-set tally: same 14 standing failures, not a mutant kill",
    18488: "born-red artefact row (bare tally), same class as L18369",
    19122: "re-derivation tally: FAILED is the standing twelve-name red baseline",
    19182: "standing-red evolution tally ('2 GONE and ZERO NEW'): baseline accounting, not a mutant verdict",
    19516: "commentary restating the MB3/MB1 pair kept at L19513/L19514",
    19736: "regex-specification row: FAIL is a token in the pattern's alternation, not a verdict",
    19737: "regex-specification row (after-state): same token-enumeration class as L19736",
    19765: "name-set-equality control: the FAILED is the authority file's standing-red trailer, not a mutant kill",
    # ---- instrument narratives inside the load-proof section: the section
    #      fact is real (L16692-16696, readback-verified) but these three
    #      rows are about the harness, not the plants it cleared
    16749: "instrument self-check narrative: both failures 'caught' by the harness, not by tests",
    16763: "harness-defect narrative: the quoted KILL-SET is the misread stdout artifact",
    16771: "leftover-plant incident: 'caught it' = catching the unreverted file by hash (restoration), not a verdict",
}


def load_pilotcaps():
    with open(LANE_PILOTCAPS, "rb") as fh:
        return fh.read().decode("utf-8")


# An independent line-level census: which lines carry a verdict shape at
# all, regardless of any unit grammar.  Recall failures are census lines
# no instrument turned into a record.
CENSUS = re.compile(
    r'\b(?:KILLED|UNKILLED|CAUGHT|SURVIVED|survives|kill-set)\b'
    r'|NOBODY SAW IT|-> [A-Za-z0-9]+ red\b|load-proof')


def census_lines(text):
    out = []
    for n, ln in enumerate(text.split("\n"), 1):
        if CENSUS.search(ln):
            out.append((n, ln.strip()))
    return out


def covered(recs):
    spans = [(r["line"], r["end_line"]) for r in recs]
    def hit(n):
        return any(a <= n <= b for a, b in spans)
    return hit


def stage_reach():
    text = load_pilotcaps()
    lines_all = text.split("\n")
    census = census_lines(text)
    print("VERDICT CENSUS (line-level, no unit grammar): %d verdict-shaped "
          "lines in %d total lines" % (len(census), len(lines_all)))

    theirs, unp_t = extract.parse(text)
    print("\nUNCHANGED INSTRUMENT (0080 extract.py) over pilotcaps: "
          "%d records, %d unparsed" % (len(theirs), len(unp_t)))
    hit_t = covered(theirs)
    miss_t = [(n, s) for n, s in census if not hit_t(n)]
    print("  census lines it covers: %d of %d" % (len(census) - len(miss_t),
                                                  len(census)))

    ours, unp_o = extract_pilotcaps.parse(text)
    print("\nADAPTED INSTRUMENT (extract_pilotcaps.py): %d records, "
          "%d unparsed" % (len(ours), len(unp_o)))
    hit_o = covered(ours)
    miss_o = [(n, s) for n, s in census if not hit_o(n)]
    print("  census lines it covers: %d of %d" % (len(census) - len(miss_o),
                                                  len(census)))
    print("\ncensus lines NEITHER instrument covers (%d):" % len(miss_o))
    for n, s in miss_o:
        print("  L%-6d %s" % (n, s[:78]))
    print("  -> recall boundary named; every line above is read back by "
          "hand before the table is final")


def stage_classify():
    text = load_pilotcaps()
    recs, unp = extract_pilotcaps.parse(text)
    cls = classify_records(recs)
    print("PRE-GATE TABLE -- %d records, %d unparsed" % (len(cls), len(unp)))
    for r in cls:
        mark = "x" if r["line"] in EXCLUSIONS else " "
        print("%s L%-5d %-9s %-9s %s" % (
            mark, r["line"], r["verdict"], r["section"][:9],
            r["reason"][:76]))
    for u in unp:
        print("u L%-5d %s" % (u["line"], u["unparsed"][:76]))
    print("tally (pre-exclusion): %s" % tally(cls))
    for ln in sorted(EXCLUSIONS):
        if not any(r["line"] == ln for r in cls):
            print("  WARNING: exclusion L%d matched 0 records" % ln)


# ------------------------------------------------------------------ controls

C1_AFFECTED_TEXT = """\
## 2026-10-16 — TASK 0090 control C1 positive (synthetic, pilotcaps dialect)

    P8  guard comparison replaced with an equal-length no-op
        the two mutated files had the same size, were written inside one
        mtime tick, and Python reused P7's `__pycache__` for P8, so the
        green verdict answered from the previous mutant's cached bytes
"""

C1_SAFE_TEXT = """\
## 2026-10-16 — TASK 0090 control C1 negative (synthetic, pilotcaps dialect)

**M9 was KILLED by a named test: `test_the_brake_refuses_before_the_join` died with AssertionError: the refusal never came**
"""

C2_TEXT = """\
## 2026-10-16 — TASK 0090 control C2 (synthetic, pilotcaps dialect)

    M5  the digest check moved after the parse      -> C4 red, as predicted
"""


def synth(text, expect, label):
    recs, unp = extract_pilotcaps.parse(text)
    cls = classify_records(recs)
    print("%s -- %d record(s), %d unparsed" % (label, len(cls), len(unp)))
    for r in cls:
        print("  L%-5d %-9s %s" % (r["line"], r["verdict"], r["reason"][:90]))
    ok = bool(cls) and all(r["verdict"] == expect for r in cls)
    print("  -> %s (%s expected)\n" % ("PASS" if ok else "FAIL", expect))
    return ok, cls


def control_c3():
    """Re-run 0080's own instrument over LANE-glm.md and reproduce 0080's
    recorded verdicts.  Drift means the ADAPTER design leaked backwards --
    fix the implementation, not the rule.

    Input is version-BOUNDED at 0080's own entry header.  LANE-glm.md is
    append-only; 0080's entry (header '## ... TASK 0080 ...') restates its
    AFFECTED findings in prose -- the C2 live-replay paragraph parses as one
    extra AFFECTED record (L4257 of the live file) -- and 0080 measured
    BEFORE that entry existed.  First run of this control failed on exactly
    that: 72 records / AFFECTED 7 vs the recorded 71/6.  Bounding the input
    reconstructs 0080's measurement conditions; extract.py and classify.py
    are untouched.  This is a control-construction fix (a version-bound
    reference over an append-only input), not a rule change."""
    with open(LANE_GLM, "rb") as fh:
        text = fh.read().decode("utf-8")
    lines = text.split("\n")
    entry_0080 = next((i for i, ln in enumerate(lines)
                       if ln.startswith("## ") and "TASK 0080" in ln), None)
    if entry_0080 is None:
        print("C3 -- 0080's instrument over LANE-glm.md:")
        print("  DRIFT: cannot find 0080's entry header to bound the input;"
              " the file changed in a way this control does not model")
        return False
    print("C3 -- 0080's instrument over LANE-glm.md, input bounded at L%d "
          "(0080's own entry header; %d tail lines excluded as post-"
          "measurement content)" % (entry_0080 + 1, len(lines) - entry_0080))
    text = "\n".join(lines[:entry_0080])
    recs, unp = extract.parse(text)
    cls = classify_records(recs)
    excl = run_0080.EXCLUSIONS
    kept = [r for r in cls if r["line"] not in excl]
    t = tally(kept)

    print("C3 -- 0080's instrument over LANE-glm.md:")
    print("  records %d (0080 recorded %d), unparsed %d (0080 recorded 0)"
          % (len(cls), REF_0080_TOTAL, len(unp)))
    print("  kept %d (0080: %d), tally %s (0080: %s)"
          % (len(kept), REF_0080_KEPT, t, REF_0080_TALLY))
    drift = []
    if len(cls) != REF_0080_TOTAL or len(unp) != 0:
        drift.append("record/unparsed count drifted")
    if len(kept) != REF_0080_KEPT or t != REF_0080_TALLY:
        drift.append("kept tally drifted")

    from collections import Counter
    per_line = {}
    for r in kept:
        per_line.setdefault(r["line"], Counter())[r["verdict"]] += 1
    ref = {}
    for ln in REF_AFFECTED_LINES:
        ref.setdefault(ln, Counter())["AFFECTED"] += 1
    for ln, n in REF_UNKNOWN_LINES.items():
        ref.setdefault(ln, Counter())["UNKNOWN"] += n
    for ln in sorted(set(ref) | {k for k, v in per_line.items()
                                 if v.get("UNKNOWN") or v.get("AFFECTED")}):
        got = per_line.get(ln, Counter())
        if ref.get(ln, Counter()) != got:
            drift.append("L%d: 0080 recorded %s, re-run produced %s"
                         % (ln, dict(ref.get(ln, Counter())),
                            dict(got)))

    safe_range = [r for r in kept if 3060 <= r["line"] <= 3211
                  and r["verdict"] == "SAFE"]
    if not safe_range:
        drift.append("no SAFE record reproduced in 0074 s3 (L3060-3211)")

    print("\n  five rows of 0080's own output, reproduced:")
    shown = 0
    for want_line in C3_PRINTED:
        rows = [r for r in kept if r["line"] == want_line]
        for r in rows:
            ref_v = ("AFFECTED" if want_line in REF_AFFECTED_LINES
                     else "UNKNOWN")
            print("    L%-5d %-9s (0080 recorded %-9s) %s"
                  % (r["line"], r["verdict"], ref_v,
                     "REPRODUCED" if r["verdict"] == ref_v else "DRIFT"))
            shown += 1
    if safe_range:
        r = safe_range[0]
        print("    L%-5d %-9s (0080 recorded SAFE    -- 0074 s3 plants, "
              "its C1 positive) REPRODUCED" % (r["line"], r["verdict"]))
        shown += 1
    print("  -> %s (%d rows shown, %d drift findings)"
          % ("PASS" if not drift else "FAIL", shown, len(drift)))
    for d in drift:
        print("    DRIFT: %s" % d)
    return not drift


def stage_controls():
    print("C1 -- two synthetic pilotcaps-dialect records through the "
          "adapter:")
    ok_aff, rec_aff = synth(C1_AFFECTED_TEXT, "AFFECTED", "  C1 positive "
                            "(size-identical write, same whole second, pyc "
                            "reused)")
    ok_safe, rec_safe = synth(C1_SAFE_TEXT, "SAFE",
                              "  C1 negative (named kill, stated signature)")
    print("C2 -- synthetic UNKNOWN:")
    ok_unk, rec_unk = synth(C2_TEXT, "UNKNOWN",
                            "  C2 (kill reason described, never named)")
    c1_ok = ok_aff and ok_safe
    c2_ok = ok_unk
    c3_ok = control_c3()

    print("\nC4 GATE")
    print("  C1 both states (AFFECTED on reuse / SAFE on named kill): %s"
          % ("yes" if c1_ok else "NO"))
    print("  C2 UNKNOWN with named missing facts:                    %s"
          % ("yes" if c2_ok else "NO"))
    print("  C3 reproduces 0080's verdicts, no drift:                %s"
          % ("yes" if c3_ok else "NO"))
    if not (c1_ok and c2_ok and c3_ok):
        print("  -> GATE REFUSED.  THE table is not printed.  Task ends "
              "with the control failure above as its result.")
        sys.exit(1)

    text = load_pilotcaps()
    recs, unp = extract_pilotcaps.parse(text)
    cls = classify_records(recs)
    kept = [r for r in cls if r["line"] not in EXCLUSIONS]
    t = tally(kept)
    if t["UNKNOWN"] == 0 or t["AFFECTED"] == 0:
        print("  -> REFUSED: all-clear-shaped table (%s) is the dangerous "
              "wrong answer here." % t)
        sys.exit(1)

    home_rate = REF_0080_TALLY["SAFE"] / REF_0080_KEPT
    away_rate = t["SAFE"] / len(kept)
    print("\nTHE TABLE -- %d kept records (%d excluded, each documented)"
          % (len(kept), len(cls) - len(kept)))
    print("distribution: SAFE %d / UNKNOWN %d / AFFECTED %d"
          % (t["SAFE"], t["UNKNOWN"], t["AFFECTED"]))
    print("SAFE rate: %.1f%% here vs %.1f%% on glm's own corpus "
          "(0080: 30/55)" % (100 * away_rate, 100 * home_rate))
    for verdict in ("AFFECTED", "UNKNOWN", "SAFE"):
        rows = [r for r in kept if r["verdict"] == verdict]
        print("\n%s (%d):" % (verdict, len(rows)))
        for r in rows:
            print("  L%-5d %s" % (r["line"], r["reason"][:84]))
    result = {"total_kept": len(kept), "distribution": t,
              "denominators": {"glm_0080": REF_0080_TALLY,
                               "pilotcaps_0090": t},
              "exclusions": {"%d" % k: v for k, v in EXCLUSIONS.items()},
              "controls": {"c1_both_states": c1_ok, "c2_unknown": c2_ok,
                           "c3_reproduced": c3_ok}}
    with open(os.path.join(HERE, "table_result.json"), "w",
              encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    print("\ntable_result.json written")


if __name__ == "__main__":
    if sys.argv[1:] == ["--stage", "reach"]:
        stage_reach()
    elif sys.argv[1:] == ["--stage", "classify"]:
        stage_classify()
    elif sys.argv[1:] == ["--stage", "controls"]:
        stage_controls()
    else:
        print("usage: run_0090.py --stage reach|classify|controls")
        sys.exit(2)
