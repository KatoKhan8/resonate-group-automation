# TASK-977 — a baseline test passes or errors depending on whether `work/` happens to exist

Found 2026-10-03 by the lane working on TASK-973, while comparing name sets for
an unrelated change, and reproduced deliberately on a third untouched master
worktree before it was written down.

## Measured

`test_nothing_was_written_by_that` calls

    os.listdir(store.PRODUCTION_WORK)

unguarded. `PRODUCTION_WORK` is `<ROOT>/work` of the tree the module was
imported from, `work/` is gitignored, and **a freshly created worktree has
none** — so the call raises `FileNotFoundError` and the test ERRORS. The same
test passes in the main checkout, and passes in a worktree as soon as anything
creates `work/` there.

**Every suite that gates a merge in this project runs from a worktree.** So this
test's outcome is a property of how old the worktree is, not of the code under
test.

## Why it matters more than one name

The merge gate compares NAME SETS. A test whose outcome depends on the age of
the directory it runs in puts a name into the set, or takes one out, for reasons
that have nothing to do with the branch — which is precisely how three finished
suites each reported exactly 231 failing names and one of them was a different
231. It is a flake generator sitting inside the baseline, and it cost real time
twice already: once as a name that "went away" and had to be positively
verified, and once in the 942 run where seven cap and ceiling names turned out
to be order-dependent rather than branch-caused (TASK-970).

It also reads as the OPPOSITE of a defect in the branch being gated: a branch
that happens to create `work/` early makes the name disappear and looks like it
fixed something.

## The fix

Guard the read, and keep the test's meaning: "nothing was written" is TRUE of a
directory that does not exist, so an absent `work/` is a PASS and not an error.
One line, in the test. Do not create the directory to make the test pass — a
test that writes into the tree's state directory to measure state is the defect
TASK-973 is about.

While there: the same shape may exist elsewhere. `grep -rn "listdir(store\." tests/`
and `grep -rn "PRODUCTION_WORK" tests/` and check each for the absent case.

## Acceptance

```
python -c "import os,shutil,subprocess,sys,tempfile; tmp=tempfile.mkdtemp(prefix='agedir-'); tree=os.path.join(tmp,'wt'); root=subprocess.run(['git','rev-parse','--show-toplevel'],capture_output=True,text=True,encoding='utf-8').stdout.strip(); subprocess.run(['git','worktree','add','--detach',tree,'HEAD'],cwd=root,capture_output=True,text=True,timeout=600); assert os.path.isdir(tree), 'the probe worktree was not created'; assert not os.path.isdir(os.path.join(tree,'work')), 'the probe worktree already has work/ - it cannot measure the absent case'; r=subprocess.run([sys.executable,'-m','unittest','tests.test_invariants','-v'],cwd=tree,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=900,env=dict(os.environ,PYTHONIOENCODING='utf-8')); out=(r.stdout+r.stderr); subprocess.run(['git','worktree','remove','--force',tree],cwd=root,capture_output=True,text=True); shutil.rmtree(tmp,ignore_errors=True); assert 'FileNotFoundError' not in out, 'the module still errors on a worktree with no work/ directory'; assert 'Ran 0 tests' not in out, 'nothing ran, so this proves nothing'; print('OK the module survives a worktree whose work/ does not exist')"
```

### NEGATIVE CONTROL

**It fails today**, on a probe worktree created fresh inside the command, with
`FileNotFoundError` in the output. Two assertions stop it passing vacuously: the
probe refuses to measure a worktree that already HAS `work/` (that is the case
which passes for the wrong reason), and `Ran 0 tests` is rejected, so a module
that fails to load cannot be read as a pass. The probe worktree is detached and
removed afterwards, so it owns no branch and leaves nothing behind — a gate
worktree that advances with master is not a reference, and this one is not meant
to be either.

The module name in the command is the one that holds the test; if the test moves,
the command must move with it rather than being deleted.

## Files

`tests/test_invariants.py:908` (the unguarded `listdir`, in `TestTheBarrierCoversEveryWriter.test_nothing_was_written_by_that`), and
whatever the grep above turns up.

## Not in scope

`PRODUCTION_WORK` resolving per tree. That is TASK-973, and its fix makes the
barrier cover the main checkout as well; it does not create anybody's `work/`.
