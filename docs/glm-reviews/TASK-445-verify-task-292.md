# TASK-445 — GLM Independent Verification: TASK-292

## Review metadata

    reviewed task       TASK-292
    reviewed branch     origin/qwen-worker-10-r9
    reviewed HEAD SHA   d3b76e3e172b59d86fd9541f15f47fcbf049c857
    SHA verified        yes — git rev-parse confirms d3b76e3e
    review worktree     C:\Users\Zvonimir\Desktop\resonate-glm-445 (detached HEAD)
    review date         2026-09-28
    reviewer            GLM (Qwen worker 6)
    disposition         REWORK
    recommendation      DO NOT MERGE

## Summary

TASK-292 built a QA harness (registry, runner, result validator, table renderer,
refusal function) with 30 passing tests. The harness logic is well-implemented
for what it tests. **But the QA gate does not stop the real send path because
it is not connected to `bisonfactory.stage()` or `heyreachfactory.stage()`.**
This is the exact TASK-277 defect — a gate built correctly and wired into
nothing that production calls — reproduced by the task that was written to
prevent it.

## Findings

### Finding 1: DISCONNECTED — `_refuse_qa` is not in the production send path

**Severity: Critical**
**Confidence: High — verified by module inspection and source analysis**

The task's central requirement (section "What to build", item 5):

> `_refuse_qa(plan, recs, report)` in `src/bisonfactory.py`, immediately after
> lane D's `_refuse_copylint` at line 86 and before `bison.bound_workspace()`

**Status: NOT IMPLEMENTED in production code.**

Verification:

```
_refuse_qa in bisonfactory: False
_refuse_copylint in bisonfactory: True
stage in bisonfactory: True
stage() references qa: False
```

`grep -rn "_refuse_qa" src/` returns zero matches. `grep -rn "refuse_qa" src/`
returns zero matches. The refusal function exists only in
`scripts/qa/refuse_qa.py` as a standalone module with a `_FakeFactoryRefused`
exception class. No production module imports or calls it.

The boundary condition said: "If lane D has landed when you start, say so with
the sha and edit it." Lane D HAS landed — `_refuse_copylint` exists at
`bisonfactory.py:87` (call) and `:581` (definition). The branch did not edit
`_refuse_qa` into bisonfactory.

### Finding 2: The "real send path" test does not test the real send path

**Severity: Critical**
**Confidence: High — verified by reading the test source**

The task required:

> A test drives the REAL send path. It calls `bisonfactory.stage(...,
> live=True)` with a check rigged to FAIL and asserts `FactoryRefused` is
> raised, and asserts that no provider call was made.

The test `TheRealSendPathIsTheEntryPoint.test_import_graph_trace_by_module_objects`
only checks:

```python
names = dir(bisonfactory)
self.assertIn("stage", names)
self.assertIn("_refuse_copylint", names)
```

It does NOT assert `_refuse_qa` is in `bisonfactory`. It does NOT assert
`stage()` calls any QA function. It passes while the wiring is absent. This is
TASK-277's defect verbatim: "Eight tests proved it worked, and all eight called
it directly; zero called `push.run(`."

The test `test_refuse_qa_raises_factory_refused_with_table` calls
`refuse_qa.refuse()` directly with `check_results` pre-built. It proves the
refusal function works in isolation. It does not prove anything reaches it from
`bisonfactory.stage()`.

**Falsification performed:** Confirmed `bisonfactory` has no `_refuse_qa`
attribute while all 30 tests pass. The tests are green with the wiring absent.

### Finding 3: `heyreachfactory.stage()` has the same gap

`grep -rn "refuse_qa|_refuse_qa|qa" src/heyreachfactory.py` returns zero
matches. The task required the same wiring at heyreachfactory's equivalent seam.
Not done.

### Finding 4: What IS built and works

The following artifacts exist at the reviewed SHA and function correctly for
what they test:

- `scripts/qa/__init__.py` — Registry (7 checks, 3 phases), verdict vocabulary,
  result validator (5 invariants), table renderer. Well-structured.
- `scripts/qa/run.py` — Runner with `--phase`, `--workspaces` (required), JSON
  output, table rendering. Correct exit code semantics.
- `scripts/qa/refuse_qa.py` — Standalone refusal function with rendered table
  in exception text. Uses `_FakeFactoryRefused` (not the real one).
- `scripts/qa/check_lead_copy.py` — One implemented check (878 lines).
- `tests/test_the_qa_gate_stops_the_real_send_path.py` — 17 tests, all pass.
- `tests/test_a_qa_result_that_does_not_add_up_is_an_error.py` — 13 tests, all
  pass.

The registry, runner, validator, and table renderer are genuine, useful
infrastructure. The result validator correctly enforces arithmetic invariants.
The verdict severity ordering is correct. The VACUOUS handling is correct. The
bypass-flag absence is verified.

**These are mergeable as infrastructure. They are not a gate.**

### Finding 5: Deletion risk

The branch deletes one file vs master:

    docs/qwen-tasks/TODO/TASK-216-find-the-supported-list-to-campaign-bind.md (104 lines)

This is a task file that was presumably moved to REVIEW/DONE on the branch.
Merging would delete it from master's TODO. Low risk but should be noted.

### Finding 6: Scope pollution — 205 files, ~30K lines

The branch carries the entire accumulated work of `qwen-worker-10-r9`, not just
TASK-292. Only these files are TASK-292's artifacts:

    scripts/qa/__init__.py          (295 lines, new)
    scripts/qa/run.py               (202 lines, new)
    scripts/qa/refuse_qa.py         (126 lines, new)
    scripts/qa/check_lead_copy.py   (878 lines, new)
    tests/test_the_qa_gate_stops_the_real_send_path.py    (302 lines, new)
    tests/test_a_qa_result_that_does_not_add_up_is_an_error.py (248 lines, new)

Everything else (29 src/ files, ~50 docs/ files, ~20 task files, ~30 other test
files) belongs to other tasks. Cherry-picking would be required; a straight
merge would bring the entire branch.

## Disposition

**REWORK.** The harness infrastructure is sound and the 30 tests are meaningful
for what they test. But the gate does not gate: `_refuse_qa` is not called from
`bisonfactory.stage()` or `heyreachfactory.stage()`, and no test proves
otherwise. This is the exact defect TASK-292 was written to prevent, and it was
reproduced.

### What is needed

1. Wire `_refuse_qa` into `bisonfactory.stage()` after `_refuse_copylint`
   (lane D has landed, so edit directly, no patch proposal needed).
2. Wire the equivalent into `heyreachfactory.stage()`.
3. Replace `test_import_graph_trace_by_module_objects` with a test that asserts
   `_refuse_qa` IS in `dir(bisonfactory)` and that `stage()` source contains
   the call. Better: a test that calls `bisonfactory.stage(...)` with a rigged
   check and asserts `FactoryRefused` with zero provider calls.
4. Replace `_FakeFactoryRefused` with the real `bisonfactory.FactoryRefused`.

### What can be cherry-picked as-is

The six files listed in Finding 6, minus the wiring gap. The registry, runner,
validator, and table renderer are genuine infrastructure.

## Evidence

    START_REVIEW_SHA       d3b76e3e172b59d86fd9541f15f47fcbf049c857
    REVIEW_WORKTREE        C:\Users\Zvonimir\Desktop\resonate-glm-445
    TESTS_RUN              30/30 pass (unittest)
    _refuse_qa in src/     0 matches (grep -rn)
    _refuse_qa in factory  False (dir() + inspect.getsource)
    stage() refs qa        False (inspect.getsource)
    Files deleted vs master 1 (TASK-216 task file)
    Branch scope           205 files, +30881/-477 lines
