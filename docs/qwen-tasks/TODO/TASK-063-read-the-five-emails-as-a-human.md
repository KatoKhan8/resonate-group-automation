# TASK-063 - Read the five-email Bison narrative as a human would

## WHY

EmailBison campaign 481 holds nine real leads carrying `subject_1`..`body_5`.
Its five steps exist and are provider-verified. **Nobody has read the five
emails one person receives, in order, as a conversation.**

Reading the LinkedIn sequence that way is what found the
four-questions-in-a-row defect. The email side has never had it done.

TASK-057 builds the renderer. This task uses it, or renders directly if
TASK-057 has not landed - do not wait for it, and do not duplicate it.

## WHAT TO PRODUCE

For at least EIGHT records that hold all five email steps, the full sequence
in order, and then a verdict per record against each of these:

    1  FIVE DIFFERENT JOBS, or one job five times?
       Name what each email is actually doing. If two are doing the same
       thing, say which two and quote the sentences that prove it.

    2  IS THE PRODUCT EVER NAMED, and by which step?
       Measured baseline across the estate: em3 names Productive in 11 of
       38 stored bodies. Report your own number.

    3  DOES ANY EMAIL CLAIM A RELATIONSHIP THAT DOES NOT EXIST?
       `claims` has been found one phrase short THREE times in two days -
       plural "discussions", bare "our conversation", "I have not heard from
       you". Read for a FOURTH and report any candidate phrasing even if
       `claims.check` currently passes it. That is the most valuable thing
       this task can find.

    4  DO TWO EMAILS OPEN THE SAME WAY?
       The known formula is [their self-description] -> [why I am writing,
       by role] -> [the ask]. `quality.structural_repetition` catches it now;
       report whether it is still present in stored copy.

    5  WOULD YOU REPLY?
       One line per record, honestly. This is a judgement and it is asked for
       deliberately - the gates cannot answer it.

## THE OUTPUT IS A DOCUMENT, NOT A SCRIPT

`docs/BISON-FIVE-STEP-READ-<date>.md`. Quote the actual copy. A reader who
has never seen this system must be able to judge the sequence from your
document alone.

Sanitise: no real person's name, email or company. Use the record id and a
role ("the founder", "the finance lead").

## WHAT YOU MAY NOT DO

- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`. Read only.
- No provider write. Reading 481 from the provider is permitted and
  encouraged - compare what is STORED against what the provider actually
  holds as per-lead variables, and report any divergence.
- Do not fix the copy. This task REPORTS. Claude decides what changes.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION.
