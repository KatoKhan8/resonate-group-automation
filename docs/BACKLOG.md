# BACKLOG — ideas parked with a rationale

**Operator rule, 2026-09-26: no new architecture specs are accepted for seven
days (until 2026-10-03). New ideas go here with a one-line rationale.**

This file exists so an idea is neither lost nor allowed to displace the work in
flight. An entry here is **not** approved, not scheduled, and not a task. It
becomes a task only when the operator says so.

Nothing in this file may be built. Phase 1 continues on Qwen with GLM first-pass
verification; the production freeze in
`docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md` stays in force.

---

## Deferred by the operator, 2026-09-26 — the onboarding layer

The onboarding layer is **review only, until a second client is signed.** Three
foundation pieces were carved out as allowed now (see
`docs/ONBOARDING-REVIEW-2026-09-26.md` when it is written); everything below is
explicitly deferred.

| Idea | Why parked |
|---|---|
| **Conversational onboarding** — an interviewing flow that elicits client knowledge in dialogue | Deferred by the operator. There is one client; a conversation layer has nobody to talk to until a second is signed, and it would sit on top of a Second Brain whose retrieval layer still has no production caller. |
| **Campaign architect** — a component that composes campaign structure from client knowledge | Deferred by the operator. Campaign strategy is TASK-320's per-segment decision and the Offer Engine is still unmerged on a branch; an architect above them would be a third layer over two that are not yet wired. |
| **UI for onboarding / knowledge editing** | Deferred by the operator. `src/web/api.py` is the only consumer of `contextpack.py` today, so a UI would deepen the one dependency the audit calls a display-only path rather than a workflow input. |

---

## Parked earlier, still open

| Idea | Why parked |
|---|---|
| **Account-level orchestration** — next-best-action, primary-contact selection, when to introduce the second and third decision maker | Operator's explicit instruction, 2026-09-26: documented as the intended NEXT layer, deliberately not built in Phase 1. The Phase 1 obligation is only that the data model must not block it — see `docs/ARCHITECTURE-ACCOUNT-FIRST-2026-09-26.md` §2 and TASK-327. |
| **Person-relevance scoring, semantic repetition detection, retargeting, the learning loop** | Listed in `docs/PHASE1-PLAN-2026-09-26.md` as phase 2. The audit calls them recommendations, not bugs, and building them now delays the thing that pays: better copy on the fifty. |
| **Reddit and Google Reviews integration** | `docs/OPERATOR-DIRECTIVES-2026-09-25.md` §8: explicitly out of Phase 1 scope. |
| **Skills six through fourteen** (client research, market intelligence, competitor research, offer development, person relevance, copy QA, reply analysis, performance learning) | The spec proposes fourteen; the operator approved **five**. Directives §6: *"Do not create ten more skills yet."* The five are on a branch and not yet wired — adding more before one is consumed would multiply documentation, not capability. |
| **InMail branch on the LinkedIn cadence** | `INMAIL_ELIGIBILITY_DETECTABLE` is False and no InMail copy has ever been approved, so `heyreachfactory` omits the branch by default. Needs approved copy and a way to detect eligibility before it is worth wiring. |
| **Removing the modules the consumer audit finds disconnected** | Classifying is TASK-344's; removal is an operator decision. Deleting a module that a future task needs is not reversible by the same person who deleted it. |
| **`researchpack` decommission** — TASK-376, 2026-09-26 | Retired-pending-decommission. The live send path reads `rec["research"]` via `packfacts.pack_for()` → `bisonfactory._copylint_batch()`. `researchpack.build()` buys from Apify through its own actors and cache, writes nothing to `rec["research"]`, and its only caller is `scripts/capture_researchpack.py` (manual, not in any generation or send path). `generate_campaign.generate()` reads `account["sources"]` but has no production caller. The canonical store is `rec["research"]`, written by `src/research.py:run()` (site crawl + paid Apify fallback). Deletion of the `src/researchpack/` package is an operator decision — it is a paid-provider integration and removing it is separate from demoting it. |

---

## Deferred by the operator, 2026-09-26 — the model-routing document

`docs/OPERATOR-DIRECTIVES-2026-09-26-MODEL-ROUTING.md` is standing policy in full.
The operator's scope implements sections 15, 16, 17 and 11 now (TASK-360 to
TASK-363). These parts wait for Phase 1.

| Idea | Why parked |
|---|---|
| **Tool-based GLM reasoning** — `get_client_brain()`, `get_account()`, `get_buying_committee()`, `get_replies()` and the rest as read-only tools a model calls to reason (directive §8) | Deferred by the operator. Its value is for account-level orchestration, which is itself deferred, and it would hand a reasoning model a read surface over stores whose retrieval layer still has no production caller. The directive's own constraint stands: no autonomous model gets prospect-facing write authority. |
| **The full model bench, 50–100 golden accounts** across strong/thin research, multiple personas, weak/strong signals, edge-case ICPs, wrong-company identity, geographies and offers (directive §12) | Deferred by the operator. TASK-363 runs the tournament on the fifty first — a real cohort with verified first-party facts and known gate results. Building a 100-account golden set before one benchmark has been read would be scaffolding ahead of evidence. |
| **Account-level orchestration as a GLM reasoning layer** — best first decision maker, primary vs secondary, channel choice, when to introduce the second and third contact, when to pause or stop (directive §9) | Already parked above under the account-first clarification; the model-routing document names GLM as the likely reasoning layer for it. Same rationale: the data model must not block it, and Phase 1's obligation stops there. |
| **Multi-pass critic on every important decision** (directive §6, three passes for campaign strategy, Offer Engine, ambiguous ICP, high-value accounts) | Partly arriving as TASK-345's GLM branch verification and TASK-362's escalation ladder. The general three-pass pattern waits until there is a campaign strategy and an Offer Engine on master to critique — both are still on branches. |
| **Cache-hit instrumentation as a first-class metric** — cacheable tokens, cached tokens, hit rate, effective input cost (directive §14) | TASK-355 prices cached tokens and TASK-361 records the counts. The dashboard-style metric waits until there are rows to aggregate, and the directive's own rule applies: do not claim caching works until real API metrics confirm it. |

---

## Future architecture ideas, not scheduled

IDEA: Subscription Subagent Fan-Out / Execution Routing

We currently think about model routing primarily as: "What level of
intelligence does this task require?" In the future we may add a
second dimension: "How should this task be executed?"

Execution modes:
1. Deterministic Python: safety, permissions, suppression, approval
   state, budgets and spend, provider-write authorization, other
   deterministic production controls.
2. Subscription subagent fan-out: parallel account research, signal
   verification, research-pack QA, code review, independent critics,
   copy and sequence critique, offline analysis, development-time
   exploration.
3. Async model APIs: production-scale reasoning, structured
   classification, enrichment pipelines, measurable latency, retries
   and cost attribution.
4. Premium API judge: ambiguous cases, disagreements between cheaper
   models, high-value or high-risk reasoning.
5. Provider APIs: EmailBison and HeyReach execution.

Future experiment: take the same 10-account vertical slice and
compare the existing API pipeline against subscription-based
parallel subagents. Fan-out per account: Account Researcher, Signal
Verifier, Offer Critic, Copy and Sequence Critic, final synthesis or
judge. Measure output quality, wall-clock batch time, disagreement
rate, HOLD rate, failure rate, API cost, cost per correct result,
orchestration overhead. Hypothesis: subscription subagents provide
cheap parallel cognition for offline and development workloads while
APIs remain the production execution layer.

Do not implement, refactor, change architecture or add runtime
dependencies for this. Current critical path unchanged: SequencePlan,
provider factories, one-account dry run, 10, 50, tournament, Launch
Readiness, operator-approved live canary.

---

## Rules for adding to this file

1. One line of rationale. Say **why it is parked**, not what it is.
2. An idea that would change a gate, a cadence, suppression, approval or spend
   control does not go here — it goes to the operator directly, because parking a
   safety question is a decision in itself.
3. When an entry becomes a task, move it out and leave the task id, so the
   rationale stays readable next to what was eventually built.
