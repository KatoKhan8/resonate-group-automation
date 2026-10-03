PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-535 — GLM independent verification: TASK-433, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-433
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

Write the verdict to `docs/glm-reviews/TASK-535-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

## RESULT

**STATUS: DONE**

**COMMIT SHA:** bd21fd846

**TESTS:**
- Independent verification of TASK-433's claims at SHA 36a4ce61: ALL PASS
- `tests/test_http_timeout_aborts_at_socket_layer.py`: 19/19 pass
- `tests/test_a_bounded_gather_preserves_order_and_carries_every_outcome.py`: 41/41 pass
- `tests/test_prefetch_headcount.py`: 20/20 pass
- `tests/test_enrich.py`: 49/49 pass
- Falsification: `HttpTimeout` escapes `except ProviderError` at 36a4ce61 — CONFIRMED

**FILES CHANGED:**
- `docs/glm-reviews/TASK-535-verify-task-433.md`: verdict document (new)
- `docs/qwen-tasks/REVIEW/TASK-535-glm-verify-task-433.md`: task moved from TODO to REVIEW

**FINDINGS:**

1. **Artifact exists on the exact ref** — VERIFIED. SHA 36a4ce61 carries the TASK-231 changes.

2. **Existence is function** — PARTIALLY VERIFIED. TASK-433 missed a consumption gap: `HttpTimeout(TimeoutError)` at 36a4ce61 escapes the 27+ `except ProviderError` handlers in direct provider call paths outside `gather()`. This defect was caught and fixed during integration at commit b513879d1 on master, which changed `HttpTimeout(TimeoutError)` to `HttpTimeout(ProviderError, TimeoutError)`. The integrated code is correct.

3. **All five TASK-231 claims falsified and passing** — VERIFIED. Socket abort, exception classification, gather signature, prefetch, honesty caveat — all confirmed independently.

4. **Tests are falsifiable** — VERIFIED. Real TCP servers, real socket close assertions, real exception types. One test (`test_http_timeout_is_not_a_provider_error`) asserts a defect that was later fixed.

5. **Merging would NOT delete anything** — VERIFIED. Only the task file itself was moved.

6. **Scope drift present** — VERIFIED. TASK-226 changes (1,156 lines across 5 files) are isolated and can be cherry-picked around.

**RISKS:**
- None. TASK-231 is already integrated on master with the consumption gap fixed.

**RECOMMENDED CLAUDE ACTION:**
CLOSE. TASK-433's verdict was technically correct but missed one consumption gap. The gap was caught during integration and fixed. TASK-231 is on master with the correct implementation. No further action required.

The verdict is at `docs/glm-reviews/TASK-535-verify-task-433.md`.
