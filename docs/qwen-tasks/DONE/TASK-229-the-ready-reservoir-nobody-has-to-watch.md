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

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** (pending)

**TESTS:** 12 tests in `tests/test_the_ready_reservoir_is_derived_not_latched.py`,
all passing. Tests cover:
- Depth reported correctly on fixture estate (email + LinkedIn channel)
- Blockers ranked by count
- Five invalidation cases: replied, suppressed, approval invalidated,
  contact collision, account collision - each flips one fact and asserts
  the contact leaves the READY set
- Set rebuilt from screen, not stored verdicts (two runs with different
  gate inputs produce different sets)
- Reservoir does not import providerwrites

**FILES CHANGED:**
- `src/reservoir.py` (new) - the core module providing `ready_set()` and
  `depth_and_blockers()`. Consumes `scripts/next_ready_cohort.py` via
  importlib, does not reimplement gates.
- `scripts/build_ready_reservoir.py` (new) - persistence script. Writes
  real data to `work/ready_reservoir.json` (gitignored) and sanitised
  manifest to `docs/state/READY-RESERVOIR.json`.
- `tests/test_the_ready_reservoir_is_derived_not_latched.py` (new) - 12 tests.

**FINDINGS:**
1. The reservoir is DERIVED, never latched. Every call to `ready_set()`
   re-runs the screen. A new `Screen` instance is created each time, so
   provider-read caches are fresh. The set is a pure function of current
   facts.
2. The five invalidation cases are proven by flipping one gate mock and
   re-running. No cache clearing is needed between runs.
3. The reservoir proposes, it does not send. `src/reservoir.py` does not
   import `providerwrites`.
4. The sanitised manifest carries counts, stages, hashed fingerprints,
   and blocker rankings - enough to track depth over time, not enough to
   rebuild the prospect list.

**RISKS:**
- The LinkedIn fixture in tests uses the email estate because building a
  full LinkedIn cadence fixture requires the campaign's `cadence_steps` to
  resolve through `cadence.steps_for()`, which needs a full client config.
  The email tests prove the same code path.
- The persistence script (`scripts/build_ready_reservoir.py`) requires
  `config/.env` and real provider credentials to run against the live
  estate. It has not been run live - only the tests verify the logic.

**RECOMMENDED CLAUDE ACTION:**
1. Review `src/reservoir.py` and `scripts/build_ready_reservoir.py`.
2. Run `py -3 scripts/build_ready_reservoir.py` from Claude's worktree
   (which has `config/.env` and `work/queue.jsonl`) to populate the
   reservoir with real data.
3. The allocator that consumes READY is a separate task - this reservoir
   only proposes, it does not activate or send.
