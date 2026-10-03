# TASK-971 — the review re-runs what the gate run already measured, on a worse budget

Measured 2026-10-03 on `task-942-token-budget`. Both review parts came back
**PASS**, and the branch verdict was then overridden:

    OVERRIDING PASS -> NEEDS_CLAUDE: the tests could not be run, so
    "0 failing" is an unmeasured zero.
    ... the test run failed to start: TIMEOUT after 600s

**The override is right and must stay.** An unmeasured zero is not a pass, and
this repository has been bitten by exactly that shape more than once tonight.
What is wrong is everything around it.

## Two defects, and the second is the one worth fixing

**1. The budget was a round number, not a budget.** 600 seconds, inline, scaling
with nothing. The branch changes **23 test modules**; the step ran out of time
and a clean branch was downgraded. Fixed immediately in the tool this queue runs
(`TEST_STEP_TIMEOUT = 1_800`, named, with the measurement beside it: the whole
suite is ~2,070s for 14,695 tests, so a 23-module subset has room). That is a
patch, not an answer.

**2. The step duplicates the gate run, worse.** The merge gate already runs the
WHOLE suite on the branch's tree and compares the failing names to a reference
measured on master. For this very branch that happened twice: run 1 gave 238
names (seven order-dependent, TASK-970), run 2 gave **231 against the
reference's 231, 0 new, 0 gone**. So at the moment the review was downgraded for
being unable to run 23 modules, the same tests had already been run — all
14,695 of them — on the same commit, with a cleaner verdict than the subset
could ever give.

**The question this task exists to answer: why does the verifier run tests at
all?** Two honest answers, and the operator should pick one rather than letting
both half-exist:

- **It should not.** The gate run is the authority for "do the tests pass on
  this branch", it is already required before any merge, and its verdict is a
  NAME-SET DIFF rather than a pass/fail. The review's job is the three questions
  it asks about the code. Then the override becomes "no gate run was supplied
  for this branch", which is a stronger check than a timeout, and the review
  gets minutes shorter.
- **It should, but as a FAST subset.** Only the test files the branch ADDED
  (`_new_test_files` already exists and uses `--diff-filter=A`), because those
  are the ones no gate reference has ever seen. Modified modules are covered by
  the gate run.

Either way the review stops paying for the suite twice.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); import inspect; src=inspect.getsource(m._run_tests_in_worktree); assert 'timeout=600' not in src, 'the round number is back'; assert 'TEST_STEP_TIMEOUT' in src or 'suite' in src.lower(), 'the step neither names its budget nor defers to the gate run'; print('OK the budget is named or the step defers')"
```

```
python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); changed=m._changed_test_files('task-942-token-budget'); added=m._new_test_files('task-942-token-budget'); assert changed and added is not None, (changed, added); print('changed:', len(changed), 'added:', len(added)); assert len(added) < len(changed), 'the added set is not smaller, so the fast-subset option saves nothing on this branch'; print('OK the added subset is', len(added), 'of', len(changed))"
```

### NEGATIVE CONTROL

Command 1 fails if anybody puts the inline 600 back, and its second clause is
deliberately permissive about WHICH answer was chosen — a task that forced one
of the two designs would be deciding the operator's question for them.

Command 2 measures whether the fast-subset option is worth anything on a real
branch before anybody builds it: if the added set were as large as the changed
set, that design saves nothing and only the first answer is left. It fails if
`_new_test_files` ever stops being narrower, which is the assumption the option
rests on.

## Files

`scripts/glm_verify_branch.py`.

## Not in scope

The override itself. "The tests could not be run, so a zero is unmeasured" is
correct and is the only reason this defect was visible at all.
