# GLM branch verification: TASK-968

Branch: `task-word-contract-enforced`
Date: 2026-10-02T23:47:24.282734+00:00
Model: glm-5.3
Duration: 168.345s
Usage: {'prompt_tokens': 14706, 'completion_tokens': 12957, 'total_tokens': 27663, 'reasoning_tokens': 11768, 'cached_tokens': 14656}

Parts: 3 (part 1=PASS, part 2=PASS, part 3=FAIL)

## Verdict: FAIL

**part 3 of 3: the branch's controlling test file (53 tests) has no run in the supplied evidence and the doc itself declares the last full-suite green superseded and a fresh pre-merge run required; additionally, none of the four keyless production lint doors the contract exists to gate is called by any test on the branch.**

## GLM spend

This call: 3 ledger rows, 83065 micro-USD

## Changed files (14)

- `docs/qwen-tasks/REVIEW/TASK-968-the-word-contract-is-enforced-by-lint.md`
- `prompts/draft.md`
- `src/copystages.py`
- `src/generate.py`
- `src/lint.py`
- `src/skills/cold_email_writing.py`
- `tests/base.py`
- `tests/test_a_thread_reply_has_its_own_word_range.py`
- `tests/test_campaign_ready_funnel.py`
- `tests/test_generate.py`
- `tests/test_ladder_propagation.py`
- `tests/test_task910_writer_contract.py`
- `tests/test_task913_writer_contract_five_plus_five.py`
- `tests/test_word_contract_enforced.py`

## Diff stat

```
 ...SK-968-the-word-contract-is-enforced-by-lint.md | 135 +++++
 prompts/draft.md                                   |   4 +-
 src/copystages.py                                  |  81 +--
 src/generate.py                                    |  55 +-
 src/lint.py                                        | 352 ++++++-----
 src/skills/cold_email_writing.py                   |  78 ++-
 tests/base.py                                      |  28 +-
 .../test_a_thread_reply_has_its_own_word_range.py  | 295 ---------
 tests/test_campaign_ready_funnel.py                |  21 +-
 tests/test_generate.py                             |  52 +-
 tests/test_ladder_propagation.py                   |  23 +-
 tests/test_task910_writer_contract.py              |  24 +-
 .../test_task913_writer_contract_five_plus_five.py |  20 +-
 tests/test_word_contract_enforced.py               | 664 +++++++++++++++++++++
 14 files changed, 1254 insertions(+), 578 deletions(-)

```

## Acceptance output

```
$ python -c "import sys; sys.path.insert(0,'.'); from src.skills import cold_email_writing as w; c=w.WORD_CONTRACT; assert set(c)=={'em1','em2','em3','em4','em5'}, c; assert all(len(v)==3 and v[0]<=v[1]<=v[2] for v in c.values()), c; assert c['em1'][0]==60 and c['em3'][0]==60 and c['em2'][0]==45, c; print('OK the contract is data and ordered:', c)"
exit=0
OK the contract is data and ordered: {'em1': (60, 75, 90), 'em2': (45, 60, 90), 'em3': (60, 75, 90), 'em4': (45, 60, 90), 'em5': (45, 65, 90)}

$ python -c "import sys; sys.path.insert(0,'.'); from src import lint; KEY='k'; rec=lambda sk,n: {'id':'r','domain':'example.test','contacts':[{'key':KEY,'email':'a@example.test','cadence':{sk:{'channel':'email','generated':True,'subject':'a subject that is fine','body':' '.join(['word']*n)}}}]}; r=rec('em2',41); step=r['contacts'][0]['cadence']['em2']; bad=lint.check_step(r, KEY, step, step_key='em2'); good=lint.check_step(rec('em2',61), KEY, rec('em2',61)['contacts'][0]['cadence']['em2'], step_key='em2'); words_bad=[f for f in (bad or []) if 'word' in str(f).lower()]; assert words_bad, 'an em2 of 41 words was not refused on word count: '+str(bad); words_good=[f for f in (good or []) if 'word' in str(f).lower()]; assert not words_good, 'a 61-word em2 was refused for its length, so the rule refuses everything: '+str(words_good); print('OK 41 refused on words, 61 not:', [str(f)[:60] for f in words_bad][:1])"
exit=0
OK 41 refused on words, 61 not: ['em2_body_41_words_under_contract_45_to_90']

$ python -c "import sys; sys.path.insert(0,'.'); from src.skills import cold_email_writing as w; room={k:(v[2]-v[0]+1) for k,v in w.WORD_CONTRACT.items()}; assert min(room.values())>=30, room; print('OK every step has at least thirty allowed lengths:', room)"
exit=0
OK every step has at least thirty allowed lengths: {'em1': 31, 'em2': 46, 'em3': 31, 'em4': 46, 'em5': 46}
```

## GLM response

### Part 1 — PASS



## 1. Production caller

**YES — the bridge is called, with one test-only exception.** The bridge is the import `from .skills import cold_email_writing as writercontract` (src/lint.py, top hunk). It is exercised in production code at two sites: `check`'s contract hunk (`bounds = writercontract.word_range(contract_step)`) and `explain_contract` (`writercontract.word_target(step)`). `check` is reached by `generate._step_refusals` (src/generate.py hunk, passes `step_key` explicitly), `check_record` (passes `step_key=day`), and the seven other doors the docstring lists via `step_key_of` recovery. `_selected_offer` is removed *with* its only caller in the same hunk — no orphan.

Exception: **`lint.STEP_WORD_CONTRACT` has no reader in this part.** `check` reads `writercontract.word_range` directly, never the alias. It exists, as far as part 1 shows, only for part 3's `TestTheContractNeverLoosensTheOldBounds`. Constant, not a gate — flag, not a defeat.

## 2. Can the acceptance check fail?

**Yes — not vacuous.** Command 2 constructs records and executes `check_step → check → writercontract.word_range`. Delete the contract hunk in `check`, or set em2's floor to 40 in part 2's `WORD_CONTRACT`, and assert 1 fires ("an em2 of 41 words was not refused"); raise em2's floor above 61 and assert 2 fires. It distinguishes 41 from 61 through live code.

Two coverage gaps it does **not** catch: (a) it never probes the ceiling — a 95-word em2, refused by this code as `em2_body_95_words_over_contract_45_to_90`, is untested here (ceiling coverage lives only in part 3); (b) it passes `step_key='em2'` explicitly, so the **recovery** path (`step_key=None`) that approve/eligibility/executionguard/campaigns/cadence/heyreachfactory/benchmark all depend on is untested by acceptance.

## 3. Do the numbers reconcile?

**Yes, within the diff.** Contract tuples match every prose site: copystages sequence block, ladder block, HARD RULES, the OUTPUT JSON line, refusal item 4 (em1/em3 60–90 aim 75; em2/em4 45–90 aim 60; em5 45–90 aim 65), and draft.md's 40–180 vs `MIN_WORDS`/`MAX_WORDS`. Room arithmetic: 90−60+1=31, 90−45+1=46 — matches the printed dict.

**But the result block contains zero production-scale evidence for the change.** The funnel is all zeros (`states {}`, no model configured), while the branch's justification is estate data it *deletes* with the old comment: 1323 stored em2 bodies, median 87 words. Recompute the collision: the new ceiling is 90 and the estate median is 87 — three words of headroom. On re-lint at any door that calls `check`, every stored em2 over 90 (with median 87, plausibly 40%+ of 1323, i.e. hundreds of bodies), every em1/em3/em5 body of 91–180 (legal yesterday under `MAX_WORDS=180`), and every 40–59-word em1/em3 (legal under floor 40) is newly refused. Operator-ordered, but unmeasured anywhere in this branch's output — the funnel that would have measured it ran on an empty queue.

## Findings

**F1 — `step_key_of`'s body fallback can return a uniquely-matching WRONG key (src/lint.py, `body = (step or {}).get("body")` hunk).** Input: a contact whose stored cadence holds only em2 with body B (52 words); a caller in the no-`step_key` doors lints an em1 candidate whose body is byte-identical B. Recovery returns `em2`, the em1 is judged 45–90, and a **52-word em1 passes a contract whose floor is 60**. Mirror: a 55-word em2 candidate colliding with a stored em1 is refused `em1_body_55_words_under_contract_60_to_90` — a retry instruction naming the wrong step and the wrong target (75 for a step whose target is 60), the exact wrong-number-to-writer defect the removed EXPLAIN comment documents. Precondition — duplicate bodies across steps — is the on-record phase7 failure mode; the ambiguity guard fires only at ≥2 matches and cannot see a unique wrong one.

**F2 — the estate cost above:** median 87 vs ceiling 90, quantified from the branch's own deleted numbers, with no re-measurement in the result block.

**F3 (minor) —** `named = step_key or step.get("step_key") or step.get("key")`: a step dict carrying a non-cadence `key` field silently disables contract recovery for that step (falls back to 40..180). Whether any builder writes `key` on steps is settled in part 2.

## Also-checked

- **Files vs task:** all four part-1 files answer to TASK-968 (draft.md wording; copystages prose; generate removes the reply plumbing with its only caller; lint enforces). tests/base.py and the six changed test files: part 2. The deleted 295-line `test_a_thread_reply_has_its_own_word_range.py` is consistent with the claimed abolition; the abolition itself is evidenced only in part 3's review doc.
- **Scratch files:** none — no *.txt/*.err/*.out in the 14-file list (the diff cannot show untracked root files, but nothing listed).

VERDICT: PASS

### Part 2 — PASS



## 1. Production caller for the new code?

**Split verdict, and one possible dead bridge.**

- `words_rule()` and `_words_phrase()` — called in-file at construction of `SKILL` (`validation` tuple and `output_schema` in `src/skills/cold_email_writing.py`). Caller exists.
- `WORD_CONTRACT` — consumed by `src/lint.py` at runtime: acceptance check 2's failure string `em2_body_41_words_under_contract_45_to_90` embeds em2's `(45, _, 90)`, which can only come from the mapping. Caller exists, **in part 1**.
- `WORD_CONTRACT` → `src/copystages.WRITER_SYSTEM` — asserted by `tests/test_task913_writer_contract_five_plus_five.py:421-427` (`slot` built from `WORD_CONTRACT["em2"]` must appear verbatim in `WRITER_SYSTEM`). Bridge holds, **definition in part 1**.
- **`word_range()` and `word_target()` (cold_email_writing.py, the two helper defs): no caller anywhere in part 2.** Acceptance check 2 calls `lint.check_step`, not `w.word_range`. If part 1's `lint.py`/`copystages.py` read `WORD_CONTRACT` directly instead of importing these helpers, they are dead bridges — **PART 1 settles it.**

## 2. Can the acceptance check fail?

Not vacuous — inputs exist:
- Check 2 fails if lint enforces nothing (em2@41 yields no word failure → `assert words_bad` fires), or if lint mistakes the *target* for the *ceiling* (em2@61 refused → second assert fires).
- Check 3 fails at e.g. `em1: (60, 75, 88)` → 29 lengths.

**Blind spot worth naming:** check 2 cannot distinguish em2@45-90 from em2@60-90 (em1's range). 41 is under both floors; 61 is inside both ranges. The discriminating input — em2 at 46-59 words, legal under the contract, illegal under the opener range — is never exercised. Lint could apply em1's floor to every reply and all three checks still pass.

## 3. Do the numbers reconcile?

Recomputed from the diff by whitespace split:

| Claim | Recomputed | |
|---|---|---|
| Contract tuples in output | match source dict exactly | ✓ |
| room 31/46/46/46/31 (hi−lo+1) | ✓ | ✓ |
| base.py "em1 75, em2 61, em3 72" | 75 / 61 / 72 | ✓ |
| task910 "em1 75, em2 61, em3 72" | identical text, "Jane" | ✓ |
| ladder `_good_body` "81 words" | 81 | ✓ |
| HARBOURLINE em3 "76 words" | 76 | ✓ |
| MERIDIAN em1/em2/em3 (no claims made) | 75 / 80 / 83 — all in contract | ✓ |
| test_generate `GOOD_BODY` "**86** WORDS" | **87** by split | off by one |
| Skill docstring canary "under contract by **19** and 7" | em2@41 is under its **floor (45) by 4**; 19 is the deficit vs the *target* 60, while the 7 for em3@53 is vs its *floor* 60 — two different bases in one sentence | sloppy |

The 86-vs-87 is one token ("17"); possibly `lint.countable_words` excludes bare numerals — counter lives in **part 1**. Neither 86 nor 87 crosses the 60-90 bounds, so no gate consequence. The "19" is docstring arithmetic only.

The funnel block (all zeros, `states {}`) reconciles trivially — empty queue, and `REFUSED: ... no model is configured` means **no generation ever ran**; the branch's "Measured 2026-10-02" canary claims (approved em2 of 41, em3 of 53) are not reproducible from any part.

## Also checked

- **File ownership:** every changed file answers to TASK-968, including the fixture-only edits (`test_campaign_ready_funnel.py`, `test_ladder_propagation.py` — bodies lengthened to meet the contract lint now enforces).
- **Scratch files:** none in the changed list.
- **The deletion:** `tests/test_a_thread_reply_has_its_own_word_range.py` (295 lines) is the *old* 2026-10-01 ruling's file; supersession is the task, so deletion is legitimate **only if** part 3's 664-line `test_word_contract_enforced.py` recreates its two live protections: (a) agreement across the three-argument callers (`approve`, `eligibility`, `executionguard` — the deleted file names them as this repo's recurring stall), and (b) `step_key_of` identity/equality resolution. Acceptance check 2 exercises **only** the explicit `step_key=` path. If part 3 skips the no-key path and part 1 dropped key recovery, every stored em2 of 45-59 words passes generation and fails `approve` — the converge-then-stall failure at whatever the queue's scale is. **PART 3 and PART 1 settle this; part 2 alone cannot.**

NO FINDING constructible from part 2 alone — the one arithmetic slip (86 vs 87) and the one basis error (19 vs 4) are comment-level with no gate consequence.

VERDICT: PASS

### Part 3 — FAIL

the branch's controlling test file (53 tests) has no run in the supplied evidence and the doc itself declares the last full-suite green superseded and a fresh pre-merge run required; additionally, none of the four keyless production lint doors the contract exists to gate is called by any test on the branch.

## 1. Production caller

Part 3 adds **zero production code** — one test file and one doc. The bridges (`explain_contract`, `step_key_of`, `writer.word_range`, `writer.word_target`, `lint.STEP_WORD_CONTRACT`) are defined in parts 1–2, and their production callers are claimed in the doc as `lint.explain` (src/lint.py:405) and `src/lint.py:735` — **verifiable only in part 1**. Name part 1. One residual candidate for NO CALLER visible from here: the doc cites a production caller for `word_range` (lint.py:735) but none for `word_target`; its only callers I can see are tests (`TestOneAuthority`). Part 1 (does lint.py/copystages.py call `word_target` when composing the "~65 words" explanation?) settles it.

Sharper, and internal to part 3: the file's own docstrings name the four doors the contract must reach — "`cadence.status_for`, `eligibility.decide`, `approve` and `executionguard`, none of which passes a step key" (`TestTheKeyIsRecovered` docstring) — and **not one of the 53 tests calls any of them, or calls `lint.check` without a key**. `test_a_caller_with_no_key_still_gets_the_gate` passes `KEY` on every call. If `approve` hands `check_step` a step whose key `step_key_of` can't recover from its record shape, it silently falls back to the 40-word floor — the exact regression this task exists to end — and this file stays green. That reach is asserted in prose and tested nowhere on this branch (part 2's test_generate covers only generate's door).

## 2. Can the acceptance fail?

Yes, all three are falsifiable — name the inputs:
- **Cmd 1**: fails under the operator's ruled TASK-964 contract, em1 `(90,120,140)` → `c['em1'][0]==60` is false. This is a live trap: the doc mandates changing `WORD_CONTRACT` in TASK-964's commit but cmd 1 still hardcodes 60 and the doc never says the acceptance must move with it.
- **Cmd 2**: fails on master (40-word floor, no word code for a 41-word em2) — its stated negative control.
- **Cmd 3**: fails on any sub-31 range, e.g. em2 `(58,60,62)`. But it **cannot fail on the defect it advertises**: it reads only `WORD_CONTRACT`, and the abolished collapse came from the *intersection* of two authorities. Reintroduce a 50–60 reply range beside em2's 45–90 and the legal set is 11 lengths — below the 30 the doc says must "fail loudly" — while cmd 3 and `TestEveryRangeHasRoom` stay green.

## 3. Do the numbers reconcile?

Recomputed and reconcile: canary deltas (60−41=19, 60−53=7, 45−41=4) at lines 13–17; refusal margins 4/7/4; `191 = 100+1+90`; `141 = 180−40+1`; "10 words over" = 100−90; room {31,46,31,46,46} = high−low+1, matching cmd 3's printed output; and the doc's "53/53 green" equals my count of **53 test methods** in the new file.

Two numbers do **not** reconcile with any evidence:
- The supplied "test results" block contains **zero tests from `tests/test_word_contract_enforced.py`** (it truncates mid-`test_generate`; ladder_propagation, task910, task913, word_contract all come after). The doc itself declares the prior 231/0/0 "SUPERSEDED" and says "this branch needs a fresh full run before it merges" — and no such run is in the evidence.
- The funnel block is all zeros with generate REFUSED (no model), so the run verified no data.

**Unmeasured blast radius at a stated scale**: the branch measured 5 canary bodies (3 of 5 now refused; the operator confirmed em2@41 only — em3@53 and em5@41 refusals rest on arithmetic, not confirmation), while its own docstring counts **4,082 generated bodies**, and the passing `test_a_stored_draft_that_fails_lint_is_planned_again` proves every newly-refused stored draft re-enters generation planning — model spend the branch's own "measured not predicted" standard was never applied to.

## Also

- Part-3 files answer to the task; the deleted `test_a_thread_reply_has_its_own_word_range.py` is justified (its live parts carried into `TestWhatCounts`/`TestTheKeyIsRecovered`). The doc discloses post-hoc authorship and the TASK-943 id collision. The em1 ceiling-90 vs operator-target-120 collision is disclosed with a same-commit condition TASK-964 must honor.
- No scratch files at repo root in the changed-file list.

VERDICT: FAIL - the branch's controlling test file (53 tests) has no run in the supplied evidence and the doc itself declares the last full-suite green superseded and a fresh pre-merge run required; additionally, none of the four keyless production lint doors the contract exists to gate is called by any test on the branch.
