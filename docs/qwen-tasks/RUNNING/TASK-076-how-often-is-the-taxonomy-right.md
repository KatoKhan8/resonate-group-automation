# TASK-076 - how often is the taxonomy actually right

## WHY THIS EXISTS

TASK-074 landed a richer reply taxonomy - INTERESTED, MEETING_INTENT,
OBJECTION - and it is SAFE. Its adversarial corpus proves 0 of 47 refusals
reach POSITIVE, and all three categories map to UNKNOWN in
`accountpolicy.CLASSIFIER_OUTCOME`, so nothing it says can widen what
automation does.

**Safe is not the same as right.** Re-probed after integration:

    "interesting spam"                        -> labelled `interested`
    "go on then, waste my time"               -> labelled `interested`
    "This is an interesting waste of my time" -> labelled `interested`

Those cannot hurt a prospect, because `interested` maps to UNKNOWN and an
UNKNOWN pauses the account. But the taxonomy exists to serve the LEARNING
DATASET, and a label of `interested` on "interesting spam" poisons exactly
the dataset it was built for.

So a standing restriction is in force, and this task is what lifts it:

    THE TAXONOMY MAY NOT BE USED TO CLAIM COPY OR VARIANT PERFORMANCE
    UNTIL ITS PRECISION IS MEASURED AGAINST HAND LABELS.

## WHAT TO MEASURE

Precision and recall per category, against replies a person has labelled.

    sample        at least 200 real replies, drawn at RANDOM from the
                  estate - not the ones the patterns already match, which
                  would measure the patterns against themselves
    hand labels   label them yourself, one at a time, reading the text
    then          compare the taxonomy's label against yours

Report, per category:

    precision   of the replies the taxonomy called INTERESTED, what share
                really were
    recall      of the replies you labelled INTERESTED, what share it found
    the errors  list the actual misclassified texts. The list is the
                deliverable; the percentages are the summary.

`scripts/task066_hand_labels.py` and `scripts/task066_extract_unknown_replies.py`
already exist and do adjacent work - read them before writing new ones.

## THE SAMPLING TRAP, AND IT HAS ALREADY BEEN PAID FOR ONCE

TASK-054 measured four prompt variants three times each on ONE record, got
3/3 everywhere, and honestly reported its hypothesis unconfirmed. Measured
against the real estate the same evening the answer was completely different,
because one record is not a sample.

Do not sample the replies your patterns match. Do not sample one campaign.
Say how you drew the sample and how many you drew, and if 200 is not
reachable say what was and why.

## WHAT A GOOD ANSWER LOOKS LIKE

    INTERESTED     precision 0.61 (n=44)   recall 0.38 (n=71)
                   38 of the 44 it called interested were sarcasm or
                   hostility containing the word "interesting"

That is a useful, honest, actionable result even though the number is bad.

    "The taxonomy works well."

is not an answer and fails this task.

## WHAT TO DO WITH THE ANSWER - RECOMMEND, DO NOT DECIDE

If precision is poor, say which patterns cause it and what you would remove.
**Do not promote any category to POSITIVE or NEGATIVE in
`accountpolicy.CLASSIFIER_OUTCOME`.** That mapping is deliberate and changing
it is Claude's decision with its own evidence, not a consequence of a good
precision number.

Removing a bad pattern is in scope. Adding a negation case is in scope.
Widening a pattern to raise recall is NOT - a taxonomy that reaches more
replies by guessing more is the defect TASK-067 was rejected for.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.**
- Do not commit prospect PII. Redact names, emails and company domains in
  anything that lands in `docs/`. Reply TEXT may be quoted where it carries
  no identifier - that is the evidence.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.

## OUTPUT

`docs/TAXONOMY-PRECISION-2026-09-14.md` - the per-category table, the sample
method, the row counts, and the list of actual errors.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands and counts, exit codes read off the
process and never through a pipe), FILES CHANGED, FINDINGS (the precision
table), RISKS, RECOMMENDED CLAUDE ACTION.
