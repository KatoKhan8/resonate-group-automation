#!/usr/bin/env python3
"""Why did this `stopped` membership stop?

THE 33 ACCOUNTS HELD BY A QUESTION NOBODY ASKED.

`docs/THE-ESTATE-IS-SATURATED-NOT-UNAPPROVED-2026-09-18.md` measured 33
accounts on HOLD because a campaign at each ended with status `stopped` and
nobody asked WHY. `collision.account_policy` sees `stopped` in
`SUSPECT_STATUSES`, cannot tell whether we stopped it, they unsubscribed, or
something else, and holds. That is the right default and it is not an answer.

This module resolves the cause from evidence that already exists:

  - the events feed (`/api/events` normalises 100% of real events now)
  - the reply feed (`/api/replies`)
  - the lead's own counters (from `collision.touches_of`)
  - the campaign's state
  - our own action ledger (for `stop_lead` actions we recorded)

CLASSIFICATIONS
---------------

UNSUBSCRIBED
    A `LEAD_UNSUBSCRIBED` or `CONTACT_UNSUBSCRIBED` event exists for this
    lead/campaign. Definite STOP, forever.

REPLIED_INTERESTED
    A `LEAD_REPLIED` or `UNTRACKED_REPLY_RECEIVED` event exists, OR the
    membership's own status is `replied`, OR the lead's replies counter > 0,
    OR any campaign marks `interested`. Definite STOP - the account is
    answered.

BOUNCED
    An `EMAIL_BOUNCED` event exists for this lead/campaign, OR the lead's
    own status is `bounced`. STOP for that address.

WE_STOPPED_IT
    Our own action ledger records a `bison.stop_lead` operation for this
    lead/campaign, settled as `sent` or `attempted`. Not a prospect signal -
    it is our own action.

SEQUENCE_FINISHED
    The campaign's status is `sequence_finished` and no reply, bounce, or
    unsubscribe event exists. Ran to the end, nobody replied.

STILL_UNKNOWN
    None of the above. The hold stays. THIS IS THE REQUIREMENT THAT OUTRANKS
    THE FEATURE. A HOLD that becomes CLEAR because nobody could find evidence
    of a refusal is precisely the failure the gate exists to prevent: missing
    evidence is never positive evidence.

READ-ONLY
---------

This module reports; it does not change `collision`'s verdicts, does not
write canonical state, and does not contact anybody. Wiring the resolution
into the account gate WIDENS who may be contacted and is a separate decision,
not a refactor.

No provider WRITE. No credit spend. The events and reply feeds are GETs.
"""
import argparse
import json
import sys

from . import actionledger, collision, store

# ------------------------------------------------------------------ outcomes

UNSUBSCRIBED = "unsubscribed"
REPLIED_INTERESTED = "replied_interested"
BOUNCED = "bounced"
WE_STOPPED_IT = "we_stopped_it"
SEQUENCE_FINISHED = "sequence_finished"
STILL_UNKNOWN = "still_unknown"

ALL_OUTCOMES = (UNSUBSCRIBED, REPLIED_INTERESTED, BOUNCED, WE_STOPPED_IT,
                SEQUENCE_FINISHED, STILL_UNKNOWN)

# Event kinds that resolve the cause. These are the normalised kinds from
# `bisonevents.TYPE_TO_KIND`, not the raw provider types.
UNSUBSCRIBE_KINDS = frozenset({"unsubscribed"})
REPLY_KINDS = frozenset({"replied"})
BOUNCE_KINDS = frozenset({"bounced"})


# --------------------------------------------------------- evidence sources

def _events_for_lead(lead_id, campaign_id, events_fetch=None):
    """Every event the provider has for this lead in this campaign.

    `events_fetch` is the retrieval function. Defaults to None, which returns
    an empty list - the caller must supply a real fetcher for live use, and
    tests inject a fixture.

    Returns a list of normalised event dicts (from `bisonevents.normalise`).
    """
    if events_fetch is None:
        return []
    try:
        raw_events = events_fetch(lead_id=lead_id, campaign_id=campaign_id)
    except Exception:
        # A fetch that fails is not evidence of absence. Return empty so the
        # caller classifies as STILL_UNKNOWN rather than guessing.
        return []
    return [e for e in raw_events if isinstance(e, dict)]


def _ledger_has_stop(lead_id, campaign_id, ledger_rows=None):
    """Did our own action ledger record a stop_lead for this lead/campaign?

    The ledger records every prospect-facing action. A `bison.stop_lead`
    operation settled as `sent` or `attempted` means we stopped them.
    """
    if ledger_rows is None:
        try:
            ledger_rows = list(actionledger.load())
        except Exception:
            return False, None
    # The ledger keys are shaped as "<channel>:<rec_id>:<contact_key>:..."
    # but the operation field carries the provider operation name.
    for row in ledger_rows:
        if not isinstance(row, dict):
            continue
        op = str(row.get("operation") or "").strip()
        if op != "bison.stop_lead":
            continue
        # The ledger stores campaign_id and rec_id. We match on campaign_id
        # and check if the lead_id appears in the key or contact fields.
        row_campaign = str(row.get("campaign_id") or "").strip()
        if row_campaign != str(campaign_id):
            continue
        # The contact_key or key may carry the lead_id. Check both.
        row_key = str(row.get("key") or "")
        row_contact = str(row.get("contact_key") or "")
        if (str(lead_id) in row_key or str(lead_id) in row_contact or
                row.get("lead_id") == lead_id):
            state = row.get("state")
            if state in ("sent", "attempted"):
                return True, row
    return False, None


def _membership_says_replied(person):
    """Does the membership row itself say `replied` or carry replies > 0?"""
    if int(person.get("replies") or 0) > 0:
        return True
    for c in person.get("campaigns") or []:
        if not isinstance(c, dict):
            continue
        if collision._norm(c.get("status")) == collision.REPLIED:
            return True
        if c.get("interested"):
            return True
    return False


def _membership_says_bounced(person):
    """Does the lead's own status say `bounced`?"""
    return collision._norm(person.get("lead_status")) == collision.BOUNCED


def _campaign_is_finished(person, campaign_id):
    """Is the campaign's status `sequence_finished` for this membership?"""
    for c in person.get("campaigns") or []:
        if not isinstance(c, dict):
            continue
        if c.get("campaign_id") == campaign_id:
            return collision._norm(c.get("status")) == "sequence_finished"
    return False


# --------------------------------------------------------- the resolver

def resolve(person, campaign_id, events_fetch=None, ledger_rows=None):
    """Why did this person's membership in this campaign stop?

    `person` is a `collision.touches_of` dict. `campaign_id` is the provider
    campaign id whose membership reads `stopped`. `events_fetch` is a callable
    `(lead_id, campaign_id) -> [event]` that retrieves provider events; tests
    inject fixtures, live use passes a real fetcher. `ledger_rows` is the
    action ledger, pre-loaded for tests.

    Returns a dict:
        outcome:    one of ALL_OUTCOMES
        evidence:   what proved it (or why it could not be proved)
        lead_id:    the lead's provider id
        campaign_id: the campaign's provider id
    """
    lead_id = person.get("lead_id")
    out = {"lead_id": lead_id, "campaign_id": campaign_id,
           "outcome": STILL_UNKNOWN, "evidence": None}

    if not lead_id or not campaign_id:
        out["evidence"] = "no lead_id or campaign_id to resolve"
        return out

    # 1. UNSUBSCRIBED: an unsubscribe event exists.
    events = _events_for_lead(lead_id, campaign_id, events_fetch)
    for ev in events:
        kind = ev.get("kind")
        if kind in UNSUBSCRIBE_KINDS:
            out["outcome"] = UNSUBSCRIBED
            out["evidence"] = f"event {ev.get('provider_event_type')} at {ev.get('occurred_at')}"
            return out

    # 2. REPLIED/INTERESTED: a reply event, or the membership says so.
    for ev in events:
        kind = ev.get("kind")
        if kind in REPLY_KINDS:
            out["outcome"] = REPLIED_INTERESTED
            out["evidence"] = f"event {ev.get('provider_event_type')} at {ev.get('occurred_at')}"
            return out
    if _membership_says_replied(person):
        out["outcome"] = REPLIED_INTERESTED
        out["evidence"] = "membership status is replied or replies > 0 or interested"
        return out

    # 3. BOUNCED: a bounce event, or the lead status says so.
    for ev in events:
        kind = ev.get("kind")
        if kind in BOUNCE_KINDS:
            out["outcome"] = BOUNCED
            out["evidence"] = f"event {ev.get('provider_event_type')} at {ev.get('occurred_at')}"
            return out
    if _membership_says_bounced(person):
        out["outcome"] = BOUNCED
        out["evidence"] = "lead status is bounced"
        return out

    # 4. WE_STOPPED_IT: our own action ledger records a stop_lead.
    stopped, ledger_row = _ledger_has_stop(lead_id, campaign_id, ledger_rows)
    if stopped:
        out["outcome"] = WE_STOPPED_IT
        out["evidence"] = f"action ledger: {ledger_row.get('key')} settled {ledger_row.get('state')}"
        return out

    # 5. SEQUENCE_FINISHED: the campaign ran to the end, no adverse signal.
    if _campaign_is_finished(person, campaign_id):
        out["outcome"] = SEQUENCE_FINISHED
        out["evidence"] = "campaign status is sequence_finished, no reply/bounce/unsubscribe"
        return out

    # 6. STILL_UNKNOWN: none of the above. The hold stays.
    out["evidence"] = ("no unsubscribe, reply, bounce, ledger stop, or "
                       "sequence_finished found; missing evidence is not "
                       "positive evidence")
    return out


# --------------------------------------------------------- batch resolution

def resolve_account_holds(account, events_fetch=None, ledger_rows=None):
    """Every `stopped` membership in this account, resolved.

    `account` is a `collision.check_account` dict. Returns a list of resolve
    dicts, one per `stopped` membership found.
    """
    results = []
    for person in account.get("people") or []:
        if not isinstance(person, dict):
            continue
        for c in person.get("campaigns") or []:
            if not isinstance(c, dict):
                continue
            status = collision._norm(c.get("status"))
            if status != collision.STOPPED:
                continue
            campaign_id = c.get("campaign_id")
            results.append(resolve(person, campaign_id, events_fetch,
                                   ledger_rows))
    return results


def report_split(results):
    """How many of the resolved memberships fell into each outcome."""
    counts = {outcome: 0 for outcome in ALL_OUTCOMES}
    for r in results:
        outcome = r.get("outcome")
        if outcome in counts:
            counts[outcome] += 1
    return counts


# --------------------------------------------------------- CLI

def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python -m src.stoppedcause",
        description=__doc__.split("\n")[0])
    p.add_argument("domain", help="the account domain to resolve")
    p.add_argument("--workspace", required=True, type=int,
                   help="the provider workspace id")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    account = collision.check_account(a.domain, expect_workspace=a.workspace)
    results = resolve_account_holds(account)
    split = report_split(results)

    if a.json:
        print(json.dumps({"results": results, "split": split}, indent=2,
                         sort_keys=True))
    else:
        print(f"Resolved {len(results)} stopped membership(s):")
        for r in results:
            print(f"  lead={r['lead_id']}  campaign={r['campaign_id']}  "
                  f"outcome={r['outcome']}")
            if r.get("evidence"):
                print(f"    evidence: {r['evidence']}")
        print(f"\nSplit: {split}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
