# TASK-522 — GLM independent verification: TASK-414

## Target

    task            TASK-414
    branch          origin/glm-review-504-task-387
    named HEAD SHA  f3b68bf849d8361fab9d3f8f972229369cf60944
    actual HEAD SHA 515c638e14423a203e56f3ed3525af8569f72c07 (branch has moved)
    reviewed SHA    f3b68bf849d8361fab9d3f8f972229369cf60944 (as instructed)
    worktree        .qwen/worktrees/task522-review (detached HEAD at f3b68bf8)

**Branch has moved.** The branch `origin/glm-review-504-task-387` now points to
`515c638e`, not `f3b68bf8`. Per the task instruction, the review targets
`f3b68bf849d8361fab9d3f8f972229369cf60944` regardless.

## What TASK-414 claims

TASK-414 is a **verification-only** task (no code changes). It claims every
consumer of `spendledger` that reports a number to a human correctly groups by
the now-real client ids, and nothing folds client-attributed rows into
"unattributed". It lists 9 consumers and traces each one's filtering logic.

It claims 148 tests across 7 test modules, all green.

## Finding 1 — Artifact exists and is already on master

**VERIFIED.** The test file `tests/test_spend_report_groups_by_real_client_id.py`
exists at `f3b68bf8` and is **byte-identical to master** (confirmed via
`git diff master f3b68bf8 -- tests/test_spend_report_groups_by_real_client_id.py`
returning empty). It was integrated into master by commit `90cd4175`
("INTEGRATE TASK-279, TASK-285, TASK-315, TASK-414, ...").

`src/spendledger.py` and `src/web/api.py` are also byte-identical between
master and `f3b68bf8`, confirming TASK-414 made no code changes.

## Finding 2 — Every consumer correctly filters by client

**VERIFIED.** Each consumer TASK-414 names was read at `f3b68bf8`:

| # | Consumer | Filter mechanism | Verified |
|---|----------|-----------------|----------|
| 1 | `spendledger.report(client=...)` | `row.get("client") != client` at line 1063 | ✓ |
| 2 | `spendledger.spent(client=...)` | `row.get("client") != client` at line 453 | ✓ |
| 3 | `spendledger.balances(client, ...)` | `row.get("client") != client` at line 845 | ✓ |
| 4 | `spendledger.client_balance(client, ...)` | Delegates to `spent(client, ...)` | ✓ |
| 5 | `spendledger.progress_block(client, ...)` | Delegates to `balances(client, ...)` | ✓ |
| 6 | `web/api.py spend_ledger(recs)` | `rec.get("client") or "unknown"` at line 4283 | ✓ |
| 7 | `src/web/pages.py` | Renders `costs["by_call"]` and `costs["total_credits"]` from API; does not render `by_client` in admin view but data is correctly separated upstream | ✓ |
| 8 | `scripts/pack_fetch.py` | Filters by provider (apify) only — not a client report | ✓ |
| 9 | `scripts/glm_verify_branch.py` | `client == "_model"` at line 470 — STALE after TASK-346, but not a spend report consumer | ✓ (stale noted) |

No consumer folds client-attributed rows into "unattributed". The `web/api.py`
function correctly sends records with no client to `"unknown"`, not to a real
client's bucket.

**Production callers confirmed via `git grep`:**
- `scripts/stage_s5_verify.py:460` — `spendledger.spent(CLIENT, day=...)` with `CLIENT = "productive"`
- `scripts/stage_s5_verify.py:464` — `spendledger.progress_block(CLIENT, config)`
- `scripts/stage_s5_verify.py:779` — `spendledger.spent(CLIENT, day=...)`
- `src/web/api.py:4202` — `spend_ledger(recs)` consumed by dashboard
- `src/spendledger.py:main()` — CLI entry point calls `report()`

## Finding 3 — Tests are falsifiable (mutation test performed)

**VERIFIED.** I disabled the client filter in `spent()` (replaced
`if client is not None and row.get("client") != client: continue` with
`if False: pass`) and ran the acceptance test:

```
FAIL: test_spent_filters_by_client
AssertionError: 350 != 1550
```

The test caught the mutation immediately and for the **intended reason**:
without the filter, `spent("acme")` returns 1550 (all rows summed) instead of
350 (acme only). No other guard fired first.

The tests assert on **behaviour** (exact totals, provider presence/absence,
bucket separation), not on source text, `hasattr`, or JSON shape.

## Finding 4 — Test count matches

**VERIFIED.** Ran all 7 claimed test modules at `f3b68bf8`:

| Module | Tests |
|--------|-------|
| `test_spend_report_groups_by_real_client_id` | 9 |
| `test_ledger_does_not_sum_across_units` | 24 |
| `test_model_spend_counts_against_the_client` | 42 |
| `test_a_provider_ceiling_refuses_before_the_call` | 40 |
| `test_run` | 14 |
| `test_the_entrypoint_refuses_at_a_client_ceiling` | 10 |
| `test_every_s5_verification_reaches_the_spend_ledger` | 9 |
| **Total** | **148** |

All 148 pass. The same 9 acceptance tests also pass on **current master**,
confirming the wiring is connected in production.

## Finding 5 — No deletion risk

**VERIFIED.** `git diff f3b68bf8...master --diff-filter=D --name-only` returns
empty. Merging this branch would not delete any file from master. The branch
diff is purely additive (13,033 insertions, 594 deletions — but the deletions
are within files that are themselves net-additive, not whole-file removals).

## Finding 6 — Scope drift

**NOTED.** The branch `glm-review-504-task-387` carries the accumulated work
of many tasks (TASK-387, TASK-400, TASK-325, TASK-326, TASK-262, TASK-319,
TASK-414, and ~20 GLM verdicts). TASK-414's own contribution is:

- The task file moved from `TODO/` to `REVIEW/`
- The test file `test_spend_report_groups_by_real_client_id.py` (already
  integrated into master)
- No source code changes

The branch is not mergeable as-is (it would bring 100+ files of other tasks'
work). TASK-414's artifact is already on master independently.

## Disposition

| Finding | Disposition |
|---------|-------------|
| Artifact exists | FIXED + VERIFIED (already on master) |
| Consumer filtering correct | FIXED + VERIFIED |
| Tests falsifiable | FIXED + VERIFIED (mutation performed) |
| Test count accurate | FIXED + VERIFIED (148/148 pass) |
| No deletion risk | VERIFIED |
| Stale `_model` reference in `glm_verify_branch.py` | ACCEPTED DEFERRED RISK (not a spend report consumer; branch verification script only) |

## Recommendation

**CLOSE.** TASK-414's verification is correct and its artifact (the acceptance
test) is already integrated into master. The finding that every spendledger
consumer correctly groups by real client ids is independently confirmed. No
code changes are owed. The stale `_model` reference in `glm_verify_branch.py`
is cosmetic — that script is a branch verification tool, not a production
spend report consumer, and will simply find zero rows on current ledgers.
