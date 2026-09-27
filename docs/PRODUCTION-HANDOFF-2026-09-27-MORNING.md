PRIORITY: READ FIRST

# PRODUCTION HANDOFF — 2026-09-27 morning

**Written at ~96-98% of Claude's weekly limit. Read this, then
`docs/OPERATING-MODE.md`.** Supersedes the 2026-09-26 evening handoff on
everything it covers.

**Nothing was sent. No campaign was activated, resumed, paused, enrolled or
attached. No provider-changing test ran.** Production freeze stays.

**Claude's weekly limit resets — ask the operator for the exact time; not
tracked programmatically. Until reset, per the operator's 2026-09-27
morning instruction: Claude does exactly two things — merge/push
GLM-passed branches on the critical path only, and answer operator
decisions. Everything else stays on its branch with a GLM verdict attached,
merged after reset.**

## 1. WHAT TO MERGE FIRST, IN ORDER

1. **TASK-400** — `src/generate.py` becomes the real caller of
   `generate_campaign` (or absorbs its body). THE critical-path fix. Just
   dispatched (`docs/qwen-tasks/TODO/TASK-400-generate-py-becomes-the-real-
   caller.md`), not yet started when this was written. Read TASK-391 first
   (see below) before touching this — it already ruled out the smaller fix.
2. **TASK-364** (SequencePlan consumed by both provider factories) — in
   REVIEW on `qwen-worker-worker-r9`. GLM verification dispatched as
   TASK-401. Merge only once TASK-401 returns a PASS verdict.
3. **TASK-391** (skills-at-runtime finding — five skills don't map onto
   `generate.py`'s five stages, TASK-400 must build on this, not repeat the
   attempt) — in REVIEW on `qwen-worker-3-r9`. GLM verification dispatched
   as TASK-402. This is a FINDING, not code — "merging" it means accepting
   the finding into `docs/qwen-tasks/DONE/` once GLM confirms it holds.
4. **TASK-367 rework** — still blocked. `OFFER-A-ECONOMIC-BUYER.cta_link` on
   `qwen-worker-4-r78` is still `book-a-demo`, not the standing single
   allowlisted link (`https://productive.io/get-started/`). TASK-382 (GLM,
   already DONE, see §4) independently confirmed this and found the branch's
   own YAML contradicts itself (line 29 vs line 273). **Nobody has applied
   the rework yet** — dispatch it as a fresh Qwen task if the queue is dry
   of it, then once fixed: **post Offer A and Offer B to the operator for
   approval before doing anything else with them.**
5. **TASK-372** (suite baseline regeneration) — failed to complete four
   times overnight (tool-call-cap / identical-poll-loop pattern). Fixed
   `pool.sh`'s dispatch prompt to require detached long-running steps with
   increasing poll backoff; manually redispatched to `resonate-qwen-2` with
   explicit anti-repetition guidance around 22:48 UTC on 09-26. **Status at
   handoff time unconfirmed** — check `docs/qwen-tasks/*/TASK-372-*.md`
   across worker branches before assuming it finished.

**Once GLM confirms TASK-400/364/391 pass their own acceptance (Checkpoint
A's seven controls, reproduced through the real `src/generate.py` path):
that is the wiring this whole project has been circling since TASK-321
first found "no production entrypoint exists in git" on 2026-09-26 evening.**

## 2. CRITICAL FINDING OF THE NIGHT — GLM CHECKPOINT A (TASK-383, DONE)

`docs/glm-reviews/checkpoint-a-2026-09-27.md`. Seven negative controls, run
against `origin/master` at `fc473844`:

    1. One production entrypoint             FAILS - generate_campaign.py
                                              has zero callers; src/generate.py
                                              is the real path and never calls it
    2. Second Brain has a real consumer      FAILS - secondbrain.for_task()
                                              is called only from the
                                              disconnected generate_campaign
                                              chain; generate.py never
                                              imports secondbrain at all
    3. Canonical research authority          HOLDS
    4. Approved-fact change reaches output   UNVERIFIABLE for production -
                                              provable only inside the
                                              disconnected chain
    5. No critical logic depends on work/    HOLDS
    6. No closed wiring loop                 FAILS - five skills -> generate_
                                              campaign -> nobody
    7. No cross-account research leakage     HOLDS

**This is the same disease QWEN.md names: "a change that is correct and not
consumed is a change that did nothing."** TASK-369, TASK-375, TASK-391 are
all internally correct, individually tested, and currently produce zero
effect on anything a real send would generate. TASK-400 is the fix.

## 3. THE OVERNIGHT POOL PROBLEM — FOUND AND PATCHED, WATCH IT

The pool went **completely idle** for a stretch overnight (0 claims, only
the operator-forbidden TASK-309 showing as "ready") because nothing refills
`docs/qwen-tasks/TODO/` automatically and a sweep can only dispatch a file
that already exists. Separately, three claims (TASK-328/387/389) sat held
for **8+ hours with zero commits** between roughly 22:36 UTC and past 07:00
UTC, invisible to every check that existed at the time.

**Fixed, in this order of discovery:**

- `scripts/pool.sh`'s `checkout -B "$br" master` had no verification and
  piped its errors to `/dev/null`. Under 12 concurrent dispatches, 6 workers
  silently built on stale, months-old branch history for 30-50 minutes
  before anyone noticed. Now fetches `origin/master`, checks out against it
  explicitly, verifies `HEAD` matches before running qwen, aborts and
  releases the claim otherwise.
- `scripts/claim_task.py` now reads a `STATUS: BLOCKED` or
  `ABSORBED_BY: TASK-nnn` field from a task's own header (TASK-384, merged
  and verified — 30/30 new tests, TASK-309 confirmed gone from the ready
  list). Replaced `pool.sh`'s hand-maintained `FORBIDDEN_TASKS` array, which
  had already let TASK-309 get dispatched twice before the real fix landed.
- `docs/OPERATING-MODE.md` WORKER POLICY: standing rule, Claude never ends a
  turn or waits on anything while fewer than 12 task files sit ready in
  TODO/. `ResonatePoolSweep` (Windows Task Scheduler, every 15 min) runs
  `pool.sh sweep` regardless of whether Claude is active.
- `scripts/pool_watchdog.sh` (NEW, running in the background as of this
  handoff — **verify it is still alive**, `tasklist` for a long-lived
  `bash.exe`/`node.exe` chain, or just check `pool-logs/pool-watchdog.log`
  for a recent timestamp): loops `pool.sh sweep` on an interval instead of
  stopping when the backlog empties (which is what let the pool go idle in
  the first place); `release_stale_claims()` releases and reports (both
  local logs plus a `notify.py` record) any claim held ≥60 min with zero
  commits since — the exact TASK-328/387/389 pattern; `requeue_stuck()`
  catches a task that reached RUNNING/ but stalled (with guards against
  requeuing already-DONE or actively-claimed work, added after the first
  version misfired and requeued five already-merged tasks); `alert_if_needed`
  (in `pool.sh`, called every sweep) posts CRITICAL when ready tasks drop
  under 6 or claims stay at zero for 2 consecutive sweeps.
- **Not verified tonight**: whether a live consumer actually delivers
  `notify.py`'s stored `failed_job_needs_attention` records to
  #resonate-os. The function only builds a durable record — that is as far
  as `src/notify.py`'s own docstring says it goes. Check the notification
  store directly, not only Slack, until this is confirmed.
- `pool.sh`'s dispatch prompt now tells every worker to detach any
  long-running step and poll with increasing backoff, never an identical
  check repeated back to back — the CLI's own loop-detector was mistaking a
  legitimate poll loop for the repetition it exists to catch, which is what
  killed TASK-372 four times.

## 4. NINE (NOW MORE) BRANCHES IN REVIEW, GLM VERIFYING

`docs/qwen-tasks/TODO/TASK-401` through `TASK-409` dispatch GLM first-pass
verification for every branch that reached REVIEW overnight: 364 (§1),
391 (§1), 318, 397 (HeyReach seat-cap, READ-ONLY — verify that was honored
before anything else), 394 (contact-key guard — check against TASK-389,
same scope, avoid double-verifying duplicate work), 396 (training-pair
capture, finding-only), 399 (docs hygiene, report-only — Claude applies any
correction, the task does not), 319, 294 (research-pack QA by identity).

**TASK-379/380/381/382 already closed** (GLM verified TASK-369/346/354/367
respectively, all before this handoff — see `docs/glm-reviews/`).
TASK-382's finding (367 blocked, YAML self-contradiction) is why §1 item 4
above exists.

**Per the operator's 96%-limit instruction: Claude cherry-picks only what a
GLM verdict confirms passes.** Do not merge 401-409's targets without
reading the GLM result first.

## 5. TASK-386 — MERGED? CHECK. REAL WORK EXISTS, UNVERIFIED BY CLAUDE

Discovered while resolving a push conflict on `qwen-worker-8-r9`: TASK-386
(ingest LinkedIn + headcount columns into records and packs) was completed
with real commits (`eb66a002` wiring headcount/LinkedIn into packs,
`afa48d18` moved to REVIEW) that Claude never saw before this handoff was
written. **Not yet verified or merged.** Check its REVIEW state and verify
before merging — same discipline as everything else, no shortcut because it
was found late.

## 6. GOVERNING DOCUMENTS, UNCHANGED PRECEDENCE

Same order as the 2026-09-26 evening handoff:
`docs/OPERATOR-DIRECTIVE-2026-09-26-VERTICAL-SLICE.md`,
`docs/OPERATING-MODE.md` (now carries the 12-ready-task-floor standing
rule and the Qwen/GLM-full-capacity order), `OPERATOR-PRODUCTION-FREEZE-
2026-09-26.md`, the model-routing/phase1/onboarding directives, `CLAUDE.md`/
`QWEN.md`. `docs/reference/OPERATOR-CONTEXT-CHECKLIST-2026-09-26.md` is
still reference only.

## 7. OPEN OPERATOR DECISIONS, CARRIED FORWARD

Everything listed in the 2026-09-26 evening handoff §6 that has not since
been resolved, plus:

- **Offer A / Offer B approval** — still pending, now additionally blocked
  on TASK-367's rework actually landing (see §1 item 4). Do not approve
  before the cta_link is fixed to the single standing link.
- **`researchpack` deletion** — TASK-376 demoted it to retired-pending-
  decommission; deleting the package outright is still a separate operator
  call, not made.
- **The 487/489/493 EmailBison campaigns** — 3 of 8 currently-active
  campaigns are ours; verified with the corrected ownership logic in
  `provider_truth.py` (campaigns.jsonl first, name prefix as fallback only).
  Nothing here changed overnight; re-verify with a fresh
  `scripts/provider_truth.py` run before trusting the numbers, per its own
  standing rule.
- **`STALE_CLAIM_MINUTES=60` and `STUCK_MINUTES=30`** in the watchdog are
  first-pass defaults, not tuned against real overnight behavior beyond
  tonight's one incident. Revisit if either fires too eagerly or too late.

## 8. CLAUDE USAGE

**~96-98% of the weekly limit at the time of this handoff.** No Claude
agents, no Buggie, run tonight or since. This document is the only
Claude-written artifact beyond code/task-file commits from this point
until the weekly reset. Per the operator's instruction: after this,
status is one line every two hours (per-worker table, ready-queue depth),
CRITICAL to #resonate-os if the queue is empty or zero claims for two
consecutive sweeps — both already wired into `pool.sh`/`pool_watchdog.sh`,
not something the next session needs to build.

## 9. THE FIRST THREE ACTIONS FOR THE NEXT SESSION (POST-RESET)

1. **Check `pool-logs/pool-watchdog.log` and `pool-logs/pool-critical.log`**
   for what happened while Claude was capacity-limited. If CRITICAL fired,
   read why before doing anything else.
2. **Read every GLM verdict TASK-401-409 (and 386's REVIEW state) produced**
   and merge what passed, in the order given in §1. Do not re-verify what
   GLM already confirmed unless something looks wrong.
3. **If TASK-400 is still incomplete or blocked**, that stays the single
   highest-priority task — it is the fix for the finding that defines
   tonight's Checkpoint A, and everything built on `generate_campaign.py`
   since TASK-369 has produced zero real effect until it lands.
