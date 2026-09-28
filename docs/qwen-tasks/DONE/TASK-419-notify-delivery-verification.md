PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-419 — Notify Delivery Verification (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `notify-delivery-verification`.

Trace whether a `src/notify.py` GLOBAL-destination notification (e.g.
`failed_job_needs_attention`, the kind `pool.sh`'s CRITICAL alert now
writes) is ever actually delivered to Slack by a live consumer, or whether
it only ever reaches the stored notification queue. Name the consumer if
one exists, with file:line, or report plainly that none was found running.
Acceptance: either a real delivered test notification traced end to end to
Slack, or an honest "no consumer found" with the queue location named.

## RESULT BLOCK

- **STATUS**: DONE
- **COMMIT SHA**: 77afc4062eb5bb72bcc8b803ebee40310ed13a3d
- **TESTS**: Read-only investigation; no tests run. All findings are grep-traced call chains.
- **FILES CHANGED**: docs/qwen-tasks/RUNNING/TASK-419-notify-delivery-verification.md (this file, state move TODO → RUNNING → DONE)
- **ARTIFACT KIND**: Finding (investigation task — the result block IS the deliverable)

### FINDINGS

**No GLOBAL-destination notification is ever delivered to Slack in this build.** The consumer exists but refuses to run.

#### The chain, traced end to end

**1. Producers** — seven call sites write GLOBAL-destination notifications to the queue via `notify.notify()` → `notify.plan()`:

| Producer | File:Line | Event type | Destination |
|---|---|---|---|
| `_announce_failure()` | `src/jobs.py:207` | `FAILED_JOB` | GLOBAL, ACTION_REQUIRED |
| `_notify_death()` | `src/supervisor.py:591` | `FAILED_JOB` | GLOBAL, ACTION_REQUIRED |
| `alert_if_needed()` | `scripts/pool.sh:248` | `failed_job_needs_attention` | GLOBAL, ACTION_REQUIRED |
| pool watchdog (3 sites) | `scripts/pool_watchdog.sh:139,189,239` | `failed_job_needs_attention` | GLOBAL, ACTION_REQUIRED |
| campaign approval | `src/orchestrator.py:361` | `CAMPAIGN_APPROVAL_REQUIRED` | GLOBAL, ACTION_REQUIRED |
| unmatched reply | `src/inbound.py:421` | `UNMATCHED_REPLY` | GLOBAL, ACTION_REQUIRED |
| reply protection | `src/replywatch.py:309` | `REPLY_PROTECTION_FAILED` | GLOBAL, CRITICAL |

All of these call `notify.notify()` which calls `notify.plan()` (`src/notify.py:703`), which writes a row with status `planned` to the notification store and stops. `notify.notify()` never calls `deliver()`.

**2. The consumer** — `scripts/notify_deliver_loop.py` is the ONLY automated delivery path:

- Registered as a supervisor monitor at `src/supervisor.py:294-297` (name: `notify_deliver`, module: `scripts.notify_deliver_loop`, interval: 60s)
- Its `sweep()` function (line 65) loads PLANNED rows and calls `notify.deliver()` (line 72)
- `notify.deliver()` (`src/notify.py:1096`) calls `slack.post()` (`src/notify.py:1117`)

**3. The refusal** — `notify_deliver_loop.py:103-105` checks `slack.live()` at startup:

```python
if not slack.live():
    print(f"REFUSED: {slack.LIVE_VAR} and {slack.KEY_VAR} must both be "
          f"set. Delivering nothing.")
    return 2
```

`slack.live()` (`src/providers/slack.py:339`) requires BOTH `SLACK_LIVE=1` AND a non-empty `SLACK_BOT_TOKEN`. In this worktree `config/.env` does not exist (only `.env.example`, which has `SLACK_LIVE=` empty). The module docstring in `src/notify.py:63` states this directly: *"Nothing here posts."*

**4. Other delivery paths** — neither delivers GLOBAL notifications in production:

- `src/digestwatch.py:250` calls `notify.deliver()` but only for `OPERATIONS_DIGEST` rows (STATUS destination, not GLOBAL)
- `scripts/slack_replay_today.py` is deliberately unrun (dry-run default, `--live` required, docstring says "DRY RUN IS THE DEFAULT")

#### Queue location

Notifications are stored at `work/notifications.jsonl`, derived from `notify.path()` (`src/notify.py:283`) which places the file alongside `store.queue_path()`.

#### Bottom line

The wiring is complete and correct: producers plan, the deliver loop sweeps, `notify.deliver()` calls `slack.post()`. But the deliver loop refuses to start without `SLACK_LIVE=1` and `SLACK_BOT_TOKEN`, and neither is set. Every GLOBAL-destination notification sits at status `planned` in `work/notifications.jsonl` and reaches no Slack channel.

- **FINDINGS**: See above. The consumer (`scripts/notify_deliver_loop.py`) EXISTS and is wired into the supervisor, but REFUSES to run because `SLACK_LIVE` is not set. No GLOBAL notification has been delivered to Slack.
- **RISKS**: If `SLACK_LIVE` is enabled without replaying the accumulated `planned` rows, the deliver loop will dump the entire backlog into the ops channel at once. `scripts/slack_replay_today.py` was built to handle this safely (date-bounded replay) but is itself unrun.
- **RECOMMENDED CLAUDE ACTION**: Decide whether to enable `SLACK_LIVE` and, if so, whether to replay the backlog through `slack_replay_today.py --live --since <date>` or let the deliver loop post everything. The plumbing is ready; only the switch is off.
