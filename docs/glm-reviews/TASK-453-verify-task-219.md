# TASK-453 — GLM independent verification: TASK-298

**Review target:** TASK-298, absent-within-the-window-is-not-absent
**Branch:** origin/qwen-worker-r9
**Branch HEAD SHA named in task:** e456c6128774cfd00960ac50d7b39c6e99a3f8cd
**Branch HEAD SHA at time of review:** cbb1e1ddda40cbef9dcb1188d3ab4a4abc71ae4f (branch has moved)
**Reviewed SHA:** e456c6128774cfd00960ac50d7b39c6e99a3f8cd (checked out in isolated worktree)
**Review date:** 2026-09-28
**Review method:** static analysis + test execution + mutation falsification in detached worktree at e456c612

---

## 1. Does the artifact exist on this ref?

**YES.** All four artifacts exist at e456c612:

| File | Status |
|------|--------|
| `scripts/qa/check_readback.py` | present, 1217 lines |
| `tests/test_absent_within_the_window_is_unconfirmed.py` | present, 11 tests |
| `tests/test_the_watcher_is_running_the_code_we_think.py` | present, 8 tests |
| `docs/QA-READBACK-2026-09-25.md` | present, 165 lines |

All 19 tests pass green at the target SHA (0.072s).

**Already integrated to master.** Blob hash comparison:

| File | master blob | branch blob | Identical? |
|------|-------------|-------------|------------|
| `scripts/qa/check_readback.py` | `70923833` | `70923833` | YES |
| `scripts/qa/__init__.py` | `ca478180` | `6f4f88af` | NO — master is more detailed |
| `tests/test_absent_within_the_window_is_unconfirmed.py` | present | present | not compared |
| `tests/test_the_watcher_is_running_the_code_we_think.py` | present | present | not compared |
| `docs/QA-READBACK-2026-09-25.md` | present | present | not compared |

TASK-298's main implementation is byte-identical on master. The task is already integrated.

---

## 2. Existence is not function — consumer analysis

**The check is a QA tool, not a production `src/` module.** It has zero callers in `src/` — by design. The consumer is the QA harness (TASK-292's runner), which reads the `CHECKS` registry in `scripts/qa/__init__.py`.

The registry entry exists on both the branch and master:

```python
"readback": {
    "module": "scripts.qa.check_readback",
    "phase": "post_push",
    "subject": "campaign",
    "blocking": True,
},
```

The module docstring on master states: "A check module that is not listed in CHECKS does not run." The entry is present, so the check IS registered and will be consumed by the QA runner when TASK-292's harness invokes it.

The check also has a CLI entrypoint (`python -m scripts.qa.check_readback --workspaces <path>`) for standalone use.

**Verdict: CONSUMED.** The QA registry is the consumer. This is the correct pattern for a QA check.

---

## 3. Falsification of the result's own claims

### 3.1 UNCONFIRMED fires correctly (ISSUE-043)

Injected fake: provider returns `[101]` when pushed `{101, 102}`.

```
Verdict: UNCONFIRMED  (not PASS, not FAIL)
pushed_and_absent: [{'lead_id': 102, 'record_id': 'rec-002'}]
present_and_not_pushed: []
```

**Confirmed.** The core ISSUE-043 fix works: absent within the window is UNCONFIRMED.

### 3.2 Retry ladder sequence

Injected fake: provider returns `[101]` for first 2 calls, then `[101, 102]`.

```
initial:   UNCONFIRMED
t+60s:     UNCONFIRMED
t+180s:    PASS
t+600s:    NOT_RUN (ladder stopped at first PASS)
Final:     PASS
Provider calls: 3
```

**Confirmed.** Matches the constructed delayed-index sequence in the result block.

### 3.3 Still absent at t+600 → FAIL

Injected fake: provider always returns `[101]` when pushed `{101, 102}`.

```
Final: FAIL
Last attempt with result: t+600s
Absent IDs: [102]
```

**Confirmed.**

### 3.4 Set equality both directions

Injected fake: pushed `{101, 102}`, provider returns `[101, 999]`.

```
pushed_count: 2, provider_count: 2  (counts match — but sets don't)
pushed_and_absent: [102]
present_and_not_pushed: [999]
```

**Confirmed.** Counts alone would have said "match" — the set diff catches the mismatch in both directions.

### 3.5 emptyrender dependency

```
emptyrender.EMPTY: EMPTY
emptyrender.LITERAL_NONE: LITERAL_NONE
emptyrender.PLACEHOLDER: PLACEHOLDER
scan: exists
classify_row: exists
summarise: exists
```

**Confirmed.** The dependency the check imports is present with the expected interface.

### 3.6 watchsink and supervisor dependencies

Both import successfully. `watchesink.heartbeats` and `watchesink.events_path` exist. `supervisor` imports cleanly.

**Confirmed.** Live-mode imports will resolve.

---

## 4. Test falsifiability — one defect found

### FINDING: `test_watcher_reported_up_with_no_mtime_pair_is_rejected` does not assert rejection

**The test name says "rejected" but the verdict is PASS.**

When `module_mtime_fn=None` and `supervisor_witnesses_fn=None`:

```
verdict: PASS
watcher_found: True
module_stale: None
process_start: None
module_mtime: None
```

The implementation's logic:

```python
verdict = PASS
if not latest_beat.get("at"):
    verdict = UNCONFIRMED
elif module_stale is True:
    verdict = FAIL
```

When `module_stale` is `None` (not `True`), the verdict stays PASS. The test asserts the fields are None but does NOT assert the verdict should be anything other than PASS. The test name implies the watcher should be "rejected" but the implementation reports it as PASS.

**The task spec says:** "A watcher reported UP with no such pair is a watcher nobody checked." The implementation records the absence in the result fields but does not reflect it in the verdict. A downstream consumer reading `verdict: PASS` would believe the watcher is confirmed when nobody checked the mtime/process pair.

**Severity:** Medium. The data is in the result JSON (`module_stale: null`, `process_start: null`, `module_mtime: null`), so a careful consumer could catch it. But the verdict itself is misleading.

**Mutation test:** If `module_stale = None` were changed to `module_stale = True`, the test would still pass (it doesn't assert on the verdict). The test is not falsifiable for this claim — it verifies the fields are None but not what the verdict should be when they are.

---

## 5. Deletion risk

**The branch would NOT delete any production files from master.**

Files deleted by the branch vs master (all task lifecycle movements, not production code):

```
docs/qwen-tasks/TODO/TASK-264-every-test-module-runs-in-isolation.md
docs/qwen-tasks/TODO/TASK-319-five-skills-as-executable-sops.md
docs/qwen-tasks/TODO/TASK-389-contact-key-guard-cleanup.md
docs/qwen-tasks/TODO/TASK-394-contact-key-guard-verification.md
docs/qwen-tasks/TODO/TASK-406-glm-verify-task-396.md
docs/qwen-tasks/TODO/TASK-407-glm-verify-task-399.md
docs/qwen-tasks/TODO/TASK-418-offer-config-consistency-check.md
docs/qwen-tasks/TODO/TASK-420-docs-hygiene-pass.md
```

These are task files moved from TODO to REVIEW/DONE/BLOCKED on the branch. No `src/`, `tests/`, or `scripts/` files are deleted.

**However:** `scripts/qa/__init__.py` on the branch (`6f4f88af`) is a LESS detailed version than on master (`ca478180`). Master has explanatory comments about why the readback entry is not optional and why `check_campaign_heyreach.py` is not registered. Merging the branch version would regress this documentation. Since TASK-298 is already integrated, this is a non-issue — master should keep its version.

---

## 6. Scope drift

The branch at e456c612 carries 75 changed files vs master, from many tasks (TASK-264, TASK-273, TASK-294, TASK-302, TASK-319, TASK-400, etc.). TASK-298's specific artifacts are 5 files:

```
scripts/qa/check_readback.py       (new)
scripts/qa/__init__.py             (modified — added readback entry)
tests/test_absent_within_the_window_is_unconfirmed.py (new)
tests/test_the_watcher_is_running_the_code_we_think.py (new)
docs/QA-READBACK-2026-09-25.md     (new)
```

Cherry-picking TASK-298 would require only these 5 files. But since all are already on master, cherry-picking is moot.

---

## Findings summary

| # | Finding | Severity | Direction |
|---|---------|----------|-----------|
| 1 | Watcher test says "rejected" but verdict is PASS when no mtime/process pair | Medium | fails-open: a watcher nobody checked is reported PASS |
| 2 | TASK-298 already integrated to master — byte-identical check_readback.py | Info | no action needed |
| 3 | Branch's `__init__.py` would regress master's more detailed version | Low | already avoided since master has the better version |

---

## Disposition

**CLOSE — already integrated.**

TASK-298's work is already on master. The main implementation file (`check_readback.py`) is byte-identical. The registry entry exists. The tests pass. The core ISSUE-043 fix (absent within the window → UNCONFIRMED, retry ladder at t+60/t+180/t+600) is correctly implemented and falsified.

One finding remains for follow-up: the watcher mtime/pair test does not assert what its name claims. The verdict is PASS when the mtime/process pair is absent, which means "a watcher nobody checked" is reported as confirmed. This is a medium-severity defect in the test and a minor gap in the implementation. It does not block integration (which already happened) but should be addressed before the QA runner relies on the watcher rule in production.

**Recommendation:** No merge action needed — TASK-298 is already on master. Create a follow-up task for the watcher test/verdict defect if the QA runner will depend on it.
