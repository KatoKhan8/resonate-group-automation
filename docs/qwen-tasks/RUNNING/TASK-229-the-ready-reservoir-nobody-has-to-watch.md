# TASK-229 - the READY reservoir nobody has to watch

## Where this comes from

`scripts/next_ready_cohort.py` answers "who could go live right now" by
walking every contact through every gate, on demand, in one pass. Read
2026-09-18 after the US cohort went live:

    EMAIL     ALREADY_LIVE 15   READY_NOW 0   NEAR_MISS 0   blocked 36
    LINKEDIN  ALREADY_LIVE  3   READY_NOW 0   NEAR_MISS 7   blocked 71

That screen is correct and it is a REPORT. Production still waits for a person
to run it, read it, and decide. The goal is a reservoir an allocator can draw
from without anybody watching a screen.

## The objective

A durable, derived READY set: `source -> qualify -> enrich -> verify ->
approve -> READY`, with READY recomputed rather than latched.

Falsifiable requirements:

1. A function that returns the current READY set per channel, with the reason
   each candidate is READY - not merely that it is. It must be built by
   RUNNING the existing screen, not by reimplementing the gates. Two opinions
   about who is safe to contact is how they drift, and
   `next_ready_cohort` already asks every gate in the order the guard asks
   them. It exposes `--json`; consume that.
2. **DERIVED, NEVER LATCHED.** A contact that was READY an hour ago and has
   since replied, been suppressed, had its approval invalidated by a copy
   edit, or had its account collide must NOT still be READY. Prove it with a
   test per case: flip each fact and assert the contact leaves the set.
   `approve.sync_state` and `approval.is_approved` already work this way and
   the docstring there explains why a latched boolean is wrong.
3. The reservoir reports its own DEPTH and its own BLOCKERS, ranked: how many
   are READY, and for everybody who is not, the FIRST gate that stops them and
   how many it stops. The current screen already computes this; the point is
   to persist it so depth over time is answerable.
4. **It proposes, it does not send.** No provider write, no activation, no
   campaign mutation. The allocator that consumes it is a separate task and
   consuming from READY is still subject to every execution-boundary recheck.
5. Persisted state goes in `work/` (gitignored, it names real people) with a
   SANITISED manifest suitable for `docs/state/` - counts, stages and a hashed
   fingerprint, enough to know whether the estate changed, deliberately not
   enough to rebuild the prospect list. `scripts/durable_state.py` is the
   pattern.

## What this must not do

- Do not approve anything. Approval is a human act and the accountability gate
  in `src/approval.py` exists because 84 approvals stamped `by: "claude"` were
  revoked. `is_accountable_approver` refuses a bare token.
- Do not weaken, skip or reorder a gate to increase depth. A reservoir of
  people who are not safe to contact is worse than an empty one.
- Do not cache a gate verdict across a run without a freshness rule. A stale
  CLEAR is the exact shape of the defect this repository keeps finding.

## Tests required

Depth is reported correctly on a fixture estate. Each of the five
invalidation cases in requirement 2 removes a contact. The set is rebuilt
from the screen rather than from stored verdicts - assert that by changing a
gate's input and confirming the set moves without anybody clearing a cache.

## Boundaries

No provider write. No credit spend. No canonical mutation.
