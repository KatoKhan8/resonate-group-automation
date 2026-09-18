# TASK-232 - thirty-three accounts held by a question nobody asked

## The measurement

`docs/THE-ESTATE-IS-SATURATED-NOT-UNAPPROVED-2026-09-18.md`. Every contact in
the estate, cross-tabulated by the first gate that stops it:

    65  stop  somebody at this account is mid-sequence right now
    33  hold  a campaign at this account ended early (stopped) and the status
              does not say whether we stopped it, they unsubscribed, or
              something else
    15  stop  1+ person(s) at this account have already replied or been marked
              interested; the account is answered
     2  hold  an address at this account bounced

The 65 and the 15 are facts and they refuse correctly. **The 33 are an
UNKNOWN wearing a refusal**, and they are about a third of everything blocked
in the estate.

## Why this is worth a task

The whole estate is saturated by the client's own outreach, so cohort growth
is a sourcing problem - except for these 33, where the inventory may already
exist and is being held by a question. `collision.account_policy` sees a
`stopped` membership, cannot tell WHY it stopped, and holds. That is the right
default and it is not an answer.

## The objective

Resolve the cause of a `stopped` membership from provider truth, and let a
HOLD become either a definite STOP or a CLEAR.

Falsifiable requirements:

1. For an account whose only adverse signal is a `stopped` membership,
   determine the cause from evidence that exists: the events feed
   (`/api/events` normalises 100% of real events now - EMAIL_SENT,
   LEAD_REPLIED, EMAIL_BOUNCED, EMAIL_SEND_FAILED, LEAD_UNSUBSCRIBED,
   UNTRACKED_REPLY_RECEIVED), the reply feed, the lead's own counters, and the
   campaign's state.
2. Classify each into: **UNSUBSCRIBED** (definite STOP, forever),
   **REPLIED/INTERESTED** (definite STOP - the account is answered),
   **BOUNCED** (STOP for that address), **WE STOPPED IT** (our own
   `stop_lead`, recorded in the action ledger - not a prospect signal),
   **SEQUENCE FINISHED** (ran to the end, nobody replied), or **STILL
   UNKNOWN**.
3. **STILL UNKNOWN keeps the HOLD.** This is the requirement that outranks
   the feature. A HOLD that becomes CLEAR because nobody could find evidence
   of a refusal is precisely the failure the gate exists to prevent: missing
   evidence is never positive evidence. The task is only worth doing if the
   UNKNOWN branch is honest.
4. READ-ONLY. It reports; it does not change `collision`'s verdicts, does not
   write canonical state, and does not contact anybody. Wiring the resolution
   into the account gate is a separate decision, because it WIDENS who may be
   contacted and that is not a refactor.
5. Report the split: how many of the 33 resolve to each class, and for the
   ones that resolve to CLEAR, exactly what evidence cleared them. An operator
   has to be able to check a sample by hand.

## Tests required

Each classification from a fixture: an unsubscribe event, a reply event, a
bounce, our own ledger stop, a finished sequence, and - the important one - a
`stopped` membership with NO corroborating evidence, which must come back
STILL UNKNOWN and keep the hold. Assert the UNKNOWN case explicitly rather
than letting it fall out of a default.

Break-proof it: make the evidence lookup return nothing for every account and
confirm every one of the 33 reports STILL UNKNOWN rather than CLEAR.

## Boundaries

No provider WRITE. No credit spend - the events and reply feeds are GETs, and
`enrich.COSTS` has no entry that this needs. No canonical mutation. Do not
touch `collision.account_policy`'s decision function in this task.

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 2a8f57e9

**TESTS:** 21 tests in `tests/test_stopped_cause_resolution.py`, all passing.
Plus `tests/test_our_own_staging_is_not_their_history` (38 tests, all passing).
One pre-existing failure in `tests/test_invariants` (`test_emailbison_posts_only_to_routes_it_declares`)
is unrelated to this task and exists on origin/master.

**FILES CHANGED:**
- `src/stoppedcause.py` (new) - READ-ONLY resolver module
- `tests/test_stopped_cause_resolution.py` (new) - 21 tests

**FINDINGS:**

The module `src/stoppedcause.py` resolves the cause of a `stopped` membership
from evidence that already exists:

1. **Events feed** (`/api/events` via `bisonevents.normalise`): checks for
   `unsubscribed`, `replied`, and `bounced` event kinds.
2. **Membership counters**: the lead's own `replies` count, `status: replied`,
   and `interested` flag.
3. **Lead status**: `bounced` lead status.
4. **Action ledger**: our own `bison.stop_lead` operations settled as `sent`
   or `attempted`.
5. **Campaign state**: `sequence_finished` status with no adverse signal.

Classifications (in priority order):
- **UNSUBSCRIBED**: definite STOP, forever
- **REPLIED_INTERESTED**: definite STOP - the account is answered
- **BOUNCED**: STOP for that address
- **WE_STOPPED_IT**: our own action, not a prospect signal
- **SEQUENCE_FINISHED**: ran to the end, nobody replied
- **STILL_UNKNOWN**: none of the above. **The hold stays.**

THE REQUIREMENT THAT OUTRANKS THE FEATURE is enforced:

- `STILL_UNKNOWN` is an explicit arm of the resolver, not a default fall-through.
- The break-proof test creates 33 accounts with NO evidence from any source
  and asserts ALL 33 report `STILL_UNKNOWN`, not `CLEAR`.
- Missing evidence is never positive evidence.

The module is READ-ONLY: it reports, it does not change `collision`'s
verdicts, does not write canonical state, and does not contact anybody.
Wiring the resolution into the account gate WIDENS who may be contacted and
is a separate decision, not a refactor.

**LIVE MEASUREMENT OWED:** The module is built and tested against fixtures.
Running it against the live 33 accounts requires a real events fetcher
wired to `/api/events` with cursor pagination. That is a separate wiring
task - this module provides the `events_fetch` callback interface for it.
The split (how many of the 33 resolve to each class) cannot be reported
from this worktree because live provider reads are Claude's, run from
Claude's worktree. The module is ready for that measurement.

**RISKS:**
- The events fetcher interface (`events_fetch(lead_id, campaign_id)`) needs
  a real implementation wired to `/api/events` with cursor pagination. The
  module provides the interface; the implementation is owed.
- The action ledger match uses `campaign_id` and `lead_id`/`contact_key`.
  If the ledger's key shape changes, the match may need updating.

**RECOMMENDED CLAUDE ACTION:**
1. Wire a real `events_fetch` implementation that calls `/api/events` with
   cursor pagination, filtering by lead_id and campaign_id.
2. Run the resolver against the live 33 HOLD accounts and report the split.
3. For any account resolving to CLEAR (SEQUENCE_FINISHED with no adverse
   signal), document exactly what evidence cleared it so an operator can
   check a sample by hand.
4. Decide whether to wire the resolution into `collision.account_policy` -
   this WIDENS who may be contacted and is a separate decision.
