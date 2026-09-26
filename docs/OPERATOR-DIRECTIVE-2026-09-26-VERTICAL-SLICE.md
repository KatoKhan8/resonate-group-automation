# RESONATE OS — CONSOLIDATE, VERIFY, FINISH THE VERTICAL SLICE

This is an operator execution directive.

Do not treat the observations below as automatically true.

FIRST verify every material claim against:

- current `origin/master`,
- current production state,
- actual provider state where relevant,
- current task branches,
- current tests,
- current canonical configuration,
- existing architecture/docs.

The recent process log suggests we are now at risk of expanding architecture faster than we are integrating it.

The objective from this point is:

> STOP EXPANDING THE ARCHITECTURE AND FINISH THE FIRST PRODUCTION-REALISTIC VERTICAL SLICE.

This does NOT mean stopping current useful work.

It means new work must now be judged primarily by whether it moves the critical production path toward a complete, safe, high-quality account-level Email + LinkedIn campaign.

Production freeze remains unchanged.

No new prospect-facing launch, enrolment, attachment, send, campaign activation, resume, or provider-changing live test without explicit operator APPROVED.

Existing active production must not be modified merely because of this directive.

---

# 0. READ CURRENT STATE FIRST

Before implementing anything:

Read the current authoritative docs, including where still applicable:

- `CLAUDE.md`
- production handoff
- current operator directives
- Phase 1 plan
- architecture upgrade spec
- production freeze
- account-first decision
- Buggie findings
- current task registry
- relevant task artifacts.

Then:

```bash
git fetch origin
git status
git rev-parse HEAD
git rev-parse origin/master
```

Inspect active worker branches and unmerged artifacts.

Do not assume the handoff is correct.

We have already observed stale state such as:

- DONE tasks remaining in TODO,
- handoff saying NOT STARTED when branch artifacts existed,
- docs saying artifacts were merged when they were branch-only,
- registry readiness disagreeing with dispatcher readiness,
- docs describing production differently from provider truth.

Machine state wins over stale prose.

---

# 1. CHANGE THE PRIMARY DEVELOPMENT KPI

Previous standing guidance emphasized:

- 100% Qwen utilization,
- all workers running,
- 2–3 tasks queued per worker.

That is no longer the primary objective.

SUPERSEDE that requirement with:

> MAXIMIZE CRITICAL-PATH THROUGHPUT, NOT WORKER UTILIZATION.

An idle worker is NOT automatically a defect.

Do not invent, split, or prematurely execute work merely to keep workers busy.

Parallelize only work that is:

1. genuinely independent,
2. useful,
3. non-conflicting,
4. capable of being verified and integrated without blocking the critical path.

If the critical path is:

Offer Engine
→ Campaign Strategy
→ Production Wiring

then finishing and verifying that chain is more important than keeping 12 workers occupied with peripheral work.

Claude remains orchestrator.

Qwen remains the preferred implementation worker where appropriate.

But worker utilization is subordinate to integration throughput.

---

# 2. DEFINE THE CURRENT CRITICAL PATH

Verify this against the repository and adjust if evidence proves otherwise.

Expected Phase 1 critical path:

CLIENT CANONICAL KNOWLEDGE
↓
SECOND BRAIN
↓
CAMPAIGN STRATEGY
↓
APPROVED OFFER A / OFFER B
↓
ACCOUNT
↓
ACCOUNT RESEARCH
↓
BUYING COMMITTEE
↓
CONTACT / ROLE RELEVANCE
↓
COPY SKILLS
↓
EMAIL SEQUENCE
+
LINKEDIN SEQUENCE
↓
CROSS-CHANNEL COORDINATION
↓
GROUNDING / COPY / SEQUENCE QA
↓
CANONICAL SEQUENCE PLAN
↓
PREVIEW
↓
APPROVAL HASH
↓
SUPPRESSION / SAFETY
↓
PROVIDER PAYLOAD
↓
PROVIDER WRITE GATE

The goal is not to create every possible future capability.

The goal is to prove this path end-to-end.

---

# 3. PRODUCE A VERIFIED CRITICAL-PATH MAP

Before adding new modules, produce a table:

COMPONENT
CURRENT IMPLEMENTATION
BRANCH
MERGED TO MASTER?
PRODUCER
CANONICAL STORE
DIRECT CONSUMER
PRODUCTION ENTRYPOINT
DOWNSTREAM EFFECT
TESTED?
REAL END-TO-END TEST?
BLOCKER
ACTION

Include at minimum:

- Client config
- Second Brain
- Offer Engine
- Five skills
- Campaign strategy
- Account intelligence
- Account research
- Buying committee
- Contact relevance
- Context compiler
- Copy engine
- Email writer
- LinkedIn writer
- Email cadence
- LinkedIn cadence
- Sequence gate
- Copylint
- Semantic QA
- Preview
- Approval system
- Suppression
- Cross-channel stop
- Spend ledger
- EmailBison adapter
- HeyReach adapter.

Do not call something WIRED merely because:

A imports B.

For production wiring, prove:

PRODUCTION ENTRYPOINT
→ A
→ B
→ downstream consumer
→ observable output.

If the path terminates in a function with zero production callers, classify it:

DISCONNECTED.

---

# 4. CONSUMER-BEFORE-PRODUCER — STRONGER DEFINITION

The existing consumer-before-producer rule remains.

Strengthen its Definition of Done.

A component is not production-wired because:

- a module exists,
- a function exists,
- a unit test passes,
- A calls B,
- a document says it is integrated.

It is wired only when a test can demonstrate:

> Changing valid upstream information changes the intended downstream production context/output through the real production entrypoint.

Example for Second Brain:

Changing an approved Second Brain capability or evidence item should affect the actual context supplied to campaign/copy generation where that fact is relevant.

The test should enter through the real production path.

Do not create artificial tests that directly invoke internal functions and then claim production integration.

---

# 5. STOP DUPLICATING BUSINESS LOGIC

Audit for duplicated business rules.

Particularly:

- Email cadence
- LinkedIn cadence
- Offer selection
- persona mapping
- account state
- suppression
- approval state
- campaign strategy
- model routing
- preview rendering.

A critical observed example must be verified:

The preview reportedly contained its own hard-coded LinkedIn waits while the canonical HeyReach cadence graph had a different tree.

If confirmed, remove this architecture pattern.

Target rule:

> PREVIEW IS A PROJECTION, NOT A SECOND IMPLEMENTATION.

The same applies to:

- XLSX exports,
- HTML preview,
- provider adapters,
- approval artifacts.

Where practical, introduce or reuse a canonical structured representation such as:

`SequencePlan`

or the existing equivalent if one already exists.

Do NOT create another parallel representation if the repo already has one.

The canonical plan should contain or reference:

ACCOUNT
CAMPAIGN
OFFER
CONTACT
CHANNEL
STEP
WAIT / TIMING
THREAD RELATION
MESSAGE
OBJECTIVE
EVIDENCE
QA RESULT
SUPPRESSION STATE
VERSION

Then:

EmailBison adapter reads it.

HeyReach
