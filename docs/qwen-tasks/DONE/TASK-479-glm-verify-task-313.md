PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-479 — GLM independent verification: TASK-313, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-313
    branch          origin/qwen-worker-9-r9
    branch HEAD SHA f1b9c357c17f4b557cbdb06f68339c7343ef3e83

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`f1b9c357c17f4b557cbdb06f68339c7343ef3e83` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`f1b9c357c17f4b557cbdb06f68339c7343ef3e83` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-479-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT KIND:** Document (GLM verification verdict)

**COMMIT SHA:** `6c95021b`

**TESTS:** N/A (read-only verification task, no code changes)

**FILES CHANGED:**
- `docs/glm-reviews/TASK-479-verify-task-219.md` (CREATED — the verdict document)
- `docs/qwen-tasks/DONE/TASK-479-glm-verify-task-313.md` (moved from TODO, result block added)

**FINDINGS:**

1. **Artifact exists and is comprehensive.** `docs/AUDIT-2026-09-26.md` exists at the target SHA (700 lines), covers all sections 3-12, names files and functions, separates confirmed bugs from recommendations, and includes test commands with results.

2. **Core claims verified:**
   - `generate_campaign.py` has zero callers in `src/` at branch HEAD — CONFIRMED
   - `secondbrain.for_task()` has no production consumer — CONFIRMED (single hit in disconnected v2 chain)
   - Email→LinkedIn cross-channel stop field name fixed, `LINKEDIN_STOP_LEAD` in SUPPORTED — CONFIRMED
   - `learning.boost()` is dead code (zero callers in `src/`) — CONFIRMED

3. **One finding is stale at branch HEAD.** The audit claims "all six offers are pending" but commit `09476cda` (position 4 in branch history, more recent than the audit commit at position 14) approved OFFER-A and OFFER-B v2. At branch HEAD, two composed offers are `approved` by the operator (Zvonimir, 2026-09-27). The six base offers remain `pending`.

4. **Massive scope drift.** The branch carries 227 commits and 64 files changed beyond master. Only 2 commits are TASK-313 specific. The branch includes TASK-305 (Groq/OpenRouter adapters), TASK-384, TASK-392, TASK-399, TASK-401/402/404 (GLM verifications), TASK-416, TASK-423/424/425, and many other tasks. Merging the entire branch would introduce unrelated work.

5. **Deletion risk is low for audit-only merge.** If only the audit document and TASK-313 task file are merged, no production code is deleted. Two task files (TASK-392, TASK-399) would be moved from TODO to REVIEW, but those are legitimate state transitions for those tasks.

6. **Test claims are plausible but not re-verified.** The audit reports test commands and results. The full suite takes ~865s and was not re-run. Individual module tests reported are consistent with codebase state. Two `test_invariants` failures are documented and explained.

**RISKS:**
- The audit's "all offers pending" finding is outdated at branch HEAD. Claude should note that OFFER-A and OFFER-B v2 are now approved when reading the audit.
- The branch should NOT be merged wholesale due to scope drift. Only the audit document should be cherry-picked.

**RECOMMENDED CLAUDE ACTION:**
1. Cherry-pick `docs/AUDIT-2026-09-26.md` from the branch (additive, no conflicts).
2. Note that the audit's offer finding is stale — two composed offers are now approved.
3. Use the audit's other findings (disconnected entrypoint, cross-channel stop, dead code) to inform the phase 1 plan.
4. Do NOT merge the entire `qwen-worker-9-r9` branch — it carries 225 commits of unrelated work.

**DISPOSITION:** MERGE WITH CAUTION (audit document in isolation, not entire branch)
