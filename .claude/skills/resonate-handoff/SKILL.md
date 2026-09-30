---
name: resonate-handoff
description: Write a Resonate OS handoff/checkpoint document so a fresh session on another machine can resume. Use when ending a session, running low on context, about to /clear or compact, when the operator asks for a handoff or checkpoint, or before pausing an autonomous run. Enforces push-before-write, remote-SHA verification, running-agent inventory, open decisions, critical path, and the next session's first actions.
---

# Handoff

Canonical rules: `CLAUDE.md` **"Durable state: GitHub is the source of truth"**,
`docs/OPERATING-MODE.md` invariant **0**, registry **§0a**, and **DEFINITION OF
DONE**. Recent examples to match in shape and length:
`docs/HANDOFF-2026-09-30-PRODUCTION.md` (compact, ~100 lines) and
`docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT-MINIMUM-CLAUDE.md`.

**The test the document must pass:** a fresh session on a different computer,
with a clone and the secrets supplied separately, can read the repository and say
what happened and what to do next. Anything that fails that test is not state, it
is scrollback.

## NEVER /clear OR COMPACT WHILE AN OPERATION IS ACTIVE

An operation is active if a provider write, a send, a campaign activation, a
live run, a dispatched worker, an uncommitted result or an unpushed branch is in
flight. Finish it, or check it in and record it, first. An unplanned shutdown
already destroyed a night of terminal state here once and nearly destroyed two
completed results.

## Step 1 — push first, then write the document

Write nothing until the tree and every branch are durable. **Commit and push are
two commands, never one** — a combined `commit && push` has been refused by the
harness classifier while git never ran, and the transcript then lied about the
remote.

    git status --short
    git branch -vv                       # ahead/behind for every branch
    git fetch origin
    git push origin <branch>             # each branch with unpushed work
    git rev-parse master origin/master   # must agree
    py -3 scripts/durable_state.py       # regenerates LEDGER + QUEUE-MANIFEST

A running or unreviewed worker branch is pushed **to its own branch and left
there** — never merged to master to make it durable. Durability and integration
are different problems.

`durable_state.py` exits non-zero when a branch holds unpushed work or a worktree
is dirty. **That exit code is a durability alarm, not a crash.** Do not write the
handoff until it is clean or the exception is named in the document.

Never commit `.env`, a key, a token or a credential; scan the staged diff.
Suite logs, verbose output and JSON dumps go **outside the repository** (scratch
dir or `%TEMP%`) — `tests/test_fixture_hygiene.py` scans untracked files, and a
`git add -A` next to a test log has already nearly published real prospect data.

## Step 2 — the document

`docs/HANDOFF-<date>-<slot>.md`. Every state line names its authority and is
**derived at write time**, never copied from the previous handoff. Prose in this
repository goes stale by design: the CLAUDE.md pointer was once two days and
forty merges out of date.

### Production state — derive each line

    master = origin/master     git fetch && git rev-parse master origin/master
    provider writes            the write-interceptor ledger, interceptor proven
                               to fire (NOT live=False, NOT "no error in a log")
    prospect-facing sends      the provider's own events (NOT our ledger:
                               ledger absence is never absence of a send)
    campaign activations       provider readback
    enrolments                 provider readback
    sending.live               killswitch.workspace_state('<client>')
    approved artifact          the record and its approval hash
    canary                     which gate it is standing at

Add the line **"Nothing was sent by this work"** when true, in exactly that
sense — never "nothing was ever sent" (OPERATING-MODE decision 24).

### Current candidate and first blocker

One block: CURRENT CANDIDATE · FIRST BLOCKER · OWNER · CLASSIFICATION. If work is
HELD, say whether it is thin evidence, a writer failure, or a genuine
contradiction between two canonical rules — the three are acted on differently.

### Running agents and workers

    py -3 scripts/claim_task.py --status
    py -3 scripts/task_registry.py

Per worker: task, state, branch, whether the worktree is on a stale SHA, whether
it has unpushed or diverged work. **A claim's recorded PID is the claiming
process, not the worker** — the authority is the process *and* its heartbeat.
Name any dispatch that was aborted and why, so the next session does not repeat
it. Say explicitly which branches must be reset before dispatching again.

### Open operator decisions

One line each, in the 🔴 format's terms: what is blocked, option A, option B,
the recommendation. Nothing resumes, activates, enrols, attaches or sends without
an explicit `APPROVED`, and a decision already recorded in OPERATING-MODE is not
re-asked.

### Critical path and what changed

The current critical path exactly as OPERATING-MODE decision 20 states it, and
a short list of what actually changed this session — commit SHA plus one line
each. A commit that is not on `origin/master` is named as a branch artifact, not
as done: **ancestry on `origin/master` is the authority, not a task file saying
DONE**.

### Red tests and known failures

Name the outstanding ones. Do not wave them through, and do not report a test
count as a verdict. **A run with no `Ran N tests` line is an absent measurement,
not a failing suite** — if a suite died, clean `%TEMP%` of `rga-*` debris and
re-run before concluding anything.

### The next session's first actions

Three to five imperatives, in order, each executable with no conversation
context. Start with the derivation commands, then the first real piece of work.
Say what is explicitly **not** to be started (OPERATING-MODE decision 15) so the
next session does not reopen a closed question.

## Step 3 — push the handoff

Commit, push, and verify `git rev-parse master origin/master` agree. A handoff
that exists only locally is exactly as lost as never writing it.

## What a handoff may not claim

A handoff saying "done, artifact verified" is not proof — measured 2026-09-26,
three of thirteen such artifacts did not exist on master. Write only what you
derived, name the authority, and mark anything unread as UNKNOWN.
