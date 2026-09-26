BTW: one more architectural requirement for review.

Do NOT interrupt, restart, or reprioritize the Phase 1 / Second Brain work currently running.

Do NOT implement a large onboarding UI now.

Review the following requirement against the architecture currently being built and tell me:

1. what already supports it,
2. what does not,
3. what needs to change now to avoid architectural rework later,
4. what should explicitly wait until after the current Phase 1 work,
5. whether any part conflicts with the current Second Brain / Offer Engine / account-level architecture.

Then incorporate only the foundational changes that are necessary now and continue the work already running.

# CLIENT ONBOARDING PRINCIPLE

Long term, onboarding a new Resonate client should NOT require me to manually understand and populate a large YAML/configuration structure.

Resonate OS should progressively build the Client Second Brain itself and ask the operator only for information or decisions it cannot safely obtain or infer.

The target experience is:

NEW CLIENT
→ minimal operator input
→ automated client research
→ Second Brain draft
→ knowledge-gap detection
→ operator/client questions
→ ICP / segment proposals
→ Offer A / Offer B proposals
→ campaign architecture
→ account research
→ buying committee
→ Email + LinkedIn strategy
→ launch readiness
→ APPROVED
→ launch

## 1. MINIMUM INITIAL INPUT

Ideally I should be able to start onboarding with something close to:

- client/company name
- website
- short description of what they want to sell
- target geography if known
- known ICP if they already have one
- available sales materials/docs
- relevant integrations/accounts

Do not require information Resonate OS can reliably research itself.

## 2. BUILD CLIENT INTELLIGENCE AUTOMATICALLY

From the website, supplied materials and approved research sources, Resonate OS should attempt to build the Client Second Brain:

- company overview
- products/services
- capabilities
- use cases
- positioning
- pricing where publicly available
- business model
- implementation/delivery model
- limitations
- differentiation
- competitors
- competitor positioning/offers
- customers
- case studies
- approved evidence
- market intelligence
- possible ICPs
- possible segments
- likely buying committee
- persona relevance
- pain hypotheses
- existing claims
- potential offers
- messaging intelligence

Do not confuse discovered information with approved information.

## 3. KNOWLEDGE STATUS MUST BE EXPLICIT

Second Brain knowledge should support statuses such as:

VERIFIED
= supported by acceptable evidence/provenance.

CLIENT_APPROVED
= explicitly confirmed by operator/client.

INFERRED
= reasonable hypothesis but not established fact.

UNKNOWN
= insufficient information.

These statuses must affect downstream behavior.

VERIFIED / CLIENT_APPROVED:
may license appropriate factual claims.

INFERRED:
may inform strategy or be expressed carefully as a hypothesis/question, but must not automatically become a factual prospect-facing assertion.

UNKNOWN:
must not be invented.

Review whether the existing provenance/evidence architecture can represent this cleanly rather than creating another parallel system.

## 4. RESONATE OS SHOULD GENERATE QUESTIONS

After automated research, Resonate OS should determine:

WHAT DO I STILL NEED FROM THE OPERATOR OR CLIENT TO RUN THIS CAMPAIGN SAFELY AND WELL?

Example:

COMMERCIAL TERMS — REQUIRED

"I can verify the product and pricing, but I cannot determine whether outbound is allowed to offer a free trial, audit, pilot, consultation, discount or other commercial mechanism."

Then ask the operator.

Another example:

CUSTOMER EVIDENCE — REQUIRED

"I found customer logos but no approved quantitative customer result that can safely be used in outbound."

Options might include:

- provide case study
- upload evidence
- do not use customer-result claims

Another:

ICP AMBIGUITY

"I found three plausible segments:
Digital agencies
Software agencies
Consultancies

Which should we prioritize?"

The operator should make decisions.

The AI should surface the decision rather than silently choosing when the choice materially affects GTM strategy.

## 5. QUESTION PRIORITY

Do not create a 70-question onboarding questionnaire.

Questions should be generated from actual knowledge gaps.

Classify them where useful:

BLOCKING
Campaign cannot safely proceed.

IMPORTANT
Campaign can proceed, but quality would materially improve with an answer.

OPTIONAL
Useful enrichment but not necessary.

Resonate OS should tell me:

"I can complete 82% of the setup automatically. I need 6 decisions from you."

That is the desired operator experience.

## 6. CAMPAIGN ARCHITECT AFTER SECOND BRAIN

Once enough information exists, Resonate OS should propose campaigns rather than requiring the operator to construct them manually.

Example:

CAMPAIGN 1

Segment:
US Digital Agencies
20–100 employees

Buying committee:
COO — primary
CEO/Founder — secondary
Head of Delivery — secondary

Primary problem:
resource visibility / delivery profitability

Offer A:
[approved campaign offer]

Offer B:
[approved campaign offer]

Channels:
Email + LinkedIn heavy

Account strategy:
[summary]

Evidence available:
[...]

Missing evidence:
[...]

Operator actions:

APPROVE
EDIT
REJECT

Campaign creation should therefore consume the Second Brain rather than independently rediscovering the client strategy.

## 7. ACCOUNT-FIRST EXECUTION

After campaign approval:

CAMPAIGN
→ candidate companies
→ cheap qualification
→ qualified accounts
→ company-level research
→ account ranking
→ buying committee discovery
→ 2–3 relevant decision makers
→ person/role relevance
→ coordinated Email + LinkedIn outreach

Do not perform full company research independently for every contact.

Reuse account intelligence across the buying committee.

This must remain compatible with the previously stated account-level orchestration requirement.

## 8. LAUNCH READINESS

Before a campaign can be activated, Resonate OS should eventually provide a Launch Readiness assessment.

Examples:

Client Intelligence — PASS
ICP — PASS
Offer A/B — PASS
Claims — PASS
Account Research — PASS
Buying Committee — PASS
Email Copy — PASS
LinkedIn Copy — PASS
Cadence — PASS
Suppression — PASS
Sender Capacity — PASS
Cross-channel Safety — PASS

Warnings should remain warnings.

True safety/correctness blockers should prevent launch.

Example:

LAUNCH BLOCKED

2 blocking issues:

1. unsupported commercial claim
2. cross-channel stop behavior not verified

Each blocker should identify:

- what is wrong,
- whether OS can fix it,
- whether operator input is required,
- what component owns the issue.

Do not create meaningless readiness percentages unless they are derived from explicit checks.

## 9. ONBOARDING SHOULD BE CONVERSATIONAL

Long term I want to be able to say something like:

"Onboard Neuralab. Website is neuralab.net. We want to sell development services to US ecommerce companies. Martina owns the account."

Resonate OS should be capable of responding conceptually:

"Initial research complete.

I can prepare most of the client setup automatically.

I need the following 6 decisions before I can safely create Campaign 1."

The operator should not need to know which internal config fields need population.

Resonate OS translates operator intent into the canonical configuration and Second Brain structures.

## 10. CONTINUOUS ONBOARDING / LEARNING

Client onboarding should not become permanently frozen after launch.

The Second Brain should evolve from actual campaign evidence.

Examples:

replies
→ objections / pain evidence

referrals
→ buying committee evidence

meetings
→ confirmed pains / priorities

positive replies
→ offer/angle evidence

opportunities
→ commercial relevance

won/lost
→ strong outcome signal

However:

Do NOT allow the system to silently rewrite approved client strategy because of a handful of replies.

Learning should create evidence and recommendations.

Material strategy changes should remain versioned and operator-reviewable.

Eventually Resonate OS should be able to say:

"COOs in this segment are producing materially more qualified meetings than Founders when Offer A is used. Recommend changing the primary persona."

That is a recommendation, not an automatic rewrite of strategy unless explicitly authorized.

## 11. COST ARCHITECTURE

Design onboarding and Second Brain retrieval so knowledge is generated at the highest reusable level.

CLIENT KNOWLEDGE
→ generated/researched once and reused.

CAMPAIGN / SEGMENT / PERSONA STRATEGY
→ generated once per relevant strategy/version and reused.

ACCOUNT INTELLIGENCE
→ generated once per company/version and reused across its decision makers.

CONTACT INTELLIGENCE
→ only person-specific information.

MESSAGE GENERATION
→ only final context required for that person/channel.

Avoid architectures that repeatedly ask LLMs to rediscover:

- what the client sells,
- the client's capabilities,
- ICP,
- campaign strategy,
- offers,
- company research,

for every individual lead.

This is both a quality and cost requirement.

## 12. CONFIGURATION SHOULD BECOME AN IMPLEMENTATION DETAIL

Do not remove or destabilize the existing client config system.

Instead, long term, onboarding should populate/update the canonical underlying configuration safely.

The operator experience should be:

intent
→ research
→ questions
→ approvals

while Resonate OS handles:

schemas
configs
versions
provenance
dependencies
validation

underneath.

Existing config/clients and other canonical stores remain authoritative where appropriate.

Do not create a parallel Second Brain database merely to support onboarding.

## 13. REVIEW THIS AGAINST CURRENT PHASE 1

Before building this onboarding layer, review the current implementation.

Return a concise architecture review:

ALREADY SUPPORTED
What Phase 1 already provides.

FOUNDATION NEEDED NOW
Small structural changes needed now so onboarding will not require a rewrite later.

DEFER
Features/UI/workflows that should wait.

CONFLICTS
Anything here that conflicts with current implementation or operator directives.

RISKS
Especially duplicated truth, fabricated provenance, unnecessary LLM calls, disconnected producers, and automatic decisions that should require operator approval.

RECOMMENDED IMPLEMENTATION ORDER
How this should be added after/currently alongside Phase 1 without derailing current work.

Do not stop the current task merely to produce this review.

Continue the current work.

When there is a safe point, perform this review, persist the resulting architectural decision/spec in the repo, commit it, push it, and report the verified remote SHA.

Do not launch or activate any new prospect-facing campaigns as part of this work.

Current production freeze remains in force.
