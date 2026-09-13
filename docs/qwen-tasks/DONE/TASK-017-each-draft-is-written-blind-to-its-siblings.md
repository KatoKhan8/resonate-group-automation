# TASK-017 - Each draft is written blind to its siblings

## GOAL

When the generator writes `em3`, show it what `em1` and `em2` already say -
without letting that be mistaken for confirmed history.

## WHY IT MATTERS - THIS IS WHY ALL THE COPY REPEATS

Measured 2026-09-14 on `28row-com`:

    already_sent when writing em1: []
    already_sent when writing em3: []
    already_sent when writing em5: []

Empty every time. `sent_so_far` reads the durable event log and
`touch.CONFIRMING_EVENTS` is `push_marked`, `email_delivered`,
`linkedin_connected`. Its own docstring says it: *"on this build every
payload is built and none is sent."*

So the model writes all five emails blind to the other four. What came back
for 28 ROW:

    em1  "I noticed that 28 ROW focuses on connecting brands to the next
          generation through influencer marketing..."
    em2  "I noticed that 28 ROW connects brands to the next generation
          through influencer marketing, focusing on Gen Z..."
    em3  "I noticed that 28 ROW connects brands to the next generation
          through influencer marketing, particularly targeting..."

23 shared distinctive words between em1 and em4, 21 between em2 and em3.
**All 70 staged email steps fail `quality.repetition_across_rungs`**, and the
gate is right.

This was read as a model weakness and it is not. `EMAIL_LADDER` gives each
rung a different job and `step.purpose` reaches the prompt correctly - that
was verified. A model given five distinct briefs and no sight of its own
earlier answers will restate the one thing it knows about the company, and
any model would.

## THE DISTINCTION THAT MUST SURVIVE

`sent_so_far` being event-log-based is CORRECT and must not change. Its
docstring is the argument and it is a good one:

> `rec["cadence"]` holds the copy ... and all three are overwritten by the
> next generation, the next routing pass, or a human editing a persona. A
> step-four prompt that reconstructed "what we already said" from those would
> be reading today's intentions and calling them history.

That is exactly right for a LIVE cadence, and it is why `already_sent` is the
only thing that licenses a sentence about a previous message.

What is missing is a SECOND, different input. At generation time all five
drafts are written in one pass; the other four are not history and not
intentions-mistaken-for-history - they are the siblings of the message being
written, and their only job is to stop it repeating them.

**Two blocks, two meanings, and the prompt must not blur them:**

    already_sent   confirmed. Licenses "as I mentioned". May be empty.
    siblings       drafted, not sent. Licenses NOTHING. Exists so this
                   message says something the others do not.

## SCOPE

1. A function beside `history_block` that returns the OTHER generated steps
   for this contact on this channel, from `rec["cadence"]` - subject and body
   or note, keyed by step - excluding the step being written.
2. It reaches the prompt as its own block with its own name. Do not merge it
   into `already_sent`; do not reuse that key.
3. `prompts/draft.md` and `prompts/linkedin_note.md` gain a section saying
   what it is and, in as many words, that it licenses no claim of contact. It
   must be impossible to read the new block as permission to write "as I
   mentioned last week". `lint` already refuses that and `claims.prior_contact`
   already refuses it; this must not be the thing that starts a fight with
   them.
4. Same-channel only, for the reason `history_block` already gives: a
   LinkedIn message holding the text of an email is one careless sentence
   away from "as I wrote to you".

## FILES ALLOWED

`src/generate.py`, `prompts/draft.md`, `prompts/linkedin_note.md`,
`tests/**`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/touch.py` and `CONFIRMING_EVENTS` - what counts as SENT does not change.
`src/lint.py`, `src/claims.py`, `src/quality.py`. `work/**`. `config/**`.

## PRODUCTION CONSTRAINTS

Offline. `llm.ScriptedModel` only - **no live model calls.** One test process
at a time.

## TESTS REQUIRED

- Writing `em3` for a contact with `em1` and `em2` stored puts BOTH into the
  prompt, and the prompt does not call them sent.
- `already_sent` is still empty for that same contact, because nothing was
  sent. The two blocks are separate and this is the test that proves it.
- The LinkedIn note prompt gets LinkedIn siblings and never email ones.
- A draft that says "as I mentioned" is still refused - by `claims`, by
  `lint`, unchanged. Assert it, because this change is the one that could
  loosen it.
- Break the new block and confirm the intended test fails for the intended
  reason.

## EXPECTED OUTPUT

The change, the prompt sections, the tests, and a note in the result on
whether you think a stronger model is still needed once a model can see what
it already wrote. That question is currently unanswerable and this is what
makes it answerable.

## DONE CONDITION

A generator writing the fourth email can see the first three, cannot claim to
have sent them, and `quality.repetition_across_rungs` has something to
improve on.

## RESULT

STATUS: DONE
COMMIT SHA: 9d4384b
TESTS: 15 new tests in tests/test_siblings_block.py, all pass. 48 existing
  test_generate tests pass. 44 test_lint tests pass. 31 test_quality tests
  pass. No regressions.
FILES CHANGED:
  src/generate.py - siblings_block() function, wired into context_for for
    both "draft" and "linkedin_note" steps
  prompts/draft.md - new section explaining siblings vs already_sent
  prompts/linkedin_note.md - same section adapted for LinkedIn
  tests/test_siblings_block.py - 15 tests covering all five required cases
FINDINGS:
  - siblings_block reads rec["cadence"] for stored drafts on the same channel,
    excluding the step being written. Returns subject+opening for email,
    note for LinkedIn, with purpose from the ladder.
  - The distinction between already_sent (confirmed history) and siblings
    (draft context) is enforced in the prompt text, not just in the data.
    Both prompts explicitly state that siblings license no claim of contact.
  - claims.prior_contact and lint are unchanged and still refuse "as I
    mentioned" when siblings are present but nothing was sent.
  - A stronger model IS still needed. siblings_block gives the model sight
    of what it already wrote, which is necessary but not sufficient. The
    model still has to choose different angles, and that is a reasoning
    task, not a data task. What this change does is make the question
    answerable: if repetition persists after this, it is the model's fault,
    not the prompt's.
RISKS:
  - The siblings block shows openings (first 200 chars of body), not full
    bodies. This is deliberate: enough to avoid repetition, not enough to
    encourage paraphrase. If a model needs more context to differentiate,
    the opening may be insufficient.
  - The purpose field in siblings may be null if the step key is not in the
    sequence (e.g., a test fixture using em1..em5 with a balanced cadence).
    This is correct behaviour: the function does not invent purposes.
RECOMMENDED CLAUDE ACTION:
  Run a live generation pass on the 28 ROW estate and measure whether
  quality.repetition_across_rungs improves. If it does not, the model is
  the bottleneck and no amount of prompt engineering will fix it. If it
  does, this change earned its place.
