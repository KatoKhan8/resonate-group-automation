# Machine hardening — 2026-09-23

Why the laptop restarted at 05:29 and killed every production loop, what was
changed to stop it recurring, and **what is still open because this session
does not hold administrator rights.**

Measured on `ZVONIMIR`, Acer Nitro AN16-41, Windows 11 Pro build 26200.
Session user `ZVONIMIR\Zvonimir` — a member of `Administrators` but running
**unelevated**, which is the constraint that splits this document in two.

---

## 1. THE CAUSE: a Windows Update restart. Not sleep, not power, not a crash

**System event 1074, 2026-09-23 05:29:09:**

    The process C:\WINDOWS\uus\AMD64\MoUsoCoreWorker.exe (ZVONIMIR) has
    initiated the ponovno pokretanje [restart] of computer ZVONIMIR on behalf
    of user NT AUTHORITY\SYSTEM for the following reason:
    Operacijski sustav: servisni paket [Operating System: Service Pack]

The last production heartbeat was written at **05:29:04**. The restart was
initiated **five seconds later**. That is the whole outage in two timestamps.

It was not one reboot but three, a servicing chain:

    04:45:21  WindowsUpdateClient 44   started downloading KB5124010
    04:51:49  WindowsUpdateClient 43   Installation Started: 2026-09 Preview
                                       Update (KB5124010) (26200.9550)
    05:29:04  --- last heartbeat: bison-494 ---
    05:29:09  User32 1074              MoUsoCoreWorker.exe -> RESTART
    05:30:06  EventLog 6006            event log stopped
    05:30:11  Kernel-Power 109         Power Action Reboot, Reason: Kernel API
    05:31:37  User32 1074              TrustedInstaller.exe -> RESTART (Upgrade)
    05:32:28  User32 1074              TrustedInstaller.exe -> RESTART (Upgrade)
    05:32:50  --- LastBootUpTime ---
    05:35:25  WindowsUpdateClient 19   Installation Successful: KB5124010

### Everything it was NOT, checked rather than assumed

| Hypothesis | Evidence against |
| --- | --- |
| Power loss / dirty shutdown | **No event 41, 6008 or 1076 in seven days.** Event 109 names `Power Action Reboot, Reason: Kernel API` — an orderly software-initiated transition |
| Sleep or hibernate | On AC, `sleep after` was **already 0 (never)** before any change today. The machine cannot have idle-slept |
| Ran out of battery | `powercfg /batteryreport` shows `Ac=1` at 05:25:00, 05:30:55 and 05:33:09 — on mains throughout. See §5 |
| Thermal | The only Kernel-Power 125 rows are ACPI thermal-zone **enumeration at boot** (`_TZ.TZ01 has been enumerated`). Routine POST output, not a throttle or a thermal shutdown. No 86/87/88 |
| User shutdown | 1074 names `NT AUTHORITY\SYSTEM` as the principal, not an interactive user |

### The two decisions that made 05:29 legal

1. **Active hours were 09:00 → 01:00.** Windows was told the machine is free
   between 01:00 and 09:00 — which is *precisely* the unattended overnight
   production window. It did what it was configured to do.
2. **`IsContinuousInnovationOptedIn = 1`** — the box was opted into "get the
   latest updates as soon as they're available", so it accepted an **optional
   Preview** release (KB5124010) mid-week. A non-urgent update took the
   machine down during a live run.

`HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate` **did not exist**, so
`NoAutoRebootWithLoggedOnUsers` was unset and auto-restart was permitted.

### The second failure, which nobody asked about

The machine came back at **05:32:50 and has been up for four hours with no
production loop running.** The reboot cost ~4 minutes; the *outage* cost ~4
hours, because nothing starts the monitors at boot. Hardening the power
settings does not fix that. **An auto-start or a supervisor service is the
larger of the two gaps** and is not addressed here.

---

## 2. POWER PLAN — applied, no elevation needed

Scheme `381b4222-f694-41f0-9685-ff5bb260df2e` (Balanced), the active scheme.
Values are seconds; `0` = never.

| Setting | Before AC | Before DC | After AC | After DC |
| --- | --- | --- | --- | --- |
| sleep after | **0** | 2700 | 0 | **0** |
| hibernate after | **0** | 2147483647 | 0 | **0** |
| hybrid sleep | **1** | **1** | **0** | **0** |
| hard disk off | **30** | **30** | **0** | **0** |
| display off | 0 | 2700 | 0 | 2700 |
| USB selective suspend | **1** | **1** | **0** | **0** |
| lid close action | *(hidden)* | *(hidden)* | **0** | **0** |

Display-off is left alone on both — blanking the panel is wanted, and a
display request is deliberately **not** taken (see §6).

**The lid setting is hidden in this scheme**, so `powercfg /query` prints
nothing for it and the before-value is genuinely unknown. The write landed and
was verified directly in the registry:

    HKLM\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes
      \381b4222-.../4f971e89-.../5ca83367-...
        ACSettingIndex : 0      DCSettingIndex : 0      (0 = Do nothing)

**Fast startup is still ON** — `HiberbootEnabled = 1`. That key is under
`HKLM\SYSTEM\...\Session Manager\Power` and is **not writable unelevated**.
See §7.

Note for honesty: on AC, sleep and hibernate were *already* never. **Nothing
in this section would have prevented the outage.** It closes a hole that was
open (hybrid sleep, 30-second disk spindown, DC idle sleep at 45 min) but was
not the one that fired.

---

## 3. WINDOWS UPDATE — partly applied

`HKLM\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings` proved writable
unelevated; the policy key did not.

| Value | Before | After |
| --- | --- | --- |
| `ActiveHoursStart` | 9 | **20** |
| `ActiveHoursEnd` | 1 | **14** |
| `SmartActiveHoursState` | *(unset)* | **0** |
| `IsContinuousInnovationOptedIn` | **1** | **0** |
| `PauseUpdatesStartTime` | *(unset)* | `2026-09-23T07:32:21Z` |
| `PauseUpdatesExpiryTime` | *(unset)* | `2026-09-30T07:32:21Z` |
| `PauseFeatureUpdatesEndTime` | *(unset)* | `2026-09-30T07:32:21Z` |
| `PauseQualityUpdatesEndTime` | *(unset)* | `2026-09-30T07:32:21Z` |

**Why 20:00 → 14:00 and not the literal "maximum window".** Windows caps the
active-hours span at **18 hours**, so 6 hours are unprotected no matter what.
The only real choice is *where* the gap falls. It was 01:00–09:00 — overnight,
unattended, exactly when the loops run alone. It is now **14:00–20:00**, the
operator's afternoon, when somebody is at the machine and a restart is
survivable. Setting `SmartActiveHoursState = 0` stops Windows re-deriving the
window from usage and quietly moving it back.

`IsContinuousInnovationOptedIn = 0` is arguably the highest-value line in this
table: it is what made the machine eligible for the optional preview build
that took it down.

**Updates are paused, not disabled.** Quality and security updates resume on
2026-09-30. This buys a week; it is not a fix, and the pause will expire
mid-project. `NoAutoRebootWithLoggedOnUsers` (§7) is the durable control.

**Confirm in the UI.** These are the values the Settings app reads, but the
Update Orchestrator re-reads them on its own schedule. Open
*Settings → Windows Update* and check it shows paused until 30 September and
active hours 20:00–14:00. If it does not, the values need re-applying
elevated.

---

## 4. TASKS AND SERVICES THAT CAN RESTART OR SLEEP THE MACHINE

`Get-ScheduledTask -TaskPath '\Microsoft\Windows\UpdateOrchestrator\*'`
returned **nothing**, and `schtasks /query` on that path exited 1 — the folder
is ACL'd to SYSTEM and is not enumerable unelevated. Reading the task
definitions off disk instead:

    C:\Windows\System32\Tasks\Microsoft\Windows\UpdateOrchestrator\
        Report policies                      Schedule Work
        Schedule Maintenance Work            Start Oobe Expedite Work
        Schedule Scan                        StartOobeAppsScan_LicenseAccepted
        Schedule Scan Static Task            StartOobeAppsScanAfterUpdate
        Schedule Wake To Work   <-- wakes    UIEOrchestrator
        USO_UxBroker                         UUS Failover Task

**There is no `Reboot`, `Reboot_AC` or `Reboot_Battery` task on this build.**
That matters: the familiar advice to "disable the UpdateOrchestrator Reboot
task" is obsolete here. Event 1074 names `MoUsoCoreWorker.exe` — the restart
comes from the **Update Session Orchestrator service itself**, which no task
disable can reach. The levers are the policy and active-hours values in §3
and §7, not a task.

`Schedule Wake To Work` is the one task in this folder that can wake a
sleeping machine for update work. It is queued for disabling in §7.

A sweep of **all** scheduled tasks for a shutdown/restart action
(`shutdown.exe`, `MusNotification`, `UsoClient`, or arguments matching
`/r`, `/s`, `Reboot`) returned **no rows** visible to this account.

### OEM power utilities — present, and not implicated

    AASSvc                       Acer Agent Service
    AcerCCAgentSvis              Acer Care Center
    AcerQAAgentSvis              Acer Quick Access
    ASMSvc                       Acer System Monitor Service
    AcerDeviceEnablingServiceV2, AcerEZSvc, AcerPixyService,
    AcerLightingService, AcerServiceSvc, AcerARTAIMMX*, AcerGAICameraService

All running. **None of them was left disabled**, deliberately: the event log
names the initiator and it is not Acer. Disabling a running OEM service to fix
a fault it demonstrably did not cause is how a hardening pass creates the next
outage. Acer Care Center and Quick Access *do* expose power and battery
profiles that can override a Windows power plan — so if the §2 values are
found reverted at some later date, these are the first suspects, and that is
the reason they are named here rather than the reason to disable them now.

---

## 5. BATTERY AND AC STATE

    DesignCapacity     90,614 mWh
    FullChargeCapacity 73,396 mWh
    Health             81.0 %
    CycleCount         0          (not reported by this firmware — not a real zero)

**The machine was on mains at the shutdown and is now.** From
`powercfg /batteryreport`, around the event:

    2026-09-23T05:25:00   Ac=1
    2026-09-23T05:30:55   Ac=1
    2026-09-23T05:33:09   Ac=1

`Win32_Battery.BatteryStatus = 2` (AC), `PowerLineStatus = Online`, charge
100%. **No operator action needed — this was not a power problem.** Battery
health at 81% after however many cycles is ordinary wear and is not
load-bearing while the machine stays plugged in.

---

## 6. THE KEEP-AWAKE REQUEST

`src/keepawake.py` + `tests/test_keepawake.py`, 11 tests, and exercised
against the real `kernel32` rather than only the fake:

    available      : True
    acquire (real) : True
    holding        : True
    holding(other) : False      <- from a second thread
    release (real) : True

It requests `ES_CONTINUOUS | ES_SYSTEM_REQUIRED`. **No `ES_DISPLAY_REQUIRED`**
— a display request on a laptop sitting closed is a burned panel, and there is
a test asserting the flag is never set on any call.

Three things it is built to refuse to lie about:

- **A `0` return is a failure**, not a previous state of zero.
  `SetThreadExecutionState` returns the prior state; not reading it is how you
  ship a keep-awake that reports success for ever. `acquire()` returns False
  and `status()["error"]` says why.
- **The request is per-thread.** `ES_CONTINUOUS` dies with the thread that
  took it, silently. `holding()` compares thread identity and returns False
  from anywhere else, so a supervisor that acquires on a worker which then
  exits can detect it. **Acquire on the main thread.**
- **`status()` carries `"covers": "idle sleep only - NOT a Windows Update
  restart"`** on every line, so no reader of a green status row concludes the
  machine is protected from the thing that actually killed it.

### Where it is wired: nowhere yet, on purpose

`src/supervisor.py` and `scripts/supervise.py` live on branch `infra` and are
**not merged to master** (TASK-263, `538f45ae`). Under the three-session rule
the production session does not edit another session's in-flight files, so
`keepawake` landed as a standalone module on master with no caller. Adoption
is one line in the supervisor's startup, on its main thread:

    from src import keepawake
    with keepawake.KeepAwake() as awake:
        if not awake.entered_ok:
            emit("KEEP-AWAKE REFUSED " + str(awake.error))
        ...

**`powercfg /requests` could not be run — it requires elevation.** So the
claim "no sleep is possible while the monitors run" is, as of now,
**unproven**. §7 carries the command.

---

## 7. STILL OPEN — needs an elevated shell

This session is not elevated. `scripts/harden_machine_elevated.ps1` contains
everything below, prints BEFORE/AFTER for each change, supports `-WhatIf`, and
refuses to run unelevated:

    powershell -ExecutionPolicy Bypass -File scripts\harden_machine_elevated.ps1

| # | Change | Why it is blocked |
| --- | --- | --- |
| 1 | `NoAutoRebootWithLoggedOnUsers = 1`, `AUPowerManagement = 0`, `AUOptions = 3` under `...\Policies\Microsoft\Windows\WindowsUpdate\AU` | key not writable; `OpenSubKey` → *Requested registry access is not allowed* |
| 2 | `HiberbootEnabled = 0` (fast startup off) | `...\Session Manager\Power` not writable |
| 3 | Disable `Schedule Wake To Work`; confirm no `Reboot*` task exists | `UpdateOrchestrator` not enumerable unelevated |
| 4 | Wake timers off (`SUB_SLEEP RTCWAKE = 0`) on AC and DC | included in the same script |
| 5 | `powercfg /requests` — the §6 proof | *requires administrator privileges* |

**Item 1 is the one that matters.** Active hours and a 7-day pause are timing
tricks; `NoAutoRebootWithLoggedOnUsers` is the setting that says no.

### Then verify

    powercfg /requests                     # expect a SYSTEM: row naming python.exe
    reg query "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
    reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power" /v HiberbootEnabled

---

## 8. WHAT THIS DOES AND DOES NOT BUY

**Does:** the machine will not idle-sleep, spin down its disk, hybrid-sleep,
suspend USB, or act on a lid close. It will not take optional preview builds.
For seven days it will not install quality updates at all. Its restart window
has moved off the overnight run and into the working afternoon.

**Does not:** stop a Windows Update restart. Until §7 item 1 is applied, the
Update Orchestrator may still restart this machine outside active hours — the
window has moved, not closed. And on 2026-09-30 the pause expires.

**Does not, and is the bigger gap:** bring the monitors back. The machine
rebooted in four minutes and sat idle for four hours. Every control in this
document is about *preventing* a restart; none of them survives one. A boot
autostart for the supervisor is the change that makes the next reboot a
four-minute event instead of a four-hour one.

The pattern in `PRODUCTION-HANDOFF-2026-09-23-OVERNIGHT.md` §7 applies to this
document too: ask what the failure looks like. A hardened power plan and a
held keep-awake request would both have looked exactly like this at 05:29:04,
and the machine would have rebooted anyway.
