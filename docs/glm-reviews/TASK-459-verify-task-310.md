# TASK-459 — Independent verification of TASK-310

## Review metadata

    Reviewed task:       TASK-310 — every APPROVED file feeds work/training/
    Reviewed branch:     origin/qwen-worker-11-r9
    Branch HEAD at fetch: c392a8ba4f07208cff6d89ac53c230aa64f4a7d5
    Target SHA (per task): 39561261f0ad4dcf71817da28669022a84d77043
    Review SHA:          39561261f0ad4dcf71817da28669022a84d77043
    Review worktree:     .qwen/worktrees/glm-459 (detached HEAD)
    Reviewer:            GLM (independent, Qwen-12)
    Date:                2026-09-28

**Note:** The branch has moved since the task was dispatched. The task specified
SHA `39561261f0ad4dcf71817da28669022a84d77043`; current HEAD is
`c392a8ba4f07208cff6d89ac53c230aa64f4a7d5`. This verdict reviews the specified
SHA as instructed.

---

## Disposition: REWORK — DISCONNECTED

The artifact exists, the tests pass, and the tests are falsifiable. However,
`reviewapproval.record()` — the function that triggers training capture — has
**zero production callers**. The training capture module is correct in isolation
but disconnected from any production path that would invoke it.

This is the same defect pattern as TASK-283 (reviewed on this same branch by
TASK-441, which reached the same REWORK verdict for the same reason).

---

## Findings

### Finding 1: Artifacts exist on this ref — VERIFIED

All five files named in the result block exist at SHA `39561261`:

| File | Status | Lines |
|------|--------|-------|
| `src/training.py` | NEW | 191 |
| `src/reviewapproval.py` | MODIFIED | +24 lines (hook added) |
| `src/store.py` | MODIFIED | +5 lines (TRAINING in STATE_OVERRIDES) |
| `tests/test_training_capture.py` | NEW | 199 (8 tests) |
| `tests/test_invariants.py` | MODIFIED | +8 lines (SELF_WRITERS) |

```
$ git log --diff-filter=A --all -- src/training.py
33675637 TASK-310: every APPROVED review file feeds work/training/
```

### Finding 2: Tests pass — VERIFIED

```
$ python -m unittest tests.test_training_capture -v
Ran 8 tests in 0.136s
OK
```

All 13 activation-refusal tests also pass (these exercise
`reviewapproval.require()`, the production-used half of the module):

```
$ python -m unittest tests.test_activation_refuses_without_the_operators_approval -v
Ran 13 tests in 0.011s
OK
```

`test_invariants` has two failures:
- `test_emailbison_posts_only_to_routes_it_declares` — pre-existing, confirmed
  unrelated (the TASK-310 result block noted this).
- `test_nothing_was_written_by_that` — environmental: no `work/` directory in
  the worktree. Not a code defect.

### Finding 3: Tests are falsifiable — VERIFIED

Mutation test: monkeypatched `_capture_training` to a no-op, then called
`reviewapproval.record()`. Result: `pairs=0, held=0`. The tests would catch
broken wiring at the unit level.

```
MUTATION TEST PASSED: tests would catch broken wiring
```

### Finding 4: Production callers — DISCONNECTED (CRITICAL)

`reviewapproval.record()` is the function that writes an approval AND triggers
training capture via `_capture_training()`. It has **zero production callers**
in `src/`:

```
$ grep -rn "reviewapproval\.record\b" src/ --include="*.py"
src/training.py:89:    Called by ``reviewapproval.record`` after the approval row is written.
```

The only hit is a docstring in `training.py`. No production code calls
`reviewapproval.record()`.

The production path uses `reviewapproval.require()` — from `bison.py:1463`,
`bison.py:1910`, `heyreach.py:1725` — to CHECK whether an approval exists
before activation. But the act of RECORDING an approval (which is what
triggers training capture) has no production entry point.

The Slack handlers reference `approval` (step-level approval, a different
module) and `clientapproval` (account-level client approval), but NOT
`reviewapproval.record()`.

**Consequence:** The training capture module will never capture anything in
production. No approval written through any real path will trigger
`_capture_training()`. The module is correct, the tests pass, but the wiring
to production is absent.

This is the recurring defect QWEN.md warns about: "a thing computed correctly
that nothing downstream reads." It is the same defect pattern as TASK-029
(extract_prospect_text with no caller), TASK-028 (id(tuple) keying that
missed through the real path), and TASK-019 (gates constructed by the test
rather than by production).

### Finding 5: Merging would not delete anything — VERIFIED

```
$ git diff origin/master...39561261 --diff-filter=D --name-only
docs/qwen-tasks/TODO/TASK-310-every-approved-file-feeds-the-training-set.md
docs/qwen-tasks/TODO/TASK-408-glm-verify-task-319.md
docs/qwen-tasks/TODO/TASK-414-spend-report-wiring-check.md
docs/qwen-tasks/TODO/TASK-421-suppression-list-audit.md
docs/qwen-tasks/TODO/TASK-422-heyreach-seat-cap-check.md
```

Only task files moved from TODO/ to REVIEW/ or DONE/. No source code, tests,
or documentation deleted. The diff is +6,810 / -177, with deletions limited to
task-file state transitions and minor edits.

### Finding 6: Scope drift — SIGNIFICANT

The branch carries 48 changed files across many tasks:

- TASK-310 (this task): ~5 files, ~300 lines
- TASK-437 (GLM verification of TASK-267): docs, scripts
- TASK-441 (GLM verification of TASK-283): docs, result block
- Multiple other task files in REVIEW/DONE
- New modules: `src/slackknowledge.py` (159 lines), `src/training.py` (191 lines)
- Significant changes to `src/packfacts.py` (+101/-16), `src/ingest.py` (+24/-9)
- Multiple new test files and scripts

TASK-310's changes can be cleanly cherry-picked: the five files named in
Finding 1 form a coherent, self-contained unit.

---

## What must be done

1. **Wire `reviewapproval.record()` into the production approval path.** The
   operator's "APPROVED <campaign> <hash>" message is processed somewhere
   (Slack handler, agent tool, or CLI). That path must call
   `reviewapproval.record()`. Until it does, training capture is disconnected.

2. **Add a test that proves the wiring.** Not a test that calls
   `reviewapproval.record()` directly — a test that drives through the
   production entry point (the Slack handler or agent tool that processes
   approvals) and verifies that `training.count()` increments.

3. **Alternatively, if `reviewapproval.record()` is intended to be called
   manually by the operator via a CLI or agent tool,** document that clearly
   and add an integration test that exercises the full path.

---

## What is safe to merge

The five TASK-310 files are safe to merge as-is:
- They do not break anything
- They do not delete anything
- They are well-tested
- The mutation test confirms the tests are meaningful

But they are not functional until the production caller is wired.

---

## Recommendation: REWORK

Wire the production caller, add a wiring test, then this is a clean MERGE.
The artifact kind is code + test. The defect is disconnection, not incorrect
implementation.

---

## Reproducible commands

```bash
# Check out the exact SHA
git worktree add .qwen/worktrees/glm-459 39561261f0ad4dcf71817da28669022a84d77043 --detach

# Run the training capture tests
cd .qwen/worktrees/glm-459
python -m unittest tests.test_training_capture -v

# Verify zero production callers
grep -rn "reviewapproval\.record\b" src/ --include="*.py"

# Mutation test: break wiring, confirm tests catch it
python -c "
import tempfile, os, shutil, sys
sys.path.insert(0, '.')
tmp = tempfile.mkdtemp(prefix='glm459-')
os.environ['QUEUE'] = os.path.join(tmp, 'work', 'queue.jsonl')
os.environ['TRAINING'] = os.path.join(tmp, 'work', 'training')
os.environ['CAMPAIGNS'] = os.path.join(tmp, 'work', 'campaigns.jsonl')
from src import campaigns as cm, reviewapproval, store, training
store.use_directory(os.path.join(tmp, 'work'))
rec = {'id': 'r1', 'company': 'A', 'domain': 'a.test', 'lane': 'cold',
       'hook': '', 'state': 'drafted', 'facts': [{'text': 'x', 'source': 's'}],
       'contacts': [{'key': 'a@a.test', 'name': 'A', 'title': 'COO',
                     'email': 'a@a.test', 'persona': 'ops', 'angle': 'g'}],
       'cadence': {'a@a.test': {'day1': {'subject': 's', 'body': 'b'}}}}
store.save([rec])
c = cm.new_campaign(campaign_id='c1', client='productive', name='T', created_by='t')
c['record_ids'] = ['r1']; c['bison_campaign_id'] = '503'
cm.save([c])
import src.reviewapproval as ra
ra._capture_training = lambda *a, **kw: None  # BREAK wiring
reviewapproval.record('503', 'h', by='zvonimir')
print(f'pairs={training.count()[\"pairs\"]} (expect 0 if tests are meaningful)')
shutil.rmtree(tmp, ignore_errors=True)
"
```
