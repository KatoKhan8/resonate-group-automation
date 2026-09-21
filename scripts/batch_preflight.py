#!/usr/bin/env python3
"""Run the factory's own refusals BEFORE the push, and prune what fails.

    py -3 scripts/batch_preflight.py --batch batch-1-2026-09-21
    py -3 scripts/batch_preflight.py --batch batch-1-2026-09-21 --apply

READ-ONLY without `--apply`. With it, the contacts that would be refused move
to the record's `excluded` list, carrying the refusal verbatim, and accounts
left with nobody leave the campaign.

## WHY A PRE-FLIGHT RATHER THAN CATCHING THE EXCEPTION

`bisonfactory.stage` refuses a WHOLE CAMPAIGN when any lead in it collides,
which is the right shape for a gate: it will not part-stage a cohort and
leave somebody wondering which half went. But it means one colliding contact
costs the other forty-four their push. Batch 1 hit exactly that - 96 contacts
across seven campaigns, and all eight campaigns refused.

So the pruning happens here, before the write, and the factory's refusal
stays as the backstop it is meant to be. Both run the same functions:
`collision.check_account` and `collision.account_policy`.

## WHAT THE LIVE CHECK KNOWS THAT THE LOCAL WALK DOES NOT

The local last-touch index answers "when did anybody last touch this
account". The live check answers what the client's estate is doing RIGHT NOW,
and it is stricter in three ways that matter:

    in_sequence        somebody is being mailed today. STOP.
    stopped            a campaign ended early - the state a reply or an
                       unsubscribe leaves behind. HOLD.
    bounced            the data is suspect. HOLD.
    sequence_finished  ran its course, no reply. ALLOWED, and still reported,
                       so "cold outreach" is never claimed about a worked
                       account.

Batch 1's local walk cleared 519 accounts on recency and the live check
refused 96 contacts at those same accounts. Recency is not the whole rule and
this is the evidence.

## THE PLANTED-NAME CHECK, AND WHY IT FIRES ON GOOD COPY

`_refuse_bad_greetings` refuses a body containing ANOTHER cohort member's
first name - the "hi-jacob" defect class, where one prospect's letter names
somebody else. Our copy names the recipient's own COMPANY three times, so a
cohort containing a person called Brick and a company called Brick Media
Group trips it.

The guard is right to fire: it cannot tell a company from a person, and the
cost of being wrong in the other direction is a prospect reading a stranger's
name. The lead is excluded and the reason recorded.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import bisonfactory, campaigns, collision, store        # noqa: E402
from src.providers import bison, load_env                        # noqa: E402


def planted_name_problems(plan):
    """Resolve the planted-name conflict by removing the SMALLER side.

    The guard refuses a body containing another cohort member's first name.
    Two ways to satisfy it - drop everyone whose body carries the name, or
    drop the one person who owns it - and on batch 1 the difference was 46
    leads against 1.

    **The offending name was 'Mark' and the word in the bodies was
    'Marketing'.** The guard does a containment check, so every lead whose
    industry line reads "I work with Marketing & Advertising teams" carried
    a cohort member's first name. Excluding 46 correct letters to keep one
    would be the tail wagging the dog; excluding the single lead called Mark
    satisfies the guard's actual intent - that no body names a stranger -
    at a fortieth of the cost.

    Both sides are recorded with the reason, so neither disappears quietly.
    """
    leads = plan.get("leads") or []
    owners = collections.defaultdict(set)
    for lead in leads:
        first = (lead.get("first_name") or "").strip()
        if len(first) > 1:
            owners[first].add((lead["record_id"], lead["contact_key"]))

    carriers = collections.defaultdict(set)
    for lead in leads:
        own = (lead.get("first_name") or "").strip()
        body = " ".join(str(step.get("body") or "")
                        for step in lead.get("copy") or [])
        for name in owners:
            if name != own and name in body:
                carriers[name].add((lead["record_id"], lead["contact_key"]))

    problems = {}
    for name, carrying in carriers.items():
        owning = owners[name]
        if len(owning) <= len(carrying):
            for key in owning:
                problems[key] = (
                    f"planted-name conflict on {name!r}: this lead's own "
                    f"first name appears inside {len(carrying)} other "
                    f"lead(s) bodies (usually as part of an ordinary word "
                    f"like 'Marketing'), so removing this one lead clears "
                    f"the guard for all of them")
        else:
            for key in carrying:
                problems[key] = (
                    f"body carries another cohort member's first name "
                    f"{name!r} (the hi-jacob defect class)")
    return problems


def collisions_for(plan, workspace_id):
    """Leads the live estate refuses, with the verdict and the reason."""
    leads = plan.get("leads") or []
    by_domain = collections.defaultdict(list)
    for lead in leads:
        domain = str(lead["email"]).rsplit("@", 1)[-1].strip().lower()
        if domain:
            by_domain[domain].append(lead)
    problems, unreadable = {}, {}
    for domain, group in by_domain.items():
        try:
            account = collision.check_account(domain,
                                              expect_workspace=workspace_id)
        except collision.CollisionUnknown as exc:
            for lead in group:
                unreadable[(lead["record_id"], lead["contact_key"])] = (
                    f"the client's estate could not be read for {domain}: "
                    f"{str(exc)[:120]}. Unreadable is not clear")
            continue
        verdict, why = collision.account_policy(account)
        if verdict in (collision.STOP, collision.HOLD):
            for lead in group:
                problems[(lead["record_id"], lead["contact_key"])] = (
                    f"live collision {verdict}: {why}")
    return problems, unreadable


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--batch", default="batch-1-2026-09-21")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    load_env()
    workspace = bison.bound_workspace()
    workspace_id = workspace.get("id")
    rows = [r for r in campaigns.load() if r.get("batch_id") == args.batch]
    print(f"\nPRE-FLIGHT  {args.batch}  campaigns {len(rows)}  "
          f"workspace {workspace_id}\n")

    drop = {}
    for row in rows:
        plan = bisonfactory.stage(row["campaign_id"], live=False)["plan"]
        collided, unreadable = collisions_for(plan, workspace_id)
        planted = planted_name_problems(plan)
        for source in (collided, unreadable, planted):
            drop.update(source)
        print(f"  {row['campaign_id']:38s} leads {len(plan['leads']):>4}  "
              f"collision {len(collided):>3}  unreadable {len(unreadable):>3}  "
              f"planted-name {len(planted):>3}")

    print(f"\n  {len(drop)} contacts would be refused")
    reasons = collections.Counter(str(v).split(":")[0] for v in drop.values())
    for reason, count in reasons.most_common():
        print(f"    {reason[:60].ljust(60)} {count}")

    if not args.apply:
        print("\n  READ-ONLY. Pass --apply to move them to `excluded`.")
        return 0

    moved = 0
    with store.transaction() as current:
        for index, record in enumerate(current):
            record_id = record.get("id")
            wanted = {key for (rid, key) in drop if rid == record_id}
            if not wanted:
                continue
            keep, held = [], list(record.get("excluded") or [])
            for contact in record.get("contacts") or []:
                if contact.get("key") in wanted:
                    held.append(dict(contact, excluded_reason=drop[
                        (record_id, contact["key"])]))
                    moved += 1
                else:
                    keep.append(contact)
            record["contacts"] = keep
            record["excluded"] = held
            current[index] = record
    print(f"\n  moved {moved} contacts to `excluded`")

    rows = campaigns.load()
    recs = {r.get("id"): r for r in store.load()}
    emptied = 0
    for row in rows:
        if row.get("batch_id") != args.batch:
            continue
        keep = [rid for rid in row.get("record_ids") or []
                if (recs.get(rid) or {}).get("contacts")]
        if len(keep) != len(row.get("record_ids") or []):
            emptied += len(row["record_ids"]) - len(keep)
            row["record_ids"] = keep
    campaigns.save(rows)
    print(f"  removed {emptied} accounts left with nobody")

    total = sum(len((recs.get(rid) or {}).get("contacts") or [])
                for row in rows if row.get("batch_id") == args.batch
                for rid in row.get("record_ids") or [])
    print(f"  batch now carries {total} leads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
