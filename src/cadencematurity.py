#!/usr/bin/env python3
"""Whether a cadence comparison has been given time to be a comparison.

## The unfairness this exists to prevent

A four-step arm finishes on day twelve. A seven-step arm finishes on day
thirty-five. Compare them on day fifteen and the four-step arm has had
every chance it will ever get while the seven-step arm has had two thirds
of one - and the four-step arm wins, on a difference that is entirely an
artefact of when somebody looked.

That is not a subtle bias. It is the largest single way a cadence
experiment produces a confident wrong answer, and it gets worse the bigger
the difference between the arms - which is exactly the difference the
experiment was built to measure.

## Maturity is per arm, and the experiment is as mature as its slowest arm

    IMMATURE           the youngest cohorts have not had time for step one
    PARTIALLY_MATURE   some contacts could have finished; many could not
    MATURE             every assigned contact has had time for every step

An arm is only comparable to another arm when both are mature. A verdict
drawn from a mature four-step arm and an immature seven-step arm is a
verdict about the calendar.

## Time is counted from assignment, per contact, not per experiment

Contacts are assigned as an audience is built, so an experiment started
six weeks ago may contain a contact assigned yesterday. Measuring from the
experiment's start date would call that cohort mature; measuring from each
contact's own assignment does not.

A contact whose sequence ended early is mature the moment it ended. They
are not waiting for step seven - step seven is never coming, and holding
the arm immature on their account would keep it immature forever.

## It does not judge outcomes

Nothing here reads a reply. Maturity says whether a comparison is *allowed
to mean anything yet*; `variants.evaluate` decides what it means. Two
questions, two modules, and an evaluator that also decided maturity would
be able to talk itself into a verdict.
"""
import argparse
import datetime
import json

from . import cadencearms, cadenceexposure, evidence

IMMATURE = "immature"
PARTIALLY_MATURE = "partially_mature"
MATURE = "mature"

LEVELS = (IMMATURE, PARTIALLY_MATURE, MATURE)

LEVEL_LABEL = {
    IMMATURE: "Too early to read",
    PARTIALLY_MATURE: "Some contacts have finished, many have not",
    MATURE: "Every contact has had time for every step",
}

# Order for "the experiment is as mature as its slowest arm".
RANK = {IMMATURE: 0, PARTIALLY_MATURE: 1, MATURE: 2}

DEFAULTS = {
    # Days after the last step's day before a cohort counts as having had
    # its full chance. A step scheduled for day 35 does not arrive at
    # 00:00 on day 35: sending is paced, windows are respected, and a
    # provider takes its own time.
    "settling_days": 3,
    # Below this share of contacts having finished, an arm is immature
    # however long it has been running - one contact who finished does not
    # make a cohort readable.
    "partial_at": 0.10,
}


def settings(config):
    merged = dict(DEFAULTS)
    merged.update(((config or {}).get("cadence_maturity") or {}))
    return merged


def _days_since(at, today=None):
    age = evidence.age_days(at, today)
    return age if age is not None and age >= 0 else None


def arm_span(arm):
    """The day the last step of this arm is scheduled for."""
    days = [int(step.get("day") or 0) for step in (arm or {}).get("steps") or []]
    return max(days) if days else 0


def contact_maturity(exp, rec, contact, today=None, config=None):
    """Has this one contact had time to experience the arm they are in?

    `None` when they are not in the experiment - an unassigned contact is
    not an immature one, and counting them would hold every arm immature
    for as long as the audience keeps growing.
    """
    policy = settings(config)
    exposure = cadenceexposure.contact_exposure(exp, rec, contact)
    if exposure is None:
        return None
    assignment = cadencearms.recorded(exp, rec, contact)
    arm = cadencearms.arm_by_id(exp, exposure["arm_id"])

    span = arm_span(arm) + int(policy["settling_days"])
    age = _days_since((assignment or {}).get("at"), today)

    # A sequence that ended is finished, whatever the calendar says. They
    # are not waiting for step seven; step seven is never coming.
    ended = exposure["state"] in (cadenceexposure.COMPLETED,
                                  cadenceexposure.STOPPED_EARLY)

    return {
        "record_id": exposure["record_id"],
        "contact_key": exposure["contact_key"],
        "arm_id": exposure["arm_id"],
        "assigned_at": (assignment or {}).get("at"),
        "days_since_assignment": age,
        # How long this arm needs before a contact in it has had every
        # chance the arm offers.
        "span_days": span,
        "finished": bool(ended),
        # Either the sequence ended, or enough time has passed that every
        # step could have happened.
        "had_full_chance": bool(ended or (age is not None and age >= span)),
        "why": ("the sequence ended" if ended
                else "not assigned long enough" if age is None or age < span
                else "every step has had time to happen"),
    }


def arm_maturity(exp, arm_id, recs, today=None, config=None):
    """Whether this arm is ready to be compared with another."""
    policy = settings(config)
    rows = []
    for rec in recs or []:
        from . import account

        for contact in account.contacts_of(rec):
            found = contact_maturity(exp, rec, contact, today, config)
            if found is not None and found["arm_id"] == arm_id:
                rows.append(found)

    arm = cadencearms.arm_by_id(exp, arm_id)
    total = len(rows)
    done = [row for row in rows if row["had_full_chance"]]
    share = (len(done) / total) if total else None

    if not total:
        level = IMMATURE
        why = "nobody is in this arm yet"
    elif share >= 1.0:
        level = MATURE
        why = "every assigned contact has had time for every step"
    elif share >= float(policy["partial_at"]):
        level = PARTIALLY_MATURE
        why = (f"{len(done)} of {total} have had their full chance; the rest "
               "were assigned too recently")
    else:
        level = IMMATURE
        why = (f"only {len(done)} of {total} have had their full chance"
               if done else
               f"none of {total} has had time for the whole arm")

    waiting = [row for row in rows if not row["had_full_chance"]]
    longest = max((row["span_days"] - (row["days_since_assignment"] or 0)
                   for row in waiting), default=0)
    return {
        "arm_id": arm_id,
        "label": (arm or {}).get("label"),
        "level": level,
        "level_label": LEVEL_LABEL[level],
        "why": why,
        "span_days": arm_span(arm) + int(policy["settling_days"]),
        "assigned": total,
        "had_full_chance": len(done),
        "share": share,
        # How much longer before this arm is readable, at the current
        # audience. Reported rather than promised: an audience that keeps
        # growing keeps moving it.
        "days_until_mature": max(0, longest) if waiting else 0,
    }


def maturity(exp, recs, today=None, config=None):
    """The experiment's maturity: that of its slowest arm.

    A verdict drawn from a mature four-step arm and an immature seven-step
    arm is a verdict about the calendar, so the comparison is only as
    readable as the arm that has had least time.
    """
    arms = [arm_maturity(exp, entry["arm_id"], recs, today, config)
            for entry in cadencearms.arms_of(exp)]
    level = min((row["level"] for row in arms), key=lambda x: RANK[x]) \
        if arms else IMMATURE
    slowest = [row["arm_id"] for row in arms if row["level"] == level]

    return {
        "experiment_id": exp.get("experiment_id"),
        "level": level,
        "level_label": LEVEL_LABEL[level],
        "comparable": level == MATURE,
        "held_back_by": slowest,
        "arms": arms,
        "days_until_mature": max((row["days_until_mature"] for row in arms),
                                 default=0),
        "why": ("every arm has had time" if level == MATURE else
                "the comparison is only as readable as the arm that has had "
                "least time: " + ", ".join(slowest)),
        "note": "a four-step arm finishes on day twelve and a seven-step arm "
                "on day thirty-five. Compared on day fifteen the shorter one "
                "wins on a difference that is entirely when somebody looked",
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.cadencematurity",
                                description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--today")
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
    found = maturity(exp, recs, a.today)
    if a.json:
        print(json.dumps(found, indent=2, default=str))
        return 0

    print(f"{found['level_label'].upper()}"
          + ("" if found["comparable"] else "  - not comparable yet"))
    for row in found["arms"]:
        share = "-" if row["share"] is None else f"{row['share']:.0%}"
        print(f"  {row['arm_id']:<10} {row['level']:<18} "
              f"{row['had_full_chance']}/{row['assigned']} ({share})  "
              f"{row['why']}")
    print("\n" + found["why"])
    print(found["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
