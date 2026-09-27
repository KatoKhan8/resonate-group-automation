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

## KOMUNIKACIJA S OPERATEROM — trajno pravilo

**Operaterova odluka, 2026-09-27. Vrijedi nakon `/clear`, u svakoj budućoj sesiji,
za Slack agenta i za sve statuse.**

1. **Operator updates i statusi pišu se na hrvatskom.** Tehnički identifikatori
   ostaju kakvi su u kodu i ne prevode se: imena testova, putanje datoteka, SHA-ovi,
   imena taskova, imena polja i naredbe.
2. **Odluke se traže jedna po jedna, u formatu 🔴 TREBAM TVOJU ODLUKU**, i svaka
   nosi preporuku s obrazloženjem. Nikada više odluka u jednom bloku, jer se tada
   odgovori na prvu i ostale se izgube.
3. **Svaka tvrdnja o stanju imenuje svoj autoritet** (vidi "State is explicit,
   never inferred" niže). To je jezično neutralno i vrijedi i na hrvatskom.

**OVO JE CLAUDEOVO ČITANJE OPERATEROVE UPUTE, NE CITAT.** Uputa od 2026-09-27
glasi "ovo pravilo upiši u docs/OPERATING-MODE.md", a samo pravilo nije bilo
izrečeno u tekstu; izvedeno je iz zahtjeva za "prvi hrvatski operator update" i za
"novi format 🔴 TREBAM TVOJU ODLUKU, jednu po jednu, s preporukom". Ako je čitanje
netočno ili preširoko, operater ga ispravlja i ova se sekcija mijenja. Zapisano je
ovako, s naznakom izvora, upravo zato što trajno pravilo izvedeno iz pretpostavke
mora biti provjerljivo, a ne nevidljivo.

## ARCHITECTURAL INVARIANTS

- **Business logic never depends on gitignored `work/`.** Safety logic,
  canonical schemas, claim-licensing evidence and any reproducible pipeline
  definition must be in git or unreachable from production — this is the same
  defect found twice already: `work/v2_run.py` (TASK-321, the production
  entrypoint had nowhere to terminate) and the case-study pages before
  TASK-365's rework (a gate whose only evidence lived in a gitignored
  directory fails open on a clean clone). Runtime and prospect state may live
  in `work/`; the logic that reasons about them may not.
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
- **State is explicit, never inferred.** Never infer execution state from a proxy
  when direct evidence exists, and every operational state claim names its
  authority. Learned the hard way on 2026-09-27: a claim's recorded PID is the
  *claiming* process and not the worker, so a PID check reports every live claim
  as dead (which is why `--reap` refuses); a branch's task-file stage is an
  artifact and not task state, which hid 134 of 143 TODO tasks and starved the
  pool to zero ready while twelve workers polled; commit freshness is not worker
  liveness; a count of files in `TODO/` is not ready depth; a config block is not
  enforcement (`messaging_rules` was recorded and read by nothing); and a passing
  test is not runtime integration (`generate_campaign` had zero production
  callers while its tests were green). `TASK-424`'s lease-based registry is the
  scheduler instance of this invariant. Campaign, approval, provider, spend and
  provenance state are the next instances, after the one-account slice.

**GLM is a permanent independent reviewer**, not an implementer:
`docs/GLM-REVIEW-PROTOCOL.md` is the standing contract — review triggers,
checkpoints, the isolated-worktree rule, falsification over confirmation, and
the eight dispositions every finding must carry. Claude reproduces every
material finding independently before it becomes work.

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

## WORKER POLICY — KRITIČNI PUT IDE NA CLAUDE SUBAGENTE

**Operaterova odluka, 2026-09-27 popodne. Nadjačava starije pravilo "Qwen
implementira, Claude samo dispatcha i mergea" ZA KRITIČNI PUT.**

Razlog je izmjeren, ne pretpostavljen: Qwen je istoga dana pao na sva tri P0
pokušaja, svaki put tako da je izgledao gotov. TASK-400 je uhvatio `NotApproved` i
tiho se vratio na stari pipeline, pa je gate ostao otvoren; TASK-364 je izgradio
derivaciju naopako, iz već izgrađenih leadova, tako da mutacija plana ne može
promijeniti projekciju a testovi su zeleni po konstrukciji; TASK-372 je dobro
izmjerio pa predložio da se 228 padova prihvati kao nova baseline. Svaki krug je
kostao sate.

- **Kritični put implementiraju Claude subagenti (Opus)**, svaki u svom worktreeju,
  s jednom acceptance provjerom. Redoslijed: `TASK-426`, pa rework `TASK-364`, pa
  `TASK-400`, pa `TASK-425` (one-account dry run).
- **GLM ostaje neovisni verdikt**, uvijek protiv head SHA grane, nikada protiv
  mastera. Verdikt bez imenovanog SHA je NIŠTAVAN.
- **Claude mergea na GLM PASS.** Ako GLM ne odgovori u 45 minuta, Claude smije
  mergeati na temelju vlastite neovisne verifikacije PLUS pregleda drugog Claude
  subagenta. Dva neovisna pogleda, nikada jedan.
- **Qwen ostaje na punom kapacitetu izvan kritičnog puta**: taksonomija padova,
  auditi, backlog, testovi.
- **Stara pravila o štednji Claude tokena s prethodnog računa ne vrijede za
  kritični put.** Claude se troši tamo gdje skraćuje vrijeme do dry runa. Izvan
  kritičnog puta disciplina ostaje.

## WORKER POLICY

**Standing order, 2026-09-26 evening:** the Qwen pool and GLM run at full capacity
on real backlog at all times; Claude only dispatches, verifies and merges. When a
worker finishes, the next task from the critical path or the standing backlog goes
out immediately; if the queue ever empties, post the reason in the status rather
than inventing work. Report per-worker task and Claude usage in every status.

**Standing order, 2026-09-26/27 overnight — the 12-ready-task floor.** Found the
hard way: the pool went fully idle for a stretch because nothing refills TODO/
while Claude is doing something else, and a sweep only ever dispatches a task
file that already exists. **Claude never ends a turn, or goes idle waiting on
something, while fewer than 12 task files sit ready in `docs/qwen-tasks/TODO/`.**
Refilling the queue with real, falsifiable, acceptance-checked tasks from the
standing backlog comes BEFORE waiting for anything else to finish. A 15-minute
`ResonatePoolSweep` scheduled task runs `scripts/pool.sh sweep` regardless of
whether Claude is active, precisely so the pool does not depend on Claude's
attention to keep moving.

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

Last verified: **`3badeab0`** on `origin/master`, 2026-09-27 12:23 Europe/Zagreb,
by `git rev-parse master origin/master` (both matched). The previous value in
this line, `cad7c7a4`, was stale by at least three commits.

This line is a snapshot and goes stale by design. **Derive it, never trust it:**

```bash
git fetch origin && git rev-parse master origin/master
```

§30 requires a machine-derived status command so state stops living in prose. Until
it exists, `scripts/task_registry.py` and `scripts/claim_task.py --status` are the
authorities for task and worker state, and the provider is the authority for
campaign state.
