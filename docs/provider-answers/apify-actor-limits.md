# apify-actor-limits

_Asked of Grok (xAI) 2026-09-26. Sources are the model's; verify before building a limit on one._

## Question

Apify: what are the concurrency, memory and run-time limits that apply to actor runs on a paid plan, and how is cost per actor run computed? Specifically for LinkedIn company-post and profile-post scrapers: what rate limits or blocking should be expected, and what are the documented limits on dataset item counts per run? Cite Apify documentation with URLs.

## Answer

**Canonical sources (read these rather than copying numbers from memory):**  
- Platform limits: [https://docs.apify.com/platform/limits](https://docs.apify.com/platform/limits)  
- Compute units / how runs are billed: [https://docs.apify.com/platform/compute-units](https://docs.apify.com/platform/compute-units)  
- Usage and resources: [https://docs.apify.com/platform/actors/running/usage-and-resources](https://docs.apify.com/platform/actors/running/usage-and-resources)  
- Running Actors (timeout, memory): [https://docs.apify.com/platform/actors/running](https://docs.apify.com/platform/actors/running)  
- Plan SKUs / included CUs: [https://apify.com/pricing](https://apify.com/pricing)  
- Storage / datasets: [https://docs.apify.com/platform/storage](https://docs.apify.com/platform/storage), [https://docs.apify.com/platform/storage/dataset](https://docs.apify.com/platform/storage/dataset)  
- Store-actor monetization (on top of CUs): [https://docs.apify.com/platform/actors/publishing/monetize](https://docs.apify.com/platform/actors/publishing/monetize)

Plan names, included CU quotas, and the numeric rows on the limits table change. **Do not hard-code a concurrency, timeout, or max-memory figure into a rate limiter unless you copied it from the live limits/pricing pages.** Below is what those docs actually specify vs what they do not.

---

### Concurrency, memory, run-time (paid plans)

**What is documented as a billing/resource model, not a single “paid plan” constant**

- You choose **allocated memory per run** (not observed RSS). You pay for the allocation for the whole run. Typical documented steps are 128 MB … 32768 MB (32 GB). The **maximum allowed memory** is a row on [the limits page](https://docs.apify.com/platform/limits); it is commonly 32768 MB for paid accounts, but **confirm on that table** — it is plan-gated in some snapshots of the docs.
- **Concurrency** is not one LinkedIn-scraper number. Platform-side it is an **account limit on concurrent Actor runs** (and historically also total memory in use). The current numbers are only on [https://docs.apify.com/platform/limits](https://docs.apify.com/platform/limits) and may be raised for Business/Enterprise. Inside a given scraper, Cheerio/Playwright `maxConcurrency` is an **actor setting**, not an Apify account limit.
- **Run time:** Actor runs take a `timeoutSecs` (API/input). Docs describe `0` as “no timeout / run until finish or abort” at the API level ([running Actors](https://docs.apify.com/platform/actors/running), [API run actor](https://docs.apify.com/api/v2#/reference/actors/run-collection/run-actor)). There **is** a platform maximum duration on the limits table. **I am not certain of the current paid-plan maximum** (public snapshots have said on the order of weeks, not minutes). Use the limits page, not a guessed hour cap.

Other limits that affect production runs (also on the limits/storage pages, not LinkedIn-specific): max input size, max dataset item size, storage retention (unnamed default retention is short; paid plans keep named storage longer — exact days are on [storage docs](https://docs.apify.com/platform/storage)).

---

### How cost per Actor run is computed

Apify bills **platform usage** and, for Store actors, often a **second price**.

**1. Compute units (always)**  
Documented definition: **1 CU = 1 GB of RAM allocated for 1 hour.**  
Formula used in the docs:

`CUs = (memory_MB / 1024) × (duration_hours)`

Example from the same model: 2048 MB for 30 minutes = 1 CU.  
Sources: [https://docs.apify.com/platform/compute-units](https://docs.apify.com/platform/compute-units), [usage and resources](https://docs.apify.com/platform/actors/running/usage-and-resources).

USD cost for that run ≈ `CUs × your effective CU price` (subscription includes a CU bundle; overage is on [pricing](https://apify.com/pricing)). Builds also consume CUs. **You are charged for allocated memory, including time spent starting, waiting on LinkedIn, retrying, or hung until timeout.**

**2. Storage**  
Dataset / KV store / request-queue GB-hours after the plan’s included storage. Retention and price: [storage](https://docs.apify.com/platform/storage).

**3. Proxy**  
Datacenter vs residential/SERPS are priced separately from CUs. [https://docs.apify.com/platform/proxy](https://docs.apify.com/platform/proxy) and the pricing page. LinkedIn actors that require residential traffic add this line item; **Apify does not publish a single “LinkedIn proxy $ / run”**.

**4. Actor monetization (Store LinkedIn scrapers usually have this)**  
Rental, pay-per-result (per dataset item), or pay-per-event. That fee is **in addition to** CUs. [Monetize](https://docs.apify.com/platform/actors/publishing/monetize). The amount is on **that actor’s Store page**, not in platform limits.

There is **no** documented platform formula “$X per LinkedIn post scrape” independent of memory, duration, proxy, and that actor’s pricing model.

---

### LinkedIn company-post and profile-post scrapers

Apify does **not** document a platform-wide LinkedIn QPS, 429 budget, or “items until block.” Those scrapers are **Store actors** with their own READMEs. You did not name an actor ID (`username/actor-name`), so the following is what **platform docs** vs **typical Store listings** actually say.

**Rate limits / blocking (what to expect, not a documented quota)**  
- Not in [platform limits](https://docs.apify.com/platform/limits). LinkedIn is the limiter.  
- Store listings for this class of actor commonly warn that LinkedIn **throttles, checkpoints, login-walls, and restricts accounts**; they often require an authenticated session cookie, delays, low concurrency, and paid proxies. That is actor README text, not an Apify SLA.  
- Apify does **not** publish a guaranteed success rate or a numeric “N posts/hour before block.” Treating any guessed QPS as documentation would be wrong.  
- Blocking is **account- and IP-dependent** and changes without Apify notice. Plan for retries, partial datasets, and run failures rather than a fixed ceiling.

**Dataset item counts per run**  
- **Platform:** datasets are not documented with a small “max posts per run” cap. Practical caps are run timeout, allocated memory, storage size, and **max size of one item** (on the storage/limits pages; commonly documented around **9 MB per item** — confirm live). [Dataset](https://docs.apify.com/platform/storage/dataset).  
- **Actor:** almost all LinkedIn post scrapers expose something like `maxItems` / `maxPosts` / `limit` in input. The default and maximum are **only on that actor’s input schema / README** (Store page → Input / Information). There is no Apify-wide “LinkedIn posts per run” number.  
- For **pay-per-result** actors, `maxChargedDatasetItems` (or equivalent) caps **billing**, not necessarily the physical dataset — see that actor’s page and [monetization docs](https://docs.apify.com/platform/actors/publishing/monetize).

Examples of Store pages to read for the two scraper types (limits live in those READMEs, not in platform limits):  
[https://apify.com/store](https://apify.com/store) — search “LinkedIn company posts” / “LinkedIn profile posts”. Common publishers include HarvestAPI, Curious Coder, API Maestro; **each actor’s `maxItems` and cookie/proxy requirements differ.**

---

### What I would not put in a production limiter

| Quantity | Documented as a stable number? |
|---|---|
| Paid-plan max concurrent runs | Only on the live [limits](https://docs.apify.com/platform/limits) table |
| Paid-plan max run duration | Same; do not guess hours/days |
| CU formula (GB-hours of **allocated** RAM) | Yes — [compute units](https://docs.apify.com/platform/compute-units) |
| LinkedIn requests/min or “safe” post count | **Docs do not state this** |
| Max dataset items per LinkedIn run | Actor input schema only; platform has no small LinkedIn-specific cap |

If you name the exact Store actor IDs you run, the item-limit and pricing fields can be quoted from those READMEs without guessing.
