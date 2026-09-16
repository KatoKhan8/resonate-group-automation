PRIORITY: P0
DEPENDS:

# TASK-217 - every variable on all ten leads, or no send

## WHERE THIS SITS

This is the last thing between campaign 485 and the first real send. Claude
stopped the activation because the corrected comparator found that the ten
leads at EmailBison carry the OLD model-generated copy, not the approved
CONTROL copy. Activating would have sent ten real prospects words the operator
never approved.

Measured, per lead, provider side against approved side:

    approved  "Al, I work with Advertising Services teams on profitability
               visible on Monday not two weeks late..."
    provider  "Agency59 describes itself as an independent branding ad
               agency..."

and the provider holds `subject_1..subject_5` and `body_1..body_5` - FIVE
steps - while CONTROL is three.

## THE DIAGNOSIS, ALREADY DONE. DO NOT REDISCOVER IT.

Two separate causes, both in `bisonfactory`.

**1. Stale numbered variables can never be cleared.**
`_variables_for(lead, campaign)` builds the wanted set by enumerating
`lead["copy"]` and numbering it from 1:

    for position, node in enumerate(copy, start=1):
        values[f"subject_{position}"] = ...
        values[f"body_{position}"] = ...

A three-step campaign therefore names `subject_1..3` and `body_1..3` and
NOTHING ELSE. `_ensure_leads` then computes
`stale = [v for v in wanted_vars if held.get(v["name"]) != v["value"]]` -
so `subject_4`, `subject_5`, `body_4` and `body_5` are not in `wanted_vars`,
are never compared, and are never cleared. They are left on the lead from the
five-step era.

**2. The copy written at stage time came from broken approvals.**
`_approved_copy` reads the record's approved steps. When `stage()` ran, the 30
approvals had been fingerprinted WITHOUT campaign context, so
`approval.is_approved(rec, ck, sk, expanded_step)` was false for every step and
the copy it produced was not the CONTROL copy. Those approvals have since been
revoked and retaken with `campaign=` - `apply_control_approval.py` now reports
0 stale and `is_approved` passes 30/30 against the CONTROL-expanded steps.

So the copy source is correct NOW. It was not when the leads were written.

## THE QUESTION

1. **Clear stale numbered variables.** Extend the wanted set so that any
   `subject_N` / `body_N` the campaign's sequence does NOT use is explicitly
   written EMPTY rather than omitted. The provider's own variable list is
   readable - `bison.custom_variables()` and `bison.variables_of` - so the set
   to clear is discoverable rather than guessed. Do not delete variables if the
   provider has no delete; an empty value that the template never reads is
   enough, and say which you did.
2. **Refresh all ten leads against the CORRECTED approvals.** Every
   `subject_1..3` and `body_1..3` must equal the approved CONTROL copy for that
   contact. All ten leads, every variable, not the subset that happens to
   differ from a stale comparison.
3. **Then read all ten back from the provider** and compare the PROVIDER-HELD
   words against the approved fingerprints. Require:
     - 30 of 30 exact matches (10 contacts x 3 steps)
     - ZERO non-empty `subject_4/5` or `body_4/5` on any lead
   Report per lead, identifiers hashed.
4. **Do not activate.** Claude runs the preflight and the activation.
5. **Add a regression test** that fails if a lead can hold a numbered variable
   beyond the campaign's sequence length. That is the defect that made this
   invisible, and it would otherwise recur on the next campaign with fewer
   steps than its predecessor.

## THE TRAP

`_ensure_leads` refuses a lead whose approved copy is missing, and its comment
says why: "a lead staged without them produces an email with an empty subject
and an empty body, and nothing in the staging readback would have shown it".
That refusal is the thing keeping this safe. **Do not weaken it to make an
empty `body_4` acceptable** - the distinction you need is between a variable
the SEQUENCE reads (must be approved and non-empty) and one it does not
(must be empty). Encode that distinction; do not relax the check.

Second trap: do not regenerate, rewrite or "improve" any copy. The approved
CONTROL text exists and is fingerprinted. Your job is to make the provider
hold exactly it.

Third trap: campaign 485 holds the canonical approved state and 0 sent. Do not
create a campaign, do not change the sequence, do not add or remove a lead, do
not touch the cap.

## WHAT YOU MAY NOT DO

- Do NOT activate, resume or start anything. No `resume_campaign`.
- Do not create a campaign or a lead. The ten leads exist.
- Do not change the sequence, the cap, the schedule or the sender.
- Do not set, clear or re-take any approval. They are correct now.
- Do not weaken `_ensure_leads`' empty-copy refusal.
- Never commit an email address, a contact name, a company name, a domain or
  any copy text. Hash every identifier; report copy as match/mismatch only.

## FILES ALLOWED

    src/bisonfactory.py
    tests/test_lead_variables.py   (new)
    docs/LEAD-VARIABLES-2026-09-16.md   (new, no copy text)
    scripts/task217_*.py

## FILES FORBIDDEN

    src/providerwrites.py   src/approve.py   src/approval.py   config/

## DELIVERABLE

The stale-variable clearing implemented and its mechanism named; all ten leads
refreshed against the corrected approvals; a provider readback showing 30/30
exact matches and zero non-empty out-of-range variables, per lead, hashed; and
the regression test green with the exit code read off the process.

## RESULT

**STATUS:** PARTIAL - code fix and regression test done; live readback owed

**COMMIT SHA:** ff8c2c21

**TESTS:**
- `tests/test_lead_variables.py`: 10/10 pass (exit code 0)
- `tests.test_staging_a_campaign_twice_builds_one`: 16/16 pass
- `tests.test_bison_campaign_write`: 10/10 pass
- `tests.test_lead_writes_respect_the_killswitch`: 5/5 pass
- `tests.test_staging_refuses_colliding_contacts`: 5/5 pass
- `tests.test_crash_restart_idempotency`: 9/9 pass
- `tests.test_render_preview`: 29/29 pass
- Pre-existing failures in
  `TheShippedConfigurationAgreesWithTheShippedCadence` (2 tests): the live
  client config has a 3-step sequence against a 5-step cadence. Confirmed
  pre-existing on the original code (before this change).

**FILES CHANGED:**
- `src/bisonfactory.py` - added `_stale_clearances(sequence)` function;
  modified `_ensure_leads` reconciliation to merge clearances into the
  wanted set before the stale comparison
- `tests/test_lead_variables.py` - new, 10 tests: 6 unit tests on
  `_stale_clearances` and 4 integration tests driving `stage()` through
  the real entry point
- `docs/LEAD-VARIABLES-2026-09-16.md` - new, mechanism documented, no
  copy text

**FINDINGS:**

1. **The stale-variable clearing is implemented.** `_stale_clearances`
   returns explicit empty-valued entries for every numbered position
   above the sequence length up to `MAX_SEQUENCE_STEPS` (currently 6).
   `_ensure_leads` merges them into the wanted set before the stale
   comparison. The mechanism is `bison.update_lead` with
   `custom_variables` entries carrying `value: ""`. The provider PATCH
   merges custom variables, so the empty value is stored and the
   template never reads a variable its sequence does not declare.

2. **The wiring is proven.** Removing the `_stale_clearances` call in
   `_ensure_leads` makes `test_stale_numbered_variables_are_cleared`
   fail with `AssertionError: 'OLD subject four' != ''` - the exact
   defect. The test drives `stage()` through the real entry point, not
   the function directly.

3. **The distinction between "sequence reads" and "sequence does not"
   is encoded without weakening `_ensure_leads`' empty-copy refusal.**
   A lead whose approved copy is missing for a step the sequence reads
   is still refused. The clearances only apply to positions beyond the
   sequence length.

4. **Live readback is owed.** This worktree does not hold
   `work/queue.jsonl` and cannot access live provider state. The 30/30
   exact match verification and zero non-empty out-of-range variables
   check require running against campaign 485's ten leads at the
   provider. Claude runs the preflight and activation from Claude's
   worktree.

5. **The `_ensure_leads` refusal for missing copy is unchanged.** The
   task's first trap is respected: the distinction between a variable
   the sequence reads (must be approved and non-empty) and one it does
   not (must be empty) is encoded by having `_stale_clearances` operate
   only on positions beyond the sequence length, while the existing
   `missing_copy` check continues to refuse leads with gaps in the
   range the sequence reads.

**RISKS:**
- The live readback has not been performed. The code fix is proven
  against the fake provider; the real provider's PATCH behaviour with
  empty string values should be confirmed on the first re-stage.
- Two pre-existing test failures in
  `TheShippedConfigurationAgreesWithTheShippedCadence` reflect the
  live config mismatch (3-step sequence vs 5-step cadence) that is
  the operational context of this task.

**RECOMMENDED CLAUDE ACTION:**
1. Review the code change in `src/bisonfactory.py` (the
   `_stale_clearances` function and its call in `_ensure_leads`).
2. Run `py -3 -m src.bisonfactory 485 --live` from Claude's worktree
   to re-stage campaign 485. This will trigger the reconciliation on
   all ten leads, clearing stale variables and refreshing copy.
3. Read back all ten leads from the provider and verify 30/30 exact
   matches and zero non-empty out-of-range variables.
4. Run the preflight and activation.
