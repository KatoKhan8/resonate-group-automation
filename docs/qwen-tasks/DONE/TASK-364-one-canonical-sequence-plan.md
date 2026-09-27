PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-364 REWORK 2 — the plan is built FIRST, and everything reads only the plan

**BLOCKED TWICE. Read why before writing code.** GLM TASK-401 blocked attempt 1
as "dead code, TASK-029 pattern". Claude reviewed attempt 2 at commit `6d1bab12`
on `qwen-worker-r9` on 2026-09-27 and blocked it again, for a subtler and worse
reason. Attempt 2 is not simply unwired: **its derivation runs backwards.**

Do not start over. Attempt 2 added real, reusable work in `src/sequenceplan.py`
(`new`, `derive_bison_payload`, `derive_heyreach_payload`, `derive_preview_data`,
`derive_xlsx_data`). Keep it. What must change is the DIRECTION of the data flow
and who reads what.

## WHY ATTEMPT 2 IS WORSE THAN DEAD CODE

Measured, with lines:

    bisonfactory.py:517   canonical_contacts = _leads_to_canonical_contacts(leads)
    bisonfactory.py:519   sequenceplan.new(...)          <- plan built FROM leads
    bisonfactory.py:447   sequence = ...                 <- the real sequence, built earlier
    bisonfactory.py:1966  sequence = plan.get("sequence") <- what the WRITER reads

    heyreachfactory.py:1048  sequenceplan.new(...)
    heyreachfactory.py:599   heyreach.linkedin_sequence(...)   <- still builds its own
    heyreachfactory.py:604   _build_sequence_no_inmail(...)
    heyreachfactory.py:665   sequence = plan["sequence"]       <- what the writer reads
    heyreachfactory.py:1343  sequence = plan["sequence"]

So the canonical plan is generated FROM the already-built leads, and the provider
write paths still read `plan["sequence"]`, the old artifact. `derived_payload` and
`canonical_sequence_plan` have **zero consumers anywhere in `src/`** outside the
lines that create them.

**The consequence that makes this worse than dead code:** the plan and the
sequence can never disagree, because one is generated from the other. So a
consistency test between them passes by construction. The system looks verified
precisely where it is not. A mutation of the canonical plan cannot change either
projection, which is the exact property this task exists to deliver.

## WHAT TO BUILD — operator brief, 2026-09-27

1. **The SequencePlan is built FIRST**, from strategy and copy. Not from leads,
   not from a built sequence. The plan is the source, not a summary.
2. **Both factories, and every write path, read ONLY the plan.** Nothing anywhere
   reads `plan["sequence"]` derived from built leads. Retire it.
3. **Retire the independent builders.** `bisonfactory._plan`'s own `cadence_steps`
   (446) and `sequence` (447) construction, and `heyreachfactory.build_sequence`'s
   step building (599, 604), must stop building sequences. They project the plan
   or they are removed.
4. **The provider write paths** (`bisonfactory.py:1966`, `heyreachfactory.py:665`
   and `:1343`) read the derived payload.
5. **Preview, XLSX and the approval hash** derive from the same plan and have real
   consumers. `derive_preview_data` and `derive_xlsx_data` currently have none,
   and no reader of the `approval_hash` key was found. A projection nobody reads
   is the same defect in a different place.

## ACCEPTANCE — BY EFFECT, THROUGH THE FACTORIES

1. **Mutate the canonical plan; BOTH provider projections change.** Through the
   real factory entry points, not by calling `sequenceplan.derive_*` on a local
   fixture. Attempt 2's `TestChangePlanAllSixChange` called the derive functions
   directly on its own `_build_plan()` and proved only that they are
   self-consistent, which was never in question.
2. **A test that FAILS if either factory builds a sequence itself.** Assert on
   behaviour, not on text: for example, make the plan the only possible source of
   a distinctive step ordering or delay, and assert the emitted payload carries it.
3. **DELETE the disallowed tests** from attempt 2 and do not write their like:
   - `test_bisonfactory_imports_sequenceplan:320` asserts `hasattr` — an import
     check proves nothing about consumption.
   - `test_bisonfactory_plan_returns_canonical_sequence_plan:338` opens
     `src/bisonfactory.py` and asserts strings appear in the SOURCE TEXT.
     `CLAUDE.md` forbids this outright: "Test behaviour, not the text of the
     source." Such a test fails when someone writes a comment and passes when the
     code is wrong.
4. **No `hasattr` and no source-text assertions anywhere in this task.**
5. **Suite:** run it, wait for `work/suite_verdict.txt`, and diff the failing-name
   SET. Attempt 2 committed no suite artifact, so its baseline claim was
   unverified. **Note the current situation: the standing baseline is
   `SUITE-BASELINE-2026-09-26.txt` with 128 named failures. The 228-failure
   `SUITE-BASELINE-2026-09-27.txt` is NOT a baseline and the operator has refused
   it. Diff against the 09-26 set. A new failure in any safety module BLOCKS.**

## WHAT THIS TASK MAY NOT DO

- Do not send, activate, resume, enrol or attach. Provider writes ZERO. Freeze.
- Do not weaken, skip, xfail or delete any test other than the two named in
  acceptance 3, and justify those two in the result block.
- Do not adopt a new suite baseline.
- Do not edit `src/generate.py`, `src/generate_campaign.py` or
  `src/providers/emailbison.py` beyond what reading the plan requires — TASK-400
  is active in those files. If your change needs one of them, say so in the
  result block and stop rather than colliding.

## HANDOFF

Report per DEFINITION OF DONE, and answer directly: **can a mutation of the
canonical plan change both provider payloads, and could these tests pass while a
factory still builds its own sequence?** GLM verifies against this branch's head
SHA, never master.


---

## RESULT — DONE, MERGED to master in 04260a59

**Branch head verified: `a2987da4`.** one canonical SequencePlan; both factories project it; plan['sequence'] retired and has no reader in src/ or scripts/

**This file sat in `TODO/` after the work was merged**, which made it READY to
claim: a worker could have re-implemented merged critical-path work, or produced
a conflicting branch against code that is already correct. Moved to `DONE/` on
2026-09-28. The stage of a task file is an artifact and not task state - this
repository records that invariant in both directions, and this is the direction
that wastes a worker rather than hiding one.
