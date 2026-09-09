#!/usr/bin/env python3
"""Demo copy experiments: five styles per message step, and five outcomes.

Fictional, and labelled so. What it exists to demonstrate is not the copy
but the *states* - because the interesting thing about an experiment is
almost always that it cannot tell you anything yet, and a demo where every
experiment has a confident winner would teach exactly the wrong lesson.

So the fixtures cover one of each:

    exploring          too early to look
    insufficient_data  looked, not enough to say
    no_clear_winner    enough data, nothing separating them
    leading            one ahead, ranges still overlapping
    winner             separated, and traffic already shifted

## The numbers here are planted, and that is the honest description

A real experiment's rates are counted from confirmed touches and replies by
`variants.results_from`, which is what a real campaign uses and what the
tests exercise. These fixtures are **summary counts**, not events: putting
four thousand touch events into the demo estate to make one screen render
would cost more than the demonstration is worth.

So the demo shows the real evaluator reading planted totals. Every
verdict, threshold, interval and traffic shift on the screen is computed
by the production code from those totals - only the totals are fictional,
and the screen says DEMO.
"""
from .. import variants as V

# ------------------------------------------------------------- the copy
#
# One coherent message per style, not one message with a word swapped. The
# point of a style experiment is that the approaches differ; five near
# identical bodies would measure nothing and would still cost five cells of
# traffic.

EMAIL_COPY = {
    "short_direct": (
        "a question about {company}",
        "{first_name}, how does {company} see project margin today - during "
        "the month, or after it closes?\n\n"
        "Most teams your size only find out afterwards. Worth a short "
        "conversation?"),
    "casual": (
        "quick one, {company}",
        "{first_name} - working with a few teams around your size on the "
        "gap between what delivery thinks a project is worth and what "
        "finance sees at month end.\n\n"
        "Usually the same story: everyone is right, the numbers just arrive "
        "too late to do anything with.\n\n"
        "Is that roughly how it looks at {company}?"),
    "professional": (
        "project margin visibility at {company}",
        "{first_name},\n\n"
        "In teams the size of {company}, utilisation and margin are "
        "typically known at the end of the month - which is after the month "
        "in which something could have been done about them.\n\n"
        "The work itself is rarely the problem. The visibility into it is.\n\n"
        "Would it be useful to compare how comparable teams have handled "
        "this?"),
    "consultative": (
        "the pattern I keep seeing at {company}'s size",
        "{first_name},\n\n"
        "There is a pattern in services teams around {company}'s size. "
        "Finance and delivery each keep their own view of a project, both "
        "are internally consistent, and they disagree by the time anyone "
        "compares them.\n\n"
        "The teams that fix it rarely change how delivery works. They stop "
        "maintaining two views.\n\n"
        "Is that a fair description of where {company} is, or have you "
        "already put something in place?"),
    "problem_led": (
        "when a project lands under margin",
        "{first_name},\n\n"
        "The expensive version of this problem is a project that lands "
        "under margin and nobody can say exactly when it went wrong.\n\n"
        "By then the answer is somewhere in a timesheet export and a "
        "finance spreadsheet that were never reconciled while the work was "
        "running.\n\n"
        "Has {company} had one of those recently?"),
}

LINKEDIN_COPY = {
    "casual": (
        "hi {first_name}, i work with services teams on getting project "
        "margin visible while the work is still running rather than after. "
        "curious how {company} handles it. happy to connect."),
    "short_direct": (
        "{first_name} - do you see project margin during the month at "
        "{company}, or after it closes? that gap is most of what i work on."),
    "professional": (
        "{first_name}, I work with services teams on project margin "
        "visibility during delivery rather than at month end. Given "
        "{company}'s size I suspect this is familiar. Happy to connect."),
    "consultative": (
        "{first_name} - the teams I work with around {company}'s size "
        "usually find finance and delivery are keeping two versions of the "
        "same project. Curious whether that is the shape of it for you."),
    "peer_to_peer": (
        "{first_name}, one operator to another: how long after a month "
        "closes do you actually know what a project made at {company}? "
        "that lag is what i spend most of my time on."),
}


def _copy_for(node_type, style):
    if node_type == "email":
        subject, body = EMAIL_COPY[style]
        return {"subject": subject, "body": body}
    return {"note": LINKEDIN_COPY[style]}


def variants_for(node_type, prefix):
    """Five complete variants for one step, in that channel's styles."""
    styles = V.STYLES_FOR[node_type]
    return [V.variant(f"{prefix}-{style}", style,
                      **_copy_for(node_type, style))
            for style in styles]


# ------------------------------------------------------ the planted results
#
# (exposures, positive replies) per style, chosen to land on one of each
# experiment state. Written as counts here and expanded into real touch and
# reply events by `install`, so nothing on the screen is a stored number.

RESULTS = {
    # Enough data, and one style clearly ahead: a winner, traffic shifted.
    "winner": {
        "short_direct": (210, 31), "casual": (205, 11),
        "professional": (208, 9), "consultative": (203, 10),
        "peer_to_peer": (206, 12), "problem_led": (206, 12),
    },
    # Ahead, but the ranges still overlap.
    "leading": {
        "short_direct": (120, 12), "casual": (118, 8),
        "professional": (121, 7), "consultative": (119, 8),
        "peer_to_peer": (117, 9), "problem_led": (117, 9),
    },
    # Plenty of data, and the two best are genuinely level - 9/150 and
    # 6/100 are both 6.0%. This is the state a demo most needs to show: the
    # honest answer to "which won" is often "neither, yet".
    "no_clear_winner": {
        "short_direct": (150, 9), "casual": (100, 6),
        "professional": (151, 8), "consultative": (149, 8),
        "peer_to_peer": (150, 8), "problem_led": (150, 8),
    },
    # Looked at, and there is not enough to say anything.
    "insufficient_data": {
        "short_direct": (11, 2), "casual": (9, 1),
        "professional": (10, 0), "consultative": (12, 1),
        "peer_to_peer": (8, 0), "problem_led": (8, 0),
    },
    # Too early to look at all.
    "exploring": {
        "short_direct": (3, 0), "casual": (2, 0), "professional": (2, 0),
        "consultative": (3, 0), "peer_to_peer": (2, 0), "problem_led": (2, 0),
    },
}

# Which planted outcome each demo step gets, and how far through it is.
STEP_STATE = {
    "open": ("winner", 0.85),            # email, day 1
    "li_intro": ("leading", 0.55),       # LinkedIn message, day 6
    "email2": ("no_clear_winner", 0.60),  # email, day 10
    "li_follow": ("insufficient_data", 0.30),
    "breakup": ("exploring", 0.04),      # email, day 67
}

PROGRESS = {step: progress for step, (_state, progress) in STEP_STATE.items()}


def results_for(step_key, node):
    """Planted exposures and outcomes for one demo step, keyed by variant.

    Shaped exactly as `variants.results_from` returns, so the evaluator
    cannot tell the difference and the demo exercises the real code.
    """
    state = (STEP_STATE.get(step_key) or (None, None))[0]
    planted = RESULTS.get(state)
    if not planted:
        return {}
    out = {}
    for entry in node.get("variants") or []:
        counts = planted.get(entry["style"])
        if not counts:
            continue
        exposures, positive = counts
        out[entry["variant_id"]] = {
            "exposures": exposures,
            V.POSITIVE_REPLIES: positive,
            # Replies are always at least the positive ones; a demo where
            # they were equal would imply every reply was positive.
            V.REPLIES: positive + max(1, exposures // 25),
            V.MEETINGS: max(0, positive // 4),
        }
    return out


def attach(graph):
    """Put five variants on every message step of the demo cadence.

    Returns the same graph. The steps named in `STEP_STATE` also get the
    traffic allocation their planted result implies - the winner's step is
    already shifted, because a demo where optimisation never visibly
    happened would be demonstrating half the feature.
    """
    for key, node in (graph.get("nodes") or {}).items():
        if not V.is_message_node(node):
            continue
        node["variants"] = variants_for(node["type"], key)
        node["objective"] = V.POSITIVE_REPLIES
        state = (STEP_STATE.get(key) or (None, None))[0]
        if state == "winner":
            leader = f"{key}-short_direct"
            shifted = V.shifted_allocation(
                node, {"state": V.WINNER, "leader": leader})
            for entry in node["variants"]:
                entry["allocation"] = shifted.get(entry["variant_id"])
            node["allocation_version"] = 2
    return graph
