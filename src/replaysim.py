#!/usr/bin/env python3
"""What happens when somebody answers, proved rather than asserted.

The reply-to-pause loop is the single most important behaviour in an outbound
system, and it is the one that is easiest to believe works. So this module runs
it: it feeds a real inbound event through the real inbound path, and then reads
the record afterwards to check each link in the chain actually moved.

    event received      the adapter produced a neutral event and it applied
    identity resolved   the event was matched to a record and a contact
    company paused      the pause is on the record, not merely intended
    cadence suppressed  every later step now refuses to send, with a reason
    slack planned       the notification was built - and NOT posted
    reporting recorded  the event stream carries what a report would count

Nothing is posted to Slack. `post` is a collector, so the payload is captured
and inspected rather than delivered, and there is a test that asserts the
collector was the only recipient.

  python -m src.replaysim --record acme --contact acme-c0 --kind positive
"""
import argparse
import json

from . import (adapters, cadence, campaigns, clients, eligibility, events,
               inbound, replies, store)

# The four inbound shapes worth rehearsing, in the words a real one arrives in.
SCENARIOS = {
    "positive_email": {
        "channel": "email",
        "provider": "bison",
        "text": "Sounds interesting. Happy to chat - what does your "
                "availability look like next week?",
        "expect": replies.POSITIVE,
        "note": "hits three positive rules; a vaguer yes classifies neutral, "
                "which is the conservative direction to be wrong in",
    },
    "negative_email": {
        "channel": "email",
        "provider": "bison",
        "text": "Not interested, please remove me from your list.",
        "expect": replies.UNSUBSCRIBE,
    },
    "linkedin_reply": {
        "channel": "linkedin",
        "provider": "heyreach",
        "text": "Happy to connect. What is it you do exactly?",
        "expect": replies.NEUTRAL,
    },
    "unclassifiable_inbound": {
        "channel": "email",
        "provider": "bison",
        "text": "\u2500\u2500\u2500\u2500\u2500",
        # TASK-020 established that no rule matched is UNKNOWN, not NEUTRAL.
        # NEUTRAL is a measurement ("we read this and it is lukewarm");
        # UNKNOWN is a gap ("we could not read this").  A line of dashes
        # is a gap, not a measurement.  The pause still fires: both
        # UNKNOWN and NEUTRAL pause the company, so safety is unchanged.
        "expect": replies.UNKNOWN,
        "note": "no rule matched and no model was available",
    },
}


class Collector:
    """Stands in for Slack. Keeps the payload; delivers nothing."""

    def __init__(self):
        self.posted = []

    def __call__(self, payload, config=None, **kw):
        self.posted.append(payload)
        return {"ok": True, "delivered": False,
                "why": "collector: this is a simulation"}


def _event_for(rec, contact_key, scenario, at=None, event_id=None):
    """A neutral inbound event, in the shape the adapters produce."""
    return {
        "provider": scenario["provider"],
        "provider_event_id": event_id or f"sim-{rec['id']}-{contact_key}",
        "type": events.REPLY_RECEIVED,
        "channel": scenario["channel"],
        "record_id": rec.get("id"),
        "contact": contact_key,
        "email": (next((c.get("email") for c in rec.get("contacts") or []
                        if c.get("key") == contact_key), None)),
        "text": scenario["text"],
        "at": at or store.now(),
    }


def _steps_after(rec, config, campaign, recs, day=21):
    """Every remaining step and what eligibility now says about it."""
    out = []
    timeline = cadence.build(rec, config, recs=recs,
                             campaign=campaign).get("contacts") or {}
    for contact in rec.get("contacts") or []:
        for step_key in timeline.get(contact.get("key")) or {}:
            decision = eligibility.decide(
                rec, contact, step_key, campaign=campaign, recs=recs,
                config=config, day=day, timeline=timeline)
            out.append({"contact_key": contact.get("key"), "step": step_key,
                        "verdict": decision["verdict"],
                        "reasons": decision["reasons"]})
    return out


def simulate(rec, contact_key, scenario="positive_email", recs=None,
             config=None, campaign=None, rows=None, at=None):
    """Run one inbound event through the real path and report each link.

    The record is mutated in memory, as the live path would mutate it. Nothing
    is saved: the caller decides whether this rehearsal is worth keeping.
    """
    spec = SCENARIOS.get(scenario)
    if spec is None:
        raise KeyError(f"unknown scenario: {scenario}")
    recs = [rec] if recs is None else recs
    if config is None:
        try:
            config = clients.load(rec.get("client"))
        except Exception:
            config = {}

    before = {
        "paused": bool(rec.get("paused")),
        "steps": _steps_after(rec, config, campaign, recs),
    }
    collector = Collector()
    event = _event_for(rec, contact_key, spec, at=at)
    outcome = inbound.handle(event, recs, rows=rows, config=config,
                             post=collector)
    after_steps = _steps_after(rec, config, campaign, recs)

    applied = outcome.get("applied") or {}
    classification = (outcome.get("classification") or {}).get("classification")
    reply_events = [e for e in rec.get("events") or []
                    if e.get("type") in (events.REPLY_RECEIVED,
                                         events.REPLY_CLASSIFIED,
                                         events.POSITIVE_REPLY_DETECTED)]

    # A step counts as suppressed when it stopped being eligible. Comparing
    # before and after is the only honest way to say the reply changed
    # anything - asserting the pause exists proves the field, not the effect.
    was_eligible = {(s["contact_key"], s["step"]) for s in before["steps"]
                    if s["verdict"] == eligibility.ELIGIBLE}
    still_eligible = {(s["contact_key"], s["step"]) for s in after_steps
                      if s["verdict"] == eligibility.ELIGIBLE}
    suppressed = sorted(was_eligible - still_eligible)

    return {
        "scenario": scenario,
        "record_id": rec.get("id"),
        "contact_key": contact_key,
        "expected_classification": spec["expect"],
        "chain": {
            "event_received": applied.get("status") == "applied",
            "identity_resolved": bool(applied.get("record_id")
                                      and applied.get("contact")),
            "company_paused": bool(rec.get("paused")),
            "cadence_suppressed": bool(suppressed) or bool(rec.get("paused")),
            "slack_planned": bool(outcome.get("notification")),
            "reporting_recorded": bool(reply_events),
        },
        # How the suppression claim above was earned. "observed" means a step
        # that was eligible before this reply is not eligible now, which is
        # the only real proof; "pause_only" means nothing was eligible to
        # begin with, so the pause is in place but nothing was demonstrated.
        "suppression_evidence": ("observed" if suppressed
                                 else "pause_only" if rec.get("paused")
                                 else "none"),
        "classification": classification,
        "classification_matches_expectation": classification == spec["expect"],
        "steps_eligible_before": len(was_eligible),
        "steps_eligible_after": len(still_eligible),
        "steps_suppressed": suppressed,
        "slack_payload": collector.posted[0] if collector.posted else None,
        "slack_delivered": False,
        "events_recorded": [e.get("type") for e in reply_events],
        "pause_reason": (rec.get("paused") or {}).get("reason"),
    }


def run_all(rec, contact_key, recs=None, config=None, campaign=None):
    """Every scenario, each against a fresh copy of the record.

    Copies rather than one record in sequence: the first reply pauses the
    company, and every scenario after it would then be testing the pause
    instead of itself.
    """
    import copy

    out = {}
    for name in SCENARIOS:
        fresh = copy.deepcopy(rec)
        others = [copy.deepcopy(r) for r in (recs or []) if r is not rec]
        out[name] = simulate(fresh, contact_key, name, recs=[fresh] + others,
                             config=config, campaign=campaign)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record", required=True)
    p.add_argument("--contact", required=True)
    p.add_argument("--kind", choices=sorted(SCENARIOS), default=None)
    p.add_argument("--campaign")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = store.load()
    rec = next((r for r in recs if r.get("id") == a.record), None)
    if rec is None:
        print(f"REFUSED: no such record: {a.record}")
        return 2
    campaign = campaigns.get(a.campaign) if a.campaign else None

    results = ({a.kind: simulate(rec, a.contact, a.kind, recs=recs,
                                 campaign=campaign)} if a.kind
               else run_all(rec, a.contact, recs=recs, campaign=campaign))
    if a.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    for name, result in results.items():
        print(f"\n{name}: classified {result['classification']} "
              f"(expected {result['expected_classification']})")
        for link, ok in result["chain"].items():
            print(f"  {'PASS' if ok else '  - '} {link}")
        print(f"  eligible steps {result['steps_eligible_before']} -> "
              f"{result['steps_eligible_after']}")
        print(f"  slack delivered: {result['slack_delivered']}")
    print("\nNothing was sent and nothing was posted to Slack.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
