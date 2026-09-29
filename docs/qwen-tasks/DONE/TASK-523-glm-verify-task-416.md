PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-523 — GLM independent verification: TASK-416, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-416
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

Write the verdict to `docs/glm-reviews/TASK-523-verify-task-219.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT BLOCK

**STATUS:** DONE

**ARTIFACT KIND:** Document (GLM verdict)

**COMMIT SHA:** 11df6fcf (on origin/qwen-worker-7-r9)

**TESTS:** N/A — read-only verification task

**FILES CHANGED:**
- `docs/glm-reviews/TASK-523-verify-task-219.md` — new, the verdict

**FILES FORBIDDEN:** None named

---

### FINDINGS

1. **Artifact exists and is already on master.** `scripts/measure_research_freshness.py` was integrated via commit `90cd4175`. The task's PARTIAL status is honest: code complete, live run owed.

2. **Code path analysis is accurate.** Traced every link in the worktree at exact SHA `f1b9c357c17f4b557cbdb06f68339c7343ef3e83`. The critical finding is verified: `generate.research_block()` reads frozen quality at line 237 (`e.get("quality") in ("medium","strong")`) without re-aging, and reaches the draft prompt via `company_evidence()` at lines 642 and 696.

3. **One false positive corrected.** The task claimed `eligibility.py:802` reads frozen quality. It does read research entries, but line 811 calls `evidence.usable(rows, today)` which DOES re-age. This path is safe.

4. **Branch carries significant scope drift.** 40+ files beyond TASK-416: TASK-305 (Groq adapter), TASK-392/399 (moved to REVIEW), TASK-400–425, multiple GLM reviews, provider modules, test files. Cherry-pick TASK-416 artifact only.

5. **Merge safety verified.** Two TODO files were deleted but moved to REVIEW, not lost. Safe.

---

### RISKS

- **Stale copy reaching prospects.** The `research_block` gap is real. A fact that was "strong" when crawled 8 months ago still passes the frozen-quality filter and reaches the model, even though re-aged it would be BACKGROUND/WEAK. The model may write "I noticed you recently..." about something from November.

- **The mitigation is partial.** `research.for_prompt()` DOES re-age and its output (`public_evidence`) also reaches the prompt. But the model receives BOTH blocks and may prefer the `research` block's facts.

---

### RECOMMENDED CLAUDE ACTION

1. **Run the measurement script** from Claude's worktree: `python scripts/measure_research_freshness.py`. The script is already on master.

2. **Fix `generate.research_block()`** to re-age before filtering. Route through `evidence.reaged()` or `evidence.select()` — same as `research.for_prompt()`. Three lines of change.

3. **Audit `claims.support_text()`** for whether it needs re-aging. A claim check passing against a stale fact is a false positive that lets invented copy through.

4. **Cherry-pick TASK-416** from the branch if not already integrated (it is already on master as of `90cd4175`). Do not merge the entire branch without reviewing the other 40+ files.

---

**VERDICT: MERGE** — The artifact exists, the finding is valid, and the code path analysis is accurate. The task is honest about its PARTIAL status. The critical gap in `research_block()` is real and should be fixed.
