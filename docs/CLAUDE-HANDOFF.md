# RESONATE OS HANDOFF

Rewritten 2026-09-13, later the same day than the previous version.
Everything here was read back from the repository or from a provider on that
date. Nothing in this file is inferred from a plan. Where it corrects the
previous handoff the correction is marked, because the previous numbers were
quoted and acted on.

## Where this stood at the end of the overnight run, 2026-09-14

    GIT        master 8e36bc6, everything pushed, worktrees clean
               53 commits overnight
               qwen-worker f505f46, pushed, nothing ahead

    QWEN       12 tasks complete and integrated, 5 queued, 0 running
               every commit reviewed before merge; four corrected on review

    PRODUCTIVE 300 domains, 113 icp_pass*, 55 verified sendable contacts
               149 email drafts, 194 LinkedIn notes, 238 approved steps
               15 accounts collision-clean, 9 in the staged cohort

    EMAILBISON 481  paused   9 sending_paused + 14 stopped, 5 steps, 0 scheduled
               451  active   1 scheduled 2026-09-14T16:24Z, not yet sent

    HEYREACH   599020  DRAFT  24 nodes, real approved copy, no list, no leads

    LIVE       confirmed touches 0. sent 0. replies 0.
               wrong recipient 0, wrong tenant 0, suppression violations 0
               duplicates 0 - nine were caught and stopped before any send

### The four numbers that changed the picture

**15, not 53.** The client's own campaigns already cover 38 of the 53
qualified accounts with a verified contact. Any "qualified accounts" figure
that does not subtract the client's estate describes inventory nobody may
work.

**Nine people the client was already emailing got into our campaign**, one of
them `in_sequence` right now. The provider refused five of nineteen; nothing
in this system objected. All fourteen are stopped and the gate that should
have caught them exists now.

**60 of 65 staged email steps repeated another step in their own sequence.**
Four regeneration passes with the gate enforcing took that to 20, and 9 of 13
records to fully clean.

**26 stored drafts asserted things the record does not support**, including a
subject reading "Final note on our previous discussions" to somebody this
system has never written to.

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

1. ~~Live provider writes refused by the permission layer.~~ **CLEARED.**
   Campaign 481 was created, capped, scheduled, given two senders and a
   five-step sequence. See "The five-step campaign".

2. **THE MODEL ACCOUNT HAS NO CREDITS. This blocks every remaining live
   deliverable on EmailBison.** Read from OpenRouter on 2026-09-13:

       GET /credits  ->  {"total_credits": 0, "total_usage": 0}
       GET /key      ->  {"is_free_tier": true, "limit": null}
       generation    ->  429 "Rate limit exceeded: free-models-per-day.
                         Add 10 credits to unlock 1000 free model requests
                         per day"   (X-RateLimit-Limit: 50)

   Fifty free requests a day, spent. A five-step draft costs five calls per
   contact plus persona-angle calls, so the twenty-account cohort needs
   roughly 120 and got 10.

   **Nothing in code fixes this.** No approved copy means no leads: the
   sequence is a template of `{SUBJECT_1}`..`{SUBJECT_5}` merge fields and a
   lead without the words sends five empty emails. `_ensure_leads` refuses,
   by name, and that refusal is correct.

   Ten dollars of credit unblocks it. Then:
   `py -3 -m src.generate --live --client productive --id ...` for the
   cohort, approve, and `py -3 -m src.bisonfactory
   productive-email-liheavy-v1 --live`.

   Two records already carry five drafts each. Neither can be staged: three
   of those ten drafts fail the typography rule added today, and a failing
   draft must be REGENERATED rather than patched - which needs the model.

3. **NO ROUTE CAN PUT A PERSON INTO A HEYREACH CAMPAIGN.** `WRITE_ROUTES` is
   seven routes and not one of them adds a lead:

       /campaign/Create               /campaign/UpdateSequence
       /campaign/Pause                /campaign/StopLeadInCampaign
       /list/CreateEmptyList          /campaign/AddLinkedInAccountsToCampaign
                                      /campaign/RemoveLinkedInAccountsFromCampaign

   Every `AddLeadsToCampaign` spelling is deliberately absent AND asserted
   absent by the seal tests, along with `Resume` and `StartCampaign`. This is
   a product decision on the record, not an oversight: a campaign can be
   built and left in DRAFT, it cannot be started, and no person can be put
   into one.

   So a HeyReach campaign containing real Productive leads is IMPOSSIBLE with
   the system as built, whatever the copy situation. Reaching it means
   deliberately crossing a safety boundary somebody drew on purpose. That is
   an operator decision. TASK-009 builds and tests the mechanism behind the
   same gates EmailBison's `add_lead` sits behind; it does not cross it.

4. **`sender_id` is null on all 285 sender rows**, which blocks per-human
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

## The model in use, and why

`config/.env` is gitignored, so this is the only durable record of it.

    LLM_MODEL = openai/gpt-4o-mini
              (was: openrouter/free, then qwen/qwen3-235b-a22b-2507)

Changed late on 2026-09-13 for two reasons, measured rather than assumed.

**Throughput.** `openrouter/free` routes to free models that queue. One
twenty-record cohort needs roughly 240 model calls once LinkedIn notes are
generated, and the free router was taking long enough that a cohort was an
overnight job on its own. The Qwen model answered a round trip in **1.8
seconds**, which turns the same cohort into minutes.

**Policy.** The operator's routing order is deterministic code, then Qwen,
then OpenRouter as escalation. A Qwen model reached through OpenRouter is not
the same thing as the local Qwen CLI that TASK-012 wires up - it is still a
paid call - but it is the right default for semantic work today and it
honours the order.

**Cost.** $0.0875 per million prompt tokens and $0.35 per million completion.
The whole twenty-record cohort is about eight cents against a $50 balance.
That is why no cap was imposed on it: the runaway risk here is a retry loop,
not the unit price.

**The Qwen model was tried first and measured out.** The policy says
Qwen-first, and `qwen/qwen3-235b-a22b-2507` answered a probe in 1.8s, so it
went in. Over one twenty-record cohort it then failed hard:

    records held by an upstream model failure    12 of 20
    batches completing cleanly                    3 of 5
    error                                        HTTP 400, `backend_error`,
                                                 "Backend request failed"

`openai/gpt-4o-mini` on the same account, same moment: **6 of 6 clean at
1.49s per call**. So the switch is on measured reliability rather than on
preference, and it is exactly the evidence the routing policy asks for -
"QWEN EARNS DEFAULT THROUGH QUALITY", and on this endpoint tonight it did
not. That says nothing about the local Qwen CLI in TASK-012, which is a
different thing entirely and is still the right default to aim at.

Those 12 records were released once the classifier was fixed. They had
nothing wrong with them.

The free tier is NOT the fallback to return to. It is capped at 50 requests a
day and that cap is what blocked this pipeline for most of the evening.

## Copy quality: what was wrong, what fixed it, where it stands

Four separate defects, found in this order, each hiding the next.

**1. `claims.check` ran only at send time.** `generate.draft` called
`lint.check` and nothing else, so a draft asserting something the record does
not support was generated, stored, approved and carried to EmailBison as a
per-lead variable. Lead 203708 carried the subject *"Final note on our
previous discussions"* for a contact this system has never written to.

**2. And it would have passed anyway.** The RELATIONSHIP patterns listed
those nouns singular, and `` after "discussion" will not match inside
"discussions". *"our previous discussion"* was refused; *"our previous
discussions"* sailed through. One letter.

**3. Every draft was written blind to its siblings.** `already_sent` reads
the durable event log, `CONFIRMING_EVENTS` requires a confirmed touch, and
nothing has been sent - so it is EMPTY when writing em1, em3 and em5 alike.
Three consecutive emails to 28 ROW opened with the same sentence. This was
read as a model weakness and was not: the ladder gives each rung a different
job and `step.purpose` reaches the prompt correctly, both verified. Any model
given five briefs and no sight of its own earlier answers repeats itself.

**4. The quality gate counted the company's own name as repetition.** Every
message in a sequence to one company names that company. `acqcom-com` showed
two colliding pairs with "acqcom", "digital" and "marketing" counted and ZERO
with them discounted, on copy that was fine.

### The three gates are now symmetrical

    lint     do the words break a rule
    claims   do they assert something untrue
    quality  do they say anything the other steps have not

Each refuses at the point of STORING, each re-plans a stored draft that fails
it, and each explains itself to the model in a sentence rather than a code.
The last part matters: the retry used to feed back `filler_phrase`, and a
model told `filler_phrase` three times has been told nothing three times.

### The model comparison, measured

    openai/gpt-4o-mini    5 of 65 steps clean.   em5 failed six straight attempts
    openai/gpt-4.1-mini   5 of 5 on first test.  em5 produced first time

`LLM_MODEL` is now `openai/gpt-4.1-mini`. `qwen/qwen3-235b-a22b-2507` was
tried first per the routing policy and held 12 of 20 records on upstream 400s.

### Where it stands

Repeated regeneration converges because the gate refuses at store time and
the reason is fed back:

    pass 0   60 of 65 steps failing
    pass 1   40 of 65
    pass 2   30 of 65,  7 of 13 records fully clean

A record is stageable only when all five steps are clean AND approved.

## Why campaign 481 is not activated, and what would activate it

It is staged, verified and PAUSED. Nothing has been sent from it and nothing
is scheduled on it.

Three reasons, and the first is the one that decides it.

**`EMAIL_ACTIVATE` is not in `providerwrites.SUPPORTED`.** The verb exists
and is well guarded - `bison.resume_campaign` takes an `expect_leads` count
and refuses if the provider disagrees, polls `queued` out rather than
reporting it as started, and classifies `failed` rather than defaulting it.
It is deliberately not enabled. The operator's authorisation tonight was
specific: HeyReach `AddLeadsToCampaign`, for verified Productive leads, after
review. It did not extend to starting an email campaign.

**There is no completed send anywhere in this system.** Confirmed touches
are zero. Promoting fifteen people onto a five-step sequence would make the
first real send of this engine a batch of fifteen, which is not rung one of
the ladder the operator described.

**The canary will produce that evidence today without anybody doing
anything.** Campaign 451 is `active` with one scheduled email at
`2026-09-14T16:24Z`, carrying fully rendered approved copy. It sends on its
own.

WHAT WOULD ACTIVATE IT, stated so the decision is one line rather than an
investigation:

    src/providerwrites.py   add EMAIL_ACTIVATE to SUPPORTED
    then                    bison.resume_campaign(481, expect_leads=15)

`expect_leads` is the containment and it must be passed: a resumed campaign
sends to EVERY lead it holds, and 481 holds fourteen older leads of which
nine are deliberately `stopped`. Passing the wrong count is how a campaign
meant for fifteen reaches twenty-nine.

A smaller first rung is available without any code change:
`bison.set_limits(481, name, emails_per_day=1)` paces the campaign to one
person a day, so 1 -> 5 -> 10 happens by the clock rather than by a decision
each time.

## The real campaign-ready inventory is 15 accounts, not 53

Measured 2026-09-14 against the client's live EmailBison estate, one
paginated search per domain, using `collision.check_account` and
`collision.account_policy` - the same functions `executionguard` asks at send
time.

    qualified, verified-sendable contact, usable company name    53
      CLEAN      collision ALLOW                                 15   (15 contacts)
      BLOCKED    hold                                            16
                 stop                                            22
      ESTATE UNREADABLE                                           0

**The client is already working 38 of the 53.** Reasons, in their own words:
"somebody at this account is mid-sequence right now"; "a campaign at this
account ended early (stopped) and the status does not say whether we stopped
it, they unsubscribed, or the provider stopped it on a reply"; "an address at
this account bounced; the data is suspect"; "1 person at this account have
already replied or been marked".

This reframes the whole funnel. The bottleneck was never ICP, contact
discovery or drafting - all three now produce more than the estate can
absorb. It is that Productive's own outbound already covers most of the
accounts this engine qualifies. Any future "qualified accounts" figure that
does not subtract the client's estate is describing inventory nobody may
work.

It is ACCOUNT-level, not address-level, because `ACCOUNT-OUTREACH.md` makes
the account the unit of outreach: a fresh contact at an account somebody is
mid-sequence with is still a second voice at the same company.

The clean fifteen, at the time of measurement:

    28row-com  acqcom-com  adcuratio-com  agency59-ca  anewagencyworld-com
    csquaredsocial-com  ethoscreate-com  mischacommunications-com
    mypersonalestatesale-com  ogpartner-dk  portsidemarketing-com
    roaringmedia-co  savagebrands-com  semcasting-com  viralityllc-com

## Two generation runs must not overlap

`generate.run` loads the whole estate, works, and writes it back. A second
run started while the first is still working holds a snapshot from before the
first one's write, and `store.refuse_history_loss` correctly kills it:

    HistoryLost: this write would forget what happened or lift a stop nobody
    lifted: anewagencyworld-com: 3 event(s) dropped. Reload and re-apply
    rather than writing a stale snapshot back over it.

That is the guard working - nothing was corrupted and the stale run simply
lost its own work. But it means generation does NOT parallelise by running
several processes, and the batching workaround must be strictly sequential.
It also means a batch script and an ad-hoc top-up run cannot overlap, which
is how this was found.

TASK-011's per-record persistence makes the window much smaller. It does not
make two concurrent runs safe.

## Checkpoint, late 2026-09-13

Things learned the expensive way tonight, recorded so nobody relearns them.

**A paid generation run died having written nothing.** `generate.run` saves
ONCE at the end, so roughly fifty minutes of OpenRouter calls across eighteen
records were lost when the process went away - no log, no exit code, no
drafts. TASK-011 fixes it properly. The operational workaround until then is
`/tmp/genbatch.sh`: two records per invocation, so each batch persists.

**`QWEN.md` now lives on `master`.** It previously existed only on
`qwen-worker`, a branch reset orphaned the commit, and a Qwen run stopped
dead reporting "No QWEN.md exists in the repository". Durable state belongs
where both branches can see it.

**A scheduled_date is not a commitment.** Campaign 451's one scheduled email
read `2026-09-14T13:19Z` earlier in the evening and `2026-09-14T16:24Z` a few
hours later. Nothing was staged or restaged in between. The provider re-plans
its own queue, so a scheduled time is an intention rather than a promise, and
reporting one as "sending at 13:19" would have been wrong.

**Enabling `linkedin_connection_note.mode: llm` costs roughly twice the model
calls per record.** A record now plans one persona angle, five email drafts
AND six LinkedIn notes - about twelve calls rather than six. That is the
price of the LinkedIn half of the cadence existing at all, and it should be
in any estimate of what a cohort costs.

## Model routing, decided 2026-09-13

The operator's policy, and it is a policy rather than a preference:

    DETERMINISTIC CODE  ->  QWEN  ->  OPENROUTER

OpenRouter is a QUALITY ESCALATION layer, not the default processor. Code
does code's job - headcount arithmetic, tolerances, ICP criteria, dedupe,
collision, suppression, membership, scheduling, idempotency, capacity. Qwen
is the default SEMANTIC worker. OpenRouter is called when Qwen's output fails
a quality gate, and the escalation carries the original evidence pack, the
Qwen attempt and the reason it failed - never a restarted research run.

Cheaper does NOT lower the evidence standard. `UNKNOWN` may never become a
fact whichever model is asked, and utilisation, profitability and resource
planning remain PERSONALISATION dimensions rather than ICP criteria.

### What was established about making Qwen reachable

`qwen serve` is NOT the route. It is a session daemon with its own protocol,
not an OpenAI-compatible `/chat/completions`, so `llm.OpenAICompatibleModel`
cannot be pointed at it.

The CLI is. `llm.py`'s whole design is "any object with
`complete(prompt) -> str`", and `--json-schema` "registers a synthetic
`structured_output` tool; the session ends on the first valid call" - which
is exactly the strict-JSON contract `llm.ask` already enforces against
`llm.SCHEMAS`. That is TASK-012, and it is one class rather than a refactor.

The thing to remember when reading that task: **Qwen Code is an AGENT.** Left
alone it narrates, uses tools and reads files. A model that opens
`work/queue.jsonl` to be helpful has just put another client's data into a
prompt.

Measured CLI facts, so nobody re-derives them: the executable is at
`C:\Users\Zvonimir\AppData\Local\qwen-code\bin\qwen.cmd` and is NOT on PATH; `--approval-mode auto` cannot run headless and
says so; `-y` is what works; `--max-tool-calls` is a HARD per-turn cap that
halted a run mid-task.

### The economics this is meant to answer

Nobody knows yet whether OpenRouter is necessary for this work. Tonight's run
is the first data point and it is an OpenRouter one, because Qwen was not
reachable when it started. The question to answer next is Qwen's first-pass
acceptance rate per task category - draft, linkedin_note, persona_angle,
hook - and to make Qwen the permanent default for every category where it
passes.

## The runbook, for the moment credits exist

Every link in this chain was verified offline on real estate data on
2026-09-13, against the real client config and the real provider campaign.
Only the model is missing.

    1  py -3 -m src.generate --live --client productive            --id 16kagency-com --id 1gslab-com ... (the 20 cohort ids)

       Reads the cohort from `campaigns.get("productive-email-liheavy-v1")`.
       Asks for exactly the email steps the client's sequence marks
       generated - em1..em5 - and re-plans any stored draft that FAILS lint,
       which is what picks up the three that the typography rule now refuses.
       A 429 stops the run and holds nobody.

    2  approve each clean step. Proven on `16kagency-com` on 2026-09-13:
       `approve.approve_step(rec, "izabelle-a", "em1", config=...)` writes a
       fingerprint, and `bisonfactory._approved_copy` then reads back exactly
       `['em1','em2','em3','em5']` and reports `['em4']` missing - em4 being
       the one that fails lint. The chain is not theoretical.

    3  py -3 -m src.bisonfactory productive-email-liheavy-v1 --live

       Stages the leads into campaign 481. Refuses by name if any contact
       still lacks a step. Leaves the campaign PAUSED - `bison.activate` is
       not a supported operation and this factory cannot start sending.

    4  read it back. `bison.campaign_lead_count(481)`,
       `bison.sequence_steps(481)`, `bison.variables_of(bison.lead(id))` -
       the last one is what proves each lead carries `subject_1`..`body_5`
       and no unnumbered pair.

Step 4 is the one that decides whether anything is true. A 200 is not a
verdict anywhere on this provider.

## Next single best action

Authorize the live write path, then stage `productive-email-liheavy-v1` and
read it back. The capability, the configuration, the cohort, the senders and
the schedule are all in place and verified offline; the only thing between
this and a production campaign visible in the EmailBison UI is permission to
make the call.
