# OFFER REVIEW — the six pending offers, 2026-09-26

**FIRST PASS (below) read `config/clients/productive-offers.yaml` on
`origin/master` at `c70db5ef` and modified nothing.**

**SECOND PASS (at the end of this file) applies the operator's decisions of
2026-09-26 and DOES change config — wording, evidence and mechanisms. Read it
alongside the first pass: where the two differ, the second pass is current.
`approval_status` was NOT changed in either pass and remains `pending` on all
six.**

**No recommendation on which offer to approve.** What follows is provenance,
conflicts and gaps. Two offers carry problems that need resolving before
approval; one of those is a direct contradiction of canonical config.

## How provenance was established

Every field below was traced to one of exactly three places:

    CLIENT_APPROVED   the client's own words in productive.yaml
                      product.capabilities — verbatim, character for character
    INFERRED          written for the offer library, a restatement or an
                      inference, NOT present in any canonical store
    UNKNOWN           absent, and listed in the offers file's own `missing:` block

**The load-time gate that already works:** `offers._validate` refuses any offer
naming a capability outside Productive's six confirmed capabilities, and refuses
any offer with no explicit `approval_status`. All six pass that gate. It does not
check personas, deliverables or evidence — which is where the problems are.

**The refusal that already works:** `offers.for_campaign(503, require_approved=True)`
raises `NotApproved`. Verified by running it. **No offer can reach copy generation
today.** That is correct, not a fault.

---

## OFFER-PM-001 — Project management

| | |
|---|---|
| **Segment / persona** | `all` / `champion` |
| **Capability** | `project_management` |
| **Problem** | projects tracked in spreadsheets and tools that do not talk to each other |
| **Value proposition** | projects, tasks and delivery in one place |
| **Concrete deliverable** | a single view of every project, its tasks and its delivery status |
| **CTA** | see what your projects look like in one place |
| **Commercial terms** | `no commercial terms - capability description only` |
| **Guarantee / discount / pilot / free work / customer result** | **NONE.** No promise of any kind. |
| **Supporting evidence** | `[]` — empty |
| **approval_status** | `pending` |
| **Campaigns** | `[503]` |

**Provenance**

- Value proposition — **CLIENT_APPROVED.** Verbatim
  `product.capabilities.project_management`: *"projects, tasks and delivery in one
  place"*.
- Problem — **INFERRED.** Not in any canonical store.
- Concrete deliverable — **INFERRED.** A restatement of the capability sentence.
  *"a single view"* is a product-behaviour assertion the config does not make.
- Persona `champion` — **INFERRED.** `product.capability_by_persona` maps only
  `economic_buyer → profitability` and `champion → budgeting`. It says nothing
  about `project_management`.

**If approved, copy could say:** that Productive puts projects, tasks and delivery
in one place, in the client's own words.

**Copy still could NOT say:** any customer result or named customer; any metric,
percentage or time saved; that it is faster/cheaper/better than a named
competitor; anything about pricing, a trial, a pilot, a discount or a guarantee;
that a dashboard, demo or screenshot can be shown — **none exists**.

---

## OFFER-TT-001 — Time tracking

| | |
|---|---|
| **Segment / persona** | `all` / `champion` |
| **Capability** | `time_tracking` |
| **Problem** | time booked in one tool and budgets tracked in another |
| **Value proposition** | time booked against the project and the budget it belongs to |
| **Concrete deliverable** | time entries linked to the project and budget they belong to |
| **CTA** | see where your team time actually goes |
| **Commercial terms** | `no commercial terms - capability description only` |
| **Guarantee / discount / pilot / free work / customer result** | **NONE.** |
| **Supporting evidence** | `[]` |
| **approval_status** | `pending` |
| **Campaigns** | `[503]` |

**Provenance**

- Value proposition — **CLIENT_APPROVED.** Verbatim
  `product.capabilities.time_tracking`.
- Problem — **INFERRED.**
- Concrete deliverable — **INFERRED**, but the closest of the six to its source:
  it restates the capability sentence without adding a new product behaviour.
- Persona `champion` — **INFERRED.** Not covered by `capability_by_persona`.

**If approved, copy could say:** that time is booked against the project and the
budget it belongs to.

**Copy still could NOT say:** how much time anyone saves; any customer example;
anything about accuracy, compliance or payroll; any commercial term.

---

## OFFER-BU-001 — Budgeting ⚠ **BLOCKED**

| | |
|---|---|
| **Segment / persona** | `all` / **`economic_buyer`** |
| **Capability** | `budgeting` |
| **Problem** | a project quoted at one number and burning at another with no visibility in between |
| **Value proposition** | what a project was quoted at and what it has burned so far |
| **Concrete deliverable** | **live** budget burn visibility from quote to current spend |
| **CTA** | know whether a project is making money while it is still running |
| **Commercial terms** | `no commercial terms - capability description only` |
| **Guarantee / discount / pilot / free work / customer result** | **NONE.** |
| **Supporting evidence** | `[]` |
| **approval_status** | `pending` |
| **Campaigns** | `[]` |

### Why BLOCKED — it contradicts canonical config

`config/clients/productive.yaml` → `product.capability_by_persona`:

    economic_buyer: profitability
    champion:       budgeting

**This offer assigns `budgeting` to `economic_buyer`. The canonical store assigns
`budgeting` to `champion`.** That is not a gap or an inference — it is a direct
conflict with the client's own persona mapping, and `_validate` does not catch it
because it only checks capability names.

Either the offer's persona is wrong, or `capability_by_persona` is out of date.
**Both are operator/client decisions, not engineering ones.** Approving the offer
as it stands would put a champion-mapped capability in front of an economic buyer.

### Second problem — unsupported specificity

The deliverable says **"live"** budget burn. The capability sentence says *"what a
project was quoted at and what it has burned so far"* — a statement of what is
shown, not of when. **"Live" is an inferred product claim**, and it cannot be
demonstrated: there is no dashboard example and no demo link (both in `missing`).

**Copy could NOT say** "live", "real-time", or "as it happens" on this offer
unless the client confirms it.

---

## OFFER-RP-001 — Resource planning

| | |
|---|---|
| **Segment / persona** | `all` / `champion` |
| **Capability** | `resource_planning` |
| **Problem** | no visibility on who is booked on what next week |
| **Value proposition** | who is booked on what next week, and where the next hire goes |
| **Concrete deliverable** | a forward-looking view of who is booked where and where the next hire goes |
| **CTA** | see who is booked on what next week |
| **Commercial terms** | `no commercial terms - capability description only` |
| **Guarantee / discount / pilot / free work / customer result** | **NONE.** |
| **Supporting evidence** | `[]` |
| **approval_status** | `pending` |
| **Campaigns** | `[]` |

**Provenance**

- Value proposition — **CLIENT_APPROVED.** Verbatim
  `product.capabilities.resource_planning`.
- Problem — **INFERRED**, and it is a near-restatement of the value proposition
  rather than an independent problem statement.
- Concrete deliverable — **INFERRED.** Adds *"forward-looking view"*.
- Persona `champion` — **INFERRED.** Not covered by `capability_by_persona`.

**Note:** this is the capability the fifty actually used most —
`resource_planning` was one of the three distinct capabilities selected across
the 31 written leads.

**If approved, copy could say:** who is booked on what next week, and where the
next hire goes.

**Copy still could NOT say:** any utilisation percentage, any headcount
recommendation, any hiring advice presented as Productive's output, or any
customer example.

---

## OFFER-BI-001 — Billing

| | |
|---|---|
| **Segment / persona** | `all` / `economic_buyer` |
| **Capability** | `billing` |
| **Problem** | invoices retyped from time and budget records instead of raised from them |
| **Value proposition** | invoices raised from the time and the budget rather than retyped |
| **Concrete deliverable** | invoices generated directly from tracked time and project budgets |
| **CTA** | stop retyping invoices from spreadsheets |
| **Commercial terms** | `no commercial terms - capability description only` |
| **Guarantee / discount / pilot / free work / customer result** | **NONE.** |
| **Supporting evidence** | `[]` |
| **approval_status** | `pending` |
| **Campaigns** | `[]` |

**Provenance**

- Value proposition — **CLIENT_APPROVED.** Verbatim `product.capabilities.billing`.
- Problem — **INFERRED.**
- Concrete deliverable — **INFERRED**, close to source.
- Persona `economic_buyer` — **INFERRED.** Not covered by `capability_by_persona`.

**One wording flag.** The CTA says *"stop retyping invoices from **spreadsheets**"*.
The capability sentence does not mention spreadsheets, and this asserts something
about **the prospect's** current process. It is a presumption about them, not a
claim about Productive — so `copylint`'s anti-fabrication rule, which checks claims
against the prospect's research pack, may or may not catch it depending on the
pack. Worth the client's view on whether that presumption is fair to make cold.

**If approved, copy could say:** invoices raised from the time and the budget
rather than retyped.

**Copy still could NOT say:** any billing accuracy figure, any hours saved, any
integration with a named accounting package, or any customer example.

---

## OFFER-PR-001 — Profitability

| | |
|---|---|
| **Segment / persona** | `all` / `economic_buyer` |
| **Capability** | `profitability` |
| **Problem** | margin visible only after a project closes, not while it is running |
| **Value proposition** | margin per project while it is running, not after it closes |
| **Concrete deliverable** | **real-time** margin per project visible during delivery |
| **CTA** | see project margin while the project is still running |
| **Commercial terms** | `no commercial terms - capability description only` |
| **Guarantee / discount / pilot / free work / customer result** | **NONE.** |
| **Supporting evidence** | `[]` |
| **approval_status** | `pending` |
| **Campaigns** | `[]` |

**Provenance**

- Value proposition — **CLIENT_APPROVED.** Verbatim
  `product.capabilities.profitability`.
- Problem — **INFERRED.**
- Concrete deliverable — **INFERRED**, and it adds **"real-time"**, which the
  capability sentence does not say. Same issue as BU-001's "live", and
  undemonstrable for the same reason: no dashboard example, no demo.
- **Persona `economic_buyer` — CLIENT_APPROVED.** `capability_by_persona` maps
  `economic_buyer → profitability`. **This is the only one of the six whose persona
  is confirmed by canonical config.**

**If approved, copy could say:** margin per project while it is running rather than
after it closes.

**Copy still could NOT say:** "real-time" (unconfirmed); any margin figure or
percentage; any customer outcome; that margin is *accurate* or *complete*, which
depends on the client's own data hygiene.

---

## COMPARISON — all six

| Offer | Capability | Persona | Persona vs canonical | Value prop provenance | Deliverable | Evidence | Terms | Campaigns | Status |
|---|---|---|---|---|---|---|---|---|---|
| **PM-001** | project_management | champion | not mapped → INFERRED | CLIENT_APPROVED verbatim | INFERRED ("a single view") | `[]` | none | 503 | pending |
| **TT-001** | time_tracking | champion | not mapped → INFERRED | CLIENT_APPROVED verbatim | INFERRED, close to source | `[]` | none | 503 | pending |
| **BU-001** | budgeting | economic_buyer | **CONFLICT — canonical says champion** | CLIENT_APPROVED verbatim | INFERRED + **"live"** unsupported | `[]` | none | — | **BLOCKED** |
| **RP-001** | resource_planning | champion | not mapped → INFERRED | CLIENT_APPROVED verbatim | INFERRED ("forward-looking") | `[]` | none | — | pending |
| **BI-001** | billing | economic_buyer | not mapped → INFERRED | CLIENT_APPROVED verbatim | INFERRED, close to source | `[]` | none | — | pending |
| **PR-001** | profitability | economic_buyer | **CLIENT_APPROVED ✓** | CLIENT_APPROVED verbatim | INFERRED + **"real-time"** unsupported | `[]` | none | — | pending |

**Uniform across all six:** `segment: all` — no segmentation at all, while
`campaignstrategy.for_segment` keys strategy on `(segment, persona)`. Six offers
with `segment: all` cannot differentiate three cohorts. **`supporting_evidence` is
empty on every one.** **No offer contains a guarantee, discount, pilot, free work,
trial, customer result or named customer** — the library is clean of invented
commercial terms, which is the thing most likely to have gone wrong and did not.

## THE ONE EFFECTIVE DUPLICATE — BU-001 and PR-001

Distinct capabilities per the client, but at the level of what a prospect reads
they make **the same argument**:

    BU-001 CTA   "know whether a project is making money while it is still running"
    PR-001 CTA   "see project margin while the project is still running"

*Making money while it is still running* and *margin while the project is still
running* are the same assertion. Both target `economic_buyer`. Both are about
in-flight financial visibility. Both deliverables add an unsupported immediacy
claim ("live" / "real-time").

**Why this matters mechanically:** if both are approved and used as Offer A and
Offer B on one campaign, the five-email sequence would develop one argument twice.
That is precisely what `sequencegate` exists to refuse — and the fifty already
shows 10 sequencegate failures, 4 of them `claims_supported` on em5.

They are **not** duplicates at the capability level: budget burn (quoted vs spent)
and margin (revenue vs cost) are different numbers. The duplication is in the
**message**, not the data.

---

## QUESTIONS FOR PRODUCTIVE

Copy-paste to the client. Each maps to a gap that currently blocks evidence or a
claim.

### Commercial mechanisms — BLOCKING

1. **Is outbound allowed to offer anything at all beyond a conversation?** A free
   trial, a demo, an audit, a pilot, a consultation, a discount, or a
   proof-of-concept. Right now every offer says "no commercial terms", so our
   emails can only invite a conversation.
2. **If a demo may be offered, what exactly is being offered** — a live call, a
   recorded walkthrough, a sandbox — and **who delivers it?**
3. **Is there any pricing we may state or reference publicly?**

### Customer evidence — BLOCKING for any result claim

4. **Can you supply one customer case study we may quote**, with the customer's
   permission to be named, or anonymised as "a 40-person agency in X"?
5. **Is there any quantified outcome we may use** — margin improvement,
   utilisation gain, hours saved, invoicing time reduced — with a source we can
   attribute?
6. **May we name any existing customer at all**, or is the customer list
   confidential?

### Assets — BLOCKING for anything visual or linked

7. **Is there a screenshot or short walkthrough of the interface we may send?** We
   currently have none, so we cannot show what any of these six offers looks like.
8. **Is there a live or recorded demo we may link to?**
9. **Is there an ROI or savings calculator?**
10. **`https://productive.io/get-started/` is the CTA link we hold.** Is that the
    right destination for a cold prospect, or should it be a different page?

### Product claims — needed to lift specific wording

11. **Is budget burn genuinely LIVE, and is margin genuinely REAL-TIME?** Both
    words appear in our offer deliverables and neither appears in your capability
    descriptions. If they are accurate we can use them; if they update on a
    schedule, what is it?
12. **Does billing integrate with named accounting software?** Our billing offer
    says invoices are "generated directly from tracked time and project budgets" —
    we cannot currently say what happens next.

### Persona mapping — the BLOCKED item

13. **Your config maps `budgeting → champion` and `profitability → economic
    buyer`. Our budgeting offer targets the economic buyer. Which is right?**
    Should budgeting be pitched to the operations/finance champion, or to the
    economic buyer?
14. **Who owns each of the other four capabilities** — project management, time
    tracking, resource planning, billing? We have inferred the persona for all
    four and your config does not cover them.

### Segmentation

15. **Should these offers differ by segment?** All six are `segment: all`. If
    digital agencies, software agencies and consultancies need different offers or
    different wording, say which, and we will split them.

---

## WHAT HAPPENS NEXT — nothing, until you say

`approval_status` is untouched on all six. No offer can reach copy generation while
it is `pending`; `for_campaign(..., require_approved=True)` raises `NotApproved`,
verified.

**BU-001 should not be approved as written** — its persona contradicts canonical
config, and that conflict must be resolved in one place or the other first.

Answering questions 1, 4 and 7 would unlock the most: commercial mechanism,
customer evidence and a visual asset are the three gaps that keep every offer at
capability-description level.


---
---

# OPERATOR DECISIONS APPLIED — 2026-09-26, second pass

Answering §12. Narrow, no redesign. **No `approval_status` changed — still 6
pending, verified after every edit.**

## CURRENT OFFER MODEL

    productive.yaml product.capabilities           6 capability sentences
    productive-offers.yaml offers:                 6 records, one per capability
    campaignstrategy.for_segment(segment, persona) selects from them

One record per capability, one capability per record, `segment: all` on all six.
There is no layer between a capability and what a prospect is offered.

## WHAT THE SIX RECORDS REPRESENT

| Record | CAPABILITY | VALUE PROPOSITION | MESSAGING ANGLE | PROSPECT-FACING OFFER | COMMERCIAL OFFER |
|---|---|---|---|---|---|
| PM-001 | yes | yes | yes | no | no |
| TT-001 | yes | yes | yes | no | no |
| BU-001 | yes | yes | yes | no | no |
| RP-001 | yes | yes | yes | no | no |
| BI-001 | yes | yes | yes | no | no |
| PR-001 | yes | yes | yes | no | no |

Every record is a capability plus its value proposition, usable as a messaging
angle. **Not one is a prospect-facing offer**, because none carries a mechanism —
nothing a prospect is invited to do or receive. `conditions` says so on all six:
*"no commercial terms - capability description only"*. None is a commercial offer.

## MODEL CLASH: **YES**

The Offer layer is occupied by capabilities. The hierarchy runs
`CAPABILITY renamed as OFFER → COPY`, the shape you named as wrong. The missing
layer is the one that turns capabilities into something offered.

Two mechanical consequences, both live:

- **A campaign cannot have Offer A and Offer B** in any meaningful sense. It has
  six capability descriptions with identical `segment: all`.
- **`campaignstrategy` selects a capability and calls it an offer.** It carries
  `primary_offer` and `secondary_offer` fields whose values are capability records.

## CAN THE CURRENT MODEL SUPPORT TRUE OFFER A/B: **PARTIAL**

The plumbing exists and is sound — load-time validation against
`CONFIRMED_CAPABILITIES`, an explicit `approval_status`, a real `NotApproved`
refusal, `missing()` listing gaps, and `campaignstrategy` already keying on
`(segment, persona)` with `primary_offer` / `secondary_offer` fields waiting.

What is missing is one layer of data and two fields. **No code needs rewriting.**

## SMALLEST REQUIRED MODEL CHANGE

Preserves all existing work. Three steps, additive:

**1. Rename the existing block, do not move it.** `offers:` becomes
`capabilities:` in `productive-offers.yaml`. The six records already *are*
capability records; the key is the only lie. `offers._validate` and
`CONFIRMED_CAPABILITIES` keep working untouched.

**2. Add a real `offers:` block above it — two records, not six.** Each references
capability ids rather than restating them, and each adds the two fields that make
it an offer:

    mechanism    demo / free_trial / public_tool — from the new `mechanisms:` block
    cta_link     the verified URL for that mechanism

**3. `campaignstrategy` reads the new `offers:` block.** Its `primary_offer` and
`secondary_offer` fields already exist and already expect one identifier each.

Provenance survives unchanged: capability sentences stay CLIENT_APPROVED verbatim;
mechanisms carry their own status; evidence carries URL, retrieval date and status.
Prospect-facing claims still fail closed — an offer whose `approval_status` is not
`approved` still raises `NotApproved`, now at the offer layer where it belongs.

## CANONICAL CONFIG CHANGES REQUIRED

**Done in this pass:**

- `productive-offers.yaml` — **"real-time" removed** from PR-001, **"live" removed**
  from BU-001 (§4). Now *"margin per project visible while the project is still
  running"* and *"budget burn visibility from quote to current spend"*.
- **`evidence:` block added** — 11 case studies, `status: CLIENT_APPROVED`, URL and
  `retrieved: 2026-09-26` on each, and **`page_text: null`**.
- **`mechanisms:` block added** — demo (OPERATOR_APPROVED, `book-a-demo/`), free
  14-day trial (public + operator approved, `get-started/`), objective
  `interest → booked meeting → AE → discovery-led handoff`. All links **verified
  HEAD 200 on 2026-09-26**.
- **`public_tools:` added** — Agency Valuation Calculator, Billable Hours
  Calculator, VERIFIED.

**NOT done, and deliberately left for you — `capability_by_persona`:**

§5 says correct `champion → budgeting` as stale so budgeting maps to the economic
buyer. **I could not do that without making a decision you did not make**, so I
reverted my first attempt rather than leave it standing:

    the field holds ONE capability per persona
    economic_buyer: profitability      <- CLIENT_APPROVED, and §11 keeps it
    champion:       budgeting          <- stale per §5

Moving `budgeting` to `economic_buyer` **displaces `profitability`**, and §11 gives
the economic buyer *both*. The schema cannot hold that, and it is load-bearing:

    src/cadence.py:775   key = capability_by_persona.get(persona)
                         sentence = capabilities.get(key)

A single-key lookup on the copy path — a list breaks it. So this needs
`cadence.product_words` changed: code on the copy path, with tests, not a config
edit. **Two questions only you can answer:**

1. Should the field become a **list** per persona (needs the `cadence.py` change), or
2. should it be **retired** in favour of the new `offers:` block, which will carry
   persona → capabilities properly?

The field is exactly as it was. Nothing reads a mapping that contradicts your
decision, because nothing was changed.

## PROPOSED OFFER A — economic buyer

| | |
|---|---|
| **Target persona** | CEO, Founder, Owner, COO, CFO (§6) |
| **Target problem** | margin and budget position invisible until a project closes |
| **Capabilities used** | `profitability` + `budgeting` |
| **Approved value proposition** | *"margin per project while it is running, not after it closes"* and *"what a project was quoted at and what it has burned so far"* — **both verbatim CLIENT_APPROVED** from `product.capabilities` |
| **Mechanism** | demo / walkthrough with a Productive AE; demo period up to one month if needed |
| **CTA** | book a demo — `https://productive.io/book-a-demo/` (HEAD 200 verified), or the segmented meeting link for the account's employee count |
| **Evidence** | one CLIENT_APPROVED case study, closest by industry/size/geography, **named only** until TASK-365 stores page text |
| **Provenance** | value props CLIENT_APPROVED · mechanism OPERATOR_APPROVED · evidence CLIENT_APPROVED, page text absent |

**Explicitly excluded:** "real-time", "instant", "live to the second"; any margin
or budget figure; any ROI, percentage or time saved; any case-study number until
traced; discounts, guarantees, free consulting, free audits, custom
implementations, POCs, customer-specific deliverables, pricing promises.

## PROPOSED OFFER B — operations

| | |
|---|---|
| **Target persona** | Operations Manager, Project Manager, Finance Manager (§6) |
| **Target problem** | delivery, time and resourcing split across tools that do not talk |
| **Capabilities used** | `project_management` + `time_tracking` + `resource_planning` |
| **Approved value proposition** | *"projects, tasks and delivery in one place"*, *"time booked against the project and the budget it belongs to"*, *"who is booked on what next week, and where the next hire goes"* — **all three verbatim CLIENT_APPROVED** |
| **Mechanism** | free 14-day trial, no credit card required; or demo |
| **CTA** | start the trial — `https://productive.io/get-started/` (HEAD 200 verified) |
| **Evidence** | one CLIENT_APPROVED case study, named only, same rule |
| **Provenance** | value props CLIENT_APPROVED · trial VERIFIED public + brief · evidence CLIENT_APPROVED, page text absent |

**Explicitly excluded:** what happens inside a demo or trial beyond verified
material; any utilisation or hours-saved figure; *"reduce admin by 30%"* and
anything quantified without evidence; the same exclusion list as Offer A.

**`billing` (BI-001) sits in neither.** It is not dropped — no capability is
deleted (§10) — but §11 names three capability groups for B and billing is not one
of them. Placing it is your call.

## THE BU-001 / PR-001 DISTINCTION UNDER A/B — §10

Offer A/B **removes the duplicated argument**, and mechanically here is why: both
capabilities now sit inside **one** offer, so they are no longer two competing
offers making one argument. The distinction you drew survives as two different
numbers inside one financial-visibility offer:

    budgeting      quoted or budgeted VERSUS consumed
    profitability  revenue, cost and margin

**The sequence must still not develop them as one argument**, and `sequencegate` is
now wired into `bisonfactory` to refuse it if it does. The earlier duplication was
at the CTA level — *"making money while it is still running"* versus *"margin while
the project is still running"* — and under A/B only one CTA exists per offer, which
is what removes it.

## REMAINING BLOCKERS BEFORE YOU CAN APPROVE OFFER A/B

Only what is genuinely required for the first vertical slice:

1. **`capability_by_persona`** — list, or retire it? Above. The only item needing a
   decision from you rather than work from us.
2. **The `offers:` → `capabilities:` rename plus the two-record `offers:` block** —
   the smallest model change. A task, not a decision.
3. **`billing`'s placement** — Offer A, Offer B, neither, or its own offer.
4. **TASK-365** — store the case-study page text so a figure becomes quotable.
   Until then copy may name a study and quote nothing from it.
5. **Segmented meeting links** — the client material has links by employee count.
   They are **not in the repo**; we hold only `book-a-demo/`. Supply them, or
   confirm the generic link is right for the slice.

**Not blockers:** trial provenance (verified public and in the brief,
reconfirmation requested), demo mechanism (approved), personas (§6), ICP (§7),
messaging themes (§8), evidence status (§9).

## WHAT CONTINUES WITHOUT THIS DECISION

Everything on the critical path. None of it waits on an approved offer:

- **TASK-321 rework** — the v2 pipeline's production entrypoint. Its blocker is the
  closed-loop wiring finding, not an offer.
- **Five Skills integration** — verified safe, no offer dependency.
- **TASK-364 SequencePlan** — one canonical object for preview, XLSX, hash and both
  provider payloads.
- **TASK-343** preview's invented LinkedIn days · **TASK-328** approval hash ·
  **TASK-331** suppression on resume · **TASK-330** grounding · **TASK-354** CTA
  link rule · **TASK-365** case-study page text.
- The vertical slice itself, up to the point where copy needs an approved offer.

**What cannot proceed:** generating prospect-facing copy that carries an offer.
`for_campaign(..., require_approved=True)` raises `NotApproved`, and that is
correct.
