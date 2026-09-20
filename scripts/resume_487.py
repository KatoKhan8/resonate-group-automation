#!/usr/bin/env python3
"""Recover campaign 487 from the 2026-09-20 pause. Dry run by default.

    py -3 scripts/resume_487.py            every gate, no write
    py -3 scripts/resume_487.py --live     the authorized write

Authorized by `docs/OPERATOR-AUTHORIZATION-2026-09-20-RESUME-487.md`, which
is the grant and the conditions both. The incident is
`docs/487-WAS-LIVE-ON-THE-18th-AND-IS-PAUSED-NOW-2026-09-20.md`.

## Why this is a script and not a call

`bison.resume_campaign(487, expect_leads=10)` is one line. It is wrapped
because the authorization attaches five conditions to it, and a condition
that lives only in a document is a condition somebody performs from memory at
seven in the morning.

## THE ACCEPTANCE TEST IS THE MEMBERSHIP

`resume_campaign` confirms the CAMPAIGN's status and nothing else. That is
the gap: it can return "started" on a campaign whose leads are all still
`sending_paused`, because nothing in it has ever looked at a lead.

(The incident document originally claimed 487 had been observed in exactly
that divergent state. It was CORRECTED - the ordering of two observations was
never established and the simple explanation, one pause setting both, is the
right one. The gap in `resume_campaign` is real either way, and it is what
this acceptance test covers.)

So this does not report success on a 200, and it does not report success on
`status: active` either.

**Ten leads reading `in_sequence` is the only success.** Campaign `active`
with leads still `sending_paused` is the same fault surviving the remedy, and
it is reported as a FAILED RECOVERY. The distinction matters because the
second outcome is the one that would otherwise be announced as a fix.

## Safe to invoke at any hour

The window gate refuses rather than waits. A session that reaches this at
03:00Z on the Sunday is told why not and what time to come back, and writes
nothing - it does not sleep, block, or decide the clock is close enough.
"""
import argparse
import datetime
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.bison_readback import _setup_data_access      # noqa: E402

CAMPAIGN = 487
EXPECT_LEADS = 10
EXPECT_SENDERS = [2736]
# 487's schedule: Mon-Fri 09:00-17:00 Europe/Zagreb. September is UTC+2, so
# the window is 07:00-15:00Z. Read from the PROVIDER at run time rather than
# trusted from here - these are the expectation, and a disagreement is a
# finding rather than a detail.
WINDOW_UTC = (7, 15)
WEEKDAYS = (0, 1, 2, 3, 4)
HEALTHY = "in_sequence"
FAULT = "sending_paused"


class Refused(RuntimeError):
    """A condition of the authorization was not met. Nothing was written."""


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def window_gate(now=None):
    """Condition 1. Inside 487's own sending window, or a refusal that says
    when to come back.

    `resume_campaign`'s docstring records the measured failure this prevents:
    a campaign whose next window is away moves to `failed` within seconds of
    a resume, which would leave 487 worse than paused.
    """
    now = now or _now()
    if now.weekday() not in WEEKDAYS:
        days = (7 - now.weekday()) % 7 or 7
        nxt = (now + datetime.timedelta(days=days)).replace(
            hour=WINDOW_UTC[0], minute=0, second=0, microsecond=0)
        raise Refused(
            f"487's window is Mon-Fri and it is {now:%A}. The window opens "
            f"{nxt:%Y-%m-%dT%H:%MZ}. Nothing written.")
    if not (WINDOW_UTC[0] <= now.hour < WINDOW_UTC[1]):
        if now.hour < WINDOW_UTC[0]:
            nxt = now.replace(hour=WINDOW_UTC[0], minute=0, second=0,
                              microsecond=0)
        else:
            days = 1 if now.weekday() < 4 else (7 - now.weekday())
            nxt = (now + datetime.timedelta(days=days)).replace(
                hour=WINDOW_UTC[0], minute=0, second=0, microsecond=0)
        raise Refused(
            f"487's window is {WINDOW_UTC[0]:02d}:00-{WINDOW_UTC[1]:02d}:00Z "
            f"and it is {now:%H:%M}Z. The window opens {nxt:%Y-%m-%dT%H:%MZ}. "
            f"Nothing written.")
    return True


def membership_of(bison, campaign_id=CAMPAIGN):
    rows = bison.membership(campaign_id) or {}
    counted = {}
    for status in rows.values():
        counted[str(status)] = counted.get(str(status), 0) + 1
    return rows, counted


def truth_gate(bison):
    """Conditions 2 and 3. What the provider says right now, before anything.

    Returns the campaign row and the membership. Raises when the state is not
    the one the authorization was granted against - INCLUDING when the fault
    has cleared on its own, which is a refusal and not a disappointment.
    """
    row = bison.campaign(CAMPAIGN) or {}
    status = str(row.get("status") or "").lower()
    rows, counted = membership_of(bison)

    if status == "active" and counted.get(HEALTHY) == EXPECT_LEADS:
        raise Refused(
            f"487 already reads active with {EXPECT_LEADS} leads "
            f"{HEALTHY}. The fault cleared on its own and there is nothing "
            f"to resume. Nothing written.")
    if status != "paused":
        raise Refused(
            f"487 reads {status!r}. This authorization was granted against a "
            f"PAUSED campaign and covers nothing else. Nothing written.")

    held = bison.campaign_lead_count(CAMPAIGN)
    if held != EXPECT_LEADS:
        raise Refused(
            f"487 holds {held} lead(s) and the authorization names "
            f"{EXPECT_LEADS}. The cohort changed under us. Nothing written.")

    senders = bison.campaign_senders(CAMPAIGN)
    if sorted(int(s) for s in senders) != sorted(EXPECT_SENDERS):
        raise Refused(
            f"487 names senders {senders} and the authorization names "
            f"{EXPECT_SENDERS}. Nothing written.")

    schedule = bison.schedule(CAMPAIGN) or {}
    if str(schedule.get("timezone")) != "Europe/Zagreb":
        raise Refused(
            f"487's timezone reads {schedule.get('timezone')!r}, not "
            f"Europe/Zagreb, so the window gate above was computed against "
            f"the wrong clock. Nothing written.")
    return row, counted, schedule


def copy_gate():
    """Condition 6. The approved words, from the provider's own render."""
    from scripts import queued_copy_readback
    code = queued_copy_readback.main([str(CAMPAIGN)])
    if code != 0:
        raise Refused(
            "the queued copy does not match the approved copy. A campaign "
            "whose rendered text is not the approved text must not send. "
            "Nothing written.")
    return True


def verdict(counted):
    """Condition 4. The membership is the acceptance test, not the status."""
    if counted.get(HEALTHY) == EXPECT_LEADS:
        return "RECOVERED"
    if counted.get(FAULT):
        return "FAULT-SURVIVED"
    return "UNCLASSIFIED"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="perform the authorized write")
    parser.add_argument("--preflight", action="store_true",
                        help="check every condition EXCEPT the window, so the "
                             "other five can be verified before the window "
                             "opens. Never writes.")
    args = parser.parse_args(argv)
    if args.preflight and args.live:
        parser.error("--preflight never writes; it cannot be combined with "
                     "--live")

    _setup_data_access()
    from src.providers import bison

    print("=" * 72)
    print(f"  RESUME {CAMPAIGN} - "
          f"{'LIVE' if args.live else 'DRY RUN'} - {_now():%Y-%m-%dT%H:%M:%SZ}")
    print("=" * 72)

    try:
        # THE WINDOW GATE IS FIRST IN THE LIVE PATH AND SKIPPED IN PREFLIGHT.
        # First, because a resume outside the window is measured to move a
        # campaign to `failed` and no other check matters if that happens.
        # Skippable in preflight for the opposite reason: a preparation run
        # that cannot execute until the window opens tells an operator
        # nothing on the Sunday evening they are preparing on. The other five
        # conditions are all checkable now, and knowing they hold is the
        # whole value of a preflight.
        if args.preflight:
            try:
                window_gate()
                print("  PASS  window    inside the window now")
            except Refused as not_yet:
                print(f"  LATER window    {not_yet}")
        else:
            window_gate()
            print("  PASS  window    inside 487's Mon-Fri 07:00-15:00Z window")
        row, counted, schedule = truth_gate(bison)
        print(f"  PASS  truth     campaign {row.get('status')!r}, "
              f"{EXPECT_LEADS} leads, senders {EXPECT_SENDERS}, "
              f"{schedule.get('timezone')}")
        print(f"        membership before: {counted}")
        copy_gate()
        print("  PASS  copy      the queued rows carry the approved text")
    except Refused as refusal:
        print(f"  REFUSED  {refusal}")
        return 2

    if not args.live:
        print()
        if args.preflight:
            print("  PREFLIGHT. Every condition except the window is MET, "
                  "and nothing was written.")
            print("  The window is the only thing outstanding.")
        else:
            print("  DRY RUN. Every gate passed and NOTHING WAS WRITTEN.")
        print("  The authorized write is: py -3 scripts/resume_487.py --live")
        return 0

    print()
    print(f"  WRITING  resume_campaign({CAMPAIGN}, "
          f"expect_leads={EXPECT_LEADS})")
    # THE OPT-IN IS HERE, AT THE ENTRY POINT, AND NOWHERE ELSE.
    #
    # `providers.allow_writes` is the transport guard added after an audit
    # agent paused THIS campaign on 2026-09-20 by importing `src` and calling
    # through with nothing in its way. The window is opened around ONE call,
    # named with the authorization it acts on, and closed immediately.
    #
    # Deliberately not inside `providerwrites.perform`: that is the path the
    # incident actually took, so a library that granted itself this window
    # would have authorised it.
    from src import providers
    try:
        with providers.allow_writes(
                "resume 487 per docs/OPERATOR-AUTHORIZATION-2026-09-20-"
                "RESUME-487.md"):
            answer = bison.resume_campaign(CAMPAIGN,
                                           expect_leads=EXPECT_LEADS)
    except Exception as exc:
        print(f"  PROVIDER REFUSED  {type(exc).__name__}: {exc}")
        print("  Condition 5: ONCE. Do not retry. Read provider truth and "
              "report.")
        return 1
    print(f"  provider answered: {answer}")

    # THE ACCEPTANCE TEST. Not the 200, and not the campaign status either.
    after_row = bison.campaign(CAMPAIGN) or {}
    _rows, after = membership_of(bison)
    print(f"  campaign status after: {after_row.get('status')!r}")
    print(f"  membership after:      {after}")
    state = verdict(after)
    print()
    if state == "RECOVERED":
        print(f"  RECOVERED. All {EXPECT_LEADS} leads read {HEALTHY!r}.")
        return 0
    if state == "FAULT-SURVIVED":
        print(f"  FAILED RECOVERY. The campaign may read "
              f"{after_row.get('status')!r}, but {after.get(FAULT)} lead(s) "
              f"still read {FAULT!r}. THIS IS THE SAME FAULT, not a fix, and "
              f"it must not be reported as one.")
        print("  Condition 5: ONCE. Do not retry. Report and stop.")
        return 1
    print(f"  UNCLASSIFIED membership {after}. Whether 487 is sending is "
          f"UNKNOWN. Read provider truth before doing anything else.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
