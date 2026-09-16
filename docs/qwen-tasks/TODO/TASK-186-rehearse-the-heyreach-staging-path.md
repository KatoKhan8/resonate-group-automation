PRIORITY: P0
DEPENDS:

# TASK-186 - rehearse the LinkedIn staging path against a fake

## WHERE THIS SITS

TASK-184 did this for EmailBison and it earned its keep immediately: it proved
`set_sequence` appends, found the brake that already existed, and wrote the
recovery procedure for a half-failed write. The LinkedIn path has no
equivalent and it is the more dangerous of the two, because on HeyReach the
write that adds a person can ACTIVATE a campaign.

What is established:

    list staging works            TASK-158: profileUrl + firstName + lastName,
                                  firstName and lastName REQUIRED, and a
                                  missing one returns 0/0/0 with HTTP success
    the path is designed          TASK-165, 42 tests
    the verb exists, OFF          TASK-172: heyreach.add_lead_to_list, in
                                  neither SUPPORTED nor CONDITIONAL, with
                                  liststaging.assert_list_safe as its predicate
    campaign staging is sealed    no campaign state is safe to add to

So the sequence to rehearse is:

    QUALIFIED -> LIST -> READBACK -> FINAL ELIGIBILITY -> CAMPAIGN -> SEND

and the rehearsal must stop where authorization stops.

## THE QUESTION

Against a FAKE transport, end to end, exactly as TASK-184 did.

1. **The entry point.** Which function should Claude call to stage a lead into
   a list, in the style of `bisonfactory.stage(campaign_id, live=True)`? It
   must carry the gates, the action ledger and the spend ledger through
   `providerwrites.perform` - not a hand-rolled call. If no such entry point
   exists yet, say so and name where it belongs.
2. **Prove the refusal while the verb is off.** With
   `heyreach.add_lead_to_list` absent from `SUPPORTED`, calling the path must
   fail closed, loudly, naming the missing permission. Test that. This is the
   most important test in the task: it is what proves the OFF switch works.
3. **Is the write idempotent?** EmailBison's `set_sequence` appends. What does
   `AddLeadsToListV2` do with a lead already in the list? TASK-158's own
   response shape distinguishes `addedLeadsCount` from `updatedLeadsCount`, so
   the provider has an opinion - establish it from that response shape and from
   the documentation, and write the recovery procedure for a half-failed add.
4. **The readback.** `addedLeadsCount: 1` is the provider's claim about its own
   write. What proves the lead is present AND the list is still unbound? Write
   it as a function and test that it fails if either half is false.
5. **What happens between LIST and CAMPAIGN.** TASK-175 asked which operation
   attaches a list to a campaign. Whatever it found, the rehearsal must show
   that the attachment step is where the full activation gate belongs, and that
   nothing in the staging path can reach it by accident.

## THE TRAP

A rehearsal that mocks the provider into agreeing is worthless. Make the fake
return the **0/0/0 silent-drop response** and assert the path treats it as a
failure, not a success - that single behaviour is the difference between this
path being safe and it losing leads invisibly, and it is what made the route
look broken for a day.

Second trap: do not enable the verb to make the rehearsal run. The rehearsal of
a disabled path is a rehearsal of the refusal, and then of the rest with the
permission injected in the test only. If that is awkward, say so - it is
better than a repository where the verb is on because a test wanted it.

## WHAT YOU MAY NOT DO

- **No provider writes.** None. Not to list 940797, not to 933603, not to
  campaign 599020. Reads allowed.
- Do not add to `SUPPORTED` or `CONDITIONAL`, in code or in a test fixture
  that leaks into the module's real state.
- Do not weaken `liststaging.assert_list_safe` or the LINKEDIN_ADD_LEAD reseal.
- Never commit a profile URL, a prospect name or a domain.

## FILES ALLOWED

    src/liststaging.py
    tests/test_list_staging_rehearsal.py   (new)
    docs/HEYREACH-STAGING-REHEARSAL-2026-09-16.md   (new)
    scripts/task186_*.py

## FILES FORBIDDEN

    src/providerwrites.py (SUPPORTED/CONDITIONAL)   work/   config/

## DELIVERABLE

The entry point Claude should call, the proof that the path refuses while the
verb is off, the idempotency answer with a recovery procedure, the readback
function that checks presence AND unboundness, and the 0/0/0 test.
