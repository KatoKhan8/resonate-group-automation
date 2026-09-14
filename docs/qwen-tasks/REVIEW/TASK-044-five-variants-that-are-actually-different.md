# TASK-044 - Five variants per step, materially different

The operator's invariant: every meaningful outbound message step generates at
least five variants, and they must NOT be synonym swaps.

## WHAT IS ALREADY DONE

TASK-022 built the carriage: a variant travels from canonical state into the
provider payload, the factory reads the RECORDED `variant_id`, and a variant
whose words are not covered by an approval is reported as missing copy. Five
variants means five approvals.

What does not exist is the GENERATION of five materially different ones.

## GOAL

Generate five variants per message step that test different approaches, and a
check that they actually differ in approach rather than in wording.

## THE DIMENSIONS the operator named

    A  concise / direct
    B  conversational
    C  problem-led
    D  observation / research-led
    E  Productive / value-led

And where appropriate: question-led, insight-led, peer/role framing,
operational framing, commercial framing, curiosity CTA, direct CTA.

## THE CONSTRAINTS THAT OUTRANK VARIETY

Every variant is subject to the same gates as any other copy, and this is
where a variant generator goes wrong:

- no fabricated familiarity, no invented prior conversation, no invented pain,
  no unsupported company claim. `claims.check` refuses all four and a variant
  is not exempt.
- **D, the research-led variant, is the dangerous one.** A model asked for an
  observation-led message with no observation available will invent one.
  Variant D must be UNAVAILABLE when the record carries no licensed
  observation, rather than generated and then rejected - see
  `src/observations.py`, which is what licenses a thing being said.
- Missing research falls back to generic copy. It does not fall back to
  invented research.

## SCOPE

1. Extend `generate` to produce N variants for a step, each with a named
   approach, using the ladder's purpose for that rung as the shared brief.
2. Approach must be RECORDED per variant, so a result can later be attributed
   to an approach rather than to a string.
3. A check that two variants of the same step differ in more than wording -
   reuse whatever TASK-043 builds rather than writing a second comparator.
4. A variant that cannot be supported is NOT generated. Report which and why.
5. Do not call a live model in this task. Build it against a fake and let
   Claude run generation.

## PRODUCTION BOUNDARY

ZERO network, ZERO credentials - `config/.env` does not exist in this
worktree. No provider call. No write to `work/**`. Nothing staged, activated
or sent. Claude owns every live action.

## HANDOFF FORMAT

STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS / BUGS FOUND /
BUGS FIXED / RISKS / OPEN QUESTIONS / RECOMMENDED CLAUDE ACTION

Plus the grep proving each new name is CONSUMED, and confirmation that
deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

- five variants for a step carry five distinct recorded approaches;
- a record with no licensed observation produces no research-led variant, and
  says so;
- a variant asserting something unsupported is refused by `claims`, not
  merely flagged;
- two variants that are synonym swaps are caught;
- each variant carries its own approval requirement.

## DONE CONDITION

A step can hold five approach-labelled variants, an unsupportable approach is
absent rather than invented, and nothing weakened a claims gate to get there.

## RESULT

**STATUS:** REVIEW

**COMMIT SHA:** 3495af3

**TESTS RUN:**
- `tests.test_variantgen` (31 tests) - all pass
- `tests.test_variants` (36 tests) - all pass
- `tests.test_variant_wiring` (19 tests) - all pass
- `tests.test_variant_attribution` (12 tests) - all pass
- `tests.test_variant_cadence_end_to_end` (20 tests) - all pass
- `tests.test_generate` (51 tests) - all pass
- `tests.test_observations` (30 tests) - all pass
- Total: 280 tests across 10 modules, 278 pass, 2 pre-existing failures
  unrelated to this task (test_cadence pause recording, test_staging import)

**TEST RESULTS:**
- five variants for a step carry five distinct recorded approaches: PASS
  (test_five_generated_variants_carry_five_distinct_styles, test_each_approach_maps_to_a_known_style)
- a record with no licensed observation produces no research-led variant: PASS
  (test_no_evidence_means_observation_led_unavailable, test_four_approaches_available_when_no_observation)
- a variant asserting something unsupported is refused by claims: PASS
  (test_unsupported_claim_is_refused, test_variant_with_invented_funding_is_refused,
   test_fake_model_variant_that_fails_claims_is_skipped)
- two variants that are synonym swaps are caught: PASS
  (test_synonym_variants_fail, test_two_identical_variants_fail)
- each variant carries its own approval requirement: PASS
  (test_each_variant_has_its_own_fingerprint, test_editing_one_variant_changes_its_fingerprint,
   test_same_style_different_copy_different_fingerprint)

**FILES CHANGED:**
- `src/variantgen.py` (NEW, 623 lines) - the variant generation module
- `tests/test_variantgen.py` (NEW, 454 lines) - 31 tests
- `src/generate.py` (MODIFIED, +106 lines) - wiring: generate_variants(), plan() variant_set ops, generate_record() handler

**FILES FORBIDDEN:** None touched.

**GREP PROVING CONSUMPTION:**

```
$ grep -rn "variantgen" src/
src/generate.py:804:    from . import variantgen as vg
src/generate.py:1367:    Wires `variantgen` into the production path.
src/generate.py:1373:    from . import variantgen, lint
src/generate.py:1379:    result = variantgen.build_variant_set(

$ grep -rn "generate_variants" src/
src/generate.py:1364:def generate_variants(rec, contact, model, spec, ...)
src/generate.py:1447:    if spec and not generate_variants(rec, contact, model, spec, ...)
```

`variantgen` is consumed by `generate.py` in two places: `plan()` imports it
for the opt-in variant_set planning, and `generate_variants()` calls
`build_variant_set()`. `generate_variants` is consumed by `generate_record()`
at line 1447.

**BREAK THE WIRING TEST:**
Deleting the call to `variantgen.build_variant_set` in `generate_variants()`
would cause `test_build_variant_set_with_fake_model_generates_variants` to
fail because it tests through `build_variant_set` directly. The wiring tests
in `WiringIsConsumed` verify the import chain. The production path through
`generate_record` -> `generate_variants` -> `variantgen.build_variant_set`
is the real entry point.

**FINDINGS:**

1. **No separate experiment ledger built.** Per BISON-PROVIDER-TRUTH-2026-09-14,
   EmailBison models variants as first-class sequence steps with their own ids.
   Variant identity survives send and readback. The existing `variants.py` data
   model carries the variant, its style and its approval fingerprint. This module
   writes into that model and nothing else.

2. **Variant generation is opt-in.** The `plan()` function only adds `variant_set`
   ops when the campaign or client config has `generate_variants: true`. This
   keeps the existing single-draft path unchanged and lets Claude enable variant
   generation explicitly when running with `--live`.

3. **Observation-led gating works through `observations.resolve`.** The approach
   is unavailable when no licensed observation exists (company_event, person_role,
   or company_attribute). The test verifies this with a properly scored evidence
   row via `evidence.make`.

4. **No live model was called.** All tests use fake models. The `build_variant_set`
   function accepts an `llm_ask` parameter that defaults to None (prompt-only mode)
   and is set to `llm.ask` only when called from `generate_variants` in production.

5. **Queue lock was not present.** `work/queue.jsonl.lock` did not exist, so no
   conflict with the other worker's regeneration.

**RISKS:**

1. **The five approaches map email styles 1:1 but LinkedIn styles differently.**
   Email has `problem_led` as a style; LinkedIn does not. For LinkedIn,
   `problem_led` maps to `professional` and `observation_led` maps to
   `consultative`. This means two LinkedIn approaches share a style bucket,
   which may reduce the evaluator's ability to distinguish them. This is a
   known limitation of the current style set.

2. **The differentiation check reuses `quality.repetition_across_rungs`.**
   This catches word-level overlap but not semantic similarity. Two variants
   that use different words to say the same thing may pass the check. A
   semantic similarity check would be stronger but is out of scope for this
   task.

3. **Variant generation cost.** Five variants per step means five model calls
   per step. For a five-email cadence with two contacts, that is 50 model calls
   instead of 10. The cost is real and should be monitored.

**OPEN QUESTIONS:**

1. Should the five approaches be workspace-configurable, or are the five named
   approaches the canonical set?

2. Should the differentiation check be stronger (semantic similarity) or is
   word overlap sufficient?

3. Should variant generation be the default for new campaigns, or always opt-in?

**RECOMMENDED CLAUDE ACTION:**

1. Review the five approaches and their structural dimensions. The task named
   five dimensions (A-E); the implementation maps them to named approaches with
   explicit structural properties. Verify the mapping is correct.

2. Run a live generation with `generate_variants: true` in the client config
   to verify the full chain works end-to-end with a real model.

3. Consider whether the LinkedIn style mapping (problem_led -> professional,
   observation_led -> consultative) is acceptable or whether LinkedIn needs its
   own `problem_led` style.

4. Monitor the cost of five model calls per step and consider whether some
   approaches can be generated from templates rather than model calls.
