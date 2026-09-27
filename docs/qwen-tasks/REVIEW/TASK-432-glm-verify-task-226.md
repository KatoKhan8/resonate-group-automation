PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-432 — GLM independent verification: TASK-226, on its exact branch head

**Standing operator rule, 2026-09-27: every branch reaching REVIEW gets a GLM
verdict dispatched against its EXACT head SHA immediately.** This task is that
verdict for one result. Follow `docs/GLM-REVIEW-PROTOCOL.md` — the standing
contract for review triggers, the isolated-worktree rule, falsification over
confirmation, and the eight dispositions every finding must carry. Read it
yourself; this file names the target, not the procedure.

## Target — review THIS, and nothing else

    task            TASK-226
    branch          qwen-worker-8-r28
    branch HEAD SHA 36a4ce61b454187772e78daac49b08282380193e

**A VERDICT THAT DOES NOT NAME THE BRANCH HEAD SHA IT REVIEWED IS VOID.** Three
of five GLM verdicts on 2026-09-27 were void on exactly that, and one was void
because it read `master` and reported on a branch: it announced "still in TODO"
while the work had sat in REVIEW on a branch for three hours. **Check out
`36a4ce61b454187772e78daac49b08282380193e` in an isolated worktree and review that tree.** Do not review master. Do
not review the branch name and assume it still points where this file says —
verify with `git rev-parse` and, if the branch has moved, say so and review
`36a4ce61b454187772e78daac49b08282380193e` anyway, because that is the artifact this verdict is about.

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
5. **Would merging it DELETE anything?** `git diff master...36a4ce61b454187772e78daac49b08282380193e --stat`. This
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

Write the verdict to `docs/glm-reviews/TASK-432-verify-task-226.md`,
commit it and push it. A finding that exists only in terminal output does not
exist.

---

## RESULT

**TASK:** TASK-432 — GLM independent verification of TASK-226

**STATUS:** DONE

**COMMIT:** (this commit)

**TESTS:** 18/19 journal tests pass on the branch HEAD. 1 failure is environmental (no `work/` dir in worktree; passes on master). 8/8 new index tests pass. Mutation test confirmed falsifiability.

**FILES CHANGED:**
- `docs/glm-reviews/TASK-432-verify-task-226.md` — the verdict

**FINDINGS:**

1. **Artifact exists and is consumed.** `src/queuejournal.py` has the offset index. `src/store.py` calls `queuejournal.replay()`, `append()`, `compact()`, `should_compact()`, `path_for()` — all gated by `QUEUE_JOURNAL` flag. The wiring was NOT changed on this branch (already exists on master).

2. **Tests are falsifiable.** Mutation test: changed index to store FIRST offset instead of LAST. `test_index_points_at_last_entry_not_first` correctly failed with `AssertionError: 'verified' != 'dropped'`. The test caught the exact bug the index exists to prevent.

3. **Index is DERIVED and rebuildable.** Three tests prove corrupt/absent/mismatched index handling. The rebuild matches the incremental maintenance.

4. **QUEUE_JOURNAL stays OFF.** Verified at `store.py:427`.

5. **No production files deleted.** `git diff --diff-filter=D` returns only a task-file move.

6. **Scope drift present.** Branch includes TASK-231 changes (`gather.py`, `providers/__init__.py`, `test_http_timeout_*`, `test_prefetch_headcount.py`). TASK-226 files are cleanly cherry-pickable (commits `590c35ef`, `a2f49494`, `67d79e49`, `8b50d8e4`).

7. **Benchmark 5000-record figure is MODELLED**, not measured. 50 and 500 are MEASURED. Scripts label correctly.

**DISPOSITION: MERGE** — with cherry-pick to separate TASK-226 from TASK-231.

**RISKS:**
- The `replay()` function reads entries twice (once for records, once for digest check). Minor inefficiency, not a bug.
- Index write atomicity on Windows: a torn write is detected and triggers rebuild. Safe but adds latency.
- The index file (`queue.jsonl.journal.idx`) needs explicit coverage in the production write barrier (flagged in TASK-226 result block as follow-up).

**RECOMMENDED CLAUDE ACTION:**
1. Cherry-pick TASK-226 commits separately from TASK-231.
2. Decide whether to turn QUEUE_JOURNAL on (performance case is strong: 0.55x at 500 records).
3. Decide whether the index file needs explicit write-barrier coverage.
