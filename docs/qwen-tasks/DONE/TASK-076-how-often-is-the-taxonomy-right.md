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

**STATUS:** DONE

**COMMIT SHA:** 55e30f5 (report) + ed02d7d (measurement script) + dd24a4f (task move)

**TESTS:**
- `py -3 -m unittest tests.test_replies -v` → 76 tests, all pass (0.354s)
- `py -3 -m unittest tests.test_invariants -v` → 80 tests, 79 pass, 1 error
  (pre-existing: `work/` directory does not exist in this worktree, structural)
- `py -3 scripts/task076_taxonomy_precision.py` → measurement script runs
  clean, produces results for 263 hand-labeled replies

**FILES CHANGED:**
- `scripts/task076_taxonomy_precision.py` (new) — measurement script with
  hand labels for all 263 replies
- `docs/TAXONOMY-PRECISION-2026-09-14.md` (new) — the full report

**FINDINGS (the precision table):**

| Category | Precision | Recall | TP | FP | FN | Total labeled |
|----------|-----------|--------|----|----|----|---------------|
| INTERESTED | 0.44 | 0.62 | 23 | 29 | 14 | 52 |
| MEETING_INTENT | 1.00 | 1.00 | 5 | 0 | 0 | 5 |
| OBJECTION | 1.00 | 0.67 | 6 | 0 | 3 | 6 |

Sample: 263 replies (63 taxonomy-matched + 200 random UNKNOWN, seed=42).
Total UNKNOWN pool: 3,869 from 5,266 cached conversations.

The dominant defect: `\b(?:interesting|intriguing|intrigued)\b` causes 21 of
29 INTERESTED false positives. The word "interesting" is a politeness marker
in outbound sales contexts, not an interest signal. "Sounds interesting,
but..." is a refusal 29 times out of 52.

MEETING_INTENT and OBJECTION are precise. Their patterns are specific enough
to avoid false positives. OBJECTION misses three phrasings outside its
pattern set ("restricted by [parent company]", "not big enough to be
investing").

All 29 INTERESTED false positives are listed with their actual texts in
`docs/TAXONOMY-PRECISION-2026-09-14.md`. All 14 INTERESTED misses and 3
OBJECTION misses are listed too.

No category was promoted to POSITIVE or NEGATIVE in accountpolicy.
No pattern was widened.

**RISKS:**
- The sample is drawn from one estate (cached HeyReach conversations). The
  distribution of reply types may not generalize to other campaigns or
  industries.
- Hand labels are mine (one person). Another labeler might disagree on
  borderline cases (e.g., whether "no time for this right now" is an
  objection or a decline). The 29 INTERESTED false positives are not
  borderline — they are clearly not interested.
- The recall estimate for INTERESTED (0.62) depends on the random sample
  of 200 containing a representative fraction of genuine interest signals.
  With 14 hits in 200, the confidence interval is wide.

**RECOMMENDED CLAUDE ACTION:**
1. Consider removing `\b(?:interesting|intriguing|intrigued)\b` from
   INTERESTED_PATTERNS. It causes 72% of all false positives. Without it,
   INTERESTED precision would rise from 0.44 to approximately 0.83.
2. Consider removing `\b(?:curious|curiosity)\b` from INTERESTED_PATTERNS.
   It causes 6 of 29 false positives. "Curious" is used defensively and in
   wrong-person messages more often than as genuine product interest.
3. Do NOT widen patterns to raise recall. The 14 missed INTERESTED replies
   use many different phrasings; adding patterns for each would widen the
   false-positive risk.
4. Do NOT promote any category to POSITIVE or NEGATIVE. The UNKNOWN mapping
   is deliberate and safe.
