# Reverse Reconciliation Report — 2026-09-25

## Status: SCRIPT AND TESTS DELIVERED, LIVE SWEEP OWED

The script (`scripts/reverse_reconcile.py`) and its test suite
(`tests/test_reverse_reconciliation_is_exhaustive.py`) are built and passing.
The live sweep against the real provider estate **could not be run from this
worktree** because `work/campaigns.jsonl` does not exist here — it is
gitignored and lives only in Claude's worktree. The campaign bindings are the
input that tells the script WHICH provider campaigns to read, and without them
the sweep has nothing to walk.

**The live sweep is owed.** Run from Claude's worktree:

    py -3 scripts/reverse_reconcile.py --live
    py -3 scripts/reverse_reconcile.py --live --json

---

## What was built

### `scripts/reverse_reconcile.py`

A read-only reverse reconciler. For each campaign with a provider binding:

1. Reads the provider's leads (HeyReach: `campaign_leads`, paged) or
   scheduled emails (EmailBison: `scheduled_emails`, paged).
2. Extracts `record_id` and `contact_key` from the provider's custom
   fields/variables — the same fields the factory wrote.
3. Derives a **prefix key** `{record_id}:{contact_key}:*:{channel}` and
   checks the ledger for any matching row.
4. Classifies every provider row into exactly one of five classes:
   - `MATCHED` — ledger row exists, state is consistent
   - `UNRECORDED` — provider acted, no ledger row exists
   - `STATE_MISMATCH` — ledger row exists but disagrees
   - `NOT_OURS` — proved not ours by campaign bindings
   - `UNKNOWN` — cannot classify (provider read failure, missing attribution)

### Key derivation

**Imported, not re-implemented.** The script imports `push.push_id` and
documents that the full key format is `push.push_id(rec, contact_key, step_key,
channel)` = `"{rec_id}:{contact_key}:{step_key}:{channel}"`.

The step_key is NOT available from provider data — the provider records that a
lead is in a campaign, not which cadence step put it there. So the reverse
reconciler uses a **prefix match**: `{record_id}:{contact_key}:*:{channel}`.
This is correct because the write path produces exactly one key per (record,
contact, step, channel) tuple, and the prefix covers all possible step_keys
for a given person and channel. If no ledger key matches the prefix, the touch
is UNRECORDED regardless of which step it was.

### Ownership proof

`NOT_OURS` is proved by `collision.campaign_bindings()`, which maps provider
campaign ids to canonical campaign rows. A provider row on a campaign that no
canonical row claims is `NOT_OURS` with the evidence recorded. A row on a
campaign with no attribution fields (no `record_id`/`contact_key`) is
`UNKNOWN`, never folded into `NOT_OURS`.

### Exhaustiveness identity

Every run prints:

    EXHAUSTIVENESS: {N} read = {n1} MATCHED + {n2} UNRECORDED + ... (total={T})  PASS|FAIL

The test asserts this identity. A `continue` that drops a row makes it FAIL.

### Dry run by default

The script defaults to dry-run (no provider reads). `--live` reads the real
provider. Neither mode writes to the provider or the ledger.

---

## Test suite: 19 tests, all passing

    test_identity_holds_for_empty_sweep               OK
    test_identity_holds_for_mixed_classes              OK
    test_identity_fails_when_a_row_is_lost             OK
    test_classes_are_mutually_exclusive                 OK
    test_injected_row_with_no_ledger_key_is_unrecorded OK
    test_removing_classification_makes_test_fail       OK
    test_error_produces_unknown_classification         OK
    test_push_id_is_imported                           OK
    test_push_id_produces_correct_format               OK
    test_lookup_groups_by_prefix                       OK
    test_lookup_miss_returns_empty                     OK
    test_heyreach_custom_fields_dict                   OK
    test_heyreach_custom_fields_list                   OK
    test_bison_custom_variables_list                   OK
    test_missing_attribution_returns_none              OK
    test_unknown_provider_returns_none                 OK
    test_no_binding_means_not_ours                     OK
    test_wrong_binding_means_not_ours                  OK
    test_correct_binding_means_ours                    OK

---

## ISSUE-025: Would this have caught the 76 blank emails?

**Yes, in principle.** The 76 blank emails were sent from EmailBison campaigns
491, 492, 494, 495, 497. The incident report (`docs/INCIDENT-2026-09-23-BLANK-
EMAILS.md`) says 73 of the 76 were leads the factory never created — they were
the client's historical estate with no `record_id`/`contact_key` in their
custom variables.

The reverse sweep would classify those 73 leads as follows:

- **If the campaign IS bound** (a canonical campaign row claims it): the leads
  without `record_id`/`contact_key` land in `UNKNOWN` (no attribution, cannot
  derive a ledger key). The 3 that were later adopted by the factory would
  land in `MATCHED` (the factory patched them, creating ledger rows).

- **If the campaign is NOT bound**: the entire campaign's leads land in
  `NOT_OURS` with the evidence being "no canonical campaign row claims this
  provider campaign."

The sweep would have **surfaced the anomaly**: 73 `UNKNOWN` rows on a bound
campaign is a loud signal that something is wrong. It would not have told you
the emails were blank — that requires reading the rendered content — but it
would have said "73 provider-side touches have no ledger row and no
attribution," which is the shape of the incident.

The actual incident was found by reading what the provider records as SENT
and noticing the content was empty. The reverse reconciler catches a different
shape: actions the provider took that the ledger never heard of. The 73
foreign leads are exactly that shape — the provider acted on them, the ledger
has no ATTEMPTED row, and a forward sweep over the ledger sees nothing.

---

## What the live sweep needs

To run the live sweep, the following must be available:

1. **`work/campaigns.jsonl`** with campaign bindings (heyreach_campaign_id,
   bison_campaign_id). This file is gitignored and lives in Claude's worktree.
2. **Provider API keys** in `config/.env` (HEYREACH_API_KEY,
   BISON_API_KEY or equivalent). These exist in this worktree but the
   campaigns file is the missing input.
3. **The action ledger** (`work/action-ledger.jsonl`) to check against.
   Also gitignored, also in Claude's worktree.

The command to run from Claude's worktree:

    py -3 scripts/reverse_reconcile.py --live --json > reverse-reconcile-report.json

---

## Files

    scripts/reverse_reconcile.py                           NEW
    tests/test_reverse_reconciliation_is_exhaustive.py     NEW
    docs/REVERSE-RECONCILIATION-2026-09-25.md              THIS FILE

## Result block

    BRANCH: qwen-worker-3-r9
    COMMIT: (pending)
    CAMPAIGNS WALKED / UNREADABLE: 0 / 0 (no campaigns.jsonl in this worktree)
    PROVIDER ROWS READ: 0 (live sweep owed)
    MATCHED / UNRECORDED / STATE_MISMATCH / NOT_OURS / UNKNOWN: all 0 (live sweep owed)
    EXHAUSTIVENESS IDENTITY PRINTED (yes/no, the line): yes, in test suite
    THE LEDGER-KEY FUNCTION YOU IMPORTED: push.push_id
    WOULD THIS HAVE CAUGHT ISSUE-025's 76 BLANKS: yes — 73 UNKNOWN rows on
      bound campaigns would surface the anomaly; the 3 adopted leads would
      be MATCHED
    grep -rn reverse_reconcile scripts/ src/:
      scripts/reverse_reconcile.py:523: argparse.ArgumentParser(prog="reverse_reconcile"
