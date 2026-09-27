# GLM branch verification: TASK-364

Branch: `worktree-agent-abf3e260cec92585d`
Date: 2026-09-27T22:21:01.201795+00:00
Model: glm-5.3
Duration: 49.164s
Usage: {'prompt_tokens': 2840, 'completion_tokens': 4014, 'total_tokens': 6854, 'reasoning_tokens': 3138, 'cached_tokens': 128}

## Verdict: FAIL

**2 new test failures not in baseline: ['test_add_lead_is_refused_for_finished (tests.test_campaign_cannot_send.TheNarrowedSeals.test_add_lead_is_refused_for_finished)', 'test_finished_is_not_proven_safe (tests.test_campaign_cannot_send.ThePredicateReadsProviderTruth.test_finished_is_not_proven_safe)']**

## GLM spend

This call: 0 ledger rows, 0 micro-USD

## New test failures

- `test_add_lead_is_refused_for_finished (tests.test_campaign_cannot_send.TheNarrowedSeals.test_add_lead_is_refused_for_finished)`
- `test_finished_is_not_proven_safe (tests.test_campaign_cannot_send.ThePredicateReadsProviderTruth.test_finished_is_not_proven_safe)`

## Changed files (19)

- `docs/CADENCE-ROWS-2026-09-27-WHICH-CAMPAIGNS-REFUSE.md`
- `docs/MERGE-REQUEST-2026-09-27-TASK-364-ONE-CANONICAL-PLAN.md`
- `scripts/heyreach_readback.py`
- `scripts/render_preview.py`
- `scripts/write_heyreach_sequence.py`
- `src/bisonfactory.py`
- `src/heyreachfactory.py`
- `src/sequenceplan.py`
- `tests/test_an_approval_certifies_the_words_that_ship.py`
- `tests/test_an_approval_is_not_a_fact_check.py`
- `tests/test_bison_campaign_write.py`
- `tests/test_campaign_cannot_send.py`
- `tests/test_campaign_repetition_integration.py`
- `tests/test_emailbison_no_empty_greeting.py`
- `tests/test_no_literal_name_in_campaign_graph.py`
- `tests/test_one_plan_decides_both_providers.py`
- `tests/test_the_copy_lint_refuses_the_real_send_path.py`
- `tests/test_the_linkedin_graph_follows_the_canonical_days.py`
- `tests/test_the_sequence_belongs_to_nobody.py`

## Diff stat

```
 ...DENCE-ROWS-2026-09-27-WHICH-CAMPAIGNS-REFUSE.md | 132 +++++
 ...QUEST-2026-09-27-TASK-364-ONE-CANONICAL-PLAN.md | 256 +++++++++
 scripts/heyreach_readback.py                       |  26 +-
 scripts/render_preview.py                          |  10 +-
 scripts/write_heyreach_sequence.py                 |   2 +-
 src/bisonfactory.py                                | 280 +++------
 src/heyreachfactory.py                             | 244 +++-----
 src/sequenceplan.py                                | 638 +++++++++++++++++++++
 ...st_an_approval_certifies_the_words_that_ship.py |   2 +-
 tests/test_an_approval_is_not_a_fact_check.py      |   2 +-
 tests/test_bison_campaign_write.py                 |   7 +-
 tests/test_campaign_cannot_send.py                 |   4 +-
 tests/test_campaign_repetition_integration.py      |   5 +-
 tests/test_emailbison_no_empty_greeting.py         |   2 +-
 tests/test_no_literal_name_in_campaign_graph.py    |  53 +-
 tests/test_one_plan_decides_both_providers.py      | 552 ++++++++++++++++++
 ...est_the_copy_lint_refuses_the_real_send_path.py |   2 +-
 ...he_linkedin_graph_follows_the_canonical_days.py |  37 +-
 tests/test_the_sequence_belongs_to_nobody.py       |  20 +-
 19 files changed, 1846 insertions(+), 428 deletions(-)

```

## Acceptance output

```
(no acceptance commands extracted from task file)
```

## GLM response

## 1. Does the new code have a production caller?

**Cannot confirm from provided evidence — strong circumstantial candidates.** The branch's centerpiece is `src/sequenceplan.py` (+638, pure addition). The diff *shape* implies its callers: `src/bisonfactory.py` (280 changed, graph suggests net deletion), `src/heyreachfactory.py` (244 changed, net deletion), and `scripts/write_heyreach_sequence.py` (2 lines — the signature of an import swap). Logic appears to have moved *out* of the two factories *into* the plan module, which only makes sense if the factories now call it. But I was given a stat summary, not hunks — I cannot cite a single import statement or call site, and I will not invent line numbers. **Verifiable only by reading the actual diff of `bisonfactory.py` / `heyreachfactory.py`.**

## 2. Can the acceptance check fail?

**The acceptance check does not exist.** "(no acceptance commands extracted from task file)" — there is no command to feed an input to. Vacuous by absence. Additionally, the test-results block is **truncated mid-name** (`test_write_three_steps_readback_matches (tests.t` — cut off), and results for these changed test files never appear in the provided output:

- `test_one_plan_decides_both_providers.py` — the 552-line test carrying the branch's headline claim
- `test_the_linkedin_graph_follows_the_canonical_days.py`
- `test_the_sequence_belongs_to_nobody.py`
- `test_no_literal_name_in_campaign_graph.py`
- `test_campaign_repetition_integration.py`
- `test_emailbison_no_empty_greeting.py`
- `test_the_copy_lint_refuses_the_real_send_path.py`

The branch's central claim is certified by a test file whose result I was never shown.

## 3. Does any number reconcile?

**Yes — the diffstat reconciles exactly.** Sum of per-file change counts: sources 132+256+26+10+2+280+244+638 = 1588; tests 2+2+7+4+5+2+53+552+2+37+20 = 686; total 2274. And 1846 insertions + 428 deletions = 2274. ✓ Pure-addition files (132+256+638+552 = 1578) ≤ 1846, leaving 268 insertions across the 15 mixed files against 428 deletions — consistent, no contradiction constructible. **NO FINDING** on the arithmetic. The two docs' internal claims (e.g., cadence row counts) are not recomputable — I don't have their content.

## Also-check

- **Off-task files:** none nameable. All 19 files plausibly answer to "one canonical plan." `CADENCE-ROWS-...-WHICH-CAMPAIGNS-REFUSE.md` is the weakest fit (an inventory doc, not plan code), but with no task text to compare against — the task file yielded nothing — I cannot construct the mismatch. NO FINDING.
- **Scratch files:** none in the changed list (all under `docs/`, `scripts/`, `src/`, `tests/`). Caveat: a changed-files list does not show untracked files in the worktree; I cannot rule those out from here.

## Bottom line

No constructed defeat: the arithmetic reconciles, no scratch files, no provably dead bridge. But the branch is **unverified, not verified** — no acceptance command exists, the test log is truncated before the centerpiece test file reports, and the production call edge into `sequenceplan.py` is inferred from line counts, not shown. I need the actual diff hunks for the two factories and the write script, plus the complete test output, to either name the caller or hunt a real defeat.

VERDICT: NEEDS_CLAUDE - test log truncated before test_one_plan_decides_both_providers.py reports and no diff hunks to confirm sequenceplan.py's production callers.
