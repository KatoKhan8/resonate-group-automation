PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-529 — GLM independent verification: TASK-423, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-423
    branch          origin/qwen-worker-6-r9
    branch HEAD SHA 6aa450938b035e4486a8e13096da83d0c2f0d067

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`6aa450938b035e4486a8e13096da83d0c2f0d067` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`6aa450938b035e4486a8e13096da83d0c2f0d067` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-529-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

**STATUS:** REVIEW  
**COMMIT SHA:** 1d86b5bd  
**TESTS:** N/A — read-only verification task, no code changes  
**FILES CHANGED:**
- `docs/glm-reviews/TASK-529-verify-task-423.md` — the verdict document (NEW)

**ARTIFACT KIND:** Document (GLM independent verification)

**VERDICT:** MERGE

**FINDINGS:**

1. **Branch HEAD SHA verified:** `6aa450938b035e4486a8e13096da83d0c2f0d067` matches the task file specification. The branch has not moved.

2. **Artifact exists and does what the result block claims:** `docs/TASK-423-FAILURE-TAXONOMY.md` exists on the target branch. The per-lead table has 37 rows, the Pareto table sums to 37, and the largest buckets are specific (`not_an_agency` and `unrendered_variable`, 13 each), not "other" or "unknown".

3. **Root cause analysis verified:** The `{firstName}` defect mechanism is correct:
   - Writer prompts at `src/copystages.py:332` and `src/copyprompts.py:343` explicitly instruct the model to write `{firstName}` (camelCase)
   - Email templates use `{first_name}` (snake_case) throughout `src/cadence.py`
   - LinkedIn steps bypass `cadence.render()` and are stored verbatim in `src/generate_campaign.py:1103`
   - No post-generation substitution exists for LinkedIn messages
   - The defect still exists on master and is caught by copylint after the TASK-378 expansion

4. **No forbidden files edited:** TASK-423 did not edit any critical-path files (`src/generate.py`, `src/generate_campaign.py`, `src/bisonfactory.py`, `src/heyreachfactory.py`, `src/sequenceplan.py`).

5. **No gates loosened:** The taxonomy correctly identifies that widening copylint to ignore `{firstName}` would convert a caught defect into a shipped one.

6. **No PII committed:** No email addresses, personal names, or phone numbers in the artifact.

7. **Artifact would be ADDED, not deleted:** `docs/TASK-423-FAILURE-TAXONOMY.md` is a new file that does not exist on master.

8. **Scope drift:** The branch carries substantial other work (TASK-400, TASK-445, TASK-455, TASK-461, TASK-246). Cherry-pick required to integrate TASK-423 in isolation. The two TASK-423 commits (`f933ec7a2` and `463271080`) are clean and self-contained.

9. **Source data missing:** `fifty-data.json` does not exist on master or the target branch. The taxonomy correctly notes this and reconstructs from surviving artifacts.

**RISKS:**
- The branch carries 30+ commits of other work. Cherry-pick the two TASK-423 commits to avoid integrating unrelated changes.
- The `{firstName}` defect still exists on master and requires the two-part fix documented in the taxonomy.

**RECOMMENDED CLAUDE ACTION:**
1. Cherry-pick commits `f933ec7a2` and `463271080` to master.
2. Implement Fix 1 ({firstName} substitution) — highest impact, 13 leads.
3. Implement Fix 2 (list pre-filter) — prevents 26% waste on next batch.
4. Address missing `fifty-data.json` as a separate artifact preservation task.
