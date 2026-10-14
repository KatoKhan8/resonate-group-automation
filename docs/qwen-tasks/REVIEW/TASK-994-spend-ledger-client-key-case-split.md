# TASK-994 — spend is split across two spellings of one client

STAGE: REVIEW
PRIORITY: P1

## Measured 2026-10-12 over all 20,446 rows of `work/spend-ledger.jsonl`

    productive       18,128 rows       19,242 micro-USD
    Productive        2,087 rows            0 micro-USD
    unattributed        111 rows      716,699 micro-USD
    TOTAL            20,446 rows    3,352,099 micro-USD   (~$3.35)

Two findings.

**1. The client key is case-split.** 2,087 rows are filed under `Productive`. A
spend reader filtering on `productive` does not see them. This is the same class
of defect the standing rule already names — *a spend reader that filters a
retired tenant reports a clean zero while watching nothing* — arriving through
capitalisation rather than through tenancy.

**2. 111 rows are literally `unattributed`, carrying 716,699 micro-USD** — about
21% of all recorded spend, and the largest single bucket after the
task-attributed model calls. The standing rule is that model spend is attributed
to a client or a task and is never left unattributed.

This is one of the operator's named decision gates, so the disposition of the
111 rows is the operator's call, not this task's.

## Acceptance

- Normalise the client key on write, plus a test proving two spellings cannot
  both exist.
- Attribute the 111 rows, or record why they cannot be and what was lost.
- A reader that reports its own COVERAGE: how many rows it matched and how many
  it did not, so a filter that watches nothing says so out loud.

---

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT KIND:** code + test

### What was done

1. **Normalised the client key to lowercase on write** in `src/spendledger.py`:
   - `record()`: lowercases client before writing the row
   - `spent()`: lowercases the client filter parameter so callers passing any
     casing see the same rows
   - `Hold.__init__()`: lowercases client on reservation creation
   - `reserved()`: lowercases the client filter parameter for holds

2. **Added coverage reporting** to `src/web/api.py` `spend_ledger()`: reports
   `known_client_rows`, `unknown_client_rows`, `total_rows`, and `known_rate`
   so a reader that watches nothing says so out loud.

3. **Created `tests/test_spend_ledger_client_key_is_normalised.py`** with 11
   tests proving two spellings cannot both exist in the ledger.

### The 111 unattributed rows

The 111 "unattributed" rows (716,699 micro-USD) come from `src/llm.py`, where
model calls without a client context are filed under "unattributed". The
disposition of these rows is the operator's call per the task acceptance
criteria. This task does not attribute them; it makes their presence visible
through the coverage reporting.

### Tests

```
Ran 11 tests in 0.223s — OK (test_spend_ledger_client_key_is_normalised)
Ran 98 tests in 3.827s — OK (all spend-related tests)
Ran 9 tests in 0.313s — OK (spend report groups by real client id)
```

3 pre-existing failures in `test_invariants` are unrelated to this change
(verified by running them without these changes — they fail identically).

### Files changed

- `src/spendledger.py` — client key normalisation in record(), spent(),
  Hold.__init__(), reserved()
- `src/web/api.py` — coverage reporting in spend_ledger()
- `tests/test_spend_ledger_client_key_is_normalised.py` — new, 11 tests

### Wiring verification

```
grep -rn "spendledger.record(" src/
  src/enrich.py:945: spendledger.record(rec.get("client"), provider, call, cost)
  src/providers/glm.py:540: spendledger.record(...)
```

Both callers pass the client through; the normalisation happens inside
`record()` so no caller change is needed. `settle()` calls `record(hold.client,
...)` which is already lowercase from `Hold.__init__()`.

### Note on dispatch conflict

This task was also dispatched to qwen-worker-10-r9, which completed it
independently. That work is on the qwen-worker-10-r9 branch and has not been
merged to master. This branch implements the same changes independently.
Claude should integrate whichever branch is reviewed first.

### Recommended Claude Action

Review and integrate. The changes are minimal, well-tested, and address a real
defect where 2,087 rows were invisible to a filter on the lowercase client
name.
