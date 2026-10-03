# MORNING HANDOVER — 2026-10-04

Runtime lane, night of 2026-10-03. Branch `task-runtime-lane-2026-10-03`.
No provider write. No send. No activation. One Slack post, to the OUTPUT
channel only.

---

## 1. THE DELIVER LOOP IS UP, SUPERVISED, AND PROVEN

**Nothing was draining the ledger at 21:30.** It is draining now.

| | |
|---|---|
| supervisor | `C:\Users\Zvonimir\Desktop\resonate-ops\runtime\supervise-notify-deliver.ps1` |
| started | detached user process, `Start-Process`, NOT a scheduled task |
| restart loop | yes — child exit is logged and the child is restarted |
| ledger drained | `C:\Users\Zvonimir\Desktop\resonate-group-automation\work\notifications.jsonl` (production) |
| heartbeat | `C:\Users\Zvonimir\Desktop\resonate-ops\runtime\deliver.heartbeat`, every 30s |
| supervisor log | `C:\Users\Zvonimir\Desktop\resonate-ops\runtime\supervisor.log` |
| loop log | `C:\Users\Zvonimir\Desktop\resonate-ops\runtime\notify-deliver.log` |
| narrowed to | `C0C6DES2L7L` only (`NOTIFY_DELIVER_CHANNELS`) |

**The restart was proven, not assumed.** The child was killed deliberately at
22:28:16 and the supervisor logged `CHILD EXITED code=-1 after 226s` and
`START child (restart #1)` five seconds later with a new pid.

**The probe reached a human in 21 seconds.** Planned 22:29:30, visible in
`#resonate-os-output` at 22:29:51, read back from the channel with
`conversations.history` rather than from the status field:

    [INFO] STATUS CHECKPOINT
    Note: canary go-checklist probe, runtime lane 2026-10-03. Declared probe
    row; proves plan -> deliver -> this channel. Safe to ignore.

Row `ce9aa8af53b71ad37827`, status `planned` -> `sent`. **The probe row is
DECLARED, not deleted** — it is left in the ledger as the audit trail for
this item.

### To restart it by hand

    & "C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\Zvonimir\Desktop\resonate-ops\runtime\supervise-notify-deliver.ps1"

A logon shortcut also exists at
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ResonateNotifyDeliver.lnk`.
**Delete it when the scheduled task below is created**, or two supervisors
will race. They will not double-deliver — the loop takes the `singlewalker`
lock and the loser exits 4 — but one of them will sit in a 300-second
backoff loop forever, which is noise.

---

## 2. FOR TODAY: THE SCHEDULED-TASK VERSION. **IT HAS NOT BEEN RUN.**

**This has NOT been run.** Registering a scheduled task was attempted twice
last night and refused both times: `Register-ScheduledTask` returned
`Access is denied` (no admin), and `schtasks` was refused by the harness
classifier. The operator said they would grant admin this morning. **Open an
ELEVATED PowerShell** and paste this exactly — it needs no editing:

    schtasks /Create /TN "ResonateNotifyDeliver" /TR "\"C:\Program Files\PowerShell\7\pwsh.exe\" -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File \"C:\Users\Zvonimir\Desktop\resonate-ops\runtime\supervise-notify-deliver.ps1\"" /SC ONLOGON /RU "%USERDOMAIN%\%USERNAME%" /RL HIGHEST /IT /F

`schtasks` has no flag for the working directory or for restart-on-failure,
so set those on the task object immediately afterwards, in the same elevated
shell — these are the restart/retry flags:

    $t = Get-ScheduledTask -TaskName "ResonateNotifyDeliver"
    $t.Settings.RestartCount                = 999
    $t.Settings.RestartInterval             = "PT1M"
    $t.Settings.ExecutionTimeLimit          = "PT0S"
    $t.Settings.MultipleInstances           = "IgnoreNew"
    $t.Settings.StartWhenAvailable          = $true
    $t.Settings.DisallowStartIfOnBatteries  = $false
    $t.Settings.StopIfGoingOnBatteries      = $false
    $t.Actions[0].WorkingDirectory          = "C:\Users\Zvonimir\Desktop\resonate-ops\runtime"
    Set-ScheduledTask -InputObject $t
    Start-ScheduledTask -TaskName "ResonateNotifyDeliver"

Then confirm it, and confirm the loop, not the task:

    Get-ScheduledTaskInfo -TaskName "ResonateNotifyDeliver" | Select-Object LastRunTime,LastTaskResult
    py -3 -c "import os,datetime; p=r'C:\Users\Zvonimir\Desktop\resonate-ops\runtime\deliver.heartbeat'; print('age_seconds %.1f' % (datetime.datetime.now().timestamp()-os.path.getmtime(p)))"

Before starting it, stop the detached supervisor and delete the logon
shortcut:

    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'supervise-notify-deliver|notify_deliver_loop' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Remove-Item "$([Environment]::GetFolderPath('Startup'))\ResonateNotifyDeliver.lnk"

**A task that exists is not a loop that runs.** The heartbeat age is the
test, not `LastTaskResult`.

---

## 3. OPENROUTER RUNNING TOTAL — every 90 minutes

Operator, 2026-10-03. Command:

    py -3 -c "from src import spendledger as sl; print(sl.spent('productive', provider='openrouter')/1_000_000)"

| wall clock | OpenRouter spend, USD | note |
|---|---|---|
| 2026-10-03 22:45 | **0.000000** | first reading. Nothing has spent on OpenRouter at all. |
| 2026-10-04 00:15 | *(due)* | |
| 2026-10-04 01:45 | *(due)* | |

### AND THE CAP DOES NOT BIND WHERE THE OPERATOR SET IT

**Read this before sizing any model work.** The operator's figure is **50 USD
for the night, fail-closed**. Measured by bisection at 22:45:

| | |
|---|---|
| operator's figure | USD 50.00 |
| `openrouter.per_day` in `config/clients/productive.yaml` | `20000000` = USD 20.00 |
| **largest spend `spendledger.check` will actually allow** | **USD 0.199973** |

The binding limit is the client-wide `budget.per_day: 200000`, which the
config itself documents as a MIXED-UNIT TRIPWIRE summing cents and credits.
At 200,000 it is a hundred times smaller than the provider ceiling sitting
behind it, so **the OpenRouter ceiling is unreachable and one dollar of
OpenRouter is refused today.**

    CLIENT CEILING: the client-wide per_day for productive is 200000 - this is
    NOT a provider ceiling, and the call was to openrouter; 27 credit(s) are
    already committed today (2026-10-03) across ALL providers

**This was NOT changed.** Raising a cap is loosening a safety limit and that
is the operator's decision, not a lane's — and the live limit is far
STRICTER than what was asked for, so nothing is at risk from leaving it. It
needs a decision this morning, because a run sized against 50 USD will halt
at 20 cents.

**And `glm` is refused outright**: it has 2,551,349 microusd of recorded
spend and **no declared ceiling**, so `check` raises `MissingCeiling` for
every GLM call. Either GLM spend is bypassing `check`, or GLM is blocked.
Both are worth an answer before the morning's verification runs.

---

## 4. THE NINE REPLIES THAT HAVE REACHED NOBODY SINCE 2026-09-28

The ledger holds **11 undelivered PLANNED rows**, all from 2026-09-28. The
deliver loop is deliberately narrowed and has left every one of them PLANNED
and untouched — nothing was suppressed, nothing was lost, and widening the
allowlist delivers them with nobody having to un-hold anything.

| count | type | channel | |
|---|---|---|---|
| 9 | `unmatched_reply_needs_review` | `C0C34GCAR27` | **RETIRED on 2026-09-27.** These cannot be delivered at all. |
| 2 | `campaign_stopped_externally` | `C0C3C6MDN9L` | deliverable the moment the operator widens the allowlist |

The nine are **replies needing a human** — the operator's named condition —
and they have been sitting for five days pointed at a dead room. They need
re-resolving through `scripts/slack_replay_today.py`, which is an operator
action by design. **This is the single most important thing in this file
after the loop itself.**

`notify.deliver` now REFUSES a retired channel (it did not before — the
retirement was enforced only when a row was ROUTED, and a row planned before
the retirement carried the dead id in its own `channel` field and would have
been posted into the retired room).

---

## 5. THE HEADROOM RE-WALK IS RUNNING

Started 22:34. `--reset`, so it is a clean walk and not a resume of the
2026-09-24 one. Roughly two hours; expect it to finish around 00:35.

- log: `C:\Users\Zvonimir\Desktop\resonate-ops\runtime\forward-book-rewalk.log`
- the 09-24 walk is backed up at
  `C:\Users\Zvonimir\Desktop\resonate-ops\runtime\forward-book-census.2026-09-24.bak.json`

Check it before reading any headroom number:

    py -3 -c "from src import providers, senderheadroom as s; providers.load_env(); st=s.load_state(); print('walked_at', s.walked_at(st)); print('freshness', s.freshness(st)); print('completeness', s.completeness(st))"

**`completeness` must be `(True, ())`.** An incomplete walk proves FULL and
proves nothing else. **REFUSED IS NOT ROOM.**

The old walk was not merely stale: its forward book ended **2026-09-30**, so
it covered no day from today onward at all.

---

## 6. WHAT IS STILL RED

See `REPORT.md` on this branch for the full table with the output that
decided each item. Red at 22:50:

- **A2** — `task-one-os-authority` is not in master
- **A4** — tree dirty: `docs/state/PROVIDER-CAMPAIGNS.json` modified (**by
  the checklist's own B2 command**) and `TASK-978` untracked; and
  `suite_verdict.txt` is 16:54, older than tonight's work
- **B2** — **provider writes from us are NOT zero.** 1,430 accepted non-test
  writes are in the ledger
- **C3** — `notify.output_channel` is not on master; `task-1008` unmerged
- **E4** — no `PHASE0-*.md` copy-review file exists
- **F1** — the cap binds at USD 0.20, not the operator's USD 50
- **F2** — walk in progress, `completeness` still False
- **G1** — nothing has been sent, so there is nothing for the provider to
  confirm. Correct, by design.
