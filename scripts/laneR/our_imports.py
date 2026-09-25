"""Lane R: what member_id shape do OUR OWN imported leads get?

63% of the client's campaign rows carry an `imp_`-prefixed member id and the
only live-validated stop matched a NUMERIC one. If leads WE add by profile
url come back `imp_`, then every cross-channel pair this lane plans would be
bound to an identifier no stop has ever been proven against - and the stop
route answers such a failure with "the lead is not present in the campaign",
which reads as a membership problem rather than an identifier one.

Our own HeyReach campaigns, from the store. Read-only.
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot      # noqa: E402
import readonly  # noqa: E402

OUT = os.path.join(boot.WORKTREE, "work", "laneR")


def shape(value):
    s = str(value or "")
    if not s:
        return "EMPTY"
    if re.fullmatch(r"\d+", s):
        return "numeric"
    if s.startswith("imp_"):
        return "imp_ prefixed"
    if s.startswith("ACoAA"):
        return "ACoAA urn"
    return "other"


def ours():
    ids = set()
    for line in open(os.path.join(boot.WORK, "campaigns.jsonl"),
                     encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("heyreach_campaign_id"):
                ids.add(int(r["heyreach_campaign_id"]))
    for line in open(boot.QUEUE, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        for c in r.get("contacts") or []:
            if isinstance(c, dict) and c.get("campaign_id_linkedin"):
                ids.add(int(c["campaign_id_linkedin"]))
    return sorted(ids)


def main():
    readonly.install(os.path.join(boot.PROD, "config", ".env"))
    readonly.selftest()
    from src.providers import heyreach

    mine = ours()
    print("HeyReach campaigns attributable to us: %d" % len(mine))
    print()
    overall = Counter()
    per = {}
    for cid in mine:
        try:
            leads, total = heyreach.campaign_leads(cid, 0, 100)
        except Exception as exc:                        # noqa: BLE001
            print("  %-8s unreadable: %s" % (cid, type(exc).__name__))
            continue
        s = Counter(shape(r.get("member_id")) for r in leads)
        st = Counter(str(r.get("campaign_status") or r.get("lead_status")
                         or "?") for r in leads)
        per[cid] = {"rows": len(leads), "total": total, "shapes": dict(s)}
        overall.update(s)
        print("  campaign %-8s rows=%-4d total=%-6s %-44s %s"
              % (cid, len(leads), total, dict(s), dict(st)))
    print()
    print("  OUR OWN leads, member_id shapes overall :", dict(overall))
    n = sum(overall.values())
    if n:
        imp = overall.get("imp_ prefixed", 0)
        print("  %d of %d (%.0f%%) are `imp_` prefixed - the class NO stop "
              "has ever been validated against." % (imp, n, 100.0 * imp / n))
    print("\n" + readonly.report())
    with open(os.path.join(OUT, "our-import-shapes.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"campaigns": per, "overall": dict(overall)}, fh, indent=1)


if __name__ == "__main__":
    main()
