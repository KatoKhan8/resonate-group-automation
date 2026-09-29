PRIORITY: P0
DEPENDS:

# TASK-292 — a push that cannot refuse is not a gate

## DISPATCH NOTE

Lane F, the standing QA suite. Eight tasks, TASK-292 … TASK-299.
**This one is the harness.** It is FIRST in usefulness and it is NOT a
dependency of the other seven: they conform to
`docs/QA-LANE-F-CONTRACT-2026-09-25.md`, which is committed, so eight workers
can run in parallel. `DEPENDS:` is empty **on purpose** — the registry parses
that line as comma-separated task ids and marks anything else BLOCKED, which
is how nine of lane E's thirteen tasks went invisible to `claim_task.py` on
2026-09-24.

**READ THE CONTRACT FIRST.** This task implements §§1-6 of it. Where this file
and the contract disagree, the contract wins and you report the disagreement.

In the minimum subset for **today's 128**.

## The question this answers

**When a pre-push check fails, does the push actually stop — on the real send
path, without a flag anybody can pass to get past it?**

And its twin, which is the one that has gone wrong here before: **can the
runner tell "every check passed" apart from "no check ran"?**

`scripts/qa/` does not exist on any branch as of `24acafff`. There is no
runner, no return shape, no refusal, no table. Everything that calls itself a
gate in this repository today is either inside `bisonfactory.stage` (the copy
lint, lane D, correct) or in a caller that the next caller will skip.

**TASK-277 is the precedent and it is two days old.** A copy lint was wired
into `src/push.py`, whose `run()` raises on `live=True` — *"live push is not
implemented in this build… No code here can reach EmailBison or HeyReach"* —
through `run_with_copylint`, which **nothing called**; only its own `.pyc`
matched. Eight tests proved it worked, and all eight called it directly; zero
called `push.run(`. The lint was wired into a module that refuses to send,
through a function nobody calls, proved by tests that call it directly. That
is the exact defect the task was written about, reproduced by the fix for it.

## What to build

`scripts/qa/__init__.py`, `scripts/qa/run.py`, and their tests.

1. **The registry.** `CHECKS` — an ordered tuple of
   `(check_id, module_name, phase, blocking)`. A module not listed does not
   run. Ship it listing all seven check ids from the contract with their
   modules, so a check landing later is one line and not a wiring exercise.
   A listed module that does not yet exist reports `NOT_IMPLEMENTED` in the
   table — **not PASS, and not silence.**
2. **The verdict and exit-code vocabulary**, contract §3:
   `PASS/FAIL/UNCONFIRMED/VACUOUS/ERROR` → `0/1/2/2/3`, with the per-phase
   refusal semantics. Put the phase mapping in ONE table in `__init__.py`; two
   copies is how pre-push and post-push come to disagree about what 2 means.
3. **The result validator.** The runner **asserts** the five invariants of
   contract §4 on every result it receives, and downgrades a result that
   breaks one to `ERROR`. It does not trust the check:
   - offenders and unverifiable hold ids, not counts, not `"…"`;
   - `clean + |union of offenders and unverifiable| == subjects`;
   - `subjects == 0` is VACUOUS, never PASS, and carries a stated reason;
   - `rules`, `counts`, `offenders` keys agree in both directions;
   - rule sentences are rendered from the run's parameters (see §5 below).
4. **`run.py --phase <phase>`** runs every blocking check for the phase,
   writes `work/qa/<run-id>/<check>.json` per check and a `TABLE.md`, returns
   the worst verdict, and renders the table.
5. **`_refuse_qa(plan, recs, report)` in `src/bisonfactory.py`**, immediately
   after lane D's `_refuse_copylint` at line 86 and **before**
   `bison.bound_workspace()` — the first provider call of any kind. It raises
   `FactoryRefused` carrying **the runner's own rendered table**, not a
   sentence written at the raise site, so a rule that did not exist when the
   function was written still names itself in the refusal. Same for
   `heyreachfactory.stage` at its equivalent seam.
   **See BOUNDARIES — lane D holds `bisonfactory`. Deliver this as a patch
   proposal in the result block, not as an edit, unless the branch has landed
   by the time you start and you can see `_refuse_copylint` in master.**
6. **The table renderer**, contract §6 — one renderer used by both the Slack
   post and the refusal text, so they are the same bytes. Every registered
   check gets a row. No prospect ids in the table; a path to the artefact.

## The acceptance bar

- **A test asserts that every `scripts/qa/check_*.py` on disk appears in
  `CHECKS`.** Not a grep of the source — an `os.listdir` of the directory
  against the tuple. A check with no registration is a check with no caller.
- **A test drives the REAL send path.** It calls `bisonfactory.stage(...,
  live=True)` with a check rigged to FAIL and asserts `FactoryRefused` is
  raised, **and asserts that no provider call was made** — assert on the
  provider module being untouched (no HTTP, no `bison.bound_workspace`), not
  on a log line. A test that calls `_refuse_qa` directly proves nothing; that
  is TASK-277's defect verbatim.
- **A test asserts the refusal text contains the offending ids and the rule
  names the check produced**, including a rule name the test invents at run
  time. If the refusal is a hardcoded sentence, this test fails.
- **A test asserts `subjects == 0` does not pass.** Register a check that
  returns zero subjects, run `--phase pre_push`, assert the runner refuses and
  the table row reads `VACUOUS` with the stated reason.
- **A test asserts a check returning `clean=128, subjects=128` while its
  offenders list is non-empty is downgraded to ERROR.** The arithmetic
  invariant must be enforced by the runner, not by the check's good manners.
- **A test asserts the exit code is the WORST verdict, not a count and not a
  boolean from a filter.** Three "green" runs in this repository meant nothing
  because a test run was piped into a filter and the filter's exit code was
  read.
- **The table is rendered for a run where one check passed, one failed, one
  was vacuous and one is not implemented, and all four rows are present.**
- There is **no `--skip-qa`, no `--force`, no environment variable** that
  disables a blocking check. `grep -rn` your own tree for one and paste the
  empty result. The only escape is `blocking=False` in `CHECKS`, in a commit.
- Suite baseline taken **by name**, both directions, against `HEAD~1`. A count
  is not a baseline.

## What evidence counts

- The import-graph trace from `scripts/batch1_push.py` to `_refuse_qa`:
  `batch1_push` → `bisonfactory.stage` → `_refuse_qa`. Print it from the
  module objects, not from a grep. `dir()` the module and show the name is
  really bound.
- The test that rigs a failing check and shows `FactoryRefused` raised with
  zero provider calls, with its output pasted.
- The rendered table for the four-state run, pasted verbatim.
- One real `--phase pre_push` run against a **copy of production's `work/`**,
  named with its path and mtime, even if every check is NOT_IMPLEMENTED — the
  point is that the runner, the artefact directory and the table are real.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Wiring the gate into `scripts/batch1_push.py` or
  `scripts/batch_preflight.py` instead of the factory.** A gate in the caller
  is a gate the next caller skips. `batch_preflight` is a PRUNER and stays
  one; a green pre-flight is not a licence to skip the gate.
- **Tests that call `_refuse_qa` or `run.main()` directly and never call
  `bisonfactory.stage`.** This is TASK-277 exactly. At least one test must
  enter through the real send path.
- **A runner that reports PASS when it ran nothing.** If `CHECKS` is empty, if
  every module is missing, if the phase matched no check — that is not a pass.
  Construct each of those three and show the runner refusing.
- **A runner that treats UNCONFIRMED as PASS pre-push** because "the provider
  was flaky and we didn't want to block the push". Pre-push, nothing has been
  written; the cost of refusing is a delay.
- **A table that lists only failures.** It cannot be told apart from a table
  where nothing ran. Every registered check gets a row.
- **Mocking the factory.** A test double for `bisonfactory.stage` proves the
  double refuses. Use the real function with the provider layer unreachable,
  and assert that it was unreachable.
- **A green unit suite as the evidence that the gate works live.** ~30 tests
  were green in this repo against three Apify actor ids that answer 404,
  because the cassette and the code agreed with each other and neither agreed
  with Apify. Run the runner against the real estate once.
- **Prospect ids in the Slack table.** Counts in the channel, ids in the file.

## Boundaries

- **NO provider writes of any kind.** Reads only, and this task needs very
  few.
- **`src/bisonfactory.py` is LANE D's** (branch
  `worktree-agent-a63bd2d9102384dba` @ `c38c5934`, unmerged). Do not edit it
  on a branch where lane D's copylint wiring is absent — you would write a
  conflicting version of the same seam. Deliver `_refuse_qa` and its call site
  as an exact patch in the result block; the production session applies it
  after lane D lands. If lane D has landed when you start, say so with the sha
  and edit it.
- Do not edit `config/.env`, `src/providers/*`, `scripts/*_watch_loop.py`, or
  anything under `work/` except `work/qa/`.
- Production `work/` is not yours. `--workspaces` is required and has no
  default; a worktree has its own stale `work/` and the one that had it was 37
  minutes behind production.

## Files

    ALLOWED    scripts/qa/__init__.py, scripts/qa/run.py,
               tests/test_the_qa_gate_stops_the_real_send_path.py,
               tests/test_a_qa_result_that_does_not_add_up_is_an_error.py,
               docs/QA-HARNESS-2026-09-25.md
    FORBIDDEN  src/bisonfactory.py and src/heyreachfactory.py (PATCH PROPOSAL
               ONLY — see boundaries), src/copylint.py, src/packfacts.py,
               src/cadence.py, config/clients/productive.yaml,
               scripts/batch1_build.py, src/providers/*, work/* except
               work/qa/, config/.env

## Result block

    STATUS:
    BRANCH:
    COMMIT SHA:
    TESTS:
    FILES CHANGED:
    IMPORT-GRAPH TRACE batch1_push -> stage -> _refuse_qa (from module objects):
    THE FAILING-CHECK TEST: refusal raised? provider calls made?:
    FOUR-STATE TABLE (pasted):
    ZERO-SUBJECT RUN: verdict and stated reason:
    ARITHMETIC-INVARIANT DOWNGRADE: shown?:
    GREP FOR A BYPASS FLAG (result pasted):
    _refuse_qa PATCH PROPOSAL (exact, or the sha you edited at):
    WORKSPACES COPY USED (path, mtime, rows):
    SUITE BASELINE vs HEAD~1 — new/gone BY NAME, both directions:
    FINDINGS:
    RISKS:
    RECOMMENDED CLAUDE ACTION:
