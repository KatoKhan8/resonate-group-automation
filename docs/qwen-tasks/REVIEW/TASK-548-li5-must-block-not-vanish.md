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
    STATE        REFUTED as a current defect (TASK-913 already fixed the
                 iteration), but the BLOCKING GUARD was missing and is now
                 added.

**TASK-913 REWORK already fixed the iteration.** Measured 2026-09-29:
`derive_heyreach_payload` now iterates `cadencelibrary.LINKEDIN_WRITER_KEYS`
which is `("li1", "li2", "li3", "li4", "li5")` - all five keys. The test
`test_heyreach_payload_consumes_li1_li5` passes, proving li5 is present in
the payload when the contact's sequences carry it.

**But there was no guard preventing a future regression.** If a contact's
sequences were missing li5 (or any other declared step), the projection would
silently drop it and return a short payload as if it were complete. That is
the discarded-subjects pathology one channel over (ISSUE-054 on email).

## What was done

1. **Reproduced and verified the fix.** Built a plan carrying all five
   LinkedIn steps, ran `derive_heyreach_payload`, and confirmed li5 is
   present. The defect is REFUTED as a current issue.

2. **Made the shortfall BLOCK.** Both `derive_heyreach_payload` and
   `derive_bison_payload` now refuse when a cadence-declared step is missing
   from a contact's sequences. The refusal names the missing step and the
   contact, so the operator can see what vanished and why.

   The guard only fires when `plan.cadence_steps` explicitly declares the
   steps. Test fixtures without `cadence_steps` retain the old silent-skip
   behaviour, because they have no declaration to violate.

3. **Tests that can fail.** Nine new tests in
   `tests/test_task548_li5_must_block.py`:
   - Control: complete five-step payload passes (both LinkedIn and email)
   - Refusal: missing li5 fires PlanRefused naming the step and contact
   - Refusal: missing li3 fires PlanRefused
   - Refusal: missing multiple steps names all of them
   - Cadence-driven: when cadence declares three steps, only three are
     expected
   - Cadence-driven refusal: cadence declares five, contact has four, refuses
   - Same three tests for email (em1-em5)

   All 60 affected tests pass (TASK-548, TASK-913, entrypoint tests).

4. **Checked the count is not hardcoded elsewhere.** Both
   `derive_heyreach_payload` and `derive_bison_payload` now use the same
   guard pattern. The preview (`derive_preview_data`) does not project steps,
   only reads them from the plan, so it is unaffected.

## RESULT BLOCK

    STATUS       DONE
    COMMIT       7f70599b
    TESTS        60 tests pass (9 new TASK-548 tests, 40 TASK-913 tests,
                 11 entrypoint tests)
    FILES        src/sequenceplan.py (derive_heyreach_payload,
                 derive_bison_payload: added blocking guards)
                 tests/test_task548_li5_must_block.py (new, 9 tests)
                 tests/test_task913_writer_contract_five_plus_five.py
                 (test 13 updated to document conditional refusal)
    FINDINGS     The defect was already fixed by TASK-913, but the blocking
                 guard was missing. The guard now prevents silent dropping of
                 declared steps. The guard is conditional: it only fires when
                 cadence_steps explicitly declares the steps, so test
                 fixtures without cadence_steps retain backward compatibility.
    RISKS        Low. The guard only refuses when a declared step is missing,
                 which is the correct behaviour. Test fixtures without
                 cadence_steps are unaffected.
    RECOMMENDED  Merge. The guard prevents the discarded-subjects pathology
    CLAUDE       from recurring on the LinkedIn channel, and extends the same
    ACTION       protection to email.

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
