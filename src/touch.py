#!/usr/bin/env python3
"""What actually happened to this prospect, as opposed to what was planned.

## The sentence this module exists to make safe

    "My colleague Anna reached out over email earlier this week."

That sentence is either true or it is a fabrication that a prospect can catch,
and the difference is not visible in the copy. It is visible only in whether
the email Anna was assigned to send *actually went out*. So this module answers
one question, narrowly, and refuses to answer it optimistically:

    Is there trustworthy evidence that a named human touched this contact on
    this channel, before now?

`src/cadence.py` already had the right instinct - its LinkedIn note is a
template rather than a generated message, with the comment "it costs nothing
and it cannot wander into referencing the email". That was the safe answer
while nothing could establish the fact. This module establishes the fact, so
the reference becomes possible without becoming inventable.

## What counts as confirmed, exactly

A touch is CONFIRMED when the record carries an event of one of these types
for that contact, that channel and that step:

    push_marked        we handed it to the provider and marked it sent
    email_delivered    the provider told us it was delivered
    linkedin_connected the provider told us the connection was accepted

and nothing weaker. In particular these are all NOT confirmed:

    a cadence step whose status is `eligible`, `pending` or `waiting`
    a draft that passed lint
    a draft a human approved
    `push_prepared` - a payload was built. A payload is not a send.
    a step that was blocked, held, failed or skipped
    a campaign that is approved
    a campaign that is launch-ready

`push_prepared` deserves the emphasis. It is the event that fires when a
payload is constructed, and in this build every payload is constructed and none
is sent - so treating it as evidence would make *every* planned touch look like
it had happened, on a system that has never sent anything. It is the single
most dangerous near-miss in the vocabulary and it is excluded by name.

## Confirmed by whom

A confirmed touch is not enough on its own. The copy names a *person*, so the
touch has to carry which person, recorded at the time it happened rather than
looked up now:

    events.record(rec, PUSH_MARKED, ..., sender_id="anna", account_id="anna07")

An assignment can be changed by a human (`assignment.reassign`). If the
reference read the *current* assignment, a reassignment would silently rewrite
history and put the wrong name in the copy. So a touch with no `sender_id` on
the event is confirmed-but-unattributed: it happened, and it may not be
referenced by name.

## What this module does not do

It does not decide what to write. It builds a context object; `cadence.py`
turns that into words. Keeping the two apart is what lets the preview screen
show the evidence beside the sentence and say which one licensed the other.
"""
import argparse
import json

from . import assignment, events, senderidentity as si, store

EMAIL = si.EMAIL
LINKEDIN = si.LINKEDIN

# ------------------------------------------------------------- the states
#
# A step is in exactly one of these, and they are deliberately not collapsed.
# "planned" and "sent" being the same word is how a system starts claiming
# things it did not do.

PLANNED = "planned"
APPROVED = "approved"
PAYLOAD_READY = "payload_ready"
SENT = "sent"
DELIVERED = "delivered"
REPLIED = "replied"
POSITIVE_REPLY = "positive_reply"
PAUSED = "paused"
HELD = "held"
BLOCKED = "blocked"
FAILED = "failed"
SKIPPED = "skipped"

STATES = (PLANNED, APPROVED, PAYLOAD_READY, SENT, DELIVERED, REPLIED,
          POSITIVE_REPLY, PAUSED, HELD, BLOCKED, FAILED, SKIPPED)

# The only states that mean "this reached the prospect". Everything else is
# either not yet, or never.
CONFIRMED_STATES = frozenset({SENT, DELIVERED, REPLIED, POSITIVE_REPLY})

# The events that establish one. `push_prepared` is absent by name; see the
# module docstring for why that is the important omission.
CONFIRMING_EVENTS = {
    events.PUSH_MARKED: SENT,
    events.EMAIL_DELIVERED: DELIVERED,
    events.LINKEDIN_CONNECTED: DELIVERED,
}

# Human wording for each state, so a preview never prints a bare code.
WORDS = {
    PLANNED: "planned, not sent",
    APPROVED: "approved, not sent",
    PAYLOAD_READY: "payload built, not sent",
    SENT: "confirmed sent",
    DELIVERED: "confirmed delivered by the provider",
    REPLIED: "replied to",
    POSITIVE_REPLY: "replied to, positively",
    PAUSED: "paused",
    HELD: "held",
    BLOCKED: "blocked",
    FAILED: "failed",
    SKIPPED: "skipped",
}


def is_confirmed(state):
    return state in CONFIRMED_STATES


# ------------------------------------------------------------- the history

def _events_for(rec, contact_key):
    return [e for e in rec.get("events") or []
            if e.get("contact") == contact_key]


def _state_from_events(entries):
    """The strongest state the events establish, and the event that did it.

    Strongest rather than latest: a delivered email that was later part of a
    paused company is still a delivered email, and the pause is a separate
    fact about what happens next.
    """
    rank = {SENT: 1, DELIVERED: 2, REPLIED: 3, POSITIVE_REPLY: 4}
    best, source = None, None
    for entry in entries:
        state = CONFIRMING_EVENTS.get(entry.get("type"))
        if state and rank.get(state, 0) > rank.get(best or "", 0):
            best, source = state, entry
    return best, source


def history(rec, contact_key, timeline=None, config=None,
            campaign=None):
    """Every step for one contact, in order, with what actually happened.

    `timeline` is `cadence.build(...)["contacts"][contact_key]` when the
    caller already has one - building it again per contact is the quadratic
    mistake `cadence.build` documents for pause lookups.
    """
    from . import cadence

    if timeline is None:
        built = cadence.build(rec, config, campaign=campaign)
        timeline = (built.get("contacts") or {}).get(contact_key) or {}

    entries = _events_for(rec, contact_key)
    by_step = {}
    for entry in entries:
        step = entry.get("step")
        if step:
            by_step.setdefault(step, []).append(entry)

    replied_at = None
    positive = False
    for entry in entries:
        if entry.get("type") in (events.REPLY_RECEIVED, events.REPLY_CLASSIFIED):
            replied_at = replied_at or entry.get("at")
            if entry.get("classification") == "positive":
                positive = True
        if entry.get("type") == events.POSITIVE_REPLY_DETECTED:
            positive = True

    # The step set is the union of what the cadence plans *now* and what the
    # events say already happened. Driving it from the timeline alone was
    # wrong in a way tests caught: a contact whose email channel later closes
    # - an MX block, a failed verification - loses its email steps from the
    # timeline, and a history built only from the timeline would then forget
    # that Anna had already emailed them. A touch that happened is a fact
    # about the past and cannot be un-happened by a change to the plan.
    steps = dict(timeline)
    for step_key, step_events in by_step.items():
        if step_key in steps:
            continue
        # Any event at all is enough to know the step exists. Confirming
        # events establish that it happened; a `push_prepared` establishes
        # only that a payload was built - but the step is still real, and a
        # refusal that says "no confirmed touch exists" when a payload-ready
        # one is sitting right there reads as a bug rather than as a rule.
        # Naming the state is what makes the refusal legible.
        _, source = _state_from_events(step_events)
        source = source or step_events[0]
        steps[step_key] = {
            "day": source.get("day"),
            "channel": source.get("channel"),
            # Named so a screen can say why this row has no copy beside it.
            "status": "historical",
            "not_in_current_cadence": True,
        }

    out = []
    for step_key, step in sorted(steps.items(),
                                 key=lambda kv: (kv[1].get("day") or 0,
                                                 kv[0])):
        step_events = by_step.get(step_key, [])
        confirmed_state, source = _state_from_events(step_events)
        state = confirmed_state or _planned_state(step)
        prepared = any(e.get("type") == events.PUSH_PREPARED
                       for e in step_events)
        if state == PLANNED and prepared:
            state = PAYLOAD_READY
        out.append({
            "step": step_key,
            "day": step.get("day") if step.get("day") is not None
            else (source or {}).get("day"),
            "channel": step.get("channel"),
            "state": state,
            "state_words": WORDS.get(state, state),
            "confirmed": is_confirmed(state),
            # Who, as recorded on the confirming event - never looked up now.
            "sender_id": (source or {}).get("sender_id"),
            "account_id": (source or {}).get("account_id"),
            "at": (source or {}).get("at"),
            "provider": (source or {}).get("provider"),
            "evidence_event": (source or {}).get("type"),
            "evidence_event_id": (source or {}).get("id"),
            "payload_prepared": prepared,
            "blocked_by": step.get("blocked_by"),
            "status": step.get("status"),
            "in_current_cadence": not step.get("not_in_current_cadence"),
        })

    return {
        "record_id": rec.get("id"),
        "contact_key": contact_key,
        "steps": out,
        "confirmed_count": len([s for s in out if s["confirmed"]]),
        "replied_at": replied_at,
        "positive_reply": positive,
        "paused": bool(rec.get("paused")),
    }


def _planned_state(step):
    """What the cadence says about a step nothing has confirmed."""
    status = step.get("status")
    return {
        "pushed": SENT,          # cadence's own word for a marked step
        "paused": PAUSED,
        "blocked": BLOCKED,
        "waiting": HELD,
        "eligible": APPROVED,
        "pending": PLANNED,
    }.get(status, PLANNED)


def confirmed_touches(rec, contact_key, before_day=None, timeline=None,
                      config=None):
    """Only the touches that actually happened, oldest first.

    `before_day` restricts to touches earlier in the cadence than the step
    being written, because a step cannot reference one that comes after it.
    """
    built = history(rec, contact_key, timeline, config)
    out = []
    for step in built["steps"]:
        if not step["confirmed"]:
            continue
        if before_day is not None and (step["day"] or 0) >= before_day:
            continue
        out.append(step)
    return out


# --------------------------------------------------- the generation context

def context(rec, contact, channel, step_key, day, workspace, timeline=None,
            config=None, rows=None, campaign=None, already_referenced=None):
    """Everything a message may safely know about what came before.

    This is the object that gets handed to generation. Four properties of it
    matter more than its contents:

    **It carries no provider payload and no secret.** Only our own vocabulary:
    a channel, a day, a sender id, a state word. There is nothing in here that
    a provider wrote, so there is nothing for a provider to inject through.

    **A reference is allowed or it is not, and the reason is in the object.**
    `may_reference` is a boolean and `reference_reason` is the sentence a
    preview screen prints beside it. A caller cannot get the boolean without
    the reason, so a screen cannot show a claim without its evidence.

    **The previous sender is the one recorded on the touch**, not the one
    currently assigned. A reassignment must not rewrite history.

    **Silence is the default.** Every path that cannot establish a fact ends
    at `may_reference: False`, and the copy falls back to standalone.

    `already_referenced` is the set of touches an earlier step in this cadence
    has already named. A reference is a thing you make once: five emails in a
    row each opening "my colleague Petar reached out on LinkedIn" is not five
    times as personal, it is a sequence a person would recognise as generated.
    """
    rows = si.load() if rows is None else rows
    current = assignment.assigned(contact, channel) or {}
    previous = confirmed_touches(rec, contact.get("key"), before_day=day,
                                 timeline=timeline, config=config)

    # Only a touch on the *other* channel is a cross-channel reference. A
    # previous email does not license an email saying "I emailed you" - that
    # is a follow-up, which the cadence templates already handle.
    cross = [t for t in previous if t["channel"] and t["channel"] != channel]

    base = {
        "record_id": rec.get("id"),
        "contact_key": contact.get("key"),
        "workspace": workspace,
        "channel": channel,
        "step": step_key,
        "day": day,
        "current_sender": {
            "sender_id": current.get("sender_id"),
            "display_name": current.get("display_name"),
            "account_id": current.get("account_id"),
            "provider": current.get("provider"),
        } if current else None,
        "confirmed_previous_touches": [
            {"channel": t["channel"], "day": t["day"], "at": t["at"],
             "sender_id": t["sender_id"], "state": t["state"],
             "step": t["step"]}
            for t in previous],
        "may_reference": False,
        "reference_reason": None,
        "reference": None,
    }

    if not cross:
        blocked = [t for t in _unconfirmed_cross(rec, contact, channel, day,
                                                 timeline, config)]
        if blocked:
            first = blocked[0]
            base["reference_reason"] = (
                f"the day {first['day']} {first['channel']} step is "
                f"{first['state_words']}, which is not evidence that it "
                "reached this contact")
        else:
            base["reference_reason"] = (
                f"no confirmed {'email' if channel == LINKEDIN else 'LinkedIn'} "
                "touch exists for this contact before this step")
        return base

    # The most recent confirmed cross-channel touch is the one worth naming.
    last = sorted(cross, key=lambda t: (t["day"] or 0))[-1]
    if already_referenced and _touch_key(last) in already_referenced:
        base["reference_reason"] = (
            f"the day {last['day']} {last['channel']} touch has already been "
            "referenced earlier in this cadence, and naming it again would "
            "read as a template rather than as a person")
        return base
    if not last.get("sender_id"):
        base["reference_reason"] = (
            f"the day {last['day']} {last['channel']} touch is confirmed, but "
            "the event does not record which sender made it, so no person may "
            "be named")
        return base

    previous_sender = si.sender(workspace, last["sender_id"], rows)
    if previous_sender is None:
        base["reference_reason"] = (
            f"the day {last['day']} {last['channel']} touch names sender "
            f"{last['sender_id']!r}, which is not a sender in this workspace")
        return base

    link = si.relationship(workspace, current.get("sender_id"),
                           last["sender_id"], rows, config)
    mode = _mode_for(current.get("sender_id"), last["sender_id"], link)
    if mode is None:
        base["reference_reason"] = link["why"]
        return base

    base["may_reference"] = True
    base["reference_reason"] = (
        f"{previous_sender.get('display_name') or last['sender_id']} / "
        f"{last['channel']} / day {last['day']} / {last['state']}"
        + (f" / {last['at']}" if last.get("at") else ""))
    base["reference"] = {
        "mode": mode,
        # The step the referenced touch belongs to, so a later step can tell
        # whether this exact touch has already been named.
        "step": last["step"],
        "channel": last["channel"],
        "day": last["day"],
        "at": last["at"],
        "state": last["state"],
        "sender_id": last["sender_id"],
        "display_name": previous_sender.get("display_name"),
        "first_name": (previous_sender.get("display_name") or "").split(" ")[0],
        "relationship": link["kind"],
        "wording": link["wording"],
    }
    return base


def _touch_key(step):
    """Identity of one touch, for "have we mentioned this already"."""
    return f"{step.get('channel')}:{step.get('step')}"


def _unconfirmed_cross(rec, contact, channel, day, timeline, config):
    """Cross-channel steps that exist but did not happen.

    Used only to explain *why* a reference is unavailable. A preview that says
    "no confirmed touch" when there is a planned one sitting right there reads
    as a bug; naming the state is what makes the refusal legible.
    """
    built = history(rec, contact.get("key"), timeline, config)
    out = []
    for step in built["steps"]:
        if step["confirmed"]:
            continue
        if not step["channel"] or step["channel"] == channel:
            continue
        if day is not None and (step["day"] or 0) >= day:
            continue
        out.append(step)
    return sorted(out, key=lambda s: -(s["day"] or 0))


# ------------------------------------------------------------- copy modes

SAME_SENDER = "same_sender_continuity"
TEAM_HANDOFF = "team_handoff"
NEUTRAL = "neutral_reference"


def _mode_for(current_sender_id, previous_sender_id, link):
    """Which of the cross-channel copy modes applies, or None for standalone.

    Three outcomes and no fourth:

    - the same human on both channels: continuity, no claim about anybody else
    - two humans the workspace has said may be described as colleagues:
      a handoff
    - two humans without that permission: None. Not a vaguer sentence - a
      *standalone message*. "Someone reached out" is still a claim about a
      relationship, and a prospect who cannot place the name is being asked to
      believe something we were not authorised to say.
    """
    if current_sender_id and current_sender_id == previous_sender_id:
        return SAME_SENDER
    if link.get("colleague_language_allowed"):
        return TEAM_HANDOFF
    return None


def explain(ctx):
    """One line a person can read, for the preview and for QA."""
    if ctx.get("may_reference"):
        return f"Cross-channel reference allowed because: {ctx['reference_reason']}"
    return f"Cross-channel reference unavailable because: {ctx['reference_reason']}"


# ----------------------------------------------------------------- summary

def timeline_rows(rec, contact_key, timeline=None, config=None):
    """The contact timeline, flattened for a table."""
    built = history(rec, contact_key, timeline, config)
    return built["steps"]


def summarise(recs, workspace=None):
    """Counts by state across many records. Reporting reads this."""
    counts = {state: 0 for state in STATES}
    confirmed_by_channel = {EMAIL: 0, LINKEDIN: 0}
    for rec in recs:
        for contact in rec.get("contacts") or []:
            if not contact.get("selected"):
                continue
            for step in timeline_rows(rec, contact.get("key")):
                counts[step["state"]] = counts.get(step["state"], 0) + 1
                if step["confirmed"] and step["channel"] in confirmed_by_channel:
                    confirmed_by_channel[step["channel"]] += 1
    return {"by_state": counts, "confirmed_by_channel": confirmed_by_channel,
            "confirmed": sum(confirmed_by_channel.values())}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.touch", description=__doc__)
    p.add_argument("--id", required=True, help="record id")
    p.add_argument("--contact")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    rec = store.get(args.id)
    if rec is None:
        print(f"no record {args.id}")
        return 1
    contacts = ([args.contact] if args.contact
                else [c.get("key") for c in rec.get("contacts") or []])
    for key in contacts:
        built = history(rec, key)
        if args.json:
            print(json.dumps(built, indent=2, default=str))
            continue
        print(f"\n{key}")
        for step in built["steps"]:
            mark = "OK" if step["confirmed"] else "  "
            who = step["sender_id"] or "-"
            print(f"  {mark} day {str(step['day']):>2}  "
                  f"{(step['channel'] or '?'):<9} {who:<12} "
                  f"{step['state_words']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
