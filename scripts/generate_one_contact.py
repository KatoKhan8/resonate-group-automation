"""Generate ONE contact's five emails. Nobody else, no LinkedIn.

Operator, 2026-09-30: "generate only for the canary contact... email only,
em1-em5. Do not plan or write the other 21 contacts or any LinkedIn steps
for this run."

WHY SCOPE MATTERS HERE RATHER THAN BEING A CONVENIENCE. `westcarygroup-com`
carries 22 contacts and `generate.plan` produced 135 ops for it - 20
persona_angle, 110 linkedin_note, 5 draft. The whole-record path asks the
writer for every contact and stores all-or-nothing per channel, so one
contact's canary depended on twenty-one strangers' copy passing too. It
never did.

The record is COPIED with a single contact before generation, so the real
record is untouched until the emails are merged back inside one
transaction. Only email steps are merged; LinkedIn is left for the ramp.
"""
import collections, copy, re, sys
from src import generate, clients, store, llm

RID = sys.argv[1] if len(sys.argv) > 1 else "westcarygroup-com"
CK = sys.argv[2] if len(sys.argv) > 2 else "lisa-moran"
ROUNDS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
EM = ("em1", "em2", "em3", "em4", "em5")
cfg = clients.load("productive"); model = llm.from_env()

for attempt in range(1, ROUNDS + 1):
    rec = next((r for r in store.load() if r.get("id") == RID), None)
    if rec is None:
        print("no record %s" % RID); break
    contact = next((c for c in rec.get("contacts") or [] if c.get("key") == CK), None)
    if contact is None:
        print("no contact %s on %s" % (CK, RID)); break

    scoped = copy.deepcopy(rec)
    scoped["contacts"] = [copy.deepcopy(contact)]
    try:
        plan = generate._generate_via_campaign(scoped, model, cfg, live=True,
                                               allow_pending_offers=False)
    except Exception as e:
        print("attempt %d RAISED %s %s" % (attempt, type(e).__name__, str(e)[:110]))
        continue
    cr = (plan.get("contacts") or [{}])[0]
    written = (scoped.get("cadence") or {}).get(CK) or {}
    have = [k for k in EM if (written.get(k) or {}).get("body")]
    print("attempt %d: stored_pairs=%d emails_written=%s"
          % (attempt, len(plan.get("stored_pairs") or []), have))
    if cr.get("held"):
        print("   held:", " ".join(str(cr.get("held"))[:200].split()))
        cnt = collections.Counter()
        for r_ in cr.get("gate_rejections") or []:
            for part in str(r_).split("; "):
                k = re.sub(r"\{.*", "", part); k = re.sub(r"'[^']*'", "'..'", k).strip()[:52]
                cnt[k] += 1
        for k, v in cnt.most_common(3):
            print("   %2dx %s" % (v, k))
    if len(have) == 5:
        with store.transaction() as rows:
            target = next(r for r in rows if r["id"] == RID)
            cad = target.setdefault("cadence", {}).setdefault(CK, {})
            for k in EM:
                cad[k] = written[k]
        print("MERGED five emails for %s / %s (email only)" % (RID, CK))
        break
else:
    print("did not converge in %d rounds" % ROUNDS)
