#!/usr/bin/env python3
"""Every prospect-facing action, written down before it is attempted.

WHY THIS HAS TO EXIST BEFORE ANY SEND ROUTE DOES.

`pilotcaps.check(plan)` compares a dict the CALLER supplies against the pilot
ceiling. It counts nothing durable. So two sequential callers each declaring
`{"linkedin_per_day": 1}` both pass, and together they send two; and a caller
who passes `{}` gets `ok: True` with every key listed as "unchecked". The module
is honest about that - `check` returns an `unchecked` list - but `require`
returns True anyway. A cap that counts what you tell it is not a cap.

And `push.push_id(rec, contact, day, channel)` already gives a stable identity
for one prospect-facing action, but nothing has ever persisted one. So after a
timeout there is no way to answer the only question that matters: did the
provider act? Retrying to find out is how somebody gets contacted twice.

So this ledger does two jobs, and they are the same job:

  1. A reservation is written BEFORE the provider is called and settled after.
     An unsettled reservation BLOCKS a retry for that key - the caller must
     reconcile against provider truth first. `reserve` is the only way in and
     it refuses a second reservation for a key already in flight.

  2. It is the durable count the pilot cap is measured against, per channel and
     per sender, over a real calendar day rather than over one caller's
     optimistic plan.

NOTHING HERE SENDS ANYTHING. It records intent and outcome. It is deliberately
written before the write layer so that on the day somebody implements a send
route, the brakes already exist, are tested, and default to refusing.
"""
import json
import os
import sys

from . import events, store

# ---------------------------------------------------------------- outcomes

ATTEMPTED = "attempted"      # reserved, provider not yet known to have acted
SENT = "sent"                # provider confirmed, and a read-back agreed
FAILED = "failed"            # provider refused before acting. Safe to retry
ABANDONED = "abandoned"      # a human decided not to complete it
UNRESOLVED = "unresolved"    # provider truth could not settle it. NEVER retry

SETTLED = (SENT, FAILED, ABANDONED)
# UNRESOLVED is deliberately NOT settled. It is the state that exists so that
# "we do not know whether they were contacted" can never be mistaken for
# "they were not contacted", and it blocks the key forever until a human
# resolves it against the provider by hand.
BLOCKING = (ATTEMPTED, UNRESOLVED)

# A key that reached a prospect is finished, and `reserve` must refuse it just
# as firmly as one still in flight. It did not: `BLOCKING` alone was consulted,
# `SENT` is not in it, and the "already sent" refusal lived only in the separate
# and OPTIONAL `require_clear`. So a direct `reserve` on a sent key succeeded -
# and because `state_of` reads the LATEST row, it also regressed the state from
# `sent` back to `attempted`, destroying the durable record that a real person
# had been contacted. `stepstate` already writes the rule down: terminal means
# terminal. This is the ledger implementing it.
TERMINAL = (SENT,)
UNRESERVABLE = BLOCKING + TERMINAL


class ActionRefused(RuntimeError):
    """The action may not be attempted. Raised, never returned."""


class Unsettled(ActionRefused):
    """A reservation for this key is still open, or is unresolved.

    The distinct type matters: this is the one refusal a caller must never
    handle by retrying. Read the provider first.
    """


def path():
    """Beside the queue, so actions and the records they touch move together."""
    return os.path.abspath(os.environ.get("ACTION_LEDGER")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "action-ledger.jsonl"))


def load():
    return store.read_jsonl(path())


def rows_for(key, rows=None):
    rows = load() if rows is None else rows
    return [r for r in rows if r.get("key") == key]


def state_of(key, rows=None):
    """The current state of this key, from its latest row. `None` if unseen."""
    found = rows_for(key, rows)
    return found[-1].get("state") if found else None


def is_blocked(key, rows=None):
    return state_of(key, rows) in BLOCKING


def is_unreservable(key, rows=None):
    """In flight, unresolved, or already sent. Any of the three refuses."""
    return state_of(key, rows) in UNRESERVABLE


def unsettled(rows=None):
    """Every key that needs reconciling before anything may be retried."""
    rows = load() if rows is None else rows
    latest = {}
    for row in rows:
        latest[row.get("key")] = row
    return [r for r in latest.values() if r.get("state") in BLOCKING]


def _day(at):
    return str(at or "")[:10]


def count_on(day, channel=None, sender_id=None, workspace=None, rows=None,
             states=None):
    """How many actions this ledger says happened on one calendar day.

    THE DURABLE COUNT. `states` defaults to everything that either reached a
    prospect or might have - `SENT` plus the two states where provider truth is
    unknown - because a cap that only counted confirmed sends would let an
    unresolved attempt buy another attempt, which is precisely the hazard.

    `workspace` SCOPES THE COUNT TO ONE TENANT - the CLIENT SLUG, not a
    provider's numeric estate id - and omitting it counts every tenant
    together. `reserve` has always required and stored the workspace, but
    this had no parameter for it, so one client's actions consumed another
    client's pilot ceiling - in a system where tenancy outranks nearly
    everything else. Callers that mean "this client" must say so.
    """
    states = (SENT, ATTEMPTED, UNRESOLVED) if states is None else states
    rows = load() if rows is None else rows
    latest = {}
    for row in rows:
        latest[row.get("key")] = row
    n = 0
    for row in latest.values():
        if row.get("state") not in states:
            continue
        if _day(row.get("at")) != _day(day):
            continue
        if channel is not None and row.get("channel") != channel:
            continue
        if sender_id is not None and str(row.get("sender_id")) != str(sender_id):
            continue
        if workspace is not None and str(row.get("workspace")) != str(workspace):
            continue
        n += 1
    return n


class CapReached(ActionRefused):
    """The durable count for this day is already at the ceiling."""


def reserve(key, *, channel, workspace, campaign_id, sender_id, rec_id,
            contact_key, step_key, operation, fingerprint, by="system",
            provider_workspace=None, cap_per_day=None, cap_per_sender=None,
            timeout=None):
    """Claim the right to attempt one prospect-facing action. Written first.

    Refuses when a reservation for this key is already open, unresolved or
    already sent, which is what makes a post-timeout retry impossible without
    reconciling. Every field is required and none is inferred: an action whose
    tenant, campaign, sender or approved fingerprint cannot be named is an
    action nobody can audit afterwards.

    THE CAPS ARE ENFORCED HERE, INSIDE THE TRANSACTION, and that placement is
    the whole point. Counting outside the lock and reserving inside it is a
    time-of-check-to-time-of-use window: two workers each read a count of 9
    against a ceiling of 10, each pass, and the ledger ends the day at 11. The
    count and the append have to be the same critical section, so the caller
    passes the ceilings in rather than checking them first.

    Both caps are scoped to `workspace`. One client's actions must never
    consume another's ceiling.
    """
    missing = [name for name, value in (
        ("key", key), ("channel", channel), ("workspace", workspace),
        ("campaign_id", campaign_id), ("sender_id", sender_id),
        ("rec_id", rec_id), ("contact_key", contact_key),
        ("step_key", step_key), ("operation", operation),
        ("fingerprint", fingerprint)) if value in (None, "")]
    if missing:
        raise ActionRefused(
            f"a reservation must name {', '.join(missing)}: an action nobody "
            f"can attribute is an action nobody can reconcile")
    row = {
        "key": key, "state": ATTEMPTED, "at": store.now(),
        "operation": operation, "channel": channel, "workspace": workspace,
        "campaign_id": campaign_id, "sender_id": sender_id,
        "rec_id": rec_id, "contact_key": contact_key, "step_key": step_key,
        "fingerprint": fingerprint, "by": by,
        # Which provider estate the action was aimed at. Recorded as evidence,
        # never used as the tenant key: `workspace` above is the client slug,
        # which is what tenancy means everywhere else in this system.
        "provider_workspace": provider_workspace,
    }
    # The check and the append happen under one lock. Two processes racing the
    # same key is exactly what this is for, so reading first and writing after
    # would reintroduce the race it exists to close.
    with store.file_transaction(path(), timeout) as rows:
        if cap_per_day is not None:
            used = count_on(row["at"], channel=channel, workspace=workspace,
                            rows=rows)
            if used + 1 > int(cap_per_day):
                raise CapReached(
                    f"{channel}: {used} action(s) already recorded today for "
                    f"workspace {workspace}, and the ceiling is {cap_per_day}")
        if cap_per_sender is not None:
            used = count_on(row["at"], channel=channel, workspace=workspace,
                            sender_id=sender_id, rows=rows)
            if used + 1 > int(cap_per_sender):
                raise CapReached(
                    f"sender {sender_id}: {used} action(s) already recorded "
                    f"today, and the per-sender ceiling is {cap_per_sender}")
        if is_unreservable(key, rows):
            existing = rows_for(key, rows)[-1]
            if existing["state"] in TERMINAL:
                raise ActionRefused(
                    f"{key} is {existing['state']} since {existing['at']}: a "
                    f"second prospect-facing action for the same step is a "
                    f"duplicate touch, not a retry")
            raise Unsettled(
                f"{key} is {existing['state']} since {existing['at']}. Read "
                f"the provider and settle it; do NOT retry a prospect-facing "
                f"action because the client did not see a response")
        rows.append(row)
    return dict(row)


def settle(key, state, *, why="", provider_response=None, readback=None,
           timeout=None):
    """Record what actually happened. Appends; never edits history."""
    if state not in (SENT, FAILED, ABANDONED, UNRESOLVED):
        raise ActionRefused(f"{state!r} is not a settlement")
    with store.file_transaction(path(), timeout) as rows:
        found = rows_for(key, rows)
        if not found:
            raise ActionRefused(f"{key} was never reserved; nothing to settle")
        if found[-1].get("state") == state:
            return dict(found[-1])
        prior = found[-1]
        row = dict(prior)
        row.update({"state": state, "at": store.now(), "why": why,
                    "settled_from": prior.get("state")})
        if provider_response is not None:
            row["provider_response"] = provider_response
        if readback is not None:
            row["readback"] = readback
        rows.append(row)
    return dict(row)


def require_clear(key, rows=None):
    """Raise unless this key may be attempted. The gate a write layer calls."""
    state = state_of(key, rows)
    if state in BLOCKING:
        raise Unsettled(
            f"{key} is {state}: provider truth must settle it before any "
            f"further attempt")
    if state == SENT:
        raise ActionRefused(
            f"{key} was already sent; a second prospect-facing action for the "
            f"same step is a duplicate touch, not a retry")
    return True


def report(rows=None):
    rows = load() if rows is None else rows
    latest = {}
    for row in rows:
        latest[row.get("key")] = row
    counts = {}
    for row in latest.values():
        counts[row.get("state")] = counts.get(row.get("state"), 0) + 1
    return {"keys": len(latest), "by_state": counts,
            "unsettled": [r["key"] for r in unsettled(rows)]}


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="python -m src.actionledger",
                                description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--day", help="count actions on this YYYY-MM-DD")
    p.add_argument("--channel")
    a = p.parse_args(argv)
    if a.day:
        print(count_on(a.day, channel=a.channel))
        return 0
    found = report()
    print(json.dumps(found, indent=1) if a.json else
          f"{found['keys']} action(s): {found['by_state']}\n"
          f"unsettled: {found['unsettled'] or 'none'}")
    return 1 if found["unsettled"] else 0


if __name__ == "__main__":
    sys.exit(main())
