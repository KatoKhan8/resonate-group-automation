# Sourcing clients whose ICP is not on LinkedIn — design

**Backlog F6. For review. Nothing here is built, and nothing should be built
until this is approved.** It depends on the server migration (increment F):
the sourcing service is a supervised Docker container and this machine has no
Docker.

---

## 1. THE PROBLEM, AND WHY THE EXISTING PATH CANNOT BE POINTED AT IT

Today's sourcing is `src/nightlysourcing.py`: source → **S3 ICP** → S4b MX →
local collision. `icp.score` reads `company_facts` — `employees`, `industry`,
`description`, `services`, `specialties`, `country` — and the client config
carries `market.size_min_employees: 20`. Every one of those is a LinkedIn-shaped
fact about a company with a public professional footprint.

A 9-person dental clinic in Split, a 4-person agency in Graz and a family
hotel in Istria have none of them. They have an address, a phone number, a
category, opening hours, a rating and a review count. **They are not smaller
versions of the current ICP; they are described by a different set of facts.**

So the change is not a new provider bolted to the existing S3. It is:

    a source that returns PLACES rather than companies
    an S3 whose criteria are per-client, because rating and review count
      mean nothing to Productive and headcount means nothing to a clinic
    an account identity that survives having no website at all

Everything downstream of qualification — collision, suppression, DNC,
verification, approval, pacing, hard stops — is unchanged, with **one
exception named in §7 that the instruction's "unchanged" cannot survive
contact with, and that is the most important paragraph in this document.**

---

## 2. THE LEGAL CONSTRAINTS, PLAINLY

Put first, because they decide the design rather than annotate it. **None of
this is legal advice and none of it has been reviewed by a lawyer. It is an
engineer naming what the rules say so that somebody qualified can rule on it
before a single message goes out.**

### 2.1 `gosom/google-maps-scraper` breaks Google's Terms of Service

Say it plainly: scraping Google Maps is prohibited by the Google Maps
Platform Terms and by Google's general ToS. The tool is excellent and widely
used and that does not change what the terms say. The realistic exposure is
not a lawsuit; it is **IP blocking, and a cease-and-desist**, and it is a
risk taken knowingly or not at all.

Running it on **our own server, for our own clients' prospecting**, with
proxies and telemetry off, is a decision the operator makes with that
sentence in front of them. It should be recorded in
`docs/OPERATOR-AUTHORIZATION-*.md` like every other standing grant, not
assumed from the fact that the code exists.

### 2.2 SerpApi / SearchApi are a CONTRACTUAL shift, not a legal blessing

The brief calls these "the ToS-clean alternative". That is not quite right and
the difference matters.

SerpApi and SearchApi scrape Google too. What they sell is that **they** carry
the ToS exposure and the blocking problem, under a contract that says so. That
is a genuine and valuable shift — it moves an operational and relationship
risk off us onto a vendor who has priced it. It does not make the underlying
activity licensed by Google, and marketing copy asserting compliance is not a
licence.

**What it buys:** no proxy management, no blocking, no scraper maintenance, a
contract to point at, and a real invoice that goes through the spend ledger.
**What it costs:** roughly $10–75 per 1,000 searches depending on plan, where
the self-hosted path costs proxies and a server we are already paying for.

### 2.3 The Google Places API is the only licensed route, and its terms forbid what we want

This is the constraint that stops "just use the official API" from being the
obvious answer, so it gets stated exactly:

- **`place_id` may be stored indefinitely.** It is the one field Google
  explicitly permits caching without limit. That is why the brief's choice of
  `place_id` as the source id is right, and it is right for a licensing reason
  as well as a technical one.
- **Everything else — name, address, phone, rating, review count, opening
  hours — may not be cached beyond a limited window** (Google's terms have
  used 30 days), must be refreshed, and must not be used to build a
  database that substitutes for the service.
- Building a persistent prospect estate out of Places content is close to the
  centre of what those terms prohibit.

So the licensed route cannot hold the data our pipeline is built to hold. That
is the honest trade: **the compliant API does not do this job**, and the two
options that do are the scraper and the SERP vendors. Anyone who says
otherwise has not read the caching clause.

### 2.4 GDPR — this is EU data about identifiable people

Croatia is in the EU and most target markets are. Local business records are
**personal data** far more often than enterprise ones: the owner's name is the
business name, the mobile is the business number, `marko@marko-dental.hr` is a
person.

- **Legal basis.** Legitimate interest, Art 6(1)(f), is the usual basis for
  B2B outreach and it is not automatic: it requires a **documented balancing
  test (LIA)** that a small trader's expectations are weighed in. Write it
  once, per client, and keep it.
- **Art 14 transparency.** Because the data was **not collected from the
  person**, they must be told — who has their data, where it came from, why,
  and how to object — at the latest with the first communication. **This is a
  change to the message template, not a policy paragraph filed away.** The
  first email needs a line saying where we got their details and how to stop.
- **Art 21 objection, and Art 17 erasure.** An objection must stop processing.
  `src/agencydnc.py` and `src/leadstop.py` already implement the mechanism;
  what is new is that the **source** must also be suppressed, or the next
  nightly sourcing run re-sources the same place and the objection is undone.
  **A suppression that the source does not read is a suppression with a
  timer on it.**
- **Data minimisation.** Do not store review text, photos, or owner names we
  have no use for. Store what a decision needs.

### 2.5 Unsolicited email — the rule is national, and local businesses fall on the wrong side of it

This is the constraint most likely to be got wrong, because the current estate
never met it.

ePrivacy is implemented per member state and B2B treatment varies:

- **UK (PECR).** The email rule exempts **corporate subscribers** — limited
  companies and LLPs. It does **not** exempt **sole traders and
  partnerships**, who are treated as individuals and require consent or soft
  opt-in. **A large share of hospitality, clinics and small agencies are
  exactly that.** The exemption the current estate relies on mostly does not
  apply to this ICP.
- **Germany (UWG §7).** Unsolicited commercial email effectively requires
  **prior consent, including B2B**. Germany is in Productive's geo list. For
  this ICP it should be treated as a no-email market unless a lawyer says
  otherwise.
- **Netherlands.** B2B permitted with opt-out, and the **Dutch opt-out
  register must be screened** against.
- **Croatia, Austria, Italy, Spain.** Opt-out regimes with national
  variations, all requiring identification of the sender and a working
  objection route.

**Design consequence, and it is not a footnote:** the per-client channel
config in §10 must be **per-country as well as per-client**, and the default
for a country with no ruling recorded is **no email**. Fail closed, the way
every other gate here does.

### 2.6 Phone is a regulated channel and we have never used it

Adding phone means adding screening we do not have:

- **UK: CTPS** for corporate lines, **TPS** for sole traders — screening is a
  legal requirement, not a courtesy, and it is a paid lookup.
- **Germany:** cold calling businesses without prior consent is restricted
  under UWG.
- National do-not-call registers vary and none of them is `agency-dnc.jsonl`.

**Phone must not ship in the same increment as sourcing.** It is its own
piece of work with its own screening provider and its own spend line.

### 2.7 Review text carries two problems, and "never invent" answers neither

- **Copyright.** A review is the author's copyrighted text. Quoting it in
  commercial outreach is reproduction, and Google's terms restrict reuse of
  review content independently of that.
- **The named-customer problem.** "I saw Ana's review about your waiting
  times" is accurate, never-invented, and will land as surveillance. The
  never-invent rule stops fabrication; it does not stop this.

**Recommendation in §11: derive, never quote.**

---

## 3. THE SOURCE — TWO BACKENDS BEHIND ONE ADAPTER

Same shape as `QUEUE_BACKEND` in `docs/STORE-SQLITE-DESIGN-2026-09-22.md`,
and for the same reason: the decision about which is live should be one
environment variable and a rollback, not a code change.

    GMAPS_BACKEND=scraper    self-hosted gosom/google-maps-scraper
    GMAPS_BACKEND=serpapi    SerpApi
    GMAPS_BACKEND=searchapi  SearchApi
    GMAPS_BACKEND=off        DEFAULT. Refuses every call with a named error.

**`off` is the default and it is not a formality.** A new sourcing backend
that is live the moment the code merges is how an unreviewed query spends a
client's budget. It goes live when the operator flips it, in the pattern §11
of the store design already established.

### The self-hosted service

A supervised Docker container on the migrated server:

- **REST jobs API**, CSV/JSON out — jobs in, places out, which is the whole
  interface.
- **Proxies** configured; **telemetry off**.
- **Under the supervisor** (`src/supervisor.py`), so it is a declared monitor
  with a heartbeat, a lock and a restart policy, and it appears in
  `cold_start`'s two-witness check like everything else. A scraping container
  that dies quietly and reports nothing is a sourcing run that returns empty
  and looks like a market with no businesses in it.
- **Rate limited deliberately.** The constraint is not our throughput, it is
  not being blocked and not being rude.

---

## 4. `src/providers/gmaps.py` — read-only, jobs in, places out

Follows every convention the other eleven adapters follow: a `ROUTES` table,
the transport seam, cassettes for tests, trimmed dicts rather than raw
payloads, and **every paid call through `enrich.spend()`** so it reaches the
waterfall ledger. A provider call that skips `spend()` is invisible to the
audit, and this repository's rule is that an audit which reports clean
because it watched nothing is worse than none.

    submit_job(query, geo, category, limit)  -> job_id
    job_status(job_id)                       -> queued|running|done|failed
    fetch_places(job_id)                     -> [place, ...]

**"Read-only" needs a definition here that the other adapters did not need.**
`submit_job` is a POST. It writes to **our own service** and changes nothing
at any third party. The invariant to assert — the `gmaps` equivalent of
`test_every_contactout_post_goes_to_a_read_only_route` — is:

> no `gmaps` route may reach a host we do not operate with anything but GET,
> and no route may mutate third-party state at all.

For the SerpApi and SearchApi backends every call is a GET against the
vendor, and the same invariant holds trivially.

### Cost

- **serpapi / searchapi:** a real per-search cost. `COSTS` entry, through
  `spend()`, capped per run like every other paid call.
- **scraper:** no per-call invoice, and **still metered**, because the proxy
  bill and the server are real and because the ledger is how a run is
  audited. A "free" provider outside the ledger is a hole in the audit.

---

## 5. PLACES → ACCOUNTS, AND THE IDENTITY PROBLEM

Mapper — proposed `src/gmapsaccounts.py`, one job, no scoring:

    place_id        -> source id                 (the one field Google lets us keep)
    website         -> domain, normalised
    name            -> company
    formatted_phone -> phone
    address + geo   -> country, city, region
    category        -> vertical
    rating          -> quality signal
    review_count    -> quality signal, and a size proxy
    business_status -> OPERATIONAL / CLOSED_TEMPORARILY / CLOSED_PERMANENTLY

### The problem the current estate has never had: no website

**`work/queue.jsonl` is keyed on `domain`.** Collision, suppression, client
approval, MX, verification and the export all assume one. A hairdresser with
a Facebook page and no site has no domain, and roughly a third of this ICP
will not have one.

Three options, and the recommendation is the third:

1. **Drop domainless places.** Simple, honest, and throws away a third of the
   market — including the businesses least contested by competitors.
2. **Synthesise a key** (`place:ChIJ...`). Every domain-shaped consumer then
   has to learn that some "domains" are not domains. That is a second
   representation of identity, and §"Prefer canonical state" in CLAUDE.md is
   about exactly this drift.
3. **Give the record a real `place_id` field and make `domain` optional**,
   with every gate that needs a domain refusing explicitly and by name when
   there is not one. Bigger change; it is the only one that does not lie.

**Option 3 is a schema change to the record model and it is the largest piece
of work in this design.** It is called out here rather than discovered during
implementation.

### Duplicates

`place_id` is primary. But one business commonly has several: a clinic and
its practitioner listings, a hotel and its restaurant. Dedupe on
`(domain, phone)` where a domain exists, and flag rather than merge where it
does not. **Merging on name and address similarity will merge two real
businesses in the same building**, which in this ICP is a shopping centre.

---

## 6. S3 BECOMES PER-CLIENT CRITERIA

`icp.score` stays. What changes is that the criteria are a **client-declared
profile** rather than one global taxonomy — and the extension point already
exists: `segments.kind_of(vertical, config)` was built so "a vertical a
client declared for its own market scores like the kind of business it said
it was", after the whole model turned out to be Productive's taxonomy.

New config block, per client:

```yaml
local_business:
  categories: [dentist, dental_clinic, orthodontist]
  exclude_categories: [hospital]
  min_rating: 4.0
  min_review_count: 15
  geos:
    - {city: Split, country: HR, radius_km: 25}
    - {city: Zagreb, country: HR, radius_km: 30}
  exclude_chains: true
  require_website: false
  require_open: true
```

### The criteria, and what each is actually evidence of

- **`min_review_count`** is the closest thing to a size and maturity proxy.
  It is also the **most gameable** signal on the list, and a business with 300
  reviews in a town of 8,000 is more likely to be buying reviews than
  thriving. A ceiling is as useful as a floor.
- **`min_rating`** is a quality proxy and a **thin one below ~10 reviews**.
  It must be read together with the count or not at all. Four reviews
  averaging 5.0 is not evidence.
- **`require_open`** — `CLOSED_PERMANENTLY` is the single highest-value filter
  here and it does not exist in the LinkedIn path at all.
- **`exclude_chains`** — a franchise branch has no buying authority. Detectable
  by repeated `(name, website)` across many `place_id`s, which is a **derived
  signal and must be computed, not guessed from the name.**

### The gate that does not move

**QUALIFIED only; REVIEW routes to enrichment.** ISSUE-019 is the reason, and
nothing about a different ICP makes undecided records safe to export. The
verdict text in `why_matched` is what the client reads, and "scored above
threshold" on an undecided row is what stopped the first client export.

---

## 7. THE PART OF "UNCHANGED" THAT CANNOT BE UNCHANGED

The brief says collision, suppression, verification, pacing and hard stops are
unchanged. Four of those five are. **Collision and suppression are not, and
pretending otherwise would ship a real defect.**

`src/collision.py` and the DNC path key on **domain**. A domainless account
cannot be collision-checked or suppressed by domain — not because the code is
wrong, but because the key does not exist for that record.

Consequences if this is not faced first:

- A domainless place **cannot be checked against the client's own campaigns**,
  so we can contact an account the client is already working.
- An objection under GDPR Art 21 from a domainless business **cannot be
  recorded against anything the next sourcing run will check**, so the next
  run re-sources it. §2.4 calls that a suppression with a timer on it.

**Therefore: collision and suppression must accept `place_id` as an
alternative key before any domainless record is created.** That is a
prerequisite, not a follow-up. If the operator prefers, option 1 in §5 —
drop domainless places — avoids it entirely and is a legitimate first
increment.

---

## 8. PERSON DISCOVERY, AND "NO PERSON" AS A RESULT

`docs/PROVIDER-ROUTING-POLICY.md` is unchanged: ContactOut first whenever
capable, then its cache, then the free crawler, then Grok, then other paid
providers, then Claude. And the company-first rule is enforced in
`enrich.spend()` rather than at call sites — no person-level call before an
ICP verdict — so it applies here by construction.

What changes is the **expected outcome**. ContactOut is a professional-network
index; for a 6-person clinic in Split it will frequently return nothing, and
that is the correct answer rather than a failure.

- **`no_person_found` is a terminal, successful state**, distinct from
  `enrichment_failed`. Conflating them makes the whole ICP look like a broken
  pipeline and hides real failures inside a normal one.
- The **free crawl leads** for this ICP, inverting the usual order in practice
  though not in policy: a small business site has a Contact page with a name
  and a role inbox far more often than ContactOut has the person.
- **Missing evidence is never positive evidence.** A guessed owner name from a
  domain is worse than no name, and `src/dossier.py` already says so.

---

## 9. ROLE INBOXES

Allowed **per client config**, off by default.

```yaml
contact_policy:
  allow_role_inbox: true
  role_inbox_prefixes: [info, hello, kontakt, praxis, reception]
  require_named_person: false
```

Three things that must hold and one that must be measured:

- **Verification is unchanged.** No email is generated for an unverified
  address, and role inboxes are **disproportionately catch-all**. The existing
  catch-all path — cleared through Reoon before use — is what decides, and a
  catch-all that does not clear stays held. This is the gate most likely to
  drop a large fraction of this ICP, and the drop is correct.
- **Personalisation must change register.** Copy written to a named founder,
  sent to `info@`, reads as a mail merge. Role-inbox copy addresses the
  business.
- **Never both.** A named person and a role inbox at one account is two
  touches on one business, which the account model already forbids as the unit
  of outreach.
- **Measure reply rate separately.** If role inboxes do not reply, this is
  volume with no outcome, and `COPY-EXPERIMENTS.md`'s rule against calling a
  winner from four replies applies here too.

---

## 10. CHANNELS PER CLIENT — AND PER COUNTRY

```yaml
channels:
  email:    {enabled: true,  countries: [HR, NL, AT]}
  phone:    {enabled: false}
  linkedin: {enabled: false}
```

Per §2.5 the permission is national, so the config is keyed by country and
**a country absent from the list is not permitted**. Fail closed. `DE` is
absent above deliberately.

**LinkedIn is off by default for this ICP** and that is a factual observation
rather than caution: the people being targeted are frequently not on it, which
is the premise of the whole document.

**Phone ships separately**, after §2.6's screening exists.

---

## 11. REVIEW TEXT AS PERSONALISATION — DERIVE, NEVER QUOTE

The brief asks for review text as a personalisation input under the
never-invent rule. The never-invent rule is necessary and **not sufficient**
here, for the two reasons in §2.7.

**Proposal: reviews are read to derive a signal, and the signal is what the
copy may use.**

    permitted    "a pattern in recent reviews mentions waiting times"
                 derived, attributable to no individual, verifiable against
                 the evidence log
    refused      "Ana wrote on 12 March that she waited 40 minutes"
                 accurate, never invented, reproduces a third party's
                 copyrighted text, and names a customer to their supplier

Mechanically this is the existing evidence model: the derived signal is a
claim, it carries its evidence, and `src/lint.py` refuses a claim the evidence
does not support. **What must be added is a lint rule that refuses a verbatim
review span in generated copy** — a claim licence, in this repository's
existing vocabulary, that permits the derivation and refuses the quotation.

Store the derived signal. **Do not store review text longer than the
derivation needs** (§2.4, minimisation).

---

## 12. WHAT DOES NOT CHANGE

Stated explicitly so no one reads this as a parallel pipeline:

- Verification: no email for an unverified address; catch-all cleared through
  Reoon or held.
- Approval: client approval gates spend; `--live` explicit; dry run default.
- Pacing: the forward book decides batch size, never the mailbox count.
- Hard stops, kill switches, volume caps, positive-reply protection.
- Every paid call through `spend()`.
- One writer, one queue, `store.py` for all state.
- Company first: no person-level spend before an ICP verdict.
- Collision and suppression, **for accounts that have a domain** — §7 is the
  exception and the prerequisite.

---

## 13. WHAT THIS DESIGN DOES NOT SETTLE

- **Whether the scraper is used at all.** §2.1 is an operator decision, and it
  should be recorded as a standing grant rather than inferred.
- **Which markets may receive email.** §2.5 needs a ruling per country. Until
  then the config is empty and nothing sends.
- **The record schema change in §5.** Option 3 is recommended and it is the
  largest single piece of work here.
- **Cost per qualified account.** Unknown until one real run. The SERP backends
  have a per-search price; the scraper has a proxy bill; neither converts to
  cost-per-qualified-account without measuring, and this register's rule is
  that a benchmark measured at the wrong size is worse than none.
- **Whether this ICP replies at all.** Everything above is machinery for
  reaching an audience nobody here has tested. The first increment should be
  **one client, one city, one category, a few dozen accounts**, measured
  before anything is scaled — the 3 → 10 → 25 → 50 progression in
  `OPERATOR-AUTHORIZATION-2026-09-15.md`, unchanged.

---

## 14. SEQUENCING

    F   server migration, Docker available          PREREQUISITE
    F6a legal rulings: 2.1 scraper grant, 2.5 per-country email    BLOCKING
    F6b collision + suppression accept place_id, or drop domainless
    F6c src/providers/gmaps.py, GMAPS_BACKEND=off, cassettes, invariant
    F6d places -> accounts mapper, dedupe, no scoring
    F6e per-client local_business criteria in S3
    F6f person discovery, no_person_found as a terminal state
    F6g role inboxes, verification unchanged
    F6h review derivation + the lint rule refusing verbatim spans
    F6i one client, one city, one category, measured

**F6a is genuinely blocking.** Every line below it is machinery for sending
messages that, in at least one named market, we currently have no basis to
send.

---

## 15. FOR THE OPERATOR — THE FIVE DECISIONS

1. **The scraper, or the SERP vendors, or neither?** §2.1 and §2.2. The
   scraper breaks Google's ToS; the vendors move that risk onto a contract and
   charge for it; the licensed API cannot hold the data (§2.3).
2. **Which countries may receive email for this ICP?** §2.5. Default is none.
3. **Domainless businesses: drop them, or change the record schema?** §5 and
   §7. Dropping is a smaller, honest first increment.
4. **Phone: now or later?** §2.6 says later, and it says why.
5. **Review text: derive only?** §11 recommends refusing verbatim quotation
   outright.
