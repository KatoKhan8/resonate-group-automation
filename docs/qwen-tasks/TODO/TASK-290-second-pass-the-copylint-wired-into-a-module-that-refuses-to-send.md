PRIORITY: P0
DEPENDS:

# TASK-290 — second pass: the copy lint was wired into a module that refuses to send

## THE VERDICT IS ALREADY ESTABLISHED. DO NOT RE-DERIVE IT.

Read in full by the production session on 2026-09-24 and recorded in
`docs/PRODUCTION-HANDOFF-2026-09-24-LATE.md` §4.1:

> TASK-277 claims *"the copy lint is on the send path, not merely present."*
> It is not:
>
> - `run_with_copylint` is **called by nothing** — only its own `.pyc` matches.
> - All 8 tests call it **directly**; 0 call `push.run(`.
> - `src/push.py` is **not the send path**. Its `run()` raises on `live=True`:
>   *"live push is not implemented in this build… No code here can reach
>   EmailBison or HeyReach."* The real path is `scripts/batch1_push.py` →
>   `bisonfactory.stage`.
>
> So the lint was wired into a module that refuses to send, through a function
> nobody calls, proved by tests that call it directly. **That is the exact
> defect the task was written about, reproduced by the fix for it.**

**STATUS: REJECTED. It does not go to master.**

**THE RE-WIRING IS NOT YOURS.** The lint belongs in `bisonfactory.stage`
before the attach, and another lane is doing that work right now. **Do not
edit `src/push.py`, `src/bisonfactory.py`, `src/copylint.py` or the lint call
site.** Two hands on that file is how this gets fixed twice and merged once.

## The question THIS task answers

**What else in the delivery is salvageable, and what is the general check that
stops this shape from shipping again?**

## What to do

1. **Salvage.** Of the 8 tests, which assert something true about the LINT
   itself (a rule catching what it should) as opposed to the wiring? Those may
   be worth keeping. List them by name with a keep/discard recommendation and
   a reason. **Do not move them** — recommend.
2. **Write the wiring assertion the lane will need**, as a test that fails
   today and will pass when the lane lands its change:
   - a batch containing a lead whose copy breaks a lint rule **cannot be
     staged** — assert on the **push refusing**, not on the lint returning a
     finding;
   - the refusal **names the lead and the rule**;
   - the lint runs **before** any provider write, not after. The blank-render
     gate already fails this way round: it refuses after the attach and the
     refusal does not roll back;
   - a rule added later is enforced automatically — the wiring reads the rule
     SET, it does not enumerate rules. Add a rule in the test and assert it
     bites without touching the call site.

   Put these in a NEW file so the lane can take it whole:
   `tests/test_the_lint_refuses_the_real_push.py`. It may be entirely RED.
   **Say which assertions are red and why.**
3. **Rule 5 of TASK-277 — is `outreachclaims` reachable from the send path?**
   Answer yes or no with a grep, and if no, leave the test red and record it
   as a finding rather than deleting it.
4. **The general check.** Propose a repository-level test that fails whenever
   a guard module has no caller on the real send path — the shape that has now
   cost `heyreach.linkedin_sequence`, `extract_prospect_text`,
   `outreachclaims` and this one. An import-graph assertion, not a text grep.

## The acceptance bar

- The salvage table: 8 tests, keep/discard, reason each.
- The new test file exists, and **every assertion in it is driven through
  `scripts/batch1_push.py` / `bisonfactory.stage`, never through
  `push.run`**. If your test imports `src/push.py`, you have reproduced the
  defect a second time.
- For each assertion: RED or GREEN today, with the message.
- The `outreachclaims` answer with its grep output.
- The general check is specified precisely enough to implement — which module
  set, which entry point, what "reachable" means — even if it is not built
  here.

## What evidence counts

- `grep -rn "run_with_copylint" src/ scripts/ tests/` output pasted. If the
  only non-test hit is the definition, that is the finding restated with
  evidence.
- The `push.run()` refusal message, quoted from the file.
- The real send path traced by name: entry script → function → provider call.
- Raw output of the new test module, run alone.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Re-deriving the verdict** instead of building on it. It is established.
- **Fixing the wiring.** That is another lane's. Write the test; leave it red.
- **A test that calls the lint directly and reports the lint works.** That is
  precisely what was rejected. The unit was never the risk.
- **Asserting on source text.** `grep "copylint" src/bisonfactory.py` returns
  a line when somebody writes a comment. Assert on the push REFUSING.
- **A green run treated as proof of wiring.** Break the wiring — delete the
  CALL, not the logic — and re-run. If your tests still pass, they prove
  nothing about connection, and connection is the whole task.
- **Touching `src/push.py`, `src/bisonfactory.py` or `src/copylint.py`.**
  Forbidden here, without exception.

## Boundaries

- **No provider writes, and no live push of any kind.** The assertions are
  about a refusal; a refusal is observable without sending.
- Tests and docs only.
- Do not merge, do not push to master.

## Files

    ALLOWED    tests/test_the_lint_refuses_the_real_push.py,
               docs/COPYLINT-SECOND-PASS-2026-09-25.md,
               docs/qwen-tasks/REVIEW/TASK-277-copylint-wiring-tests.md
               (append a REVIEW block recording the REJECTED verdict)
    FORBIDDEN  src/push.py, src/bisonfactory.py, src/copylint.py,
               scripts/batch1_push.py, src/providers/*, work/*, config/.env

## Result block

    BRANCH:
    COMMIT:
    SALVAGE TABLE (8 tests: keep/discard + reason):
    NEW TEST FILE ASSERTIONS, EACH RED OR GREEN, WITH MESSAGE:
    THE REAL SEND PATH, TRACED BY NAME:
    grep -rn run_with_copylint src/ scripts/ tests/:
    IS outreachclaims REACHABLE FROM THE SEND PATH, YES/NO + grep:
    THE PROPOSED GENERAL CHECK (module set, entry point, definition of
      reachable):
    CONFIRM: I DID NOT EDIT push.py, bisonfactory.py OR copylint.py
