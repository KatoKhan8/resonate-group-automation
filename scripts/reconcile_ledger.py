#!/usr/bin/env python3
"""Settle unresolved action-ledger keys FROM PROVIDER TRUTH, never from hope.

WHY THIS EXISTS.

`executionguard.authorize` refuses a key that is still ATTEMPTED: "provider
truth must settle it before any further attempt". That is the right refusal
and it is the one that makes a crash safe - a reservation written before a
prospect-facing write means a run that dies mid-write leaves a durable trace
rather than a question.

But the refusal has to be answerable, and until now nothing answered it. A
canary that died on a provider READ TIMEOUT left a key ATTEMPTED, and every
later attempt for that contact refused - correctly, and permanently, because
the thing that would clear it was a person reading the provider by hand.

WHAT IT MAY AND MAY NOT CONCLUDE.

    the lead IS at the provider        -> the write landed. SENT.
    the lead is NOT at the provider    -> the write did not land. FAILED,
                                          which is reservable again, so a
                                          clean retry is allowed.
    the provider cannot be read        -> NOTHING. Leave it ATTEMPTED.

That third branch is the whole discipline. An unreadable provider is not
evidence of absence, and "we could not check, so assume it did not happen" is
precisely how a person gets messaged twice. `UNRESOLVED` exists for the case
where provider truth genuinely cannot settle it, and this script never writes
it automatically - that is a judgement about a specific incident, not a
default.

It reads and it settles. It never writes to a provider.

DRY RUN BY DEFAULT.

    py -3 scripts/reconcile_ledger.py
    py -3 scripts/reconcile_ledger.py --live --by claude
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import actionledger, campaigns, store  # noqa: E402
from src.providers import heyreach  # noqa: E402

# Only operations this script knows how to check against a provider. A key for
# anything else is reported and left alone: settling a key whose evidence this
# script cannot read would be guessing with extra steps.
CHECKABLE = ("heyreach.add_lead",)


def _profile_for(row, recs):
    """The LinkedIn URL this key's contact carries, or None."""
    rec_id, contact_key = row.get("rec_id"), row.get("contact_key")
    for rec in recs:
        if rec.get("id") != rec_id:
            continue
        for contact in rec.get("contacts") or ():
            if contact.get("key") == contact_key:
                return contact.get("linkedin")
    return None


def main(argv=None):
    p = argparse.ArgumentParser(prog="reconcile_ledger", description=__doc__)
    p.add_argument("--live", action="store_true")
    p.add_argument("--by", default="operator")
    a = p.parse_args(argv)

    rows = actionledger.unsettled()
    if not rows:
        print("nothing unsettled")
        return 0

    recs = store.load()
    camp_rows = campaigns.load()
    settled, left = 0, 0

    for row in rows:
        key = row.get("key")
        operation = row.get("operation")
        print(f"\n{key}")
        print(f"  state      {row.get('state')}  since {row.get('at')}")
        print(f"  operation  {operation}")
        if operation not in CHECKABLE:
            print("  LEFT       this script cannot read provider truth for "
                  "that operation")
            left += 1
            continue

        provider_id = None
        for campaign in camp_rows:
            if str(campaign.get("campaign_id")) == str(row.get("campaign_id")):
                provider_id = campaign.get("heyreach_campaign_id")
                break
        if not provider_id:
            print(f"  LEFT       campaign {row.get('campaign_id')!r} names no "
                  f"heyreach campaign, so there is nothing to read")
            left += 1
            continue

        url = _profile_for(row, recs)
        if not url:
            print("  LEFT       the contact carries no LinkedIn URL, so "
                  "membership cannot be checked")
            left += 1
            continue

        try:
            membership = heyreach.readback_membership(provider_id, [url])
        except Exception as e:
            # THE BRANCH THAT MUST NOT GUESS.
            print(f"  LEFT       provider unreadable ({type(e).__name__}: "
                  f"{e}). An unreadable provider is not evidence of absence")
            left += 1
            continue

        present = bool(membership.get("found"))
        if present:
            verdict, why = actionledger.SENT, (
                f"reconciled from provider truth: the lead IS in campaign "
                f"{provider_id}")
        else:
            verdict, why = actionledger.FAILED, (
                f"reconciled from provider truth: the lead is NOT in campaign "
                f"{provider_id}, so the attempt did not reach it")
        print(f"  PROVIDER   found={sorted(membership.get('found') or [])} "
              f"total={membership.get('total')}")
        print(f"  {'SETTLE' if a.live else 'WOULD SETTLE'}     {verdict}: {why}")
        if a.live:
            # SETS ARE NOT JSON. `readback_membership` returns `found` and
            # `missing` as sets because that is the right shape to compare,
            # and the ledger is a JSONL file - so handing it the raw dict
            # raises inside the encoder, after the transaction has opened.
            # Sorted lists preserve the evidence and serialise.
            actionledger.settle(
                key, verdict, why=f"{why} (by {a.by})",
                readback={
                    "found": sorted(membership.get("found") or []),
                    "missing": sorted(membership.get("missing") or []),
                    "total": membership.get("total"),
                })
            settled += 1

    print(f"\n{settled} settled, {left} left for a person"
          f"{'' if a.live else '  (DRY RUN - nothing written)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
