# TASK-028 - An eight-step email cadence, without changing what em5 means

Operator backlog: the BUILD CADENCE VARIANTS step, and experiment E1 in
`docs/ESTATE-LEARNING-2026-09-14.md`.

## GOAL

A second email cadence of eight steps over about twenty days, selectable by
name beside `productive_li_heavy_v1`, so that sequence LENGTH becomes a
comparable variable rather than a rewrite.

## WHY IT MATTERS

Measured on the client's own estate, reply rate by sequence length:

    1 step   0.85%   (n=3,163)     22 steps  2.23%   (n=2,422)
    8 steps  8.49%   (n=17,690)    44 steps  2.38%   (n=20,337)

Our production campaign runs five. The closest thing to a controlled
comparison in the estate - campaigns 334/335 running the SAME first five
subject lines as 327/328 at 22 steps instead of 8 - gives 2.23% against 8.39%.

This is evidence, not proof: length is confounded with recency and with list.
So the deliverable is a cadence that can be RUN AGAINST the five-step one,
not a replacement for it. Nothing here deletes or edits
`PRODUCTIVE_LI_HEAVY_V1`.

## THE HAZARD, AND IT IS THE WHOLE DIFFICULTY OF THIS TASK

`generate.purpose_for(channel, ordinal)` indexes ONE GLOBAL LADDER by
position:

    EMAIL_LADDER has exactly 5 rungs
    purpose_for("email", 6) returns None

A step carries no purpose of its own - `position()` computes its ordinal
within its channel and the ladder is looked up by that number. So:

**Appending three rungs to `EMAIL_LADDER` would silently change what `em5`
means.** Today rung 5 is "Close the loop. Give them an easy no, make no new
pitch, ask for nothing beyond permission to stop" - the breakup. In an
eight-rung ladder the breakup belongs at rung 8, and rung 5 becomes something
else. Every five-step cadence would keep asking for rung 5 and get the new
one.

That is not hypothetical. EmailBison campaign 481 is staged with nine real
leads carrying approved `subject_5`/`body_5`, and a regeneration after a
ladder change would rewrite the final email of a live sequence into a
different message without anybody choosing that.

So the ladder must become SELECTABLE rather than global. Whatever design you
choose - a per-cadence ladder name, a ladder on the sequence, a purpose on the
step - the test that decides it is:

    the existing five-step cadence's em5 still resolves to the breakup rung,
    byte for byte, after the change

Write that test FIRST.

## SCOPE

1. Make the ladder selectable, smallest change that works. Do not invent
   configuration nobody asked for; one mechanism, one caller.
2. Add an eight-rung email ladder. It is NOT invented - it is read off the
   client's best-performing sequence (12.23% reply), whose steps 6, 7 and 8
   are the cost of the current setup, a referral ask, and a breakup:

       1  relevance                     (existing rung 1)
       2  a different angle             (existing rung 2)
       3  new value / a use case        (existing rung 3)
       4  a short bump, different       (existing rung 4)
       5  the cost of the current way of doing it
       6  what a team their size found when they looked
       7  THE REFERRAL ASK - am I talking to the right person about this,
          and who should I be talking to. This is the rung that feeds
          stakeholder escalation in ACCOUNT-OUTREACH.md
       8  close the loop                (existing rung 5, moved)

3. Add `PRODUCTIVE_EMAIL_EIGHT_V1` to `cadencelibrary.SEQUENCES`. Days
   1, 3, 6, 8, 11, 14, 17, 20, mirroring the best performer's waits of
   2/3/2/3/3/3/3/1.
4. CHECK THE CAPS BEFORE YOU FINISH. `config/clients/productive.yaml` paces
   volume for eleven touches over twenty-one days. An eight-email cadence
   alongside six LinkedIn steps is fourteen, and a cadence whose steps are
   silently dropped by a weekly cap is the exact failure `cadencelibrary`'s
   own docstring warns about. Either this cadence is email-led with fewer
   LinkedIn touches, or the caps move with it - decide, say why in a comment,
   and prove the touch count with a test.

## FILES ALLOWED

`src/cadencelibrary.py`, `src/generate.py`, `config/clients/productive.yaml`,
`tests/`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/providerwrites.py`, `src/executionguard.py`, `src/killswitch.py`,
`src/approve.py`, `src/bisonfactory.py`, `src/heyreachfactory.py`,
`src/providers/**`, `work/**`.

Do NOT stage anything at a provider and do NOT generate any copy - there are
no credentials in this worktree. This task builds a cadence; running it is
Claude's.

## TESTS REQUIRED

- em5 of the five-step cadence still resolves to the breakup rung after the
  change - write this one first and watch it pass before and after;
- the eight-step cadence resolves eight DISTINCT purposes, none None;
- `purpose_for` beyond a ladder's length still returns None rather than
  repeating the last rung;
- the touch count over twenty-one days is what the cadence claims, against
  the configured caps;
- both cadences are selectable by name and neither changes the other.

Then break each guard deliberately and confirm the intended test fails for
the intended reason.
