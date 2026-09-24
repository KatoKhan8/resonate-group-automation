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
