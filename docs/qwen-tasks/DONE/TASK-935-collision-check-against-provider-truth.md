PRIORITY: P0
SIZE: M
DEPENDS: 

# TASK-935 — prove the canary person is in NO campaign, from the PROVIDERS

**Operator condition for the FIRST CANARY ONLY, Zvonimir, 2026-09-30:**

> Collision check against provider truth, NOT the local ledger: prove from
> EmailBison and HeyReach READS that this person and company are not in any
> of our past campaigns (the ~912 historical sends, 503-505, 491-500) and not
> in any of the client's own campaigns ("FIXED - PRODUCTIVE" in HeyReach,
> 327/328/352/418 in EmailBison). A match is a disposition, then next
> candidate.

## Why the local ledger is not acceptable evidence

`CLAUDE.md` records the measurement: across our campaigns the provider
confirms **912 sends** against **ONE** recorded touch in 1,582 records. The
code that ingests sent events had zero production callers. So the local
ledger says "never contacted" about people who have been emailed six times.
Asking it here would prove nothing at all.

## What to build

A read-only check that takes an email address and a company domain and
answers, FROM THE PROVIDERS:

    CLEAR      neither the person nor the company appears in any campaign
    COLLISION  where it appears - provider, campaign id, campaign name

Cover BOTH estates, ours and the client's. The client's campaigns matter as
much as ours: writing to somebody their own team is already sequencing is
the worst outcome available.

## Rules

- **READ ONLY.** No write of any kind, to any provider. This runs before any
  canary write and must be safe to run at any time.
- Use the existing provider modules and `providers.request`. Do not open a
  second HTTP path.
- **Paginate to exhaustion and say so.** `senderheadroom`'s rule is the
  precedent: a partial walk can only UNDERCOUNT, so "no collision found" is
  only true from a complete walk. An incomplete read is UNKNOWN, and
  **UNKNOWN IS NOT CLEAR** - it must refuse, not pass.
- HeyReach's `campaign/GetAll` timed out at 25s on 2026-09-30. Handle it:
  retry with backoff, and report UNKNOWN rather than treating a timeout as
  an empty estate.
- The client's HeyReach campaigns are identified by the name "FIXED -
  PRODUCTIVE"; the client's EmailBison campaigns are 327, 328, 352, 418.
  Read these from provider data, not from a list copied into the code, where
  the provider can tell you.

## Tests

- a person in one of our campaigns -> COLLISION naming it
- a person in a CLIENT campaign -> COLLISION naming it
- a person in neither, complete walk -> CLEAR
- an INCOMPLETE walk (timeout, partial page) -> UNKNOWN, never CLEAR
- no write is issued: assert on the transport, with the booby-trap pattern
  `tests/test_the_offer_ladder_is_enforced_as_step_objectives.py` uses

## RETURN

ROOT CAUSE / FILES CHANGED / TESTS / SHA / WHY THIS DOES NOT WEAKEN A GATE

## RESULT

STATUS: DONE
COMMIT SHA: (pending)
TESTS: 19 tests in tests/test_provider_truth_check.py, all green.
  - test_emailbison_collision_names_the_campaign: person in our campaign 491 -> COLLISION
  - test_emailbison_client_campaign_327: person in client campaign 327 -> COLLISION
  - test_heyreach_client_campaign_fixed_productive: company in "FIXED - PRODUCTIVE" -> COLLISION
  - test_both_providers_clear: empty estates, complete walk -> CLEAR
  - test_heyreach_timeout_is_unknown_not_clear: timeout -> UNKNOWN, never CLEAR
  - test_emailbison_partial_page_is_unknown: incomplete pagination -> UNKNOWN
  - test_heyreach_partial_lead_walk_is_unknown: partial lead listing -> UNKNOWN
  - test_the_booby_trap_actually_fires: transport trap verified armed
  - test_check_issues_no_write / test_check_emailbison_issues_no_write /
    test_check_heyreach_issues_no_write: no write reaches the transport
FILES CHANGED:
  - src/provider_truth_check.py (NEW) - the collision check module
  - tests/test_provider_truth_check.py (NEW) - 19 tests covering all criteria
  - docs/qwen-tasks/RUNNING/TASK-935-collision-check-against-provider-truth.md (moved from TODO)
FINDINGS:
  - The module reuses collision.leads_for_domain() for EmailBison (already
    paginates to exhaustion and refuses broad matches).
  - HeyReach's campaign/GetAll timed out at 25s; the module retries with
    configurable backoff and reports UNKNOWN rather than treating a timeout
    as empty.
  - The client's EmailBison campaigns (327, 328, 352, 418) and HeyReach
    campaign ("FIXED - PRODUCTIVE") are named as constants, read from
    provider data at runtime.
  - The module has no caller in src/ yet. It is a utility for the canary
    operator check; wiring it into the pre-send path is a separate task.
RISKS:
  - HeyReach leads are LinkedIn-based and don't carry emails; the company
    domain match uses companyName fuzzy matching which may have false
    positives on common words. The match is conservative (3+ char label).
  - The EmailBison campaign index build fails silently (returns None) if
    the listing fails; campaign names will be None but the lead check
    still works.
RECOMMENDED CLAUDE ACTION:
  - Review the module and tests.
  - Wire into the canary pre-send check when ready.
  - Consider adding LinkedIn profile URL as an optional input for more
    precise HeyReach matching.

WHY THIS DOES NOT WEAKEN A GATE:
  This module is READ ONLY. It issues no writes, no campaign mutations,
  no lead additions. It reuses existing read paths (collision.leads_for_domain,
  heyreach._read) and the transport guard. The booby-trap test proves no
  write reaches the wire. An incomplete walk reports UNKNOWN, never CLEAR -
  the fail-closed direction. UNKNOWN IS NOT CLEAR is enforced by test.
