#!/usr/bin/env python3
"""Accounts that went quiet, and whether there is anything new to say to them.

## A timer means re-evaluate, not send

That is the whole design. "Ninety days have passed" is not a reason to
write to somebody; it is a reason to look again. So this module produces a
*verdict per account* and never an action, never a draft, never a queued
step. Everything downstream - the campaign builder, approval, the
eligibility gate - runs exactly as it does for any other outreach, because
an account that went quiet has earned no exemptions.

## Reviving with the angle that already failed is a repeat

An account that heard "your utilisation reporting is manual" and said
nothing does not need to hear it again in March. If the only thing that
has changed is the date, the honest verdict is that there is nothing new,
and the account waits.

So the question is not "has enough time passed" but "has anything changed
that gives us something to say". Four things can:

    a new signal        something happened there since we last wrote
    a new person        a decision maker we have never approached
    an unused angle     a pain this client sells against that we never led with
    an employment change  the person we wrote to has gone

Any one of them makes a case. None of them makes a decision - `READY`
means somebody may now look at this account, and the four reasons are on
the row so the person looking can see what the case rests on.

## What closes an account permanently, and what merely defers it

`NEVER` and `NOT_YET` are different answers and merging them would be the
expensive mistake in both directions: re-approaching somebody who asked us
to stop, or permanently writing off an account that is simply mid-
conversation this week.

    NEVER        unsubscribed, account-level removal, an existing client,
                 or told plainly that we had the wrong company
    NOT_YET      a live conversation, a booked meeting, a running campaign,
                 fatigue, or simply not enough time yet
    NOTHING_NEW  eligible, and nothing has changed since we last wrote
    READY        eligible, and at least one thing has

## Everything is read from canonical state

Touches come from confirmed events through `account.touches`, replies from
`account.replies`, the account's own state from `accountpolicy`, fatigue
from `fatigue`. Nothing is re-derived here and nothing is written. A second
opinion about what a reply meant would be a second reply policy.
"""
import argparse
import json

from . import (account, accountpolicy as ap, clients, evidence, fatigue,
               signals as signal_module, store)

# ------------------------------------------------------------------ verdicts

NEVER = "never"
NOT_YET = "not_yet"
NOTHING_NEW = "nothing_new"
READY = "ready"

VERDICTS = (NEVER, NOT_YET, NOTHING_NEW, READY)

VERDICT_LABEL = {
    NEVER: "Closed",
    NOT_YET: "Not yet",
    NOTHING_NEW: "Nothing new to say",
    READY: "Worth looking at again",
}

# ------------------------------------------------------------------- reasons

# Permanent.
UNSUBSCRIBED = "they asked us to stop"
ACCOUNT_REMOVED = "the company asked us to stop"
EXISTING_CLIENT = "they are already a client"
WRONG_COMPANY = "they told us we had the wrong company"

# For now.
NEVER_CONTACTED = "nothing has been sent to this account yet"
TOO_SOON = "not long enough since the last touch"
CONVERSATION_LIVE = "a conversation is live"
MEETING_BOOKED = "a meeting is booked"
FATIGUED = "this account has had too much recently"

# What makes a case.
NEW_SIGNAL = "new_signal"
NEW_PERSON = "new_person"
UNUSED_ANGLE = "unused_angle"
EMPLOYMENT_CHANGE = "employment_change"

CASES = (NEW_SIGNAL, NEW_PERSON, UNUSED_ANGLE, EMPLOYMENT_CHANGE)

CASE_LABEL = {
    NEW_SIGNAL: "something happened there since we last wrote",
    NEW_PERSON: "a decision maker we have never approached",
    UNUSED_ANGLE: "a pain we have never led with here",
    EMPLOYMENT_CHANGE: "the person we wrote to has moved on",
}

DEFAULTS = {
    # Long on purpose. A re-approach sooner than this is not a revival, it
    # is the same campaign with a gap in it, and the recipient reads it
    # that way.
    "cooling_days": 90,
    # How far back a signal still counts as "since we last wrote". Without
    # a floor, an account last touched two years ago revives on a signal
    # from eighteen months ago, which is new only in the arithmetic.
    "signal_within_days": 120,
}

# Reply classifications that close an account rather than pause it. Read
# from the outcome vocabulary `events` already uses, so a new outcome does
# not silently land in the wrong half.
CLOSING = {
    "unsubscribe": UNSUBSCRIBED,
    "account_dnc": ACCOUNT_REMOVED,
    "existing_client": EXISTING_CLIENT,
    "wrong_person": None,          # not closing: it names somebody else
}


def settings(config):
    merged = dict(DEFAULTS)
    merged.update(((config or {}).get("revival") or {}))
    return merged


# --------------------------------------------------------------- the history

def last_touch(rec):
    """When we last confirmably reached anybody here, or None.

    Confirmed only. A prepared payload and an approved draft are not
    outreach that happened, and a cooling period measured from a step that
    never left would start the clock on a message nobody received.
    """
    confirmed = account.touches(rec, confirmed_only=True)
    return confirmed[-1]["at"] if confirmed else None


def angles_used(rec):
    """Every angle this account has actually been written with.

    From the contacts that were touched, because the angle is a property
    of who we wrote to and what we said to them. An angle carried by a
    draft nobody sent has not been used.
    """
    touched = {t["contact_key"] for t in account.touches(rec, confirmed_only=True)}
    used = set()
    for contact in account.contacts_of(rec):
        if contact.get("key") in touched and contact.get("angle"):
            used.add(contact["angle"])
    return used


def angles_available(config, persona=None):
    """The angles this client sells against, from their own configuration.

    They live at `personas.<persona>.angles`, which is where
    `clients.angles_for` reads them - not at a top level of their own.
    Reading a level that does not exist returns an empty set, makes every
    angle look used, and answers "nothing new here" for the whole estate
    while looking exactly like a working check.

    `persona` narrows it to one role's angles. Without it, every angle the
    client sells against counts, which is the right question at account
    level: a pain we have never led with at this company is worth saying
    even if the person who would hear it is not the one we wrote to.
    """
    found = set()
    # `or {}` because every other function here takes a missing config in
    # its stride and this one raised. `clients.personas(None)` throws, and
    # the only reason no screen hit it is that both callers happen to pass
    # a config; a benchmark calling it directly did not.
    for name in clients.personas(config or {}):
        if persona and name != persona:
            continue
        found.update(k for k in clients.angles_for(config, name) if k)
    return found


def untouched_contacts(rec):
    """Selected decision makers this account has never heard from."""
    touched = {t["contact_key"] for t in account.touches(rec, confirmed_only=True)}
    return [c for c in account.contacts_of(rec)
            if c.get("selected") and c.get("key") not in touched]


def _closing_outcome(rec):
    """A reply classification that closes the account, or None."""
    for reply in account.replies(rec):
        closed = CLOSING.get(reply.get("classification"))
        if closed:
            return closed
    return None


def _has_meeting(rec):
    for reply in account.replies(rec):
        if reply.get("classification") == "meeting":
            return True
    return False


def _departed(rec):
    """Did somebody we wrote to leave the company?

    A `left_company` outcome is the clearest revival trigger there is: the
    reason the account went quiet has just been removed, and whoever
    replaced them has never heard from us.
    """
    for reply in account.replies(rec):
        if reply.get("classification") == "left_company":
            return True
    return False


def _new_signals(rec, since, today=None, config=None, policy=None,
                 workspace=None, signal_index=None):
    """Signals observed after the last touch and recently enough to matter."""
    policy = policy or settings(config)
    workspace = workspace or rec.get("client")
    found = list(signal_module.derive(rec, workspace, config, today))
    found += (list((signal_index or {}).get(rec.get("id")) or [])
              if signal_index is not None
              else signal_module.for_record(rec.get("id"), workspace))

    out = []
    for signal in found:
        # Engagement signals are readings of our own outreach. "We wrote to
        # them" is not news from the account, and counting it would revive
        # every quiet account on the strength of having gone quiet.
        if signal_module.SCOPE_OF.get(signal.get("type")) == \
                signal_module.ENGAGEMENT:
            continue
        at = signal.get("observed_at")
        if not at:
            continue
        if since and str(at) <= str(since):
            continue
        age = evidence.age_days(at, today)
        if age is not None and age > int(policy["signal_within_days"]):
            continue
        out.append(signal)
    return out


# ---------------------------------------------------------------- the verdict

def assess(rec, today=None, config=None, workspace=None, signal_index=None):
    """Should anybody look at this account again, and what would be new?

    Never an instruction. `READY` means a person may now consider this
    account for a campaign, and everything that governs outreach - the
    approval gate, the eligibility gate, suppression, fatigue - applies to
    whatever they build exactly as it would to a first approach.
    """
    policy = settings(config)
    workspace = workspace or rec.get("client")

    def verdict(name, why, **extra):
        return {"record_id": rec.get("id"), "company": rec.get("company"),
                "domain": rec.get("domain"), "workspace": workspace,
                "verdict": name, "verdict_label": VERDICT_LABEL[name],
                "why": why, "cases": [], "last_touch": None, **extra}

    # Permanent first, and before anything is computed. An account that
    # asked us to stop must not have its signals read to see whether it is
    # interesting again.
    closed = _closing_outcome(rec)
    if closed:
        return verdict(NEVER, closed)
    state, state_why = ap.account_state(rec)
    if state == ap.SUPPRESS:
        return verdict(NEVER, ACCOUNT_REMOVED)
    if rec.get("state") == "dropped":
        return verdict(NEVER, rec.get("drop_reason") or "dropped")

    touched_at = last_touch(rec)
    if touched_at is None:
        # Not a revival candidate: there is nothing to revive. Named rather
        # than swept into NOT_YET, because "we have not started" and "we
        # tried and it went quiet" are different queues.
        return verdict(NOT_YET, NEVER_CONTACTED)

    if _has_meeting(rec):
        return verdict(NOT_YET, MEETING_BOOKED, last_touch=touched_at)
    if state == ap.HOLD:
        return verdict(NOT_YET, CONVERSATION_LIVE, last_touch=touched_at,
                       detail=(state_why or {}).get("reason"))

    age = evidence.age_days(touched_at, today)
    cooling = int(policy["cooling_days"])
    if age is not None and age < cooling:
        return verdict(NOT_YET, TOO_SOON, last_touch=touched_at,
                       days_since=age, cooling_days=cooling)

    tired = fatigue.account_check(rec, at=today, config=config)
    if tired.get("state") == fatigue.BLOCK:
        return verdict(NOT_YET, FATIGUED, last_touch=touched_at,
                       days_since=age, detail=tired.get("why"))

    # Eligible by time. Now: is there anything new to say?
    cases = []
    fresh = _new_signals(rec, touched_at, today, config, policy, workspace,
                         signal_index)
    if fresh:
        cases.append({"case": NEW_SIGNAL, "label": CASE_LABEL[NEW_SIGNAL],
                      "detail": ", ".join(sorted({
                          signal_module.LABEL.get(s.get("type"), s.get("type"))
                          for s in fresh}))[:200],
                      "count": len(fresh)})

    if _departed(rec):
        cases.append({"case": EMPLOYMENT_CHANGE,
                      "label": CASE_LABEL[EMPLOYMENT_CHANGE],
                      "detail": "somebody we wrote to has left", "count": 1})

    new_people = untouched_contacts(rec)
    if new_people:
        cases.append({"case": NEW_PERSON, "label": CASE_LABEL[NEW_PERSON],
                      "detail": ", ".join(
                          c.get("name") or c.get("key") for c in new_people
                      )[:200],
                      "count": len(new_people)})

    unused = angles_available(config) - angles_used(rec)
    if unused:
        cases.append({"case": UNUSED_ANGLE, "label": CASE_LABEL[UNUSED_ANGLE],
                      "detail": ", ".join(sorted(unused))[:200],
                      "count": len(unused)})

    if not cases:
        return verdict(NOTHING_NEW,
                       "nothing has changed here since we last wrote, so a "
                       "re-approach would be the same message with a later "
                       "date on it",
                       last_touch=touched_at, days_since=age)

    return verdict(READY,
                   "; ".join(c["label"] for c in cases),
                   last_touch=touched_at, days_since=age, cases=cases)


def candidates(recs, today=None, config=None, workspace=None,
               signal_index=None):
    """Every account assessed, ready ones first, then by how long they waited.

    All of them rather than only the ready ones: the counts a person needs -
    how many are closed, how many are simply too soon, how many have
    nothing new - are lost by a filter, and "no revival candidates" reads
    very differently from "forty, and none of them has anything new".
    """
    # Built once for the whole walk. `signals.for_record` re-reads the
    # entire signal file per account otherwise - measured at 9.4ms an
    # account and rising against a 2,000-signal file, against 0.29ms and
    # flat with an index. The parameter existed and nothing ever passed
    # one, which is the same shape as the defect this module was written
    # to avoid.
    if signal_index is None:
        signal_index = signal_module.index(workspace or
                                           (recs[0].get("client")
                                            if recs else None))
    out = [assess(rec, today, config, workspace, signal_index)
           for rec in recs]
    order = {READY: 0, NOTHING_NEW: 1, NOT_YET: 2, NEVER: 3}
    out.sort(key=lambda r: (order[r["verdict"]],
                            -(r.get("days_since") or 0),
                            str(r["record_id"])))
    return out


def summarise(rows):
    counts = {v: 0 for v in VERDICTS}
    cases = {c: 0 for c in CASES}
    for row in rows:
        counts[row["verdict"]] += 1
        for case in row.get("cases") or []:
            cases[case["case"]] += 1
    return {
        "counts": counts,
        "cases": cases,
        "ready": counts[READY],
        "total": len(rows),
        # Said on the summary rather than only in the docstring, because
        # this is the number somebody will want to act on in bulk.
        "note": "a verdict, never an instruction. READY means an account "
                "may be looked at again - every gate that governs outreach "
                "still applies to whatever is built from it",
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.revival",
                                description=__doc__)
    p.add_argument("--client")
    p.add_argument("--today")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = [r for r in store.load()
            if not a.client or r.get("client") == a.client]
    config = clients.load(a.client) if a.client else {}
    rows = candidates(recs, today=a.today, config=config, workspace=a.client)
    found = summarise(rows)
    if a.json:
        print(json.dumps({"summary": found, "rows": rows}, indent=2,
                         sort_keys=True))
        return 0

    for verdict in VERDICTS:
        print(f"{VERDICT_LABEL[verdict]:<24} {found['counts'][verdict]}")
    print()
    for row in rows:
        if row["verdict"] != READY:
            continue
        print(f"  {row['record_id']:<20} {row['company'] or '':<28} "
              f"{row.get('days_since')} days quiet")
        for case in row["cases"]:
            print(f"      {case['label']}: {case['detail']}")
    print("\n" + found["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
