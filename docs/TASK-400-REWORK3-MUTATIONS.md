# TASK-400 REWORK 3 — mutation record

Branch `task400-rework3`, off `5c356b7d` (rework 2). Run on 2026-09-27.

**A red test is not proof by itself.** For each of the operator's four approved
behaviours the behaviour was BROKEN in production, the intended test was
confirmed to fail, the failure message was read to confirm it was the intended
failure, and the other tests were read to confirm a different guard had not
fired first. Every mutation was reverted and `git diff src/` confirmed
byte-identical to the commit before the next one was applied.

Acceptance check between every mutation:
`py -3 -m unittest tests.test_generate` and
`py -3 -m unittest tests.test_task400_rework3`.

---

## MUTATION 1 — behaviour 1 (copylint retry stays)

`src/generate_campaign.py`, `copylint_failures()` returns `[]` — the batch-lint
report is computed and read by nothing, which is what it did before this task.

**Intended test:** `tests.test_task400_rework3.TestBehaviour1CopylintRetryStays
.test_a_draft_copylint_refuses_is_regenerated_and_never_stored`

**Result:** FAILED, intended reason —
`AssertionError: 1 != 2 : the writer was not asked again, so a draft copylint
refused went straight through`.

**Did another guard fire first?** No, and this was designed to be provable:
`test_the_isolation_holds_before_anything_else_is_claimed` PASSED under the
mutation, and it asserts that `lint.check` returns `[]` for the same body while
`copylint.check_batch` refuses it. So the only gate that can cause the
regeneration is the batch lint. `test_the_rule_was_not_widened_to_let_it_through`
also passed, so the failure is in the consumer and not in the rule.

**Collateral (consistent, not masking):** the two behaviour-2 tests also failed,
because they drive the same buzzword fixture.

---

## MUTATION 2 — behaviour 2 (a draft that failed a gate is never stored)

`src/generate_campaign.py`, the writer loop's `else` branch replaced with `pass`
— the attempt budget runs out and the last refused draft is kept.

**Intended test:** `tests.test_task400_rework3
.TestBehaviour2NeverStoredAsASendCandidate
.test_a_set_that_never_passes_leaves_no_row_anywhere`

**Result:** FAILED, intended reason — `AssertionError: {'day1': {'channel':
'email', ...}} != {}`: a row for the refused copy is on the record.

**Did another guard fire first?** No. Exactly ONE test failed.
`test_the_budget_is_bounded_rather_than_a_loop` still passed, so the three
attempts still happened — the mutation changed only what is done with the
refusal, which is the behaviour under test.

---

## MUTATION 3 — behaviour 3 (a model error holds the record)

`src/generate_campaign.py`, `except llm.ModelError: raise` restored to
`result["held"] = "model error: ..."`, which is what rework 2 shipped.

**Intended tests:** both of
`tests.test_task400_rework3.TestBehaviour3AModelErrorHoldsTheRecord`

**Result:** both FAILED, intended reasons —

- `test_a_writer_failure_holds_the_record_and_stores_no_copy`:
  `AssertionError: 'verified' != 'held' : a model failure passed silently with
  no copy, which is fail-open`.
- `test_a_fault_of_ours_stops_the_run_rather_than_blaming_the_record`:
  `AssertionError: ModelUnavailable not raised`.

**Did another guard fire first?** No. In both cases the FIRST assertion in the
test is the one that failed, and the remaining eleven tests passed.

**Noted while doing this:** `tests.test_generate
.TestDryRunAndDefaults.test_a_model_failure_holds_the_record_rather_than_guessing`
is NOT sensitive to this mutation, because its `Failing` model raises on the
strategy call, which happens outside `_process_contact`'s `try`. That test
therefore proves the `generate_record` half of behaviour 3 and not the
`_process_contact` half — which is why the two tests above exist.

---

## MUTATION 4 — behaviour 4 (approved and sent are never overwritten)

`src/generate.py`, `_protected_reason()` returns `None` unconditionally.

**Intended tests:** `tests.test_task400_rework3
.TestBehaviour4ApprovedAndSentAreNeverOverwritten
.test_an_approved_draft_is_never_overwritten` and
`.test_a_sent_draft_is_never_overwritten`

**Result:** both FAILED, intended reasons — the stored body became the
regenerated copy: `APPROVED copy was overwritten, which invalidates the approval
hash the operator's yes is bound to`, and `copy that has already been SENT was
rewritten`.

**Did another guard fire first?** No. `test_an_unapproved_draft_is_regenerated`
and `test_partial_regeneration_still_refuses_loudly_by_default` both still
passed, so the mutation removed exactly the approved/sent protection and left
the regeneration path and the partial-regeneration refusal intact.

---

## MUTATION 5 — behaviour 2, the second door

`src/generate.py`, `_adapt_plan_to_cadence`'s `if refusals:` replaced with
`if False:` — a step that fails a per-draft gate is written anyway.

**Why a fifth:** there are two doors, and the writer's retry makes the store
door unreachable in the wired path. That is exactly the condition under which a
guard rots unnoticed, so it is driven directly rather than through `run()`.

**Intended test:** `tests.test_task400_rework3
.TestBehaviour2NeverStoredAsASendCandidate.test_the_store_door_refuses_on_its_own`

**Result:** FAILED, intended reason — `AssertionError: Lists differ:
[('rowan-blake', 'day1'), ('rowan-blake', 'day15')] != []`.

**Did another guard fire first?** No. Exactly one test failed.

---

## What the mutations did NOT prove

- Nothing here exercises a real provider or a real model. Provider writes are
  zero by construction: the campaign path contains no provider call, and the
  four provider refusals are asserted separately in
  `tests/test_task400_rework2.py::TestBothProvidersRefuseAStampedRecord`, which
  fails the test if the module's `request` seam is reached.
- `_protected_reason` is proven for an APPROVED step and for a step whose status
  is `stepstate.PUSHED`. `CONFIRMED` and `CANCELLED` are terminal by the same
  `stepstate.is_terminal` call and are not separately driven.
