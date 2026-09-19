#!/usr/bin/env python3
"""When can this mailbox actually send? Derived from the forward-book walk.

THE DEFECT THIS EXISTS TO CLOSE.
`docs/THE-SEND-DATE-IS-THE-MAILBOX-2026-09-19.md` proved that the day a cohort
sends is a property of the MAILBOX and not of the campaign. Sender 2736 was
booked 15/15 on Monday by client campaign 327 and 15/15 on Tuesday by client
campaign 328, so campaign 487's ten openers went to Wednesday - the first day
that mailbox had a single free slot.

Nothing in sender selection reads that. `senderinventory.readiness()` asks
whether an inbox is connected, warmed and under its bounce tolerance, all of
which are questions about DELIVERABILITY. None of them is a question about
LATENCY, so the selector cannot tell a mailbox with fifteen free slots
tomorrow from one booked solid for three days. That is why a cohort approved
on the 18th sends on the 24th.

`scripts/bison_forward_book_census.py` already computes the input and already
gets the hard part right - its report refuses to name a mailbox free when the
walk is incomplete. But it prints, and nothing imports it. This module is that
logic made callable, with the refusal contract kept rather than dropped on the
way out.

THE ASYMMETRY THAT MAKES THIS SAFE
----------------------------------

A walk of the forward book can only ever UNDERCOUNT commitments: a row not yet
reached is a row not yet counted. That asymmetry is not a nuisance, it is the
whole safety contract, and it runs one way:

    a count that already reaches the limit    proves FULL
    a count below the limit                   proves NOTHING on its own

So FULL survives an incomplete, stale or partial walk. ROOM does not, and
every path to ROOM here has to earn it.

VOCABULARY
----------

FULL
    The rows already counted reach or exceed the mailbox's daily limit for
    that day. Sound on any walk, complete or not.

ROOM
    The walk is complete, fresh, covers every active campaign, and the limit
    is known - and under all of that the day has free slots.

REFUSED
    The question cannot be answered from this evidence. Returned with a
    reason naming what is missing. **REFUSED IS NOT ROOM.** A caller that
    treats it as free has reintroduced the defect this module exists to close.

WHY FRESHNESS IS PART OF THE CONTRACT
-------------------------------------

The client's campaigns insert new scheduled rows on every sending day - 352
alone holds 95,726 of them. A walk finished on the 17th said sender 3437 had
eleven free slots on the 22nd; by the time campaign 489 was planned on the
18th, the provider put it on the 24th instead. The walk was not wrong when it
was taken. It was old.

So a walk that is fresh enough to prove FULL may be far too old to prove ROOM,
and `STALE_AFTER_HOURS` gates only the second.

READ-ONLY. Pure functions over a JSON file. No provider call, no credit, no
canonical write.
"""

import datetime
import json
import os

FULL = "FULL"
ROOM = "ROOM"
REFUSED = "REFUSED"

DEFAULT_STATE = os.path.join("work", "forward-book-census.json")

# One sending day. The client's scheduler inserts rows daily, so a walk older
# than this cannot be trusted to prove a mailbox free - only to prove it full.
STALE_AFTER_HOURS = 24

# How far ahead `earliest_day` will look before giving up. A mailbox with no
# free day inside three weeks is not a scheduling problem, it is a capacity
# one, and saying so is more useful than a date five months out.
DEFAULT_HORIZON_DAYS = 21

# Monday..Friday. Passed in by the caller rather than assumed, because which
# days a cohort may send on is a property of the CAMPAIGN SCHEDULE and not of
# the mailbox - 487 is Mon-Fri Europe/Zagreb while the client's own campaigns
# demonstrably send at weekends.
WEEKDAYS = (0, 1, 2, 3, 4)


class HeadroomRefused(ValueError):
    """The evidence cannot answer the question. Carries the reason."""


def load_state(path=None):
    """Read the census state file. Missing file is REFUSED, never empty."""
    path = path or DEFAULT_STATE
    if not os.path.exists(path):
        raise HeadroomRefused(
            f"no forward-book walk at {path!r}: commitments are unknown, "
            "which is not the same as zero")
    with open(path, "r", encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict) or not isinstance(
            state.get("campaigns"), dict):
        raise HeadroomRefused(
            f"{path!r} is not a census state file (no `campaigns` map)")
    return state


def walked_campaigns(state):
    """The campaign ids this walk covered, as strings."""
    return {str(c) for c in (state.get("campaigns") or {})}


def completeness(state):
    """`(complete, incomplete_ids)`. Complete means every walk reached its end."""
    campaigns = state.get("campaigns") or {}
    if not campaigns:
        return False, ()
    incomplete = tuple(sorted(
        str(cid) for cid, entry in campaigns.items()
        if not entry.get("complete")))
    return (not incomplete), incomplete


def walked_at(state):
    """The OLDEST `finished_at` across the walks, or None.

    The oldest rather than the newest: a census is only as current as its
    stalest campaign, and the stale one is where the missed rows are.
    """
    stamps = []
    for entry in (state.get("campaigns") or {}).values():
        stamp = entry.get("finished_at") or entry.get("started_at")
        if stamp:
            stamps.append(str(stamp))
    if not stamps:
        return None
    return min(stamps)


def _parse(stamp):
    text = str(stamp).replace("Z", "+00:00")
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def freshness(state, now=None, max_age_hours=STALE_AFTER_HOURS):
    """`(fresh, age_hours, walked_at)`. An unparseable stamp is NOT fresh."""
    stamp = walked_at(state)
    if stamp is None:
        return False, None, None
    walked = _parse(stamp)
    if walked is None:
        return False, None, stamp
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    age = (now - walked).total_seconds() / 3600.0
    return (age <= max_age_hours), age, stamp


def coverage(state, active_campaign_ids):
    """`(covers, missing)` - did the walk see every campaign that can book rows?

    A mailbox's commitments are the sum over every campaign that may schedule
    from it. A walk that missed one is not a smaller answer, it is a wrong
    one, because the rows it did not look at are exactly the rows that would
    have made the mailbox full.
    """
    walked = walked_campaigns(state)
    missing = tuple(sorted(
        str(c) for c in (active_campaign_ids or ()) if str(c) not in walked))
    return (not missing), missing


def book(state):
    """`{sender_id: {day: committed}}`, summed across every walked campaign."""
    out = {}
    for entry in (state.get("campaigns") or {}).values():
        for compound, count in (entry.get("by_sender_day") or {}).items():
            if "|" not in str(compound):
                continue
            sid, day = str(compound).rsplit("|", 1)
            if not day:
                continue
            try:
                sender = int(sid)
            except (TypeError, ValueError):
                continue
            out.setdefault(sender, {})
            out[sender][day] = out[sender].get(day, 0) + int(count or 0)
    return out


def committed(state, sender_id, day, forward=None):
    """Rows already counted for this mailbox on this day. A LOWER BOUND."""
    forward = book(state) if forward is None else forward
    return int((forward.get(int(sender_id)) or {}).get(str(day), 0))


def verdict(state, sender_id, day, limit, active_campaign_ids=(),
            need=1, now=None, forward=None, max_age_hours=STALE_AFTER_HOURS):
    """`(FULL | ROOM | REFUSED, reason, free)` for one mailbox on one day.

    `free` is the number of free slots when the answer is ROOM, and None
    otherwise - including for FULL, where the count is a lower bound and the
    true overage is unknown.

    The order of the checks is the point. FULL is tested FIRST, against the
    raw count, because it is sound on evidence too weak for anything else.
    Only once fullness is ruled out do the completeness, freshness, coverage
    and limit gates get a say, and any one of them refusing means REFUSED.
    """
    used = committed(state, sender_id, day, forward=forward)

    try:
        cap = int(limit)
    except (TypeError, ValueError):
        cap = None

    # FULL first: an undercount that already reaches the limit is still a full
    # mailbox, and no amount of missing evidence can make it emptier.
    if cap is not None and used + int(need) > cap:
        return FULL, (f"{used} of {cap} already booked on {day}, so {need} "
                      f"more does not fit"), None

    if cap is None:
        return REFUSED, ("no daily limit is known for this mailbox, so "
                         "nothing may be planned on it"), None

    complete, incomplete = completeness(state)
    if not complete:
        return REFUSED, (f"the walk is incomplete ({', '.join(incomplete)}), "
                         f"so {used} is 'not seen yet' rather than 'free'"), None

    covers, missing = coverage(state, active_campaign_ids)
    if not covers:
        return REFUSED, (f"the walk did not cover active campaign(s) "
                         f"{', '.join(missing)}, whose rows would book this "
                         f"mailbox too"), None

    fresh, age, stamp = freshness(state, now=now, max_age_hours=max_age_hours)
    if not fresh:
        age_text = f"{age:.1f}h old" if age is not None else "undated"
        return REFUSED, (f"the walk is {age_text} (finished {stamp}) and the "
                         f"client's campaigns insert rows every sending day, "
                         f"so it can prove FULL but not ROOM"), None

    return ROOM, (f"{used} of {cap} booked on {day}, {cap - used} free"), (
        cap - used)


def earliest_day(state, sender_id, limit, active_campaign_ids=(), need=1,
                 on_or_after=None, sending_days=WEEKDAYS,
                 horizon_days=DEFAULT_HORIZON_DAYS, now=None,
                 max_age_hours=STALE_AFTER_HOURS):
    """The first sending day this mailbox can take `need` more. `(day, reason)`.

    Returns `(None, reason)` when no day inside the horizon has room, and
    raises nothing: a mailbox with no room is an answer, not an error.

    **A REFUSED day is skipped rather than accepted.** If every day in the
    horizon refuses, the result is `(None, ...)` naming the first refusal,
    because a selector that fell through to "probably fine" would be exactly
    the blindness this module was written to remove.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if on_or_after is None:
        start = now.date()
    elif isinstance(on_or_after, str):
        start = datetime.date.fromisoformat(on_or_after)
    elif isinstance(on_or_after, datetime.datetime):
        start = on_or_after.date()
    else:
        start = on_or_after

    forward = book(state)
    allowed = set(sending_days or ())
    first_refusal = None
    looked = 0

    for offset in range(int(horizon_days) + 1):
        day = start + datetime.timedelta(days=offset)
        if allowed and day.weekday() not in allowed:
            continue
        looked += 1
        state_word, reason, free = verdict(
            state, sender_id, day.isoformat(), limit,
            active_campaign_ids=active_campaign_ids, need=need, now=now,
            forward=forward, max_age_hours=max_age_hours)
        if state_word == ROOM:
            return day.isoformat(), reason
        if state_word == REFUSED and first_refusal is None:
            first_refusal = reason

    if first_refusal is not None:
        return None, (f"no day in the next {horizon_days} could be proven "
                      f"free: {first_refusal}")
    if not looked:
        return None, (f"no sending day falls inside the next {horizon_days} "
                      f"days for weekdays {sorted(allowed)}")
    return None, (f"every one of the {looked} sending day(s) in the next "
                  f"{horizon_days} is booked to this mailbox's limit")


def rank(state, senders, active_campaign_ids=(), need=1, on_or_after=None,
         sending_days=WEEKDAYS, horizon_days=DEFAULT_HORIZON_DAYS, now=None,
         max_age_hours=STALE_AFTER_HOURS):
    """Order candidate mailboxes by how soon each can send. Pure.

    `senders` is an iterable of `(sender_id, daily_limit)`. Returns a list of
    `{"sender_id", "limit", "day", "reason"}` sorted soonest-first, with the
    mailboxes that could not be proven free LAST rather than dropped - a
    caller that needs to explain why a slow mailbox was chosen needs to see
    the ones that refused.

    **This ranks on LATENCY ONLY.** It says nothing about whether an inbox is
    connected, warm, under its bounce tolerance or attributable to the right
    human, and it must never be the only filter in a selection path.
    `senderinventory.readiness()` answers deliverability and
    `senderidentity` answers whose mailbox it is; both still apply, and the
    mailbox with the earliest free day is routinely the wrong one to pick.
    """
    out = []
    for sender_id, limit in senders:
        day, reason = earliest_day(
            state, sender_id, limit, active_campaign_ids=active_campaign_ids,
            need=need, on_or_after=on_or_after, sending_days=sending_days,
            horizon_days=horizon_days, now=now, max_age_hours=max_age_hours)
        out.append({"sender_id": int(sender_id), "limit": limit,
                    "day": day, "reason": reason})
    out.sort(key=lambda row: (row["day"] is None, row["day"] or "",
                              row["sender_id"]))
    return out
