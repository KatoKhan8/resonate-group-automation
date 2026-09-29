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

**STATUS:** DONE
**COMMIT SHA:** 83bbdb71
**TESTS:** N/A — read-only verification task, verdict is the deliverable
**FILES CHANGED:**
- `docs/glm-reviews/TASK-529-verify-task-219.md` — the verdict document (NEW)

**ARTIFACT KIND:** document (independent verification verdict)

**FINDINGS:**

1. **Branch HEAD SHA confirmed:** `git rev-parse origin/qwen-worker-6-r9` returned `6aa450938b035e4486a8e13096da83d0c2f0d067` — matches task file exactly.
2. **Artifact exists:** `docs/TASK-423-FAILURE-TAXONOMY.md` (352 lines) at the reviewed SHA. Created by commit `f933ec7a`, updated by `46327108`.
3. **Pareto math verified:** 13+13+4+3+2+2 = 37. Each lead appears exactly once.
4. **`{firstName}` mechanism verified at cited lines:**
   - `copystages.py:332` — contains `{firstName}` (camelCase) ✓
   - `copyprompts.py:343` — contains `{firstName}` (camelCase) ✓
   - `cadence.py` — uses `{first_name}` (snake_case) throughout ✓
   - `generate_campaign.py:477` — LinkedIn text stored directly from model output, no render() call ✓
   - `copylint.py:481` — UNRENDERED_RE matches `{firstName}` ✓
5. **No production deletions:** `git diff master...6aa45093 --diff-filter=D --name-only -- src/ tests/` returns empty.
6. **Scope drift:** Branch carries 40 commits from multiple tasks (TASK-400, TASK-246, TASK-439, TASK-445, TASK-455, TASK-461). TASK-423's own work is 3 commits touching only 2 docs files — cleanly cherry-pickable.
7. **Consumption:** Document is referenced in integration queue, operating mode, and handoff docs. No code consumption expected for analysis task.
8. **No PII committed:** Uses R## identifiers only.

**RECOMMENDATION:** MERGE via cherry-pick of commits `f933ec7a`, `46327108`, `d76f860d`.

**RISKS:**
- Source data (`fifty-data.json`) missing — taxonomy reconstructed from posted HTML/XLSX. Task was transparent about this.
- 8 "copylint-only" leads classified from TASK-342 re-lint numbers, not direct measurement.

**RECOMMENDED CLAUDE ACTION:** Cherry-pick the 3 TASK-423 commits. The analysis is sound and the fix list is actionable.
