# TASK 0100 — Apify spend is invisible, and one path is uncapped

Offline code-and-config reading. No Apify, provider or network call was made.
No cap, budget or config value was changed. `src/providers/*` was not opened.
Nothing was applied; everything below is a proposal.

Measured 2026-10-15 on `task-qwen-0090-watcher-treekill-2026-10-15`
at `566081c6e`.

---

## 0. Three artefacts this task names do not exist

Stated first because the task's own framing rests on them:

| named | status |
|---|---|
| `queue/_STANDING-RULES.md` | no `queue/` directory in this tree; `git log --all -- 'queue/*'` returns nothing |
| `FINDING-apify-and-signals-2026-10-15.md` | not in the tree, not in history |
| "the catalogue" (families of failing check) | no such file; only `docs/SLACK-AGENT-QUESTION-CATALOGUE.md`, unrelated |

So the standing rules were not read, because there is nothing to read. The
catalogue's family 1 is used below with the definition the task supplied
inline ("a check that cannot match"), not with a definition taken from a
catalogue nobody can produce.

**0090 is finished** on this branch: `fd6362dce` (step 1, the watcher's timeout
kills the TASK) and `566081c6e` (step 2, default 90 → 150). Tree clean.

---

## 1. They are two paths. Named, and distinct.

Not one path read twice. They share the `providers/apify` *module* for the
HTTP lifecycle and share nothing else — different entry points, different
Apify endpoints, different cost vocabulary, different ledger, different
bound, different callers.

### Path A — the website crawler

```
src/enrich.py:1182-1185     research.run(rec, config, live=…, spend=spend,
                                         scrape_budget=scrape_budget, …)
src/research.py:710-712     spend("apify-research", …, provider="apify",
                                  reason_code=PUBLIC_EVIDENCE_REQUIRED)
src/research.py:745-760     apify.start_run / wait_for / dataset_items
```

- Call name `apify-research`. Priced **0** by `enrich.COSTS` (`src/enrich.py:48`)
  and listed in `UNPRICED` (`src/enrich.py:114`).
- Goes through `enrich.spend()` (`src/enrich.py:865`), so it reaches BOTH
  `spendledger.record(...)` and `waterfall.record_step(...)`.
- Bounded by `research.RunBudget` (`src/research.py:283-308`), a **run count**
  seeded from `apify.settings(config)["max_runs_per_batch"]` at
  `src/enrich.py:1503-1505`. `config/clients/productive.yaml:185-189` sets
  `max_runs_per_batch: 75`.
- Called from production: the enrichment pipeline, every live `enrich.run()`.
- Third consumer of the zero price: `src/refresh.py:100-101` maps both
  `COMPANY_RESEARCH` and `PERSON_RESEARCH` to `apify-research`, so the refresh
  *forecast* also prices company and person research at zero.

### Path B — the research-pack actors

```
scripts/pack_fetch.py, scripts/capture_researchpack.py
  → src/researchpack/pack.py:223  run_actor(...)
  → src/researchpack/pack.py:147-151
        spendledger.reserve(client, config, spec["cost"],
                            provider="apify", call=name, unit="cents")
        spendledger.settle(hold)
  → pack.py:153 _live_runner → pack.py:161-183 _start (POST /acts/<a>/runs)
```

- Three actor names, priced in **integer cents** by
  `src/researchpack/actors.py:35-60`: `company_posts` 5, `open_roles` 4,
  `person_posts` 6.
- Goes through `spendledger` directly. **Never touches `enrich.spend()` and
  therefore never writes a waterfall step.**
- Bounded by `config/clients/productive.yaml:789-791`,
  `budget.providers.apify: {total: unlimited, per_day: 5000}`.
- **Zero callers anywhere under `src/`.** `grep -rn "run_actor\|researchpack"
  src/` outside the package returns only comments. Its only live callers are
  two operator scripts. Path B is a hand-run tool; path A is the pipeline.

### The one thing they do share, and it is the wrong thing

Both write `provider="apify"` into the same ledger. So the single
`budget.providers.apify` ceiling spans both paths — and spans them
**asymmetrically**:

- Path B raises the meter (cents) and can be refused by it.
- Path A reads the meter and **can never raise it**, because every row it
  writes is `expected_cost: 0`.

A day where path B has burned 5,000 cents will therefore refuse path A's
*free-to-the-ledger* crawl, while no number of path A crawls can ever refuse
anything. That coupling is not stated in either comment.
`config/clients/productive.yaml:785-788` asserts "This ceiling does not see
it" — that is true of path A's *contribution* and false of path A's
*subjection*.

---

## 2. What has actually been spent

### Authority, named first

This checkout (`C:\Users\Zvonimir\qwc`, confirmed the main checkout by
`git rev-parse --git-common-dir`) has an **empty `work/`** — only
`suite.lock.queue`. There is no spend ledger here at all.

The production ledger is in a **separate clone of the same repo**
(`origin` identical, `KatoKhan8/resonate-group-automation`):

    C:\Users\Zvonimir\Desktop\resonate-group-automation\work\spend-ledger.jsonl
    20,449 rows, 0 unparsable

Three other trees hold vestigial ledgers (4, 35 and 1 rows). The 20,449-row
file is the only one that can be the authority, and the figures below are
from it. **This is itself an invariant-0 problem:** the canonical spend
authority is not in the canonical checkout, and nothing in the repo says
which tree holds it.

### Apify rows: 563, all client `productive`, **not one carries a `unit`**

```
by call        apify-research 268 | open_roles 121 | person_posts 107
               site_content    29 | company_slug 22 | company_posts  16
by unit        None × 563
sum expected_cost                                               447
last apify row                              2026-09-30T18:35:20Z
last ledger row of any provider             2026-10-12T00:09:58Z
```

### By day

| day | path | rows | summed `expected_cost` |
|---|---|---:|---:|
| 2026-09-10 | A `apify-research` | 10 | **0** |
| 2026-09-12 | A `apify-research` | 214 | **0** |
| 2026-09-15 | A `apify-research` | 29 | **0** |
| 2026-09-24 | B actors | 295 | **447** |
| 2026-09-30 | A `apify-research` | 15 | **0** |

### What that means, path by path

**Path A: the ledger cannot know, and does not say so.** 268 live runs are
recorded, each one a real Apify actor start billing real compute units, and
the column that holds what they cost reads 0 — 268 times. `spent(client,
provider="apify")` therefore returns a number from which path A is
arithmetically absent. The authority that *could* answer is Apify's own
account usage, read as `apify_usd_month_to_date` by
`src/costs.py:349-350`. **That key has no writer anywhere in the repo and no
file containing it exists on disk** — not in the production `work/`, not
anywhere under `Desktop`. So `src/costs.py` has never been fed an Apify
reading, and the honest answer for path A is **UNKNOWN**, not zero.

**Path B: 447 cents, all time, all on one day, and the figure is an estimate
nobody ever settled.** `pack.run_actor` calls `spendledger.settle(hold)` with
no `actual_cost` (`pack.py:151`), and `settle` then writes `hold.cost` —
the *planned* figure — permanently (`spendledger.py:757-760`). Nothing in the
system ever compares it to what Apify charged. `src/spendledger.py:139-144`
already states the 447 as the all-time figure, so this measurement
corroborates the code's own note.

### Two things the rows say that the code does not

1. **The recorded costs do not match the current price table.** The 295 rows
   carry costs of 1, 2 and 3 cents (148 × 2, 145 × 1, 2 × 3).
   `actors.ACTORS` today prices them 4, 5 and 6. The rows predate the table.
2. **Two of the five call names do not exist.** `site_content` (29 rows) and
   `company_slug` (22 rows) appear nowhere in `src/`, `scripts/` or `tests/`,
   and `git log --all -S"company_slug" -- '*.py'` returns nothing. 51 paid
   Apify runs were ledgered by code that is not in this repository's history.
   That is a third vocabulary, and it is the shape the task anticipated —
   worth its own finding.

### Has the ceiling ever been consulted?

Yes, and never meaningfully. Path B has written nothing since **2026-09-24**;
the ceiling was added **2026-09-25**. So no chargeable Apify call has been
checked against it, ever. The 15 path-A rows of 2026-09-30 *did* call
`spendledger.check(client, config, 0, provider="apify")` — fifteen
comparisons of `447 + 0 > 5000`, fifteen passes by construction.

---

## 3. Can an alarm fire on the zero-priced path? No. Family 1.

**Verdict: family 1 — a check that cannot match.** Four independent reasons,
any one of which is sufficient:

1. **The quantity is structurally constant.** `check` refuses on
   `already + cost > limit` (`spendledger.py:636`). `cost` is
   `COSTS["apify-research"]` = 0, by construction and by a test that asserts
   it (`tests/test_research_spend.py:201`). `already` is a sum of
   `expected_cost`, to which path A contributes 0 per row. The inequality
   `447 + 0 > 5000` has one value and will have it forever.
2. **The `total` scope is not compared at all.** `_limit("unlimited")` returns
   `None` (`spendledger.py:552-562`) and `check` skips any scope whose limit
   is `None`.
3. **The lifetime-ceiling guard is gated on `cost > 0`**
   (`spendledger.py:704`). So path A never even reaches the "is anything
   bounding this at all?" question — the one guard written specifically to
   catch an unbounded provider cannot see the one call that is unbounded.
4. **`alerts()` cannot emit an Apify row under any ledger state.** It skips a
   provider whose `critical_at` is `None` (`spendledger.py:973-975`), and
   `CRITICAL_REMAINING = {"cheapverifier": 10_000}` (`spendledger.py:134`) is
   the whole table. Independently, `remaining` is also `None`, because
   `_remaining(None, …)` returns `None` when the `total` is unlimited. Two
   reasons, either one fatal.

The in-memory `RunBudget` is the only thing that bounds path A, and it is
**per process**. It is created in `enrich.run()` and dies with it, so three
enrichment passes in one day each start up to 75 runs and nothing in the
system can state the total — which is precisely the defect
`src/enrich.py:900-905` already records for the credit budget, reproduced one
layer down and not noticed.

Minor, adjacent: `RunBudget.allow()` appends to `started` *before* `spend()`
runs (`research.py:717`), so under `--cap 0` — where `Budget.affordable`
deliberately refuses `UNPRICED` calls — each refusal still consumes a run
slot. Noted, not in scope.

---

## 4. What `unlimited` costs in the worst case

`per_day: 5000` is **integer cents**, so **$50.00 per client per day**.

`check` admits a call iff `already + cost <= 5000`, so the day's committed
total can never *exceed* 5,000. The arithmetic the current config permits:

```
per day        5,000 cents                 =    $50.00
30 days       30 × 5,000 = 150,000 cents   = $1,500.00
365 days     365 × 5,000 = 1,825,000       = $18,250.00
```

**There is no terminus.** `total: unlimited` means the 30-day figure is not a
cap but a *rate*: the config permits $50/day forever, and names no number at
which anything stops, slows or alerts. The client-wide `per_day: 200000`
does not bind it — it is 40× larger and, as
`config/clients/productive.yaml:774-780` concedes, it sums cents with credits
and is a tripwire rather than an amount.

**And $1,500 is not the exposure, it is the bound on the system's own
guess.** The 5,000 is compared against `actors.ACTORS[*]["cost"]`, planned
figures that `settle` never reconciles against a real charge. The ledger
already proves the guess drifts: the rows on disk say 1/2/3 and the table now
says 4/5/6. The true 30-day exposure of path B is **$1,500 × (real cost ÷
estimated cost)**, and nothing in this system knows that ratio.

Path A's 30-day exposure is **not expressible**. 75 runs per batch × an
unbounded number of batches per day × an unknown price per run.

---

## 5. Proposal — not applied

### Is a money ledger possible for path A at all?

**No, not honestly, and not from inside this task's boundary.** Three
reasons:

1. Apify bills compute units. Nothing in the config, the price table or the
   ledger carries a price per compute unit, and inventing one is the thing
   `USD_PER_UNIT` exists to refuse (`spendledger.py:185-195`: `None` means
   "nobody has priced it", and that is a real answer).
2. Even if the run object carried its own charge, CLAUDE.md's standing rule
   is "Provider modules return trimmed dicts, never raw payloads" — so it
   would have to be deliberately threaded through `apify.wait_for`. Whether it
   survives the trim today **cannot be answered here**: this task forbids
   opening `src/providers/*`. That is the single thing an implementer must
   check first.
3. The charge is not known at the moment of the call, and
   `spendledger.record`'s whole contract is to record the EXPECTED charge at
   call time. A settle-later design is a different ledger.

### So: a run-count ledger. Said plainly.

**A spend ledger that cannot see a provider should record that it cannot, and
this one records zero. Zero and unknown are different numbers.** The honest
fix is to count what the system actually knows — runs started — and to refuse
to express it in money.

**The smallest change.** In `enrich.spend()` (`src/enrich.py:925-945`), where
the durable row is written, branch once on `call in UNPRICED`:

```python
if live:
    from . import spendledger
    unpriced = call in UNPRICED
    ledger_provider = "apify-crawler" if unpriced else provider
    ledger_cost, ledger_unit = (1, "runs") if unpriced else (cost, None)
    try:
        spendledger.check(rec.get("client"), config, ledger_cost,
                          provider=ledger_provider)
    except spendledger.BudgetExceeded as e:
        ...
    spendledger.record(rec.get("client"), ledger_provider, call,
                       ledger_cost, unit=ledger_unit)
```

plus two one-line table entries in `src/spendledger.py`:

```python
LEDGER_UNITS["apify-crawler"] = "runs"
USD_PER_UNIT["runs"] = None      # nobody has priced a run, and nothing may invent one
```

Five properties, each deliberate:

- **`COSTS["apify-research"]` stays 0.** The credit cap must remain unable to
  refuse a crawl; raising it to 1 would mix runs into a credit budget — the
  exact unit hazard the config comments already name. This is why
  `tests/test_research_spend.py::WhatDoesNotBoundIt` **stays green**, both
  assertions. The fix contradicts no existing test.
- **A separate provider key, not `unit="runs"` under `"apify"`.** Writing runs
  under `provider="apify"` would put cents and runs under one unit-blind
  ceiling; `balances()` already detects this and reports `units_seen` as a
  list precisely because "a provider whose rows carry two units has a ceiling
  that means nothing" (`spendledger.py:877-880`). Splitting the key respects
  that detector instead of tripping it.
- **`USD_PER_UNIT["runs"] = None` makes the ledger say it cannot know.**
  `usd_estimate` then returns `(None, None, "unknown")`, and the row's
  `usd_estimate` field is written as unknown rather than as 0. That is the
  whole point of the fix in one line.
- **It fails closed, and that is the operator decision this surfaces.** With
  `ledger_cost = 1`, `check` reaches the `cost > 0 and governed and not
  declares(config, "apify-crawler", "total")` branch and raises
  `MissingCeiling` — every live research crawl is refused until the operator
  declares `budget.providers.apify-crawler: {total: <N>, per_day: <N>}` **in
  runs**. That config change is not proposed here and must not be made
  without the operator: it is the first real ceiling path A has ever had, and
  picking its number is a policy decision.
- **It makes `RunBudget` durable.** The per-day run count survives the
  process, which the in-memory cap never did.

**Companion, one line, independent of the above.** 563 historical rows read
`expected_cost: 0` with no way to tell "free" from "unpriced". Adding
`"priced": False` to rows whose call is in `UNPRICED`, and surfacing
`unpriced_calls` per provider in `balances()`, stops `spent_all_time: 0` ever
being read as "nothing was spent". Worth doing even if the run-count ledger
is rejected.

### Also surfaced, needing an operator, not a patch

1. The spend authority lives in a different clone from the main checkout.
2. 51 paid Apify runs (`site_content`, `company_slug`) were ledgered by code
   that is not in this repository's history.
3. `actors.ACTORS` prices drifted from every row on disk and nothing settles.
4. `budget.providers.apify` spans two paths with opposite relationships to it.

---

## 6. Born-red test — written here, deliberately not applied

For the run-count fix. Would live at
`tests/test_an_unpriced_run_is_counted_not_zeroed.py`.

```python
"""Zero and unknown are different numbers, and the ledger writes zero.

`COSTS["apify-research"]` is 0 because Apify bills compute units, which is
a price this system is never told. `enrich.spend` then writes that 0 into
the durable ledger, so 268 real actor runs are recorded as having cost
nothing - indistinguishable in `spent()` from a provider that charges
nothing at all. These tests fail today, each for its own stated reason.

They do NOT ask for `COSTS["apify-research"]` to change. The credit cap
must stay unable to refuse a crawl; `test_research_spend.WhatDoesNotBoundIt`
says so and stays green. What is asked for is that the DURABLE row record a
run, in a unit nobody can convert to money.
"""
import unittest

from src import enrich, research, spendledger
# `ResearchSpend` carries `seeded()`; `stub_apify()` currently sits one level
# down on `ALiveRunIsRecorded` (test_research_spend.py:90). Lifting it to
# `ResearchSpend` is a one-line move and is part of this change; subclassing
# `ALiveRunIsRecorded` instead would re-run its nine tests under a second name.
from tests.test_research_spend import ResearchSpend

CONFIG = {
    "research": {"apify": {"enabled": True}},
    "budget": {"providers": {"apify-crawler": {"total": "unlimited",
                                               "per_day": 500}}},
}


class AnUnpricedRunIsCountedNotZeroed(ResearchSpend):

    def setUp(self):
        super().setUp()
        self.rec = self.seeded()                  # a record `research.why` wants
        self.stub_apify()                         # start_run / wait_for / dataset_items

    def _run_one(self):
        budget = enrich.Budget()
        enrich.enrich_record(self.rec, budget, live=True, log=[],
                             config=CONFIG,
                             scrape_budget=research.RunBudget(cap=10))
        rows = [r for r in spendledger.load()
                if r.get("call") == "apify-research"]
        self.assertTrue(rows, "the run must reach the durable ledger at all")
        return rows

    # RED today: the row is written with expected_cost 0.
    def test_the_row_counts_the_run(self):
        row = self._run_one()[-1]
        self.assertEqual(row["expected_cost"], 1,
                         "one actor run is one run; 0 says it was free")

    # RED today: the row carries no `unit`, so `row_unit` falls back to
    # LEDGER_UNITS["apify"] == "cents" and 268 runs read as 0 cents.
    def test_the_row_names_its_unit_and_it_is_not_money(self):
        row = self._run_one()[-1]
        self.assertEqual(row.get("unit"), "runs")

    # RED today: provider is "apify", so runs would be summed into the same
    # ceiling as researchpack's cents.
    def test_the_crawler_does_not_share_the_actors_ceiling(self):
        row = self._run_one()[-1]
        self.assertEqual(row["provider"], "apify-crawler")
        self.assertNotIn("runs", spendledger.balances(
            self.rec["client"], CONFIG)["apify"]["units_seen"])

    # RED today: "runs" is absent from USD_PER_UNIT, so .get returns None and
    # usd_estimate already answers "unknown" - but nothing declares it, so a
    # unit added later could silently acquire a rate. This pins the decision.
    def test_a_run_has_no_dollar_price_and_none_is_invented(self):
        self.assertIn("runs", spendledger.USD_PER_UNIT)
        self.assertIsNone(spendledger.USD_PER_UNIT["runs"])
        estimate, rate, source = spendledger.usd_estimate(1, "runs")
        self.assertIsNone(estimate)
        self.assertEqual(source, "unknown")

    # RED today: RunBudget is in-memory, so a second pass restarts the count.
    def test_a_second_pass_cannot_restart_the_count(self):
        self._run_one()
        before = spendledger.spent(self.rec["client"],
                                   provider="apify-crawler")
        self.rec = self.seeded()
        self._run_one()
        self.assertGreater(
            spendledger.spent(self.rec["client"], provider="apify-crawler"),
            before,
            "the durable count must survive the process that started the run")

    # RED today: cost is 0, so `check` skips the lifetime guard entirely and
    # an undeclared crawler ceiling is never noticed.
    def test_an_undeclared_crawler_ceiling_refuses_rather_than_spending(self):
        bare = {"research": {"apify": {"enabled": True}},
                "budget": {"providers": {}}}
        with self.assertRaises(spendledger.MissingCeiling):
            spendledger.check(self.rec["client"], bare, 1,
                              provider="apify-crawler")


if __name__ == "__main__":
    unittest.main()
```

**Attacking the test, as the rules require.** Each case must be confirmed to
fail for *its own* reason and not for a shared one — in particular
`test_the_row_counts_the_run` must fail on the value `0`, not on
`self.assertTrue(rows)`, which would mean the run never reached the ledger
and would be a different bug. The control is
`tests/test_research_spend.py::ALiveRunIsRecorded::test_a_live_run_writes_the_waterfall_step_the_audit_reads`
(line 117), which proves a live run already reaches the ledger; if it is
green and these are red, the red is about the *contents* of the row and not
about the row's existence.
