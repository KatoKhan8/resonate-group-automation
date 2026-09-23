PRIORITY: P1
DEPENDS:

# TASK-257 — a per-seat daily LinkedIn ledger, where a shared seat can never prove ROOM

`src/seatledger.py`. Per seat, per day: what THIS system did, and an explicit
UNKNOWN for what the client did on the same seat.

## The situation this has to model honestly

ISSUE-010, re-measured 2026-09-20: HeyReach has 41 accounts, 34 active, 33
with valid auth, and **0 unallocated — all 33 are already in campaigns, mostly
the client's. We own 4 of 86.** The connection limit is 40/day per seat.

So most seats are SHARED. The client works them through their own campaigns,
on a workspace-wide key, and **their actions are not in our action ledger and
cannot be got at.** The 2026-09-22 handoff has the live version of this: 33
campaigns IN_PROGRESS, one per attested seat, connection requests at 0.

## The contract — mirror `senderheadroom`, and be stricter

`src/senderheadroom.py`'s refusal contract is load-bearing and CLAUDE.md says
so. Use its vocabulary, because an operator already knows how to read it:

    FULL      this seat will take no more of OUR actions today
    ROOM      this seat provably has capacity
    REFUSED   cannot be proven either way, with a reason naming what is missing

**The asymmetry is the whole design.** Our ledger is a LOWER BOUND on a seat's
use: it can only undercount, because it sees our actions and not the client's.
Therefore:

    ours >= 40                    -> FULL. Provable from our ledger alone.
                                     A lower bound at the ceiling is still at
                                     the ceiling.
    seat is EXCLUSIVELY ours      -> ROOM is computable: 40 - ours.
    seat is SHARED with the client-> REFUSED, ALWAYS, with reason
                                     `client_usage_unknown`.

**And the second line of that is different from `senderheadroom` in a way that
must not be smoothed over.** There, REFUSED means *not yet proven* — a fresher,
more complete walk can turn it into ROOM. Here, on a shared seat, REFUSED is
**permanent**: no walk of our own ledger can ever prove room on a seat somebody
else is also working, because the missing quantity is unobservable rather than
unwalked. A future session WILL try to close that gap by inferring client usage
from HeyReach's campaign counters. Say in the module docstring that it cannot
be done and why: the counters are per campaign, we cannot enumerate the
client's 82 campaigns reliably, and a seat's daily total is not derivable from
the campaigns we can see. **A guessed denominator is worse than a missing one.**

## Shared or exclusive is provider truth, not a guess

A seat is EXCLUSIVE only when a fresh provider read shows every campaign
touching it is one of ours. Anything else — a stale read, a campaign we cannot
attribute, a paging error — is SHARED. Fail closed: treating a shared seat as
exclusive is what produces a confident wrong ROOM, and ROOM is the answer that
licenses an action.

Attribution comes from `provider_truth` / `PROVIDER-CAMPAIGNS.json`, which is
the repo's existing answer to "what does the provider actually say". Do not
add a second source.

## Build

    daily(seat_id, day, rows=None)    -> {"ours": int, "client": "UNKNOWN"|0,
                                          "verdict": FULL|ROOM|REFUSED,
                                          "reason": str, "limit": 40}
    ledger(day, rows=None)            -> every attested seat, that shape
    report(day)                       -> the operator table

`ours` comes from `actionledger.count_on(day, channel="linkedin",
sender_id=seat)`. **Do not write a second counter.** That function already
collapses to the latest row per key and already defaults `states` to
`SENT + ATTEMPTED + UNRESOLVED` — the three that either reached somebody or
might have — and its docstring explains why a cap counting only confirmed
sends lets an unresolved attempt buy another attempt. That reasoning is
exactly as true per seat.

Pass `workspace` through. Tenancy outranks nearly everything here and
`count_on` carries a comment about one client's actions having consumed
another's ceiling.

`client` is the literal string `"UNKNOWN"` on a shared seat and `0` on an
exclusive one. **Never `None`, never absent, never 0-as-a-placeholder.** The
register's standing rule is that missing evidence is never positive evidence,
and an absent field reads as zero to the next person who writes a sum.

## Falsifiable requirements — tests first

1. A seat with 3 of our actions and no client campaign: `ours` 3, `client` 0,
   verdict ROOM, remaining 37.
2. The same seat with ONE client campaign on it: `ours` 3, `client`
   `"UNKNOWN"`, verdict **REFUSED**, reason `client_usage_unknown`. Remaining
   is absent or `"UNKNOWN"` — **assert it is not a number.** This is the test
   that stops the next person computing `40 - 3`.
3. A shared seat with 40 of our own actions: verdict **FULL**, not REFUSED.
   A lower bound at the ceiling is still at the ceiling, and this is the one
   case where a shared seat gives a definite answer.
4. A stale or incomplete provider read makes every seat SHARED, not exclusive.
   Break the read deliberately and assert no seat comes back ROOM.
5. `ours` counts ATTEMPTED and UNRESOLVED, not only SENT. Build a ledger with
   one of each and assert the count is 3, not 1.
6. Two workspaces on one seat do not pool: a count scoped to workspace A does
   not see workspace B's rows.
7. A day boundary is the same calendar day `count_on` uses. Do not introduce a
   second definition of "today" — `accounts_opened_on`'s docstring warns that
   two definitions in one gate is a defect waiting for a timezone.
8. **The module never writes.** It is a reader over the action ledger and the
   provider truth file. No new state file, no cache.

## Do not

- Do not infer client usage from anything. Not campaign counters, not seat
  activity, not a delta between reads.
- Do not edit `src/providers/heyreach.py` — the production session owns it.
- Do not add a `linkedin_per_day` cap enforcement path. `executionguard` and
  `pilotcaps` own caps; this module REPORTS. A reader that starts refusing
  actions is a second gate disagreeing with the first.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 48249b77eaa429c897a36e03f5281cb103c505a9
- **TESTS:** 24 tests in `tests.test_the_linkedin_seat_ledger_refuses_room_on_a_shared_seat` — all pass. Covers all 8 falsifiable requirements: exclusive seat ROOM, shared seat REFUSED with non-numeric remaining, shared seat FULL at 40+, stale provider truth → no ROOM, ATTEMPTED+UNRESOLVED counted, workspace scoping, day boundary alignment, no writes.
- **FILES CHANGED:**
  - `src/seatledger.py` (new) — the module: `daily()`, `ledger()`, `report()`. Mirrors senderheadroom's FULL/ROOM/REFUSED contract. Uses `actionledger.count_on` directly. Reads PROVIDER-CAMPAIGNS.json for attribution. Never writes.
  - `tests/test_the_linkedin_seat_ledger_refuses_room_on_a_shared_seat.py` (new) — 24 tests covering every falsifiable requirement.
- **FINDINGS:**
  - The module has no production caller yet. `grep -rn seatledger src/` returns only the module's own file. This is expected: the task specifies a REPORTING module, not a gate. The first consumer will be a diagnostic or operator report, not an execution path.
  - With the live PROVIDER-CAMPAIGNS.json (86 total campaigns, 4 ours), every attested seat will be SHARED and every verdict will be REFUSED or FULL. ROOM is only reachable when campaigns_total == campaigns_created_by_resonate, which is not the current state.
  - The `client` field is the literal string `"UNKNOWN"` on shared seats and integer `0` on exclusive seats. Never None, never absent.
- **RISKS:**
  - The attribution logic is coarse: if total > ours, ALL seats are SHARED. A future improvement could enumerate client campaign senders and determine per-seat exclusivity, but the task explicitly forbids inferring client usage from anything.
  - The module loads PROVIDER-CAMPAIGNS.json from disk by default. Tests pass the provider_truth dict directly to avoid file I/O.
- **RECOMMENDED CLAUDE ACTION:** Review and integrate. The module is a reader with no production caller — wiring it into a diagnostic report or operator table is the natural next step.
