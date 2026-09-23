#!/usr/bin/env python3
"""Proposed rules, distinguished from unwired code.

## The three levels

    observation   A   what was measured. Already produced by learning.py;
                      this module makes it addressable by id rather than
                      recomputable on every read.
    proposal      B   a rule somebody or something suggests, carrying:
                      the observation ids it rests on, the change it would
                      make, the surface it would touch, who proposed it,
                      when, and its status.
    approval      C   an operator decision on one proposal: approved or
                      rejected, by whom, when, with a reason.

## The one hard rule

Nothing in `src/` or `scripts/` may write an approval. `approve()` raises
unconditionally. An approval is a hand-edit to `config/clients/*.yaml` by
a person, and the codebase enforces that the same way it enforces its other
one-way doors - a guard that raises, not a comment.

## A rule reaches a surface only from C

`behind()` answers which approved rule, if any, is behind a value on one of
the three surfaces. Nothing automatic: the consumer check is a read, not a
write. An unapproved proposal changes no client answer.

## What learning.boost() is under this scheme

Classified in TASK-266's FINDINGS. The function computes a priority nudge
from measured performance and has zero callers in `src/` or `scripts/`.
Under this module it is a B that was never promoted - a proposal without a
proposal record.
"""
from . import store

# ------------------------------------------------------------------ surfaces
#
# The three things a rule may change. A proposal whose surface is not one of
# these is refused rather than coerced, because a proposal that says
# "change the pricing page" is not a copy/icp/routing rule and pretending
# it was would file it under a surface it cannot act on.

COPY = "copy"
ICP = "icp"
ROUTING = "routing"
SURFACES = (COPY, ICP, ROUTING)

SURFACE_LABEL = {
    COPY: "Message copy",
    ICP: "Who we target",
    ROUTING: "How accounts are routed",
}

# ------------------------------------------------------------------- statuses
#
# Closed vocabulary. An unknown value is refused rather than coerced, because
# a proposal whose status is silently normalised to "proposed" could skip a
# rejection somebody already recorded.

PROPOSED = "proposed"
APPROVED = "approved"
REJECTED = "rejected"
SUPERSEDED = "superseded"
STATUSES = (PROPOSED, APPROVED, REJECTED, SUPERSEDED)

STATUS_LABEL = {
    PROPOSED: "Proposed, awaiting decision",
    APPROVED: "Approved by operator",
    REJECTED: "Rejected by operator",
    SUPERSEDED: "Superseded by a later proposal",
}


class LearningRuleError(ValueError):
    """A proposal or observation was refused, and the message says why."""


# ------------------------------------------------------------- observations
#
# What was measured. Already produced by learning.py; this only needs to be
# addressable by id, not recomputed. An observation is a fact; a proposal
# rests on facts.

def observation(obs_id, *, what, evidence=None, source=None, at=None):
    """One measurement. Addressable by id so proposals can point at it."""
    obs_id = str(obs_id or "").strip()
    if not obs_id:
        raise LearningRuleError("an observation must have an id")
    what = (what or "").strip()
    if not what:
        raise LearningRuleError(
            "an observation must say what was measured")
    return {
        "id": obs_id,
        "what": what[:600],
        "evidence": (evidence or "").strip()[:600] or None,
        "source": source,
        "at": at or store.now(),
    }


# --------------------------------------------------------------- proposals
#
# A rule somebody or something suggests. The observation ids it rests on are
# required: a proposal without evidence is a preference, and the distinction
# is the whole point of the three-level scheme.

def proposal(prop_id, *, observation_ids, surface, what, why=None,
             proposed_by=None, at=None, status=None):
    """One proposed rule. Refused without observation ids or a known surface.

    `observation_ids` is a non-empty sequence of observation ids this
    proposal rests on. A proposal without evidence is not a B - it is an
    opinion wearing one, and the scheme exists to tell them apart.
    """
    prop_id = str(prop_id or "").strip()
    if not prop_id:
        raise LearningRuleError("a proposal must have an id")

    if not observation_ids:
        raise LearningRuleError(
            "a proposal must carry the observation ids it rests on - "
            "without them it is a preference, not a proposal")
    observation_ids = tuple(str(o).strip() for o in observation_ids)
    if any(not o for o in observation_ids):
        raise LearningRuleError(
            "an observation id in the proposal is empty")

    surface = (surface or "").strip().lower()
    if surface not in SURFACES:
        raise LearningRuleError(
            f"unknown surface {surface!r}; must be one of {SURFACES}")

    what = (what or "").strip()
    if not what:
        raise LearningRuleError(
            "a proposal must say what change it would make")

    status = (status or PROPOSED).strip().lower()
    if status not in STATUSES:
        raise LearningRuleError(
            f"unknown status {status!r}; must be one of {STATUSES}")

    return {
        "id": prop_id,
        "observation_ids": observation_ids,
        "surface": surface,
        "what": what[:600],
        "why": (why or "").strip()[:600] or None,
        "proposed_by": proposed_by,
        "at": at or store.now(),
        "status": status,
        "superseded_by": None,
    }


# --------------------------------------------------------------- approvals
#
# The one hard rule. Nothing in src/ or scripts/ writes an approval. An
# approval is a person editing config/clients/*.yaml, and the code enforces
# that by refusing every programmatic attempt.

def approve(proposal_entry, *, approved_by=None, reason=None):
    """Refuse. Always.

    An approval is a human act. This function exists so a test can prove
    that a programmatic approval attempt raises, and so the rule has a
    single addressable home rather than living only in a comment.
    """
    raise LearningRuleError(
        "no code path may write an approval. An approval is a person "
        "editing config/clients/*.yaml. This is enforced, not advised.")


# -------------------------------------------------- status transitions

def reject(prop_id, proposal_entry, *, rejected_by=None, reason=None):
    """Mark a proposal rejected. A person decided; the code records."""
    if proposal_entry.get("status") != PROPOSED:
        raise LearningRuleError(
            f"cannot reject a {proposal_entry.get('status')!r} proposal; "
            f"only a {PROPOSED!r} one may be rejected")
    return {
        **proposal_entry,
        "status": REJECTED,
        "rejected_by": rejected_by,
        "reject_reason": (reason or "").strip()[:600] or None,
    }


def supersede(old_entry, new_entry):
    """Mark an old proposal superseded by a new one. Both survive.

    The old row is not deleted or corrected. "We proposed X, then proposed
    Y" is the value of the log, and a log showing only the current proposal
    is a configuration file with worse ergonomics.
    """
    if old_entry.get("status") == SUPERSEDED:
        raise LearningRuleError(
            "that proposal has already been superseded; supersede the one "
            "that replaced it")
    if old_entry.get("status") not in (PROPOSED, APPROVED):
        raise LearningRuleError(
            f"cannot supersede a {old_entry.get('status')!r} proposal")
    return {**old_entry, "status": SUPERSEDED,
            "superseded_by": new_entry.get("id")}


def mark_approved(prop_id, proposal_entry):
    """Set status to approved. NOT an approval - a record of one.

    This is the seam a hand-edit reaches: the operator edits the YAML, the
    import records that the proposal is now approved. The function does not
    decide; it records a decision that was made elsewhere.
    """
    if proposal_entry.get("status") == SUPERSEDED:
        raise LearningRuleError(
            "a superseded proposal cannot be approved")
    if proposal_entry.get("status") not in (PROPOSED,):
        raise LearningRuleError(
            f"cannot approve a {proposal_entry.get('status')!r} proposal; "
            f"only a {PROPOSED!r} one may be approved")
    return {**proposal_entry, "status": APPROVED}


# --------------------------------------------------------- consumer check
#
# A rule reaches a surface only from C. `behind()` answers which approved
# rule, if any, is behind a value. This is a read, not a write.

def behind(approved_rules, surface, value):
    """Which approved rule, if any, is behind this value on this surface.

    `approved_rules` is an iterable of proposal entries with status
    APPROVED. Returns the first one whose surface matches and whose `what`
    names the value, or None.

    A value with no approved rule behind it is not a defect - it is the
    default state of affairs. Most values were set before this scheme
    existed, and that is fine.
    """
    if surface not in SURFACES:
        raise LearningRuleError(
            f"unknown surface {surface!r}; must be one of {SURFACES}")
    for rule in approved_rules:
        if rule.get("status") != APPROVED:
            continue
        if rule.get("surface") != surface:
            continue
        if value and rule.get("what") and value in rule["what"]:
            return rule
    return None


def approved_for(approved_rules, surface):
    """Every approved proposal on this surface. Filter, not transform."""
    if surface not in SURFACES:
        raise LearningRuleError(
            f"unknown surface {surface!r}; must be one of {SURFACES}")
    return [r for r in approved_rules
            if r.get("status") == APPROVED and r.get("surface") == surface]
