# MERGE REQUEST — the batch pipeline, 2026-09-25

**Lane S.** Branch `worktree-agent-a34cc988dda35ca26`, rebased onto master
(43 commits behind when it started; the rebase is what brought `per_day`
15,000 into this worktree at all). Four new files, **no existing file
changed**, so the regression surface is zero.

```
src/batchpipeline.py                                    the manifest, the
                                                        denominators, the
                                                        budget, the progress
                                                        block
scripts/batch_pipeline.py                               plan / run / progress
                                                        / budget
tests/test_a_batch_is_not_through_a_stage_that_returned_nothing.py   39 tests
scratch/mutate_batchpipeline.py                         10 mutations, each
                                                        asserted against the
                                                        test that must catch it
```

---

## THE HEADLINE, AND IT CHANGES TONIGHT'S PLAN

**Today's per-day credit headroom is 635, not 15,000.** The ledger carries
18,809 credits committed lifetime and **14,365 of those were committed
today**, against a `per_day` of 15,000. The lifetime remainder of 31,191 in
the brief is right; the daily one was never stated and it is the ceiling that
binds first.

A 1,000-contact batch needs ~2,000 verification credits. **No batch can
verify tonight.** `size_against_ledger` puts batch 1 at 317 affordable
addresses of its 1,000, and that number is reported rather than rounded up.
The ceiling is not raised.

This is moot for tonight in any case, because **CheapVerifier is not live** —
`src/providers/cheapverifier.py` does not import. Lane Q owns it. The
verification stage is a **seam**, and it reports `blocked` naming what it
waits on. It does **not** fall back to the ContactOut-first order: that order
still works and would have produced a green stage and a real number, and the
operator said not to spend the raised ceiling on it. A stage that quietly
bought the declined order would look identical in every report to one that
bought the chosen order, and the money would be gone either way.

---

## WHAT RAN, AND AGAINST WHICH DENOMINATOR

Every percentage below names what it is a percentage **of**. The manifest
stores the denominator's **name and its value** on every stage, and
`record_stage` refuses to write a percentage whose denominator is unknown.

### The file

| quantity | count | what it counts |
|---|---|---|
| contacts | **12,407** | one row is one person at one company |
| company domains | **10,418** | distinct `domain` across the rows |
| email domains | **10,418** | distinct `mx.email_domain(email)` — identical to the company domains on this file, checked rather than assumed |
| addresses | **12,407** | distinct `email` |
| rows carrying an address | **12,407** | all of them |

### Batch 1 — `US East / Marketing & Advertising / economic_buyer`

1,000 contacts, 981 company domains, 981 email domains, 1,000 addresses.

| stage | status | through | denominator | % |
|---|---|---|---|---|
| qualification | done | 1,000 | contacts_in_batch (1,000) | 100.0 |
| mx | **done** | 978 | email_domains_in_batch (981) | 99.7 |
| discovery | **skipped** | 0 | contacts_missing_address (0) | — |
| verification | **blocked** | 0 | addresses_in_batch (1,000) | 0.0 |
| packs | done | 612 | company_domains_in_batch (981) | 62.4 |
| render | blocked | 0 | contacts_verified (unknown) | — |
| lint | blocked | 0 | contacts_rendered (unknown) | — |
| cohort | blocked | 0 | contacts_linted (unknown) | — |
| push | blocked | 0 | contacts_cohorted (unknown) | — |

- **qualification is a re-read, not a re-judge.** This file is
  qualification's output — the rows are what survived the 09-07 approval
  snapshot and four exclusions. The stage counts rows carrying
  `provenance.approval_snapshot` and says so in `counted_from`. A row without
  one is not silently passed; it is not counted.
- **mx is real work and it is free.** 978 of 981 email domains reached a
  decision over live DNS in 44 seconds. **925 of the 978 permit the email
  channel** (`known_allowed` or `unknown_provider`). `dns_failure` is HELD —
  we could not ask, which is not the same fact as nobody accepting mail.
- **discovery is skipped and the reason is measured.** 0 of 1,000 rows lack
  an address. At 2.81 credits/domain, buying it would be pure waste. `skipped`
  is its own word so nobody later reads it as work that happened.
- **credits spent this batch: 0. Apify runs: 0. Dollars: $0.00.**

### Progress block, emitted from the manifests

`bp.progress(file_slug)` is a function the foreground session can call; the
CLI prints exactly what it returns. Nothing recomputes a count for a report,
so the report cannot drift from what happened.

`pushed` and `sent` are **null**, and null is not zero — it means nobody has
read them back from the provider. Our own counters never populate them.

---

## THE ETA

**Throughput ETA: NOT MEASURABLE, and that is the correct answer.**

Timing MX and qualification — the two free, quick stages — and dividing gives
"the file finishes in six minutes". It is arithmetically correct and
completely false, because every paid stage is waiting on an adapter that does
not exist. `eta_for_file` now refuses outright while **any stage is
BLOCKED**, and lists what each is blocked on. Blocked is not the same as
unmeasured: unmeasured means we have not timed it, blocked means we know it
cannot start and we know it is on the critical path.

**Funding ETA: measurable, and it is the one that binds.**

| | |
|---|---|
| addresses outstanding | 12,407 |
| credits per address **asked** | 2.00 |
| credits needed | **24,814** |
| left today | 635 |
| left lifetime | 31,191 |
| days of budget needed | **3** |
| lifetime ceiling covers it | **YES**, margin **6,377** |

The 5.17 figure in circulation is credits per **sendable** address (lane N:
7,182 asked → 2,774 sendable). Reserving against it would under-reserve by
2.6x, because the ledger is charged for every address asked and not only for
the ones that answer well. The planner reserves against **asked**.

---

## FINDINGS

### 1. The union pack cache is keyed `<domain>::<profile>`, and a naive lookup finds nothing

The cache holds 6,667 entries, every one profile `site_content`. A lookup on
the bare domain matches **zero**. Indexed by each entry's own `domain` field
instead:

- **6,186 of 10,418 company domains (59.4%) already have a pack**
- **7,555 of 12,407 rows (60.9%) sit on a covered domain**
- 4,232 domains still need a crawl

A packs stage that had trusted the bare-domain lookup would have reported 0%
coverage and re-crawled 6,186 domains that were already paid for. The stage
indexes by the `domain` field, which is the only reading that survives a key
format change.

### 2. The worktree hazard is a *spending* hazard — `LedgerNotCredible`

`spendledger.path()` derives from `store.queue_path()`; `work/` is
gitignored; so **every git worktree carries its own empty spend ledger**. A
paid stage run from one reads `spent_today = 0`, `spent_total = 0` and
believes the whole `per_day` and the whole lifetime total are free — and
`spendledger.check`, the only thing enforcing `per_day` across processes,
agrees with it, because it is reading the same empty file.

Measured in this worktree today: real ledger 18,809 committed / 14,365 today
/ **635 left**. The worktree's own ledger: nothing, and **15,000 apparently
available**.

`require_credible_ledger` now refuses paid sizing when the ledger carries no
rows for a client that declares a ceiling. It is deliberately crude — it does
not try to work out which workspace is production, because a process that
guessed wrong would be exactly as dangerous as one that did not check.

### 3. Homogeneous slicing gives **41 batches, not 13** — and a tail that cannot be a cohort

The brief's 13 comes from 12,407 ÷ 1,000. Slicing homogeneously on (geo zone,
industry group, persona) gives 41, because a slice smaller than 1,000 is its
own batch rather than one padded from the next slice — which is the entire
point.

The credit total does not change (the address count is the same), but the
**operational** count does, and the tail is a problem to decide before it is
run:

- 18 batches carry **≥ 300** contacts — these map cleanly onto cohorts
- **22 batches carry ≤ 50 contacts, and 15 of those carry fewer than 5**

(Counted from the 41 written manifests, not from the planner's own return —
the first draft of this document said 19 / 15 / 10 from a scratch script and
was wrong on all three. The manifests are what the code actually produced.)

PRODUCTION-SCALE-POLICY says a campaign is a COHORT and never a person. A
one-contact batch is a campaign per person. **These need an operator
decision**: hold the tail, or merge it on a named dimension (the obvious one
is persona, collapsing `champion` and `economic_buyer` within a zone). They
are planned and manifested; none of them should be run as a cohort as they
stand.

### 4. Geo: 1,975 rows cannot be zoned, and 67 do not look US at all

`geo.resolve` places a row from its CITIES table, which this supplier's
location text often defeats — "Dallas-Fort Worth Metroplex", "Greater Tampa
Bay Area", and 585 rows that say only "United States". Extracting the US
**state** on whole tokens first (never substrings — a substring test puts a
New Yorker in the Central zone) lifts placement from 4,294 to 10,365 rows.

| zone | rows |
|---|---|
| US East | 4,794 |
| US West | 3,317 |
| US Central | 2,254 |
| **US Unzoned** | **1,975** |
| **Non-US suspect** | **67** |
| total | 12,407 |

(Summed from the 41 manifests. 4,794 + 3,317 + 2,254 = 10,365 placed.)

`US Unzoned` is its own slice and is **never merged into a placed one** —
folding "United States" with no city and no state into US East to tidy the
batches would put people three time zones away into a cohort whose send
window was chosen for them.

`Non-US suspect` is 67 rows in a file classified as US whose location text
resolves confidently elsewhere. Either the supplier's US classification is
wrong on them or a city name is ambiguous across two countries. Held out and
reported rather than reassigned.

### 5. `--max-credits` on `stage_s5_verify.py` is not bounded downward

Its comment says "unless overridden DOWNWARD on the command line", and
nothing enforces the direction: `--max-credits 50000` is honoured and
silently replaces the declared `per_run` of 2,000. Lane N's file, not edited
here, reported rather than changed. The reservation logic itself is sound —
it reserves `PER_ADDRESS_ESTIMATE` under a lock **before** asking, which is
what fixed the 2,044-against-2,000 overshoot.

### 6. The mutation harness was reporting the wrong guard

Mutations written milliseconds apart defeated CPython's `.pyc` staleness
check (source mtime and size, and Windows timestamps are coarser than that),
so a run re-imported the **previous** mutation's bytecode. M8 was reported as
caught by M7's test and read as a pass. Found by applying M8 by hand and
seeing a different test fail. The harness now runs with `-B`, clears
`__pycache__`, and **asserts which test must catch each mutation** — "something
went red" is not evidence that a guard is tested.

---

## THE GUARDS, AND THE PROOF THEY WORK

Three refusals in `record_stage`, each one a failure this estate has
committed:

1. **A stage that attempted work and produced nothing cannot be `done`.** It
   is `empty`, it is flagged in the progress block, and `percent_through`
   never counts it. Batch 1's first dry run recorded `mx` as `empty` — 0 of
   981 — exactly as it should, because the dry run counts from a cache the
   worktree had never filled.
2. **A percentage cannot be written against a denominator nobody named**, or
   one whose value is unknown. `render` is measured against
   `contacts_verified`, which is unknown until verification runs, so render
   cannot be reported as "0%" of anything.
3. **A stage cannot produce more than its denominator.** When it appears to,
   the two numbers are counting different things and the report is already
   wrong.

Plus: a mixed batch is refused; `counted_from` is mandatory for any non-zero
count and names what was **read back**; and an ETA refuses while anything is
blocked.

**39 tests. 10 mutations, all 10 caught by the intended test.** Re-run the
check with `py -3 scratch/mutate_batchpipeline.py` rather than believing this
paragraph.

---

## REDACTION

This document and the manifest were self-tested **after** writing, against
**every value in all 12,407 source rows** — not against a pattern.

- **Manifest: 0 leaks.** 19 whole-token name matches, every one an ordinary
  English word in the manifest's own prose (`group` inside `industry_group`,
  `advertising` inside the slice label, `this`, `cache`, `rows`).
- **Structural check: 0 problems.** The stronger argument: the manifest is
  walked and every string in it proved to come from a closed vocabulary the
  code owns, or from a field explicitly allowed to carry prose or a filename.
  A field the format grows later and nobody adds to the allowlist **fails**
  this check rather than passing it.

The filter reports two verdicts because there are two questions. An address,
a domain or a profile URL in an artefact is a `LEAK` and there is no innocent
reading of it. A person's or company's **name** matched as a whole token is
`REVIEW`: string search genuinely cannot tell a leaked surname from the same
letters used as an English word, and claiming otherwise in either direction
is worse than saying so.

**The filter was proved to still catch a leak**, by planting real values from
the source into a copy of the manifest: a planted address produced 3 LEAK
findings, a planted domain 1, a planted profile URL 1, and a planted company
name moved the REVIEW count. A planted identifier in a manifest field, and in
a field invented for the test, were both caught structurally.

Membership lives in `work/batches/<file>/members/<n>.jsonl`, gitignored. The
manifest names the file and never its contents.

---

## WHAT THE FOREGROUND SESSION OWNS

**No provider write happened here and none can.** `push` is declared as a
stage so a batch can be held AT it and reported as waiting. Performing it —
push, enrolment, activation — belongs to the foreground session, after five
samples and a 15-minute veto, every batch, every time.

The gates that stay are carried on every manifest as named, unset fields:
full-sweep empty render (never a sample — it caught 31% of a batch with no
subject and no body today), post-attach readback, bounce hard stop, the
account rule, provider-confirmed numbers, and the five-sample veto.

---

## NEXT

1. **An operator decision on the 15-batch tail.** Hold, or merge on a named
   dimension. Do not run a one-contact cohort.
2. **Verification unblocks when lane Q lands `cheapverifier.py`.** The seam
   asks the module for `check()`; nothing else needs changing here, and the
   call itself belongs in `stage_s5_verify.py`, which already reserves before
   it asks.
3. **Budget: batch 1 can verify 317 addresses today at most.** Tomorrow's
   15,000 covers seven batches; the file needs three days of budget and
   finishes with 6,377 of lifetime margin. Nothing here raises a ceiling.
4. **MX can run free on every batch tonight**, ahead of verification. It is
   ~45 seconds per 1,000-contact batch and it shrinks what verification has
   to be bought for.
