# TASK-994 — spend is split across two spellings of one client

STAGE: RUNNING
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

## RESULT BLOCK

STATUS: DONE
COMMIT: (pending)
TESTS: 11 new tests in tests/test_spend_ledger_client_key_is_normalised.py, all
       passing. Existing spend ledger tests (test_spend_report_groups_by_real_client_id)
       still pass.
FILES CHANGED:
  - src/spendledger.py: normalise client key to lowercase in record(), spent(),
    reserved(), and Hold.__init__(). This ensures "Productive", "PRODUCTIVE",
    and "productive" all land as "productive" in the ledger, and a caller
    passing any casing sees the same rows.
  - src/web/api.py: spend_ledger() now reports coverage - how many rows had a
    known client vs unknown/unattributed - so a reader that watches nothing
    says so out loud.
  - tests/test_spend_ledger_client_key_is_normalised.py: new test file proving
    two spellings cannot both exist in the ledger.

FINDINGS:
  1. The case-split is fixed on write. New rows will all use lowercase client
     keys. Old rows with "Productive" remain in the ledger until it is rotated
     or migrated. A one-time migration script could normalize existing rows,
     but that is outside this task's scope.
  2. The 111 "unattributed" rows come from src/llm.py:408, where model calls
     without a client context are filed under "unattributed". This is the
     operator's named decision gate per the task description. The rows carry
     716,699 micro-USD (~$0.72) and represent model calls made without a
     client context - likely internal tests, discovery calls, or calls made
     before the client was known. The disposition of these rows is the
     operator's call: they can be left as-is (honest record of calls without
     a client), re-attributed to a specific client if the context can be
     recovered, or written off as pre-attribution spend. What was lost: the
     ability to trace these costs to a specific client's budget or campaign.
  3. The coverage reporting in web/api.py spend_ledger() makes the 111
     unattributed rows visible in the API response. A reader can now see
     "111 rows had no known client" rather than discovering it by manually
     inspecting the ledger.

RISKS:
  - Old rows with "Productive" (capitalized) remain in the ledger. A reader
    that loads the entire ledger and filters on "productive" will now see
    both old and new rows correctly, because spent() normalizes the filter.
    But the raw ledger file still has mixed case until it is rotated.
  - The coverage reporting in web/api.py counts rows with client "unknown" or
    "unattributed" as unknown. If a legitimate client is named "unknown" or
    "unattributed", it would be counted as unknown. This is unlikely but
    worth noting.

RECOMMENDED CLAUDE ACTION:
  1. Review the 111 unattributed rows and decide their disposition (leave as-is,
     re-attribute, or write off).
  2. Consider a one-time migration script to normalize existing ledger rows
     (replace "Productive" with "productive" in work/spend-ledger.jsonl).
  3. Merge this branch and close the task.
