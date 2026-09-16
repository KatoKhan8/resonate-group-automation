PRIORITY: P0
DEPENDS:

# TASK-172 - list staging has no verb, and therefore no permission

## WHERE THIS SITS

`src/providerwrites.py` enumerates every write this system can perform. The
LinkedIn verbs are:

    heyreach.add_lead            SUPPORTED, and CONDITIONAL on
                                 _campaign_is_a_declared_staging_campaign
    heyreach.create_list         not supported
    heyreach.create_campaign     not supported
    heyreach.set_sequence        SUPPORTED
    heyreach.assign_sender       not supported
    heyreach.set_limits          not supported
    heyreach.pause               SUPPORTED
    heyreach.activate            not supported
    heyreach.start_empty_for_staging   SUPPORTED, CONDITIONAL

There is no verb for adding a lead to a LIST. TASK-158 proved the route works
and TASK-165 designed the path, and neither could name the permission it needs,
because the permission does not exist.

That matters more than it looks. `heyreach.add_lead` is conditional on the
destination being a declared staging campaign proven unable to send - and
provider truth says NO campaign state is safe: DRAFT refuses the add, PAUSED
and FINISHED can activate on it. So the conditional can never be satisfied, and
the verb is sealed in practice. Correct, and deliberate.

List staging is a different door. It needs its own verb and its own condition.

## THE QUESTION

Specify the verb completely, and DO NOT enable it.

1. **The verb.** Its constant name and its string, in the style of the others.
   Which module performs it, and where does the schema TASK-158 established -
   `profileUrl`, `firstName`, `lastName`, the last two required - get enforced
   before the request leaves.
2. **The condition.** Write the predicate, in the style of
   `_campaign_is_a_declared_staging_campaign` and
   `_campaign_is_ours_and_holds_nobody`. It must answer, from a provider read
   taken at the moment of the write: is this list ours, is it in our tenant, and
   is it attached to NO campaign. Campaign 599020 has list 933603 attached, so
   "a list we created" is not the condition.
3. **What the condition cannot promise.** A list unbound at the moment of the
   write can be attached a second later by anyone with provider access. Say
   plainly what this verb's permission does and does not guarantee, and what
   would detect the attachment afterwards.
4. **The refusal tests.** Against a fake transport: list attached to a campaign,
   list in another tenant, list not ours, missing firstName, missing lastName,
   the 0/0/0 silent-drop response treated as failure, condition not consulted,
   provider read unavailable. Every one must refuse, and the last must refuse
   fail-closed.
5. **The case for and against enabling it**, stated for an operator who will
   read only this section. What it buys, what it risks, what becomes possible
   the moment it is on, and what stays impossible.

## THE TRAP

Do not add the verb to `SUPPORTED`. Do not add it to `CONDITIONAL`. Define the
constant and the predicate function, wire the refusals, and leave the
permission OFF. Membership of `SUPPORTED` is an operator decision and this task
does not have it - the comment on `LINKEDIN_ADD_LEAD` records what enabling a
prospect-facing route cost to justify, and that is the bar.

Second trap: a verb that exists and is unsupported must FAIL CLOSED, loudly,
with a message naming the missing permission. A verb that exists and silently
does nothing is worse than no verb.

## WHAT YOU MAY NOT DO

- **No provider writes.** None. Not to list 940797, not anywhere.
- Do not add to `SUPPORTED` or `CONDITIONAL`.
- Do not modify `heyreach.add_lead` or its condition, and do not weaken
  `LINKEDIN_START_EMPTY_FOR_STAGING`.
- Never commit a profile URL, a name or a prospect identifier.

## FILES ALLOWED

    src/providerwrites.py   (the CONSTANT and the PREDICATE only - not the
                             SUPPORTED tuple, not the CONDITIONAL map)
    src/liststaging.py
    tests/test_list_staging_permission.py   (new)
    docs/LIST-VERB-PROPOSAL-2026-09-16.md   (new)

## FILES FORBIDDEN

    work/   config/

## DELIVERABLE

The verb constant, the condition predicate, the honest statement of what the
condition cannot promise, the refusal tests green with the exit code read off
the process, and the operator's case for and against - on the explicit record
that the permission is left OFF.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 1df8e44
- **TESTS:**
  - `tests.test_list_staging_permission` — 31 tests, all green, exit code 0
  - `tests.test_list_staging` — 42 tests, all green, exit code 0
  - `tests.test_invariants` — all green
  - `tests.test_a_person_can_enter_a_heyreach_campaign` — all green (including `test_supported_is_exactly_this`, which asserts the exact SUPPORTED tuple and still passes because the new verb is NOT in it)
  - `tests.test_campaign_audit` — all green
  - Combined run: 245 tests, exit code 0
- **FILES CHANGED:**
  - `src/providerwrites.py` — added `LINKEDIN_ADD_LEAD_TO_LIST = "heyreach.add_lead_to_list"` constant (line 108) and its OPERATIONS entry (line 164). NOT added to SUPPORTED, NOT added to CONDITIONAL.
  - `src/liststaging.py` — changed to import `LINKEDIN_ADD_LEAD_TO_LIST` from `providerwrites` instead of defining it locally. No other changes.
  - `tests/test_list_staging_permission.py` — NEW. 31 tests covering every refusal path the task names.
  - `docs/LIST-VERB-PROPOSAL-2026-09-16.md` — NEW. The operator's case for and against enabling.
- **FINDINGS:**
  - The constant is consumed: defined in `providerwrites.py`, imported by `liststaging.py` (used in `stage_lead` result dict), and referenced in 14 test assertions. `grep -rn LINKEDIN_ADD_LEAD_TO_LIST src/` returns 4 hits across 2 modules.
  - The verb fails closed: `providerwrites.perform(LINKEDIN_ADD_LEAD_TO_LIST, ...)` raises `WriteUnsupported` with a message naming the operation (`heyreach.add_lead_to_list`) and the channel (`linkedin`). The transport is never reached.
  - The predicate (`assert_list_safe`) checks what it can (`campaignIds` is empty, read live from provider) and refuses everything else fail-closed. It cannot verify list ownership or tenant membership because the HeyReach list API returns no ownership field (`LIST_FIELDS = (id, name, listType, totalItemsCount, campaignIds, creationTime)`). This limitation is documented in the OPERATIONS entry and the proposal doc.
  - The 0/0/0 silent-drop response (`addedLeadsCount: 0, totalLeads: 0, duplicateLeads: 0`) is treated as failure: the readback finds the lead absent, verdict is UNKNOWN, `stage_lead` raises `ListStagingUnverified`.
  - Gate ordering is correct: validation runs before the safety check, the safety check runs before the transport. A validation failure does not consult the predicate.
- **RISKS:**
  - The predicate is a point-in-time check, not a lock. A list unbound at the moment of the write can be attached to a campaign a second later. The readback (`readback_list_add`) detects this after the fact and classifies DRIFTED, but the lead is already in the list.
  - Enabling this verb does not enable `LINKEDIN_ADD_LEAD` or any other verb. The two are separate doors with separate keys.
- **RECOMMENDED CLAUDE ACTION:** Review the proposal doc (`docs/LIST-VERB-PROPOSAL-2026-09-16.md`) and decide whether to enable the verb. If yes: add `LINKEDIN_ADD_LEAD_TO_LIST` to `SUPPORTED` and add `CONDITIONAL[LINKEDIN_ADD_LEAD_TO_LIST] = assert_list_safe`. The predicate and the refusals are already in place.
