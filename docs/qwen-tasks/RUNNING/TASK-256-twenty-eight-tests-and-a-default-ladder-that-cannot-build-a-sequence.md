PRIORITY: P1
DEPENDS: TASK-258

# TASK-256 — 28 tests against the threading invariant, and the default ladder that contradicts it

Measured 2026-09-22, `docs/state/SUITE-BASELINE-2026-09-22.md` section 3.1.
**The largest single cluster in the suite baseline: 28 of 111.**

## The failure

All 28 raise the same refusal:

    bisonfactory.FactoryRefused: step 3 is not a thread reply but carries a
    distinct subject ('{SUBJECT_3}' vs opener '{SUBJECT_1}')

    test_bison_campaign_write   11
    test_render_preview         11
    test_task081_thread_reply    6

The guard arrived with **TASK-219 at `4c9d63d3`, 2026-09-16** — "only the
opener owns a subject" — a deliberate tightening of the standing
EMAILBISON-COPY-REQUIREMENTS contract, which CLAUDE.md carries: *a sequence is
one conversation, same-thread follow-ups use the provider's thread_reply
rather than a new subject every step*.

**Changed contract. UPDATE THE FIXTURES, NEVER THE GUARD.** This is the same
rule TASK-250 states for the verification roles, for the same reason: a test
that goes green by weakening a standing copy contract is worth less than the
failure. Do not add an escape hatch, do not make the invariant conditional,
and do not skip the tests.

## The ladder half is NOT yours — TASK-258 owns it, and it lands FIRST

This task originally asked which of the ladder or the invariant was wrong and
said to stop rather than guess. **That question has been answered by the
operator** (Zvonimir, 2026-09-22): the ladder is wrong, the invariant stands,
and `THREAD_REPLY_PATTERNS` becomes opener-false / follow-ups-true. That work
is **TASK-258**.

So: **do not change `src/cadencelibrary.py`, and do not run beside TASK-258.**
Both tasks touch `tests/test_task081_thread_reply.py` and both touch the
threading shape; two workers there will collide. Wait for TASK-258 to land,
then start from a tree where the default is already correct.

**TASK-258 HAS LANDED AND IT ALREADY CLEARED 13 OF THE 28.** Measured on
branch `infra` immediately after integrating it, with no fixture touched:

    module                       before   after
    test_task081_thread_reply         6       0   all six, fixed by the ladder
    test_render_preview              11       4   seven cleared
    test_bison_campaign_write        11      11   unchanged - these are yours

    total                            28      15

So **your real scope is 15, not 28**, and the whole of it is in
`test_bison_campaign_write` plus four in `test_render_preview`. Re-measure
before you start rather than trusting this table - it was taken at one commit
and the register's rule is that a derived report is only as good as its last
verification.

**Do not "fix" a test that is already passing.** That is how a diff grows a
hundred lines answering to nothing, and it is the specific risk on a task
whose brief says 28 and whose reality is 15.

## Then the fixtures

Per test, the same two shapes TASK-250 uses:

- the test is **about threading** → give it a shape that satisfies the
  invariant and keep what it was asserting. `test_task081_thread_reply` is
  this; it exists to prove thread_reply survives a round trip, and it can do
  that on a compliant sequence.
- the test merely needs **a sequence** → smallest possible change, one line,
  no ceremony.

## Falsifiable requirements

1. All 28 green, with the guard unchanged. `git diff src/bisonfactory.py`
   must be empty for the invariant block at lines ~288-308.
2. **The ladder-default and no-override tests belong to TASK-258. Do not
   write them here.** If they are already present when you start, that task
   has landed and you are building on it correctly. Two workers writing the
   same test in two files is worse than neither writing it.
3. Attack it: restore one fixture to its pre-fix shape and confirm the
   invariant still refuses. A cluster this size is exactly where a guard gets
   quietly loosened to clear a number.

## Do not

- Do not weaken, gate or make optional the invariant in
  `src/bisonfactory._sequence_steps`.
- Do not edit `config/clients/*.yaml` to make tests pass. Those are operator
  decisions about live copy.
- Do not touch `src/providers/` — the production session owns it.
- Do not touch `src/cadencelibrary.py`. TASK-258 owns it.
