#!/usr/bin/env python3
"""Everything that arrives from outside, on one path.

An email reply from EmailBison, a LinkedIn reply from HeyReach and a reply typed
in by hand are three different payloads describing the same thing: a human
answered. They are normalised to one neutral event, applied once, and then
walked through the same four steps in the same order, every time:

    1. apply the event      (idempotent on the provider's own event id)
    2. pause the company    (both channels, every contact, no exceptions)
    3. classify the reply   (conservatively, and never to resume anything)
    4. notify a human       (best effort, and allowed to fail)

The order is the whole design. The pause happens before anything is classified
and long before anyone is told, so a classifier that misreads a message, a
Slack workspace that is down, and a notification that nobody opens all leave
the same outcome: the company stops being contacted. Nothing in step 3 or 4 can
reach back and undo step 2.

  python -m src.inbound apply --provider emailbison --file payload.json
  python -m src.inbound show
"""
import argparse
import json
import sys

from . import (adapters, campaigns, clients, events, notify, observability,
               orchestrator, replies, store)


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


def handle(event, recs, rows=None, config=None, post=None, model=None):
    """One inbound event, start to finish. Returns what happened at each step."""
    outcome = {"event": event, "applied": None, "paused": False,
               "classification": None, "notification": None}

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
        # Operational, and global. `notify.notify` cannot raise, so an alert
        # that cannot route leaves this path exactly as it found it.
        outcome["notification"] = notify.notify(
            notify.UNMATCHED_REPLY, None,
            fields={"provider": event.get("provider"),
                    "status": applied["status"],
                    "why": applied.get("why"),
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

    verdict = replies.apply(
        rec, applied.get("contact"), _text_of(event),
        at=event.get("at"), model=model, channel=event.get("channel"),
        provider=event.get("provider"),
        provider_event_id=event.get("provider_event_id"),
        # The provider's own autoresponder flag where it has one. `None`
        # means it did not say, which `ooo.detect` treats as unknown rather
        # than as a denial.
        automated=event.get("automated"))
    outcome["classification"] = verdict["verdict"]

    # The pause is already in place. What follows can fail freely.
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
           model=None):
    """A provider payload in, a list of outcomes out. Saves once, at the end."""
    adapter = adapters.ADAPTERS.get(provider)
    if adapter is None:
        raise ValueError(f"no adapter for provider {provider!r}")
    own = recs is None
    recs = store.load() if own else recs

    # The adapter carries the reply text on the neutral event. It is read for
    # classification and never written to a record: see handle().
    neutral = adapter(payloads)
    outcomes = [handle(e, recs, rows=rows, config=config, post=post, model=model)
                for e in neutral]
    if own and any(o["applied"] and o["applied"]["status"] == "applied"
                   for o in outcomes):
        store.save(recs)
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
