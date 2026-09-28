# TASK-458 — Independent verification of TASK-308

## Target

    task            TASK-308
    branch          qwen-worker-4-r9-task280
    branch HEAD SHA cdffd0a2d3bab2bea4d7a35373876fce93cc97fe
    reviewed at     cdffd0a2 (detached, verified with git rev-parse)
    date            2026-09-28

The branch HEAD SHA matches the task file's target. The branch has not moved.

## What TASK-308 claimed

An Anthropic (Claude Sonnet 5) adapter for prospect-facing copy:
- Direct to Anthropic API, not through OpenRouter
- Key read through `providers.model_key("anthropic")`
- Cost from response usage, priced from a recorded table
- Batch mode (submit, poll, collect) with partial result reporting
- Dollar-denominated spend ledger rows with explicit `unit` field
- 37 tests, all passing

## Findings

### Finding 1: DISCONNECTED — zero production callers [CRITICAL]

**Claim under challenge:** The result block says "write_copy_batch() is the pipeline function that unblocks TASK-306's writing step."

**What I measured:**

```
git grep -n "write_copy_batch\|record_spend\|cost_from_usage" <sha> -- src/
  | grep -v "src/providers/anthropic.py"
=> (empty)

git grep -n "from.*anthropic\|import.*anthropic" <sha> -- src/
  | grep -v "src/providers/anthropic.py"
=> (empty)
```

No code anywhere in `src/` outside `anthropic.py` itself imports or calls any function from it. The only reference in `src/` is the key mapping in `src/providers/__init__.py:142`. The result block itself admits: "write_copy_batch() is defined but has no production caller yet. TASK-306 is the integration point."

Per the standing rule (QWEN.md, "THE RULE THAT DECIDED THREE REVIEWS"): "Zero production callers means DISCONNECTED, which is a rework and not a merge."

The result block's caller chain section lists `record_spend` as "called by tests; production caller is TASK-306's pipeline" — this is an admission that the only caller is the test suite.

**Disposition: DISCONNECTED. The adapter is a correct module with no wire to production.**

### Finding 2: Unit scheme diverges from master [HIGH]

**Claim under challenge:** The task correction (added 2026-09-25) explicitly specified: "Anthropic's native unit is micro-dollars stored as an integer ($0.00256 -> 2560), unit: 'microusd'."

**What I measured:**

The branch writes `unit: "usd"` with `amount: 0.00256` (float). Master has since built a complete unit framework:

```python
# master:src/spendledger.py
LEDGER_UNITS = {"apify": "cents", "anthropic": "microusd", ...}
MICRO = 1_000_000
def to_micro_usd(usd): ...
```

Master expects `microusd` for Anthropic. The branch's `_append_row` bypasses master's `record(..., unit=)` seam entirely, writing through a parallel path with a different unit name and a float instead of an integer.

If this branch were merged as-is, Anthropic rows would carry `unit: "usd"` while master's `LEDGER_UNITS` says `"microusd"`, and `row_unit()` would read the row's own `unit` field ("usd") — which is not in `USD_PER_UNIT`, so `usd_estimate()` would return `None` with `rate_source: "unknown"`. Dollar spend from Anthropic would be unreportable.

**Disposition: The unit scheme is stale relative to master. Reconciliation needed.**

### Finding 3: _append_row is redundant with master's record() [MEDIUM]

**Claim under challenge:** The branch adds `_append_row()` to `spendledger.py` as a new helper.

**What I measured:** Master's `record()` already accepts `unit=None` as a parameter (line 320-321). The branch was written before this seam existed, and the task file warned about the concurrent edit. Master has since absorbed the unit seam the branch needed.

The `_append_row` function duplicates the lock/refuse-production-write logic that `record()` already provides. On master, `record(client, provider, call, 0, unit="microusd")` with `expected_cost` set to `to_micro_usd(cost_usd)` would achieve the same result through the canonical path.

**Disposition: Redundant with master. Would need to be replaced by a `record()` call using master's unit seam.**

### Finding 4: Tests pass and are internally falsifiable [POSITIVE]

**What I measured:**
- All 37 tests pass in 0.265s in an isolated worktree at the exact SHA.
- Mutation test: replacing `cost_from_usage` with a lambda returning -999.0 propagated through `complete()` — confirming the wiring is real, not decorative.
- Mutation test: replacing `_append_row` with a capturing fake confirmed `record_spend` calls it with correct fields (`unit: "usd"`, `amount: 0.00256`).
- `_headers()` source confirmed to call `model_key("anthropic")`, not `os.environ.get`.

**Limitations:**
- Tests replay hand-written cassettes. They verify the code's behavior given specific inputs but cannot verify the code works against the real Anthropic API. No live integration test exists.
- The cassette-based approach means a bug in the HTTP request construction (e.g., wrong content-type, missing header) would not be caught unless the test explicitly asserts on the request shape — and some tests do (endpoint, auth header), which is good.
- `write_copy_batch` is tested only indirectly through the batch sub-functions. No test exercises the full `write_copy_batch` -> `create_batch` -> `poll_batch` -> `get_batch_results` chain with the `copyprompts` integration.

**Disposition: Tests are meaningful for what they cover. They do not cover the production wiring because there is no production wiring to cover.**

### Finding 5: Scope drift — three tasks on one branch [MEDIUM]

**What I measured:** The branch carries 12 commits beyond master, spanning three tasks:

| Task  | Commits | Files                                                  | Lines |
|-------|---------|--------------------------------------------------------|-------|
| 308   | 2       | anthropic.py, test_anthropic.py, cassette, spendledger | 1142  |
| 315   | 2       | test_a_reply_stops_the_other_channel.py                | 1254  |
| 280   | 4       | reverse_reconcile.py, test_reverse_reconciliation...   | 1046  |
| meta  | 4       | task file moves, result blocks                         | ~260  |

Merging the whole branch would bring in TASK-280 and TASK-315 alongside TASK-308. Extracting just TASK-308 would require cherry-picking 3-4 files.

**Disposition: Branch carries work from two other tasks. Cherry-pick required for TASK-308 alone.**

### Finding 6: Merge would not delete master content [POSITIVE]

**What I measured:** `src/providers/anthropic.py` does not exist on master. `tests/test_anthropic.py` does not exist on master. The new files are purely additive. The `spendledger.py` diff adds `_append_row` (18 lines) which master does not have. The `test_invariants.py` diff adds "anthropic" to the POST allowlist.

Master has 451 files / 75,590 lines beyond this branch. None would be deleted by merging the branch's additions.

**Disposition: Safe from deletion. Conflict with master's evolved spendledger.py is the concern, not data loss.**

## Disposition

**REWORK.**

The adapter is well-built code. The tests are meaningful. The endpoint, auth, key loading, cost calculation and batch handling are all correct as far as offline testing can verify.

But the artifact is DISCONNECTED:
1. Zero production callers. `write_copy_batch()`, `record_spend()`, `complete()` — none is called from anywhere in `src/` outside the module itself. The result block admits this. The standing rule makes this a rework, not a merge.
2. The unit scheme (`usd` float) diverges from what master has since built (`microusd` integer). Merging as-is would produce unreportable spend.
3. `_append_row` duplicates master's `record(..., unit=)` seam.

**What rework looks like:**
- Wire `write_copy_batch()` into its production caller (TASK-306's pipeline, or whatever has since absorbed that work on master).
- Switch from `_append_row` + `unit: "usd"` to `record(..., unit="microusd")` with `expected_cost=to_micro_usd(cost_usd)`, using master's seam.
- Cherry-pick TASK-308 files alone, leaving TASK-280 and TASK-315 for their own reviews.

**RECOMMENDED CLAUDE ACTION:** REWORK. The adapter code is sound but must be wired into a production caller and reconciled with master's unit framework before merge.
