PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-440 — GLM independent verification: TASK-281, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-281
    branch          qwen-worker-2-r9
    branch HEAD SHA f03c74fc01a40df45419742e122268d11c8395a1

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`f03c74fc01a40df45419742e122268d11c8395a1` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`f03c74fc01a40df45419742e122268d11c8395a1` anyway, because that is the artifact this verdict is about.

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
5. **Would merging it DELETE anything?** `git diff master...f03c74fc01a40df45419742e122268d11c8395a1 --stat`. This
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

Write the verdict to `docs/glm-reviews/TASK-440-verify-task-281.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

    STATUS: DONE
    ARTIFACT KIND: document (GLM verdict)
    BRANCH: qwen-worker-7-r9
    COMMIT: 3d51f0f2
    TARGET REVIEWED: TASK-281 on qwen-worker-2-r9 at exact SHA f03c74fc01a40df45419742e122268d11c8395a1
    
    DISPOSITION: REWORK
    RECOMMENDATION: CHERRY-PICK the three TASK-281 artifacts, do not merge the branch
    
    FINDINGS:
      1. DISCONNECTED (Critical): Zero production callers. The script exists
         but nothing in src/ or scripts/ imports or invokes it. This is the
         recurring defect: a thing computed correctly that nothing downstream
         reads. Verification: `grep -rn "reengagement_provider_read" src/ scripts/`
         returns nothing outside the script's own definition.
      
      2. SCOPE DRIFT (High): The branch carries 93 file changes across 46
         commits. TASK-281 is 3 files. Merging wholesale would introduce
         unrelated work (TASK-293, TASK-318, TASK-364, TASK-372, TASK-387,
         TASK-397, TASK-400, TASK-410, TASK-423/424/425, offer approvals,
         status reports, GLM verdicts). Cherry-pick only the three TASK-281
         files: commit 99795a3e18f04fa1925bfeb05d8211464c409a4d.
      
      3. DELETED FILE (Medium): docs/qwen-tasks/TODO/TASK-372-the-suite-baseline-is-73-failures-short.md
         is deleted without a corresponding addition in REVIEW/ or DONE/ on
         this branch. Needs separate review.
      
      4. CODE QUALITY (Low): scripts/reengagement_provider_read.py:333 calls
         assess_reengage(sends, sends, now=now) instead of assess_reengage(row,
         sends, now=now). The bug is harmless because assess_reengage never
         reads its first parameter, but the signature is misleading.
      
      5. LIVE RUN NOT EXECUTED (Medium): The task acknowledges this. The
         per-row table with real provider ages is owed. The script and tests
         are correct in isolation but the I/O path against production state
         is not verified.
    
    WHAT IS CORRECT:
      - All three artifacts exist on the target ref (verified)
      - Script does not read cached last-touch.json (grep returns nothing)
      - Provider age is load-bearing (mutation test verified: removing provider
        data changes verdict from TOO_RECENT to HELD, not silent cache fallback)
      - 30/30 tests pass
      - Tests are falsifiable (assert on behavior, not source text)
      - No fixture provider responses in the production script
    
    WHAT IS OWED:
      1. Wire the script into a production caller (batch job, pipeline step,
         or entrypoint). Until then, it is DISCONNECTED.
      2. Run the live measurement from Claude's worktree against production
         state to fill in the TBD numbers in the report.
      3. Fix the assess_reengage call-site bug (line 333).
      4. Cherry-pick commit 99795a3e, do not merge the branch.
    
    TESTS:
      Verified in isolated worktree at f03c74fc:
      - python -m unittest tests.test_reengagement_age_is_read_not_cached -v
        Ran 30 tests in 0.002s ... OK
      - Mutation test: compare_row with sends vs None produces different
        verdicts (TOO_RECENT vs HELD), proving the dependency is real.
    
    FILES CHANGED:
      docs/glm-reviews/TASK-440-verify-task-281.md (new, 308 lines)
    
    REPRODUCIBLE VERIFICATION:
      git worktree add .qwen/worktrees/task440-review f03c74fc01a40df45419742e122268d11c8395a1 --detach
      cd .qwen/worktrees/task440-review
      grep -rn "reengagement_provider_read" src/ scripts/ | grep -v "reengagement_provider_read.py:"
      # (empty - proves zero callers)
      grep -n "last-touch" scripts/reengagement_provider_read.py
      # (empty - proves no cache read)
      python -m unittest tests.test_reengagement_age_is_read_not_cached -v
      # 30 tests, all pass
      git diff master...f03c74fc --stat | tail -1
      # 93 files changed, 10615 insertions(+), 315 deletions(-)
    
    RISKS:
      - The script remains DISCONNECTED until wired into production.
      - The live run is owed; all per-row numbers in the report are placeholders.
      - The branch has significant scope drift; cherry-pick, do not merge.
    
    RECOMMENDED CLAUDE ACTION:
      1. Cherry-pick commit 99795a3e from qwen-worker-2-r9 to extract only
         the three TASK-281 artifacts.
      2. Wire scripts/reengagement_provider_read.py into a production caller
         (batch job or pipeline step).
      3. Run the live measurement from Claude's worktree against production
         state to fill in the TBD numbers.
      4. Fix the assess_reengage call-site bug (line 333).
      5. Review the deleted TASK-372 task file separately.
