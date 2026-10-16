# TASK-0120 -- stage runner.
#
#   --stage baseline   reproduce 0090's baseline over the same corpus bytes:
#                      158 records / 2 refused / 82 kept / SAFE 14 /
#                      UNKNOWN 67 / AFFECTED 1.  The re-grade's denominators
#                      stand on this reproduction.
#   --stage controls   C1: the three rows 0090 predicted would flip
#                      (L16148, L10480, L15382) must go UNKNOWN -> SAFE under
#                      the widening, each printed with its evidence lines.
#                      If any does not, the widened rule is wrong and that is
#                      the finding.  C2: rows with no evidence in any form
#                      (L7645, L5926) must stay UNKNOWN, shown unmoved.
#                      C3: the home corpus (LANE-glm.md, input bounded at
#                      0080's own entry header, the 0090 C3 discipline) first
#                      reproduces 0080's strict 71/55/{30,19,6}, then is
#                      re-graded under the widened reader: all 30 SAFE rows
#                      must stay SAFE (a demotion is a finding against the
#                      widening), the 6 AFFECTED unchanged, home
#                      UNKNOWN->SAFE flips printed informationally.
#   --stage table      THE re-grade, printed only after the controls pass and
#                      refused if all-clear-shaped (UNKNOWN 0 or AFFECTED 0):
#                      every kept row strict -> widened; the 67 old-UNKNOWN
#                      subset tallied with denominator 67 and the kept-set
#                      denominator 82 beside it; every flip printed as
#                      line -> old grade -> new grade -> firing clause; W2a/
#                      W2b refusals printed; results mirrored to
#                      table_result.json.
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODEX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CODEX, "0090"))
sys.path.insert(0, os.path.join(CODEX, "0080"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import extract                       # noqa: E402  0080's home extractor, UNCHANGED
import extract_pilotcaps             # noqa: E402  0090's adapter, UNCHANGED
from classify import classify_records, tally   # noqa: E402  UNCHANGED
import run_0080                      # noqa: E402  home EXCLUSIONS
import run_0090                      # noqa: E402  foreign EXCLUSIONS + refs
import widen                         # noqa: E402  the widened reader

LANE_PILOTCAPS = run_0090.LANE_PILOTCAPS
LANE_GLM = run_0090.LANE_GLM
REF_0090_TALLY = {"SAFE": 14, "UNKNOWN": 67, "AFFECTED": 1}


def foreign_kept():
    text = open(LANE_PILOTCAPS, "rb").read().decode("utf-8")
    recs, unp = extract_pilotcaps.parse(text)
    cls = classify_records(recs)
    kept = [r for r in cls if r["line"] not in run_0090.EXCLUSIONS]
    return text, recs, unp, cls, kept


def home_bounded():
    """LANE-glm.md bounded at 0080's entry header (0090's C3 discipline --
    the file is append-only and 0080's own prose would otherwise parse as
    records).  Returns (bounded_text, records, unparsed, classified, kept)."""
    text = open(LANE_GLM, "rb").read().decode("utf-8")
    lines = text.split("\n")
    entry = next((i for i, ln in enumerate(lines)
                  if ln.startswith("## ") and "TASK 0080" in ln), None)
    if entry is None:
        raise SystemExit("C3 bound lost: 0080's entry header not found")
    bounded = "\n".join(lines[:entry])
    recs, unp = extract.parse(bounded)
    cls = classify_records(recs)
    kept = [r for r in cls if r["line"] not in run_0080.EXCLUSIONS]
    return entry, bounded, recs, unp, cls, kept


def stage_baseline():
    text, recs, unp, cls, kept = foreign_kept()
    t = tally(kept)
    print("corpus sha256 %s  (%d B, %d lines)"
          % (hashlib.sha256(text.encode("utf-8")).hexdigest(), len(text.encode("utf-8")),
             text.count("\n") + 1))
    print("records %d, refused/unparsed %d, kept %d"
          % (len(cls), len(unp), len(kept)))
    print("strict tally %s   0090 recorded %s  ->  %s"
          % (t, REF_0090_TALLY,
             "REPRODUCED" if t == REF_0090_TALLY else "DRIFT"))
    return t == REF_0090_TALLY


def stage_controls():
    ok = {}
    text, recs, unp, cls, kept = foreign_kept()
    wide = {w["line"]: w for w in widen.widen_corpus(kept, text)}

    print("C1 -- 0090's three predicted flips, under the widening:")
    c1 = True
    for ln in (16148, 10480, 15382):
        w = wide[ln]
        flipped = w["strict"] == "UNKNOWN" and w["wide"] == "SAFE"
        c1 = c1 and flipped
        print("  L%-6d %s -> %-7s %s" % (ln, w["strict"], w["wide"],
                                         "FLIPPED" if flipped else "DID NOT FLIP"))
        print("         clause: %s" % (w["clause"] or "-"))
        print("         reason: %s" % w["reason_wide"][:100])
        print("         evidence block lines: %s"
              % (w["block"] if w["block"] else "(row only)"))
    print("  C1 %s" % ("PASS" if c1 else
                       "FAIL -- the widened rule is wrong; that is the finding"))
    ok["C1"] = c1

    print("\nC2 -- no evidence in any form, must stay UNKNOWN:")
    c2 = True
    for ln in (7645, 5926):
        w = wide[ln]
        unmoved = w["strict"] == "UNKNOWN" and w["wide"] == "UNKNOWN"
        c2 = c2 and unmoved
        print("  L%-6d %s -> %-7s %s" % (ln, w["strict"], w["wide"],
                                         "UNMOVED" if unmoved else "MOVED"))
        print("         why: %s" % w["reason_wide"][:100])
    print("  C2 %s" % ("PASS" if c2 else "FAIL"))
    ok["C2"] = c2

    print("\nC3 -- home corpus (LANE-glm.md) under the widened reader:")
    entry, bounded, grecs, gunp, gcls, gkept = home_bounded()
    print("  input bounded at L%d (0080's entry header)" % (entry + 1))
    t = tally(gkept)
    strict_ok = (len(gcls) == run_0090.REF_0080_TOTAL and len(gunp) == 0
                 and len(gkept) == run_0090.REF_0080_KEPT
                 and t == run_0090.REF_0080_TALLY)
    print("  strict reproduction: records %d (71), unparsed %d (0), kept %d "
          "(55), tally %s ({'SAFE': 30, 'UNKNOWN': 19, 'AFFECTED': 6}) -> %s"
          % (len(gcls), len(gunp), len(gkept), t,
             "REPRODUCED" if strict_ok else "DRIFT"))
    gwide = widen.widen_corpus(gkept, bounded)
    demoted = [w for w in gwide if w["strict"] == "SAFE"
               and w["wide"] != "SAFE"]
    aff = [w for w in gwide if w["strict"] == "AFFECTED"]
    aff_changed = [w for w in aff if w["wide"] != "AFFECTED"]
    flips = [w for w in gwide if w["strict"] == "UNKNOWN"
             and w["wide"] == "SAFE"]
    print("  30 SAFE rows re-graded: %d stayed SAFE, %d DEMOTED"
          % (sum(1 for w in gwide if w["strict"] == "SAFE"
                 and w["wide"] == "SAFE"), len(demoted)))
    for w in demoted:
        print("    DEMOTED L%d -> %s (%s)" % (w["line"], w["wide"],
                                              w["reason_wide"][:80]))
    print("  AFFECTED rows: %d, all unchanged: %s"
          % (len(aff), not aff_changed))
    print("  home UNKNOWN->SAFE under the widening: %d (informational)"
          % len(flips))
    for w in flips:
        print("    L%d %s" % (w["line"], w["reason_wide"][:90]))
    c3 = strict_ok and not demoted and not aff_changed
    print("  C3 %s" % ("PASS" if c3 else "FAIL -- a demotion is a finding "
                       "against the widening"))
    ok["C3"] = c3
    ok["_gwide"] = gwide
    ok["_wide"] = wide
    return ok


def stage_table(controls):
    wide = controls["_wide"]
    text, recs, unp, cls, kept = foreign_kept()
    assert len(wide) == len(kept) == 82, (len(wide), len(kept))

    new_t = {"SAFE": 0, "UNKNOWN": 0, "AFFECTED": 0}
    for w in wide.values():
        new_t[w["wide"]] += 1

    # gate: all-clear-shaped tables are refused outright
    if new_t["UNKNOWN"] == 0 or new_t["AFFECTED"] == 0:
        print("TABLE REFUSED: all-clear shape %s -- fail-closed" % new_t)
        return

    print("THE RE-GRADE -- 82 kept rows, strict -> widened:")
    print("  strict:  SAFE 14 / UNKNOWN 67 / AFFECTED 1")
    print("  widened: SAFE %d / UNKNOWN %d / AFFECTED %d   (denominator 82)"
          % (new_t["SAFE"], new_t["UNKNOWN"], new_t["AFFECTED"]))

    old_unknown = sorted(w["line"] for w in wide.values()
                         if w["strict"] == "UNKNOWN")
    ou_new = {"SAFE": 0, "UNKNOWN": 0, "AFFECTED": 0}
    for w in wide.values():
        if w["strict"] == "UNKNOWN":
            ou_new[w["wide"]] += 1
    print("\nTHE ONE QUESTION -- the 67 strict-UNKNOWN rows under the widened "
          "rule (denominator 67; kept-set denominator 82 beside):")
    print("  SAFE    %2d/67   (%d/82 kept)" % (ou_new["SAFE"], new_t["SAFE"]))
    print("  UNKNOWN %2d/67" % ou_new["UNKNOWN"])
    print("  AFFECTED %d/67   (0 -- the stale path is not widened, by spec)"
          % ou_new["AFFECTED"])

    flips = sorted((w for w in wide.values() if w["wide"] != w["strict"]),
                   key=lambda w: w["line"])
    print("\nEVERY FLIP (%d):" % len(flips))
    for w in flips:
        print("  L%-6d -> %-7s -> %-7s -> %s"
              % (w["line"], w["strict"], w["wide"], w["clause"]))
        print("         %s" % w["reason_wide"][:110])
        if w["block"]:
            print("         evidence block: L%d-L%d"
                  % (w["block"][0], w["block"][-1]))

    unchanged_safe = [w for w in wide.values() if w["strict"] == "SAFE"]
    unchanged_aff = [w for w in wide.values() if w["strict"] == "AFFECTED"]
    print("\nRows the strict rule graded correctly, re-graded:")
    print("  14 SAFE rows: all still SAFE: %s"
          % all(w["wide"] == "SAFE" for w in unchanged_safe))
    print("  1 AFFECTED row (L6827): still AFFECTED: %s"
          % all(w["wide"] == "AFFECTED" for w in unchanged_aff))
    print("  -> the widened rule flips %s row(s) the strict rule graded "
          "correctly" % (len(flips) - sum(1 for w in flips
                                          if w["strict"] == "UNKNOWN")))

    refusals = sorted((w for w in wide.values()
                       if w["strict"] == "UNKNOWN" and w["wide"] == "UNKNOWN"
                       and "REFUSED" in w["reason_wide"]),
                      key=lambda w: w["line"])
    print("\nW2a/W2b refusals (count stated, list did not certify -- the "
          "widening refusing, not failing) (%d):" % len(refusals))
    for w in refusals:
        print("  L%-6d %s" % (w["line"], w["reason_wide"][:100]))

    out = {"denominator_kept": 82, "strict": REF_0090_TALLY,
           "widened": new_t, "unknown67": ou_new,
           "flips": [{"line": w["line"], "old": w["strict"],
                      "new": w["wide"], "clause": w["clause"],
                      "reason": w["reason_wide"], "block": w["block"]}
                     for w in flips],
           "refusals": [{"line": w["line"], "reason": w["reason_wide"]}
                        for w in refusals]}
    with open(os.path.join(HERE, "table_result.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("\nmirrored to .codex/0120/table_result.json")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--stage":
        stage = sys.argv[2]
    elif len(sys.argv) >= 2:
        stage = sys.argv[1].replace("--stage-", "")
    else:
        stage = ""
    if stage == "baseline":
        sys.exit(0 if stage_baseline() else 1)
    elif stage == "controls":
        c = stage_controls()
        sys.exit(0 if (c["C1"] and c["C2"] and c["C3"]) else 1)
    elif stage == "table":
        c = stage_controls()
        if not (c["C1"] and c["C2"] and c["C3"]):
            print("TABLE REFUSED: controls did not all pass")
            sys.exit(1)
        print()
        stage_table(c)
        sys.exit(0)
    else:
        raise SystemExit("usage: run_0120.py --stage baseline|controls|table")
