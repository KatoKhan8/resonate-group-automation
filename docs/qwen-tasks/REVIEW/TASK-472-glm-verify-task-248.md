PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-472 — GLM independent verification: TASK-248, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-248
    branch          origin/qwen-worker-7-task-248
    branch HEAD SHA f37cc9b77a80d42819e8469cdc2a916b33cfcd82

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`f37cc9b77a80d42819e8469cdc2a916b33cfcd82` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`f37cc9b77a80d42819e8469cdc2a916b33cfcd82` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-472-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

**STATUS** DONE

**COMMIT SHA** 13413f02

**TESTS** N/A - this is a review task, not an implementation task. Verified TASK-248's 19 tests all pass in the isolated worktree.

**FILES CHANGED**
- `docs/glm-reviews/TASK-472-verify-task-219.md` — new. Independent verdict document with 13 verification sections, findings summary, and recommendation.
- `docs/qwen-tasks/REVIEW/TASK-472-glm-verify-task-248.md` — moved from TODO.

**FINDINGS**

1. **Artifacts exist on exact ref f37cc9b7** — VERIFIED. All four claimed files (readback module, loop script, prompt, tests) exist and match the result block claims.

2. **Import reachability is STRONG** — VERIFIED. Neither `slackagentreadback.py` nor `slack_agent_loop.py` imports `providerwrites`, `orchestrator`, `providers.bison`, or `providers.heyreach`. Transitive import analysis confirms no forbidden module is reachable. This is the primary safety property: even if the LLM wanted to execute a write, no code path exists.

3. **Prompt injection tests are WEAK** — The tests use `ScriptedModel` with a fixed canned response, not a real LLM. They prove the code path produces output, not that a real LLM would refuse hostile instructions. However, the import reachability test is the real safety net, so this weakness is secondary.

4. **`store.save` reachability test is WEAK** — Checks whether `save` is in `vars(slackagentreadback)`, which is false because the module imports `store as _store`. But `_store.save` IS technically accessible. The test passes for the wrong reason. Again, import reachability is the real safety property.

5. **Junk files committed** — `.qwen-TASK.err` and `.qwen-TASK.out` are scratch output files that should not be in the repo. These must be stripped before merge.

6. **Scope list is CORRECT** — VERIFIED against https://docs.slack.dev/reference/scopes. All 8 scope names are exact matches.

7. **Merge safety** — VERIFIED. No deletions. All changes are additive (4 new files + append to SLACK-NOTIFICATIONS.md).

8. **Consumption** — VERIFIED. The readback module is consumed by the loop script. The chain is connected: `slack_agent_loop.py` → `slackagentreadback.gather()` → `store.load()`, `campaigns.load()`, etc.

9. **Idempotency tests** — STRONG. Tracker persists across restart, no duplicates.

10. **Failed readback tests** — STRONG. Errors are reported, never omitted, never cached.

11. **No conflict markers** — VERIFIED.

12. **All 19 tests pass** — VERIFIED in isolated worktree.

**RISKS**
- The junk files (`.qwen-TASK.err`, `.qwen-TASK.out`) must be removed before merge.
- The prompt injection test limitation should be documented: it tests the code path, not the LLM's behavior. The import reachability test is the real safety property.

**RECOMMENDED CLAUDE ACTION**
REWORK: Remove the two junk files, then merge. The core implementation is sound. The operator owes: add 7 scopes to the Slack app and reinstall (documented in SLACK-NOTIFICATIONS.md section 7).

**DISPOSITION** REWORK

**RECOMMENDATION** Remove junk files, then merge. Core safety property is correctly implemented and tested.
