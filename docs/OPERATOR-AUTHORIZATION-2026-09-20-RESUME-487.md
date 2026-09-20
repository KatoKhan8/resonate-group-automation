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
> it flipped to `paused` - its ten leads had already flipped to
> `sending_paused` before that. Nothing in our system wrote to it, sender 2736
> is healthy and unchanged, and 487 is the only one of 25 campaigns in the
> estate that moved. Did you pause it?

## The answer

> **"I didn't touch it."**

So the pause is **unattributed and presumed provider-side**. The operator did
not pause it, which removes the one reading under which resuming would have
been overriding a human decision rather than recovering from a fault.

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

4. **THE ACCEPTANCE TEST IS THE MEMBERSHIP, NOT THE CAMPAIGN STATUS.** This
   is the whole lesson of the incident. 487 read `active` for hours while
   every one of its leads read `sending_paused`, and `resume_campaign`
   confirms the campaign status and nothing else. A resume is SUCCESSFUL only
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

## The runner

`scripts/resume_487.py` implements every condition above and refuses rather
than defaults on each. It is safe to invoke at any hour: outside the window
it declines and explains, so a session that reaches it early does not have to
reason about the clock.

    py -3 scripts/resume_487.py            dry run - checks every gate
    py -3 scripts/resume_487.py --live     the authorized write
