# Spend ledger, reconciled in full — 2026-10-12

An earlier version of this table was a silent top-10 truncation presented as if
complete. It explained roughly 20,326 of 20,446 rows and 735,941 of 3,352,099
micro-USD. This is the whole ledger, and the rows and the amounts now sum.

Source: `work/spend-ledger.jsonl`. **20,446 rows parsed, 0 unparseable lines,
17 distinct client keys.** Cost field is `expected_cost`.

| client key | rows | micro-USD |
|---|---:|---:|
| `productive` | 18,128 | 19,242 |
| `Productive` | 2,087 | 0 |
| `unattributed` | 111 | 716,699 |
| `TASK-968` | 30 | 658,581 |
| `TASK-INTEGRATION` | 22 | 542,737 |
| `TASK-INTEG-V2` | 15 | 343,132 |
| `TASK-972` | 13 | 276,069 |
| `TASK-962` | 8 | 167,467 |
| `TASK-942` | 8 | 165,922 |
| `TASK-940` | 6 | 112,892 |
| `TASK-964` | 6 | 140,768 |
| `_model` | 4 | 35,864 |
| `TASK-1004` | 3 | 64,897 |
| `TASK-973` | 2 | 47,677 |
| `TASK-903` | 1 | 15,389 |
| `TASK-946` | 1 | 18,128 |
| `TASK-990` | 1 | 26,635 |
| **TOTAL** | **20,446** | **3,352,099** |

Rows reconcile: **true** (20,446 = 20,446). Cost reconciles: 3,352,099
micro-USD ≈ **$3.35** total recorded spend, all of it model spend.

`TASK-990` is this session's own adversarial-review call, attributed
deliberately.

## The three findings this table carries

**1. The client key is case-split.** 2,087 rows sit under `Productive` and
18,128 under `productive`. A reader filtering the lowercase key misses the
other 2,087 entirely. This is the same class of defect the standing rule
already names — *a spend reader that filters a retired tenant reports a clean
zero while watching nothing* — arriving through capitalisation rather than
tenancy. Tasked as TASK-994.

**2. 111 rows are literally `unattributed`, carrying 716,699 micro-USD** — 21%
of all recorded spend and the largest bucket after the task-attributed model
calls. The standing rule is that model spend is attributed to a client or a
task and never left unattributed. **This is one of the operator's named
decision gates**, so the disposition of those rows is theirs, not this
document's.

**3. The two biggest keys carry almost no cost, and the small keys carry
almost all of it.** `productive` has 18,128 rows for 19,242 micro-USD while
`TASK-968` has 30 rows for 658,581. The per-row costs differ by four orders of
magnitude, so **row counts are not a proxy for spend here** and any report that
ranks by row count will rank backwards. That is presumably provider-vs-model
calls sharing one ledger; worth knowing before reading any summary of it.

## Method, so it can be re-run

    py -3 -c "import json,collections,io; ..."

The full one-liner is in the session transcript; the material points are: parse
every line, count unparseable ones rather than skipping them silently, resolve
`client` when it is a dict, map a missing client to an explicit
`MISSING_CLIENT_FIELD` key rather than to `unattributed`, and print **every**
key with no `most_common(n)` truncation. The truncation is what produced the
unreconciled version.
