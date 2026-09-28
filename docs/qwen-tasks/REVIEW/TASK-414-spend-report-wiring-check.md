PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-414 — Spend Report Wiring Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `spend-report-wiring-check`.

Does the spend report read what the ledger's client-attribution work now
writes? Trace every consumer of spendledger that reports a number to a
human; confirm each groups by the now-real client ids correctly, not still
folding everything into "unattributed". Acceptance: run the report against
a fixture with mixed client-attributed and unattributed rows; confirm the
client total is correct, not folded in.

## RESULT

**STATUS:** DONE
**ARTIFACT KIND:** finding (verification task - no code changes needed)
**COMMIT SHA:** 81a69566
**TESTS:** 148 tests across 7 test modules, all green:
  - test_spend_report_groups_by_real_client_id (9 tests) - the direct acceptance test
  - test_ledger_does_not_sum_across_units (24 tests)
  - test_model_spend_counts_against_the_client (42 tests)
  - test_a_provider_ceiling_refuses_before_the_call (40 tests)
  - test_run (14 tests)
  - test_the_entrypoint_refuses_at_a_client_ceiling (10 tests)
  - test_every_s5_verification_reaches_the_spend_ledger (9 tests)

**FILES CHANGED:** none (verification only)

**FINDINGS:**

Every consumer of spendledger that reports a number to a human correctly
groups by the now-real client ids. Nothing folds client-attributed rows
into "unattributed".

Consumers traced:

1. `spendledger.report(client=...)` - filters by `row.get("client") != client`.
   Correctly separates clients. The existing test proves acme=350, globex=700,
   unattributed=500 from a mixed fixture, with no folding.

2. `spendledger.spent(client=...)` - same filter. Used by stage_s5_verify.py
   with an explicit CLIENT constant.

3. `spendledger.balances(client, ...)` - filters by `row.get("client") != client`.
   Per-provider breakdown stays within the named client.

4. `spendledger.client_balance(client, ...)` - delegates to `spent(client, ...)`.

5. `spendledger.progress_block(client, ...)` - delegates to balances() and
   client_balance().

6. `web/api.py spend_ledger(recs)` - groups by `rec.get("client") or "unknown"`.
   Records with no client land under "unknown", not under a real client.
   Proven by test: acme=300, globex=300, unknown=50 from a mixed fixture.

7. `src/web/pages.py` - renders costs["total_credits"] and costs["by_call"]
   from the API. Does not render by_client in the admin view, but the data
   is correctly separated in the API response.

8. `scripts/pack_fetch.py` - filters by provider (apify) only, not a client
   report. Computes an Apify cost rate across all rows.

9. `scripts/glm_verify_branch.py` - looks for `client == "_model"`, which is
   STALE after TASK-346 moved model spend to the calling client. This is a
   branch verification script, not a spend report consumer, but worth noting:
   it will find zero rows on current ledgers.

**RISKS:** None. The wiring is correct and the tests prove it.

**RECOMMENDED CLAUDE ACTION:** Accept. No code changes needed - the
client-attribution work (TASK-346) is fully honoured by every report consumer.
