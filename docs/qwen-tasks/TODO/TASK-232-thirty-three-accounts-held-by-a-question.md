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
