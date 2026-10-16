# Quick audit view: Layer 1 records -> Layer 2 verdicts, one line each.
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import extract          # noqa: E402
from classify import classify_records, tally  # noqa: E402

recs, unp = extract.extract(sys.argv[1])
cls = classify_records(recs)
for r in cls:
    print("L%-5d %-10s %-8s %-14s %-13s %-13s %-8s %s" % (
        r["line"], r["entry"][:10], r["outcome"],
        (",".join(r["names"])[:14] or "-"),
        (r["signature"] or "-"),
        (r["size_change"] or "-") +
        ("(%+d)" % r["derived_delta"] if r.get("derived_delta") is not None
         else ""),
        r["verdict"], r["excerpt"][:46]))
print("-- %d records, %d unparsed, tally %s"
      % (len(recs), len(unp), tally(cls)))
