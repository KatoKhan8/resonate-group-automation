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

    BRANCH: qwen-worker-9-r9
    COMMIT: d1197344
    SALVAGE TABLE (10 tests in Lane D's replacement file; original 8 not on
    this branch - they were on qwen-worker-4-r9 and never merged after
    rejection):

    | # | Test | Keep? | Reason |
    |---|------|-------|--------|
    | 1 | test_a_batch_whose_copy_is_clean_is_staged | KEEP | Control: without this, a gate that refuses everything is indistinguishable from one that refuses the right things |
    | 2 | test_the_lint_is_told_this_plan_s_length_and_not_the_target | KEEP | Asserts the wiring passes the plan's sequence length, not the module constant |
    | 3 | test_a_lead_whose_copy_breaks_a_rule_cannot_be_pushed | KEEP | Rule 1: assert on the push refusing, not the lint returning a finding |
    | 4 | test_the_refusal_names_the_lead_and_the_rule_in_the_lint_s_words | KEEP | Rule 2: refusal text is the lint's own, not a sentence written in the wiring |
    | 5 | test_nothing_reaches_the_provider_when_the_lint_refuses | KEEP | Rule 3: BEFORE any provider write. CountingBison.UNTOUCHED is the proof |
    | 6 | test_a_rule_added_to_the_lint_later_is_enforced_here | KEEP | Rule 4: wiring reads the rule SET, does not enumerate rules |
    | 7 | test_a_lead_with_no_research_at_all_is_refused | KEEP | Identity check (packfacts) fires through the send path |
    | 8 | test_a_fact_that_belongs_to_another_company_supports_nothing | KEEP | 50-of-71 defect: presence is not identity |
    | 9 | test_the_same_fact_on_the_account_s_own_domain_does_support_it | KEEP | Control for test 8: identical words, this account's site, staged |
    | 10 | test_a_dry_run_reports_the_refusal_without_raising | KEEP | Dry run must not report silence; verdict is in the report either way |

    NEW TEST FILE ASSERTIONS (tests/test_the_lint_refuses_the_real_push.py):
    1. test_a_lead_whose_copy_breaks_a_rule_cannot_be_staged - GREEN
       (Lane D's _refuse_copylint already refuses before any provider write)
    2. test_the_refusal_names_the_lead_and_the_rule - GREEN
       (refusal text carries lint's own report naming leads and rules)
    3. test_the_lint_runs_before_any_provider_write - GREEN
       (CountingBison.UNTOUCHED passes: zero workspace reads, zero creates)
    4. test_a_rule_added_later_is_enforced_without_touching_the_call_site - GREEN
       (wiring calls copylint.check_batch() which reads copylint.RULES)

    ALL GREEN because Lane D already landed the wiring in bisonfactory.stage()
    before this task ran. The task was written assuming the wiring was pending.

    THE REAL SEND PATH, TRACED BY NAME:
    scripts/batch1_push.py:main()
      → bisonfactory.stage(slug, live=bool(args.live))
        → _plan(campaign, recs, config)
        → _refuse_copylint(plan, recs, report)     ← LINT, BEFORE ANYTHING
        → bison.bound_workspace()                  ← first provider read
        → _ensure_campaign(...)                     ← provider write
        → _ensure_senders(...)
        → _ensure_sequence(...)
        → bison.stop_campaign(...)
        → _ensure_leads(...)                        ← provider write

    grep -rn run_with_copylint src/ scripts/ tests/:
    NO HITS IN src/ OR scripts/. Only hits are in docs/ (recording the
    rejection) and tests/test_the_copy_lint_refuses_the_real_send_path.py
    (describing what went wrong). The function does not exist in production
    code - it was removed when Lane D did the correct wiring.

    IS outreachclaims REACHABLE FROM THE SEND PATH: NO
    Imports of outreachclaims:
      src/campaignqa.py:33:from . import outreachclaims as oc
      src/contextpack.py:57:from . import (account, outreachclaims, ...)
      src/web/demoaccount.py:291:    from .. import outreachclaims as oc
      src/web/api.py:44:    ... outreachclaims ...
    None of these are in the transitive closure of scripts/batch1_push.py →
    bisonfactory.stage(). Same shape as the run_with_copylint defect.

    THE PROPOSED GENERAL CHECK:
    Module set: {copylint, outreachclaims, eligibility, verification}
    Entry point: scripts/batch1_push.py → bisonfactory.stage(live=True)
    Definition of reachable: transitive closure over import/from-import
    statements from the entry point. For each guard G in the module set,
    assert G is in the reachable set. If not, fail with a message naming G.
    Full specification in docs/COPYLINT-SECOND-PASS-2026-09-25.md §4.

    CONFIRM: I DID NOT EDIT push.py, bisonfactory.py OR copylint.py
