# TASK-116: The 49 "I noticed" openers that never moved

2026-09-15. Measured against `work/queue.snapshot.jsonl` stamped
`2026-09-14T21:52:15Z from master 0ac5e60, 300 records`.

---

## THE COUNT

| Scope | I noticed | Total | Fraction |
|-------|-----------|-------|----------|
| TASK-063 (33 contacts, all 5 steps) | 47 | 165 | 28% |
| This analysis (34 contacts, all 5 steps) | 47 | 170 | 28% |
| This analysis (all email steps in estate) | 48 | 232 | 21% |
| TASK-098 (provider readback, reported) | 49 | 234 | 21% |

TASK-063's 47 is reproduced exactly. The 48th step is one contact outside
the 33-contact set TASK-063 used (that contact lacks em4). The 49th TASK-098
reported likely came from a step added between the snapshot and the provider
readback.

**The per-step breakdown is unchanged from TASK-063:**

    em1: 12    em2: 14    em3: 9    em4: 10    em5: 2

---

## WHICH EXPLANATION: STALE COPY OR ACTIVE REGENERATION?

**Explanation (1): stale copy that never re-planned.**

The evidence is conclusive:

### 1. The steps were never re-planned

All 48 steps carry approval timestamps from 2026-09-13, in five batches:

    21:47:32    41 steps    (the initial generation)
    22:16:33     1 step
    22:37:18     2 steps
    22:49:25     1 step
    23:01:50     3 steps

None has been re-approved since. The stored body is the original generation.

### 2. The model does NOT produce "I noticed" any more

108 email draft attempts on 2026-09-14 produced subject lines. Zero began
with "I noticed". The subjects use different patterns:

    "How does [company] manage live budget tracking?"
    "How Productive connects budgets, time, and resourcing live"
    "Improving utilisation and capacity planning at [company]"
    "Should I close your file for now, [first name]?"

The model's current prompt and ladder produce different openers. The phrase
is not being actively regenerated.

### 3. The old copy is stuck in a regeneration deadlock

The planner now catches 47 of 48 steps via the quality gate
(`repetition_across_rungs`). It schedules regeneration. But:

- New drafts fail lint for the same `repetition_across_rungs` reason
- The old "I noticed" copy is what the new draft is compared against
- The new draft cannot be different enough to pass while being similar
  enough to be about the same company and role
- Three attempts are made per step; all three fail; the old copy stays

This is the same deadlock `generate.py:913-937` documents for LinkedIn notes:
"whichever note is rewritten is compared against the old siblings that still
say the same thing, so the replacement collides and the old note stays."

**The count did not move because the set was never replaced. It is (1).**

---

## IS "I NOTICED" EVEN A DEFECT?

### What is wrong is not the phrase; it is the monotony

"I noticed that [Company] [does something]" is a reasonable opener in
isolation. It signals observation, not flattery. The problem is:

1. **Within a sequence**: One record has the IDENTICAL first sentence across
   all four "I noticed" steps. Another has the same first sentence on em1,
   em2, and em3. A person receiving these emails sees the same opening
   three times.

2. **Across the estate**: 48 of 232 steps (21%) open identically. Every
   fifth email a recipient might receive from this system starts the same
   way. That is monotony, not a writing defect.

3. **The structural formula is the real repetition**: TASK-063 found the
   pattern is [their self-description] -> [why I am writing, by role] ->
   [the ask]. The "I noticed" opener is just the most visible symptom of
   a formula that repeats even when the opener changes.

### The quality gate catches it now, but too late

The quality gate (`repetition_across_rungs`) requires three shared words AND
50% overlap of the smaller set. Two long emails sharing an opening sentence
but diverging in the body pass this threshold. The gate fires on records
where the bodies barely diverge but not on records where the shared opener
is diluted by different subsequent content.

---

## THE FULL PICTURE OF THE ESTATE'S EMAIL OPENERS

Top opener patterns across 232 email steps:

     48  "i noticed"         (21%)
      6  "this is"           (3%)
      5  "productive is"     (2%)
      5  "[company name]"    (2%)
      5  "[company name]"    (2%)
      4  "i understand"      (2%)
      4  "a new"             (2%)
      4  "[company name]"    (2%)

After "I noticed", the next most common opener appears 6 times. The
distribution is heavily top-loaded on one phrase.

---

## WHAT THE REGENERATION LOG SHOWS

Of the 19 records carrying "I noticed" steps:

- All 19 had regeneration attempts on 2026-09-14
- The most common rejection reason: `repetition_across_rungs`
- Second most common: `the subject is 60 characters or more`
- Third: `unsupported claim` (on em5 steps with "Since I have not heard")
- Some records had THREE full regeneration rounds and none converged

The regeneration infrastructure is working. It is colliding with the
existing copy that is the very thing it is trying to replace.

---

## OBSERVATIONS

1. (n=48) All 48 "I noticed" steps were generated on 2026-09-13 and never
   replaced. The set identity is unchanged from TASK-063's count.
2. (n=108) Fresh draft attempts on 2026-09-14 do not produce "I noticed"
   openers. The model's current prompt produces different patterns.
3. (n=13) 13 of 48 "I noticed" steps have within-record siblings with
   identical or near-identical first sentences. This is the monotony a
   recipient experiences.
4. (n=19) All 19 records with "I noticed" had regeneration attempts that
   failed to replace the old copy. The rejection reason is
   `repetition_across_rungs` - the new draft is too similar to the old one.
5. (n=121) 121 of 232 email steps share an empty approval fingerprint,
   indicating they were approved without the fingerprint mechanism.

## HYPOTHESES

1. The "I noticed" opener was the default pattern of an earlier ladder/prompt
   version. The ladder fixes changed the model's behaviour, but the old copy
   was never invalidated because `regen_stale_ladder` is opt-in and was not
   set when the regeneration ran.
2. The quality gate's 50% overlap threshold lets formulaic copy through when
   the emails are long enough. The shared opener is diluted by different
   body content. Lowering the threshold or adding an opener-specific check
   would catch more cases but risks false positives on legitimately similar
   companies.
3. The regeneration deadlock is structural: any replacement must be compared
   against the copy it replaces, and the comparison metric penalises
   similarity that is inherent to writing about the same company twice.

## PROVEN LEARNINGS

1. A count that does not move is not evidence that nothing changed. The
   count stayed at 47 because the same steps were never replaced. Other
   measurements (Productive naming, sender identity) moved because those
   steps WERE regenerated. The "I noticed" steps were not, for a specific
   mechanical reason: the regeneration deadlocks on its own reference copy.
