PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-457 — GLM independent verification: TASK-305, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-305
    branch          qwen-worker-9-r9
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

Write the verdict to `docs/glm-reviews/TASK-457-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT BLOCK

STATUS: DONE

COMMIT SHA: (pending)

TESTS: 19/19 pass on the branch head (unittest, isolated worktree)

FILES CHANGED:
  - docs/glm-reviews/TASK-457-verify-task-305.md (NEW) — the verdict
  - docs/qwen-tasks/REVIEW/TASK-457-glm-verify-task-305.md (MOVED from TODO/)

ARTIFACT KIND: document (review verdict)

FINDINGS:

1. **DISCONNECTED — zero production callers.** `groq.complete()`,
   `openrouter.complete()`, and `groq.fallback_complete()` are never imported
   or called by any production code. The generation path (`src/generate.py` →
   `src/llm.py` → `HttpModel`) does not use the new adapters. The modules are
   correct in isolation and completely unused. This is the canonical
   "existence is not function" defect.

2. **Scope drift.** The branch carries unrelated changes to `src/notify.py`
   (retired channels, ops_channel rewrite) and `src/providers/slack.py`
   (load_env in live()). These are Slack fixes from other tasks, not
   TASK-305's work.

3. **Live probe not run.** Acknowledged honestly in the result block.
   GROQ_API_KEY is absent from the worktree. Rate limit unmeasured.

4. **Tests are good contract tests but test the island, not the wiring.**
   Mutation: delete both adapter files, all other tests still pass.

5. **No deletion risk.** Only two task markdown files would be deleted.

6. **Credential registration correct.** Names match adapter constants.

RECOMMENDATION: REWORK

The adapters need a production caller before merge. Either `src/llm.py`'s
`HttpModel` delegates to the new adapters based on base URL, or
`src/generate.py` calls `groq.fallback_complete()` directly. The scope drift
(notify.py, slack.py) must be separated. The live probe is owed from Claude's
worktree.

RISKS: None from the verdict itself. The risk is in the branch: merging
disconnected code that passes its own tests but changes no production
behaviour.
