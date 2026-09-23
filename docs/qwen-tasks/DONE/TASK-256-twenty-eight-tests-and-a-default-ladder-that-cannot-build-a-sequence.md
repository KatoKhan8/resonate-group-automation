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

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** a290823c
- **TESTS:**
  - `test_bison_campaign_write`: 15/15 pass (was 4/15, 11 failures fixed)
  - `test_render_preview`: 29/29 pass (was 25/29, 4 failures fixed)
  - `test_task081_thread_reply`: 26/26 pass (was already 26/26 after TASK-258)
  - Total scope was 15 tests, not 28: TASK-258 cleared 13 before this task
    started (test_task081_thread_reply 6→0, test_render_preview 11→4,
    test_bison_campaign_write unchanged at 11).
  - Broader run: 251 tests across 9 related modules, 249 pass. The 2 failures
    in test_invariants are pre-existing (ProviderError import invariant and
    bison route invariant) and unrelated to this task's changes.
- **FILES CHANGED:**
  - `tests/test_bison_campaign_write.py`: thread_reply_pattern changed from
    `[False, True, False]` to `[False, True, True]`. Three assertion sites
    updated (test_threading_is_false_true_true, readback in
    test_write_three_steps_readback_matches, module docstring). The fixture
    now satisfies the invariant: opener owns the subject, both follow-ups are
    thread replies.
  - `scripts/render_preview.py`: 14 email fixture approvals updated across
    three fixtures (_fixture_rec_email, _fixture_rec_email_second,
    _fixture_rec_email_missing). Each approval now carries a real fingerprint
    computed by `approval.fingerprint()` over the actual step content, and
    `"by": "operator"` so `is_accountable_approver` passes. The placeholder
    fingerprints ("fixture-approve-emN") never matched the computed hash and
    had no "by" field, so `_certified_copy` returned None for every step,
    making the preview report MISSING COPY for all emails.
- **FINDINGS:**
  - `git diff src/bisonfactory.py` is empty: the threading invariant at
    lines ~288-308 is unchanged.
  - Attack verified: restoring the pre-fix pattern `[False, True, False]`
    causes `_sequence_steps` to refuse with the original error message
    ("step 3 is not a thread reply but carries a distinct subject"). The
    guard is load-bearing and was not loosened.
  - The render_preview failures were NOT about threading. They were about
    email fixture approvals that could never certify: placeholder
    fingerprints that were never computed from the content, and no `by`
    field for `is_accountable_approver`. The HeyReach fixtures have the
    same placeholder pattern but go through a different code path
    (`heyreachfactory.custom_fields_for`) that does not call
    `_certified_copy`, which is why those tests passed.
- **RISKS:**
  - The edge-case email fixtures in render_preview.py (lines ~1400-1735)
    still carry placeholder fingerprints ("edge-approve-emN") without "by"
    fields. These are not among the 15 failing tests and the edge-case
    tests pass because they test structural properties (greeting rendering,
    name extraction) rather than approved copy content. A future task that
    asserts on approved copy in edge-case previews will hit the same wall.
- **RECOMMENDED CLAUDE ACTION:** Integrate. The invariant is unchanged, the
  fixtures satisfy it, and the attack confirms the guard still refuses the
  pre-fix shape.
