# OPERATING MODE — the only currently-effective rules

**First operational document after `CLAUDE.md`.** Per vertical-slice §29 this
carries **only what is in force now**. Historical directives stay immutable and
auditable; they are referenced, not copied.

Governing document: **`docs/OPERATOR-DIRECTIVE-2026-09-26-VERTICAL-SLICE.md`**,
sections 0–40 plus the final principle, complete and verbatim. **Where it differs
from an earlier standing order, it wins.**

---

## CURRENT OBJECTIVE

> STOP EXPANDING THE ARCHITECTURE AND FINISH THE FIRST PRODUCTION-REALISTIC
> VERTICAL SLICE.

The test for every new task (final principle): **does this get us from canonical
client knowledge to a verified, provider-ready, account-level Email + LinkedIn
outreach plan?** If no, it goes to `docs/BACKLOG.md` unless it is a P0
safety/correctness issue.

Phase 1 success is defined by the **34-point acceptance scenario in §32**, on one
qualified account with 2–3 decision makers, demonstrated **through real production
entrypoints** — not mock-only paths.

## CRITICAL PATH

    CLIENT CANONICAL KNOWLEDGE → SECOND BRAIN → CAMPAIGN STRATEGY
    → APPROVED OFFER A/B → ACCOUNT → ACCOUNT RESEARCH → BUYING COMMITTEE
    → CONTACT/ROLE RELEVANCE → COPY SKILLS → EMAIL + LINKEDIN SEQUENCE
    → CROSS-CHANNEL COORDINATION → QA → CANONICAL SEQUENCE PLAN → PREVIEW
    → APPROVAL HASH → SUPPRESSION/SAFETY → PROVIDER PAYLOAD → WRITE GATE

**Live chain as of `cad7c7a4`:** Offer Engine **on master** (TASK-333 integrated) →
campaign strategy (TASK-320, running) → production wiring (TASK-321, blocked on
320). Five skills verified ready on branch, not yet integrated.

Execution order is **§37**. Do not reorder it without repository evidence.

## PRODUCTION FREEZE

`docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md`. **No launch, activation,
enrolment, provider attachment, prospect-facing send, resume, or
provider-changing live test without the operator's explicit APPROVED.** Existing
active production is not modified because of a directive. **493 is the only
campaign sending and stays as it is.** No live canary is authorised (§35).

## ARCHITECTURAL INVARIANTS

- **Code governs; LLMs reason.** Suppression, sending eligibility, activation,
  budgets, ceilings, schemas, identity, provenance, provider state, cadence and
  approval are decided in Python. **No model verdict overrides a deterministic
  FAIL** (§28, model-routing §5).
- **One truth (§5).** Preview, XLSX, provider adapters, approval and QA are
  **projections** of one canonical plan, never second implementations. Do not
  create a parallel representation if one exists.
- **Consumer before producer (§4).** Wired means: *changing valid upstream
  information changes downstream production output through the real entrypoint.*
  A module, a function, a passing unit test, `A imports B`, or a doc saying
  "integrated" are **not** wiring. Zero production callers = **DISCONNECTED**.
- **Provider truth wins (§26).** Unreadable provider state is **UNKNOWN**, never
  clean/zero/safe. Complete pagination; a partial read is not estate truth.
- **Identity fails closed (§27).** ADMITTED / REFUSED / UNVERIFIABLE. Research
  stays account-bound; never bind Company B's research to Company A.
- **Provenance is never fabricated.** VERIFIED / CLIENT_APPROVED / INFERRED /
  UNKNOWN. INFERRED may inform strategy, never become a prospect-facing assertion.
  UNKNOWN is not invented.
- **Grounding binds claim to evidence meaning (§28)**, not a token to the same
  token somewhere in the source.
- **Cadence is fixed.** Five emails, days 1/4/8/12/21, em1 new/A · em2 reply A ·
  em3 new/B · em4 reply B · em5 new/C — **pending §6 reconciliation**, which must
  document the canonical rule before anything changes.
  LinkedIn `PRODUCTIVE_LI_HEAVY_V1`, five steps, days 1/3/6/10/15, two branches
  (`docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md`). Not simplified, not shortened.
- **GitHub is the source of truth.** Committed, pushed, remote SHA verified. A
  branch artifact is not on master.
- **Machine state wins over stale prose (§0).**

## MODEL POLICY

`docs/OPERATOR-DIRECTIVES-2026-09-26-MODEL-ROUTING.md` stands, sharpened by §15:
**use resetting capacity preferentially for useful eligible work; never create
work to consume capacity.** Allowance is a tie-breaker, not the objective.

    Qwen / local     implementation, bulk transformation
    Groq             trivial fast classification
    GLM Flash        extraction, synthesis, fact normalisation, relevance,
                     semantic QA, grounding, reply classification
    GLM high/max     strategy, ambiguity, difficult QA, independent critic
    Sonnet           prospect-facing copy — until §34's tournament says otherwise
    CODE             every safety decision

Escalation (§18): cheap pass with confidence → accept; uncertain or conflicting →
GLM high; **still ambiguous → operator question**, never a third model guessing.
Never max reasoning for trivial extraction. Router: `TASK-360`; observability:
`TASK-361`; no model slug outside `config/model_policy.yaml`.

## WORKER POLICY

**SUPERSEDES `docs/OPERATOR-DIRECTIVES-2026-09-25.md` §13 entirely.** That section
required 100% utilisation and 2–3 queued tasks per worker, and called an idle
worker a defect.

**§1 replaces it: MAXIMIZE CRITICAL-PATH THROUGHPUT, NOT WORKER UTILIZATION.**

- **An idle worker is not a defect. A shallow queue is not a defect.** Neither is
  reported as one.
- **Do not invent, split or prematurely execute work to keep workers busy.**
- Parallelise only work that is *all four*: independent, useful, non-conflicting,
  and verifiable/integrable without blocking the critical path.
- Claude orchestrates and merges. Qwen implements. GLM reviews first-pass.
- Buggie (§21) is scaled to consequence: full review for safety/provider/approval/
  suppression/provenance/ledger/critical integration and at master checkpoints;
  targeted checks otherwise. **Report-only. Findings become tasks. Buggie does not
  fix its own findings.**

## DEFINITION OF DONE

§36. Not done because code was written, the worker exited 0, tests were claimed, or
a branch was pushed. Critical-path tasks report: TASK · STATUS · FILES · **SCOPE
DEVIATIONS** · TESTS · TEST RESULTS · **PRODUCTION ENTRYPOINT** · **CONSUMER** ·
**END-TO-END EFFECT** · LOCAL SHA · REMOTE SHA · BRANCH · MERGED? · MASTER SHA
AFTER MERGE · PRODUCTION IMPACT · REMAINING RISK.

**Claude verifies before merge. Cherry-pick only the required files** where a
branch carries junk or scope drift — merging pollution to save time is forbidden,
and one such branch would have silently reverted the provenance fix.

Tests must be falsifiable (§20): ask *how could this pass while the implementation
is still wrong?* Not accepted: proving a function exists, JSON shape, a token
appearing, a fake cassette returning fake data.

**Suite (§19):** baseline is `docs/state/SUITE-BASELINE-2026-09-26.txt`, **128
named failures**. A known baseline failure is visible debt; a **new failure
BLOCKS**; the baseline count **may never silently increase**. Never delete a
legitimate test for green CI — a safety test failing because production violates
the contract is evidence.

## LAUNCH BLOCKERS

Open, and each blocks prospect-facing launch:

1. **Approval hash not enforced** — `require(campaign_id)` passes no hash at all
   three call sites, so an approval survives a re-render. §22, `TASK-328`.
2. **Resume does not re-evaluate suppression** — `EMAIL_RESUME` is `facing=False`,
   so `revalidate()` never runs. §23, `TASK-331`.
3. **No mailbox has a stored signature** — 155 email steps render empty. §24,
   `TASK-341`. Must become a Launch Readiness item.
4. **Cross-channel stop unproven at the provider** — readback required, never
   inferred from logs or mocks. §25. Needs separate operator authorisation.
5. **Grounding passes on token coincidence** — `_traces` reduces to
   `token in supported`. §28, `TASK-330`.
6. **`unrendered_variable`** — 13 of the fifty's 31 written leads. §37 step 15.
7. **Preview duplicates cadence** — hardcoded LinkedIn days 1/3/8/14 against a
   canonical 1/3/6/10/15. §5, §37 step 18, `TASK-343`.
8. **All 6 offers are `approval_status: pending`** — correct fail-closed, and an
   **operator decision** (§40). Campaign strategy has no approved offer to use.

Launch Readiness (§35) reports PASS / WARNING / BLOCKED / UNKNOWN per category.
**UNKNOWN is not PASS.**

## DEFERRED WORK

`docs/BACKLOG.md`, with a rationale per entry. Per §31: conversational onboarding
and its UI, large onboarding workflow, autonomous account orchestration, the
50–100 account model bench, elaborate multi-provider usage automation, new external
signal sources, Reddit, Google Reviews, major learning automation, retargeting
automation, UI polish.

Also deferred by covering instruction: **`TASK-359`** (nightly multi-provider usage
job) until the internal ledger is proven — only the ledger-based cost view runs,
and **no scheduled task is registered**; **`TASK-363`** (copy tournament) until the
50-account slice is stable (§34).

## CURRENT MASTER SHA

Last verified: **`cad7c7a4`** on `origin/master`.

This line is a snapshot and goes stale by design. **Derive it, never trust it:**

```bash
git fetch origin && git rev-parse master origin/master
```

§30 requires a machine-derived status command so state stops living in prose. Until
it exists, `scripts/task_registry.py` and `scripts/claim_task.py --status` are the
authorities for task and worker state, and the provider is the authority for
campaign state.
