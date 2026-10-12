# TASK-994 — spend is split across two spellings of one client

STAGE: QUEUED
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
