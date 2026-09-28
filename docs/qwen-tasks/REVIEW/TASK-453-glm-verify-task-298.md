PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-453 — GLM independent verification: TASK-298, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-298
    branch          origin/qwen-worker-r9
    branch HEAD SHA e456c6128774cfd00960ac50d7b39c6e99a3f8cd

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`e456c6128774cfd00960ac50d7b39c6e99a3f8cd` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`e456c6128774cfd00960ac50d7b39c6e99a3f8cd` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-453-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT BLOCK

    STATUS: REVIEW
    ARTIFACT KIND: finding (GLM verdict document)
    BRANCH: qwen-worker-7-r9
    COMMIT SHA: 61befa3a
    REVIEWED SHA: e456c6128774cfd00960ac50d7b39c6e99a3f8cd
    TESTS: 19/19 green at target SHA
           tests/test_absent_within_the_window_is_unconfirmed.py (11 tests)
           tests/test_the_watcher_is_running_the_code_we_think.py (8 tests)
    FILES CHANGED:
           docs/glm-reviews/TASK-453-verify-task-219.md (new, the verdict)

    VERDICT: CLOSE — already integrated to master.

    FINDINGS:
           1. check_readback.py is byte-identical on master (blob 70923833).
              TASK-298 was already cherry-picked/integrated.
           2. The ISSUE-043 fix is correctly implemented and falsified:
              - Absent within the window → UNCONFIRMED (not PASS, not FAIL)
              - Retry ladder at t+60/t+180/t+600, stops at first PASS
              - Still absent at t+600 → FAIL with lead id
              - Set equality diffed BOTH directions (counts alone rejected)
           3. DEFECT: test_watcher_reported_up_with_no_mtime_pair_is_rejected
              says "rejected" in its name but the verdict is PASS when no
              mtime/process pair is available. The watcher is reported as
              confirmed when nobody checked. Medium severity — the data is
              in the result JSON but the verdict is misleading.
           4. Branch's __init__.py would regress master's more detailed
              version (master has explanatory comments). Already avoided
              since master has the better version.

    CONSUMER ANALYSIS:
           check_readback is a QA tool, not a src/ module. The consumer is
           the QA registry (scripts/qa/__init__.py CHECKS), which has the
           readback entry on both the branch and master. CONSUMED.

    DELETION RISK:
           No production files deleted. 8 TODO task files moved to
           REVIEW/DONE/BLOCKED (lifecycle movement, not destructive).

    SCOPE DRIFT:
           Branch carries 75 files from many tasks. TASK-298's artifacts
           are 5 files. Cherry-pick would be needed, but moot since
           already integrated.

    RISKS:
           The watcher verdict defect (finding 3) should be fixed before
           the QA runner depends on the watcher rule in production.

    RECOMMENDED CLAUDE ACTION:
           No merge action needed — TASK-298 is already on master.
           Consider a follow-up task for the watcher test/verdict defect.
