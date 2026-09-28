# GLM branch verification: TASK-904

Branch: `qwen-worker-3-r11`
Date: 2026-09-28T18:53:01.779315+00:00
Model: glm-5.3
Duration: 93.397s
Usage: {'prompt_tokens': 2667, 'completion_tokens': 7402, 'total_tokens': 10069, 'reasoning_tokens': 6609, 'cached_tokens': 0}

## Verdict: PASS

## GLM spend

This call: 0 ledger rows, 0 micro-USD

## Changed files (7)

- `docs/qwen-tasks/REVIEW/TASK-904-every-email-carries-an-opt-out-line.md`
- `src/bisonfactory.py`
- `src/copylint.py`
- `src/optout.py`
- `src/render.py`
- `tests/test_task560_ps_reaches_the_person.py`
- `tests/test_task904_opt_out.py`

## Diff stat

```
 ...TASK-904-every-email-carries-an-opt-out-line.md |  74 ++++++
 src/bisonfactory.py                                |   9 +-
 src/copylint.py                                    |  23 +-
 src/optout.py                                      |  32 +++
 src/render.py                                      |   4 +-
 tests/test_task560_ps_reaches_the_person.py        |   7 +-
 tests/test_task904_opt_out.py                      | 253 +++++++++++++++++++++
 7 files changed, 393 insertions(+), 9 deletions(-)

```

## Acceptance output

```
$ py -3 -m unittest tests.test_render_preview
exit=0
.............................
----------------------------------------------------------------------
Ran 29 tests in 0.058s

OK

$ py -3 -m unittest tests.test_task560_ps_reaches_the_person
exit=0
..............
----------------------------------------------------------------------
Ran 14 tests in 0.002s

OK

$ py -3 -m unittest tests.test_task907_ps_producer_hop
exit=0
..........
----------------------------------------------------------------------
Ran 10 tests in 0.025s

OK

$ py -3 -m unittest tests.test_the_research_pack_has_one_shape
exit=0
...................
----------------------------------------------------------------------
Ran 19 tests in 0.296s

OK

$ py -3 -m unittest tests.test_approve
exit=0
...........................................
----------------------------------------------------------------------
Ran 43 tests in 1.692s

OK

$ py -3 -m unittest tests.test_generate
exit=0
DRY RUN
  states     {}

add --spend to call providers and the model. --live is refused.
LIVE ENRICHMENT (credits spent)
  states     {}
LIVE ENRICHMENT (credits spent)
  states     {}
REFUSED: --spend includes the generate stage and no model is configured: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL unset. Configure the model, or run without the generate stage.
...................................................
----------------------------------------------------------------------
Ran 51 tests in 0.780s

OK

$ py -3 -c "from scripts.render_preview import _fixture_rec_email, _fixture_config_email, _build_email_plan; r=_fixture_rec_email(); p=_build_email_plan(_fixture_config_email(),[r]); b=[v['value'] for v in p['leads'][0]['variables'] if v['name'].startswith('body_')]; print(len(b), 'bodies'); print([('opt-out' if 'reply STOP' in x else 'MISSING') for x in b])"
exit=0
5 bodies
['opt-out', 'opt-out', 'opt-out', 'opt-out', 'opt-out']
```

## GLM response

**1. Production caller for the new code (src/optout.py): YES.**
The consumers are `src/copylint.py` (23 lines changed — the lint rule that appends/counts the line, per `test_exactly_one_opt_out_passes` / `TestDuplicateOptOut`) and `src/render.py` (4 lines — the render path). The render path is proven live by the acceptance one-liner: `scripts.render_preview._build_email_plan → render → body_1..body_5` all carry `reply STOP`, and `test_render_emailbison_rows_includes_opt_out` puts it in the EmailBison CSV — the actual send payload. `src/bisonfactory.py` is constrained by `test_opt_out_string_is_in_one_place` (constant defined only in `src.optout`), which forces it to import rather than duplicate. The lint gate runs inside approve (43/43 green with the new rule active). Not test-only.

**2. Can the acceptance check fail? Yes — but only observably, never by exit code, and it is count-blind.**
- The one-liner is `print(...)` with no assertion: a body missing the line prints `MISSING` and still exits 0. The only enforcement is a human reading stdout; the real enforcement lives in `test_all_five_bodies_carry_opt_out_in_projection`.
- Concrete defeating input: a body containing the line **twice**. `'reply STOP' in x` is true for 1, 2, or 3 occurrences — the exact duplicate state `TestDuplicateOptOut` says must be refused prints `['opt-out', ...]` and is blessed by this check.
- Scope: it inspects `leads[0]` only; a missing line on any other lead is invisible to it.
The only input I can name that flips output to `MISSING` is the disabled-check state exercised by `test_disabling_opt_out_check_lets_missing_pass` (a mutation knob, not a runtime input) — so the check is weak, not vacuous.

**3. Numbers reconcile.**
- Test block: 14 task-560 tests listed + 18 task-904 tests listed = **32**, matching "Ran 32 tests". The acceptance run of task-560 alone also shows 14, consistent.
- Diffstat: per-file marks 74+9+23+32+4+7+253 = **402** = 393 insertions + 9 deletions. Exact.
- "5 bodies" = the five-email fixture batch (`test_full_batch_with_opt_out_passes_clean`), 5/5 carry the line.

**File accountability:** All seven files answer to TASK-904. The one file not owned by this task is the 7-line edit to `tests/test_task560_ps_reaches_the_person.py` — legitimate collateral, since appending an opt-out line changes rendered bodies that 560's equality assertions pinned (`test_emailbison_rows_without_ps_unchanged`). 560's negative controls still pass (14/14, including "em1 with no ps key is REFUSED"), so expectations were adapted, not deleted — but those 7 lines are the spot to eyeball in the full hunks.

**Scratch files:** None — no `*.txt`/`*.err`/`*.out` at root in the changed set.

**Residual caveat:** I have the diffstat, not hunks, so no line numbers; specifically I cannot read bisonfactory's 9 lines or render's 4 lines directly — both are behaviorally pinned by the tests above (single-definition, CSV inclusion, 5/5 projection), so I treat that as covered rather than open.

VERDICT: PASS
