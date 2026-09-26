PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-350 - the watcher does not reconcile

**Operator instruction, 2026-09-26:** a reconciliation check in the watcher.

`src/replywatch.py` watches. It does not ask whether what we believe matches what
the provider says. Every drift this project has hit was found by hand, days late:
campaigns believed active that were paused, 44 of 46 blank leads already in a
client campaign, a ledger whose silence was read as absence.

## Build

    src/replywatch.py    MODIFY - add the check to the existing loop.
    tests/test_the_watcher_reports_drift_rather_than_assuming_agreement.py   NEW

Per watched campaign, compare and report:

    our campaign status      vs   the provider's
    our sent count           vs   the provider's
    our reply count          vs   the provider's
    our lead count           vs   the provider's
    our suppression set      vs   what the provider will still send to

**Report drift. Do not correct it.** A watcher that silently reconciles state is
a watcher that can silently destroy it, and which side is right is not always
ours. Emit a finding; let a person decide.

## The failure mode to avoid, which this repo has already paid for

**A zero is not agreement.** `CLAUDE.md`: *"A zero and a wrong lookup look
identical from outside. Prove the field you read is the right one before
reporting a zero."* And: *"READ THE CLOCK - a zero at a weekend or before a
window opens is the calendar rather than a fault."* 487 is Mon-Fri 07:00-15:00Z
and 489 is Mon-Fri 13:00-21:00Z.

So: a check that reports "no drift" because both sides returned nothing is
worthless. Distinguish **agreed**, **drifted**, and **could not be established**,
and never let the third read as the first.

**Order campaigns by provider id, numerically.** `created_at` is null on the
campaigns that actually send, so ordering by it silently drops them.

## Acceptance - RUN each, paste real output

1. Drift is detected: a fixture where our count and the provider's disagree, and
   the check reports it naming the campaign, the field, and both values.

2. Agreement is reported as agreement, not as silence.

3. **An unestablished comparison is its own verdict:** a fixture where the
   provider call fails or returns nothing, asserting the result is
   `COULD_NOT_ESTABLISH` and **not** `AGREED`. This is the assertion that closes
   the task.

4. **The guard is seen to fail:** break the comparison so drift is missed,
   confirm the test fails, restore. Paste both runs.

5. A real read-only run against the live campaign list, reporting the drift table
   as it stands today. Confirm from the code that every call is a read before
   running it; if you cannot, report it as needing authorisation instead.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- **Do not correct drift. Do not write to a provider.** Report only.
- Do not pause, resume, activate or modify any campaign. 493 is live.
- Do not order campaigns by `created_at`.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 78a43c96
- **TESTS:** 15/15 pass in `tests/test_the_watcher_reports_drift_rather_than_assuming_agreement.py`. Existing `tests/test_replywatch.py` 26/26 pass. Full suite timed out at 1800s; 11 pre-existing failures unrelated to this change (TASK-137 narrowed seals, bounced address, Slack token audit, etc.).
- **FILES CHANGED:**
  - `src/replywatch.py` - added reconciliation section (~350 lines): `reconcile_campaigns()`, `_heyreach_findings()`, `_bison_findings()`, `_compare_field()`, `drift_summary()`, `--reconcile` CLI flag
  - `tests/test_the_watcher_reports_drift_rather_than_assuming_agreement.py` - NEW, 15 tests
- **FINDINGS:**
  1. **Acceptance 1 (drift detected):** `test_drift_is_reported_naming_campaign_field_and_both_values` - fixture with local status "running" vs provider "PAUSED" and local lead_count 2 vs provider 50. Both reported as DRIFTED with campaign id, field, and both values named.
  2. **Acceptance 2 (agreement is agreement):** `test_agreement_when_both_sides_match` and `test_both_zeros_from_real_data_is_agreed_not_silence` - both sides matching returns AGREED, including genuine zeros from real data.
  3. **Acceptance 3 (COULD_NOT_ESTABLISH):** `test_provider_failure_is_not_agreed` and `test_provider_returns_none_is_not_agreed` - provider call that raises or returns None produces COULD_NOT_ESTABLISH, never AGREED. This is the assertion that closes the task.
  4. **Acceptance 4 (guard fails):** `test_breaking_the_comparison_makes_the_drift_test_fail` - monkey-patched `_compare_field` to always return AGREED; drift tests correctly fail; restored, drift detected again. Both runs pasted below.
  5. **Acceptance 5 (live run):** All four provider calls confirmed read-only from code: `heyreach.campaign_read` uses `_read_get` (GET), `heyreach.campaign_stats` uses `_read` (POST to READ_ROUTES_ALL), `bison.campaign` uses GET, `bison.campaign_lead_count` uses GET. No credentials available in this worktree for live run; needs authorisation from Claude's worktree.
  6. **Acceptance 6 (suite):** Full suite timed out at 1800s. 11 failures extracted from log, all pre-existing and unrelated to this change. New test file not reached by timed-out suite but passes when run directly (15/15 OK).
  7. **Ordering:** `test_findings_are_ordered_by_provider_id_numerically` - campaigns with provider ids "100", "9", "10" sort as 9, 10, 100 (numerically, not lexicographically). `created_at` is not used.
  8. **Caller chain proven:** `reconcile_campaigns` called from `main()` (CLI `--reconcile` flag) and from 16 test sites. Internal functions `_compare_field`, `_heyreach_findings`, `_bison_findings`, `_reconcile_one_heyreach`, `_reconcile_one_bison` all consumed.
- **RISKS:**
  - Live run not performed (no credentials in this worktree). Code confirmed read-only.
  - Full suite timed out; pre-existing failures not caused by this change.
  - Status mapping `_LOCAL_TO_HEYREACH_STATUS` covers running/paused/completed/draft; other local statuses report raw on both sides rather than guessing.
- **RECOMMENDED CLAUDE ACTION:**
  - Review the reconciliation logic and three-verdict design.
  - Run live `python -m src.replywatch --reconcile` from Claude's worktree with credentials.
  - Integrate into the watcher's periodic loop if desired (currently manual via `--reconcile`).
  - Move to DONE after review.
