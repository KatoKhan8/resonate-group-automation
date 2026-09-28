# GLM branch verification: TASK-905

Branch: `qwen-worker-5-r12`
Date: 2026-09-28T19:17:13.200621+00:00
Model: glm-5.3
Duration: 83.585s
Usage: {'prompt_tokens': 3566, 'completion_tokens': 6956, 'total_tokens': 10522, 'reasoning_tokens': 6175, 'cached_tokens': 0}

## Verdict: PASS

## GLM spend

This call: 0 ledger rows, 0 micro-USD

## Changed files (3)

- `docs/qwen-tasks/REVIEW/TASK-905-the-projection-must-come-from-the-plan.md`
- `src/bisonfactory.py`
- `tests/test_task905_projection_from_plan.py`

## Diff stat

```
 ...K-905-the-projection-must-come-from-the-plan.md |  75 +++++++
 src/bisonfactory.py                                | 111 +++++++++-
 tests/test_task905_projection_from_plan.py         | 228 +++++++++++++++++++++
 3 files changed, 409 insertions(+), 5 deletions(-)

```

## Acceptance output

```
$ py -3 -c "import shutil,os; src=r'C:/Users/Zvonimir/Desktop/resonate-group-automation/work'; dst=os.path.join(os.environ.get('TEMP','.'),'probe-work-905'); shutil.rmtree(dst,ignore_errors=True); shutil.copytree(src,dst); print(dst)"
exit=0
C:\Users\Zvonimir\AppData\Local\Temp\probe-work-905

$ py -3 scripts/runtime_approval_hash_probe.py --state "%TEMP%/probe-work-905" --mode project --campaign productive-email-batch1-kresimir --construct-from productive-email-batch1-kresimir --construct-limit 1
exit=0
== CONSTRUCTED INPUT (in the COPY only) ==
  {"cloned_from": "productive-email-batch1-kresimir", "campaign_id": "productive-email-batch1-kresimir", "record_ids": ["ogpartner-dk"], "cadence_steps": ["li1", "em1", "li2", "em2", "li3", "em3", "li4", "em4", "li5", "em5"]}

== SETUP ==
  state (COPY)            C:\Users\Zvonimir\AppData\Local\Temp\probe-work-905
  QUEUE env               C:\Users\Zvonimir\AppData\Local\Temp\probe-work-905\queue.jsonl
  copy queue sha256       dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
  model stub              http://127.0.0.1:55685  (loopback, not a real provider)
  CLI argv                python -m src.bisonfactory productive-email-batch1-kresimir
  instruments             A wrappers + B code-object profiler

== MEASURED PHASE: the real CLI, on copied production input ==
  generate.main() exit     1
  stub model calls         0

  target                                  wrapper profiler
  generate.run                                  0        0
  generate.generate_record                      0        0
  generate._generate_via_campaign               0        0
  generate._adapt_plan_to_cadence               0        0
  generate_campaign.generate                    0        0
  sequenceplan.new                              0        0
  sequenceplan.approval_hash                    1        1
  sequenceplan.derive_preview_data              0        0
  sequenceplan.derive_bison_payload             1        1
  sequenceplan.derive_heyreach_payload          0        0
  sequenceplan.for_campaign                     1        1
  sequenceplan.derive_bison_sequence            1        1
  bisonfactory._plan                            1        1
  bisonfactory._approved_copy                   0        0


== POSITIVE CONTROL 1: the projection and approval-hash tracers ==
  Each is called DIRECTLY. Both instruments must record ENTERED,
  or the NOT ENTERED above is UNKNOWN rather than a finding.

  target                                  wrapper profiler
  sequenceplan.approval_hash                    4        4
  sequenceplan.derive_preview_data              1        1
  sequenceplan.derive_bison_payload             1        1
  sequenceplan.derive_heyreach_payload          1        1
  sequenceplan.derive_bison_sequence            0        0
  direct-call returns      {"derive_preview_data": "dict", "derive_bison_payload": "dict", "derive_heyreach_payload": "dict", "approval_hash": "51038dd2e812cd60"}

== POSITIVE CONTROL 2: the provider-write interceptor ==
  deliberate write         POST https://send.resonategroup.co/api/leads
  outcome                  ProviderWriteRefused: REFUSED POST https://send.resonategroup.co/api/leads - a mutating provider call with no explicit authorization (no RESONATE_PROVIDER_WRITES and no allow_writes() scope). This is the guard added after 
  interceptor recorded it  True
  record                   {"phase": "CONTROL", "method": "POST", "host": "send.resonategroup.co", "url": "https://send.resonategroup.co/api/leads", "is_write": true, "prospect_facing": true, "production_guard": "ProviderWriteRefused", "outcome": "REFUSED by production guard"}

== THE FIVE ANSWERS, MEASURED PHASE ONLY ==
  generator                NOT ENTERED   (wrapper 0, profiler 0)
  SequencePlan             NOT CREATED   (wrapper 0, profiler 0)
  canonical projection     ENTERED       (wrapper 1, profiler 1)
  approval hash            ENTERED       (wrapper 1, profiler 1)
  provider writes          0

== INTEGRITY ==
  copy queue sha256 after  dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
  forbidden work/ writes   1  [{"phase": "CONTROL", "path": "C:\\Users\\Zvonimir\\Desktop\\resonate-group-automation\\.qwen\\worktrees\\verify-99924-accept\\work\\provider-write-refusals.jsonl", "mode": "a"}]
  non-loopback connects    0  
  provider calls, MEASURED 0 (all hosts)
  provider hosts, MEASURED none
  production queue.jsonl    UNCHANGED
    before dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
    after  dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
  production campaigns.jsonl UNCHANGED
    before 00b6f103bbdb469f25a7977665e4e08339f30f2b827d9e2a3c82be560d4c5931
    after  00b6f103bbdb469f25a7977665e4e08339f30f2b827d9e2a3c82be560d4c5931

== WHAT THE CLI PRINTED (first 30 lines) ==
  FactoryRefused: the sequence-level gate refuses 1 of 1 lead(s) in this push, and it runs before any provider write so nothing has reached the estate:
  ogpartner-dk/jacob-faertz
    sequence gate: FAILED on 1 check(s)
      FAIL  step_objectives            em2      pursues none of the offer's step objectives: rung 2 is 'quote versus burn' and this step shares no word with it
      warn  no_repetition              subjects this cadence opens 1 thread(s), so there are 1 thread subject(s) to compare and duplicate thread subjects could NOT be checked
      warn  step_objectives            em1      no step carries rung 1, whose objective is 'margin visibility', so that objective was NOT checked. A step that rendered to nothing is dropped before this check sees it
      warn  step_objectives            em3      no step carries rung 3, whose objective is 'resource decisions that move margin', so that objective was NOT checked. A step that rendered to nothing is dropped before this check sees it
      warn  step_objectives            em4      no step carries rung 4, whose objective is 'Report Intelligence as mechanism, only if it strengthens the angle', so that objective was NOT checked. A step that rendered to nothing is dropped before this check sees it
      warn  step_objectives            em5      no step carries rung 5, whose objective is 'reframe and close', so that objective was NOT checked. A step that rendered to nothing is dropped before this check sees it
      warn  step_objectives            sequence lexical overlap only: a step carrying its rung's vocabulary while arguing something else passes this check. Semantic objective-following is NOT verified here
      warn  capability_matches         batch    batch_capabilities not supplied: whether stage D is choosing or defaulting was NOT checked
  REGENERATE the affected steps; the failure names which lead and which step is wrong.

$ py -3 -m unittest tests.test_render_preview
exit=0
.............................
----------------------------------------------------------------------
Ran 29 tests in 0.010s

OK

$ py -3 -m unittest tests.test_task560_ps_reaches_the_person
exit=0
..............
----------------------------------------------------------------------
Ran 14 tests in 0.003s

OK

$ py -3 -m unittest tests.test_task907_ps_producer_hop
exit=0
..........
----------------------------------------------------------------------
Ran 10 tests in 0.026s

OK

$ py -3 -m unittest tests.test_task904_opt_out
exit=0
..................
----------------------------------------------------------------------
Ran 18 tests in 0.008s

OK

$ py -3 -m unittest tests.test_the_research_pack_has_one_shape
exit=0
...................
----------------------------------------------------------------------
Ran 19 tests in 0.259s

OK

$ py -3 -m unittest tests.test_approve
exit=0
...........................................
----------------------------------------------------------------------
Ran 43 tests in 1.709s

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
Ran 51 tests in 0.484s

OK

$ py -3 -c "import sys; from scripts.render_preview import _fixture_rec_email as F, _fixture_config_email as C, _build_email_plan as B; from src import optout as O; p=B(C(),[F()]); bad=[(i,v['name'],v['value'].count(O.OPT_OUT_LINE)) for i,L in enumerate(p['leads']) for v in L['variables'] if v['name'].startswith('body_') and v['value'].count(O.OPT_OUT_LINE)!=1]; sys.exit('WRONG opt-out count: %r' % (bad,)) if bad else print('OK: exactly one opt-out line in every body on every lead')"
exit=0
OK: exactly one opt-out line in every body on every lead

$ py -3 -c "import sys; from scripts.render_preview import _fixture_rec_email as F, _fixture_config_email as C, _build_email_plan as B; p=B(C(),[F()]); b=[v['value'] for v in p['leads'][0]['variables'] if v['name']=='body_1']; sys.exit('em1 P.S. count=%r' % [x.count('P.S.') for x in b]) if [x for x in b if x.count('P.S.')!=1] else print('OK: em1 carries exactly one P.S.')"
exit=0
OK: em1 carries exactly one P.S.
```

## GLM response

**1. Production caller — YES.** The caller is the CLI itself: `python -m src.bisonfactory productive-email-batch1-kresimir`. Measured phase: `bisonfactory._plan` wrapper 1 / profiler 1, and inside that call tree `sequenceplan.for_campaign` 1, `sequenceplan.derive_bison_payload` 1 (the projection), `sequenceplan.approval_hash` 1. `bisonfactory._approved_copy` 0 — the old projection source is off the production path. This is the real module entrypoint on copied production input, not a test, not `work/`.

**2. Can the check fail — YES, not vacuous.** Concrete failing inputs:
- Edit one word of a plan body after approval (e.g. `body_2` of em2 in the ogpartner-dk plan). If the projection were still sourced from `_approved_copy`, both `approval_hash` and `derive_bison_payload` output stay unchanged → `test_mutating_body_changes_approval_hash` and `test_mutating_body_changes_projection` fail.
- Regress `_plan` to call `_approved_copy`: wrapper count flips to ≥1 in the measured phase and `test_approved_copy_not_called_by_plan` fails. The probe discriminates bug from fix.

**3. Arithmetic — reconciles.**
- Diffstat: 75 (doc) + 228 (tests) + 106 ins/5 del (`bisonfactory.py`) = 409 ins + 5 del; the `bisonfactory.py` row 111 = 106+5 ✓.
- Tests: 3+2+3+2+4+2 = 16 = "Ran 16 tests" ✓.
- Five answers vs table: `generate.*` 0/0 → generator NOT ENTERED ✓; `sequenceplan.new` 0/0 → NOT CREATED ✓; `derive_bison_payload` 1/1 → projection ENTERED ✓; `approval_hash` 1/1 ✓; provider writes 0 = measured provider calls 0, non-loopback connects 0 ✓.
- Queue sha256 identical before/after (dd984f8a…), campaigns.jsonl identical (00b6f103…) → no state mutation ✓.

**Defeat hunt:**
- CLI exit 1 (`FactoryRefused`, em2 fails step_objectives vs rung 2 "quote versus burn"): a data-level gate refusal on the one constructed lead, running before any provider write; projection and hash were still entered pre-gate. 0 provider calls, 0 credits — no measurable cost. NO FINDING.
- "forbidden work/ writes = 1": phase=CONTROL — the `ProviderWriteRefused` guard's own log of the deliberately triggered control write, in the verify worktree. Not the measured phase. NO FINDING.
- Positive control 1 shows `derive_bison_sequence` 0/0 direct (absent from direct-call returns), so a measured NOT ENTERED on it would be UNKNOWN — but measured was 1/1. No impact.
- Residual, not a defeat: the gate refused 1/1 leads, so the probe never observed the projection consumed by `generate.run` downstream; the claim is verified at derivation time only. Observing send-path consumption requires a lead that passes the sequence gate.

**Changed files:** all three answer to TASK-905 — the review doc (task ID in filename), the fix in `src/bisonfactory.py`, and `tests/test_task905_projection_from_plan.py`. No scratch files (`*.txt`/`*.err`/`*.out`) at repo root in the changed list.

VERDICT: PASS
