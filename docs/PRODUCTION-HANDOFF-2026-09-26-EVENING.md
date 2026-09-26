# PRODUCTION HANDOFF — 2026-09-26 evening

**Read this, then `docs/OPERATING-MODE.md`.** It supersedes the 2026-09-26 morning
handoff on everything it covers.

**Nothing was sent. No campaign was activated, resumed, paused, enrolled or
attached. No provider-changing test ran. No provider write of any kind occurred
today** — the action ledger's last row is still 2026-09-18.

**The next session does MERGE, PUSH and DECISIONS only.** Claude's weekly limit is
at ~90%.

---

## 1. CAMPAIGN STATE — AND IT IS NOT FRESHLY VERIFIED

**No provider read was made today.** The figures below are from the 2026-09-26
morning handoff, and `docs/state/PROVIDER-CAMPAIGNS.json` was generated
**2026-09-23T10:02Z** — three days stale.

    493   ACTIVE, the only campaign sending, 22 leads / 22 sent
    491 492 494 496 503 504 505   paused
    495   archived
    497 498   completed

**Checklist item 7 applies: verify provider state before making any current claim.**
Run `scripts/provider_truth.py` (a read) before acting on these numbers. Treat them
as last-known, not as current.

76 recipients remain suppressed from the 09-23 blank-email incident, verified
through `channels.email_verdict`. Four who replied to a blank email still need
their senders personally: 491/142778, 491/190068, 492/142663, 497/167877.

## 2. GOVERNING DOCUMENTS, IN PRECEDENCE ORDER

1. **`docs/OPERATOR-DIRECTIVE-2026-09-26-VERTICAL-SLICE.md`** — governing. Sections
   0–40 plus the final principle, complete and verified (41 sections, no gaps).
2. **`docs/OPERATING-MODE.md`** — the only currently-effective rules, per §29. Read
   second, always.
3. **`docs/OPERATOR-PRODUCTION-FREEZE-2026-09-26.md`** — never overridden by an
   architecture or throughput directive.
4. `OPERATOR-DIRECTIVES-2026-09-26-MODEL-ROUTING.md`, `-PHASE1.md`,
   `-ONBOARDING.md`, `ARCHITECTURE-ACCOUNT-FIRST-2026-09-26.md`.
5. `OPERATOR-DIRECTIVES-2026-09-25.md` — **except §13, superseded.**
6. `CLAUDE.md`, `QWEN.md`, standing policy files.

**`docs/reference/OPERATOR-CONTEXT-CHECKLIST-2026-09-26.md` is REFERENCE ONLY.** Not
governing, not a directive, not permission to redesign. Current machine state wins
over it.

**§13 is dead.** Worker utilisation is no longer the KPI — critical-path throughput
is. **An idle worker is not a defect. A shallow queue is not a defect.** Do not
invent work to fill the pool.

## 3. CRITICAL PATH — WHAT IS VERIFIED ON MASTER

`origin/master` = **`b3336974`**. 30 commits integrated today.

| Component | On master | Verified how |
|---|---|---|
| Second Brain provenance | ✅ | By hand: 0 hardcoded sources, `verified=False` default, `**scope` raises. 37 facts, none verified-true. |
| Offer Engine | ✅ | 11 tests; `NotApproved` raises naming the offer; `missing()` returns the 5 gaps |
| Campaign strategy, per segment | ✅ | **Mutation-verified**: disabling the cache breaks 3 tests. `model_call_count()==1` for 50 leads |
| sequencegate → bisonfactory | ✅ | AST-verified call site inside `stage()` line 54, after copylint, before any provider call, refuses and names the step. Closes audit Bug 5 |
| Model spend → ledger | ✅ | Ceiling **proven to fire**: `BudgetExceeded` naming "PROVIDER CEILING". `to_micro_usd(0.00256)=2560` |
| Suite baseline | ✅ | `docs/state/SUITE-BASELINE-2026-09-26.txt`, **128 named failures**, 12,737 tests |
| LinkedIn cadence as-built | ✅ | `docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md` — 5 steps, days 1/3/6/10/15, two branches, **no step dropped before the provider** |

**NOT on master:** the v2 copy pipeline (`copyengine`, `copystages`, `copyprompts`
have no production caller), five skills, SequencePlan, `capability_by_persona` as a
list, the Offer A/B layer.

**The finding that defines the critical path:** TASK-321's rework concluded **no
production entrypoint exists in git**. The path that produced the ten and the fifty
is `work/v2_run.py`, which is **gitignored and not in version control**. So the v2
layer has nowhere to terminate, and wiring it is not a code problem — it is that
the production entrypoint itself is missing from the repository.

## 4. TASKS — EVERY BRANCH AWAITING REVIEW

All workers idle; **0 claims**. Five branches pushed, none merged.

| Task | Worker | Branch | Artifact | Acceptance / verdict |
|---|---|---|---|---|
| **366** capability list | qwen-3 | `qwen-worker-3-r76` | `productive.yaml`, `cadence.py`, `secondbrain.py`, tests | **List landed with your exact values.** Verify primary resolves first for both personas, bare string still works, unknown persona still omits, `product_words` still returns one sentence |
| **321** wiring | qwen-2 | `qwen-worker-2-r75` | **finding only, no code** | **DONE — "the second answer": no production entrypoint in git.** The permitted honest answer. Read it before planning the slice |
| **365** case-study evidence | qwen-worker | `qwen-worker-r74` | `scripts/fetch_case_studies.py`, `copylint.py`, tests | Still RUNNING at close. 11 pages fetched? claim-not-on-page refuses? summary figure absent from page reported, not allowed? |
| **354** CTA link rule | qwen-5 | `qwen-worker-5-r77` | `productive-offers.yaml`, `productive.yaml`, `copylint.py` | **`book-a-demo/` must be REFUSED despite HEAD 200** — that proves the allowlist, not the resolver. Also sets `domain: productive.io` and self-exclusion |
| **368** GLM reconciliation | qwen-4 | `qwen-worker-4-r77` | `docs/glm-reviews/CHECKLIST-RECONCILIATION-2026-09-26.md` | Sections A–D only. **No file:line = not a confirmed gap.** Triage A into tasks; ignore the rest |
| **367** Offer A/B layer | — | queued, needs 366 | — | Two offers, both `pending`. Offers reference capability ids, never restate a value proposition |
| **364** SequencePlan | — | queued, needs 321 | — | One object, six consumers; changing the plan changes all six |
| **342** review workbook | — | queued | — | 3 sheets + HTML, projection only, no model call, posted pair immutable |
| 323 326 328 330 331 332 336 337 338 339 340 341 343 344 345 346 347 348 349 350 351 352 353 355 356 357 358 359 360 361 362 363 | — | mixed | — | See `docs/state/TASK-REGISTRY.json`. **309 is permanently merge-blocked — do not dispatch** |

## 5. OPERATOR DECISIONS MADE TODAY

- **ONE prospect-facing link, standing:** `https://productive.io/get-started/` only.
  No segmented meeting links, no `book-a-demo`, no other Productive URL, ever.
  **This superseded a segmented-links instruction issued minutes earlier — those are
  withdrawn.** Allowlist of exactly one.
- **`capability_by_persona` is an ordered list, first entry primary.**
  `economic_buyer: [profitability, budgeting, billing]`,
  `champion: [resource_planning, project_management, time_tracking]`. It owns angle
  order only — the `offers:` block owns persona-to-offer. No second mapping.
- **Personas:** economic buyer = CEO, Founder, Owner, COO, CFO. Champion =
  Operations Manager, Project Manager, Finance Manager. Operations Director either,
  by seniority and context.
- **Offer A** (economic buyer) = profitability + budgeting + financial/operational
  visibility, mechanism demo with a Productive AE. **Offer B** (operations) =
  project_management + time_tracking + resource_planning, mechanism trial or demo.
  **Both stay `pending`.**
- **Demo approved**, up to one month if needed; booked AE meeting is an approved
  CTA. **Not** inferred from it: discounts, guarantees, free consulting, free
  audits, custom implementations, POCs, customer deliverables, pricing promises.
- **Trial:** 14 days, no credit card. VERIFIED (public + brief), reconfirmation
  requested. **Not in canonical config** — `productive.yaml` has no offers block.
- **Case studies CLIENT_APPROVED:** the 11 public studies may be named with figures
  published on those pages. **`page_text` is `null` on every record, so nothing is
  quotable yet.** An `operator_summary` figure absent from its page is NOT LICENSED
  and must be reported.
- **Profitability while a project runs** is approved; "real-time" and "live" were
  removed from PR-001 and BU-001.
- **§13 superseded**, TASK-359 deferred, TASK-363 deferred until the slice is stable.

## 6. OPEN DECISIONS FOR THE OPERATOR — one line each

1. **Approve Offer A / Offer B?** Nothing prospect-facing can carry an offer until you do.
2. **Where does `billing` go** — Offer A, Offer B, neither, or its own offer?
3. **The 300-lead Monday cohort cannot be built from inventory** — 237 usable contacts, and their freshness is unestablished because the queue records no send events.
4. **Run TASK-340's $2 cache measurement** once TASK-355 prices cached tokens correctly?
5. **No mailbox has a signature stored** — supply them, or accept unsigned sends?
6. **The 9,107 already-verified leads** revert to `held` under the new order; grandfather them?
7. **A zero-cost call to an undeclared provider** is still allowed; which position wins?
8. **Cents-vs-credits backfill rate** for historical ledger rows — confirm `usd_estimate: null` for unpriced providers?
9. **`LINKEDIN_STOP_LEAD` has never run live** — authorise one narrow controlled cross-channel test?
10. **`work/v2_run.py` is not in git**, so the only path that has ever produced copy is unreproducible from a clone — accept, or make rebuilding it a P0?

## 7. CLAUDE USAGE

**~90% of the weekly limit** (your figure — I have no programmatic read). Foreground
is restricted to reading worker and GLM output, merging verified branches, pushing,
answering decisions, and one status line per two hours. **No Claude agents, no
Buggie runs** (13 Claude agents), no Claude-written docs beyond the status line.
**Stop at 98%.**

Anything genuinely needing Claude goes to `docs/BACKLOG.md` with its reason and
waits for the reset. **TASK-345's GLM branch-verification harness has not landed**,
so "GLM gives first-pass merge verdicts" currently runs through Qwen-driven tasks
rather than an automated gate.

## 8. THE FIRST THREE ACTIONS FOR THE NEXT SESSION

**Merge, push and decisions only.**

**1. Verify and merge TASK-366** (`qwen-worker-3-r76`). Cherry-pick by path. Check:
primary resolves first for both personas, a bare string still works, an unknown
persona still omits rather than crashing, and `product_words` still returns
`capability` as one sentence. **Three branches today carried a pre-322
`secondbrain.py` that would have silently reverted the provenance fix — check every
file you take, not just the ones the task names.** Merging 366 unblocks TASK-367.

**2. Read TASK-368's GLM reconciliation**
(`docs/glm-reviews/CHECKLIST-RECONCILIATION-2026-09-26.md` on `qwen-worker-4-r77`).
Triage section A only. **No file:line means not a confirmed gap.** Use existing
tasks where they exist; create the smallest task only where none does. Do not create
one task per checklist item.

**3. Read TASK-321's finding and put the entrypoint question to the operator.** It
concluded no production entrypoint exists in git. Until that is resolved, TASK-364
(SequencePlan) and the vertical slice have nowhere to terminate, and every "wire the
v2 layer" task will keep producing closed loops — **three did today.**

**Do not** dispatch TASK-309 (merge-blocked), approve any offer, resume any
campaign, or run Buggie.
