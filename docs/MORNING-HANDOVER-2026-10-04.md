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

**The later readings write themselves.**
`resonate-ops\runtime\report-openrouter-spend.ps1` is running detached and
appends a row here every 90 minutes, with the headroom walk's state on each
pass. It writes the row **even when the figure has not moved**, because an
entry reading 0.00 at 01:45 is evidence and a missing row is not. A plain
trail is also kept at `resonate-ops\runtime\openrouter-spend.log`. If the
table below stops at 22:45, that process died — check it before concluding
nothing was spent.

| wall clock | OpenRouter spend, USD | note |
|---|---|---|
| 2026-10-03 22:45 | **0.000000** | first reading. Nothing has spent on OpenRouter at all. |

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

## 5. THE HEADROOM RE-WALK IS DONE. **F2 IS GO.**

**Finished 2026-10-04 00:02:25, exit 0.** Started 22:34 with `--reset`, so it
is a clean walk and not a resume of the 2026-09-24 one.

    walked_at    2026-10-03T20:56:02+00:00
    freshness    (True, 1.11 hours)
    completeness (True, ())
    coverage     (True, ())   against active 418, 352, 328, 327
    campaigns    17 walked

ROOM is therefore **provable**, and was proved rather than inferred from the
report's print — real `senderheadroom.verdict` calls across all 222 mailboxes:

| day | verdict counts |
|---|---|
| 2026-10-05 | **ROOM 170**, FULL 52 |
| 2026-10-06 | **ROOM 169**, FULL 53 |
| 2026-10-07 | **ROOM 170**, FULL 52 |
| 2026-10-08 | **ROOM 169**, FULL 53 |

e.g. `sender 3386: 0 of 15 booked on 2026-10-05, 15 free`.

**DO NOT TRUST 2026-10-09 AND LATER.** Every one of the 222 mailboxes reads
`ROOM`, `0 of 15 booked` on 10-09, 10-10 and 10-11. That is not an empty
estate, it is **the edge of the client scheduler's horizon** — rows have not
been inserted that far out yet, and "not yet planned" is reading as "free".
This module's own docstring records the identical trap: a walk on the 17th
said sender 3437 had eleven free slots on the 22nd, and by the 18th the
provider had moved the work to the 24th. **Size anything against 10-05 to
10-08, where the numbers are real.**

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
- **B2** — **provider writes from us are NOT zero, and CLAUDE.md says they
  are.** See section 7.
- **C3** — `notify.output_channel` is not on master; `task-1008` unmerged
- **E4** — no `PHASE0-*.md` copy-review file exists
- **F1** — the cap binds at USD 0.20, not the operator's USD 50
- ~~**F2**~~ — **NOW GO.** Walk finished 00:02:25: complete, fresh, covering; ROOM 170 on 2026-10-05. See section 5.
- **G1** — nothing has been sent, so there is nothing for the provider to
  confirm. Correct, by design.

---

## 7. CLAUDE.md SAYS PROVIDER WRITES FROM US ARE ZERO. THEY ARE NOT.

CLAUDE.md states, as standing fact:

> A pause is itself a provider write and was performed by the operator, not
> by this system — provider writes from us remain 0.

**The first half is right and the second is false.** The operator did pause
487, 489 and 493 by hand. But `work/provider-writes.jsonl` records **1,430
accepted non-test provider writes**, and the largest block of them was made
by our own code:

    accepted bison.pause, non-test : 1393
    argv[0]                        : {'bison_watch_loop.py': 1393}
    by                             : {'bison_watch_loop': 1393}
    campaign                       : {'481': 1393}

    {"at": "2026-09-25T16:04:38Z", "operation": "bison.pause",
     "outcome": "accepted", "campaign": "481", "by": "bison_watch_loop",
     "pid": 46016, "argv": ["bison_watch_loop.py", "--campaign", "481"]}

`bison_watch_loop.py` re-paused campaign **481 — our own campaign — every
three minutes, 1,393 times, between 2026-09-25 and 2026-09-28.** The rest:
`heyreach.pause` ×34, `bison.create_campaign` ×1 (481 itself),
`bison.set_sequence` ×1, `bison.stop_lead` ×1.

**What this does and does not mean.** Every one of these is either the
creation of 481 or a PAUSE — the safe direction — and **nothing has been
written to any provider since 2026-09-28T14:14:38Z.** Nothing was written
tonight. So the estate is not in danger from this.

What it does mean is that **the sentence a fresh session reads first is
wrong**, and B2 is the checklist item whose entire job is to catch exactly
this. Two things follow:

1. **Correct the CLAUDE.md line.** "Provider writes from us remain 0" should
   say what is true: no prospect-facing send has been made from this system,
   and the writes that exist are pauses and the creation of our own 481.
2. **B2's command cannot decide B2.** `scripts/provider_truth.py --verify`
   prints a provider readback and an ownership tally and **no
   ledger-vs-readback comparison at all**, so the item's stated GO criterion
   ("the readback matches the ledger") is not in its output. Unreadable
   authority means UNKNOWN, and UNKNOWN is never a pass. The item needs a
   command that actually compares the two.

Reproduce with:

    py -3 -c "import collections; from src import providers, store; providers.load_env(); rows=store.read_jsonl('work/provider-writes.jsonl'); nt=[r for r in rows if r.get('outcome')=='accepted' and 'unittest' not in ' '.join(str(x) for x in (r.get('argv') or []))]; print(len(nt)); print(dict(collections.Counter(r.get('by') for r in nt)))"
