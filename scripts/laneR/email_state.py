"""Lane R step 3: what are 491-498 actually DOING right now?

The whole cross-channel question turns on this. `collision.account_policy`
answers STOP when `anyone_in_sequence`, and every candidate in this cohort is
in one of these campaigns by construction - so whether these campaigns are
RUNNING decides whether the shipped gate refuses the entire population.

Asked of the provider. The store's `status` field is a record of an intention.

Eight campaign reads plus one lead read per sampled person.
"""
import json
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot      # noqa: E402
import readonly  # noqa: E402

OUT = os.path.join(boot.WORKTREE, "work", "laneR")
COHORT = list(range(491, 499))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20260925

    readonly.install(os.path.join(boot.PROD, "config", ".env"))
    readonly.selftest()

    from src.providers import bison

    print("=== the eight campaigns, from the provider ===")
    camps = {}
    for cid in COHORT:
        try:
            row = bison.campaign(cid)
        except Exception as exc:                     # noqa: BLE001
            print("  %s : READ FAILED %s" % (cid, type(exc).__name__))
            continue
        data = row.get("data") if isinstance(row, dict) else None
        data = data if isinstance(data, dict) else row
        camps[cid] = data
        print("  %-4s status=%-12s type=%-10s leads=%s" % (
            cid, data.get("status"), data.get("type"),
            data.get("total_leads")))
    print()

    rows = json.load(open(os.path.join(OUT, "cohort-491-498.json"),
                         encoding="utf-8"))["rows"]
    pool = [r for r in rows if r["bison_lead_id"]]
    random.Random(seed).shuffle(pool)
    sample = pool[:n]
    print("=== per-person email state, provider, n=%d of %d ==="
          % (len(sample), len(pool)))

    verdicts = Counter()
    per_campaign_status = Counter()
    detail = []
    for r in sample:
        try:
            lead = bison.lead(int(r["bison_lead_id"]))
        except Exception as exc:                      # noqa: BLE001
            verdicts["READ_FAILED:%s" % type(exc).__name__] += 1
            detail.append({"record_id": r["record_id"],
                           "state": "READ_FAILED"})
            continue
        data = lead.get("data") if isinstance(lead, dict) else None
        data = data if isinstance(data, dict) else lead
        entries = data.get("lead_campaign_data") or []
        mine = [e for e in entries
                if str(e.get("campaign_id")) in {str(c) for c in COHORT}]
        others = [e for e in entries
                  if str(e.get("campaign_id")) not in {str(c) for c in COHORT}]
        for e in mine:
            per_campaign_status[str(e.get("status"))] += 1
        statuses = {str(e.get("status")) for e in mine}
        replied = bool(data.get("replied") or data.get("replied_at"))
        unsub = bool(data.get("unsubscribed") or data.get("unsubscribed_at"))
        bounced = bool(data.get("bounced") or data.get("bounced_at"))
        verdicts["in_cohort_campaign" if mine else "NOT in any 491-498"] += 1
        if replied:
            verdicts["replied (provider)"] += 1
        if unsub:
            verdicts["unsubscribed (provider)"] += 1
        if bounced:
            verdicts["bounced (provider)"] += 1
        if others:
            verdicts["also in a campaign OUTSIDE 491-498"] += 1
        detail.append({
            "record_id": r["record_id"],
            "cohort_statuses": sorted(statuses),
            "n_other_campaigns": len(others),
            "replied": replied, "unsubscribed": unsub, "bounced": bounced,
            "top_level_keys": sorted(data.keys())[:0],
        })

    print()
    for k, v in verdicts.most_common():
        print("  %-42s %d" % (k, v))
    print()
    print("  per-campaign membership status words:")
    for k, v in per_campaign_status.most_common():
        print("     %-24s %d" % (k, v))
    print()
    print(readonly.report())

    path = os.path.join(OUT, "email-state-sample.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"n": len(sample), "seed": seed, "pool": len(pool),
                   "campaigns": {str(k): {"status": v.get("status"),
                                          "total_leads": v.get("total_leads")}
                                 for k, v in camps.items()},
                   "verdicts": dict(verdicts),
                   "statuses": dict(per_campaign_status),
                   "rows": detail}, fh, indent=1)
    print("\nwrote", path)


if __name__ == "__main__":
    main()
