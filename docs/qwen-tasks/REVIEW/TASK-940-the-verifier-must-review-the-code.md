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
python -c "import sys,os; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); p=m.bind_spend_to_the_main_ledger(); assert p, 'no ledger resolved: git would not answer absolutely'; assert not p.startswith(os.path.abspath('.')+os.sep), 'the ledger resolved INSIDE this tree, so a worktree bills a throwaway file: '+p; r,c,by=m._read_spend(); assert r>0, 'zero glm rows: either the reader is blind (the retired-tenant filter) or this is the wrong ledger'; print('OK spend reads the ONE ledger:', r, 'glm rows,', len(by), 'clients,', p)"
python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); t=m.acceptance_text('docs/qwen-tasks/REVIEW/TASK-940-the-verifier-must-review-the-code.md'); assert 'review_range' in t, 'the acceptance prose is not extractable'; assert m.acceptance_text(None)=='', 'the negative control returned something'; print('OK acceptance prose extractable:', len(t), 'chars, control empty')"
```

### NEGATIVE CONTROL

Each command above must be able to fail. The fifth carries its own negative
control inline (`acceptance_text(None)` must be empty). The first fails on a
branch whose merge cannot be found; the second fails if the prompt is built from
the stat; the third fails in a worktree with no `config/.env` reachable, which is
exactly the state that made every GLM call today return `MissingKey`.

**COMMAND 4 WAS ITSELF VACUOUS AND IS REWRITTEN.** It asserted
`isinstance(by, dict)` and GLM caught it with the command's own output as the
evidence: it passed on `0 glm rows, 0 clients`, because `spendledger.path()`
resolves against the CALLING TREE's gitignored `work/` and an acceptance
worktree has no ledger at all. Measured: the main checkout held **39** glm rows
while the verifier's own worktree held **2** - its own calls, 30,688 micro-USD,
invisible to the production spend audit. The command now resolves the ledger
through `--git-common-dir`, refuses one that lands inside the calling tree, and
requires `rows > 0`, so it fails under the per-tree defect AND under the
retired-tenant blindness it was written for.

### Mutation

Revert the `diff_full` argument in `main`'s `_build_prompt` call to `diff_stat`
and command 2 must go red with "the patch is not in the prompt".

Three more, each applied alone, each with `__pycache__` wiped first so no
same-length edit can be served from a stale `.pyc`:

- drop `**CAPTURE` from `_git` and
  `test_the_diff_is_text_and_still_carries_the_character` goes red - the patch
  comes back `None` on any byte the locale codec cannot map;
- rebuild the patch as one alphabetical `git diff` and
  `test_the_code_hunk_comes_before_the_docs_hunk` goes red - `docs/` precedes
  `scripts/` and the truncation banner then cuts the code;
- have `ledger_path` fall back to `ROOT` instead of returning `None` and
  `test_the_ledger_sits_under_the_main_checkout_not_under_this_tree` goes red,
  as does acceptance command 4.

## Files

`scripts/glm_verify_branch.py`. The verifier is not allowed to grow a second
copy of any number it already reads from a constant.
