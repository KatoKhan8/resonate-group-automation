PRIORITY: P2
SIZE: XS
DEPENDS:

# TASK-374 — the write-audit scanner does not exclude `.claude/`

Found 2026-09-26 verifying TASK-370 before merge. Not a production defect;
a local-environment stability gap in a safety-adjacent test.

## The defect

`tests/test_nothing_writes_to_a_provider.py:python_files()` excludes
`__pycache__`, `.git`, `work`, `node_modules`, `.venv`, `venv` from its walk —
not `.claude`, which `.gitignore` also excludes. A developer machine or CI
runner that has ever created an agent worktree under `.claude/worktrees/`
(a full checkout of the repo, including its own copy of every provider call)
will get hundreds of duplicate "undeclared write" findings that have nothing
to do with the actual repository — measured 2026-09-26: 708 spurious entries
from one leftover worktree, versus 25 real ones.

This does not affect what merges to master — `.claude/` is gitignored, so a
clean clone or CI checkout never has this problem — but it means the test is
not reliably runnable on a machine that has ever used a Claude Code worktree,
which is exactly the kind of machine running this suite tonight.

## Build

    tests/test_nothing_writes_to_a_provider.py   MODIFY, one line

Add `.claude` to the excluded-directories tuple in `python_files()`, the same
way `.git` and `work` are already excluded.

## Acceptance

1. Before: with a `.claude/worktrees/<anything>/` present containing a `.py`
   file with a provider-shaped POST, `test_every_http_write_in_the_repository_is_declared`
   fails with entries whose path starts `.claude/`.
2. After: the same fixture produces zero `.claude/`-prefixed findings.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against the current baseline. Not a count.

## What this task may NOT do

- Do not touch `ALLOWED`, `CALLS`, `REQUEST_METHOD` or `REQUEST_DATA` — this
  is a directory-exclusion fix only, unrelated to TASK-370's regex work.
- Nothing sent, nothing activated.

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: (pending)
TESTS: `python -m unittest tests.test_nothing_writes_to_a_provider -v` — 7/7 OK.
  Fixture proof: created `.claude/worktrees/fake/sneaky.py` containing a
  `Request(url, method="POST", data=b"")` call; `python_files()` returned
  zero `.claude/`-prefixed paths. Fixture removed after verification.
FILES CHANGED: `tests/test_nothing_writes_to_a_provider.py` — one line:
  added `".claude"` to the excluded-directories tuple in `python_files()`.
FINDINGS: None. The fix is exactly what the task described: a one-token
  addition to an existing exclusion tuple. No other directory needs the
  same treatment — `.claude/` is the only gitignored directory that can
  contain a full recursive checkout of the repository.
RISKS: None. The exclusion is a directory name filter on `os.walk`; it
  cannot mask a real finding in any non-`.claude` path.
RECOMMENDED CLAUDE ACTION: Cherry-pick onto master.
