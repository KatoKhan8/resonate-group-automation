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

# The two-witness rule, the boot time and the staleness tolerance all live in
# `src/supervisor.py` and are imported rather than reimplemented here. This
# file carried its own copy for one afternoon, and that copy looked up
# `watchsink.heartbeat_path(monitor_name)` - which matches the real heartbeat
# file of exactly ZERO of the eight monitors. `--verify` would have polled for
# ten minutes, timed out, and reported a recovery time that meant nothing.
#
# Two implementations of one liveness rule is how a status board and a
# recovery check come to disagree about whether the estate is up.
#: How long a full recovery is allowed to take before `--verify` gives up.
#: The machine rebooted in three minutes on 2026-09-23; a supervisor that has
#: not brought every monitor up in ten is not slow, it is stuck.
VERIFY_DEADLINE = 600

witnesses = supervisor.witnesses
boot_time = supervisor.boot_time
STALE_BEAT_MULTIPLE = supervisor.STALE_BEAT_MULTIPLE
DEFAULT_INTERVAL = supervisor.DEFAULT_INTERVAL


def lock_survey(booted_at, lock_dir=None):
    """Lock files sorted into stale, live and unknown.

    Returns paths rather than verdicts, so the caller decides. `unknown` is
    everything when the boot time could not be read: fail closed, touch
    nothing - deleting a live monitor's lock is worse than leaving a dead
    one's.
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
        try:
            mtime = os.path.getmtime(fp)
        except OSError:
            continue
        (stale if mtime < booted_at else live).append(fp)
    return {"stale": stale, "live": live, "unknown": []}


def lock_pid(path):
    try:
        with open(path, encoding="utf-8") as f:
            return int((f.read() or "0").strip() or 0)
    except (OSError, ValueError):
        return 0


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
