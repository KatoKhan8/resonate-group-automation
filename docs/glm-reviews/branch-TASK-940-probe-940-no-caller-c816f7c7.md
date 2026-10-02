# GLM branch verification: TASK-940

Branch: `probe-940-no-caller`
Date: 2026-10-02T15:23:29.079391+00:00
Model: glm-5.3
Duration: 41.517s
Usage: {'prompt_tokens': 2051, 'completion_tokens': 2960, 'total_tokens': 5011, 'reasoning_tokens': 2293, 'cached_tokens': 128}

## Verdict: FAIL

**all five acceptance commands exit=1 (verifier functions missing or signature-mismatched), the single changed file src/collision.py implements neither TASK-940's verifier nor any caller for the new dead function.**

## GLM spend

This call: 1 ledger rows, 5556 micro-USD

## Changed files (1)

- `src/collision.py`

## Diff stat

```
 src/collision.py | 12 ++++++++++++
 1 file changed, 12 insertions(+)

```

## Acceptance output

```
$ python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); b,h,how=m.review_range('task-suite-lock'); assert b, 'merged branch resolved to no range'; assert 'merged by' in how, how; fs=m._changed_files('task-suite-lock'); assert len(fs)==4, fs; print('OK merged-branch range:', how, len(fs), 'files')"
exit=1
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); b,h,how=m.review_range('task-suite-lock'); assert b, 'merged branch resolved to no range'; assert 'merged by' in how, how; fs=m._changed_files('task-suite-lock'); assert len(fs)==4, fs; print('OK merged-branch range:', how, len(fs), 'files')
                                                                                                                                                                                               ^^^^^^^^^^^^^^
AttributeError: module 'v' has no attribute 'review_range'

$ python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); st,df=m._diff_against_master('task-suite-lock'); p=m._build_prompt('b','T',['src/suitelock.py'],st,df,'ran','tests'); assert 'def acquire' in p, 'the patch is not in the prompt'; assert len(p) < 60000, len(p); print('OK the prompt carries the patch:', len(p), 'chars')"
exit=1
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); st,df=m._diff_against_master('task-suite-lock'); p=m._build_prompt('b','T',['src/suitelock.py'],st,df,'ran','tests'); assert 'def acquire' in p, 'the patch is not in the prompt'; assert len(p) < 60000, len(p); print('OK the prompt carries the patch:', len(p), 'chars')
                                                                                                                                                                                                                                          ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _build_prompt() takes 6 positional arguments but 7 were given

$ python -c "import sys,os; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); p=m.env_path(); assert os.path.isfile(p), 'no config/.env reachable from a worktree: '+p; print('OK credentials reachable:', os.path.basename(os.path.dirname(os.path.dirname(p))))"
exit=1
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import sys,os; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); p=m.env_path(); assert os.path.isfile(p), 'no config/.env reachable from a worktree: '+p; print('OK credentials reachable:', os.path.basename(os.path.dirname(os.path.dirname(p))))
                                                                                                                                                                                            ^^^^^^^^^^
AttributeError: module 'v' has no attribute 'env_path'

$ python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); r,c,by=m._read_spend(); assert isinstance(by,dict), by; print('OK spend reads by provider, not by a retired tenant:', r, 'glm rows,', len(by), 'clients')"
exit=1
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); r,c,by=m._read_spend(); assert isinstance(by,dict), by; print('OK spend reads by provider, not by a retired tenant:', r, 'glm rows,', len(by), 'clients')
                                                                                                                                                                                       ^^^^^^
ValueError: not enough values to unpack (expected 3, got 2)

$ python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); t=m.acceptance_text('docs/qwen-tasks/REVIEW/TASK-940-the-verifier-must-review-the-code.md'); assert 'review_range' in t, 'the acceptance prose is not extractable'; assert m.acceptance_text(None)=='', 'the negative control returned something'; print('OK acceptance prose extractable:', len(t), 'chars, control empty')"
exit=1
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); t=m.acceptance_text('docs/qwen-tasks/REVIEW/TASK-940-the-verifier-must-review-the-code.md'); assert 'review_range' in t, 'the acceptance prose is not extractable'; assert m.acceptance_text(None)=='', 'the negative control returned something'; print('OK acceptance prose extractable:', len(t), 'chars, control empty')
                                                                                                                                                                                         ^^^^^^^^^^^^^^^^^
AttributeError: module 'v' has no attribute 'acceptance_text'
```

## GLM response

**1. Production caller for the new code?**
NO CALLER. The only changed file is `src/collision.py`; the diff adds exactly one symbol, `reconcile_owner_with_ledger(campaign_id, ledger_rows=None)` (added lines 1417–1428, appended *after* the `if __name__ == "__main__": raise SystemExit(main())` guard at line 1416). No call site appears in the diff, and no other file was touched to add one. The "bridge" bridging `collision.py` to the ledger connects to nothing. Latent bug worth noting: `reconcile_owner_with_ledger(None, [{}])` returns `"OURS"`, because `str(row.get("bison_campaign_id")) == str(None) == "None"` — a false ownership verdict on a missing key — but with no caller this is dead code, not a live cost.

**2. Can the acceptance check fail?**
It doesn't need an input — it already fails. All five commands exited 1:
- `m.review_range` → AttributeError (function absent from `scripts/glm_verify_branch.py`)
- `m._build_prompt` → TypeError, 6 params vs 7 passed
- `m.env_path` → AttributeError
- `m._read_spend` → ValueError, returns 2 values, 3 unpacked
- `m.acceptance_text` → AttributeError

Beyond that, the acceptance suite belongs to a different task: it targets branch `task-suite-lock`, asserts `'def acquire' in p` (a `suitelock.py` symbol), and expects 4 changed files. Even with the script's signatures fixed, command 2 fails on this branch: the patch contains `reconcile_owner_with_ledger`, not `def acquire`. And none of the five commands reference `collision.py` or invoke the new function, so the change itself is never exercised.

**3. Do the numbers reconcile?**
No. `assert len(fs)==4` vs the diff stat `1 file changed, 12 insertions(+)` → 1 ≠ 4. No `print` statement in any command ever executed, so zero measurements were produced. Nothing in the result block reconciles because there is no result block.

**Also check**
- **File–task match:** `src/collision.py` does NOT answer to TASK-940. The acceptance path `docs/qwen-tasks/REVIEW/TASK-940-the-verifier-must-review-the-code.md` and the five commands show TASK-940 is about implementing the verifier (`review_range`, `_build_prompt` w/ 7 args, `env_path`, 3-tuple `_read_spend`, `acceptance_text`) in `scripts/glm_verify_branch.py` — a file this branch never touches. The added function is unrelated scope.
- **Scratch files:** none at repo root; changed-files list contains only `src/collision.py`.

VERDICT: FAIL - all five acceptance commands exit=1 (verifier functions missing or signature-mismatched), the single changed file src/collision.py implements neither TASK-940's verifier nor any caller for the new dead function.
