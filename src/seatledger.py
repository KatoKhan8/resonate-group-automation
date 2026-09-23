#!/usr/bin/env python3
"""Per-seat daily LinkedIn ledger: what THIS system did, and UNKNOWN for
what the client did on the same seat.

THE SITUATION THIS MODELS HONESTLY
-----------------------------------

HeyReach has 41 accounts, 34 active, 33 with valid auth, and 0 unallocated -
all 33 are already in campaigns, mostly the client's. We own 4 of 86. The
connection limit is 40/day per seat. Most seats are SHARED. The client works
them through their own campaigns, on a workspace-wide key, and their actions
are not in our action ledger and cannot be got at.

THE ASYMMETRY THAT MAKES THIS SAFE
-----------------------------------

Our ledger is a LOWER BOUND on a seat's use: it can only undercount, because
it sees our actions and not the client's. That asymmetry runs one way:

    ours >= 40                    -> FULL. Provable from our ledger alone.
                                     A lower bound at the ceiling is still at
                                     the ceiling.
    seat is EXCLUSIVELY ours      -> ROOM is computable: 40 - ours.
    seat is SHARED with the client-> REFUSED, ALWAYS, with reason
                                     client_usage_unknown.

The second line is different from `senderheadroom` in a way that must not be
smoothed over. There, REFUSED means *not yet proven* - a fresher, more
complete walk can turn it into ROOM. Here, on a shared seat, REFUSED is
**permanent**: no walk of our own ledger can ever prove room on a seat
somebody else is also working, because the missing quantity is unobservable
rather than unwalked.

WHY CLIENT USAGE CANNOT BE INFERRED
------------------------------------

A future session may try to close that gap by inferring client usage from
HeyReach's campaign counters. It cannot be done: the counters are per
campaign, we cannot enumerate the client's 82 campaigns reliably, and a
seat's daily total is not derivable from the campaigns we can see. A guessed
denominator is worse than a missing one.

EXCLUSIVE VS SHARED IS PROVIDER TRUTH
--------------------------------------

A seat is EXCLUSIVE only when a fresh provider read shows every campaign
touching it is one of ours. Anything else - a stale read, a campaign we
cannot attribute, a paging error - is SHARED. Fail closed: treating a shared
seat as exclusive is what produces a confident wrong ROOM, and ROOM is the
answer that licenses an action.

Attribution comes from `provider_truth` / `PROVIDER-CAMPAIGNS.json`, which
is the repo's existing answer to "what does the provider actually say". No
second source.

VOCABULARY - mirrors `senderheadroom`
--------------------------------------

FULL
    This seat will take no more of OUR actions today. ours >= limit.

ROOM
    This seat provably has capacity. Only on an EXCLUSIVE seat with ours <
    limit.

REFUSED
    Cannot be proven either way, with a reason naming what is missing. On a
    shared seat this is PERMANENT - no further walk of our ledger will change
    it.

READ-ONLY. Pure functions over the action ledger and the provider truth file.
No provider call, no credit, no canonical write. No new state file, no cache.
"""

import json
import os

from . import actionledger

FULL = "FULL"
ROOM = "ROOM"
REFUSED = "REFUSED"

LIMIT = 40

PROVIDER_TRUTH_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "state", "PROVIDER-CAMPAIGNS.json")


def _load_provider_truth(path=None):
    """Read the provider truth file. Missing or malformed is None - which
    means every seat is SHARED. A missing file is not an empty workspace."""
    path = path or PROVIDER_TRUTH_PATH
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or "heyreach" not in data:
        return None
    return data


def _seat_key(value):
    """A seat id compared as TEXT. Never coerced, never parsed.

    THIS WAS `int(seat_id)` AND A SEAT ID IS AN IDENTITY, NOT A NUMBER.
    `int()` failed in both directions at once:

      it RAISED on anything non-numeric, so a provider id like `acc-7` was an
      uncaught ValueError rather than a classified refusal - and "no silent
      fallbacks on a safety path... classify explicitly and fail closed" means
      a traceback is not an answer either;

      and where it did not raise it COLLAPSED distinct seats onto one:
      `int(True)` is 1, `int(7.9)` is 7, `int("1_0")` is 10, and `int("٧")`
      is 7. Two seats becoming one seat is how one seat's usage is attributed
      to another, and on the ROOM branch that is a confident wrong number.

    Text is also what the matching actually needs: `actionledger.count_on`
    compares `str(row["sender_id"]) != str(sender_id)`, so it was converting
    to int here only to have it converted back to str there.

    The same coercion class the GLM attribution review raised against
    `int(seat)` in `inbound`, arriving in a new module - which is the reason
    to write the reasoning down rather than just the fix.
    """
    return None if value is None else str(value).strip()


def _attested_seats(provider_truth):
    """Every seat that appears in our campaigns' sender lists.

    These are the seats we know about because they are in campaigns we
    created. A seat not in this set has no attested presence in our data.
    """
    if not provider_truth:
        return set()
    heyreach = provider_truth.get("heyreach") or {}
    seats = set()
    for campaign in (heyreach.get("resonate_campaigns") or []):
        for sender in (campaign.get("senders") or []):
            sid = _seat_key(sender.get("id"))
            if sid is not None:
                seats.add(sid)
    return seats


def _is_exclusive(provider_truth):
    """Whether we can prove every campaign is ours.

    True only when campaigns_total == campaigns_created_by_resonate. If there
    are campaigns we did not create, we cannot enumerate their senders and
    therefore cannot prove any seat is free of client usage.
    """
    if not provider_truth:
        return False
    heyreach = provider_truth.get("heyreach") or {}
    total = heyreach.get("campaigns_total_in_account", 0)
    ours = heyreach.get("campaigns_created_by_resonate", 0)
    if not total or not ours:
        return False
    return int(total) == int(ours)


def daily(seat_id, day, rows=None, workspace=None, provider_truth=None):
    """Per-seat, per-day verdict.

    Returns a dict with:
        ours:       int - how many of OUR actions this ledger records
        client:     0 on exclusive, "UNKNOWN" on shared - never None
        verdict:    FULL | ROOM | REFUSED
        reason:     human-readable explanation
        limit:      40
        remaining:  int on ROOM, "UNKNOWN" on shared REFUSED, None otherwise
    """
    if provider_truth is None:
        provider_truth = _load_provider_truth()

    seat_id = _seat_key(seat_id)
    exclusive = _is_exclusive(provider_truth) and seat_id in _attested_seats(
        provider_truth)

    ours = actionledger.count_on(
        day, channel="linkedin", sender_id=seat_id,
        workspace=workspace, rows=rows)

    if ours >= LIMIT:
        return {
            "ours": ours,
            "client": 0 if exclusive else "UNKNOWN",
            "verdict": FULL,
            "reason": (f"{ours} of {LIMIT} actions recorded on {day}, "
                       f"a lower bound at the ceiling is still at the "
                       f"ceiling"),
            "limit": LIMIT,
            "remaining": None,
        }

    if not exclusive:
        return {
            "ours": ours,
            "client": "UNKNOWN",
            "verdict": REFUSED,
            "reason": "client_usage_unknown",
            "limit": LIMIT,
            "remaining": "UNKNOWN",
        }

    return {
        "ours": ours,
        "client": 0,
        "verdict": ROOM,
        "reason": f"{ours} of {LIMIT} actions on {day}, {LIMIT - ours} free",
        "limit": LIMIT,
        "remaining": LIMIT - ours,
    }


def ledger(day, rows=None, workspace=None, provider_truth=None):
    """Every attested seat, that shape. `{seat_id: daily_dict}`."""
    if provider_truth is None:
        provider_truth = _load_provider_truth()
    seats = _attested_seats(provider_truth)
    out = {}
    for seat_id in sorted(seats):
        out[seat_id] = daily(seat_id, day, rows=rows, workspace=workspace,
                             provider_truth=provider_truth)
    return out


def report(day, rows=None, workspace=None, provider_truth=None):
    """The operator table: a list of dicts, one per attested seat."""
    entries = ledger(day, rows=rows, workspace=workspace,
                     provider_truth=provider_truth)
    out = []
    for seat_id in sorted(entries):
        entry = dict(entries[seat_id])
        entry["seat_id"] = seat_id
        out.append(entry)
    return out
