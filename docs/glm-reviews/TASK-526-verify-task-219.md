# GLM Independent Verification: TASK-419

## Review metadata

| Field | Value |
|---|---|
| Task | TASK-419 — Notify Delivery Verification |
| Branch under review | origin/qwen-worker-6-r9 |
| Branch HEAD SHA (as named by task) | 6aa450938b035e4486a8e13096da83d0c2f0d067 |
| Verified HEAD SHA | `git rev-parse origin/qwen-worker-6-r9` → 6aa450938b035e4486a8e13096da83d0c2f0d067 ✅ MATCH |
| Review worktree | .qwen/worktrees/task-526-review (detached HEAD at 6aa45093) |
| Reviewer | GLM (TASK-526) |
| Date | 2026-09-29 |
| Task artifact kind | Finding (read-only investigation — result block IS the deliverable) |

## What TASK-419 claims

TASK-419 traced whether GLOBAL-destination notifications ever reach Slack. Its result block claims:

1. Seven producers write GLOBAL-destination notifications to the queue via `notify.notify()` → `notify.plan()`.
2. `scripts/notify_deliver_loop.py` is the ONLY automated delivery path.
3. The deliver loop refuses to start without `SLACK_LIVE=1` and `SLACK_BOT_TOKEN`.
4. No GLOBAL notification has been delivered to Slack.
5. The wiring is complete and correct; only the switch is off.

## Verification of each claim

### Claim 1: Seven producers → GLOBAL

**PARTIALLY VERIFIED. The named producers exist and route to GLOBAL, but the list is incomplete.**

Verified producers (file:line from the isolated worktree at 6aa45093):

| # | Producer | Cited location | Actual location | Event type | Routes to GLOBAL? |
|---|---|---|---|---|---|
| 1 | `_announce_failure()` | src/jobs.py:207 | src/jobs.py:207 ✅ | FAILED_JOB | ✅ (ROUTES line 235) |
| 2 | `_notify_death()` | src/supervisor.py:591 | src/supervisor.py:591 ✅ | FAILED_JOB | ✅ (ROUTES line 235) |
| 3 | `alert_if_needed()` | scripts/pool.sh:248 | scripts/pool.sh:245 ⚠️ | failed_job_needs_attention | ✅ (via FAILED_JOB routing) |
| 4 | pool watchdog (3 sites) | scripts/pool_watchdog.sh:139,189,239 | 139,189,239 ✅ | failed_job_needs_attention | ✅ |
| 5 | campaign approval | src/orchestrator.py:361 | src/orchestrator.py:361 ✅ | CAMPAIGN_APPROVAL_REQUIRED | ✅ (ROUTES line 216) |
| 6 | unmatched reply | src/inbound.py:421 | src/inbound.py:421 ✅ | UNMATCHED_REPLY | ✅ (ROUTES line 234) |
| 7 | reply protection | src/replywatch.py:309 | src/replywatch.py:309 ✅ | REPLY_PROTECTION_FAILED | ✅ (ROUTES line 237) |

**Omitted GLOBAL producers not named in the result block:**

| # | Producer | Location | Event type | Routes to GLOBAL? |
|---|---|---|---|---|
| 8 | report generation | src/web/api.py:4961 | REPORT_GENERATED | ✅ (ROUTES line 239) |
| 9 | campaign stopped | scripts/bison_watch_loop.py:348-349 | CAMPAIGN_STOPPED_EXTERNALLY | ✅ (ROUTES line 223) |
| 10 | blank content | scripts/bison_watch_loop.py:438-439 | CAMPAIGN_BLANK_CONTENT | ✅ (ROUTES line 224) |

Non-GLOBAL callers correctly excluded (verified): `digest.py:221` → OPERATIONS_DIGEST → STATUS; `api.py:4966` → REPORT_AVAILABLE → WORKSPACE; `bison_watch_loop.py:104` and `heyreach_watch_loop.py:63` → CAMPAIGN_MILESTONE → WORKSPACE.

**Line number accuracy:** 6 of 7 named sites match exactly. `pool.sh:248` is off by 3 (actual: 245). Minor — the function def is at line 215, the call at 245.

### Claim 2: `notify.notify()` → `plan()`, never `deliver()`

**VERIFIED.**

- `notify.notify()` at `src/notify.py:763` wraps `plan()` in a try/except (line 773: `return plan(...)`). It never calls `deliver()`.
- `plan()` at `src/notify.py:702` builds and stores a notification row with status `planned`. It never calls `deliver()`.
- `deliver()` at `src/notify.py:1096` is a separate function only reachable from outside the `notify` module.

### Claim 3: `notify_deliver_loop.py` is the only automated delivery path

**VERIFIED.**

`grep -rn "notify\.deliver" src/ scripts/` returns exactly three callers:

1. `scripts/notify_deliver_loop.py:72` — the automated sweep loop ✅
2. `src/digestwatch.py:250` — only for OPERATIONS_DIGEST rows (STATUS destination, not GLOBAL) ✅
3. `scripts/slack_replay_today.py:133` — manual tool, dry-run default, `--live` required ✅

The supervisor registration is confirmed at `src/supervisor.py:294-297`:
```python
{"name": "notify_deliver",
 "module": "scripts.notify_deliver_loop",
 "args": ["--interval", "60"], "interval": 60,
 "heartbeat": {"file": "notify-deliver.json"}},
```

### Claim 4: The deliver loop refuses without SLACK_LIVE

**VERIFIED.**

`scripts/notify_deliver_loop.py:106-109`:
```python
if not slack.live():
    print(f"REFUSED: {slack.LIVE_VAR} and {slack.KEY_VAR} must both be "
          f"set. Delivering nothing.")
    return 2
```

`slack.live()` at `src/providers/slack.py:338-352` requires BOTH `SLACK_LIVE` in ("1","true","yes","on") AND a non-empty `SLACK_BOT_TOKEN`.

`slack.post()` at `src/providers/slack.py:402-413` independently raises `SlackPostingNotEnabled` if `live()` returns False — a second guard.

### Claim 5: No GLOBAL notification has been delivered to Slack

**VERIFIED by construction.** The chain is: producers → `notify.notify()` → `plan()` → stored row with status `planned` → `work/notifications.jsonl`. The only automated path from `planned` to `sent` is `notify_deliver_loop.py`, which refuses to start. The queue location is confirmed at `src/notify.py:299-302`.

## Falsification attempts

### Can a notification reach Slack without SLACK_LIVE?

No. Two independent guards refuse:
1. `notify_deliver_loop.py:106` — exits with code 2 before entering the sweep loop.
2. `slack.post():410` — raises `SlackPostingNotEnabled` even if somehow called directly.

### Can any path bypass `notify_deliver_loop.py`?

Only `scripts/slack_replay_today.py`, which is deliberately unrun by default (dry-run, `--live` flag required, docstring states "DRY RUN IS THE DEFAULT"). Not an automated path.

### Could the accumulated backlog be dangerous?

Yes, and the result block correctly identifies this risk: if `SLACK_LIVE` is enabled without replaying the accumulated `planned` rows, the deliver loop will dump the entire backlog at once. `slack_replay_today.py` was built to handle this safely.

## Deletion risk

The branch deletes three TODO files vs master (all task files moved to DONE/REVIEW):
- `docs/qwen-tasks/TODO/TASK-391-*` (moved to DONE)
- `docs/qwen-tasks/TODO/TASK-419-*` (moved to DONE)
- `docs/qwen-tasks/TODO/TASK-439-*` (moved to REVIEW)

These are legitimate state moves, not destructive deletions. TASK-419 itself only changed its own task file (TODO → DONE with result block). No production code was modified by TASK-419.

## Scope drift

The branch `origin/qwen-worker-6-r9` carries extensive work beyond TASK-419 (TASK-400, TASK-423, TASK-427, TASK-391, TASK-913/914/915/916/917, and others — 43 files changed, +5887/-413 lines). TASK-419's own contribution is limited to moving its task file and recording the finding. Cherry-picking TASK-419 alone would be clean: only the task file move.

## Disposition

### Findings

| # | Finding | Severity | Evidence |
|---|---|---|---|
| 1 | Core finding is correct: no GLOBAL notification reaches Slack | Confirmed | Chain traced end-to-end in isolated worktree at 6aa45093 |
| 2 | Producer list incomplete: 10 GLOBAL producers exist, result block names 7 | Minor | `src/web/api.py:4961`, `scripts/bison_watch_loop.py:348,438` omitted |
| 3 | Line number off by 3 for pool.sh | Cosmetic | Cited 248, actual 245 |
| 4 | The wiring is complete and the refusal is real | Confirmed | Two independent guards verified |
| 5 | The backlog risk is correctly identified | Confirmed | `slack_replay_today.py` exists for safe replay |

### Recommendation

**MERGE** — TASK-419 is a read-only investigation whose finding is correct and verified. The core claim (no GLOBAL notification reaches Slack because the deliver loop refuses without `SLACK_LIVE`) is true. The incomplete producer list is a minor gap in an investigation task — it does not change the conclusion, because ALL producers are blocked by the same refusal. The finding is accurate, the risk is correctly identified, and the artifact (the result block) exists on the branch at the named SHA.

The three omitted producers (api.py report generation, bison_watch_loop campaign_stopped and blank_content) are worth noting for completeness but do not affect the operational conclusion: nothing reaches Slack until `SLACK_LIVE` is enabled.
