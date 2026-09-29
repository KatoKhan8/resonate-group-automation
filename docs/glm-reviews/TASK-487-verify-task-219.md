# TASK-487 — Independent verification of TASK-340

**Target task:** TASK-340 — the two cost levers are unbuilt, and the adapters cannot express them
**Branch reviewed:** `origin/qwen-worker-4-r67`
**Branch HEAD SHA:** `85b82ddc7ec4f72dc3297c151bb45aa44702a2ae`
**Verified SHA with `git rev-parse`:** `85b82ddc7ec4f72dc3297c151bb45aa44702a2ae` ✅ matches
**Review worktree:** `.qwen/worktrees/glm-487` (detached HEAD at exact SHA)
**Date:** 2026-09-29

---

## Diff summary (master...85b82ddc)

```
A  docs/qwen-tasks/REVIEW/TASK-340-...md        (156 lines, result block)
D  docs/qwen-tasks/TODO/TASK-340-...md           (81 lines, moved to REVIEW)
M  src/llm.py                                    (+37/-6, cache param + batch)
A  src/providers/anthropic.py                    (517 lines, new adapter)
M  src/providers/glm.py                          (+13/-1, cache param)
M  tests/test_invariants.py                      (+7/-2, POST allowlist)
A  tests/test_the_cohort_preamble_is_paid_for_once.py  (485 lines, 15 tests)
```

No files deleted except the TODO task file (moved to REVIEW). No production code removed. No scope drift outside TASK-340's named files.

---

## Finding 1: Artifacts exist on the ref ✅

| Artifact | Status | Evidence |
|----------|--------|----------|
| `src/providers/anthropic.py` | EXISTS, 517 lines | `git diff --diff-filter=A` |
| `src/providers/glm.py` cache param | EXISTS | `glm.py:299` sets `chat_template_kwargs.enable_cache` |
| `src/llm.py` cache + batch | EXISTS | `llm.py:311` cache_control, `llm.py:386` complete_batch method, `llm.py:401` module-level |
| `tests/test_the_cohort_preamble_is_paid_for_once.py` | EXISTS, 15 tests | All 15 pass in 0.094s |
| `tests/test_invariants.py` allowlist | MODIFIED | "anthropic" added to POST allowlist at line 293 |

---

## Finding 2: ZERO production callers — DISCONNECTED ❌

This is the recurring defect. The standing rule: **"Zero production callers means DISCONNECTED, which is a rework and not a merge."**

### What I checked

```
grep -rn "complete_batch\|cache=True\|anthropic\.complete" src/ --include="*.py"
```

Result: every hit is inside the definition site (`anthropic.py`, `glm.py`, `llm.py`). Zero callers in `src/generate.py`, `src/replies.py`, `src/enrich.py`, or any other production module.

```
grep -rn "from.*anthropic\|import.*anthropic" src/ --include="*.py"
```

Result: empty. No file in `src/` imports the anthropic module. The only references to "anthropic" outside `anthropic.py` itself are:
- `src/llm.py:269` — a string check `"anthropic" in base` for provider routing (pre-existing)
- `src/providers/__init__.py:142` — key registration (pre-existing)
- `src/spendledger.py:152` — unit registration (pre-existing)

```
grep -rn "complete_batch\|\.complete(.*cache" src/generate.py src/replies.py src/enrich.py
```

Result: empty. The generation entry point does not use `complete_batch` and does not pass `cache=True`.

### The result block acknowledges this

> "The Anthropic adapter has no production caller yet. It is importable and tested, but `generate.py` does not route to it. Wiring it in is a separate task."

This is TASK-029 again: a good function with no caller. The task built the transport but did not wire it into the generation flow. The cost levers exist but no production path uses them.

### Falsification

Break the wiring test: remove `anthropic.complete` from `anthropic.py`. The 15 tests still pass because they import `anthropic` directly. No production test fails because no production code calls it. The tests prove the adapter works in isolation; they do not prove it is connected.

---

## Finding 3: Ledger measurement OWED ❌

Acceptance criterion #3:

> "The before/after ledger measurement above, with real numbers pasted."

The result block:

> "The before/after ledger measurement is OWED. The task requires running a fixture cohort of 10 leads with and without caching, reading ledger rows, and reporting the delta. This requires live API calls against a real endpoint with a funded account."

This is not met. The task explicitly requires real cost numbers from the ledger, not a prediction. The result block defers this to Claude.

---

## Finding 4: Correctness test is vacuous ⚠️

`test_cached_and_uncached_produce_same_content` feeds the same `CANNED_RESPONSE` to both calls and asserts the output is identical. This proves nothing about whether caching changes the model's actual output. It would pass even if caching completely broke the output, because both calls return the same mock.

`test_cached_and_uncached_send_same_prompt` is better: it asserts the user message content is identical in both request bodies. This is a real assertion about the transport, not the model output.

The task's acceptance criterion #4 says: "the copy produced with caching on is equivalent to caching off for the same input." The test does not verify this against a real model.

---

## Finding 5: Tests are partially falsifiable ✅/⚠️

### What the tests do well

- Assert on request bodies, not flags ✅
- Verify `cache_control: {"type": "ephemeral"}` appears in the body when `cache=True` ✅
- Verify no `cache_control` when `cache=False` ✅
- Verify batch creates one request covering N items (2 requests: create + poll, not N+1) ✅
- Verify ledger rows are written ✅
- Use `_Recorder` transport injection — good pattern ✅

### What the tests do not prove

- That any production code uses the new APIs (because none does)
- That caching does not change model output (vacuous mock test)
- That the before/after cost delta is real (measurement owed)
- That the full suite passes (result block does not mention `work/suite_verdict.txt`)

---

## Finding 6: Merge safety ✅

- Only one file deleted: the TODO task file (moved to REVIEW). This is intentional.
- No production code removed.
- No blob hash collisions with master (checked `--diff-filter=D`).
- Branch carries only TASK-340 work in the diff.

---

## Finding 7: Scope drift ✅ clean

The diff contains only TASK-340 files:
- `src/providers/anthropic.py` (new)
- `src/providers/glm.py` (modified)
- `src/llm.py` (modified)
- `tests/test_the_cohort_preamble_is_paid_for_once.py` (new)
- `tests/test_invariants.py` (modified)
- Task file moved from TODO to REVIEW

No unrelated changes. No scratch files. No accidental edits.

---

## Finding 8: OpenAI-compatible batch is not a batch ⚠️

`OpenAICompatibleModel.complete_batch()` loops and calls `self.complete()` for each prompt. The module-level `llm.complete_batch()` delegates to this. For the OpenAI-compatible path (GLM, xAI), there is no actual batching — it is sequential calls.

The result block acknowledges this. The Anthropic adapter's `complete_batch()` uses `/v1/messages/batches` for true batching.

This is not a defect — the OpenAI-compatible API has no standard batch endpoint — but it means the "batch entry point" claim only holds for Anthropic.

---

## Disposition

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | Artifacts exist on the ref | — | ✅ VERIFIED |
| 2 | Zero production callers | P0 | ❌ DISCONNECTED — rework required |
| 3 | Ledger measurement owed | P1 | ❌ NOT MET — acceptance criterion #3 |
| 4 | Correctness test vacuous | P2 | ⚠️ PARTIALLY MET — transport verified, model output not |
| 5 | Tests partially falsifiable | — | ⚠️ BODY ASSERTIONS ✅, WIRING ❌, MEASUREMENT ❌ |
| 6 | Merge safety | — | ✅ SAFE |
| 7 | Scope drift | — | ✅ CLEAN |
| 8 | OpenAI batch is sequential | P3 | ⚠️ ACKNOWLEDGED — not a defect, a limitation |

---

## Recommendation: **REWORK**

Two blockers prevent merge:

1. **Zero production callers.** The Anthropic adapter, `complete_batch()`, and `cache=True` are built and tested but nothing in `src/` calls them. This is the exact recurring defect this repository has been bitten by (TASK-029, TASK-028, TASK-019 on 2026-09-14). The result block says "Wiring it in is a separate task" — but the standing rule says zero production callers means DISCONNECTED, which is a rework and not a merge. The task must either wire the adapter into `generate.py` or explicitly scope this out with a named follow-up task that Claude accepts.

2. **Ledger measurement owed.** Acceptance criterion #3 requires real before/after cost numbers from the ledger. The result block defers this to Claude. This is not met.

### What is good

- The Anthropic adapter is well-structured and follows the repository's patterns.
- The cache directive tests assert on request bodies, not flags.
- The batch test verifies one request covers N items.
- The ledger integration is in place.
- The code is safe to merge once the wiring and measurement are done.

### What is owed

1. Wire `anthropic.complete()` into `generate.py` or name the follow-up task.
2. Run the before/after cost measurement from Claude's worktree with a funded account.
3. Replace the vacuous correctness test with a real one, or acknowledge that model-output equivalence cannot be tested without a live model.
4. Run the full suite and report `work/suite_verdict.txt`.

---

**VERDICT: REWORK**

The transport is built and tested. The wiring is absent. The measurement is owed. The code is good; the connection is missing.
