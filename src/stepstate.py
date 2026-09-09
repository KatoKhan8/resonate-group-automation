#!/usr/bin/env python3
"""The lifecycle of one cadence step, written down.

## Why it needed writing down

Statuses accumulated organically - `pending`, `eligible`, `waiting`, `blocked`,
`skipped`, `pushed` - each added where it was needed and each perfectly sensible
on its own. What was missing was the shape: which of them can follow which, and
what it means when one appears where it should not. A step that goes from
`pushed` back to `eligible` is not a status, it is a second send.

So this is the machine, and it is deliberately built over the names that
already exist rather than a parallel vocabulary. `cadence.status_for()` still
computes the status; this says whether the move it computed was legal, and
refuses the ones that are not.

## Terminal means terminal

`pushed`, `cancelled` and `confirmed` have no way out. That is the property
that makes the logical push id trustworthy: once a step has gone, nothing in
this system can put it back in a state where it would go again.

## Held is not blocked is not skipped

    held      waiting on something that may resolve - approval, verification
    blocked   a rule says no, and it is not going to stop saying no
    skipped   this step does not apply to this contact at all
    cancelled a human or a reply ended it

Four ways to not send, and collapsing them loses the only information an
operator can act on.
"""

# The states, mapped onto what cadence already emits. Names in parentheses are
# the existing cadence status strings; where they differ, the cadence name wins
# because it is what is stored.
PLANNED = "planned"          # a step exists in the timeline but has no draft
PENDING = "pending"          # cadence: not yet due
UNAPPROVED = "unapproved"    # drafted, awaiting a human
HELD = "held"                # a condition may yet pass
WAITING = "waiting"          # gated on an external event (connection accepted)
ELIGIBLE = "eligible"        # every condition passes; may be prepared
PREPARED = "prepared"        # a payload exists, nothing has left
PUSHED = "pushed"            # handed to a provider. Terminal.
CONFIRMED = "confirmed"      # the provider says it went. Terminal.
SKIPPED = "skipped"          # not applicable: channel closed for this contact
BLOCKED = "blocked"          # a rule refuses it
PAUSED = "paused"            # the company or contact is paused
CANCELLED = "cancelled"      # ended deliberately. Terminal.
FAILED = "failed"            # the provider refused it; may be retried

STATES = (PLANNED, PENDING, UNAPPROVED, HELD, WAITING, ELIGIBLE, PREPARED,
          PUSHED, CONFIRMED, SKIPPED, BLOCKED, PAUSED, CANCELLED, FAILED)

TERMINAL = (PUSHED, CONFIRMED, CANCELLED)

# Where a step may go from where it is. Anything absent is illegal.
TRANSITIONS = {
    PLANNED: (PENDING, UNAPPROVED, SKIPPED, BLOCKED, PAUSED, CANCELLED),
    PENDING: (UNAPPROVED, ELIGIBLE, HELD, WAITING, SKIPPED, BLOCKED, PAUSED,
              CANCELLED),
    UNAPPROVED: (ELIGIBLE, HELD, PENDING, SKIPPED, BLOCKED, PAUSED, CANCELLED),
    HELD: (ELIGIBLE, UNAPPROVED, PENDING, WAITING, SKIPPED, BLOCKED, PAUSED,
           CANCELLED),
    WAITING: (ELIGIBLE, HELD, PENDING, SKIPPED, BLOCKED, PAUSED, CANCELLED),
    # An eligible step can lose its eligibility: an edit, a reply, a pause.
    ELIGIBLE: (PREPARED, HELD, UNAPPROVED, PENDING, WAITING, SKIPPED, BLOCKED,
               PAUSED, CANCELLED),
    # Prepared but not sent. A crash here returns it to eligible, which is what
    # makes the payload stage safe to repeat.
    PREPARED: (PUSHED, FAILED, ELIGIBLE, HELD, BLOCKED, PAUSED, CANCELLED),
    PUSHED: (CONFIRMED,),
    CONFIRMED: (),
    # Not applicable now may become applicable: an MX policy change, a
    # verification that lands. It may never become pushed directly.
    SKIPPED: (PENDING, ELIGIBLE, HELD, BLOCKED, CANCELLED, PAUSED),
    BLOCKED: (PENDING, ELIGIBLE, HELD, UNAPPROVED, SKIPPED, PAUSED, CANCELLED),
    PAUSED: (PENDING, ELIGIBLE, HELD, SKIPPED, BLOCKED, CANCELLED),
    FAILED: (ELIGIBLE, PREPARED, HELD, BLOCKED, CANCELLED),
    CANCELLED: (),
}


class IllegalTransition(RuntimeError):
    """This step cannot go there from here. Nothing was changed."""


def known(state):
    return state in STATES


def is_terminal(state):
    return state in TERMINAL


def allowed(current, nxt):
    """Is this move legal? An unknown state is never legal."""
    if current is None:
        return nxt in STATES
    if current not in STATES or nxt not in STATES:
        return False
    if current == nxt:
        return True                      # recomputing the same status is fine
    return nxt in TRANSITIONS.get(current, ())


def check(current, nxt, where=""):
    """Raise unless the move is legal. Returns the next state."""
    if not allowed(current, nxt):
        options = ", ".join(TRANSITIONS.get(current, ())) or "nowhere"
        raise IllegalTransition(
            f"{where or 'step'}: cannot go {current!r} -> {nxt!r}. "
            f"From {current!r} it may only go to: {options}")
    return nxt


def apply(step, nxt, where="", at=None):
    """Move a stored step, recording where it came from.

    The history is kept because "why is this skipped" is answered by the
    sequence, not by the current value.
    """
    from . import store
    current = step.get("status")
    check(current, nxt, where)
    if current != nxt:
        step.setdefault("history", []).append(
            {"from": current, "to": nxt, "at": at or store.now()})
    step["status"] = nxt
    return step


def reconcile(step, computed, where=""):
    """Accept a freshly computed status, or say why it cannot be accepted.

    cadence.build() recomputes a status from scratch every time it is called,
    which is the right design - it means nothing can drift. This is where that
    recomputation meets the rule that a sent step stays sent: a computed status
    that would move a terminal step is refused rather than written.
    """
    current = step.get("status")
    if current in TERMINAL and computed != current:
        return {"ok": False, "status": current,
                "why": f"{current} is terminal; refusing to move it to {computed}"}
    if not allowed(current, computed):
        return {"ok": False, "status": current,
                "why": f"illegal transition {current} -> {computed}"}
    return {"ok": True, "status": computed, "why": None}


def summarise(timeline):
    """Counts by state across a whole timeline."""
    counts = {}
    for steps in (timeline or {}).values():
        for step in steps.values():
            state = step.get("status") or PLANNED
            counts[state] = counts.get(state, 0) + 1
    return counts
