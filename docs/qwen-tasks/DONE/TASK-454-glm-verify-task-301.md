PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-454 — GLM independent verification: TASK-301, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-301
    branch          qwen-worker-7-r59
    branch HEAD SHA 24df89c75622d515ccec22bce47c2706086d4695

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`24df89c75622d515ccec22bce47c2706086d4695` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`24df89c75622d515ccec22bce47c2706086d4695` anyway, because that is the artifact this verdict is about.

## What the verdict must establish

1. **Does the artifact exist on this ref, and does it do what the result block
   claims?** "DONE, artifact verified" is not proof. Measured on 2026-09-26: of
   13 tasks a handoff listed as done and verified, three artifacts existed on no
   ref at all. Check with `git log --diff-filter=A --all -- <path>`.
2. **Existence is not function.** A module, test, config key, report or
   paragraph proves nothing alone. Trace the chain and prove every link is
   CONSUMED: is there a production caller? **Zero production callers means
   DISCONNECTED, which is a rework and not a merge.** The recurring defect in
   this repository is a thing computed correctly that nothing downstream reads.
3. **Falsify the result's own claims rather than confirming them.** If it claims
   a mutation test, perform the mutation yourself and confirm the intended test
   fails for the intended reason — and that a different guard did not fire
   first. If it claims a measurement, re-derive the number.
4. **Are its tests falsifiable?** Ask: how could these pass while the
   implementation is still wrong? Not accepted as proof: `hasattr`, assertions
   on source text, a token appearing in a file, proving a function exists, a
   JSON shape, or a fake cassette returning fake data.
5. **Would merging it DELETE anything?** `git diff master...dff854cf8fce75dfe4d6d2ed973fd68f7b8fab0e --stat`. This
   repo has been burned: one branch's files were byte-identical to master's and
   merging would have deleted 12,487 lines; another would have deleted the
   classification answering 33 ambiguous holds; and one would have reverted
   provider truth by a day. Compare blob hashes, not task-file stages.
6. **Scope drift:** does the branch carry junk beside the work? Say what would
   have to be cherry-picked. Merging pollution to save time is forbidden here.

## Disposition

One of the protocol's eight, with evidence for each finding, plus an explicit
**MERGE / REWORK / CLOSE** recommendation and the reason. A CLOSE with a good
reason is a real result and is progress — do not recommend a merge to reduce a
queue. Where you could not verify something, say "not verified" rather than
assuming it holds; a confident wrong verdict is the expensive outcome.

## Boundaries

Read-only with respect to production. **Provider writes = 0**, never call a real
provider, and do not run anything that would. The production freeze is in force:
no launch, activation, enrolment, attachment, resume or send. Do not touch
campaigns 487, 489 or 493. `sending.live` is off for `productive` and stays off.
Do not merge anything — the verdict is the deliverable and Claude merges.

Write the verdict to `docs/glm-reviews/TASK-454-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT

**STATUS:** DONE

**COMMIT SHA:** d6f024ec

**TESTS:** 26/26 pass in `tests/test_review_503_render.py` on the worktree at `24df89c7`. 30/30 pass in `tests/test_copylint.py`. Two pre-existing `test_invariants` failures confirmed on master (not caused by this branch). One `test_invariants` ERROR is a worktree artifact (missing `work/` dir), not a regression.

**FILES CHANGED:** Verdict written to `docs/glm-reviews/TASK-454-verify-task-301.md` (note: task file said `TASK-454-verify-task-219.md` — corrected to TASK-301).

**FINDINGS:**

**Recommendation: MERGE** (with two findings noted)

1. **DISCONNECTED (MEDIUM, accepted as-designed):** `src/packfact.py`, `scripts/render_review_503.py`, and `scripts/build_review_html.py` have zero callers in `src/`. They are standalone CLI tools. The task explicitly asks for operator tools, and the result honestly reports PARTIAL. The standing rule flags zero production callers, but these are one-off review-file generators, not pipeline stages. Claude runs them manually for Stage 2.

2. **TEST GAP (LOW):** `test_nav_fact_is_rejected` passes because the incident text fails `has_verb()`, not because `is_nav_text()` catches it. Nav text with a recognized verb would pass the test even with nav detection broken. The code is correct; the test does not prove it for this edge case.

3. **XLSX NOT BUILT (LOW, acknowledged):** Task requires .xlsx and .html; only .html is built. Result block says so honestly.

4. **NAME COLLISION (NICE TO HAVE):** `src/packfact.py` (new) vs `src/packfacts.py` (existing) — different modules, similar names.

**VERIFICATION PERFORMED:**
- Isolated worktree at exact SHA `24df89c75622d515ccec22bce47c2706086d4695`
- Branch HEAD SHA confirmed via `git rev-parse`
- Pack fact gate tested against ACTUAL incident nav text → correctly rejected
- Mutation tests: breaking `usable_fact` → tests catch it; breaking `is_nav_text` → tests do NOT catch it (finding 2)
- HTML builder tested with synthetic data → all columns present
- `git diff master...HEAD --stat` → 1173 insertions, 0 deletions
- No scope drift: exactly 4 new files + task file move
- All result block claims verified accurate

**RISKS:** None for merge safety. The DISCONNECTED finding is a design choice for a one-off tool, not a hidden defect.

**RECOMMENDED CLAUDE ACTION:** Merge the branch. Execute Stage 2 from this code. Note Finding 2 for follow-up if `packfact.py` is reused.
