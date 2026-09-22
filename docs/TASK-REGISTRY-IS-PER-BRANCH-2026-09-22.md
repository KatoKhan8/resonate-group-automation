# The task registry is per-branch, so there are 219 of them

**Answer to a direct question from the operator, 2026-09-22:** *do the infra
session's Qwen tasks run through the same pool and task registry the
production session and the Slack agent read?*

**No. They do not, and the problem is structural rather than a
misconfiguration.**

---

## 1. The measurement

`docs/qwen-tasks/{TODO,RUNNING,DONE}/` is a set of FILES INSIDE THE
REPOSITORY. Files inside a repository are branched. So the registry is
branched, and there is one registry per branch:

    master                     RUNNING: TASK-192
    infra                      RUNNING: TASK-192, TASK-262
    qwen-worker-2-task-261     RUNNING: TASK-192, TASK-261
    qwen-worker-4-task-263     RUNNING: TASK-192, TASK-262, TASK-263
    qwen-worker-r57            RUNNING: TASK-192, TASK-250

`scripts/task_registry_scan.py`, run across every branch:

    261 tasks across 219 branches; 192 DISAGREE between branches.

**The agent is not wrong.** It reads the production worktree, master's
RUNNING holds only TASK-192, and it reports exactly that. It is *true of
master* and *false of the system* — five tasks were in flight at that moment.

## 2. Why this is not a misconfiguration

Claim state — who is working on what, right now — is **runtime state**. It
changes minute by minute and it has exactly one correct value at any instant.

Code is **versioned state**. It is branched on purpose, so that two people can
hold different versions of it at once.

Storing the first in the second means the registry inherits branching, and
branching is precisely the property a claim must not have. CLAUDE.md already
draws this line for everything else:

> *Git holds what reconstructs the system: code, tests, docs, config SCHEMAS,
> checkpoint and handoff state. Production runtime state and sensitive
> datasets get their own durable storage and never git.*

The task registry is on the wrong side of that sentence, and it has been since
it was created.

## 3. What it has already cost — once, measured

**TASK-250.** It was claimed on `qwen-worker-r57` (`61a2bc60`), the worker
edited fixtures (`126dcfa1`), then died. The file stayed in that branch's
`RUNNING/` with no result block.

`master`'s registry still showed TASK-250 in `TODO`. The infra session read
that view, correctly concluded it was unstarted, merged the stalled work —
and regressed the suite from 82 to 123 failures before measuring and
reverting.

The scanner reports that exact shape today:

    TASK-250  {'TODO': N, 'RUNNING': 1}  <-- DISAGREES
          RUNNING  qwen-worker-r57
          TODO     master, infra, ...

**One registry would have shown it as claimed and none of that would have
happened.**

## 4. The fix — a claim ledger outside the versioned tree

`work/task-claims.jsonl`, append-only, beside every other piece of runtime
state, reached through one module.

    {"task": "TASK-263", "state": "RUNNING", "by": "infra/qwen-4",
     "branch": "qwen-worker-4-task-263", "at": "...", "pid": 12345}

Why `work/`:

- **It is already the shared runtime-state directory.** All three sessions
  and all eight Qwen worktrees resolve it to the same physical path, because
  they are worktrees of one repository on one machine.
- **It is gitignored**, so it cannot be branched, which is the entire point.
- **`store.lock()` already exists** and is proven cross-process on Windows.
  A claim is a read-modify-write and needs exactly that.
- **It moves with `store.use_directory()`** if it is added to
  `STATE_OVERRIDES`, so tests cannot write the real one.
- It survives the server migration unchanged — §4 of
  `docs/SERVER-MIGRATION-PLAN.md` puts `work/` on the mounted volume.

`claim(task, by)` refuses if the task is already RUNNING and the holder's pid
is alive — that is `src/singlewalker.py`'s existing contract, and it should be
reused rather than rewritten.

**The markdown files stay.** They are the task's CONTENT — the brief, the
falsifiable requirements, the result block — and that genuinely is versioned
state that belongs in git. What moves out is only the *stage*: which directory
the file sits in becomes a row in the ledger instead.

### Why not "have the agent read both"

It works today and breaks on the third branch. There are 219. The scanner in
§5 is that patch, built deliberately as a *read-only* stopgap rather than as
the answer.

## 5. What exists as of this commit

`scripts/task_registry_scan.py` — read-only, no change to anything, works now:

    py -3 scripts/task_registry_scan.py --running     who claims what, where
    py -3 scripts/task_registry_scan.py --conflicts   only the dangerous rows

It exits non-zero when any task's stage differs between branches, so it can
gate a dispatch. **Run it before dispatching anything**, in any session.

It is the read side only. It makes the truth *discoverable*; it does not make
it *single*.

## 6. What I am asking the production session to decide

1. **Adopt the claim ledger** (§4). It is a change under `work/` and to
   `store.STATE_OVERRIDES`, and `work/` belongs to the production session, so
   I have not built it.
2. **Point the Slack agent at the ledger** once it exists, instead of at
   master's directory listing. Until then, pointing it at the scanner would
   at least make its answer true.
3. **Decide what happens to `qwen-worker-r57`'s TASK-250 claim**, which is
   still RUNNING on that branch with a dead worker. It is superseded by
   TASK-262 but nothing has released it.

Until (1) lands, the operating rule is: **run the scanner before dispatching,
and treat RUNNING anywhere as RUNNING everywhere.**
