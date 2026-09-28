# ~30K POOL SUPPLY — A BOUNDED 500-RECORD SAMPLE

**Operator instruction, Zvonimir, 2026-09-28. NOT STARTED. Needs one explicit
`APPROVED` before anything runs.**

**DO NOT START UNTIL THE P0-C ARTIFACT IS POSTED.** This sits behind the
critical path (P0-B → P0-C Brand IQ matrix → TASK-425 rerun → operator review)
and must never be in front of it.

## The question this answers

**Is the ten-account test blocked by a SUPPLY problem or a PIPELINE problem?**

Measured 2026-09-28, `qualify.state_of` over all 1,582 production records
grouped by batch:

    24k staging track       554 records    0 qualified
    two 09-21 batches       477 records    0 qualified
    intake 00000-00250      250 records    0 qualified
    three pilot batches     300 records  113 qualified

**The large sources have zero qualified records because nothing was ever run on
them, not because they were rejected.** Every account that can license a claim
today comes from 300 pilot records. Until a sample is actually put through the
pipeline, "the estate cannot supply ten accounts with 2-3 decision makers" is a
statement about what we have processed, not about what exists.

## The run

**A seeded random sample of 500 from the ~30k source file, through the NORMAL
pipeline.** Seeded so the selection is reproducible and cannot be re-rolled to
a friendlier answer. Nothing bespoke: the same ingest, ICP qualification,
research and persona classification production uses.

**Hard spend cap: USD 25.** See the cost section — the cap must be enforced as
a **unit** cap, because the ledger cannot enforce a dollar one.

## What it reports — COUNT / REASON / AUTHORITY / STATE per transition

    source domains in file          COUNT  AUTHORITY  the source file itself
    parsed / valid                  COUNT  REASON     per rejection reason
    deduplicated                    COUNT  REASON     against the existing estate
    ICP prefilter                   COUNT  REASON     per exclusion reason
    eligible for research           COUNT  REASON
    researched                      COUNT  REASON     free crawler vs paid leg
    qualified                       COUNT  AUTHORITY  qualify.state_of
    tier A / tier B / tier C        COUNT  AUTHORITY  icp.score
    decision-maker capacity         COUNT  AUTHORITY  routing.DEFAULT_CAPS

**Every transition names the authority that produced its number**, and every
drop names its reason. A funnel with an unexplained step is not a funnel.

**The tier split is the actual deliverable.** All 64 currently qualified
records with research are **tier C**, and tier C licenses **one** decision
maker — which is why zero accounts can offer 2-3. If the sample produces tier A
or B, the ten-account test is a supply problem we can solve by processing more.
If 500 fresh records are also all tier C, it is a **pipeline problem** — the
scoring or the evidence depth, not the source — and processing more would not
have helped.

## COST ESTIMATE — and an honest problem with it

**Measured inputs, not assumptions:**

- **ICP qualification costs ZERO.** Measured on TASK-430 across 665 companies:
  the classifier is deterministic code, no model call.
- **The free crawler covers most research.** Of 394 records carrying research
  today, **220 (55.8%) used the free `local_http` crawler ONLY** and **174
  (44.2%) needed a paid leg** — every paid one being `apify`.
- So 500 records project to roughly **220 paid research calls**, at the
  ledger's `apify / site_content` rate of ~2 units per call and
  `apify / open_roles` at 2 — on the order of **450-900 apify units**.

**⚠ THE LEDGER CANNOT CONVERT THAT TO DOLLARS, AND THAT IS ITS OWN FINDING.**
`work/spend-ledger.jsonl` records `expected_cost` in **provider-native units,
not USD** — `deliverable-verify` at 1.0, `contactout / decision-makers` at 10,
`glm / complete` at 10,209.5 (tokens). Summing the column yields "39,228 USD",
which is plainly not money. **Only 2 of 17,939 rows carry `usd_estimate`,
`rate` and `rate_source`.**

So the USD 25 cap **cannot be enforced or verified from the ledger as it
stands.** Two options, and the operator should pick one as part of approving:

1. **Enforce the cap in units**, converting USD 25 through the apify rate card
   once, and record that rate with its source on every row of this run — which
   is what `rate`/`rate_source` exist for and what 2 rows already do.
2. **Fix the ledger first** so `usd_estimate` is populated for every paid call.
   Correct, and it is a separate task that would delay this one.

**Recommendation: option 1 for this run, and file option 2 as its own task.**
A run that stops at a measured unit ceiling is genuinely bounded; a run that
claims a dollar ceiling it cannot measure is not.

## Hard constraints

- **PROVIDER WRITES = 0.** Research reads; nothing is staged, enrolled or sent.
  `sending.live` stays false, the freeze stands.
- **Company first.** No paid person-level call before a company reaches an
  explicit ICP verdict — rejected, review and unknown all mean zero person
  credits.
- **Every paid call goes through `enrich.spend()`** so it reaches the ledger. A
  provider call that skips it is invisible to the audit.
- **Stop at the cap**, and report the funnel truncated rather than overrunning.
- Back up `work/queue.jsonl` first; verify every write from a fresh process.
- **Do not widen any gate to improve the funnel.** A disappointing funnel is
  the answer, not a problem with the measurement.

## What approval is being asked for

**One `APPROVED`** covering: the seeded 500-record sample, the normal pipeline,
a spend ceiling enforced in units equivalent to USD 25 at a recorded rate, and
the funnel report above. Nothing in this brief sends anything to anybody.
