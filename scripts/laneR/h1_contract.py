"""Lane R: is `GetCampaignsForLead` actually filtering, or agreeing with me?

30 of 30 sampled profiles came back already enrolled, and EIGHT campaign ids
appeared for every one of them. That is also exactly what an ignored filter
looks like - the documented failure mode on this vendor, measured on the
inbox route, where an unrecognised key is discarded in silence and the whole
estate comes back looking like a result.

A finding this size is worth more than a plausible story, so four controls:

  C1  a well-formed profile url that cannot be in the estate  -> expect 0,
      or a stated refusal. Eight campaigns here means the filter is fiction.
  C2  the operator's own test identity                        -> expect the
      campaign the 2026-09-25 stop was measured on, and NOT the eight.
  C3  two real profiles side by side                          -> expect
      DIFFERENT campaign sets. Identical sets are the tell.
  C4  the eight ids, read as campaigns                        -> how large
      are they? Eight campaigns holding the whole cohort is a fact about the
      client's estate, not about this sample, if they are huge.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot      # noqa: E402
import readonly  # noqa: E402

OUT = os.path.join(boot.WORKTREE, "work", "laneR")
EIGHT = ["473854", "523987", "429680", "467366", "523922", "429679",
         "523932", "523983"]


def main():
    readonly.install(os.path.join(boot.PROD, "config", ".env"))
    readonly.selftest()
    from src.providers import heyreach

    print("=== C1: a profile that cannot be in the estate ===")
    for slug in ("laneR-control-does-not-exist-20260925",
                 "aaaaaaaa-bbbbbbbb-cccccccc-not-a-person"):
        url = "https://www.linkedin.com/in/%s" % slug
        try:
            camps, tot = heyreach.campaigns_for_lead(url)
            print("  control slug -> %d campaigns, totalCount=%s"
                  % (len(camps), tot))
            if camps:
                print("     !! THE FILTER IS NOT HONOURED. ids:",
                      sorted({str(c.get('campaignId')) for c in camps}))
        except Exception as exc:                        # noqa: BLE001
            print("  control slug -> refused: %s %s"
                  % (type(exc).__name__, str(exc)[:90]))

    print("\n=== C3: two real profiles, do their campaign sets differ? ===")
    rows = json.load(open(os.path.join(OUT, "cohort-491-498.json"),
                          encoding="utf-8"))["rows"]
    pool = [r for r in rows if r["profile_url"]]
    random.Random(7).shuffle(pool)
    sets = []
    for r in pool[:4]:
        camps, tot = heyreach.campaigns_for_lead(r["profile_url"])
        ids = sorted({str(c.get("campaignId")) for c in camps})
        sets.append(set(ids))
        print("  record %-8s -> %2d campaigns, totalCount=%s"
              % (str(r["record_id"])[:8], len(ids), tot))
    if len(sets) >= 2:
        same = all(s == sets[0] for s in sets)
        print("  all four identical? %s   %s" % (
            same,
            "!! that is what an ignored filter looks like" if same
            else "sets differ - the filter is honoured"))
        for i in range(1, len(sets)):
            print("     only in #1 vs #%d: %d ids" % (
                i + 1, len(sets[0] - sets[i])))

    print("\n=== C4: how big are the eight campaigns everybody is in? ===")
    for cid in EIGHT:
        try:
            stats = heyreach.campaign_stats(int(cid))
            leads, total = heyreach.campaign_leads(int(cid), 0, 1)
            print("  %-8s leads=%-8s connectionsSent=%-7s replies=%-6s "
                  "uniqueContacted=%s"
                  % (cid, total, stats.get("connectionsSent"),
                     stats.get("totalMessageReplies"),
                     stats.get("uniqueLeadsContacted")))
        except Exception as exc:                        # noqa: BLE001
            print("  %-8s unreadable: %s %s"
                  % (cid, type(exc).__name__, str(exc)[:70]))

    print("\n" + readonly.report())


if __name__ == "__main__":
    main()
