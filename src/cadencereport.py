#!/usr/bin/env python3
"""One cadence experiment, everything known about it, and what may be said.

## Five questions, already answered elsewhere

    cadenceexposure   who actually experienced each arm
    cadencematurity   whether enough time has passed to compare them
    cadencereplies    what each arm earned, and after which step
    cadencevalue      what each individual step added
    cadencesafety     what it cost the people who received it

This assembles them. It computes nothing of its own about outcomes, which
is deliberate: a reporting layer that recalculated a rate would be a second
answer to a question that already has one, and the two would drift.

## It does not own a verdict either

The statistical question - k cells, exposures, outcomes, is anything
separated - is the same question `variants.evaluate` already answers for
copy, with the same Wilson intervals and the same refusal to call four
replies against three. So the arms are adapted into the shape it expects
and it decides. One evaluator, one set of thresholds, one place to correct
a mistake in either.

Thresholds may be raised for cadence under `cadence_experiments` in a
workspace config, because an arm needs more people than a wording does.
Absent that, copy's thresholds apply.

## Maturity outranks the statistics

An evaluator handed a four-step arm and a seven-step arm on day fifteen
will happily find a winner, and it will be the short arm, and the finding
will be about the calendar. So a verdict is never actionable while any arm
is still immature, whatever the intervals say.

That gate is the reason this module exists rather than a screen calling
`variants.evaluate` directly.

## Every refusal is named

`refusals` lists each reason a stronger statement was not made, in the
order they were checked. A report that says "no clear winner" and does not
say whether that is for want of time, for want of people, or because the
arms genuinely perform alike is a report that gets read as the last of the
three.
"""
import argparse
import json

from . import (cadencearms, cadenceexposure, cadencematurity, cadencereplies,
               cadencesafety, cadencevalue, piiredact, variants)

IMMATURE = "immature"
NO_WINNER = "no_winner"
SAFETY_DISAGREES = "safety_disagrees"

REFUSAL_LABEL = {
    IMMATURE: "not every arm has had time to run",
    NO_WINNER: "the arms are not separated by more than their intervals",
    SAFETY_DISAGREES: "the leading arm also costs more",
}


def thresholds(config=None):
    """Copy's thresholds, unless this workspace raised them for cadence.

    Returned in the shape `variants.settings` reads, so the evaluator is
    configured rather than reimplemented.
    """
    override = ((config or {}).get("cadence_experiments") or {})
    if not override:
        return config
    merged = dict(config or {})
    merged["experiments"] = {**((config or {}).get("experiments") or {}),
                             **override}
    return merged


def as_node(exp, objective=None):
    """The arms in the shape `variants.evaluate` reads.

    An adapter built at read time, not a second store: the arms stay where
    they are and this is thrown away with the report. `style` carries the
    arm's label so the verdict sentence names "7 steps" rather than an id.
    """
    return {
        "type": "email",
        "objective": objective or variants.DEFAULT_OBJECTIVE,
        "variants": [
            {"variant_id": entry["arm_id"],
             "style": (cadencearms.arm_by_id(exp, entry["arm_id"]) or {}
                       ).get("label") or entry["arm_id"],
             "status": variants.ACTIVE}
            for entry in cadencearms.arms_of(exp)],
    }


def as_results(replies, objective):
    return {arm_id: {"exposures": row["exposed"], objective: row["replies"]}
            for arm_id, row in replies.items()}


def report(exp, recs, campaign=None, today=None, config=None, objective=None):
    """Everything known about one experiment, and what may be said of it."""
    objective = objective or variants.DEFAULT_OBJECTIVE
    positive = objective == variants.POSITIVE_REPLIES

    maturity = cadencematurity.maturity(exp, recs, today, config)
    exposure = cadenceexposure.summarise(exp, recs, campaign)
    replies = cadencereplies.by_arm(exp, recs, campaign,
                                    positive_only=positive)
    safety = cadencesafety.compare(exp, recs, campaign)
    value = cadencevalue.compare(exp, recs, campaign, positive_only=positive,
                                 config=config)

    evaluation = variants.evaluate(as_node(exp, objective),
                                   as_results(replies, objective),
                                   config=thresholds(config),
                                   objective=objective)

    refusals = []
    if not maturity["comparable"]:
        refusals.append({
            "code": IMMATURE, "label": REFUSAL_LABEL[IMMATURE],
            "why": maturity["why"],
            "days_until_mature": maturity["days_until_mature"]})
    if evaluation["state"] != variants.WINNER:
        refusals.append({
            "code": NO_WINNER, "label": REFUSAL_LABEL[NO_WINNER],
            "why": evaluation["why"], "days_until_mature": None})

    leader = evaluation.get("leader")
    if leader and leader in (safety.get("costs_more") or []):
        refusals.append({
            "code": SAFETY_DISAGREES, "label": REFUSAL_LABEL[SAFETY_DISAGREES],
            "why": safety["why"], "days_until_mature": None})

    actionable = not refusals
    arms = []
    for entry in cadencearms.arms_of(exp):
        arm_id = entry["arm_id"]
        arm = cadencearms.arm_by_id(exp, arm_id) or {}
        arms.append({
            "arm_id": arm_id,
            "label": arm.get("label"),
            "steps": len(arm.get("steps") or []),
            "shape": _shape(arm),
            "maturity": next((row for row in maturity["arms"]
                              if row["arm_id"] == arm_id), None),
            "replies": replies.get(arm_id),
            "safety": (safety.get("arms") or {}).get(arm_id),
            "value": value.get(arm_id),
        })

    return _safe_text({
        "experiment_id": exp.get("experiment_id"),
        "objective": objective,
        "objective_label": variants.OBJECTIVE_LABEL.get(objective, objective),
        "arms": arms,
        "exposure": exposure,
        "maturity": maturity,
        "evaluation": evaluation,
        "safety": safety,
        # The whole point of the module: a verdict is only actionable when
        # nothing above refused, and every refusal is named rather than
        # collapsed into "no clear winner".
        "actionable": actionable,
        "leader": leader if actionable else None,
        "refusals": refusals,
        "headline": headline(maturity, evaluation, refusals, actionable),
        "note": "every rate here is computed by the module that owns the "
                "question; this assembles them and adds none of its own",
    })


def _safe_text(value):
    """Walk a structure and redact every string through piiredact.

    A report dict can carry a forbidden domain in an arm label, a headline,
    or a refusal reason.  Walking rather than redacting at one known field
    means a new field that happens to hold text is covered without a
    separate change here.  Non-string leaves are returned unchanged.
    """
    if isinstance(value, str):
        return piiredact.redact(value)
    if isinstance(value, dict):
        return {k: _safe_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_text(item) for item in value]
    return value


def _shape(arm):
    """`E -> E -> LI -> E`. Not guarded: an arm whose steps cannot be
    described is one `cadencearms.validate` should have refused, and
    swallowing that here would hide a validation gap behind a missing
    label."""
    from . import cadence

    return cadence.describe_steps(arm.get("steps") or [])


def headline(maturity, evaluation, refusals, actionable):
    """One sentence, and the reason underneath it."""
    if actionable:
        return f"{evaluation['why']}."
    first = refusals[0]
    if first["code"] == IMMATURE:
        days = first.get("days_until_mature")
        return ("Too early to read: " + first["why"]
                + (f"; about {days} days to go." if days else "."))
    return f"No decision yet: {first['why']}."


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.cadencereport",
                                description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--today")
    p.add_argument("--objective", default=variants.DEFAULT_OBJECTIVE,
                   choices=list(variants.OBJECTIVES))
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
    found = report(exp, recs, campaign, today=a.today,
                   objective=a.objective)
    if a.json:
        print(json.dumps(found, indent=2, default=str))
        return 0

    print(found["headline"] + "\n")
    for arm in found["arms"]:
        rep = arm["replies"] or {}
        safe = arm["safety"] or {}
        rate = "-" if rep.get("rate") is None else f"{rep['rate']:.1%}"
        harm = "-" if safe.get("rate") is None else f"{safe['rate']:.1%}"
        print(f"  {arm['arm_id']:<10} {arm['steps']} steps  "
              f"{arm['shape'] or '':<24} "
              f"replies {rep.get('replies', 0)}/{rep.get('exposed', 0)} "
              f"({rate})   cost {safe.get('harmed', 0)}/"
              f"{safe.get('exposed', 0)} ({harm})")
        settled = (arm["value"] or {}).get("settles_at")
        if settled:
            print(f"             replies stop after step {settled}")
    if found["refusals"]:
        print("\n  not acted on because:")
        for row in found["refusals"]:
            print(f"    - {row['label']}: {row['why']}")
    print("\n" + found["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
