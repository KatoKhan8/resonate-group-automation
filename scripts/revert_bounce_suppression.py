#!/usr/bin/env python3
"""Who the bounce rule closed - and the measurement that there is no way back.

TASK 0120, suppression lane, 2026-10-15. THIS SCRIPT WRITES NOTHING WITHOUT
`--apply`, AND WITH `--apply` THE STORE REFUSES IT. That is the finding, not
a bug in this file.

## The premise that did not survive

The task asked for "the reversal command verbatim, as 0100 did". 0100's
reversal took rows off `agency-dnc.jsonl`, which is a file with no such
guard. This mechanism does not write there: it closes an address by writing
`events.EMAIL_BOUNCED` on the record, and **an event cannot be removed from
a record by any sanctioned write path in this repository.**

Measured 2026-10-15, by running it:

    src.store.HistoryLost: this write would forget what happened or lift a
    stop nobody lifted: rec-1: 1 event(s) dropped: ev_302e8d176bd34479.
    Reload and re-apply rather than writing a stale snapshot back over it.

`store.refuse_history_loss` (`src/store.py:1400-1455`) runs inside
`store.transaction()` at line 339 and inside `store.save` at 1674 - both
sanctioned writers - and its own docstring says why there is no flag:

    "Strict, with no opt-out, because nothing in this repository clears any
    of these... If a deliberate lift is ever wanted, it should have to argue
    with this function rather than slip past it."

So the honest statement, and it belongs in the operator's decision rather
than buried in a script: **once the bounce rule closes an address, this
system has no mechanism to reopen it.** Rule 2 is therefore not a
convenience - for the 1.75% of addresses that have ever accepted mail from
us, the two survivable soft bounces are the only forgiveness that exists.

## The two ways to get one, and neither is this lane's to choose

  1. **A retraction event** - `EMAIL_BOUNCE_RETRACTED`, appended, that
     `channels._bounced` honours when it is newer than the bounce it names.
     Additive, auditable, and it does not fight the store. It is also an
     UN-SUPPRESSION PATH that `refuse_history_loss` cannot see, in a
     codebase whose whole suppression model rests on stops being one-way.
     That is an operator decision, not an implementation detail.
  2. **Widen the guard** to permit a removal that carries a named reason and
     an operator stamp - which is what its docstring invites ("argue with
     this function"). More work, and the guard stops being a flat rule.

RECOMMENDATION: 1, gated so only this script with `--apply` can write the
retraction, and only against events this mechanism itself wrote. But not
until the operator has said so, because an un-suppression path built by a
lane that was asked for a reversal command is exactly how a safety model
acquires a hole nobody voted for.

## What this script is for in the meantime

`--apply` is kept, and kept honest: it attempts the removal through
`store.transaction()`, the store refuses, and the refusal is printed with
the authority named. A command documented as working that has never been
run is how this project ends up with a reversal nobody can execute.

Without `--apply` it is the weekly report that `0090` and `0110` both
recommended beside a hard rule: every address the mechanism closed, which
campaign closed it and when. The event TYPE says which half of the rule did
it - `email_bounced` closed the address, `email_bounced_soft` only counted -
and the class is not re-stated beside it, because a second copy of a fact
the type already carries is free to disagree with it.

## What happens to someone suppressed by a bounce that later proves transient

  1. **The address is closed from the moment the event is written and
     nothing reopens it.** No decay, no expiry, no re-verification path.
     Per the above, not by hand either.
  2. **Only the EMAIL channel, and only that ADDRESS.** `channels._bounced`
     is keyed to the contact, so a colleague at the same company is
     untouched and LinkedIn is untouched. `nextaction` reports
     `contact:email_bounced`, and the remedy it already names is the one
     that is actually available: a new address for that person.
  3. **They are not on the agency DNC**, so nothing about them is
     person-level or permanent across channels, and no human decision has
     been recorded about them. The mechanism never writes to that list.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import channels, events, store                         # noqa: E402

KINDS = (events.EMAIL_BOUNCED, events.EMAIL_BOUNCED_SOFT)


def written_by_the_mechanism(entry):
    """Positively, never by absence.

    A bounce from the replies feed or a webhook comes through
    `adapters.from_emailbison` with a two-part `provider_event_id` of
    `emailbison:<uuid>` and no `scheduled_email_id`. It is a different fact
    with a different provenance, and a reversal that swept those up would
    reopen an address on evidence it never examined.
    """
    if entry.get("type") not in KINDS:
        return False
    if entry.get("provider") != "emailbison":
        return False
    if not entry.get("scheduled_email_id"):
        return False
    parts = str(entry.get("provider_event_id") or "").split(":")
    return len(parts) == 4 and parts[0] == "emailbison"


def matches(entry, campaign=None, contact=None, since=None):
    if campaign and str(entry.get("campaign_id") or "") != str(campaign):
        return False
    if contact and entry.get("contact") != contact:
        return False
    if since and str(entry.get("at") or "") < since:
        return False
    return True


def closed_addresses(recs):
    """The NAME-SET this is reported against: who is closed by a bounce.

    `(record id, contact key)` pairs, asked of `channels._bounced` itself
    rather than recomputed here - the question is what the SEND PATH thinks,
    and a second implementation of it could agree with this script and
    disagree with production.
    """
    out = set()
    for rec in recs:
        for contact in rec.get("contacts") or []:
            if channels._bounced(rec, contact):
                out.add((rec.get("id"), contact.get("key")))
    return out


def plan(recs, campaign=None, contact=None, since=None, record_id=None):
    """What a reversal would have to remove, and what it would leave."""
    targets, left_alone = [], []
    for rec in recs:
        if record_id and rec.get("id") != record_id:
            continue
        for entry in rec.get("events") or []:
            if entry.get("type") not in KINDS:
                continue
            if not written_by_the_mechanism(entry):
                left_alone.append({"rec_id": rec.get("id"),
                                   "id": entry.get("id"),
                                   "why": "not written by the bounce rule"})
                continue
            if not matches(entry, campaign, contact, since):
                continue
            targets.append({"rec_id": rec.get("id"), "entry": dict(entry)})
    return targets, left_alone


def attempt_removal(targets):
    """Try it through the sanctioned writer, and report what refused.

    Returns `(removed, refusal)`. `refusal` is the store's own message, not
    a paraphrase of it: the point of running this is to put the authority's
    own words in front of whoever asked for a reversal.
    """
    wanted = {}
    for target in targets:
        wanted.setdefault(target["rec_id"], set()).add(target["entry"]["id"])
    removed = 0
    try:
        with store.transaction() as rows:
            for rec in rows:
                ids = wanted.get(rec.get("id"))
                if not ids:
                    continue
                before = len(rec.get("events") or [])
                rec["events"] = [e for e in (rec.get("events") or [])
                                 if e.get("id") not in ids]
                removed += before - len(rec["events"])
    except store.HistoryLost as refused:
        return 0, str(refused)
    return removed, None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--campaign", help="only bounces from this campaign")
    p.add_argument("--contact", help="only this contact key")
    p.add_argument("--record", help="only this record id")
    p.add_argument("--since", help="only events at or after this ISO stamp")
    p.add_argument("--apply", action="store_true",
                   help="attempt the removal. The store refuses it; see the "
                        "module docstring")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = store.load()
    closed = closed_addresses(recs)
    targets, left_alone = plan(recs, a.campaign, a.contact, a.since, a.record)
    out = {"dry": not a.apply,
           "closed_by_a_bounce": sorted(f"{r}::{c}" for r, c in closed),
           "would_remove": len(targets),
           "left_alone_other_provenance": len(left_alone),
           "events": [{"rec_id": t["rec_id"], "id": t["entry"].get("id"),
                       "type": t["entry"].get("type"),
                       "at": t["entry"].get("at"),
                       "campaign_id": t["entry"].get("campaign_id")}
                      for t in targets]}

    status = 0
    if a.apply:
        removed, refusal = attempt_removal(targets)
        out["removed"] = removed
        out["refused_by"] = refusal
        if refusal:
            out["authority"] = ("store.refuse_history_loss, src/store.py:"
                                "1400-1455, no opt-out. There is no reversal "
                                "for a recorded bounce in this system today; "
                                "see the module docstring for the two ways "
                                "to get one and who decides")
            status = 1

    if a.json:
        print(json.dumps(out, indent=1))
    else:
        for key, value in out.items():
            if key == "events":
                for event in value:
                    print(f"   {event['rec_id']} {event['type']} "
                          f"{event['at']} campaign={event['campaign_id']}")
            else:
                print(f"{key}: {value}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
