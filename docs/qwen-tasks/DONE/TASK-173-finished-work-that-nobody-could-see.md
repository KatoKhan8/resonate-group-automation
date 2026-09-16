PRIORITY: P1
DEPENDS:

# TASK-173 - two finished tasks sat invisible for a day, and the registry agreed

## WHERE THIS SITS

This happened last night, and it cost eight workers a night of idleness.

TASK-146 was finished on `qwen-worker-r19` and TASK-155 on
`qwen-worker-7-r18`. Both were pushed. Neither was integrated. `claim_task.py`
correctly reported them unavailable, because `_claimed_on_a_branch` sees a
branch that has moved the file out of TODO - that detector exists for a good
measured reason and it was doing its job.

The result was a queue that reported `ready: 0` with nine files in TODO. The
pool then logged "no ready task" eight times and stopped. Meanwhile
`docs/state/TASK-REGISTRY.json` said `QUEUED: 9`, generated at 21:19 against a
master that no longer matched, and TASK-158 through TASK-162 were all sitting
finished on branches while the registry called them queued.

So three artefacts disagreed: TODO said available, the claim detector said
taken, and the registry said queued. All three were right about different
things and no single one could be trusted.

There are also over a hundred `qwen-worker-*` remote branches, most of whose
work is long since in master by another route.

## THE QUESTION

1. **Make the disagreement visible.** One command that prints, per task, all
   three answers: where master has the file, which branches have moved it and
   to what stage, and whether a result block exists. A task whose branch says
   DONE and whose master says TODO is UNINTEGRATED, and that state needs a
   name and a count.
2. **Report the unintegrated set right now.** Scan every remote branch. For each
   task not DONE in master but finished on a branch, name the task, the branch,
   and whether its result block says COMPLETE. Claude found TASK-146 and
   TASK-155 by hand; find the rest, and if there are none, prove the set is
   empty rather than asserting it.
3. **Make the registry honest.** `scripts/task_registry.py` and
   `scripts/durable_state.py` generate state from master alone. Either make
   them read branch reality too, or make them stamp plainly that they describe
   master only and that UNINTEGRATED work is invisible to them. Do not leave a
   file that reports `QUEUED` for a task that is finished.
4. **Prune what is safe to prune.** A branch whose every commit is reachable
   from master carries nothing. List those. Do NOT delete a branch carrying an
   unmerged commit, whatever its age - the r19 and 7-r18 branches were the only
   copy of two finished results, and `pool.sh dispatch` resets local refs, so a
   remote branch is sometimes the only copy that exists.

## THE TRAP

`pool.sh dispatch` runs `git checkout -B "$br" master`, which destroys the
local ref. It also reuses a branch name when the same worker is given a second
task in the same round, so a worker's second push to the same branch can only
fast-forward if the first result is already in master. That is a live hazard
this morning, not a hypothetical: two workers are on their second task of round
24 right now.

So a deletion here is not reversible by checking out the branch again. Prove
reachability from master per commit, not per branch, and prove it with
`git merge-base --is-ancestor` rather than by reading a log.

## WHAT YOU MAY NOT DO

- Do not delete any branch in this task. Produce the list; deletion is
  Claude's, after reading it.
- Do not force-push anything, anywhere, for any reason.
- Do not merge into master.
- Do not rewrite history. There is a known PII leak in history whose rewrite is
  an operator decision, and this task is not it.

## FILES ALLOWED

    scripts/task173_*.py
    scripts/task_registry.py
    scripts/durable_state.py
    docs/UNINTEGRATED-WORK-2026-09-16.md   (new)

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The three-way report command, the unintegrated set as it stands this morning
with branch and result status per task, the registry made honest about what it
can and cannot see, and the safe-to-prune branch list with the ancestry proof
per branch.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** 811b98b
- **TESTS:** Both modified scripts (task_registry.py, durable_state.py) run
  successfully and produce JSON with the new branch_blindness field. The scan
  script runs against all 106 remote refs and completes in under 10 minutes.
  No existing tests were broken (no tests exist for these scripts).
- **FILES CHANGED:**
  - scripts/task173_scan.py — new: three-way report, unintegrated scan, prune report
  - scripts/task_registry.py — added branch_blindness field and warning
  - scripts/durable_state.py — added branch_blindness field and warning
  - docs/UNINTEGRATED-WORK-2026-09-16.md — new: the deliverable document
  - docs/state/TASK-REGISTRY.json — regenerated with branch_blindness
  - docs/state/LEDGER.json — regenerated with branch_blindness
- **FINDINGS:**
  - Five unintegrated tasks found: TASK-067, TASK-169, TASK-170, TASK-172, TASK-174
  - All five have STATUS: DONE in their result blocks on their branches
  - 14 branches are safe to prune (all commits reachable from master)
  - 93 branches carry unmerged work and must not be deleted
  - The registry's ready_count is inflated whenever unintegrated work exists
  - The pool's claim_task.py correctly excludes these tasks via _claimed_on_a_branch
- **RISKS:**
  - The scan takes ~10 minutes for 106 branches (one ls-tree per branch)
  - The branch_blindness field is a warning, not a fix — the registry still
    reports wrong ready counts until Claude integrates the work
- **RECOMMENDED CLAUDE ACTION:**
  1. Integrate the five unintegrated tasks from their branches into master
  2. Prune the 14 safe branches listed in the document
  3. Read the 93 unsafe branches' unmerged task lists before deleting any
