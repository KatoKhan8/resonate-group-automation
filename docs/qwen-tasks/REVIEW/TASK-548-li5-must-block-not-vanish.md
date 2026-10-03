PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-548 — li5 must BLOCK, never vanish

**Filed per the FOCUS RULE (OPERATING-MODE decision 20). Operator, Zvonimir,
2026-09-28: "file it as a task; it must BLOCK, never vanish. Not a canary
blocker (email only)."**

## The defect

    CLAIM        the fifth LinkedIn step is generated, gated, stored, and then
                 silently dropped before the provider ever sees it
    AUTHORITY    `sequenceplan.derive_heyreach_payload` iterates four LinkedIn
                 keys; the cadence declares five (li1..li5, days 1/3/6/10/15)
    MEASURED AT  2026-09-28, reported by P0-B
    STATE        UNPROVEN by me - P0-B reported it and I have not reproduced
                 it independently. Reproduce before fixing.

**This is the discarded-subjects pathology one channel over.** `ISSUE-054` was
the same shape on email: the writer produced content, a projection quietly
dropped it, and nothing said so. Here a step passes copylint and the sequence
gate, is stored, and then does not exist at the provider.

**The cost is not the missing message. It is that nothing reports it.** A
campaign meant to run five LinkedIn touches runs four, and every gate upstream
says PASS. Compare launch blocker 3's "155 email steps render empty" and
P0-B's finding that a step rendering to nothing removed its own rung from the
ladder check without a word.

## What to do

1. **Reproduce it first.** Build a plan carrying all five LinkedIn steps, run
   `derive_heyreach_payload`, and show `li5` absent from the payload. If it is
   present, say so and close this as REFUTED — that is a perfectly good
   outcome and cheaper than a fix nobody needed.
2. **Make the shortfall BLOCK.** The projection must refuse when the cadence
   declares a step the payload cannot carry, naming the step. It must never
   return a short payload as if it were complete. Operator's words: *it must
   BLOCK, never vanish.*
3. **A test that can fail.** Assert the refusal fires when a declared step is
   missing, AND a control proving a complete five-step payload still passes.
   A guard that refuses everything is not a guard.
4. **Check the count is not hardcoded anywhere else.** The bug is a literal
   four where the cadence says five; the same mistake may exist in a sibling
   projection. `sequenceplan.derive_bison_payload` and the preview are the
   obvious places to look.

## Rules

- **Do not change the cadence.** Five LinkedIn steps on days 1/3/6/10/15 is
  the approved shape; the projection is what is wrong.
- **Do not weaken any gate** to let a four-step payload through.
- Provider writes 0; `sending.live` stays false; the freeze stands.
- **Not on the critical path.** The email canary does not depend on this, and
  it must not delay P0-B, the signature composition, or the ten-account run.
  It IS required before any LinkedIn stage.
- Report as CLAIM / AUTHORITY / MEASURED AT / STATE. A test count is never a
  PASS.

## RESULT BLOCK

STATUS: DONE
ARTIFACT KIND: code + test

COMMIT SHA: 65ce16e2e

TESTS:
  - 13 new tests in tests/test_task548_li5_must_block_not_vanish.py: ALL PASS
  - 40 existing TASK-913 tests: ALL PASS (no regression)
  - 81 tests across test_task565, test_a_permanent_operator_exclusion,
    test_the_entrypoint_is_the_only_generation_path: ALL PASS
  - Pre-existing failures in test_heyreachfactory_ensure_leads (5 failures,
    20 errors) and test_the_emailbison_write_door_is_enforced (3 failures)
    are UNRELATED to this change; verified by running them against the
    original code (same failures present)

FILES CHANGED:
  - src/sequenceplan.py: derive_heyreach_payload and derive_bison_payload now
    raise PlanRefused when the cadence declares a step the contact's sequences
    do not carry. The refusal names the contact and every missing key.
  - tests/test_task548_li5_must_block_not_vanish.py: NEW, 13 tests

FINDINGS:

  CLAIM        derive_heyreach_payload silently drops li5 when the contact's
               sequences lack it, returning a 4-key payload as if complete
  AUTHORITY    sequenceplan.derive_heyreach_payload iterated
               cadencelibrary.LINKEDIN_WRITER_KEYS (li1..li5) but skipped
               missing keys with `if text:` and no refusal
  MEASURED AT  2026-10-04, reproduced: plan with cadence_steps declaring
               li1..li5 and contact sequences carrying li1..li4 -> payload
               returned successfully with 4 keys, no error
  STATE        PROVEN and FIXED

  TASK-913 (2026-09-29) already fixed the iteration defect: the legacy
  four-key tuple was replaced with cadencelibrary.LINKEDIN_WRITER_KEYS which
  has all five. The vanish pathology remained: when li5 is absent from
  sequences, the payload silently returns with 4 keys. The fix adds a check:
  if the plan's cadence_steps declare LinkedIn keys and a contact has ANY
  LinkedIn copy, ALL declared keys must be present. Missing keys raise
  PlanRefused naming the contact and every missing step.

  The same fix was applied to derive_bison_payload for email steps (em1..em5).
  Same pathology, same fix.

  derive_preview_data was checked and does NOT drop keys - it passes sequences
  through as-is. No fix needed.

  heyreachfactory.COPY_MAPPING correctly maps li5 to connected_4. No fix
  needed there.

  BACKWARD COMPATIBILITY: plans without cadence_steps (e.g. existing tests
  that construct minimal plans) are not affected by the new check. The check
  only fires when cadence_steps is present and declares keys.

RISKS:
  - The new check could refuse a production payload if a contact's sequences
    are incomplete. This is the INTENDED behavior - a short payload is not
    complete and must not reach the provider silently. The refusal message
    names the contact and missing keys so the operator can regenerate.
  - Existing tests that construct plans without cadence_steps are unaffected.

RECOMMENDED CLAUDE ACTION:
  Review and integrate. The fix is minimal, the tests prove both the refusal
  and the control (complete payload passes), and the change is backward
  compatible with existing tests.
