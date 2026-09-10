# Overnight report — 2026-09-10 into 2026-09-11

The 250-domain dry run, what it measured, and the four defects it exposed.

---

## HEAD / TREE / VALIDATION

```
HEAD    f0996be
commits 12 this session on top of 4e5e70c
tree    clean; the batch inputs are now gitignored rather than untracked

full suite      7,029 tests   OK   (definitive, settled tree)
offline harness 7,029 tests   OK   "nothing reached off this machine"
hygiene/secrets 64 tests      OK
mutations       26            each caught by the intended test
```

The two suites were run with a gap between them, which is what CLAUDE.md
prescribes and what I failed to do yesterday - that omission produced the one
"failure" in the previous report.

---

## 1. The 250-domain run

The pack's own README says the files are nested: **50 ⊂ 250 ⊂ 1,000 ⊂ 5,000 ⊂
24,710**. So ingest was also a dedupe test, and it passed exactly: 250 rows in,
50 skipped as already queued, 200 new records, queue 100 → 300. No duplicates,
no malformed rows, one column.

Run in three stages, each measured:

| | credits | apify | outcome |
|---|---|---|---|
| ingest | 0 | 0 | 200 new, 50 deduped, < 1s |
| zero-cap pass | **0** | **$0.00** | every paid call refused, verified against provider counters |
| paid pass | 145 → 200 | $0.858 | 200 records, nothing hit the cap |

The zero-cap pass is worth its own line: it exercised the new UNPRICED rule in
production. Every `company-information-from-domain` and every `apify-research`
was refused at `--cap 0`, and both ContactOut and Apify counters were unchanged
afterwards. A dry run that genuinely costs nothing.

### 50 versus 200, measured

```
                            50-COHORT   |     200 NEW
  domains in                50   100%   |  200   100%
  company facts             45    90%   |  172    86%
  research executed         22    44%   |   17     8%
  vertical known            21    42%   |   55    28%
  conf medium+high           5    10%   |    2     1%
  QUALIFIED                  4     8%   |    2     1%
  review                     8    16%   |   22    11%
  rejected                  20    40%   |   71    36%
  unknown                   18    36%   |  105    52%
  people found               4     8%   |    0     0%
  2/2 verified               2     4%   |    0     0%
```

**The nonlinearity is entirely research throughput.** Company facts scale
linearly — 90% against 86%, which is domain quality, not a system property.
Research does not: 44% against 8%. And qualification tracks research almost
exactly: 8% against 1%.

The cause is one configured number. `max_runs_per_batch` is 10, so a batch
researches ten companies however many are in it. The 50-cohort got three passes
— thirty slots for fifty domains. The 200-cohort got two — twenty slots for two
hundred.

**Yield here is throughput-limited, not quality-limited.** That is a better
problem to have than the one this cohort had yesterday, and it is a different
one.

---

## 2. Scale model, from measured inputs

```
measured   apify per research run    $0.0429   (20 runs, $0.857785)
           research wall time        55s median (29 observed runs)
           research slots per batch  10        (client config)
           share needing research    64%       (127 of 200 after one pass)

 domains  credits  research   apify $  batches  research time
     250      250       159      6.81       16          2.4 h
    1000     1000       635     27.23       64          9.7 h
    5000     5000      3175    136.17      318         48.5 h
   24710    24710     15691    672.97     1569        239.7 h
```

ESTIMATES, linearly extrapolated from one 200-domain run. Two caveats that
matter more than the numbers:

- Research is **serial**. That time column is wall clock for one process, and
  it is the figure that changes most if research is ever parallelised. Ten
  days of continuous crawling for the full universe is not a plan.
- ContactOut's email bucket quota is 39,215. The full universe costs **63% of
  it in company lookups alone**, before a single person is enriched.

And one hard floor found tonight: the free tier alone qualifies nobody. A
zero-cap pass yields only `headcount_signal` and **zero of twelve ICP
dimensions score**. One credit per domain is the minimum for any verdict at
all.

---

## 3. What the run exposed

### 3a. LinkedIn copy was never claim-checked — P0

`eligibility._email_checks` runs `lint.check` then `claims.verify`.
`_linkedin_checks` ran neither.

The fabrication this whole programme exists to prevent — "you are running
utilisation at <their company>", told to a real person about a company that never
said it — **was a LinkedIn note**. The only code that would have refused it is
`executionguard`, and the routine path (`push.heyreach_rows` →
`verify_before_payload` → `eligibility.decide`) does not go through it.

Same shape as the collision check that was hardened on email and left open on
LinkedIn until yesterday morning. Fixed, with the invariant asserted as a
property of both branches rather than as two instances.

### 3b. …and the checker could not have caught that sentence anyway

`claims.is_claim` recognised a **number** or an **event word**. "you are
running utilisation" has neither, so a flat statement about how somebody else's
company operates was not a claim at all.

`asserts_about_them` now catches second-person operational assertions. Every
part of its shape exists to avoid refusing honest copy: verbs not possessives
(the canary note says "at your size"), an operational term required ("you are
welcome to book a slot" asserts nothing), hedges exempt (the day-21 template is
conditional and negated), questions already exempt.

**It immediately found three fabrications in this repository's own copy.**
`demo.py`'s `no_signal` and `irrelevant` hooks both read "You run delivery
across several teams at once" — on records that by their own names carry no
signal. And `test_e2e.py`'s constant literally named `GOOD_BODY` opened "you
are running the finance side of a team spread across several offices", about a
company with no `offices` fact; the one in the cassettes belongs to a different
company. All three rewritten to generalise and ask.

### 3c. `--cap` had no odometer

`enrich.Budget` lives in memory for one invocation. I ran three passes over one
cohort at `--cap 260`; each was individually inside budget and nothing could
state the total. `pilotcaps` bounds volume, not money, and there is **no
monetary budget anywhere in this repository** — searched.

`spendledger` is durable, day-scoped and tenant-scoped, wired into
`enrich.spend` because that is the single door every paid call already uses. It
reports honestly right now:

```
expected total   145
expected today   145
  contactout     145
  apify          0
ceilings
  per_run / per_day / per_provider_per_day / total   UNLIMITED - none declared
```

**It does not choose a budget.** See READY_FOR_OPERATOR.

### 3d. The ContactOut counters lag, and that changes an earlier finding

Yesterday's report said ContactOut was "unchanged all day" against 22 expected
credits, and called it COST_UNRECONCILED. Read again eight hours later, the
same window showed `count` +4, `phone_count` +3, `search_count` +25 — and the
verdict became **RECONCILED**.

The module had said "either these do not meter, **or the counters lag**" and
refused to choose. The second was true. That refusal is why this is a cheap
correction rather than a wrong claim standing in a report.

`PENDING_SETTLEMENT` now exists for it, with the window stated as bounds rather
than a number pretending to be exact: not settled at 20 minutes, settled by 8
hours, nothing observed between.

---

## 4. Tests

```
copy/push/e2e/guard band   1,527   OK
run + invariants + ledger    115   OK
mutations this session        20   each caught by the intended test
```

Mutations by guard: durable budget 4 (dry-run charges, ceiling never consulted,
unscoped check permitted, corrupt ledger reads as empty); cost settling 2;
cost reconciliation 4; LinkedIn tenancy 3; crash window 3; plus the claims
work verified by three real fabrications it found in fixtures.

Two registries caught the spend ledger's absence the night it was added —
`store.STATE_OVERRIDES` via `test_invariants`, and `test_run`'s allowed-files
list. Both are working.

---

## 5. Things I got wrong tonight

Recorded because the pattern matters more than the instances.

- **I killed a healthy run.** The paid pass looked hung at 4 records; I
  sampled during the research phase, where each record takes ~60s, and read
  the checkpoint lag as a stall. 45 records had actually survived. The
  checkpoint made it cheap, which is what it is for.
- **Three times I computed a value and did not consume it.** Stage timings
  added to the run report and never printed. `measured_after` added to
  `reconcile` and never passed by its own CLI. Both committed by the person
  who had just written a commit message about that exact habit.
- **My first claims rule refused the day-21 template**, which is conditional
  and asserts nothing — the false-positive class that gets a safety test
  deleted rather than fixed.

---

## 6. READY_FOR_OPERATOR

**1. Declare a budget, or decide there is none.**
`spendledger` enforces `per_run`, `per_day`, `per_provider_per_day` and
`total` from client config. All four are currently undeclared, which means
unlimited, and the report says so on every line.
*Safe default:* leave undeclared; `--cap` still bounds each run.
*Recommendation:* declare `total` first — it is the one that would have caught
tonight's three-passes-at-260. A figure is yours to choose; I have deliberately
not invented one.
*Unblocks:* a ceiling that survives a restart.

**2. HeyReach campaign 594061 — unpause, or grant live-provider permission.**
14 of 15 gates pass against fresh provider truth. Two independent blockers
remain and neither is a bug: the killswitch's global layer is derived from
`push.py` raising rather than read from a flag, and this environment's
permission layer refuses live provider writes.
*Exact action:* press unpause in the HeyReach UI. One connection request, seat
116968, one staged lead, copy verified against the approved fingerprint.
*Risk to accept:* `heyreach.pause` is implemented but not declared supported,
because it has never once succeeded against the provider. Until it does, this
system can start nothing it can stop — which is why the `stoppability` gate
caps LinkedIn at one contact.

**3. ContactOut metering — a support question, not a code question.**
200 expected credits against a settled-later delta. The buckets do move; they
lag by hours. Worth asking ContactOut which operations bill against which
counter, so `costs.py` can stop saying PENDING.

**4. Research throughput is the yield ceiling.**
`max_runs_per_batch: 10` is client config. At 250 domains it is 16 batches; at
24,710 it is 1,569 and ten days of serial crawling.
*Recommendation:* do not raise it blindly — raise it with a per-day Apify
ceiling declared at the same time (item 1), or parallelise research behind a
bounded worker count.

---

## 7. Next

**P0** — Person enrichment for the two newly qualified 250-cohort companies
(they qualified after enrich had already run; one more pass picks them up).
**P1** — `providerwrites.perform` still has no production caller: the
Authorization machinery is a door with no traffic. Wiring `push.py` through it
is the single largest architectural debt left.
**P2** — `claims` is still not called on the `render.py` CSV path, on approval,
or at generation. Three more places the same guard is absent.


---

# Addendum

## Scaling audit — the quadratic term was already gone

Searched for the traps the addendum names. The result is short because the
work was already done: `push.collect` computes `paused_set` once with a
comment reading "Once, not once per record: this is the quadratic term
otherwise", and `cadence.build` takes it as a parameter for the same reason.
`eligibility.decide` defaults `recs=[rec]` rather than the whole queue. The
`store.load()` calls that remain are CLI entry points and report modules,
which is where they belong.

What is left, measured:

    clients.load() per record in push.collect   0.83 ms   -> 20.5 s at 24,710
    evidence.boilerplate per research item      215 us    -> 21 s at 24,710
    serial research                             55 s each -> 240 HOURS

**Optimising anything other than research concurrency is noise at this
scale.** The boilerplate call was memoised anyway because it was pure and
repeated - `segments.text_of` fell from 542.5us to 54.6us per record - but
that is a ten-times improvement on a term worth twenty seconds against one
worth ten days.

## 24,710 preflight — validated, not processed

No enrichment, no provider calls, no spend:

    rows 24710   non-empty 24710   unique 24710   duplicates 0
    malformed 0  columns ['domain']  distinct TLDs 218
    domain length min 4, p50 15, max 36
    5,000-file nesting claim   VERIFIED (subset, checked rather than trusted)

## Credit efficiency

    credits / input domain          0.6
    credits / qualified account    20.8
    credits / person found          7.5
    credits / verified email       37.4
    credits / campaign ready        n/a  (nothing has reached it)

    company-information-from-domain  145   78%
    decision-makers                   40   22%
    aiark-people-search                2
    apify-research                     0   (unpriced: $0.858 of real compute)

Expected credits only; observed is a separate question and `costs.py` keeps
it separate. The company lookup dominates and is unavoidable - the free tier
qualifies nobody, proven by a zero-cap pass that scored zero of twelve ICP
dimensions across 200 domains.

---

# PROSPEX reference audit

Reviewed `asiifdev/business-leads-ai-automation` (MIT) as a source of
patterns. **It is a Google-Maps scraper plus an LLM copy generator with a
dashboard.** There is no sending, no email verification, no suppression, no
cadence and no reply handling; the entire outreach surface is a
copy-to-clipboard button. So it offers nothing to port for send-safety, and
most of its value here is as a counter-example.

### Adapted

**1. Progress needs a denominator known before the work starts.** Their fix
for progress sitting at 0% derives a percentage from the *plan* - query x
area combinations, capped by `maxResults` - never from the discovered count.
That is the transferable idea, and its corollary is the important half: if
you do not have a denominator, do not show a percent. Recorded for the
progress work; their storage model (a mutable scalar column, no event log,
progress running backwards on a retry) is explicitly not adopted, because
our ledger already holds confirmed events.

**2. Their broken idempotency is worth a test we do not have.** They enqueue
with no `jobId`, so two POSTs start two concurrent jobs on one campaign;
retries re-scrape and rely on `skipDuplicates`, which can never fire because
the migration creates **no unique index on the leads table at all**. Textbook
computed-correctly-consumed-by-nothing. We have reserve/settle and crash
tests, but no test asserting that *re-running a completed stage produces zero
new ledger rows* - which matters, because I re-ran the 250 cohort three times
tonight. Queued as the next implementation.

**3. Rates should carry their own denominator.** Their `conversionRate` is a
pre-formatted string over "every lead ever scraped", so it silently falls as
they scrape more and no consumer can re-base it. Our scorecard rule of
numerator/denominator is the right one and this is a concrete example of the
failure it prevents.

### Worth knowing, not adopted

Their secret handling has one good idea - a `"v1:"` version prefix on
encrypted values so a format change can migrate in place - with a fail-open
flaw: an unprefixed value is returned verbatim. And API keys stored as
`sha256` plus a display prefix, returned in plaintext exactly once, is a
sound shape if we ever expose one.

### What NOT to copy, explicitly

- **Silent synthetic data on provider failure.** When a scrape throws, they
  fabricate leads with invented names, addresses and plausible phone numbers
  and insert them unflagged into the same table, exportable to vCard. A
  fabricated record indistinguishable from a real one is the single worst
  thing in that repository, and it is the exact class our LIVE-READINESS
  vocabulary exists to forbid.
- **Silent mock LLM content** on API error, documented as the intended dev
  path.
- **Tenancy fail-open.** A missing workspace claim resolves to
  `"default-workspace"`, and their campaign update and delete endpoints pass
  no workspace at all.
- A health endpoint that pings only the database and would report `ok` with a
  dead worker.
- A live SQLite database committed to the repository.

### Database question, answered

No migration is needed. At 24,710 domains the binding constraint is 240
hours of serial research, not query patterns over JSONL. The append-only
ledgers (action, spend) are exactly the shape a relational store would be
worst at, and the one genuinely relational question - "which contacts share
an identity" - is already a single batch pass in `dedupe.find`. Revisit if
concurrent writers appear, which is a process-topology decision rather than a
storage one.


---

# Final state

## The funnel now, across all 300 records

```
qualified companies      9
people found            25
2/2 verified sendable    5
linkedin present        25
```

Nine qualified companies where yesterday morning there were none, produced
without loosening a single ICP rule. The two the 250-cohort qualified after
its enrichment pass had already run were picked up by one further pass - 4
records, 51 credits, 57.7 seconds, and the run printed its own stage timings
for the first time.

## Top blockers on the critical path

1. **`providerwrites.perform` has no production caller.** The Authorization
   machinery is a door with no traffic; `push.py` does not go through it.
   Largest architectural debt remaining, and the reason 3a below was possible.
2. **`heyreach.pause` is implemented and not declared supported** - it has
   never succeeded against the provider. Until it does, this system can start
   nothing it can stop, and `stoppability` correctly caps LinkedIn at one.
3. **Research throughput** caps yield: 10 runs per batch, serial, 55s each.
4. **`claims` is still absent** from the `render.py` CSV path, from approval,
   and from generation. Three more places the guard is not wired.
5. **Person enrichment is a second pass**, so a company that qualifies during
   a run gets contacts only on the next one.

## Top remaining attack surfaces

1. An unmatched inbound reply stops nothing at all (PRODUCT-GAPS 41).
2. `cadence.status_for` reads only the record-level pause, so a planning view
   can show a replied contact's step as eligible.
3. The HeyReach webhook branch trusts `eventType` without a direction check;
   unreached today because the poller produces only conversation pages.
4. `claims` self-certification: the model's own `hook` is read back as
   support, guarded only by a one-token overlap check.
5. Four pieces of fixture copy asserted unsupported facts until tonight -
   which suggests the sixth is somewhere nobody has looked yet.

## What became autonomous tonight

- A dry run that genuinely costs nothing, verified against provider counters.
- A spend ceiling that survives a restart, and a cost claim that names its own
  evidence class and refuses to resolve what it cannot.
- LinkedIn copy checked to the same standard as email, on the routine path.
- A re-run that provably buys nothing again.

## What still requires the operator

Unchanged and unblocked by anything I can do: press unpause on 594061, or
grant this environment permission to perform live provider writes. Everything
around that boundary is ready.
