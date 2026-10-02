# TASK-961 — the review range can belong to another branch, and the task file leaks

## Why

Both found by GLM on 2026-10-02, in the first verdicts it formed with the code
actually in front of it, and both left out of TASK-940 deliberately: that task's
declared scope was the patch the reviewer sees, and these are separate defects
in the same file.

### 1. `_merge_commit_for` takes the OLDEST merge on the ancestry path

For an already-merged branch the honest review unit is `M^1..M` — what the merge
added to master — because a merged branch's diff against master is empty and a
retroactive review of one reviews nothing. The function finds that merge with
`--ancestry-path` and takes the first row.

If a branch was merged into an INTEGRATION branch and that branch was later
merged into master, the ancestry path holds both merges, and the oldest is the
integration one. The range is then `M_int^1..M_int`: everything the integration
branch brought, including OTHER branches' commits. The verdict would be formed
about a diff the named branch did not write — and a PASS on that diff says
nothing about the branch, while a FAIL blames it for somebody else's code.

Not yet observed in this repository, because every merge in the queue goes
straight to master. It is one integration branch away from firing, and the
failure is silent: the report prints the range it used, which is correct and
true, and nobody reads it as wrong.

### 2. `_find_task_file` leaks its `mkstemp` copy

A branch's task file is read out of the branch with `git show` and written to a
temporary file so the acceptance extractor can read it; the file is never
removed. Measured: **10 `task-from-branch-*.md` files already sit in `%TEMP%`**
from one evening's verification runs, and a `--dry-run` that calls nothing
leaves exactly one more behind in 9.6 seconds.

The copy only happens when a BRANCH is passed - `_find_task_file(task_id,
branch=None)` falls back to globbing the invoking tree - and that is how the
first version of the acceptance command below came to pass vacuously: it called
the function without a branch, took the glob path, created no temporary file and
asserted that none had leaked. The command now drives the whole script instead,
which exercises the real path and leaves the implementer free to clean up with
`atexit`, a `finally`, or a context manager.

Measured harm today: `%TEMP%` litter. Measured harm later: that same directory
already shadowed the standard library once in this project (`inspect.py` left in
Windows Temp broke every script run from there), so leaving named files in it is
not free.

## Acceptance

**Both commands must be run from a checkout of the branch under review**, not
from master: `review_range`, `_merge_commit_for` and the `mkstemp` task-file
copy are all TASK-940's own additions. Measured the hard way — run from a
master-based worktree, command 1 PASSES (master's `_find_task_file` globs the
tree and creates no temporary file at all) and command 2 dies on
`hasattr(m, '_merge_commit_for')`, which is a missing function rather than the
defect this task is about.

```
python -c "import glob,os,subprocess,sys,tempfile; pat=os.path.join(tempfile.gettempdir(),'task-from-branch-*'); before=set(glob.glob(pat)); r=subprocess.run([sys.executable,'scripts/glm_verify_branch.py','--branch','task-940-glm-verifier','--task','TASK-940','--dry-run'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=900); after=set(glob.glob(pat)); assert r.returncode==0, (r.stdout+r.stderr)[-400:]; assert after<=before, 'a finished run left its task-file copy behind: '+str(sorted(os.path.basename(x) for x in after-before)); print('OK a whole run leaves no task-file copy behind')"
```

```
python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); import subprocess; assert hasattr(m,'_merge_commit_for'), 'this is master s script, not the branch s: run from a checkout of the branch under review'; base,head,how=m.review_range('task-suite-lock'); out=subprocess.run(['git','rev-list','--ancestry-path','--merges','task-suite-lock..master'],capture_output=True,text=True,encoding='utf-8').stdout.split(); assert out, 'no merge found, so this branch cannot exercise the choice'; assert head==out[-1] or len(out)==1, 'the range used '+head[:8]+' while the NEWEST ancestry-path merge is '+out[0][:8]+' and the oldest is '+out[-1][:8]+'; for a branch merged through an integration branch the oldest is the wrong one'; print('OK the merge chosen is the one that brought the branch to master:', how)"
```

### NEGATIVE CONTROL

Command 1 fails today with `a finished run left its task-file copy behind:
['task-from-branch-....md']` — measured, 9.6 seconds, one file per run. Command 2 passes today on `task-suite-lock`, which has exactly ONE
ancestry-path merge, and that is stated rather than hidden: it is a REGRESSION
guard, and its own `assert out` refuses to pass on a branch where the choice is
not exercised at all. A branch merged through an integration branch is what
distinguishes the two readings, and there is none in this repository yet — so
the implementer must build one as a fixture, in a temporary repository, the way
`TheCodeIsShownBeforeTheProse` builds its own.

## Files

`scripts/glm_verify_branch.py`, and a test in
`tests/test_the_glm_verdict_compares_like_with_like.py`, which already carries
the fixture-repository pattern this needs.

## Not in scope

The prompt budget and the 180 s ceiling (TASK-959). The spend ledger
(TASK-960). Anything about what a PASS means.
