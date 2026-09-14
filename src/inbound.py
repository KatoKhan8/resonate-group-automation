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
import json
import sys

from . import (accountpolicy, adapters, campaigns, clients, events, leadstop,
               notify, ooo,
               observability, orchestrator, replies, store)


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

    What it returns is the audit trail: `None` when there was nothing to
    stop, otherwise the outcome or the reason it could not be done.
    """
    if not contact or not (contact or {}).get("bison_lead_id"):
        return None
    try:
        return leadstop.stop_contact(rec, contact, events.REPLY_RECEIVED,
                                     rows=rows, live=True)
    except Exception as e:
        # Explicitly classified, never swallowed: an unstopped person is the
        # thing somebody has to go and look at.
        return {"stopped": False, "error": type(e).__name__,
                "why": str(e)[:200]}


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
        # Operational, and global. `notify.notify` cannot raise, so an alert
        # that cannot route leaves this path exactly as it found it.
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
