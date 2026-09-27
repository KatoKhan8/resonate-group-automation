# TASK-434 — GLM Independent Verification: TASK-245

## Review metadata

| Field | Value |
|-------|-------|
| Task reviewed | TASK-245 — nightly sourcing ends at candidates |
| Branch | origin/qwen-worker-4-r9 |
| Branch HEAD SHA | e05f401e6b3126bd248a7a54c14b3ba86828c73a |
| SHA verified by | `git rev-parse origin/qwen-worker-4-r9` → matches |
| Review worktree | ../glm-review-task-434 (detached at e05f401e) |
| Review date | 2026-09-27 |
| Reviewer | GLM (independent, via TASK-434) |
| Protocol | docs/GLM-REVIEW-PROTOCOL.md |

## What TASK-245 claims (from its result block)

- **STATUS:** DONE
- **ARTIFACT KIND:** test fix
- **COMMIT SHA:** 22ea4ca0 (fix) + 28df9351 (move to REVIEW)
- **TESTS:** 24/24 pass in `tests/test_task245_nightly_sourcing_ends_at_candidates.py`
- **FILES CHANGED:** Only test fixtures — added `icp_status: "qualified"` and `_sourced_at` to 3 fixtures in `TestWeeklyExportColumns`
- **RISKS:** None — production code unchanged
- **Pre-existing failure:** `test_review_may_not_reach_the_export.test_the_real_pool_on_disk_is_refused_today` confirmed present before this change

## Findings

### F1 — Artifact exists and does what the result block claims: VERIFIED

The production modules (`src/nightlysourcing.py`, `src/candidatelist.py`, `src/candidateexport.py`) exist on master AND on the branch. The test file exists on both. The branch's diff is exactly what the result block says: 3 test fixtures in `TestWeeklyExportColumns` gained two fields each (`icp_status: "qualified"`, `_sourced_at: "2026-09-25T02:00:00+00:00"`).

**Evidence:**
```
$ git diff master...e05f401e -- tests/test_task245_nightly_sourcing_ends_at_candidates.py
```
Shows exactly 6 added lines across 3 fixtures. No other changes to the test file.

```
$ git diff master...e05f401e -- src/nightlysourcing.py src/candidatelist.py src/candidateexport.py
```
Empty. Production code is byte-identical to master.

### F2 — Tests pass on the branch, fail on master without the fix: VERIFIED

**On the branch (with fix):**
```
$ python -m unittest tests.test_task245_nightly_sourcing_ends_at_candidates -v
Ran 24 tests in 0.296s
OK
```

**On master (without fix):**
```
$ python -m unittest tests.test_task245_nightly_sourcing_ends_at_candidates.TestWeeklyExportColumns -v
FAILED (failures=3)
```
The 3 failures are `test_export_csv_shape`, `test_export_json_payload`, `test_export_marks_candidates` — exactly the 3 tests whose fixtures were fixed.

**Root cause confirmed:** `exportable_candidates()` in `src/candidateexport.py:71-108` requires both `icp_status == "qualified"` (ISSUE-019 verdict gate) and `_sourced_at` provenance (ISSUE-031 retired-pool gate). The fixtures were written before these gates landed and were not updated. The fix is correct and minimal.

### F3 — Existence is not function: production callers traced

| Module | Production callers | Verdict |
|--------|-------------------|---------|
| `nightlysourcing` | `scripts/qualify_sourced_supply.py:122,134` (calls `_mx_classify`, `_local_collision`); CLI via `python -m src.nightlysourcing` | CONSUMED |
| `candidatelist` | `nightlysourcing.py:170,538,583`; `candidateexport.py:99,181`; `scripts/source_agency_supply.py:212` | CONSUMED |
| `candidateexport` | No importer in `src/` or `scripts/`. CLI only via `python -m src.candidateexport` | CLI-ONLY |

**Assessment:** `candidateexport` has no programmatic caller. It is invoked as a scheduled CLI job (Monday 07:00 Zagreb). This is architecturally valid for a weekly export — it is the terminal output of the pipeline, not an intermediate layer. However, it means TASK-244's approval intake cannot yet import `candidateexport`'s output programmatically and must parse the CSV/JSON file. This is not a defect in TASK-245 but a gap for TASK-244 to close.

### F4 — Test falsifiability assessment

**Strong tests (behavioral, could catch real bugs):**
- `test_full_pipeline_dry_run` — runs the full pipeline with faked search, verifies candidates are produced
- `test_candidate_has_no_contacts` — runs pipeline, asserts no contacts/email/linkedin in output
- `test_rejected_domain_stays_on_list` — verifies deduplication and state persistence
- `test_duplicate_domain_is_not_appended` — verifies domain-level dedup
- `test_export_csv_shape`, `test_export_json_payload`, `test_export_marks_candidates` — verify export output structure and state transitions

**Weaker tests (source-text assertions, could be fooled by renaming):**
- `test_pipeline_refuses_to_advance` — calls `nightlysourcing.pipeline_refuses_to_advance_past_candidates()` which uses `inspect.getsource(run)` to check for forbidden names. This is a source-text assertion. It catches direct imports of forbidden modules but would not catch a new forbidden call through an alias or wrapper.
- `test_no_person_search_in_stages` — same pattern, `inspect.getsource` on each stage function

**Mutation test not performed:** The result block does not claim a mutation test, and I did not perform one. The source-text guards are structural barriers, not behavioral proofs. A developer could add a people-search call under a different name and these tests would not catch it. The behavioral test `test_candidate_has_no_contacts` partially covers this (contacts would appear in output), but only if the search actually returns contacts in the fake.

### F5 — Pre-existing failure confirmed

`test_review_may_not_reach_the_export.TheLegacyPoolIsRetiredFromEveryExportPath.test_the_real_pool_on_disk_is_refused_today` fails on BOTH master and the branch with the same error: `RetiredCandidatePool not raised`. The result block correctly identifies this as pre-existing and unrelated to the fix.

**Root cause:** The on-disk `candidates.jsonl` is empty (0 rows), so `exportable_candidates()` returns an empty list and the legacy-pool refusal never triggers. This is an environmental precondition, not a code defect.

### F6 — Deletion risk: NONE for production code

```
$ git diff master...e05f401e --diff-filter=D --name-only
docs/qwen-tasks/TODO/TASK-264-every-test-module-runs-in-isolation.md
docs/qwen-tasks/TODO/TASK-279-the-19612-packs-arrive-in-chunks-or-not-at-all.md
docs/qwen-tasks/TODO/TASK-408-glm-verify-task-319.md
docs/qwen-tasks/TODO/TASK-414-spend-report-wiring-check.md
docs/qwen-tasks/TODO/TASK-422-heyreach-seat-cap-check.md
```

All "deleted" files are task files moving from TODO to REVIEW/DONE — normal workflow stage transitions. No production code, no tests, no configuration is deleted.

### F7 — Scope drift: SIGNIFICANT

The branch carries 51 commits not on master. Only 3 are TASK-245:
- `22ea4ca0` — fix 3 export test fixtures
- `28df9351` — move to REVIEW
- `be43623b` — update commit SHA

The other 48 commits are from TASK-246, TASK-264, TASK-279, TASK-285, TASK-298, TASK-326, TASK-364, TASK-408, TASK-410, TASK-414, TASK-422, TASK-423, TASK-426, TASK-427, TASK-429, and operator decisions/handoff docs.

**Cherry-pick scope:** To merge only TASK-245's work, cherry-pick `22ea4ca0` alone. It is a single commit touching only `tests/test_task245_nightly_sourcing_ends_at_candidates.py` with 6 added lines. The other 48 commits are independent work that should be reviewed and merged through their own verdicts.

## Disposition

| Finding | Disposition | Evidence |
|---------|-------------|----------|
| Artifact exists | VERIFIED | `git diff master...e05f401e` shows exactly the claimed change |
| Tests pass | VERIFIED | 24/24 on branch; 3 fail on master without fix |
| Production callers | VERIFIED | nightlysourcing and candidatelist consumed; candidateexport CLI-only |
| Test falsifiability | PARTIALLY VERIFIED | Behavioral tests are strong; source-text guards are structural but not behavioral |
| Pre-existing failure | CONFIRMED | Same failure on master, environmental cause |
| Deletion risk | NONE | Only task-file stage moves |
| Scope drift | SIGNIFICANT | 48 non-TASK-245 commits on branch; cherry-pick `22ea4ca0` |

## Recommendation: MERGE (cherry-pick only)

**MERGE** — but cherry-pick `22ea4ca0` only, not the whole branch.

The fix is correct, minimal, and well-scoped:
- 3 test fixtures updated to match production gates that already exist
- No production code changed
- Tests fail without the fix, pass with it
- Root cause is clear (fixtures predate ISSUE-019 and ISSUE-031 gates)
- No deletion risk
- No scope creep in the artifact itself

The branch's other work (48 commits from 14+ tasks) is separate and should be reviewed through its own GLM verdicts. Several of those tasks already have verdicts in REVIEW (TASK-408, TASK-410, etc.).

**What to cherry-pick:**
```
git cherry-pick 22ea4ca0
```

**What NOT to merge from this branch:** Everything else. The branch is a worker accumulation branch, not a single-task branch.

## Reproducibility

All commands in this review are reproducible:
```
git worktree add ../glm-review-task-434 e05f401e6b3126bd248a7a54c14b3ba86828c73a --detach
cd ../glm-review-task-434
python -m unittest tests.test_task245_nightly_sourcing_ends_at_candidates -v
git diff master...e05f401e -- tests/test_task245_nightly_sourcing_ends_at_candidates.py
git diff master...e05f401e -- src/nightlysourcing.py src/candidatelist.py src/candidateexport.py
```
