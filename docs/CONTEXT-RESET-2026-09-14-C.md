# Context reset checkpoint C, 2026-09-14 18:2xZ

**SUPERSEDED** by `docs/CONTEXT-RESET-2026-09-15-D.md` and
`docs/CONTEXT-RESET-2026-09-15-E.md` (current). This document is historical.
Do not act on its numbers.

Supersedes `CONTEXT-RESET-2026-09-14.md` and `-B.md` where they disagree.
Everything here was READ from git or from a provider today. Nothing is
inferred from a plan.

**THE TWO MOST IMPORTANT LINES IN THIS FILE, and both are now good news:**

    campaign 451 SENT 2026-09-14T16:24:20Z - the first real send, 0 bounced
    HeyReach 599020 UPDATED - 27/27 provider readback PASS

Sections 3 and 4 below were written BEFORE the HeyReach write and are left in
place because the before-state matters. **Section 19 is the current truth for
HeyReach and supersedes section 3.**

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

---

## 12. WORKER MAPPING AT CHECKPOINT TIME

Dispatched 2026-09-14 evening, after credentials reached the worktrees. All
running concurrently; none had reached REVIEW when this was written.

    worker    worktree                  branch          task
    1         resonate-qwen-worker      qwen-worker     TASK-054 product name
    2         resonate-qwen-2           qwen-worker-2   TASK-060 credential
                                                        verification
    3         resonate-qwen-3           qwen-worker-3   TASK-058 HeyReach
                                                        touch -> reply
    4         resonate-qwen-4           qwen-worker-4   TASK-059 Bison
                                                        email -> reply
    5         resonate-qwen-5           qwen-worker-5   TASK-057 five-email
                                                        preview
    6         resonate-qwen-6           qwen-worker-6   TASK-042 no real name
                                                        in campaign copy
    7         resonate-qwen-7           qwen-worker-7   TASK-041 two quadratics
    8         resonate-qwen-8           qwen-worker-8   TASK-039 what the model
                                                        actually gets

    still in TODO   TASK-061 (drive the regeneration to a passing dry run),
                    TASK-036, 037, 040, 044

**A WORKER'S OUTPUT IS NOT FINISHED WORK.** Each was told to move its task to
`REVIEW/`, not `DONE/`. Claude reviews, then moves it to `DONE` or back to
`REWORK` with precise feedback. Four of the six Qwen tasks integrated earlier
today needed correction; the reasons are in §8 and are worth reading before
trusting any of the above.

**HOW TO DISPATCH**, because it is not obvious and two workers were killed by
getting it wrong today:

    C:\Users\Zvonimir\AppData\Local\qwen-code\bin\qwen.cmd
        --approval-mode yolo
        "<the task prompt>"

Absolute path - `qwen` is NOT on PATH. Do NOT pass `--max-tool-calls`; a 400
cap killed two workers mid-task. Run each from inside its own worktree.

## 13. REGENERATION - WHERE IT ACTUALLY GOT TO

The full pass COMPLETED (exit 0). 619 generation steps across 64 records of
the 300 in the queue; the rest answered "nothing to generate", which is the
planner correctly finding no failing step.

The dry run still refuses, and **the blocker MOVED**, which is what
convergence looks like when the refusal names one contact at a time:

    before   acqcom-com/brian-price        connected_1 vs connected_4
    after    <client-a86dfd>-com/ranjan-damodar  five colliding pairs, all sharing
                                           "across", "capacity", "projects"

`brian-price` is fixed. `ranjan-damodar` is worse than he was: four messages
arguing capacity in four different sentences, which is precisely the defect
the operator named at the start of the day.

TASK-061 drives this loop, caps it at five passes, and asks the question that
decides what to fix next - whether the shared words are SUBJECT words
(capacity, profitability, utilisation) or STRUCTURAL ones. Subject words mean
`SUBJECT_VOCABULARY` needs widening; structural ones mean the ladder does.
**That call is Claude's, not Qwen's.**


---

## 14. CREDENTIAL VERIFICATION - PASSED, AND WHAT IT PROVED

TASK-060, run by Qwen worker 2 on `qwen-worker-2`, integrated to master.

    QWEN_MODEL_ACCESS      PASS
    QWEN_PROVIDER_CONFIG   PASS
    QWEN_TASK_EXECUTION    PASS

    10 of 11 planned steps generated, 17 model calls for one record.
    em2 failed all three lint attempts and was NOT stored, correctly.
    The repetition, unsupported-claim and subject-length gates all fired.

Claude generated nothing on its behalf. The worker read the task, reached the
model, wrote copy, ran the gates against its own output, ran the tests and
committed. **Bulk regeneration, variant generation and live prompt
measurement are all delegable from here.**

It also corroborated TASK-054 without being told it existed: "No step mentions
Productive by name." Third independent observation of the same defect.

### Secret leak scan - NONE

Every value of length >= 12 in `config/.env`, one variable at a time, via
`git grep -F` across all ten remote branches:

    CONTACTOUT_TOKEN, AIARK_KEY, REOON_KEY, DELIVERABLE_KEY, BISON_KEY,
    EMAILBISON_API_KEY, HEYREACH_KEY, APIFY_TOKEN, BLITZ_API_KEY,
    LLM_API_KEY                        absent from every branch

    BISON_BASE, LLM_MODEL, LLM_BASE_URL   present and NOT secret - an API
                                          base URL and a model name, both
                                          documented in BUILD-SPEC.md

**A FIRST PASS REPORTED TEN LEAKS AND WAS WRONG.** It ORed every value into
one `git grep -F -e ... -e ...`, so a match on the model name looked like a
match on a key. Anyone re-running this check will write the same query;
search one variable at a time and classify config separately from secrets.

Re-run it after any change that touches credentials or worktrees.


---

## 15. SECOND DISPATCH ROUND - ALL EIGHT WORKERS RUNNING

    worker  branch          task
    1       qwen-worker     TASK-054 REWORK  measure the estate, not one record
    2       qwen-worker-2   TASK-061         drive regeneration to a passing
                                             dry run, capped at five passes
    3       qwen-worker-3   TASK-058         HeyReach touch -> reply
    4       qwen-worker-4   TASK-059         Bison email -> reply
    5       qwen-worker-5   TASK-057         five-email preview renderer
    6       qwen-worker-6   TASK-063         read the five emails as a human
    7       qwen-worker-7   TASK-064         read the LinkedIn cadence, both
                                             branches, as a human
    8       qwen-worker-8   TASK-039         what the model actually gets

    TODO    TASK-036, 037, 040, 044, 062
    REWORK  TASK-042 (name gate), TASK-054 (sampling)

### Reviewed this round

**TASK-041 INTEGRATED.** Two quadratics and a repeated policy lookup, fixed
without changing any verdict. Verified on 84 tests across the real affected
surface. Note for future task authors: TASK-041 named two test modules that
DO NOT EXIST (`test_campaign_segments`, `test_bisonfactory`). Check a module
name before putting it in a task file.

**TASK-042 REJECTED to REWORK.** The name gate breaks SEVENTEEN tests -
twelve errors in `test_the_sequence_belongs_to_nobody` and five in
`test_campaign_repetition_integration`. That first module is the one
protecting the exact defect the gate exists to prevent, so a gate that breaks
it is wrong somewhere. Design kept, wiring sent back. Master reverted and
green.

**TASK-054 REJECTED to REWORK, and this is the more interesting one.** Qwen
measured four prompt variants three times each on ONE record, got 3/3
everywhere including the baseline, and honestly reported its hypothesis
unconfirmed. The harness is good; the conclusion is not. Measured against the
real estate the same evening:

    stored li4 notes  50, naming Productive 21   42%
    stored em3 bodies 38, naming Productive 11   29%

The behaviour is STOCHASTIC. Twelve runs of one record landed on a record
that names it reliably; three in five do not. Neither "0 of 3, broken" from
TASK-052 nor "3 of 3, fine" describes the system. **The Productive-
introduction defect is REAL and remains open**, now with a measured baseline
to beat.

## 16. A FINDING NOBODY WAS LOOKING FOR

13 of 630 stored steps still carry an em dash or curly apostrophe AFTER a
full regeneration pass:

    1gslab-com li1 li3 li4, 25wat-com li1, <client-abb4a2>-com li1 li4, and others

`lint` refuses those characters, so `plan` DID re-plan them. The regeneration
then failed to produce a replacement that passed the other gates, and
`linkedin_note` stores nothing on failure - **so the old failing note stays
exactly where it was.**

It cannot ship: `cadence.status_for` holds it and `eligibility` refuses the
payload. But it is compared against as a SIBLING, which means a bad note that
will never be sent can block a good replacement by colliding with it. TASK-062
asks whether that is actually happening and recommends rather than deletes -
removing stored generated work is Claude's call, and `CLAUDE.md` says a record
is dropped with a reason rather than deleted.


---

## 17. THE CRITICAL PATH, CORRECTED

`docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md` is the important read.
Short version, measured on the contact that is blocking the dry run:

**The copy really is bad.** `<client-a86dfd>-com/ranjan-damodar` asks the same
question four times - "utilisation and capacity across your projects" - which
is the original defect with a different noun, plus a fabricated "our previous
discussions" on a record whose `prior_contact` is False.

**Every gate correctly catches it** and the planner re-plans all six notes
with accurate reasons.

**And it still cannot be fixed by regenerating**, because the old failing
notes remain SIBLINGS. `_note_quality` compares a new candidate against the
stored steps, so a good new `li2` is judged against five stale notes that say
nothing but "capacity across projects", collides with four, is refused, and
is never stored. The stale note stays; the next pass hits the same wall.

That is exactly the observed behaviour: a completed pass MOVED the blocker
from `brian-price` to `ranjan-damodar` instead of clearing it.

    TASK-062 IS THE UNBLOCKER FOR TASK-061.

TASK-061 should be expected to report NOT CONVERGED until 062 lands, and that
is the finding rather than a failure.

### The route not taken

Discounting the client's own angle vocabulary clears all five collisions on
this contact - measured, 5 to 0 - and was REJECTED. `SUBJECT_VOCABULARY`'s own
comment says structural words like "visibility" and "planning" must keep
counting, and the client's angle list contains both. A gate that passes four
askings of the same question is not a better gate; it is the defect returning
with the alarm switched off. **Do not widen it.**

## 18. FIRST REAL OUTCOME DATA - TASK-058 INTEGRATED

76,315 outbound LinkedIn touches across 26,113 conversations, read from the
provider. `docs/ESTATE-HEYREACH-OUTCOMES-2026-09-14.md`.

    per-conversation reply    4,007 of 26,113     15.34%
    per-touch reply           5,291 of 76,315      6.93%
    POSITIVE reply            178 of 76,315       0.233%
    reply delay               median 6.1h

**73.6% of replies are unreadable to the classifier** - 3,894 of 5,291. That
is the number that reframes the rest: 0.233% positive is what survived a
classifier that cannot read three quarters of its input, so it is a FLOOR
rather than a rate, and any copy comparison built on the readable quarter is
a comparison over a biased sample.

TASK-066 is queued and running against it, with the rule that outranks the
number: do not reduce `unknown` by guessing. An UNKNOWN pauses the account; a
wrong POSITIVE lets automation continue at somebody who said no.


---

## 19. HEYREACH IS UPDATED - THIS SUPERSEDES SECTION 3

    py -3 scripts/heyreach_readback.py productive-linkedin-production-v1 --expect
    REAL EXIT CODE = 0
    27 passed, 0 failed     VERDICT: PASS     sequence_matches: MATCH

Full evidence: `docs/HEYREACH-599020-UPDATED-2026-09-14.md` and
`docs/evidence-heyreach-readback-2026-09-14.txt`.

    nodes              24 -> 17
    merge variables     0 -> 8
    'jacob'        PRESENT -> absent
    '&Partner'     PRESENT -> absent
    repeated msg on a path  YES -> none

    UNCHANGED, deliberately: DRAFT, 0 leads, no schedule, one seat 174892.

**Nothing has been sent and nobody has been added.** `LINKEDIN_ADD_LEAD` is
still not in `providerwrites.SUPPORTED`; the start verbs are still absent from
`heyreach.WRITE_ROUTES`.

### What cleared it

TASK-068. `plan` regenerated ONE note at a time, so a contact whose notes were
mutually repetitive could never escape - each candidate was compared against
the five stale notes still saying the same thing. Now a colliding set is
regenerated AS A SET, transactionally: build the whole replacement, gate it
together, commit only if every member passes, keep the originals on failure.

**Do not weaken `SUBJECT_VOCABULARY` or any repetition gate.** It was measured
and rejected: discounting the client's angle vocabulary clears the collisions
and passes four identical questions. See
`docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md`.

## 20. THE NEXT PRODUCTION DECISION IS NOT "ADD LEADS"

    pushable   3 of 15 contacts        (was 10 before the gates tightened)

The sequence write did not depend on that number - the graph carries merge
fields. **A lead add does.** Three is a thin cohort and the other twelve are
blocked by unsupported claims or copy that still fails a gate. Raising it is
regeneration work, not a permission change.

And the product is still named in only 42% of `li4` notes and 29% of `em3`
bodies. TASK-065 is measuring it per SEQUENCE rather than per step, which is
the right question: does a person who receives the whole cadence learn what
Productive is?

**Order stands: sequence first, leads second, and leads only when the cohort
is worth sending to.**

## 21. WHAT MUST NOT BE REPEATED AFTER THE RESET

- **Do not re-run the HeyReach write to "make sure".** It is done and proven.
  Re-read it with `heyreach_readback.py --expect` if in doubt; that is free.
- **Do not widen any repetition gate**, `SUBJECT_VOCABULARY` included.
  Measured, rejected, and the reasoning is written down.
- **Do not conclude Qwen is unavailable from one quota error.** It was
  recorded as dead for six days and was Pro hours later.
- **Do not read a test verdict through a pipe.** A pipe reports the filter's
  status; `EXIT=0` from `tail` hid a real failure once today.
- **Do not trust a Qwen result block's "tests pass"** without running the
  NEIGHBOURS of what changed. Four of today's results needed correction and
  three of those passed their own new tests.
- **Do not treat `opened: 0` as a signal** on a campaign with
  `open_tracking: False`.
- **Do not count an UNKNOWN reply as negative.** 73.6% of LinkedIn replies
  are unreadable; that is a measurement gap, not a finding about prospects.

## 22. QWEN STATE AT HANDOFF

Eight worktrees. **Every branch is PUSHED - nothing is stranded on the
laptop.** Unintegrated work sits in each branch's `docs/qwen-tasks/REVIEW/`.

    worker  worktree                  branch          awaiting review
    1       resonate-qwen-worker      qwen-worker     TASK-054 + its REWORK
    2       resonate-qwen-2           qwen-worker-2   TASK-060, 061, 068 (all
                                                      three already integrated)
    3       resonate-qwen-3           qwen-worker-3   TASK-058 (integrated),
                                                      TASK-069 four-verdict map
    4       resonate-qwen-4           qwen-worker-4   TASK-059 RUNNING
    5       resonate-qwen-5           qwen-worker-5   TASK-057 RUNNING
    6       resonate-qwen-6           qwen-worker-6   TASK-063, 064, 071
    7       resonate-qwen-7           qwen-worker-7   TASK-066, 067
    8       resonate-qwen-8           qwen-worker-8   TASK-065 RUNNING

**UNREVIEWED AND WORTH READING FIRST:** TASK-069 (does the EmailBison
step-level join exist - four verdicts), TASK-071 (API capability map),
TASK-067 (thread-context reply classification), TASK-064 (LinkedIn cadence
read), TASK-063 (five-email read).

    TODO   036, 037, 040, 044, 070
    REWORK 042 (name gate - breaks 17 tests), 054 (sampling)

### Dispatch mechanics - two mistakes already paid for

    C:\Users\Zvonimir\AppData\Local\qwen-code\bin\qwen.cmd
        --approval-mode yolo  "<prompt>"

`qwen` is NOT on PATH; use the absolute path. **Do NOT pass
`--max-tool-calls`** - a 400 cap killed two workers mid-task. Run each from
inside its own worktree. Credentials are present in all eight
(`scripts/sync_worker_env.py --write` re-syncs them; it prints names, never
values, and refuses any worktree where git does not ignore `config/.env`).

## 23. FIRST ACTIONS AFTER THE RESET, IN ORDER

**1. Confirm nothing regressed, cheaply:**

    py -3 scripts/heyreach_readback.py productive-linkedin-production-v1 --expect
    echo $?        # MUST be read without a pipe. Expect 0, 27/27 PASS.

**2. Review the five unreviewed Qwen results** listed in section 22, starting
with TASK-069 - what it concludes decides what TASK-070 may claim.

**3. Raise `pushable` from 3 of 15.** That is the gate on a lead cohort, and
it is regeneration work:

    py -3 -m src.generate --live --client productive
    py -3 scripts/write_heyreach_sequence.py productive-linkedin-production-v1

If the queue lock is stale - `work/queue.jsonl.lock` naming a dead pid -
remove it. That happened once today after a run was killed mid-write; the
lock guard correctly wrote nothing.

**4. Only then consider leads.** Enabling `LINKEDIN_ADD_LEAD` is a separate
operator decision and should not be taken at `pushable: 3`.

**5. In parallel, keep eight workers saturated.** The queue has five TODO and
two REWORK items, and TASK-070 depends on TASK-069's verdicts.
