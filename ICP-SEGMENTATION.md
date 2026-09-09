# Qualifying companies before spending on people

Upload 5,000 domains. Decide which of them Productive is actually for, why,
who to approach, and what finding those people would cost — all of it before a
single paid person search runs.

    python -m src.companies --size 5000 --write     # a synthetic upload
    python -m src.qualify --client productive --batch 2026-08
    python -m src.qualify --client productive --dossier co00000
    python -m src.dmplan --client productive --batch 2026-08

Nothing in that sequence calls a provider, spends a credit, or sends anything.

## Why company-first

Decision-maker enrichment is the first genuinely expensive operation in this
system. Running it before qualification means paying to find people at
companies that were never prospects — and at 5,000 domains that is most of the
bill. So the order is:

    CSV domains → normalise → dedupe → suppress
                → classify → score → segment → prioritise → route personas
                → plan the spend → **STOP**
                → (human approves) → person enrichment → existing waterfall

A rejected company consumes **zero** person credits. A company under review
consumes zero until a human decides. Both keep their records and their reasons.

On the 5,000-company synthetic upload, 1,978 companies are qualified — so 3,022
of them, **60% of the upload**, cost nothing beyond the free classification.

## The ICP model

Twelve dimensions, each scored from stored facts by arithmetic anybody can
follow. Every weight, penalty and threshold is client config: Productive's ICP
will change, and it should change in a YAML file rather than in this module.

| Dimension | Default weight | What it asks |
|---|---:|---|
| `agency_fit` | 20 | is this a client-services business at all |
| `employee_count` | 15 | is it big enough to feel the problem |
| `project_delivery` | 12 | does it deliver client projects |
| `delivery_complexity` | 8 | more than one team, more than one discipline |
| `resource_planning_need` | 8 | signals about scheduling people |
| `profitability_need` | 8 | signals about project margin |
| `utilization_need` | 6 | signals about billable time |
| `distributed_teams` | 5 | several offices or remote delivery |
| `time_tracking_need` | 5 | timesheets and budgets |
| `operational_complexity` | 5 | retainers plus projects, many clients |
| `geography` | 4 | in a market this client sells to |
| `service_not_product` | 4 | sells time, not licences |

Penalties are **subtracted, not scaled** — a negative signal is a reason, not a
discount: `product_company` 40, `ecommerce` 40, `holding_entity` 35,
`not_a_service_business` 30, `too_small` 25, `irrelevant_industry` 25,
`unsuitable_enterprise` 20, `contradictory_evidence` 10.

`unsuitable_enterprise` is the ceiling beside the floor. A 20,000-person listed
group is not a rejection — large agencies exist and buy — but it is a different
motion from an outbound email to a COO. The threshold is `max_employees`, and
setting it to `None` removes the check for a client whose ICP has no ceiling.

`contradictory_evidence` is scored small on purpose. The damage a contradiction
does is to *confidence*, and treating it as a rejection would throw away a
company whose evidence merely needs a second look.

Every verdict carries a `scoring_version`, so a batch scored under an older
model is visible as such rather than silently compared against a newer one.

### Three rules

**Missing information is never positive evidence.** A company with no employee
count does not get the benefit of the doubt on size. It gets a `missing` note,
its confidence drops, and the gap is listed in `missing_evidence`.

**Confidence and score answer different questions.** A low score on good
evidence is a *rejection*. A low score on no evidence is a *task*. They must
never share a bucket, because one is a decision and the other is work.

Confidence is computed from five named components, each a fraction with the
sentence behind it:

| Component | What it asks |
|---|---|
| `coverage` | how many of the twelve dimensions were scored at all |
| `source_diversity` | how many distinct places the picture came from |
| `source_quality` | how much of the evidence is actually usable |
| `recency` | how old the dated facts are |
| `consistency` | do any two stored facts disagree |

Coverage sets the ceiling and the other four can only lower it. No amount of
corroboration makes up for not having scored the dimensions, and a
contradiction has to be able to pull a well-covered company out of `high`
rather than being averaged away by four components that happen to look fine.

Corroboration is demanded only of companies that *have* research. Qualification
runs before research does — that is the whole point of company-first — so
requiring a second source at this stage would put the entire batch at `medium`
and make the tiers meaningless.

### Contradictions

Two stored facts that cannot both be true. The engine does not adjudicate them,
because it usually cannot; it refuses to sound certain. Four are detected:

- `vertical_vs_non_icp` — classified as an agency while showing SaaS,
  ecommerce or holding signals
- `size_vs_offices` — more offices than people
- `headcount_sources_disagree` — two sources differing by a factor of two or
  more, which is not one fact with noise on it
- `implausible_founding_year` — a typo, but one that feeds `company_maturity`

A company with a contradiction can never be reported as `high` confidence.

**Nothing is deleted.** A rejected company keeps its record and its reasons, so
"why did we not contact them?" is answerable a year later.

### Statuses and tiers

| Status | Meaning | Person credits |
|---|---|---:|
| `qualified` | scored above the threshold on enough evidence | per tier |
| `review` | judged, and it landed between the thresholds | 0 |
| `rejected` | judged, and it is not our market | 0 |
| `unknown` | not enough could be scored to judge at all | 0 |

| Tier | Threshold | Contacts |
|---|---:|---:|
| A | ≥ 75 | 3 |
| B | ≥ 60 | 2 |
| C | ≥ 45 | 1 |
| REVIEW | — | 0 |
| NOT_ICP | < 30, or a decisive negative | 0 |

### Certainty outranks volume of evidence

A decisive negative — clear SaaS, ecommerce, holding-company or under-size
evidence — settles the question **before** the how-much-do-we-know gate runs.
Not knowing a product company's headcount does not make it any less a product
company, and an obvious rejection arriving as `unknown` sends a human to
re-read what the system already knew.

## Vertical taxonomy

Deterministic keyword classification, not a model: the same company must land
in the same segment every time and a reviewer has to see why.

Digital Marketing Agency · Performance Marketing Agency · Creative / Branding
Agency · SEO Agency · PR / Communications Agency · Software Development Agency
· Product Development Agency · Design / UX Agency · Consulting · Professional
Services · Architecture / Engineering · Other Agency · Other Professional
Services · Non ICP / Other

**UNKNOWN is a real answer.** A company we cannot place is not "Other Agency" —
it is unclassified, and it goes to review. Forcing a subvertical from one
keyword is how a software agency receives copy about creative retainers. Two
distinct signals are required, or one strong multi-word phrase.

Non-ICP signals are checked first: a SaaS company that also says "consulting"
is a SaaS company.

Also derived: `business_model` (agency / consultancy / product / ecommerce /
hybrid), `employee_band`, `company_maturity`, `delivery_model` (project /
retainer / mixed / staff_augmentation), `office_count` and a distributed-team
indicator.

## Employee bands

Eight bands and `UNKNOWN`, declared once in `segments.BANDS` and read by every
module that compares sizes:

    1_9 · 10_19 · 20_49 · 50_99 · 100_199 · 200_499 · 500_999 · 1000_PLUS

`50_199` and `500_PLUS` used to be single bands and each spanned a real change
in who owns resourcing. A 60-person agency routes to an operations lead and a
190-person one is starting to route to finance; a band containing both cannot
express that, and `band_order` is what every merge and routing decision
compares.

The table is client configuration. A client selling only to enterprises has no
use for four bands under fifty. What a client may not do is leave a gap,
overlap two bands, or close the top: `segments.bands()` raises on all three,
because a band table that is quietly wrong misroutes every company in the batch
and looks like nothing happened.

## Geography and region

Regions are GTM constructs, not geography, and the country is stored separately
so a region can be redrawn without losing what was known: **UK, DACH, Nordics,
Benelux, CEE, Southern Europe, US East, US Central, US West, Canada, Australia
/ New Zealand, Other.** The mapping is configurable per client.

`region_confidence` travels with the region. A US company with no state is
`Other` with confidence `unknown` — a different fact from "somewhere else
entirely", and the two must not share a campaign.

## Timezone

Timezone is a campaign field, not a display detail. An email that lands at
04:00 local is worse than one that never arrives.

- Stored as an **IANA name** (`Europe/Zagreb`), never a UTC offset. An offset
  is right for half the year, and the wrong half is the one nobody checks.
- Three fields always travel together: `timezone`, `timezone_source`
  (city / country_single_zone / country_dominant_zone), `timezone_confidence`.
- Where a country spans zones — the US, Australia, Canada — the timezone is
  `None`, scheduling is **held**, and the reason says so. A guessed timezone is
  worse than a missing one: a missing one stops the send, a guessed one sends
  confidently at the wrong hour.
- On the 5,000-company set, 370 companies (7.4%) are correctly unschedulable.

Sending windows are calculated in **prospect local time** — email 09:00–11:30,
LinkedIn 09:30–16:00 by default, Monday to Friday, all configurable. The
conversion runs through the IANA zone, so it moves with daylight saving instead
of drifting an hour twice a year. Nine DST tests cover the northern and
southern hemispheres and a zone that does not observe it at all.

No sending is implemented. This is the calculation and the preview.

### The cadence schedule

`src/schedule.py` turns a whole cadence into the UTC instants each step would
fire at.

    python -m src.schedule --demo

The four-city demo is the fastest way to see why timezone is not a display
detail: the same "09:30 local" is a fourteen-hour spread in UTC across London,
New York, Zagreb and Sydney, and two of those four move by an hour on
different weekends.

Two failures it exists to prevent. A step whose local date falls outside the
configured sending days **rolls forward and says it rolled** — sending silently
on the Saturday and silently dropping the step are both wrong. A company whose
timezone is unknown is **held in full rather than per step**, because six
identical refusals read as six problems rather than one, and it is never given
a time.

## Persona routing

Searching the same titles everywhere is not merely ineffective — each search is
a paid call, so a strategy that ignores size spends money finding people who do
not exist.

| Strategy | When | Priority |
|---|---|---|
| `founder_led` | 1–19 people, or size unknown | founder → operations |
| `operations_led` | 20–199 people | operations → finance → resource management → founder |
| `finance_led` | 200+ people, or a consultancy at 20–199 | finance → operations → delivery → resource management |
| `delivery_led` | software / product agencies at 20+ | delivery → operations → resource management → finance |

Five persona families: `founder`, `operations`, `finance`, `delivery`,
`resource_management`. Resource management is a family rather than a few titles
inside `delivery`, because where the role exists at all it owns scheduling
outright, and a persona that means two different jobs cannot be given one
angle. It is last in every priority list because it only exists above a certain
size.

An unknown size uses the founder strategy deliberately: it targets roles that
exist at every size. Strategies, titles and band mapping are all configurable.

## Credit planning

Three numbers, and they are different on purpose:

- **expected** — what this costs if it goes normally
- **maximum** — what it costs if every conditional call fires
- **fallback exposure** — the part of the maximum that only exists because a
  fallback might be needed

The batch cap is set against the **maximum**, because that is the number that
can arrive on an invoice. ContactOut stays first: the AI Ark fallback is
conditional, carries the reasons that would justify it, and is counted in the
maximum and never in the expectation.

At 5,000 companies: 1,978 planned searches, 3,248 maximum contacts, **23,028
expected credits, 26,984 maximum**, of which 3,956 is fallback exposure.

## The approval gate

    COMPANY ANALYSIS COMPLETE → REVIEW SUMMARY → APPROVE DM PLAN → ENRICHMENT

The approval fingerprints the qualification result — every company's status,
tier, contact cap and target titles. Requalify a batch and the fingerprint
changes, so an approval given for the old verdicts goes stale and says so.

`dmplan.may_enrich()` is the single gate, and it refuses a rejected or review
company *even when the batch approval is current*.

## Campaign segmentation

    PRODUCTIVE-UK-DIGITAL-50_199-OPERATIONS
    PRODUCTIVE-DACH-SOFTWARE-50_199-FINANCE
    PRODUCTIVE-NORDICS-CREATIVE-20_49-FOUNDER

Segments are built at full specificity and **merged upward** until each is
worth writing for. The ladder gives up the least important dimension first:

    full → band_family → vertical_family → region_family → persona_only

The persona is surrendered last, because a message to the wrong role is not a
coarser message — it is the wrong message. Minimum size (50) and maximum (500)
are configurable, and every company records which rung it ended on and why, so
"why are these two in the same campaign?" has a real answer.

At 5,000 companies: **17 segments, none below the minimum, none large enough
to split.**

## Messaging strategy

Structured input for a later generator, never copy. A pain is recommended only
where an ICP dimension actually fired; the typical-but-unsupported ones are
kept and labelled as **hypotheses** for a human rather than handed to a model
as facts.

## Resume

Every record carries the state it actually reached: `not_processed`,
`company_enriched`, `classified`, `review_required`, `qualified`, `rejected`,
`dm_enrichment_approved`, `dm_enrichment_pending`, `dm_enrichment_complete`.

Qualification stores a fingerprint of the inputs a verdict was derived from, so
re-running a batch requalifies the companies whose facts changed and skips the
rest. A batch that stops at company 2,731 resumes at 2,731.

## 5,000 companies, measured

| | |
|---|---|
| runtime | 6.4 s (787 companies/second) |
| peak memory | 92.1 MB |
| qualified / review / rejected / unknown | 1,978 / 922 / 1,332 / 768 |
| tiers A / B / C | 263 / 744 / 971 |
| needs manual review | 1,690 |
| companies costing zero person credits | 3,022 (60% of the upload) |
| schedulable | 4,630 (370 held for timezone) |
| campaign segments | 17, none below minimum |
| planned DM searches | 1,978 |
| expected / maximum credits | 23,028 / 26,984 (3,956 fallback exposure) |
| companies with contradictory evidence | 476 |

    python -m src.scalesim --qualify --size 5000

Every phase is linear in batch size, checked by comparing a 200-company run to
an 800-company one, best-of-three after a warm-up.

## The future web UI

`src/explorer.py` is the query layer a segment explorer will sit on.

**Filters** (exact match on stated vocabulary, so a saved view means the same
thing next month): icp_status, icp_tier, icp_confidence, vertical, subvertical,
industry, business_model, employee_band, country, region, timezone,
timezone_confidence, company_maturity, delivery_model, persona, strategy,
segment_key, state — plus ranges (`score_min`, `score_max`) and flags
(`manual_review`, `requires_enrichment`, `schedulable`).

**Drill:** batch → segment → company → persona_plan → contacts.

Contacts are a *declared* level that is empty until enrichment is approved and
run, so the UI's shape does not change when they arrive.

Two rules: an unknown filter name **raises** rather than returning everything —
a UI that silently ignores a typo teaches people to trust a wrong number — and
every list response carries `total` beside the page.

No function in the explorer spends a credit or calls a provider.
