#!/usr/bin/env python3
"""Start every production monitor, once each, and refuse to start a second one.

    py -3 scripts/start_monitors.py --status
    py -3 scripts/start_monitors.py --plan
    py -3 scripts/start_monitors.py --live

## Why this exists

On 2026-09-23 a Windows Update restart at 05:29:09 killed every loop. The
machine was back at 05:32:50. **It then sat for four hours with nothing
running**, because the loops had only ever been started by hand, one command
at a time, from whichever terminal happened to be open. The reboot cost four
minutes; the outage cost four hours, and the difference is this file.

`docs/MACHINE-HARDENING-2026-09-23.md` covers the other half - stopping the
restart. This half assumes the restart happens anyway.

## One instance each, on TWO witnesses

Starting a second `bison_watch_loop --campaign 492` does not double the
watching. It doubles the provider calls and interleaves two writers onto one
heartbeat. So nothing is started that is already running, and "running" is
decided by two independent witnesses:

    beat      work/heartbeat/<watcher>.json newer than STALE_SECONDS
    process   a python process whose command line runs this script
              (and this --campaign, where there is one)

**Either one alone is proof of life.** They are here because they fail apart,
and the first version of this file used only the beat and was wrong within the
hour:

`slack_agent_loop` writes its heartbeat when it handles a Slack envelope, not
on a timer. Twenty quiet minutes therefore look exactly like death. Measured
2026-09-23: pid 34924 alive, socket reconnected, log healthy, heartbeat 21.5
minutes old, `--status` saying DOWN. Had the logon autostart fired in that
state it would have launched a **second agent beside the first** - two Socket
Mode clients on one app, both answering the same message.

The process witness covers that. The beat witness covers the reverse case,
where the process table cannot be read at all. Only when both are silent is a
monitor down, and `--status` prints which witness spoke.

## It does not adopt the supervisor

`src/supervisor.py` (TASK-263) lives on branch `infra` and is not merged. When
it is, this file's job shrinks to starting the supervisor, and the per-monitor
table below moves into it. Until then this is deliberately the dumbest thing
that survives a reboot.

## Registering it at logon

    py -3 scripts/start_monitors.py --install-task

registers `ResonateMonitors` under Task Scheduler for the current user, at
logon, with a 60-second delay so the network is up. **Automatic logon after a
restart is a separate setting and is NOT done here** - it needs either
`netplwiz` with a stored password, or Windows' "Use my sign-in info to
automatically finish setting up after an update" (Settings -> Accounts ->
Sign-in options). Without one of those, a reboot leaves the machine at the
lock screen and no logon task fires. `--install-task` prints that.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")
BEATS = os.path.join(WORK, "heartbeat")

#: A heartbeat older than this is read as dead. The slowest loop below beats
#: on a 300s interval, so this is four missed beats and not a close call.
STALE_SECONDS = 1200

#: watcher name in work/heartbeat/<name>.json  ->  argv after `py -3`
MONITORS = [
    ("replies",          ["scripts/reply_watch_loop.py", "--interval", "300"]),
    ("notify-deliver",   ["scripts/notify_deliver_loop.py"]),
    ("digest",           ["scripts/digest_loop.py"]),
    ("bison-487",        ["scripts/bison_watch_loop.py", "--campaign", "487", "--interval", "180"]),
    ("bison-489",        ["scripts/bison_watch_loop.py", "--campaign", "489", "--interval", "180"]),
    ("bison-491",        ["scripts/bison_watch_loop.py", "--campaign", "491", "--interval", "180"]),
    ("bison-492",        ["scripts/bison_watch_loop.py", "--campaign", "492", "--interval", "180"]),
    ("bison-494",        ["scripts/bison_watch_loop.py", "--campaign", "494", "--interval", "180"]),
    ("bison-495",        ["scripts/bison_watch_loop.py", "--campaign", "495", "--interval", "180"]),
    # 496, 497 and 498 were ACTIVE and unwatched until 2026-09-23.
    # 497 is where the blank emails were found, BY HAND, because nothing
    # was watching it - and `--restart bison-497` failed for the same
    # reason. A campaign that can send and has no watcher is a campaign
    # whose incidents are discovered by a person noticing.
    ("bison-496",        ["scripts/bison_watch_loop.py", "--campaign", "496", "--interval", "180"]),
    ("bison-497",        ["scripts/bison_watch_loop.py", "--campaign", "497", "--interval", "180"]),
    ("bison-498",        ["scripts/bison_watch_loop.py", "--campaign", "498", "--interval", "180"]),
    # `heyreach_watch_loop` takes NO --campaign: it watches the campaigns it
    # finds itself. Passing one made argparse exit 2 before the first beat,
    # which is exactly the failure --status is meant to surface. It did.
    ("heyreach-605732",  ["scripts/heyreach_watch_loop.py", "--interval", "300"]),
    ("slack-agent",      ["scripts/slack_agent_loop.py"]),
    # `slack_followup_loop` was NOT in this table and was NOT running, so the
    # "restart it after D3" in the afternoon plan was a START, not a restart,
    # and a reboot would have killed it with nothing to bring it back - the
    # same gap §8 records for the 90k walk. It belongs here because
    # `slackfollowup.deliverer_is_running()` reads its heartbeat to decide
    # whether the agent may offer the follow-up at all: an absent loop is not
    # a quiet loop, and the offer must not be made on a heartbeat that no
    # process is writing.
    ("slack-followup",   ["scripts/slack_followup_loop.py", "--interval", "60"]),
    # THE MONDAY REPORT, ADDED 2026-09-24, AND IT HAD NEVER BEEN STARTED.
    #
    # `weeklyreportwatch` and `weeklyreportpdf` were written, tested, and in
    # this table's absence would have fired for the first time on Monday
    # 2026-09-28 only if somebody remembered to start the process by hand -
    # and a reboot would have taken it away again with nothing to bring it
    # back. That is the third time this exact gap is being closed here: the
    # comment above records `slack_followup_loop` missing for the same
    # reason, and `digest_loop` before it.
    #
    # FIVE MINUTES IS INSIDE THE WINDOW. The preview is due at 07:30 and the
    # post at 08:00, and `decide` refuses to post at all if the 07:30
    # preview never ran - so the interval has to guarantee a tick between
    # them. 300s lands at worst five minutes after 07:30, which is inside
    # the half hour the stop window occupies.
    #
    # No heartbeat, and that is fine here: `state()` above is UP if EITHER
    # witness says so, and a live process is proof of life on its own.
    ("weekly-report",    ["scripts/weekly_report_loop.py", "--interval", "300"]),
]

TASK_NAME = "ResonateMonitors"


def beat_age(name, now=None):
    """Seconds since this watcher last beat, or None if it never has."""
    path = os.path.join(BEATS, f"{name}.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    for key in ("epoch",):
        if isinstance(data.get(key), (int, float)):
            return (now or time.time()) - data[key]
    try:
        return (now or time.time()) - os.path.getmtime(path)
    except OSError:
        return None


def all_python_processes():
    """(pid, commandline) for every python process, fetched ONCE.

    Once, because the alternative is a PowerShell round-trip per monitor and
    eleven of those is slower than everything else this script does.
    """
    ps = ("Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
          "Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress")
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                              capture_output=True, text=True, timeout=60)
        rows = json.loads(done.stdout or "[]")
    except Exception:                                           # noqa: BLE001
        return []
    if isinstance(rows, dict):
        rows = [rows]
    return [(int(r.get("ProcessId")), r.get("CommandLine") or "")
            for r in rows if r.get("ProcessId")]


def matches(argv, commandline):
    """Does this command line run this monitor? Script name plus --campaign."""
    if os.path.basename(argv[0]) not in commandline:
        return False
    if "--campaign" in argv:
        want = "--campaign " + argv[argv.index("--campaign") + 1]
        if want not in commandline:
            return False
    return True


def state(name, now=None, argv=None, procs=None):
    """UP if EITHER witness says so. Two witnesses, because they fail apart.

    THE HEARTBEAT IS NOT A TIMER FOR EVERY LOOP. `slack_agent_loop` writes
    its heartbeat when it handles a Slack envelope, so twenty quiet minutes
    look exactly like death - measured 2026-09-23, pid 34924 alive, socket
    reconnected, log healthy, heartbeat 21.5 minutes old.

    Reading that as DOWN is not a cosmetic bug. `--live` would have started
    a SECOND agent beside the running one at every logon: two Socket Mode
    clients on one app, both answering the same message.

    So a live process is proof of life on its own. A fresh heartbeat is too
    - it covers the case where the process table cannot be read. Only when
    BOTH are silent is a monitor down.
    """
    age = beat_age(name, now=now)
    fresh = age is not None and age <= STALE_SECONDS
    alive = None
    if argv is not None and procs is not None:
        alive = any(matches(argv, line) for _pid, line in procs)
    if fresh or alive:
        return "UP", age
    if age is None:
        return "NEVER", None
    return "DOWN", age


def status(out=print):
    now = time.time()
    procs = all_python_processes()
    down = 0
    out(f"{'watcher':<20} {'state':<7} {'last beat':>12}  witness")
    out("-" * 56)
    for name, argv in MONITORS:
        st, age = state(name, now=now, argv=argv, procs=procs)
        if st != "UP":
            down += 1
        shown = "never" if age is None else f"{age/60:.1f} min ago"
        alive = any(matches(argv, line) for _pid, line in procs)
        fresh = age is not None and age <= STALE_SECONDS
        witness = "+".join(
            [w for w, on in (("beat", fresh), ("process", alive)) if on]) or "-"
        out(f"{name:<20} {st:<7} {shown:>12}  {witness}")
    out("-" * 56)
    out(f"{len(MONITORS) - down} UP, {down} not UP "
        f"(stale after {STALE_SECONDS//60} min)")
    return down


def spawn(argv):
    """Detached, so it outlives this process and the terminal that ran it."""
    log = os.path.join(WORK, f"w-{os.path.basename(argv[0])}.out")
    flags = 0
    if os.name == "nt":
        flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
                 | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    handle = open(log, "a", encoding="utf-8")
    return subprocess.Popen([sys.executable] + argv, cwd=ROOT,
                            stdout=handle, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,
                            creationflags=flags, close_fds=True)


def start(live=False, only=None, out=print):
    now = time.time()
    procs = all_python_processes()
    started, skipped = [], []
    for name, argv in MONITORS:
        if only and name not in only:
            continue
        st, age = state(name, now=now, argv=argv, procs=procs)
        if st == "UP":
            why = ("process alive" if any(matches(argv, l) for _p, l in procs)
                   else f"beating {age/60:.1f} min ago")
            skipped.append((name, why))
            out(f"  SKIP  {name:<20} already UP ({why})")
            continue
        if not live:
            out(f"  PLAN  {name:<20} would start: py -3 {' '.join(argv)}")
            started.append(name)
            continue
        proc = spawn(argv)
        started.append(name)
        out(f"  START {name:<20} pid {proc.pid}")
    return started, skipped


def pids_for(argv):
    """PIDs whose command line runs this monitor's script. Windows-specific.

    Matching on the SCRIPT PATH, not on a friendly name: two bison watchers
    differ only by `--campaign N`, so the campaign argument is matched too
    when there is one. A restart that killed the wrong watcher would be a
    silent gap on a live campaign.
    """
    script = os.path.basename(argv[0])
    want = []
    if "--campaign" in argv:
        want.append("--campaign " + argv[argv.index("--campaign") + 1])
    ps = ("Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
          "Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress")
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                              capture_output=True, text=True, timeout=60)
        rows = json.loads(done.stdout or "[]")
    except Exception:                                       # noqa: BLE001
        return []
    if isinstance(rows, dict):
        rows = [rows]
    out = []
    for row in rows:
        line = row.get("CommandLine") or ""
        if script not in line:
            continue
        if any(w not in line for w in want):
            continue
        out.append(int(row.get("ProcessId")))
    return out


def restart(names, out=print):
    """Stop, then start. For a merge: the loops import once and never reload.

    `--live` alone will NOT do this - it skips anything with a fresh
    heartbeat, which is exactly right for a crash recovery and exactly wrong
    after a merge. A merge is not a deploy, and this is the deploy.
    """
    table = dict(MONITORS)
    rc = 0
    for name in names:
        argv = table.get(name)
        if argv is None:
            out(f"  UNKNOWN monitor {name!r}")
            rc = 1
            continue
        pids = pids_for(argv)
        if not pids:
            out(f"  {name:<20} no process found; starting fresh")
        for pid in pids:
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, text=True, timeout=30)
                out(f"  STOP  {name:<20} pid {pid}")
            except Exception as exc:                        # noqa: BLE001
                out(f"  STOP  {name:<20} pid {pid} FAILED: {exc}")
                rc = 1
        time.sleep(2)
        proc = spawn(argv)
        out(f"  START {name:<20} pid {proc.pid}")
    return rc


def install_task(out=print):
    """Register the logon task. Prints what automatic logon still needs."""
    cmd = (f'"{sys.executable}" "{os.path.join(ROOT, "scripts", "start_monitors.py")}" --live')
    argv = ["schtasks", "/Create", "/TN", TASK_NAME, "/SC", "ONLOGON",
            "/DELAY", "0000:01", "/RL", "LIMITED", "/F", "/TR", cmd]
    done = subprocess.run(argv, capture_output=True, text=True)
    out((done.stdout or "").strip() or (done.stderr or "").strip())
    if done.returncode != 0:
        # schtasks /Create ONLOGON needs elevation. The Startup folder does
        # not, and it fires at the same moment for the same user. Preferred
        # ONLY as a fallback because a task is visible in one place a person
        # thinks to look and a .cmd in Startup is not - so it names itself.
        out("")
        out("  schtasks refused (not elevated). Falling back to the Startup")
        out("  folder, which needs no admin:")
        startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft",
                               "Windows", "Start Menu", "Programs", "Startup")
        target = os.path.join(startup, "resonate-monitors.cmd")
        try:
            os.makedirs(startup, exist_ok=True)
            script = os.path.join(ROOT, "scripts", "start_monitors.py")
            log = os.path.join(WORK, "autostart.out")
            lines_out = [
                "@echo off",
                "rem Resonate OS production monitors, started at logon.",
                "rem Created 2026-09-23, after a Windows Update restart left",
                "rem the machine up for four hours with nothing running.",
                "rem Delete this file to stop them starting automatically.",
                'cd /d "%s"' % ROOT,
                "rem wait for the network before the first provider call",
                "timeout /t 60 /nobreak >nul",
                '"%s" "%s" --live >> "%s" 2>&1' % (sys.executable, script, log),
            ]
            crlf = chr(13) + chr(10)
            with open(target, "w", encoding="utf-8", newline="") as handle:
                handle.write(crlf.join(lines_out) + crlf)
            out(f"    wrote {target}")
            out("    (it waits 60s for the network, then starts anything DOWN)")
        except OSError as exc:
            out(f"    FAILED: {exc}")
            return 1
    out("")
    out("  A LOGON TASK ONLY FIRES IF SOMEBODY LOGS ON.")
    out("  After an unattended reboot this machine stops at the lock screen")
    out("  and nothing here runs. To make the logon automatic, ONE of:")
    out("    * Settings -> Accounts -> Sign-in options -> 'Use my sign-in info")
    out("      to automatically finish setting up after an update' = On")
    out("      (works for Windows-initiated restarts, which is what killed")
    out("       2026-09-23; it does NOT cover a power cut)")
    out("    * netplwiz -> clear 'Users must enter a user name and password',")
    out("      which stores the password and covers every restart. It weakens")
    out("      physical security on a laptop: that is the operator's call.")
    return done.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--only", action="append")
    parser.add_argument("--install-task", action="store_true")
    parser.add_argument("--restart", action="append",
                        help="stop and start this monitor, whatever its "
                             "heartbeat says. Use after a merge.")
    args = parser.parse_args(argv)

    if args.install_task:
        return install_task()
    if args.restart:
        print("")
        print("RESTARTING " + ", ".join(args.restart))
        print("")
        return restart(args.restart)
    if args.status or not (args.plan or args.live):
        return 0 if status() == 0 else 1

    print(f"\n{'STARTING' if args.live else 'PLAN'} monitors "
          f"(stale after {STALE_SECONDS//60} min)\n")
    started, skipped = start(live=args.live, only=set(args.only or []) or None)
    print(f"\n  {len(started)} {'started' if args.live else 'would start'}, "
          f"{len(skipped)} already up")
    if args.live:
        print("\n  Heartbeats take up to one interval to appear. Verify with:")
        print("    py -3 scripts/start_monitors.py --status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
