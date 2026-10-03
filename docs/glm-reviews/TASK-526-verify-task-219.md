# GLM Independent Verification: TASK-419

**Review target:** TASK-419 — Notify Delivery Verification  
**Branch:** origin/qwen-worker-6-r9  
**Branch HEAD SHA:** 6aa450938b035e4486a8e13096da83d0c2f0d067  
**Review worktree:** .qwen/worktrees/task526-review (detached at exact SHA)  
**Review date:** 2026-10-04  
**Reviewer:** GLM (Qwen Code session)

---

## Verdict: **CLOSE** — Finding verified, already observable on master

TASK-419 is a pure investigation task. No code changes. The artifact is the result block itself, and the finding is correct: **no GLOBAL-destination notification reaches Slack in this build** because the deliver loop refuses without `SLACK_LIVE=1` and `SLACK_BOT_TOKEN`.

The finding is already observable on master — the code is byte-identical. Merging the task file move from TODO/ to DONE/ is cosmetic and does not change production behavior.

---

## 1. Does the artifact exist on this ref?

**Yes.** The task file exists at `docs/qwen-tasks/DONE/TASK-419-notify-delivery-verification.md` on the branch at SHA 6aa450938.

**Artifact kind:** Finding (investigation task — the result block IS the deliverable).  
**FILES CHANGED:** Only the task file itself (state move TODO → RUNNING → DONE).  
**Production code changes:** Zero. Confirmed by `git diff master...6aa450938b035e4486a8e13096da83d0c2f0d067 -- src/ scripts/` returning empty for all production files.

---

## 2. Existence is not function — is the chain consumed?

**The chain is traced correctly and the finding is valid.** The task does not claim to have changed anything; it claims to have observed that the wiring is complete but the switch is off. This is verified.

### The chain, independently traced

**Producers (7 call sites write GLOBAL-destination notifications):**

| Producer | File:Line (verified) | Event type | Destination |
|---|---|---|---|
| `_announce_failure()` | `src/jobs.py:197` (task says 207) | `FAILED_JOB` | GLOBAL, ACTION_REQUIRED |
| `_notify_death()` | `src/supervisor.py:585` (task says 591) | `FAILED_JOB` | GLOBAL, ACTION_REQUIRED |
| `alert_if_needed()` | `scripts/pool.sh:245` (task says 248) | `failed_job_needs_attention` | GLOBAL, ACTION_REQUIRED |
| pool watchdog (3 sites) | `scripts/pool_watchdog.sh:139,189,239` | `failed_job_needs_attention` | GLOBAL, ACTION_REQUIRED |
| campaign approval | `src/orchestrator.py:361` | `CAMPAIGN_APPROVAL_REQUIRED` | GLOBAL, ACTION_REQUIRED |
| unmatched reply | `src/inbound.py:421` | `UNMATCHED_REPLY` | GLOBAL, ACTION_REQUIRED |
| reply protection | `src/replywatch.py:309` | `REPLY_PROTECTION_FAILED` | GLOBAL, CRITICAL |

**Minor discrepancy:** Line numbers are off by 2-6 lines in three cases. The functions exist and call `notify.notify()` as claimed. This is a documentation precision issue, not a factual error.

**All producers call `notify.notify()` → `notify.plan()` (line 763 → line 702).** Verified: `plan()` writes a row with status `planned` to the notification store and does NOT call `deliver()`. Grep for `^\s*deliver\(` inside `plan()` returns zero matches.

**The consumer:** `scripts/notify_deliver_loop.py` is the ONLY automated delivery path for GLOBAL notifications.

- Registered as a supervisor monitor at `src/supervisor.py:294-295` (name: `notify_deliver`, module: `scripts.notify_deliver_loop`, interval: 60s). Verified.
- Its `sweep()` function (line 65) loads PLANNED rows and calls `notify.deliver()` (line 72). Verified.
- `notify.deliver()` (`src/notify.py:1096`) calls `slack.post()` (`src/notify.py:1117`). Verified.

**The refusal:** `scripts/notify_deliver_loop.py:103-105` checks `slack.live()` at startup:

```python
if not slack.live():
    print(f"REFUSED: {slack.LIVE_VAR} and {slack.KEY_VAR} must both be "
          f"set. Delivering nothing.")
    return 2
```

`slack.live()` (`src/providers/slack.py:338-351`) requires BOTH:
- `SLACK_LIVE` flag in ("1", "true", "yes", "on")
- Non-empty `SLACK_BOT_TOKEN`

Verified: `LIVE_VAR = "SLACK_LIVE"` (line 330), `KEY_VAR = "SLACK_BOT_TOKEN"` (line 45).

**Other delivery paths — neither delivers GLOBAL notifications in production:**

1. `src/digestwatch.py:250` calls `notify.deliver()` but only for `OPERATIONS_DIGEST` rows (STATUS destination, not GLOBAL). Verified.
2. `scripts/slack_replay_today.py:133` calls `notify.deliver()` but is deliberately unrun (dry-run default, `--live` required). Verified.

**Queue location:** `work/notifications.jsonl`, derived from `notify.path()` (`src/notify.py:299-302`) which places the file alongside `store.queue_path()`. Verified.

---

## 3. Falsify the result's own claims

**Claim:** No GLOBAL-destination notification is ever delivered to Slack.

**Falsification attempt:** Search for any other caller of `notify.deliver()` that might bypass the refusal check.

**Result:** Grep for `notify\.deliver\(` across the entire worktree returns 11 matches:
- `src/digestwatch.py:250` — STATUS destination only, not GLOBAL
- `scripts/notify_deliver_loop.py:72` — the main consumer, refuses without SLACK_LIVE
- `scripts/slack_replay_today.py:133` — deliberately unrun
- `tests/test_notify.py` (4 matches) — test code
- Documentation files (4 matches) — not executable

**No other path delivers GLOBAL notifications.** The claim holds.

**Claim:** The wiring is complete and correct; only the switch is off.

**Falsification attempt:** Check if the code on master differs from the branch.

**Result:** `git diff master...6aa450938b035e4486a8e13096da83d0c2f0d067 -- src/ scripts/` returns empty. The code is byte-identical. The finding is already observable on master.

**The claim holds.**

---

## 4. Are the tests falsifiable?

**Not applicable.** TASK-419 is a read-only investigation task. The result block states: "Read-only investigation; no tests run. All findings are grep-traced call chains."

The finding is not a test assertion; it's an observation about production code behavior. The observation is verifiable by grep and is verified.

---

## 5. Would merging it DELETE anything?

**No.** The branch adds one file (`docs/qwen-tasks/DONE/TASK-419-notify-delivery-verification.md`) and removes one file (`docs/qwen-tasks/TODO/TASK-419-notify-delivery-verification.md`). This is a state move, not a deletion.

`git diff master...6aa450938b035e4486a8e13096da83d0c2f0d067 --stat` shows 43 files changed, but the task-specific change is limited to the task file move. The other files belong to other tasks on the branch (TASK-400, TASK-423, TASK-439, TASK-445, TASK-455, TASK-461).

---

## 6. Scope drift

**The branch carries work from multiple tasks.** The diff includes:
- TASK-400 (generate.py becomes the real caller) — 91 lines
- TASK-423 (failure taxonomy) — 41 lines
- TASK-439 (GLM review of TASK-280) — 357 lines
- TASK-445 (GLM review of TASK-292) — 178 lines
- TASK-455 (GLM review of TASK-302) — 152 lines
- TASK-461 (GLM review of TASK-315) — 157 lines
- TASK-419 (this task) — 77 lines

**Cherry-pick scope:** Only the TASK-419 task file move. The other files are unrelated to this verdict.

---

## Disposition

**CLOSE.** The finding is verified and already observable on master. The code behavior is unchanged between master and the branch. Merging the task file move is cosmetic and does not affect production.

### Findings

1. **Finding verified:** No GLOBAL-destination notification reaches Slack. The consumer exists but refuses without `SLACK_LIVE=1` and `SLACK_BOT_TOKEN`. Every GLOBAL-destination notification sits at status `planned` in `work/notifications.jsonl`.

2. **Minor documentation discrepancy:** Three line numbers in the result block are off by 2-6 lines. This does not affect the finding's validity.

3. **No code changes:** TASK-419 made zero production code changes. The artifact is the result block.

4. **Already on master:** The code behavior is byte-identical on master. The finding is already observable.

5. **Risk noted:** If `SLACK_LIVE` is enabled without replaying the accumulated `planned` rows, the deliver loop will dump the entire backlog into the ops channel at once. `scripts/slack_replay_today.py` was built to handle this safely but is itself unrun.

### Recommendation

**CLOSE.** The finding is valid and already observable. No merge is required — the code is unchanged. The task file move from TODO/ to DONE/ is administrative and can be done as part of routine queue cleanup.

**Operator decision owed:** Whether to enable `SLACK_LIVE` and, if so, whether to replay the backlog through `slack_replay_today.py --live --since <date>` or let the deliver loop post everything. This is not a defect; it's a switch that is deliberately off.

---

## Verification commands

All findings are reproducible with read-only commands:

```bash
# Verify the branch SHA
git rev-parse origin/qwen-worker-6-r9
# Expected: 6aa450938b035e4486a8e13096da83d0c2f0d067

# Verify no code changes
git diff master...6aa450938b035e4486a8e13096da83d0c2f0d067 -- src/ scripts/
# Expected: empty

# Verify the refusal check
grep -A 5 "if not slack.live()" scripts/notify_deliver_loop.py
# Expected: refusal message and return 2

# Verify slack.live() requirements
grep -A 10 "def live()" src/providers/slack.py
# Expected: requires SLACK_LIVE flag AND SLACK_BOT_TOKEN

# Verify no other GLOBAL delivery path
grep -rn "notify\.deliver(" src/ scripts/ | grep -v test | grep -v digestwatch
# Expected: only notify_deliver_loop.py and slack_replay_today.py
```

---

**Verdict delivered.** The finding is correct, the chain is traced, and the code is unchanged on master. CLOSE.
