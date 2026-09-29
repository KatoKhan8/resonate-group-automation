PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-501 — GLM independent verification: TASK-383, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-383
    branch          origin/qwen-worker-5-r9
    branch HEAD SHA d0432a8945acc1070bc07d952776ad679e7c755c

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`d0432a8945acc1070bc07d952776ad679e7c755c` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`d0432a8945acc1070bc07d952776ad679e7c755c` anyway, because that is the artifact this verdict is about.

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

Write the verdict to `docs/glm-reviews/TASK-501-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

**STATUS:** DONE
**ARTIFACT KIND:** Document (independent GLM verification)
**COMMIT SHA:** (pending push)
**BRANCH:** `qwen-worker-8-r9`
**REVIEWED SHA:** `d0432a8945acc1070bc07d952776ad679e7c755c` (exact HEAD of `origin/qwen-worker-5-r9` at task dispatch; branch has since moved to `0e1331b1`)
**TESTS:** Read-only verification — all 7 controls and 3 findings independently reproduced via grep/import trace in isolated worktree at target SHA
**FILES CHANGED:**
- `docs/glm-reviews/TASK-501-verify-task-383.md` (new, verdict document)
- `docs/qwen-tasks/REVIEW/TASK-501-glm-verify-task-383.md` (moved from TODO, result block added)

**VERDICT: MERGE**

TASK-383's review document (`docs/glm-reviews/checkpoint-a-0077c76e.md`) is **accurate and well-evidenced**. All seven control dispositions independently confirmed:

| # | Control | TASK-383 | TASK-501 independent check |
|---|---|---|---|
| 1 | One production entrypoint | FAILS | ✓ CONFIRMED — `grep -rn "generate_campaign" src/ scripts/` returns zero hits |
| 2 | Second Brain has real consumer | FAILS | ✓ CONFIRMED — `business_context_for` has zero callers; `generate.py` does not import `secondbrain` |
| 3 | Canonical research = one authority | HOLDS | ✓ CONFIRMED — `researchpack` references are docstrings only |
| 4 | Changed fact → changed artifact | UNVERIFIABLE | ✓ AGREED — test calls disconnected `generate_campaign` directly |
| 5 | No `work/` dependency | HOLDS | ✓ CONFIRMED — zero direct `work/` access in `src/` |
| 6 | No closed wiring loop | FAILS | ✓ CONFIRMED — all 5 `skills.load()` calls in `generate_campaign.py` only; `generate.py` imports none of the new modules |
| 7 | No cross-account leakage | HOLDS | ✓ CONFIRMED — exact identity join (record_id + domain) |

All three new findings (A: dead code, B: two architectures, C: declarative-only metadata) confirmed.

**Deletion risk:** NONE — only TODO task files moved to DONE (normal lifecycle).
**Scope drift:** SIGNIFICANT — branch carries 19 commits / 57 files; TASK-383's artifact is one clean file (commit `edf9eee2`). Cherry-pick recommended.

**FINDINGS:**
- The closed wiring loop remains the live blocker. Five skills → `generate_campaign.py` → nobody.
- The review document itself is correct and valuable.
- The branch is a multi-task integration branch; the review artifact should be cherry-picked independently.

**RISKS:** None in the review document itself. The architectural defect it identifies remains unresolved.

**RECOMMENDED CLAUDE ACTION:** Merge the review document (cherry-pick `edf9eee2` or extract the file). The central finding feeds directly into TASK-137's scope (narrowing seals / wiring the entrypoint).
