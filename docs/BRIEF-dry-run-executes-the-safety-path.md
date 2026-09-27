# BRIEF — a zero-write dry run EXECUTES the safety path

**NOT A POOL TASK, AND DELIBERATELY NOT IN `docs/qwen-tasks/TODO/`.** This is
critical-path implementation, which the operator reserved for Claude subagents on
2026-09-27. It lived in `TODO/` for about a minute until I checked whether
`claim_task.py` honours a "CLAUDE ONLY" marker in a task file. **It does not** -
there is no such filter, so any file in `TODO/` whose dependencies are met is
claimable by the next Qwen worker the 15-minute sweep reaches. A comment saying
who a task belongs to is not an access control, which is the same class of
mistake as a config block that nothing enforces. So the brief lives here and
Claude dispatches it directly.

Dispatch AFTER `TASK-364` is merged: both change `src/bisonfactory.py`.

**CLAUDE ONLY. This is critical path** (operator, 2026-09-27 night). Not for the
Qwen lane. It starts only after `TASK-364` is merged, because both change
`src/bisonfactory.py`.

## THE RULE THIS IMPLEMENTS

Operator definition, 2026-09-27 night, now recorded in `docs/OPERATING-MODE.md`:

> A dry run means **"execute the real decision and safety path without provider
> writes"**. It NEVER means "skip the safety path because `live=false`".

## THE DEFECT

`bisonfactory.stage()` returns before **both** `_refuse_copylint` and
`_refuse_sequence_gate` when `live=False`. So a zero-write run never runs the
sequence gate at all, and never runs the batch copy lint. Found by the
independent review of `TASK-426` on 2026-09-27; pre-existing, and not introduced
by that fix.

Why it matters beyond tidiness: **`TASK-425`, the one-account dry run, is the
milestone the whole vertical slice is judged on, and its acceptance criterion 3
requires offer sequencing "enforced by `sequencegate`, with a negative test",
from a run that performs zero provider writes.** As the code stands those two
requirements contradict each other — the gate only runs when writes are allowed.
So this is not a cleanup, it is the thing standing between the project and its
own acceptance test. It is also why a green dry run is currently evidence of less
than it appears to be, which is the failure mode this repository keeps paying
for: a check that did not run looks exactly like a check that passed.

## WHAT TO BUILD

A dry run runs the real decision and safety path and performs **zero provider
writes**. Concretely:

1. **`sequencegate` executes on a dry run.**
2. **A bad sequence is REFUSED on a dry run** — the refusal is the same refusal,
   for the same reason, as it would be live.
3. **A valid sequence PROCEEDS to the dry-run projection** rather than being
   refused for lack of a provider.
4. **Provider writes stay exactly zero**, and that is proven rather than assumed.
5. The same question applies to `_refuse_copylint`, which sits beside it and is
   skipped by the same early return. Treat it the same way unless you find a
   real reason it must differ — and if you find one, state it rather than
   silently doing half the job.

**What you must NOT do:** do not make the dry run perform a provider write in
order to reach the gate. Do not relax, skip or special-case any gate for the
dry-run path. Do not introduce a third mode beside dry and live. If a gate
genuinely cannot run without a provider readback, say so by name and explain
what it would take — do not fake the readback, and do not let a fixture stand in
for a provider read without saying so loudly.

## ACCEPTANCE CHECK (one check, behavioural, through the real entrypoint)

Through `bisonfactory.stage(campaign_id, live=False)` — the real production
entrypoint, not a helper:

- a campaign whose sequence violates the gate is **REFUSED**, and the refusal
  names the gate;
- a campaign whose sequence is valid **reaches the dry-run projection**;
- **the provider transport is never reached in either case.** Prove it with the
  booby-trap this repo already uses: install a transport via
  `providers.set_transport` that raises on any call, so a write arriving at all
  fails the test rather than passing quietly. `providers.request` is the single
  chokepoint every provider module goes through. See
  `tests/test_sending_live_off_blocks_only_our_new_writes.py` for the pattern.

Then **MUTATE**, because a green test proves nothing until it has been attacked:
restore the early return and confirm the intended test fails for the intended
reason, and that a different guard did not fire first. Assert the file actually
changed before running (a patch silently no-opping while the suite reports OK has
happened here), and verify the tree is byte-identical after restoring — and mind
that this tree is CRLF, so a text-mode rewrite that normalises to LF is not a
restoration.

## PROTECTED PROOFS — these must still pass afterwards

    tests/test_lead_writes_respect_the_killswitch              5
    tests/test_staging_hands_the_sequence_gate_its_inputs      12
    tests/test_sending_live_off_blocks_only_our_new_writes      6
    tests/test_staging_is_not_sending

**`test_staging_is_not_sending` is the one to read first.** This task moves work
INTO the non-live path, and that module exists to hold the line that staging is
not sending. Do not weaken it to accommodate this change; if it genuinely
conflicts, that is a finding for the operator, not a test to edit.

## BOUNDARIES

Provider writes = 0. Never call a real provider. The production freeze is in
force: no launch, activation, enrolment, attachment, resume or send. Do not touch
campaigns 487, 489 or 493. `sending.live` is off for `productive` and stays off —
note this means an EmailBison lead write is refused by the killswitch anyway, so
do not read a killswitch refusal as evidence about this task's change.

No `hasattr`, no source-text assertions. Never weaken a gate or a test. Surgical
changes only. Suite discipline: the baseline is a LIST of named failures, not a
count; diff failing test NAMES; a new named failure blocks; 228 is never a
baseline; the baseline is known to be incomplete, so report rather than adopt.

Commit and push to your own branch at every meaningful commit — two separate
calls, never chained with `&&`, and no backticks inside a `-m` message (they get
shell-interpreted and silently eat text; use a heredoc with `-F -`). Verify local
and remote SHAs agree. Do not merge to master.

Report: TASK · STATUS · FILES · SCOPE DEVIATIONS · TESTS · TEST RESULTS ·
MUTATION PERFORMED · PRODUCTION ENTRYPOINT · CONSUMER · END-TO-END EFFECT ·
LOCAL SHA · REMOTE SHA · BRANCH · MERGED? (no) · REMAINING RISK. Name the branch
and head SHA explicitly.
