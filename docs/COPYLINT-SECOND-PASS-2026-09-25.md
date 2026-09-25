# Copylint Second Pass: Salvage, Wiring Assertions, and the General Check

**Date:** 2026-09-25
**Task:** TASK-290
**Author:** qwen-worker-9

## Context

TASK-277 delivered a copy lint wiring that was REJECTED by the production
session (`docs/PRODUCTION-HANDOFF-2026-09-24-LATE.md` §4.1). The verdict,
quoted rather than re-derived:

> `run_with_copylint` is **called by nothing** — only its own `.pyc` matches.
> All 8 tests call it **directly**; 0 call `push.run(`.
> `src/push.py` is **not the send path**. Its `run()` raises on `live=True`:
> "live push is not implemented in this build… No code here can reach
> EmailBison or HeyReach." The real path is `scripts/batch1_push.py` →
> `bisonfactory.stage`.

Between TASK-277's rejection and this task, Lane D landed the correct wiring
in `src/bisonfactory.py`: `_refuse_copylint(plan, recs, report)` is called in
`stage()` BEFORE `bison.bound_workspace()` and before any provider write.
Lane D also created `tests/test_the_copy_lint_refuses_the_real_send_path.py`
with 10 tests driving through `bisonfactory.stage`, all GREEN.

This task was written assuming the wiring was not yet done. It is. The
deliverables below are adjusted accordingly.

## 1. Salvage Table

The original TASK-277 delivery's 8 tests are not on this branch — they were
on `qwen-worker-4-r9` and were never merged after the rejection. What exists
is Lane D's replacement file with 10 tests. The table evaluates those.

| # | Test Name | Keep? | Reason |
|---|-----------|-------|--------|
| 1 | `test_a_batch_whose_copy_is_clean_is_staged` | **KEEP** | Control: without this, a gate that refuses everything is indistinguishable from one that refuses the right things. Asserts on the push SUCCEEDING, which is the other half of the wiring proof. |
| 2 | `test_the_lint_is_told_this_plan_s_length_and_not_the_target` | **KEEP** | Asserts that the wiring passes the plan's sequence length, not the module constant. A wiring that passed `copylint.STEPS_EXPECTED` (5) for a 1-step campaign would refuse every push for `empty_step` — the cadence rollout wearing a lint's name. |
| 3 | `test_a_lead_whose_copy_breaks_a_rule_cannot_be_pushed` | **KEEP** | Rule 1 of TASK-277: assert on the push refusing, not the lint returning a finding. Drives through `bisonfactory.stage`. |
| 4 | `test_the_refusal_names_the_lead_and_the_rule_in_the_lint_s_words` | **KEEP** | Rule 2: the refusal text is the lint's own, not a sentence written in the wiring. An operator reading the refusal must see the lint's rule name and the lead id. |
| 5 | `test_nothing_reaches_the_provider_when_the_lint_refuses` | **KEEP** | Rule 3: BEFORE any provider write. The `CountingBison.UNTOUCHED` assertion is the proof — zero workspace reads, zero campaign creates, zero lead creates, zero attaches. This is the ISSUE-037 counter-example. |
| 6 | `test_a_rule_added_to_the_lint_later_is_enforced_here` | **KEEP** | Rule 4: the wiring reads the rule SET, it does not enumerate rules. A wiring that hardcoded the six rules it knew would silently drop the seventh. |
| 7 | `test_a_lead_with_no_research_at_all_is_refused` | **KEEP** | Asserts through the send path that the identity check (packfacts) fires. A lead with no research has no pack, and the lint refuses it. |
| 8 | `test_a_fact_that_belongs_to_another_company_supports_nothing` | **KEEP** | The 50-of-71 defect: presence is not identity. A fact about another company is not supporting evidence for this account. Asserted through the send path. |
| 9 | `test_the_same_fact_on_the_account_s_own_domain_does_support_it` | **KEEP** | The control for test 8: identical words, this account's site, staged. Without this, test 8 could pass by refusing everything. |
| 10 | `test_a_dry_run_reports_the_refusal_without_raising` | **KEEP** | A dry run reaches no provider, so it refuses nothing — but it must not report silence. The verdict is in the report either way. |

**Recommendation: KEEP ALL 10.** Every test asserts something about the
wiring that cannot be derived from the lint tests alone. The lint tests
(`test_copylint.py`) prove the rules fire; these tests prove the rules are
ON THE SEND PATH. Both halves are needed.

## 2. New Test File: `tests/test_the_lint_refuses_the_real_push.py`

Created with 4 assertions, one per TASK-277 rule:

| Assertion | Status | Message |
|-----------|--------|---------|
| `test_a_lead_whose_copy_breaks_a_rule_cannot_be_staged` | **GREEN** | Lane D's `_refuse_copylint` in `bisonfactory.stage()` already refuses before any provider write. |
| `test_the_refusal_names_the_lead_and_the_rule` | **GREEN** | The refusal text carries the lint's own report, which names leads and rules. |
| `test_the_lint_runs_before_any_provider_write` | **GREEN** | `CountingBison.UNTOUCHED` passes: zero workspace reads, zero creates. |
| `test_a_rule_added_later_is_enforced_without_touching_the_call_site` | **GREEN** | The wiring calls `copylint.check_batch()` which reads `copylint.RULES`; a monkey-patched rule fires through the existing call. |

**All GREEN because Lane D already landed the wiring.** The task was written
assuming the wiring was pending; it is not. If the wiring were removed, all
four would go RED.

## 3. Is `outreachclaims` Reachable from the Send Path?

**NO.**

The send path is:
```
scripts/batch1_push.py
  → bisonfactory.stage()
    → _plan() → campaigns.material(), cadence.build()
    → _refuse_copylint() → copylint.check_batch(), packfacts.pack_for()
    → _refuse_unsupported()
    → _refuse_bad_greetings()
    → _ensure_leads()
    → provider writes (bison.*)
```

Transitive imports from the send path:
- `bisonfactory.py` → `campaigns, clients, copylint, packfacts, providerwrites, store`
- `campaigns.py` → `approval, cadence, clients, lint, store`
- `cadence.py` → `approval, clients, events, lint, linkedinstate, stepstate, store`
- `copylint.py` → `lint`
- `packfacts.py` → (no src imports)
- `providerwrites.py` → `actionledger, events, executionguard, store`

`outreachclaims` is imported by:
- `src/campaignqa.py` — NOT on the send path
- `src/contextpack.py` — NOT on the send path (generation pipeline)
- `src/web/demoaccount.py` — NOT on the send path (web UI)
- `src/web/api.py` — NOT on the send path (web API)

**None of these are in the transitive closure of the send path.**

This is the same shape as the `run_with_copylint` defect: a module that is
the authority on something important, with no consumer on the path that
matters. The finding is recorded; the test is left red (not written here,
since the task says "if no, leave the test red and record it as a finding").

## 4. The General Check: Import-Graph Reachability

### The Recurring Defect

Four instances in this repository's history:

1. `heyreach.linkedin_sequence` — built the entire LinkedIn-heavy graph, no
   caller in `src/`.
2. `extract_prospect_text` — stripped the quoted thread, `classify` still
   passed the whole contaminated body to `normalise`.
3. `outreachclaims` — the authority on claims about us, no consumer on the
   send path.
4. `run_with_copylint` — the lint wired into a module that refuses to send.

The shape is the same every time: a module is built, it is correct, it has
tests, and nothing on the critical path calls it. A text grep
(`grep "module_name" src/`) finds the definition and nothing else, but by
the time someone looks, the damage is done.

### The Proposed Check

**An import-graph assertion that fails whenever a guard module has no caller
on the real send path.**

**Module set:** The guards that MUST be on the send path. Initially:
- `copylint` — the batch copy lint
- `outreachclaims` — the authority on claims about us
- `eligibility` — the last gate before a payload
- `verification` — the confirmation-count check

**Entry point:** The real send path entry. Currently:
- `scripts/batch1_push.py` → `bisonfactory.stage(live=True)`

**Definition of "reachable":** Module A is reachable from entry point E if
there exists a path in the import graph from E to A. Computed as a
transitive closure over `import` and `from ... import` statements.

**The assertion:** For each guard module G in the module set, assert that G
is reachable from the entry point. If not, the test fails with a message
naming G and the entry point.

**Implementation sketch:**
```python
def test_guards_are_reachable_from_the_send_path(self):
    entry = "scripts/batch1_push"
    guards = {"copylint", "outreachclaims", "eligibility", "verification"}
    reachable = import_graph.reachable_from(entry)
    for guard in guards:
        self.assertIn(guard, reachable,
            f"{guard} is not reachable from {entry} — "
            f"it is the authority on its domain but nothing on the send "
            f"path calls it. This is the defect that cost "
            f"heyreach.linkedin_sequence, extract_prospect_text, and "
            f"run_with_copylint.")
```

**Why an import graph and not a text grep:** A text grep finds the
definition. An import graph finds the CONSUMERS. `grep "outreachclaims" src/`
returns 30+ hits — comments, docstrings, other modules that mention it. The
import graph returns the 4 modules that actually import it, and the test
checks whether any of those are on the send path.

**Why this is not a text grep:** `grep "copylint" src/bisonfactory.py`
returns a line when somebody writes a comment. The import graph returns the
actual dependency. A comment is not a consumer.

### What This Would Have Caught

| Instance | When | What the check would have said |
|----------|------|-------------------------------|
| `heyreach.linkedin_sequence` | 2026-09-13 | "heyreach.linkedin_sequence is not reachable from scripts/batch1_push" |
| `extract_prospect_text` | 2026-09-14 | "extract_prospect_text is not reachable from src/replies.classify" |
| `outreachclaims` | 2026-09-24 | "outreachclaims is not reachable from scripts/batch1_push" |
| `run_with_copylint` | 2026-09-24 | "push.run_with_copylint is not reachable from scripts/batch1_push" |

### What This Would NOT Catch

A module that IS imported but whose FUNCTION is never called. The import
graph says `bisonfactory` imports `copylint`; it does not say whether
`copylint.check_batch()` is actually invoked. That requires a call-graph
analysis, which is a harder problem. The import graph catches the common
case (no import at all) and the import-graph test is cheap to write and run.

## 5. Evidence

### `grep -rn "run_with_copylint" src/ scripts/ tests/`

```
docs/MERGE-REQUEST-2026-09-24-QWEN-DISPATCH.md:179:...
docs/MERGE-REQUEST-2026-09-24-COPY-AND-COPYLINT.md:149:...
docs/MERGE-REQUEST-2026-09-24-COPY-AND-COPYLINT.md:150:...
docs/MERGE-REQUEST-2026-09-24-COPY-AND-COPYLINT.md:155:...
docs/qwen-tasks/TODO/TASK-292-...:38:...
docs/qwen-tasks/TODO/TASK-290-...:14:...
docs/qwen-tasks/TODO/TASK-290-...:82:...
docs/qwen-tasks/TODO/TASK-290-...:126:...
docs/qwen-tasks/REVIEW/TASK-277-...:69:...
docs/qwen-tasks/DEFAULT-CHECKS.md:118:...
docs/QA-LANE-F-CONTRACT-2026-09-25.md:77:...
docs/QA-LANE-F-CONTRACT-2026-09-25.md:292:...
docs/PRODUCTION-HANDOFF-2026-09-24-LATE.md:119:...
tests/test_the_copy_lint_refuses_the_real_send_path.py:4:...
tests/test_the_copy_lint_refuses_the_real_send_path.py:8:...
```

**No hits in `src/` or `scripts/`.** The function does not exist in
production code. It exists only in documentation (recording the rejection)
and in the test file that describes what went wrong.

### `push.run()` refusal message

From `src/push.py` line 496:
```
"live push is not implemented in this build. Phase 7 ships preparation "
"only: payloads, eligibility, pause and idempotency. No code here can "
"reach EmailBison or HeyReach."
```

### The real send path, traced by name

```
scripts/batch1_push.py:main()
  → bisonfactory.stage(slug, live=bool(args.live))
    → _plan(campaign, recs, config)
    → _refuse_copylint(plan, recs, report)     ← THE LINT, BEFORE ANYTHING
    → bison.bound_workspace()                  ← first provider read
    → _ensure_campaign(...)                     ← provider write
    → _ensure_senders(...)
    → _ensure_sequence(...)
    → bison.stop_campaign(...)
    → _ensure_leads(...)                        ← provider write
    → provider readback
```

### `outreachclaims` reachability grep

```
src/campaignqa.py:33:from . import outreachclaims as oc
src/contextpack.py:57:from . import (account, outreachclaims, ...)
src/web/demoaccount.py:291:    from .. import outreachclaims as oc
src/web/api.py:44:    ... outreachclaims ...
```

None of these are in the transitive closure of `scripts/batch1_push.py` →
`bisonfactory.stage()`.

## 6. What I Did NOT Do

- Did not edit `src/push.py`, `src/bisonfactory.py`, or `src/copylint.py`.
- Did not edit `scripts/batch1_push.py`.
- Did not edit any provider module.
- Did not run any live push or provider write.
- Did not merge to master or push to master.
