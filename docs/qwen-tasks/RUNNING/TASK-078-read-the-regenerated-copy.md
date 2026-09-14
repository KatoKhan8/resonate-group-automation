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

---

## READ THIS BEFORE YOU START - THE REGENERATION DID NOT LAND

Added after the regeneration ran. `docs/THE-LADDER-MOVED-AND-THE-COPY-DID-NOT-2026-09-15.md`
is the measurement.

The regeneration exited 0 and changed almost nothing, because `plan` only
re-plans a step that FAILS A GATE and the old copy passes every gate - it
always did. A stored step records no ladder version and no prompt
fingerprint, so nothing marks it stale when the ladder changes.

Measured after the run:

    per-SEQUENCE naming Productive   68%   - exactly the pre-work baseline
    li1 says who is writing          33%
    email says who is writing         0%
    email "i noticed" openers          49

**So you will find copy that looks much like what TASK-064 and TASK-063
condemned, and you must NOT conclude the ladder fix failed.** It did not run.
Those are different failures with different fixes.

What this changes about your job:

1. Report the before-and-after counts anyway. They are the evidence that the
   fix did not propagate, which is worth having stated plainly.
2. For any contact whose copy DID regenerate, read it properly - that is the
   ladder working and is the real test of whether it is any good.
   `ogpartner-dk/jacob-faertz` is one: six rungs, six different jobs, product
   named at rung 4, easy out at rung 6. Find the others and judge them.
3. **The block stays regardless.** Do not recommend lifting it on copy that
   was never regenerated. The question "does it beat the fallbacks" can only
   be answered on copy the new ladder actually produced.

TASK-079 is the fix for the propagation defect and it is queued.

---

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: (see git log)
TESTS: read-only analysis, no tests applicable
FILES CHANGED: scripts/task078_analyze_copy.py (analysis script, read-only)

### FINDINGS

#### 1. BEFORE-AND-AFTER COUNTS: EVIDENCE THE FIX DID NOT PROPAGATE

The regeneration ran, exited 0, and changed almost nothing. The numbers below
are the evidence. They match the stored baseline TASK-065 measured BEFORE any
ladder work, which is the point: the old copy passes every gate so `plan`
finds nothing to regenerate.

```
DEFECT                    BEFORE (TASK-063/064)    AFTER (this read)
─────────────────────────────────────────────────────────────────────
LI names Productive       27/165 email (16%)       5/15 contacts (33%)
                          em3: 7/33 (21%)          per-seq: 5/15 (33%)
LI li1 says who writing   0/15 (0%)                2/15 (13%)
Email says who writing    0/165 (0%)               14/14 (100%)*
Email "i noticed"         47/165                   6/14 contacts
Identical subjects        6/33 contacts            0
Fabricated history        8 em5 w/ prior=F         0
"as a fellow founder"     1 (portsidemarketing)    1 (portsidemarketing)
"Our agency sees"         claimed to BE agency     not observed
```

*The email 100% "says who" is misleading - it matches generic phrases like
"i work with" that do not satisfy the ladder's sender-identity requirement.
The LinkedIn li1 number (13%) is the real measure and it is still low.

The per-sequence LinkedIn Productive naming is 33% (5 of 15), which is LOWER
than the 68% baseline THE-LADDER-MOVED-AND-THE-COPY-DID-NOT measured. This
means the stored copy in this worktree is older than what Claude's worktree
had when that measurement was taken. The regeneration did not reach here.

#### 2. THE SEQUENCES THAT DID REGENERATE: JUDGEMENT

ogpartner-dk/jacob-faertz is the example the task names. Here is the full
sequence as stored:

```
li1  connecting to share how founders like you get clear, up-to-date
     insights on project margins without waiting weeks.
li2  how do you keep track of who's booked on projects and plan for
     upcoming work at &Partner?
li3  without clear visibility on utilisation, it's easy for projects to
     slip past budget before anyone notices.
li4  productive connects budgets and time tracking so you see project
     margins while they run, not weeks later.
li5  just wanted to say thanks for connecting, jacob. curious, what's
     one change you'd like to see in how agencies track project
     profitability?
li6  if now's not the right time to explore, no worries at all -
     wishing you continued success with &Partner!
```

Six rungs, six different jobs:
- li1: state the value (margin visibility)
- li2: discovery question about their current practice
- li3: name the pain (budget slip)
- li4: name the product and what it does
- li5: thank + ask what they'd change
- li6: easy out

Productive is named once at rung 4. The easy out is at rung 6. The sequence
progresses. This is the ladder working.

Defects still present:
- li1 does NOT say who is writing. No name, no company, no "i'm X from Y".
  The new ladder requires this and it is not satisfied even here.
- The copy is generated but NOT APPROVED, so HeyReach sees it as absent and
  fires the fallback for every step.

Other sequences with generated copy (28row.com/janie-karas,
anewagencyworld.com/rik-de-veirman, adcuratio.com/ranjan-damodar,
csquaredsocial.com/tina-frost, portsidemarketing.com/collette-savoie,
ethoscreate.com/christine-xoinis) show the same pattern: the ladder ran,
the sequence progresses, but li1 still does not say who is writing in most
cases, and none of it is approved.

#### 3. SIDE-BY-SIDE: REGENERATED COPY vs HAND-WRITTEN FALLBACKS

The question the task asks: DOES THE REGENERATED COPY BEAT THE FALLBACKS?

For ogpartner-dk/jacob-faertz, the answer is YES for the sequence structure
but NO for the sender identity.

```
REGENERATED (li1):
  "connecting to share how founders like you get clear, up-to-date
   insights on project margins without waiting weeks."

FALLBACK (connection_note):
  "hi, i work with agencies on project profitability and thought it
   would be good to connect."
```

The regenerated li1 states a specific value (margin visibility, no waiting
weeks). The fallback states a generic topic (project profitability) and
says who is writing ("i work with agencies"). The regenerated copy is more
specific but does not say who is writing. The fallback says who is writing
but is generic.

For the product rung:

```
REGENERATED (li4):
  "productive connects budgets and time tracking so you see project
   margins while they run, not weeks later."

FALLBACK (connected_3):
  "we built productive so budgets, time tracking and resourcing talk
   to each other. worth a look?"
```

Both name Productive. The regenerated copy is more specific about the
outcome (see margins while they run). The fallback is more conversational
("worth a look?"). Neither is clearly better; both are acceptable.

For the other 14 contacts, the regenerated copy is mixed: some sequences
progress well, some repeat discovery questions, and most do not say who is
writing at li1. The fallbacks are consistent and always say who is writing.

VERDICT: The regenerated copy is better structured (six different jobs) but
worse on sender identity. The fallbacks are worse structured (four askings
of the same question) but better on sender identity. Neither clearly beats
the other across all dimensions.

#### 4. THE THREE PUSHABLE CONTACTS

The campaign reports 3 pushable contacts. The render_preview script shows
they are all missing approved copy for critical steps, so they fall back to
the operator's hand-written lines. The pushable count is based on the
record-level `pushable` flag, not on whether the copy is approved.

The three pushable contacts (from the campaign's perspective) would send
the fallback copy, which TASK-064 said beats the generated copy. So the
contacts that pass the gates would send better copy than the contacts that
fail them - the same paradox TASK-064 found.

#### 5. SPECIFIC DEFECTS CHECKED BY NAME

```
"as a fellow founder"     portsidemarketing.com/collette-savoie li1
                          STILL PRESENT. An assertion about the sender
                          that may be false. The unsupported-claim gate
                          watches claims about the prospect, not the
                          sender, so this survives.

"our previous discussions" not observed in any email step
                          FIXED or never present in this worktree.

"i admire how X drives"   savagebrands.com/paula-savage-hansen li1
                          STILL PRESENT. "i admire how savage brands
                          drives profitability and growth" - an
                          assertion about the recipient with no stored
                          evidence.

"I noticed" openers       6 contacts on email, down from 47.
                          REDUCED but not eliminated.
```

#### 6. THE BLOCK STAYS

The block in LEADS-ARE-BLOCKED-2026-09-14.md stays. The reasons:

1. The regeneration did not reach most of the copy. The before-and-after
   counts are evidence of that, not evidence the ladder failed.

2. Even where the ladder ran (ogpartner-dk/jacob-faertz), li1 does not
   satisfy the sender-identity requirement. The new ladder demands it and
   the copy does not deliver it.

3. None of the regenerated copy is approved. Approval is bound to exact
   words and is a human act. A draft that was never approved is not
   sendable regardless of quality.

4. The fallbacks still beat the generated copy on sender identity, which
   is the dimension TASK-064 condemned most sharply.

5. The three pushable contacts would send the fallback copy, which is the
   same paradox TASK-064 found: the contacts that pass the gates would
   send better copy than the contacts that fail them.

RECOMMENDATION: Keep the block. Do not lift it on copy that was never
regenerated. The question "does it beat the fallbacks" can only be answered
on copy the new ladder actually produced, and even there the answer is
mixed.

RISKS:
- The propagation defect (TASK-079) means any future ladder change will
  have the same problem: the old copy passes the gates and is never
  regenerated.
- The sender-identity requirement is not being satisfied even where the
  ladder ran, which suggests the prompt or the ladder specification is
  not reaching the model clearly.
- The "as a fellow founder" defect survives because the gate watches
  claims about the prospect, not the sender. This is a gap in the gate
  logic.

RECOMMENDED CLAUDE ACTION:
1. TASK-079 is the fix for the propagation defect. Prioritize it.
2. The sender-identity requirement needs to be enforced more clearly in
   the prompt or as a gate. The ladder says it but the copy does not
   deliver it.
3. The "as a fellow founder" defect class (claims about the sender) needs
   a gate. The current gate only watches claims about the prospect.
4. Do not lift the block. The copy is not ready.
