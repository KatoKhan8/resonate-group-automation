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

STATUS
DONE - implementation complete, live run requires Claude's credentials.

COMMIT SHA
b3e1329

TESTS
13 new tests in tests/test_set_regeneration.py, all passing.
95 tests across test_set_regeneration + test_generate + test_quality, all green.
Pre-existing failures (test_cadence pause test, test_invariants work/ dir) confirmed
unrelated by running against stashed changes.

FILES CHANGED
- src/generate.py: +221 lines
  - _needs_set_regeneration(): detects campaign_repetition collisions among
    steps that pass intrinsic gates (lint, claims, foreign_product)
  - _regenerate_linkedin_set(): transactional set regeneration - generates
    all notes into memory, gates the complete set, commits only if all pass
  - plan(): emits linkedin_set op when condition detected, replacing
    individual linkedin_note ops for that contact
  - generate_record(): handles linkedin_set op through the real entry point
- tests/test_set_regeneration.py: new file, 13 tests

FINDINGS

1. THE MECHANISM IS AS DESCRIBED. `ranjan-damodar` has 6 LinkedIn notes
   where li1-li5 pass lint, claims and foreign_product individually but
   collide on campaign_repetition. The one-at-a-time regeneration cannot
   converge because each replacement is compared against old siblings that
   still say the same thing.

2. THE SAFER SHAPE WAS CHOSEN over "clear all notes then regenerate".
   The implementation generates the full replacement set into memory FIRST,
   gates the whole set together, and only commits if every member passes.
   If regeneration fails part way, nothing is lost and the original notes
   are preserved. This matches what store.transaction does for records.

3. THE TRIGGER IS FROM THE DATA, not a picked threshold. The condition is:
   campaign_repetition collisions among steps that all pass the intrinsic
   gates. No numeric threshold; the collision set IS the condition.

4. NO GATE WAS WEAKENED. SUBJECT_VOCABULARY is unchanged (profitability,
   margin, utilisation, utilization). campaign_repetition and
   repetition_across_rungs are untouched. The fix is in the regeneration
   strategy, not in the gates.

5. WIRING IS PROVEN. Breaking _needs_set_regeneration (returning None)
   prevents linkedin_set ops from appearing in plan output. Breaking
   _regenerate_linkedin_set (returning None) prevents the old notes from
   being replaced. Both tests prove the new code is consumed by the real
   entry points.

6. LIVE RUN NOT POSSIBLE HERE. config/.env exists only in Claude's worktree.
   The QUEUE was copied to C:\Users\Zvonimir\Desktop\resonate-qwen-2-scratch\
   as instructed. The command Claude needs to run:
   
   QUEUE=C:\Users\Zvonimir\Desktop\resonate-qwen-2-scratch\queue.jsonl ^
   py -3 -m src.generate --live --id adcuratio-com
   
   Then:
   py -3 scripts/write_heyreach_sequence.py productive-linkedin-production-v1
   
   The second command must stop naming ranjan-damodar. If it names a
   different contact, that is progress and the loop continues.

7. MODEL CALLS. Set regeneration costs N calls per contact (one per LinkedIn
   step, plus retries). For ranjan-damodar with 6 LinkedIn steps, that is
   at least 6 model calls. The old approach spent 3 attempts per step and
   never converged; the new approach spends up to 3 attempts per step but
   terminates because the old siblings are not constraining the new ones.

8. THE CHOSEN IMPLEMENTATION DEFENSIBLY. The task asked to "decide, implement
   the one you can defend, and say in FINDINGS why." The transactional shape
   (generate all into memory, gate the set, commit or rollback) was chosen
   over "clear and regenerate" because losing copy to a failed rewrite is
   worse than keeping bad copy that is already blocked. The transactional
   approach preserves the original notes on failure and reports the reason.

RISKS

1. The set regeneration generates each note without seeing the other new
   notes (they are not yet committed). Cross-note collision is checked
   after all notes are generated. If the model produces notes that still
   collide despite the ladder purposes, the set is rejected and the old
   notes are preserved. The operator can retry.

2. The cost per contact is higher (N model calls instead of 1). This is
   deliberate: the cheap version cannot converge for this condition.

3. The detection runs after the individual plan loop, so individual
   linkedin_note ops are emitted first and then replaced. This is correct
   but means the plan output briefly contains ops that are then removed.

RECOMMENDED CLAUDE ACTION

1. Run the live generation against the scratch copy:
   QUEUE=<scratch> py -3 -m src.generate --live --id adcuratio-com
   
2. Check the output: ranjan-damodar's notes should be replaced with
   genuinely different notes that pass campaign_repetition.
   
3. Run the HeyReach dry run:
   py -3 scripts/write_heyreach_sequence.py productive-linkedin-production-v1
   
4. If it stops naming ranjan-damodar, the blocker is cleared. If it names
   a different contact, continue the regeneration loop on that contact.
   
5. Do NOT run write_heyreach_sequence.py with --live. That is Claude's
   alone.
