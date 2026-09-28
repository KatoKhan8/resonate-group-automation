#!/usr/bin/env python3
"""READ-ONLY probe: can the cross-channel stop be exercised at all today?

Written for the cross-channel stop live-validation DESIGN (operator decision
14, 2026-09-28). It answers one question and writes nothing anywhere:

    HOW MANY CONTACTS ARE BOUND ON BOTH PROVIDERS, and how many records sit
    in both an EmailBison campaign row and a HeyReach campaign row?

That is the population the cross-channel stop can act on. If it is zero the
stop is not "working" and not "broken" - it is UNEXERCISABLE, and
`inbound._stop_at_provider` renders the absence as `"linkedin: no lead"`,
which it deliberately does NOT treat as a refusal. A sweep over that
population reports clean while stopping nobody, which is the shape of defect
this repository has paid for repeatedly.

WHY THE QUEUE PATH IS EXPLICIT. A worktree has its own empty `work/`, so this
probe run from a worktree against the default path measures an empty estate
and would report zero for the wrong reason - a false negative that looks
exactly like the true one. Point `QUEUE` at the production queue, or pass
`--queue`, and the probe REFUSES rather than answers when the file is absent.

    py -3 scripts/probe_cross_channel_stop.py --queue <path to work/queue.jsonl>

NO PROVIDER CALLS. NO WRITES. Loads two files through `src.store` /
`src.campaigns` and counts. Nothing here may be given a `--live` flag.
"""
import argparse
import os
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--queue", help="path to the production work/queue.jsonl")
    args = parser.parse_args(argv)

    if args.queue:
        os.environ["QUEUE"] = os.path.abspath(args.queue)

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src import campaigns, store

    queue = store.queue_path()
    if not os.path.exists(queue):
        print(f"REFUSED: no queue at {queue}. The state is UNKNOWN, not zero.")
        print("Pass --queue pointing at the production work/queue.jsonl.")
        return 2
    print(f"queue     {queue}")
    print(f"campaigns {store.campaigns_path()}")

    recs = store.load()
    rows = campaigns.load()

    contacts = both = email_only = linkedin_only = unbound = 0
    both_rows = []
    for rec in recs:
        for contact in rec.get("contacts") or []:
            contacts += 1
            has_email = bool(contact.get("bison_lead_id"))
            has_linkedin = bool(contact.get("heyreach_lead_id"))
            if has_email and has_linkedin:
                both += 1
                both_rows.append((rec.get("id"), contact.get("key"),
                                  rec.get("client")))
            elif has_email:
                email_only += 1
            elif has_linkedin:
                linkedin_only += 1
            else:
                unbound += 1

    print(f"\nrecords {len(recs)}  contacts {contacts}")
    print(f"BOUND ON BOTH PROVIDERS        {both}"
          f"   <- the cross-channel stop's whole population")
    print(f"email binding only             {email_only}")
    print(f"linkedin binding only          {linkedin_only}")
    print(f"no provider binding            {unbound}")
    for row in both_rows[:25]:
        print(f"    both: record={row[0]!r} contact={row[1]!r} client={row[2]!r}")

    email_rows = [r for r in rows if r.get("bison_campaign_id")]
    li_rows = [r for r in rows if r.get("heyreach_campaign_id")]
    dual_rows = [r for r in rows
                 if r.get("bison_campaign_id") and r.get("heyreach_campaign_id")]
    print(f"\ncampaign rows {len(rows)}: bison {len(email_rows)}  "
          f"heyreach {len(li_rows)}  BOTH ON ONE ROW {len(dual_rows)}")

    in_email = set()
    in_linkedin = set()
    for row in email_rows:
        in_email |= set(row.get("record_ids") or [])
    for row in li_rows:
        in_linkedin |= set(row.get("record_ids") or [])
    overlap = sorted(in_email & in_linkedin)
    print(f"records in an email row {len(in_email)}  "
          f"in a linkedin row {len(in_linkedin)}  IN BOTH {len(overlap)}")
    for rid in overlap[:25]:
        print(f"    in both rows: {rid!r}")

    print("\nREAD-ONLY. Provider calls 0. Writes 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
