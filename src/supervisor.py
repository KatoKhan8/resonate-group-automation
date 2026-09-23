"""One supervisor for every monitor, replacing nohup.

WHY THIS EXISTS. Monitors are launched with bare nohup: nothing stops two of
the same one running, nothing restarts a crashed one, nothing notices when
one dies. A watcher that is not running is indistinguishable from one
reporting no activity. CLAUDE.md's handoff records `bison_watch_loop`
surviving a breaking change "only because it predates the guard by 3h and
holds the old module in memory; any restart would have killed the only
LinkedIn monitor". That is the shape of the problem.

WHAT THIS USES. `src/singlewalker.py` for per-monitor locks - a second
implementation of a lock is how the two disagree. `src/watchsink.py` for
heartbeat reading - the supervisor does not invent a parallel heartbeat
format. `src/notify.py` for notifications - never a direct Slack call.

WHAT THIS DOES NOT DO. The loops themselves are not modified - the
supervisor runs `scripts/*_watch_loop.py` UNMODIFIED. No production state is
touched. No daemonising, no pidfile of its own - foreground process, logs to
stdout/stderr, SIGTERM stops children cleanly, ready for systemd.

THE INTERPRETER is `sys.executable`, resolved once. Not `py -3`, not
`python`, not a PATH lookup. `py -3` does not exist on Linux and this must
survive the server migration unchanged.
"""
import json
import os
import signal
import subprocess
import sys
import time

from . import keepawake, notify, singlewalker, store

# --------------------------------------------------------- monitor table
#
# DATA, NOT CODE. A monitor can be added without editing the supervisor.
# Re-derived from the 2026-09-22 morning handoff §8.
#
# `interval` is the monitor's own poll interval, carried for informational
# purposes and for the reset threshold (a run lasting 2x the interval is
# considered clean). `slack_agent` has no interval - it is a long-lived
# event-driven loop.
#
# `is_script` marks entries whose `module` is a file path rather than a
# dotted module name. Production monitors all use dotted module names; the
# flag exists so tests can spawn fixture scripts.

MONITORS = [
    {"name": "bison_mailbox_utilisation",
     "module": "scripts.bison_mailbox_utilisation",
     "args": ["--interval", "300"], "interval": 300},
    {"name": "reply_watch",
     "module": "scripts.reply_watch_loop",
     "args": ["--interval", "300"], "interval": 300},
    {"name": "notify_deliver",
     "module": "scripts.notify_deliver_loop",
     "args": ["--interval", "60"], "interval": 60},
    {"name": "bison_watch_487",
     "module": "scripts.bison_watch_loop",
     "args": ["--campaign", "487", "--interval", "180"], "interval": 180},
    {"name": "bison_watch_489",
     "module": "scripts.bison_watch_loop",
     "args": ["--campaign", "489", "--interval", "180"], "interval": 180},
    {"name": "heyreach_watch",
     "module": "scripts.heyreach_watch_loop",
     "args": ["--interval", "300"], "interval": 300},
    {"name": "digest",
     "module": "scripts.digest_loop",
     "args": ["--interval", "300"], "interval": 300},
    {"name": "slack_agent",
     "module": "scripts.slack_agent_loop",
     "args": [], "interval": None},
]

# --------------------------------------------------------- backoff
#
# Start at 30 SECONDS, not 1. A provider returning 429 answered by an
# instant restart is a self-inflicted rate limit. Double to a ceiling of
# 10 minutes. Reset on a clean run.

INITIAL_DELAY = 30
CEILING_DELAY = 600
# A run lasting at least 2x this threshold is considered clean and resets
# the backoff. For monitors with an interval, the threshold is 2x the
# interval. For interval-less monitors (slack_agent), 600s.
CLEAN_RUN_THRESHOLD = 600


def _backoff_delays():
    """The backoff sequence, pre-computed. 30, 60, 120, 240, 480, 600, 600..."""
    delays = []
    current = INITIAL_DELAY
    for _ in range(20):
        delays.append(min(current, CEILING_DELAY))
        current *= 2
    return delays


_BACKOFF_TABLE = _backoff_delays()


def _next_delay(consecutive_failures=1, last_run_duration=0,
                clean_threshold=CLEAN_RUN_THRESHOLD):
    """The delay before the next restart.

    `consecutive_failures` is 1-indexed: the first failure gets index 0 in
    the table (30s), the second gets index 1 (60s), etc.

    A run lasting at least `clean_threshold` seconds resets the counter, so
    a monitor that ran for an hour before crashing gets 30s, not 10 minutes.
    """
    if last_run_duration >= clean_threshold:
        return INITIAL_DELAY
    idx = min(consecutive_failures - 1, len(_BACKOFF_TABLE) - 1)
    return _BACKOFF_TABLE[max(0, idx)]


# --------------------------------------------------------- lock paths

def _lock_dir():
    """Where per-monitor lock files live. Beside the queue, not under work/."""
    return os.path.abspath(
        os.environ.get("SUPERVISOR_LOCKS")
        or os.path.join(os.path.dirname(store.queue_path()),
                        "supervisor-locks"))


def _lock_path(name, lock_dir=None):
    return os.path.join(lock_dir or _lock_dir(), "%s.lock" % name)


# --------------------------------------------------------- state file

def _state_dir():
    return os.path.abspath(
        os.environ.get("SUPERVISOR_STATE")
        or os.path.join(os.path.dirname(store.queue_path()),
                        "supervisor"))


def _write_state(mon, state_dir, pid=None, exit_code=None,
                 restart_count=None):
    """Record a monitor's current state. Beside the queue, not under work/."""
    directory = state_dir or _state_dir()
    store.refuse_production_write(directory)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "%s.json" % mon["name"])
    existing = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:                                       # noqa: BLE001
            existing = {}
    existing["name"] = mon["name"]
    if pid is not None:
        existing["pid"] = pid
        existing["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime())
    if exit_code is not None:
        existing["last_exit_code"] = exit_code
        existing["last_exit_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                 time.gmtime())
    if restart_count is not None:
        existing["restart_count"] = restart_count
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(existing, f, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _read_state(name, state_dir=None):
    directory = state_dir or _state_dir()
    path = os.path.join(directory, "%s.json" % name)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:                                           # noqa: BLE001
        return {}


# --------------------------------------------------------- spawn / stop

def _spawn(mon, lock_dir=None, state_dir=None):
    """Start one monitor. Acquires its singlewalker lock first.

    Raises `singlewalker.AlreadyWalking` if the lock is held by a live
    process - which is the whole point: a second supervisor, or a
    hand-started monitor of the same name, is refused.
    """
    lock = _lock_path(mon["name"], lock_dir)
    singlewalker.acquire(lock)
    try:
        cmd = _build_command(mon)
        proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
        _write_state(mon, state_dir, pid=proc.pid)
        return proc
    except Exception:
        singlewalker.release(lock)
        raise


def _build_command(mon):
    """The command to start a monitor. sys.executable, always."""
    if mon.get("is_script"):
        return [sys.executable, mon["module"]] + list(mon.get("args") or [])
    return ([sys.executable, "-m", mon["module"]]
            + list(mon.get("args") or []))


def _stop_child(proc):
    """SIGTERM, then wait. No orphan left behind."""
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
    except OSError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


# --------------------------------------------------------- death tracker

class _DeathTracker:
    """Track monitor deaths and decide when to notify.

    A monitor that dies twice in an hour produces exactly ONE notification -
    not one per death, and not one per supervisor tick. After a notification
    fires, the window resets so a persistent failure does not spam.
    """

    WINDOW = 3600  # one hour

    def __init__(self):
        self._deaths = {}     # name -> [timestamps]
        self._notified = {}   # name -> last notification timestamp

    def record_death(self, name, now=None):
        """Record a death. Returns True if a notification should fire."""
        now = time.time() if now is None else now
        deaths = self._deaths.setdefault(name, [])
        deaths.append(now)
        # Prune deaths outside the window
        cutoff = now - self.WINDOW
        self._deaths[name] = [t for t in deaths if t > cutoff]
        deaths = self._deaths[name]

        if len(deaths) < 2:
            return False
        # Two deaths in the window. Have we already notified for this pair?
        last_notified = self._notified.get(name, 0)
        # Notify if we haven't notified since the second death in this window
        if last_notified < deaths[-2]:
            self._notified[name] = now
            return True
        return False


def _notify_death(name, exit_code, restart_count):
    """Send a notification through the existing routing table.

    Uses FAILED_JOB - a monitor dying twice in an hour is a job that failed
    and needs attention. Routed to (GLOBAL, ACTION_REQUIRED).
    """
    notify.notify(
        notify.FAILED_JOB,
        fields={
            "job_name": "monitor:%s" % name,
            "exit_code": str(exit_code),
            "restart_count": str(restart_count),
            "detail": ("Monitor %s has died twice in one hour (exit %s, "
                       "%d restarts). It is being restarted but needs "
                       "human attention."
                       % (name, exit_code, restart_count)),
        },
        ids={"monitor": name},
    )


# --------------------------------------------------------- status

def _monitor_status(mon, lock_dir=None, state_dir=None):
    """The status of one monitor: UP or DOWN, pid, heartbeat age, exit code,
    restart count."""
    name = mon["name"]
    state = _read_state(name, state_dir)

    result = {
        "name": name,
        "module": mon["module"],
        "interval": mon.get("interval"),
        "status": "DOWN",
        "pid": None,
        "last_exit_code": state.get("last_exit_code"),
        "last_exit_at": state.get("last_exit_at"),
        "restart_count": state.get("restart_count", 0),
        "heartbeat_age": None,
    }

    # Check if the child process is alive, using the PID from the state
    # file (which is the CHILD's PID, not the supervisor's).
    child_pid = state.get("pid")
    if child_pid and singlewalker._alive(child_pid):
        result["status"] = "UP"
        result["pid"] = child_pid

    # Read heartbeat age from watchsink
    from . import watchsink
    try:
        hb_path = watchsink.heartbeat_path(name)
        if os.path.exists(hb_path):
            with open(hb_path, encoding="utf-8") as f:
                hb = json.load(f)
            epoch = hb.get("epoch")
            if isinstance(epoch, (int, float)):
                result["heartbeat_age"] = time.time() - epoch
    except Exception:                                           # noqa: BLE001
        pass

    return result


def format_status(monitors, lock_dir=None, state_dir=None):
    """Format the status of all monitors for --status output.

    A declared-but-not-running monitor is visibly DOWN rather than absent
    from the output - that is the whole point, and an absent row reads as
    "fine" to a tired reader at 2am.
    """
    lines = []
    lines.append("%-30s %-6s %-8s %-12s %-8s %s" % (
        "MONITOR", "STATUS", "PID", "EXIT_CODE", "RESTARTS", "HB_AGE"))
    lines.append("-" * 90)
    for mon in monitors:
        st = _monitor_status(mon, lock_dir, state_dir)
        hb = ("%.0fs" % st["heartbeat_age"]
              if st["heartbeat_age"] is not None else "-")
        exit_code = (str(st["last_exit_code"])
                     if st["last_exit_code"] is not None else "-")
        lines.append("%-30s %-6s %-8s %-12s %-8s %s" % (
            st["name"], st["status"],
            str(st["pid"]) if st["pid"] else "-",
            exit_code, st["restart_count"], hb))
    return "\n".join(lines)


# --------------------------------------------------------- main loop

def _run(monitors=None, lock_dir=None, state_dir=None):
    """The supervisor main loop. Foreground, logs to stdout/stderr.

    Starts every declared monitor, polls for exits, restarts crashed ones
    with backoff, notifies on repeated deaths, propagates SIGTERM.
    """
    monitors = monitors if monitors is not None else MONITORS
    tracker = _DeathTracker()
    children = {}           # name -> Popen
    failures = {}           # name -> consecutive failure count
    started_at = {}         # name -> time.time() when last started
    pending_restart = {}    # name -> time to restart at

    # SIGTERM: stop everything and exit
    stopping = [False]

    def _handle_sigterm(signum, frame):
        stopping[0] = True

    old_handler = signal.signal(signal.SIGTERM, _handle_sigterm)

    # THE POWER REQUEST, held on the main thread for as long as the
    # supervisor runs. `docs/MACHINE-HARDENING-2026-09-23.md` 6 specifies
    # exactly this and records why it was not done there: `keepawake` landed
    # on master with no caller because this file lives on `infra`, and the
    # production session does not edit another session's in-flight files.
    # This is that one line, on the side of the rule that owns the file.
    #
    # It does NOT raise when refused. A supervisor that cannot take a power
    # request should still supervise - loudly, so that
    # `powercfg /requests` showing nothing is a known state rather than a
    # mystery at 2am.
    with keepawake.KeepAwake() as awake:
        if not awake.entered_ok:
            print("SUPERVISOR KEEP-AWAKE REFUSED %s - the machine may sleep "
                  "while the monitors run" % (awake.error,), flush=True)
        else:
            print("SUPERVISOR keep-awake held; powercfg /requests should now "
                  "name this process", flush=True)
        return _supervise(monitors, lock_dir, state_dir, tracker, children,
                          failures, started_at, pending_restart, stopping,
                          old_handler)


def _supervise(monitors, lock_dir, state_dir, tracker, children, failures,
               started_at, pending_restart, stopping, old_handler):
    """The loop itself, so `_run` reads as what it guarantees: the power
    request is held around everything below and released on every exit."""
    try:
        # Start every monitor
        for mon in monitors:
            try:
                proc = _spawn(mon, lock_dir)
                children[mon["name"]] = proc
                failures[mon["name"]] = 0
                started_at[mon["name"]] = time.time()
                print("SUPERVISOR started %s (pid %d)"
                      % (mon["name"], proc.pid), flush=True)
            except singlewalker.AlreadyWalking as e:
                print("SUPERVISOR skipped %s: %s"
                      % (mon["name"], e), flush=True)

        # Poll loop
        while not stopping[0]:
            time.sleep(1)
            now = time.time()

            for mon in monitors:
                name = mon["name"]
                proc = children.get(name)
                if proc is None:
                    # Check if it is time for a pending restart
                    restart_at = pending_restart.get(name, 0)
                    if restart_at and now >= restart_at:
                        try:
                            proc = _spawn(mon, lock_dir)
                            children[name] = proc
                            started_at[name] = now
                            del pending_restart[name]
                            print("SUPERVISOR restarted %s (pid %d)"
                                  % (name, proc.pid), flush=True)
                        except singlewalker.AlreadyWalking as e:
                            print("SUPERVISOR cannot restart %s: %s"
                                  % (name, e), flush=True)
                    continue

                # Check if the child has exited
                ret = proc.poll()
                if ret is None:
                    continue

                # Child exited
                duration = now - started_at.get(name, now)
                children.pop(name, None)
                _write_state(mon, state_dir, exit_code=ret)

                print("SUPERVISOR %s exited with code %s after %.0fs"
                      % (name, ret, duration), flush=True)

                # Release the lock so we can re-acquire on restart
                singlewalker.release(_lock_path(name, lock_dir))

                # Track deaths and maybe notify
                if tracker.record_death(name, now):
                    state = _read_state(name, state_dir)
                    restart_count = state.get("restart_count", 0) + 1
                    _write_state(mon, state_dir,
                                 restart_count=restart_count)
                    _notify_death(name, ret, restart_count)
                    print("SUPERVISOR notified for %s (died twice in 1h)"
                          % name, flush=True)

                # Schedule restart with backoff
                count = failures.get(name, 0) + 1
                failures[name] = count
                delay = _next_delay(consecutive_failures=count,
                                    last_run_duration=duration)
                pending_restart[name] = now + delay
                print("SUPERVISOR will restart %s in %.0fs"
                      % (name, delay), flush=True)

                # A clean run resets the failure count
                clean_threshold = max(CLEAN_RUN_THRESHOLD,
                                      (mon.get("interval") or 300) * 2)
                if duration >= clean_threshold:
                    failures[name] = 0

    finally:
        signal.signal(signal.SIGTERM, old_handler or signal.SIG_DFL)
        # Stop every child
        for name, proc in list(children.items()):
            print("SUPERVISOR stopping %s (pid %s)"
                  % (name, proc.pid), flush=True)
            _stop_child(proc)
        # Release every lock
        for mon in monitors:
            singlewalker.release(_lock_path(mon["name"], lock_dir))
        print("SUPERVISOR stopped", flush=True)
