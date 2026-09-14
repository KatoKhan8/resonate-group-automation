# Context reset checkpoint B, 2026-09-14

Written immediately before a `/clear`. Everything here was measured today
against the repository or a provider. Supersedes
`docs/CONTEXT-RESET-2026-09-14.md` where they disagree.

Read with: `docs/CAMPAIGN-ACCEPTANCE-2026-09-14.md` (the operator's twelve P0
points and what provider truth says about each),
`docs/HEYREACH-VARIABLES.md`, `docs/HEYREACH-PERSONALISATION-2026-09-14.md`,
`docs/ESTATE-LEARNING-2026-09-14.md`, `docs/TRIAGE-2026-09-14.md`.

---

## GIT

    master HEAD      7c917ef
    origin/master    7c917ef        identical
    worktree         clean

    qwen-worker      e04d873   running TASK-033 (ten-test cluster)
    qwen-worker-2    d3c9369   idle
    qwen-worker-3    1e9197d   TASK-043 COMPLETE, NOT INTEGRATED - see below
    qwen-worker-4    e6ee2af   TASK-039 COMPLETE, NOT INTEGRATED - see below

### Completed Qwen work that is NOT in master, and why

**TASK-043 (semantic duplicate detection), `qwen-worker-3`.** Adds
`quality.campaign_repetition` and wires it into `heyreachfactory`. The
function and its own tests pass. The WIRING breaks three existing tests in
`tests/test_the_sequence_belongs_to_nobody.py`. Backed out rather than
debugged under context pressure. **Re-attempt from that branch; do not start
over.**

**TASK-039 (evidence-pack audit), `qwen-worker-4`.** Completed, not reviewed.
No conflict markers.

Neither is lost. Both branches are pushed.

## TESTS, MEASURED

    py -3 scripts/run_suite.py --timeout 2700
    failures 15   wall 1831.9s   timed_out False   exit_code 1

15 against 24 earlier today and 29 at the first context reset. Two of the 15
were fixed after that run and are not re-measured.

`test_fixture_hygiene` is GREEN (11 tests) - that privacy cluster is closed.

Known remaining clusters, all PRE-EXISTING, none introduced today:
`test_e2e` (~8) and `test_preproduction` (~4) - TASK-033 is on them, and
several are stale seven-step-cadence expectations rather than defects.

## EMAILBISON - REAL STATE

    481  paused   23 leads = 9 sending_paused + 14 deliberately stopped
         5 SEQUENCE STEPS, provider-visible, ids 4729-4733, order 1-5,
         waits 3/4/4/9/1, every one active:True
         subjects {SUBJECT_1}..{SUBJECT_5}, bodies {BODY_1}..{BODY_5}
         emails_sent 0, replied 0, scheduled 0

    451  active   1 lead, 1 step
         1 scheduled email, status `scheduled`,
         2026-09-14T16:24:00Z, sent_at None, opens 0, replies 0
         NOT MOVED all day. This is the only scheduled live action anywhere.

### THE 2-STEP REPORT IS NOT REPRODUCIBLE

The operator reported campaign 481 showing only STEP 1 and STEP 2. **The API
returns five, all active, consecutive.** The whole workspace holds exactly two
Resonate campaigns - 481 with five steps and 451 with one. There is no
two-step Productive campaign.

Most likely the UI: the sequence is a TEMPLATE of merge fields, so the editor
shows `{SUBJECT_1}` and no words, because the copy lives per lead in custom
variables. A view that collapses, paginates, or only renders steps it
considers complete would present as fewer steps than exist.

**Do not rebuild on the assumption steps 3-5 are missing.** Confirm which
campaign and which screen first. If the UI genuinely shows two, that is a
finding about the UI or about how merge-field steps are stored, not about the
generator.

PROVEN: five steps exist at the provider, read back.
ASSUMED: nothing about what the UI displays.

## HEYREACH - REAL STATE

    599020  DRAFT, seat 174892, list 933603 bound and holding 0 items
            24 nodes, 4 distinct message texts
            'jacob' IS STILL IN THE GRAPH.  merge fields are NOT.

**THIS IS THE OPEN P0.** The graph carries ONE contact's personalised words -
"hi jacob... at &Partner?" - for a canonical row naming fourteen records. The
fix is committed (`4f93f2f`, `3192153`) and the corrected sequence has NOT
been written, because every live provider write is refused by the Claude Code
permission classifier. Three command shapes were tried, then stopped.

**No lead may be added until the sequence is replaced.** Order matters:
sequence first, leads second.

PROVEN: the full gate chain - killswitch, suppression, collision, tenant,
unsupported-sequence, per-contact `executionguard.authorize` - passes in dry
run for 8 real contacts against real provider state, refused 0, transport not
reached. Two contacts are held by account collision (a campaign at each
account ended early) so the real cohort is EIGHT, not fifteen.

ASSUMED: nothing about `AddLeadsToCampaignV2`'s response shape. It has never
been called. The verdict comes from `readback_membership` either way.

## COPY STATE - TODAY'S CENTRAL FINDING

**THE GENERATED LINKEDIN COPY FAILS NARRATIVE PROGRESSION.** Read with
`python scripts/render_preview.py productive-linkedin-production-v1`, which
renders what a person actually receives. One lead's already-connected path:

    connected_1  "how do you currently ensure profitability is visible in
                  your projects?"
    connected_2  "without clear visibility on profitability, projects can
                  easily go off track. how are you currently managing this?"
    connected_3  "i'd love to share how teams like yours have improved their
                  project visibility and profitability..."
    connected_4  "just checking in to see if you had any thoughts on how we
                  can help enhance profitability for your projects."

Four messages, four askings of the same question. No introduction. The word
"Productive" appears nowhere. Every one passes every gate individually.

**THE FALLBACKS ARE BETTER THAN THE GENERATED COPY**, and that is the clue:

    connection_note  who I am, why connect
    connected_1      the question
    connected_2      what most agencies find
    connected_3      what Productive is and what it joins up
    connected_4      an easy out, and who else owns this

WHO -> PROBLEM -> PRODUCT -> CLOSE. Eight lines written by hand into
`config/clients/productive.yaml` have the progression the generated sequence
does not. `generate.LINKEDIN_LADDER` already gives each rung a different job
and `step.purpose` reaches the prompt - verified. **So the ladder is not the
problem; the model is not following it.** That is where the copy fix belongs,
not in more variants.

The EMAIL copy is better but has the same disease structurally. Four of five
staged emails open `[company self-description] -> [why I am writing, by role]
-> [ask]`. Different words, one formula, and "I am reaching out to you as COO
and Co-Founder" appears in two of them, reading as if the SENDER holds the
title. `quality.repetition_across_rungs` passed all of it because it counts
shared distinctive WORDS and the formula varies its words.

### Required, and preserved as rules

    WHO / RELEVANCE -> PROBLEM / OBSERVATION -> PRODUCTIVE / VALUE
    -> DIFFERENT ANGLE -> CLOSE / CTA

- no naked contextless discovery question; a question is earned by context;
- introduce Productive naturally and early enough that the recipient knows
  what it is;
- never invent pain - distinguish OBSERVED / INFERRED / HYPOTHESIS / UNKNOWN;
- personalisation comes from evidence or falls back to generic, never to
  invented research;
- >= 5 materially distinct variants per meaningful step, differing in
  approach and not in synonyms;
- first name, company, title are VARIABLES, never literals in campaign copy;
- email and LinkedIn coordinate rather than duplicate.

### Cadence

    EMAIL     5 touches over ~3 weeks  (`productive_li_heavy_v1`)
    LINKEDIN  ~6 activities, branching on connection state, open profile,
              accepted / not accepted, InMail availability, reply state

`PRODUCTIVE_EMAIL_EIGHT_V1` also exists now (8 steps, days 1/3/6/8/11/14/17/20)
because the estate says 8-step sequences reply at 8.49% against every other
shape. It is a comparable variant, not a replacement.

## HEYREACH VARIABLE SYNTAX - SETTLED

Measured across 81 campaign sequences: **3,295 single-brace occurrences, ZERO
double-brace.** `{{first_name}}` would reach a prospect as literal text.

    {FIRST_NAME} 1197  {COMPANY} 922  {MY_FIRST_NAME} 598
    {POSITION} 228     {INDUSTRY} 228 {LOCATION} 108   {Icebreaker} 6

`POSITION` and `INDUSTRY` are provider-filled and we use neither.
`MY_FIRST_NAME` is the SENDER and we never use it. `Icebreaker` is the only
custom field in the estate; our design sends EIGHT per lead, which is
unproven at that shape.

## OPEN P0 - none of these is complete, and a task existing is not completion

1. **The provider still holds the defective HeyReach sequence.** Blocked on a
   permission, not on code. Nothing may be pushed into 599020 until it is
   replaced and read back.
2. **Generated copy has no narrative progression.** The ladder is right and
   the model is not following it. Fix the generation, not the variant count.
3. **Confirm the EmailBison 2-vs-5 step report.** API says five. Establish
   what the UI shows before rebuilding anything.
4. **Provider-readback assertion**: a five-email cadence must be proved to
   become FIVE provider-visible steps - a different assertion from "the
   readback matched what we sent".
5. **Render and inspect the complete 5-email sequence before promotion.**
   `render_preview.py` covers LinkedIn; the email side needs the same.
6. **Cross-channel repetition detection** - TASK-043, complete on
   `qwen-worker-3`, wiring unsound.
7. **No scale-up while provider-visible structure is known defective.**

## OPEN P1

- `sender_id` null on all 285 sender rows - no prospect has a human owner
  (TASK-036, queued).
- Two quadratics and a per-lead transaction make 30k records unusable
  (TASK-041, queued, measured in `docs/SCALE-MEASUREMENT-30K.md`).
- LinkedIn reply classification is 64% unreadable; email 46.5%.

## WHAT IS BLOCKED, AND IT IS NOT THE REPOSITORY

Refused by the Claude Code permission classifier all session:

    py -3 -m src.generate --live ...          no copy can be generated
    heyreachfactory.stage(live=True)          no provider write can happen

The cost of the first is exact: 45 accounts qualify with a verified contact
and a usable company name, 23 contacts have five approved email steps, and 9
survive the quality gates. The gap is entirely generation and regeneration.

`qwen.cmd` was refused early and now works; it needed no rule in the end.

## NEXT SESSION BOOT ORDER

Run these, in order, before deciding anything:

    1  cat docs/CONTEXT-RESET-2026-09-14-B.md        (this file)
    2  cat docs/CAMPAIGN-ACCEPTANCE-2026-09-14.md    (the operator's P0s vs
                                                      provider truth)
    3  git log --oneline -15 && git status
    4  ls docs/qwen-tasks/TODO docs/qwen-tasks/DONE | head -40
    5  py -3 scripts/render_preview.py productive-linkedin-production-v1
       -> this is what a person receives. Read it before believing any gate.
    6  py -3 scripts/campaign_ready_funnel.py
       -> 9 email-ready, 9 LinkedIn-ready, 8 after collision
    7  provider truth, read-only:
       bison.campaign(481) / bison.sequence_steps(481)  -> expect 5 steps
       bison.scheduled_emails(451)                      -> the 16:24Z send
       heyreach.campaign_sequence(599020)               -> expect 'jacob'
                                                           STILL PRESENT

### What must NOT happen

- Do not add any lead to HeyReach 599020 before the sequence is replaced.
- Do not scale campaign 481 beyond its 9 leads while copy progression is
  unfixed.
- Do not mark an OPEN P0 complete because a task file or a test exists.
  Complete means the BEHAVIOUR is proven, at the provider.
- Do not weaken a gate to raise a readiness number.

### The route from here to a large live Productive test

    1  unblock the two refused commands (permission rules)
    2  write the corrected merge-field sequence to 599020, read it back,
       confirm 'jacob' is gone and the merge fields are present
    3  fix copy progression - the ladder's brief is not reaching the model -
       then REGENERATE, and read `render_preview` before believing it
    4  confirm the EmailBison step-count question
    5  bounded canary: 451 sends at 16:24Z today and is the first real send
       this system will have made. Record sent_at, status, opens, replies.
       A watcher was sampling it every 3 minutes into
       `%TEMP%/451_watch.jsonl`; that process does not survive the reset.
    6  promote on evidence: 1 -> 5 -> 10 -> 25, each rung requiring zero
       wrong-recipient, zero duplicate, zero suppression violation, zero
       fabricated claim, and correct provider membership read back
