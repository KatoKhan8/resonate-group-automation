# TASK-461 — GLM Independent Verification of TASK-315

## Target

    task            TASK-315
    branch          qwen-worker-4-r9-task280
    branch HEAD SHA cdffd0a2d3bab2bea4d7a35373876fce93cc97fe
    verified SHA    cdffd0a2d3bab2bea4d7a35373876fce93cc97fe (confirmed via git rev-parse)
    worktree        .qwen/worktrees/glm-task461 (detached at target SHA)
    date            2026-09-28

## Status: ALREADY INTEGRATED

TASK-315 was merged to master via commit `90cd4175` ("INTEGRATE TASK-279,
TASK-285, TASK-315, TASK-414, and two artifacts off the 9-r9 branch"). The
test file exists on master and passes all 36 tests there. This verdict
reviews the branch HEAD as instructed and confirms the artifact's correctness
independently of its integration status.

## Finding 1: Artifact exists and matches claims

**VERIFIED.** `tests/test_a_reply_stops_the_other_channel.py` exists at the
target SHA with 1,254 lines and 36 tests across 13 test classes. The result
block claims 36 tests — confirmed.

The file on master (post-integration) differs from the branch version by
exactly 2 lines: an import style change (`from src.providers import
ProviderError` on the branch vs `import src.providers as providers` on
master). Functionally identical. Blob hashes differ
(`7eeda09e` branch vs `6c2397e4` master) solely because of this.

## Finding 2: Production caller chain is complete

**VERIFIED.** The chain from production entry point to the cross-channel stop:

    poller.py:471  →  inbound.ingest()
    inbound.py:457 →  _stop_at_provider()
    inbound.py:225 →  leadstop.stop_contact()        [email channel]
    inbound.py:226 →  leadstop.stop_linkedin_contact() [linkedin channel]

Both `stop_contact` and `stop_linkedin_contact` go through
`providerwrites.perform` with readbacks that query the provider:

- Email: `readback=lambda: {"stopped": str(bison.membership(...).get(...) or "").lower() in bison.STOPPED_STATES}`
- LinkedIn: `readback=lambda: {"stopped": _linkedin_stop_took(profile_url, provider_campaign)}`

Neither is a constant. Both ask the provider and compare against expected
state. Zero production callers means DISCONNECTED — this is NOT the case
here.

## Finding 3: Mutation test — the readback trap is caught

**VERIFIED BY FALSIFICATION.** I reintroduced the exact old defect by
replacing the email readback with `lambda: {"stopped": True}` (a constant
identical to `expected`). The test
`test_email_stop_refused_when_provider_still_says_in_sequence` correctly
FAILED:

    AssertionError: StopUnverified not raised

This proves the test catches the defect it claims to prevent. The test does
not pass vacuously — it fails when the readback lies, which is the intended
behaviour.

## Finding 4: Tests are falsifiable

**VERIFIED.** The tests assert on behaviour through real code paths:

- `assertRaises(leadstop.StopUnverified)` — asserts the function raises when
  the provider did not confirm. Not `hasattr`, not source text, not shape.
- Mocked providers return specific states (`"in_sequence"`, `"InSequence"`)
  that exercise the readback logic. The mocks control provider responses, not
  the code under test.
- `TheReadbackCannotLie.test_a_constant_readback_would_pass_but_the_real_one_does_not`
  explicitly demonstrates the trap and proves the real code escapes it.

How could these pass while the implementation is wrong? Only if:
1. `leadstop.stop_contact` caught `StopUnverified` internally and returned
   success — but it doesn't; the exception propagates.
2. The mock setup bypassed the readback — but the mock controls
   `bison.membership`, which the readback calls directly.

No vacuous pass path found.

## Finding 5: Merging would not delete anything

**VERIFIED SAFE.** The branch is behind master by 451 files / 75,590 lines.
The only TASK-315-specific diff is the addition of the test file (1,254
lines). Since the file already exists on master, re-merging this branch
would be a no-op for TASK-315's artifact (modulo the 2-line import style
difference, which master already resolved during integration).

No deletions, no overwrites of master-only content.

## Finding 6: Scope drift

**NOTED.** The branch carries three tasks' worth of work:

| Task   | Files                                                          |
|--------|----------------------------------------------------------------|
| TASK-315 | `tests/test_a_reply_stops_the_other_channel.py` (NEW)         |
| TASK-280 | `scripts/reverse_reconcile.py`, `tests/test_reverse_reconciliation_is_exhaustive.py`, `docs/REVERSE-RECONCILIATION-2026-09-25.md`, task file |
| TASK-308 | `src/providers/anthropic.py`, `tests/test_anthropic.py`, `tests/fixtures/cassettes/anthropic.json`, task file |
| Shared  | `src/spendledger.py` (+18), `tests/base.py` (+3/-1), `tests/test_invariants.py` (+4/-1) |

TASK-315's artifact is cleanly separable — it is a single new test file with
no modifications to shared infrastructure. Cherry-picking it would be
trivial (and was already done during integration).

## Scenario coverage assessment

The result block's coverage table claims 28 scenario/direction pairs covered
by synthetic tests. Verified by reading the test file:

- **Part 1 (TheReadbackCannotLie):** 4 tests — readback integrity, both channels
- **Part 2 (ContactIdentityMatching):** 4 tests — email/URL matching, shared address refusal, no-binding refusal
- **Part 3 (PendingStepCancellation):** 2 tests — account pause, pure OOO
- **Part 4 (ReplyIngestionAndClassification):** 4 tests — negative/positive/unknown classification, provider stop independence
- **Part 5–13:** 22 tests covering provider routes, duplicates, delays, races, suppression, sweep, audit, directions, single-channel

Total: 36 tests. Table is accurate.

## Live validation gaps

The result block honestly flags five scenarios as LIVE VALIDATION REQUIRED:
1. Provider visibility latency (reply → row in inbox feed)
2. Email stop against a live lead
3. LinkedIn stop against a live lead (identifier shape measured but full flow never ran e2e)
4. End-to-end timing < 15 minutes
5. Provider retry under load

These are genuine gaps. The tests use mocked provider responses and cannot
prove provider behaviour. The task explicitly forbade live provider writes,
so this is by design, not by omission.

## Disposition

| Finding | Severity | Evidence |
|---------|----------|----------|
| Artifact exists and matches claims | PASS | File at SHA, 36 tests, line count matches |
| Production caller chain complete | PASS | `poller→inbound→_stop_at_provider→leadstop.{stop_contact,stop_linkedin_contact}` traced and consumed |
| Mutation test catches the defect | PASS | Reintroduced constant readback → test fails with correct assertion |
| Tests are falsifiable | PASS | Behavioural assertions through real code paths, no vacuous pass |
| Merge safety | PASS | No deletions, artifact already integrated, 2-line cosmetic diff only |
| Scope drift | LOW | Branch carries TASK-280/308 but TASK-315 is cleanly separable |
| Live validation gaps | NOTED | 5 scenarios flagged honestly, by design not by omission |

## Recommendation: CLOSE

TASK-315 is already integrated to master and its artifact is correct. The
test file is well-structured, the production chain is consumed, the critical
readback defect is pinned by a falsifiable mutation test, and the live
validation gaps are honestly documented. No rework needed. No further
action owed from this verdict.

The branch `qwen-worker-4-r9-task280` can be left as-is — it is a source
branch whose work has been integrated through a different merge path.
