# OPERATING MODE — which standing order wins, as of 2026-09-26

**The governing directive is
`docs/OPERATOR-DIRECTIVE-2026-09-26-VERTICAL-SLICE.md`.** Where it differs from an
earlier standing order, **it wins.** This file records those differences
explicitly, so nobody has to infer them by comparing documents.

Its objective, in its own words:

> STOP EXPANDING THE ARCHITECTURE AND FINISH THE FIRST PRODUCTION-REALISTIC
> VERTICAL SLICE.

---

## ⚠ THE DIRECTIVE ON DISK IS INCOMPLETE — READ THIS BEFORE ACTING ON IT

**The vertical-slice directive was received truncated.** The file ends mid-sentence
in **section 5**:

    Then:

    EmailBison adapter reads it.

    HeyReach

**Sections 6 through 39 were not received.** That includes every section the
operator referenced by number when transmitting it:

    §15   GLM usage is preferential for eligible work
    §16   the internal spend ledger, on which TASK-359's deferral depends
    §29   this file
    §34   the 50-account vertical slice, on which TASK-363's ordering depends
    §37   the ordered execution list — "continue with section 37 in order"
    §39   the checkpoint — "execute section 39"

**Consequences, stated plainly:**

1. **Sections 39 and 37 have NOT been executed**, because they were never
   received. This is not an omission of judgement; the text does not exist here.
2. The supersessions below **are** actionable and **are** in force, because the
   operator stated them completely in the covering message that transmitted the
   directive. They do not depend on the missing sections.
3. Anything else the missing sections require is **not** in force yet, because
   nobody here has read it.

**Do not treat the file as a complete policy.** Sections 0–5 are verbatim and
binding. Beyond section 5, this repository has no directive text. The remainder
must be re-sent before any part of it is implemented or cited.

---

## 1. SUPERSEDED: worker utilisation is no longer the KPI

**`docs/OPERATOR-DIRECTIVES-2026-09-25.md` §13** — *"Qwen does all heavy lifting.
The pool runs at 100% capacity at all times, with a queue of at least two or three
ready tasks per worker… A queue under two ready tasks per worker is reported as a
DEFECT. An idle worker is reported as a DEFECT."*

**is SUPERSEDED by vertical-slice §1:**

> MAXIMIZE CRITICAL-PATH THROUGHPUT, NOT WORKER UTILIZATION.
>
> An idle worker is NOT automatically a defect.
>
> Do not invent, split, or prematurely execute work merely to keep workers busy.

**What changes in practice:**

- **An idle worker is no longer reported as a defect.** A shallow queue is no
  longer reported as a defect.
- Work is parallelised only when it is genuinely independent, useful,
  non-conflicting, and verifiable and integrable without blocking the critical
  path — all four, per §1.
- Status reports still say what is running and what is queued, because that is
  useful information. They stop calling those numbers failures.
- **This resolves a tension that was already live.** Before this directive, the
  queue was repeatedly driven to depth with peripheral tasks to satisfy the
  two-per-worker floor, while the Phase 1 chain — the actual critical path — sat
  blocked behind unintegrated branches. §13 was the reason; it no longer is.

**Claude remains orchestrator. Qwen remains the preferred implementer.** Only the
utilisation target is withdrawn.

## 2. DEFERRED: the nightly multi-provider usage job

**TASK-359** — the 00:00 Europe/Zagreb job reading usage and balance across every
provider — **is DEFERRED until the internal spend ledger is proven** (vertical-slice
§16).

**Until then, only the ledger-based cost view runs.** That is the view built on
`spendledger` rows: TASK-323 (model spend reaches the ledger, ceiling proven to
fire), TASK-346 (rows carry the real client), TASK-361 (rows carry the routing
decision), TASK-355 (cached tokens priced correctly), TASK-352 (a report that never
sums two units).

**The first run does NOT happen tonight.** No Windows scheduled task is registered.
Nothing that reads a provider dashboard on a timer is started.

**Why this is the right order rather than a loss:** the usage job's value is
cross-checking our own numbers against each provider's. Until the internal ledger
is trustworthy there is nothing to cross-check it against, and a job that reports
a provider's figure beside a ledger that shows zero rows would invite exactly the
wrong conclusion. The ledger came first for a reason.

The delegation rule the job was to enforce — resetting allowances consumed before
anything billed per token — is preserved in §4 below and applies at dispatch time
without the job.

## 3. REORDERED: the copy tournament runs after the slice is stable

**TASK-363** — the A/B/C/D blind tournament (Sonnet / GLM high / GLM Flash /
GPT-6 Sol) — **runs after the 50-account vertical slice is stable**
(vertical-slice §34).

It is not cancelled and its design is unchanged: same facts, same prompts, blind
pages, mapping withheld, email and LinkedIn scored separately, existing gates run
on every arm, capped at $25, no conclusion drawn.

**Claude Sonnet remains the writer in the meantime.** Choosing a writer from a
tournament run against a pipeline that is not yet wired end-to-end would measure
the wrong thing — the arms would be compared on copy generated outside the
production path.

## 4. GLM: preferential, never make-work

Vertical-slice §15: **GLM usage is preferential for eligible work, and never work
created to consume allowance.**

This sharpens, rather than reverses, the model-routing directive. That document
says use GLM aggressively where it makes the system smarter and *"do not generate
meaningless tokens merely to consume allowance"*. §15 makes the second half
binding:

- **Eligible work goes to GLM first.** Its 5-hour and weekly allowances reset, so
  they are consumed before anything billed per token — as are Grok, the Groq free
  tier and the local Qwen pool.
- **No task is created, split or run in order to use allowance.** An unused
  resetting allowance is not a loss to be avoided; inventing work to fill it is a
  cost.
- **Claude's weekly limit stays protected:** orchestration, merges and
  prospect-facing copy only.

## 5. UNCHANGED — none of the following is relaxed by anything above

- **The production freeze.** `docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md`. No
  launch, activation, enrolment, provider attachment, prospect-facing send,
  resume, or provider-changing live test without the operator's explicit
  **APPROVED**. Existing active production is not modified because of a directive.
  493 stays as it is.
- **The review-approval gate.** `reviewapproval.require` still gates activation,
  resume and top-up. Note `TASK-328`: the approval hash is recorded and **not yet
  enforced** at any call site, so an approval row is not proof the current copy was
  reviewed.
- **The five-step email cadence and its threading.** Days 1/4/8/12/21; em1 new/A,
  em2 reply A, em3 new/B, em4 reply B, em5 new/C. Not shortened, not reordered.
- **The LinkedIn cadence tree.** `PRODUCTIVE_LI_HEAVY_V1`, five steps at days
  1/3/6/10/15 across the two branches documented in
  `docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md`. Not simplified, not replaced
  without a separate explicit review.
- **The ceilings.** `spendledger.check` and every per-provider and per-client
  ceiling. Not widened to let a task finish.
- **The GitHub rule.** Committed, pushed, remote SHA verified. A local commit is
  not a completed task; a branch artifact is not on master.
- **Deterministic code governs.** Suppression, sending eligibility, activation,
  budgets, schemas, identity, provenance, provider state, cadence and approval are
  decided in Python. No model verdict overrides a deterministic FAIL.

## 6. Precedence, when two documents disagree

1. `docs/OPERATOR-DIRECTIVE-2026-09-26-VERTICAL-SLICE.md` — **sections 0–5 only**,
   being all that has been received.
2. This file, for the supersessions recorded above.
3. `docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md` — never overridden by an
   architecture or throughput directive.
4. `docs/OPERATOR-DIRECTIVES-2026-09-26-MODEL-ROUTING.md`,
   `docs/OPERATOR-DIRECTIVES-2026-09-26-PHASE1.md`,
   `docs/OPERATOR-DIRECTIVES-2026-09-26-ONBOARDING.md`,
   `docs/ARCHITECTURE-ACCOUNT-FIRST-2026-09-26.md`.
5. `docs/OPERATOR-DIRECTIVES-2026-09-25.md` — **except §13**, superseded above.
6. `CLAUDE.md`, `QWEN.md` and the standing policy files.

**Machine state wins over stale prose**, in all cases and at every level of this
list. Vertical-slice §0 says so, and this session has already found a handoff
reporting three artifacts as verified on master that do not exist there.
