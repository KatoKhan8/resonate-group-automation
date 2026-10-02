# GLM branch verification: TASK-940

Branch: `task-940-glm-verifier`
Date: 2026-10-02T19:48:25.062650+00:00
Model: glm-5.3
Duration: 155.91s
Usage: {'prompt_tokens': 14943, 'completion_tokens': 12200, 'total_tokens': 27143, 'reasoning_tokens': 11093, 'cached_tokens': 14656}

## Verdict: NEEDS_CLAUDE

**30,596 unseen chars include the scratch-override and report-writer tail of main(), and the JSON baseline the tests pin to 231 entries is not among the branch's changed files, so its post-merge existence cannot be determined from this diff.**

## GLM spend

This call: 1 ledger rows, 25497 micro-USD

## Changed files (7)

- `docs/glm-reviews/branch-TASK-903-task-step-objectives-convergence-8a542b7c.md`
- `docs/glm-reviews/branch-TASK-940-probe-940-no-caller-c816f7c7.md`
- `docs/glm-reviews/branch-TASK-942-task-942-token-budget-73bc571e.md`
- `docs/glm-reviews/branch-TASK-946-task-lock-atomic-publish-4f11c8f7.md`
- `docs/qwen-tasks/REVIEW/TASK-940-the-verifier-must-review-the-code.md`
- `scripts/glm_verify_branch.py`
- `tests/test_the_glm_verdict_compares_like_with_like.py`

## Diff stat

```
 ...03-task-step-objectives-convergence-8a542b7c.md |  93 ++++
 ...branch-TASK-940-probe-940-no-caller-c816f7c7.md |  95 ++++
 ...anch-TASK-942-task-942-token-budget-73bc571e.md | 134 ++++++
 ...h-TASK-946-task-lock-atomic-publish-4f11c8f7.md |  84 ++++
 .../TASK-940-the-verifier-must-review-the-code.md  |  47 ++
 scripts/glm_verify_branch.py                       | 524 ++++++++++++++++++---
 ...test_the_glm_verdict_compares_like_with_like.py | 189 +++++++-
 7 files changed, 1094 insertions(+), 72 deletions(-)

```

## Acceptance output

```
$ python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); b,h,how=m.review_range('task-suite-lock'); assert b, 'merged branch resolved to no range'; assert 'merged by' in how, how; fs=m._changed_files('task-suite-lock'); assert len(fs)==4, fs; print('OK merged-branch range:', how, len(fs), 'files')"
exit=0
OK merged-branch range: merged by 6f3aeda2 4 files

$ python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); st,df=m._diff_against_master('task-suite-lock'); p=m._build_prompt('b','T',['src/suitelock.py'],st,df,'ran','tests'); assert 'def acquire' in p, 'the patch is not in the prompt'; assert len(p) < 60000, len(p); print('OK the prompt carries the patch:', len(p), 'chars')"
exit=0
OK the prompt carries the patch: 24984 chars

$ python -c "import sys,os; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); p=m.env_path(); assert os.path.isfile(p), 'no config/.env reachable from a worktree: '+p; print('OK credentials reachable:', os.path.basename(os.path.dirname(os.path.dirname(p))))"
exit=0
OK credentials reachable: resonate-group-automation

$ python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); r,c,by=m._read_spend(); assert isinstance(by,dict), by; print('OK spend reads by provider, not by a retired tenant:', r, 'glm rows,', len(by), 'clients')"
exit=0
OK spend reads by provider, not by a retired tenant: 0 glm rows, 0 clients

$ python -c "import sys; sys.path.insert(0,'.'); import importlib.util as u; s=u.spec_from_file_location('v','scripts/glm_verify_branch.py'); m=u.module_from_spec(s); s.loader.exec_module(m); t=m.acceptance_text('docs/qwen-tasks/REVIEW/TASK-940-the-verifier-must-review-the-code.md'); assert 'review_range' in t, 'the acceptance prose is not extractable'; assert m.acceptance_text(None)=='', 'the negative control returned something'; print('OK acceptance prose extractable:', len(t), 'chars, control empty')"
exit=0
OK acceptance prose extractable: 2696 chars, control empty
```

## GLM response

## Findings

**F1 — Acceptance command 4 is vacuous as run, and its own output proves it.**
The command executes `_read_spend()` with `cwd=wt_path` (the acceptance worktree) and `sys.path.insert(0,'.')` → it imports the worktree's `src.spendledger`. The ledger is a gitignored runtime file; this branch's own `env_path()` docstring states the principle: "a worktree created by `git worktree add` has NONE." Measured output: `0 glm rows, 0 clients` — while this same branch commits review docs recording billed calls from the same day (`branch-TASK-903-...md`: "This call: 1 ledger rows, 15389 micro-USD"; plus probe-940, 942, 946). The assert is `isinstance(by, dict)` — no ledger *content* can fail it. The retired-tenant blindness this check claims to guard against ("filtered `client == "_model"`, matched nothing, printed 0 rows") also prints 0 rows on an empty ledger. Cost: the spend-accounting fix ships with zero guarding evidence. Fix: resolve the ledger via `--git-common-dir` like `env_path()`, and assert `rows > 0`.

**F2 — The baseline the tests pin is not carried by the branch.**
`BASELINE_PATH` → `docs/state/SUITE-BASELINE-2026-10-02-FULL.json`. It is **not** among the 7 changed files, and nothing in this diff creates it. `test_the_json_baseline_holds_231_named_failures` does `assertEqual(231, len(baseline))`; `_load_baseline` returns `set()` when the file is absent. Failing input: clean checkout of merged master if that JSON is untracked or lives on an unmerged sibling → `231 != 0`, suite red at integration. The green run only proves the operator's tree has the file. Cannot be resolved from this diff.

**F3 — 30,596 of 79,833 patch characters are unseen, including verdict-affecting code.**
The diff cuts off mid-comment at `@@ -586,7` ("# Override verdict on deterministic failures / if scratch:") — the scratch-file override and the entire report writer after `fh.write(f"# GLM branch verification...")` are uninspectable. Per the banner's own rule, this alone forces NEEDS_CLAUDE.

## The three questions

**1. Caller:** YES. Within `scripts/glm_verify_branch.py`: `main()` calls `env_path()` (Step 4), `review_range()` (twice directly, plus via `_diff_against_master`/`_changed_files`/`_changed_test_files`), `acceptance_text()` (under `acceptance_missing`), `_read_spend_safely()` (before/after the call); `_merge_commit_for` ← `review_range`. The script's own invocation is evidenced by four committed run records dated 2026-10-02. No orphan bridge in the visible ~62k chars — but the tail of `main()` is unseen (F3).

**2. Can acceptance fail?** Commands 1, 2, 3, 5: yes — unmerged branch fails `assert b`; oversized/missing patch fails `'def acquire' in p` or `len(p) < 60000`; missing `.env` fails `isfile`; extractor regression fails `'review_range' in t`. Command 4: **no ledger content can fail it** — see F1. One of five guards is vacuous.

**3. Numbers:** Banner: 49,237 + 30,596 = 79,833 ✓. Diffstat: 1,094 + 72 = 1,166 = 93+95+134+84+47+524+189 ✓. "Ran 14 tests" = 14 tests listed ✓. TASK-903 usage: 14,892 + 5,895 = 20,787 ✓. Not recomputable from this diff: 15,389 µUSD (no price table) and baseline 231 (file absent from the diff — F2). `_build_prompt` arithmetic is sound: `render("") + banner(≤400) + (room−400) ≤ MAX − SYSTEM − 2000`.

## Also check

- `docs/glm-reviews/branch-TASK-{903,940,942,946}-*.md` are tool *outputs* about other tasks, including one on a synthetic probe branch (`probe-940-no-caller`). Defensible as evidence for TASK-940; they are run exhaust, not deliverables. Flagged, not disqualifying.
- Scratch files at repo root: none among the changes ✓.

VERDICT: NEEDS_CLAUDE - 30,596 unseen chars include the scratch-override and report-writer tail of main(), and the JSON baseline the tests pin to 231 entries is not among the branch's changed files, so its post-merge existence cannot be determined from this diff.
