# TASK-0080 -- stage runner.
#
#   --stage classify   extract + classify EVERY mutation-proof record in
#                      LANE-glm.md, print the pre-gate table, then
#                      cross-check recall against 0078's independent
#                      census instrument over the pre-0079 slice.
#   --stage controls   C4 gate: refuse to print THE table unless C1
#                      printed both its states (SAFE on plants, UNKNOWN
#                      when reasons are redacted), C2 printed both its
#                      states (AFFECTED on the P3 replay, SAFE on the
#                      revert), and C3 states both error directions with
#                      at least 12 kept rows.  An all-SAFE table is
#                      refused outright.  Then, and only then, print the
#                      post-exclusion table and its distribution.
#
# Exclusions are DOCUMENTED per line, each because the record is not a
# mutation-proof claim at all (baseline run, proposals, design prose,
# restatements) or is commentary about other records (census-about-
# census -- qwen/0176 counted that class and died at 14 records).
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "0078"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import extract                # noqa: E402
from classify import classify_records, tally  # noqa: E402
import parse_lane             # noqa: E402  (0078's census instrument)

LANE = r"C:\Users\Zvonimir\Desktop\resonate-ops\LANE-glm.md"

# 0079's entry header (L4041): the census ran over the file as of 0078.
PRE_0079_LINES = 4040

EXCLUSIONS = {
    51: "B4 standing-guard description: the self-destruct is the guard's "
        "designed behavior, not a planted mutation result",
    108: "B7 proposed-test shapes: proposals in the queue doc, no run "
         "happened, no verdict exists to clear",
    3103: "0074 s3 defect-state baseline: the FAILED is the DEFECT's own "
          "red before repair, not a mutant's kill",
    3871: "0078 s1 design prose: describes the instrument's intended "
          "demonstration, records no result",
    3908: "0078 s2 header-state fact: a pyc-header observation line, "
          "verdict-free context for the demonstration kept at L3911/L3915",
    3958: "0078 s3 census table row: commentary about other records",
    3960: "0078 s3 census table row: commentary about other records",
    3961: "0078 s3 census table row: commentary about other records",
    3962: "0078 s3 census table row: commentary about other records",
    3967: "0078 s3 census table row: commentary about other records",
    3969: "0078 s3 census table row: commentary about other records",
    3970: "0078 s3 census table row: commentary about other records",
    3971: "0078 s3 census table row: commentary about other records",
    4006: "0078 s3 C2 recap: restates the demonstration kept at "
          "L3911/L3915",
    4009: "CONTROL-B census listing: same census-about-census class",
    4154: "0079 C4 gate recap: restates R1's +10 B control already "
          "recorded at L4143",
}


def load():
    with open(LANE, "rb") as fh:
        text = fh.read().decode("utf-8")
    return text


def classified(text):
    recs, unp = extract.parse(text)
    return classify_records(recs), unp


def stage_classify():
    text = load()
    cls, unp = classified(text)
    print("PRE-GATE TABLE -- %d records, %d unparsed" % (len(cls), len(unp)))
    for r in cls:
        mark = "x" if r["line"] in EXCLUSIONS else " "
        print("%s L%-5d %-9s %s" % (mark, r["line"], r["verdict"],
                                    r["reason"][:88]))
    print("tally (pre-exclusion): %s" % tally(cls))

    # Recall cross-check: 0078's census instrument, independent parser,
    # over the pre-0079 slice.  Its findings must be a SUBSET of ours --
    # anything it found and we did not is a recall failure.
    slice_text = "\n".join(text.split("\n")[:PRE_0079_LINES])
    theirs, _ = parse_lane.parse(slice_text)
    ours, _ = extract.parse(slice_text)
    their_lines = {r["line"] for r in theirs}
    our_lines = {r["line"] for r in ours}
    missing = sorted(their_lines - our_lines)
    print("\nCENSUS CROSS-CHECK (pre-0079 slice): theirs %d lines, ours %d"
          % (len(their_lines), len(our_lines)))
    for ln in missing:
        row = next(r for r in theirs if r["line"] == ln)
        print("  RECALL MISS L%d: %s" % (ln, row["excerpt"][:70]))
    extra = sorted(our_lines - their_lines)
    print("  ours-only lines (%d): %s"
          % (len(extra), ", ".join(str(l) for l in extra)))
    print("  -> %s" % ("RECALL OK (census subset)"
                       if not missing else "RECALL FAILURE"))

    # every documented exclusion must match exactly the records it claims
    for ln, why in sorted(EXCLUSIONS.items()):
        hit = [r for r in cls if r["line"] == ln]
        if not hit:
            print("  WARNING: exclusion L%d matched 0 records" % ln)
    return cls, unp


def stage_controls():
    cls, unp = classified(load())

    with open(os.path.join(HERE, "c1_result.json"), encoding="utf-8") as fh:
        c1 = json.load(fh)
    c1_ok = (c1.get("positive_pass") and c1.get("negative_pass"))

    with open(os.path.join(HERE, "c2_result.json"), encoding="utf-8") as fh:
        c2 = json.load(fh)
    c2_states = (c2.get("legs", {}).get("stale", {}).get("verdict"),
                 c2.get("legs", {}).get("revert", {}).get("verdict"))
    c2_ok = (c2.get("pass") and c2_states == ("AFFECTED", "SAFE"))

    with open(os.path.join(HERE, "c3_hand_validation.txt"),
              encoding="utf-8") as fh:
        c3 = fh.read()
    kept = len([ln for ln in c3.split("\n")
                if ln.startswith("  UNK") or ln.startswith("  SAFE")
                or ln.startswith("  AFF")])
    c3_ok = (kept >= 12
             and "false SAFE" in c3 and "false UNKNOWN" in c3)

    print("C4 GATE")
    print("  C1 both states (plants SAFE / redacted UNKNOWN): %s"
          % ("yes" if c1_ok else "NO"))
    print("  C2 both states (replay AFFECTED / revert SAFE): %s  %s"
          % ("yes" if c2_ok else "NO", c2_states))
    print("  C3 both error directions, %d kept rows (floor 12): %s"
          % (kept, "yes" if c3_ok else "NO"))
    if not (c1_ok and c2_ok and c3_ok):
        print("  -> GATE REFUSED.  THE table is not printed.")
        sys.exit(1)

    kept_recs = [r for r in cls if r["line"] not in EXCLUSIONS]
    t = tally(kept_recs)
    if t["UNKNOWN"] == 0 or t["AFFECTED"] == 0:
        print("  -> REFUSED: all-clear-shaped table (%s) is the dangerous "
              "wrong answer here." % t)
        sys.exit(1)

    print("\nTHE TABLE -- %d kept records (%d excluded, each documented "
          "above)" % (len(kept_recs), len(cls) - len(kept_recs)))
    print("distribution: SAFE %d / UNKNOWN %d / AFFECTED %d"
          % (t["SAFE"], t["UNKNOWN"], t["AFFECTED"]))
    for verdict in ("AFFECTED", "UNKNOWN", "SAFE"):
        rows = [r for r in kept_recs if r["verdict"] == verdict]
        print("\n%s (%d):" % (verdict, len(rows)))
        for r in rows:
            print("  L%-5d %s" % (r["line"], r["reason"][:86]))
    result = {"total_kept": len(kept_recs), "distribution": t,
              "exclusions": {"%d" % k: v for k, v in EXCLUSIONS.items()},
              "controls": {"c1_both_states": c1_ok,
                           "c2_states": list(c2_states),
                           "c3_kept_rows": kept}}
    with open(os.path.join(HERE, "table_result.json"), "w",
              encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    print("\ntable_result.json written")


if __name__ == "__main__":
    if sys.argv[1:] == ["--stage", "classify"]:
        stage_classify()
    elif sys.argv[1:] == ["--stage", "controls"]:
        stage_controls()
    else:
        print("usage: run_0080.py --stage classify|controls")
        sys.exit(2)
