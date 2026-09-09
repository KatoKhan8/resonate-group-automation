#!/usr/bin/env python3
"""What each step adds, and where a sequence stops paying for itself.

## The question a total cannot answer

"The seven-step arm got 34 replies and the four-step arm got 29" is the
wrong number to look at, because it cannot distinguish two very different
worlds: one where steps five to seven earned five replies, and one where
they earned none and the difference is noise. Both produce the same
totals.

The number that decides whether to run three more steps is the *marginal*
one: of the people who reached step five, how many replied after it.

## The denominator is who reached that step, never who was in the arm

Steps late in a sequence are seen by fewer people - some replied, some
unsubscribed, some are still waiting for the date to arrive. Dividing a
late step's replies by the whole arm makes every sequence look like it
decays, whether it does or not, because the denominator is the same while
the population shrinks.

So step five's rate is over the people who actually reached step five.

## Survivorship is a fact here, not a bias to remove

The people who reach step five are exactly the people who did not reply to
steps one through four. That is a harder audience by construction, and the
rate at step five is *conditional* on having survived to it.

That conditioning is not a flaw to correct - it is the decision. "If I add
a fifth step, what happens to the people still there?" is a question about
survivors, and the survivors are who the fifth step would be sent to.
Reported as `conditional` on every row so nobody reads the number as an
unconditional one.

## What it refuses to say

An empty column is not evidence of nothing. Zero replies after step six
means one of two things - the step earns nothing, or nine people reached
it - and those are not the same finding. A step below the minimum reach
is `TOO_FEW` and never `NO_EVIDENCE`, and a sequence with a `TOO_FEW`
anywhere after the settling point has no settling point at all.
"""
import argparse
import json

from . import cadencearms, cadenceexposure, cadencereplies, variants

PAYS = "pays"
NO_EVIDENCE = "no_evidence"
TOO_FEW = "too_few"

VERDICTS = (PAYS, NO_EVIDENCE, TOO_FEW)

VERDICT_LABEL = {
    PAYS: "replies arrive after this step",
    NO_EVIDENCE: "enough people reached it and none replied after it",
    TOO_FEW: "too few reached it to say anything",
}

DEFAULTS = {
    # Below this many people reaching a step, its column says nothing. The
    # same threshold `variants.evaluate` uses for exposures per variant,
    # for the same reason and deliberately not a second number.
    "minimum_reached": 30,
}


def settings(config):
    merged = dict(DEFAULTS)
    merged.update(((config or {}).get("cadence_value") or {}))
    return merged


def _verdict(reached, replies, minimum):
    if replies > 0:
        return PAYS
    if reached >= minimum:
        return NO_EVIDENCE
    return TOO_FEW


def step_value(exp, recs, arm_id, campaign=None, positive_only=False,
               config=None):
    """One row per position in the arm: who reached it, who replied after.

    Position is ordinal in what a contact actually saw, not in what was
    scheduled for them - a contact whose second step was skipped because a
    channel was closed reached position two when their next step landed.
    `cadencereplies` places replies by the same ordinal, so the two agree.
    """
    policy = settings(config)
    arm = cadencearms.arm_by_id(exp, arm_id) or {}
    planned = list(arm.get("steps") or [])

    rows = [row for row in cadenceexposure.exposures(exp, recs, campaign)
            if row["arm_id"] == arm_id]
    answers = [row for row in cadencereplies.replies_for(exp, recs, campaign)
               if row["arm_id"] == arm_id
               and (row["positive"] if positive_only else True)]

    # One reply per person, the first, for the same reason as in
    # `cadencereplies.by_arm`: a longer arm has more chances to be answered
    # twice and must not be paid for it.
    first = {}
    for row in sorted(answers, key=lambda r: str(r.get("at") or "")):
        first.setdefault((row["record_id"], row["contact_key"]), row)
    counted = list(first.values())

    exposed = [row for row in rows if row["started"]]
    out, running = [], 0
    for index in range(1, len(planned) + 1):
        reached = [row for row in rows if row["reached"] >= index]
        replies = [row for row in counted if row["after_step_index"] == index]
        running += len(replies)
        rate = (len(replies) / len(reached)) if reached else None
        out.append({
            "index": index,
            "step": planned[index - 1].get("key"),
            "day": planned[index - 1].get("day"),
            "channel": planned[index - 1].get("channel"),
            # The two numbers this module exists to keep together.
            "reached": len(reached),
            "replies": len(replies),
            "rate": rate,
            "low": (variants.wilson_low(len(replies), len(reached))
                    if reached else None),
            "high": (variants.wilson_high(len(replies), len(reached))
                     if reached else None),
            # Of everybody who started the arm. Not the same question, and
            # a screen that shows only one of them misleads either way.
            "cumulative_replies": running,
            "cumulative_rate": (running / len(exposed)) if exposed else None,
            "verdict": _verdict(len(reached), len(replies),
                                int(policy["minimum_reached"])),
            "conditional": index > 1,
            "why_conditional": (
                None if index == 1 else
                f"rate among people who did not reply to steps 1-{index - 1}"),
        })
    return out


def settles_at(steps, config=None):
    """The first step after which nothing more arrives, or None.

    None is the common answer and the honest one. A sequence has a
    settling point only when every step from some position onward reached
    enough people to have shown a reply and showed none. One `too_few`
    after that position and there is no answer yet - a column that is
    empty because nobody got there is not a column that earned nothing.
    """
    if not steps:
        return None, "no steps"
    for index in range(len(steps)):
        rest = steps[index:]
        # A `too_few` anywhere in `rest` fails this test on its own, which
        # is why there is no separate check for one: an empty column that
        # nobody reached is not a column that earned nothing.
        if all(row["verdict"] == NO_EVIDENCE for row in rest):
            if index == 0:
                return None, ("nothing arrived after any step; this is not a "
                              "settling point, it is an arm with no replies")
            settled = steps[index - 1]
            return settled["index"], (
                f"replies stop after step {settled['index']} "
                f"({settled['step']}); every step after it reached at least "
                "the minimum and produced none")
    thin = [row["index"] for row in steps if row["verdict"] == TOO_FEW]
    if thin:
        return None, ("too few people have reached step"
                      + ("s " if len(thin) > 1 else " ")
                      + ", ".join(str(i) for i in thin)
                      + " to say whether the sequence stops paying")
    return None, "replies are still arriving at the last step"


def curve(exp, recs, arm_id, campaign=None, positive_only=False,
          config=None):
    """The whole arm: per-step value, and where it flattens if it does."""
    steps = step_value(exp, recs, arm_id, campaign, positive_only, config)
    settled, why = settles_at(steps, config)
    paying = [row["index"] for row in steps if row["verdict"] == PAYS]
    return {
        "experiment_id": exp.get("experiment_id"),
        "arm_id": arm_id,
        "steps": steps,
        "settles_at": settled,
        "why": why,
        "last_paying_step": paying[-1] if paying else None,
        # What could be removed if the settling point holds. Reported, not
        # recommended: this module measures, it does not decide.
        "steps_after_settling": (
            [row["step"] for row in steps if settled and row["index"] > settled]
            if settled else []),
        "note": "each rate is over the people who reached that step, and is "
                "conditional on their not having replied to an earlier one",
    }


def compare(exp, recs, campaign=None, positive_only=False, config=None):
    """Every arm's curve, side by side."""
    return {entry["arm_id"]: curve(exp, recs, entry["arm_id"], campaign,
                                   positive_only, config)
            for entry in cadencearms.arms_of(exp)}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.cadencevalue",
                                description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--arm")
    p.add_argument("--positive", action="store_true")
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

    found = (compare(exp, recs, campaign, a.positive) if not a.arm
             else {a.arm: curve(exp, recs, a.arm, campaign, a.positive)})
    if a.json:
        print(json.dumps(found, indent=2, default=str))
        return 0

    for arm_id, row in sorted(found.items()):
        print(f"\n{arm_id}")
        for step in row["steps"]:
            rate = "-" if step["rate"] is None else f"{step['rate']:.1%}"
            print(f"  {step['index']}. {str(step['step']):<8} "
                  f"{step['replies']:>3}/{step['reached']:<5} {rate:>6}  "
                  f"{step['verdict']}")
        print(f"  -> {row['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
