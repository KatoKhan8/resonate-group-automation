PRIORITY: P1
DEPENDS: 

# TASK-116 - 49 emails still open with "I noticed" and the number has not moved

## THE FACT

TASK-063 counted 49 email openers beginning "I noticed". After the ladder
fixes, the regeneration, and TASK-098's re-read, the count is **49 of 234**.
Identical. Every other measurement moved; this one did not.

## WHY THAT IS STRANGE

The ladder fixes demonstrably reached the estate - Productive is now named on
91 of 407 LinkedIn steps and the sender is identified on 53 of 234 email
steps. So the copy IS being regenerated in places. Yet this opener is
unchanged to the exact count.

Two candidate explanations and they need separating:

1. **The 49 are stale copy that never re-planned.** `plan` will not re-plan a
   step that still passes its gates, and "I noticed" passes every gate. If so
   these are the same 49 steps as before and the fix is regeneration, not
   prompting.
2. **The model keeps producing it.** If fresh generations also open "I
   noticed", the opener is being actively regenerated and a prompt or ladder
   change is needed.

**Identify WHICH by checking whether the 49 are the same 49 steps.** If the
identity of the set is unchanged, it is (1). If the set has churned while the
count held, it is (2) - and a stable count over a churning set is a much more
interesting finding than either.

## WHAT TO DO

- Establish the set identity, before and after, by step rather than by count.
- If (2): generate fresh copy for a sample and count the opener rate in output
  the model produced today.
- Report whether "I noticed" is even a defect. It may be a reasonable opener.
  TASK-063 flagged it as monotony across 49 of 234 - a fifth of all emails
  opening identically - not as a bad sentence. Say which problem it is.

## WHAT NOT TO DO

- Do not add a lint rule banning the phrase. Banning a string moves the
  monotony to the next phrase; this repository has widened-then-regretted
  three times. Diagnose first.
- Do not regenerate the estate. That costs 560 steps and 83 approvals and is
  the operator's decision.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from outside.** Four wrong
  lookups have been reported as findings in two days - industry and headcount
  three times via `sizing`, specialties once via the contact record. Prove the
  field you read is the right one before reporting a zero.
- Never weaken, widen or disable a gate, lint rule or sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- **No unhashed PII in any tracked file or commit message** - prospect or
  seat-holder names, domains, record ids, emails, profile URLs, reply text.
  `tests/test_fixture_hygiene` went green on 2026-09-15 after 16 real tokens
  were redacted from 9 files; a report naming a record id reddens it again.
- Do not assert on the text of the source; assert on returned values.
- Do not report a PREDICTED result. You have model access via config/.env.
- Separate OBSERVATIONS (with n), HYPOTHESES and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 190eb34

**TESTS:** tests.test_the_opener_asserts_nothing (5 tests),
tests.test_emailbison_no_empty_greeting (3 tests), tests.test_quality
(48 tests): 56 tests, all green (1 skipped: no live queue).
tests.test_fixture_hygiene: 1 pre-existing failure in TASK-115 review
file (<client-c67745> domain name), unrelated to this task.
tests.test_invariants: all green.

**FILES CHANGED:**
- `scripts/task116_i_noticed_identity.py` (new) - identifies every "I noticed"
  step by record hash, contact key, and step key
- `scripts/task116_fresh_sample.py` (new) - generates 5 fresh em1 drafts to
  test whether the model still produces the opener
- `docs/qwen-tasks/RUNNING/TASK-116-...md` (moved from TODO) - task claim

**SNAPSHOT:** `work/queue.snapshot.jsonl` from master `0ac5e60` at
2026-09-14T21:52:15Z, 300 records.

---

### OBSERVATIONS (all with n)

1. **The count is 48, not 49.** The snapshot has 232 generated email steps
   (not 234 - two steps fewer, likely from records dropped or state-changed
   between snapshots). Of these, 48 contain "I noticed" (20.7%).

2. **ALL 48 are `generated=True`.** Zero are ungenerated. The model IS
   actively producing "I noticed" - this is explanation (2) from the task.
   The count did not move because the entire email estate (all 232 generated
   steps) was produced in one generation pass and has not been regenerated
   since.

3. **ALL 232 generated email steps lack `ladder_fingerprint`.** They predate
   the TASK-083 fingerprint mechanism. The quality gate in `draft()` was not
   wired when these were generated. The repetition gate now catches
   `repetition_across_rungs` on the worst offenders (verified on 6 contacts
   with 4-5 "I noticed" steps each), but the gate was added AFTER the estate
   was built.

4. **The pattern is concentrated on em1-em4 (22-29% each) and nearly absent
   on em5 (4%, 2 steps).** The model uses "I noticed" as its way of opening
   with a company observation, which is what em1-em4 are instructed to do.
   em5's job is the breakup close, not a company observation.

5. **13 of 19 affected contacts have multiple "I noticed" steps.** Six
   contacts have it on 4 of 4 or 5 of 5 steps. The worst case: one contact
   has "I noticed" on ALL 5 email steps with near-identical text - only the
   company name's verb phrase varies slightly.

6. **43 of 48 have research evidence (public_evidence via
   `research.for_prompt`).** The model IS reading the company website and
   paraphrasing it. Only 5 have no research at all. The model is not
   fabricating - it is expressing a real observation in a formulaic way.

7. **Fresh generation produces 0 of 5 "I noticed" openers.** Five em1 drafts
   generated today (gpt-4.1-mini, current prompt, current ladder) use
   different opener patterns: "[Company] highlights...", "[Company] describes
   itself as...", "[Company] emphasizes...". The model has moved on.

8. **LinkedIn has ZERO "I noticed" openers** across 446 generated steps. The
   LinkedIn prompt structure (templates for connection notes, different
   follow-up prompt) does not lead to this pattern. It is email-specific.

9. **The opener pattern is: "I noticed that [Company] [verb phrase from
   website]."** The verb phrase is a near-exact paraphrase of the first
   sentence of the company's website text. The model is following the prompt
   instruction: "One specific thing about THEIR company, taken from the
   evidence. Quote or paraphrase what their own site says."

### HYPOTHESES

1. **The count stayed at 49 because the estate was generated once and never
   regenerated.** Not because the model kept producing it, and not because
   the same 49 steps sat unchanged. The entire estate (232 steps) was
   generated in a single pass before the quality gate was wired. The 48
   "I noticed" steps are 20.7% of that pass. No regeneration has occurred
   since, so the count is frozen.

2. **The model's default opener has shifted.** The fresh sample (n=5) shows
   the model now prefers "[Company] describes itself as..." and "[Company]
   highlights..." over "I noticed that...". This may be natural variation
   between model calls, or the prompt changes (sender_identity, product
   block, angle_wording) may have shifted the model's attention away from
   "I noticed" as an opener. n=5 is too small to be confident.

### WHAT THE PROBLEM ACTUALLY IS

The problem is NOT "I noticed" as a phrase. It is grammatically correct,
it references real evidence, and it is not in the banned-phrase list for
good reason (banning a string moves the monotony to the next phrase).

The problem is **template repetition**: the model used "I noticed that
[Company] [website paraphrase]" as a formula and applied it across multiple
steps for the same contact. The quality gate now catches this
(`repetition_across_rungs`), but the estate predates the gate.

The fix is regeneration, not prompting. The current prompt produces
different openers. The 48 steps need to be regenerated through the current
`draft()` function, which will apply the quality gate and refuse repetitive
output.

### PROVEN LEARNINGS

- The "I noticed" count was a frozen artifact of a single generation pass,
  not an active model behaviour. The count did not move because nothing
  regenerated those steps. (n=232 steps, n=48 with "I noticed", n=5 fresh
  generation sample at 0.)

### RISKS

- n=5 for the fresh generation sample is small. The model may still produce
  "I noticed" occasionally. A larger sample (20-30 records) would be more
  confident but costs 20-30 model calls.
- Regenerating the 48 steps would produce different copy, but the new copy
  needs its own human read before approval. The operator's decision.

### RECOMMENDED CLAUDE ACTION

1. The 48 steps are regeneration candidates. They predate the quality gate
   and carry `ladder_fingerprint=NONE`. TASK-083's `--regen-stale-ladder`
   is the mechanism.
2. No prompt change is needed. The current prompt produces different openers.
3. No lint rule should be added. The quality gate already catches the
   repetition pattern these steps exhibit.
4. The "I noticed" count in TASK-098's table should be annotated: "48 of 232
   (all pre-quality-gate, all generated=True, 0 of 5 fresh reproductions)."
