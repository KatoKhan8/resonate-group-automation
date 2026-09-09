#!/usr/bin/env python3
"""Which cohorts are doing better, said carefully enough to act on.

## What this is allowed to conclude

That a cohort's observed rate is higher than the workspace baseline, with
enough evidence that the difference is unlikely to be noise. That is all.

It is **observational**. Every account in a cohort was chosen by somebody,
worked by somebody, and written to with copy somebody wrote. When German
agencies of fifty to a hundred people reply more often, the honest
sentence is "these accounts replied more often", not "being a German
agency causes replies". The difference matters because the second sentence
invites a decision - target more German agencies - that the evidence does
not support on its own.

So `describe()` returns rates, counts and an interval, and the word
"observed" appears in every summary. There is no `cause` field, no
`because`, and no recommendation phrased as an instruction.

## What it may never do

**Move the ICP.** A cohort performing badly is not a reason to narrow what
the client sells to; it may be a reason to look. `recommend()` returns
suggestions a person accepts or ignores, and there is no code path from
here to `qualify`. See GTM-STRATEGY.md: canonical strategy changes are
explicit human decisions, recorded with their basis.

**Override a refusal.** A cohort boost may raise attention. It cannot make
a suppressed account eligible, cannot outrank a DNC, a client ruling, an
account hold or fatigue. `boost()` returns a bounded number and the
eligibility layer never consults it.

**Cross a workspace.** What worked for one client is not evidence about
another's market, and treating it as such would leak one client's
performance into another's targeting.

## Small samples

The failure this is built against is optimising on four replies against
three. A cohort below the floor is `INSUFFICIENT_DATA` and gets no state,
no lift and no recommendation - not a cautious one, none. The Wilson lower
bound is used rather than the raw rate for the same reason it is used in
`variants`: a plain proportion says one reply from one send is a hundred
per cent.
"""
from . import variants

# ------------------------------------------------------------------ outcomes
#
# What counts as the thing worth having. Opens and clicks are deliberately
# absent: they measure whether a message was rendered, and optimising for
# them optimises for subject lines that get opened by people who then do
# nothing.

CONTACTED = "contacted"
REPLIED = "replied"
POSITIVE = "positive"
MEETING = "meeting"

OUTCOMES = (REPLIED, POSITIVE, MEETING)

OUTCOME_LABEL = {
    REPLIED: "replied",
    POSITIVE: "replied positively",
    MEETING: "booked a meeting",
}

# The default question. Positive replies rather than any reply: a cohort
# that generates many "no thank you"s is not performing.
DEFAULT_OBJECTIVE = POSITIVE

# ------------------------------------------------------------------- states

INSUFFICIENT_DATA = "insufficient_data"
EARLY_SIGNAL = "early_signal"
PROMISING = "promising"
HIGH_CONFIDENCE = "high_confidence"
NO_DIFFERENCE = "no_difference"
DECLINING = "declining"

STATES = (INSUFFICIENT_DATA, EARLY_SIGNAL, PROMISING, HIGH_CONFIDENCE,
          NO_DIFFERENCE, DECLINING)

STATE_LABEL = {
    INSUFFICIENT_DATA: "Not enough yet to say anything",
    EARLY_SIGNAL: "Something, but it could still be noise",
    PROMISING: "Ahead of the baseline",
    HIGH_CONFIDENCE: "Clearly ahead of the baseline",
    NO_DIFFERENCE: "No different from the baseline",
    DECLINING: "Behind the baseline",
}

DEFAULTS = {
    # Below this a cohort says nothing at all. Chosen so a handful of
    # replies cannot produce a state.
    "minimum_contacted": 40,
    "minimum_outcomes": 6,
    # How far ahead of the baseline before it is worth mentioning.
    "minimum_lift": 0.30,
    # The most a cohort may add to an account's priority, as a fraction of
    # the score. Small on purpose: this is one input among five and it is
    # the least well established of them.
    "maximum_boost": 0.10,
    # Confidence: a cohort is only "clear" when its lower bound is above
    # the baseline's own rate.
    "confident_at": 80,
}


def settings(config=None):
    found = dict(DEFAULTS)
    block = ((config or {}).get("learning") or {})
    for key, value in block.items():
        if key in found and value is not None:
            try:
                found[key] = type(DEFAULTS[key])(value)
            except (TypeError, ValueError):
                pass
    return found


# ------------------------------------------------------------------ cohorts
#
# The dimensions a cohort can be cut on. Every one is canonical state that
# something else already decided - this module joins and counts, which is
# the only arithmetic a learning surface should be doing.

DIMENSIONS = ("country", "region", "vertical", "industry", "employee_band",
              "icp_tier", "persona", "angle", "channel", "playbook",
              "signal_type", "discovery_source")


def cohort_key(row, dimensions):
    """The tuple that identifies a cohort, or None if the row cannot fill it.

    A row missing one of the dimensions is *excluded* rather than bucketed
    under "unknown". An "unknown country" cohort is not a market segment,
    it is a data-quality report wearing one, and acting on it would mean
    acting on the accounts we know least about.
    """
    values = []
    for name in dimensions:
        value = row.get(name)
        if value in (None, "", "unknown", "UNKNOWN", "none"):
            return None
        values.append(str(value))
    return tuple(values)


def _rate(successes, trials):
    return (successes / float(trials)) if trials else 0.0


def baseline(rows, objective=DEFAULT_OBJECTIVE):
    """The workspace's own rate. Every cohort is measured against this.

    Not an industry benchmark: what this workspace actually does is the
    only fair comparison, because the copy, the senders and the ICP are
    all held roughly constant within it.
    """
    contacted = sum(1 for row in rows if row.get(CONTACTED))
    hits = sum(1 for row in rows if row.get(CONTACTED) and row.get(objective))
    return {
        "objective": objective,
        "contacted": contacted,
        "outcomes": hits,
        "rate": _rate(hits, contacted),
        "why": (f"{hits} of {contacted} contacted accounts "
                f"{OUTCOME_LABEL[objective]}" if contacted
                else "nothing has been contacted in this workspace yet"),
    }


def describe(rows, dimensions, config=None, objective=DEFAULT_OBJECTIVE):
    """Every cohort on these dimensions, with what can honestly be said.

    `rows` is one row per account: the dimensions it belongs to, whether it
    was contacted, and which outcomes it produced. Building that is the
    caller's job, because it is the caller that holds the workspace scope.
    """
    policy = settings(config)
    base = baseline(rows, objective)

    buckets = {}
    skipped = 0
    for row in rows:
        if not row.get(CONTACTED):
            continue
        key = cohort_key(row, dimensions)
        if key is None:
            skipped += 1
            continue
        found = buckets.setdefault(key, {"contacted": 0, "outcomes": 0})
        found["contacted"] += 1
        if row.get(objective):
            found["outcomes"] += 1

    cohorts = []
    for key, counts in buckets.items():
        cohorts.append(_assess(key, dimensions, counts, base, policy,
                               objective))
    cohorts.sort(key=lambda c: (-c["rate"], c["cohort"]))

    return {
        "objective": objective,
        "dimensions": list(dimensions),
        "baseline": base,
        "cohorts": cohorts,
        "cohorts_with_enough_data": len(
            [c for c in cohorts if c["state"] != INSUFFICIENT_DATA]),
        # Named rather than dropped: a large number here means the cohort
        # cut is mostly measuring what is missing from the data.
        "skipped_incomplete": skipped,
        "floor": {"contacted": policy["minimum_contacted"],
                  "outcomes": policy["minimum_outcomes"]},
        "note": ("Observed rates. Every account here was chosen, worked and "
                 "written to by somebody, so a difference between cohorts is "
                 "a difference between those campaigns as much as between "
                 "the cohorts themselves."),
    }


def _assess(key, dimensions, counts, base, policy, objective):
    contacted = counts["contacted"]
    outcomes = counts["outcomes"]
    rate = _rate(outcomes, contacted)
    label = " / ".join(key)

    row = {
        "cohort": label,
        "parts": dict(zip(dimensions, key)),
        "contacted": contacted,
        "outcomes": outcomes,
        "rate": rate,
        "baseline_rate": base["rate"],
    }

    if (contacted < policy["minimum_contacted"]
            or outcomes < policy["minimum_outcomes"]):
        # No state, no lift, no recommendation. Not a cautious one - none.
        return {
            **row,
            "state": INSUFFICIENT_DATA,
            "state_label": STATE_LABEL[INSUFFICIENT_DATA],
            "lift": None,
            "low": None,
            "why": (f"{contacted} contacted and {outcomes} "
                    f"{OUTCOME_LABEL[objective]}; this says nothing until "
                    f"{policy['minimum_contacted']} and "
                    f"{policy['minimum_outcomes']}"),
        }

    low = variants.wilson_low(outcomes, contacted)
    lift = ((rate - base["rate"]) / base["rate"]) if base["rate"] else None

    if base["rate"] and low > base["rate"]:
        state = HIGH_CONFIDENCE
    elif lift is not None and lift >= policy["minimum_lift"]:
        state = PROMISING
    elif lift is not None and lift <= -policy["minimum_lift"]:
        state = DECLINING
    elif lift is not None:
        state = NO_DIFFERENCE
    else:
        state = EARLY_SIGNAL

    return {
        **row,
        "state": state,
        "state_label": STATE_LABEL[state],
        "lift": lift,
        "low": low,
        "why": (f"{outcomes} of {contacted} {OUTCOME_LABEL[objective]} "
                f"({rate:.1%}) against a workspace baseline of "
                f"{base['rate']:.1%}"
                + (f", about {1 + lift:.1f}x" if lift and lift > 0 else "")),
    }


# --------------------------------------------------------------- what to do

def recommend(described, config=None):
    """Suggestions a person accepts or ignores. Nothing here acts.

    Phrased as things to consider rather than as instructions, because the
    evidence is observational and the reader is the one who knows what else
    was true about those campaigns.
    """
    policy = settings(config)
    out = []
    for cohort in described["cohorts"]:
        if cohort["state"] == HIGH_CONFIDENCE:
            out.append({
                "kind": "prioritise",
                "cohort": cohort["cohort"],
                "what": f"Consider prioritising {cohort['cohort']}",
                "why": cohort["why"],
                "state": cohort["state"],
            })
        elif cohort["state"] == DECLINING:
            out.append({
                "kind": "examine",
                "cohort": cohort["cohort"],
                "what": f"Consider looking at why {cohort['cohort']} is "
                        "behind",
                # Deliberately not "stop targeting". A cohort can be behind
                # because the copy for it was weak, which is a different
                # problem with a different fix.
                "why": cohort["why"] + ". This may be the cohort, the copy, "
                       "the senders or the timing - the number does not say "
                       "which",
                "state": cohort["state"],
            })
    return {
        "recommendations": out,
        "considered": len(described["cohorts"]),
        "with_enough_data": described["cohorts_with_enough_data"],
        "note": ("Suggestions. None of these changes anything until a person "
                 "decides, and none of them can change the ICP - that is an "
                 "explicit decision recorded with its basis."),
    }


def boost(cohort, config=None):
    """How much a cohort's performance may add to an account's priority.

    Bounded and small. This is one input among five in `priority`, and it
    is the least well established of them - it rests on observed rates
    from campaigns that differed in other ways too.

    It cannot make anything eligible. `hygiene` and `eligibility` decide
    that and never consult this.
    """
    policy = settings(config)
    if not cohort or cohort.get("state") != HIGH_CONFIDENCE:
        return 0.0
    lift = cohort.get("lift") or 0.0
    if lift <= 0:
        return 0.0
    return round(min(policy["maximum_boost"], lift * 0.05), 4)
