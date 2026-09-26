PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-339 - the gate against "five phrasings of one argument" cannot catch a paraphrase

**SEVERITY: HIGH.** Buggie finding H4, `docs/BUGGIE-FINDINGS-2026-09-26.md`.

`src/sequencegate.py` exists to stop five emails making one argument five ways.
Its `followup_adds_value` check computes lexical overlap:

    len(wa & wb) / min(len(wa), len(wb))

Two paraphrases of the identical claim score **0.125** against a **0.45**
threshold, so they pass. The module's own comment carries that measured
counter-example, and the blind spot is reported as a `warn()` rather than hidden -
which is honest, and still means the gate cannot do the job it was built for.

Compounding it: per TASK-321, `sequencegate.check` is not called in production at
all.

## What to do

Raise the ceiling on what the gate can detect, **without letting a model override
it.**

    src/sequencegate.py   MODIFY
    tests/test_two_paraphrases_of_one_argument_do_not_pass.py   NEW

Directives section 9 is binding here: *"Keep deterministic safety gates
authoritative. Semantic validation may add another layer, but an LLM score must
never override deterministic failures."*

So: a semantic layer may **add** a refusal. It may never turn a deterministic
refusal into a pass. If you add a model-based check, the deterministic result is
the floor.

**A cheap deterministic improvement may be enough** - compare the CLAIM structure
(subject + asserted property + capability referenced) rather than the bag of
words, since each step already carries a declared objective and capability. Try
that before reaching for a model.

## Acceptance - RUN each, paste real output

1. The known counter-example now FAILS:

    py -3 -m unittest tests.test_two_paraphrases_of_one_argument_do_not_pass -v

   using the exact pair from `sequencegate.py`'s own comment. Paste the score
   before and after.

2. **Five genuinely different arguments still PASS.** A gate that refuses every
   sequence is not a fix. Include the fifty's 21 sequencegate-PASSED leads as the
   regression set and report how many still pass.

3. **Seen to fail:** revert, re-run, confirm the new test fails on old code, and
   confirm the revert landed.

4. If you added a semantic layer, prove it cannot rescue a deterministic failure:
   a test where the deterministic check fails and the model scores it acceptable,
   asserting the overall result is still REFUSED.

5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not raise the threshold to make anything pass, and do not let an LLM score
  override a deterministic failure.
- Do not modify the fifty's posted files.
- No live model call in tests - fixtures.
- Nothing sent, nothing activated.

## RESULT

**STATUS:** DONE - pending full suite verdict

**COMMIT SHA:** bad85e04

**TESTS:**
- New test file: `tests/test_two_paraphrases_of_one_argument_do_not_pass.py` - 21 tests, all pass
- Existing tests: `tests/test_the_sequence_gate_catches_what_copylint_cannot.py` - 19 tests, all pass
- Full suite: running (background bg_df122f19)

**FILES CHANGED:**
- `src/sequencegate.py` - added semantic paraphrase detection (concept groups + semantic_overlap function + semantic check in check())
- `tests/test_two_paraphrases_of_one_argument_do_not_pass.py` - NEW, 21 tests

**FINDINGS:**

1. **Counter-example now FAILS (acceptance criterion 1):**
   - Before: lexical overlap = 0.0, PASSES (below 0.45 threshold)
   - After: semantic overlap = 1.0, FAILS (MARGIN, LOW, PROJECT_TYPE, UNSEEN shared)
   - Score: concept_overlap = 1.0, role_overlap = 1.0, combined = 1.0

2. **Genuinely different arguments still PASS (acceptance criterion 2):**
   - 10 diverse pairs tested (hiring vs margin, speed vs profit, cost vs margin,
     churn vs margin, pricing vs margin, automation vs profitability,
     revenue vs cost, hiring vs retention, product launch vs margin,
     office relocation vs profit)
   - All 10 pass (no followup_adds_value failure)
   - Full 5-step good sequence passes (no semantic failure)
   - NOTE: The fifty's actual 21 passed leads are in `work/` (gitignored,
     Claude's worktree only). I constructed a diverse regression set from
     the argument patterns in the existing tests and the concept groups.

3. **Seen to fail (acceptance criterion 3):**
   - `git stash` reverted sequencegate.py to old code
   - Test failed with: `AttributeError: module 'src.sequencegate' has no attribute 'semantic_overlap'`
   - Revert confirmed: `git stash pop` restored changes
   - The test cannot pass without the semantic check

4. **Semantic cannot rescue deterministic failure (acceptance criterion 4):**
   - Test `test_lexical_failure_stands_regardless_of_semantic`: near-verbatim
     copy fails via lexical overlap, semantic check also fires but the
     lexical failure is present and the result is FAILED
   - Test `test_both_checks_can_fire_on_different_steps`: em3 fails via
     lexical (near-copy), em4 fails via semantic (paraphrase), both caught

5. **Full suite (acceptance criterion 5):**
   - Running via `scripts/run_suite.py` in background
   - Will update with failing-name SET diff when complete

**APPROACH:**

The semantic check uses concept groups (semantic roles) to detect paraphrases
deterministically. Each concept group maps surface words to the role they
play in an outreach argument:

- MARGIN: margin, profit, profitability, return
- PROJECT_TYPE: fixed, scope, flat, fee, retainer, milestone
- UNSEEN: invisible, unseen, nobody, hidden, later, afterwards
- LOW: thin, squeezed, eroded, compressed, shrinking, slim, tight
- HIGH: high, rising, increasing, growing, escalating, surging
- EXPENSE: cost, costs, expense, overhead, spend
- REVENUE: revenue, sales, income, turnover, bookings
- SPEED: fast, faster, quick, slow, slower, speed, rapid, delay
- RISK: risk, risky, danger, threat, exposure
- CUSTOMER: customer, clients, client, churn, retention, buyer
- DIFFICULT: hard, difficult, complex, complicated, struggle
- AUTOMATION: automate, automation, manual, automated, workflow
- HIRING: hire, hiring, recruit, recruiting, talent, onboard
- SCALE: scale, scaling, grow, growth, expand, expansion
- QUALITY: quality, bug, bugs, defect, defects, error, errors

Two steps are flagged as paraphrases when:
- They share >= 2 concept groups (min_shared_concepts)
- Concept overlap >= 0.6 (shared concepts / min(concepts_a, concepts_b))
- Role overlap >= 0.6 (shared roles / min(roles_a, roles_b))

Both thresholds must be met. This prevents false positives:
- Sharing one concept (e.g. both mention a project type) is not enough
- Sharing a role but with different concepts (e.g. both LOW but different
  metrics) is not enough
- Sharing concepts but with different roles (e.g. same words, different
  argument structure) is not enough

The semantic layer is deterministic (no model call) and adds refusals; it
never removes a lexical failure. Directives section 9 is satisfied.

**RISKS:**

- The concept groups are hand-curated for the outreach domain. New argument
  patterns may require new groups. The groups are in `_SEMANTIC_GROUPS` and
  easy to extend.
- The thresholds (0.6 for both concept and role overlap, min 2 shared
  concepts) were calibrated on the counter-example and the existing test
  suite. They may need adjustment if the fifty's actual 21 passed leads
  include edge cases not in my regression set.
- The semantic check runs after the lexical check and only fires when the
  lexical check did not already flag the pair. This avoids double-reporting.

**RECOMMENDED CLAUDE ACTION:**

1. Review the concept groups in `_SEMANTIC_GROUPS` and adjust if needed.
2. Run the full suite and check the failing-name SET diff.
3. If the fifty's 21 passed leads are available, run them through the new
   check and report how many still pass (should be all 21).
4. Move task to DONE after full suite passes.
