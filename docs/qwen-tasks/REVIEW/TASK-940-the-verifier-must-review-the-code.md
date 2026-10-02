# TASK-940 — the GLM verifier must review the code, not a summary of it

## Why

`scripts/glm_verify_branch.py` is the adversarial first pass over every branch
before it is merged. On 2026-10-02 it was measured and **every verdict it had
ever produced was formed without the code**: `_diff_against_master` computed the
full patch, `main` discarded it, and the prompt's slot was literally named
`diff_stat` under a heading that said "(summary)". A reviewer asked "does this
new function have a production caller" was being shown file names and line
counts.

Seven further defects were measured the same day and are fixed with it. Each is
named in the commit message with how it was measured.

## Scope

`scripts/glm_verify_branch.py` only. No change to `src/`, no provider write, no
Slack post, no push.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); b,h,how=m.review_range('task-suite-lock'); assert b, 'merged branch resolved to no range'; assert 'merged by' in how, how; fs=m._changed_files('task-suite-lock'); assert len(fs)==4, fs; print('OK merged-branch range:', how, len(fs), 'files')"
python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); st,df=m._diff_against_master('task-suite-lock'); p=m._build_prompt('b','T',['src/suitelock.py'],st,df,'ran','tests'); assert 'def acquire' in p, 'the patch is not in the prompt'; assert len(p) < 60000, len(p); print('OK the prompt carries the patch:', len(p), 'chars')"
python -c "import sys,os; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); p=m.env_path(); assert os.path.isfile(p), 'no config/.env reachable from a worktree: '+p; print('OK credentials reachable:', os.path.basename(os.path.dirname(os.path.dirname(p))))"
python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); r,c,by=m._read_spend(); assert isinstance(by,dict), by; print('OK spend reads by provider, not by a retired tenant:', r, 'glm rows,', len(by), 'clients')"
python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); t=m.acceptance_text('docs/qwen-tasks/REVIEW/TASK-940-the-verifier-must-review-the-code.md'); assert 'review_range' in t, 'the acceptance prose is not extractable'; assert m.acceptance_text(None)=='', 'the negative control returned something'; print('OK acceptance prose extractable:', len(t), 'chars, control empty')"
```

### NEGATIVE CONTROL

Each command above must be able to fail. The fifth carries its own negative
control inline (`acceptance_text(None)` must be empty). The first fails on a
branch whose merge cannot be found; the second fails if the prompt is built from
the stat; the third fails in a worktree with no `config/.env` reachable, which is
exactly the state that made every GLM call today return `MissingKey`.

### Mutation

Revert the `diff_full` argument in `main`'s `_build_prompt` call to `diff_stat`
and command 2 must go red with "the patch is not in the prompt".

## Files

`scripts/glm_verify_branch.py`. The verifier is not allowed to grow a second
copy of any number it already reads from a constant.
