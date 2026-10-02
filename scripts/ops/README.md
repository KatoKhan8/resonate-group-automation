# scripts/ops — the tools a merge gate uses

These are operator tools, not production code. Nothing under `src/` imports
them, and that is deliberate: a gate tool that production depended on would be a
gate tool nobody could change during a release.

| tool | what it answers |
|---|---|
| `refdiff.py` | does this branch's suite run carry a NEW failing name against the reference? |
| `canarypath.py` | is this branch on the send path, measured by the import closure rather than judged? |

## `refdiff.py`

    python scripts/ops/refdiff.py <reference log> <branch log> [label]

**A baseline is a NAMED LIST and is compared by SET, never by count** — operator,
2026-10-02, after three finished suites each reported exactly 231 failing names
and one of them was a different 231. This tool prints its own two controls on
every run (the reference against itself must give 0 new, one planted name must
give exactly 1) and REFUSES a verdict if either fails, because a reader that
cannot see the thing makes its zeros worthless and those zeros are the whole
verdict.

It extracts failures with `run_suite._parse_failures` and normalises with
`suite_baseline.strip_prefix`. Not a grep: `grep -cE '^(FAIL|ERROR): '` over a
227-failure log returned **0**, because unittest only prints the closing summary
when a run finishes and a killed run never reaches it.

It finds those two modules by trying `REFDIFF_SCRIPTS`, then its own repository,
then the main checkout via `git rev-parse --path-format=absolute
--git-common-dir`, then the reference log's own directory — and prints which one
it used. The last candidate was the ONLY one it had until the reference logs were
moved out of a session scratchpad, at which point it died on
`FileNotFoundError`: a durability move that silently broke the one reader every
merge verdict rests on.

## `canarypath.py`

    python scripts/ops/canarypath.py <repo with all branches> <branch> [...]

Walks what the sending entry points actually import, transitively, inside
`src/`, and reports whether a branch touches that closure. Measured 2026-10-02:
the closure is **109 of 258** `src/` modules.

## What is NOT here, and where it lives

Large logs, the frozen reference checkout, the canary shortlist and the provider
readback are operational state, not code, so they stay out of git:

    C:\Users\Zvonimir\Desktop\resonate-ops

with its own `README.md` carrying the rule for each — including the one that
matters most: **nobody enters the frozen reference.** A gate worktree that
advances with master is not a reference; one was checked out from under a
44-minute run and that measurement was lost.

`copyreview.py` stays there rather than here on purpose: **it has never been
run.** Phase 0 has not started, `copy-review/` is empty, and existence is not
function. It comes into the repository the day it captures a real draft.
