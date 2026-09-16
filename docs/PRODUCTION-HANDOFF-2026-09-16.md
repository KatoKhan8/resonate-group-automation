# Production handoff - 2026-09-16, before context reset

Written by Claude. Everything here is read off provider truth, the code, or a
measured run. Where a number came from a stale artefact it says so.

**NOTHING HAS BEEN SENT ON EITHER CHANNEL. Send exposure to date: ZERO.**

---

## 1. HEYREACH - provider IDs, exact

    list 940797    "RESONATE - STAGING PROBE - DO NOT USE"
                   campaignIds [604869] - BOUND, no longer a staging target
                   1 lead: the TASK-158 schema probe, which turned out to be
                   an operator-approved contact
    list 933603    campaignIds [599020] - bound to the old production campaign
    list 943957    "RESONATE - PRODUCTIVE LINKEDIN COHORT 2026-09-16"
                   campaignIds [] - UNBOUND
                   4 leads, the ready cohort, all staged and read back
    campaign 599020  "RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1"
                   status FINISHED, 0 direct leads, seat 174892
                   sequence 17 nodes / 8 word-bearing, hash cf93bda7fc1e
    campaign 604869  "RESONATE - PRODUCTIVE LINKEDIN CANARY - CONTROL"
                   status DRAFT, linkedInUserListId 940797, seat 174892
                   sequence 17 nodes / 8 word-bearing, hash cf93bda7fc1e
                   IDENTICAL graph to 599020 - reproduced, not rebuilt
                   campaign-level approval recorded, fingerprint
                   3585d3c21b8cfe6a3ca3
    seat 174892    resolves, active
    canonical rows  productive-linkedin-canary-v1 -> 604869 (approved)
                    productive-linkedin-production-v1 -> 599020

**604869 is a dead end for sending.** Its bound list holds only the HELD
contact. It is DRAFT, so it sends nothing, and it should be left alone rather
than activated.

### READY / HOLD cohorts, LinkedIn

6 contacts carry full `li1-li5` `operator-control-arm` approval with
fingerprints, across 4 accounts. Re-checked against
`collision.account_policy` at run time:

    READY  4 contacts / 3 accounts - staged in list 943957
           profile hashes 6acd6d9f031b, 4684b25b0372, c01f0c88111c,
           4258f756357d
           account f3945ded7f71  1 contact   5 emails sent, finished, no reply
           account 035712846aff  1 contact   0 prior contact
           account 7c559ffe3538  2 contacts  21 emails sent, finished, no reply

    HOLD   2 contacts / 1 account - account c0ef6483d378
           9 emails across 2 campaigns; one `stopped` and the provider does
           NOT record why. `account_policy` will not infer whether we stopped
           it, they unsubscribed, or a reply stopped it. THE HOLD IS CORRECT.
           One of these two is the contact staged in list 940797.

    HEYREACH_READY_COHORT = 4
    HEYREACH_LIVE_COHORT  = 0
    HEYREACH_SENT         = 0

**Account 7c559ffe3538 has had 21 emails.** It passes policy because they were
finished campaigns with no reply. That is defensible and it is also a heavily
worked account - an operator judgement, not a gate failure.

---

## 2. EMAILBISON - provider IDs, exact

    workspace 10   "PRODUCTIVE"
    campaign 481   paused, 23 leads, 0 sent. NOT a destination: all 23 carry
                   6-40 historical touches under a non-CONTROL 5-step sequence
    campaign 451   completed, 1 lead, 1 sent
    campaign 484   ARCHIVED, 0 leads. Abandoned: created with a 5-step
                   sequence before the 3-step config existed
    campaign 485   ARCHIVED -> revived by the operator to DRAFT -> currently
                   DRAFT
                   10 leads, 3 sequence steps, cap 20/day, 0 sent
                   sender [2736] attached and provider-verified
                   canonical row productive-email-control-v2
                   provider_status_expected declared 'draft'

**485 MUST BE REBUILT AND MUST NOT BE ACTIVATED.** Two reasons, both provider
truth:

1. Its sequence violates the threading invariant - step 2 carries a distinct
   `{SUBJECT_2}`, step 3 is `thread_reply: false` with its own `{SUBJECT_3}`.
2. `bison.set_sequence` APPENDS. No replace, no per-step delete. So the
   sequence cannot be corrected in place; a second write leaves the campaign
   carrying both.

### The archive defect - root cause established

**EmailBison archives a campaign that has no sending account attached.**
4 for 4 across the workspace: 451 (sender 3948) completed, 481 (senders 2736,
2737) paused, 484 (none) archived ~6 min after creation, 485 (none) archived
~10 min after creation. Nothing in this repository archives anything - there
is no archive route and no campaign DELETE in `bison.WRITE_ROUTES`, and 481
received the identical call sequence and survived. The difference is the
ABSENCE of `attach-sender-emails`.

**Consequence for the rebuild: attach the sender DURING staging**, by naming
it on the campaign row before `stage()` runs, rather than leaving the campaign
senderless while somebody chooses. `_ensure_senders` deliberately no-ops on an
empty row ("choosing an inbox would be choosing who a prospect hears from"),
and on this provider that window is minutes.

### Email cohort

    17  rendered by TASK-167, all passing lint and claims
    16  survive the per-contact collision check (one domain had 13 prior
        emails at the provider - a real hit)
    11  have a resolved persona
    10  have an `em2` step at all - the approved CONTROL cohort
        30 steps (10 x em1/em2/em3), all fingerprinted against the
        CONTROL-expanded copy, 0 stale

    EMAILBISON_READY_COHORT = 10
    EMAILBISON_LIVE_COHORT  = 0
    EMAILBISON_SENT         = 0

**The leads at the provider still carry the OLD generated copy.** Measured:
provider `body_1` reads "<company> describes itself as..." where the approved
CONTROL reads "<first name>, I work with <sector> teams on...". `stage()`
reported "created 1 lead(s), reused 9" - nine lead objects were reused from
the 2026-09-13 staging and their custom variables were never fully rewritten.
TASK-217 implemented the clearing; it has NOT yet been applied to 485's leads,
and 485 is being replaced anyway.

---

## 3. AUTHORIZATIONS ALREADY GRANTED

All in `OPERATOR-AUTHORIZATION-2026-09-16.md`. **A fresh session may act on
these without re-asking.**

    bison.create_campaign      SUPPORTED (pre-existing)
    bison.set_sequence         SUPPORTED (pre-existing)
    bison.assign_sender        SUPPORTED, CONDITIONAL -> campaign 485 only
    bison.activate             SUPPORTED, CONDITIONAL -> campaign 485 only
    heyreach.set_sequence      SUPPORTED (pre-existing)
    heyreach.add_lead_to_list  SUPPORTED, CONDITIONAL -> list must be unbound
    heyreach.create_campaign   SUPPORTED, CONDITIONAL -> list ours/unbound/
                               holding approved leads
    heyreach.activate          SUPPORTED, CONDITIONAL -> campaign 604869 only
    heyreach.create_list       SUPPORTED, no condition (an empty list is inert)

    EMAIL CONTROL sequence approved for the 10-contact cohort
    HeyReach activation approved: campaign 604869, seat 174892,
      max exposure 1 person / up to 4 messages

**STILL SEALED, do not touch:** `CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False` and
`LINKEDIN_ADD_LEAD` refused on the first line of its own condition. Adding a
lead to a HeyReach campaign ACTIVATES it - vendor-documented for PAUSED and
FINISHED - and 599020 is FINISHED right now.

**SCOPE GAPS a fresh session must notice:**

- `bison.activate`'s condition names **485**, which is being replaced. The
  rebuilt campaign will need `_AUTHORIZED_EMAIL_CAMPAIGN` updated to its id.
  That is an operator decision, not a refactor.
- `heyreach.activate`'s condition names **604869**, which is the dead end. The
  campaign bound to list 943957 will need the same.

---

## 4. TASK-219 AND TASK-221 RESULTS

**TASK-219 - the threading invariant. DONE, integrated.** Only the opener owns
a subject. The config is the threaded shape, all three steps reference
`{SUBJECT_1}`, `thread_reply_pattern [false, true, true]`, final wait 1 (the
provider rejects 0 - measured). `_variables_for` writes `subject_1` only and
empties the rest. 18 tests including the two negative ones: a follow-up with
`thread_reply=false` and its own subject FAILS the preflight.

The design call, made by Claude: every step references `{SUBJECT_1}` because
TASK-159 measured that a thread-reply step still CARRIES `email_subject` - the
flag is the mechanism, not subject omission. So one subject variable exists and
`subject_2`/`subject_3` cannot be generated at all.

**TASK-221 - the exact-match safety gate. MERGED AND RED. THIS IS THE
BLOCKER FOR EMAILBISON ACTIVATION.** Verified by Claude, not assumed:

    py -3 -m unittest tests.test_no_activation_without_an_exact_match
    Ran 46 tests - FAILED (failures=9, errors=3, expected failures=5)

Run in isolation, so this is not a test-ordering artefact. Failing:

    ERROR  test_wrong_body, test_wrong_delay, test_wrong_subject
           IndexError - `bodies[-1]` on an EMPTY list
    FAIL   test_wrong_subject/sender/tenant/daily_limit/new_lead_limit,
           test_an_extra_lead, test_a_missing_lead, test_an_extra_sequence_step,
           test_an_already_activated_campaign,
           test_activation_is_refused_at_the_write_door_regardless

**Root cause, measured not guessed.** On the demo fixture,
`configdiff.approved_bison` returns `subjects=0, bodies=0, delays=0,
thread_replies=0, actions=0` while `lead_set=1` and `_lead_copy=1`. Because
`approved_bison` now builds the expected sequence from
`config["email_sequence"]` (src/configdiff.py:635, via
`bisonfactory._sequence_steps`) - part of the TASK-215 compare_bison rewrite -
and **`config/clients/demo.yaml` has no `email_sequence` block at all**
(grep returns nothing). So `_sequence_steps(None, steps)` yields `[]`, the
expected sequence is empty, and every mutation test has nothing to mutate.
The fixture's cadence resolves 7 demo steps (day1..day21), so the cadence side
is fine; it is the sequence template side that is empty.

**What this does and does not mean.**
- It is NOT evidence that the production readback is broken.
  `config/clients/productive.yaml` DOES declare `email_sequence`, and
  `compare_bison` on the live Productive campaign produced a non-empty diff
  today - that is how the stale `lead_copy` on 485 was caught.
- It IS the case that the module which guarantees "activation is refused on
  anything less than an exact match" currently proves nothing about the email
  sequence. Whether an empty expected sequence BLOCKS or silently AGREES is
  exactly what those 9 tests existed to establish, and right now it is
  unproven either way.
- Therefore: **do not activate EmailBison until this module is green.** The
  likely fix is small - give `demo.yaml` an `email_sequence` matching its
  fixture expectations, the same way it was given
  `providers.emailbison.workspace: 99` earlier today - but "likely small" is
  not "verified", and the gate must be proven before it is relied on.
- `tests/test_heyreach_start_is_sealed.py` is GREEN, 23 tests, isolated. The
  HeyReach seals are intact.

**TASK-217 - lead variable clearing. DONE, integrated.** `_stale_clearances`
writes explicit empty values for numbered positions above the sequence length,
proven by removing the call and watching the test fail with the exact defect.

**TASK-215 - `compare_bison`. DONE, integrated.** It was comparing approved
resolved copy against sequence placeholders, and cadence days against provider
`wait_in_days` - two pairs of different quantities, so it could never pass.
Now compares like for like and compares resolved copy against the LEAD'S
CUSTOM VARIABLES, which is where the words live. That fix is what caught the
stale-copy defect on 485.

---

## 5. REMAINING EXACT STEPS TO LIVE

### EmailBison

0. **FIRST, AND BLOCKING: make `tests.test_no_activation_without_an_exact_match`
   green.** It is red for the reason in section 4 - `demo.yaml` has no
   `email_sequence`, so the expected sequence is empty. Fix the fixture/config,
   then confirm each mutation test still CATCHES its mutation (break one
   deliberately and watch the intended test fail for the intended reason).
   Do not activate EmailBison before this passes.
2. Create a NEW campaign row (`productive-email-control-v3`) with
   `cadence_steps` = the 3-step CONTROL, `daily_volume.email` 20, and
   **`senders.email` naming 2736 BEFORE staging** - see the archive defect.
3. `py -3 scripts/write_control_campaign.py --live --with-leads` after
   pointing `CAMPAIGN_ID` at v3.
4. Re-apply the lead variables so every `subject_1`/`body_1..3` matches the
   approved CONTROL and `subject_2..N`/`body_4..5` are empty. TASK-217's
   clearing does this during `stage()`; verify it from the provider, per lead.
5. `configdiff.compare_bison(...)` must return PASS with `lead_copy` matching.
6. Ask the operator to re-scope `_AUTHORIZED_EMAIL_CAMPAIGN` to the v3 id.
7. `py -3 scripts/activate_control_campaign.py --live` (point it at v3).
8. Provider readback; confirm sending; reconcile the ledger.

### HeyReach

1. Create a campaign bound to **list 943957** with seat 174892 -
   `scripts/create_linkedin_canary_campaign.py` with `LIST_ID` changed, or a
   sibling script. `heyreach.create_campaign` is authorized and its condition
   passes for 943957 (ours, unbound, holding approved leads).
2. Reproduce the sequence: `heyreach.sequence_for_write(
   heyreach.campaign_sequence(599020))` then `heyreach.set_sequence` - already
   authorized. Verify the hash is `cf93bda7fc1e`.
3. Create a canonical campaign row bound to it, with `provider_delays`
   `[["DAY", 1]]`, `org_unit` 118832, seat 174892, and the 4 record ids -
   copy the shape of `productive-linkedin-canary-v1`.
4. Record the campaign approval through `orchestrator.decide(..., role="admin")`
   - never by hand-setting `campaign["approval"]`; the fingerprint binding is
   the point.
5. Ask the operator to re-scope `_AUTHORIZED_LINKEDIN_CANARY` to the new id.
6. Mint the Authorization per contact via `executionguard.authorize` with a
   `configdiff.compare_heyreach(..., staging=True)` readback, then
   `providerwrites.perform(LINKEDIN_ACTIVATE, ...)` with
   `expect_leads` = the list's lead count.
7. Provider readback; confirm sending; reconcile the ledger.

**Expected max send exposure at HeyReach activation: 4 people, up to 4
messages each.** The graph branches on connection state - already-connected
receives up to 4 messages, cold receives 1 connection request then up to 3.

---

## 6. FILES THAT MATTER

    OPERATOR-AUTHORIZATION-2026-09-16.md   every grant, verbatim scope
    docs/ACTIVATION-DECISION-2026-09-16.md why the global killswitch is the
                                           wrong lever - push.run's live send
                                           is UNIMPLEMENTED, not disabled, and
                                           the provider does the sending
    docs/BISON-ARCHIVE-ROOT-CAUSE-2026-09-16.md
    docs/DOES-A-BOUND-LIST-SEND-2026-09-16.md   the audience is the bound list
    docs/COMPARE-BISON-2026-09-16.md
    docs/LEAD-VARIABLES-2026-09-16.md
    docs/ONLY-THE-OPENER-OWNS-A-SUBJECT-2026-09-16.md
    docs/QWEN-QUOTA-EXHAUSTED-2026-09-16.md     quota restored; ignore the file
    work/approval/                              real prospect copy, gitignored

    scripts/apply_control_approval.py        email approvals, dry-run default
    scripts/write_control_campaign.py        the Bison campaign write
    scripts/activate_control_campaign.py     Bison activation preflight
    scripts/create_linkedin_canary_campaign.py
    scripts/stage_linkedin_ready_cohort.py   list 943957 + the 4 ready leads
    scripts/activate_linkedin_canary.py      approval -> authorize -> activate

Every script is dry-run by default and refuses on any preflight surprise.

---

## 7. THINGS A FRESH SESSION WILL OTHERWISE GET WRONG

- `work/queue.snapshot.jsonl` is STALE. It produced at least two wrong numbers
  today. Read live state and quote its record count.
- The Z.AI / GLM Coding Plan is configured in `config/.env`
  (`ZAI_API_KEY`, `ZAI_BASE_URL` = the **coding** endpoint, `ZAI_MODEL`
  = `glm-5.3`). Auth probe PASSED. The worker backend is deliberately NOT
  built - the operator agreed to defer it until both channels are live. The
  endpoint remaps models: `glm-5.2`/`glm-5.3` serve `glm-5.3`,
  `glm-4.6`/`glm-4.5-air` serve `glm-5.3-flash`.
- **The key in `config/.env` was pasted into a chat transcript and should be
  rotated.**
- Qwen quota was exhausted and is restored; the pool is healthy. Dispatch with
  `POOL_ROUND=rNN bash scripts/pool.sh sweep` using a NEW round number each
  sweep.
- `claim_task.py --status` reports "stale branches hiding available tasks: 87".
  Those are old DONE tasks; it is noise, not a queue problem.
- Two mistakes of mine worth not repeating: I approved 30 email steps without
  passing `campaign=`, so the fingerprints covered the wrong text and my own
  verification used the 3-argument `is_approved`, which compares the stored
  step to itself and agrees unconditionally. And I reset a worktree while its
  worker was still running, losing TASK-164's commits (recovered from reflog).
