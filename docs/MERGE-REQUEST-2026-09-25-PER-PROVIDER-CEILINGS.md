# Per-provider spend ceilings, enforced before the call

**Lane T — 2026-09-25. Branch `worktree-agent-a5ab2805834c167b3`, branched from
`master` at `444e59f0` and rebased onto it.**

This is the money path. Everything here is enforced before a paid call or it is
decoration, so every claim below is followed by the test that would fail if it
stopped being true, and by what that test does when its guard is removed.

---

## 1. What this changes, in one paragraph

Spend ceilings were CLIENT-scoped: one `per_day`, one `total`, one declared-
and-never-enforced `per_run`. They are now PER PROVIDER, the client `total` is
gone, `per_run` is enforced by RESERVATION rather than inspection so it holds
at production concurrency, a bulk job's `creditsReserved` is checked against
the remaining balance before the upload is committed and is never ledgered as
spend, every refusal names the scope AND the provider, every progress block
carries the per-provider balance, and a CRITICAL fires once at 10,000
CheapVerifier credits remaining.

**One thing in here needs an operator decision before merge. It is in §9.**

---

## 2. The schema

`config/clients/<client>.yaml`:

```yaml
budget:
  per_day: 200000            # SANITY CEILING ONLY. Not a budget.
  providers:
    cheapverifier:
      total: 100000          # the ACCOUNT BALANCE, not a policy number
      per_day: 95000
      per_run: 10000
    deliverable:
      total: 500000
      per_day: 95000
    reoon:
      total: 500000
      per_day: 95000
    contactout:
      total: unlimited       # a DECISION, not an omission
    apify:
      total: unlimited       # see §9
```

| key | scope | meaning |
| --- | --- | --- |
| `budget.total` | client, lifetime | lifetime cap across every provider. **Removed for this client.** |
| `budget.per_day` | client, per UTC day | now a tripwire against a runaway loop |
| `budget.per_run` | client, per invocation | **Removed for this client.** See §5 |
| `budget.per_provider_per_day` | client, per provider per day | legacy client-wide default; still honoured |
| `budget.providers.<name>.total` | one provider, lifetime | |
| `budget.providers.<name>.per_day` | one provider, per UTC day | |
| `budget.providers.<name>.per_run` | one provider, per invocation | |

Three rules the schema carries that are not obvious from the shape:

1. **A provider block and the client block are independent.** Neither
   substitutes for the other and both are enforced. A provider block is not a
   share of the client's number.
2. **`unlimited` is a word an operator writes; an absent key is a ceiling
   somebody forgot.** They both mean "no number bounds this", and they are
   treated completely differently — see §4.
3. **`None` is reported as UNLIMITED and says so.** A progress line prints
   `run unlimited` for a provider with no declared `per_run` rather than `0`
   or a default nobody chose.

`spendledger.provider_caps(config, provider)` resolves one provider's block;
`spendledger.declares(config, provider, scope)` answers the different question
of whether anybody decided it.

---

## 3. The migration, with the numbers it was measured against

Ground truth, read off the ledger on 2026-09-25 before any of this landed:

| provider | all-time | today |
| --- | ---: | ---: |
| deliverable | 8,262 | 7,194 |
| reoon | 8,236 | 7,171 |
| contactout | 1,562 | 0 |
| apify | 447 | 0 |
| blitz | 232 | 0 |
| aiark | 70 | 0 |
| **TOTAL** | **18,809** | **14,365** |

### Before

```
per_run                2000     declared, enforced by NOTHING
per_day               15000     14,365 committed today ->    635 left
per_provider_per_day   None
total                 50000     18,809 committed all time -> 31,191 left
```

### After

```
budget.per_day       200000     sanity tripwire only
budget.total             --     REMOVED
budget.per_run           --     REMOVED
providers.*                     the ceilings above
```

### What the client caps had to become, and why

This was the question the lane was told to raise rather than answer, and the
operator answered it. The arithmetic that forced it:

* **`total` 50,000 under provider totals of 100,000 / 500,000 / 500,000 is
  decoration.** 31,191 credits of headroom remained. A CheapVerifier run
  against its 100,000 ceiling would have halted at 31,191 with a `total`
  refusal that reads nothing like "your provider ceiling was fine". For all
  three provider totals to be simultaneously reachable the client `total`
  would have had to be at least 1,102,311 — the three ceilings plus the 2,311
  already spent with the other providers — at which point it is not a budget,
  it is a number that exists to be large enough. The operator removed it.
* **`per_day` 15,000 under three provider `per_day` ceilings of 95,000
  cannot reach any of them**, let alone all three (285,000). 635 credits
  remained on the day the decision was made. It is now 200,000 and it is a
  tripwire, not a budget: nothing is expected to approach it, and anything
  that does is a bug and not a busy day.
* **`per_run` 2,000 against a required CheapVerifier `per_run` of 10,000 was
  not a headroom problem, it was a contradiction.** A 10,000-credit
  CheapVerifier run would have been refused at 2,001 by a CLIENT ceiling. The
  operator's decision makes the per-provider ceilings the caps, so the client
  `per_run` went with the `total`. **Nothing invented a replacement.** If a
  client-wide `per_run` tripwire is wanted it must be at least as large as the
  largest provider `per_run`, or it silently becomes the real ceiling again.

Tests: `TheClientCeilingBindsFirstAndSaysSo` — five tests that pin exactly how
a client ceiling outranks a provider ceiling, using the measured numbers, plus
`test_the_sanity_per_day_is_a_tripwire_and_still_refuses`.

---

## 4. The swap is ATOMIC, and the state between the two halves is refused

Until this change the client `total` of 50,000 was the **only lifetime cap the
estate had**. Removing it one commit before the per-provider totals are
enforced leaves the account bounded by nothing, and a 200,000/day tripwire
cannot see a runaway that happens inside a single day.

So the removal and the enforcement land in the same commit, and the
intermediate state is made impossible rather than merely avoided:

> **`spendledger.check` refuses a paid call that no lifetime ceiling covers.**
> With no client `budget.total` and no `budget.providers.<name>.total` for the
> provider being called, it raises `MissingCeiling` — naming the provider and
> the exact key to declare — instead of reading `None` as unlimited.

`MissingCeiling` subclasses `BudgetExceeded` deliberately. Every caller on the
spend path already catches that and treats it as "do not make this call", so an
estate that loses its lifetime cap **stops spending** rather than meeting a new
exception type at the top of a stack trace mid-batch.

Three details that make it a real guard rather than a slogan:

* **`unlimited` written in the config satisfies it; a missing key does not.**
  A decision and an omission must not look alike. `provider_caps` maps both to
  `None` (correctly — neither bounds anything); `declares` is what tells them
  apart.
* **It is checked LAST.** A refusal reading "no lifetime ceiling" when the
  true answer is "per_day is exhausted" would send somebody to edit the wrong
  key. Pinned by `test_a_real_crossing_is_still_named_by_its_own_scope`.
* **A free call is not refused for want of a ceiling.** `people-count` costs
  nothing and a planning step must not be stopped by a budget question that
  does not apply to it.

This is the same defect class as an empty expectation matching everything and
an empty ledger reading as an unspent budget: **a missing cap must never parse
as an unlimited one.**

Tests: `TheSwapIsAtomic` — 14 tests, including six that read the file that
actually ships rather than a fixture of it.

---

## 5. `per_run` stopped being a lie: reservation, not inspection

`per_run` was in `SCOPES`, returned by `caps()`, printed in the S5 preflight,
and enforced by nothing. The cost of that was measured, not argued: on
2026-09-25 a chunk stopped at **2,044 credits against a declared ceiling of
2,000** — twenty-two addresses past it — while every test in the file passed,
because the tests ran at `--workers 1` and production runs at 8.

**A cap tested after the answer can only ever report an overshoot.** So the
property now lives in `spendledger` itself rather than in each runner:

```python
hold = spendledger.reserve(client, config, cost, provider=..., call=...)
#   check + claim under ONE lock -> other workers cannot see this room
answer = provider_call(...)
spendledger.settle(hold, actual_cost)    # ledger row written, THEN hold dropped
#   or spendledger.release(hold)         # nothing bought, nothing ledgered
```

`spendledger.holding(...)` is the context-manager form: it releases on an
exception and settles on a clean exit.

* `committed()` — ledger spend **plus** credits held by calls in flight — is
  what every ceiling is now checked against. Checking `spent()` alone is
  exactly how eight workers each saw room only one of them could have.
* `settle` appends the ledger row **before** dropping the hold, so the
  committed total never dips for the moment in between — a moment another
  worker's check can land in.
* Ledger rows now carry `run_id` (they were `null` before), which is what
  makes `per_run` computable from the ledger at all, and it survives across
  the processes of one orchestrated pass via the `RUN_ID` environment
  variable.
* `scripts/stage_s5_verify.py`'s `--max-credits` is now a belt beside a brace
  rather than the only control there is. It was not touched.
* **`src/verification.py` — the path `stage_s5_verify.py` drives at K=8 — was
  converted from check-then-record to reserve-then-settle.** A call the
  provider did not charge for releases its hold instead of settling it, and a
  raising provider call releases rather than leaking.

### A hazard this introduces, and what to do about it

A run id is per process. A **long-lived process must call
`spendledger.new_run()` once per pass**, or its `per_run` accumulates until it
halts — which would look like the ceiling misbehaving rather than a missing
call. Checked 2026-09-25: none of the three `*_watch_loop.py` daemons, nor any
other `while True` loop in the tree, reaches a spend path, so nothing needs
this today. It is written down because the first daemon that starts spending
will need it.

---

## 6. The concurrency test, and its red proof

The single-worker test is exactly what missed this last time, so the test is a
**pair**, and the pair is the point.

`tests/test_a_provider_ceiling_refuses_before_the_call.py`,
class `ParallelWorkersCannotShareTheSameRoom`:

* The ledger is seeded to 38 against a `per_run` ceiling of 40. Eight **real
  threads** meet at a `threading.Barrier` and each asks for 2. Exactly one can
  have it. Between claiming and settling each sleeps — that sleep is the
  provider call, and it is the window the old shape left open.
* `test_k_workers_cannot_collectively_cross_a_provider_per_run` asserts the
  **ledger total** (the number the audit reads) is exactly 40, and that seven
  of the eight were refused.
* `test_the_same_eight_workers_DO_cross_it_when_they_only_check` drives the
  same eight threads through check-then-call-then-record and asserts that it
  **crosses**. This is the red proof kept live instead of claimed in a commit
  message: remove the reservation and the first test fails; make the race
  impossible and the second fails and the first stops proving anything.
  Neither can quietly become vacuous. It does not assert *how far* past,
  because that is the scheduler's business — measured here at six or seven of
  eight getting through, not always all eight, and a flaky control gets
  deleted along with the proof it carries.
* `test_a_free_running_race_also_holds_the_ceiling` runs eight workers buying
  until refused, with no seeding and no rendezvous. Its loop is **bounded** at
  50 attempts per worker against a ceiling that permits 20 calls in total, so
  that deleting the guard fails the test instead of hanging the suite — a
  suite that hangs gets killed rather than read.

### Every test shown to fail when its guard is removed

Fourteen guards were removed one at a time from `src/spendledger.py` and
`src/verification.py`, the suite run against each, and the file asserted
byte-identical to its original afterwards. Baseline green; post-restore green.
The tooling is not committed (`work/` is gitignored).

| guard removed | tests that went red |
| --- | ---: |
| M1 provider ceilings not enforced at all | 15 |
| M2 client `per_run` dropped from `check` | 2 |
| M3 provider `per_run` dropped from `check` | 10 |
| M4 reservations not counted (`committed` == `spent`) | 4 |
| M5 `reserve` checks but never registers the hold | 7 |
| M6 a reservation is ledgered as spend | 5 |
| M7 the CRITICAL threshold is gone | 7 |
| M8 the CRITICAL fires every time (no once-marker) | 1 |
| M9 the CRITICAL never re-arms after a top-up | 1 |
| M10 `per_run` counts every run, not this one | 9 |
| M11 a ledger row does not say which run bought it | 1 |
| M12 `holding()` does not release on an exception | 1 |
| M13 the progress block drops the per-provider balance | 4 |
| M14 verification checks instead of reserving | 2 |

The ones that matter individually:

* **M5** (reserve without registering) kills
  `test_k_workers_cannot_collectively_cross_a_provider_per_run` — the
  concurrency test fails for the intended reason, not a different guard.
* **M14** (the real money path reverted to check-then-record) kills
  `test_the_credits_are_HELD_while_the_provider_call_is_in_flight`, which asks
  `spendledger.reserved()` **from inside the provider call** while driving the
  real `verification.verify`. That assertion is on behaviour, not on the text
  of the source — an earlier draft grepped `src/verification.py` for
  `spendledger.reserve(` and was replaced, because a test that reads source
  fails when somebody writes a comment and passes on a call wired to nothing.
* **M8** and **M9** separate the two halves of "fires once": one test dies if
  it spams, a different one dies if it never re-arms.

Also updated, because they pinned the LEAK open and it is now closed:
`tests/test_the_second_client_runs_on_the_same_engine.py` (the
`test_LEAK_the_declared_per_run_ceiling_is_never_enforced` case now asserts the
refusal, and adds that A's spend does not consume B's `per_run`) and
`tests/test_a_run_holds_itself_to_the_declared_per_run.py` (Lane N's
`test_per_run_is_still_not_enforced_by_the_ledger_itself`, which said in its
own docstring that it should fail the day `check` learned `per_run`).

---

## 7. The bulk path: `creditsReserved` is HELD, not spent

`/file/upload` answers `creditsReserved` — credits the vendor has put aside for
a job it has not run. Per the vendor's own spec that is a hold, not a charge.

```python
hold = spendledger.reserve_upload(client, config, "cheapverifier",
                                  response["creditsReserved"])
#   raises BudgetExceeded BEFORE the upload is committed if it would cross
commit_upload(...)
...
spendledger.settle(hold, actual_credits)   # or release(hold) if cancelled
```

* **No ledger row is written by the reservation.** Ledgering a hold as spend
  makes our expected total disagree with the invoice.
* **It is still refused if it would cross.** A 9,000-credit reservation
  against a 5,000-credit balance is a batch that halts in the middle whether
  or not we call it spend.
* **It counts against every ceiling while outstanding**, including the balance
  the CRITICAL reads.
* On completion the ledger takes the **real** number, not the estimate.

Tests: `ABulkReservationIsCheckedBeforeTheUploadIsCommitted` — seven tests,
including `test_a_reservation_is_held_and_is_not_spend`,
`test_the_hold_BITES_or_it_is_only_bookkeeping` (the same call is allowed
without the hold and refused with it) and
`test_a_reservation_inside_the_balance_lets_the_upload_through`, which is the
control that stops the refusal tests passing on a seam that refuses everything.

### The seam lane Q should call

`src/providers/cheapverifier.py` belongs to lane Q and was not touched. What
this lane expects it to call, in order:

1. `POST /file/upload`, read `creditsReserved` from the response.
2. `hold = spendledger.reserve_upload(client, config, "cheapverifier", credits_reserved)`
   — **before** committing the upload. On `BudgetExceeded`: do not commit, and
   cancel the vendor-side reservation.
3. Commit the upload; run the job.
4. `spendledger.settle(hold, actual_credits)` when it completes, or
   `spendledger.release(hold)` if it is cancelled or fails.

For a per-address call rather than a bulk job, use
`with spendledger.holding(client, config, cost, provider="cheapverifier", call=...)`
— reserve, call, settle, with release on an exception, in one statement.
`spendledger.CRITICAL_REMAINING` already names `cheapverifier`; nothing else
needs adding there.

---

## 8. The CRITICAL at 10,000 remaining

**Shape.** `spendledger.CRITICAL_REMAINING = {"cheapverifier": 10_000}`. This
is the one provider whose `total` is an account balance rather than a policy
number: reaching it does not mean the ceiling worked, it means a batch halts
part-finished with rows bought and rows not, and the operator finds out from
the halt. 10,000 is roughly one large batch of warning — enough to top up
*between* batches instead of during one.

Two functions, because they answer two questions:

* `alerts(client, config)` — every CRITICAL that is **true right now**. Says
  nothing about firing. A standing CRITICAL rides along in every progress
  block, because fired-once must not mean hidden.
* `fire_alerts(client, config)` — only the ones **not yet announced**. The
  marker is durable (`spend-alerts.json`, beside the ledger, derived from its
  path so it moves with it and needs no second environment override).

**Fires once.** `check()` runs per call and a CRITICAL repeated per call is a
CRITICAL nobody reads — the alert that cried wolf is the same defect as no
alert. **Re-arms on a top-up:** when the balance climbs back above the
threshold the marker is cleared, so the next fall announces again. A one-shot
that never re-arms protects exactly one top-up cycle.

**Text:**

```
CRITICAL: cheapverifier has 9,000 credit(s) left of 100,000 for <client>, at
or below the 10,000 alert threshold. Top up before the next batch - at this
balance a batch halts part-finished, with rows bought and rows not.
```

A held reservation counts against the balance the alert reads: 9,000 credits
held are 9,000 credits the account cannot spend twice, ledgered or not.

### The per-provider balance in every PROGRESS block

`spendledger.progress_block(client, config)`:

Rendered against the measured ground truth above, with a 7,000-credit bulk
reservation outstanding:

```
PROVIDER BALANCE  client=<client>  run=run-5c84af7361e4  (expected credits)
  apify            left unlimited   today unlimited   run unlimited
  cheapverifier    left 93000 of 100000   today 88000 of 95000   run 3000 of 10000  <-- ACCOUNT BALANCE
                   (7000 credit(s) held by calls in flight, not yet ledgered)
  contactout       left unlimited   today unlimited   run unlimited
  deliverable      left 491738 of 500000   today 87806 of 95000   run unlimited
  reoon            left 491764 of 500000   today 87829 of 95000   run unlimited
  CLIENT-WIDE      left unlimited   today 178635 of 200000   run unlimited
```

A standing CRITICAL appends its line to the same block.

A progress line that reports rows done tells you how far the batch got and
nothing about whether it can finish. The CLIENT-WIDE line is there because
whichever ceiling binds has to be visible — and since the swap it is the one
line that reports `unlimited` for its lifetime cap, which is the swap made
visible rather than hidden.

---

## 9. Open items — read before merging

### 9.1 `blitz` and `aiark` are refused on their next paid call

Both have spend history (232 and 70 credits) and **neither is named in the
operator's decision**, so neither has a declared `total`. Under §4 that means
their next paid call raises `MissingCeiling` rather than proceeding against no
ceiling at all.

That is the conservative direction and it is deliberate — but it is a live
behaviour change, so it is here rather than in a stack trace. **The operator
needs to name them**: a number, or `total: unlimited` if they are deliberately
uncapped like ContactOut. `test_every_provider_the_ledger_has_ever_paid_is_declared`
pins the current set so it cannot drift unnoticed.

### 9.2 Apify's "5,000 $-cents/day" has no home

The decision names `apify 5,000 $-cents/day, as already declared`. Searched
2026-09-25: **there is no cents-denominated ceiling anywhere in this
repository**, and this ledger counts credits. Apify bills compute units,
`COSTS["apify-research"]` is zero, and Apify's real bound today is
`research.apify` in the client file — `max_runs_per_batch: 75`,
`max_items_per_run: 20`, `max_pages_per_domain: 5`.

Writing `5000` into `budget.providers.apify.total` would silently reinterpret
cents as credits, which is **worse than no ceiling because it looks like one**.
So `apify` is declared `total: unlimited` in this ledger with the reason
written beside it, and a cents-denominated ceiling is left as an operator
decision about which unit it is in and which code enforces it.

### 9.3 The empty-ledger hazard — lane S owns the predicate, this lane owns the seam

An agent's worktree has its own `work/`, which is gitignored and therefore
starts **empty**. Every per-provider `total` here is computed as
declared-minus-spent, so an empty ledger reads as "nothing spent, the whole
balance available" — in every worktree simultaneously. That would defeat these
ceilings without crossing one.

**Lane S owns `LedgerNotCredible`. Nothing in this lane decides whether a
ledger is credible, and nothing here duplicates that check** — two credibility
gates each assuming the other ran is the failure this is trying to avoid.

What this lane provides instead is a guarantee about where that gate has to go:
**every ceiling in `spendledger` reads the ledger through `load()`**, and
`test_every_ceiling_reads_the_ledger_through_load` proves it by making `load`
refuse and asserting that `check`, `reserve`, `reserve_upload`, `balances`,
`alerts` and `progress_block` all propagate the refusal. So lane S's gate
installed in `load()` covers all of them, and a ceiling that read the file some
other way would be a hole their gate could never cover.

**Action for whoever integrates both lanes:** confirm `LedgerNotCredible` is
raised from `spendledger.load()` (or from `store.read_jsonl` beneath it), and
run this test — it is the one that will notice if the gate ends up somewhere
that does not cover these ceilings.

---

## 10. Files

| file | what changed |
| --- | --- |
| `src/spendledger.py` | per-provider ceilings, `per_run` enforcement, reservations (`reserve`/`settle`/`release`/`holding`/`reserve_upload`), `MissingCeiling`, `balances`, `progress_block`, `alerts`/`fire_alerts`, `run_id` on every row |
| `src/verification.py` | the K=8 money path converted from check-then-record to reserve-then-settle |
| `config/clients/productive.yaml` | the swap: client `total` and `per_run` removed, `per_day` 200,000 as a tripwire, `budget.providers` declared |
| `tests/test_a_provider_ceiling_refuses_before_the_call.py` | new — 57 tests |
| `tests/test_the_second_client_runs_on_the_same_engine.py` | the `per_run` LEAK case now asserts the refusal |
| `tests/test_a_run_holds_itself_to_the_declared_per_run.py` | Lane N's "still not enforced" case turned the other way up |

Not touched: `src/providers/cheapverifier.py` (lane Q),
`scripts/stage_s5_verify.py`, `scripts/*_watch_loop.py`, `config/.env`.

No credit was spent in this lane. It is enforcement, not verification.
