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
