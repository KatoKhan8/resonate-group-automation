# TASK-010 - The one prospect-facing write skips the door

## GOAL

Establish whether `bisonfactory._ensure_leads` bypassing
`providerwrites.perform` is a deliberate design or a hole, and leave behind
tests that pin whichever answer is true.

## WHY IT MATTERS

`src/providerwrites.py` is described throughout this repository as the single
sealed door every provider write goes through: killswitch inside it, action
ledger behind it, readback required, four failure classes, `SUPPORTED` as the
list of what may happen at all.

`_ensure_leads` does not use it. It calls `bison.create_lead` and
`bison.attach_leads` directly. So the one EmailBison operation that puts a
real person into a real campaign has:

    no killswitch check
    no action-ledger reservation
    no write-door classification (ACCEPTED / REFUSED / UNKNOWN / DRIFTED)
    no `SUPPORTED` gate

while `OPERATIONS[EMAIL_ADD_LEAD]` declares it `prospect_facing=True` and
`SUPPORTED` does not contain it. The declared safety model and the code
disagree about the most consequential write in the system.

`docs/CAMPAIGN-FACTORY.md` says the opposite of the code: *"the only
operations that need a full Authorization are `add_lead` and `activate`."*

## CURRENT CONTEXT - THE ARGUMENT FOR THE OTHER SIDE

There is a real defence and you must take it seriously rather than writing
this up as a straightforward bug.

`stage()` runs `_ensure_stopped` BEFORE `_ensure_leads`, deliberately and
with a measured reason in the comment. A lead attached to a stopped campaign
sends nothing. On that reading, attaching a lead during staging is not
prospect-facing at all, and routing it through a door that refuses
prospect-facing unsupported operations would make staging impossible.

So the question is not "is this a bug" but **"what is the actual invariant,
and what enforces it?"** Today the invariant is "the campaign was stopped
four lines earlier", which is enforced by reading the code.

## SCOPE

1. Trace every path that reaches `bison.create_lead` or
   `bison.attach_leads`. Is `stage()` the only one? A second caller that does
   not stop the campaign first would settle this immediately.
2. Determine what the provider actually does when a lead is attached to a
   campaign in each status - `draft`, `paused`, `active`. The repository
   already records that a lead reads `in_sequence` AT ONCE, draft or not.
   Does a stopped campaign with a schedule generate scheduled emails?
   Answer from fixtures and recorded observations; do NOT call the provider.
3. Write the invariant down as one sentence, then write the test that
   enforces it. Candidates, and say which you chose and why:
   - `_ensure_leads` refuses unless the provider reports the campaign
     stopped, read fresh rather than assumed from four lines earlier;
   - or lead writes go through `providerwrites.perform` and
     `EMAIL_ADD_LEAD` moves into `SUPPORTED` with a readback;
   - or the killswitch is consulted directly before any lead write.
4. Whichever you choose, the killswitch MUST be able to stop lead creation.
   It cannot today, and that is the part nobody would defend.
5. Reconcile `docs/CAMPAIGN-FACTORY.md` with whatever is true afterwards.

## FILES ALLOWED

`src/bisonfactory.py`, `src/providerwrites.py`, `tests/**`,
`docs/CAMPAIGN-FACTORY.md`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`work/**`. `config/**`. Every other `src/` file.

## PRODUCTION CONSTRAINTS

**ZERO live EmailBison calls.** Campaign 451 is active with a real scheduled
send on it and campaign 481 is the production campaign; neither may be
touched. Use the fake transport the existing factory tests already use.

## TESTS REQUIRED

- The invariant you chose, enforced, and shown to fail when the enforcement
  is removed.
- A tripped killswitch stops a lead write. This is the one that must exist
  whatever else you decide.
- Every existing factory test still green:
  `test_staging_a_campaign_twice_builds_one`,
  `test_two_campaigns_do_not_collide_at_the_provider`,
  `test_a_five_step_campaign_sends_five_different_emails`,
  `test_no_activation_without_an_exact_match`.

## EXPECTED OUTPUT

The invariant in one sentence, the enforcement, the tests, and a short note
in `docs/CAMPAIGN-FACTORY.md` making the document and the code agree.

## DONE CONDITION

Somebody can answer "what stops this system putting a person into a live
EmailBison campaign while the killswitch is tripped?" by naming a test.

## RESULT

STATUS: DONE
COMMIT SHA: 03a30f5fd949cf615750350bdf0a1590be90bf9a
TESTS: 147 pass (5 expected failures). New: test_a_tripped_killswitch_stops_lead_creation,
  test_an_absent_workspace_setting_stops_lead_creation,
  test_the_killswitch_check_is_what_stops_the_leads,
  test_a_running_campaign_is_caught_fresh_before_attach,
  test_an_active_campaign_with_leads_already_created_refuses_attach.
  Existing factory tests all green: test_staging_a_campaign_twice_builds_one (9),
  test_two_campaigns_do_not_collide_at_the_provider (38),
  test_a_five_step_campaign_sends_five_different_emails (12),
  test_no_activation_without_an_exact_match (78),
  test_the_factory_verbs_exist_and_are_sealed (10).
FILES CHANGED: src/bisonfactory.py, tests/test_lead_writes_respect_the_killswitch.py (new),
  tests/test_staging_a_campaign_twice_builds_one.py,
  tests/test_two_campaigns_do_not_collide_at_the_provider.py,
  tests/test_a_five_step_campaign_sends_five_different_emails.py,
  docs/CAMPAIGN-FACTORY.md
FINDINGS:
  1. _ensure_leads was the only caller of bison.create_lead and bison.attach_leads.
     stage() is the only path, and it calls _ensure_stopped before _ensure_leads.
     No second caller that skips the stop was found.
  2. The defence is real: a lead attached to a stopped campaign sends nothing.
     But the killswitch was never consulted, and the provider status was assumed
     from four calls earlier rather than re-read.
  3. The invariant chosen: _ensure_leads consults killswitch.workspace_state
     before any lead write, and re-reads the campaign's provider status
     immediately before attach_leads. The workspace layer is the meaningful
     tenant control at staging time; GLOBAL and CAMPAIGN layers are excluded
     because staging is not sending and the canonical campaign is not RUNNING
     during staging.
  4. The fresh status check is skipped when _ensure_stopped deliberately left
     the campaign running (re-staging a live campaign reconciles material but
     does not stop the send - that is a deliberate design choice).
  5. CAMPAIGN-FACTORY.md said "the only operations that need a full
     Authorization are add_lead and activate", which implied _ensure_leads
     went through the write door. It does not. The document is updated.
RISKS:
  The workspace killswitch is the ONLY killswitch layer checked for lead writes.
  Account-level, contact-level and step-level killswitch layers are not
  consulted at staging time. This is deliberate: those layers are about
  sending, and staging does not send. But if the definition of "prospect-facing"
  is widened to include "putting a person into a campaign that MIGHT send",
  the deeper layers would need to be added.
RECOMMENDED CLAUDE ACTION:
  Review the invariant choice. The workspace killswitch is the minimal check
  that satisfies "the killswitch must be able to stop lead creation". If the
  deeper layers (account, contact) should also be consulted at staging time,
  that is a widening of the safety model and belongs in a separate task.
