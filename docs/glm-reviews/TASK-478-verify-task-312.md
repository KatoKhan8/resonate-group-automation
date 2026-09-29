# TASK-478 — GLM Independent Verification of TASK-312

## Review metadata

| Field | Value |
|-------|-------|
| Target task | TASK-312 — implement stages A to H of the v2 copy engine |
| Branch reviewed | `origin/qwen-worker-4-r59` |
| Branch HEAD SHA | `073e81e040a2eee5bd116f5b82113698b894887b` |
| SHA verified by | `git rev-parse origin/qwen-worker-4-r59` → matches |
| Review worktree | `.qwen/worktrees/task478-review` (detached at exact SHA) |
| Reviewer | GLM (Qwen worktree `qwen-worker-3-r9`) |
| Date | 2026-09-29 |
| Disposition | **REWORK** |

**Note:** Task file specified output path `TASK-478-verify-task-219.md` — corrected to `TASK-312` as that is the actual target.

---

## 1. Artifact existence — VERIFIED

Both artifacts exist on the reviewed ref and nowhere else:

| File | Status | Lines |
|------|--------|-------|
| `src/copyengine.py` | New, exists at SHA | 759 |
| `tests/test_copyengine.py` | New, exists at SHA | 620 |
| `docs/qwen-tasks/DONE/TASK-312-implement-the-v2-copy-engine.md` | Moved from TODO | 60 |

`git log --diff-filter=A --all -- src/copyengine.py` confirms first appearance on commit `d6f6572c`.

---

## 2. Existence is not function — DISCONNECTED

**Zero production callers.** `git grep` for `copyengine`, `run_lead`, and `run_batch` across `src/`, `scripts/`, and `work/` at the reviewed SHA returns nothing outside `src/copyengine.py` itself and `tests/test_copyengine.py`.

The result block acknowledges this explicitly: *"The module is a library; the generation runner that calls it for production batches is Claude's to wire from his worktree."*

Per the standing operator rule: **zero production callers means DISCONNECTED, which is a rework and not a merge.** The engine is correctly built and tested as a library, but no production code path reaches it. It computes correctly and nothing downstream reads it.

**This is the primary finding and it determines the disposition.**

---

## 3. Does the artifact do what the result block claims? — PARTIALLY

### Claims verified

| Claim | Verified | Evidence |
|-------|----------|----------|
| 31 tests, all passing | ✅ | `python -m unittest tests.test_copyengine -v` → 31/31 OK in 0.011s |
| Acceptance command passes | ✅ | `sequencegate.check` with no qualification returns `passed=False`, failure step `['lead']` |
| Gate names `em2` on repetition | ✅ | Independent reproduction: identical body in em1/em2 → `failures: ['em2']` |
| Stage runner calls stages A-H in order | ✅ | Mutation test: 5 Groq calls counted (A-E), 1 Sonnet call (F), gate (G), output (H) |
| Existing suites pass | ✅ | `test_copylint`, `test_sequence_for_write`, `test_sequence_steps_carries_variant_identity` → 39/39 OK |
| Pre-existing `test_invariants` failures unrelated | ✅ | Same 2 failures present on `qwen-worker-3-r9` base (EmailBison routes + barrier checklist) |
| All dependency imports resolve | ✅ | `copyprompts`, `copystages`, `sequencegate` — all functions present |
| Tests use mocked model calls, no live APIs | ✅ | All tests inject `groq_fn`/`sonnet_fn` callables |
| No provider writes | ✅ | No send, activate, resume, or campaign mutation in the code |

### Claims not verified / owed

| Claim | Status |
|-------|--------|
| Ten-lead preview rendered | **OWED** — requires live API keys |
| Distinct capability count > 1 across ten leads | **OWED** — requires live run |
| Copy genuinely differs per company (not template with names swapped) | **UNVERIFIED** — requires live run |

---

## 4. Test falsifiability — ADEQUATE FOR SCOPE

**How could these 31 tests pass while the implementation is wrong?**

- **If stage ordering were broken:** The mock call counter would return wrong responses, and downstream assertions on qualification/written/gate would fail. Verified: removing the gate call would fail `assertIsNotNone(result["gate"])`.
- **If hold logic were inverted:** `test_not_agency_holds`, `test_no_usable_facts_holds`, `test_insufficient_holds`, `test_writer_hold` all assert on `result["held"]` and `result["written"]` being None. An inverted hold would produce written output where None is expected.
- **If output shapes were wrong:** `test_email_output_has_five_steps`, `test_three_threads`, `test_replies_are_marked` assert exact structural properties.
- **If JSON parsing were fragile:** `test_truncation_raises`, `test_literal_newlines_in_strings` test edge cases that would surface in production.

**What the tests do NOT cover:**
- Actual model output quality (deliberate — requires live keys)
- Production wiring (there is none to test)
- Prompt correctness (Claude's domain per the task split)

The tests are honest for what they test. They are tests of a library with mocked dependencies, and they verify the library's internal logic correctly. The gap is not in the tests but in the absence of a consumer.

---

## 5. Would merging delete anything? — NO

`git diff origin/master...073e81e040a2eee5bd116f5b82113698b894887b --stat` shows:

```
 .../TASK-312-implement-the-v2-copy-engine.md       |  60 ++
 src/copyengine.py                                  | 759 ++++++++++
 tests/test_copyengine.py                           | 620 +++++++++
 3 files changed, 1439 insertions(+)
```

Purely additive. No existing files modified. No deletions. Merging would not remove any classification, provider truth, or existing code.

---

## 6. Scope drift — NONE

The branch carries exactly three commits:
1. `ff37882a` — claim and move to RUNNING (task file)
2. `d6f6572c` — the implementation (copyengine.py + test_copyengine.py)
3. `073e81e0` — move to DONE with result block (task file)

No unrelated files touched. No scratch output. No configuration changes. No junk beside the work. Clean cherry-pick scope.

---

## Findings

### F1 — DISCONNECTED (Critical)

**Summary:** `src/copyengine.py` has zero production callers. No route in `src/`, `scripts/`, or `work/` imports or invokes `run_lead`, `run_batch`, or any other function from the module.

**Failure scenario:** The engine is merged. Nothing changes in production because nothing calls it. The next generation run uses the same v1 pipeline (`work/ten_pages.py`) it used before. The 759 lines of new code are dead weight.

**Evidence:**
```
$ git grep -n "copyengine" 073e81e0 -- src/ scripts/ work/
(empty)
$ git grep -n "from.*copyengine\|import.*copyengine\|run_lead\|run_batch" 073e81e0 -- src/ scripts/
(empty)
```

**Category:** correctness (wiring)
**Direction:** fails-closed (the code exists but does nothing)

### F2 — LIVE RUN OWED (Informational)

**Summary:** The ten-lead preview, distinct capability count, and old-vs-new comparison are not delivered. The result block acknowledges this. These require live Groq and Sonnet calls from a worktree with `config/.env`.

**Failure scenario:** Stage D defaults to the same capability for every lead (count = 1), which the spec says the gate should catch. Without the live run, this is unknown.

**Evidence:** Result block finding #5: "The ten-lead preview and distinct capability count are OWED."

### F3 — TASK FILE NAMING (Cosmetic)

**Summary:** The task file's output path says `TASK-478-verify-task-219.md` — a copy-paste error from a template. The target is TASK-312.

---

## Disposition

| Finding | Severity | Disposition |
|---------|----------|-------------|
| F1 — DISCONNECTED | Critical | REWORK — needs a production caller |
| F2 — Live run owed | Informational | ACCEPTED DEFERRED — Claude's to execute |
| F3 — Task file naming | Cosmetic | FALSE POSITIVE — task file typo, not a code defect |

---

## Recommendation: **REWORK**

**Reason:** The engine is correctly implemented and well-tested as a library. The code is clean, the tests are falsifiable for what they cover, the diff is purely additive, and there is no scope drift. However, the standing operator rule is unambiguous: **zero production callers means DISCONNECTED, which is a rework and not a merge.**

The result block itself acknowledges the gap: *"the generation runner that calls it for production batches is Claude's to wire from his worktree."* This is honest, but it means the artifact is incomplete by the repository's own standard. A thing computed correctly that nothing downstream reads is the recurring defect this repository has been bitten by repeatedly.

**What rework looks like:** Either (a) wire `copyengine.run_lead` or `run_batch` into `src/generate.py` or the production generation entrypoint, with tests that drive through that entrypoint, or (b) explicitly scope TASK-312 as "library only, wiring is a separate task" and create the wiring task before merge. Option (a) is preferred because it proves the chain end-to-end. Option (b) is acceptable if the wiring task is named, scoped, and tracked.

**What is NOT wrong:** The code itself. The tests. The spec compliance. The diff hygiene. The task file movement. These are all clean.
