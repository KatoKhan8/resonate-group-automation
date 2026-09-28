# GLM branch verification: TASK-908

Branch: `qwen-worker-10-r14`
Date: 2026-09-28T19:47:47.149380+00:00
Model: glm-5.3
Duration: 116.049s
Usage: {'prompt_tokens': 3346, 'completion_tokens': 9728, 'total_tokens': 13074, 'reasoning_tokens': 8785, 'cached_tokens': 128}

## Verdict: PASS

## GLM spend

This call: 0 ledger rows, 0 micro-USD

## Changed files (3)

- `docs/qwen-tasks/REVIEW/TASK-908-the-approval-hash-must-cover-the-sender.md`
- `src/sequenceplan.py`
- `tests/test_task908_approval_hash_covers_sender.py`

## Diff stat

```
 ...-908-the-approval-hash-must-cover-the-sender.md |  87 ++++++++++++++++++
 src/sequenceplan.py                                |   2 +
 tests/test_task908_approval_hash_covers_sender.py  | 102 +++++++++++++++++++++
 3 files changed, 191 insertions(+)

```

## Acceptance output

```
$ py -3 -m unittest tests.test_render_preview
exit=0
.............................
----------------------------------------------------------------------
Ran 29 tests in 0.059s

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
Ran 10 tests in 0.023s

OK

$ py -3 -m unittest tests.test_task904_opt_out
exit=0
..................
----------------------------------------------------------------------
Ran 18 tests in 0.008s

OK

$ py -3 -m unittest tests.test_task905_projection_from_plan
exit=0
................
----------------------------------------------------------------------
Ran 16 tests in 0.045s

OK

$ py -3 -m unittest tests.test_task906_signature_composed_into_copy
exit=0
....................................
----------------------------------------------------------------------
Ran 36 tests in 0.007s

OK

$ py -3 -m unittest tests.test_approve
exit=0
...........................................
----------------------------------------------------------------------
Ran 43 tests in 1.789s

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
Ran 51 tests in 0.761s

OK

$ py -3 -c "import sys, copy; from src import sequenceplan as S; p={'client':'c','account':'a','strategy':{'strategy_id':'s'},'contacts':[{'email':'x@y.z','sequences':{'em1':'b','ps_em1':'P.S. one'},'subjects':{'em1':'s1'}}]}; a=copy.deepcopy(p); a['contacts'][0]['sender']='anna@productive.io'; b=copy.deepcopy(p); b['contacts'][0]['sender']='other@productive.io'; ha,hb=S.approval_hash(a),S.approval_hash(b); n=copy.deepcopy(p); h1,h2=S.approval_hash(n),S.approval_hash(copy.deepcopy(n)); sys.exit('sender not covered: %s == %s'%(ha,hb)) if ha==hb else (sys.exit('unstable: %s != %s'%(h1,h2)) if h1!=h2 else print('OK: sender covered and hash stable'))"
exit=0
OK: sender covered and hash stable

$ py -3 -c "import shutil,os; src=r'C:/Users/Zvonimir/Desktop/resonate-group-automation/work'; dst=os.path.join(os.environ.get('TEMP','.'),'probe-work-908'); shutil.rmtree(dst,ignore_errors=True); shutil.copytree(src,dst); print(dst)"
exit=0
C:\Users\Zvonimir\AppData\Local\Temp\probe-work-908

$ py -3 scripts/runtime_approval_hash_probe.py --state "%TEMP%/probe-work-908" --mode project --campaign productive-email-batch1-kresimir --construct-from productive-email-batch1-kresimir --construct-limit 1
exit=0
== CONSTRUCTED INPUT (in the COPY only) ==
  {"cloned_from": "productive-email-batch1-kresimir", "campaign_id": "productive-email-batch1-kresimir", "record_ids": ["ogpartner-dk"], "cadence_steps": ["li1", "em1", "li2", "em2", "li3", "em3", "li4", "em4", "li5", "em5"]}

== SETUP ==
  state (COPY)            C:\Users\Zvonimir\AppData\Local\Temp\probe-work-908
  QUEUE env               C:\Users\Zvonimir\AppData\Local\Temp\probe-work-908\queue.jsonl
  copy queue sha256       dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
  model stub              http://127.0.0.1:51271  (loopback, not a real provider)
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
  direct-call returns      {"derive_preview_data": "dict", "derive_bison_payload": "dict", "derive_heyreach_payload": "dict", "approval_hash": "9ae51e6bfe32ad50"}

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
  forbidden work/ writes   1  [{"phase": "CONTROL", "path": "C:\\Users\\Zvonimir\\Desktop\\resonate-group-automation\\.qwen\\worktrees\\verify-111652-accept\\work\\provider-write-refusals.jsonl", "mode": "a"}]
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
```

## GLM response

**1. Production caller — YES, named.**
The only production change is the 2 added lines in `src/sequenceplan.py`, which live inside the hashed-payload builder that `approval_hash` uses. The measured phase ran the real CLI (`python -m src.bisonfactory productive-email-batch1-kresimir`) on copied production state and recorded `sequenceplan.approval_hash` ENTERED (wrapper 1 / profiler 1), reached via `bisonfactory._plan` (1/1) → `sequenceplan.for_campaign` (1/1), with `derive_bison_sequence` (1/1) in the chain. Positive control 1 proves both instruments record on direct calls (approval_hash 4/4), so the 1/1 is measured, not unknown. Caveat: the run refused at the sequence gate before `bisonfactory._approved_copy` (0/0), so the *consumption* side of the hash is unmeasured — only computation is runtime-proven.

**2. Can the acceptance check fail — YES, it is falsifiable.**
Revert the 2 lines (parent commit) and the acceptance one-liner exits 1 with `sender not covered: <ha> == <hb>`; the stability clause likewise fails on any nondeterministic serialization. Given the change as shipped, I could not construct a failing input: contact-level sender (one-liner + `test_sender_change_moves_hash_per_contact`), plan-level sender (`test_plan_level_sender_moves_hash`), senderless stability (`test_two_senderless_plans_hash_identically`, `test_no_sender_still_hashes`) all pass. Defeats attempted and rejected: (a) sender at a third location — no evidence production populates one, so no concrete input; (b) collision via the 16-hex (64-bit) truncation — birthday bound needs ~2^32 plans for 50%; at 10^6 plans P ≈ 3×10⁻⁸, unmeasurable. Not vacuous.

**3. Numbers reconcile.**
- 87 + 2 + 102 = 191 = "3 files changed, 191 insertions(+)" ✓
- 7 test names listed = "Ran 7 tests ... OK" ✓
- Acceptance suites: 29+14+10+18+16+36+43+51 = 217, all OK ✓
- Probe internal consistency: 1 `for_campaign` → 1 `approval_hash`; 0 provider calls ↔ 0 non-loopback connects; copy queue sha before==after (`dd984f8a…`); production `queue.jsonl` and `campaigns.jsonl` shas unchanged before/after ✓. The constructed input touched the COPY's campaign state (CLI processed `ogpartner-dk`), while production shas held — consistent.
- One number flagged: "forbidden work/ writes 1" — phase=CONTROL, path is the disposable verification worktree's own `work/provider-write-refusals.jsonl` (the guard logging the deliberate control write). Production state untouched (shas above). Cost: one log line in a worktree slated for deletion. Probe hygiene, not a branch defect.

**Changed files vs. task:** all three answer to TASK-908 — the review doc, the 2-line production change, the test suite. No fourth file.

**Scratch files:** none. Diff contains exactly 3 files; probe artifacts went to `%TEMP%\probe-work-908` plus the one CONTROL-phase append noted above. No `*.txt`/`*.err`/`*.out` at repo root.

**Non-blocking notes:**
- Measured CLI exit 1 is a pre-existing sequence-gate refusal (`em2` shares no vocabulary with rung 2, lead `ogpartner-dk/jacob-faertz`) — upstream of this change, fired before any provider write, and not caused by hash coverage. It is the guard working.
- Because of that refusal, sender-coverage's effect on approval *outcomes* rests on the unit tests, not the runtime probe. The probe's five answers only claim the hash was entered, which it measured.
- The diff supplied is a summary; the actual 2 lines of `src/sequenceplan.py` were not shown. Behavior was verified through the runtime probe and 7 tests rather than by reading them — acceptable here given dual-instrument measurement with positive controls.

VERDICT: PASS
