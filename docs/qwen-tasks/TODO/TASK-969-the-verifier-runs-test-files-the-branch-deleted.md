# TASK-969 — the verifier runs test files the branch deleted, and fails the branch for it

Found while gating `task-word-contract-enforced` on 2026-10-03. The multi-part
GLM review ended:

    --- Verdict: FAIL ---
    1 new test failures not in baseline:
      ['unittest.loader._FailedTest.test_a_thread_reply_has_its_own_word_range']

That module **does not exist on the branch** — the branch deleted it
deliberately, replacing its 295 lines with `tests/test_word_contract_enforced.py`
(which keeps its cases and says so in two docstrings).

## The mechanism, measured

`_changed_test_files(branch)` in `scripts/glm_verify_branch.py` asks

    git diff --name-only <base> <head> -- tests/

and git's changed-file list **includes deletions**. `_run_tests_in_worktree`
then runs every name it was given, so `unittest` is asked to load a module that
is not there, answers with `unittest.loader._FailedTest`, and the branch-level
override — "new test failures not in baseline" — turns that into a FAIL for the
whole branch.

Its sibling `_new_test_files` already uses `--diff-filter=A`, so the tool knows
how to ask git a narrower question. `_changed_test_files` just never did.

**Measured, so the blame lands in the right place:** nothing in `tests/`, `src/`
or `scripts/` registers the deleted module — the only references anywhere are
prose inside the new test's docstrings. So the name came from the verifier, not
from a broken registration in the repository.

## Why this is worth a task rather than a note

**Any branch that DELETES a test file fails the gate**, and deleting a test is
the correct move whenever its subject is replaced — which is exactly what the
word-contract branch did when the abolished 15-to-60 reply range went away. A
gate that punishes the honest removal of a stale test teaches people to leave
stale tests in place.

It also costs a GLM call and a verdict every time, and it did here: the branch's
real findings were almost buried under a loader error.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); files=m._changed_test_files('task-word-contract-enforced'); assert files, 'this branch changes test files, so an empty list means the reader is blind'; gone=[f for f in files if 'test_a_thread_reply_has_its_own_word_range' in f]; assert not gone, 'the verifier still names a file the branch deleted: '+str(gone); print('OK', len(files), 'changed test files, none of them deleted')"
```

```
python -c "import subprocess,sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); B='task-word-contract-enforced'; files=m._changed_test_files(B); missing=[f for f in files if subprocess.run(['git','cat-file','-e',B+':'+f],capture_output=True).returncode]; assert not missing, 'named files that are not in the BRANCH the tests will run from: '+str(missing); print('OK all', len(files), 'named files exist in', B)"
```

### NEGATIVE CONTROL

Command 1 fails today naming
`tests/test_a_thread_reply_has_its_own_word_range.py`, and its first assertion
is the control that the reader is not simply returning nothing: this branch
really does change test files, so an empty list would be a different defect
wearing the same green.

Command 2 is the stronger form of the same question: `--diff-filter=d` fixes the
git call, but the property that matters is that **every file handed to
`unittest` exists in the BRANCH the tests will run from**. A fix that filtered
deletions but still named a file renamed out from under it would pass command 1
and fail command 2.

It asks git about the branch rather than the filesystem, and that correction was
itself measured: the first version checked `os.path.isfile` under the INVOKING
tree's `ROOT` and failed on `tests/test_word_contract_enforced.py` — a file that
exists on the branch and not in the tree the command was run from. The command
was reporting where it was standing, not what the verifier does.

## Files

`scripts/glm_verify_branch.py`.

## Not in scope

The branch that exposed it. Its real findings are recorded in TASK-968 and were
measured separately — one true (`is_contract_failure` had no production caller,
now removed), one mine (a vacuous acceptance command, now deleted) and one
refuted (`lint.word_range` was moved, not orphaned).
