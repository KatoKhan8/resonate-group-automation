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

## RESULT

**STATUS: DONE**

**ARTIFACT KIND:** code + test

**ROOT CAUSE:** No module existed that checks both EmailBison and HeyReach
from the providers themselves (not the local ledger) for person and company
collisions across both our and the client's campaigns. The local ledger says
"never contacted" about people who have been emailed six times because the
ingestion code had zero production callers.

**FILES CHANGED:**
- `src/collisioncheck.py` (NEW) — the collision check module
- `src/providers/heyreach.py` — added `company_name` to `campaign_leads` output
  (backward-compatible, one line)
- `tests/test_collision_check_against_provider_truth.py` (NEW) — 15 tests

**TESTS:** 15/15 pass in 0.002s. All five required arms covered:
1. Person in our campaign → COLLISION naming it ✓
2. Person in client campaign → COLLISION naming it ✓
3. Person in neither, complete walk → CLEAR ✓
4. Incomplete walk (timeout) → UNKNOWN, never CLEAR ✓
5. No write issued → booby-trap on transport ✓

Additional tests: company domain matching, multi-page pagination, combined
verdict logic.

**SHA:** 0aeb10c7

**WHY THIS DOES NOT WEAKEN A GATE:**
- READ ONLY. No write route is added or called. The booby-trap test proves
  no provider request is a write.
- Uses existing provider modules (`bison.find_lead_by_email`,
  `heyreach.campaigns`, `heyreach.campaign_leads`) and `providers.request`.
  No second HTTP path.
- Paginates to exhaustion. `_all_heyreach_campaigns` and `_all_campaign_leads`
  compare walked count against `totalCount` and raise on mismatch.
- Timeouts retried with backoff (3 attempts). Exhausted retries → UNKNOWN.
- UNKNOWN is never collapsed to CLEAR. The combined verdict is
  UNKNOWN > COLLISION > CLEAR.
- The one-line change to `campaign_leads` adds `company_name` to the return
  dict. Existing callers ignore unknown keys; no test broke.

**CALLER:** This module is an operator tool for the first canary check.
It has no automated caller yet — wiring it into the canary pipeline is a
separate task. `grep -rn collisioncheck src/` returns only self-references.
The artifact is the module and its tests.

**RISKS:**
- HeyReach walk is expensive (all campaigns × all leads). For the current
  estate (~82 campaigns) this is manageable but not cheap.
- Company name matching uses domain-label substring match (e.g., "acme" in
  "Acme Corporation"). False positives are acceptable (err on side of
  caution); false negatives would be a problem but the label is distinctive
  enough for real company names.
- 3 pre-existing `test_invariants` failures (about `reviewapproval` barrier
  checklist) are unrelated to this change.
