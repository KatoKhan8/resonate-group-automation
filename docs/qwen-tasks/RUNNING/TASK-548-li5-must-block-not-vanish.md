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
