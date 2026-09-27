PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-358 - CheapVerifier exists on a branch and is not in the waterfall

Found by TASK-347 while it was blocked. Verified independently on master
2026-09-26.

## The two halves, and fixing one without the other achieves nothing

**1. The module is not on master.** `src/providers/cheapverifier.py` - 1,141
lines, written against the live API - exists only on branch
`worktree-agent-a9fe2f7a7ad9343aa` (commits `a5d50144`, `01c45d9d`). It is not on
master and not on any worker branch.

**2. The waterfall does not know it exists.** `src/waterfall.py:236` declares the
`email_verification` stage's providers as **ContactOut, Deliverable and Reoon.**
CheapVerifier is absent, so `waterfall.record_step` raises
`WaterfallViolation: cheapverifier is not part of the email_verification
waterfall` on the first paid call. `01c45d9d`'s own commit message records exactly
that failure.

So cherry-picking the module alone reproduces a known failure. Both halves land
together or neither does.

The credential is already present (`CHEAPVERIFIER_API_KEY` in `config/.env`) and
`config/clients/productive.yaml` already declares its budget
(`total: 100000, per_day: 95000, per_run: 10000`), so the operator's intent to use
it is on record.

## This is NOT blocking email verification

Three providers are already registered for `email_verification`. Nothing is
stalled waiting on this; CheapVerifier is a **cost** improvement, not a
capability. Do not present it as unblocking anything.

## Build

    src/providers/cheapverifier.py   cherry-pick from the branch, BY PATH.
    src/waterfall.py                 MODIFY - register it in the
                                     email_verification providers tuple.
    tests/test_cheapverifier_is_part_of_the_waterfall.py   NEW

**Cherry-pick by path, never merge the branch** - it is an agent worktree branch
and carries unrelated work.

## Where it goes in the order matters, and it is a product decision

`PROVIDER-ROUTING-POLICY.md` is the standing provider order, set by the operator
on 2026-09-16, and it is *"a PRODUCT priority rather than a cost optimisation"*:
ContactOut first whenever capable, then its cache, then the free crawler, then
Grok, then other paid providers, then Claude.

**Read `waterfall.describe()` before changing `src/waterfall.py`** - CLAUDE.md
says so explicitly, and it already encodes most of this policy.

**Do not place CheapVerifier ahead of ContactOut** to save money. That would
invert a policy the operator set deliberately. Place it among the other paid
providers, and if the code makes the right position ambiguous, put the question
under FINDINGS rather than choosing.

## Acceptance - RUN each, paste real output

1. The module imports and its entry point is callable:

    py -3 -c "import sys;sys.path.insert(0,'.');from src.providers import cheapverifier as cv;\
    print([x for x in dir(cv) if not x.startswith('_')][:12])"

2. **The WaterfallViolation is gone.** This is the whole task, so prove the thing
   that failed now passes:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import waterfall as W;\
    d=W.describe();\
    provs=[p['provider'] for p in d[W.EMAIL_VERIFICATION]['providers']];\
    assert 'cheapverifier' in provs, provs;\
    print('email_verification order:',provs)"

   Name the real shape if `describe()` differs - read it, do not assume.

3. **ContactOut is still first.** Assert its index is before CheapVerifier's. A
   test that only checks membership would let the policy be inverted silently.

4. **A fixture call records a waterfall step without raising**, and writes a
   ledger row through `enrich`'s `spend()` so it is visible to the audit.

5. **No live call.** Fixtures only. CheapVerifier has a real balance and this task
   may not spend a credit of it. If you believe a live call is required, stop and
   report it as LIVE VALIDATION REQUIRED.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt`.

## What this task may NOT do

- Do not merge `worktree-agent-a9fe2f7a7ad9343aa`. Cherry-pick by path.
- Do not reorder the waterfall to put a cheaper provider first.
- Do not make a live verification call. Do not spend a credit.
- Nothing sent, nothing activated.
