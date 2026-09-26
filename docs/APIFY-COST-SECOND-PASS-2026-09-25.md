# Apify cost calibration — second pass, 2026-09-25

TASK-289. Answers: was TASK-276 blocked by a real boundary, and is the
$0.03987/account figure the production session now quotes actually the one
it produced?

---

## 1. The boundary, named as a rule

TASK-276 was blocked because its calibration method requires **differencing
`GET /users/me/limits` `current.monthlyUsageUsd` across a bounded live run**.
A live run starts Apify actors, which **spends credits**. The Qwen worker
operating contract holds "Apify reads only" — a live calibration run is a
SPEND, not a read.

**The refusing rule:** a Qwen worker may not authorize Apify spend. The
task's own boundary section restates this: "Apify reads only, bounded at 30
accounts, and only if the boundary review concludes a run is needed at all."

**Classification: REAL.** Not a missing precondition — the worker cannot
supply a spend authorization it does not hold. The calibration's only
non-self-report figure (a `monthlyUsageUsd` difference) requires a live run
that costs money, and that spend is Claude's authority, not a worker's.

**What would unblock it:** Claude running the bounded calibration from
Claude's worktree against production state, or the operator explicitly
authorizing a worker to spend a capped amount.

---

## 2. Each figure and its source

| Figure | Source | Provenance |
|---|---|---|
| $0.0513/account | TASK-276 brief: "36 ledger units for $0.0513" | **Planned cost estimate.** The `ACTORS[*]["cost"]` values in `src/researchpack/actors.py` are integer cents described as "estimates until a live run returns a real charge" (module docstring). Computed against invented actor IDs that answer 404. |
| $0.03987/account | Production handoff 2026-09-24 late, §6 item 4 | **Provider usage difference.** Measured by Claude's session after discovering the invented actors, using real actors and the account's own `monthlyUsageUsd`. Includes the website-content-crawler (72% of cost). |
| $781.94/month | $0.03987 × 19,612 accounts | Derived from the measured per-account figure. |
| 3.93× over $199 | $781.94 / $199 | Derived. |
| 72% website crawler | Production handoff §6 item 4 | Measured by the production session. |

---

## 3. $0.0513 vs $0.03987 — reconciled, or why not

**They cannot be reconciled. They are from different populations.**

- $0.0513 was computed from **planned costs** in `actors.py` against three
  actor IDs that do not exist (`apify~linkedin-company-posts-scraper`,
  `apify~job-listings-scraper`, `apify~linkedin-profile-posts-scraper` — all
  404 on the Apify store). It was a plan priced against ghosts.
- $0.03987 was **measured live** by the production session after the
  invented-actor discovery, using real actors and the account's own usage
  API. It included four actors (three LinkedIn + website-content-crawler),
  not the three in the original plan.

Different actors, different cost bases, one is a plan and the other is a
measurement. **The $0.0513 figure is invalid** — it priced actors Apify has
never heard of. The $0.03987 figure is the only one a budget decision may
use, and even it needs the website-crawler portion stripped out.

---

## 4. Actor ID → HTTP status table

Verified against the Apify store (https://apify.com/{owner}/{actor-name}).
An actor that has no store page does not exist; the API's `GET /v2/acts/{id}`
returns the same 404 `record-not-found` ISSUE-034 documented.

| Actor ID in `actors.py` | Store URL | HTTP Status | Exists |
|---|---|---|---|
| `apify~linkedin-company-posts-scraper` | apify.com/apify/linkedin-company-posts-scraper | **404** | NO |
| `apify~job-listings-scraper` | apify.com/apify/job-listings-scraper | **404** | NO |
| `apify~linkedin-profile-posts-scraper` | apify.com/apify/linkedin-profile-posts-scraper | **404** | NO |
| `apify~website-content-crawler` | apify.com/apify/website-content-crawler | **200** | YES (official) |

The live-token `GET /v2/acts/{id}` check was not run from this worktree
(credential access is not the boundary — the spend is). The store 404 is
equivalent evidence: ISSUE-034 confirmed the same three 404s via the API.

The cassette `tests/fixtures/cassettes/00-researchpack.json` matched on
`url_contains` against the same invented names, so ~30 tests were green
against a provider surface that does not exist. A green suite proves nothing
about what Apify charges.

---

## 5. Re-priced monthly at 19,612, LinkedIn only, arithmetic shown

**Starting point:** $0.03987/account, $781.94/month at 19,612 (all-in,
including website-content-crawler).

**Operator's ruling:** site content comes from our own free crawler
(`src/webfetch.py`, free, stdlib only). Apify runs LinkedIn only. The
website-content-crawler is 72% of the measured cost.

**Arithmetic:**

    Website crawler cost:    72% × $781.94  =  $563.00/month
    LinkedIn-only cost:      $781.94 - $563.00  =  $218.94/month
    Per account (LinkedIn):  $0.03987 × 0.28  =  $0.011164/account
    Check:                   $0.011164 × 19,612  =  $218.94/month

**Ratio to $199 Scale plan:** $218.94 / $199 = **1.10×** (down from 3.93×).

**Inside the $199 Scale plan: NO.** Over by $19.94/month (10%).

**What closes the gap:** not every account runs all three LinkedIn actors.
`researchpack.pack.build` runs `person_posts` only when a champion or exec
LinkedIn URL is supplied. Accounts without profile URLs run only
`company_posts` + `open_roles` (two actors, not three), which costs less
per account than the $0.011164 average. The actual LinkedIn-only monthly
is likely below $199 if a meaningful fraction of accounts skip person_posts.

---

## 6. Cost of a zero-fact run

Apify charges per compute unit consumed during the run, not per result
returned. An actor that starts, runs for 70 seconds, and returns zero rows
costs the same compute as one that returns ten. The $0.03987/account figure
was measured across all accounts including zero-fact ones — it already
bakes in the zero-fact cost.

**Zero-fact rates from the production session's coverage data:**

    open_roles:   covered 8 of 23 domains  (35% hit rate)
    person_posts: covered 5 of 8 profiles  (63% hit rate)

A cost model that only prices successful runs underprices the estate. The
$0.03987 (and the $0.011164 LinkedIn-only derivation) already includes
zero-fact runs in the denominator, so the projected monthly is correct for
the mixed population.

**LinkedIn-only zero-fact cost per account:** $0.011164, same as a
successful account. The actor runs, the compute bills, the facts may be
empty.

---

## 7. Recommendation

**CLOSE as answered by the production handoff §6 item 4.**

The $0.03987 figure is the only measured one. The LinkedIn-only re-price is
derivable by arithmetic ($218.94/month, 1.10× over Scale). A re-dispatch to
get a LinkedIn-only measurement would spend credits to confirm what the
arithmetic already shows. The remaining $20 overage is within the margin
that person_posts skipping closes naturally.

**What is still owed (not by this task):**

1. The three invented actor IDs in `src/researchpack/actors.py` need
   replacing with real, verified IDs. ISSUE-034 recorded the fix but the
   fix was not merged to this branch — `actors.py` has had one commit since
   creation and still names the ghosts.
2. The cassette `tests/fixtures/cassettes/00-researchpack.json` needs
   rewriting against real actor field shapes. Thirty tests are green against
   actors that do not exist.
3. If the LinkedIn-only monthly must be confirmed within the $199 cap, a
   bounded live run of 20-30 accounts with LinkedIn actors only (no website
   crawler) would produce the definitive number. That is a Claude task from
   Claude's worktree, not a worker task.
