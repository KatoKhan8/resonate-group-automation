"""Does the raw queue file know any of the 128, in any state including dropped?

`store.load()` replays deltas and could in principle hide a row. The raw file
cannot. Both are asked, plus every stage artefact that names an address, so
"never contacted" rests on a positive reading of the estate rather than on one
lookup that happened to return nothing.
"""
import sys, os, json, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = r'C:/Users/Zvonimir/Desktop/resonate-group-automation/work'

detail = json.load(open(os.path.join(W, "lane-h-render-2026-09-25.json"),
                        encoding="utf-8"))
the128 = {r["email"].lower() for r in detail if r["in_128"]}
dom128 = {r["domain"].lower() for r in detail if r["in_128"]}
ren = {r["email"].lower() for r in detail
       if r["in_128"] and r["state"] == "rendered"}
dom_ren = {r["domain"].lower() for r in detail
           if r["in_128"] and r["state"] == "rendered"}
print("the 128: %d addresses over %d domains; re-rendered %d over %d domains"
      % (len(the128), len(dom128), len(ren), len(dom_ren)))

# THE CONTROL: a set that MUST be found, so a zero below is evidence rather
# than a broken lookup. The 51 UK/EU leads that DO have a queue record.
control = {r["email"].lower() for r in detail if not r["in_128"]}
control_dom = {r["domain"].lower() for r in detail if not r["in_128"]}
print("control (UK/EU leads that DO have a record): %d over %d domains"
      % (len(control), len(control_dom)))

hits_dom, hits_mail, rows, staged = set(), set(), 0, collections.Counter()
c_dom, c_mail = set(), set()
with open(os.path.join(W, "queue.jsonl"), encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if not line:
            continue
        rows += 1
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        dom = str(rec.get("domain") or "").lower()
        if dom in dom128:
            hits_dom.add(dom)
            staged[str(rec.get("stage") or rec.get("status") or "?")] += 1
        if dom in control_dom:
            c_dom.add(dom)
        for contact in (rec.get("contacts") or []):
            mail = str(contact.get("email") or "").lower()
            if mail in the128:
                hits_mail.add(mail)
            if mail in control:
                c_mail.add(mail)

print("\nraw work/queue.jsonl: %d rows" % rows)
print("  CONTROL found: %d of %d domains, %d of %d addresses"
      % (len(c_dom), len(control_dom), len(c_mail), len(control)))
print("  the 128 found: %d of %d domains, %d of %d addresses"
      % (len(hits_dom), len(dom128), len(hits_mail), len(the128)))
if staged:
    print("  their stages:", dict(staged))
