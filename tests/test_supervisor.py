"""One supervisor for every monitor, replacing nohup.

The recurring failure class: monitors launched with bare nohup, so nothing
stops two of the same one running, nothing restarts a crashed one, and
nothing notices when one dies. A watcher that is not running is
indistinguishable from one reporting no activity.

These tests use FIXTURE monitors - small scripts that exit on command - and
never touch production state.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import store, supervisor, singlewalker  # noqa: E402


def _fixture_script(body):
    """Write a temp Python script and return its path."""
    fd, path = tempfile.mkstemp(suffix=".py", prefix="fixture-monitor-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    return path


class _SupervisorTestBase(unittest.TestCase):
    """Isolate the store and give every test a throwaway state directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-supervisor-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._env = {k: os.environ.get(k)
                     for k in ("QUEUE", "OUT") + store.STATE_OVERRIDES}
        self.addCleanup(self._restore_env)
        store.use_directory(os.path.join(self.tmp, "work"))
        self.state_dir = os.path.join(self.tmp, "supervisor-state")
        os.makedirs(self.state_dir, exist_ok=True)
        self.lock_dir = os.path.join(self.tmp, "locks")
        os.makedirs(self.lock_dir, exist_ok=True)

    def _restore_env(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class InterpreterTest(_SupervisorTestBase):
    """The interpreter is sys.executable, asserted by reading the spawned
    command, not by grepping the source."""

    def test_the_spawned_command_uses_sys_executable(self):
        script = _fixture_script("import sys; sys.exit(0)")
        self.addCleanup(os.unlink, script)
        mon = {"name": "fixture_interp", "module": script,
               "args": [], "interval": 60, "is_script": True}
        proc = supervisor._spawn(mon, self.lock_dir, self.state_dir)
        self.addCleanup(_kill_proc, proc)
        # The command list starts with sys.executable
        self.assertEqual(sys.executable, proc.cmd_args[0]
                         if hasattr(proc, "cmd_args")
                         else proc.args[0])
        proc.terminate()
        proc.wait(timeout=5)


class LockTest(_SupervisorTestBase):
    """Two supervisors, or a supervisor plus a hand-started monitor of the
    same name, cannot both run it. The second refuses with AlreadyWalking.
    Test with two real processes, not by calling acquire twice in one."""

    def test_two_supervisors_cannot_run_the_same_monitor(self):
        script = _fixture_script(
            "import time; time.sleep(30)")
        self.addCleanup(os.unlink, script)
        mon = {"name": "fixture_lock", "module": script,
               "args": [], "interval": 60, "is_script": True}

        proc1 = supervisor._spawn(mon, self.lock_dir, self.state_dir)
        self.addCleanup(_kill_proc, proc1)

        # A second spawn of the same monitor must fail
        with self.assertRaises(singlewalker.AlreadyWalking):
            supervisor._spawn(mon, self.lock_dir, self.state_dir)

        proc1.terminate()
        proc1.wait(timeout=5)

    def test_a_hand_started_holder_blocks_the_supervisor(self):
        """If something else holds the lock, the supervisor refuses."""
        lock = os.path.join(self.lock_dir, "fixture_hand.lock")
        singlewalker.acquire(lock)
        self.addCleanup(singlewalker.release, lock)

        mon = {"name": "fixture_hand", "module": "scripts.noop",
               "args": [], "interval": 60}
        with self.assertRaises(singlewalker.AlreadyWalking):
            supervisor._spawn(mon, self.lock_dir)


class RestartBackoffTest(_SupervisorTestBase):
    """A monitor that exits non-zero is restarted; the interval doubles;
    it caps. Driven with a fixture monitor that exits on command."""

    def test_backoff_starts_at_30_seconds_and_doubles_to_cap(self):
        delays = supervisor._backoff_delays()
        self.assertEqual(30, delays[0])
        self.assertEqual(60, delays[1])
        self.assertEqual(120, delays[2])
        self.assertEqual(240, delays[3])
        self.assertEqual(480, delays[4])
        # Caps at 600 (10 minutes)
        self.assertEqual(600, delays[5])
        self.assertEqual(600, delays[6])

    def test_backoff_resets_after_a_clean_run(self):
        """A monitor that ran for long enough before crashing resets the
        backoff to the initial 30 seconds."""
        # A clean run is one that lasted at least the reset threshold
        delay = supervisor._next_delay(consecutive_failures=3,
                                       last_run_duration=700)
        self.assertEqual(30, delay)

    def test_backoff_does_not_reset_after_a_short_run(self):
        delay = supervisor._next_delay(consecutive_failures=3,
                                       last_run_duration=10)
        # 3 consecutive failures: 30 * 2^2 = 120
        self.assertEqual(120, delay)


class StatusTest(_SupervisorTestBase):
    """--status shows a declared-but-not-running monitor as DOWN."""

    def test_a_declared_but_not_running_monitor_is_visibly_down(self):
        mon = {"name": "fixture_down", "module": "scripts.noop",
               "args": [], "interval": 60}
        state = supervisor._monitor_status(mon, self.lock_dir,
                                           self.state_dir)
        self.assertEqual("DOWN", state["status"])
        self.assertEqual("fixture_down", state["name"])

    def test_status_shows_pid_when_running(self):
        script = _fixture_script(
            "import time; time.sleep(30)")
        self.addCleanup(os.unlink, script)
        mon = {"name": "fixture_status", "module": script,
               "args": [], "interval": 60, "is_script": True}
        proc = supervisor._spawn(mon, self.lock_dir, self.state_dir)
        self.addCleanup(_kill_proc, proc)
        try:
            state = supervisor._monitor_status(mon, self.lock_dir,
                                               self.state_dir)
            # UP_ONE_WITNESS, not UP. This fixture sleeps and writes no
            # heartbeat, and `_monitor_status` is now the two-witness verdict:
            # a live pid alone is forgeable across a reboot, and a monitor
            # that cannot prove it is WORKING must not read the same as one
            # that has. The pid is still reported, which is what this test is
            # actually about.
            self.assertEqual("UP_ONE_WITNESS", state["status"])
            self.assertTrue(state["witness_process"])
            self.assertEqual(proc.pid, state["pid"])
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_status_shows_last_exit_code(self):
        mon = {"name": "fixture_exit", "module": "scripts.noop",
               "args": [], "interval": 60}
        # Write a state file with a known exit code
        state_file = os.path.join(self.state_dir, "fixture_exit.json")
        os.makedirs(self.state_dir, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"name": "fixture_exit", "last_exit_code": 42,
                        "last_exit_at": "2026-09-22T12:00:00Z",
                        "restart_count": 3}, f)
        state = supervisor._monitor_status(mon, self.lock_dir,
                                           self.state_dir)
        self.assertEqual(42, state["last_exit_code"])
        self.assertEqual(3, state["restart_count"])


class NotificationTest(_SupervisorTestBase):
    """A monitor that dies twice in an hour produces exactly ONE
    notification - not one per death, and not one per supervisor tick."""

    def test_two_deaths_in_an_hour_triggers_one_notification(self):
        tracker = supervisor._DeathTracker()
        now = 1000000.0
        # First death - no notification yet
        result1 = tracker.record_death("fixture_notify", now)
        self.assertFalse(result1)
        # Second death within the hour - notification triggered
        result2 = tracker.record_death("fixture_notify",
                                       now + 1800)
        self.assertTrue(result2)
        # Third death - already notified, no duplicate
        result3 = tracker.record_death("fixture_notify",
                                       now + 2400)
        self.assertFalse(result3)

    def test_deaths_spread_over_two_hours_each_pair_triggers(self):
        tracker = supervisor._DeathTracker()
        now = 1000000.0
        # First pair
        tracker.record_death("fixture_pair", now)
        triggered = tracker.record_death("fixture_pair", now + 600)
        self.assertTrue(triggered)
        # After the window passes, a new pair should trigger again
        later = now + 7200  # 2 hours later
        result = tracker.record_death("fixture_pair", later)
        self.assertFalse(result)  # only one death in new window
        result2 = tracker.record_death("fixture_pair", later + 600)
        self.assertTrue(result2)  # second death in new window


class SigtermTest(_SupervisorTestBase):
    """SIGTERM to the supervisor stops every child. No orphans. Assert by
    pid."""

    def test_sigterm_stops_every_child(self):
        script = _fixture_script(
            "import time, signal\n"
            "signal.signal(signal.SIGTERM, signal.SIG_DFL)\n"
            "time.sleep(60)")
        self.addCleanup(os.unlink, script)

        children = []
        for i in range(3):
            mon = {"name": "fixture_sigterm_%d" % i, "module": script,
                   "args": [], "interval": 60, "is_script": True}
            proc = supervisor._spawn(mon, self.lock_dir, self.state_dir)
            children.append(proc)

        # Give them a moment to start
        time.sleep(0.5)
        pids = [p.pid for p in children]

        # Stop all children via the supervisor's stop function
        for proc in children:
            supervisor._stop_child(proc)

        # Assert every child is gone
        for pid in pids:
            self.assertFalse(_pid_alive(pid),
                             "pid %d should be dead after SIGTERM" % pid)


class ProductionWriteTest(_SupervisorTestBase):
    """The supervisor writes nothing under work/ in a test."""

    def test_no_write_under_work(self):
        """The supervisor state goes to its own directory, not work/."""
        mon = {"name": "fixture_nowrite", "module": "scripts.noop",
               "args": [], "interval": 60}
        supervisor._write_state(mon, self.state_dir, pid=None,
                                exit_code=None)
        state_file = os.path.join(self.state_dir, "fixture_nowrite.json")
        self.assertTrue(os.path.exists(state_file))
        # Nothing in the work directory
        work_dir = os.path.join(self.tmp, "work")
        if os.path.isdir(work_dir):
            supervisor_files = [f for f in os.listdir(work_dir)
                                if "supervisor" in f.lower()]
            self.assertEqual([], supervisor_files)


class MonitorTableTest(_SupervisorTestBase):
    """The monitor table is data, not code."""

    #: A registry the derived half can be computed from without touching
    #: `work/`. Injected rather than read so these tests assert the table's
    #: SHAPE and do not depend on which campaigns happen to be live.
    ROWS = [
        {"campaign_id": "c491", "status": "running", "bison_campaign_id": 491},
        {"campaign_id": "c489", "status": "completed", "bison_campaign_id": 489,
         "completed_at": "2026-08-01T00:00:00Z"},
        {"campaign_id": "hr", "status": "running",
         "heyreach_campaign_id": 605732},
    ]

    def _table(self):
        return supervisor.monitors(rows=self.ROWS,
                                   sequence_source=lambda p, c: 0)

    def test_the_table_is_a_list_of_dicts(self):
        table = self._table()
        self.assertIsInstance(table, list)
        for mon in table:
            self.assertIn("name", mon)
            self.assertIn("module", mon)
            self.assertIn("interval", mon)

    def test_every_monitor_has_a_unique_name(self):
        names = [m["name"] for m in self._table()]
        self.assertEqual(len(names), len(set(names)))

    def test_known_monitors_are_present(self):
        """The STATIC loops. The campaign watchers are derived and are
        asserted in tests/test_the_derived_table_is_the_incident_gates_15.py
        instead - naming
        a campaign here would put a second hand-written list in the repo,
        which is the thing the one-table decision removed."""
        names = {m["name"] for m in self._table()}
        for expected in ("reply_watch", "notify_deliver", "digest",
                         "slack_agent", "slack_followup"):
            self.assertIn(expected, names,
                          "%s missing from the monitor table" % expected)

    def test_bison_mailbox_utilisation_is_not_in_the_table(self):
        """OPERATOR DECISION 2026-09-23. It writes no heartbeat, so it can
        never have a second witness and can never be verified; counting it UP
        on a pid alone is the claim a reused pid forges across a reboot.
        Whether it is a loop or a nightly job is production's call."""
        names = {m["name"] for m in self._table()}
        self.assertNotIn("bison_mailbox_utilisation", names)

    def test_the_derived_half_is_present(self):
        names = {m["name"] for m in self._table()}
        self.assertIn("bison_watch_491", names)
        self.assertIn("heyreach_watch_605732", names)
        # 489 finished long ago and the source says nothing is in sequence.
        self.assertNotIn("bison_watch_489", names)


class SupervisorIntegrationTest(_SupervisorTestBase):
    """End-to-end: a supervisor running fixture monitors, with restart
    and status."""

    def test_a_crashed_monitor_is_restarted(self):
        """A fixture that exits non-zero is restarted by the supervisor."""
        # Create a script that exits with code 1 the first time, then
        # sleeps forever. We use a marker file to distinguish first vs
        # subsequent runs.
        marker = os.path.join(self.tmp, "marker")
        script = _fixture_script(
            "import os, sys, time\n"
            "marker = %r\n"
            "if not os.path.exists(marker):\n"
            "    open(marker, 'w').close()\n"
            "    sys.exit(1)\n"
            "time.sleep(60)\n" % marker)
        self.addCleanup(os.unlink, script)
        self.addCleanup(_safe_unlink, marker)

        mon = {"name": "fixture_restart", "module": script,
               "args": [], "interval": 60, "is_script": True}

        # Override backoff to be fast for testing
        original = supervisor._next_delay
        supervisor._next_delay = lambda **kw: 0.1
        self.addCleanup(setattr, supervisor, "_next_delay", original)

        # Start the monitor - it will exit 1
        proc1 = supervisor._spawn(mon, self.lock_dir, self.state_dir)
        proc1.wait(timeout=10)
        self.assertEqual(1, proc1.returncode)

        # Release the lock after the child exits (the supervisor's _run
        # does this; we simulate it here since we call _spawn directly)
        singlewalker.release(
            os.path.join(self.lock_dir, "fixture_restart.lock"))

        # Restart it - this time it should stay up
        proc2 = supervisor._spawn(mon, self.lock_dir, self.state_dir)
        self.addCleanup(_kill_proc, proc2)
        time.sleep(0.5)
        self.assertIsNone(proc2.poll())

        proc2.terminate()
        proc2.wait(timeout=5)

    def test_status_output_contains_all_monitors(self):
        """--status shows every declared monitor, even the ones that are
        DOWN."""
        table = supervisor.STATIC_MONITORS
        output = supervisor.format_status(table,
                                          self.lock_dir,
                                          self.state_dir)
        for mon in table:
            self.assertIn(mon["name"], output,
                          "%s missing from --status output" % mon["name"])
        # Every monitor is DOWN since none are running
        self.assertIn("DOWN", output)


def _kill_proc(proc):
    try:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _safe_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _pid_alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid],
                             capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


if __name__ == "__main__":
    unittest.main()
