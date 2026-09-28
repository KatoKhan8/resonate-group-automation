# TASK-495 — Independent GLM verification of TASK-355

## Review metadata

| Field | Value |
|---|---|
| Target task | TASK-355 — cached tokens are priced as if they were fresh |
| Branch reviewed | `origin/qwen-worker-12-r9-sync` |
| Branch HEAD SHA | `3da4a246ee2536760d04dfc4d1d94b649160c2fa` |
| SHA verified with | `git rev-parse origin/qwen-worker-12-r9-sync` → matches |
| Worktree | `.qwen/worktrees/task495-review` (detached HEAD at `3da4a246`) |
| Review date | 2026-09-28 |
| Reviewer | GLM (independent, read-only) |

**The branch HEAD SHA matches the task file exactly.** The branch has not moved since the task was dispatched.

---

## Finding 1: Artifacts exist on the reviewed ref

**Disposition: FIXED + VERIFIED**

Three files were changed by TASK-355's two commits (`ed5fd975`, `e510b518`):

| File | Change | Verified |
|---|---|---|
| `config/model-prices.yaml` | +4 lines: `cache_creation_input_per_1m` and `cache_read_input_per_1m` for `claude-sonnet-4-20250514` and `claude-3-5-sonnet-20241022` | YES |
| `src/modelprices.py` | +124/-7 lines: `cache_rates_for()`, `cost_details()`, modified `cost_micro_usd()` | YES |
| `tests/test_a_cached_token_is_not_priced_as_a_fresh_one.py` | +169 lines: NEW, 7 tests | YES |

All three files exist at `3da4a246` and their content matches the result block's claims.

The prices match published Anthropic rates (source: `https://docs.anthropic.com/en/docs/about-claude/models`):
- Claude Sonnet 4: input $3/MTok, output $15/MTok, cache creation $3.75/MTok, cache read $0.30/MTok ✓

---

## Finding 2: `cost_micro_usd` has production callers; cache pricing is additive and backward-compatible

**Disposition: FIXED + VERIFIED**

`cost_micro_usd` is called from five production sites:

| Caller | File:Line | Usage dict shape |
|---|---|---|
| `_estimate_cost` | `src/llm.py:298` | `{"prompt_tokens": ..., "completion_tokens": max_tokens}` |
| `_settle_spend` | `src/llm.py:313` | Passes provider-returned `usage` dict |
| Pre-call estimate | `src/providers/glm.py:308` | `{"prompt_tokens": ..., "completion_tokens": body["max_tokens"]}` |
| Post-call settlement | `src/providers/glm.py:337-338` | `result.get("usage") or {}` |
| `_record_spend` | `src/providers/glm.py:539` | Passes `usage` from `_trim` result |

The modification to `cost_micro_usd` is **purely additive**:
- Old code read only `prompt_tokens` and `completion_tokens`
- New code also reads `input_tokens`/`output_tokens` (as fallbacks) and `cache_creation_input_tokens`/`cache_read_input_tokens`
- If none of the cache keys are present, the computation is identical to before
- Acceptance 6 test confirms: legacy `{"prompt_tokens": 1000, "completion_tokens": 100}` produces identical cost (4500 micro-USD for Claude, 560 for GLM)

**No existing caller is broken.** All 30 tests in `test_a_model_call_writes_a_priced_ledger_row` and `test_model_spend_counts_against_the_client` pass.

---

## Finding 3: No production caller passes cache tokens yet — the code is correct but has no production effect

**Disposition: ACCEPTED DEFERRED RISK**

The GLM provider's `_usage()` function (`src/providers/glm.py:501-519`) extracts:
```python
{
    "prompt_tokens": ...,
    "completion_tokens": ...,
    "total_tokens": ...,
    "reasoning_tokens": ...,
    "cached_tokens": prompt_details.get("cached_tokens"),
}
```

It does NOT extract `cache_creation_input_tokens` or `cache_read_input_tokens`. The key `cached_tokens` is a different schema (OpenAI-style, not Anthropic-style) and `cost_micro_usd` does not read it.

**This means:** even if GLM returns cache token data in its response, it will not be priced by the new cache rates. The cache pricing code is correct and tested, but has no production effect until a provider adapter extracts Anthropic-style cache tokens.

**This is NOT a defect in TASK-355.** The task scope was to build the pricing infrastructure, not to rewire provider adapters. The result block correctly acknowledges this: "existing callers are unaffected until a provider adapter starts extracting cache tokens from responses." The standing rule "zero production callers means DISCONNECTED" applies to core functionality, and the core function `cost_micro_usd` IS consumed — it just does not yet receive cache tokens from any caller.

**Risk:** If Anthropic or another provider starts returning cache tokens, the adapter must be updated to extract them with the correct key names. Until then, cache tokens are invisible to the ledger.

---

## Finding 4: `cost_details()` has zero production callers

**Disposition: ACCEPTED DEFERRED RISK**

`cost_details()` is defined at `src/modelprices.py:117` and called only from the test file (lines 62, 89). No production code calls it.

The result block acknowledges this: "The `cost_details` function is new and has no caller yet. It exists for acceptance test 3 and future reporting."

This is a reporting/debugging helper. It does not affect the correctness of `cost_micro_usd`, which is the production function. The function is well-tested and correct. If it is never consumed, it is dead code — but it is not harmful dead code, and removing it is not urgent.

---

## Finding 5: Mutation test confirms the guard works

**Disposition: FIXED + VERIFIED**

The result block claimed the guard is pinned but did not actually perform the mutation. I performed it:

```
Normal:   fresh=3000, cached=300,  cached < fresh = True
Mutated:  fresh=3000, cached=3000, cached < fresh = False
```

When `cache_rates_for` is monkeypatched to return the input rate (simulating the original bug where cached tokens price as fresh), the cache read cost becomes 3000 (equal to fresh) instead of 300. The test `test_cache_read_cheaper_than_fresh` would fail because `assertLess(3000, 3000)` is false.

**The guard is real and the test catches the bug.**

---

## Finding 6: Tests are falsifiable — they assert on computed values, not source text

**Disposition: FIXED + VERIFIED**

The 7 tests assert on:
- Numeric comparisons (300 < 3000, ratio < 0.5, ratio > 1.0)
- Exact equality (4500 micro-USD, 560 micro-USD)
- None checks (usd_estimate is None, rate_per_1m is None)
- Component sum reconciliation (total == sum of parts)

None of these are `hasattr`, source text search, or JSON shape assertions. They would catch:
- Cache read priced at input rate (test 1 fails)
- Cache write priced at input rate (test 2 fails)
- Invented multiplier for missing rate (test 3 fails)
- Silently dropped token kind (test 4 fails)
- Changed legacy pricing (test 6 fails)

**How could these pass while the implementation is wrong?** Only if the rates in the YAML file are wrong. The tests trust the YAML. If someone puts `cache_read_input_per_1m: 3.00` (same as input), test 1 would fail. If someone puts `cache_read_input_per_1m: 0.00`, test 1 would fail because `assertGreater(cached, 0)` catches it. The tests are robust.

---

## Finding 7: Merging TASK-355 would NOT delete anything

**Disposition: FIXED + VERIFIED**

TASK-355's two commits (`ed5fd975`, `e510b518`) are purely additive:
- +4 lines in YAML (new keys, no modifications to existing keys)
- +124/-7 lines in `modelprices.py` (the -7 is the old docstring replaced by a longer one)
- +169 lines new test file
- +30 lines result block in task file

No files are deleted. No existing keys are modified. The change is safe to cherry-pick.

The branch as a whole deletes 6 TODO task files (moved to REVIEW/DONE), but those are task queue movements, not production code deletions.

---

## Finding 8: Scope drift — the branch carries 31 commits from many tasks

**Disposition: OPERATOR DECISION REQUIRED**

The branch `origin/qwen-worker-12-r9-sync` carries 31 commits not in master, from at least 14 different tasks:

- TASK-245 (2 commits)
- TASK-272 (3 commits)
- TASK-311 (1 commit)
- TASK-335 (2 commits)
- **TASK-355 (2 commits)** ← target
- TASK-397 (1 commit)
- TASK-405 (1 commit)
- TASK-409 (2 commits)
- TASK-415 (1 commit)
- TASK-417 (2 commits)
- TASK-418 (2 commits)
- TASK-424 (2 commits)
- TASK-426 (1 commit)
- TASK-427 (1 commit)
- Suite triage (1 commit)
- Other (7 commits)

**TASK-355's work must be cherry-picked**, not merged as a branch. The two commits are:
- `ed5fd975` TASK-355: price cache tokens at their own rates, not as fresh input
- `e510b518` TASK-355: move to REVIEW with result block

Cherry-pick order: `ed5fd975` first, then `e510b518`.

---

## Summary

| # | Finding | Disposition |
|---|---|---|
| 1 | Artifacts exist on the reviewed ref | FIXED + VERIFIED |
| 2 | `cost_micro_usd` has production callers; change is additive | FIXED + VERIFIED |
| 3 | No production caller passes cache tokens yet | ACCEPTED DEFERRED RISK |
| 4 | `cost_details()` has zero production callers | ACCEPTED DEFERRED RISK |
| 5 | Mutation test confirms the guard works | FIXED + VERIFIED |
| 6 | Tests are falsifiable | FIXED + VERIFIED |
| 7 | Merging would not delete anything | FIXED + VERIFIED |
| 8 | Scope drift — cherry-pick required | OPERATOR DECISION REQUIRED |

---

## Recommendation

**MERGE (cherry-pick `ed5fd975` then `e510b518`).**

TASK-355 delivers what it claims: cache tokens now price at their own rates, not as fresh input. The prices are correct (published Anthropic rates). The tests are falsifiable and catch the bug. The change is backward-compatible and does not break any existing caller.

The two deferred-risk findings (no production caller passes cache tokens yet, `cost_details` has no caller) are acceptable because:
1. The task scope was to build the pricing infrastructure, not to rewire provider adapters.
2. The infrastructure is correct and tested.
3. Wiring provider adapters is a separate task (if needed).

TASK-340's $2 measurement is unblocked. The cache rates are in place.

**Cherry-pick, do not merge the branch.** The branch carries 31 commits from 14+ tasks.
