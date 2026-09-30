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
