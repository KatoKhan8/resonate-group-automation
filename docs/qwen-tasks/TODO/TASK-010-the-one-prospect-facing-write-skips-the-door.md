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

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
