BTW — do not stop or restart Phase 1 / Second Brain work if it is already in progress.

Continue from the current repository state and existing PHASE1 plan.

Before creating any additional Second Brain, Offer Engine, research, signal, or intelligence modules, audit the Phase 1 work that already exists and apply the following rules to it.

## 1. CONSUMER BEFORE PRODUCER

The TASK-317 finding is now an architectural warning, not an isolated bug.

No intelligence component is complete merely because it:

- researches something,
- extracts facts,
- stores facts,
- scores something,
- creates an index,
- creates provenance,
- or exposes a function.

For every existing and proposed Second Brain component, explicitly document:

SOURCE
→ CANONICAL STORAGE
→ RETRIEVAL
→ CONSUMER
→ DECISION / COPY EFFECT
→ VALIDATION

Every producer must have a named production consumer.

If a component currently has zero production callers, classify it explicitly as:

DISCONNECTED

Do not build another parallel implementation to solve that problem.

Wire the existing component correctly or document why it should be removed.

TASK-317's zero-caller finding must be incorporated into this review.

## 2. SECOND BRAIN MUST NOT BECOME A PARALLEL DATABASE

Preserve the operator requirement:

There must be one source of truth per fact.

Build the Second Brain on top of the existing:

- client config,
- research packs,
- playbooks,
- contextpack,
- campaign data,
- approved claims,
- offer data,
- learning data,
- existing docs where appropriate.

Do not copy the same client fact into multiple independent stores.

Every persisted fact should have, where applicable:

- value,
- source,
- source URL/reference,
- observed date,
- freshness,
- verification status,
- client,
- scope,
- provenance.

If the canonical value already exists in productive.yaml or another existing canonical store, reference it rather than creating another authoritative copy.

## 3. STRATEGY BEFORE PERSONALIZATION

The target architecture is:

CLIENT INTELLIGENCE
→ MARKET / ICP
→ CAMPAIGN STRATEGY
→ APPROVED OFFERS
→ ACCOUNT RESEARCH
→ SIGNAL / PERSON RELEVANCE
→ CONTROLLED PERSONALIZATION
→ COPY

Do not allow account-level AI to independently invent the sales strategy.

Account research may:

- establish relevance,
- select evidence,
- influence prioritization,
- influence which approved angle is strongest,
- personalize wording.

It must not independently invent:

- a new commercial offer,
- a new Productive capability,
- a discount,
- a pilot,
- a guarantee,
- a customer result,
- an unsupported problem,
- or an entirely new campaign strategy.

## 4. OFFER ENGINE BEFORE MORE PERSONALIZATION COMPLEXITY

Phase 1 should make the campaign offer explicit.

For each campaign define:

- ICP / segment,
- persona,
- primary problem,
- Offer A,
- Offer B,
- approved capabilities,
- supporting evidence,
- approved CTA strategy,
- allowed claims,
- prohibited claims.

IMPORTANT:

Two offers does NOT mean two outreach steps.

Email cadence remains FIVE steps.

HeyReach remains multi-step.

The five email messages should strategically develop the campaign's approved offers rather than inventing five separate per-lead pitches.

## 5. SECOND BRAIN INDEX

The Second Brain index should be a navigation and retrieval layer over canonical knowledge, not another independent truth store.

It should make visible:

- Client profile
- ICP
- Market intelligence
- Competitors
- Customer intelligence
- Approved capabilities
- Offers
- Evidence / cases
- Messaging guidance
- Campaigns
- Performance learning
- Missing information
- Research priorities

Most importantly, show:

USED BY

for every important knowledge object.

I want to be able to see which skills, campaign strategies, copy stages, validators, or learning components actually consume that knowledge.

A beautiful Second Brain full of facts that never reach campaign strategy or copy is a failed implementation.

## 6. SKILLS MUST BE EXECUTABLE WORKFLOW COMPONENTS

Phase 1 still starts with the five approved skills:

1. Account Research
2. Signal Verification
3. Campaign Strategy
4. Cold Email Writing
5. LinkedIn Writing

Do not create ten more skills yet.

Each skill must specify:

- purpose,
- inputs,
- Second Brain context retrieved,
- tools/sources allowed,
- procedure,
- good examples,
- bad examples,
- what NOT to do,
- output schema,
- validation,
- failure behavior,
- human escalation,
- downstream consumer.

The skill must actually be called by the production workflow.

A Markdown file describing best practice but never used by an agent is documentation, not an implemented skill.

## 7. FIX PROVENANCE PROPERLY

GLM already identified fabricated provenance in TASK-317.

Treat this as P0.

Never fabricate provenance to satisfy a schema or validator.

If source provenance is unavailable, store:

UNKNOWN / UNVERIFIED

and prevent that fact from licensing a prospect-facing claim where appropriate.

A missing source is preferable to a fake source.

Add tests specifically proving that fabricated or synthetic provenance cannot pass as verified evidence.

## 8. VERSION THE CONTEXT USED FOR DECISIONS

The recent production work has shown that system state changes quickly while multiple lanes and agents operate concurrently.

For significant generated artifacts and batch decisions, record enough context to reproduce the decision.

At minimum where relevant:

- repo commit SHA,
- client config version/hash,
- campaign ID,
- campaign strategy version,
- offer version,
- cadence version,
- research/context pack version,
- provider snapshot timestamp,
- generation timestamp.

Do not blindly regenerate everything when one component changes.

The purpose is traceability:

"What exact knowledge and strategy caused this message to be generated?"

## 9. DO NOT LET VALIDATORS BECOME VOCABULARY MATCHERS

The overnight research/copy work demonstrated that lexical overlap can produce false confidence.

A message sharing the word "marketing" with a research pack is not evidence that the message is grounded in the research.

Grounding validation must evaluate whether the prospect-facing claim is actually supported by the underlying evidence.

Keep deterministic safety gates authoritative.

Semantic validation may add another layer, but an LLM score must never override deterministic failures.

## 10. PRESERVE CURRENT PRODUCTION SAFETY

Do not let this architecture work interfere with current campaigns or pending production work.

Preserve:

- EmailBison integration,
- HeyReach integration,
- suppression,
- approvals,
- cross-channel safety work,
- spend ceilings,
- tenancy,
- existing campaign history,
- five-step email cadence,
- existing threading rules currently verified by the repository,
- multi-step LinkedIn cadence.

Do not send or activate anything because of this directive.

Do not silently migrate active campaigns to the new architecture.

## 11. GITHUB IS MANDATORY

Continue the GitHub discipline established in the latest handoff.

Every completed Phase 1 task must be:

- documented,
- tested,
- committed,
- pushed,
- remote SHA verified.

No meaningful Phase 1 implementation should exist only in a worktree, local branch, Claude session, Qwen session, Slack message, or temporary work directory.

For every completed task report:

TASK
STATUS
FILES
TESTS RUN
TEST RESULT
CONSUMER
LOCAL SHA
REMOTE SHA
BRANCH
MERGE STATUS
PRODUCTION IMPACT

Never report DONE if the artifact has not been pushed and verified remotely.

## 12. ACTION NOW

Do NOT restart Phase 1.

Do NOT duplicate work already implemented.

First read:

docs/PRODUCTION-HANDOFF-2026-09-26-MORNING.md

docs/OPERATOR-DIRECTIVES-2026-09-25.md

docs/PHASE1-PLAN-2026-09-26.md

docs/ARCHITECTURE-UPGRADE-SPEC.md

Then inspect all Phase 1 / Second Brain tasks already implemented, running, in review, or queued.

Produce a concise table:

TASK
COMPONENT
STATUS
PRODUCER
CANONICAL STORE
PRODUCTION CONSUMER
TESTED
REMOTE SHA
ACTION

Specifically flag:

- zero-caller components,
- duplicate stores,
- fabricated or missing provenance,
- data produced but never consumed,
- skills existing only as documentation,
- Offer Engine work that can invent unsupported offers,
- research that cannot affect campaign strategy or copy,
- validators that pass on lexical coincidence.

Fix P0 correctness problems before expanding the architecture.

Then continue the existing Phase 1 plan rather than creating a new one.

Commit and push any changes.

Report the verified origin/master SHA when complete.
