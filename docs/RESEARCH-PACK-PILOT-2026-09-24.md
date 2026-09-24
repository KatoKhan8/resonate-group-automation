# Research packs on four sources: the actors, the widening, and what a bounded pilot measured

Lane 1, 2026-09-24. Operator: Apify is on the SCALE plan - $199 prepaid, 128
concurrent runs, datacenter proxies - and the $20 pilot cap is removed. Four
sources wanted: company page posts (last 3), open roles, a champion's and an
exec's own posts, and the company's website content.

This document is the measurement. `src/researchpack/` is the code and
`tests/test_researchpack.py` is what holds it.

---

## 0. THE FIRST FINDING, BEFORE ANY PILOT: THE ACTOR IDS WERE INVENTED

`src/researchpack/actors.py`, as merged from the slack-agent session, named
three actors:

    apify~linkedin-company-posts-scraper
    apify~job-listings-scraper
    apify~linkedin-profile-posts-scraper

All three answer **404 `record-not-found`** on `GET /v2/acts/{id}`. They do
not exist. Nothing in the package could ever have run, and the cassettes
matched on those same invented names, so 30-odd tests were green against
actors Apify has never heard of. Checked 2026-09-24 with the live token;
`apify~website-content-crawler`, the one id that was not invented, answers
200.

This is the "a green test that cannot fail" shape again, one layer out: the
fixtures were not merely invented, they were invented for a provider surface
nobody had ever seen.

---

## 1. THE ACTORS, AND WHERE "NO SESSION" WAS CONFIRMED

Every id below was found in `GET /v2/store`, confirmed with
`GET /v2/acts/{id}`, and then RUN from this account, which holds no LinkedIn
cookie of any kind. The README quotes are from each actor's own latest build
(`GET /v2/actor-builds/{id}` -> `actorDefinition.readme`), not from a
marketing page.

| source | actor id | needs a session? | confirmed where |
| --- | --- | --- | --- |
| open roles | `bebity/linkedin-jobs-scraper` | no | README: "**no LinkedIn account, no cookies, no login required**". 3.9M runs since Feb 2023. Ran live, returned rows. |
| company posts | `harvestapi/linkedin-company-posts` | no | README: "No cookies or account required: Access profile data without sharing cookies or risking account restrictions". Ran live, returned 3 posts in 12s. |
| person posts | `harvestapi/linkedin-profile-posts` | no | Same actor family, same README line. Ran live, returned rows. |
| site content | `apify~website-content-crawler` | no | Apify's own first-party crawler; already in `src/providers/apify.py`. No LinkedIn surface at all. |
| (slug resolver, opt-in) | `harvestapi/linkedin-company` | no | README: "No cookies or account required". Not a source: it makes no fact. |

None of the four authenticates as a person. None reads a logged-in view.
`needs_session` is carried on every registry entry and asserted, so an actor
added later has to answer the question rather than inherit a silence.

### Proxies: datacenter, and no code path to residential

`{"useApifyProxy": true}` with no `apifyProxyGroups` is Apify's automatic
DATACENTER pool. Residential requires naming the `RESIDENTIAL` group, and no
input built anywhere in `src/researchpack/` names a proxy group at all - a
test asserts that. Nothing was blocked during the pilot, so nothing moved,
and moving one actor later would be a reviewed edit rather than a flag.

Note also that `proxyConfiguration` is the **crawler's** input field. The
three LinkedIn actors do not declare it - they route their own requests -
so the merged code's "set it on every input" was inventing input for three
actors that would have rejected or ignored it.

---

## 2. WHAT WAS WIDENED, AND WHAT WAS NOT

`providers.apify.check_url` was bounded to the record's own company domain.
A LinkedIn actor's target is on `linkedin.com` by construction, so that had
to give. It gave in exactly one place:

- `check_url(url, allowed_domain=...)` now accepts a domain **or a tuple of
  domains**. It is still an allowlist and it is still stated at the call site.
- `providers.apify.RESEARCH_HOSTS = ("linkedin.com",)` is the whole of the
  widening, named in the provider module rather than passed in as a string by
  whoever wants one.
- `src/researchpack/pack.py::_checked` is the only consumer, and it passes the
  actor's own declared `hosts`.

**Unchanged, and each still runs for a LinkedIn URL exactly as for a site
crawl:** the http/https scheme check, the embedded-credential check, the port
check, the loopback-name list, the internal-suffix list, the literal
private/reserved-address check, and the DNS resolution check. A widened
DOMAIN allowlist cannot reach a private address because the address guards do
not consult it. Tests assert that `169.254.169.254`, `file:///etc/passwd` and
a credentialed URL are still refused **on the LinkedIn path**, and that
nothing is started and nothing is charged when a URL is refused.

**What was refused:** the company site crawl's allowlist did not move.
`site_content` still means the record's own domain, `candidate_urls` and
`evidence_from_items` still pass a single domain, and no actor was given a
"fetch this arbitrary URL" input.

---

## 3. THE OPERATOR'S SPECIFIC QUESTION: CAN THE JOBS ACTOR SUPPLY THE SLUG?

**Mechanically, yes.** Every row `bebity/linkedin-jobs-scraper` returns
carries both

    "companyUrl":     "https://www.linkedin.com/company/<slug>?trk=..."
    "companyWebsite": "https://<the company's own site>/"

and the actor can be aimed with `companyName` - a company NAME, which the
estate has - so nothing has to be known about LinkedIn before the run. The
slug comes out, and `company_posts` becomes addressable. Confirmed live.

**And it is only accepted when those two fields agree.** `companyName` is a
text filter: a search for one name returns other companies' jobs, and taking
their `companyUrl` would buy another company's posts and put them in front of
this one. `actors.slug_from_jobs` returns a slug only when that row's
`companyWebsite` is on the record's own domain, and `None` otherwise.

**But the coverage bound is severe, and this is the part to read.** A company
with no live LinkedIn job listing returns zero rows, and zero rows carry zero
slugs. Verified that this is a real absence rather than a name-matching
failure: targeting by `companyName` and by the company's LinkedIn jobs page
URL both returned 0 for the same companies, while a company that is hiring
returned rows by both routes.

**Measured over the 24 pilot accounts:**

| where the slug came from | accounts | share |
| --- | --- | --- |
| `open_roles` — the route the operator asked for | 3 | **12.5%** |
| `harvestapi/linkedin-company` — the opt-in resolver, only after the jobs route failed | 12 | 50.0% |
| nowhere: neither could name a page on this domain | 9 | 37.5% |

So the honest answer is: **the jobs actor can supply the slug, and for this
estate it does so for one account in eight.** Eight of 24 jobs runs returned
any row at all (33%), and of those eight only three returned a row whose
`companyWebsite` was this record's own domain. It is not a mechanism failure
and no other input to that actor fixes it - a company with no live LinkedIn
job listing has no row to carry a slug.

`harvestapi/linkedin-company` (`searches: [company name]` -> `linkedinUrl` +
`website`) resolved 12 more for $0.0024 per account, under the same identity
test. It is **opt-in** (`build(..., resolve_slug=True)`) because it is a
fifth actor and a cost the operator did not ask for.

---

## 4. THE PILOT

`scripts/researchpack_pilot.py --accounts 25 --live --cold --resolve-slug
--budget-usd 3.00`, run 2026-09-24 from 18:06Z against the first 25
accounts of `work/queue.jsonl` by domain order, cold cache.

**24 accounts completed.** The process was killed by the harness at account
24 of 25 before it printed its own summary, and its stdout was
block-buffered and lost with it. Nothing measured was lost: the facts it
bought are in `work/researchpack-pilot-cache.json` and the charges are on
Apify's own run records, which is better provenance than the script's
arithmetic. The figures below are reconstructed from those two, and
`work/researchpack-pilot-summary.json` holds the reconstruction.

### 4a. A SECOND DEFECT THE PILOT FOUND: 70% OF THE JOBS ROWS WERE SOMEBODY ELSE

Before the coverage table, the finding that changes it.

`companyName` is a text filter. Of the **71 job rows** returned across the
eight accounts that got any, **50 were a different company** - and on four of
those eight accounts, all ten rows were. `slug_from_jobs` already applied an
identity test to the SLUG, but the FACTS were being made from every row.
Unfixed, this pack would have asserted that somebody else is hiring on five
of eight accounts that had roles at all.

Fixed: `actors.is_this_company` is now the one identity test, applied to the
facts as well as the slug, fail-closed when there is no domain to check
against. `tests/test_researchpack.py::test_another_companys_job_makes_no_fact`
is the regression, verified by removing the guard and watching it fail.

**The coverage table below is post-fix.** The uncorrected figure for
`open_roles` was 8/24; five of those eight were another company's roles.

### 4b. COVERAGE PER SOURCE, 24 ACCOUNTS

"Addressable" = the pack could aim the actor at all. "Covered" = the pack
came away with at least one usable fact of that kind - a url, a date and a
quotable snippet. A run that succeeded and returned nothing is not coverage.

| source | addressable | covered | of all 24 | of addressable |
| --- | --- | --- | --- | --- |
| `site_content` | 23 | 20 | **83.3%** | 87.0% |
| `company_posts` | 15 | 10 | **41.7%** | 66.7% |
| `person_posts` (exec) | 12 | 8 | **33.3%** | 66.7% |
| `open_roles` (post-fix) | 24 | 3 | **12.5%** | 12.5% |
| `person_posts` (champion) | 2 | 2 | **8.3%** | 100.0% |

**At least one fact of some kind: 22 of 24 accounts.** The company's own
website is the source that carries the estate, and it is also the only one
that needs no LinkedIn presence.

Two coverage bounds are the ESTATE's rather than the actors':

- **`person_posts` is bounded by whether a contact has a LinkedIn URL at
  all.** Across the whole queue, 744 of 1,543 records (48%) have one contact
  with a profile URL and 100 (6.5%) have two. In this slice only 2 accounts
  carried a champion. Where a profile URL existed, the actor found posts on
  two thirds of them.
- **`open_roles` is bounded by whether the company is hiring on LinkedIn.**
  Most of this estate is small marketing and development agencies, and 16 of
  24 had no listing at all.

### 4c. OBSERVED COST, FROM APIFY'S OWN RUN RECORDS

Not the planned figure and not the ledger's rounded cents: `usageTotalUsd`
on each run, summed per actor, over 24 accounts. The SCALE plan bills this
account at tier SILVER.

| actor | runs | billed items | failed | total | per account |
| --- | --- | --- | --- | --- | --- |
| `apify/website-content-crawler` | 24 | compute units | 2 | $0.69316 | **$0.02888** |
| `bebity/linkedin-jobs-scraper` | 24 | 71 | 0 | $0.08050 | **$0.00335** |
| `harvestapi/linkedin-profile-posts` | 14 | 36 | 0 | $0.06370 | **$0.00265** |
| `harvestapi/linkedin-company-posts` | 15 | 33 | 0 | $0.06250 | **$0.00260** |
| `harvestapi/linkedin-company` (opt-in) | 21 | 16 | 0 | $0.05705 | **$0.00238** |
| **TOTAL** | 98 | | 2 | **$0.95691** | **$0.03987** |

(The account's own cycle total moved $0.0731 -> $1.0916 across the day,
which also carries the smoke tests, a 3-account validation run and four
diagnostic jobs runs. The table above is the pilot's runs only; four
diagnostic runs at $0.0001 are netted out of the jobs line.)

**The website crawler is 72% of the bill on its own.** The four LinkedIn
actors together cost $0.01098 per account; the site crawl costs $0.02888.
It is also the only one billed in compute units rather than per item, and
the only one that failed - 2 runs of 24, which still cost compute and
returned nothing.

---

## 5. WHAT THIS COSTS AT 19,612 ACCOUNTS

The cache TTL is 30 days, so a full pass over the estate is a monthly cost
and the arithmetic is one multiplication.

### THE HEADLINE: ALL FOUR SOURCES ON ALL 19,612 ACCOUNTS DOES NOT FIT

    $0.03987 per account  x  19,612 accounts  =  $781.94 per month
    budget                                       $199.00 per month
                                                 ---------------
                                                 3.93x over

At $0.03987 the $199 buys **4,991 accounts a month**, not 19,612.

### THE SAME ARITHMETIC FOR EVERY SHAPE WORTH CONSIDERING

| what runs | $/account | x 19,612 | vs $199 | accounts $199 buys |
| --- | --- | --- | --- | --- |
| all four + slug resolver (what was measured) | $0.03987 | **$781.9** | 3.93x over | 4,991 |
| all four, slug from the jobs run only (the literal instruction) | $0.03548 | **$695.8** | 3.50x over | 5,609 |
| three LinkedIn sources + resolver, no site crawl | $0.01098 | **$215.5** | 1.08x over | 18,116 |
| three LinkedIn sources, jobs-slug only, no site crawl | $0.00659 | **$129.3** | **fits, $70 spare** | 30,179 |

Working for the two derived rows: dropping the resolver removes its
$0.00238 and drops `company_posts` to the 3 accounts the jobs route
addressed (8 posts: 3 x $0.00005 + 8 x $0.00175 = $0.01415 over 24 accounts
= $0.00059), so `company_posts` falls from $0.00260 to $0.00059. Dropping
the site crawl removes $0.02888.

### WHAT THAT MEANS, PLAINLY

1. **The budget question is the website crawler, not LinkedIn.** All three
   LinkedIn sources plus the slug resolver, on every one of the 19,612
   accounts, is $215 - within 8% of the budget and inside it after any of
   the levers below. The site crawl alone on 19,612 accounts is $566.
2. **The crawl is bounded by `site_content.limit`, currently 5 pages.** It
   is the one lever that is a one-line change; its cost is not linear in
   pages because each run has a fixed startup, so the saving has to be
   measured rather than assumed.
3. **Or the estate is the lever.** 19,612 is the whole TAM; the accounts
   that reach a campaign are a small fraction of it, and research bought for
   an account nobody writes to is spend with no addressee. Research packs on
   the approved and campaign-bound accounts - the shape
   `STREAMING-ARCHITECTURE.md` already describes - is comfortably inside
   $199 with all four sources.
4. **Nothing here needs residential proxies.** Not one run was blocked, so
   nothing moved off the datacenter pool and no residential cost arises.

This is an arithmetic and a set of options, not a decision. Which accounts
get a research pack is the operator's call.

---

## 5b. THE FIXED CODE WAS THEN RUN LIVE

The identity fix landed after the 24 accounts were bought, so it had to be
proved on something it had not already paid for. Account 25 -
`aciworldwide.com`, the one the killed process never reached - was run on
2026-09-24 19:50Z against the fixed code: `open_roles`, `company_slug` and
`site_content` all started, returned, and produced a pack. $0.0385 for that
account and the 24 cache reads together, of which $0.0001 was its empty jobs
run.

**The pilot's own cache is quarantined rather than kept.** It holds the
`open_role` facts made BEFORE the identity fix, 50 of which are another
company, and a cache is a thing that gets served. It is renamed
`work/researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json` - the evidence
survives and nothing reads it. A coverage table computed from it still shows
the pre-fix `open_roles` figure of 8; the corrected 3 is recomputed from the
rows, as section 4a says.

---

## 6. WHAT IS NOT PROVEN HERE

- **A pack is not copy.** `src/copylint.py` is what makes a fact load-bearing
  and nothing in this pilot generated a draft.
- **The 30-day cache TTL is untested against reality.** It is asserted in the
  tests and nothing has yet been re-bought after expiry.
- **Coverage was measured on the first 25 accounts by domain order**, which
  is an arbitrary slice of one estate of small marketing and development
  agencies. It is representative of THIS estate and should not be read as a
  LinkedIn-wide rate.
- **The site crawl's cost is compute units and varies with the site.** The
  per-account figure here is this estate's average, not a price.
