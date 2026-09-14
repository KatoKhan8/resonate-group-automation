# TASK-068 - A mutually repetitive sequence cannot be fixed one note at a time

## THE MECHANISM, MEASURED

`adcuratio-com/ranjan-damodar` blocks the HeyReach dry run. Its six LinkedIn
notes say, in order:

    li1  "share insights on operations and project capacity"
    li2  "how do you currently track utilisation and capacity across your
          live projects?"
    li3  "how are you currently managing capacity across your teams?"
    li4  "challenges in tracking utilisation and capacity across your
          projects?"
    li5  "any thoughts on improving utilisation and capacity across your
          live projects?"

Against the INTRINSIC gates - the ones that do not depend on siblings - **li1
through li5 all PASS** lint, claims and `foreign_product`. Only li6 fails, on
a fabricated "our previous discussions".

So TASK-062's exclusion cannot help: there is nothing invalid to exclude.
These are five individually clean notes that all say the same thing.

**And `generate.plan` regenerates ONE STEP AT A TIME.** Whichever note is
rewritten is compared against the four that still say "capacity across
projects", so a replacement must differ from all four at once or be refused
and discarded. The old note stays, the next pass faces the same wall, and the
sequence can never converge. That is why a completed regeneration MOVED the
blocker from one contact to the next instead of clearing it.

## GOAL

A contact whose notes are mutually repetitive is regenerated AS A SET, so no
member of the old set constrains the new one.

## THE SHAPE OF THE FIX - AND THINK BEFORE CODING

The obvious implementation is "clear all the contact's notes, then
regenerate". Consider it carefully, because it has a real cost: if
regeneration then fails part way, the contact ends with FEWER notes than it
started with. Losing copy to a failed rewrite is worse than keeping bad copy
that is already blocked.

A safer shape: generate the full replacement set into memory FIRST, gate the
whole set together, and only commit it if every member passes. That is
transactional and it matches what `store.transaction` already does for
records. If it fails, nothing is lost and the reason is reportable.

Decide, implement the one you can defend, and say in FINDINGS why.

## WHEN DOES IT TRIGGER

Not always - regenerating six notes when one is stale wastes five model
calls. A reasonable trigger is `campaign_repetition` reporting collisions
among steps that all pass the intrinsic gates, which is exactly the state
that one-at-a-time cannot escape. Establish the condition from the data
rather than picking a threshold.

## PROVE IT ON THE REAL BLOCKER

    QUEUE=<scratch copy> py -3 -m src.generate --live --id adcuratio-com
    py -3 scripts/write_heyreach_sequence.py productive-linkedin-production-v1

The second command must stop naming `ranjan-damodar`. If it names a different
contact, that is progress and the loop continues; report the sequence of
blockers as TASK-061 did.

Report the model calls spent. Regenerating a set is more expensive per
contact than one step, and the whole point is that it terminates where the
cheap version cannot.

## WHAT YOU MAY NOT DO

- **Do not weaken `campaign_repetition`, `repetition_across_rungs` or
  `SUBJECT_VOCABULARY` to make the dry run pass.** Measured and rejected
  already: discounting the client's angle vocabulary clears all five
  collisions on this contact, and the copy it would then pass is four
  askings of the same question. See
  `docs/WHY-REGENERATION-CANNOT-CONVERGE-2026-09-14.md`.
- Do not delete stored copy except as part of a transaction that replaces it.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`; use a scratch
  copy with `QUEUE` pointed at it.
- No provider write. `--live` on `write_heyreach_sequence.py` is Claude's.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION.
