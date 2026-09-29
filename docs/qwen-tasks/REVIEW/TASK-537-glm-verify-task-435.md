PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-537 — GLM independent verification: TASK-435, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-435
    branch          origin/glm-review-504-task-387
    branch HEAD SHA f3b68bf849d8361fab9d3f8f972229369cf60944

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`f3b68bf849d8361fab9d3f8f972229369cf60944` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`f3b68bf849d8361fab9d3f8f972229369cf60944` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-537-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT

**STATUS:** DONE  
**COMMIT SHA:** `001a9374`  
**TESTS:** N/A (read-only review, no code changes)  
**FILES CHANGED:**  
- `docs/glm-reviews/TASK-537-verify-task-435.md` (added, 277 lines)
- `docs/qwen-tasks/REVIEW/TASK-537-glm-verify-task-435.md` (moved from TODO)

**FINDINGS:**

TASK-435's verdict on TASK-246 is **correct in its core finding and recommendation**.
The REWORK disposition is justified: the wiring tests use `hasattr` and `assertIs`,
which are explicitly prohibited by QWEN.md as proof. The fix is small and specific.

**However, TASK-435 made a factual error in Finding 7 (deletion risk).** It claimed
the three deleted task files "do NOT exist on master," but two of them DO exist on
master (TASK-310 and TASK-388). Merging the branch as a whole would delete those two
task files from master. This is a real deletion risk that TASK-435 missed.

**Verified claims:**
- TASK-435 reviewed the correct SHA (`8db92715`) ✅
- The artifact exists and does what the result block claims ✅
- The production caller exists (`push.py:531` calls `enrollmenttags.preflight()`) ✅
- The wiring tests are NOT falsifiable (use `hasattr` and `assertIs`) ✅
- The CLI tests are NOT falsifiable (use `callable` and `find_spec`) ✅
- Scope drift is significant (78 commits, 121 files) ✅
- All 38 tests pass ✅
- REWORK recommendation is correct ✅

**Incorrect claim:**
- Deletion risk: TASK-435 said deleted files don't exist on master, but TASK-310
  and TASK-388 DO exist on master and would be deleted by a full merge ❌

**Recommendation:** MERGE TASK-435's verdict. The REWORK disposition for TASK-246
is correct. The cherry-pick scope (3 commits: `5c3e3f30`, `49d44051`, `19fb39a7`)
is critical to avoid deletion risk.

**RISKS:**

If TASK-246 is merged without fixing the wiring tests, a future refactor could
silently disconnect `enrollmenttags.preflight()` from `push.run()` and the tests
would not catch it. This is the exact defect that cost three tasks on 2026-09-14.

If the branch is merged as a whole (without cherry-pick), TASK-310 and TASK-388
would be deleted from master. This is the exact defect that has burned this
repository before.

**RECOMMENDED CLAUDE ACTION:**

1. Accept TASK-435's REWORK verdict for TASK-246
2. Cherry-pick the three TASK-246 commits from `qwen-worker-7-r9` at SHA `8db92715`
3. Do NOT merge the branch as a whole (deletion risk)
4. TASK-246 must fix the wiring tests before merge: replace `hasattr`/`assertIs`
   with a test that calls `push.run()` and asserts the result contains `tag_coverage`
