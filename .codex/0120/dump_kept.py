# TASK-0120 scratch -- dump the 82 kept rows of 0090's baseline with spans,
# facts and reason heads, so the widening is derived from measured recording
# forms (readback) and not invented.  Read-only over the corpus.
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODEX = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(CODEX, "0090"))
sys.path.insert(0, os.path.join(CODEX, "0080"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import extract_pilotcaps                    # noqa: E402
from classify import classify_records       # noqa: E402
import run_0090                             # noqa: E402  EXCLUSIONS

LANE_PILOTCAPS = r"C:\Users\Zvonimir\Desktop\resonate-ops\LANE-pilotcaps.md"

text = open(LANE_PILOTCAPS, "rb").read().decode("utf-8")
recs, unp = extract_pilotcaps.parse(text)
cls = classify_records(recs)
kept = [r for r in cls if r["line"] not in run_0090.EXCLUSIONS]
print("records %d, unparsed %d, kept %d" % (len(cls), len(unp), len(kept)))
for r in kept:
    print("L%-6d e%-6d %-9s %-8s n=%-26s s=%-18s %s" % (
        r["line"], r["end_line"], r["verdict"], r["outcome"],
        ",".join(r["names"])[:26] or "-", (r["signature"] or "-")[:18],
        r["reason"][:60]))
