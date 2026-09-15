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

---

## RESULT

**STATUS:** BLOCKED - queue access required

**COMMIT SHA:** N/A

**TESTS:** N/A

**FILES CHANGED:** None

**FINDINGS:**

### Blocker

This task requires reading `work/queue.jsonl` with 300 real records and 92 contacts to measure six copy defects across every generated step. The queue is **empty in this worktree** - `work/` is gitignored per QWEN.md and contains no data.

QWEN.md states:
> To READ real record data, use the snapshot: `work/queue.snapshot.jsonl` - a read-only copy of production

No snapshot file exists in this worktree either.

### What the task requires

1. **Hardcoded first names** - grep all generated steps for literal names from the contact set
2. **Merge variables that are real** - check each step against provider variable exposure (HeyReach: `{connection_note}`, etc.; EmailBison: `headline`, `industry`, `location` only)
3. **Duplicate follow-ups** - normalise and compare steps within each sequence
4. **Productive introduced with context** - per-sequence: is the product named, at which rung, with what explanation
5. **Greeting and personalisation render** - count empty slots, undefined/null, cohort names, missing greetings
6. **Signatures** - count missing or incomplete sender identity

Each measurement requires iterating over the 92 contacts on not-dropped records and reading their generated steps through the real entry points (`generate._note_quality`, `generate._quality_of`, etc.).

### What would unblock this

1. **Provide queue access** - either:
   - Populate `work/queue.snapshot.jsonl` in this worktree (Claude can copy from production)
   - Run the measurement from Claude's worktree where `work/queue.jsonl` exists
   - Provide a filtered/aggregated export that preserves the generated step text without PII

2. **Alternative** - if the measurement has already been done in another worktree or session, point to the result document

### What I did NOT do

- Did not measure on fixtures (TASK-037 was rejected for this reason)
- Did not regenerate (costs 560 steps and 83 human approvals)
- Did not print unhashed prospect data
- Did not fabricate numbers from incomplete data

**RECOMMENDED CLAUDE ACTION:**
This task is a pure measurement with no code changes. It should be run from a worktree with queue access, or the queue should be made available here. The six defect rates are load-bearing for the send decision - an operator cannot decide whether a defect is universal or rare without the count.
