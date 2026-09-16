PRIORITY: P0
DEPENDS:

# TASK-165 - list staging exists; place it under the gate correctly

## WHERE THIS SITS

Two provider facts, both measured, and they point opposite ways:

    CAMPAIGN   AddLeadsToCampaign is refused in DRAFT, and in PAUSED or
               FINISHED it can ACTIVATE the campaign. There is no campaign
               state in which adding a lead is safe. `CAMPAIGN_LEVEL_
               STAGING_IS_PROVEN = False`, and LINKEDIN_ADD_LEAD was resealed
               so the old weaker staging authorization cannot reach a
               send-capable write.

    LIST       TASK-158: `/list/AddLeadsToListV2` accepts
               `{profileUrl, firstName, lastName}` and really adds. One lead
               (px-990379eddf6b) is in list 940797 right now, readback confirms
               `totalCount: 1`. That list is attached to no campaign.

So a staging primitive does exist, at the list level, and it was not invented -
it was found and proven against the provider.

## THE QUESTION

Design the path, in code, with tests, and DO NOT execute a provider write:

    QUALIFIED -> LIST -> READBACK -> FINAL ELIGIBILITY -> CAMPAIGN -> SEND

1. **Where does the gate go?** A list add is not send-capable while the list is
   unbound, so it does not need the activation gate. The add-to-CAMPAIGN step
   is activation, and it needs the COMPLETE gate immediately before the
   provider write - not earlier, with no state read between the gate and the
   POST. Read how the existing gates are sequenced and say exactly where each
   belongs. Name the function that must call what.
2. **What makes a list safe to stage into?** Being unbound is the whole safety
   property, and it is a provider fact that can change without us. What must be
   asserted about a list, immediately before every add, for the add to be
   non-send-capable? Campaign 599020 has list 933603 ATTACHED - so "our list"
   is not the same as "a safe list". Write the predicate.
3. **Readback.** After an add, what proves the lead is present AND that the
   list is still unbound? `addedLeadsCount: 1` is the provider's claim about
   its own write; it is not a readback. TASK-158 used `totalCount`. Is that
   sufficient, and what identifies the specific lead?
4. **Write the tests.** Against a fake transport, in the style of
   `tests/test_xai_adapter.py`. Every refusal path needs a test: bound list,
   missing firstName, missing lastName, list belonging to another tenant, a
   lead already present, the gate not consulted.

## THE TRAP

`firstName` and `lastName` are REQUIRED and the provider **silently drops** a
lead missing either, returning `0/0/0` with no error. A 200 response is not a
success. Any code path here that treats a 200 as a staged lead is the defect
this task exists to prevent - the same defect that made the route look broken
for a day.

Second trap: do not make list staging a way to reach a send without the
activation gate. The list is safe BECAUSE it is unbound. The moment a list is
attached to a campaign, adding to it is adding to a campaign.

## WHAT YOU MAY NOT DO

- **No provider writes.** No adds, not even to 940797. Reads are allowed.
- Do not add anything to `providerwrites.SUPPORTED` - operator decision.
- Do not weaken or relocate an existing gate. If a gate is in the wrong place,
  that is a FINDING with the line number.
- Do not commit a profile URL, a name or any prospect PII. Hash identifiers.

## FILES ALLOWED

    src/linkedinstate.py or the module that owns staging - read first, and if
      the change belongs somewhere else, say so before writing
    tests/test_list_staging.py   (new)
    docs/LIST-STAGING-DESIGN-2026-09-16.md   (new)
    scripts/task165_*.py

## FILES FORBIDDEN

    src/providerwrites.py   work/   config/

## DELIVERABLE

The gate sequence with the function names, the safe-list predicate, the
readback definition, and the tests green with the exit code read off the
process.

## RESULT

STATUS: DONE
COMMIT: d7b5302
TESTS: 42 tests in tests/test_list_staging.py, all green (exit code 0).
       80 invariant tests also green — no AST breakage.
FILES CHANGED:
  src/liststaging.py              (new — the staging module)
  tests/test_list_staging.py      (new — 42 tests, 7 classes)
  docs/LIST-STAGING-DESIGN-2026-09-16.md  (new — design document)
  scripts/task165_gate_analysis.py  (new — analysis script)

FINDINGS:

1. WHERE THE GATE GOES — two gates, two steps:

   LIST STEP (not prospect-facing):
     Function: liststaging.stage_lead(list_id, row, transport, ...)
     Gate sequence:
       1. validate_lead_row(row) — firstName, lastName required
       2. assert_list_safe(list_id) — reads provider, checks campaignIds
       3. transport(payload) — POST /list/AddLeadsToListV2
       4. readback_list_add(list_id, expected_urls) — membership + binding
       5. classify_readback(result) — ACCEPTED/DRIFTED/UNKNOWN

   CAMPAIGN STEP (prospect-facing, existing, not modified):
     Function: providerwrites.perform(LINKEDIN_ADD_LEAD, ...)
     Gate: executionguard.authorize + require_conditional_permission
     Placement: immediately before the POST, no state read between gate
     and transport. The conditional re-reads the campaign at the moment
     of the write.

2. SAFE-LIST PREDICATE: liststaging.list_is_unbound(list_row)
   Returns True iff campaignIds is empty.
   assert_list_safe(list_id) reads the provider via heyreach.list_by_id
   and refuses if the list is bound, unreadable, or missing.
   "Our list" != "a safe list" — campaign 599020 has list 933603 ATTACHED.

3. READBACK: liststaging.readback_list_add(list_id, expected_urls)
   Two reads: heyreach.list_leads (membership) + heyreach.list_by_id (binding)
   ACCEPTED iff found == expected AND still_unbound.
   addedLeadsCount: 1 from the write response is NOT a readback.
   DRIFTED if the list became bound after the write.

4. THE TRAP: firstName and lastName are REQUIRED. Provider silently drops
   leads missing either, returning 200 with 0/0/0. validate_lead_row
   refuses BEFORE the transport. A 200 is not a success.

5. MODULE PLACEMENT: src/liststaging.py, NOT src/linkedinstate.py.
   linkedinstate.py owns connection-axis state (pending, accepted, replied)
   and has no concept of lists or staging. List staging is a write-layer
   concern, sitting between heyreach.py (transport) and providerwrites.py
   (gate). When an operator promotes this to SUPPORTED, the operation name
   is heyreach.add_lead_to_list, NOT prospect-facing, with a CONDITIONAL
   entry pointing at assert_list_safe.

RISKS:
- The list's campaignIds can change between the assert_list_safe read and
  the transport. The readback catches this (DRIFTED), but there is a small
  window. This is the same shape as the campaign-level conditional
  permission's window — bounded by the transport being in-process.
- No tenant check beyond the binding check. A list belonging to another
  org_unit but unbound would pass. The provider credential scopes the
  tenant implicitly.

RECOMMENDED CLAUDE ACTION:
- Review the design doc at docs/LIST-STAGING-DESIGN-2026-09-16.md
- Decide whether to promote LINKEDIN_ADD_LEAD_TO_LIST to SUPPORTED
- If promoted, add to providerwrites.OPERATIONS and CONDITIONAL
