PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-401 — GLM first-pass verification: TASK-364 (SequencePlan consumed by both provider factories)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with GLM first-pass verdicts. Claude cherry-picks only what GLM confirms
passes. Do this one first, alongside TASK-402 (391).**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself, follow it exactly (isolated
worktree, read-only, falsification over confirmation, eight dispositions).

## Target

TASK-364, "one canonical SequencePlan" — in REVIEW on `qwen-worker-worker-r9`
(the primary worktree branch). Read its own acceptance criteria from
`docs/qwen-tasks/DONE/` or the REVIEW copy first.

## What GLM's pass must produce

1. Reproduce whatever the task claims: does `bisonfactory.py` and
   `heyreachfactory.py` now build their provider payloads FROM a SequencePlan
   object (`sequenceplan.derive_*`), or do they still build their own
   payload independently and the plan is decorative? This is the exact
   "existence is not function" question - prove consumption, not presence.
2. If a prior WIP existed on this branch (commit `59f8647f`,
   `derive_xlsx_data`/`qa_validate`), confirm whether the final result
   actually uses those functions or superseded them.
3. Run whatever tests the task claims; reproduce at least one with a
   deliberately broken plan field to confirm the factory's output changes.
4. Any new finding, file:line.

## RESULT

**STATUS: BLOCKED — TASK-364 is NOT_DONE, 4 of 6 acceptance criteria fail**

**Artifact kind:** finding (read-only verification, no code changes)

**COMMIT SHA:** N/A (verification only, no code written)

**START_MASTER_SHA:** `12143b0c` (qwen-worker-r9 HEAD, 2026-09-27)

**TESTS:** Mutation test run. `derive_bison_payload` correctly detects plan mutations (body "Original body" → "MUTATED BODY", `Changed: True`). Import-graph test run: `bisonfactory.py` source contains zero occurrences of "sequenceplan" or "derive_bison_payload"; `heyreachfactory.py` source contains zero occurrences of "sequenceplan" or "derive_heyreach_payload". Existing 11 tests in `test_the_entrypoint_is_the_only_generation_path.py` pass but do NOT exercise the production factories.

## FINDINGS

### 1. The derive functions exist and work correctly in isolation

`src/sequenceplan.py` on master has five functions:
- `new()` — builds the plan skeleton
- `approval_hash()` — deterministic SHA-256 over stable JSON serialization
- `derive_preview_data()` — preview projection
- `derive_bison_payload()` — EmailBison projection
- `derive_heyreach_payload()` — HeyReach projection

Mutation test confirms `derive_bison_payload` reads from the plan:

    Before: Original body
    After:  MUTATED BODY
    Changed: True

### 2. Neither factory imports or calls any sequenceplan function

    grep "sequenceplan" src/bisonfactory.py    → 0 hits (master AND commit 3213472f)
    grep "sequenceplan" src/heyreachfactory.py → 0 hits (master AND commit 3213472f)

`bisonfactory._plan()` (line 428) builds its own email plan from `campaigns.material()`, `cadence.steps_for()`, `_sequence_steps()`, and `_approved_copy()` — completely independent of `sequenceplan`.

`heyreachfactory.build_sequence()` (line 587) builds its own LinkedIn graph via `heyreach.linkedin_sequence()` or `_build_sequence_no_inmail()` — completely independent of `sequenceplan`.

### 3. `derive_xlsx_data()` and `qa_validate()` do not exist on master

They existed on the TASK-364 branch at commit `3213472f` (286-line expansion of sequenceplan.py) but were never merged to master. Master's `sequenceplan.py` has only the original five functions. Two of six consumers are missing.

### 4. The prior WIP (commit 59f8647f) is superseded

Commit `59f8647f` added the first 90 lines of `sequenceplan.py` as a WIP checkpoint. Commit `3213472f` superseded it with the full 286-line version including `derive_xlsx_data` and `qa_validate`. Neither version was consumed by the factories.

### 5. TASK-364's own tests acknowledge the failure while passing

At commit `3213472f`, `test_every_representation_derives_from_one_plan.py` contains:

    test_bisonfactory_plan_function_still_exists:
        "bisonfactory._plan still builds from campaign state. It is the
        OLD pipeline... Report the parallel builder."
        → assertTrue(hasattr(bisonfactory, "_plan"))  # PASSES

    test_heyreachfactory_still_builds_independently:
        "heyreachfactory still builds its own LinkedIn graph. Report it."
        → assertTrue(hasattr(heyreachfactory, "assemble_linkedin_copy"))  # PASSES

These tests ASSERT that the parallel builders still exist and PASS. The acceptance criterion says the parallel builders must derive from the plan or be gone. A test that passes while the criterion fails is the TASK-029 pattern: correct code, absent wiring, green tests.

### 6. `generate_campaign.py` is a parallel entrypoint, not a factory rewiring

`generate_campaign.py` imports `sequenceplan`, calls `sequenceplan.new()`, and returns the plan. But it does NOT call any `derive_*` function. The factories that production actually uses (`bisonfactory`, `heyreachfactory`) are untouched.

### Summary against TASK-364 acceptance criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | One object, six consumers | **FAIL** | Only 4 of 6 derive functions exist on master; `derive_xlsx_data` and `qa_validate` missing |
| 2 | Change plan, all six change | **PARTIAL** | 4 change; 2 do not exist to change |
| 3 | No consumer carries its own cadence | **FAIL** | `bisonfactory._plan` (line 428) and `heyreachfactory.build_sequence` (line 587) carry their own |
| 4 | Hash deterministic and sensitive | **PASS** | `approval_hash()` uses stable JSON serialization; mutation test confirms sensitivity |
| 5 | No fifth representation | **FAIL** | Two parallel builders remain fully independent; zero imports of sequenceplan in either factory |
| 6 | Full suite diff | **NOT RUN** | Verification is structural; existing tests do not exercise production factories |

## Dispositions (eight-fold)

1. **derive_bison_payload / derive_heyreach_payload exist but have no production consumer** — EXISTING TASK (TASK-364 must wire them into the factories or remove the factories)
2. **derive_xlsx_data / qa_validate missing from master** — EXISTING TASK (TASK-364 must implement them)
3. **bisonfactory._plan builds independently** — EXISTING TASK (TASK-364 acceptance #5 explicitly names this)
4. **heyreachfactory.build_sequence builds independently** — EXISTING TASK (TASK-364 acceptance #5 explicitly names this)
5. **generate_campaign.py is a parallel entrypoint** — ACCEPTED DEFERRED RISK (TASK-369 integration; not this task's scope)
6. **approval_hash is correct** — FIXED + VERIFIED (passes mutation test)
7. **Tests pass while acceptance fails** — FALSE POSITIVE (the tests acknowledge the failure in docstrings but assert the opposite of what acceptance requires)
8. **Prior WIP commit 59f8647f** — SUPERSEDED (commit 3213472f replaced it)

## Verdict

**BLOCKED — NOT SAFE TO MERGE.**

TASK-364 built the canonical SequencePlan object and four derive functions that work correctly in isolation. But the production factories (`bisonfactory`, `heyreachfactory`) do not import or call any of them. They still build their own parallel representations. Two of six consumers (`derive_xlsx_data`, `qa_validate`) do not exist on master. The tests pass by asserting the parallel builders exist rather than asserting they were removed.

This is the TASK-029 pattern: correct code, absent wiring, green tests. The derive functions are dead code in production — nothing calls them except tests against the new entrypoint.

## RISKS

- Merging TASK-364 as-is would add a canonical object that nothing consumes, creating the illusion of progress while the parallel builders remain authoritative.
- The `generate_campaign.py` entrypoint coexists with the production factories. If production still runs through `bisonfactory`/`heyreachfactory`, the canonical plan is bypassed entirely.

## RECOMMENDED CLAUDE ACTION

TASK-364 is NOT done. The remaining work:
1. Implement `derive_xlsx_data()` and `qa_validate()` in `src/sequenceplan.py`.
2. Wire `bisonfactory._plan()` to consume `sequenceplan.derive_bison_payload()` or remove it.
3. Wire `heyreachfactory.build_sequence()` to consume `sequenceplan.derive_heyreach_payload()` or remove it.
4. Write tests that drive through the PRODUCTION factories and assert the derive functions are what the factories call.
5. Break the wiring and confirm the tests fail (TASK-029 negative control).
