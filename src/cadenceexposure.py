#!/usr/bin/env python3
"""What a contact actually received, as opposed to what they were assigned.

## The number that would otherwise be wrong

A contact assigned to a seven-step arm who replies after three confirmed
steps received three. Reporting them as having completed seven is the
single most damaging error this layer can make, and it is the easy one to
make: the arm says seven, the assignment says seven, and nothing else in
the record disagrees out loud.

Every rate in a cadence experiment has one of these counts underneath it.
A seven-step arm whose contacts mostly stopped at step two is not a
seven-step arm in any sense that a comparison can use, and an evaluator
handed "assigned" as its denominator would be comparing the arm somebody
configured against the arm somebody else actually ran.

## Assignment is not exposure, and neither is completion

    ASSIGNED         in the arm, and nothing has been sent
    STARTED          at least one step confirmed
    IN_PROGRESS      some steps confirmed, more still to come
    COMPLETED        every step in the arm confirmed
    STOPPED_EARLY    fewer steps than the arm has, and it will not resume

`STOPPED_EARLY` is the one that carries a reason, because "they replied"
and "they asked us to stop" and "somebody else at the account replied" are
three different facts about the experiment and only one of them is a
result.

## Censoring is a fact about the experiment, not a defect in it

A contact who replies at step three is *censored* - the arm did not finish
and the reason it did not finish is the outcome the experiment was looking
for. Reporting them as an incomplete run would be as wrong as reporting
them as a complete one.

Borrowed from survival analysis for the same reason it exists there: the
observations that stopped early are the informative ones, and dropping
them biases everything.

## Everything is counted from confirmed events

`touch.CONFIRMED_STATES` is the authority on what reached somebody.
Planned, approved and payload-ready steps are counted separately and never
as exposure - a denominator under a message nobody received makes a long
arm look worse than it is, and a numerator under one makes it look better.
"""
import argparse
import json

from . import accountpolicy as ap, account, cadencearms, touch

# Where a contact stands in the arm they were put in.
ASSIGNED = "assigned"
STARTED = "started"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"
STOPPED_EARLY = "stopped_early"

STATES = (ASSIGNED, STARTED, IN_PROGRESS, COMPLETED, STOPPED_EARLY)

STATE_LABEL = {
    ASSIGNED: "Assigned, nothing sent",
    STARTED: "Started",
    IN_PROGRESS: "Part way through",
    COMPLETED: "Completed the arm",
    STOPPED_EARLY: "Stopped early",
}

# Why a sequence stopped before the arm ran out. Ordered by how final they
# are: a removal request is not a pause somebody lifts.
REPLIED = "replied"
POSITIVE = "positive_reply"
NEGATIVE = "negative_reply"
UNSUBSCRIBED = "unsubscribed"
ACCOUNT_HELD = "account_held"
ACCOUNT_SUPPRESSED = "account_suppressed"
CONTACT_STOPPED = "contact_stopped"
DROPPED = "record_dropped"

TERMINATIONS = (UNSUBSCRIBED, ACCOUNT_SUPPRESSED, DROPPED, CONTACT_STOPPED,
                ACCOUNT_HELD, POSITIVE, NEGATIVE, REPLIED)

TERMINATION_LABEL = {
    REPLIED: "they replied",
    POSITIVE: "they replied, positively",
    NEGATIVE: "they replied, negatively",
    UNSUBSCRIBED: "they asked us to stop",
    ACCOUNT_HELD: "the account is held - somebody there is in conversation",
    ACCOUNT_SUPPRESSED: "the company asked us to stop",
    CONTACT_STOPPED: "this person's sequence was stopped",
    DROPPED: "the record was dropped from its batch",
}

# Terminations that are outcomes the experiment was looking for, as
# against terminations that are safety acting. Both stop the sequence and
# they mean opposite things about the arm.
OUTCOMES = (REPLIED, POSITIVE, NEGATIVE)
SAFETY = (UNSUBSCRIBED, ACCOUNT_SUPPRESSED, ACCOUNT_HELD, CONTACT_STOPPED,
          DROPPED)


def _confirmed_steps(rec, contact_key):
    """Which of this contact's steps actually reached them, in order.

    Confirmed only, and deduplicated by step key: a step delivered and
    then reported replied is one exposure, not two.
    """
    seen, out = set(), []
    for row in account.touches(rec, contact_key, confirmed_only=True):
        key = row.get("step")
        if not key or key in seen:
            continue
        # Said twice, on purpose, exactly as `push.verify_before_payload`
        # says its verification rule twice. `confirmed_only=True` above
        # already filters this, so neither check can fire while the other
        # holds - and removing either one alone changes nothing, which a
        # mutation run confirms.
        #
        # It is here because this is where the invariant lives: a step
        # that did not reach somebody is not exposure. A future caller
        # that assembled rows by hand, or a refactor that loosened
        # `touches`, would still meet it. A guard that exists once is a
        # guard one refactor away from gone.
        if row.get("state") not in touch.CONFIRMED_STATES:
            continue
        seen.add(key)
        out.append(row)
    return out


def _termination(rec, contact, replies):
    """Why this sequence will not continue, or None if it may.

    Read in order of finality. A contact who both replied and was
    suppressed is reported as suppressed: the removal request is the fact
    that decides what happens next, and the reply is already counted as an
    outcome elsewhere.
    """
    if rec.get("state") == "dropped":
        return DROPPED
    state, _why = ap.account_state(rec)
    if state == ap.SUPPRESS:
        return ACCOUNT_SUPPRESSED
    contact_state, _ = ap.contact_state(contact)
    if contact_state == ap.SUPPRESS:
        return UNSUBSCRIBED
    if contact_state == ap.STOP:
        return CONTACT_STOPPED
    if replies:
        if any(r.get("positive") for r in replies):
            return POSITIVE
        classified = {r.get("classification") for r in replies}
        if "negative" in classified or "unsubscribe" in classified:
            return NEGATIVE
        return REPLIED
    if state == ap.HOLD:
        # After replies, deliberately. A hold caused by this contact's own
        # reply should be reported as the reply; a hold with no reply here
        # is somebody else at the account, which is a different fact.
        return ACCOUNT_HELD
    if contact_state == ap.HOLD:
        return ACCOUNT_HELD
    return None


def termination(rec, contact, replies=None):
    """Why this contact's sequence will not continue, or None if it may.

    Public because it is the only vocabulary in the codebase for that
    question, and the outcome record needs the same words. A second stop
    reason list computed somewhere else is how two answers to "why did we
    stop writing to Sarah" start disagreeing - and unlike most duplication,
    that one is visible to a client.

    Independent of any experiment: a contact in no arm still stopped for a
    reason, and `contact_exposure` is unreachable for them.
    """
    from . import account

    if replies is None:
        replies = account.replies(rec, contact.get("key"))
    return _termination(rec, contact, replies)


def contact_exposure(exp, rec, contact, campaign=None):
    """What this one person received of the arm they are in.

    `None` when they are not in the experiment at all. An unassigned
    contact is not a zero-exposure participant, and counting them as one
    would put every contact in the estate in the denominator.
    """
    assignment = cadencearms.recorded(exp, rec, contact)
    if not assignment:
        return None
    arm = cadencearms.arm_by_id(exp, assignment.get("arm_id"))
    if arm is None:
        return None

    planned = list(arm.get("steps") or [])
    keys = [step["key"] for step in planned]
    confirmed = _confirmed_steps(rec, contact.get("key"))
    # Only steps belonging to *this* arm count. A confirmed touch on a step
    # key the arm does not contain came from a different sequence - an
    # earlier campaign, or the legacy cadence - and crediting it here would
    # borrow another campaign's history.
    mine = [row for row in confirmed if row.get("step") in set(keys)]
    reached = len(mine)

    replies = account.replies(rec, contact.get("key"))
    stopped = _termination(rec, contact, replies)

    if reached == 0:
        state = ASSIGNED
    elif reached >= len(planned):
        state = COMPLETED
    elif stopped:
        state = STOPPED_EARLY
    else:
        state = IN_PROGRESS

    return {
        "experiment_id": exp.get("experiment_id"),
        "arm_id": arm["arm_id"],
        "record_id": rec.get("id"),
        "contact_key": contact.get("key"),
        "workspace": assignment.get("unit_key") and rec.get("client"),
        "state": state,
        "state_label": STATE_LABEL[state],
        "started": reached > 0,
        # The two numbers the whole layer exists to keep apart.
        "planned": len(planned),
        "reached": reached,
        "steps": [{"key": row.get("step"), "channel": row.get("channel"),
                   "at": row.get("at"), "sender_id": row.get("sender_id"),
                   "variant_id": row.get("variant_id"),
                   "variant_version": row.get("variant_version")}
                  for row in mine],
        "not_reached": [key for key in keys
                        if key not in {row.get("step") for row in mine}],
        "terminated": stopped,
        "termination_label": TERMINATION_LABEL.get(stopped),
        # Censored means the arm did not finish and the reason it did not
        # finish is informative. Dropping these observations biases
        # everything; reporting them as incomplete runs is as wrong as
        # reporting them as complete ones.
        "censored": bool(stopped) and reached < len(planned),
        "censored_by": ("outcome" if stopped in OUTCOMES
                        else "safety" if stopped in SAFETY else None),
        "replied": bool(replies),
        "positive": any(r.get("positive") for r in replies),
        "note": "reached is confirmed touches on this arm's own steps. "
                "Planned, approved and payload-ready steps are not "
                "exposure",
    }


def exposures(exp, recs, campaign=None):
    """Every assigned contact's exposure. Unassigned contacts are absent."""
    out = []
    for rec in recs or []:
        for contact in account.contacts_of(rec):
            found = contact_exposure(exp, rec, contact, campaign)
            if found is not None:
                out.append(found)
    return out


def summarise(exp, recs, campaign=None):
    """Per arm: assigned, started, completed, and what stopped the rest.

    Every count carries its denominator, and the denominators are
    different on purpose. `started` is out of `assigned`; `completed` is
    out of `started`, because a contact who never received a first step
    has not run the arm and including them makes every arm look worse in
    proportion to how many were suppressed before it began.
    """
    rows = exposures(exp, recs, campaign)
    arms = {entry["arm_id"]: entry for entry in cadencearms.arms_of(exp)}

    out = {}
    for arm_id, entry in arms.items():
        mine = [row for row in rows if row["arm_id"] == arm_id]
        started = [row for row in mine if row["started"]]
        completed = [row for row in mine if row["state"] == COMPLETED]
        stopped = [row for row in mine if row["state"] == STOPPED_EARLY]
        reached = sum(row["reached"] for row in mine)
        out[arm_id] = {
            "arm_id": arm_id,
            "label": entry.get("label"),
            "planned_steps": len(entry.get("steps") or []),
            "assigned": len(mine),
            "started": len(started),
            "completed": len(completed),
            "stopped_early": len(stopped),
            "still_running": len([row for row in mine
                                  if row["state"] == IN_PROGRESS]),
            # Out of started, not out of assigned. A contact suppressed
            # before step one never ran the arm.
            "completion_rate": (len(completed) / len(started)
                                if started else None),
            "touches": reached,
            "touches_per_started": (reached / len(started)
                                    if started else None),
            "censored": len([row for row in mine if row["censored"]]),
            "censored_by_outcome": len([row for row in mine
                                        if row["censored_by"] == "outcome"]),
            "censored_by_safety": len([row for row in mine
                                       if row["censored_by"] == "safety"]),
            "terminations": {
                reason: len([row for row in mine
                             if row["terminated"] == reason])
                for reason in TERMINATIONS
                if any(row["terminated"] == reason for row in mine)},
            "replied": len([row for row in mine if row["replied"]]),
            "positive": len([row for row in mine if row["positive"]]),
        }

    return {
        "experiment_id": exp.get("experiment_id"),
        "unit": exp.get("unit"),
        "arms": [out[arm_id] for arm_id in arms],
        "assigned": len(rows),
        "note": "started is out of assigned; completed is out of started. "
                "A contact suppressed before step one never ran the arm, "
                "and counting them against it makes an arm look worse in "
                "proportion to how many were stopped before it began",
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.cadenceexposure",
                                description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    from . import campaigns, store

    campaign = campaigns.get(a.campaign, campaigns.load())
    exp = (campaign or {}).get(cadencearms.EXPERIMENT_KEY)
    if not exp:
        print("no cadence experiment on that campaign")
        return 1
    recs = [r for r in store.load()
            if r.get("id") in (campaign.get("record_ids") or [])]
    found = summarise(exp, recs, campaign)
    if a.json:
        print(json.dumps(found, indent=2, default=str))
        return 0

    for row in found["arms"]:
        rate = ("-" if row["completion_rate"] is None
                else f"{row['completion_rate']:.0%}")
        print(f"  {row['arm_id']:<10} {row['planned_steps']} steps  "
              f"assigned {row['assigned']:>4}  started {row['started']:>4}  "
              f"completed {row['completed']:>4} ({rate} of started)  "
              f"stopped early {row['stopped_early']:>4}")
        for reason, count in sorted(row["terminations"].items()):
            print(f"       {count:>4}  {TERMINATION_LABEL[reason]}")
    print("\n" + found["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
