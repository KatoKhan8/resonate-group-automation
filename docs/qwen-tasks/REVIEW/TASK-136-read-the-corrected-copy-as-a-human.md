PRIORITY: P0
DEPENDS: 

# TASK-136 - read the CORRECTED copy as a human. This is the ship gate.

## WHY THIS EXISTS AND WHY IT IS DIFFERENT FROM TASK-130

TASK-130 returned **DOES NOT BEAT FALLBACKS, zero of 69**, on four named
defects. All four have since been fixed IN THE BRIEF - `cadencelibrary` rung 6
and both prompts - and re-measured by Claude on 12 records, 73 fresh steps:

    easy out present in li6     11 of 69  ->  100%
    referral ask in li6                   ->  100%
    "I noticed"                 34 emails ->    0%
    "i admire how"              ~16%      ->    2%
    same greeting six times     69 of 69  ->    0

**That copy has never been read by a human.** TASK-130's verdict describes copy
that no longer exists, exactly as TASK-098's described copy that no longer
existed when TASK-130 ran. This is the third time the gate has had to be
re-taken against fresh output, and it is the correct cost of changing the
brief.

## THE QUESTION, UNCHANGED

Not "is this acceptable". It is:

    DOES THIS COPY BEAT THE HAND-WRITTEN FALLBACKS?

`connected_1` through `connected_4` in the client config are the bar. They beat
everything the model produced on two previous reads.

## WHAT TO READ

Sequences whose steps carry a `ladder_fingerprint` written AFTER the TASK-131
fixes. Filter on it and say how many you read - reading stale steps and
reporting them as the new copy is the one mistake that makes this task
worthless.

Read WHOLE SEQUENCES. Six clean messages can still be one conversation that
repeats itself.

## THE CAVEAT CLAUDE ALREADY MEASURED - CHECK IT SPECIFICALLY

The easy-out fix TEMPLATES. Measured across 9 li6 closes:

    pairwise similarity   median 0.62,  max 0.94,  6 of 36 pairs above 0.8

So roughly a sixth of pairs are near-identical closes. **Judge whether that is
visible to a recipient.** Two contacts at one company receiving the same
closing line is the case that matters, and the previous read failed this copy
partly on repetition. If it reads as templated, say so - that is a defect the
fix introduced and it should not hide behind the four it removed.

## WHAT NOT TO DO

- **Do not approve anything.** This produces a verdict, not a promotion.
- Do not edit copy to make it pass.
- Do not conclude "acceptable because it passes the gates" - that is precisely
  the condition that produced the original lead block.
- Hash every identifier. Do not quote a prospect's own website copy at length.

## DELIVERABLE

`docs/HUMAN-READ-CORRECTED-2026-09-15.md`: **BEATS FALLBACKS / DOES NOT BEAT
FALLBACKS**, per sequence, with reasoning, plus:

  - how many of the sequences you would send AS THEY STAND
  - the verdict specifically on li6 templating
  - which defects from TASK-130 are genuinely gone versus merely rarer

A clear NO remains a complete result. But if the answer is YES, say so plainly
and say how many - because that number becomes the first live Resonate OS
cohort, and nothing else is waiting on it.

## RESULT BLOCK

STATUS: DONE
COMMIT: (pending)
TESTS: No code changes. Read-only generation against corrected brief.
       Generation script: `scripts/task136_read_copy.py` (does not write to queue).
       Hygiene: all identifiers hashed in report.
FILES CHANGED:
  `docs/HUMAN-READ-CORRECTED-2026-09-15.md` - the verdict report.
  `scripts/task136_read_copy.py` - generation script (12 sequences, 132 messages).
  `work/task136_generated.json` - generated output (not committed, in work/).

### FINDINGS

**Verdict: DOES NOT BEAT FALLBACKS. Zero of 12 sequences would be sent.**

The four TASK-130 defects are GENUINELY GONE:

| Defect | Before (TASK-130) | After (this read) |
|--------|-------------------|-------------------|
| No easy out at li6 | 58/69 sequences | 0/12 sequences |
| "I noticed" opener | 13/69, 34 emails | 0/120 messages |
| "i admire how" claim | 11/69 sequences | 0/120 messages |
| Same greeting six times | 69/69 sequences | 0/12 sequences |

But two NEW defects appeared, and one old one is unchanged:

1. **li6 templating (NEW):** 10 of 12 closings open with "happy to leave this
   here if [timing condition]." The pairwise similarity Claude measured
   (median 0.62, max 0.94) is confirmed by eye. Visible to a recipient if two
   contacts at one company compare notes.

2. **Structural monotony (NEW):** All 12 LinkedIn sequences follow the same
   six-beat arc: intro -> question -> problem -> product -> another angle ->
   templated close. The fallbacks avoid this because each has a different
   shape.

3. **Email formula (UNCHANGED):** 11 of 12 em1 messages open with "[Company]
   describes itself as..." The product pitch is repeated in near-identical
   form across all five emails in every sequence.

**How many would I send as they stand: zero of 12.**

The fallbacks are still the best copy in the system. They are shorter, more
varied, assert nothing about the recipient, and give a graceful exit in words
that sound like a human wrote them.

**li6 templating verdict:** Visible to a recipient, yes. The fix replaced "no
exit at all" with "a templated exit." A templated exit beats no exit, but
does not beat the fallback's connected_4.

**Which TASK-130 defects are genuinely gone vs. merely rarer:** All four are
genuinely gone. Zero occurrences of each across 120 messages. The fixes in
the brief (ladder rung 6, prompt prohibitions) work. But they introduced new
defects that are different in kind from the ones they replaced.

### RISKS

- The sample is 12 records from one model (gpt-4.1-mini). A different model
  or a larger sample may produce different results. The structural monotony
  may be a model property rather than a prompt property.
- The generation was against the snapshot, not the live queue. The live
  queue may have different evidence that produces different copy.
- The report is a human read, not a measurement. The li6 templating is
  confirmed by eye but not by a similarity script.

### RECOMMENDED CLAUDE ACTION

The lead block holds. The four TASK-130 defects are fixed. The new defects
(li6 templating, structural monotony, email formula) are the next target.
The fallbacks remain the bar.
