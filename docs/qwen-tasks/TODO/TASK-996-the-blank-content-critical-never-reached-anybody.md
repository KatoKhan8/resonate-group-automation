# TASK-996 — the blank-content CRITICAL never reached anybody, 1,410 times

STAGE: QUEUED
PRIORITY: P0

## Measured 2026-10-12 on `task-halt-idempotent-2026-10-12`

The blank-content halt on campaign 481 has fired **every 180 seconds since
2026-09-25**. `work/provider-writes.jsonl` holds **1,410 accepted
`bison.pause 481` rows** by `bison_watch_loop`, out of 1,417 pause rows in the
whole ledger.

**And the alert reached nobody, not once.** `work/notifications.jsonl` holds
exactly ONE `campaign_blank_content` row ever:

    campaign 497, 2026-09-23, status: failed, ids: {},
    last_error: AttributeError: 'str' object has no attribute 'get'

With `ids: {}` the `notification_id` is constant for the event type, and `plan`
is idempotent, so **all 1,410 firings collapsed onto that single failed 497 row
and planned nothing.**

So the control detected correctly, paused correctly, and told nobody for
seventeen days. The detection half worked; the reporting half was a no-op whose
silence was indistinguishable from "nothing to report".

Two consequences recorded for the record:

- CLAUDE.md line 122, "provider writes from us remain 0", is **false** and has
  been since 2026-09-25. Not edited here; stated so it is not relied upon.
- A merge is not a deploy. PID 14156 still runs the pre-fix code and will keep
  writing one pause every 180s until that watcher restarts.

## What is already fixed, and where

`task-halt-idempotent-2026-10-12` makes the halt fire once per condition and
passes `ids={campaign_id, condition}` so the notification is no longer
collapsed. 28 tests, mutation-verified.

## What this task is for — the part NOT fixed

The delivery `AttributeError: 'str' object has no attribute 'get'` is a separate
defect in the notify delivery path. It is the same shape as the one that broke
`quality._selected` on a hand-built evidence list: something is handing a string
where a dict is expected. Find it, fix it, and add a test proving a notification
whose delivery fails is reported as failed rather than silently absent.

## Acceptance

- The `AttributeError` traced to a file and line, and fixed.
- A test proving a failed delivery surfaces. An alert that fails to send must
  not look like an alert that had nothing to say.
- A check that a notification carrying `ids: {}` cannot silently coalesce every
  future instance of its event type onto one row.

## Constraints on this assignment — operator, 2026-10-12

Work in YOUR OWN worktree only.

- **Scope is the notify DELIVERY defect only.** The idempotency half is already
  fixed on `task-halt-idempotent-2026-10-12`; do not redo it and do not merge it.
- **No provider call, no network, no Slack post, no send.** Reproduce the
  delivery failure against a collector or a stub, never a live channel.
- **Do not read or touch old campaigns** (274/327/328/352 or any live campaign).
- **Do not change the order or the behaviour of the existing production flow**
  beyond fixing the stated `AttributeError` and the `ids: {}` coalescing.
- **Do not merge, and do not push to master.** Commit on your own worker branch.
- **One suite at a time.** Other lanes are live. Run only the modules you touch,
  never `unittest discover`, never `scripts/run_suite.py`.
- **Never `git stash`** — worktrees share one stash.

## What a finished result looks like

1. The `AttributeError: 'str' object has no attribute 'get'` traced to a FILE
   AND LINE, and fixed. The error is in the notify delivery path; the one
   recorded instance is the `campaign_blank_content` row for campaign 497 on
   2026-09-23 in `work/notifications.jsonl`. Note the same error signature
   appeared elsewhere from a hand-built list where dicts were expected, so look
   for something handing a string where a mapping is read.
2. **A positive control proving a failed delivery is REPORTED as failed** rather
   than silently absent. Make delivery fail, and show the test goes red if the
   failure is swallowed. This is the whole point: 1,410 firings collapsed onto
   one failed row and nobody was ever told.
3. A test proving a notification carrying `ids: {}` cannot coalesce every future
   instance of its event type onto a single row.
4. The test modules you ran, with their actual output pasted in `REPORT.md`.
