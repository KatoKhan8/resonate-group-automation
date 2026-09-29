# GLM Independent Verification: TASK-296

**Verifier:** TASK-452 (GLM review layer)
**Target task:** TASK-296 — eleven campaigns legitimately hold three steps
**Branch:** qwen-worker-11-task314
**Branch HEAD SHA reviewed:** ddc0bc816fed25b327cbe070d0597ba03ae2b67e
**SHA verified with `git rev-parse`:** confirmed — FETCH_HEAD and the named SHA both resolve to ddc0bc81.
**Isolated worktree:** `.qwen/worktrees/glm-452` (detached HEAD at ddc0bc81)
**Date:** 2026-09-29

---

## 1. Do the artifacts exist on this ref?

**YES.** All three allowed files exist at the branch head:

| File | Lines | Verified via |
|------|-------|-------------|
| `scripts/qa/check_campaign_bison.py` | 703 | `git ls-tree` + read in worktree |
| `tests/test_step_counts_agree_while_the_keys_do_not.py` | 820 | `git ls-tree` + read in worktree |
| `docs/QA-CAMPAIGN-BISON-2026-09-25.md` | 100 | `git ls-tree` + read in worktree |

Additionally, `scripts/qa/__init__.py` (1 line, docstring only) was added as a package marker.

The TASK-296 task file was moved from `TODO/` to `REVIEW/` with a filled result block.

---

## 2. Does the code do what the result block claims?

### 2.1 The eight rules — each verified by reading the implementation

| Rule | Implementation | Key property | Verified |
|------|---------------|--------------|----------|
| `campaign_exists` | `bison.campaign(id)` at line 133 | By ID, not by name (ISSUE-036) | ✓ |
| `step_count_matches` | `rule_step_count_matches` line 146 | Set equality `provider_orders == expected`, not count. `diff_step_keys` returns both-direction diffs | ✓ |
| `templates_use_only_carried_variables` | line 176 | Extracts `{VAR}` via regex, lowercases, diffs both directions against `bison.variables_of()` on up to 50 leads | ✓ |
| `sender_attached_and_connected` | line 217 | Exact match: `status.lower().strip() == "connected"`. Calls `bison.bound_workspace()` before trusting sender list | ✓ |
| `schedule_and_limits_set` | line 266 | Checks `days`, `start_time`, `end_time`, `timezone`, `max_emails_per_day` — all must be present and non-empty | ✓ |
| `no_settled_blank_rows` | line 290 | Zero rows → VACUOUS (not PASS). Uses `emptyrender.scan()`. Settled = status in sent/stopped/bounced | ✓ |
| `not_paused` | line 324 | Checks provider `status` against per-row `pause` intent. Reports which intent was used | ✓ |
| `id_matches_our_registry` | line 351 | Direct int comparison of provider ID vs `bison_campaign_id` | ✓ |

### 2.2 Tests pass

```
Ran 58 tests in 0.068s
OK
```

Run in the isolated worktree at ddc0bc81 via `python -m unittest tests.test_step_counts_agree_while_the_keys_do_not -v`.

### 2.3 The central claim: set diff catches what count comparison misses

**MUTATION TEST PERFORMED.** Replaced `diff_step_keys` with a count-based comparison:

```python
def mutant_diff(a, b):
    sa, sb = set(a), set(b)
    if len(sa) == len(sb):
        return [], []  # count matches -> pass (WRONG)
    return sorted(sa - sb), sorted(sb - sa)
```

Result:
- `{1,2,4}` vs `{1,2,3}`: mutant returns `([], [])` — wrongly passes.
- Original returns `([4], [3])` — correctly catches the defect.
- Under the mutation, `test_count_matches_but_keys_differ` FAILS with `AssertionError: 3 not found in []` — the intended test fails for the intended reason.
- `test_count_match_keys_mismatch_message_names_both_sides` FAILS with `AssertionError: 'only_provider' not found in detail` — also the intended reason.
- The three tests for cases where counts and keys agree (eleven three-step, four-step, matching keys) still pass under mutation — confirming the mutation is specific, not blanket-breaking.

**The tests are falsifiable.** They assert on set-diff output, not on counts or source text.

---

## 3. Existence is not function — does anything consume this?

**`check_campaign_bison` has zero production callers in `src/`.**

Grep results for `check_campaign_bison` across the entire branch:
- `scripts/qa/check_campaign_bison.py` — the definition (self-reference)
- `tests/test_step_counts_agree_while_the_keys_do_not.py` — the test suite
- `docs/QA-CAMPAIGN-BISON-2026-09-25.md` — documentation
- `docs/qwen-tasks/REVIEW/TASK-296-...` — the task file

No `src/` module imports it. No harness registry references it. `scripts/qa/__init__.py` is a single-line docstring with no CHECKS registry.

**However**, this is by design for this task. The task spec says to build a standalone QA script with a CLI entry point. The result block acknowledges: "Register the check in `scripts/qa/__init__.py::CHECKS` when the harness (TASK-292) lands." The check is consumed by:
1. Its CLI (`python -m scripts.qa.check_campaign_bison --workspaces ... --campaign ...`)
2. Its test suite (58 tests)
3. Its importable `run()` function for future harness integration

**Verdict on consumption:** NOT DISCONNECTED. A QA check script's consumer is the operator who runs it and the harness that will orchestrate it. The task explicitly scoped the harness integration to TASK-292. The `run()` function is real and tested through its actual entry point (the test suite calls `run()`, not individual rules, for the integration tests).

---

## 4. Are the tests falsifiable?

**YES, with one gap.**

| Test class | Falsifiable? | How it could pass while wrong |
|-----------|-------------|-------------------------------|
| `TestDiffStepKeys` | ✓ | Mutation test above confirms — asserts on set-diff output values |
| `TestStepCountMatchesWhileKeysDoNot` | ✓ | Drives through `rule_step_count_matches` with FakeBison transport, asserts on `only_in_provider`/`only_in_stored` |
| `TestExtractTemplateVariables` | ✓ | Pure function, asserts on returned sets |
| `TestTemplateVariables` | ✓ | Drives through `rule_templates_use_only_carried_variables`, asserts on both-direction diffs |
| `TestSenderStatus` | Partially | Uses mock sender objects passed directly to the rule function, NOT through FakeBison. The result block acknowledges: "FakeBison's sender-emails route returns `{"id": s}` without a status field." |
| `TestNoSettledBlankRows` | ✓ | Drives through the rule with constructed row data, asserts on vacuous/settled/pending classification |
| `TestNotPaused` | ✓ | Pure dict-in, dict-out through the rule function |
| `TestCampaignExists` | ✓ | Through FakeBison transport |
| `TestScheduleAndLimits` | ✓ | Through FakeBison transport |
| `TestIdMatches` | ✓ | Pure dict comparison |
| `TestFullRun` | ✓ | End-to-end through `run()`, asserts on verdict, failed_rules, arithmetic closure |
| `TestConstructedFailures` | ✓ | One per rule, asserts on specific message content |

**The gap:** The sender status rule cannot be integration-tested end-to-end through FakeBison because the fake does not serve a `status` field on sender objects. The tests work around this by passing mock sender objects directly. This means a bug in `campaign_senders_with_status()` (the function that pages the real sender-emails route and keeps full objects) would not be caught by the test suite. The result block discloses this honestly.

**Not accepted as proof (per protocol):**
- No `hasattr` assertions ✓ (none found)
- No assertions on source text ✓ (none found)
- No token-in-file checks ✓ (none found)
- The FakeBison transport IS a real transport-layer fake (not a fixture cassette), and `set_transport(self.fb)` swaps the actual provider module's transport

---

## 5. Would merging DELETE anything?

**No production code deletion.** The only files deleted by this branch relative to master are task files moving between directories:

```
docs/qwen-tasks/TODO/TASK-314-where-the-heyreach-steps-are-lost.md  (moved to REVIEW/)
docs/qwen-tasks/TODO/TASK-398-suppression-list-audit.md             (moved to REVIEW/)
docs/qwen-tasks/TODO/TASK-413-heyreach-seat-cap-check.md            (moved to REVIEW/)
```

These are task lifecycle moves, not content deletions. No source, config, or state file is deleted.

---

## 6. Scope drift

**SIGNIFICANT.** This is a multi-task branch. TASK-296's own changes are clean, but the branch carries at least five other tasks' work:

### Files outside TASK-296's allowed list:

| File | Belongs to | Nature |
|------|-----------|--------|
| `src/bisonfactory.py` (+50/-13) | TASK-364 | **FORBIDDEN for TASK-296**. Adds `sequenceplan` import, builds `SequencePlan` in `_plan()`, adds `sequence_plan`/`qa`/`derived_payload` to return dict |
| `src/heyreachfactory.py` (+40/-1) | TASK-364 | Same pattern: `sequenceplan` import, `SequencePlan` construction, `derive_heyreach_payload` |
| `src/sequenceplan.py` (+94) | TASK-364 | New `derive_xlsx_data()` function |
| `tests/test_every_representation_derives_from_one_plan.py` (+588) | TASK-364 | 26 tests for sequence plan derivation |
| `tests/test_no_cadence_step_is_silently_dropped.py` (+254) | TASK-314 | Regression test for dropped cadence steps |
| `scripts/stage_work_to_host.sh` (+102) | Infrastructure | Nightly work/ staging script |
| `scripts/task413_seat_cap_check.py` (+190) | TASK-413 | HeyReach seat cap check |
| `scripts/task413_seat_cap_probe.py` (+76) | TASK-413 | Seat cap probe |
| `docs/state/TASK-413-SEAT-CAP-CHECK.json` (+708) | TASK-413 | Seat cap check results |
| `docs/state/SENDER-CAPACITY.json` (modified) | TASK-413 | Updated sender capacity data |
| Multiple TASK-314/364/398/410/413 task files | Various | Task lifecycle moves |

### Cherry-pick assessment

TASK-296's own files could be cherry-picked cleanly:
- `scripts/qa/__init__.py`
- `scripts/qa/check_campaign_bison.py`
- `tests/test_step_counts_agree_while_the_keys_do_not.py`
- `docs/QA-CAMPAIGN-BISON-2026-09-25.md`
- `docs/qwen-tasks/REVIEW/TASK-296-eleven-campaigns-legitimately-hold-three-steps.md` (moved from TODO/)

These five files have no dependency on the TASK-364/314/413 changes. The check imports `src.providers.bison` and `src.emptyrender`, both of which are unchanged on this branch relative to master.

**Merging the whole branch to save time would import TASK-364's factory wiring, TASK-314's regression test, TASK-413's seat cap scripts, and infrastructure changes alongside TASK-296's QA check. That is pollution.**

---

## 7. Additional findings

### 7.1 No live run has been performed

The check has never been run against the live EmailBison estate. The result block says so explicitly: "Cannot run against live provider (READS ONLY, credentials in config/.env, not available for live provider reads from this worktree)."

This is not a defect in the artifact — the task boundaries say "READS ONLY at EmailBison" and the check is designed to run from Claude's worktree against a named `work/` copy. But it means the first live run is still owed, and the result block's "PER-CAMPAIGN TABLE: N/A" is honest about this.

### 7.2 `subjects == 0` exits 2

Confirmed in the code (line 694): `sys.exit(2)` for UNCONFIRMED/VACUOUS verdicts. The VACUOUS path is triggered when `target_ids` is empty (line 574). ✓

### 7.3 Campaigns ordered by provider ID, numerically

Confirmed: `sorted(target_ids)` at line 567. Not by `created_at`. ✓

### 7.4 The connected-status check is exact-match, not substring

Line 244: `str(st).lower().strip() == "connected"`. The result block notes the risk: "If the provider uses a different status string (e.g., 'active', 'valid'), the check will refuse valid senders." This is the safe failure mode.

---

## 8. Dispositions

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | The three TASK-296 artifacts exist, are correctly implemented, and their 58 tests pass | — | VERIFIED |
| 2 | The central claim (set diff catches count-match/key-mismatch) is confirmed by mutation test | — | VERIFIED |
| 3 | Zero production callers in `src/` — but this is by design for a QA script; consumed by CLI + tests + future harness | Low | ACCEPTED (task-scoped) |
| 4 | Sender status rule cannot be integration-tested through FakeBison (fake serves no status field) | Low | NOTED (disclosed in result block) |
| 5 | No live run against the EmailBison estate has been performed | Medium | OWED (Claude to run from production worktree) |
| 6 | Branch carries significant scope drift: TASK-314, TASK-364, TASK-398, TASK-413, infrastructure — must cherry-pick, not merge | Medium | CHERRY-PICK ONLY |
| 7 | `src/bisonfactory.py` was edited despite being FORBIDDEN for TASK-296 | — | Not TASK-296's doing; belongs to TASK-364 |
| 8 | No production code would be deleted by merging | — | CLEAN |

---

## 9. Recommendation

**MERGE (cherry-pick) — TASK-296's own files are correct and well-tested.**

The three artifacts and their tests are solid. The set-diff defect is real, the implementation catches it, and the mutation test proves the tests would detect a regression to count comparison. The result block is honest about what was and was not done (no live run, FakeBison gap).

**Conditions:**

1. **Cherry-pick only TASK-296's files.** The branch carries four other tasks' work and infrastructure changes. Merging the whole branch would import unreviewed TASK-364 factory wiring, TASK-314 regression tests, and TASK-413 seat cap scripts.
2. **Run the check live.** The first production run against the real EmailBison estate is still owed. Claude should run it from his worktree against a named `work/` copy.
3. **TASK-292 dependency.** The check is not registered in any QA harness. When TASK-292 (the harness) lands, `check_campaign_bison.run` should be registered in `scripts/qa/__init__.py::CHECKS`.

**CLOSE: no.** The work is real, the tests are falsifiable, and the artifact does what it claims. Closing would waste it.

**REWORK: no.** The implementation is correct for what it is. The gaps (no live run, FakeBison sender status) are acknowledged and acceptable for the task's scope.
