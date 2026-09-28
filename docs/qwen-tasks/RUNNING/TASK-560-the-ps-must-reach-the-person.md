PRIORITY: P0
SIZE: M
DEPENDS: 

# TASK-560 — the P.S. must reach the rendered email and the projection

**Operator decision, Zvonimir, 2026-09-28: rendering the P.S. in the email a
person receives is a CANARY REQUIREMENT.**

## The state, retracted and confirmed

P0-B first reported the P.S. renders. **It retracted that**, and an independent
review confirmed the retraction and found it **understated**:

    src/bisonfactory.py    contains ZERO `ps` references
    src/render.py          reads `subject` / `body` only
    approval.fingerprint   does NOT cover `ps` - identical fingerprint with
                           and without it
    _certified_copy        its `forbidden` set omits `ps`

So the P.S. reaches the stored step and **no prospect-facing surface, no
operator-facing surface, and no client export.** Gating is fixed; rendering
does not exist.

**The fingerprint gap is the dangerous one: approved copy and the same copy
with a different P.S. hash identically, so an approval does not cover it.**

## Acceptance — proven END TO END, not per-function
1. The P.S. appears in the **rendered email body** a person would receive.
2. The P.S. appears in the **EmailBison projection** — the payload the provider
   is actually handed.
3. **`approval.fingerprint` changes when the P.S. changes.** Negative control:
   two drafts differing only in the P.S. must produce **different** fingerprints.
4. `_certified_copy`'s `forbidden` set covers `ps`.
5. **A required P.S. that is missing BLOCKS** — it must never vanish silently.
   Negative control: a step with no P.S. is refused, naming the step.
6. Mutation: drop the P.S. from the projection; acceptance 2 must go red.

## Files
`src/bisonfactory.py`, `src/render.py`, `src/sequenceplan.py`, `src/approve.py`
as needed, plus your own tests. **Do NOT touch `src/generate.py`** (TASK-557)
or `src/claims.py` (TASK-558).

## RULES THAT OUTRANK FINISHING — every brief here

- **NEVER WIDEN A GATE TO MAKE A DRAFT PASS.** If a gate refuses correct copy,
  fix what it CONSULTS, never what it PERMITS.
- **A test count is never a PASS.** Name the real path exercised, the negative
  control, and the killed mutation.
- **EVERY new check needs a NEGATIVE control** — an input that must be REFUSED
  — and a **NEAR-MISS** control, not only an obvious one. The B1 defect below
  exists precisely because every control used a pack containing the literal
  word.
- **MUTATION CHECK IS MANDATORY.** Break your own fix in source, prove the
  intended test goes red for the intended reason, confirm no other guard fired
  first, restore the source and verify **byte-identical by sha256**.
  These files are **CRLF**: a `\n`-anchored regex matches zero times and your
  mutation becomes a silent no-op that looks like a surviving test.
- **PROVIDER WRITES = 0.** `sending.live` is false, the freeze stands, nothing
  is sent to anybody.
- Production `work/` is READ-ONLY. Verify `work/queue.jsonl` and
  `work/campaigns.jsonl` unchanged **by sha256 from a fresh process** — mtime
  is the wrong instrument, 23 loops write that checkout.
- **Write suite logs OUTSIDE the repository.** A log inside the tree became
  part of `test_fixture_hygiene`'s corpus and nearly committed real prospect
  domains. And interrupting a suite leaves one temp dir per test — 94,867 of
  them broke every later run. **A suite with no `Ran N tests` line is an
  absent measurement, not a failure**: sweep `%TEMP%` and re-run.
- Suite baseline is `docs/state/SUITE-BASELINE-2026-09-26.txt`, 128 named
  failures, compared **AS SETS, NEVER COUNTS**. It is known stale on master
  (TASK-549): four of its entries fail on master with no branch at all.
- Commit and push to your own branch; **verify the remote with `git rev-parse`**.
  Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** (VERIFIED / UNPROVEN /
  UNKNOWN) and your exact branch head SHA. GLM verifies against that SHA.

---

# REWORK 1 — 2026-09-28 late, Claude (merge authority)

**GLM verified `qwen-worker-r9` head `afef8fb2` and returned FAIL.** Its
literal verdict line was `NEEDS_CLAUDE`; the two defects below are the part
that is a real defect rather than an unverifiable branch. Report:
`docs/glm-reviews/branch-TASK-560.md`. Decisions:
`docs/MERGE-DECISIONS-2026-09-28-GLM-ROUND.md`.

**START FROM A CLEAN BRANCH OFF `origin/master` `cf2f828e`. Do NOT continue on
`qwen-worker-r9`.** That branch carries **45 distinct task ids across 184
commits**, and GLM could not attribute a single `src/` hunk to TASK-560 inside
it: *"no hunk is attributable to 560 from this diffstat, so I cannot cite a
call site."* A correct fix on that branch is still unmergeable, so a pass
there is worth nothing. Branch name: `task-560-ps-rework`.

## DEFECT 1 — the P.S. tests exist TWICE, under two ids

`afef8fb2` adds BOTH:

    tests/test_task553_ps_must_reach_the_person.py   340 lines   3 tests RED
    tests/test_task560_ps_reaches_the_person.py      324 lines   claimed green

Neither module exists on master. Two modules encode two different contracts
for one feature and one of them is red. The red ones:

    test_task553_...TestBodyWithPs.test_body_with_ps_appends
    test_task553_...TestBodyWithPs.test_empty_body_with_ps_returns_ps
    test_task553_...TestRenderIncludesPs.test_render_body_with_ps_appends

**Ship ONE module.** 553 is the superseded id for this very task, so the 553
module is a leftover, not a second requirement. **Decide which contract is
correct before deleting either** — if the 553 assertions describe the right
behaviour and the implementation does not satisfy them, the implementation is
what is wrong. Do not delete a red test to make a suite green.

## DEFECT 2 — two REAL regressions, confirmed against master independently

    test_the_research_pack_has_one_shape.AbsenceIsNotAnError
      .test_a_record_with_no_research_still_produces_copy
      .test_an_empty_list_is_the_same_as_absent

**These PASS on master `143f132f` and FAIL on `afef8fb2`.** Measured by Claude
on a clean worktree: modules `test_the_research_pack_has_one_shape`,
`test_generate`, `test_set_regeneration` → **84 tests, 1 failure**, and that
one failure is neither of these two. So this is a **regression you caused**,
not baseline drift, and not the stale-baseline artifact.

**The invariant being broken is load-bearing: a record with NO research must
still produce copy.** Absence is not an error. If composing the P.S. made an
empty or absent research pack fatal, the P.S. path is asserting something it
must not. Fix the cause, not the test.

## THE PRE-EXISTING FAILURE — do NOT try to fix it here

    test_set_regeneration.SetRegenerationTransactionTest
      .test_successful_regeneration_replaces_all_notes   AssertionError: 5 != 6

**That fails on master with no branch at all.** It is TASK-549's problem, not
yours. Do not touch it, and do not report it as yours.

## ACCEPTANCE — unchanged, plus these

The six original acceptance points stand in full. Additionally:

7. **The diff is attributable.** Every changed file answers to TASK-560. A
   reviewer must be able to name the production call site that renders the
   P.S. GLM's first question is "name the production caller" and
   `afef8fb2` could not answer it.
8. **One P.S. test module, not two.**
9. **`test_the_research_pack_has_one_shape` is green**, all classes.
10. **Compare the baseline AS SETS, never counts** — it is stale
    (TASK-549), so a count comparison will mislead you in both directions.

**Provider writes = 0. `sending.live` stays false. The freeze stands. Nothing
is sent to anybody.** Production `work/` is read-only; verify
`work/queue.jsonl` and `work/campaigns.jsonl` unchanged by sha256 from a fresh
process.

**This task is the head of the artifact critical path: `560 -> 904 -> 905 ->
906`, all four on the same rendering path, and 904 cannot start until this
lands.** It is the only thing between the operator and a one-account review
artifact that contains a P.S. at all.

---

# REWORK 2 — 2026-09-28 late, Claude (merge authority)

**Branch `qwen-worker-3-r10` head `803ba8fc`. GLM verdict: `NEEDS_CLAUDE`.
Claude read the diff body and decided. Report:
`docs/glm-reviews/branch-TASK-560.md`.**

## WHAT WAS RIGHT — keep all of it

The structure is exactly what was asked: **a clean 3-commit branch off master,
5 files, every one attributable to TASK-560**, one test module and no duplicate
553 module. **Both regressions from rework 1 are fixed** —
`test_the_research_pack_has_one_shape` is green, all 19 tests. Do not redo any
of this.

**GLM's "41 lines in `src/bisonfactory.py` may be dead code" is REFUTED** —
Claude read the diff body GLM was not given. Those lines are live and each one
answers to an acceptance point: `material["ps"]` in the fingerprint (3),
`"ps"` added to `_certified_copy`'s `forbidden` set (4), and `_append_ps`
feeding `_variables_for` (2). **No action needed. Do not delete them.**

## THE ONE DEFECT — acceptance 5 does not hold: the P.S. CAN vanish silently

`_approved_copy` (`src/bisonfactory.py` ~1101):

    if "ps" in found and not (found.get("ps") or "").strip():
        missing.append(f"{key} (missing P.S.)")

**This blocks only when the key is PRESENT and empty. A step whose `ps` key is
ABSENT passes.** So the single representation that is refused —
the explicit empty string — is **exactly the one that omit-empty and proto3
serializers elide.** Any boundary that drops empty fields converts the
blocking case into the silently-passing case and ships P.S.-less mail.

**Acceptance 5 of this brief says: "A required P.S. that is missing BLOCKS —
it must never vanish silently." As delivered, it vanishes silently.** Found by
GLM; the input is nameable, so it is a defect and not a theoretical worry.

`tests/test_task560_ps_reaches_the_person.py::test_step_without_ps_field_is_fine`
**blesses the bypass** — but read it before changing it: it uses **`em2`**,
which legitimately has no P.S. **The test is correct; the implementation
generalised it to every step.**

## THE FIX — key the check on the STEP, not on the key's presence

**Whether a P.S. is required is a property of WHICH STEP this is, not of
whether the field survived serialisation.** The intent is recorded at
`src/generate.py:2056` — *"ps on em1 and em3"*. So:

    em1 / em3, no `ps` key        ->  BLOCK, naming the step   (required, lost)
    em1 / em3, `ps` present empty ->  BLOCK, naming the step   (required, empty)
    em2 / em4 / em5, no `ps` key  ->  PASS                     (never had one)

This closes the bypass, keeps `test_step_without_ps_field_is_fine` valid as
written, and is the same rule TASK-907 acceptance 4 depends on — **the two
briefs must not disagree about it.**

**`src/generate.py:2056` is a DOCSTRING, and a docstring is not canonical
state.** Prefer a real authority if one exists — `cadence.steps_for` or the
sequence spec — and if none does, put the required-P.S. step set in **ONE**
named place that both this check and TASK-907 read. Do not hardcode `em1`/`em3`
in two files.

## Acceptance — only these, the rest already passed

1. **NEGATIVE CONTROL, the one that failed:** a **required** step (em1/em3)
   with the `ps` key **entirely absent** is REFUSED, naming the step. Assert
   the refusal, not a log line.
2. `em2` with no `ps` key still passes —
   `test_step_without_ps_field_is_fine` stays green, unchanged.
3. The required-P.S. step set lives in exactly one place.
4. `test_the_research_pack_has_one_shape` stays green, all classes. **It was
   broken once by this task already.**
5. **MUTATION:** invert the step-key condition; acceptance 1 must go red for
   that reason with no other guard firing first. Restore, verify
   **byte-identical by sha256**. Files are **CRLF** — an `\n`-anchored regex
   matches zero times and the mutation becomes a silent no-op.

**Do NOT touch `src/generate.py`** — TASK-907 owns the producer hop, and its
brief says so. **Its `ps` key is the thing your check must not require to be
present.** Stay in `src/bisonfactory.py`.

## START HERE — your previous work is on the REMOTE, not in your tree

**The dispatcher resets your worktree to `origin/master` before you start, so
the rendering work from rework 1 is NOT in your working tree. It is safe on
the remote at `origin/qwen-worker-3-r10` = `803ba8fc`.**

**FIRST COMMAND, before anything else:**

    git merge --no-edit origin/qwen-worker-3-r10

That brings back the 5-file rendering change (`src/render.py`,
`src/bisonfactory.py`, `src/approval.py`, the test module, the task file).
**Verify it arrived** — `git log --oneline` must show
`TASK-560: P.S. reaches rendered email and projection` — then make the
one-defect fix below on top of it. **Do not re-implement rework 1 from
scratch; it was correct.**

If the merge conflicts, the conflict is in the task file's appended text only;
take both sides and keep going.

**`test_set_regeneration...test_successful_regeneration_replaces_all_notes`
fails on master at `5 != 6` with no branch at all. Not yours. Do not fix it,
do not report it.**

**Provider writes = 0. `sending.live` false. Freeze stands.**
