#!/usr/bin/env python3
"""Demo GTM decisions: fictional choices, real reasoning discipline.

What this has to demonstrate is not that decisions can be stored but that
the log is *honest about itself*:

    a decision measured here, with its numbers
    a decision that was somebody's judgement, saying so
    a decision the client asked for, attributed to them
    a decision that was superseded, with both halves kept
    a setting changed with no reason recorded

That last one is deliberate. A demo where every setting is explained would
teach that the unexplained list is decorative; it is the most useful thing
on the page.

Nothing here is a real client or a real decision.
"""
from .. import gtm


def build(workspace="productive"):
    """The demo decision set, oldest first - the file is append-only."""
    return [
        gtm.decision(
            workspace, gtm.QUALIFICATION,
            decided="Treat delivery-team size as the qualifying signal, not "
                    "headcount",
            why="A 30-person agency with 25 billable people is a better fit "
                "than a 90-person firm with eight",
            basis=gtm.MEASURED,
            evidence="Of 14 meetings booked in Q2, 11 were at companies "
                     "where delivery was over half of headcount",
            policy_key="market.size_min_employees",
            decided_by="rae@productive.test"),

        gtm.decision(
            workspace, gtm.CHANNEL,
            decided="Open on LinkedIn in DACH rather than email",
            why="Cold email reputation in the region is worse than ours and "
                "the first touch is what pays for the rest",
            basis=gtm.JUDGEMENT,
            decided_by="rae@productive.test"),

        gtm.decision(
            workspace, gtm.MESSAGING,
            decided="Lead with margin visibility, not utilisation",
            why="The client's own customers describe the problem as not "
                "knowing whether a project made money until it is over",
            basis=gtm.CLIENT,
            decided_by="rae@productive.test"),

        # Superseded below. Kept because "we believed this, then we learned
        # otherwise" is the part of a decision log worth having.
        gtm.decision(
            workspace, gtm.CADENCE,
            decided="Three touches then stop",
            why="Anything longer reads as pressure at this deal size",
            basis=gtm.JUDGEMENT,
            decided_by="rae@productive.test"),

        gtm.decision(
            workspace, gtm.SPEND,
            decided="No paid person-level enrichment before an explicit ICP "
                    "verdict",
            why="Person credits spent on a company we then reject are the "
                "single largest avoidable cost in this motion",
            basis=gtm.MEASURED,
            evidence="Q1 waterfall ledger: 38% of person credits were spent "
                     "on companies later marked rejected or review",
            policy_key="dm_plan.max_batch_credits",
            decided_by="rae@productive.test"),
    ]


REPLACEMENT = {
    "area": gtm.CADENCE,
    "decided": "Five touches across both channels, then stop",
    "why": "The fourth and fifth touches produced a third of last quarter's "
           "replies, and none of the complaints",
    "basis": gtm.MEASURED,
    "evidence": "Q2: 9 of 27 replies arrived on touch 4 or 5; 0 unsubscribe "
                "requests cited frequency",
    "decided_by": "rae@productive.test",
}


def install(workspace="productive"):
    """Write the demo decisions, then supersede one of them.

    Superseding through the real function rather than by writing a
    doctored row: the demo should exercise the same path an operator does,
    or it is demonstrating something that has never run.
    """
    rows = build(workspace)
    for entry in rows:
        gtm.record(entry)

    stored = gtm.load(workspace)
    older = next((r for r in stored
                  if r["decided"] == "Three touches then stop"), None)
    if older is not None:
        gtm.supersede(workspace, older["id"],
                      gtm.decision(workspace, **REPLACEMENT))
    return gtm.load(workspace)
