"""Lane R step 1c: the cohort, joined the way the store actually shapes it.

A contact carries NO email campaign id. `campaigns.jsonl` carries
`bison_campaign_id` and `record_ids`, so the 491-498 population is

    campaigns with bison_campaign_id in 491..498
      -> their record_ids
        -> those records' contacts

and every number below names which of those three levels it counts.

Reads only, store only. No provider call.
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402

COHORT = set(range(491, 499))
OUT_OF_SCOPE = {503, 504, 505}
OUT = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "work", "laneR")


def jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def slug_of(value):
    """The /in/ slug, or None. A value that is not a profile URL is NOT one."""
    s = str(value or "").strip()
    if not s:
        return None
    low = s.lower()
    if "linkedin.com/in/" not in low:
        return None
    tail = s[low.index("linkedin.com/in/") + len("linkedin.com/in/"):]
    tail = tail.split("?")[0].split("#")[0].strip("/")
    return tail or None


def profile_url(slug):
    return "https://www.linkedin.com/in/%s" % slug


def main():
    os.makedirs(OUT, exist_ok=True)
    camps = list(jsonl(boot.CAMPAIGNS))

    def pick(ids):
        return [c for c in camps
                if str(c.get("bison_campaign_id") or "").isdigit()
                and int(c["bison_campaign_id"]) in ids]

    mine = pick(COHORT)
    theirs = pick(OUT_OF_SCOPE)
    print("campaign rows with bison_campaign_id in 491-498 :", len(mine))
    print("campaign rows with bison_campaign_id in 503-505 :", len(theirs))
    print("all bison_campaign_id values present            :",
          sorted(int(c["bison_campaign_id"]) for c in camps
                 if str(c.get("bison_campaign_id") or "").isdigit()))
    print()

    def record_ids(rows):
        ids = set()
        for c in rows:
            for r in c.get("record_ids") or []:
                ids.add(str(r))
        return ids

    mine_recs, theirs_recs = record_ids(mine), record_ids(theirs)
    print("distinct record_ids, 491-498 :", len(mine_recs))
    print("distinct record_ids, 503-505 :", len(theirs_recs))
    print("overlap between the two      :", len(mine_recs & theirs_recs))
    print()

    per_campaign = defaultdict(set)
    for c in mine:
        for r in c.get("record_ids") or []:
            per_campaign[int(c["bison_campaign_id"])].add(str(r))
    for cid in sorted(per_campaign):
        print("  campaign %s -> %d records" % (cid, len(per_campaign[cid])))
    print()

    rows, oos_rows = [], []
    rec_state = Counter()
    shape = Counter()
    n_rec_seen = 0
    for rec in jsonl(boot.QUEUE):
        rid = str(rec.get("id"))
        in_mine, in_theirs = rid in mine_recs, rid in theirs_recs
        if not (in_mine or in_theirs):
            continue
        n_rec_seen += 1
        for c in rec.get("contacts") or []:
            if not isinstance(c, dict):
                continue
            slug = slug_of(c.get("linkedin"))
            row = {
                "record_id": rid,
                "domain": rec.get("domain"),
                "contact_key": c.get("key"),
                "bison_lead_id": c.get("bison_lead_id"),
                "heyreach_lead_id": c.get("heyreach_lead_id"),
                "campaign_id_linkedin": c.get("campaign_id_linkedin"),
                "linkedin_raw": c.get("linkedin"),
                "slug": slug,
                "profile_url": profile_url(slug) if slug else None,
                "title": c.get("title"),
                "persona": c.get("persona"),
                "first_name": c.get("first_name"),
                "last_name": c.get("last_name"),
                "sendable": c.get("sendable"),
                "stopped": c.get("stopped"),
                "paused": c.get("paused"),
                "do_not_contact": c.get("do_not_contact"),
                "record_state": rec.get("state") or rec.get("status"),
                "campaigns": sorted(
                    cid for cid, rs in per_campaign.items() if rid in rs),
            }
            (rows if in_mine else oos_rows).append(row)
            if in_mine:
                rec_state[str(row["record_state"])] += 1
                shape["slug" if slug else "NOT a /in/ profile url"] += 1

    print("records of 491-498 found in queue.jsonl :", n_rec_seen,
          "of", len(mine_recs))
    print()
    print("--- 491-498, contact level ---")
    print("contacts under those records            :", len(rows))
    b = [r for r in rows if r["bison_lead_id"]]
    print("  carrying bison_lead_id                :", len(b))
    print("  carrying a non-empty linkedin value   :",
          len([r for r in b if str(r["linkedin_raw"] or "").strip()]))
    print("  whose linkedin value is a /in/ url    :",
          len([r for r in b if r["slug"]]))
    print("  carrying heyreach_lead_id             :",
          len([r for r in b if r["heyreach_lead_id"]]))
    print("  carrying campaign_id_linkedin (store) :",
          len([r for r in b if r["campaign_id_linkedin"]]))
    print("  stopped / paused / DNC                :",
          len([r for r in b if r["stopped"] or r["paused"]
               or r["do_not_contact"]]))
    print("  distinct domains behind them          :",
          len({r["domain"] for r in b}))
    print("  record states                         :",
          ", ".join("%s=%d" % kv for kv in rec_state.most_common()))
    print("  linkedin value shapes                 :",
          ", ".join("%s=%d" % kv for kv in shape.most_common()))
    print()
    print("--- 503/504/505, contact level ---")
    print("contacts under those records            :", len(oos_rows))
    print("  carrying a non-empty linkedin value   :",
          len([r for r in oos_rows
               if str(r["linkedin_raw"] or "").strip()]))
    print("  whose linkedin value is a /in/ url    :",
          len([r for r in oos_rows if r["slug"]]))

    path = os.path.join(OUT, "cohort-491-498.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"cohort": sorted(COHORT), "n_contacts": len(rows),
                   "rows": rows}, fh, indent=1)
    print("\nwrote", path, "(gitignored,", len(rows), "rows)")


if __name__ == "__main__":
    main()
