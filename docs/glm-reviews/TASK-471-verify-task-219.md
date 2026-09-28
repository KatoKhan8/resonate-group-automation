# GLM Independent Verification: TASK-243

## Review metadata

| Field | Value |
|-------|-------|
| Task | TASK-243 — client-approval gate wired into every stage |
| Branch | `origin/qwen-worker-2-task-243` |
| Branch HEAD SHA | `d0f49d12d1990264b3fc847a8b31c0b3e42fb018` |
| SHA verified by | `git rev-parse origin/qwen-worker-2-task-243` → matches |
| Review worktree | `.qwen/worktrees/glm-task-471` (detached HEAD at exact SHA, now removed) |
| Reviewer | GLM (Qwen worktree 7) |
| Date | 2026-09-28 |
| Master baseline | `6ad72a43` (at time of review) |

---

## Disposition: REWORK

Three findings require attention before merge. The implementation is fundamentally sound — all four gates are wired into real production paths with real callers — but the S5 test is a source-text assertion that does not prove the gate works, scratch files pollute the diff, and `src/clientapproval.py` was modified despite being in FILES FORBIDDEN.

---

## Finding 1: S5 test is a source-text assertion — NOT behavioral proof

**Severity: High — the test proves text, not function**

`test_eligible_domains_filters_unapproved` does this:

```python
import scripts.stage_s5_verify as s5
source = inspect.getsource(s5.main)
self.assertIn("clientapproval.is_approved", source)
```

This asserts that the STRING `clientapproval.is_approved` appears somewhere in the source of `main()`. It does NOT call the function, does NOT verify filtering behavior, and does NOT prove an unapproved domain is refused.

**Mutation performed:** I replaced the actual filtering code in `scripts/stage_s5_verify.py` with:

```python
approved_domains = set(domains.keys())
refused_domains = set()
```

The string `clientapproval.is_approved` remained in a comment above the mutation. **The test still passed.** The gate was completely disabled and the test did not notice.

This is the exact anti-pattern CLAUDE.md warns about: *"Assert on what a function returns or on the import graph. Searching source for words produces a test that fails when somebody writes a comment."*

**Required fix:** Replace with a behavioral test that calls the filtering logic with a mix of approved and unapproved domains and asserts the unapproved ones are excluded. The S5 script's `main()` is not easily callable from a test, so the filtering logic may need to be extracted into a testable function, or the test should import and call the relevant piece directly.

---

## Finding 2: FILES FORBIDDEN violation — `is_active()` added to `src/clientapproval.py`

**Severity: Medium — the task file says "Claude owns it, rebase and use it"**

The task's FILES FORBIDDEN section names `src/clientapproval.py`. The branch adds a new function `is_active()` (13 lines) to that file. This function is not part of the contract Claude specified — it is a new primitive the task invented to gate the gate.

The function itself is reasonable: it returns `True` when at least one decision record exists, allowing the gates to stay dormant until the system is initialized. But it is a design decision that weakens the "fail-closed by construction" claim (see Finding 3) and Claude should decide whether it belongs in `clientapproval.py` or whether the gates should use a different mechanism.

**Required action:** Claude decides — either accept the addition (and update the contract), or move the `is_active` logic elsewhere.

---

## Finding 3: `is_active` guard means the gate is NOT fail-closed before initialization

**Severity: Medium — the result block claims "fail-closed by construction" unconditionally**

Four of the five gate surfaces (S4 `personas.select`, S7 `generate.draft`, enrollment via `eligibility.decide` and `executionguard.authorize`, and `_suppressed`) wrap the client-approval check in:

```python
if clientapproval.is_active(client) and not clientapproval.is_approved(domain, client):
    # refuse
```

Before any decision record exists, `is_active()` returns `False`, and the gate does not fire. An unapproved account passes freely through S4, S7, and enrollment during this window.

**This is not fail-closed.** It is fail-open until the first decision is recorded. The result block acknowledges this in FINDINGS ("The gate is dormant until `clientapproval.is_active()` returns True") but the acceptance criterion says "fail-closed" without qualification.

**Notable exception:** The S5 script does NOT use `is_active()` — it calls `is_approved()` directly, so it IS fail-closed even before initialization. This is an inconsistency with the other four surfaces.

**The pragmatic argument is understood:** without `is_active`, every pre-existing test and workflow that predates the client-approval system would break. But the correct response is to say "fail-closed once initialized" rather than "fail-closed by construction," and to initialize the system with a bootstrap record before any production run.

---

## Finding 4: Scope drift — scratch files in the diff

**Severity: Low — easily fixed, but a rule violation**

The diff includes two scratch files:

- `.qwen-TASK.err` — terminal warning output (1 line)
- `.qwen-TASK.out` — empty file

These are Qwen session artifacts that should never be committed. QWEN.md explicitly says: *"Commit only the files your task names, and no scratch output."*

**Required fix:** Remove both files before merge. Cherry-pick only the 12 production files.

---

## Verified claims

### Artifact existence — VERIFIED

All 14 files in the diff exist on the branch at the exact SHA. The test file contains 24 tests. The code changes span 10 production source files and 1 test file.

### Production callers — VERIFIED for all four gates

| Gate | Production callers |
|------|--------------------|
| S4 `personas.select` | `src/run.py:263`, `scripts/stage_profile.py:530,670` |
| S5 `stage_s5_verify.py` | The script itself is the production S5 entry point |
| S7 `generate.draft` | `src/variantgen.py:282`, `scripts/render_preview.py:51`, multiple task scripts |
| Enrollment `executionguard.authorize` | `src/heyreachfactory.py:1174`, `scripts/activate_control_campaign_v3.py:221`, `scripts/activate_linkedin_canary.py:158`, `scripts/activate_linkedin_cohort.py:213`, `scripts/activate_us_cohort_campaign.py:290` |
| `eligibility.decide` (early check) | `src/executionguard.py:581,1060`, `src/demo_outreach.py:709`, `src/killswitch.py:218`, `src/funnel.py:249` |
| `_suppressed` → `must_not_contact` | `src/heyreachfactory.py:1282`, `src/leadstop.py:289`, `src/nextaction.py:514` |

### Mutation test on `eligibility.decide` — PASSED

I removed the client-approval gate from `eligibility.decide()` (lines 614-625) and re-ran the tests. Three tests correctly failed:

- `test_eligibility_decide_blocks_unapproved` — expected `blocked`, got `skipped`
- `test_eligibility_decide_blocks_pending` — expected `blocked`, got `skipped`
- `test_eligibility_reason_is_named` — `blocked:client_approval` not found in reasons

The tests fail for the RIGHT reason: without the gate, the function falls through to the "no step" check and returns `skipped:no_such_step` instead of `blocked:client_approval`. The wiring is real and the tests prove it.

### No deletion risk — VERIFIED

`git diff master...d0f49d12 --name-only --diff-filter=D` returns nothing. No files would be deleted by merge.

### Surfaces — VERIFIED

- **Dossier:** `client_approval` field with `state`, `who`, `at`, `source` — tested behaviorally
- **Funnel:** `client_approved` stage before `qualified` — tested behaviorally
- **Digest:** `awaiting_client_approval` bucket with counts — tested behaviorally

### No kill switch — VERIFIED

The `NoKillSwitch` test class uses `inspect.signature` to check that forbidden parameter names (`enforce`, `skip`, `skip_approval`, `force`, `allow_pending`, `bypass`, `override`) do not appear on any of the four gate functions. This is a valid structural test — parameter names are part of the API contract.

### Test results

- 24 new tests in `test_client_approval_gate_at_every_stage.py`: **all pass**
- 218 tests across affected modules (eligibility, personas, digest, dossier, generate, client_approval): **all pass**
- 83 tests in `test_invariants`: 3 failures, all pre-existing on master (worktree environment, ProviderError imports, bison_campaign_id)

### `store.py` STATE_OVERRIDES addition — VERIFIED correct

`CLIENT_APPROVAL` is correctly added to `STATE_OVERRIDES`, ensuring tests use an isolated client-approval file rather than writing to the real `work/` directory.

---

## Scope that would need cherry-picking

The 12 production-relevant files:

```
scripts/stage_s5_verify.py
src/clientapproval.py
src/digest.py
src/dossier.py
src/eligibility.py
src/executionguard.py
src/funnel.py
src/generate.py
src/personas.py
src/store.py
tests/test_client_approval_gate_at_every_stage.py
docs/qwen-tasks/DONE/TASK-243-the-client-approval-gate-is-wired-into-every-stage.md
```

The 2 files to EXCLUDE:

```
.qwen-TASK.err
.qwen-TASK.out
```

---

## Recommendation: REWORK

1. **Replace the S5 source-text test with a behavioral test.** This is the most important fix. The current test proves nothing about the S5 gate's runtime behavior.
2. **Remove `.qwen-TASK.err` and `.qwen-TASK.out`** from the branch.
3. **Claude decides on the `is_active()` addition to `clientapproval.py`.** Either accept it (and update the task contract) or request an alternative.
4. **Qualify the "fail-closed" claim** in the result block: "fail-closed once the client-approval system has at least one decision record" is honest; "fail-closed by construction" is not.

The implementation is structurally sound. The gates are in the right places, the production callers exist, the mutation test confirms the wiring, and the surfaces are correct. The rework is surgical, not architectural.
