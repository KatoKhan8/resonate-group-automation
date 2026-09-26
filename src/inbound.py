#!/usr/bin/env python3
"""Everything that arrives from outside, on one path.

An email reply from EmailBison, a LinkedIn reply from HeyReach and a reply typed
in by hand are three different payloads describing the same thing: a human
answered. They are normalised to one neutral event, applied once, and then
walked through the same four steps in the same order, every time:

    1. apply the event      (idempotent on the provider's own event id)
    2. classify the reply   (conservatively, and never to resume anything)
    3. pause the account    (conditional on the classification)
    4. notify a human       (best effort, and allowed to fail)

The order is the whole design. The reply is applied (step 1), then classified
(step 2), and ONLY THEN is the pause decided (step 3). The pause is
conditional on the classification: an UNKNOWN reply still pauses (fail-safe),
a human "not interested" pauses, but a pure out-of-office does not. Only a
positively identified machine reply may skip the pause.

  python -m src.inbound apply --provider emailbison --file payload.json
  python -m src.inbound show
"""
import argparse
import contextlib
import datetime
import json
import os
import sys

from . import (accountpolicy, actionledger, adapters, campaigns, clients,
               events, leadstop,
               providers,
               notify, ooo,
               observability, orchestrator, replies, store)


# TASK-238: The only LinkedIn seat we operate and the campaigns on it.
# An event on a seat NOT in this set is provably not ours and the unmatched
# notification is suppressed. An event on THIS seat with no record match is
# kept - it might be ours and absence of evidence is never proof.
# Source: docs/state/PROVIDER-CAMPAIGNS.json (2026-09-20 readback).
#
# 2026-09-23: THESE TWO LITERALS WENT STALE AND NOTHING REPORTED IT.
#
# They were read back on 2026-09-20, when the account held 86 campaigns and 4
# were ours. On 2026-09-23 the provider says 119 and 37: the 33 "RESONATE
# PRODUCTIVE LI B1 SEAT <n>" campaigns (613724-613761) run on 33 DISTINCT
# seats, none of them 174892 and none of them in the set below. So the first
# unattributable reply to one of our own B1 campaigns would be dropped here as
# "positively not ours" and nobody would be told.
#
# It has not fired yet - 75 connection requests, 3 accepted, 0 replies - which
# is luck, not a design. This is the register's own recurring shape: a value
# that was true when it was written, cached where nothing could notice it had
# gone stale. The structural answer it prescribes is that such a value carries
# the date and source it came from and REFUSES rather than answers when it
# cannot prove it is current. That is what `_owned()` below does.
OWNED_SEATS = {174892}
OWNED_CAMPAIGNS = {605732, 605487, 604869, 599020}

#: How old the readback may be before it stops licensing a drop. A campaign
#: can be created and started inside an hour, so this is short on purpose.
OWNERSHIP_MAX_AGE_HOURS = 24

#: The ONLY provider routes the reply path may write to. Fragments, matched
#: case-insensitively against the URL, so a host change cannot void them.
#:
#: A reply stops a lead. It does not enrol, pause, resume, create, attach or
#: set a schedule, and `allow_writes(only=STOP_ROUTES)` is what makes that a
#: property of the code rather than a claim about it.
STOP_ROUTES = (
    "stop-future-emails",     # EmailBison /campaigns/{id}/leads/stop-future-emails
    "stopleadincampaign",     # HeyReach  /campaign/StopLeadInCampaign
)

_OWNERSHIP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "state", "PROVIDER-CAMPAIGNS.json")


def _readback(path=None, now=None):
    """Seats and campaigns the PROVIDER says are ours, with its own age.

    Returns `(seats, campaigns, fresh, why)`. `fresh` is False whenever the
    file is missing, unreadable, undated or older than
    `OWNERSHIP_MAX_AGE_HOURS` - and `why` says which, because "we could not
    prove ownership" and "this is not ours" must never print the same.
    """
    path = path or _OWNERSHIP_FILE
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        return set(), set(), False, f"readback unreadable: {exc}"

    block = (data or {}).get("heyreach") or {}
    seats, camps = set(), set()
    for row in block.get("resonate_campaigns") or []:
        cid = row.get("heyreach_campaign_id")
        if cid is not None:
            with contextlib.suppress(TypeError, ValueError):
                camps.add(int(cid))
        for sender in row.get("senders") or []:
            sid = sender.get("id")
            if sid is not None:
                with contextlib.suppress(TypeError, ValueError):
                    seats.add(int(sid))

    stamp = (data or {}).get("generated_at")
    if not stamp:
        return seats, camps, False, "readback carries no generated_at"
    try:
        at = datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return seats, camps, False, f"unparseable generated_at: {stamp!r}"
    if at.tzinfo is None:
        at = at.replace(tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    age = (now - at).total_seconds() / 3600.0
    if age > OWNERSHIP_MAX_AGE_HOURS:
        return seats, camps, False, (
            f"readback is {age:.0f}h old (limit {OWNERSHIP_MAX_AGE_HOURS}h); "
            f"run scripts/provider_truth.py")
    return seats, camps, True, None


def _owned(path=None, now=None):
    """The sets a drop may be decided against, or `None` meaning REFUSE.

    The literals above are a FLOOR, never a ceiling: they are unioned in so a
    readback that has lost a campaign cannot make us disown one we know about.
    """
    seats, camps, fresh, why = _readback(path=path, now=now)
    if not fresh:
        return None, why
    return (seats | OWNED_SEATS, camps | OWNED_CAMPAIGNS), None


def _positively_not_ours(event):
    """Can we PROVE this event belongs to another operator?

    TASK-238. The HeyReach API key is workspace-wide and the inbox watcher
    sees the CLIENT'S traffic too. An event on a seat we do not operate is
    provably not ours. An event with no seat field, or on our seat, is kept
    regardless - absence of evidence is never a drop.

    Returns True ONLY when at least one field positively places this event
    on a seat or campaign that is not ours. Returns False for every other
    case: no field, our seat, our campaign, or an unknown value.

    2026-09-23: and False whenever the ownership readback cannot be PROVEN
    CURRENT. A stale allowlist cannot distinguish "another operator's seat"
    from "a seat of ours created since the readback", and on 2026-09-23 it
    held one seat against 33 live ones. Refusing to drop costs a notification
    nobody needed; dropping wrongly costs a reply nobody saw.
    """
    owned, _why = _owned()
    if owned is None:
        return False
    owned_seats, owned_campaigns = owned

    seat = event.get("linkedin_account_id")
    if seat is not None:
        try:
            if int(seat) not in owned_seats:
                return True
        except (TypeError, ValueError):
            pass
    cid = event.get("external_campaign_id")
    if cid is not None:
        try:
            if int(cid) not in owned_campaigns:
                return True
        except (TypeError, ValueError):
            pass
    return False


def _contact_of(rec, contact_key):
    """`events.apply` reports the contact KEY. The stop needs the contact."""
    for contact in (rec or {}).get("contacts") or []:
        if contact.get("key") == contact_key:
            return contact
    return None


def _stop_at_provider(rec, contact, rows=None):
    """Tell the provider this person stops, if we can name them there.

    Never raises. An inbound event that fails here must still be applied,
    classified and notified - losing the reply because the stop failed would
    trade a queued email for a lost one, and the queued email is the thing a
    person can still be told about.

    What it returns is the audit trail: a dict keyed by channel (`email`,
    `linkedin`), each entry carrying `attempted`, `stopped` and - when it
    could not be done - the reason. `summarise_stops` turns it into the line
    a watcher prints.
    """
    # PER CHANNEL, AND "NOT ATTEMPTED" IS AN OUTCOME.
    #
    # OPERATOR DECISION 2026-09-23. `reply_watch_loop` printed "the lead is
    # stopped on both channels" unconditionally, so a lead that was never
    # stopped reported as stopped - twice, on the safety path. The line is now
    # built from this return value, so it can only say what happened.
    #
    # It returns one entry per channel rather than a single verdict, because
    # the three outcomes a caller has to tell apart are:
    #
    #     stopped       the provider confirmed it on readback
    #     refused       we tried and could not - somebody may still be written
    #                   to, and this is the one that raises an alert
    #     no lead here  this contact was never staged on that channel, which
    #                   is not a failure and must not read as one
    #
    # BOTH CHANNELS ARE NOW ATTEMPTED. Only the EmailBison half was ever
    # called from here, while `STOP_ROUTES` above has authorised the HeyReach
    # route the whole time and `leadstop.sweep` has stopped both channels
    # since TASK-235. So the guarantee in ACCOUNT-OUTREACH.md - a confirmed
    # reply stops that lead on BOTH channels - was true of the sweep and not
    # of the live reply path, which is the path that matters. A reply
    # arriving on LinkedIn has to stop the email sequence and vice versa, and
    # the operator's 2026-09-23 test is exactly the case that was broken.
    out = {}
    for channel, binding, stopper in (
            ("email", "bison_lead_id", leadstop.stop_contact),
            ("linkedin", "heyreach_lead_id", leadstop.stop_linkedin_contact)):
        if not contact or not (contact or {}).get(binding):
            out[channel] = {"attempted": False, "stopped": False,
                            "why": f"this contact carries no {binding}, so "
                                   f"there is nobody to stop on {channel}"}
            continue
        out[channel] = _stop_one(rec, contact, rows, channel, stopper)
    return out


#: Channel order in every summary line, so two reads of the same event are
#: comparable by eye.
STOP_CHANNELS = ("email", "linkedin")


def summarise_stops(outcomes):
    """One line saying what the stops actually did, and whether any refused.

    Returns `(line, refusals)`. `refusals` is the list a caller alerts on -
    a stop that was REFUSED means somebody may still be written to after they
    answered, which is the only outcome here worth waking anybody for.

    "no lead on that channel" is reported and is NOT a refusal. Most contacts
    are staged on one channel only, and an alert on every single-channel
    contact is an alert nobody reads by the end of the week.
    """
    parts, refusals = [], []
    for outcome in outcomes or []:
        stops = (outcome or {}).get("provider_stop") or {}
        if not isinstance(stops, dict):
            continue
        for channel in STOP_CHANNELS:
            entry = stops.get(channel)
            if not isinstance(entry, dict):
                continue
            if not entry.get("attempted"):
                parts.append(f"{channel}: no lead")
            elif entry.get("already"):
                parts.append(f"{channel}: already stopped")
            elif entry.get("stopped"):
                parts.append(f"{channel}: stopped")
            else:
                reason = entry.get("why") or entry.get("error") or "unknown"
                parts.append(f"{channel}: REFUSED ({str(reason)[:120]})")
                refusals.append({"channel": channel,
                                 "record": ((outcome or {}).get("applied")
                                            or {}).get("record_id"),
                                 "why": str(reason)[:300]})
    return ("; ".join(parts) if parts else "no provider binding to stop"), \
        refusals


def _stop_one(rec, contact, rows, channel, stopper):
    """One channel's stop attempt, never raising. See `_stop_at_provider`."""
    try:
        # THE SCOPE THAT WAS MISSING, 2026-09-23.
        #
        # `reply_watch_loop` opts into no write scope. It sets
        # REPLY_POLL_ENABLED and nothing else, so every stop this function
        # attempted was refused by `refuse_unauthorized_write` and caught
        # below as an error nobody read. Megan Ward replied "no thank you" on
        # LinkedIn at 11:12:33Z; the stop was refused at 11:19:35Z and she
        # stayed `in_sequence` in EmailBison 491 for 2h07m.
        #
        # It hid because EmailBison marks a lead `replied` by itself when the
        # reply arrives BY EMAIL. Four of five locally-stopped contacts read
        # `replied` at the provider for that reason alone. The cross-channel
        # case - a LinkedIn reply stopping an email sequence - is the only
        # one that depends on this call, and it is the one that was broken.
        #
        # `only=STOP_ROUTES` and not a bare scope: this path may stop a lead
        # and may do nothing else. A future refactor that adds a pause, a
        # resume or an enrolment here is refused rather than silently
        # authorised, which is the whole point of the guard the 487 incident
        # bought.
        #
        # `persist=False`: INGEST OWNS THE SAVE. See PROBLEM-REGISTER
        # ISSUE-001 and `leadstop._record`. This call sits between
        # `base = store.digest()` and `store.save(recs, expect_digest=base)`,
        # so a nested transaction in the stop recorder changes the file, the
        # outer save refuses with QueueChanged, and THIS ingest's own work -
        # the REPLY_RECEIVED event, its classification, the account pause -
        # is discarded. The stop event is written onto the in-memory record
        # instead and rides ingest's single save, like everything else here.
        with providers.allow_writes(
                "reply received: stop this lead on the other channel "
                "(ACCOUNT-OUTREACH.md). Scoped to stop routes only.",
                only=STOP_ROUTES):
            report = stopper(rec, contact, events.REPLY_RECEIVED,
                             rows=rows, live=True, persist=False)
        return {"attempted": True, "stopped": bool(report.get("stopped")),
                "already": bool(report.get("already")),
                "status_after": report.get("status_after"),
                "campaign": report.get("campaign"),
                "lead_id": report.get("lead_id")}
    except Exception as e:
        # Explicitly classified, never swallowed: an unstopped person is the
        # thing somebody has to go and look at.
        return {"attempted": True, "stopped": False,
                "error": type(e).__name__, "why": str(e)[:200]}


def _campaign_for(rec, rows=None):
    """The campaign a record belongs to, if any. A reply is still handled for
    a record in no campaign - it just has less to say in the alert."""
    rows = campaigns.load() if rows is None else rows
    for campaign in rows:
        if rec.get("id") in (campaign.get("record_ids") or []):
            return campaign
    return None


def _text_of(event):
    for field in ("text", "body", "message", "reply", "snippet", "content"):
        value = event.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _is_pure_ooo(verdict, event):
    """A machine-generated out-of-office with no human sentence.

    TASK-030: the only case where the account pause is lifted after
    `replies.apply` has applied it. Both conditions must hold: the reply
    must be classified as out_of_office AND the absence must be
    machine-generated (either by provider flag or by machine-only phrasing
    in the text). A human writing about their own absence is NOT a pure
    OOO, and an out-of-office that also contains a human sentence is
    caught by `ooo.detect` returning HUMAN_ABSENCE rather than
    AUTORESPONDER.
    """
    cls = (verdict.get("verdict") or {}).get("classification")
    if cls != replies.OUT_OF_OFFICE:
        return False
    reading = ooo.detect(_text_of(event), automated=event.get("automated"))
    return reading["is_absence"] and reading["kind"] == ooo.AUTORESPONDER


# TASK-349: which inbound event types are provider-confirmed facts the ledger
# must record. A send the provider observed and a reply that arrived are both
# written back. Everything else (bounces, connection acceptances, unknown) is
# not a send or reply and is left to the record's own event log.
_LEDGER_KINDS = {
    events.EMAIL_DELIVERED: actionledger.PROVIDER_SENT,
    events.REPLY_RECEIVED: actionledger.PROVIDER_REPLIED,
}


def _write_back_to_ledger(event, applied, rec):
    """Record a provider-confirmed send or reply in the action ledger.

    Returns the ledger row on first write, None on a replay or for event types
    that are not sends or replies. Never raises: a ledger write failure must
    not stop the reply path (classification, pause, notification).
    """
    event_type = (applied.get("event") or {}).get("type")
    kind = _LEDGER_KINDS.get(event_type)
    if kind is None:
        return None
    provider_event_id = event.get("provider_event_id")
    if not provider_event_id:
        return None
    try:
        return actionledger.record_provider_event(
            provider_event_id,
            kind=kind,
            provider=event.get("provider"),
            channel=event.get("channel"),
            campaign_id=event.get("external_campaign_id"),
            contact_key=applied.get("contact"),
            rec_id=applied.get("record_id"),
            workspace=rec.get("client"),
            provider_timestamp=event.get("at"),
        )
    except Exception:                                       # noqa: BLE001
        return None


def handle(event, recs, rows=None, config=None, post=None, model=None):
    """One inbound event, start to finish. Returns what happened at each step."""
    outcome = {"event": event, "applied": None, "paused": False,
               "classification": None, "notification": None,
               "provider_stop": None}

    applied = events.apply(recs, event)
    outcome["applied"] = applied
    # Counted, not stored: an event naming a record it does not belong to must
    # not be able to write to that record's log merely by naming it.
    observability.count({
        "applied": events.EVENT_INGESTED,
        "duplicate": events.EVENT_DUPLICATE,
    }.get(applied["status"], events.EVENT_UNKNOWN),
        provider=event.get("provider"), status=applied["status"],
        reason=applied.get("why"))
    if applied["status"] in ("unmatched", "unknown"):
        # AN UNATTRIBUTABLE REPLY STILL STOPS THE CADENCE TO THAT PERSON.
        #
        # `events.match_record` refuses to guess which record a reply answers
        # when the same person is on more than one, and that refusal is right:
        # attributing it wrongly pauses the wrong company. But nothing else
        # happened either. Reproduced: "please stop, we are not interested"
        # from an address held on two records left BOTH unpaused, with
        # `eligibility.decide` answering `eligible` on both - while the
        # identical reply to a person on one record paused correctly. Being
        # known twice made the person less safe.
        #
        # So the stop is applied to every record carrying them and the
        # attribution is still not made: no reply event, no classification,
        # no claim that any of these records received anything. A hold is
        # reversible by the person who reads the reply. A send is not.
        held = []
        if events.is_reply(event):
            for candidate, contact in events.correspondents(recs, event):
                if accountpolicy.hold_for_unattributed_reply(
                        candidate, contact, at=event.get("at")):
                    held.append((candidate.get("id"), contact.get("key")))
        outcome["held_unattributed"] = held
        # TASK-238: An event on a seat or campaign that is NOT ours is
        # dropped - no notification raised. The hold above is NOT skipped:
        # an unattributable reply still stops the cadence to that person
        # even when the event is the client's, because correspondents finds
        # no records of ours and the hold is a no-op by itself.
        #
        # An event with no seat/campaign field, or on OUR seat, keeps the
        # notification. Absence of evidence is never a drop.
        if _positively_not_ours(event):
            outcome["notification"] = {
                "dropped": True,
                "reason": "positively_not_ours",
                "provider": event.get("provider"),
                "seat": event.get("linkedin_account_id"),
                "campaign": event.get("external_campaign_id"),
            }
        else:
            outcome["notification"] = notify.notify(
                notify.UNMATCHED_REPLY, None,
                fields={"provider": event.get("provider"),
                        "status": applied["status"],
                        "why": applied.get("why"),
                        "held": len(held),
                        "action": "a person decides; nothing is auto-attributed"},
                ids={"provider_event_id": event.get("provider_event_id")})
    if applied["status"] != "applied":
        return outcome                      # duplicate, unmatched or unknown

    rec = next((r for r in recs if r["id"] == applied["record_id"]), None)
    if rec is None:
        return outcome
    outcome["paused"] = bool(rec.get("paused"))

    # TASK-349: write the provider-confirmed fact to the action ledger.
    # A send that happened and a reply that arrived are facts about production,
    # and the ledger is what answers "who did this, and when". The write-back
    # fires for every applied event that is a send or a reply, before the
    # reply-specific logic below. It is idempotent on the provider event id,
    # so a replayed webhook writes nothing.
    outcome["ledger"] = _write_back_to_ledger(event, applied, rec)

    if not events.is_reply(applied.get("event") or {}):
        return outcome                      # delivered, bounced, connected

    if config is None:
        try:
            config = clients.load(rec.get("client"))
        except Exception:
            config = {}

    # THE PROVIDER STOP IS INDEPENDENT OF CLASSIFICATION.
    #
    # The provider keeps its own scheduler and its own queue. Whether the
    # reply was positive, negative or an out-of-office does not change that
    # they should stop receiving the sequence. This tells the provider, and
    # it is attempted BEFORE classification because the stop is a safety
    # REDUCTION - it can only ever mean somebody receives less.
    #
    # It is not gated behind --live the way a send is. A contact with no
    # provider binding is a no-op, which is every record staged before this
    # existed.
    outcome["provider_stop"] = _stop_at_provider(
        rec, _contact_of(rec, applied.get("contact")), rows)

    # TASK-030 rework: save the pause state BEFORE `replies.apply`.
    # `replies.apply` calls `accountpolicy.apply_reply` for all non-automated
    # replies, which may pause the account. For a pure out-of-office, the
    # account must NOT be paused - only the contact is deferred. We save
    # the state so we can undo the account-level pause for pure OOO while
    # keeping the contact-level state that `replies.apply` recorded.
    _pre_pause = rec.get("paused")

    verdict = replies.apply(
        rec, applied.get("contact"), _text_of(event),
        at=event.get("at"), model=model, channel=event.get("channel"),
        provider=event.get("provider"),
        provider_event_id=event.get("provider_event_id"),
        automated=event.get("automated"))
    outcome["classification"] = verdict["verdict"]

    # TASK-030: The pause is conditional on the classification.
    #
    # `replies.apply` called `accountpolicy.apply_reply` for all non-automated
    # replies, which may have paused the account. For a pure out-of-office
    # (machine-generated, no human sentence), the account pause is lifted
    # here. The contact-level deferral from `apply_reply` is kept. The
    # restore is logged: an account that is not paused with nothing in the
    # log saying why is indistinguishable from one nobody ever paused.
    #
    # For everything else, the fail-safe ensures the account is paused:
    # an UNKNOWN reply, a human "not interested", an OOO with a human
    # sentence, an automated referral - all pause.
    if _is_pure_ooo(verdict, event):
        # Pure OOO: the account must NOT be paused. `apply_reply` maps
        # OOO to NOT_NOW which is CONTINUE at ACCOUNT scope, so the
        # account is usually not paused. But if a pre-existing pause was
        # present, it is preserved. If `apply_reply` or a policy change
        # were to pause the account, we undo it here and log why.
        if rec.get("paused") and not _pre_pause:
            rec["paused"] = _pre_pause
        store.log(rec, "pause_restored",
                  "pure out-of-office: account not paused; "
                  "contact deferred for oooreturn follow-up")
    elif not rec.get("paused"):
        # Fail-safe: any reply that is not a pure OOO pauses the account.
        # `replies.apply` may have already paused it (for UNKNOWN, POSITIVE,
        # OOO+human through NOT_NOW -> HOLD at ACCOUNT scope), but for
        # NEGATIVE and UNSUBSCRIBE the policy is at CONTACT scope, so the
        # account is not paused. We pause it here to preserve the fail-safe.
        # An automated reply that is not a pure OOO (e.g. a referral) also
        # pauses here, because `replies.apply` skipped `apply_reply` for it.
        accountpolicy._hold_account(
            rec, applied.get("contact"),
            (verdict.get("verdict") or {}).get("classification", "unknown"),
            event.get("at"), channel=event.get("channel"),
            reason=event.get("type"))

    outcome["paused"] = bool(rec.get("paused"))

    # What follows can fail freely.
    if replies.is_positive(verdict["verdict"]):
        campaign = _campaign_for(rec, rows)
        notice = orchestrator.positive_reply_notification(
            rec, applied.get("contact"),
            {**verdict["verdict"], "channel": event.get("channel")},
            config, campaign=campaign, source=event.get("provider"), post=post)
        outcome["notification"] = notice
        # Whatever Slack did, the company is still paused.
        outcome["paused"] = bool(rec.get("paused"))
    return outcome


def ingest(payloads, provider, recs=None, rows=None, config=None, post=None,
           model=None, provider_workspace=None):
    """A provider payload in, a list of outcomes out. Saves once, at the end."""
    adapter = adapters.ADAPTERS.get(provider)
    if adapter is None:
        raise ValueError(f"no adapter for provider {provider!r}")
    own = recs is None
    # The digest of the queue as it was read. `handle` does network I/O - a
    # Slack post for an unmatched reply, another for a positive one - between
    # applying the event and saving, so this path cannot hold the queue lock
    # throughout and must not clobber whatever else wrote in the meantime.
    # `store.save(expect_digest=...)` turns that into a refusal.
    base = store.digest() if own else None
    recs = store.load() if own else recs

    # The adapter carries the reply text on the neutral event. It is read for
    # classification and never written to a record: see handle().
    neutral = adapter(payloads)
    # Stamped here rather than inside each adapter: the estate is a property of
    # the CREDENTIAL that did the reading, not of the payload, and an adapter is
    # a pure translation that has never been told which key fetched its input.
    if provider_workspace is not None:
        for event in neutral:
            event.setdefault("provider_workspace", provider_workspace)
    outcomes = [handle(e, recs, rows=rows, config=config, post=post, model=model)
                for e in neutral]
    if own and any(o["applied"] and o["applied"]["status"] == "applied"
                   for o in outcomes):
        store.save(recs, expect_digest=base)
    return outcomes


def manual(record_id, contact_key, text, channel="email", at=None, client=None):
    """A reply someone types in. Same path, same pause, same classification."""
    return events.neutral(
        type=events.REPLY_RECEIVED, channel=channel, provider="manual",
        provider_event_id=f"manual:{record_id}:{contact_key}:{at or store.now()}",
        record_id=record_id, contact_key=contact_key, client=client,
        at=at or store.now(), text=text)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.inbound")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--provider", required=True, choices=sorted(adapters.ADAPTERS))
    a.add_argument("--file", required=True)
    args = p.parse_args(argv)

    with open(args.file, encoding="utf-8") as f:
        payload = json.load(f)
    outcomes = ingest(payload, args.provider)
    for outcome in outcomes:
        applied = outcome["applied"] or {}
        verdict = outcome.get("classification") or {}
        print(f"  {applied.get('status', '?'):<10} "
              f"{applied.get('record_id') or '-':<16} "
              f"paused={outcome['paused']} "
              f"{verdict.get('classification') or ''}")
    print("\nNo message was sent to anyone. Replies pause; they never answer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
