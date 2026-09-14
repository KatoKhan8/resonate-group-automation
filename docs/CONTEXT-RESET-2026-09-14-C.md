# Context reset checkpoint C, 2026-09-14 18:2xZ

Supersedes `CONTEXT-RESET-2026-09-14.md` and `-B.md` where they disagree.
Everything here was READ from git or from a provider today. Nothing is
inferred from a plan.

**The single most important line in this file:** the first real send happened
today, and the HeyReach campaign is still NOT updated at the provider.

---

## 1. GIT - VERIFIED

    master HEAD     9caa824  (or later; `git log --oneline -1` is authority)
    origin/master   identical, verified with `git fetch && git rev-parse`
    worktree        clean

    ALL EIGHT worker branches sit at ec02c80, which is an ancestor of master.
    UNINTEGRATED COMMITS: ZERO. UNPUSHED COMMITS: ZERO.

    worktree                              branch
    C:\Users\Zvonimir\Desktop\resonate-group-automation   master
    C:\...\resonate-qwen-worker           qwen-worker
    C:\...\resonate-qwen-2                qwen-worker-2
    C:\...\resonate-qwen-3                qwen-worker-3
    C:\...\resonate-qwen-4                qwen-worker-4
    C:\...\resonate-qwen-5                qwen-worker-5
    C:\...\resonate-qwen-6                qwen-worker-6
    C:\...\resonate-qwen-7                qwen-worker-7
    C:\...\resonate-qwen-8                qwen-worker-8

Nothing is stranded on a branch. Everything of value is on master and pushed.

## 2. QWEN PRO

**AVAILABLE.** Probed twice this session: a cheap probe returned `READY`, and
a real file read that spends tokens returned a correct answer with no 429.

    binary      C:\Users\Zvonimir\AppData\Local\qwen-code\bin\qwen.cmd
                NOT on PATH. Always invoke by absolute path.
    version     0.23.3
    capacity    ~40k weekly (operator), eight worktrees prepared

**EARLIER TODAY QWEN WAS QUOTA-EXHAUSTED AND IS NO LONGER.** Do not carry the
old "Qwen is unavailable" conclusion forward. The recovery policy is in §8.

    RUNNING     none. All eight workers are idle and synced.
    REVIEW      empty
    REWORK      empty
    BLOCKED     empty
    TODO        TASK-036, 037, 039, 040, 041, 042, 044, 054, 057, 058, 059

**CREDENTIALS ARE NOW IN EVERY WORKTREE.** The operator authorised full
credential access for Qwen on 2026-09-14, superseding the narrow `LLM_*`-only
proposal in `docs/DELEGATION-BOUNDARY-2026-09-14.md`. That document is
retained for its argument about WHY the seam mattered; its recommendation is
overtaken by a broader grant.

    mechanism   scripts/sync_worker_env.py
                plain file copies. No symlink, no junction, no admin rights,
                nothing that can break on this Windows box.
    safety      it REFUSES to write into any worktree whose git does not
                ignore `config/.env`, and it prints variable NAMES with
                AVAILABLE/MISSING and never a value.
    rotation    re-run with `--write`. Copies do not propagate on their own.

Verified after the write, in all eight worktrees:

    config/.env    IGNORED (.gitignore line 5), untracked,
                   zero dirty .env entries
    verdict        NO WORKTREE CAN COMMIT config/.env

14 variables available in each: the three `LLM_*`, plus BISON, HEYREACH,
CONTACTOUT, APIFY, REOON, DELIVERABLE, BLITZ and the workspace pin.

**THE PROHIBITION THAT NOW MATTERS MORE THAN IT DID THIS MORNING.** Qwen
worktrees hold real EmailBison and HeyReach keys. Every task file dispatched
since carries it explicitly: **READS ONLY.** No write, no send, no campaign
mutation, no lead added, no sequence replaced. `QWEN.md`'s old claim that
"there are no credentials in this worktree - so this is structural, not a
promise" is NO LONGER TRUE, and the protection is now a rule rather than a
property. That is a real reduction in safety margin, bought deliberately for
throughput, and the next session should know it was a trade and not an
oversight.

## 3. HEYREACH - THE P0

    campaign 599020   RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1
    status            DRAFT
    leads             0          read from the provider, not inferred
    listId            None
    nodes             24         expected 17
    merge variables   NONE       expected 8
    'jacob' present   YES

**LIVE WRITE HAS NOT OCCURRED. THE PROVIDER IS UNCHANGED.** The operator
checked the dashboard and was right; `docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md`
is the API agreeing with them.

**Permission is no longer the blocker.** The operator granted
`Bash(py -3 scripts/write_heyreach_sequence.py:*)` this session.

**The blocker is COPY, and the gate is correct to refuse:**

    acqcom-com/brian-price's copy repeats itself: 'connected_1' and
    'connected_4' share 4 words (across, day-to-day, right, tracking)

Regeneration progress at checkpoint time: **471 generation steps logged
across 51 records** and STILL RUNNING as a background job that will not
survive the reset. It is safe to lose: `store.transaction()` commits per
record, so every finished record is durable, and re-running is idempotent -
the planner only re-plans steps that fail a gate.

**A defect found and fixed while chasing this, and it is why a full
regeneration did not converge:** two repetition checks disagreed and the
stricter one was unreachable from the generation loop. `campaign_repetition`
(stage-time) said li2 vs li5 collide; `repetition_across_rungs` (what the
storer and planner ran) said NONE. So the storer kept accepting replacements
that collided the same way, forever. `_note_quality` now asks both, so the
stage-time check is a backstop rather than the only place the question is
asked. Commit `ec02c80`.

## 4. EMAILBISON

    campaign 451   RESONATE - PRODUCTIVE CANARY - Hot Soup Group
    status         completed
    emails_sent    1
    sent_at        2026-09-14T16:24:20Z
    bounced        0     unsubscribed 0     replied 0
    open_tracking  FALSE

**THE FIRST REAL SEND THIS SYSTEM HAS EVER MADE.** Full write-up in
`docs/CANARY-451-SENT-2026-09-14.md`, with the 290 watcher samples preserved
in `docs/evidence-451-watch-2026-09-14.jsonl`.

**`opened: 0` MEANS NOTHING** - open tracking is off on that campaign, so the
zero is an absent measurement, not an absent open. `replied: 0` is real but
was hours old at n=1 and is not a reply rate. The three-minute watcher is
dead after the reset; re-read 451 from the provider to see whether a reply
has landed since.

    campaign 481   paused, 23 leads, 5 provider-visible steps, 0 sent

The five-step cadence EXISTS at the provider and is verified - ids 4729-4733,
waits 3/4/4/9/1, all active. The "2-step" report from an earlier session is
NOT reproducible against the API and is a UI question, not a generator one.

481 cannot send: `EMAIL_ACTIVATE` is not in `providerwrites.SUPPORTED`. Its
nine live leads carry copy generated against ladder rungs 1, 3 and 4 that
ALL CHANGED TODAY, so that copy must be regenerated before 481 is considered
again.

## 5. CAMPAIGN QUALITY - THE RULES, AND EACH WAS PAID FOR

Every one of these came from a measured defect today, not from taste.

- **No hardcoded names.** 599020 carries "hi jacob" for a row naming
  fourteen records. Thirteen other people would have received it.
- **Real merge variables, single brace.** Measured across 81 sequences:
  3,295 single-brace occurrences, ZERO double. `{{first_name}}` reaches a
  prospect as literal text.
- **The model must be told what Productive IS.** The word "Productive"
  occurred ZERO times in the rendered prompt. The `product:` block in
  `config/clients/productive.yaml` is the fix and both prompts consume it.
- **Distinct narrative progression.** WHO -> PROBLEM -> WHAT IT IS ->
  DIFFERENT ANGLE -> EASY OUT.
- **No repeated question.** Four askings of the profitability question is the
  defect that started this.
- **No unsupported claims**, and the rule keeps turning out one phrase short:
  plural `discussions`, bare `our conversation`, and `I have not heard from
  you` were all found and closed TODAY. Expect a fourth.
- **No invented product.** `ProjectSync` was generated and stored clean
  through every gate; `claims.foreign_product` now refuses it.
- **Safe fallbacks.** The operator's eight hand-written LinkedIn fallback
  lines pass every gate and read better than the generated copy. They are
  the floor, and they are good.
- **Five email steps, six LinkedIn activities**, branching on state.
- **Five materially different variants per meaningful step** - NOT built.
  TASK-044 is queued and needs model access.

## 6. LEARNING SYSTEM

    historical HeyReach analysis   NOT STARTED - TASK-058 queued
    historical Bison analysis      NOT STARTED - TASK-059 queued
    reply classifier               exists; LinkedIn 64% unreadable,
                                   email 46.5%
    outcome attribution            DOES NOT EXIST. Nothing can say which
                                   touch produced which reply.
    experiments running            none
    confirmed touches              1, for the first time ever

Findings worth carrying: 8-step email sequences reportedly reply at 8.49%
(n=17,690) - TASK-059 must RE-DERIVE that rather than trust it.

## 7. PRODUCTION SCALE

    CANARY  ->  SMALL BATCH  ->  MEDIUM  ->  LARGE
      DONE        <- we are here, not yet started

Rung 1 complete and clean: 1 sent, 0 bounced, 0 unsubscribed, correct
recipient, no fabricated claim.

**Evidence required before the next promotion:**

    email    481's nine leads regenerated against the CURRENT ladder,
             rendered and read as a human, then EMAIL_ACTIVATE enabled
             deliberately with `expect_leads` matching
    linkedin 599020 written, read back, and EXPECTED == ACTUAL on all 27
             rows of `scripts/heyreach_readback.py --expect`
    both     no wrong recipient, no duplicate, no suppression violation,
             no fabricated claim

## 8. ORCHESTRATION POLICY - PERMANENT

**QWEN PRO IS THE PRIMARY WORKFORCE.** Target ~80% of safely delegatable
implementation and analysis work.

**CLAUDE** owns architecture, decomposition, acceptance criteria, root-cause
analysis, code review, safety review, provider-write authorisation, provider
readback, experiment design, integration and promotion.

Claude must not duplicate Qwen work without a documented reason. The
permitted reasons: repeated Qwen failure, architectural judgment, production
authority, credentials that prevent delegation, or a P0 where waiting stops
production.

**REVIEW IS NOT A FORMALITY.** Six Qwen tasks were integrated today and FOUR
needed correction:

    TASK-049  checked only the FIRST contact and called the rest safe by
              assumption. 2 of 10 had repeating copy and neither was first.
    TASK-052  claimed a fix; measured 0 of 3 and did not work.
    TASK-055  silently rewrote two curly apostrophes as ASCII, which would
              have made `lint` refuse every contraction like "don't". Its
              own thirteen new tests passed because they built fixtures from
              the same mangled constant.
    TASK-053  correct, but its exit code had to be read off the process -
              piping to `tail` reported 0 where the real code was 1.

**QUOTA POLICY.** A quota or rate-limit failure is TEMPORARY and must never
be recorded as "Qwen is unavailable". If the provider states a reset time,
retry shortly after it. Otherwise probe every THREE HOURS with a cheap probe
("reply READY"). Queued work stays queued; never silently move a Qwen
backlog to Claude.

## 9. NEXT ACTIONS - ORDERED

**P0-1. Re-run the regeneration and drive it to a passing dry run.**
Immediately executable:

    py -3 -m src.generate --live --client productive
    py -3 scripts/write_heyreach_sequence.py productive-linkedin-production-v1

Repeat until the second command stops raising `FactoryRefused`. It is
idempotent and only re-plans failing steps. The gate now asks both
repetition questions, so it can converge where it previously could not.

**P0-2. Live write, then readback, then compare.** Permission is granted.

    py -3 scripts/write_heyreach_sequence.py productive-linkedin-production-v1 --live
    py -3 scripts/heyreach_readback.py productive-linkedin-production-v1 --expect
    echo $?          # MUST be read without a pipe. A pipe reports tail's status.

All 27 rows must pass. `jacob` absent, 8 merge variables, no repeated message
on any path.

**P0-3. Dispatch Qwen.** Eight idle workers, eleven queued tasks. Dispatch
with the absolute binary path, `--approval-mode yolo`, and NO
`--max-tool-calls` cap - a 400 cap killed two workers mid-task today.

**P1-1.** Export provider history to `work/exports/` so TASK-058 and TASK-059
can run. Claude does the read; Qwen does the analysis.
**P1-2.** Regenerate 481's nine leads against the current ladder, render,
read as a human.
**P1-3.** TASK-054 - the product rung says "our platform", not "Productive".
Needs model access in a Qwen worktree, or Claude runs it.

**P2.** TASK-044 five variants; TASK-057 email preview; TASK-036/037/039/
040/041/042.

## 10. THE ONE DECISION WAITING ON THE OPERATOR

Grant the Qwen worktrees an `.env` containing ONLY `LLM_API_KEY`,
`LLM_BASE_URL` and `LLM_MODEL`. Without it, bulk regeneration, variant
generation and live prompt measurement cannot be delegated, and the ~80%
target cannot be met on the work that actually matters right now.

---

## 11. TWO THINGS THE NEXT SESSION WILL SEE AND SHOULD NOT MISREAD

**A regeneration was still running when this was written.** `py -3 -m
src.generate --live --client productive`, 471 steps logged across 51 records.
It writes through `store.transaction()`, which is atomic per record, so the
ledger is consistent whenever it stops. It does not survive the reset. Re-run
it; it is idempotent and only re-plans steps that fail a gate.

Verified at checkpoint time: `work/queue.jsonl` holds **300 records, zero
unparseable**.

**`work/queue.jsonl.32172.tmp` is stale garbage.** Dated 01:01 today, and
process 32172 is long gone - an interrupted write from an earlier session.
`store` writes to a temp file and renames, so a leftover temp means a process
died mid-write, NOT that the queue is damaged. The queue parses cleanly. It
was left in place rather than deleted because `work/` is production state and
a handoff is not the moment to tidy it.
