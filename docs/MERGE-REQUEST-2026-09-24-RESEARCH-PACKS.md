# Research packs for tomorrow's UK/EU cohort — merge request

Lane C, 2026-09-24 late evening into 2026-09-25. Branch
`worktree-agent-aea4a82ef07084898`. **Not merged, not pushed.**

Read §1 first. It answers the question the coordinator asked at 23:4x and it
is the only thing here on tomorrow's critical path.

---

## 1. THE 128 CARRY NO FREE-CRAWL RESEARCH AT ALL. THE TWO SETS ARE DISJOINT

The coordinator was told 366 of 394 researched records (93%) would pass
copylint rule 1, and asked the narrower question: how many of the 128 UK/EU
leads going out tomorrow.

**The rate does not transfer, because the intersection is empty.**

    the 153 UK/EU domains  INTERSECT  the 394 researched domains  =  0
    the 153 UK/EU domains  INTERSECT  the 224 local_http domains  =  0
    even the 39 UK/EU domains that DO have a queue record         =  0 researched

Cross-tabulated, not inferred. 568 `local_http` research rows exist in
`work/queue.jsonl` across 224 domains and **not one of them is a domain in
tomorrow's cohort.** This is handoff §8's recurring shape exactly — a
headline from a stage that had not asked the next stage's question — and it
is why the question had to be asked of the leads by name.

### 1.1 Which set is "the 128"

The handoff gives the number and no derivation. Measured against the current
stage files:

| set | leads | domains |
| --- | --- | --- |
| `s7-copy.jsonl` rows | 927 | |
| rendered | 814 | |
| rendered, UK or EU by `s3-icp.jsonl` country | 179 | 153 |
| …and client-approved (all of them are) | 179 | 153 |
| …**that match no queue record at all** | **128** | **114** |
| under `batch1_build`'s own caps (uk 2×45, eu 1×45) | 105 | 92 |

179 − 51 matched = 128. That is the only cut of this data that lands on the
handoff's number, so **"the 128 clean UK/EU leads" are the ones with no
record in the queue** — which also reads sensibly as "clean": not already
worked, not among the 63 stopped. **Stated as an inference.** If the operator
meant a different 128, every table below is also given for the 179 and for
the 105, so the answer can be read off whichever set is meant.

### 1.2 The answer, after tonight's free crawl

Measured with `scripts/researchpack_copylint_gap.py`, which imports
`copylint.pack_text`, `copylint.first_line` and `copylint._WORD` and calls
them rather than describing them — a second copy of the matching would be a
report that agrees with itself and not with the gate.

| set | leads | carry free-crawl **before** tonight | carry free-crawl **now** | **pass rule 1 now** |
| --- | --- | --- | --- | --- |
| the 128 (no queue record) | 128 | **0** | 99 · 77.3% | **72 · 56.2%** |
| under the cohort caps | 105 | **0** | 95 · 90.5% | **77 · 73.3%** |
| all UK/EU rendered | 179 | **0** | 148 · 82.7% | **116 · 64.8%** |

So of the 128: **72 would pass rule 1 today and 56 would still refuse the
push.** Of those 56, **29 have no usable crawled page at all** and the other
27 have one their step-1 opener does not touch.

### 1.3 The gap was seven minutes and no dollars, and it is already closed

`scripts/researchpack_cohort.py --no-cap --sources site_content --live`, run
2026-09-24 23:0xZ over all 153 UK/EU domains:

    153 domains · 116 covered (75.8%) · 277 http requests · 334.2 seconds
    0 Apify runs · 0 ledger rows · $0.00000

Crawler outcomes over the 153: `HTTP_SUCCESS` 115, `HTTP_INSUFFICIENT` 11,
`NON_2XX` 9, `BLOCKED` 7, `JS_RENDERING_REQUIRED` 4, `RESEARCH_FAILED` 4,
`TIMEOUT` 3. **Nothing here needs Apify and nothing here needs a branch
merge** — `src/webfetch.py` is already on master.

The 37 that returned nothing are the residual. They are a mixed bag and only
`JS_RENDERING_REQUIRED` (4) and `BLOCKED` (7) are worth a second attempt at
all; `HTTP_INSUFFICIENT` (11) means the site answered and says too little,
which no amount of re-reading changes.

### 1.4 A WARNING ABOUT WHAT A RULE-1 PASS MEANS HERE

**A pass is not evidence the opener is grounded.** Rule 1 asks whether any
word over four letters in the step-1 opener appears anywhere in the pack
text. A crawled page is a long dump of a site's own prose and navigation, so
a match is easy to come by. Of the 117 leads passing on a crawled pack when
this was measured:

- **54 pass on exactly one distinct word.**
- The single word doing the most work is **`marketing`, in 53 of them.**
  Then `teams` 9, `advertising` 8, `agence` 5, `design` 4, `digital` 3.
- **24 of 117 pass on category words alone** (from a hand-listed set of 26
  such words) and nothing more specific.

That is not a defect in `copylint` — it is what happens when the copy was
rendered by S7 **before any pack existed**, so the opener cannot be
referencing one. The honest reading is that these openers are not grounded
in the research; they merely share vocabulary with it. **The real fix is
re-rendering step 1 from the pack**, which is S7's job and production's
code, not this lane's. Raising rule 1's bar without doing that would simply
refuse the whole cohort.

---

## 2. WHAT WAS BUILT

### 2.1 The operator ruling, made unrepresentable rather than documented

`apify~website-content-crawler` was 72% of the per-account bill — $0.02888
of $0.03987, $566 of the $781.94 a month that all four sources on 19,612
accounts would cost against $199. The operator ruled: site content from our
own free crawler, Apify runs LinkedIn only.

- `src/researchpack/site.py` is new: it wraps `src/webfetch.py`, which
  already existed and which `enrich` already costs at 0 credits.
- The crawler is **deleted** from `actors.ACTORS`, not flagged off. An entry
  with a price and an `enabled: False` beside it is one edit from returning.
  `build_input("site_content", ...)` raises `KeyError` and a test asserts
  that no remaining actor id contains "website" or "crawler".
- `actors.FREE_SOURCES` carries `site_content` with `usd_per_account: 0.0`
  and `provider: local_http`.
- `pack.build` reports it in `free`, never in `bought`, so the coverage
  table and the spend table cannot disagree about the same source.
- `_site_urls` went with it. It guessed `/about`, `/team`, `/careers` and
  handed the list to Apify; `webfetch` reads the homepage's own links and
  never requests a path blind — which is the defect that put two 404 pages'
  navigation text into evidence on the first live crawl.
- The identity question is asked at the point the site fact is made
  (`site.on_this_domain`) rather than inherited from `webfetch.same_domain`.
  "Cannot happen" is what was said about the job rows before 50 of 71 turned
  out to be a different company.

**Apify per account is now $0.01098 planned** — $215 at 19,612 against $199,
rather than $781.94.

### 2.2 The spend ceiling was RECORDED and never CHECKED

`run_actor` wrote a `spendledger` row for every paid call and never called
`spendledger.check`. Productive's declared `per_day: 5000` therefore bounded
nothing on this path: the ledger filled up and the runs kept starting. That
is this repository's own recurring shape — computed correctly, read by
nobody.

- `pack.check_budget` now runs **before** the call and before the record.
- `BudgetExceeded` propagates out of `build`. A caller halts on a ceiling
  rather than being handed a thin pack that reads as a quiet estate.
- An unattributed run is refused outright. `record(client or
  "unattributed", ...)` is gone: `spendledger.check` refuses a falsy client
  by its own contract and that refusal is kept rather than smoothed over.
- The free site read is deliberately **not** subject to a ceiling — a
  ceiling on a call that cannot be billed would stop a pack for a reason
  that does not exist.

**Nothing was widened. No ceiling was raised.** `--budget-usd` on the runner
can only stop a walk sooner than a declared ceiling would.

### 2.3 Four scripts

| script | what it is for |
| --- | --- |
| `scripts/researchpack_cohort.py` | packs for the accounts a push will actually carry, with `--no-cap` and `--sources` for the free pass |
| `scripts/researchpack_copylint_gap.py` | §1: rule 1 asked of the leads themselves, per set, with the denominator every time |
| `scripts/researchpack_ledger_slice.py` | what a run committed, selected on `at` rather than on `day` |
| `scripts/researchpack_reconstruct.py` | the report rebuilt from the ledger, Apify's run records and the cache, after the walk was killed |

---

## 3. DOLLARS SPENT, WITH THE LEDGER ROWS THAT PROVE IT

### 3.1 What was committed — `work/spend-ledger.jsonl`

`py -3 scripts/researchpack_ledger_slice.py --since 2026-09-24T21:50:00+00:00`

    133 row(s), 200 credit(s)
      apify  open_roles      67 row(s)   134 credit(s)
      apify  person_posts    65 row(s)    65 credit(s)
      apify  company_posts    1 row(s)     1 credit(s)

    first {"at": "2026-09-24T21:52:04+00:00", "day": "2026-09-24",
           "client": "productive", "provider": "apify", "call": "open_roles",
           "expected_cost": 2, "run_id": null}
    last  {"at": "2026-09-24T23:01:03+00:00", "day": "2026-09-24",
           "client": "productive", "provider": "apify", "call": "open_roles",
           "expected_cost": 2, "run_id": null}

Every paid call is one of those rows. **No Apify run in this lane was made
outside the ledger**, and none was made without `check_budget` first.

The free crawl over 153 domains wrote **zero** rows, because it bought
nothing. A zero-cost row for a provider that cannot charge would make the
next audit reconcile against an invoice with no line for it, and a test
asserts there is none.

### 3.2 What was billed — Apify's own run records

Not the ledger's rounded cents and not a projection: `usageTotalUsd` on each
run, from `GET /v2/actor-runs` filtered on `startedAt`.

| actor | runs | status | billed | per account |
| --- | --- | --- | --- | --- |
| `harvestapi/linkedin-profile-posts` | 65 | 65 SUCCEEDED | $0.28275 | $0.00435 |
| `bebity/linkedin-jobs-scraper` | 66 | 66 SUCCEEDED | $0.05170 | $0.00080 |
| `harvestapi/linkedin-company-posts` | 1 | 1 SUCCEEDED | $0.00530 | $0.00008 |
| `apify~website-content-crawler` | **0** | — | **$0.00000** | **$0.00000** |
| **TOTAL** | **132** | 132 SUCCEEDED | **$0.33975** | **$0.00523** |

Over the 65 accounts the walk reached. **$0.00523 per account against the
pilot's $0.03987** — the site crawl is gone and the LinkedIn half came in
under its own planned figure too.

200 credits committed against $0.33975 billed is the ledger's round-up
working as designed: `planned_cost` rounds a sub-cent call UP to one cent,
which overstates and therefore fails closed.

### 3.3 Against the ceilings

    per_day                5000     committed today at the start   2125
    per_run                2000     committed by this lane          200
    per_provider_per_day   none declared
    total                 50000

Read before anything was bought, printed by the runner, and never near. **No
ceiling refused anything, and none was raised.**

---

## 4. COVERAGE PER SOURCE

### 4.1 The Apify walk — 65 accounts of the 92-account capped cohort

| source | billed by | covered | of 65 | facts | $ per covered account |
| --- | --- | --- | --- | --- | --- |
| `site_content` | **ours** | 51 | **78.5%** | 119 | **$0.00000** |
| `person_posts` | apify | 53 | **81.5%** | 134 | $0.00534 |
| `open_roles` | apify | 1 | **1.5%** | 1 | $0.05170 |
| `company_posts` | apify | 1 | **1.5%** | 3 | $0.00530 |
| **any fact at all** | | **62** | **95.4%** | | |

### 4.2 The finding in that table: `open_roles` bought 66 runs and covered 1 account

The pilot measured `open_roles` at 12.5% post-fix on 24 US-heavy accounts.
On this UK/EU cohort it is **1 of 65**. 66 runs billed $0.05170 — about
$0.00078 each, which is the start fee and almost no items, so most returned
**no rows at all**. These are small agencies and they are not posting jobs
on LinkedIn.

That matters more than its own coverage, because `open_roles` is **the only
source of the LinkedIn company slug**, which is what makes `company_posts`
addressable. One slug came out, so `company_posts` covered one account.

**The operator's question from the pilot now has a second data point: the
jobs actor can supply the slug, and on this cohort it does so for 1 account
in 65.** The opt-in resolver `harvestapi/linkedin-company` reached 50% on
the pilot at $0.00238 per account — **$0.22 for these 92**. It was **not**
turned on: it is a cost the operator did not ask for, `actors.py` marks it
opt-in for that reason, and a fallback that turns itself on is a cost
nobody chose. It is one flag and the price is stated.

### 4.3 The free crawl — all 153 UK/EU domains

    116 of 153 covered (75.8%) · 277 requests · 334.2 seconds · $0.00000

`site_content` is now both the widest source and the only free one. On the
cohort that matters it covers more accounts than every paid source except
`person_posts`, and it costs nothing.

---

## 5. WHAT I REFUSED TO WIDEN

- **No declared ceiling was raised**, and the runner cannot raise one:
  `--budget-usd` only stops a walk sooner. The `per_day` of 5,000 was read
  and printed before the first call.
- **The company-identity guard was not weakened.** `actors.is_this_company`
  is byte-identical to the commit that introduced it, still applied to both
  the slug and the facts, still fail-closed with no domain. The same
  question is now asked of site pages too.
- **`src/providers/apify.py` was not edited.** Lane C is under a standing
  instruction not to; the file is adopted byte-identical from
  `researchpack-four-sources-2026-09-24` (`git diff --cached <branch> --
  src/providers/apify.py` is empty) and not one line in it is mine.
- **The pre-fix pilot cache was not served.**
  `researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json` was not read, and
  neither was the shared `work/research-pack-cache.json`. This lane's runs
  use caches named for themselves.
- **`tests/test_nothing_writes_to_a_provider` was not relaxed.** It reported
  `('scripts/researchpack_cohort.py', 'DYNAMIC')` because its scanner strips
  docstrings and comments but not ordinary strings, so a print reading
  `"%d request(s)"` is indistinguishable from `request(verb, url)`. Nothing
  was added to `ALLOWED` — that would have declared a write the file does
  not make. The print was reworded. **The scanner limitation is real and is
  recorded here rather than fixed**, because a guard that is blunt about a
  verb it cannot read is the right guard.
- **No EmailBison call, no HeyReach call, no write to `work/queue.jsonl` or
  `work/campaigns.jsonl`.** Every file this lane wrote in `work/` is new and
  named for this lane, except `work/spend-ledger.jsonl`, which is
  append-only and which every paid call is required to reach.

---

## 6. TESTS

`tests/test_researchpack.py` — the cassette suite, plus two new classes.

**Verified by breaking the guards, not by watching them pass:**

- Removing `check_budget` from `run_actor` turns exactly the five
  `TheCeilingIsCHECKEDAndNotOnlyRECORDED` tests red, each with
  "BudgetExceeded not raised" rather than because some other guard fired
  first. Restored, green again.
- Neutering `site.on_this_domain` turns exactly one test red,
  `test_a_page_off_this_domain_makes_no_fact`. Restored, green again.

**WHAT THE SITE TESTS PROVE AND WHAT THEY DO NOT.** The page rows in them are
built by `webfetch._page` itself on real markup, so the fields
`site.research` reads are the fields the crawler writes. The **envelope** —
`outcome`, `pages`, `stats` — is a double, and a double cannot prove the
crawler returns that shape. What proves it is §1.3 and §4.3: 153 real
domains read live through `webfetch.research`, with the classification of
each one reported. That is stated in the test file itself rather than left
for a reader to discover.

---

## 7. WHAT REMAINS UNVERIFIED

1. **27 of the 92 capped accounts have no Apify pass.** The walk was killed
   by the harness at 65, exactly as the pilot was killed at 24 of 25.
   Finishing them is about $0.14 and 12 minutes. Their site content is
   already read — the free pass covered all 153 domains.
2. **"The 128" is an inference**, derived in §1.1 and reproducible, but the
   handoff states the number without a derivation. If a different 128 is
   meant, §1.2 carries the 105 and the 179 as well.
3. **Rule 1 passing is not rule 1 being satisfied in spirit** — §1.4. 24 of
   117 passes rest on category words alone and 54 on a single word. Nothing
   here re-renders a single opener, and until S7 renders step 1 from a pack
   the grounding is coincidental.
4. **The other five copylint rules were not measured** on this cohort. Only
   rule 1 was asked. `empty_step` in particular will fire on every one of
   these leads until em4/em5 are rendered — the half-applied cadence in the
   late handoff §2 — and that is a different blocker with a different owner.
5. **`bisonfactory.stage`'s copylint wiring was not read.** The coordinator
   reports it is on the send path. This lane measured the rule, not the
   wiring, and takes the wiring on report.
6. **The 30-day cache TTL is still untested against reality**, unchanged
   from the pilot. Nothing has yet been re-bought after expiry.
7. **`person_posts` coverage is bounded by the estate, not the actor.** 54
   of the 92 capped accounts carry a champion profile and 38 an exec's;
   where a profile URL exists the actor found posts on about two thirds.
8. **Site coverage is this estate's.** 75.8% on 153 UK/EU agency sites is not
   a web-wide rate, and `HTTP_INSUFFICIENT` (11) is a real property of small
   agency sites rather than a crawler failure.

---

## 8. FILES

    src/researchpack/site.py            new - the free site source
    src/researchpack/actors.py          the crawler deleted; FREE_SOURCES; SOURCES
    src/researchpack/pack.py            check_budget; take_site; free/site in the pack
    src/researchpack/__init__.py        exports
    tests/test_researchpack.py          65 tests, two new classes
    scripts/researchpack_cohort.py      new
    scripts/researchpack_copylint_gap.py new
    scripts/researchpack_ledger_slice.py new
    scripts/researchpack_reconstruct.py new
    docs/RESEARCH-PACK-PILOT-2026-09-24.md   adopted from lane 1, unchanged

Adopted byte-identical from `researchpack-four-sources-2026-09-24` and NOT
authored here: `src/providers/apify.py`, `tests/fixtures/cassettes/00-researchpack.json`,
`scripts/researchpack_pilot.py`, `scripts/capture_researchpack.py`,
`docs/RESEARCH-PACK-PILOT-2026-09-24.md`.

Deliberately not taken from that branch, because they belong to other lanes:
`src/replyreconcile.py` and its test, `scripts/bison_watch_loop.py`, the
reply-reconciliation merge request, and `docs/state/PROBLEM-REGISTER.md`
(its rows there renumber against master's).
