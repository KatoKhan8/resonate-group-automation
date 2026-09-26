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

HeyReach adapter reads it.

Preview renders it.

XLSX exports it.

Approval hashes it.

QA validates it.

One truth.

---

# 6. RECONCILE EMAIL THREADING BEFORE CHANGING IT

There has been conflicting evidence about the intended five-email threading model.

Historical architecture described:

A new
A reply
B new
B reply
C new

Some runtime evidence previously suggested a one-thread invariant.

The recent fifty reportedly rendered:

A new
A reply
B new
B reply
C new.

Do not assume either interpretation.

Inspect:

- current production code,
- provider constraints,
- tests,
- current campaign state,
- architecture spec.

Document the actual canonical rule.

Do not modify live cadence based on an old prompt.

Once canonicalized, preview and provider payload must derive from the same rule.

---

# 7. LINKEDIN — PRESERVE THE REAL TREE

LinkedIn remains strategically important.

Do NOT simplify the existing LinkedIn cadence merely because the new architecture is being integrated.

Verify the actual current HeyReach tree.

The recent process suggests the canonical implementation is richer than the preview represented.

If confirmed:

preserve the working cadence/tree.

Improve:

- copy,
- role relevance,
- account context,
- Email complementarity,
- cross-channel awareness.

LinkedIn should not paraphrase Email.

Email can carry structured commercial/value arguments.

LinkedIn can carry:

- lighter observations,
- contextual touches,
- relationship building,
- questions,
- role/account relevance.

But all messages must remain evidence-backed.

---

# 8. ACCOUNT-FIRST — STOP REDESIGNING WHAT ALREADY EXISTS

Verify the current account model.

Recent inspection suggested existing code already supports much of:

- account contacts,
- graph,
- referrals,
- team/buying committee concepts,
- decision-maker priority,
- reply effects,
- account policy.

If true:

DO NOT create another account orchestration data model.

Reuse it.

Phase 1 requires:

ACCOUNT
→ research once
→ buying committee
→ 2–3 decision makers
→ lighter person relevance
→ coordinated Email + LinkedIn.

Do not perform full company research independently for each contact.

Future autonomous account-level orchestration remains deferred unless required to avoid a data-model dead end.

---

# 9. SECOND BRAIN / CONFIG / ONBOARDING OWNERSHIP

Prevent three competing sources of truth.

Target conceptual ownership:

## CLIENT CONFIG

Operator/client-approved operational truth.

Examples:

- approved capabilities
- commercial constraints
- approved offers
- campaign rules
- sender policy
- client-specific settings.

## SECOND BRAIN / EVIDENCE

Research-derived knowledge with:

- value
- provenance
- source
- date
- freshness
- verification state
- scope.

Knowledge status:

VERIFIED
CLIENT_APPROVED
INFERRED
UNKNOWN

## ONBOARDING

Workflow that:

- researches,
- detects gaps,
- asks questions,
- requests approval,
- populates/references the canonical stores.

ONBOARDING IS NOT A THIRD KNOWLEDGE STORE.

Second Brain must not replace canonical config.

Config must not become an unsourced research database.

Verify the current implementation respects this.

Fix foundational conflicts now.

Defer large onboarding UI/workflow work.

---

# 10. OFFER ENGINE OWNERSHIP

Prevent duplication among:

capabilities
playbooks
offers
campaign strategy
hypotheses
value matching
contact angles
copy.

Use clear ownership:

CAPABILITY
= what the client/product can actually do.

OFFER
= approved prospect-facing motion/mechanism.

CAMPAIGN STRATEGY
= which problem/persona/offer/angle/objective applies to the segment.

ACCOUNT RELEVANCE
= why the strategy is relevant to this company.

CONTACT ANGLE
= how that account relevance maps to this role/person.

COPY
= how we express the already-decided strategy.

A downstream layer must not silently recreate upstream strategy.

The copywriter must not invent a new offer.

Account research must not invent client capabilities.

Person relevance must not invent account facts.

---

# 11. FINISH OFFER ENGINE + FIVE SKILLS + CAMPAIGN STRATEGY FIRST

Verify the current branch state.

Recent evidence suggested:

- Offer Engine exists on an unmerged branch,
- five skills exist on an unmerged branch,
- campaign-first strategy is not yet implemented/wired,
- production wiring is downstream of those.

If still true, this is the highest-value implementation chain.

Priority:

1. verify Offer Engine artifact,
2. verify tests,
3. integrate safely,
4. verify five skills,
5. integrate safely,
6. implement campaign-first strategy,
7. wire all three through the actual generation entrypoint,
8. prove the end-to-end consumer path.

Do not start a parallel replacement.

---

# 12. RESEARCH STOP CONDITIONS

More research is not automatically better.

Implement or document staged research sufficiency.

Conceptually:

EXISTING / FREE DATA
↓
WEBSITE
↓
QUALIFICATION
↓
ENOUGH EVIDENCE?

YES → STOP

NO
↓
COMPANY LINKEDIN / JOBS / APPROVED SOURCES
↓
ENOUGH?

YES → STOP

NO
↓
ADDITIONAL RESEARCH

Person-level research should be incremental.

Company-level research should be reused across decision makers.

Define evidence sufficiency based on the actual downstream decision.

Do not crawl merely because a source is available.

---

# 13. COPY — FIX PIPELINE YIELD BEFORE MODEL TOURNAMENTS

The fifty reportedly produced:

50 cohort leads

19 held

31 written

16 copylint-clean

21 sequencegate-passed

13 passing both.

Verify these numbers from the artifact.

If correct, the immediate issue is not simply writer quality.

Investigate failure distribution.

Particularly:

- unrendered variables,
- unsupported specificity,
- semantic repetition,
- missing evidence,
- incorrect role mapping,
- missing signature,
- sequence inconsistency.

Target:

maximize:

`usable_output / cohort`

before spending significant engineering time comparing premium writer models.

The Sonnet vs GLM copy tournament remains useful.

But it is not on the critical path until the pipeline itself reliably produces valid sequences.

---

# 14. COST — MEASURE THE RIGHT DENOMINATORS

Do not report a single ambiguous "cost per lead."

Track at least:

COST / COHORT LEAD

COST / QUALIFIED LEAD

COST / WRITTEN LEAD

COST / GATE-PASSING LEAD

COST / ENROLLED LEAD

later:

COST / POSITIVE REPLY

COST / QUALIFIED MEETING.

Recent numbers suggested approximately:

6.29c / cohort lead

10.15c / written lead

24.20c / both-gates-passing lead.

Verify rather than copying these numbers.

The key optimization target during development is:

COST PER USABLE OUTBOUND UNIT.

A higher gate-pass rate can reduce effective cost dramatically even if raw generation spend remains constant.

---

# 15. MODEL ROUTING — MAXIMUM VALUE, NOT MAXIMUM CONSUMPTION

Preserve the intent to use more GLM.

But change the optimization target.

DO NOT optimize for:

"consume resetting allowance before it expires."

Optimize for:

> USE RESETTING CAPACITY PREFERENTIALLY FOR USEFUL ELIGIBLE WORK, BUT NEVER CREATE WORK MERELY TO CONSUME CAPACITY.

GLM should be used aggressively where it improves:

- reasoning,
- synthesis,
- critique,
- ambiguity resolution,
- account decisions,
- strategy,
- QA.

Do not run unnecessary repeated reviews after sufficient confidence exists.

Model routing should eventually consider:

TASK TYPE
QUALITY REQUIREMENT
UNCERTAINTY
DECISION IMPORTANCE
CONTEXT SIZE
LATENCY
MARGINAL QUALITY UPLIFT
COST
AVAILABLE ALLOWANCE

Allowance is a constraint/tie-breaker.

It is not the objective function.

---

# 16. MODEL ROUTER — DO NOT OVERBUILD NOW

Continue foundational work needed for:

- centralized model policy,
- structured output,
- reasoning levels,
- fallbacks,
- observability,
- usage/cost tracking.

But defer a large model-benchmark platform until the vertical slice works.

Likewise:

do not build elaborate daily usage automation across every provider before our own internal spend ledger is trustworthy.

First:

MODEL CALL
→ LEDGER
→ UNIT
→ COST
→ CEILING
→ TEST PROVING CEILING FIRES.

Then improve provider usage ingestion.

---

# 17. SPEND LEDGER MUST BE REAL

Verify TASK-323 and related fixes.

Previously:

- model calls were not writing spend,
- ceilings therefore read empty data,
- mixed units were summed incorrectly.

Required invariant:

Every billable/limited model call records:

provider
model
task_type
input_tokens
cached_input_tokens where available
output_tokens
reasoning mode where available
cost or normalized microusd where known
timestamp
client/campaign/account where appropriate.

Do not guess unknown provider pricing.

UNKNOWN remains UNKNOWN.

A ceiling test must prove the call is actually refused when the configured ceiling is exceeded.

---

# 18. GLM STOP CONDITION

Use GLM heavily where useful.

But define escalation.

Example:

cheap/Flash model
→ high confidence + strong evidence
→ accept.

uncertain/conflicting
→ full GLM high.

material strategic ambiguity
→ GLM max / independent critic.

still ambiguous
→ operator question.

Do not automatically run three model passes for every extraction.

Use multi-pass reasoning where:

- decision value is high,
- uncertainty is high,
- failure consequence is material.

---

# 19. TEST HEALTH — RED MUST MEAN SOMETHING

Verify current full-suite baseline.

Recent evidence suggested approximately 128 known failing/error tests.

If the suite remains permanently red, introduce a controlled baseline/quarantine mechanism.

Required behavior:

KNOWN BASELINE FAILURE
= visible technical debt.

NEW FAILURE
= BLOCK.

Baseline count must never silently increase.

Track reduction over time.

Do not hide or delete legitimate tests simply to obtain green CI.

A safety test that fails because production violates the contract is evidence, not noise.

---

# 20. TEST FALSIFIABILITY

Continue the Buggie-derived principle:

For important safety/integration tests ask:

> HOW COULD THIS TEST PASS WHILE THE IMPLEMENTATION IS STILL WRONG?

Particularly for:

- provenance,
- approval hash,
- suppression,
- spend ceiling,
- cadence,
- provider writes,
- cross-channel stop,
- account identity,
- unsupported claims.

Use negative controls and mutation-style checks where appropriate.

Do not accept tests that merely prove:

- a function exists,
- JSON has the right shape,
- a token appears somewhere,
- a fake cassette returns expected fake data.

---

# 21. BUGGIE — USE IT WHERE CONSEQUENCE JUSTIFIES IT

Buggie has found valuable defects.

Keep it as an independent skeptic.

But do not let "continuous Buggie everywhere" become another throughput bottleneck.

Suggested policy:

SAFETY / PROVIDER / APPROVAL / SUPPRESSION / PROVENANCE / LEDGER / CRITICAL INTEGRATION
→ full relevant Buggie review.

NORMAL ISOLATED LOW-RISK TASK
→ targeted tests/static checks.

MASTER INTEGRATION CHECKPOINT
→ broader Buggie review.

Buggie remains report-only unless operator policy changes.

Findings become implementation tasks.

Buggie does not fix its own findings.

---

# 22. APPROVAL HASH — FIX END TO END

Verify the reported defect:

approval artifact stores a hash but production calls `require(campaign_id)` without supplying the current artifact hash.

If confirmed, fix the architecture end-to-end.

Target:

CANONICAL OUTREACH ARTIFACT
↓
DETERMINISTIC SERIALIZATION
↓
HASH
↓
OPERATOR APPROVAL
↓
CURRENT HASH PROVIDED TO WRITE GATE
↓
MATCH?

YES → eligible for next safety checks.

NO → REFUSE.

Any material rerender/change must invalidate the previous approval.

Do not implement this by hashing one preview representation while provider payload derives from another representation.

The hash should correspond to the canonical approved outreach plan.

---

# 23. SUPPRESSION ON RESUME

Verify the reported issue that resume may not re-evaluate suppression.

If confirmed, fix it before new production activation.

A campaign/contact/account that became suppressed after pause must not resume merely because it was eligible before the pause.

Resume must re-evaluate relevant current safety state.

Write negative tests.

---

# 24. SIGNATURES — SIMPLE P0 LAUNCH BLOCKER

Verify mailbox signature state.

Recent evidence suggested no mailbox had a stored signature and all rendered copy showed the missing-signature placeholder.

Do not create a new architecture subsystem for this.

Add signature availability to Launch Readiness.

No production send if required sender/signature state is incomplete.

---

# 25. CROSS-CHANNEL STOP — PROVE IT, DO NOT ASSUME IT

Before scale launch, prove actual provider behavior.

We need a controlled end-to-end test eventually:

EMAIL REPLY
↓
REPLY INGEST
↓
CONTACT/ACCOUNT STATE
↓
CROSS-CHANNEL POLICY
↓
HEYREACH STOP
↓
PROVIDER READBACK CONFIRMS STOPPED.

Where relevant test the reverse direction too.

Do not infer success from:

- local event logs,
- function calls,
- mocked provider responses.

Provider readback is required.

Do not run the live test without explicit operator approval.

Prepare everything required so the operator can authorize one narrow controlled test.

---

# 26. PROVIDER TRUTH WINS

For:

- sends,
- replies,
- bounces,
- membership,
- campaign state,
- channel state,

provider truth is authoritative where available.

Local state may cache/represent it.

It must not silently contradict it.

If provider state is unreadable:

UNKNOWN

not:

clean / zero / safe.

Use complete pagination.

Do not treat partial reads as full estate truth.

---

# 27. IDENTITY SAFETY

Preserve:

ADMITTED
REFUSED
UNVERIFIABLE

for account/company identity where appropriate.

Never bind research from Company B to Company A merely because:

- email domain resembles something,
- LinkedIn search returned a result,
- job actor returned a row,
- name is similar.

Research facts must remain account-bound.

Wrong-company research must fail closed.

---

# 28. SEMANTIC GROUNDING — NOT TOKEN COINCIDENCE

Verify/fix the anti-fabrication weakness where a reused number/token can incorrectly license an unsupported claim.

Grounding must bind:

CLAIM
↔ EVIDENCE MEANING

not:

CLAIM TOKEN
↔ SAME TOKEN SOMEWHERE IN SOURCE.

Similarly:

"marketing" appearing in a source does not prove a marketing-specific strategic claim.

Improve semantic/evidence binding without allowing an LLM judge to override deterministic safety rules.

---

# 29. ONE CURRENT OPERATING DOCUMENT

We now have many historical directives.

Do not delete the audit trail.

But create or update ONE concise current-state document, e.g.:

`docs/OPERATING-MODE.md`

This becomes the first operational document after `CLAUDE.md`.

It should contain only CURRENTLY EFFECTIVE rules:

CURRENT OBJECTIVE

CRITICAL PATH

PRODUCTION FREEZE

ARCHITECTURAL INVARIANTS

MODEL POLICY

WORKER POLICY

DEFINITION OF DONE

LAUNCH BLOCKERS

DEFERRED WORK

CURRENT MASTER SHA

Do not duplicate hundreds of lines from old directives.

Reference historical docs where needed.

Historical directives remain immutable/auditable.

If an old standing rule is superseded, say so explicitly.

---

# 30. MACHINE-DERIVED STATUS

Reduce reliance on prose handoffs.

Create or improve a machine-derived status command if one does not already exist.

Example:

```bash
python scripts/status.py
```

or the repo-equivalent.

It should derive as much as possible rather than accepting manual declarations.

Target sections:

PRODUCTION
- campaigns actually active/sending
- freeze
- pending launches
- provider reconciliation status

PHASE 1
- critical-path components
- merged?
- tested?
- wired?
- blocker

TASKS
- TODO
- REVIEW
- DONE
- stale/mismatched state

WORKERS
- actual claims
- actual locks
- branch/task

SAFETY
- approval gate
- suppression
- provider-write gate
- cross-channel status

COPY
- copy engine version
- cadence version
- skills version
- model policy

COST
- ledger health
- known spend
- ceiling status.

Do not turn this into a huge dashboard project.

CLI/text output is sufficient.

---

# 31. DEFERRED WORK — DO NOT LET IT EXPAND PHASE 1

Unless required to avoid architectural rework, defer:

- full conversational onboarding UI,
- large onboarding workflow,
- autonomous account orchestration,
- massive model benchmark platform,
- elaborate multi-provider daily usage automation,
- new external signal sources,
- Reddit research,
- Google Reviews,
- major learning automation,
- sophisticated retargeting automation,
- unnecessary UI polish.

Record them.

Do not implement them now.

---

# 32. VERTICAL SLICE — PHASE 1 ACCEPTANCE SCENARIO

This becomes the primary definition of Phase 1 success.

Given:

ONE qualified Productive account
with:
2–3 relevant decision makers

Resonate OS must demonstrate:

1. Load canonical Productive client intelligence.

2. Retrieve the relevant Second Brain context.

3. Select/use an approved campaign strategy.

4. Use approved Offer A / Offer B.

5. Research the company ONCE.

6. Reuse company evidence across the buying committee.

7. Identify/select 2–3 relevant decision makers.

8. Create lighter role/person relevance for each.

9. Generate coordinated Email + LinkedIn strategy.

10. Produce the canonical five-email sequence according to the verified threading model.

11. Produce the real canonical LinkedIn cadence/tree.

12. LinkedIn complements rather than paraphrases Email.

13. Each follow-up has a distinct objective/value contribution.

14. No unsupported factual claims.

15. No fabricated provenance.

16. No unrendered variables.

17. No missing required sender/signature state.

18. Copylint passes.

19. Sequence gate passes.

20. Semantic grounding passes.

21. Account identity passes.

22. Preview renders the SAME canonical plan used by provider adapters.

23. XLSX/HTML are projections of the same plan, not independent business logic.

24. Approval hash pins the exact canonical outreach artifact.

25. Material rerender invalidates prior approval.

26. Suppression is evaluated.

27. Resume re-evaluates current suppression.

28. Spend is written to the ledger.

29. Model/provider ceilings can actually refuse.

30. Provider writes remain blocked without operator APPROVED.

31. EmailBison payload can be generated from the canonical plan.

32. HeyReach payload can be generated from the canonical plan.

33. No actual provider write occurs during this acceptance test.

34. Cross-channel stop behavior is ready for a separately authorized live controlled test.

This must be demonstrated through the real production entrypoints as far as safely possible.

Not through isolated mock-only paths.

---

# 33. SCALE THE ACCEPTANCE TEST

Once ONE account passes:

run the same architecture on:

10 accounts.

Then:

50 accounts.

Compare against the previous fifty baseline.

Measure:

held
written
copylint pass
sequencegate pass
both pass
unsupported claim rate
unrendered variable rate
semantic repetition
LinkedIn/Email complementarity
research reuse
model calls/account
model calls/contact
cost/cohort lead
cost/written lead
cost/gate-passing lead.

Do not compare copy aesthetically only.

Compare pipeline quality.

---

# 34. MODEL TOURNAMENT AFTER PIPELINE STABILITY

Once the 50-account vertical slice is stable enough:

run:

Sonnet
vs
GLM strong
vs
GLM cheap/Flash where appropriate

on identical canonical context.

Blind evaluation.

Then update model policy based on evidence.

Do not permanently hard-code a winner based on intuition.

But do not let the tournament delay the integration work above.

---

# 35. LIVE CANARY ONLY AFTER READINESS

Do not launch automatically.

After the vertical slice passes at useful scale, produce a Launch Readiness report.

Minimum categories:

CLIENT INTELLIGENCE
CAMPAIGN STRATEGY
OFFERS
ACCOUNT RESEARCH
BUYING COMMITTEE
EMAIL
LINKEDIN
GROUNDING
PROVENANCE
CADENCE
SIGNATURE
SUPPRESSION
APPROVAL HASH
CROSS-CHANNEL SAFETY
PROVIDER STATE
LEDGER
SPEND CEILINGS

Each:

PASS
WARNING
BLOCKED
UNKNOWN

UNKNOWN is not PASS.

Then request operator approval for a small live canary.

No live canary is authorized by this directive.

---

# 36. DEFINITION OF DONE FOR WORKER TASKS

A worker task is not DONE merely because:

- code was written,
- worker exited 0,
- tests were claimed,
- branch was pushed.

For critical-path work report:

TASK
STATUS
FILES
SCOPE DEVIATIONS
TESTS
TEST RESULTS
PRODUCTION ENTRYPOINT
CONSUMER
END-TO-END EFFECT
LOCAL SHA
REMOTE SHA
BRANCH
MERGED?
MASTER SHA AFTER MERGE
PRODUCTION IMPACT
REMAINING RISK.

Claude verifies before merge.

Cherry-pick only the required commits/files where a worker branch contains junk or scope drift.

Do not merge branch pollution merely to save time.

---

# 37. EXECUTION ORDER

Unless repository evidence requires a different dependency order, execute approximately:

## P0 — STATE / SAFETY

1. Verify actual master + production state.
2. Produce critical-path map.
3. Verify existing P0 safety findings.
4. Fix/merge approval-hash correctness.
5. Fix/merge suppression-on-resume.
6. Verify model ledger/ceiling path.
7. Add signature readiness blocker.
8. Preserve production freeze.

## P0 — PHASE 1 CORE

9. Verify + integrate Second Brain fixes.
10. Verify + integrate Offer Engine.
11. Verify + integrate five skills.
12. Implement/integrate campaign-first strategy.
13. Wire all of them through the real production generation entrypoint.
14. Prove end-to-end consumption.

## P0 — COPY / CHANNEL

15. Fix unrendered-variable defect.
16. Reconcile canonical email threading.
17. Canonicalize actual LinkedIn tree.
18. Remove preview cadence duplication.
19. Ensure Email/LinkedIn consume canonical strategy.
20. Improve semantic grounding/repetition gates.

## P0 — VERTICAL SLICE

21. Build/identify canonical SequencePlan or reuse existing equivalent.
22. One account end-to-end dry run.
23. Fix blockers.
24. Ten-account dry run.
25. Fix systemic blockers.
26. Fifty-account dry run.
27. Compare to previous fifty.

## AFTER THAT

28. Model tournament.
29. Cost optimization based on measured call distribution.
30. Prepare controlled cross-channel live test.
31. Produce Launch Readiness.
32. Wait for operator APPROVED before canary.

---

# 38. DO NOT CREATE ANOTHER GIANT PLAN AND STOP THERE

This directive is not asking for another architecture essay.

The first step is verification.

Then implementation.

Then tests.

Then integration.

Then the vertical slice.

Use documentation to preserve decisions, not as a substitute for implementation.

Do not respond merely:

"Here is the plan."

Execute the safe development work.

---

# 39. INITIAL RESPONSE / CHECKPOINT

After verifying current state, give me a concise checkpoint before or while continuing implementation:

## VERIFIED CLASHES

Only conflicts confirmed against current repo/state.

## FALSE ALARMS

Things from this directive that are already fixed or no longer true.

## CRITICAL PATH

The actual dependency chain from current master.

## TOP BLOCKERS

Maximum 10.

## WORK NOW

What is being implemented immediately.

## DEFERRED

What you intentionally will NOT work on yet.

## PRODUCTION

Confirm whether anything prospect-facing changed.

Then continue implementation without waiting for another message unless an actual operator decision is required.

---

# 40. OPERATOR DECISIONS

Do not silently make decisions that materially change:

- live campaign state,
- commercial terms,
- suppression policy,
- client-approved claims,
- production cadence,
- provider authorization,
- prospect-facing launch,
- pricing/offer promises.

If such a decision blocks the critical path:

surface it clearly.

Do not stop unrelated safe development work.

---

# FINAL OPERATING PRINCIPLE

From this point forward, ask of every new task:

> DOES THIS DIRECTLY HELP US GET FROM CANONICAL CLIENT KNOWLEDGE TO A VERIFIED, PROVIDER-READY, ACCOUNT-LEVEL EMAIL + LINKEDIN OUTREACH PLAN?

If YES:

do it according to dependency priority.

If NO:

put it in backlog unless it is a P0 safety/correctness issue.

We have enough architecture.

Now integrate it.

We have enough agents.

Now optimize throughput.

We have enough intelligence producers.

Now prove consumers.

We have enough copy experiments.

Now make the pipeline reliably produce valid output.

The immediate objective is:

SECOND BRAIN
+
OFFER ENGINE
+
CAMPAIGN STRATEGY
+
ACCOUNT RESEARCH
+
BUYING COMMITTEE
+
FIVE SKILLS
+
EMAIL
+
LINKEDIN
+
QA
+
APPROVAL
+
SAFETY
+
PROVIDER-READY PAYLOAD

working as ONE VERIFIED SYSTEM.

Do not launch anything without explicit operator APPROVED.
