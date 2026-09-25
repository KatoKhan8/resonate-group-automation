# S5 over the US cold cohort, 2026-09-25

Lane N. Counts only: no address, domain, contact key or company name appears
in this file or in anything else this lane committed.

## The blocker, cleared before anything was bought

Master's `stage_s5_verify.py` is the pre-fix version. Measured on the two
properties that matter, in the git objects rather than from the handoff:

| | master | 97832f0e |
|---|---|---|
| `spendledger` references in `stage_s5_verify.py` | 0 | 13 |
| `store.lock` references in `spendledger.py` | 0 | 2 |

Both claims confirmed. Master's S5 does not reach the spend ledger at all -
the "22,000 credits with no ledger row" defect - and master's
`spendledger.record` is the bare append that tore the ledger on 09-24.

Cleared by rebasing this branch onto current master (`5a14bd19`) and
cherry-picking `97832f0e`, which applied clean; it was the only commit that
branch held that master did not. Both properties were then verified **in the
working-tree files that were actually about to run**, not in the git objects:
13 and 2.

The nine tests the fix carries pass. More to the point, one of them was
proven capable of failing: with `store.lock` replaced by a no-op context
manager - exactly master's behaviour - `test_a_held_lock_blocks_the_append_
rather_than_racing_it` fails with "QueueLocked not raised". A green test that
cannot go red is not evidence.

## The operator's ceiling, and the one it exposed

`config/clients/productive.yaml` `budget.per_day` 5,000 -> **15,000**.
`per_run: 2000` and `total: 50000` untouched. Asserted by effect
(`spendledger.caps(clients.load("productive"))`), not by reading the file
back.

`total` is the ceiling that binds: 4,444 committed at the start of the day,
so 45,556 of headroom, and 45,556/15,000 = **3.04 days**. The operator's
"three days" is exact.

The operator's "the 09-07 supply is to 0.2% exactly one budget wide" I could
**not** reproduce. One budget of headroom buys 45,556/1.98 = 23,008
addresses; the amended 09-07 set carries 26,252 eligible addresses (16,929
pending + 9,323 already settled or parked at the start of today). That is
12.4% apart, not 0.2%. Nothing was decided on it - `total` was not touched -
but the number should not be repeated as though it had been checked.

### `per_run: 2000` was declared and enforced by nothing

`spendledger.check` iterates `per_day` and `total`, then tests
`per_provider_per_day`. `per_run` is in `spendledger.SCOPES`, is returned by
`caps()`, and has no consumer on any spend path. Already pinned as a LEAK by
`test_the_second_client_runs_on_the_same_engine.py`, and the runner prints
"declared and NOT enforced" on every start.

At `per_day` 5,000 that was nearly harmless. At 15,000 one invocation could
spend seven and a half times the limit the client file states. The runner now
holds itself to the client's **own** declared `per_run` via `--max-credits`.

## Two defects the spend itself found

**The cap held at K=1 and was crossed at K=8.** Chunk 1 stopped at 2,044
credits against a ceiling of 2,000 while every test passed - because the
tests ran at `--workers 1` and production runs at 8. `Executor.map` submits
every task at once, so workers keep buying while the consumer walks results
in order; a cap tested *after* each answer can only ever report an overshoot.
Workers now RESERVE before asking, at an estimate rounded UP from the
measured 1.98 so the run stops early rather than late, reconciled against the
real ledger cost once each address answers. After the fix the three clean
chunks stopped at **1,999, 2,000 and 2,000**. The new test runs at K=8 and
asserts the ledger total; with the reservation neutralised it fails at 66
credits against a ceiling of 40.

**Three passes bought the same cohort at once.** A stop killed the shell and
not the python child it had spawned, and the surviving shell loop spawned
another chunk on top. It was noticed only because three processes interleaved
their output into one log. `per_day` was never at risk - `check` re-reads the
ledger before every call - but `per_run` is enforced per process, and two
passes that read the same journal at startup take the same pending set and
buy some of it twice. A pass now takes an exclusive advisory lock for its
whole duration, `timeout=0` so a second pass refuses rather than queueing
behind a list that is already being bought. Verified live: a second pass
launched against a running one printed REFUSED and bought nothing.

*Operationally: killing the shell does not kill the python child on this
machine. Check for an orphaned process and confirm the ledger has stopped
growing before believing a run has stopped.*

## The cohort is scoped by person; eligibility is scoped by domain

`eligible_domains` filters domains and `contacts_for` then takes every
address the source list holds on one. Of the cohort's 10,418 domains, 7,647
(73.4%) are S5-eligible on the amended 09-07 set, and they carry 6,817
pending addresses - but only 6,019 are cohort members. The other 798 are
addresses the cohort's four exclusions had already removed. A domain-scoped
run buys all 798, about 1,580 credits re-verifying people excluded from the
push. `--only` intersects the run with the cohort file; it is restriction
only and can never add an address. It held 10,915 non-cohort pending
addresses out of every pass.

## What was spent, and what it bought

Verification only. **No discovery was bought** - at 2.81 credits/domain it
competes with verification for the same budget, and the mission was
verification depth on an existing cohort, not new supply.

From the ledger, not from the runner's counter:

| | |
|---|---|
| credits committed today | **14,365** / 15,000 |
| ledger rows today | 14,365 (deliverable 7,194, reoon 7,171) |
| addresses answered | **7,182** |
| cost per address asked | 2.00 |
| committed all time | 18,809 / 50,000 (31,191 headroom) |

Outcomes, and **only the first class is sendable**:

| state | n | share |
|---|---|---|
| **verified** | **2,774** | **38.6%** |
| held | 3,109 | 43.3% |
| accept_all_uncleared | 1,139 | 15.9% |
| unknown | 141 | 2.0% |
| invalid | 19 | 0.3% |

**2,774 sendable**, at 5.17 credits each. 562 addresses parked. Yesterday's
push was hundreds; the verification half of tomorrow's is thousands.

`verified` is the verification half only. READY additionally needs S6
collision and suppression, S7 copy, and the ICP verdict.

### Reconciliation

Ledger 14,365 credits; journal 14,347. **Difference 18, and the ledger is the
larger** - so no call went round the ledger, which is the direction that
would matter. The 18 are calls that were paid for and whose verdict was lost
when the three concurrent processes were killed: the ledger row is written at
the moment of the call, the journal row only after the answer comes back. The
gap was exactly 18 before the clean run and exactly 18 after it, which is
what says it is that incident rather than an ongoing leak. Those addresses
were left un-settled and will be re-asked.

## Two findings for whoever sizes the next run

**Deliverable is not degraded; `risky` is just its answer.** 49% of the first
sample held on "the primary is unknown", which looked like a failing provider
until it was compared like for like. `deliverable.classify` maps the vendor's
`risky` onto `unknown`. The rate is 35.1% today against 34.1% on 09-24 - the
same, on the same provider pair. The whole-journal rate of 10.4% is not the
comparison to make: for most of that journal the primary was ContactOut,
which the operator removed from this client's verification roles on 09-21.

**Re-asking a `risky` hold is poor value, and the backlog is mostly those.**
Measured on addresses actually asked twice:

| first answer | rescued by the retry | credits per rescue |
|---|---|---|
| "primary is missing" (the throttle shape the rule was written for) | 37.3% | 5.4 |
| "primary is unknown" (`risky`) | 16.4% | **12.2** |

Against 5.17 credits per sendable address on fresh supply, re-asking a
`risky` hold costs roughly twice as much per lead. `RETRYABLE` was written
for ContactOut answering 429, where a second ask genuinely clears a transient
failure; "primary is unknown" was put in the same bucket, but it is a real
verdict about the address and a second ask mostly returns it again. Worth an
operator decision before the remaining ~2,400 of that shape are re-bought:
the same credits buy about twice the leads spent on addresses never asked.

## Routing

`policy_for(config)` resolves to primary **deliverable**, secondary **reoon**,
catch-all **reoon**, two confirmations - the client override the operator set
on 09-21 when ContactOut was removed from Productive's verification roles.
ContactOut was never called. Note that `PROVIDER-ROUTING-POLICY.md`'s "the
stated order and the configured roles are the same thing" section still
documents primary=contactout/secondary=deliverable, which is `DEFAULT_POLICY`
and not what this client runs; the runner reads `policy_for(config)` and is
right to. The doc is stale on that point.
