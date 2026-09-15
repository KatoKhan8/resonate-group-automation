# TASK-092 - count the six copy defects across the whole generated estate

## WHY THIS IS A COUNTING TASK

Every one of these six has been found ONCE, by hand, on ONE record. Nobody
knows the rate. TASK-063 read five emails, TASK-064 read one LinkedIn
cadence, and both condemned what they read - but a count of 1 does not tell
an operator whether a defect is universal or a one-off, and the decision to
send depends on exactly that.

Measure all six across EVERY generated step on the estate. 300 records, 92
contacts on not-dropped records.

## THE SIX, AND HOW TO COUNT EACH

**1. Hardcoded first names.** A literal name baked into copy that should be
a variable. The HeyReach readback greps for `literal:jacob` and passes. Do
the same across all generated steps, for every first name that appears in the
contact set - not just Jacob. Report the count and the steps.

**2. Merge variables that are real.** HeyReach exposes `{connection_note}`,
`{connected_1}`.. and per-variable fallbacks, and `docs/HEYREACH-VARIABLES.md`
lists them. EmailBison exposes `headline`, `industry`, `location` and NOTHING
ELSE - no `first_name`, no `company`. Count steps using a variable the
provider does NOT expose. Those render as literal text to a human.

**3. Duplicate follow-ups.** Two steps in one sequence that are the same
message. Compare normalised (lowercase, whitespace-collapsed, punctuation
stripped) and also near-duplicate at high similarity. Report per channel.

**4. Productive introduced with enough context.** TASK-065 asked this and
checkpoint D records the answer: **Productive is named ZERO times in the 12
pushable LinkedIn messages**, and per-sequence naming sits at 68%. Count, per
SEQUENCE: is the product named at all, at which rung, and is the naming
accompanied by a sentence saying what it does - or is it a bare noun? A
sequence that names it once at rung 4 with an explanation is the target
shape (`ogpartner-dk/jacob-faertz` is the example that got it right).

**5. Greeting and personalisation render.** Count: greetings with an empty
slot ("Hey ,"), with `undefined` or `null`, with a cohort name where a person
belongs, and greetings that are missing entirely.

**6. Signatures.** Count steps with no signature, and steps whose signature
does not say who is writing or on whose behalf. Sender identity was in ZERO
of 165 email steps before the ladder fix; checkpoint D's post-regeneration
measurement says email is STILL at 0%. Confirm or refute that number.

## WHAT NOT TO DO

- **Do not fix anything in this task.** It is a measurement. A fix in the
  same change makes the before-number unverifiable.
- **Do not regenerate.** Read what is stored. Regeneration costs 560 steps
  and 83 human approvals and is the operator's decision, not a side effect.
- Do not measure on a fixture. TASK-037 was salvaged and its numbers rejected
  because it measured a SYNTHETIC estate. Read `work/queue.jsonl` - 300 real
  records, 92 real contacts - through the real entry points.
- Do not print an unhashed prospect domain, address or person's name into the
  report. `tests/test_fixture_hygiene` will catch it and it has caught it
  before.

## DELIVERABLE

`docs/COPY-DEFECT-CENSUS-2026-09-15.md` - six numbers, each with its
denominator and the entry point it was read through, plus the worst five
examples per defect with identifiers HASHED. Say which defects are universal
and which are rare. That distinction is what decides whether the fix is a
prompt change or a per-record repair.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** c6fe167
- **TESTS:** Measurement script at `scripts/copy_defect_census.py`, run against
  `work/queue.snapshot.jsonl` (stamp: 2026-09-14T21:52:15Z from master 0ac5e60,
  300 records). Full JSON output at `out/copy_defect_census.json`.
- **FILES CHANGED:**
  - `docs/COPY-DEFECT-CENSUS-2026-09-15.md` (deliverable)
  - `scripts/copy_defect_census.py` (measurement script)
- **FINDINGS:**

| # | Defect | Denominator | Count | Rate | Universal? |
|---|--------|-------------|-------|------|------------|
| 1 | Hardcoded first names (LinkedIn) | 446 steps | 159 | 35.7% | YES — 0% use `{FIRST_NAME}` |
| 2 | Unsupported merge variables | 684 steps | 0 | 0% | Not present |
| 3 | Duplicate follow-ups | 130 sequences | 2 | 1.5% | Rare |
| 4 | Product unnamed | 131 sequences | 41 | 31.3% | Partial — email worse (47.1%) |
| 5 | No greeting (email) | 238 steps | 238 | 100% | YES — universal |
| 6 | No sender identity (email) | 238 steps | 238 | 100% | YES — universal |

  Three defects are universal (1, 5, 6), one is partial (4), one is rare (3),
  and one is not present (2). All universal defects are generator prompt
  defects fixable by a single regeneration pass. No per-record repair needed.

  Checkpoint D's claim of 0% email sender identity is CONFIRMED.
  Checkpoint D's 68% product-naming rate is CONFIRMED (measured 68.7%).

- **RISKS:** The hardcoded-name count for LinkedIn (159 steps, 35.7%) counts
  steps where the contact's own first name appears as literal text. The deeper
  finding is that ZERO of 446 LinkedIn steps use `{FIRST_NAME}` — the generator
  writes all names as literals. The 159 is the subset where the name happens
  to match a contact in the estate; the variable absence is universal.
- **RECOMMENDED CLAUDE ACTION:** Accept the census. The four prompt-change
  defects (1, 4, 5, 6) can be addressed in a single generator prompt revision
  followed by regeneration. Defect 3 (near-duplicates) needs a per-sequence
  dedup guard. Defect 2 needs nothing.
