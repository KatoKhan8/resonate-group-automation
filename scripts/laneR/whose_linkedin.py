"""Lane R: H1 excluded 32 of 33 email-live candidates. WHOSE campaigns?

If they are OUR campaigns the pairing has largely already happened and the
job is a reconciliation. If they are the CLIENT's, the population is spoken
for and must not be touched. Nothing in the store can answer this - exactly
one contact carries `heyreach_lead_id` - so it is asked of the provider.

`campaigns_for_lead` returns campaignId, campaignName, campaignStatus and
this person's leadStatus in each. The NAME is never printed: it is the
client's campaign name. Only the id, the status and whether the id is in our
own attributable set.
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


def ours():
    """Every HeyReach campaign id this system can attribute to itself."""
    ids = set()
    path = os.path.join(boot.WORK, "campaigns.jsonl")
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("heyreach_campaign_id"):
            ids.add(str(row["heyreach_campaign_id"]))
    for line in open(boot.QUEUE, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        for c in row.get("contacts") or []:
            if isinstance(c, dict) and c.get("campaign_id_linkedin"):
                ids.add(str(c["campaign_id_linkedin"]))
    return ids


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 424242

    readonly.install(os.path.join(boot.PROD, "config", ".env"))
    readonly.selftest()
    from src.providers import heyreach

    mine = ours()
    print("HeyReach campaign ids attributable to us, from the store: %d"
          % len(mine))

    rows = json.load(open(os.path.join(OUT, "cohort-491-498.json"),
                          encoding="utf-8"))["rows"]
    pool = [r for r in rows if r["profile_url"]]
    random.Random(seed).shuffle(pool)
    sample = pool[:n]

    tally = Counter()
    per_person = Counter()
    lead_status = Counter()
    camp_status = Counter()
    hit_ids = Counter()
    detail = []
    for r in sample:
        try:
            camps, _t = heyreach.campaigns_for_lead(r["profile_url"])
        except Exception as exc:                       # noqa: BLE001
            tally["UNVERIFIABLE (%s)" % type(exc).__name__] += 1
            continue
        if not camps:
            tally["in NO linkedin campaign"] += 1
            per_person[0] += 1
            continue
        per_person[len(camps)] += 1
        ids = {str(c.get("campaignId")) for c in camps}
        for cid in ids:
            hit_ids[cid] += 1
        for c in camps:
            lead_status[str(c.get("leadStatus"))] += 1
            camp_status[str(c.get("campaignStatus"))] += 1
        if ids <= mine:
            tally["ONLY in campaigns we can attribute to us"] += 1
        elif ids & mine:
            tally["in BOTH ours and campaigns we cannot attribute"] += 1
        else:
            tally["ONLY in campaigns we CANNOT attribute (the client's)"] += 1
        detail.append({"record_id": r["record_id"],
                       "n_campaigns": len(camps),
                       "ours": sorted(ids & mine),
                       "not_ours": sorted(ids - mine)})

    print("\nsampled %d profiles\n" % len(sample))
    for k, c in tally.most_common():
        print("  %-56s %d" % (k, c))
    print("\n  campaigns per person:")
    for k, c in sorted(per_person.items()):
        print("     %-4s campaigns : %d people" % (k, c))
    print("\n  their leadStatus across all those memberships:")
    for k, c in lead_status.most_common():
        print("     %-28s %d" % (k, c))
    print("\n  those campaigns' own status:")
    for k, c in camp_status.most_common():
        print("     %-28s %d" % (k, c))
    print("\n  the %d distinct campaign ids hit; top 12 by how many of the "
          "sample they hold:" % len(hit_ids))
    for cid, c in hit_ids.most_common(12):
        print("     %-12s %-14s %d" % (
            cid, "OURS" if cid in mine else "not attributable", c))
    print("\n" + readonly.report())

    path = os.path.join(OUT, "whose-linkedin.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"n": len(sample), "seed": seed, "tally": dict(tally),
                   "per_person": {str(k): v for k, v in per_person.items()},
                   "lead_status": dict(lead_status),
                   "campaign_status": dict(camp_status),
                   "ours": sorted(mine),
                   "hit_ids": dict(hit_ids), "rows": detail}, fh, indent=1)
    print("wrote", path)


if __name__ == "__main__":
    main()
