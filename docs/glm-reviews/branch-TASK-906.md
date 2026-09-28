# GLM branch verification: TASK-906

Branch: `qwen-worker-8-r13`
Date: 2026-09-28T19:35:40.579901+00:00
Model: glm-5.3
Duration: 103.705s
Usage: {'prompt_tokens': 3007, 'completion_tokens': 8331, 'total_tokens': 11338, 'reasoning_tokens': 7521, 'cached_tokens': 0}

## Verdict: FAIL

**acceptance command `runtime_approval_hash_probe.py --mode project` exited 2 (missing required `--state`) and never verified approval-hash stability for the bodies this branch changed.**

## GLM spend

This call: 0 ledger rows, 0 micro-USD

## Changed files (7)

- `docs/qwen-tasks/REVIEW/TASK-906-the-signature-must-be-composed-into-the-copy.md`
- `scripts/render_preview.py`
- `src/bisonfactory.py`
- `src/render.py`
- `src/sendersignature.py`
- `src/trailingcontent.py`
- `tests/test_task906_signature_composed_into_copy.py`

## Diff stat

```
 ...the-signature-must-be-composed-into-the-copy.md |  58 +++
 scripts/render_preview.py                          |  12 +-
 src/bisonfactory.py                                |  51 ++-
 src/render.py                                      |  62 +--
 src/sendersignature.py                             |  69 +++
 src/trailingcontent.py                             |  64 +++
 tests/test_task906_signature_composed_into_copy.py | 489 +++++++++++++++++++++
 7 files changed, 756 insertions(+), 49 deletions(-)

```

## Acceptance output

```
$ py -3 -m unittest tests.test_render_preview
exit=0
.............................
----------------------------------------------------------------------
Ran 29 tests in 0.062s

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
Ran 10 tests in 0.022s

OK

$ py -3 -m unittest tests.test_task904_opt_out
exit=0
..................
----------------------------------------------------------------------
Ran 18 tests in 0.007s

OK

$ py -3 -m unittest tests.test_the_research_pack_has_one_shape
exit=0
...................
----------------------------------------------------------------------
Ran 19 tests in 0.307s

OK

$ py -3 -m unittest tests.test_approve
exit=0
...........................................
----------------------------------------------------------------------
Ran 43 tests in 1.728s

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
Ran 51 tests in 0.736s

OK

$ py -3 scripts/runtime_approval_hash_probe.py --mode project
exit=2
usage: runtime_approval_hash_probe.py [-h] --state STATE [--id IDS]
                                      [--limit LIMIT] [--negative-control]
                                      [--no-live] [--mode {generate,project}]
                                      [--campaign CAMPAIGN]
                                      [--construct-from CONSTRUCT_FROM]
                                      [--construct-limit CONSTRUCT_LIMIT]
                                      [--json JSON_OUT]
runtime_approval_hash_probe.py: error: the following arguments are required: --state

$ py -3 -c "import sys; from scripts.render_preview import _fixture_rec_email as F, _fixture_config_email as C, _build_email_plan as B; from src import optout as O; p=B(C(),[F()]); bad=[(i,v['name'],v['value'].count(O.OPT_OUT_LINE)) for i,L in enumerate(p['leads']) for v in L['variables'] if v['name'].startswith('body_') and v['value'].count(O.OPT_OUT_LINE)!=1]; sys.exit('WRONG opt-out count: %r' % (bad,)) if bad else print('OK: exactly one opt-out line in every body on every lead')"
exit=0
OK: exactly one opt-out line in every body on every lead

$ py -3 -c "import sys; from scripts.render_preview import _fixture_rec_email as F, _fixture_config_email as C, _build_email_plan as B; p=B(C(),[F()]); b=[v['value'] for v in p['leads'][0]['variables'] if v['name']=='body_1']; sys.exit('em1 P.S. count=%r' % [x.count('P.S.') for x in b]) if [x for x in b if x.count('P.S.')!=1] else print('OK: em1 carries exactly one P.S.')"
exit=0
OK: em1 carries exactly one P.S.
```

## GLM response

## 1. Production caller for the new code?

**Probable callers exist, but I can only prove it behaviorally, not textually.**
- The bridge modules are `src/trailingcontent.py` (+64) and `src/sendersignature.py` (+69).
- Callers should be `src/render.py` (62 changed lines, deletion-heavy — consistent with deleting local `_append_ps` and importing the shared one) and `src/bisonfactory.py` (+51 — consistent with gaining signature composition into the projection).
- Evidence: `test_signature_in_rendered_email` and `test_signature_in_projection` exercise the real modules and pass, so *something* in production composes the signature.
- **Blind spot I cannot close from a diffstat:** `test_no_append_ps_in_render` / `test_no_append_ps_in_bisonfactory` are absence-only checks (grep for a function *named* `_append_ps`). They would pass if `render.py` inlined a differently-named local appender and left `trailingcontent.py` called only by tests. The import lines are not visible in what I was given. Callers: named, inferred, not proven.

## 2. Can the acceptance check fail?

- **The probe cannot pass at all — and didn't.** `py -3 scripts/runtime_approval_hash_probe.py --mode project` → **exit=2**, argparse "required: --state". It errored before doing any work. TASK-906 changes the content of every `body_N`; the approval-hash probe is exactly the guard that the change doesn't invalidate approved sends, and **it never executed**. Every input fails as invoked, because the argument is missing.
- The opt-out one-liner is non-vacuous (the fixture yields five `body_` variables, per `test_all_five_bodies_have_exactly_one_opt_out`); a double-compose would make `count != 1` and exit non-zero. But it covers one record × one config — no missing-sender, no pre-existing-opt-out variants at acceptance level.
- The P.S. one-liner inspects only `body_1` of `leads[0]`. The em3-own-P.S.-dedupe case is covered by unit tests only.

## 3. Do the numbers reconcile?

- Diffstat: 58+12+51+62+69+64+489 = **805** = 756 insertions + 49 deletions. ✓
- Enumerated new tests: 5+3+4+5+3+6+3+4+3 = **36** = "Ran 36 tests". ✓
- 7 files listed = 7 in diffstat. ✓

## Also check

- **Files vs. task:** all seven answer to "signature composed into the copy." `scripts/render_preview.py` is tooling, but it's the harness the acceptance one-liners import and it had to track the new compose API — acceptable.
- **Scratch files:** none among changed files (*.txt/*.err/*.out absent). Untracked files aren't visible in a diffstat — not checkable from what I was given.
- Note: `test_owner_to_identity` cites `clients.sender_identity`, but `clients.py` is unchanged — fine (pre-existing consumer link), just confirming it's not a missed edit.

## The defeat

The acceptance transcript contains an **exit=2**. The branch's own evidence shows a required runtime verification (approval-hash stability on the changed projection) never ran, while every other check that did run was fixture-scoped. Exit=0 on 220 unit tests does not cover this.

VERDICT: FAIL - acceptance command `runtime_approval_hash_probe.py --mode project` exited 2 (missing required `--state`) and never verified approval-hash stability for the bodies this branch changed.
