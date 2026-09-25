# RESONATE OS: GTM Intelligence & Outreach Architecture Upgrade

## YOUR ROLE

You are the lead architect and senior GTM engineer responsible for reviewing and improving Resonate OS.

Repository: https://github.com/KatoKhan8/resonate-group-automation

I want you to review the existing architecture and propose a substantial upgrade to how Resonate OS researches clients, develops campaign strategies, generates outreach, evaluates signals, and learns from campaign performance.

This is an architectural improvement proposal, NOT authorization to immediately implement changes.

First, inspect the actual repository, identify what already exists, determine what needs improvement, and present a concrete implementation plan.

Do not rebuild existing functionality unnecessarily.

Preserve all existing production safety mechanisms, integrations, approval workflows, and historical campaign data.

---

# 1. NON-NEGOTIABLE REQUIREMENTS

The existing outreach cadence must remain intact.

## EMAIL CADENCE

Keep the existing five-step email cadence.

Do NOT reduce the email sequence to two steps.

Do NOT replace the current cadence with a two-message outreach model.

Preserve the existing threading structure:

- Email 1: New thread, subject A.
- Email 2: Reply to thread A.
- Email 3: New thread, subject B.
- Email 4: Reply to thread B.
- Email 5: New breakup thread, subject C.

Preserve the existing scheduling configuration unless an explicitly approved campaign-level change is required.

The goal is to improve the quality, relevance, and strategic purpose of all five emails.

Every email must introduce a meaningful new angle, insight, offer, resource, or reason to engage.

Do not generate five variations of the same sales pitch.

## LINKEDIN CADENCE

Preserve the existing multi-step HeyReach outreach architecture.

Do not reduce the LinkedIn sequence to two steps.

Maintain existing connection requests, follow-up messages, campaign steps, scheduling, sender assignment, cross-channel coordination, and reply handling.

Inspect the actual HeyReach implementation before proposing modifications.

The email and LinkedIn sequences must remain coordinated without duplicating the same argument or question unnecessarily.

Preserve existing provider-specific limitations and validated capabilities.

## PRODUCTION SAFETY

Do not modify active campaigns, sending schedules, production configurations, or existing provider campaigns without explicit authorization.

Preserve:

- EmailBison integration.
- HeyReach integration.
- Existing approval and activation gates.
- Suppression and do-not-contact rules.
- Cross-channel reply detection and stopping.
- Account-level contact restrictions.
- Existing campaign and sender ownership.
- Idempotency and duplicate prevention.
- Rate limits and spending controls.
- Workspace and client isolation.
- Audit trails and historical records.
- Existing copylint and sequencegate protections.

No messages should be sent or campaigns activated during this review.

---

# 2. THE CORE STRATEGIC CHANGE

The current copy engine is heavily focused on generating personalized outreach at the individual lead level.

I want to move toward a campaign-first, intelligence-driven architecture.

The new hierarchy should be:

Client Intelligence → Market Research → ICP & Segment Strategy → Campaign Offer Strategy → Account Research → Signal Validation → Controlled Personalization → Five-Step Email Cadence + Multi-Step HeyReach Cadence → Performance Learning.

The most important principle:

AI should not invent a completely new sales strategy for every individual lead.

Instead, the system should develop a strong, research-backed campaign strategy and dedicated offers for each segment.

Individual personalization should adapt that strategy using verified account and person-specific information.

Research determines relevance.

The approved offer determines what we are selling.

The campaign strategy determines how we communicate it.

AI helps execute, personalize, and improve the strategy.

The goal is not maximum personalization.

The goal is relevant, commercially effective outreach at scale.

---

# 3. BUILD A CLIENT SECOND BRAIN

I want a structured, persistent intelligence workspace for every client.

Before proposing a new system, inspect the existing:

- Client configurations.
- Research modules.
- Research packs.
- Context packs.
- Playbooks.
- GTM decision memory.
- Campaign strategy modules.
- Reporting and learning infrastructure.

Determine what can be reused.

The Client Second Brain should become the central source of client-specific knowledge for research agents, campaign strategy agents, offer development, and copy generation.

It should contain the following sections.

## A. Client Profile

Research and document:

- What the client sells.
- Product and service capabilities.
- Pricing and packaging.
- Primary use cases.
- Customer onboarding and implementation.
- Business model.
- Product limitations.
- Differentiation.
- Approved positioning.
- Claims the client can substantiate.
- Claims the client does not permit.

## B. Market Intelligence

Research the client's market:

- Market structure.
- Industry-specific operational challenges.
- Customer business models.
- Relevant market trends.
- Common buying triggers.
- Relevant terminology.
- Operational and financial challenges.
- Changes affecting customer demand.

Focus on insights that can materially improve campaign strategy.

Do not collect research merely to create a large database.

## C. Competitor Intelligence

Research the client's main competitors.

Include:

- Competitor products and services.
- Pricing and packaging when available.
- Positioning.
- Target customers.
- Publicly documented capabilities.
- Strengths and limitations supported by evidence.
- Customer reviews.
- Competitor offers.
- Relevant case studies.
- Verified competitive differentiation.

Do not invent competitor weaknesses or make unsupported comparative claims.

## D. Customer Intelligence

Research the client's existing customers and ideal customer profiles.

Include:

- Customer segments.
- Company characteristics.
- Buyer personas.
- Relevant business models.
- Common use cases.
- Documented customer outcomes.
- Customer case studies.
- Buying triggers.
- Common objections.
- Reasons customers select the product.

Distinguish verified customer information from inferred customer characteristics.

## E. Offer Library

Create a structured library of approved campaign offers.

Each offer should include:

- Offer ID.
- Target segment.
- Buyer persona.
- Business problem.
- Value proposition.
- Concrete deliverable.
- Supporting evidence.
- CTA.
- Conditions and limitations.
- Approval status.
- Offer version.
- Campaigns using the offer.

AI may recommend new offers, but it must not invent discounts, guarantees, deliverables, customer results, or commercial terms.

## F. Messaging Intelligence

Maintain:

- Approved messaging examples.
- Successful and unsuccessful campaign examples.
- Client-specific tone of voice.
- Relevant industry terminology.
- Approved positioning.
- Common objections.
- Messaging patterns to avoid.
- Evidence supporting particular claims.

## G. Learning Memory

Maintain a structured history of:

- Campaign performance.
- Offer performance.
- Customer objections.
- Positive and negative replies.
- Changes in messaging.
- Tested hypotheses.
- Strategy decisions.
- Outcomes associated with those decisions.

Do not treat an AI-generated interpretation as a verified fact.

## SECOND BRAIN INDEX

Create an index page that allows an operator to understand the client and navigate the intelligence workspace.

The index should show:

1. Client overview.
2. ICP and customer segments.
3. Market intelligence.
4. Competitor intelligence.
5. Approved offers.
6. Messaging strategy.
7. Available evidence and case studies.
8. Current campaigns.
9. Recent learning.
10. Missing information and research priorities.

Every important fact must retain its source, retrieval date, verification status, and relationship to the client.

Do not pass the entire Second Brain into every AI prompt.

Implement task-specific retrieval so each agent receives only the information relevant to its current task.

---

# 4. BUILD A CAMPAIGN-FIRST OFFER ENGINE

This is one of the most important changes.

Instead of generating a unique pitch for every lead, develop a dedicated campaign strategy for a clearly defined segment.

Every campaign should have two primary offers.

These are TWO OFFERS, NOT TWO OUTREACH STEPS.

The email cadence remains five steps, and the HeyReach cadence remains multi-step.

Each campaign must define:

- Target ICP.
- Target segment.
- Buyer persona.
- Primary business problem.
- Primary offer.
- Secondary offer.
- Supporting evidence.
- Approved messaging angles.
- Campaign objective.
- CTA strategy.
- Disqualification criteria.

Both offers should provide concrete value to the recipient.

They must be based on actual client capabilities and approved commercial terms.

The five-email sequence should use these two offers strategically without repeating the same argument.

For example:

Email 1: Establish relevance and introduce the primary offer.

Email 2: Add a new operational insight related to the primary offer.

Email 3: Introduce the secondary offer through a new thread and distinct value proposition.

Email 4: Provide useful supporting evidence, a practical example, or a new perspective.

Email 5: Close the sequence with a concise, contextually appropriate final message.

This is an illustrative structure, not a requirement to rewrite existing cadence rules blindly.

The campaign strategy agent should determine the specific objective of each step before copy generation.

Each step must provide something new.

The LinkedIn cadence should complement the email strategy while preserving its existing multi-step structure and provider-specific behavior.

---

# 5. IMPROVE SIGNAL INTELLIGENCE

Inspect the existing:

src/signals.py
src/priority.py
src/contextpack.py
src/playbooks.py

And all related signal collection, research, scoring, and campaign integration modules.

Do not rebuild existing signal infrastructure.

The key improvement is evaluating whether a signal is relevant to the specific person receiving the outreach.

A company-level signal is not automatically a person-level buying signal.

Introduce or improve the following dimensions:

1. Signal authenticity.
2. Signal freshness.
3. Account relevance.
4. Person relevance.
5. Relationship between the signal and the client's offer.
6. Confidence in the available evidence.

Example:

A company is hiring five software developers.

This may be relevant to a Head of Delivery responsible for team capacity.

It may be less relevant to a finance contact who has no documented involvement in hiring or resource allocation.

The agent must explain why the signal matters to the recipient.

Do not confuse plausible involvement with verified personal responsibility.

A signal can be used for prioritization without being appropriate to mention directly in outreach.

Preserve existing claim verification and evidence requirements.

## SIGNAL SOURCES

Prioritize a small number of practical sources:

- Relevant LinkedIn posts.
- Company announcements.
- Company news.
- Job postings.
- Publicly available company information.
- Google Reviews, when relevant and reliably accessible.

Do not implement Reddit scraping at this stage.

Do not build a complex universal signal scraping infrastructure before validating the initial sources.

For Google Reviews, first establish whether useful information exists for the target market and whether it can be obtained reliably and lawfully.

Every signal should retain its original source and timestamp.

Add a mechanism for retracting incorrect or outdated signals.

Preserve signal history so we can understand why an account received a particular priority at a particular time.

---

# 6. BUILD A SKILLS AND SOP LIBRARY

I want Resonate OS to have documented best-practice procedures for its major AI-driven activities.

However, do not create hundreds of generic skills merely to increase the number of skills.

Start with a focused library of high-value, reusable SOPs.

Inspect the existing playbook architecture and determine how it can be extended or connected to the new skills system.

Proposed initial skills:

1. Client Research.
2. Market Intelligence.
3. Competitor Research.
4. Customer and ICP Research.
5. Offer Development.
6. Account Research.
7. Signal Verification.
8. Person Relevance Assessment.
9. Campaign Strategy.
10. Cold Email Writing.
11. LinkedIn Outreach Writing.
12. Copy Quality Assurance.
13. Reply Analysis.
14. Campaign Performance Learning.

Each skill must have:

- Purpose.
- Required inputs.
- Required context from the Client Second Brain.
- Approved tools and data sources.
- Execution procedure.
- Examples of successful execution.
- Examples of unacceptable execution.
- Validation criteria.
- Expected output schema.
- Failure handling.
- Human escalation conditions.
- Tests.

A skill must be executable and testable.

Do not create documentation that is disconnected from the actual agent workflow.

The relevant skill must be loaded and applied when the agent performs its associated task.

---

# 7. REBUILD THE COPYWRITING APPROACH AROUND EXAMPLES

The copywriting system should rely less on generic AI writing instructions and more on high-quality examples, approved offers, verified research, and explicit rules about what NOT to do.

Build a dedicated Copywriting Skill.

It should use:

- Approved client messaging.
- Relevant campaign offers.
- Client Second Brain context.
- High-quality cold email examples.
- Strong LinkedIn outreach examples.
- Examples of unsuccessful messaging.
- Client-specific tone of voice.
- Existing copylint and sequencegate rules.

Each example should contain relevant metadata:

- Target persona.
- Industry.
- Campaign objective.
- Offer.
- Message type.
- Actual copy.
- Why the example was selected.
- Available performance evidence.

Do not automatically classify a message as successful simply because it received a reply.

Do not scrape thousands of examples before validating that the initial example library improves output quality.

Start with a curated collection.

Make the example library expandable over time.

## COPYWRITING RULES

Preserve existing operator requirements, including:

- No dashes in generated outreach copy.
- No invented source URLs.
- No unsupported company claims.
- No invented customer outcomes.
- No generic Productive paragraphs.
- No repetitive follow-ups.
- No unsupported problem assertions.
- No unrendered variables.
- Correct sender identity.
- Correct email threading.
- Correct signature handling.
- Correct LinkedIn personalization.
- Correct relationship between email and LinkedIn messaging.

Preserve existing approved P.S. and subject-line behavior unless a specific change is proposed and approved.

The agent must not generate a new sales pitch independently for every lead.

It should adapt the campaign's approved strategy and offers using verified account context.

Personalization must add genuine relevance.

A generic compliment or unrelated company fact is not meaningful personalization.

---

# 8. IMPROVE COPY VALIDATION

Inspect the existing copylint and sequencegate implementations.

Preserve their current protections.

Add validation for:

- Semantic repetition across all five email steps.
- Repetition between email and LinkedIn messages.
- Consistency with the approved campaign offer.
- Unsupported commercial promises.
- Unsupported customer results.
- Signal-to-person relevance.
- Consistency with the Client Second Brain.
- Correct message objective for each cadence step.
- Correct use of primary and secondary offers.
- Correct threading and subject assignment.
- Correct sender identity and signature.
- Appropriate personalization.
- Correct handling of missing research.

The existing lexical overlap checks should remain as fast, deterministic validation.

Add semantic validation where it materially improves detection of repeated arguments.

Do not allow an LLM quality score to override deterministic safety failures.

Quality validation should report the exact message, failed rule, supporting evidence, and recommended correction.

Do not silently regenerate an entire sequence when only one message fails.

---

# 9. IMPROVE THE LEARNING ENGINE

Inspect the existing learning, reply classification, account policy, reporting, and campaign performance modules.

The system should learn which offers, messaging angles, signals, and segments produce meaningful commercial outcomes.

Capture:

- Campaign ID.
- Offer ID and version.
- Segment.
- Buyer persona.
- Signal type.
- Copy version.
- Sender.
- Channel.
- Positive replies.
- Negative replies.
- Objections.
- Qualified meetings.
- Sales opportunities.
- Other available commercial outcomes.

Separate actual prospect statements from AI interpretations.

Do not optimize only for reply rate.

Prioritize qualified meetings and meaningful commercial outcomes.

The system should be able to identify recurring objections and propose changes to campaign strategy.

AI may recommend improvements to offers and messaging.

It must not automatically change approved commercial terms or active campaigns.

---

# 10. CONTEXTUAL RETARGETING

Introduce a controlled retargeting workflow that can evaluate accounts approximately two weeks after their previous outreach sequence has ended.

IMPORTANT:

This does not replace the five-step email cadence.

It does not replace the existing multi-step HeyReach cadence.

The two-week interval is a configurable eligibility review, not permission to send another message automatically.

Before recommending retargeting, verify:

- Previous campaign completion.
- Previous email and LinkedIn activity.
- Positive and negative replies.
- Suppression status.
- Do-not-contact requests.
- Explicit follow-up timing requested by the prospect.
- Existing conversations.
- Other active campaigns.
- New relevant signals.
- Updated account context.
- Whether a genuinely new offer or value proposition exists.

Never retarget a prospect who has requested no further contact.

Never override an explicit future follow-up date.

Do not restart the same sequence with slightly different wording.

The system should explain why retargeting is justified and what has changed since the previous campaign.

Retargeting must go through the existing approval and activation mechanisms.

---

# 11. PRESERVE AND IMPROVE THE EXISTING INFRASTRUCTURE

Review the following areas for correctness, integration gaps, unnecessary duplication, and scalability:

- ICP qualification.
- Research and enrichment.
- Campaign segmentation.
- Account intelligence.
- Signal scoring.
- Copy generation.
- Email and LinkedIn cadence generation.
- EmailBison integration.
- HeyReach integration.
- Cross-channel reply handling.
- Suppression and account policies.
- Campaign approvals.
- Sender assignment.
- Queue and job processing.
- Provider rate limits.
- Spend tracking.
- Audit logging.
- Workspace isolation.
- Reporting.
- Railway deployment.
- Test coverage.

Do not assume that a feature is missing simply because it is not immediately visible in the UI.

Trace the actual implementation.

Identify functionality that already exists but is not connected to the relevant workflow.

Prefer extending existing modules over introducing duplicate systems.

Do not replace stable, tested infrastructure merely to make the architecture look cleaner.

---

# 12. PERFORMANCE AND COST CONTROL

The new architecture should reduce unnecessary AI work.

Client research should be reusable across campaigns.

Campaign strategy and offer development should happen primarily at the campaign level.

Individual lead processing should focus on:

- ICP qualification.
- Account-specific research.
- Signal relevance.
- Person relevance.
- Controlled personalization.
- Quality validation.

Do not repeatedly perform expensive market or competitor research for every lead.

Introduce appropriate caching, freshness policies, and versioning.

Evaluate where inexpensive models are sufficient and where a more capable model materially improves output quality.

Do not assume that every stage requires a separate LLM call.

Measure the actual cost per campaign, per processed lead, and per qualified meeting where data is available.

Preserve existing spend limits and provider ceilings.

---

# 13. REQUIRED AUDIT AND IMPLEMENTATION PROPOSAL

Before writing code, inspect the actual repository and produce the following deliverables.

## A. CURRENT STATE AUDIT

For every major area, report:

- What currently exists.
- Relevant files and functions.
- What is working based on available evidence.
- What is incomplete.
- What is duplicated.
- What is disconnected from the actual workflow.
- What requires live validation.
- What should remain unchanged.

Distinguish confirmed bugs from architectural recommendations.

Do not claim that tests pass unless you have executed them.

## B. GAP ANALYSIS

Compare the current architecture with the proposed architecture.

For every proposed improvement, identify:

- Existing implementation that can be reused.
- Missing functionality.
- Required modifications.
- Dependencies.
- Migration considerations.
- Risks.
- Expected operational benefit.

## C. PROPOSED ARCHITECTURE

Produce a clear architecture showing how these components interact:

Client Second Brain → Campaign Strategy → Offer Engine → Account Research → Signal Intelligence → Copywriting Skills → Five-Step Email Cadence + Multi-Step HeyReach Cadence → Quality Gates → Approval → Sending → Learning Engine.

Explain where each component stores information and how information moves between components.

Identify the canonical source of truth for client facts, offers, campaign strategy, and account-level evidence.

Avoid introducing multiple competing sources of truth.

## D. IMPLEMENTATION ROADMAP

Divide the implementation into practical phases.

Prioritize changes that allow us to launch and validate improved campaigns quickly.

Suggested order:

Phase 1: Client Second Brain, Offer Engine, campaign-first strategy, copywriting skills, and improved five-step copy generation.

Phase 2: Signal relevance, external signal integration, and improved quality validation.

Phase 3: Learning Engine, contextual retargeting, and performance-driven strategy recommendations.

Adjust this order if the actual repository reveals important dependencies.

For every phase, provide:

- Exact files to modify.
- New modules required.
- Existing modules to reuse.
- Data model changes.
- API changes.
- UI changes.
- Migration requirements.
- Tests to add.
- Acceptance criteria.
- Dependencies.
- Risks.

## E. PROOF OF CORRECTNESS

Explain how you will demonstrate that:

1. Email campaigns still contain five steps.
2. Existing email threading remains correct.
3. HeyReach retains its existing multi-step behavior.
4. Email and LinkedIn remain coordinated.
5. Existing campaigns are not silently modified.
6. Client-specific data remains isolated.
7. Approved offers cannot be changed without authorization.
8. Unsupported claims cannot reach the sending layer.
9. Suppression and do-not-contact rules remain authoritative.
10. Retargeting cannot bypass existing safety controls.
11. Historical data and audit records are preserved.
12. New functionality does not break existing provider integrations.

Include regression tests for the existing cadence and provider behavior.

---

# 14. FINAL INSTRUCTIONS

This is a proposal and audit task.

Do not immediately implement the architecture.

Do not modify production data.

Do not activate or send anything.

Do not delete existing features.

Do not shorten the five-step email cadence.

Do not shorten the existing HeyReach cadence.

Do not assume that a module is missing without inspecting the repository.

Do not create unnecessary abstractions or duplicate existing functionality.

Do not build Reddit integration at this stage.

Do not spend time investigating or changing the Productive booking link.

Focus on making Resonate OS more commercially effective through stronger client intelligence, better offers, more relevant signals, higher-quality copy, and systematic learning.

Your final response should contain:

1. Executive summary of the current architecture.
2. Confirmed technical and architectural findings.
3. Proposed changes, ordered by priority.
4. Existing functionality that should be preserved.
5. Detailed Client Second Brain design.
6. Offer Engine design.
7. Skills and SOP architecture.
8. Signal intelligence improvements.
9. Copy engine and quality gate improvements.
10. Learning and retargeting architecture.
11. Exact implementation roadmap with files, dependencies, and tests.
12. Risks, unresolved questions, and decisions requiring operator approval.

Be critical of the proposal itself.

If an idea is unnecessary, already implemented, too expensive, or likely to introduce complexity without meaningful value, explain why and propose a simpler alternative.

Do not agree with every suggestion automatically.

Base your recommendations on the actual codebase, existing architecture, documented requirements, and evidence.

The objective is to improve the existing Resonate OS, not to build another system beside it.

**Start by auditing the repository. Present the findings and implementation proposal before making any changes.**
