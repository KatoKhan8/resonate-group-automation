# TASK-0140 -- probe the classifier's borderline rows before accepting the
# verdicts: (1) the surprising PROMOTABLEs' capacity numbers, (2) every named
# EXISTS candidate with kill/survive VOCABULARY that failed only the scoping
# rule, (3) the named-ABSENT tokens of the rows currently UNKNOWN-STILL.
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage3_classify as S3                      # noqa: E402  (reuse gates)

rows = json.load(open(os.path.join(HERE, "resolve.json"), encoding="utf-8"))
by_ln = {r["line"]: r for r in rows}
cur = json.load(open(os.path.join(
    r"C:\Users\Zvonimir\Desktop\resonate-ops\glm-0140",
    "promotion-inventory.json"), encoding="utf-8"))
cur_v = {o["line"]: o["verdict"] for o in cur["rows"]}

print("== surprising PROMOTABLEs: chosen carrier capacity ==")
for ln in (5478, 5926, 7469, 9476, 12436, 14932, 15449, 15451, 18057, 19784):
    r = by_ln[ln]
    for c in r["cands"]:
        if c["kind"] == "path" and c["status"] == "EXISTS" \
                and S3.capable(c, r):
            cap = c["capacity"]
            print("L%-6d %-28s %-34s n=%-6d sigs=%s clr=%s link=%s "
                  "origin=%s" % (
                      ln, r["need"][:28],
                      os.path.basename(c["path"])[:34], cap["names"],
                      ",".join(cap["sigs"])[:40] or "-",
                      ",".join(cap["clearing"])[:30] or "-",
                      ",".join(cap["link"])[:20] or "-", c["origin"]))
            break

print("\n== named EXISTS with vocabulary that FAILED ONLY scoping ==")
for r in rows:
    if cur_v[r["line"]] == "PROMOTABLE-IF-READ":
        continue
    vocab_hits = []
    for c in r["cands"]:
        if (c.get("origin") == "named" and c["kind"] == "path"
                and c["status"] == "EXISTS" and c.get("capacity")):
            cap = c["capacity"]
            if r["need"].startswith("kill:") and cap["sigs"]:
                vocab_hits.append((c, "sigs"))
            if (r["need"] == "survive:needs-clearing-fact"
                    and cap["clearing"]):
                vocab_hits.append((c, "clearing"))
    if vocab_hits:
        c, kind = vocab_hits[0]
        cap = c["capacity"]
        print("L%-6d t=%-5s %-24s %-22s %s: %s n=%d %s=%s link=%s" % (
            r["line"], r["entry"]["task"], r["need"], cur_v[r["line"]],
            os.path.basename(c["path"])[:40], kind, cap["names"], kind,
            ",".join(cap[kind])[:40], ",".join(cap["link"])[:24] or "-"))

print("\n== named-ABSENT tokens per current UNKNOWN-STILL row ==")
for o in cur["rows"]:
    if o["verdict"] != "UNKNOWN-STILL":
        continue
    r = by_ln[o["line"]]
    toks = [c["token"] for c in r["cands"]
            if c.get("origin") == "named" and c["status"] == "ABSENT"]
    print("L%-6d t=%-5s %s" % (o["line"], r["entry"]["task"],
                               " | ".join(t[:52] for t in toks[:5])
                               or "(none)"))
