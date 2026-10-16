# TASK-0080 -- CONTROL C1, both legs.
#
# POSITIVE: TASK-0074's section-3 entry verbatim (LANE-glm.md L3060..L3211,
# the entry between '## 2026-10-16 10:26 — TASK 0074 — section 3' and
# TASK-0075's header).  Six plants A-F, each a recorded kill with every
# clearing fact present: named kill-sets, stated signatures, a verbatim
# mutation pair (Plant B), and the entry's `__pycache__`-deleted-between-
# plant-and-run protocol sentence.  PASS = the six plant records
# (file lines 3144..3172) each print SAFE.
#
# NEGATIVE: the same slice with every RECORDED REASON redacted -- each
# redaction names the disjunct whose absence it models:
#   test_ tokens                     -> 'a-test'      (a: named kill-set)
#   `if unpriced:` / `if False and
#     unpriced:` (Plant B's pair)    -> '(a mutation)' (b: verbatim pair;
#                                                       a: its signature)
#   (got "...") receipts             -> '(a wrong label)' (a: Plant E)
#   KeyError / AssertionError        -> 'Error'       (a: bare error class)
#   the pyc protocol phrase          -> neutral prose (d: entry pycache)
# Outcome vocabulary is untouched: every plant's 'Killed N' sits OUTSIDE
# backticks in this entry, and no redaction touches backtick structure at
# all (a first cut also rewrote backtick spans and, because spans wrap at
# the ~95-col break, mispaired across the gap and ate the kill vocabulary
# -- that cut is recorded here so the simplification is not mysterious).
# The fixture models the pre-0072 recording style: outcomes written down,
# reasons not.  PASS = zero records print SAFE; the six plant records and
# the baseline-run bullet all print UNKNOWN (fail closed).
#
# A glance at qwen/0176's failure: it hand-counted a 14-record sample that
# mixed VERIFICATION commentary into the denominator.  This control counts
# only records the extractor itself produced, and asserts the plant range
# holds exactly six.
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import extract            # noqa: E402
from classify import classify_records  # noqa: E402

LANE = r"C:\Users\Zvonimir\Desktop\resonate-ops\LANE-glm.md"
OFFSET = 3059             # fixture line k  <->  file line OFFSET + k
PLANT_LO, PLANT_HI = 3144, 3172

with open(LANE, "rb") as fh:
    lines = fh.read().decode("utf-8").split("\n")
positive = "\n".join(lines[OFFSET:3211])

REDATIONS = [
    (re.compile(r'test_[a-z0-9_]+'), 'a-test',
     'a: named kill-set'),
    # Plant B's pair only derives a size when BOTH tokens sit around the
    # transform marker; redacting the left token alone leaves the wrapped
    # right token unpaired, and keeps the fixture's line count 1:1 with the
    # positive slice so record lines map identically in both legs.
    (re.compile(r'`if unpriced:`\s*->'), '(a mutation) ->',
     'b: verbatim pair, left token (unpairs the derivation)'),
    (re.compile(r'\(got "[^"]*"\)'), '(a wrong label)',
     'a: wrong-label receipt'),
    (re.compile(r'\bKeyError\b|\bAssertionError\b'), 'Error',
     'a: error class'),
    (re.compile(r'were deleted between plant and run'),
     "were handled per the era's custom",
     'd: entry __pycache__ protocol'),
]
negative = positive
for pat, repl, why in REDATIONS:
    negative = pat.sub(repl, negative)


def run(name, text):
    with open(os.path.join(HERE, "c1_%s.md" % name), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    recs, unp = extract.parse(text)
    cls = classify_records(recs)
    for r in cls:
        r["file_line"] = r["line"] + OFFSET
    plants = [r for r in cls if PLANT_LO <= r["file_line"] <= PLANT_HI]
    return cls, plants, unp


full, plants, unp = run("positive", positive)
pos_ok = (len(plants) == 6 and all(r["verdict"] == "SAFE" for r in plants)
          and unp == [])
print("C1 POSITIVE (%d records, %d unparsed, %d in plant range):"
      % (len(full), len(unp), len(plants)))
for r in full:
    print("  L%-4d %-9s %s" % (r["file_line"], r["verdict"], r["reason"][:74]))
print("  -> %s" % ("PASS (six plants, all SAFE)" if pos_ok else "FAIL"))

red, rplants, runp = run("negative", negative)
neg_ok = (len(rplants) == 6
          and all(r["verdict"] == "UNKNOWN" for r in rplants)
          and all(r["verdict"] != "SAFE" for r in red)
          and runp == [])
print("C1 NEGATIVE (%d records, %d unparsed, %d in plant range):"
      % (len(red), len(runp), len(rplants)))
for r in red:
    print("  L%-4d %-9s missing: %s" % (r["file_line"], r["verdict"],
                                        r["reason"][:70]))
print("  -> %s" % ("PASS (no SAFE anywhere; six plants UNKNOWN)"
                   if neg_ok else "FAIL"))

result = {
    "positive_pass": pos_ok, "negative_pass": neg_ok,
    "positive": {"records": len(full), "plants": len(plants),
                 "verdicts": {r["file_line"]: r["verdict"] for r in plants}},
    "negative": {"records": len(red), "plants": len(rplants),
                 "verdicts": {r["file_line"]: r["verdict"] for r in red}},
    "redactions": ["%s -> %s  (%s)" % (p.pattern, repl, why)
                   for p, repl, why in REDATIONS],
}
with open(os.path.join(HERE, "c1_result.json"), "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=1)
print("c1_result.json written; C1 %s" %
      ("PASS" if (pos_ok and neg_ok) else "FAIL"))
sys.exit(0 if (pos_ok and neg_ok) else 1)
