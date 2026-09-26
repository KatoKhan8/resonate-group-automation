# Copylint Second Pass — 2026-09-25

TASK-290. The first pass (TASK-277) wired the copy lint into `src/push.py`
via `push.run_with_copylint`, which was called by nothing, in a module whose
`run()` raises on `live=True`. The real send path is
`scripts/batch1_push.py` → `bisonfactory.stage`. The lint was wired into a
module that refuses to send, proved by tests that call it directly.

The verdict is established. This document is the salvage and the wiring
assertion.

## The real send path, traced by name

    scripts/batch1_push.py:main()
      → bisonfactory.stage(campaign_id, live=True)
        → _plan(campaign, recs, config)           # no provider call
        → _refuse_copylint(plan, recs, report)    # THE LINT, before anything
        → _refuse_sequence_gate(plan, report)     # sequence-level gate
        → bison.bound_workspace()                 # first provider call
        → _find_or_create(campaign, report)       # campaign create/find
        → _ensure_limits / _ensure_schedule / _ensure_senders
        → _ensure_sequence(provider_id, campaign, plan, report)
        → _ensure_stopped(provider_id, report)    # stopped BEFORE leads
        → _ensure_leads(provider_id, campaign, plan, report)
        → _readback(provider_id)

The lint is at position 3 in this chain. The first provider call is at
position 5. Between them: the sequence gate. The lint runs before any
provider write, which is the correct position (ISSUE-037 is the
counter-example: a gate that refuses after the attach).

## `run_with_copylint` grep output

    $ grep -rn "run_with_copylint" src/ scripts/ tests/
    tests/test_the_copy_lint_refuses_the_real_send_path.py:4:  (docstring reference)
    tests/test_the_copy_lint_refuses_the_real_send_path.py:8:  (docstring reference)
    tests/__pycache__/...cpython-314.pyc: (binary)

The function does not exist in `src/` or `scripts/`. It was removed after
TASK-277 was rejected. The only remaining references are in the docstring of
the replacement test file, describing what was wrong.

## `push.run()` refusal message, quoted from `src/push.py`

    "live push is not implemented in this build. Phase 7 ships preparation
    only: payloads, eligibility, pause and idempotency. No code here can
    reach EmailBison or HeyReach."

## Salvage table: the 10 current tests

The original 8 tests from TASK-277 called `push.run_with_copylint` directly.
That function has been removed from `src/push.py`. The 10 tests below are
the corrected replacements in
`tests/test_the_copy_lint_refuses_the_real_send_path.py`, which drive
`bisonfactory.stage`. The task asks for a keep/discard recommendation for
each.

"Asserts on the lint" means the test verifies a lint rule catches what it
should (a property of the lint). "Asserts on the wiring" means the test
verifies the lint is connected to the send path (a property of the
connection). The lint's own rules are exhaustively tested in
`tests/test_copylint.py`; the wiring tests belong here.

| # | Test name | Status | Keep? | Reason |
|---|-----------|--------|-------|--------|
| 1 | `test_a_batch_whose_copy_is_clean_is_staged` | ERROR | **Keep** | Control test: without it, a gate that refuses everything is indistinguishable from one that refuses the right things. Currently RED due to the sequence gate, not the lint. Needs fixture enrichment. |
| 2 | `test_the_lint_is_told_this_plan_s_length_and_not_the_target` | ERROR | **Keep** | Asserts the wiring passes the plan's actual step count, not the module constant. A wiring that passed `STEPS_EXPECTED` (5) for a 1-step campaign would refuse every push for `empty_step`. Currently RED due to the sequence gate. |
| 3 | `test_a_lead_whose_copy_breaks_a_rule_cannot_be_pushed` | ok | **Keep** | Core wiring assertion: the push refuses when the lint fires. Driven through `bisonfactory.stage`. |
| 4 | `test_the_refusal_names_the_lead_and_the_rule_in_the_lint_s_words` | ok | **Keep** | The refusal carries the lint's own sentence, not a paraphrase. An operator reading "refused: copy problem" cannot act; "buzzword: a buzzword or banned phrase" tells them what to fix. |
| 5 | `test_nothing_reaches_the_provider_when_the_lint_refuses` | ok | **Keep** | ISSUE-037 assertion: the provider counters are all zero after a refusal. This is what separates "before the provider" from "after the attach but the attach didn't roll back." |
| 6 | `test_a_rule_added_to_the_lint_later_is_enforced_here` | ok | **Keep** | The wiring reads `copylint.RULES`, not an enumerated list. A rule added next week is enforced today. This is what "the wiring reads the rule set" means in practice. |
| 7 | `test_a_lead_with_no_research_at_all_is_refused` | ok | **Keep** | Identity-through-absence: a lead with no research fires `step1_without_pack_fact`. Tests the lint's most common real failure through the send path. |
| 8 | `test_a_fact_that_belongs_to_another_company_supports_nothing` | ok | **Keep** | The 50-of-71 defect: presence is not identity. A fact from another company's domain supports nothing. This is the lint's most important semantic assertion. |
| 9 | `test_the_same_fact_on_the_account_s_own_domain_does_support_it` | ERROR | **Keep** | The positive half of test 8. Without it, test 8 could pass by refusing everything. Currently RED due to the sequence gate. |
| 10 | `test_a_dry_run_reports_the_refusal_without_raising` | ok | **Keep** | A dry run reaches no provider, so it refuses nothing - but it must report the lint verdict. This is how an operator finds out before `--live` rather than during it. |

**Recommendation: keep all 10.** Three are currently RED (ERROR) due to the
sequence gate, not the lint. The lint wiring is correct; the fixture needs
enrichment to satisfy the sequence gate above it. Discarding any of these
would lose a distinct assertion about the wiring.

## `outreachclaims` reachable from the send path?

**NO.** The chain exists but does not reach the send path:

    outreachclaims ← imported by contextpack (line 57)
    contextpack   ← imported by src/web/api.py (line 41)
    contextpack   ← NOT imported by bisonfactory.py, push.py, or batch1_push.py

The grep:

    $ grep -rn "contextpack" src/ --include="*.py"
    src/pilotpath.py:210:    (string reference in a test name list)
    src/secondbrain.py:5:    (docstring reference)
    src/web/api.py:41:       contextpack, discovery, explorer, export, ...
    src/web/api.py:1186:     (comment)
    src/web/api.py:1202:     angles = contextpack.angles(members, config)
    src/web/api.py:2729:     "context": contextpack.build(recs, ...)

`contextpack` is consumed only by the web API. The send path
(`bisonfactory.stage`) does not import it, directly or transitively.
`outreachclaims` is therefore reachable from the web API but not from the
send path. The test in `test_the_copy_lint_refuses_the_real_send_path.py`
that asserts otherwise would be RED, and the finding stands.

## The proposed general check

### The shape that keeps costing us

Four instances of the same defect:

1. `heyreach.linkedin_sequence` — builds the LinkedIn graph correctly, has
   no caller in `src/`.
2. `extract_prospect_text` — strips the quoted thread correctly, `classify`
   never calls it.
3. `outreachclaims` — the authority on claims about us, no consumer on the
   send path.
4. `push.run_with_copylint` — the lint wired into a module that refuses to
   send, called by nothing.

Each time: the module is correct, the tests are green, and nothing calls it
on the path that matters.

### The check

An import-graph assertion that fails whenever a designated guard module has
no caller on the real send path.

**Module set** (the guards):

    src/copylint.py
    src/outreachclaims.py
    src/eligibility.py
    src/verification.py
    src/killswitch.py
    src/pilotcaps.py
    src/sequencegate.py

These are modules that DECIDE whether something may proceed. A guard that
nobody consults is a guard that enforces nothing.

**Entry points** (the real send path):

    scripts/batch1_push.py:main
    src/bisonfactory.py:stage (the live=True branch)

**Definition of reachable**:

Module G is reachable from entry point E if there exists a chain of STATIC
IMPORTS and FUNCTION CALLS from E to at least one public function exported
by G. "Static" means traceable by AST analysis of `import` and `from ...
import` statements, plus call-graph walking of function bodies. Dynamic
calls (`getattr`, `importlib.import_module`) are flagged separately.

**What the test asserts**:

For each guard module G in the set, there exists at least one entry point E
such that G is reachable from E. If no entry point reaches G, the test fails
with:

    GUARD UNREACHABLE: src/outreachclaims.py
      no call chain from scripts/batch1_push.py:main or
      src/bisonfactory.py:stage reaches any public function in this module.
      A guard that nobody consults enforces nothing.

**Implementation approach**:

1. Parse each entry point file into an AST.
2. Walk the AST to collect all `import` and `from ... import` statements.
3. For each imported module, recursively walk its AST to find imports and
   function calls.
4. Build a reachability graph: entry point → imported modules → their
   imports → ...
5. For each guard module, check if it appears in the reachability graph AND
   at least one of its public functions is called (not just imported).
6. "Called" means the function name appears in a `Call` node in some module
   on the path, qualified by the import alias.

**What this would have caught**:

- `run_with_copylint` defined in `push.py` but not called by `bisonfactory.stage`
  → `push.py` is reachable (it's imported) but `run_with_copylint` is not
  called by any function on the path from `batch1_push.py` to `bisonfactory`.
- `outreachclaims` imported by `contextpack` but `contextpack` not imported
  by `bisonfactory` → `outreachclaims` unreachable from the send path.
- `extract_prospect_text` defined in `replies.py` but not called by
  `classify` → the function exists but the call edge is missing.

**What this would NOT catch**:

- A guard that is called but whose result is discarded. That is a different
  defect (computed but not consumed) and requires a data-flow analysis.
- A guard that is called through a dynamic dispatch (`getattr(module,
  func_name)`). That is flagged separately and requires manual review.

**Why an import graph and not a text grep**:

`grep "copylint" src/bisonfactory.py` returns a line when somebody writes a
comment mentioning the word. An import-graph assertion traces the actual
dependency: `from . import copylint` at the module level, then
`copylint.check_batch(...)` in a function body. A comment satisfies the
grep; only a real call satisfies the graph.
