# GLM branch verification: TASK-901

Branch: `task-901-figure-gate-fix`
Date: 2026-09-28T16:57:42.083451+00:00
Model: glm-5.3
Duration: 98.912s
Usage: {'prompt_tokens': 3273, 'completion_tokens': 8361, 'total_tokens': 11634, 'reasoning_tokens': 7443, 'cached_tokens': 3264}

## Verdict: FAIL

**72% of the insertions are out-of-scope TASK-425/copy-engine work, there is no acceptance command, and no TASK-901 test outcome appears in the truncated transcript, so the claimed fix is verified by nothing shown.**

## GLM spend

This call: 0 ledger rows, 0 micro-USD

## Changed files (31)

- `docs/P0B-COPY-ENGINE-PARETO-2026-09-28.md`
- `docs/TASK-425-FINDINGS-2026-09-28.md`
- `docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md`
- `docs/TASK-425-OPERATER-SAZETAK-2026-09-28.md`
- `docs/qwen-tasks/REVIEW/TASK-901-the-figure-gate-matches-a-four-character-prefix.md`
- `docs/state/PROBLEM-REGISTER.md`
- `scripts/task425_artifact.py`
- `scripts/task425_criterion4_completeness.py`
- `scripts/task425_one_account_dry_run.py`
- `scripts/task425_verdict_mutations.py`
- `src/bisonfactory.py`
- `src/campaignstrategy.py`
- `src/copystages.py`
- `src/generate.py`
- `src/generate_campaign.py`
- `src/offers.py`
- `src/sequencegate.py`
- `tests/base.py`
- `tests/task425fixture.py`
- `tests/test_changing_an_approved_fact_changes_the_output.py`
- `tests/test_generate.py`
- `tests/test_only_the_last_subject_may_claim_finality.py`
- `tests/test_task400_rework2.py`
- `tests/test_task400_rework3.py`
- `tests/test_task901_figure_gate_prefix.py`
- `tests/test_the_copy_engine_converges_and_still_refuses.py`
- `tests/test_the_entrypoint_actually_loads_its_skills.py`
- `tests/test_the_entrypoint_is_the_only_generation_path.py`
- `tests/test_the_entrypoint_refuses_at_a_client_ceiling.py`
- `tests/test_the_offer_ladder_is_enforced_as_step_objectives.py`
- `tests/test_the_research_pack_has_one_shape.py`

## Diff stat

```
 docs/P0B-COPY-ENGINE-PARETO-2026-09-28.md          |  614 ++
 docs/TASK-425-FINDINGS-2026-09-28.md               |  600 ++
 docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md      | 7092 ++++++++++++++++++++
 docs/TASK-425-OPERATER-SAZETAK-2026-09-28.md       |  142 +
 ...-figure-gate-matches-a-four-character-prefix.md |  105 +
 docs/state/PROBLEM-REGISTER.md                     |  201 +
 scripts/task425_artifact.py                        |  973 +++
 scripts/task425_criterion4_completeness.py         |  122 +
 scripts/task425_one_account_dry_run.py             | 1528 +++++
 scripts/task425_verdict_mutations.py               |  155 +
 src/bisonfactory.py                                |  133 +-
 src/campaignstrategy.py                            |   45 +-
 src/copystages.py                                  |  131 +-
 src/generate.py                                    |  669 +-
 src/generate_campaign.py                           |  639 +-
 src/offers.py                                      |   19 +
 src/sequencegate.py                                |  410 +-
 tests/base.py                                      |   46 +-
 tests/task425fixture.py                            |  390 ++
 ...changing_an_approved_fact_changes_the_output.py |    4 +
 tests/test_generate.py                             |   58 +-
 ...est_only_the_last_subject_may_claim_finality.py |   39 +-
 tests/test_task400_rework2.py                      |    2 +
 tests/test_task400_rework3.py                      |   23 +-
 tests/test_task901_figure_gate_prefix.py           |  335 +
 ..._the_copy_engine_converges_and_still_refuses.py |  997 +++
 ...est_the_entrypoint_actually_loads_its_skills.py |    1 +
 ...t_the_entrypoint_is_the_only_generation_path.py |    1 +
 ...t_the_entrypoint_refuses_at_a_client_ceiling.py |    2 +-
 ..._offer_ladder_is_enforced_as_step_objectives.py |  632 ++
 tests/test_the_research_pack_has_one_shape.py      |  141 +-
 31 files changed, 16166 insertions(+), 83 deletions(-)

```

## Acceptance output

```
(no acceptance commands extracted from task file)
```

## GLM response

*(Only a diffstat was provided, not file bodies — I cannot cite line numbers and will not invent them. Findings below are the ones constructible from the diffstat, the file list, and the captured output.)*

## 1. Production caller?

Split population:

- **TASK-901 code itself** (figure gate, `src/sequencegate.py`): caller exists on the generation path — `src/generate.py` and `src/copystages.py` are modified in this same branch and the entrypoint/copy-engine tests pass through them. Exact call line not citable from a summary.
- **TASK-425 code riding this branch** — `scripts/task425_artifact.py` (973), `scripts/task425_criterion4_completeness.py` (122), `scripts/task425_one_account_dry_run.py` (1,528), `scripts/task425_verdict_mutations.py` (155), `tests/task425fixture.py` (390): **NO CALLER**. Nothing under `src/` imports from `scripts/`. **3,168 lines with no production caller.**

## 2. Can the acceptance check fail?

**No — it is vacuous by absence.** The result block itself says "(no acceptance commands extracted from task file)". Worse: the only TASK-901 verification is `tests/test_task901_figure_gate_prefix.py`, authored on this same branch, and **its results do not appear in the transcript** — the output truncates mid-name inside `test_generate.py` (`test_a_draft_that_never_passes_is_not_s…`), which sorts alphabetically before `test_task400_*`, `test_task901_*`, and `test_the_copy_engine_*`. The sole TASK-901 line shown is a sha256, which cannot fail. Zero TASK-901 test outcomes are in evidence.

## 3. Numbers reconcile?

- **Diffstat: reconciles exactly.** Per-file churn sums to 16,249 = 16,166 insertions + 83 deletions; file count 31 ✓.
- **Test totals: cannot reconcile** — transcript cut before any "Ran N tests" summary; pass count unverifiable.
- **Dry-run counts: contradiction.** Captured stdout shows `DRY RUN states {}`, `LIVE ENRICHMENT (credits spent) states {}` (×2), `DRY RUN … 0 record(s)` — zero records enriched or generated — under a header that claims **credits spent**. Meanwhile `docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md` is 7,092 lines billed as a *one-account* dry run. If that artifact reports any record count > 0, it contradicts the 0-record stdout; if it reports 0, the title is false.
- sha256 `e13cd9c8…52dff2`: not recomputable from a diffstat. NO FINDING.

## Files vs. task

Answer to TASK-901: `src/sequencegate.py`, `tests/test_task901_figure_gate_prefix.py`, `docs/qwen-tasks/REVIEW/TASK-901-….md`, `docs/state/PROBLEM-REGISTER.md` (~1,051 churn).

**Out of scope:** four `task425_*` scripts + fixture + three TASK-425 docs = 11,002 lines; `docs/P0B-COPY-ENGINE-PARETO…` = 614; copy-engine rework in `src/{bisonfactory,campaignstrategy,copystages,generate,generate_campaign,offers}.py` ≈ 1,636 churn plus ~1,810 lines of its tests. **≥11,616 of 16,166 insertions (72%) do not answer to TASK-901.**

## Scratch files

None — all 31 changed files are `.md`/`.py` under `docs/`, `scripts/`, `src/`, `tests/`. NO FINDING.

VERDICT: FAIL - 72% of the insertions are out-of-scope TASK-425/copy-engine work, there is no acceptance command, and no TASK-901 test outcome appears in the truncated transcript, so the claimed fix is verified by nothing shown.
