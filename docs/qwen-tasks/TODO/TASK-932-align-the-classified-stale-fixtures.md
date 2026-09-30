PRIORITY: P0
SIZE: S
DEPENDS: 

# TASK-932 — align the two stale fixtures that are ALREADY classified

`docs/RED-TEST-CLASSIFICATION-2026-09-30.md` names these and gives the exact
cause. **Do not re-diagnose them. Do not audit anything else.**

## 1. `test_generate` — 3 failures, one cause

The `harbourline` record in `tests/fixtures/phase5.jsonl` has **ZERO pack
facts**, so `copylint.step1_without_pack_fact` can never pass for it whatever
the copy says - `not supported` is true on its own. That rule was a WARNING
until the operator's PROOF-MODE demotion expired on 2026-09-28 and has
refused correctly ever since.

Give the fixture a pack, the way `tests/base.canonical_research` builds one,
and make `GOOD_BODY`'s opening line share a content word with it so step 1 is
grounded. `tests/test_the_offer_ladder_is_enforced_as_step_objectives.py` was
fixed the same way today - read that commit first, it is the worked example.

Then `len(retry_prompts) == 1` becomes true again, because the good draft is
accepted on the second attempt instead of every attempt being refused.

## 2. `test_set_regeneration` — 1 failure

`test_generate_record_replaces_colliding_set` uses `MERIDIAN_SEQUENCES`,
which is keyed for a sequence the record is no longer on, so the writer output
never satisfies the record's own cadence and the `linkedin_set` op is never
marked done. Align the fixture to the record's canonical sequence. Its sibling
failure was fixed today by reading the count from
`cadencelibrary.LINKEDIN_WRITER_KEYS` instead of a literal 6.

## RULES

- **NEVER WIDEN A GATE OR A LINT TO MAKE A FIXTURE PASS.** Fix the FIXTURE.
  `step1_without_pack_fact` must keep refusing a real ungrounded opener, and
  you must prove it still does.
- Do not touch `src/copylint.py`, `src/claims.py`, `src/sequencegate.py` or
  `src/evidence.py`. If you believe you must, STOP and say so.
- Mutation check is mandatory: break your own fix, prove the intended test
  goes red for the intended reason, restore, verify byte-identical by sha256,
  and clear `__pycache__` before re-running - a cp-based restore leaves stale
  bytecode and a restored file then tests exactly like the mutated one.

## RETURN

ROOT CAUSE / FILES CHANGED / TESTS / SHA / WHY THIS DOES NOT WEAKEN A GATE
