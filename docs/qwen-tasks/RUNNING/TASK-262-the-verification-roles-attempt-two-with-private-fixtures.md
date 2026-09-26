PRIORITY: P1
DEPENDS:

# TASK-262 — the verification roles, attempt 2: private fixtures, shared ones untouched

**This supersedes TASK-250 as the thing to work on.** TASK-250 states the
defect correctly and its "update the fixtures, not the policy" rule still
holds. What it does not say — and what killed attempt 1 — is that the phase
fixtures are SHARED.

## What happened to attempt 1, measured

`qwen-worker-r57` claimed TASK-250 (`61a2bc60`) and edited the shared phase
fixtures (`126dcfa1`), then stopped: still in `RUNNING/`, no result block. The
infra session merged it, measured the whole suite, and reverted it.

    before   11,226 tests    82 distinct failures
    after    11,346 tests   123 distinct failures      +41

    gone:   6   test_e2e 2, test_invariants 1, PII guard 3 (master's fix)
    new:   47   test_approve 14, test_push 13, test_cadence 5,
                test_generate 4, + 11 across 8 more modules

Every new failure is `'blocked' != 'eligible'` or a missing cadence key:
records that no longer verify, so every gate below them refuses.

## THE RULE FOR THIS ATTEMPT — operator, Zvonimir, 2026-09-22

> *The shared phase fixtures are the trap. Never mutate a shared fixture; give
> the migrating tests their own fixture copies, keep phase5/phase7 untouched
> for the other consumers, and run the full suite by name diff before the
> claim is marked DONE.*

Concretely:

1. **`tests/fixtures/phase2.jsonl`, `phase5.jsonl`, `phase6.jsonl` and
   `phase7.jsonl` MAY NOT BE EDITED.** Not one line. They are the shared
   baseline for modules that have nothing to do with verification roles.

2. **A test that needs deliverable-primary evidence gets its OWN fixture**,
   copied and renamed — `phase7-deliverable.jsonl` or similar — and reads
   that. The shared file keeps serving everyone else exactly as it does now.

3. **Run the FULL suite and diff BY NAME, both directions, before marking the
   task DONE.** Not a count. The baseline artifact is
   `docs/state/SUITE-BASELINE-2026-09-22.json` (82 distinct at
   `f7badaa5`); regenerate it and `comm` the two lists. **Attempt 1 did not do
   this, which is exactly how 47 new failures reached a merge.**

## Who reads what — verified, and check it again before you edit

    phase2.jsonl   test_audit, test_render
    phase5.jsonl   test_audit, test_generate, test_company_evidence_cache,
                   test_siblings_block
    phase6.jsonl   test_personas
    phase7.jsonl   test_approve, test_cadence, test_double_verification,
                   test_events

`phase7.jsonl` alone feeds four modules. That is why a one-line change to it
cost 47 failures, and it is the number to keep in mind when a copy feels like
overkill.

**Re-derive this list yourself** — `grep -rl phase7.jsonl tests/` — rather
than trusting the table. It was accurate on 2026-09-22 and this register's
first rule is that a derived report is only as good as its last verification.

## The defect itself (from TASK-250, unchanged)

Productive's verification roles changed on 2026-09-21: primary moved from
ContactOut to Deliverable, and ContactOut was removed from verification
entirely. `verification.is_sendable` recomputes from the evidence against the
CLIENT's policy, so on a `productive` record a `(contactout, reoon)` pair is
no longer a verified address and the record lands `held` where the test
expects `approved`.

**Update the fixtures, never the policy.** The roles are an operator decision
in `config/clients/productive.yaml` and asserted by
`tests/test_productive_verification_roles.py`. A test that goes green by
weakening them is worth less than the failure.

## Recover attempt 1's work rather than reinventing it

`126dcfa1` on `qwen-worker-r57` is preserved, unmerged. Its approach was
RIGHT and only its blast radius was wrong:

- evidence moves from contactout to deliverable
- a `tests/fixtures/cassettes/deliverable.json` cassette is added — **take
  this as-is, it is 302 lines of work and it is not shared state**
- `test_e2e` calls `confirm_deliverable_contract()` in setup so the waterfall
  will call deliverable

Cherry-pick or copy what applies. Just do not take its edits to the four
shared phase files.

## Falsifiable requirements

1. The ~19 verification-role failures in `test_e2e` and `test_enrich` are
   gone. Identify them by name from the baseline JSON first, so "gone" is
   checkable rather than asserted.
2. **`git diff` shows ZERO changes to `phase2/5/6/7.jsonl`.** This is the one
   that gets checked first at review.
3. Full-suite name diff in both directions, pasted into the result block:
   what went green, and **what is new**. New must be empty.
4. The baseline moves from 82 down, and the result block states the new
   number and the delta by name.
5. `tests/test_productive_verification_roles.py` still passes untouched.

## Do not

- Do not edit `phase2.jsonl`, `phase5.jsonl`, `phase6.jsonl`, `phase7.jsonl`.
- Do not edit `src/verification.py`, `src/lint.py`, `src/approve.py`, or
  `config/clients/*.yaml`. If a test cannot be fixed without one of them, that
  is a FINDING: write it in the result block and stop.
- Do not edit `src/providers/*`, `config/.env`, `scripts/*_watch_loop.py` or
  anything under `work/`.
- Do not mark DONE on a count. Requirement 3 is a list.
