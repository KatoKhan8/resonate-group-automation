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

## One instance each, and the check is the heartbeat, not a pid file

A pid file records what somebody intended. `work/heartbeat/<watcher>.json`
records what is actually beating, and `watchsink.heartbeats()` already reads
it. A watcher whose heartbeat is younger than `STALE_SECONDS` is live and is
NOT restarted - starting a second `bison_watch_loop --campaign 492` does not
double the watching, it doubles the provider calls and interleaves two writers
onto one heartbeat.

A heartbeat older than that is treated as dead. That is a judgement and it can
be wrong in one direction: a loop wedged but alive looks dead here and gets a
second instance. `--status` prints the ages so a person can see it before
`--live` acts on it.

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
    # `heyreach_watch_loop` takes NO --campaign: it watches the campaigns it
    # finds itself. Passing one made argparse exit 2 before the first beat,
    # which is exactly the failure --status is meant to surface. It did.
    ("heyreach-605732",  ["scripts/heyreach_watch_loop.py", "--interval", "300"]),
    ("slack-agent",      ["scripts/slack_agent_loop.py"]),
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


def state(name, now=None):
    age = beat_age(name, now=now)
    if age is None:
        return "NEVER", None
    return ("UP" if age <= STALE_SECONDS else "DOWN"), age


def status(out=print):
    now = time.time()
    down = 0
    out(f"{'watcher':<20} {'state':<7} {'last beat':>12}")
    out("-" * 42)
    for name, _argv in MONITORS:
        st, age = state(name, now=now)
        if st != "UP":
            down += 1
        shown = "never" if age is None else f"{age/60:.1f} min ago"
        out(f"{name:<20} {st:<7} {shown:>12}")
    out("-" * 42)
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
    started, skipped = [], []
    for name, argv in MONITORS:
        if only and name not in only:
            continue
        st, age = state(name, now=now)
        if st == "UP":
            skipped.append((name, f"beating {age/60:.1f} min ago"))
            out(f"  SKIP  {name:<20} already UP ({age/60:.1f} min ago)")
            continue
        if not live:
            out(f"  PLAN  {name:<20} would start: py -3 {' '.join(argv)}")
            started.append(name)
            continue
        proc = spawn(argv)
        started.append(name)
        out(f"  START {name:<20} pid {proc.pid}")
    return started, skipped


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
    args = parser.parse_args(argv)

    if args.install_task:
        return install_task()
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
