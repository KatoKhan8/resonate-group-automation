# TASK-503 — Independent GLM Verification of TASK-386

**Target task:** TASK-386 — ingest the client file's LinkedIn and headcount columns into records and packs
**Branch reviewed:** `origin/qwen-worker-8-r9`
**Branch HEAD SHA:** `afa48d18ab6df1e3478cd7abf1c30a59287ddd59`
**Verified SHA:** `afa48d18ab6df1e3478cd7abf1c30a59287ddd59` (confirmed via `git rev-parse`)
**Review method:** Isolated worktree at exact SHA (`.qwen/worktrees/task503-review`)
**Review date:** 2026-09-29

---

## 1. Does the artifact exist on this ref, and does it do what the result block claims?

**VERIFIED.** The artifact exists at the exact SHA.

### What was claimed

`src/packfacts.py:pack_for()` now calls two new functions — `_add_company_facts` and `_add_linkedin_facts` — that include headcount and LinkedIn URL facts in the pack that `copylint.check_batch` reads.

### What was found

**`src/packfacts.py` at SHA `afa48d18`:**
- `_add_company_facts(rec, admitted)` at line 144: reads `rec["company_facts"]["headcount"]` and `rec["company_facts"]["linkedin"]`. Headcount included only when `state in ("agreed", "single_source")` AND `isinstance(value, int) and value > 0`. Company LinkedIn included when present and non-empty.
- `_add_linkedin_facts(rec, admitted)` at line 166: iterates `rec["contacts"]` and includes each contact's `linkedin` URL when present and non-empty.
- Both functions called from `pack_for()` at lines 139-140, after the research-row loop.

**`tests/test_packfacts_includes_record_facts.py`** — new file, 226 lines, 17 tests across 4 classes:
- `HeadcountInPack` (7 tests): agreed/single_source with value → present; conflict/unestablished/zero/band-only → absent; no company_facts → no crash.
- `LinkedInInPack` (5 tests): contact URL → present; company URL → present; empty → absent; no contacts → no crash; multiple contacts → each contributes.
- `EndToEndTrace` (3 tests): "45-person team" traces through `copylint.untraceable`; "200-person team" does NOT trace; no-headcount body is clean.
- `WiringCheck` (2 tests): assert the functions are actually called by `pack_for`, not just defined.

**All 17 tests pass** (ran `py -3 -m unittest tests.test_packfacts_includes_record_facts -v` in the isolated worktree: 17/17 OK in 0.039s).

---

## 2. Existence is not function — is there a production caller?

**VERIFIED. The chain is connected end-to-end.**

```
src/bisonfactory.py:559   pack, _ = packfacts.pack_for(by_id.get(lead.get("record_id")))
src/bisonfactory.py:560   packs[lead_id] = pack
src/bisonfactory.py:575   found = copylint.check_batch(leads, packs, steps_expected=expected)
```

`bisonfactory._copylint_batch` builds the packs dict by calling `packfacts.pack_for` for each lead's record. The packs are passed directly to `copylint.check_batch`. The new facts enter the pack inside `pack_for` and are therefore visible to `copylint.untraceable` when it checks each lead's copy.

**Zero-consumer risk: NONE.** The production caller exists and consumes the pack directly.

---

## 3. Falsification of the result's own claims

### 3a. Wiring break test (INDEPENDENTLY REPRODUCED)

Disabled the two calls at `packfacts.py:139-140` by commenting them out. Re-ran WiringCheck:

```
test_pack_for_calls_add_company_facts ... FAIL
test_pack_for_calls_add_linkedin_facts ... FAIL

AssertionError: 'headcount: 10' not found in [] : _add_company_facts is not wired into pack_for
AssertionError: False is not true : _add_linkedin_facts is not wired into pack_for
```

**Both tests fail for the intended reason** — the facts disappear from the pack when the wiring is removed. No different guard fires first. Restoring the calls brings the facts back.

### 3b. End-to-end trace (INDEPENDENTLY REPRODUCED)

Ran a live trace at the SHA:

```
Pack facts:
   {'snippet': 'headcount: 45', 'source': 'company_facts.headcount'}
   {'snippet': 'linkedin profile: https://linkedin.com/in/alice', 'source': 'contact.linkedin'}

Body: "Your 45-person team probably juggles spreadsheets."
Untraced: []                          ← 45 traces correctly

Body: "Your 200-person team probably juggles spreadsheets."
Untraced: ['200']                     ← 200 correctly flagged as untraced
```

### 3c. Negative controls (VERIFIED BY TEST)

- Conflicted headcount → absent from pack ✓
- Unestablished headcount → absent from pack ✓
- Band-only (agreed, value=None, range=[11,50]) → absent from pack ✓
- Zero headcount → absent from pack ✓
- Empty LinkedIn URL → absent from pack ✓
- No company_facts key → no crash ✓
- No contacts key → no crash ✓

---

## 4. Are the tests falsifiable?

**YES.** The tests assert on `pack_for`'s output (the pack dict), not on source text. They drive the real entry point (`packfacts.pack_for`) and check the resulting pack — the same object `copylint.check_batch` receives.

**How they could pass while the implementation is wrong:**
- If `copylint.untraceable` changed its number-extraction logic, the EndToEndTrace tests would need updating — but they would still correctly test that the pack carries the fact.
- If the headcount gating logic were inverted (e.g., `state not in (...)`) the negative tests would catch it.
- The WiringCheck tests specifically guard against the "defined but not called" defect that burned TASK-029 and TASK-019.

**Not accepted as proof but not present:** No `hasattr`, no source-text assertions, no fake cassettes.

---

## 5. Would merging it DELETE anything?

**NO source/test deletions.** `git diff master...afa48d18 --diff-filter=D --name-only -- src/ tests/` returns empty.

Three task files are deleted from `docs/qwen-tasks/TODO/` (TASK-334, TASK-373, TASK-375) — these are queue movements to DONE, not code deletions. The same files appear as additions in `docs/qwen-tasks/DONE/`.

TASK-386's own diff is purely additive:
- `src/packfacts.py`: +42 lines (7 docstring + 2 wiring calls + 33 new function body)
- `tests/test_packfacts_includes_record_facts.py`: new file, +226 lines

---

## 6. Scope drift

**The branch carries work from multiple tasks** (TASK-369, 373, 374, 375, 376, 377, and others). The full branch diff is 54 files, +3212/-366 lines.

**TASK-386's own contribution is isolated to two files:**
- `src/packfacts.py`
- `tests/test_packfacts_includes_record_facts.py`

The other source changes (`campaignstrategy.py`, `generate.py`, `generate_campaign.py`, `llm.py`, `slackconversation.py`) belong to TASK-373 (client threading) and TASK-375 (skill loading) and are already integrated or pending their own verdicts.

**Cherry-pick path:** TASK-386's two commits (`eb66a002` wire, `55d94e1e` result block) can be cherry-picked cleanly — they touch only `src/packfacts.py` and the new test file.

---

## Findings

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | The artifact exists, is wired into the production chain, and the tests catch wiring breaks | — | CONFIRMED |
| 2 | Headcount gating is correct: only agreed/single_source with positive int value enters the pack | — | CONFIRMED |
| 3 | No headcount is invented; missing evidence stays absent | — | CONFIRMED |
| 4 | CLI ingest path (`ingest.py`) still drops LinkedIn URLs — `_add_linkedin_facts` will find nothing from that path | Low | DOCUMENTED (not a regression; function is a no-op when data is absent) |
| 5 | The client CSV's `Url` column normalises to `url` which is not in `columns.py`'s alias table — web upload path may not map it | Low | DOCUMENTED (TASK-347's concern, not TASK-386's) |

---

## Disposition

**MERGE.**

TASK-386 is a clean, well-scoped, read-only change that closes a real gap: headcount and LinkedIn facts were present on the record but invisible to `copylint.untraceable`. The fix is minimal (two functions, called from the existing entry point), the gating is correct (missing evidence stays absent), the production chain is verified end-to-end, and the tests are falsifiable — proven by independent wiring break and live trace reproduction.

The documented risks (CLI ingest path, `Url` column alias) are upstream concerns for TASK-347 and do not make this change unsafe. The functions are no-ops when the data is absent.

---

## Reproducible commands

```bash
# Check out exact SHA
git worktree add .qwen/worktrees/review afa48d18ab6df1e3478cd7abf1c30a59287ddd59 --detach

# Run the tests
cd .qwen/worktrees/review
py -3 -m unittest tests.test_packfacts_includes_record_facts -v

# Verify production caller
grep -n "packfacts.pack_for" src/bisonfactory.py

# Verify wiring break detection
# Comment out lines 139-140 in src/packfacts.py, then:
py -3 -m unittest tests.test_packfacts_includes_record_facts.WiringCheck -v
# Both should FAIL

# Clean up
cd ../..
git worktree remove .qwen/worktrees/review
```
