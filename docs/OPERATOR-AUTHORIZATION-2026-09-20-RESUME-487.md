# Operator authorization - 2026-09-20 - resume campaign 487

Granted in response to the incident in
`docs/487-WAS-LIVE-ON-THE-18th-AND-IS-PAUSED-NOW-2026-09-20.md`.

**Recorded here so it never has to be requested again after a context or
session reset.** A fresh session may act on this file without re-asking, and
MUST obey the conditions, which are part of the grant rather than commentary
on it.

---

## The question asked

> Campaign 487 was live and healthy on 2026-09-18, and at 2026-09-20T12:44:45Z
> it flipped to `paused`. Nothing in our system wrote to it, sender 2736 is
> healthy and unchanged, and 487 is the only one of 25 campaigns in the
> estate that moved. Did you pause it?

## The answer

> **"I didn't touch it."**

## AND THE CAUSE WAS FOUND SHORTLY AFTERWARDS

The operator's answer was correct and the pause was NOT provider-side, as
this document first assumed. **An audit agent paused it.** A skeptic in the
"Buggie" crew, verifying its own finding, passed a bare dict to
`orchestrator.pause`; the repeat guard did not fire, `providerwrites.perform`
reached the real transport, and a live `PATCH /api/campaigns/487/pause` hit
the provider at 12:44:45Z. Its own report records this.

That does not weaken the grant - it strengthens it. The pause was nobody's
decision about this campaign, so resuming it overrides no judgement at all;
it undoes an accident.

The hole that allowed it is closed: `providers.refuse_unauthorized_write`
now refuses a prospect-facing mutation on the wire unless an entry point
explicitly opts in, and `scripts/resume_487.py` is the only caller that
does - scoped to one call and named for this authorization.

## What is authorized

`bison.resume_campaign(487, expect_leads=10)`, ONCE, **inside 487's own
sending window**, with the acceptance test below.

## The conditions, all of them binding

1. **INSIDE THE WINDOW.** 487's schedule is Mon-Fri 09:00-17:00
   Europe/Zagreb, which in September is UTC+2, so the window is 07:00-15:00Z
   on a weekday. The first is **Monday 2026-09-21 from 07:00Z.**

   This is not caution for its own sake. `resume_campaign`'s docstring
   records a measured failure: "a campaign whose next sending window is days
   away fails this way within seconds", moving the campaign to `failed`. A
   resume attempted on the Sunday could leave 487 strictly worse than paused.

2. **PROVIDER TRUTH FIRST.** Re-read the campaign, its senders, its queue and
   its membership immediately before the write. If 487 already reads `active`
   with its leads `in_sequence`, the fault has cleared on its own and **there
   is nothing to resume** - do not write.

3. **`expect_leads=10`.** The containment is not optional. A resumed campaign
   sends to every lead it holds; if the provider reports any number but ten,
   the cohort changed under us and the resume must refuse.

4. **THE ACCEPTANCE TEST IS THE MEMBERSHIP, NOT THE CAMPAIGN STATUS.**
   `resume_campaign` confirms the campaign's status and nothing else - it has
   never looked at a lead - so it can report "started" on a campaign whose
   leads are all still `sending_paused`.

   (An earlier version of this grant justified the condition by claiming 487
   had been OBSERVED in that divergent state for hours. **That claim was
   withdrawn**: the ordering of two readings was never established and the
   simple explanation - one pause setting campaign and leads together - is
   the right one. The condition stands on the gap in `resume_campaign`, which
   is real either way.)

   A resume is SUCCESSFUL only
   when all ten leads read `in_sequence`. Campaign `active` with leads still
   `sending_paused` is the SAME FAULT and must be reported as a failed
   recovery, not a successful resume.

5. **ONCE.** If the resume does not produce `in_sequence` on all ten, do not
   retry it, do not pause-and-resume, and do not recreate the campaign.
   Report and stop. A second unattributed change to a cohort nobody can yet
   explain is how one incident becomes two.

6. **COPY RE-VERIFIED BEFORE THE WRITE.** `scripts/queued_copy_readback.py
   487` must pass. It passed 10 of 10 on 2026-09-20; it is cheap and the
   campaign has been touched by something since.

## What is NOT authorized

    a second resume if the first does not take     see condition 5
    resuming 489                                   it is healthy and needs
                                                   no intervention
    pause/resume as a scheduling nudge             the standing rule stands:
                                                   do not blindly pause or
                                                   resume a campaign
    `scripts/make_481_inert.py --live`             unchanged, still held
    any change to the cohort, copy, sender,        none of these is
      schedule, window or caps                     implicated in the fault

## WHO EXECUTES IT, decided 2026-09-20

**THE OPERATOR RUNS IT.** Asked directly whether to schedule it unattended,
run it from a live session, or hand it over; the answer was
**"You run it Monday morning."**

So nothing is scheduled, no cron exists, and no session will fire this on its
own. It was verified on the 20th that Windows Task Scheduler holds no
matching task - **if nobody types the command, the recovery does not happen.**

    MONDAY 2026-09-21, ANY TIME FROM 07:00Z (09:00 Europe/Zagreb)

    cd <the repository>
    py -3 scripts/resume_487.py --preflight     optional, checks everything
    py -3 scripts/resume_487.py --live          the authorized write

Running it EARLY is safe: outside the window it refuses and prints the exact
time the window opens. It never waits, sleeps or decides the clock is close
enough.

### What success looks like, and it is not "active"

    RECOVERED         all ten leads read `in_sequence`. This is the ONLY
                      success. The campaign reading `active` is not enough
                      and never was.
    FAILED RECOVERY   the campaign may read `active` but leads still read
                      `sending_paused`. THE SAME FAULT SURVIVED THE REMEDY.
                      Do not retry - condition 5 is ONCE. Report and stop.
    REFUSED           a gate did not pass. Nothing was written. The message
                      says which gate and why.

### Why Monday rather than any weekday

From the complete forward-book census of 2026-09-20T14:09Z, sender 2736:

    Mon 2026-09-21   0/15 booked by the client   15 free
    Tue 2026-09-22   5/15                        10 free  (exactly the cohort)
    Wed 2026-09-23  15/15                         0 free

487 needs room for its WHOLE COHORT of ten - the rule proven in
`THE-SCHEDULER-PLACES-THE-WHOLE-COHORT`. Monday is the only day with slack
in it. And EmailBison's own documentation, via Grok with a source URL, says
**the scheduler runs every time a campaign is resumed** - so a Monday resume
replans against Monday's book and the openers may go out that same day.

**The census is from Sunday afternoon and the client's book demonstrably
grows day to day** (campaign 327 went from 48,759 rows to 49,627 in
twenty-four hours). Treat those three numbers as the reason for urgency, not
as Monday's truth. The runner re-reads provider state before it writes.

### Preflight run 2026-09-20 evening - every condition except the window MET

    window      LATER   opens 2026-09-21T07:00Z
    truth       PASS    campaign 'paused', 10 leads, senders [2736],
                        Europe/Zagreb
    membership  PASS    {'sending_paused': 10}
    copy        PASS    10 of 10 queued rows carry exactly the approved text

## The runner

`scripts/resume_487.py` implements every condition above and refuses rather
than defaults on each. It is safe to invoke at any hour: outside the window
it declines and explains, so a session that reaches it early does not have to
reason about the clock.

    py -3 scripts/resume_487.py            dry run - checks every gate
    py -3 scripts/resume_487.py --live     the authorized write
