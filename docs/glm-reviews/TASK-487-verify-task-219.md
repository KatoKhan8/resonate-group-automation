# TASK-487 — GLM independent verification of TASK-340

**Target branch:** `origin/qwen-worker-4-r67`
**Branch HEAD SHA:** `85b82ddc7ec4f72dc3297c151bb45aa44702a2ae`
**SHA verified:** `git rev-parse origin/qwen-worker-4-r67` → `85b82ddc7ec4f72dc3297c151bb45aa44702a2ae` ✓
**Task reviewed:** TASK-340 — the two cost levers (prompt caching, batch submission)
**Review date:** 2026-10-03

---

## Summary

**RECOMMENDATION: REWORK**

The two cost levers are built as transport-layer capabilities but have **zero production callers**. Not one. The Anthropic adapter, `complete_batch()`, and the `cache=` parameter on all three adapters are never invoked from `generate.py`, `modelrouter.py`, `campaign_strategy.py`, or any other production module. The result block admits this explicitly ("The Anthropic adapter has no production caller yet"). Per CLAUDE.md and the standing rule: **zero production callers means DISCONNECTED, which is a rework and not a merge.**

Additionally, the task's primary acceptance criterion — a before/after ledger cost measurement with real numbers — was not met. The result block states it is "OWED."

---

## Finding 1: Zero production callers — DISCONNECTED

**Severity: Critical. This is the repository's recurring defect.**

Grep results against `origin/qwen-worker-4-r67`:

```
# Who calls anthropic.complete() or anthropic.complete_batch()?
git grep -n "anthropic\.complete\|from.*anthropic.*import\|import.*anthropic" -- src/
→ (empty) — zero hits outside src/providers/anthropic.py itself

# Who calls llm.complete_batch()?
git grep -n "llm\.complete_batch\|from.*llm.*import.*complete_batch" -- src/
→ (empty) — zero hits outside src/llm.py itself

# Who passes cache=True/False to any complete() call in production?
git grep -n "\.complete(.*cache" -- src/ | grep -v providers/anthropic.py | grep -v providers/glm.py | grep -v llm.py
→ (empty) — zero hits

# Does generate.py know about anthropic?
git grep -n "anthropic" -- src/generate.py src/modelrouter.py src/campaign_strategy.py
→ (empty) — zero hits
```

**What exists:**
- `src/providers/anthropic.py` (517 lines) — a complete Messages API adapter with caching and batch
- `src/providers/glm.py` — `cache=False` parameter added
- `src/llm.py` — `cache=False` parameter on `OpenAICompatibleModel.complete()`, plus `complete_batch()` method and module-level entry point

**What is missing:**
- Any routing in `generate.py` or `modelrouter.py` that dispatches to `anthropic.complete()` for Claude models
- Any caller in the generation pipeline that passes `cache=True`
- Any caller anywhere that invokes `complete_batch()` with actual lead batches

This is the exact defect pattern recorded in CLAUDE.md under "THE RULE THAT DECIDED THREE REVIEWS ON 2026-09-14":
> "A change that is correct and not consumed is a change that did nothing."

The task's own RISKS section acknowledges this: *"The Anthropic adapter has no production caller yet. It is importable and tested, but `generate.py` does not route to it."*

**Falsification performed:** I searched for every possible consumption path — direct import, module-level call, routing table entry, model-provider mapping. None exists. The adapter is an island.

---

## Finding 2: Ledger measurement not performed — acceptance criterion unmet

**Severity: Critical. This is the task's primary acceptance criterion.**

TASK-340's acceptance criterion #3:
> "The before/after ledger measurement above, with real numbers pasted."

The task specification is explicit:
> "Report cost per lead before and after, from the LEDGER, not from an estimate."
> "Do NOT report a predicted saving."

The result block states:
> "The before/after ledger measurement is OWED."

No ledger rows were read. No before/after comparison was made. No cost delta was reported. The task's central deliverable — proving that caching reduces per-lead cost with measured numbers — does not exist.

This is not a minor gap. The entire justification for the task is the cost saving, and the saving is unmeasured.

---

## Finding 3: Tests are partially falsifiable but one is vacuous

**Severity: Suggestion.**

**Tests that ARE meaningful:**
- `test_anthropic_cached_has_cache_control_on_system` — asserts on the actual request body, checking that `system` is a list with `cache_control: {"type": "ephemeral"}`. Good: asserts on the wire format, not a flag.
- `test_anthropic_uncached_has_no_cache_control` — negative control, confirms absence. Good.
- `test_glm_cached_has_cache_directive` — asserts `chat_template_kwargs.enable_cache` in the body. Good.
- `test_batch_submits_n_items_in_one_request` — asserts 2 HTTP calls (create + poll) for 3 items, not 3. Good: proves the batch is one request.
- `test_cached_call_writes_ledger_row` — reads the actual ledger file. Good.

**Test that is NOT falsifiable:**
- `test_cached_and_uncached_produce_same_content` — feeds the SAME canned response to both calls and asserts the content is identical. This is vacuous: it proves the adapter returns whatever the transport returns, which is true by construction. A caching implementation that corrupted the output would still pass this test, because both calls get the same canned response. A real correctness test would need to either (a) call a real endpoint twice or (b) at minimum verify that the request bodies differ ONLY in the cache directive, not in any other field that could affect output.

**The `hasattr` pattern in `llm.complete_batch()`:**
```python
if hasattr(model, "complete_batch"):
    return model.complete_batch(prompts, ...)
```
`OpenAICompatibleModel` always has `complete_batch` (it was added in this same task), so the `hasattr` check always succeeds for the only model class that goes through this path. The fallback to sequential `complete()` calls is dead code for all real models. The test `test_module_batch_falls_back_for_plain_model` tests the fallback with a `PlainModel` that has no `complete_batch`, but no production model lacks it. This is not a bug but it is misleading: the fallback path is untestable in production conditions.

---

## Finding 4: Merging would not delete source code

**Severity: Informational.**

`git diff master...origin/qwen-worker-4-r67 --stat`:
```
 src/llm.py                                         |  37 +-
 src/providers/anthropic.py                         | 517 ++++++++++
 src/providers/glm.py                               |  13 +-
 tests/test_invariants.py                           |   7 +-
 tests/test_the_cohort_preamble_is_paid_for_once.py | 485 ++++++++++
```

All source changes are additions. The `glm.py` change adds a parameter with a default of `False`, so existing callers are unaffected. The `llm.py` change adds a parameter with a default of `False` and two new functions. The `test_invariants.py` change adds "anthropic" to the POST allowlist.

The doc changes are a task file moving from TODO to REVIEW (delete from TODO, add to REVIEW). This is expected workflow state.

**No source code deletion risk.**

---

## Finding 5: Scope drift — scratch file committed then removed

**Severity: Nice to have.**

Commit `44100378d` committed `suite_output.txt` (3 lines of test output). Commit `85b82ddc7` (HEAD) removed it. The scratch file does not exist at the branch head, but it was committed and then cleaned up in a separate commit. This is the exact pattern that QWEN.md §6 warns about: "scratch output committed into the repository root."

At the branch head, the file is gone. No pollution would reach master. But the two-commit history (add scratch, remove scratch) is noise.

---

## Finding 6: GLM cache directive may not match the endpoint

**Severity: Suggestion. Not verified against GLM API docs.**

The GLM adapter adds `body["chat_template_kwargs"] = {"enable_cache": True}` when `cache=True`. This is a GLM Coding Plan endpoint-specific field. The adapter's docstring says it speaks to a Chat Completions-compatible endpoint (`/chat/completions`). Whether `chat_template_kwargs.enable_cache` is honoured by that endpoint is not verified. If the endpoint ignores unknown fields, the cache directive is silently a no-op, and the tests pass because they only assert the field is present in the body — not that the endpoint honours it.

This is marked UNVERIFIED rather than confirmed as a defect.

---

## Finding 7: Cache pricing gap acknowledged but not addressed

**Severity: Suggestion.**

The result block acknowledges: *"Cache pricing in `model-prices.yaml` does not yet account for `cache_creation_input_tokens` or `cache_read_input_tokens`. The ledger rows carry these counts but `cost_micro_usd` treats them as normal input tokens."*

This means the ledger records cache token counts but prices them incorrectly — cache read tokens should be ~90% cheaper, but the current pricer charges full price. The cost measurement (Finding 2) would therefore show no saving even if caching were wired in and measured, because the pricer doesn't know about cache discounts. This compounds Finding 2: even if the measurement were performed, it would not show the expected saving.

---

## Disposition table

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | Zero production callers — DISCONNECTED | Critical | REWORK |
| 2 | Ledger measurement not performed | Critical | REWORK |
| 3 | Correctness test is vacuous | Suggestion | REWORK |
| 4 | No source deletion on merge | Informational | No action needed |
| 5 | Scratch file committed then removed | Nice to have | No action needed (cleaned at HEAD) |
| 6 | GLM cache directive may not match endpoint | Suggestion | UNVERIFIED |
| 7 | Cache pricing gap | Suggestion | REWORK (compounds #2) |

---

## Recommendation: REWORK

TASK-340 built transport-layer capabilities that are correct in isolation but have zero connection to the production generation pipeline. The repository has been burned repeatedly by this exact defect — code that is correct but unconsumed. The result block itself acknowledges the gap.

**What must happen before merge:**

1. **Wire the Anthropic adapter into the generation flow.** `generate.py` or `modelrouter.py` must route Claude-model calls through `anthropic.complete()` instead of (or in addition to) the OpenAI-compatible path. Without this, the adapter is dead code.
2. **Wire `cache=True` into the generation flow.** The cohort preamble is assembled somewhere in the generation pipeline. That caller must pass `cache=True` when the model supports it. Without this, caching is dead code.
3. **Wire `complete_batch()` into the generation flow.** The cohort loop must submit leads via `complete_batch()` when batching is enabled. Without this, batch is dead code.
4. **Perform the ledger measurement.** Run 10 leads uncached, 10 leads cached, read the ledger, report the delta. This is the task's central acceptance criterion.
5. **Fix cache pricing in `model-prices.yaml`.** Without cache-aware pricing, the ledger measurement will not show the expected saving even if caching is wired in.
6. **Replace the vacuous correctness test** with one that verifies the request bodies differ only in the cache directive.

**What is safe to keep:** The adapter code, the test structure, the `test_invariants.py` allowlist update. These are well-built. They just need a consumer.
