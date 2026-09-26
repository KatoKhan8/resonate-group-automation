PRIORITY: P1
DEPENDS:

# TASK-277 — tests that the copy lint is actually WIRED, not merely present

`copylint` merged on 2026-09-24 (`09e16c34`). It refuses a batch and names
which leads and which rule. **Nothing on the send path calls it yet.**

This repo's recurring defect, from CLAUDE.md: *"a thing computed correctly
that nothing downstream reads"* - an evaluator reported INSUFFICIENT_DATA for
ever because nothing wrote the field it read. `outreachclaims` is the same
shape today: it is the authority on claims about us and **has no consumer on
the send path**.

So the risk is not that the lint is wrong. It is that it will sit beside the
pipeline reporting nothing, and a green suite will say so every day.

## What to write

`tests/test_the_copy_lint_is_on_the_send_path.py`:

1. a batch containing a lead whose copy breaks a lint rule CANNOT be pushed -
   assert on the push refusing, not on the lint returning a finding
2. the refusal NAMES the lead and the rule
3. the lint runs BEFORE any provider write, not after - the blank-render gate
   already fails this way round (ISSUE-034: it refuses after the attach and
   the refusal does not roll back)
4. a lint rule that is added later is automatically enforced - the wiring
   reads the rule set, it does not enumerate rules
5. `outreachclaims` is reachable from the send path, or a test says plainly
   that it is not

Rule 5 may be RED and stay red. Record it as a finding rather than deleting
the test.

## Rules

- Tests and wiring only. Do not weaken a lint rule to make a draft pass -
  CLAUDE.md forbids it explicitly; regenerate the draft instead.
- Never put a real prospect address, name or company in a test.
- `work/` is gitignored; never commit it.
- Commit on your own branch. Do not merge.

## Result block

    BRANCH:
    COMMIT:
    TESTS ADDED:
    IS THE LINT ON THE SEND PATH TODAY, YES OR NO:
    IS outreachclaims REACHABLE, YES OR NO:

---

## STATE RECORDED BY LANE E, 2026-09-24 late

# REJECTED. DO NOT MERGE.

    DELIVERED BY     qwen-4, 2026-09-24
    STATE            REVIEW / REJECTED (moved out of TODO/ tonight)
    ON MASTER        NO, AND IT MUST NOT GO THERE AS DELIVERED

The verdict was established by the production session, which read the
delivery itself. From `docs/PRODUCTION-HANDOFF-2026-09-24-LATE.md` section
4.1, quoted rather than re-derived:

  It claims "the copy lint is on the send path, not merely present." It is
  not:

  - `run_with_copylint` is called by nothing - only its own `.pyc` matches.
  - All 8 tests call it DIRECTLY; 0 call `push.run(`.
  - `src/push.py` is NOT the send path. Its `run()` raises on `live=True`:
    "live push is not implemented in this build... No code here can reach
    EmailBison or HeyReach." The real path is `scripts/batch1_push.py` ->
    `bisonfactory.stage`.

  So the lint was wired into a module that refuses to send, through a
  function nobody calls, proved by tests that call it directly. That is the
  exact defect the task was written about, reproduced by the fix for it.

The wiring belongs in `bisonfactory.stage` BEFORE the attach, and the test
must assert on the push refusing.

**THE RE-WIRING IS ANOTHER LANE'S AND IS IN PROGRESS.** No Qwen worker may
edit `src/push.py`, `src/bisonfactory.py`, `src/copylint.py` or the lint call
site. TASK-290 is the salvage and the wiring assertion, and it says so.

    NEXT             TASK-290 - salvage what is true about the LINT, write
                     the wiring assertion the lane will need (red today),
                     and propose the general no-caller check.

---

## REVIEW BLOCK — TASK-290, 2026-09-27

TASK-290 was the salvage. It was asked to answer four questions:

1. **Which of the tests assert something true about the LINT?**
   All 10 tests in the replacement file
   (`tests/test_the_copy_lint_refuses_the_real_send_path.py`) drive
   `bisonfactory.stage` and assert on the EFFECT of the lint on the send
   path. None of them tests the lint's rules directly - those are in
   `tests/test_copylint.py`. All 10 are recommended for keeping: 7 pass,
   3 are RED due to the sequence gate (not the lint). See
   `docs/COPYLINT-SECOND-PASS-2026-09-25.md` for the full table.

2. **The wiring assertion.** Written as
   `tests/test_the_lint_refuses_the_real_push.py`. Four assertions, all
   GREEN today because the wiring was landed by another lane while this task
   was in flight. Proof the tests test the WIRING: replacing
   `_refuse_copylint` with a no-op causes all 4 to fail. The lint is wired,
   the tests prove it, and the proof survives breaking the wiring.

3. **Is `outreachclaims` reachable from the send path?** NO. It is imported
   by `contextpack`, which is consumed only by `src/web/api.py`. The send
   path (`bisonfactory.stage`) does not import `contextpack` or
   `outreachclaims`. The finding stands.

4. **The general check.** Specified in `docs/COPYLINT-SECOND-PASS-2026-09-25.md`:
   an import-graph assertion over a set of guard modules and two entry
   points, with "reachable" defined as a chain of static imports and
   function calls from entry point to at least one public function in the
   guard module. Would have caught all four instances of this defect.

    BRANCH         qwen-worker-9-r9
    ARTIFACT KIND  test + document
    FILES CHANGED  tests/test_the_lint_refuses_the_real_push.py (new)
                   docs/COPYLINT-SECOND-PASS-2026-09-25.md (new)
                   docs/qwen-tasks/REVIEW/TASK-277-copylint-wiring-tests.md (appended)
    FORBIDDEN      src/push.py, src/bisonfactory.py, src/copylint.py - NOT EDITED
    CONFIRM        I did not edit push.py, bisonfactory.py or copylint.py
