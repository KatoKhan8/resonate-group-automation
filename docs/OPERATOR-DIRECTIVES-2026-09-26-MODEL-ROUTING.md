BTW: do not interrupt, cancel, restart, or reprioritize anything currently running.

Continue all current Phase 1 / Second Brain / Offer Engine / account-level architecture / skills / QA / Qwen / GLM development work from its current state.

This is an additional architecture and model-routing directive to REVIEW and INCORPORATE into the work already underway.

## CONTEXT

We have significantly more GLM capacity available than we are currently using.

Current Z.AI usage dashboard is approximately:

- 5-hour limit: ~1% used
- 26 / 28K credits shown
- weekly limit: ~1% used
- 88 / 140K credits shown
- cumulative tokens: ~612K
- peak usage so far: ~216K tokens
- total usage duration: ~2h 8m

Therefore:

DO NOT optimize Resonate OS around minimizing GLM usage merely for the sake of minimizing usage.

We have substantial unused capacity.

The objective should be:

MAXIMIZE QUALITY PER OUTBOUND DECISION

while still avoiding architecturally wasteful repeated work.

Use GLM aggressively where additional reasoning, critique, synthesis or validation can materially improve the system.

Do not generate meaningless tokens merely to consume allowance.

Use available capacity to improve intelligence and reliability.

---

# 1. REVIEW CURRENT MODEL ROUTING

Audit every AI/LLM stage currently implemented or planned in Resonate OS.

For every stage report:

TASK
CURRENT MODEL
CURRENT PURPOSE
CALL FREQUENCY
ACCOUNT / CONTACT / CAMPAIGN LEVEL
INPUT CONTEXT
OUTPUT
PRODUCTION CONSUMER
CURRENT QUALITY RISK
GLM CANDIDATE?
RECOMMENDED GLM MODEL/MODE
REASON

Include at minimum:

- client research
- Second Brain extraction
- market intelligence
- competitor intelligence
- customer/case-study intelligence
- ICP classification
- company qualification
- account research
- fact extraction
- signal verification
- signal relevance
- person relevance
- buying committee selection
- account hypothesis
- capability/value matching
- campaign strategy
- Offer Engine
- sequence strategy
- email copy
- LinkedIn copy
- cross-channel strategy
- sequence QA
- semantic repetition detection
- grounding validation
- provenance validation
- reply classification
- objection extraction
- referral detection
- learning extraction
- campaign performance analysis
- next-best-action reasoning
- account-level orchestration
- development/code review where relevant.

Do not change production routing blindly.

First understand what exists.

---

# 2. TARGET MODEL PHILOSOPHY

Move toward a model architecture approximately like this, subject to benchmark results:

## QWEN / LOCAL

Use for:

- implementation grunt work
- code generation tasks
- deterministic-support tasks
- cheap transformations
- bulk processing where reasoning quality is not the bottleneck

## GROQ

Use for:

- ultra-fast classification
- simple extraction
- simple ICP checks
- inexpensive high-volume structured tasks
- tasks where latency matters and reasoning depth does not

## GLM FLASH / CHEAP GLM TIER

Evaluate as the PRIMARY INTELLIGENCE WORKHORSE for:

- Second Brain extraction
- company research synthesis
- market intelligence synthesis
- competitor extraction
- customer/case-study extraction
- fact normalization
- signal verification
- signal relevance
- person relevance
- buying committee analysis
- account summaries
- semantic QA
- grounding checks
- reply classification
- objection extraction
- learning extraction

## FULL GLM / HIGH REASONING

Evaluate for:

- Offer Engine reasoning
- campaign strategy
- account strategy
- complex ICP decisions
- multi-signal synthesis
- buying committee strategy
- cross-channel strategy
- next-best-action reasoning
- account-level orchestration
- difficult QA cases
- independent critic/reviewer
- architecture/code review where useful

Use the highest available reasoning mode for genuinely difficult decisions where quality benefits.

Do NOT use maximum reasoning indiscriminately for trivial extraction.

## CLAUDE SONNET

Keep as premium prospect-facing writer where benchmark evidence supports it.

Current default assumption may remain:

Sonnet = final email copy

But this must become an evidence-based routing decision rather than permanent architectural dogma.

Benchmark GLM against Sonnet for:

- cold email
- follow-ups
- LinkedIn connection copy
- LinkedIn follow-ups
- breakup/close
- persona differentiation
- cross-channel complementarity.

If GLM matches or beats Sonnet for a specific task, allow the router to use GLM there.

## PYTHON / DETERMINISTIC CODE

Remains FINAL AUTHORITY for:

- suppression
- sending eligibility
- campaign activation
- budgets
- spend ceilings
- schemas
- identity safety
- provenance requirements
- provider state
- cadence constraints
- hard validation
- operator approval
- production writes.

LLMs reason.

Code governs.

---

# 3. SECOND BRAIN + GLM

Design GLM usage around the Client Second Brain.

GLM should NOT repeatedly rediscover the client for every account.

Target hierarchy:

CLIENT SECOND BRAIN
↓
CAMPAIGN / SEGMENT / PERSONA STRATEGY
↓
ACCOUNT INTELLIGENCE
↓
BUYING COMMITTEE
↓
PERSON RELEVANCE
↓
MESSAGE CONTEXT

Use the highest reusable knowledge level possible.

Example:

Productive capabilities should not be inferred 5,000 times.

Productive positioning should not be inferred 5,000 times.

Campaign Offer A/B should not be recreated for every lead.

Company research should not be repeated independently for CEO, COO and Head of Delivery.

Instead:

CLIENT intelligence = reusable

CAMPAIGN strategy = reusable

ACCOUNT research = reusable across decision makers

PERSON context = incremental

MESSAGE generation = final lightweight layer.

This is both a QUALITY and COST architecture requirement.

---

# 4. USE GLM TO IMPROVE SECOND BRAIN QUALITY

Where useful, GLM should review and synthesize:

CLIENT PROFILE

MARKET INTELLIGENCE

COMPETITOR INTELLIGENCE

CUSTOMER INTELLIGENCE

OFFER LIBRARY

MESSAGING INTELLIGENCE

LEARNING MEMORY

MISSING INFORMATION

RESEARCH PRIORITIES

But preserve canonical-source rules.

GLM must not create a parallel truth store.

Every factual output must preserve or reference provenance.

Knowledge status remains conceptually:

VERIFIED
CLIENT_APPROVED
INFERRED
UNKNOWN

GLM may reason from INFERRED information.

It must not silently convert inference into verified fact.

UNKNOWN remains UNKNOWN.

Never fabricate provenance.

---

# 5. GLM AS INDEPENDENT CRITIC

Increase GLM usage as an independent reviewer.

This is important because previous GLM review already identified defects that primary implementation/review had missed.

Use GLM strategically to challenge:

- unsupported claims
- fabricated provenance
- fake specificity
- repeated arguments
- weak personalization
- wrong-company research
- persona mismatch
- offer mismatch
- strategy inconsistency
- Email/LinkedIn duplication
- unsupported commercial promises
- bad inference from thin evidence
- account identity mismatch
- missing production consumers
- dead code / zero-caller intelligence components.

However:

GLM criticism does not override deterministic gates.

A deterministic FAIL remains FAIL.

---

# 6. MULTI-PASS QUALITY FOR IMPORTANT OUTPUTS

Because GLM capacity is currently abundant, use additional reasoning passes where they materially improve quality.

For important campaign/account decisions consider:

PASS 1
Generate structured recommendation.

PASS 2
Independent GLM critic challenges recommendation.

PASS 3
Reconcile only if disagreement materially affects strategy.

Do NOT use three passes for every trivial extraction.

Use multi-pass reasoning for:

- campaign strategy
- Offer Engine
- ambiguous ICP decisions
- high-value accounts
- account orchestration
- risky claims
- difficult QA
- strategy changes based on learning.

---

# 7. STRUCTURED OUTPUT BY DEFAULT

For internal pipeline stages, prefer structured machine-readable GLM output rather than prose.

Example:

account_id
qualification
confidence
evidence_ids
primary_persona
secondary_personas
account_hypothesis
offer_id
angle_id
signal_ids
person_relevance
unknowns
risks
recommended_action

Validate schemas in deterministic code.

Free-form prose should primarily be used where prose itself is the product:

- Email
- LinkedIn
- operator explanation where appropriate.

---

# 8. TOOL-BASED GLM REASONING

Prepare architecture for GLM to reason using read-only Resonate OS tools.

Potential tools:

get_client_brain()

get_campaign_strategy()

get_offers()

get_account()

get_account_research()

get_contacts()

get_buying_committee()

get_signals()

get_email_state()

get_linkedin_state()

get_replies()

get_referrals()

get_suppression_state()

get_performance()

get_learning_memory()

This becomes particularly valuable for future account-level orchestration.

Conceptually:

READ ACCOUNT
→ reason
→ READ CONTACTS
→ reason
→ READ EMAILBISON STATE
→ reason
→ READ HEYREACH STATE
→ reason
→ READ REPLIES
→ reason
→ NEXT BEST ACTION

Do not give an autonomous reasoning model unrestricted prospect-facing write authority.

Any future:

send
activate
enroll
suppress
modify campaign

action must still pass deterministic policy and operator-approval rules.

---

# 9. ACCOUNT-LEVEL ORCHESTRATION

GLM is a strong candidate for the future reasoning layer that decides:

- best first decision maker
- primary vs secondary contact
- Email vs LinkedIn starting channel
- when to introduce second decision maker
- when to introduce third decision maker
- when engagement from one contact changes strategy for others
- when to pause
- when to escalate
- when to stop the account.

Do not build the full autonomous orchestrator now if it derails Phase 1.

But ensure current Second Brain/account data architecture supports it.

Account remains the strategic unit.

Contact remains the personalization/delivery unit.

---

# 10. LINKEDIN REMAINS HEAVY

Do not accidentally turn this architecture into an email-first system.

Our existing LinkedIn cadence tree is strategically important and was directionally strong.

The copy needs improvement.

The cadence itself should not be replaced without explicit review.

Use GLM to improve:

- LinkedIn-specific writing
- channel differentiation
- relationship-oriented messaging
- account context
- role relevance
- non-repetitive follow-ups
- cross-channel awareness.

Email + LinkedIn should operate as one coordinated account motion.

GLM should help determine whether a LinkedIn message adds NEW VALUE compared with what the contact has already received by email.

---

# 11. SONNET VS GLM COPY TOURNAMENT

Create a benchmark plan, but do NOT disrupt current Phase 1 work to run it immediately if other P0 work is active.

Use the same accounts/context.

Generate blind variants:

A = current Sonnet writer

B = strongest appropriate GLM model with high/max reasoning where appropriate

C = cheaper GLM/Flash variant where appropriate

Compare blindly.

Do not expose model identity to the evaluator.

Evaluate:

- specificity
- factual grounding
- naturalness
- clarity
- Productive explanation
- persona relevance
- account relevance
- offer clarity
- CTA quality
- follow-up novelty
- semantic repetition
- fake specificity
- hallucination
- Email/LinkedIn complementarity.

Evaluate Email and LinkedIn separately.

Store results.

Do not permanently choose a model from intuition.

Choose from evidence.

---

# 12. CREATE A MODEL BENCH

Design a reusable internal benchmark harness.

Golden dataset should eventually contain approximately 50–100 representative accounts across:

- strong research
- thin research
- multiple personas
- weak signals
- strong signals
- edge-case ICPs
- wrong-company identity cases
- multiple geographies
- multiple offers.

For each relevant task compare available models.

Track:

QUALITY
GROUNDING
HALLUCINATION
CONSISTENCY
LATENCY
INPUT TOKENS
OUTPUT TOKENS
CACHE HIT
COST
HUMAN PREFERENCE

Maintain a versioned:

MODEL_POLICY

Example:

model_policy_v1
model_policy_v2
...

Changing the best model should not require changing Resonate OS architecture.

The router changes.

The workflow remains stable.

---

# 13. MAXIMUM QUALITY DOES NOT MEAN MAXIMUM TOKENS

Important distinction:

We want to use our available GLM capacity aggressively.

We do NOT want waste.

Do not send a 100K-token Second Brain to a model when task-specific retrieval requires 8K.

Do not use max reasoning for extracting a company name.

Do not perform full company research three times because three contacts exist.

Do not rerun unchanged intelligence.

Instead spend GLM capacity on:

BETTER REASONING

BETTER CRITIQUE

BETTER RESEARCH SYNTHESIS

BETTER QA

BETTER ACCOUNT DECISIONS

BETTER OFFER SELECTION

BETTER CROSS-CHANNEL STRATEGY

BETTER LEARNING.

---

# 14. CACHE AGGRESSIVELY

Review GLM/Z.AI caching capabilities and ensure our request architecture maximizes cache reuse where supported.

Stable context should be separated from variable context where practical.

Examples of stable/reusable context:

- Resonate system rules
- client Second Brain
- approved claims
- capabilities
- campaign strategy
- offers
- skill instructions
- QA rubrics.

Variable context:

- account research
- person
- signals
- provider state
- recent interactions.

Instrument:

cacheable tokens
cached tokens
cache hit rate
effective input cost.

Do not claim caching works until actual API responses/metrics confirm it.

---

# 15. MODEL ROUTER

Do not scatter hard-coded model names throughout the codebase.

Design or improve a centralized MODEL ROUTER.

Conceptually:

TASK
↓
QUALITY REQUIREMENT
↓
COMPLEXITY
↓
CONTEXT SIZE
↓
LATENCY REQUIREMENT
↓
MODEL POLICY
↓
MODEL
↓
REASONING LEVEL
↓
FALLBACK
↓
OBSERVABILITY

Example policy:

simple extraction
→ Groq / GLM Flash

research synthesis
→ GLM Flash

complex account strategy
→ GLM high

critical strategy ambiguity
→ GLM max

final email
→ benchmark-selected premium writer

semantic QA
→ GLM Flash

difficult QA
→ GLM high

deterministic safety
→ CODE

This should be configurable/versioned.

---

# 16. ESCALATION INSTEAD OF ONE MODEL FOR EVERYTHING

Use cheap-first / escalate-on-uncertainty where appropriate.

Example:

GLM Flash:
confidence 0.94
clear evidence
→ accept.

GLM Flash:
confidence 0.51
conflicting evidence
→ escalate to GLM high/max.

GLM high:
still ambiguous
→ operator question.

Similarly:

deterministic QA passes
+ cheap semantic QA passes
→ DONE.

Semantic QA uncertain
→ deep GLM critic.

Deep critic identifies material risk
→ HOLD.

This lets us exploit GLM heavily without blindly using the most expensive/deepest reasoning for every operation.

---

# 17. OBSERVABILITY

Every model call should eventually record:

task_type
client
campaign
account
contact if applicable
model
model_policy_version
reasoning_level
input_tokens
cached_input_tokens if available
output_tokens
latency
cost if measurable
result status
retry count
fallback used
quality/gate result.

This is necessary for later cost optimization.

Do NOT pause current development to do the full cost analysis now.

But do not build new AI paths that are invisible to observability.

We will perform detailed cost attribution later.

---

# 18. DEVELOPMENT USE OF GLM

We also have enough GLM capacity to use it more aggressively during development.

Where useful, use GLM as an independent engineering reviewer for:

- architecture reviews
- test quality
- falsifiability
- integration wiring
- zero-caller detection
- provenance correctness
- concurrency/state bugs
- provider adapter assumptions
- security/safety boundaries
- migration risks.

Important lesson from previous work:

A test proving that code executes is not enough.

Ask the critic:

"How could this test pass while the implementation is still wrong?"

Use negative controls and mutation-style reasoning where appropriate.

---

# 19. PRODUCTION SAFETY REMAINS UNCHANGED

This directive expands MODEL USAGE.

It does NOT expand production authority.

Existing production freeze remains fully in force.

No new:

campaign launches
campaign activations
lead enrollments
provider attachments
prospect-facing sends

without my explicit APPROVED.

Do not alter currently active campaigns merely to test GLM.

Development, simulations, previews, benchmarks and dry runs may continue.

---

# 20. DO NOT DERAIL CURRENT WORK

Do not stop the task currently running to implement all of this.

At the next safe point:

1. review this directive against current Phase 1 architecture,
2. identify what is already supported,
3. identify the smallest foundational changes needed now,
4. identify what should wait,
5. update the architecture/model-routing plan,
6. persist the decision in the repo,
7. commit,
8. push,
9. verify remote SHA.

Return:

ALREADY SUPPORTED

GLM OPPORTUNITIES NOW

FOUNDATION CHANGES NEEDED NOW

DEFER UNTIL AFTER PHASE 1

CURRENT MODEL ROUTING PROBLEMS

PROPOSED MODEL POLICY

BENCHMARK PLAN

RISKS

REMOTE SHA

Do not create another disconnected architecture document that nobody consumes.

Any model-routing design must identify the production caller/consumer.

Continue current Second Brain / Phase 1 development after incorporating the relevant requirements.

The goal is not "use GLM more."

The goal is:

USE GLM CAPACITY AGGRESSIVELY WHERE IT MAKES RESONATE OS SMARTER, MORE GROUNDED, MORE RELIABLE AND BETTER.
