# TASK-048 - The rung that asks for the shortest message against a floor

## THE FINDING, MEASURED

`em4` of `productive_li_heavy_v1` is not written for several records, and
`account-a`'s `em5` and `viralityllc-com`'s `em4` were recorded at the last
checkpoint as steps that "will not clear on the current model".

Regenerated live on `ogpartner-dk` 2026-09-14: em4 came back NOT WRITTEN
again, after three attempts.

The cause is in the brief, not the model. `cadencelibrary.EMAIL_FIVE_LADDER`
rung 4 says:

    "A short bump that makes a DIFFERENT argument from every email before it.
     The shortest message in the sequence - and still a whole one: the
     forty-word floor applies here exactly as it does everywhere else.
     One idea, one question, no recap."

And `lint` refuses a body under forty words. So the rung asks for the
shortest message in the sequence and the floor says it may not be short. The
model is being asked to satisfy two instructions at once and the log shows
what that produces - `"the body is under 40 words"` three times, then
nothing stored.

The same shape was measured on 2026-09-13 for `em5`: six of twenty records
across two full regeneration passes failed exactly this way, and six
contacts could not be staged for want of one message each.

## GOAL

`em4` is written, reliably, for every record where the other four are.

## THE RULE YOU MAY NOT BREAK

**Do not widen the forty-word floor.** `CLAUDE.md`: "Never widen a lint rule
to make a draft pass. Regenerate the draft." That is not negotiable and it is
the whole reason this task exists rather than a one-line config change.

So the fix is in the BRIEF: rung 4 has to ask for something a forty-word
message can actually be. "The shortest message in the sequence" is the phrase
doing the damage - it invites a twenty-word message and then the floor
refuses it.

## WHAT TO ESTABLISH FIRST, BEFORE CHANGING THE WORDING

Measure. Do not guess.

1. How many words does the model actually return for rung 4 today, across
   several attempts? Take the rejected drafts off the record log - they are
   stored under `rejected` on the `draft` log entry.
2. Is it clustering just under forty, or far under? Those are different
   problems: just under is a brief that needs one more sentence asked of it,
   far under is a brief the model is reading as "be terse".
3. Does the retry feedback help? `generate.draft` feeds the reason back on
   attempt two and three. Does the word count move between attempts?

Then rewrite the rung so that the shortest message in the sequence is still
comfortably a forty-word message, and prove the change with a real
generation run against the fixture model AND a measured live run on one
record.

## WHERE IT GOES

`src/cadencelibrary.py`, `EMAIL_FIVE_LADDER` rung 4 - index 3. Rung 5 is
UNTOUCHABLE: EmailBison campaign 481 holds nine real leads carrying approved
`subject_5`/`body_5` generated against it, and changing rung 5 silently
rewrites the final email of a staged sequence.

`EMAIL_EIGHT_LADDER` carries the same rung 4 and should move with it.

## PROVE IT

A ladder edit that makes the prompt nicer and does not change the outcome is
not a fix. The test is behavioural: generate em4 and assert it is STORED,
against a model fixture whose rung-4 answer is realistic rather than
pre-padded to pass.

Then regenerate one real record and report the word counts.

## WHAT YOU MAY NOT DO

- Do not change the forty-word floor, or `lint.py` at all.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`. To generate
  against real data, copy the queue to a scratch path and point `QUEUE` at
  it, which is how the copy-progression fix was proved on 2026-09-14.
- No provider call, no campaign mutation.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION.
