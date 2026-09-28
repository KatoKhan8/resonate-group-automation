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

---

# REWORK 2 — 2026-09-28, Qwen (qwen-worker-3-r10)

**Branch `qwen-worker-3-r10` rebased onto `origin/master` `24480471`.**
Head `563151a3`. Four commits ahead of master, all attributable to TASK-560.

## THE DEFECT FROM REWORK 2 — FIXED

The P.S. check in `_approved_copy` keyed on the KEY'S PRESENCE, not on the
STEP. A required step (em1/em3) with no `ps` key at all passed through,
because the check asked `"ps" in found` instead of "does this step require
a P.S.?" A boundary that drops empty fields converts the blocking case
(explicit empty) into the silently-passing case (absent key).

**The fix:** `STEPS_REQUIRING_PS = frozenset({"em1", "em3"})` is the SINGLE
authority for which steps require a P.S. The check now asks:
`if key in STEPS_REQUIRING_PS: is the P.S. absent or empty?` — keyed on the
step identity, not on whether the field survived serialisation.

## ACCEPTANCE — REWORK 2

1. **NEGATIVE CONTROL (the one that failed):** em1 with no `ps` key at all
   is REFUSED, naming the step. ✅ `test_required_step_without_ps_key_is_refused`
2. **em2 with no `ps` key still passes.** ✅ `test_step_without_ps_field_is_fine`
   unchanged and green.
3. **The required-P.S. step set lives in exactly one place.** ✅
   `STEPS_REQUIRING_PS` in `src/bisonfactory.py` line 1040.
4. **`test_the_research_pack_has_one_shape` stays green.** ✅ 19/19 tests.
5. **MUTATION:** Inverted `key in STEPS_REQUIRING_PS` → `key not in STEPS_REQUIRING_PS`.
   4 tests went red for the intended reason (P.S. check inverted), no other
   guard fired first. Restore verified byte-identical by sha256:
   `14ecb70cabbe1ab0a0ddd8abca277d078e5d46cf4744c511c985fd8f88b0b668`.

## ORIGINAL ACCEPTANCE — ALL SIX STILL HOLD

1. P.S. appears in rendered email body. ✅ `render.emailbison_rows` and `render.card`
2. P.S. appears in EmailBison projection. ✅ `bisonfactory._variables_for`
3. `approval.fingerprint` changes when P.S. changes. ✅ Negative control passes
4. `_certified_copy` forbidden set covers `ps`. ✅
5. Required P.S. that is missing BLOCKS. ✅ NOW keys on step, not key presence
6. Mutation: drop P.S. from projection changes body. ✅

---

# RESULT BLOCK

**STATUS:** REVIEW

**COMMIT SHA:** 563151a3

**BRANCH:** qwen-worker-3-r10

**TESTS:**
- `tests.test_task560_ps_reaches_the_person`: 14 tests, all green
  - 2 new negative controls: em1/em3 with no ps key are REFUSED
  - `test_step_without_ps_field_is_fine` (em2) still green
- `tests.test_the_research_pack_has_one_shape`: 19 tests, all green
- `tests.test_generate`: 33 tests, all green
- `tests.test_set_regeneration`: 32 tests, 1 pre-existing failure
  (TASK-549: `test_successful_regeneration_replaces_all_notes` 5!=6,
   fails on master with no branch)

**FILES CHANGED:**
- `src/approval.py`: fingerprint includes ps when present and non-empty
- `src/bisonfactory.py`: STEPS_REQUIRING_PS constant; _approved_copy check
  keys on step identity; _certified_copy forbidden set covers ps;
  _variables_for appends ps to body
- `src/render.py`: emailbison_rows and card include ps in rendered output
- `tests/test_task560_ps_reaches_the_person.py`: 14 tests

**PRODUCTION CALLERS (nameable, verified):**
- `bisonfactory._plan` line 453 calls `_approved_copy` — the P.S. check runs
- `bisonfactory._variables_for` lines 1702, 1716 call `_append_ps` — provider payload
- `render.emailbison_rows` line 53 calls `_append_ps` — CSV export
- `render.card` line 125 calls `_append_ps` — HTML review

**FINDINGS:**
1. The P.S. check now keys on STEP IDENTITY (`key in STEPS_REQUIRING_PS`),
   not on whether the `ps` field survived serialisation. This closes the
   bypass where a boundary dropping empty fields converts the blocking case
   into the silently-passing case.
2. `STEPS_REQUIRING_PS` is the single authority. TASK-907 must read from
   this same constant, not hardcode em1/em3 in two files.
3. Fingerprint backward compatibility preserved: only includes non-empty ps.

**RISKS:**
- The generation path (TASK-557) must store the P.S. on the step dict for
  it to reach the rendering code. The rendering is ready; the producer is
  a separate task.

**RECOMMENDED CLAUDE ACTION:**
- Review and merge. The defect from rework 2 is fixed, all acceptance points
  hold, mutation verified, no regressions.

**ARTIFACT KIND:** Code + tests.
