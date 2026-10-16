# TASK-0120 scratch -- every one of the 67 strict-UNKNOWN rows: strict facts,
# widened disposition, reason, block lines.  Verification readback for the
# re-grade; read-only over the corpus.
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODEX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CODEX, "0090"))
sys.path.insert(0, os.path.join(CODEX, "0080"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import extract_pilotcaps                 # noqa: E402
from classify import classify_records    # noqa: E402
import run_0090                          # noqa: E402
import widen                             # noqa: E402

text = open(run_0090.LANE_PILOTCAPS, "rb").read().decode("utf-8")
recs, unp = extract_pilotcaps.parse(text)
cls = classify_records(recs)
kept = [r for r in cls if r["line"] not in run_0090.EXCLUSIONS]
rows = {w["line"]: w for w in widen.widen_corpus(kept, text)}
n = 0
for r in kept:
    if r["verdict"] != "UNKNOWN":
        continue
    n += 1
    w = rows[r["line"]]
    print("L%-6d %-8s blk=%-30s %s" % (
        r["line"], r["outcome"],
        (",".join(str(x) for x in w["block"]) or "-")[:30],
        w["reason_wide"][:118]))
print("total %d" % n)
