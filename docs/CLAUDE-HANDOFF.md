# RESONATE OS HANDOFF

Rewritten 2026-09-13, later the same day than the previous version.
Everything here was read back from the repository or from a provider on that
date. Nothing in this file is inferred from a plan. Where it corrects the
previous handoff the correction is marked, because the previous numbers were
quoted and acted on.

## Repository

- branch: `master`
- HEAD: `9605da0` "A missing model is not a bad record"
- remote: `origin` https://github.com/KatoKhan8/resonate-group-automation.git
- remote HEAD: identical. Everything is pushed.
- worktree: clean apart from `work/`, which is gitignored by design.

Second worktree: `C:\Users\Zvonimir\Desktop\resonate-qwen-worker` on
`qwen-worker`, for the parallel worker. It carries `QWEN.md`, its standing
brief. It has NO `config/.env`, so it cannot reach a provider - that is
structural rather than a promise.

## Canonical goal

Resonate OS is the internal multi-client outbound engine for Resonate Group.
Current production client: Productive. Resonate admins operate it; clients
receive reporting.

---

## What is BLOCKED and needs the operator

These are the only things stopping the mission, and none of them is a code
defect.

1. **Live provider writes are refused by the session's permission layer.**
   `python -m src.bisonfactory <campaign> --live` and any script calling a
   write verb were denied by the auto-mode classifier. Provider READS work
   and were used throughout. Until a Bash permission rule allows the write
   path, no campaign can be staged, no sequence written, no lead attached.
   This is the single gate in front of everything under "Next actions".

2. **`sender_id` is null on all 285 sender rows**, which blocks per-human
   attribution (`assignment.py`). It does NOT block staging - corrected
   below.

---

## Corrections to the previous handoff

**The contact funnel is far healthier than recorded.** The previous handoff
said "104 of 113 qualified accounts have ZERO contacts" and reasoned from
"the 9 qualified accounts WITH contacts". Measured on the same estate:

    qualified (icp_pass*)                       113
    of those, WITH at least one contact          74      (not 9)
    contacts on qualified accounts               89
    of those, verified AND sendable              55
    accounts holding >=1 verified sendable       54
    of those, persona economic_buyer             50 contacts
                       champion                   5 contacts

The count that read zero was reading the top-level `contact["verified"]`
field, which is null on all 89. The authority is
`verification.is_sendable`, which recomputes from the evidence list, and it
says 55. Contact discovery is NOT the bottleneck. Drafting was.

**`sender_id` null does not block staging.** The previous handoff filed this
as a P0 against account-level execution, which is right, and it was being
read as blocking the campaign. `bisonfactory._ensure_senders` reads
`provider_account_id`, and 225 Productive EmailBison inboxes carry one, are
active, and 222 report health `ok`. What `sender_id` blocks is which HUMAN
owns a prospect, not which inbox sends.

**`{SUBJECT}` rendering is VERIFIED, not unproven.** `config/clients/
productive.yaml` carried a comment saying it was unproven and gated resuming
on it. Campaign 451's scheduled email reads back from `/scheduled-emails`
with `email_subject: "Profitability visible on Monday, not two weeks late"`
and a fully rendered body - the approved copy, not the merge field, before
any send. The comment is corrected.

---

## `wait_in_days`, measured

It is the wait **AFTER** the step that declares it, before the next one.

Read off the client's own live campaign 352 on 2026-09-13. 381 consecutive
scheduled-email pairs whose two steps declare DIFFERENT waits - the only
pairs that can tell the two readings apart, since equal waits discriminate
nothing:

    earlier wait 3, later wait 1   ->  delta 3 in 59 of 87 pairs
    earlier wait 3, later wait 4   ->  delta 3 in 115 of 168
    earlier wait 4, later wait 3   ->  delta 4 in 77 of 126

The mode is the earlier step's wait in all three groups. The one-to-two day
spread around it is the sending window and the weekend.

So `productive_li_heavy_v1`'s email days 1, 4, 8, 12, 21 declare waits
3, 4, 4, 9 and a fifth that has no successor and is checked against nothing.

---

## The five-step campaign

**Shipped as capability. NOT yet staged at the provider** - blocked item 1.

`config/clients/productive.yaml` now declares `email_sequence.steps`, keyed
by cadence step key (`em1`..`em5`). The keys are the whole mechanism:
`bisonfactory._sequence_steps` matches each declared delay to the cadence gap
it claims to reproduce and refuses a mismatch, so the delays stay DECLARED
(per `docs/CAMPAIGN-FACTORY.md`) and are nonetheless true.

A custom variable holds one value per lead, so the merge fields are numbered:
`{SUBJECT_3}` resolves to `subject_3`, carrying the words approved for `em3`
on that contact. Matched by step key, never by position - approvals are
fingerprinted per step key. `bison.LEAD_VARIABLES` declares six pairs;
`MAX_SEQUENCE_STEPS` is 6 and a longer cadence is refused rather than
silently truncated.

**The refusal that matters:** a contact who cannot fill every step of the
sequence is not staged, and the whole run stops rather than the one lead
being skipped. A dry run lists exactly who and which steps without raising.
Before this, a lead with no approved copy was staged with `""` for subject
and body: the campaign, sequence, schedule, sender and membership all read
back correct and the person received an empty email.

The single-step shape still works and is what campaign 451 carries.

## The production campaign row

Created, not staged.

    campaign_id   productive-email-liheavy-v1
    client        productive
    name          RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - BUYER - LIHEAVY-V1
    records       20 accounts (the pilot ceiling; `pilotcaps.CEILING.companies`)
    senders       EmailBison 2736 and 2737, both health ok, 15/day each
    daily_volume  email 20 (the pilot ceiling), linkedin 0
    window        Mon-Fri 09:00-17:00 Europe/Zagreb

**Why the name says ZAGREB-HOURS and not a geography.** EmailBison schedules
ONE window per campaign, so the window is the property the campaign actually
determines. Country is `unknown` on 39 of the 54 candidate accounts, so a
name claiming EU or US would be a claim the data does not support.

The cohort was filtered on `cadence.company_name` succeeding as well as on
ICP and verification: `automotiveonly-com` is qualified and has a verified
sendable contact and its only company name is its own hostname, which the
engine refuses to address a stranger by. That is the guard working.

Dry run on 2026-09-13 returns the five steps with waits 3/4/4/9/0 and 20
leads.

## Drafting

**This was the real bottleneck and it is now moving.**

`python -m src.generate --live` could never reach a model. `main` never
called `llm.from_env()`, so it ran with `NoModel`, and `NoModel` raised the
same `ModelError` a real failure raises, so `generate_record` HELD the
record - writing a configuration mistake into canonical state, once per
record, under a banner printing "GENERATED". Measured: one such run moved
`16kagency-com` from `verified` to `held` with no event. Fixed at all three
points (`9605da0`), and `NoModelConfigured` now exists so the two cases
cannot be confused again.

With that fixed, `16kagency-com` generated five real lint-passing drafts
against `openrouter/free`. A batch for the whole 20-account cohort was
started the same session.

Drafts are NOT approvals. `_approved_copy` requires `step["approval"]`, and
nothing in this session approved anything.

**Copy quality, observed and not fixed:** one generated body referred to the
prospect's own company in the third person ("highlights their commitment"),
and one contained a mojibake apostrophe. Both passed lint. Worth a pass
before anything is approved.

---

## EmailBison

PROVIDER TRUTH, re-read 2026-09-13:

- workspace bound to this credential: **10, "PRODUCTIVE"**
- **434, 441, 447, 449, 450 all return 404.** Deleted. Confirmed again today.
- **451 EXISTS, status `active`**, name `RESONATE - PRODUCTIVE CANARY - Hot
  Soup Group`, canonical row `productive-canary-email-2026-09-13`, one lead,
  one scheduled email for 2026-09-14 13:19Z, one step, `wait_in_days` 3.
  Do NOT mutate it. Re-staging pauses it.
- campaign 352 is the client's own: 44 sequence steps, 95,340 scheduled
  emails across 6,356 pages, 21,176 leads. Read-only, and the source of the
  `wait_in_days` measurement.

Provider quirks that still hold and still bite:

- `per_page` is ignored; every list route returns 15 rows. Count from
  `meta.total`. `_paged` refuses a walk over 40 pages rather than returning a
  page as an inventory - it did exactly that on 352 today.
- `POST /campaigns` discards every field except `name`.
- The sequence route APPENDS. No replace, no delete, no per-step route.
- `GET .../schedule` and `attach-sender-emails` answer 200 with
  `success: false`. The status code is not the verdict.
- `?email=` is not a filter.
- DELETE is asynchronous.
- `custom_variables` must be a LIST of name/value objects, declared first.
- Staging invalidates approval. Stage THEN approve.

## HeyReach

Read-only this session. Nothing was written. Two corrections.

- **599020** RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1, **DRAFT**, seat
  174892, `listId` **null** - not 933603, which the previous handoff recorded.

  **It is NOT an empty shell.** It carries a full branching sequence:
  connection request, messages, `VIEW_PROFILE` nodes, conditional `END`
  branches and an **`INMAIL`** node. Every message payload reads
  `NOT APPROVED COPY {NOT_APPROVED_COPY} - structural placeholder ... This
  campaign carries no approved copy and must not be started` - 32 occurrences
  of that marker across the tree. It is a deliberate proof of shape and it is
  safe: no list, no leads, no approved words, and `StartCampaign` is not a
  wired verb.

  Two things to know before touching it. The `INMAIL` node depends on a
  capability this system has NOT established - `cadencelibrary` holds any
  step naming `CAP_INMAIL` for exactly that reason, so the provider campaign
  contains a step the planner would refuse. And a sequence write APPENDS
  nowhere here but `set_sequence` replaces, so re-writing it is possible in a
  way EmailBison's is not.

  It now has a canonical row: `productive-linkedin-production-v1`, `draft`,
  no records, mapped to 599020. It had none, which is exactly how a second
  campaign gets built for the same purpose - and HeyReach has no campaign
  DELETE, so an orphan cannot be removed, only owned.
- **594061** the earlier canary, paused.
- 48 other campaigns belong to the client. Do not touch them.
- `WRITE_ROUTES` is seven routes. Resume, StartCampaign and every
  `AddLeadsToCampaign` spelling are deliberately absent and asserted absent.
- Open Profile detection and InMail send are NOT established capabilities.
  Steps naming them are HELD, never silently skipped.

## Live execution

- confirmed touches: 0
- scheduled actions: 1 (EmailBison 451, Monday 2026-09-14 13:19Z)
- sent: 0. replies: 0. ambiguous: 0.
- live rung: ONE authorized canary. `UNSTOPPABLE_CHANNEL_CAP = 1`.
- killswitch: armed and untripped.

## Cadence

`productive_li_heavy_v1` in `src/cadencelibrary.py`, selected by the `cadence:`
key. 5 email, 6 LinkedIn, 11 touches, 21 days.

    day 1   li1 connect  + em1        day 12  em4
    day 3   li2 message               day 15  li5
    day 4   em2                       day 18  li6
    day 6   li3 message               day 21  em5
    day 8   em3
    day 10  li4

Event-driven, never calendar-driven. Time passing is not a decline.

---

## Parallel worker

`docs/qwen-tasks/` holds the queue: `TODO/`, `RUNNING/`, `DONE/`, and a
README describing the lifecycle. Six tasks are written, each stating its
FILES FORBIDDEN, which matters more than its goal.

    TASK-001  observable full-suite verdict        RUNNING
    TASK-002  HeyReach capability contract         TODO
    TASK-003  linkedinstate red-team               TODO
    TASK-004  30k scale measurement                TODO
    TASK-005  crash/restart idempotency seams      TODO
    TASK-006  multi-client isolation               TODO

The `qwen` CLI is at `C:\Users\Zvonimir\AppData\Local\qwen-code\bin\qwen.cmd`
and is NOT on PATH. Headless needs `-y`; `--approval-mode auto` cannot run
non-interactively and says so. `--max-tool-calls` is a HARD per-turn cap and
halted the first run; `-c` resumes.

Nothing Qwen produces has been reviewed or integrated yet.

---

## Test verdict

`test_generate`, `test_invariants`, `test_a_model_is_configured_or_it_is_not`,
`test_failure_injection`, `test_the_opener_asserts_nothing`,
`test_nothing_talks_back_to_a_prospect`, `test_no_model_is_not_a_bad_record`:
**206 tests, OK, exit 0**, read from unittest rather than from a pipe.

The factory group - `test_a_five_step_campaign_sends_five_different_emails`,
`test_staging_a_campaign_twice_builds_one`,
`test_two_campaigns_do_not_collide_at_the_provider`,
`test_no_activation_without_an_exact_match`: **130 tests, OK, exit 0.**

The WHOLE suite still has no observed verdict. That is TASK-001.

Two pre-existing failures were found and fixed this session, both stale
constants in test form rather than product defects. They had been failing on
a clean tree and no run in the previous session looked.

---

## P0

1. Authorize the live provider write path. Everything below waits on it.
2. Stage `productive-email-liheavy-v1` and read it back: five steps, waits
   3/4/4/9, two senders, the Zagreb window, the 20-lead membership.
3. Approve the generated copy. Drafts exist; approvals do not, and
   `_approved_copy` refuses without them - correctly.

## P1

1. The full suite has never been observed to a verdict (TASK-001, running).
2. HeyReach 599020 now has a canonical row, but its sequence carries an
   `INMAIL` node whose capability is unproven and which the planner would
   hold. Decide whether the shape is right before any copy is written into
   it; `set_sequence` replaces, so it can be rewritten.
3. Open Profile and InMail capability unmeasured (TASK-002).
4. Four cost estimators multiply by `cadence.GENERATED_KEYS`, which still
   reads two generated emails while Productive generates five. Every LLM
   estimate for this client is out by 2.5x, in the direction that matters.
   See `PRODUCT-GAPS.md`.
5. Generated copy quality: third-person references to the prospect's own
   company, and at least one mojibake character. Both passed lint.
6. `sender_id` null on all sender rows blocks per-human attribution.

## Next single best action

Authorize the live write path, then stage `productive-email-liheavy-v1` and
read it back. The capability, the configuration, the cohort, the senders and
the schedule are all in place and verified offline; the only thing between
this and a production campaign visible in the EmailBison UI is permission to
make the call.
