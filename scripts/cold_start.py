#!/usr/bin/env python3
"""Bring the estate back after a machine restart. Plans by default.

WHY THIS EXISTS. On 2026-09-23 a Windows Update restart took this machine
down at 05:29 and it was back at 05:32 - three minutes. The monitors were
down for FOUR HOURS, because nothing starts them but a person typing.
`docs/MACHINE-HARDENING-2026-09-23.md` closes on exactly this:

    "Does not, and is the bigger gap: bring the monitors back. Every control
    in this document is about *preventing* a restart; none of them survives
    one."

Every recovery so far has been manual. This is the script that makes the last
one the last one.

TWO WITNESSES, because one of them is forgeable. A monitor counts as UP only
when BOTH hold:

    witness 1  a live process, from the supervisor's state file, AND that
               state file was written AFTER the current boot
    witness 2  a heartbeat written AFTER the current boot, and no older than
               twice the monitor's own poll interval

Neither is admissible alone. PIDS ARE REUSED ACROSS A REBOOT: after a restart
the number in a pre-boot state file names whatever process the kernel handed
it to next, so `supervisor._monitor_status` can report UP for a monitor that
is not running - and the adoption step in
`docs/PRODUCTION-HANDOFF-2026-09-23-OVERNIGHT.md` is "post --status showing
all UP", which is precisely the claim a reused pid forges. A heartbeat alone
is no better: a beat from before the reboot is a record of the machine's
previous life, and a process that is alive but wedged beats nothing while
still holding its pid.

WHAT IT DOES NOT DO. It does not send, does not write a queue record, does
not touch `config/.env`, `src/providers/*` or anything under `work/` except
to READ cursors and heartbeats and to REMOVE lock files that provably predate
the current boot. It starts nothing without `--start`.

    py -3 -m scripts.cold_start                  # plan: what is down, what is stale
    py -3 -m scripts.cold_start --start          # clear stale locks, start supervisor
    py -3 -m scripts.cold_start --verify         # poll until two witnesses agree
    py -3 -m scripts.cold_start --json           # the plan, machine-readable
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import singlewalker, store, supervisor, watchsink  # noqa: E402

#: A heartbeat older than this many times a monitor's own interval is not a
#: witness. Two, not one: a monitor that polls every 300s and is mid-poll when
#: asked has legitimately not beaten for slightly over 300s, and an alarm that
#: fires on the normal case is an alarm people learn to ignore.
STALE_BEAT_MULTIPLE = 2

#: For the event-driven monitors that declare no interval.
DEFAULT_INTERVAL = 300

#: How long a full recovery is allowed to take before `--verify` gives up.
#: The machine rebooted in three minutes on 2026-09-23; a supervisor that has
#: not brought every monitor up in ten is not slow, it is stuck.
VERIFY_DEADLINE = 600


def boot_time():
    """Epoch seconds of the last boot, or None if it cannot be established.

    NONE IS NOT ZERO, and every caller below fails closed on it. A caller that
    could not read the boot time must not conclude that every lock is stale -
    that would delete the locks of monitors running perfectly well, which is
    the opposite of this script's job.

    Windows: `Win32_OperatingSystem.LastBootUpTime`, via PowerShell, because
    this repository carries no third-party dependencies and `psutil` is not
    installed. Linux: `/proc/stat`'s `btime`, the same fact with no subprocess
    at all. The server migration lands on Linux, so the cheap branch is the
    one that survives.
    """
    if os.name != "nt":
        try:
            with open("/proc/stat", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("btime "):
                        return float(line.split()[1])
        except OSError:
            return None
        return None

    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_OperatingSystem)"
             ".LastBootUpTime.ToString('o')"],
            capture_output=True, text=True)
    except OSError:
        return None
    if out.returncode != 0:
        return None
    stamp = (out.stdout or "").strip()
    if not stamp:
        return None
    try:
        return datetime.datetime.fromisoformat(stamp).timestamp()
    except ValueError:
        return None


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def lock_survey(booted_at, lock_dir=None):
    """Lock files sorted into stale, live and unknown.

    Returns paths rather than verdicts, so the caller decides. `unknown` is
    everything when the boot time could not be read: fail closed, touch
    nothing.
    """
    lock_dir = lock_dir or supervisor._lock_dir()
    found = []
    if os.path.isdir(lock_dir):
        for fn in sorted(os.listdir(lock_dir)):
            fp = os.path.join(lock_dir, fn)
            if os.path.isfile(fp):
                found.append(fp)

    if booted_at is None:
        return {"stale": [], "live": found, "unknown": found}

    stale, live = [], []
    for fp in found:
        mtime = _mtime(fp)
        if mtime is None:
            continue
        (stale if mtime < booted_at else live).append(fp)
    return {"stale": stale, "live": live, "unknown": []}


def lock_pid(path):
    try:
        with open(path, encoding="utf-8") as f:
            return int((f.read() or "0").strip() or 0)
    except (OSError, ValueError):
        return 0


def witnesses(mon, booted_at, now=None):
    """The two witnesses for one monitor, and the verdict they support.

    `status` is UP only when both witnesses hold. Anything else is reported as
    what it is - DOWN, or UNKNOWN when the evidence cannot be trusted - rather
    than rounded to UP, because the whole point of this function is that the
    existing single-witness check says UP too easily.
    """
    now = time.time() if now is None else now
    name = mon["name"]
    state = supervisor._read_state(name)
    state_file = os.path.join(supervisor._state_dir(), "%s.json" % name)
    state_written = _mtime(state_file)

    pid = state.get("pid")
    alive = bool(pid) and singlewalker._alive(pid)
    state_after_boot = (booted_at is not None and state_written is not None
                        and state_written >= booted_at)
    process_witness = bool(alive and state_after_boot)

    beat_epoch = None
    try:
        hb_path = watchsink.heartbeat_path(name)
        if os.path.exists(hb_path):
            with open(hb_path, encoding="utf-8") as f:
                beat = json.load(f)
            if isinstance(beat.get("epoch"), (int, float)):
                beat_epoch = float(beat["epoch"])
    except (OSError, ValueError):
        beat_epoch = None

    interval = mon.get("interval") or DEFAULT_INTERVAL
    beat_age = (now - beat_epoch) if beat_epoch is not None else None
    beat_after_boot = (booted_at is not None and beat_epoch is not None
                       and beat_epoch >= booted_at)
    beat_fresh = (beat_age is not None
                  and beat_age <= interval * STALE_BEAT_MULTIPLE)
    heartbeat_witness = bool(beat_after_boot and beat_fresh)

    if booted_at is None:
        status, why = "UNKNOWN", "boot time unreadable, so neither witness " \
                                 "can be dated"
    elif process_witness and heartbeat_witness:
        status, why = "UP", ""
    elif alive and not state_after_boot:
        status, why = "UNKNOWN", ("its state file predates the boot, so the "
                                  "pid it names is not the pid that wrote it")
    elif process_witness and not heartbeat_witness:
        status, why = "DOWN", ("process alive but no fresh beat since boot - "
                               "running and not working is still not up")
    elif heartbeat_witness and not process_witness:
        status, why = "DOWN", ("a beat since boot but no live process - it "
                               "started and died")
    else:
        status, why = "DOWN", "neither witness"

    return {
        "name": name,
        "module": mon["module"],
        "interval": interval,
        "status": status,
        "why": why,
        "pid": pid if alive else None,
        "witness_process": process_witness,
        "witness_heartbeat": heartbeat_witness,
        "state_written_at": state_written,
        "beat_at": beat_epoch,
        "beat_age": beat_age,
        "restart_count": state.get("restart_count", 0),
        "last_exit_code": state.get("last_exit_code"),
    }


def cursors():
    """Where each watcher last spoke, read-only.

    A heartbeat says WHEN a watcher last spoke. It does not say what it will
    do next, and after a four-hour gap that difference is the whole question:
    a watcher resuming from a cursor picks up where it stopped, one resuming
    from "now" silently skips the gap. Both are reported so the gap is visible
    before anything is started.
    """
    out, now = [], time.time()
    for row in watchsink.heartbeats():
        epoch = row.get("epoch")
        out.append({
            "watcher": row.get("watcher") or row.get("source"),
            "state": row.get("state"),
            "beat_at": epoch,
            "age_seconds": (now - epoch)
            if isinstance(epoch, (int, float)) else None,
            "note": row.get("note"),
        })
    return sorted(out, key=lambda r: (r["watcher"] or ""))


def build_plan(booted_at=None):
    booted_at = boot_time() if booted_at is None else booted_at
    monitors = [witnesses(m, booted_at) for m in supervisor.MONITORS]
    return {
        "at": datetime.datetime.now(
            datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "booted_at": booted_at,
        "uptime_seconds": (time.time() - booted_at) if booted_at else None,
        "boot_time_readable": booted_at is not None,
        "locks": lock_survey(booted_at),
        "monitors": monitors,
        "up": [m["name"] for m in monitors if m["status"] == "UP"],
        "not_up": [m["name"] for m in monitors if m["status"] != "UP"],
        "cursors": cursors(),
        "work_dir": os.path.dirname(store.queue_path()),
    }


def age(seconds):
    if seconds is None:
        return "-"
    if seconds < 90:
        return "%.0fs" % seconds
    if seconds < 5400:
        return "%.0fm" % (seconds / 60)
    return "%.1fh" % (seconds / 3600)


def format_plan(plan):
    lines = []
    if not plan["boot_time_readable"]:
        lines.append(
            "BOOT TIME UNKNOWN. No lock will be cleared and no monitor can be "
            "confirmed: both witnesses are dated against the boot. Clearing a "
            "live monitor's lock is worse than leaving a dead one's.")
    else:
        lines.append("booted %s ago  (%s)" % (
            age(plan["uptime_seconds"]),
            datetime.datetime.fromtimestamp(
                plan["booted_at"]).strftime("%Y-%m-%d %H:%M:%S")))
    lines.append("work   %s" % plan["work_dir"])
    lines.append("")

    lines.append("%-30s %-8s %-5s %-5s %-8s %-9s %s" % (
        "MONITOR", "STATUS", "PROC", "BEAT", "PID", "BEAT_AGE", "NOTE"))
    lines.append("-" * 104)
    for m in plan["monitors"]:
        lines.append("%-30s %-8s %-5s %-5s %-8s %-9s %s" % (
            m["name"], m["status"],
            "yes" if m["witness_process"] else "no",
            "yes" if m["witness_heartbeat"] else "no",
            m["pid"] or "-", age(m["beat_age"]), m["why"]))

    lines.append("")
    lines.append("%d of %d monitors have two witnesses." % (
        len(plan["up"]), len(plan["monitors"])))

    locks = plan["locks"]
    if locks["stale"]:
        lines.append("")
        lines.append("STALE LOCKS - mtime predates the boot, so the pid "
                     "inside belongs to something else now:")
        for fp in locks["stale"]:
            lines.append("    %-40s pid %s" % (os.path.basename(fp),
                                               lock_pid(fp)))
    if locks["live"]:
        lines.append("")
        lines.append("LOCKS WRITTEN SINCE THE BOOT - left alone:")
        for fp in locks["live"]:
            lines.append("    %-40s pid %s" % (os.path.basename(fp),
                                               lock_pid(fp)))

    if plan["cursors"]:
        lines.append("")
        lines.append("%-34s %-12s %s" % ("WATCHER", "LAST BEAT", "STATE"))
        lines.append("-" * 70)
        for c in plan["cursors"]:
            lines.append("%-34s %-12s %s" % (
                c["watcher"], age(c["age_seconds"]), c["state"] or "-"))

    lines.append("")
    lines.append("PLAN ONLY - nothing started, nothing removed. "
                 "--start clears the stale locks and starts the supervisor.")
    return "\n".join(lines)


def clear_stale_locks(plan, dry_run=False):
    """Remove the locks that provably predate the boot. Returns what went."""
    removed = []
    for fp in plan["locks"]["stale"]:
        if dry_run:
            removed.append(fp)
            continue
        try:
            os.unlink(fp)
            removed.append(fp)
        except OSError as exc:                                  # noqa: BLE001
            print("could not remove %s: %s" % (fp, exc))
    return removed


def supervisor_already_running(plan):
    """True when any monitor has a live process from a post-boot state file.

    ONE INSTANCE EACH. A second supervisor would spawn a second copy of every
    monitor, and two reply watchers on one cursor is the failure `singlewalker`
    exists to prevent. The per-monitor locks would refuse the duplicates, but
    refusing eight children one at a time is a worse way to find out than not
    starting.
    """
    return any(m["witness_process"] for m in plan["monitors"])


def verify(deadline=VERIFY_DEADLINE, poll=10, started_at=None, out=print):
    """Poll until every monitor has two witnesses, or the deadline passes.

    Returns `(ok, elapsed_seconds, plan)`. `elapsed` is measured from
    `started_at` when given - so a recovery time can be quoted from the boot
    rather than from whenever somebody happened to run this.
    """
    t0 = time.time()
    started_at = t0 if started_at is None else started_at
    plan = None
    while True:
        plan = build_plan()
        if not plan["not_up"]:
            return True, time.time() - started_at, plan
        if time.time() - t0 >= deadline:
            out("gave up after %s; still not up: %s" % (
                age(time.time() - t0), ", ".join(plan["not_up"])))
            return False, time.time() - started_at, plan
        out("  waiting on %d: %s" % (len(plan["not_up"]),
                                     ", ".join(plan["not_up"])))
        time.sleep(poll)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Bring the estate back after a machine restart.")
    p.add_argument("--start", action="store_true",
                   help="Clear stale locks and start the supervisor. Without "
                        "this the script only plans.")
    p.add_argument("--verify", action="store_true",
                   help="Poll until every monitor has two witnesses, and "
                        "report the recovery time.")
    p.add_argument("--dry-run", action="store_true",
                   help="With --start: say what would be cleared and start "
                        "nothing.")
    p.add_argument("--deadline", type=int, default=VERIFY_DEADLINE,
                   help="Seconds --verify will wait (default %d)."
                        % VERIFY_DEADLINE)
    p.add_argument("--json", action="store_true",
                   help="Emit the plan as JSON.")
    args = p.parse_args(argv)

    plan = build_plan()
    print(json.dumps(plan, indent=2, sort_keys=True) if args.json
          else format_plan(plan))

    if args.verify and not args.start:
        print()
        ok, elapsed, _ = verify(deadline=args.deadline,
                                started_at=plan["booted_at"])
        print("recovery %s since boot" % age(elapsed) if plan["booted_at"]
              else "recovery %s" % age(elapsed))
        return 0 if ok else 1

    if not args.start:
        return 0

    print()
    if supervisor_already_running(plan):
        print("REFUSING: a monitor is already running with a post-boot state "
              "file, so a supervisor is up. One instance each - start a "
              "second and every monitor gets a twin.")
        return 1

    removed = clear_stale_locks(plan, dry_run=args.dry_run)
    print("cleared %d stale lock(s)" % len(removed) if removed
          else "no stale locks to clear")

    if args.dry_run:
        print("--dry-run: the supervisor was NOT started")
        return 0

    print("starting the supervisor; it starts every declared monitor in "
          "order and restarts them with backoff")
    sys.stdout.flush()
    supervisor._run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
