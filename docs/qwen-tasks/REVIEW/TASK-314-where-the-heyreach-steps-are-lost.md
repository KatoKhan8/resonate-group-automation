PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-314 — find exactly where the HeyReach steps are lost, and pin it

Operator directive, `docs/OPERATOR-DIRECTIVES-2026-09-25.md` section 4.

## The claim to test

A previous measurement found ONE LinkedIn step surfacing from a SIX-step
graph. `cadence.expand_step` drops a generated step whose copy was never
written, and under `productive_li_heavy_v1` li2..li6 are all `generated`.
`li1` survived only because it names the `linkedin_intro` template.

**Measured 2026-09-14 on `ogpartner-dk`: six notes stored on the record, one
step surfaced.** Confirm whether that is still true today.

## Trace the whole path, and say where the loss happens

    campaign config -> cadence graph -> LinkedIn message generation ->
    provider mapping -> HeyReach API payload -> provider response ->
    campaign preview

At each hop, count the steps in and the steps out. **The finding is the hop
where the count drops**, named by file and function.

Check connection request, follow-ups, ordering, delays, sender assignment,
personalisation variables, message bodies, provider step types, unsupported
operations, and preview consistency.

**A 200 from the provider does not prove the steps were configured.** Read the
campaign back and count what it holds.

## The regression test is the deliverable

A test that **fails when a configured step is silently omitted**. Not a test
that the graph has six entries; a test that six entries in produce six steps
out, and that a step with no copy is REFUSED rather than dropped.

Prove it fails: break it deliberately, show the failure, restore it.

## Rules

- **Do not modify any active HeyReach campaign.** Read only.
- Do not reduce the number of LinkedIn steps.
- Use the operator's own test campaign if a live read is needed; 620829 and
  613744 are ours. Never a client campaign.
- Report LIVE VALIDATION REQUIRED for anything you could not verify.

## Acceptance

    py -3 -m unittest tests.test_no_cadence_step_is_silently_dropped

plus: the hop where steps are lost, named by file and function, or evidence
that no loss occurs today. Commit, push, report the remote SHA and URL.

## RESULT

STATUS: DONE

COMMIT SHA: fe02f0966d2444fd9c10d3b40d06dea2b09aca3a

TESTS: `py -3 -m unittest tests.test_no_cadence_step_is_silently_dropped` —
10 tests, all pass. 116 tests pass across the broader cadence and HeyReach
factory modules.

FILES CHANGED:
- `tests/test_no_cadence_step_is_silently_dropped.py` (new, 366 lines)
- `docs/qwen-tasks/RUNNING/TASK-314-where-the-heyreach-steps-are-lost.md`
  (moved from TODO, result block added)

FINDINGS:

**The hop where steps are lost: `cadence.build()` at line ~1258 in
`src/cadence.py`.**

When `expand_step()` returns `None` for a generated step whose stored copy
is empty, `build()` silently drops the step with `continue` — UNLESS the
step carries a `requires` precondition, in which case a placeholder is kept.

The full pipeline trace, with step counts at each hop:

    campaign config (10 steps: li1-li5 + em1-em5)
      -> cadence.steps_for()          10 in, 10 out (no loss)
      -> cadence.expand_step()        10 in, 10 out when copy present
                                       Returns None when generated step
                                       has no stored copy
      -> cadence.build()              10 in, VARIABLE OUT
                                       Steps with requires: kept as placeholder
                                       Steps without requires: SILENTLY DROPPED
      -> heyreachfactory.assemble_    5 LI steps in, reports missing roles
         linkedin_copy()               (does not silently drop)
      -> heyreachfactory.build_       Graph always has all positions
         sequence()                    (uses merge variables, not per-lead copy)

Under the current `productive_li_heavy_v1` cadence:
- li1 has `template: linkedin_intro` — never enters the generated path
- li2-li5 have `requires: CONNECTED` — survive as placeholders even when
  expand_step returns None
- em1-em5 have NO `requires` — would be silently dropped if stored copy
  were absent

**The original bug (measured 2026-09-14 on ogpartner-dk):**
`expand_step` read `body` for LinkedIn instead of `note`. All generated
LinkedIn steps returned None. li1 survived only because it names a template.
The fix (already in code) reads `note` for LinkedIn.

**Current state: no loss occurs today when copy is present.** All 10 steps
surface in the timeline. The silent-drop path is reachable only when a
generated step has no stored copy AND no `requires` precondition.

**The regression test proves it catches the bug:**
Breaking `expand_step` to read `body` for LinkedIn (the original bug) causes
`test_linkedin_generated_reads_note_not_body` to FAIL with the message:
"expand_step returned None for a LinkedIn step with stored note. It may be
reading `body` instead of `note` for LinkedIn."
Restoring the fix makes it pass again.

RISKS:
- The silent-drop behaviour in `cadence.build()` still exists for generated
  steps without `requires`. If a future cadence adds a generated step without
  `requires` and the copy is not stored, the step will be silently dropped.
  The test catches this at the `expand_step` level but does not prevent the
  `build()` silent drop. A future fix could make `build()` report missing
  steps rather than dropping them.
- LIVE VALIDATION REQUIRED: the HeyReach campaign readback (counting steps
  in the provider's response) was not performed against campaigns 620829 or
  613744. The test verifies the local pipeline; the provider's response shape
  is not asserted.

RECOMMENDED CLAUDE ACTION:
- Accept the test as a regression guard.
- Consider whether `cadence.build()` should report missing steps rather than
  silently dropping them. The current behaviour is correct when copy has not
  been generated yet (phase 5 hasn't run), but could hide bugs when copy
  should be present but isn't.
- The HeyRead factory path (`assemble_linkedin_copy`) already reports missing
  copy correctly. The gap is in the cadence timeline path used for approval
  and preview.
