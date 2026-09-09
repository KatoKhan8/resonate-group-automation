#!/usr/bin/env python3
"""Why this account, and why now - as arithmetic somebody can argue with.

## The number is the least interesting part

"AI says 92" is not a score, it is an assertion. What an operator needs is
the *decomposition*: how much of this is fit, how much is something that
just happened, how much is that we already know somebody there. Those are
different questions with different remedies - a poor fit is a targeting
problem and a stale signal is a timing problem - and a single number hides
which one you have.

So every score returns its own components, each with the evidence behind
it, and the screen shows the working.

## Five components, and they are deliberately not comparable

    ICP FIT           does this company match what the client sells to
    SIGNAL STRENGTH   is anything happening there
    TIMING            is what is happening still current
    PERSONA COVERAGE  do we have the right people, verified
    ENGAGEMENT        have we already got somewhere

Weights are per workspace, because the mix that matters for one client is
not the mix for another. The defaults lean on fit and engagement, because
those are the two we measure most reliably.

## Priority is not permission

The most important line in this module. A score says *worth attention*; it
says nothing about whether anything may be sent. `hygiene` and
`eligibility` decide that, they outrank this completely, and
`assess()` reports the eligibility verdict beside the score precisely so
that no screen can show one without the other.

A suppressed account can score 90. It is still suppressed.
"""
from . import accountpolicy as ap, signals as signal_module

ICP_FIT = "icp_fit"
SIGNAL_STRENGTH = "signal_strength"
TIMING = "timing"
PERSONA_COVERAGE = "persona_coverage"
ENGAGEMENT = "engagement"
COMPONENTS = (ICP_FIT, SIGNAL_STRENGTH, TIMING, PERSONA_COVERAGE, ENGAGEMENT)

COMPONENT_LABEL = {
    ICP_FIT: "Fits the ICP",
    SIGNAL_STRENGTH: "Something is happening",
    TIMING: "It is still current",
    PERSONA_COVERAGE: "We have the right people",
    ENGAGEMENT: "We have got somewhere before",
}

# Per workspace. These lean on fit and engagement because they are the two
# components measured most reliably - signal strength depends on sources
# that do not exist yet, so weighting it heavily would be weighting a
# number that is mostly zero.
DEFAULT_WEIGHTS = {
    ICP_FIT: 0.35,
    SIGNAL_STRENGTH: 0.20,
    TIMING: 0.10,
    PERSONA_COVERAGE: 0.15,
    ENGAGEMENT: 0.20,
}

# What "held" means, as a sentence rather than a category name. These
# strings reach a client-facing reporting dimension, and "held:
# unclassified" - true, and meaningless to anybody who does not already
# know the taxonomy - is not good enough there.
HELD_BECAUSE = {
    ap.POSITIVE: "held: someone replied and a person is handling it",
    ap.NEUTRAL: "held: someone replied and a person is handling it",
    ap.NEGATIVE: "held: they told us they are not interested",
    ap.NOT_NOW: "held: they asked us to come back later",
    ap.NOT_ICP: "held: they told us they are not a fit",
    ap.REFERRAL: "held: we were passed on to somebody else here",
    ap.EXISTING_CLIENT: "held: they are already a client",
    ap.WRONG_PERSON: "held: we reached the wrong person",
    ap.LEFT_COMPANY: "held: the person we knew has left",
    ap.UNKNOWN: "held: a reply nobody has classified yet",
}

HIGH = "high"
MEDIUM = "medium"
LOW = "low"
TIERS = (HIGH, MEDIUM, LOW)
DEFAULT_THRESHOLDS = {HIGH: 70, MEDIUM: 40}

TIER_LABEL = {HIGH: "High priority", MEDIUM: "Medium priority",
              LOW: "Low priority"}


def weights(config=None):
    """Component weights in force, normalised so they sum to one."""
    found = dict(DEFAULT_WEIGHTS)
    override = ((config or {}).get("priority") or {}).get("weights") or {}
    for key, value in override.items():
        if key in found and value is not None:
            found[key] = float(value)
    total = sum(found.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: v / total for k, v in found.items()}


def thresholds(config=None):
    found = dict(DEFAULT_THRESHOLDS)
    override = ((config or {}).get("priority") or {}).get("tiers") or {}
    for key, value in override.items():
        if key in found and value is not None:
            found[key] = float(value)
    return found


def tier_of(score, config=None):
    limits = thresholds(config)
    if score >= limits[HIGH]:
        return HIGH
    if score >= limits[MEDIUM]:
        return MEDIUM
    return LOW


# ------------------------------------------------------------ components

def _icp_fit(rec):
    """From the verdict `qualify` already stored. Never recomputed here.

    A second opinion about ICP would be a second ICP, and the client
    configured one. The verdict lives at `qualification.verdict`, which is
    where `qualify.company` writes it - reading anywhere else scores every
    account zero and looks exactly like a working scorer.
    """
    verdict = ((rec.get("qualification") or {}).get("verdict") or {})
    status = verdict.get("icp_status")
    score = verdict.get("icp_score")
    tier = verdict.get("icp_tier")

    if score is None and status is None:
        return 0.0, "no ICP verdict recorded yet", None
    if status == "rejected":
        reasons = verdict.get("classification_reasons") or []
        return (0.0,
                "ICP rejected"
                + (f": {reasons[0]}" if reasons else ""), 0)
    if score is None:
        return 0.5, f"ICP {status}, no score recorded", None

    # `icp_score` is 0..100 here. Kept in its own units for the sentence and
    # normalised only for the weighted sum.
    return (max(0.0, min(1.0, float(score) / 100.0)),
            f"ICP score {float(score):g}"
            + (f", tier {tier}" if tier else "")
            + f" ({status or 'unscored'})",
            score)


def _persona_coverage(rec, config=None, suppressed=None):
    """Do we have the people, and can we actually reach them?

    Counts *verified reachability*, not contacts found: three unverified
    addresses are not coverage, and treating them as coverage is how an
    account looks ready and then produces nothing.

    `suppressed` is passed in rather than loaded here. `channels.evaluate`
    reads the suppression file when it is not given one, which is once per
    contact - fine for one account and a few thousand file reads across a
    workspace.
    """
    from . import account, channels

    contacts = [c for c in account.contacts_of(rec) if c.get("selected")]
    if not contacts:
        return 0.0, "no decision maker selected yet", 0
    reachable = 0
    for contact in contacts:
        # (rec, contact) - not (contact, rec). Reversed, every verdict came
        # back useless and the exception guard below hid it.
        verdict = channels.evaluate(rec, contact, config, suppressed)
        if verdict and verdict.get("mode") not in (None, channels.NONE):
            reachable += 1
    # Three reachable decision makers is full marks: an account-based
    # sequence does not get better with a fourth, it gets noisier.
    score = min(1.0, reachable / 3.0)
    return (score,
            f"{reachable} of {len(contacts)} selected decision maker(s) "
            f"reachable on a verified channel",
            reachable)


def _engagement(rec, config=None):
    """How far we have already got. Positive replies dominate deliberately."""
    from . import account

    contacts = account.contacts_of(rec)
    best, why = 0.0, "nobody here has replied"
    for contact in contacts:
        key = contact.get("key")
        replies = account.replies(rec, key)
        if not replies:
            continue
        outcome = ap.classify_outcome(rec, key)
        name = contact.get("name") or key
        if outcome == ap.POSITIVE:
            return 1.0, f"{name} replied positively", outcome
        if outcome in (ap.REFERRAL, ap.EXISTING_CLIENT):
            best, why = max(best, 0.8), f"{name}: {outcome.replace('_', ' ')}"
        elif outcome == ap.NOT_NOW:
            best, why = max(best, 0.5), f"{name} asked us to come back later"
        else:
            best, why = max(best, 0.3), f"{name} replied"
    if best == 0.0:
        touched = [c for c in contacts
                   if account.touches(rec, c.get("key"), confirmed_only=True)]
        if touched:
            return 0.15, f"{len(touched)} contact(s) written to, no reply yet", None
    return best, why, None


def assess(rec, workspace=None, config=None, extra_signals=None, now=None,
           suppressed=None, signal_index=None):
    """This account's priority, its components, and whether it is eligible.

    `extra_signals` are signals from outside the event log - manual or, one
    day, a provider. First-party ones are derived here rather than passed
    in, so a caller cannot forget them.

    The eligibility verdict travels with the score and is not part of it.
    That separation is the point: priority is worth-attention, eligibility
    is may-we-send, and a screen that showed the first without the second
    would be inviting somebody to write to a suppressed account.
    """
    from . import hygiene

    workspace = workspace or rec.get("client")
    found = list(signal_module.derive(rec, workspace, config, now))
    # Stored signals for this record, scoped to this workspace. Manual
    # today; a provider's one day. Derived ones are never stored, so these
    # two sets cannot double-count the same fact.
    # `signal_index` is `signals.index(workspace)` built once by a caller
    # working through many accounts. Without it every account re-reads the
    # whole signals file, which is fine for one and quadratic for an
    # estate.
    found += (list((signal_index or {}).get(rec.get("id")) or [])
              if signal_index is not None
              else signal_module.for_record(rec.get("id"), workspace))
    found += list(extra_signals or [])

    # `signal strength` and `timing` ask one question: is something
    # happening *at this company*. Engagement signals answer a different
    # one - how far we have already got - and ENGAGEMENT below scores that
    # from the same events. Feeding them to both counts one reply twice,
    # and it makes an account we merely wrote to last week report "1 fresh
    # signal", which reads as interest from them rather than activity from
    # us. Scoring is external only; the returned list keeps everything,
    # because the screens show both and label which is which.
    external = [s for s in found
                if signal_module.SCOPE_OF.get(s.get("type"))
                != signal_module.ENGAGEMENT]
    strength = signal_module.strength(external, now, config)
    everything = signal_module.strength(found, now, config)

    fit_score, fit_why, fit_raw = _icp_fit(rec)
    coverage_score, coverage_why, reachable = _persona_coverage(
        rec, config, suppressed)
    engagement_score, engagement_why, outcome = _engagement(rec, config)

    contributing = strength["contributing"]
    timing_score = (max((r["decay"] for r in contributing), default=0.0))
    timing_why = ("nothing current" if not contributing
                  else f"freshest signal is at {timing_score:.0%} of its "
                       f"original weight")

    parts = {
        ICP_FIT: (fit_score, fit_why),
        SIGNAL_STRENGTH: (strength["score"],
                          f"{strength['count']} live signal(s)"
                          if strength["count"] else "no live signals"),
        TIMING: (timing_score, timing_why),
        PERSONA_COVERAGE: (coverage_score, coverage_why),
        ENGAGEMENT: (engagement_score, engagement_why),
    }

    share = weights(config)
    components = []
    total = 0.0
    for key in COMPONENTS:
        raw, why = parts[key]
        points = raw * share[key] * 100.0
        total += points
        components.append({
            "component": key,
            "label": COMPONENT_LABEL[key],
            "raw": raw,
            "weight": share[key],
            "points": points,
            "why": why,
        })

    score = round(total, 1)
    action, blocked = hygiene.ACTION_OF[hygiene.FRESH], None
    account_state, account_why = ap.account_state(rec)
    if account_state == ap.SUPPRESS:
        action, blocked = hygiene.SUPPRESS, "the company asked us to stop"
    elif account_state == ap.HOLD:
        action = hygiene.HOLD
        blocked = HELD_BECAUSE.get((account_why or {}).get("outcome"),
                                   "held while a conversation is live")

    return {
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "workspace": workspace,
        "score": score,
        "tier": tier_of(score, config),
        "tier_label": TIER_LABEL[tier_of(score, config)],
        "components": sorted(components, key=lambda c: -c["points"]),
        "signals": signal_module.summarise(found, now, config),
        # Across every signal, not only the scored ones: a stale engagement
        # signal is still something a person reading the account wants to
        # see, even though it is not what moved the number.
        "stale_signals": everything["stale"],
        # Reported beside the score, never folded into it.
        "eligibility": {"action": action, "blocked": blocked,
                        "eligible": blocked is None},
        "why_now": why_now(components, strength, engagement_why),
    }


def why_now(components, strength, engagement_why):
    """One sentence a person would actually say, from the top components.

    Not the score, and not every component: the two or three that are
    carrying it. A "why now" listing all five is a restatement of the
    table underneath it.
    """
    carrying = [c for c in components if c["points"] >= 5.0][:3]
    if not carrying:
        return "Nothing here stands out yet."
    fresh = [r for r in strength["contributing"]
             if r["freshness"] == signal_module.FRESH]
    parts = []
    for part in carrying:
        # The signal component already counts them; saying "6 live" and
        # then "6 fresh" in one sentence is the same fact twice.
        if part["component"] == SIGNAL_STRENGTH and fresh:
            parts.append(f"{len(fresh)} fresh signal(s)")
        elif part["component"] == TIMING and fresh:
            continue
        else:
            parts.append(part["why"])
    return "; ".join(parts) + "."
