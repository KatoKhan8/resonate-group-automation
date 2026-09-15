# Orchestration: zero idle, atomic claiming, and a backlog that outlasts it

Standing policy, set by the operator 2026-09-15. It survives `/clear` and a
machine restart because it lives here and in the scripts, not in a context
window.

---

## 1. THE ZERO-IDLE RULE

    8 workers available  ->  8 useful independent tasks running

When a worker finishes: collect its result, commit and push its branch, put
the result in the review queue, and **immediately give that worker the next
task.** Do not wait for review. Claude's review and Qwen's execution run in
parallel; a worker that waits for a reviewer is a worker not working.

`scripts/pool.sh loop` implements this. Each sweep gives every free worker the
highest-priority ready task. It never touches master - review and integration
stay Claude's.

## 2. ATOMIC CLAIMING, AND WHY WORDING WAS NOT ENOUGH

On 2026-09-15 six of eight workers independently selected the same task and
four produced the same answer. The dispatch prompt had named one task per
worker. `QWEN.md` outranked it by saying "take the task Claude named, OR the
highest-priority file in TODO".

The wording was fixed. **That alone would not have been enough.** Two workers
that both READ a TODO directory a millisecond apart both see the task as free,
because reading a directory claims nothing. The claim has to be an atomic
write that exactly one racer can win.

`scripts/claim_task.py` uses `os.open(O_CREAT | O_EXCL)` - atomic on Windows
and POSIX. Proven under load: eight concurrent claimers, one winner, seven
refused.

Two details that are load-bearing:

- **Claims resolve to the MAIN worktree by absolute path.** The eight
  worktrees each have their own `docs/` and `work/`; a claim written into a
  worker's own tree coordinates nothing, which is the bug itself.
- **`--reap` is disabled, deliberately.** The pid in a claim belongs to the
  process that WROTE it, and Claude claims on a worker's behalf before
  launching it, so that process has always already exited. A pid-based reap
  would report all eight live claims as dead and release every one - handing
  each task to a second worker and reproducing the collision with more
  confidence behind it. Releasing is explicit, per task; the pool loop
  releases from the subshell that actually knows its worker finished.

## 3. THE BACKLOG MUST OUTLAST THE POOL

    8 workers  ->  maintain >= 16 READY tasks
    overnight  ->  prefer 20-30

`scripts/task_registry.py` writes `docs/state/TASK-REGISTRY.json` carrying
TASK_ID, STATUS, PRIORITY, WORKER, CLAIMED_AT, DEPENDENCIES, BRANCH, RESULT and
REVIEW_STATUS. Every field is DERIVED - from the task files, from git, and from
the claim directory. **It exits non-zero when fewer than 16 tasks are ready**,
so idleness is visible before it happens rather than after.

States: `QUEUED`, `CLAIMED`, `RUNNING`, `AWAITING_REVIEW`, `REWORK`, `BLOCKED`,
`DONE`. A task in TODO with a live claim is CLAIMED, not QUEUED - a worker
already holds it. The directory is durable and committed; the claim is atomic
and machine-local. Neither alone says whether a task is free.

Claude replenishes continuously. **Every discovered defect, unanswered
production question and useful analysis becomes a task.** A finding that stays
in a commit message is a finding nobody will act on.

## 4. PRIORITY - RESEARCH MUST NOT BECOME AN EXCUSE

    P0   unblock real production
    P1   validated campaigns, cohorts, sender assignment, provider write
    P2   learning that directly improves production
    P3   quality and classifier improvements
    P4   broader research and infrastructure

When a P0 blocker clears, redirect capacity immediately toward campaign
completion, cohort creation, lead batches, sender assignment, provider write,
readback, live.

**There is almost never a reason for seven workers to idle because one P0
blocker exists.** Historical outcome analysis, cadence work, classifier
improvement, signal discovery, cohort clustering, enrichment quality, copy and
sequence QA, duplicate detection, provider capability analysis, readback
verification, tests and documentation are all independent of any single
blocker. But research is not a substitute for shipping, and a run that
improves architecture while creating zero production has failed.

## 5. CLAUDE ORCHESTRATES; QWEN EXECUTES

Claude's scarce capacity goes on deciding, prioritising, reviewing,
integrating, resolving ambiguity, and protecting production. If Qwen can
reasonably investigate, measure, generate, test or implement it, delegate it.

**Review is not a formality.** Of seventeen integrations on 2026-09-14, five
needed material correction - a taxonomy that inverted refusals into positives,
a branch that would have reverted four files, a precision number that demanded
a pattern be deleted. On 2026-09-15 a worker reported LinkedIn variant
diversity as "achieved" when re-measurement showed the openings were 4:1
collapsed and most of the apparent gain came from a detector fix rather than
from the copy.

So: **take named files, never merge a worker branch wholesale**, re-run the
measurement rather than believing the result block, and run the NEIGHBOURS of
any test a worker says is green.

## 6. WHAT A WORKER MAY NEVER DO

Provider writes of any kind. Sends. Campaign creation or activation. Adding
leads. Merging to master. Committing `config/.env`, a key or a token.
Committing unhashed PII - prospect or seat-holder. Weakening a gate, a lint
rule or a sender limit to make something pass or to gain volume. Reading a
test verdict through a pipe. Reporting a predicted result instead of a
measured one.

A worker that hits a boundary writes it under FINDINGS, commits, pushes, and
stops. **That is a good outcome, not a failure.**
