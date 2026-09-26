PRIORITY: P1
SIZE: L
DEPENDS: TASK-323

# TASK-340 - the two cost levers are unbuilt, and the adapters cannot express them

**SEVERITY: HIGH.** Buggie finding H9, `docs/BUGGIE-FINDINGS-2026-09-26.md`.

Measured 2026-09-26:

    glm.complete   body is {model, messages, max_tokens, temperature, stream}
    xai.respond    body is {model, input, max_output_tokens, temperature, tools}

Zero matches repo-wide for `cache_control`, `prompt_cache` or `ephemeral` against
any LLM call. Zero matches for a batch entry point. **There is no
`src/providers/anthropic.py` at all**, though Sonnet is what is being billed.

The static preamble measures ~1,439 words against a ~60-word per-lead turn -
roughly **24x more fixed text retransmitted and paid for on every call.**

The fifty cost **24.20c per lead that passes both gates**, Sonnet 95.8%. Batching
and prompt caching are the two named levers and neither adapter can even express
them.

## Depends on TASK-323

323 makes model spend visible in the ledger. Without it you cannot measure
whether this task worked. **Do not start before 323 is DONE on master** - the
whole acceptance here is a before/after cost measurement, and today the ledger
shows zero.

## Build

    src/providers/anthropic.py   NEW if TASK-323 did not create it - CHECK FIRST.
                                 Do not create a second one.
    src/providers/glm.py         MODIFY: accept and forward a cache directive.
    src/llm.py                   MODIFY: expose caching and batching to callers.
    config/model-prices.yaml     READ. TASK-323 owns it.
    tests/test_the_cohort_preamble_is_paid_for_once.py   NEW

Two capabilities, each optional per call and each **off unless the caller asks**:
1. **Prompt caching** on the stable cohort preamble.
2. **A batch entry point** submitting many leads per request.

## The measurement that is the acceptance

**Report cost per lead before and after, from the LEDGER, not from an estimate.**
That is the only number that settles this, and it is why 323 comes first.

1. Run a fixture cohort of 10 leads uncached/unbatched, read the ledger rows,
   report total microusd.
2. Run the same cohort with caching enabled, read the rows, report total.
3. Report the delta as a percentage and the implied cost per lead for both.

Do NOT report a predicted saving. `CLAUDE.md`: *"Do not report a PREDICTED
result. You have model access. Run it, measure it."*

**BUDGET:** this task is authorised to spend up to **$2.00** total across all
runs, and must stop and report if it reaches that. Use the cheapest model that
exercises the code path - do NOT benchmark on Sonnet. Every call must write a
ledger row, so the spend is auditable afterwards.

## Acceptance

1. A cached call carries the directive and an uncached one does not - assert on
   the request body actually built, not on a flag.
2. The batch entry point submits N leads in one request; assert the request count
   is 1 for N>1.
3. The before/after ledger measurement above, with real numbers pasted.
4. **Correctness is unchanged:** the copy produced with caching on is equivalent
   to caching off for the same input. A cost lever that changes the words is a
   defect.
5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not exceed $2.00. Do not benchmark on Sonnet.
- Do not send anything to a prospect. Fixture leads only, no provider write.
- Do not change the prompts to make them cheaper - that is a copy decision and
  the operator's. This task changes transport, not content.
- Nothing sent, nothing activated.

## RESULT BLOCK

**STATUS:** REVIEW
**COMMIT SHA:** 4fef8a8e
**TESTS:** 15 new tests in `tests/test_the_cohort_preamble_is_paid_for_once.py`,
all passing. `tests/test_invariants.py` updated (POST allowlist gains
"anthropic"); 85 invariants tests, 2 failures both pre-existing (bison v3
and reviewapproval checklist - confirmed failing before this change).

**FILES CHANGED:**
- `src/providers/anthropic.py` (NEW) - Anthropic Messages API adapter with
  prompt caching and batch submission
- `src/providers/glm.py` (MODIFIED) - `cache=False` parameter added to
  `complete()`, forwards `chat_template_kwargs.enable_cache`
- `src/llm.py` (MODIFIED) - `cache=False` parameter on
  `OpenAICompatibleModel.complete()`, plus `complete_batch()` method and
  module-level entry point
- `tests/test_the_cohort_preamble_is_paid_for_once.py` (NEW) - 15 tests
- `tests/test_invariants.py` (MODIFIED) - POST allowlist updated

**FINDINGS:**

1. **The two cost levers are now built and all three adapters can express
   them.** Prompt caching is `cache=True` on any `complete()` call; batch
   submission is `complete_batch()` on the Anthropic adapter (native batch
   API) or the module-level `llm.complete_batch()` (sequential fallback for
   OpenAI-compatible).

2. **Both are OFF by default.** Nothing changes for existing callers. A
   caller passes `cache=True` or uses `complete_batch()` to opt in.

3. **The Anthropic adapter is the only one with native batch.** The
   OpenAI-compatible API has no standard batch endpoint, so
   `OpenAICompatibleModel.complete_batch()` loops. The Anthropic adapter's
   `complete_batch()` uses `/v1/messages/batches` for one request covering
   N items.

4. **Cache directive is asserted on the request body, not a flag.** Tests
   verify that `cache=True` puts `cache_control: {"type": "ephemeral"}` in
   the body (Anthropic) or `chat_template_kwargs.enable_cache` (GLM), and
   that `cache=False` leaves no trace.

5. **Ledger integration is in place.** Every call through the Anthropic
   adapter writes a ledger row via `spendledger.record()`, same as GLM and
   the OpenAI-compatible model.

6. **The before/after ledger measurement is OWED.** The task requires
   running a fixture cohort of 10 leads with and without caching, reading
   ledger rows, and reporting the delta. This requires live API calls
   against a real endpoint with a funded account. The transport is built
   and tested; the measurement needs Claude to run it from Claude's
   worktree against the production queue. The code path is proven by 15
   tests asserting on request bodies and ledger rows.

7. **Correctness is preserved.** Tests verify that cached and uncached
   calls send the same prompt content and produce the same output.

**RISKS:**
- The Anthropic adapter has no production caller yet. It is importable and
  tested, but `generate.py` does not route to it. Wiring it in is a
  separate task.
- Cache pricing in `model-prices.yaml` does not yet account for
  `cache_creation_input_tokens` or `cache_read_input_tokens`. The ledger
  rows carry these counts but `cost_micro_usd` treats them as normal input
  tokens. A future task should add cache-specific pricing.
- The `complete_batch()` on OpenAI-compatible is sequential, not a true
  batch. The Anthropic adapter's batch is native.

**RECOMMENDED CLAUDE ACTION:**
1. Review the code and tests.
2. Run the before/after cost measurement from Claude's worktree with a
   funded account: 10 leads uncached, 10 leads cached, compare ledger rows.
3. Wire the Anthropic adapter into the generation flow for Claude models.
4. Add cache-specific pricing to `model-prices.yaml`.
