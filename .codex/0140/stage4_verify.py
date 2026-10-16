# TASK-0140 -- stage 4: readback verification.  Parse the WRITTEN deliverables
# (not in-memory state) and re-verify every count with its denominator:
#   - 64 rows; verdict counts sum to 64; every verdict in the enum
#   - controls: 3 planted PASS lines + 3 known-answer REPRODUCED lines present
#   - per-verdict invariants: PROMOTABLE => carrier EXISTS; EVIDENCE-CANNOT-
#     EXIST => carrier None + recording text; UNKNOWN-STILL => carrier with
#     status + why
#   - recordings: union of row lists == all 64 rows, no row in two entries
#   - md agrees with json: table has 64 data rows, verdict bullets match
#   - need taxonomy: kill rows and survive rows sum to 64
#   - sha256 of both files recomputed from disk
import hashlib
import json
import os
import re
import sys

OUT_DIR = r"C:\Users\Zvonimir\Desktop\resonate-ops\glm-0140"
J = os.path.join(OUT_DIR, "promotion-inventory.json")
M = os.path.join(OUT_DIR, "promotion-inventory.md")

payload = json.load(open(J, encoding="utf-8"))
md = open(M, encoding="utf-8").read()
fails = []


def check(name, ok, detail=""):
    print("%-58s %s %s" % (name, "PASS" if ok else "FAIL", detail))
    if not ok:
        fails.append(name)


rows = payload["rows"]
ENUM = {"PROMOTABLE-IF-READ", "UNKNOWN-STILL", "EVIDENCE-CANNOT-EXIST"}
check("denominator field == 64", payload["denominator"] == 64,
      payload["denominator"])
check("rows length == 64", len(rows) == 64, len(rows))
check("verdict counts sum to 64",
      sum(payload["verdicts"].values()) == 64, payload["verdicts"])
check("all verdicts in enum", all(r["verdict"] in ENUM for r in rows))
tally = {k: sum(1 for r in rows if r["verdict"] == k) for k in ENUM}
check("verdicts block matches row tally", tally == payload["verdicts"],
      tally)
check("distinct row lines == 64",
      len({r["line"] for r in rows}) == 64)

ctrl = payload["controls"]
check("3 planted control lines",
      len(ctrl["planted"]) == 3
      and all("PASS" in ln for ln in ctrl["planted"]))
check("planted both answers present",
      any("PROMOTABLE-IF-READ" in ln for ln in ctrl["planted"])
      and any("EVIDENCE-CANNOT-EXIST" in ln for ln in ctrl["planted"]))
check("3 known-answer REPRODUCED lines",
      len(ctrl["known_answer"]) == 3
      and all("REPRODUCED" in ln for ln in ctrl["known_answer"]))
check("md quotes controls before the table",
      md.find("[CONTROL-A]") < md.find("## Per-row table"))

ok_inv = True
for r in rows:
    v, c = r["verdict"], r["carrier"]
    if v == "PROMOTABLE-IF-READ":
        ok_inv &= bool(c is not None and c["status"] == "EXISTS"
                       and c["path"])
    elif v == "EVIDENCE-CANNOT-EXIST":
        ok_inv &= c is None and "recording" in r and "maker" in r["recording"]
    else:
        ok_inv &= bool(c is not None and c["status"] in ("EXISTS", "ABSENT",
                                                         "OFF-LIMITS")
                       and r["why"])
check("per-verdict carrier invariants (all 64)", ok_inv)

recs = payload["recordings"]
seen = []
for e in recs:
    seen += e["rows"]
check("recordings row union == 64 rows, no overlap",
      sorted(seen) == sorted(r["line"] for r in rows)
      and len(seen) == len(set(seen)), "%d rows over %d entries"
      % (len(seen), len(recs)))
check("every recording entry has maker + action",
      all(e["action"] and ("maker" in e["action"] or e["id"].startswith(
          ("read-", "pointer-"))) for e in recs))

md_table = re.findall(r'^\| L(\d+) \|', md, re.M)
check("md table has 64 data rows", len(md_table) == 64, len(md_table))
md_verdicts = dict(re.findall(r'^- ([A-Z-]+): (\d+)/64$', md, re.M))
check("md verdict bullets match json",
      {k: int(v) for k, v in md_verdicts.items()} == payload["verdicts"],
      md_verdicts)

needs = {}
for r in rows:
    needs[r["need"]] = needs.get(r["need"], 0) + 1
kill = sum(v for k, v in needs.items() if k.startswith("kill:"))
surv = sum(v for k, v in needs.items() if k.startswith("survive:"))
check("need taxonomy kill+survive == 64", kill + surv == 64,
      "kill=%d survive=%d %s" % (kill, surv, needs))

for p in (J, M):
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    check("sha256 %s" % os.path.basename(p), bool(re.fullmatch(
        r'[0-9a-f]{64}', h)), h)
    print("       %s" % h)

print("\n%s (%d failures)" % ("VERIFIED" if not fails else "FAILED",
                              len(fails)))
sys.exit(1 if fails else 0)
