#!/usr/bin/env python3
"""People who said they would be back, and whether today is the day.

## A date means re-evaluate, not send

The same rule `revival` is built on, and for the same reason. "They said
the 8th" is not permission to write on the 8th; it is a reason to look
again on the 8th. So this produces a *verdict per person* and never an
action, never a draft, never a queued step.

## The state this has to reason around, stated plainly

An out-of-office classifies as `OUT_OF_OFFICE`, which
`accountpolicy.CLASSIFIER_OUTCOME` maps to `NOT_NOW`, whose plan is
`replier=stop`. So today an autoresponder **stops that contact**, exactly
as a flat refusal does, and nothing ever lifts it. That is why a return
date was worth reading and why this module exists.

It does not lift it either. `accountpolicy.apply_reply` "only ever writes
state that is absent, so a classification cannot lift a hold"; `revival`
says the same - a timer "may add to that state and may never subtract from
it". A scheduler that cleared `stopped` because a date arrived would be
the one thing in this system allowed to reopen a person automatically, and
it would do it on the strength of a regex reading of an autoresponder.

So the asymmetry holds: this reports that somebody is due back and that
nothing else stands in the way. A person lifts the stop, and everything
downstream - approval, eligibility, verification, the kill switch - runs
exactly as it would for any other outreach.

## What it looks past, and only this

Exactly one piece of state: a `stopped` whose `reason` is `not_now`, which
`CLASSIFIER_OUTCOME` produces for `out_of_office` and nothing else. That
stop *is* the deferral being followed up, so treating it as a refusal
would make every out-of-office permanent and this module pointless.

Every other blocker still blocks, and the permanent ones are checked
first, before a date is even read:

    unsubscribed, suppressed        NEVER - they asked us to stop
    account-level removal           NEVER
    a stop for any other reason     NEVER - that is a refusal, not a wait
    they have left the company      NEVER - for this person
    a reply since the absence       NOT_YET - a human has this now
    a live conversation, a meeting  NOT_YET
    fatigue                         NOT_YET
    no readable return date         NEEDS_A_PERSON
    the date has not arrived        NOT_YET

## Superseding

The latest absence wins. Somebody who extends their leave sends a second
autoresponder, and reading the first one would follow up into the middle
of it.
"""
import argparse
import datetime
import json

from . import (account, accountpolicy as ap, clients, events, fatigue,
               revival, store)

# ------------------------------------------------------------------ verdicts

DUE = "due"
NOT_YET = "not_yet"
NEVER = "never"
NEEDS_A_PERSON = "needs_a_person"

VERDICTS = (DUE, NOT_YET, NEVER, NEEDS_A_PERSON)

VERDICT_LABEL = {
    DUE: "Back now - worth looking at",
    NOT_YET: "Not yet",
    NEVER: "Closed",
    NEEDS_A_PERSON: "They did not say when",
}

# The stop this module is allowed to look past, and nothing else. It is what
# `accountpolicy` writes for an out-of-office and for no other outcome.
DEFERRAL_REASON = ap.NOT_NOW

UNSUBSCRIBED = "they asked us to stop"
ACCOUNT_REMOVED = "the company asked us to stop"
REFUSED = "they were stopped for a reason that is not a wait"
DEPARTED = "they have left the company"
REPLIED_SINCE = "they have come back to us since; a person has this"
CONVERSATION_LIVE = "a conversation is live"
MEETING_BOOKED = "a meeting is booked"
FATIGUED = "this account has had too much recently"
NOT_DUE = "the date they gave has not arrived"
NO_DATE = "they did not say when they would be back"
BACK = "the date they gave has arrived and nothing else is in the way"


def today_iso(today=None):
    """The day to judge against. Never invented: a caller may pass one."""
    if today:
        return str(today)[:10]
    return store.now()[:10]


def _date(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------- the trigger

# The two ways somebody names a date for coming back. An out-of-office is
# an absence; a "try me in November" is not. They are different events and
# different sentences, and every question after that - is this person still
# approachable, has anything changed, is the date due - is identical, so
# they share this module rather than a copy of it.
DATED_EVENTS = (events.OUT_OF_OFFICE_RECORDED, events.NOT_NOW_RECORDED)

SOURCE_LABEL = {
    events.OUT_OF_OFFICE_RECORDED: "they were away",
    events.NOT_NOW_RECORDED: "they asked us to come back later",
}


def latest_absence(rec, contact_key):
    """The most recent dated intention from this person, or None.

    Later supersedes earlier, across both kinds. Somebody who extends their
    leave sends a second autoresponder; somebody who says "not now" after an
    out-of-office has replaced the earlier date, and following the older one
    up would land in the middle of what they actually asked for.
    """
    found = [e for e in (rec.get("events") or [])
             if e.get("type") in DATED_EVENTS
             and e.get("contact") == contact_key]
    if not found:
        return None
    return sorted(found, key=lambda e: str(e.get("at") or ""))[-1]


def _replied_since(rec, contact_key, when):
    """A reply from this person after their absence was recorded.

    The absence itself is a reply, so it is excluded by time rather than by
    type: anything at or before the moment we recorded the absence is that
    same message being read again.
    """
    for reply in account.replies(rec, contact_key):
        at = str(reply.get("at") or "")
        if at and when and at > str(when):
            return reply
    return None


def _others_replied_since(rec, contact_key, when):
    """A colleague who has replied since this absence, or None.

    Read directly rather than inferred from the account hold, which cannot
    answer it: the hold is idempotent, so it keeps whoever raised it first.
    """
    for reply in account.replies(rec):
        who = reply.get("contact_key")
        at = str(reply.get("at") or "")
        if who and who != contact_key and at and when and at > str(when):
            return who
    return None


def _departed(rec, contact_key):
    for reply in account.replies(rec, contact_key):
        if reply.get("classification") == "left_company":
            return True
    return False


def _has_meeting(rec):
    """Reading canonical state, not re-deciding a rule.

    `revival` asks the same question of the same event log. Which
    classifications *close* an account is a rule with one definition -
    `revival.CLOSING`, used below - but "is there a meeting recorded here"
    is a read, and importing a private helper to do it would couple two
    modules for one line.
    """
    return any(reply.get("classification") == "meeting"
               for reply in account.replies(rec))


def _contact_of(rec, contact_key):
    for contact in account.contacts_of(rec):
        if contact.get("key") == contact_key:
            return contact
    return None


# -------------------------------------------------------------- the verdict

def assess(rec, contact_key, today=None, config=None, workspace=None):
    """Is this person back, and is anything else in the way?

    Never an instruction. `DUE` means somebody may now look at this
    person; it does not lift their stop and it does not build a message.
    Returns None when there is no absence to follow up, which is not a
    verdict - it is simply not a candidate.
    """
    absence = latest_absence(rec, contact_key)
    if absence is None:
        return None

    workspace = workspace or rec.get("client")
    contact = _contact_of(rec, contact_key) or {}
    day = today_iso(today)

    def verdict(name, why, **extra):
        return {"record_id": rec.get("id"), "company": rec.get("company"),
                "domain": rec.get("domain"), "workspace": workspace,
                "contact": contact_key,
                "name": contact.get("name"),
                "verdict": name, "verdict_label": VERDICT_LABEL[name],
                "why": why,
                "return_date": absence.get("return_date"),
                "return_status": absence.get("return_status"),
                "absence_kind": absence.get("absence_kind"),
                "source": absence.get("type"),
                "source_label": SOURCE_LABEL.get(absence.get("type"), ""),
                "recorded_at": absence.get("at"),
                "as_of": day, **extra}

    # -- permanent, and before a date is read. Somebody who asked us to stop
    #    must not have their return date consulted to see if they are back.
    if contact.get("unsubscribed"):
        return verdict(NEVER, UNSUBSCRIBED)
    if contact.get("suppressed"):
        return verdict(NEVER, UNSUBSCRIBED)
    closed = _closing(rec)
    if closed:
        return verdict(NEVER, closed)
    state, state_why = ap.account_state(rec)
    if state == ap.SUPPRESS:
        return verdict(NEVER, ACCOUNT_REMOVED)
    if rec.get("state") == "dropped":
        return verdict(NEVER, rec.get("drop_reason") or "dropped")
    if _departed(rec, contact_key):
        return verdict(NEVER, DEPARTED)

    # -- a stop that is not this deferral is a refusal, and stays one.
    stopped = contact.get("stopped") or {}
    if stopped and stopped.get("reason") != DEFERRAL_REASON:
        return verdict(NEVER, REFUSED, detail=stopped.get("reason"))

    # -- they came back to us on their own. That is a conversation, and a
    #    follow-up written against a stale autoresponder would talk over it.
    since = _replied_since(rec, contact_key, absence.get("at"))
    if since is not None:
        return verdict(NOT_YET, REPLIED_SINCE,
                       detail=since.get("classification"))

    # -- account-level deferrals, read from the same authorities revival uses.
    if _has_meeting(rec):
        return verdict(NOT_YET, MEETING_BOOKED)

    # The absence held the account as well as the contact: `events.apply`
    # pauses the whole company on any reply, before anything is classified,
    # so the hold reads `outcome: unknown` even for an autoresponder.
    # Treating that as a live conversation would make every out-of-office
    # permanent, which is the state this module exists to fix.
    #
    # Two questions, because neither answers it alone. `_hold_account` is
    # idempotent, so the *first* reply to hold an account keeps the
    # attribution for ever: a colleague who replies afterwards never
    # appears in `by`, and reading only that would call their live
    # conversation this person's own absence. And a colleague who was
    # already in conversation before the absence never appears in a
    # since-the-absence search. So:
    #
    #   the hold was raised by somebody else   a conversation predating this
    #   somebody else replied since            a conversation started since
    if state == ap.HOLD and (state_why or {}).get("by") not in (
            None, contact_key):
        return verdict(NOT_YET, CONVERSATION_LIVE,
                       detail=(state_why or {}).get("by"))
    colleague = _others_replied_since(rec, contact_key, absence.get("at"))
    if colleague is not None:
        return verdict(NOT_YET, CONVERSATION_LIVE,
                       detail=f"{colleague} has replied since")
    tired = fatigue.account_check(rec, at=day, config=config)
    if tired.get("state") == fatigue.BLOCK:
        return verdict(NOT_YET, FATIGUED, detail=tired.get("why"))

    # -- now, and only now, the date.
    when = _date(absence.get("return_date"))
    if when is None:
        # An absence with no readable date is not a failure of this module;
        # it is a person's job. `ooo.return_date` recorded why.
        return verdict(NEEDS_A_PERSON, NO_DATE,
                       detail=absence.get("return_status"))
    now = _date(day)
    if now is None or now < when:
        return verdict(NOT_YET, NOT_DUE,
                       days_until=((when - now).days if now else None))
    return verdict(DUE, BACK, days_since_return=(now - when).days)


def _closing(rec):
    """An account-level reply that closes it. `revival.CLOSING` is the one
    definition of which classifications do that; a second list here would
    be a second answer to the same question."""
    for reply in account.replies(rec):
        closed = revival.CLOSING.get(reply.get("classification"))
        if closed:
            return closed
    return None


def candidates(recs, today=None, config=None, workspace=None):
    """Every recorded absence, judged. Ordered so the due ones read first."""
    rows = []
    for rec in recs or []:
        if workspace and rec.get("client") != workspace:
            continue
        seen = {e.get("contact") for e in (rec.get("events") or [])
                if e.get("type") in DATED_EVENTS}
        for contact_key in sorted(k for k in seen if k):
            row = assess(rec, contact_key, today=today, config=config,
                         workspace=workspace)
            if row is not None:
                rows.append(row)
    order = {DUE: 0, NEEDS_A_PERSON: 1, NOT_YET: 2, NEVER: 3}
    return sorted(rows, key=lambda r: (order[r["verdict"]],
                                       str(r.get("return_date") or ""),
                                       r["record_id"]))


def summarise(rows):
    counts = {name: 0 for name in VERDICTS}
    for row in rows:
        counts[row["verdict"]] += 1
    return counts


# ------------------------------------------------------------------- the CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m src.oooreturn",
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--client", help="one workspace, or every record")
    parser.add_argument("--today", help="judge against this date, not now")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    recs = store.load()
    config = clients.load(args.client) if args.client else None
    rows = candidates(recs, today=args.today, config=config,
                      workspace=args.client)

    if args.json:
        print(json.dumps({"as_of": today_iso(args.today),
                          "counts": summarise(rows), "rows": rows}, indent=2))
        return 0

    counts = summarise(rows)
    print(f"  as of {today_iso(args.today)}")
    for name in VERDICTS:
        print(f"    {VERDICT_LABEL[name]:28} {counts[name]}")
    print()
    for row in rows:
        if row["verdict"] not in (DUE, NEEDS_A_PERSON):
            continue
        who = row.get("name") or row["contact"]
        print(f"  {row['verdict_label']:28} {who} at {row['company']}")
        print(f"    {row['why']}")
        if row.get("return_date"):
            print(f"    they said {row['return_date']}")
    print("\nA date is a reason to look, not permission to write. Nothing")
    print("here lifts a stop, drafts a message or queues a step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
