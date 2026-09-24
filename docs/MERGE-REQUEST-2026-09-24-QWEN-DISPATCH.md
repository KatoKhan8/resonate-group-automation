# Merge request — Qwen pool dispatch, 2026-09-24 late

    LANE      E (Qwen pool dispatch)
    BRANCH    worktree-agent-a12ddab5c442ad2f9
    WORKTREE  .claude/worktrees/agent-a12ddab5c442ad2f9
    BASE      24acafff, tip of master at 2026-09-24 22:52
    SCOPE     docs only. No `src/`, no `scripts/`, no `config/`, no `work/`,
              no provider call of any kind.

This lane wrote task files and recorded queue state. **It changed no running
code and made no provider read or write.**

---

## 1. TODO DEPTH, BEFORE AND AFTER

    DISPATCHABLE DEPTH   before  1      <- CRITICAL. The rule is >= 10;
                                           below 5 is a CRITICAL.
                         after   13

    RAW FILE COUNT in docs/qwen-tasks/TODO/
                         before  33
                         after   42

**The two numbers disagree and both are true.** The handoff records the
dispatchable depth as 1; the directory held 33 files. The gap is the finding,
not a bookkeeping detail:

- **Four finished tasks were still filed in `TODO/`.** TASK-275, 277 and 278
  were delivered tonight and TASK-276 was blocked, and all four sat in `TODO/`
  as though they were waiting for a worker. They are moved in this branch
  (§3).
- **At least two `TODO/` files are claimed in another worktree.** `TASK-192`
  and `TASK-262` are in `TODO/` on master AND in `RUNNING/` inside
  `resonate-qwen-worker`, `resonate-qwen-6`, `-7` and `-8`, whose working
  trees were last touched 2026-09-23 21:33-21:36. `TASK-272` is additionally
  in qwen-7's `RUNNING/` and `TASK-273` in qwen-8's. A file in `TODO/` here
  and `RUNNING/` there is exactly the collision `README.md` was rewritten to
  prevent on 2026-09-15, when six workers picked the same task and four
  produced the same result.
- The rest of the 29 older files have not been triaged in this lane. **Some
  are certainly live and some are certainly superseded, and nobody knows
  which**, which is why the pool reads as deep and dispatches as empty.

That triage is **TASK-287** (§2), which audits the problem register and the
queue in one sweep. Until it runs, treat the dispatchable depth as **13** —
the thirteen written tonight — and do not assume the other 29 are available.

    REVIEW/   14 files (was 11)
    BLOCKED/   3 files (was 2)

---

## 2. THE TEN TASKS

The operator named ten items. They are dispatched as **thirteen files**,
because item 10 is four separate second-pass reviews and four workers cannot
claim one file.

    #   ID        TITLE
    1   TASK-279  the 19,612 packs arrive in chunks or they do not arrive
    2   TASK-280  the reconciler only asks one direction
    3   TASK-281  the UK/EU re-engagement age comes from the provider, not
                  the cache
    4   TASK-282  the spend report nobody reads on a Monday
    5   TASK-283  S7 renders three bodies and the cadence wants four
    6   TASK-284  the MX walk that stopped before it finished
    7   TASK-285  the collision walk batch 3 is sitting behind
    8   TASK-286  the suite baseline is a list of names, or it is nothing
    9   TASK-287  four issue numbers were taken twice
    10  TASK-288  second pass: do the account-rule tests actually fail, and
                  for the right reason?          (reviews TASK-275)
        TASK-289  second pass: the Apify calibration that hit a boundary
                                                 (reviews TASK-276)
        TASK-290  second pass: the copy lint was wired into a module that
                  refuses to send                (reviews TASK-277)
        TASK-291  second pass: does the spend report read the provider, or
                  read us?                       (reviews TASK-278)

### Priorities and dependencies

    P0   279, 280, 281, 283, 285, 288, 290
    P1   282, 284, 286, 287, 289, 291

    TASK-291 BLOCKS TASK-282       do not wire an unsourced spend figure into
                                   a client-visible Monday document
    TASK-282 DEPENDS ON TASK-278   which is not on master
    TASK-283 DEPENDS ON the cadence completion, which Lane B owns
    TASK-285 DEPENDS ON TASK-275's red tests
    TASK-290 DEPENDS ON TASK-277, whose verdict is already REJECTED

### What every file carries

Each one states **the question it answers**, **the acceptance bar**, **what
evidence counts**, and **WHAT WOULD MAKE THIS A FALSE PASS** — written
specifically so the task cannot be satisfied by mocking the thing under test.
Each names FILES ALLOWED and FILES FORBIDDEN, and each ends in a result block
whose fields are the evidence, not a summary.

Two house lessons are baked into every acceptance bar that can carry them:

- **A suite baseline is a LIST, not a count.** `74` and `74` compare equal
  while a different 74 tests fail, and the 2026-09-23 host comparison hid 17
  host-only failures behind two counts that differed by exactly 17.
  Regenerate the JSON and diff the SETS **both directions**. TASK-286 is
  entirely this; TASK-280, 283, 284, 285, 286 and 288 each require a
  two-direction set diff of their own.
- **A green suite proves nothing live.** Fixtures get invented and then mock
  the buggy function — about thirty tests were green against three Apify
  actor ids that answer 404, because the cassette and the code agreed with
  each other and neither agreed with Apify. Every task that could be
  satisfied by fixtures requires a live provider read or a `work/*.jsonl`
  row, quoted by named field.

A third, from the worktree lesson: every task that touches state names
`WORKSPACES` and requires the worker to say **which copy of production's
`work/` it read and when that copy was taken**. Most worker worktrees have no
`work/queue.jsonl` at all, and the one that did held a copy 37 minutes behind
production.

---

## 3. TONIGHT'S FOUR DELIVERIES — STATE RECORDED

None is on master. All four are moved out of `TODO/` and carry an appended
`STATE RECORDED BY LANE E` block.

    TASK-275  account-rule + collision-gate RED tests
              qwen-2, r9      -> REVIEW/     review: TASK-288

    TASK-276  Apify cost calibration
              boundary hit    -> BLOCKED/    review: TASK-289

    TASK-277  copylint wiring
              qwen-4          -> REVIEW/     **REJECTED, DO NOT MERGE**
                                             review: TASK-290

    TASK-278  spend report from provider balances
              qwen-5          -> REVIEW/     review: TASK-291

### TASK-277 — the verdict, recorded not re-derived

Established by the production session, which read the delivery itself
(`PRODUCTION-HANDOFF-2026-09-24-LATE.md` §4.1): `run_with_copylint` is called
by nothing; all 8 tests call it directly and 0 call `push.run(`; and
`src/push.py` is not the send path at all — its `run()` raises on
`live=True`, and the real path is `scripts/batch1_push.py` →
`bisonfactory.stage`. **The lint was wired into a module that refuses to
send, through a function nobody calls, proved by tests that call it
directly** — the exact defect the task was written about, reproduced by the
fix for it.

**The re-wiring belongs to another lane and is in progress.** TASK-290 states
this in its FORBIDDEN list: no Qwen worker may edit `src/push.py`,
`src/bisonfactory.py`, `src/copylint.py` or the lint call site. TASK-290's
job is the salvage table, the red wiring assertion the lane will need, and a
proposal for the general "guard module with no caller" check.

---

## 4. THE ROLLING DEFAULT-CHECK LIST

New file: **`docs/qwen-tasks/DEFAULT-CHECKS.md`**, kept beside the TODO and
refilled every status cycle so it never falls below ten. 12 entries, 0
claimed.

**Idle workers are never idle.** A worker with no claimed task takes the
lowest-numbered unclaimed check rather than helping itself to a `TODO/` file
dispatched to somebody else. Results land as a short doc or a task file —
**never as a change to running code**, and never as a provider write.

    QWEN — walk a live process, or measure a stage
      DC-01  a campaign's queue vs our store, every mismatch with evidence
      DC-02  a watcher's heartbeat vs its own log (and the module mtime
             against the process start — a merge is not a deploy)
      DC-03  a cohort's READY count vs the S5 journal
      DC-04  S5 verification throughput and cost/row; the cheapest speed-up
      DC-05  one other stage's throughput and cost/row
      DC-06  every campaign listing sorted by created_at — it is null on the
             campaigns that actually send
      DC-07  queue hygiene: TODO/ vs what is genuinely dispatchable

    GLM — one merged safety path, looking for the bypass
      DC-08  one gate or stop: how can it pass without checking?
      DC-09  one ownership/reconciliation path: an id compared across
             providers, a set membership standing in for a resolution
      DC-10  one guard module with no caller, by import graph

    GROK — one provider or cost question, with sources
      DC-11  a documented rate/concurrency limit that speeds a stage up
      DC-12  a cheaper endpoint or batch API, priced at 19,612

Findings that save time or cost become tasks the same day.

---

## 5. WHICH WORKERS ARE IDLE

Determined from each worktree's `docs/qwen-tasks/RUNNING/` and its working-
tree mtimes. **Directory listings only — no other worktree was written to.**

    qwen-2   IDLE      RUNNING/ empty · tree touched 2026-09-24 21:08
    qwen-3   IDLE      RUNNING/ empty · tree touched 2026-09-24 21:09
    qwen-4   IDLE      RUNNING/ empty · tree touched 2026-09-24 21:08
    qwen-5   IDLE      RUNNING/ empty · tree touched 2026-09-24 21:27

    qwen-1   STALE     RUNNING/ holds TASK-192, TASK-262 · 2026-09-23 21:33
    (worker)
    qwen-6   STALE     RUNNING/ holds TASK-192, TASK-262 · 2026-09-23 21:36
    qwen-7   STALE     RUNNING/ holds TASK-192, TASK-262, TASK-272
                                                          · 2026-09-23 21:33
    qwen-8   STALE     RUNNING/ holds TASK-192, TASK-262, TASK-273
                                                          · 2026-09-23 21:33

**Four idle, and four holding day-old claims that master still shows as
TODO.** The four stale worktrees are not proof that four workers are running:
a `RUNNING/` file is a claim, and a claim 25 hours old with no branch movement
is a claim nobody is working. Verify before believing the pool is busy —
`README.md` records that a worker replying "Ready. What's the task?" has done
nothing, and that a pool can look busy while doing nothing at all.

### Suggested first dispatch, one task per worker, named explicitly

    qwen-2   TASK-285   the collision walk. NOT TASK-288 - qwen-2 wrote
                        TASK-275 and must not review its own delivery.
    qwen-3   TASK-288   second pass on the account-rule red tests. qwen-3
                        wrote none of tonight's four.
    qwen-4   TASK-291   second pass on the spend report. NOT TASK-290 -
                        qwen-4 wrote the copylint delivery.
    qwen-5   TASK-290   second pass on the copylint delivery. NOT TASK-291 -
                        qwen-5 wrote the spend report.

**A worker does not review its own delivery.** qwen-2 wrote TASK-275 and
qwen-4 wrote TASK-277 and qwen-5 wrote TASK-278; each of those three is
assigned somebody else's review above. The remaining ten tasks dispatch as the
stale workers are confirmed free.

Dispatch by absolute path, one named task per worker, and have each worker
`git mv` its file to `RUNNING/` as its first action so the claim is visible:

    C:\Users\Zvonimir\AppData\Local\qwen-code\bin\qwen.cmd
        --approval-mode yolo  "<prompt naming exactly one task file>"

---

## 6. WHAT THIS LANE DID NOT DO

- **No provider call.** No EmailBison, HeyReach or Apify read or write.
- **No edit to** `config/.env`, `src/providers/*`, `scripts/*_watch_loop.py`
  or anything under `work/`.
- **No edit to Lane B's files** — `config/clients/productive.yaml`,
  `src/cadence.py`, `scripts/batch1_build.py`. TASK-283 verifies against them
  and forbids editing them.
- **No edit to Lane D's files** — the copylint wiring, `src/push.py`, the
  `bisonfactory` lint call site. TASK-290 forbids all four.
- **No touch to another worktree.** The idle census is directory listings.
- **No merge, no push to master.** This branch is for review.

## 7. REVIEW CHECKLIST FOR WHOEVER TAKES THIS

- [ ] The thirteen new files are docs only; `git diff --stat` shows nothing
      outside `docs/`.
- [ ] TASK-290 forbids the files Lane D owns, and does not duplicate its work.
- [ ] TASK-283 forbids the files Lane B owns.
- [ ] The four moved task files carry their recorded state and no task file
      was deleted.
- [ ] `DEFAULT-CHECKS.md` has >= 10 entries and the no-code-change rule.
- [ ] The dispatch assignment does not give any worker its own delivery to
      review.
