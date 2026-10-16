# TASK-0110 -- full facts for the 19 UNKNOWN records of 0080's table.
# Read-only over LANE-glm.md; reuses 0080's extractor+classifier verbatim.
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "0080"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import extract  # noqa: E402
from classify import classify_records  # noqa: E402

LANE = r"C:\Users\Zvonimir\Desktop\resonate-ops\LANE-glm.md"
with open(LANE, "rb") as fh:
    text = fh.read().decode("utf-8")

recs, unp = extract.parse(text)
cls = classify_records(recs)
unknown = [r for r in cls if r["verdict"] == "UNKNOWN"]
print("UNKNOWN records: %d" % len(unknown))
for r in unknown:
    print("=" * 70)
    print("line=%s entry=%s outcome=%s" % (r["line"], r["entry"], r["outcome"]))
    print("names=%r" % (r["names"],))
    print("signature=%r size_change=%r derived_delta=%r stale=%r"
          % (r["signature"], r["size_change"], r.get("derived_delta"),
             r.get("stale_marker")))
    print("reason=%s" % r["reason"])
    print("excerpt:")
    print(r["excerpt"])
print("=" * 70)
print("total records %d, unparsed %d" % (len(recs), len(unp)))
