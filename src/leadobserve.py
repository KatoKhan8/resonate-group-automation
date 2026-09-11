#!/usr/bin/env python3
"""What the provider did to a staged lead, recorded when it changes.

## Why this exists

Nothing in this system could record that a LinkedIn invitation went out.
`touch.CONFIRMING_EVENTS` is writable only by a send path that raises or by a
webhook HeyReach does not expose, so a canary's first touch was unrecordable by
construction - the funnel would report zero confirmed actions for ever while a
real person sat in a live campaign.

`heyreach.campaign_leads` answers it per lead. This is the durable half: read
provider truth, compare it to the last thing recorded, and append a row ONLY
when the state actually moved.

## Rules

**A transition is provider truth or it does not exist.** Nothing here derives a
state from elapsed time, from campaign status, or from a counter.
`progressStats` is never consulted: it is a residual that counts a lead which
has done nothing and goes negative on live campaigns.

**Campaign ACTIVE is not a send.** The canary campaign moved to `IN_PROGRESS`
the moment an operator unpaused it, while its one lead still read
`Pending / None / lastActionTime null`. Anything that treated the campaign
status as the action would have reported a message nobody received.

**Exactly once.** A row is appended only when `state` differs from the last row
for that lead, so polling every minute for a week leaves one row per real
change. That is what makes "transition the logical action to OBSERVING exactly
once" enforceable rather than aspirational.

**UNKNOWN is recorded, not resolved.** An unrecognised provider value becomes
`heyreach.LIFECYCLE_UNKNOWN` upstream and is stored with the raw words beside
it, so a vocabulary change shows up as a row a person can read rather than as a
silently neighbouring state.

## What it is not

It is not the action ledger. The ledger records what THIS SYSTEM did and is the
authority on duplicate suppression; this records what the PROVIDER did, which
for a hand-staged canary is the only record there is. They are reconciled by
`reconcile()`, which states plainly when one has a row the other does not -
today that is the normal case, because the canary was staged by a person in the
vendor UI and no reservation was ever written.
"""
import argparse
import json
import os
import sys

from . import events, linkedin, store
from .providers import heyreach

# Every observation, append-only, beside the queue - the same argument the
# spend ledger makes: the records and what happened to them move together.
FILE = "lead-observations.jsonl"


def path():
    return os.path.abspath(os.environ.get("LEAD_OBSERVATIONS")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           FILE))


def load():
    try:
        return store.read_jsonl(path())
    except FileNotFoundError:
        return []


def last_for(campaign_id, lead_id, rows=None):
    """The most recent recorded state for one lead, or None."""
    found = None
    for row in (load() if rows is None else rows):
        if (str(row.get("campaign_id")) == str(campaign_id)
                and str(row.get("provider_lead_id")) == str(lead_id)):
            found = row
    return found


def observe(campaign_id, now=None):
    """Read the provider and append a row for every lead that moved.

    Returns the rows appended, which is empty on a quiet poll - and an empty
    list is the ordinary answer. A poller that wrote something every tick would
    make a week of nothing look like a week of activity.
    """
    leads, total = heyreach.campaign_leads(campaign_id)
    stats = heyreach.campaign_stats(campaign_id)
    campaign = heyreach.campaign_by_id(campaign_id) or {}
    rows = load()
    appended = []
    for lead in leads:
        previous = last_for(campaign_id, lead.get("provider_lead_id"), rows)
        if previous is not None and previous.get("state") == lead.get("state"):
            continue
        appended.append({
            "at": now or store.now(),
            "campaign_id": str(campaign_id),
            "campaign_status": campaign.get("status"),
            "provider_lead_id": lead.get("provider_lead_id"),
            "provider_profile_id": lead.get("provider_profile_id"),
            "sender_id": lead.get("sender_id"),
            "state": lead.get("state"),
            "was": (previous or {}).get("state"),
            # The provider's own words and its own timestamp. `at` above is
            # when this system looked; `provider_at` is when the provider says
            # it happened, and conflating them would date every action to
            # whenever a poll happened to run.
            "provider_at": lead.get("at"),
            "raw": lead.get("raw"),
            "error_code": lead.get("error_code"),
            "why": lead.get("why"),
            "lead_count": total,
            "campaign_stats": stats,
        })
    if appended:
        with store.file_transaction(path()) as existing:
            existing.extend(appended)
    return appended


def history(campaign_id=None):
    rows = load()
    if campaign_id is None:
        return rows
    return [r for r in rows if str(r.get("campaign_id")) == str(campaign_id)]


def reached(campaign_id):
    """Leads the provider says have actually been contacted.

    `heyreach.REACHED` deliberately excludes FAILED: a failed lead may already
    have been accepted, and 28 of 851 sampled leads were exactly that.
    """
    seen = {}
    for row in history(campaign_id):
        seen[row.get("provider_lead_id")] = row.get("state")
    return {lead for lead, state in seen.items() if state in heyreach.REACHED}


class Ambiguous(RuntimeError):
    """One provider lead matched more than one contact. Nobody may guess."""


def match_lead(lead, recs):
    """(record, contact) for the human this provider lead is, or None.

    Matched on `linkedin.canonical`, because it is the only identifier that
    survives the round trip: HeyReach returns `customFields: []` on every
    conversation, so the record id and contact key this system sends are
    write-only decoration and cannot be read back.

    Refuses to guess. Two contacts behind one profile raises rather than
    picking the first - a wrong person is the one outcome this whole module
    exists to prevent, and "probably them" is how that happens.
    """
    key = linkedin.key(lead.get("profile_url"))
    if not key:
        return None
    found = [(rec, contact)
             for rec in recs
             for contact in (rec.get("contacts") or [])
             if contact.get("linkedin")
             and linkedin.key(contact["linkedin"]) == key]
    if len(found) > 1:
        raise Ambiguous(
            f"provider lead {lead.get('provider_lead_id')!r} matches "
            f"{len(found)} contacts: "
            + ", ".join(f"{r.get('id')}/{c.get('key')}" for r, c in found)
            + ". Reconcile the duplicate before recording a touch")
    return found[0] if found else None


def _linkedin_step(rec, contact_key):
    """The one LinkedIn step this contact has, or None if it is not one.

    Only used to date the touch onto a cadence day so
    `eligibility._separation` can see it. When it cannot be determined the
    touch is still recorded - a touch nobody can place on a day is worth far
    more than no touch at all, and `fatigue` reads the event either way.
    """
    steps = ((rec.get("cadence") or {}).get(contact_key) or {})
    linkedin_steps = [(key, step) for key, step in steps.items()
                      if (step or {}).get("channel") == "linkedin"]
    return linkedin_steps[0] if len(linkedin_steps) == 1 else (None, {})


def confirm_touches(campaign_id, recs=None, live=False):
    """Record the canonical confirmed touch for a lead the PROVIDER reached.

    THE OTHER HALF OF THE DUPLICATION LAW. `providerwrites.perform` records a
    touch when THIS system writes to the provider. The canary is the opposite
    case: an operator staged the lead and unpaused the campaign by hand, so
    `eligibility` answers `blocked:campaign_already_launched` and HeyReach
    sends the connection request on its own schedule. Resonate OS is not the
    executor there - it can only observe.

    Without this, the moment that invitation goes out the provider knows and
    nothing here does: `funnel` reports zero confirmed actions for ever,
    `touch` sees nothing, and the duplication law has no touch to refuse a
    second action against. That is this repository's named recurring defect -
    a thing computed correctly that nothing downstream reads - sitting on the
    single most safety-relevant fact the provider publishes.

    Idempotent by construction. The event carries a `provider_event_id` of
    (provider, campaign, lead, state), and `events.record` returns None for a
    duplicate, so polling every minute for a week records one touch per real
    transition. The provider's OWN timestamp dates the event, never now(): a
    reconciliation run days later must not claim the invitation went out
    today.

    Dry by default. `live=True` writes.
    """
    recs = store.load() if recs is None else recs
    leads, _total = heyreach.campaign_leads(campaign_id)
    recorded, unmatched, already = [], [], []
    for lead in leads:
        if lead.get("state") not in heyreach.REACHED:
            continue
        found = match_lead(lead, recs)
        if found is None:
            # Reported, never guessed. A lead the provider reached that this
            # system cannot place is a reconciliation question for a person.
            unmatched.append(lead.get("provider_lead_id"))
            continue
        rec, contact = found
        step_key, step = _linkedin_step(rec, contact.get("key"))
        entry = {
            "rec_id": rec.get("id"), "contact_key": contact.get("key"),
            "provider_lead_id": lead.get("provider_lead_id"),
            "state": lead.get("state"), "at": lead.get("at"),
            "step": step_key,
        }
        (recorded if live else already).append(entry)
        if not live:
            continue
        with store.transaction() as rows:
            live_rec = store.get(rec.get("id"), rows)
            if live_rec is None:
                continue
            written = events.record(
                live_rec, events.PUSH_MARKED,
                contact_key=contact.get("key"), channel="linkedin",
                at=lead.get("at") or store.now(),
                provider="heyreach",
                provider_event_id=(f"heyreach:{campaign_id}:"
                                   f"{lead.get('provider_lead_id')}:"
                                   f"{lead.get('state')}"),
                step=step_key, day=(step or {}).get("day"),
                sender_id=lead.get("sender_id"),
                campaign_id=str(campaign_id))
            if written is None:
                recorded.pop()
                already.append(entry)
    return {"live": live, "recorded": recorded, "already": already,
            "unmatched": unmatched}


def reconcile(campaign_id):
    """What the provider did, beside what this system recorded doing.

    For a hand-staged canary the honest answer is that the ledger is empty and
    the provider acted anyway, because a person staged the lead in the vendor
    UI. That is a difference worth stating rather than smoothing over: it is
    the reason `funnel.provider_staged` reads 0 while a real prospect sits in a
    live campaign.
    """
    from . import actionledger

    ledger = {row.get("key") for row in actionledger.load()
              if str(row.get("campaign_id")) == str(campaign_id)}
    seen = reached(campaign_id)
    rows = history(campaign_id)
    if not rows:
        note = "nothing observed yet; this campaign has never been read"
    elif seen and not ledger:
        note = ("the provider has acted on leads this system never reserved: "
                "the campaign was staged by hand in the vendor UI, so there is "
                "no ledger row to reconcile against")
    elif seen and ledger:
        note = "both sides have rows; compare them lead by lead"
    else:
        note = ("observed, and the provider has not contacted anybody yet. "
                "The leads are enrolled and waiting on the provider's own "
                "schedule")
    return {"campaign_id": str(campaign_id),
            "provider_reached": sorted(str(x) for x in seen),
            "ledger_keys": sorted(ledger),
            "observations": len(rows),
            "note": note}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.leadobserve",
                                description=__doc__)
    p.add_argument("--campaign", required=True, help="provider campaign id")
    p.add_argument("--json", action="store_true")
    p.add_argument("--history", action="store_true",
                   help="print what has been recorded, without reading the "
                        "provider")
    p.add_argument("--confirm", action="store_true",
                   help="record a canonical confirmed touch for every lead "
                        "the provider has reached. Dry unless --live")
    p.add_argument("--live", action="store_true",
                   help="with --confirm, actually write the touches")
    a = p.parse_args(argv)

    if a.confirm:
        out = confirm_touches(a.campaign, live=a.live)
        if a.json:
            print(json.dumps(out, indent=1))
            return 0
        print(f"campaign {a.campaign}: "
              f"{len(out['recorded'])} touch(es) recorded, "
              f"{len(out['already'])} already known, "
              f"{len(out['unmatched'])} unmatched"
              + ("" if out["live"] else "   (DRY - pass --live to write)"))
        for lead_id in out["unmatched"]:
            print(f"  UNMATCHED lead {lead_id}: the provider reached somebody "
                  f"this system cannot place. Reconcile by hand.")
        return 0

    if a.history:
        rows = history(a.campaign)
    else:
        rows = observe(a.campaign)
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    if not rows:
        print(f"campaign {a.campaign}: no change since the last observation")
        return 0
    for row in rows:
        print(f"{row['at']}  lead {row['provider_lead_id']}  "
              f"{row.get('was') or '-'} -> {row['state']}"
              + (f"  ({row['error_code']})" if row.get("error_code") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
