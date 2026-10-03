# LANE 3 - classifying the 21 unmatched phase-2 scenarios

## Log

1. Worktree `wt-scen3` created from master 2bf7b8a5 on branch `task-scen3-classify`.
2. REPORT.md created empty before any read.
3. Read `docs/phase2-scenarios/README.md` and `CATALOGUE.md` (30 rows) from the
   lane-3 worktree of `task-phase2-simclock`.
4. Read `C:\Users\Zvonimir\Desktop\resonate-ops\briefs\phase2-brief.md`.
5. **The "21 unmatched" artefact FOUND.** It is not a separate file: it is the
   phase-2 run committed on `task-phase2-simclock` at `787fa450`, under
   `docs/phase2-run-2026-10-03/`. `RUN-LOG.txt` ends
   `firings 90, matched 69, unmatched 21, late 0`, and `FINAL-TABLE.md` carries
   the per-scenario table and two sub-tables, "Every unmatched field" and
   "Every key no authority could answer".

## IMPORTANT - what "the 21" actually is

The handoff sentence "the 21 unmatched phase-2 scenarios" is loose. The run
fired **30 scenarios x 3 firings = 90**. 69 firings matched, **21 firings did
not**. Those 21 firings are **7 distinct scenarios**, each failing on all three
of its firings:

    S09, S13, S15, S16, S17, S24, S29   (7 x 3 = 21)

They decompose into **16 distinct (scenario, field) mismatches**. All three
firings of a scenario failed on exactly the same fields, so the verdict is a
property of the scenario, not of the firing. This report therefore classifies
at the field level (16 rows), rolls that up to the scenario (7 verdicts), and
restates it per firing so that literally all 21 carry a verdict.

## Method

Everything judged on master 2bf7b8a5 by EXECUTION, not by reading the run's
report. The classifier reproduced the run's `actual` column EXACTLY for all
six classifiable rows, which is what licenses judging a simclock-branch run on
master; the two branches differ in src/ only in copystages, generate, lint,
providerwrites, skills, store.

Four reproduction scripts, in this session's scratchpad: repro1.py (classifier
+ accountpolicy), repro5.py (the channels/eligibility split, with an
unsubscribed control), repro7.py (OUTCOME_POLICY, and that `unknown` has no
entry), repro8.py (the discriminators that separate defect from
wrong-scenario).

ONE TRAP HIT AND RECORDED: the first script was written to /tmp, which is the
%TEMP% root, where a stray inspect.py shadows the stdlib. Importing
src.channels from there EXECUTED that file, which called
`bison.fetch_replies` - a LIVE provider read, stopped only by BISON_KEY being
absent from config/.env. Scripts moved into the session scratchpad and re-run
clean. This is the known windows-temp-inspect-shadows-stdlib hazard and it is
worse than recorded: it does not merely fail, it attempts a provider call.

## The three findings everything rests on

- F1. `channels.*_verdict` has no reason constant for a reply or a stop. Its
  whole vocabulary is 16 constants and names only `unsubscribed`, `bounced`,
  `suppressed`, `operator_excluded`, addresses, MX, verification and profile
  shape. `eligibility.must_not_contact` is the stop authority and answers
  correctly (`blocked:replied`, `blocked:contact_stopped`).
- F2. `unknown` is the one OUTCOME with no OUTCOME_POLICY entry, so the six
  categories mapping to it have no consequence at all. TASK-1004 (REVIEW, not
  on master) fixes the reachability half for interested/meeting_intent/question.
- F3. The operator's dated definition of a positive exists, in
  resonate-ops/copy-review/POSITIVE-SAMPLE-2026-10-03.md, and names "a request
  to talk" and "a question about the offer" - and records the second limb as
  unsettled (10 broad vs 7 narrow).

## Verdicts

By field (16):   pravi defekt 7, krivo napisan scenarij 6, nema pravila 3.
By firing (21):  pravi defekt 6, krivo napisan scenarij 12, nema pravila 3.
By scenario (7): defekt S09 S13; krivi scenarij S15 S17 S24 S29; nema pravila S16.

Deliverable: docs/PHASE2-UNMATCHED-CLASSIFICATION-2026-10-03.md, which holds
the 16-row table, the 7-row roll-up, the 21-firing table and the separate
"Odluke za operatera" list.

## Opened

- docs/qwen-tasks/TODO/TASK-1010-a-request-for-call-times-is-not-a-positive.md
- docs/qwen-tasks/TODO/TASK-1011-wrong-person-is-filed-as-not-a-fit.md
  (part 2 carries the channels/eligibility side-finding)

Numbers chosen by inspection - 1007 is the highest in use across every ref -
and NOT by the task allocator, which is itself an open operator decision.

TASK-1004 covers two of the seven defect fields and is already written and at
REVIEW. No duplicate was opened.

## Operator list

Three questions, in the deliverable under "Odluke za operatera": Q1 the
breadth of the "question about the offer" limb; Q2 the class of a past-failure
objection; Q3 whether an EA redirect pauses the cadence.

## Constraints honoured

Own worktree, never master, no commit to master. No `git stash`. No
tests.offline / unittest discover / scripts/run_suite.py - pid 149644 holds
the suite; only direct module imports were needed. No provider write, no Slack
post, no write to production work/. No change to src/ - both defects are
described with a fix and left for their tasks, and no rule was widened to make
a scenario pass.
