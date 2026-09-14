# The ladder moved and the copy did not

2026-09-15, measured after the regeneration that was supposed to fix the copy
TASK-064 and TASK-063 refused.

## WHAT WAS EXPECTED AND WHAT HAPPENED

TASK-075 rewrote the LinkedIn ladder so rung 1 demands sender identity and
rungs 2-6 each state what the previous rung spent. TASK-063's fix carried the
same sender requirement into the email prompt. Then a full regeneration ran
against the corrected ladder and exited 0.

Measured across the 686 stored steps that carry copy:

    LINKEDIN  n=448      EMAIL  n=238
      names Productive      32%        names Productive      32%
      says who is writing    5%        says who is writing    0%
      opens "i noticed"       0        opens "i noticed"     49

    li1 (the connection note)   22 of 66 say who is writing   33%
    li4 (the product rung)      46 of 69 name Productive      67%
    per-SEQUENCE naming it      90 of 132                     68%

**68% is exactly the stored baseline TASK-065 measured BEFORE any of this
work.** The email side is at 0% sender identity, unchanged, and "i noticed"
survives 49 times on the channel where TASK-063 counted 47.

The regeneration ran, exited clean, and changed almost nothing.

## WHY - AND IT IS NOT A BUG IN THE LADDER

`plan` re-plans a step when that step FAILS A GATE. That is the correct and
deliberate design, and TASK-072 relied on it: it is why a regeneration is
idempotent and cheap to re-run.

**But a stored step records nothing about what produced it.** Every field
name across the whole estate:

    approval, body, channel, generated, note, subject, template

No ladder version. No prompt fingerprint. No generation timestamp.

So when the LADDER changes, nothing about the existing copy changes. The old
copy still passes lint, still passes the repetition checks, still passes the
claims gate - because it always did. `plan` looks at it, finds no failing
gate, and reports **"nothing to generate"**. The improvement reaches only the
steps that happened to be failing for some other reason, which is why li1
moved to 33% and email moved to 0%.

There is no `--force` and no `--regenerate` flag. `py -3 -m src.generate
--help` offers `--live`, `--id`, `--limit`, `--client` and nothing else.
**There is currently no way to say "the ladder moved, redo the copy."**

## THIS IS THE MIRROR OF A DEFECT ALREADY FIXED ONCE

TASK-068 fixed the stale-SIBLING problem: a good new note was judged against
five stale notes saying the same thing, so it could never be stored. The fix
was to regenerate a colliding set AS A SET.

This is the same shape one level up. There, stale copy blocked a replacement.
Here, stale copy IS the replacement, forever, because nothing marks it stale.
Both are the system preserving an old answer to a question that has changed.

## WHAT THIS MEANS FOR THE LEAD BLOCK

`docs/LEADS-ARE-BLOCKED-2026-09-14.md` stands, and the reason is now
sharper. The block was never going to lift from this regeneration, because
the regeneration could not reach the copy the human reads condemned.

**Anyone reading the new copy will find it looks much like the old copy, and
will be tempted to conclude the ladder fix did not work.** It did. It was
never applied. Those are different failures with different fixes, and the
numbers above are how to tell them apart.

The one place it demonstrably DID apply is worth keeping, because it shows
the ladder is right when it runs. `ogpartner-dk/jacob-faertz`:

    li1  connecting to share how founders like you get clear, up-to-date
         insights on project margins without waiting weeks
    li2  how do you keep track of who's booked on projects and plan for
         upcoming work at &Partner?
    li3  without clear visibility on utilisation, it's easy for projects to
         slip past budget before anyone notices
    li4  productive connects budgets and time tracking so you see project
         margins while they run, not weeks later
    li5  thanks for connecting, jacob. curious, what's one change you'd like
         to see in how agencies track project profitability?
    li6  if now's not the right time to explore, no worries at all

Six rungs, six different jobs, the product named once at rung 4, an easy out
at rung 6. That is the ladder working. It still does not say WHO is writing,
so rung 1 is only partly satisfied even here.

## THE FIX IS NOT "REGENERATE EVERYTHING"

Deleting all stored copy would work and would be wrong. It discards approvals
- which are bound to exact words and are a human act - and it spends model
credits on steps that are already good.

What is needed is a way for the system to KNOW that a step was generated
against a ladder that no longer exists. That is TASK-079.

Note the interaction that makes this delicate: an approval is bound to the
exact words. Invalidating copy therefore invalidates approval, which is
correct - a person approved words, not an intention - but it means a
ladder change silently un-approves work. That consequence has to be
deliberate and visible, not a side effect somebody discovers.
