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
    the operation is not checkable     -> UNCONFIRMABLE, with the reason.

That third branch is the whole discipline. An unreadable provider is not
evidence of absence, and "we could not check, so assume it did not happen" is
precisely how a person gets messaged twice. `UNRESOLVED` exists for the case
where provider truth genuinely cannot settle it, and this script never writes
it automatically - that is a judgement about a specific incident, not a
default.

The fourth branch closes the silence bug: an operation this script cannot
check against ANY provider is settled to UNCONFIRMABLE with a reason, rather
than skipped with a `continue` that reports "0 settled, 0 problems" while
keys rot.

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
from src.providers import bison, heyreach  # noqa: E402

# Operations this script can check against a provider. Each entry names the
# provider module and the check strategy. A key for anything else is settled
# to UNCONFIRMABLE with the reason, not silently skipped.
CHECKABLE = ("heyreach.add_lead", "heyreach.activate", "bison.activate")


def _profile_for(row, recs):
    """The LinkedIn URL this key's contact carries, or None."""
    rec_id, contact_key = row.get("rec_id"), row.get("contact_key")
    for rec in recs:
        if str(rec.get("id")) != str(rec_id):
            continue
        for contact in rec.get("contacts") or ():
            if contact.get("key") == contact_key:
                return contact.get("linkedin")
    return None


def _email_for(row, recs):
    """The email address this key's contact carries, or None."""
    rec_id, contact_key = row.get("rec_id"), row.get("contact_key")
    for rec in recs:
        if str(rec.get("id")) != str(rec_id):
            continue
        for contact in rec.get("contacts") or ():
            if contact.get("key") == contact_key:
                return contact.get("email")
    return None


def _bison_campaign_id(row, camp_rows):
    """The EmailBison campaign id for this ledger row's campaign, or None."""
    for campaign in camp_rows:
        if str(campaign.get("campaign_id")) == str(row.get("campaign_id")):
            return campaign.get("bison_campaign_id")
    return None


def _heyreach_campaign_id(row, camp_rows):
    """The HeyReach campaign id for this ledger row's campaign, or None."""
    for campaign in camp_rows:
        if str(campaign.get("campaign_id")) == str(row.get("campaign_id")):
            return campaign.get("heyreach_campaign_id")
    return None


def _check_heyreach_add_lead(row, recs, camp_rows):
    """Check a heyreach.add_lead key against provider truth.

    Returns (verdict, why, readback) or (None, reason, None) if uncheckable.
    """
    provider_id = _heyreach_campaign_id(row, camp_rows)
    if not provider_id:
        return None, (f"campaign {row.get('campaign_id')!r} names no heyreach "
                      f"campaign, so there is nothing to read"), None

    url = _profile_for(row, recs)
    if not url:
        return None, ("the contact carries no LinkedIn URL, so membership "
                      "cannot be checked"), None

    try:
        membership = heyreach.readback_membership(provider_id, [url])
    except Exception as e:
        return None, (f"provider unreadable ({type(e).__name__}: {e}). "
                      f"An unreadable provider is not evidence of absence"), None

    present = bool(membership.get("found"))
    readback = {
        "found": sorted(membership.get("found") or []),
        "missing": sorted(membership.get("missing") or []),
        "total": membership.get("total"),
    }
    if present:
        return actionledger.SENT, (
            f"reconciled from provider truth: the lead IS in campaign "
            f"{provider_id}"), readback
    return actionledger.FAILED, (
        f"reconciled from provider truth: the lead is NOT in campaign "
        f"{provider_id}, so the attempt did not reach it"), readback


def _check_heyreach_activate(row, recs, camp_rows):
    """Check a heyreach.activate key against provider truth.

    An activate reservation means the campaign was to be started. Provider
    truth is: is the campaign in a sending state, AND is this lead in it?
    """
    provider_id = _heyreach_campaign_id(row, camp_rows)
    if not provider_id:
        return None, (f"campaign {row.get('campaign_id')!r} names no heyreach "
                      f"campaign, so there is nothing to read"), None

    url = _profile_for(row, recs)
    if not url:
        return None, ("the contact carries no LinkedIn URL, so membership "
                      "cannot be checked"), None

    try:
        status = heyreach.campaign_status(provider_id)
    except Exception as e:
        return None, (f"provider unreadable ({type(e).__name__}: {e}). "
                      f"An unreadable provider is not evidence of absence"), None

    if status in ("IN_PROGRESS",):
        pass
    elif status in ("DRAFT",):
        return actionledger.FAILED, (
            f"reconciled from provider truth: campaign {provider_id} is "
            f"{status!r} and cannot be sending"), {"status": status}
    else:
        return None, (f"campaign {provider_id} is {status!r}, which this "
                      f"reconciler cannot classify as sending or not"), None

    try:
        membership = heyreach.readback_membership(provider_id, [url])
    except Exception as e:
        return None, (f"provider unreadable on membership check "
                      f"({type(e).__name__}: {e})"), None

    present = bool(membership.get("found"))
    readback = {
        "status": status,
        "found": sorted(membership.get("found") or []),
        "missing": sorted(membership.get("missing") or []),
        "total": membership.get("total"),
    }
    if present:
        return actionledger.SENT, (
            f"reconciled from provider truth: campaign {provider_id} is "
            f"{status} and the lead IS in it"), readback
    return actionledger.FAILED, (
        f"reconciled from provider truth: campaign {provider_id} is "
        f"{status} but the lead is NOT in it"), readback


def _check_bison_activate(row, recs, camp_rows):
    """Check a bison.activate key against provider truth.

    An activate reservation means the campaign was to be resumed. Provider
    truth is: is the campaign in a started state, AND is this lead in it?
    """
    provider_id = _bison_campaign_id(row, camp_rows)
    if not provider_id:
        return None, (f"campaign {row.get('campaign_id')!r} names no bison "
                      f"campaign, so there is nothing to read"), None

    email = _email_for(row, recs)
    if not email:
        return None, ("the contact carries no email address, so bison "
                      "membership cannot be checked"), None

    try:
        camp = bison.campaign(provider_id)
    except Exception as e:
        return None, (f"provider unreadable ({type(e).__name__}: {e}). "
                      f"An unreadable provider is not evidence of absence"), None

    status = str(camp.get("status") or "").lower()
    if status in bison.STARTED_STATES:
        pass
    elif status in ("draft", "paused"):
        return actionledger.FAILED, (
            f"reconciled from provider truth: campaign {provider_id} is "
            f"{status!r} and is not sending"), {"status": status}
    else:
        return None, (f"campaign {provider_id} is {status!r}, which this "
                      f"reconciler cannot classify as sending or not"), None

    try:
        lead_row = bison.find_lead_by_email(email)
    except Exception as e:
        return None, (f"provider unreadable on lead lookup "
                      f"({type(e).__name__}: {e})"), None

    if lead_row is None:
        return actionledger.FAILED, (
            f"reconciled from provider truth: no lead with email {email!r} "
            f"exists at the provider"), {"status": status, "lead_found": False}

    lead_id = lead_row.get("id")
    try:
        states = bison.membership(provider_id, [lead_id])
    except Exception as e:
        return None, (f"provider unreadable on membership check "
                      f"({type(e).__name__}: {e})"), None

    in_campaign = lead_id in states if isinstance(lead_id, int) else False
    readback = {"status": status, "lead_id": lead_id,
                "lead_status": states.get(lead_id) if in_campaign else None}
    if in_campaign:
        return actionledger.SENT, (
            f"reconciled from provider truth: campaign {provider_id} is "
            f"{status} and lead {lead_id} IS in it "
            f"(status: {states.get(lead_id)})"), readback
    return actionledger.FAILED, (
        f"reconciled from provider truth: campaign {provider_id} is "
        f"{status} but lead {lead_id} is NOT in it"), readback


_CHECKERS = {
    "heyreach.add_lead": _check_heyreach_add_lead,
    "heyreach.activate": _check_heyreach_activate,
    "bison.activate": _check_bison_activate,
}


def _record_touch_for(row, recs):
    """Write the confirmed touch for a key that provider truth says was SENT.

    Constructs a minimal Authorization from the ledger row so
    `providerwrites._record_confirmed_touch` can find the record and step.
    Idempotent: `events.record` is already idempotent on the event id, and
    the id is derived from the action key.
    """
    from src import providerwrites
    from src.executionguard import Authorization

    auth = Authorization(
        key=row.get("key"),
        operation=row.get("operation"),
        channel=row.get("channel"),
        workspace=row.get("workspace"),
        campaign_id=row.get("campaign_id"),
        sender_id=row.get("sender_id"),
        rec_id=row.get("rec_id"),
        contact_key=row.get("contact_key"),
        step_key=row.get("step_key"),
        fingerprint=row.get("fingerprint"),
    )
    providerwrites._record_confirmed_touch(auth)


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
    settled, unconfirmable, left = 0, 0, 0

    for row in rows:
        key = row.get("key")
        operation = row.get("operation")
        print(f"\n{key}")
        print(f"  state      {row.get('state')}  since {row.get('at')}")
        print(f"  operation  {operation}")

        checker = _CHECKERS.get(operation)
        if checker is None:
            reason = (f"this reconciler cannot check {operation!r} against "
                      f"any provider")
            print(f"  UNCONFIRMABLE  {reason}")
            if a.live:
                actionledger.settle(
                    key, actionledger.UNCONFIRMABLE,
                    why=f"{reason} (by {a.by})")
            unconfirmable += 1
            continue

        verdict, why, readback = checker(row, recs, camp_rows)
        if verdict is None:
            print(f"  LEFT       {why}")
            left += 1
            continue

        # AN UNRESOLVED KEY MAY BE PROVEN SENT. IT MAY NEVER BE CALLED FAILED.
        #
        # Added in review, 2026-09-20, before this reached master. The loop
        # walks `unsettled()`, which is ATTEMPTED **and** UNRESOLVED, and
        # applied one rule to both. For an ATTEMPTED key "the lead is not at
        # the provider" is good evidence the write never landed, and FAILED -
        # which is reservable - is the right answer.
        #
        # For an UNRESOLVED key it is not. UNRESOLVED means we could not
        # determine whether the person was contacted, and `actionledger` puts
        # it in BLOCKING so the key is refused forever until a human looks.
        # A lead ABSENT from a campaign is not proof nobody was emailed - a
        # lead that was added, emailed and then stopped or removed reads
        # exactly the same way. Settling that to FAILED would return the key
        # to reservable and re-open the duplicate-send path that Buggie
        # attacked and confirmed closed (REFUTED-001 in the problem register).
        #
        # Positive evidence is different and is allowed through: the lead IS
        # there, so the action demonstrably landed, so SENT is a fact rather
        # than an inference from absence. The asymmetry is the same one
        # `senderheadroom` runs on - presence proves, absence does not.
        if (row.get("state") == actionledger.UNRESOLVED
                and verdict != actionledger.SENT):
            print(f"  LEFT       this key is UNRESOLVED and the provider does "
                  f"not positively confirm the action ({why}). Absence is not "
                  f"proof nobody was contacted, and settling it {verdict} "
                  f"would make the key reservable again")
            left += 1
            continue

        print(f"  {'SETTLE' if a.live else 'WOULD SETTLE'}     "
              f"{verdict}: {why}")
        if a.live:
            actionledger.settle(
                key, verdict, why=f"{why} (by {a.by})",
                readback=readback)
            if verdict == actionledger.SENT:
                try:
                    _record_touch_for(row, recs)
                except Exception as e:
                    print(f"  TOUCH FAILED  {type(e).__name__}: {e}")
            settled += 1

    print(f"\n{settled} settled, {unconfirmable} unconfirmable, "
          f"{left} left for a person"
          f"{'' if a.live else '  (DRY RUN - nothing written)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
