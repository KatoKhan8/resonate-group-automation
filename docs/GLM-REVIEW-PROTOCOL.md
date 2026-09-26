GLM CONTINUOUS REVIEW INTEGRATION DIRECTIVE

The first independent GLM canary audit is now complete, pushed, and durable.

This directive has TWO goals:

1. make sure the work from that audit is actually consumed by the main execution stream;
2. make GLM a permanent, high-value independent review layer for the rest of Phase 1.

IMPORTANT:

Do NOT interrupt useful work already running.

Do NOT stop, cancel, restart, reprioritize, or steal workers from currently useful
Claude/Qwen tasks.

This directive is additive to the current execution stream.

==================================================
1. CONSUME THE COMPLETED GLM AUDIT
==================================================

The completed independent review is:

Reviewed master:
b33369748a91435f23524ede40ad74b1c54fb7cf

Review branch:
review/glm-b333697

Review commit / remote SHA:
db9c2b179c415f2610574bd2bca29abf919f1ec8

Review document:
docs/glm-reviews/canary-readiness-b333697.md

Review worktree:
C:\Users\Zvonimir\glm-review\glm-review-b333697

Before considering the review consumed, ensure every GLM finding has exactly one
current disposition:

- FIXED + VERIFIED
- EXISTING TASK
- NEW TASK
- RUNTIME VERIFICATION REQUIRED
- SUPERSEDED
- FALSE POSITIVE
- ACCEPTED DEFERRED RISK
- OPERATOR DECISION REQUIRED

No finding may disappear merely because master moved.

Do not duplicate tasks.

Where Claude already triaged a finding, preserve that work and link the disposition.

Specifically preserve the known results already produced from the review:

- EMAIL_RESUME P0 was independently reproduced and routed through TASK-331.
- spend-ceiling finding was independently reproduced.
- TASK-346 introduced the pre-provider reserve/refusal mechanism.
- client/config attribution into the spend gate remains a separate wiring concern and
  must not be considered solved merely because reserve() exists.
- cadence single-source finding remains subject to its existing task/current state.
- provider-write-audit transport-shape finding remains subject to its existing task/current state.
- Account Identity was only PARTIALLY REVIEWED.
- Approval Identity was code-level reviewed with no defect found, but code-level proof
  must not be mislabeled runtime proof.

Re-check CURRENT origin/master before relying on any historical status.

Machine state wins.

==================================================
2. GLM IS NOW A PERMANENT INDEPENDENT REVIEW LAYER
==================================================

From now through completion of the first production-realistic vertical slice, actively
use GLM where independent reasoning materially improves confidence.

Claude remains:

ORCHESTRATOR / INTEGRATOR / FINAL TRIAGE OWNER

Qwen remains:

PRIMARY IMPLEMENTATION WORKER

GLM becomes:

INDEPENDENT REVIEWER / CRITIC / RED TEAM / HIGH-REASONING SECOND OPINION

GLM should NOT become the default implementer.

GLM should NOT duplicate Qwen work.

GLM should NOT be given work merely because capacity is available.

Use GLM aggressively where independence has high expected value.

==================================================
3. MANDATORY GLM REVIEW TRIGGERS
==================================================

Before the first live canary, GLM should independently review material changes involving:

A. safety-critical provider writes

- send
- activate
- resume
- enrol
- attach
- stop
- suppression
- cross-channel stop propagation
- approval identity
- payload/hash identity

B. canonical pipeline wiring

Especially the final chain:

Second Brain
→ Campaign Strategy
→ Offer A/B
→ Account Research
→ Signal Verification
→ Buying Committee / Person Relevance
→ Skills
→ SequencePlan / canonical plan
→ Email + LinkedIn projections
→ QA
→ approval
→ provider-ready write gate

GLM should try to prove that each supposedly wired component has a REAL consumer and
REAL downstream effect.

Zero-consumer components are defects, not implementation success.

C. canonical-source problems

Use GLM to look specifically for:

- two cadence sources
- two persona mappings
- two research stores
- duplicated offer ownership
- preview-specific business logic
- provider-specific business logic that bypasses canonical planning
- stale compatibility paths that silently remain authoritative

D. grounding and claims

GLM should independently challenge:

- unsupported prospect claims
- invented outcomes
- invented commercial terms
- inferred facts promoted to VERIFIED
- case-study claims without stored evidence
- signal token coincidence masquerading as grounding
- offer language stronger than evidence licenses

E. account identity

Before canary, GLM must finish the previously partial review sufficiently to prove:

one account
→ correct company identity
→ shared account research
→ correct 2–3 decision makers
→ correct person/company joins
→ no research leakage across accounts
→ no wrong-company signal/copy inheritance

F. spend/cost enforcement

After TASK-373 or equivalent client-context wiring lands, GLM should independently try
to falsify the claim that:

client
→ config
→ ceiling
→ reserve
→ provider call
→ settlement

is actually enforced through the production entrypoint.

The critical negative control is:

exceeded client/provider ceiling
→ provider call count remains zero.

G. canonical production entrypoint

TASK-369 or its final equivalent is especially important.

Once integrated, give GLM an independent review asking:

Does ONE version-controlled production generation entrypoint actually consume the
canonical layers we claim it consumes?

Do not accept imports or available functions as wiring.

Require observable downstream effect.

==================================================
4. GLM REVIEW AFTER IMPORTANT MERGES
==================================================

Do NOT send every tiny commit to GLM.

Use review batches.

When a coherent critical-path group lands, create a GLM review checkpoint.

Good checkpoints include:

CHECKPOINT A
production generation entrypoint + canonical research store

CHECKPOINT B
Offer A/B + capability_by_persona list migration + campaign strategy

CHECKPOINT C
Five Skills runtime integration + grounding/QA

CHECKPOINT D
SequencePlan/cadence + Email/LinkedIn projections

CHECKPOINT E
provider safety + approval + suppression + spend

CHECKPOINT F
complete production-realistic vertical slice

This keeps GLM useful without turning it into a second implementation team.

==================================================
5. GLM REVIEW CONTRACT
==================================================

Every new independent GLM review must:

- start from CURRENT origin/master
- use its own isolated clean worktree
- stamp exact START_MASTER_SHA
- never use the dirty primary checkout as its workspace
- remain read-only except for its own review document/branch
- cite exact file:line evidence
- include reproducible read-only commands
- distinguish static/code proof from runtime proof
- mark unsupported claims UNVERIFIED
- mark incomplete areas PARTIALLY REVIEWED
- re-fetch origin/master at completion
- detect master movement
- mark potentially superseded findings
- never merge
- never modify production/provider state
- never automatically create implementation
- hand findings back to Claude for independent reproduction and triage

Claude owns the decision about whether a GLM finding becomes implementation work.

==================================================
6. USE GLM FOR FALSIFICATION, NOT CONFIRMATION
==================================================

Do not prompt GLM:

"verify that this works."

Prefer:

"try to prove this claim false."

Examples:

Try to produce a path where a suppressed recipient reaches a provider write.

Try to produce a path where a stale approval authorizes a changed artifact.

Try to produce a model call that bypasses the client spend ceiling.

Try to produce two different LinkedIn schedules for the same canonical campaign.

Try to make one account consume another account's research.

Try to generate copy using a claim not licensed by the Second Brain/evidence store.

Try to show that a skill exists but has no runtime consumer.

Try to show that preview output differs semantically from provider-ready output.

Try to show that an account-level interaction fails to influence another decision maker
when policy says it should.

Negative controls and mutation tests are preferred over happy-path assertions.

==================================================
7. GLM SHOULD REVIEW OUTPUT QUALITY TOO
==================================================

GLM is not only a safety reviewer.

Once the canonical vertical slice produces real artifacts, use GLM as an independent
semantic critic for a representative sample.

Review:

- account research quality
- signal relevance
- buying-committee selection
- persona relevance
- Offer A/B use
- email sequence progression
- LinkedIn complementarity
- semantic repetition
- unsupported claims
- false personalization
- weak hypotheses
- evidence use
- CTA consistency
- account-level coordination

But:

deterministic CODE gates remain authoritative for deterministic safety constraints.

GLM does not get to override:

suppression
approval
budget ceilings
provider state requirements
identity constraints
schema constraints
canonical cadence
operator authorization

==================================================
8. MODEL ROUTING PRINCIPLE
==================================================

Continue maximizing useful GLM capacity, but optimize for VALUE rather than token usage.

Use:

Qwen/local:
implementation, bulk deterministic transformation, mechanical coding

Groq:
cheap/simple classification where appropriate

GLM Flash:
research extraction, synthesis, relevance, semantic QA, grounding, classification

GLM high/max:
strategy, ambiguity resolution, architecture criticism, independent audit, difficult
semantic QA, falsification

Sonnet:
premium prospect-facing generation where the benchmark justifies it

CODE:
final authority for deterministic safety and provider rules

Do not use expensive GLM reasoning for trivial extraction.

Do use it where a wrong answer can create:

- unsafe outreach
- false claims
- broken architecture
- duplicated canonical state
- account identity leakage
- incorrect provider behavior
- expensive rework

==================================================
9. DO NOT BLOCK THROUGHPUT
==================================================

GLM review must not unnecessarily serialize the whole project.

Safe independent development continues while GLM reviews a completed checkpoint.

A GLM finding blocks only:

- the affected unsafe integration
- its dependent live canary
- or production activation where materially relevant.

It does NOT automatically stop unrelated useful work.

If GLM discovers P0:

independently reproduce it first.

Then:

existing task → use/update it

no existing task → smallest dedicated task

Do not duplicate tasks.

Do not pull useful workers off unrelated in-progress work unless continuing that exact
work would produce invalid artifacts.

==================================================
10. NEXT GLM USE
==================================================

Do not start a new GLM audit merely because this directive exists.

First inspect CURRENT execution state.

Identify the next coherent critical-path checkpoint that has actually landed and is
stable enough to review.

Given the current known state, likely high-value upcoming review targets are:

1. TASK-369 production generation entrypoint after integration;
2. TASK-373 client-aware spend wiring after integration;
3. Offer A/B + capability_by_persona list migration after both land;
4. Five Skills runtime wiring;
5. final account-level Email + LinkedIn vertical slice.

Choose based on MACHINE STATE, not this historical ordering.

==================================================
11. DURABLE STATE
==================================================

Make sure the main execution/handoff state records:

- the completed GLM review artifact
- its SHA
- its disposition status
- GLM's permanent reviewer role
- the rule that future GLM reviews start from current master
- the requirement that Claude independently reproduces material findings
- the next GLM checkpoint when one becomes concrete

Do not copy the entire 485-line audit into operating docs.

Reference the artifact.

One source of truth.

==================================================
12. CONTINUE EXECUTION
==================================================

After recording this review protocol:

continue current work.

Do not stop currently running workers.

Do not wait for GLM unnecessarily.

Do not ask operator for confirmation unless an actual operator-only decision is required.

At the next appropriate critical-path checkpoint, actively invoke GLM again rather than
letting the independent-review capability go unused.

The objective is not maximum GLM usage.

The objective is maximum useful independent intelligence per critical decision.
