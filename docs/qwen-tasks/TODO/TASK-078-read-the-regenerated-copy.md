# TASK-078 - read the regenerated copy, and it decides whether leads move

## THIS IS THE GATE THAT LIFTS THE BLOCK

`docs/LEADS-ARE-BLOCKED-2026-09-14.md` is the decision this task exists to
revisit. Read it first. Short version: the three pushable contacts passed
every automated gate and failed a human read on all six verdicts, so no leads
were added to HeyReach 599020.

Since that read, three things changed:

    TASK-075   rung 1 now REQUIRES sender identity; rungs 2-6 each state
               what the previous rung already spent, so "ask a discovery
               question" can no longer satisfy all six
    TASK-063   the same fix reached the EMAIL prompt, which TASK-075 had
               missed - sender identity was in ZERO of 165 email steps
    Claude     ran a full regeneration against the corrected ladder

**Nobody has read the output.** That is this task.

## WHAT TO DO

Render and read, both channels, every contact.

    LinkedIn   scripts/task064_render_cadence.py
    email      scripts/render_preview.py   (renders through bisonfactory,
               the same path that builds the real provider payload)

Then answer PER CONTACT, with the rendered text quoted:

    does the recipient learn WHO is contacting them        yes / no
    does the recipient learn WHY them                      yes / no
    does the recipient learn WHAT Productive is            yes / no
    does each message do a DIFFERENT job from the last     yes / no
    would you send this to a stranger                      yes / no
    any assertion the record does not support              list it

## THE COMPARISON THAT MATTERS MOST

TASK-064 and TASK-063 both found the same inversion: **the operator's
hand-written fallbacks beat every generated message.** They name the product,
say who is writing, progress, and assert nothing unsupported.

So the question is not "is the new copy acceptable". It is:

    DOES THE REGENERATED COPY BEAT THE HAND-WRITTEN FALLBACKS?

Quote both side by side for at least three contacts. If the fallbacks still
win, say so plainly - that is a complete and useful answer, and it keeps the
block in place, which is the correct outcome.

## THE DEFECTS TO CHECK BY NAME

Each was measured, so each is falsifiable now:

    sender identity        was ZERO of 165 email steps and 0 of 15
                           connection notes. What is it now?
    Productive named       was 27 of 165 email steps (16%); em3, whose job
                           it is, 7 of 33 (21%)
    "I noticed" openers    was 47 of 165 steps
    identical subjects     was 6 of 33 contacts with at least two
    fabricated history     was 8 em5 emails saying "our previous
                           discussions" with prior_contact False
    "our agency sees"      claimed to BE the recipient's own agency
    "as a fellow founder"  an assertion about the SENDER

Report each as a before-and-after count. A number that did not move is a
finding, not a failure.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** No lead add, no campaign write, no send.
- **Do not approve anything.** Approval is a human act and it is what stands
  between this copy and a prospect. Your read INFORMS it; it does not
  substitute for it.
- Do not widen a gate. If a gate refuses the new copy, the copy is wrong.
- Do not regenerate - read what is stored. If the copy still looks stale,
  say so and say which contact.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS (the per-contact table,
the before-and-after counts, and the side-by-side against the fallbacks),
RISKS, RECOMMENDED CLAUDE ACTION - and state explicitly whether the block in
LEADS-ARE-BLOCKED-2026-09-14.md should be lifted, kept, or kept for some
contacts and lifted for others.
