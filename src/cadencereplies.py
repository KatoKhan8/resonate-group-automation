#!/usr/bin/env python3
"""Which step a reply actually followed, and which arm may claim it.

## The question this answers, and the two it refuses to

A cadence experiment asks whether seven steps beat four. The answer turns
almost entirely on *where the replies arrive*: if every reply lands by step
three, steps four to seven cost money and buy nothing, and no comparison of
final totals will show that - both arms will look similar and the longer
one will look slightly better for having had more chances.

So the useful unit is not "this arm got eleven replies". It is "this arm
got eleven replies, and nine of them arrived after step two".

Two things this deliberately does not say:

- **It does not say the step caused the reply.** Last-touch is a reporting
  convention, and the same one `variants.results_from` uses. Somebody who
  replies after step four saw steps one to four; attributing to the last
  one is a choice made for a denominator that means something, not a claim
  about cause. `journey` travels beside every attribution so nobody reads
  it as one.
- **It does not guess.** A reply with no confirmed touch before it is
  reported as unattributed, never as step one. Inbound arrives: somebody
  forwards a message, replies to a different campaign, or answers a
  LinkedIn note nobody has confirmed yet. Counting those against step one
  would credit the opener with replies it never earned, and the opener is
  exactly the step an experiment is trying to judge.

## Before, not last

The touch a reply is attributed to is the last confirmed one *before the
reply's own timestamp*. Not the last confirmed touch overall: a step can
be confirmed after a reply arrives - a provider callback lands late, a
batch was already in flight when somebody answered - and crediting that
step would say a message sent on Tuesday caused a reply received on
Monday.

That is not hypothetical tidiness. It is the direction of the error that
matters: a late confirmation always attaches to a *later* step, so the
bias runs towards making long arms look better, which is the exact
question the experiment exists to settle.

## The denominator is exposure

Contacts who *started* the arm, not contacts assigned to it. Somebody
assigned and then suppressed before step one has not experienced the
cadence, and putting them in the denominator makes every arm look worse in
proportion to how many people it never reached.
"""
import argparse
import json

from . import account, cadencearms, cadenceexposure, evidence

UNATTRIBUTED = "unattributed"


def _at(value):
    return str(value or "")


def attribute_to_step(at, steps):
    """The last confirmed touch at or before `at`, or None.

    `steps` is the arm's own confirmed touches, in order, as
    `cadenceexposure` reports them. Takes a timestamp rather than a reply
    because an unsubscribe is placed in a sequence by exactly the same
    rule, and two copies of this would be two chances to disagree about
    which step somebody was on.
    """
    when = _at(at)
    before = [row for row in steps if _at(row.get("at")) <= when]
    if not before or not when:
        return None
    return before[-1]


def attribute_reply(reply, steps):
    """The last confirmed touch before this reply, or None."""
    return attribute_to_step(reply.get("at"), steps)


def contact_replies(exp, rec, contact, campaign=None):
    """Every reply from one contact, placed in its arm and its sequence.

    `None` when the contact is not in the experiment. An empty list when
    they are in it and have not replied - which is a different fact, and
    the caller needs both.
    """
    exposure = cadenceexposure.contact_exposure(exp, rec, contact, campaign)
    if exposure is None:
        return None

    steps = exposure["steps"]
    order = {row.get("key"): index + 1 for index, row in enumerate(steps)}
    first_touch = _at(steps[0].get("at")) if steps else None

    out = []
    for reply in account.replies(rec, contact.get("key")):
        after = attribute_reply(reply, steps)
        key = (after or {}).get("key")
        out.append({
            "experiment_id": exposure["experiment_id"],
            "arm_id": exposure["arm_id"],
            "record_id": exposure["record_id"],
            "contact_key": exposure["contact_key"],
            "at": reply.get("at"),
            "channel": reply.get("channel"),
            "classification": reply.get("classification"),
            "positive": bool(reply.get("positive")),
            # The step it followed, and how far into the arm that is.
            "after_step": key or UNATTRIBUTED,
            "after_step_index": order.get(key),
            "attributed": key is not None,
            "why_unattributed": None if key else (
                "no confirmed touch on this arm before the reply"),
            # How many of the arm's steps this person had actually seen.
            # The number the incremental-value question is asked of.
            "steps_seen": order.get(key) or 0,
            "planned": exposure["planned"],
            "days_to_reply": evidence.days_between(first_touch,
                                                   reply.get("at")),
            # Every variant they saw, in order, so a last-touch number is
            # never read as a claim about one message alone.
            "journey": [row.get("variant_id") for row in steps
                        if row.get("variant_id")],
        })
    return out


def replies_for(exp, recs, campaign=None):
    """Every attributed reply across a set of records."""
    out = []
    for rec in recs or []:
        for contact in account.contacts_of(rec):
            found = contact_replies(exp, rec, contact, campaign)
            if found:
                out.extend(found)
    return out


def by_arm(exp, recs, campaign=None, positive_only=False):
    """Per arm: who was exposed, who replied, and after which step.

    `exposed` rather than `assigned` is the denominator, so the rate is a
    property of the arm rather than of how many people it never reached.
    """
    rows = cadenceexposure.exposures(exp, recs, campaign)
    answers = replies_for(exp, recs, campaign)

    out = {}
    for entry in cadencearms.arms_of(exp):
        arm_id = entry["arm_id"]
        arm = cadencearms.arm_by_id(exp, arm_id) or {}
        mine = [row for row in rows if row["arm_id"] == arm_id]
        exposed = [row for row in mine if row["started"]]
        theirs = [row for row in answers if row["arm_id"] == arm_id
                  and (row["positive"] if positive_only else True)]

        # One contact may reply more than once. The arm's rate is a rate of
        # people, not of messages, so the first reply is the one counted -
        # a second reply from somebody already counted is not a second
        # success and would inflate a long arm, which has more chances.
        first = {}
        for row in sorted(theirs, key=lambda r: _at(r["at"])):
            first.setdefault((row["record_id"], row["contact_key"]), row)
        counted = list(first.values())

        after = {}
        for row in counted:
            after[row["after_step"]] = after.get(row["after_step"], 0) + 1

        attributed = [row for row in counted if row["attributed"]]
        indexes = sorted(row["after_step_index"] for row in attributed)
        out[arm_id] = {
            "arm_id": arm_id,
            "label": arm.get("label"),
            "steps": len(arm.get("steps") or []),
            "assigned": len(mine),
            "exposed": len(exposed),
            "replies": len(counted),
            "attributed": len(attributed),
            "unattributed": len(counted) - len(attributed),
            "rate": (len(counted) / len(exposed)) if exposed else None,
            "after_step": after,
            # Where the replies actually arrive. The whole argument for
            # running the experiment at all.
            "median_step": (indexes[len(indexes) // 2] if indexes else None),
            "latest_step": (indexes[-1] if indexes else None),
            "note": "denominator is contacts who started the arm; a reply "
                    "with no confirmed touch before it is unattributed "
                    "rather than credited to step one",
        }
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.cadencereplies",
                               description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--positive", action="store_true",
                   help="count positive replies only")
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
    found = by_arm(exp, recs, campaign, positive_only=a.positive)
    if a.json:
        print(json.dumps(found, indent=2, default=str))
        return 0

    for arm_id, row in sorted(found.items()):
        rate = "-" if row["rate"] is None else f"{row['rate']:.1%}"
        print(f"{arm_id:<10} {row['steps']} steps  "
              f"{row['replies']}/{row['exposed']} ({rate})  "
              f"median after step {row['median_step'] or '-'}")
        for step, count in sorted(row["after_step"].items()):
            print(f"    after {step:<14} {count}")
        if row["unattributed"]:
            print(f"    {row['unattributed']} unattributed - no confirmed "
                  "touch before the reply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
