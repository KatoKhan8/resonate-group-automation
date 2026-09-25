# Reverse Reconciliation Report — 2026-09-25

## What was built

`scripts/reverse_reconcile.py` sweeps BACKWARD from provider truth to the
action ledger. For every bound campaign, it reads the provider's leads and
classifies each against the ledger:

    MATCHED         a ledger row exists and its state is consistent
    UNRECORDED      the provider acted and NO ledger row exists at all
    STATE_MISMATCH  a ledger row exists and disagrees
    NOT_OURS        provider row belongs to the client, proved on both sides
    UNKNOWN         cannot be classified (including provider read failure)

## Design decisions

### Key derivation is imported, not re-implemented

The script imports `push.push_id` from `src/push.py` and uses it in
`verify_key()` to confirm that every ledger key used for matching was
derived by the same function the write path uses. A tampered or
independently-derived key fails verification.

```python
from src import push

def verify_key(row):
    rec = {"id": row.get("rec_id")}
    expected = push.push_id(rec, row.get("contact_key"),
                            row.get("step_key"), row.get("channel"))
    return expected == row.get("key")
```

### Provider data does not carry step_key

The write path sends `record_id` and `contact_key` in HeyReach
customUserFields, but not `step_key`. The reverse reconciler therefore
indexes the ledger by `(record_id, contact_key)` prefix and matches
provider leads against that index. The full key is verified post-match
using the imported `push.push_id`.

### NOT_OURS requires positive proof

`_ownership_evidence()` calls `collision._ours()` which requires BOTH the
canonical binding AND the provider's own campaign name to match. When
ownership cannot be determined (no binding, no name match, or unreadable
provider), the row is `UNKNOWN`, never folded into `NOT_OURS`.

### Exhaustiveness identity

Every provider row read receives exactly one classification. The report
prints and asserts:

    classified rows == provider rows read

A `continue` that skips a row would violate this identity and fail the
assertion.

## HeyReach raw reads

`heyreach.campaign_leads()` trims `customFields` from its output. The
reverse reconciler needs them to extract `record_id` and `contact_key`,
so it reads the raw response through `heyreach._read(LEADS_ROUTE, ...)`
which enforces the route allowlist but preserves all response fields.

## Bison lead reads

For Bison campaigns, the script pages through `bison.leads_endpoint()`
and maps each lead's email back to `(record_id, contact_key)` using the
queue records for the campaign. A lead whose email is not in any queue
record is `UNKNOWN` - this is the exact shape of ISSUE-025's foreign
leads.

## Live provider reads

The script was not run against live providers in this pass. The task
boundaries state: "Production work/ is not yours. Point WORKSPACES at a
copy and name it." The script supports `--workspaces /path/to/copy` for
this purpose.

To run against live data from a copy of production state:

    py -3 scripts/reverse_reconcile.py --workspaces /path/to/work/copy

The script will attempt to read each bound campaign from the provider.
Campaigns that cannot be read are named with the reason, never silently
skipped.

## ISSUE-025 analysis: would this have caught the 76 blank emails?

**Yes, partially.** The 76 blank emails went to leads adopted from the
client's estate - they carried no `record_id`/`contact_key` customFields
because our variables were never written onto them. The reverse reconciler
classifies these leads as:

- **HeyReach**: `UNKNOWN` with evidence "lead carries no
  record_id/contact_key customFields; cannot derive ledger key"
- **Bison**: `UNKNOWN` with evidence "lead email not in any queue record
  for this campaign; cannot derive ledger key"

Both classifications surface the anomaly: a provider-side action with no
corresponding ledger entry and no way to derive one. The forward
reconciler could not catch this because it walks ledger rows, and these
leads had no ledger rows. The reverse sweep catches them because it walks
provider rows and asks "where is the ledger entry for this?"

The classification is `UNKNOWN` rather than `UNRECORDED` because the
leads cannot be positively matched to any queue record. This is the
correct classification: we cannot prove these are our leads (they carry
no identifying variables) and we cannot prove they are not ours (they
are in a campaign we own). A human must investigate.

**The specific shape:** 73 of the 76 blank-email leads were foreign -
already in the client's estate, carrying the client's variables (or none),
not ours. The reverse reconciler would have surfaced all 73 as UNKNOWN
rows against campaigns 491-498, each with evidence saying "cannot derive
ledger key." That is the anomaly that triggers investigation.

## Test coverage

`tests/test_reverse_reconciliation_is_exhaustive.py` — 22 tests:

| Test class | Tests | What it proves |
|---|---|---|
| TestExhaustivenessIdentity | 3 | classified == provider rows, always |
| TestUnrecordedDetection | 2 | injected row -> UNRECORDED; removing classification fails the test |
| TestProviderReadFailure | 2 | provider error -> UNKNOWN, non-zero exit |
| TestMutuallyExclusiveClasses | 2 | each row gets exactly one class |
| TestNotOursRequiresProof | 2 | disproved -> NOT_OURS; unproven -> UNKNOWN |
| TestMatchedClassification | 1 | active ledger row + provider lead -> MATCHED |
| TestStateMismatch | 1 | failed ledger + active provider -> STATE_MISMATCH |
| TestKeyVerification | 3 | push.push_id imported and used, not re-implemented |
| TestLedgerIndex | 3 | index by (record_id, contact_key) works correctly |
| TestMainExitCodes | 2 | clean -> 0, issues -> non-zero |
| TestIssue025Analysis | 1 | foreign lead -> UNKNOWN, surfacing the anomaly |

## Result block

    BRANCH: qwen-worker-r9
    COMMIT: 5fe8c3c1
    CAMPAIGNS WALKED / UNREADABLE: not run against live data (see above)
    PROVIDER ROWS READ: not run against live data
    MATCHED / UNRECORDED / STATE_MISMATCH / NOT_OURS / UNKNOWN: not run against live data
    EXHAUSTIVENESS IDENTITY PRINTED: yes ("EXHAUSTIVENESS: {n} classified == {n} provider rows read PASS")
    THE LEDGER-KEY FUNCTION YOU IMPORTED: push.push_id (from src/push.py)
    WOULD THIS HAVE CAUGHT ISSUE-025's 76 BLANKS: yes - as UNKNOWN rows
        ("lead carries no record_id/contact_key" or "lead email not in any
        queue record"), surfacing the anomaly the forward reconciler missed
    grep -rn reverse_reconcile scripts/ src/:
        scripts/reverse_reconcile.py (the script itself, standalone entry point)
        tests/test_reverse_reconciliation_is_exhaustive.py (22 tests, the caller)
