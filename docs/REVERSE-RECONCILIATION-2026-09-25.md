# Reverse Reconciliation Report

Generated: 2026-09-25
Key derivation: `push.push_id` (imported from `src.push`)

## Status

**This report documents the implementation and test results. A live provider
sweep could not be run from this worktree because `work/campaigns.jsonl` does
not exist here (QWEN.md: 7 of 8 worktrees have no `work/queue.jsonl`). The
script is structurally correct, tested, and ready to run from Claude's
worktree where production state lives.**

## What Was Built

`scripts/reverse_reconcile.py` - a script that sweeps BACKWARD from provider
truth to the ledger, the inverse of `reconcile_ledger.py`.

### Classification Logic

For each bound campaign, the script:

1. Reads the provider's leads (HeyReach via `campaign_leads`, EmailBison via
   `membership` + `lead`)
2. Builds a contact index from the queue (LinkedIn URL -> (rec_id, contact_key)
   for HeyReach, email -> (rec_id, contact_key) for EmailBison)
3. For each provider lead, looks up matching ledger rows by (rec_id, contact_key)
4. Classifies each provider-side touch:

| Classification   | Meaning |
|------------------|---------|
| MATCHED          | A ledger row exists and its state is consistent |
| UNRECORDED       | The provider acted and NO ledger row exists at all |
| STATE_MISMATCH   | A ledger row exists and disagrees with provider state |
| NOT_OURS         | Provider row is provably not from this system |
| UNKNOWN          | Cannot be classified (never folded into NOT_OURS) |

### Key Derivation

The script imports `push.push_id` from `src.push` and does NOT reimplement it:

```python
from src import push  # the key derivation, imported not rebuilt
# ...
dk = push.push_id(rec, ckey, step_key, "linkedin")  # or "email"
```

`push.push_id` returns `f"{rec['id']}:{contact_key}:{step_key}:{channel}"`.

### Ownership Evidence

NOT_OURS must be proved, not assumed. The script uses `collision.campaign_bindings()`
to determine which provider campaigns are claimed by canonical rows, and
`collision._ours` logic (the provider's own campaign name must carry the binding
suffix `[client/campaign_id]`).

A row that cannot be classified is UNKNOWN, and UNKNOWN is an outcome, never
folded into NOT_OURS.

### Exhaustiveness Identity

The script prints and verifies:

    EXHAUSTIVENESS: <classified> classified + <unknown> unknown = <total> total
    (provider rows read: <total>)

This is an assertion in the test suite: `classified + UNKNOWN == provider rows
read`. A `continue` that loses a row breaks the identity.

## Test Results

25 tests in `tests/test_reverse_reconciliation_is_exhaustive.py`, all passing:

    test_attempted_ledger_with_provider_present_is_matched ... ok
    test_attempted_ledger_without_provider_is_state_mismatch ... ok
    test_failed_ledger_with_provider_present_is_state_mismatch ... ok
    test_no_ledger_rows_is_unrecorded ... ok
    test_no_ledger_rows_no_provider_state_is_unrecorded ... ok
    test_sent_ledger_with_provider_lead_is_matched ... ok
    test_empty_hash ... ok
    test_hash_is_case_insensitive ... ok
    test_hash_is_deterministic ... ok
    test_hash_is_not_the_raw_value ... ok
    test_none_hash ... ok
    test_email_index ... ok
    test_linkedin_index ... ok
    test_multiple_contacts ... ok
    test_identity_holds_with_lost_row_simulation ... ok
    test_all_matched_holds_the_identity ... ok
    test_empty_sweep_holds_the_identity ... ok
    test_mixed_classifications_holds_the_identity ... ok
    test_push_id_is_called ... ok
    test_push_is_imported_in_reverse_reconcile ... ok
    test_filters_by_campaign ... ok
    test_groups_multiple_rows ... ok
    test_classify_returns_exactly_one_label ... ok
    test_heyreach_error_propagates ... ok
    test_sweep_returns_error_on_provider_failure ... ok

    Ran 25 tests in 0.057s - OK

### Key Test Properties

1. **Exhaustiveness identity**: `classified + UNKNOWN == provider rows read`.
   A `continue` that loses a row fails the identity.

2. **Injected provider row with no ledger key lands in UNRECORDED**:
   `test_no_ledger_rows_is_unrecorded` drives through `_classify_provider_lead`,
   the real entry point. Removing the classification call makes it fail.

3. **Provider read failure produces non-zero exit**:
   `test_sweep_returns_error_on_provider_failure` verifies that a provider
   exception propagates as an error string, and the script returns non-zero
   when errors are present.

4. **Key derivation is imported, not reimplemented**:
   `test_push_is_imported_in_reverse_reconcile` and `test_push_id_is_called`
   verify the import and call are present in the source.

## Live Sweep Results

**Not available from this worktree.** The script ran and produced:

    Campaigns walked: 0
    Campaigns with errors: 0
    Provider rows read: 0
    MATCHED: 0, UNRECORDED: 0, STATE_MISMATCH: 0, NOT_OURS: 0, UNKNOWN: 0

This is correct: there are no campaigns in this worktree's `work/campaigns.jsonl`
because the file does not exist here. The script is structurally correct but
cannot read live provider data without campaign bindings.

**To run the live sweep**: copy `work/campaigns.jsonl`, `work/queue.jsonl`, and
`work/action-ledger.jsonl` from Claude's worktree to a temp directory, then run:

    python scripts/reverse_reconcile.py --workspace /path/to/copy

Or run directly from Claude's worktree where production state lives.

## ISSUE-025 Analysis

The 76 blank emails (ISSUE-025) were sent from EmailBison campaigns 491-498.
These were leads that the provider had but the ledger had no ATTEMPTED row for -
the adoption path imported client leads directly.

**Would this sweep have caught it?** Yes, in principle. A reverse sweep over
campaigns 491-498 would classify those leads as UNRECORDED: the provider has
them, the ledger does not. This is exactly the shape the forward reconciler
cannot catch, because the forward reconciler starts from ledger rows and those
leads have none.

However, the live classification cannot be shown from this worktree because the
campaign bindings are not present. The report from a live run would list every
UNRECORDED row with hashed contact ids and the provider's own response fields
(campaign id, lead id, event type, timestamp).

## What Evidence Is Owed

To complete the live evidence requirement:

1. **Per-campaign counts** from a run against production campaign bindings
2. **At least one UNRECORDED row** with provider response fields quoted and
   the ledger query that returned nothing quoted beside it
3. **ISSUE-025 classification**: the actual rows from campaigns 491-498 and
   their classifications

This requires running the script from Claude's worktree or with a copy of
production state.

## Files

- `scripts/reverse_reconcile.py` - the reverse reconciler
- `tests/test_reverse_reconciliation_is_exhaustive.py` - 25 tests
- `docs/REVERSE-RECONCILIATION-2026-09-25.md` - this report

## grep -rn reverse_reconcile scripts/ src/

    scripts/reverse_reconcile.py:483:        prog="reverse_reconcile",

The script is a standalone entry point (like `reconcile_ledger.py`), invoked
directly rather than imported by other modules. The forward reconciler has the
same pattern: `grep -rn reconcile_ledger src/` returns nothing.
