"""D1: cold start. Two witnesses, one instance, and nothing trusted to a pid.

The 2026-09-23 restart is the case these are written against: the machine was
back in three minutes and the monitors were down for four hours. The scripts
under test bring them back; these tests are about the ways that could report
success while not having done it.

THE CENTRAL ONE. `supervisor._monitor_status` decides a monitor is UP by
asking whether the pid in its state file is alive. Across a reboot that pid
belongs to whatever the kernel handed the number to next, so UP is a
coincidence - and the adoption step in the production handoff is "post
--status showing all UP". Every test below that mentions a witness exists
because of that sentence.
"""
import json
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

from scripts import cold_start
from src import supervisor


MON = {"name": "probe_watch", "module": "scripts.probe_watch_loop",
       "args": [], "interval": 300}

BOOT = 1_000_000.0


class _ColdStartTest(unittest.TestCase):
    """A fake estate: its own state dir, lock dir and heartbeat dir."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-coldstart-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state_dir = os.path.join(self.tmp, "state")
        self.lock_dir = os.path.join(self.tmp, "locks")
        os.makedirs(self.state_dir)
        os.makedirs(self.lock_dir)

        self._patches = [
            mock.patch.object(supervisor, "_state_dir",
                              lambda: self.state_dir),
            mock.patch.object(supervisor, "_lock_dir", lambda: self.lock_dir),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def write_state(self, pid, written_at, name=MON["name"]):
        path = os.path.join(self.state_dir, "%s.json" % name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"pid": pid, "restart_count": 0}, f)
        os.utime(path, (written_at, written_at))
        return path

    def write_beat(self, epoch, name=MON["name"]):
        path = os.path.join(self.tmp, "%s.beat.json" % name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"epoch": epoch, "state": "ok"}, f)
        p = mock.patch("src.watchsink.heartbeat_path", lambda *a, **k: path)
        p.start()
        self.addCleanup(p.stop)
        return path

    def write_lock(self, name, mtime, pid=4321):
        path = os.path.join(self.lock_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(pid))
        os.utime(path, (mtime, mtime))
        return path

    def alive(self, yes):
        p = mock.patch("src.singlewalker._alive", lambda pid: yes)
        p.start()
        self.addCleanup(p.stop)


class TwoWitnessesOrItIsNotUp(_ColdStartTest):

    def test_both_witnesses_is_up(self):
        self.write_state(pid=999, written_at=BOOT + 10)
        self.write_beat(BOOT + 60)
        self.alive(True)

        w = cold_start.witnesses(MON, BOOT, now=BOOT + 100)

        self.assertEqual(w["status"], "UP")
        self.assertTrue(w["witness_process"])
        self.assertTrue(w["witness_heartbeat"])

    def test_a_live_pid_from_a_pre_boot_state_file_is_not_a_witness(self):
        """The forged UP. The pid is alive; it is not this monitor's pid."""
        self.write_state(pid=999, written_at=BOOT - 500)
        self.write_beat(BOOT + 60)
        self.alive(True)

        w = cold_start.witnesses(MON, BOOT, now=BOOT + 100)

        self.assertNotEqual(w["status"], "UP")
        self.assertEqual(w["status"], "UNKNOWN")
        self.assertFalse(w["witness_process"])
        self.assertIn("predates the boot", w["why"])

    def test_a_live_process_with_no_fresh_beat_is_not_up(self):
        """Running is not working. A wedged monitor keeps its pid."""
        self.write_state(pid=999, written_at=BOOT + 10)
        self.write_beat(BOOT + 20)
        self.alive(True)

        # 300s interval, tolerance 2x, so 700s after the beat is stale.
        w = cold_start.witnesses(MON, BOOT, now=BOOT + 720)

        self.assertEqual(w["status"], "DOWN")
        self.assertTrue(w["witness_process"])
        self.assertFalse(w["witness_heartbeat"])

    def test_a_beat_from_before_the_boot_is_not_a_witness(self):
        """A heartbeat from the machine's previous life proves nothing."""
        self.write_state(pid=999, written_at=BOOT + 10)
        self.write_beat(BOOT - 30)
        self.alive(True)

        w = cold_start.witnesses(MON, BOOT, now=BOOT + 60)

        self.assertFalse(w["witness_heartbeat"])
        self.assertEqual(w["status"], "DOWN")

    def test_a_fresh_beat_with_a_dead_process_is_not_up(self):
        self.write_state(pid=999, written_at=BOOT + 10)
        self.write_beat(BOOT + 60)
        self.alive(False)

        w = cold_start.witnesses(MON, BOOT, now=BOOT + 100)

        self.assertEqual(w["status"], "DOWN")
        self.assertIn("started and died", w["why"])

    def test_an_unreadable_boot_time_confirms_nothing(self):
        """Fail closed. Without a boot time neither witness can be dated."""
        self.write_state(pid=999, written_at=BOOT + 10)
        self.write_beat(BOOT + 60)
        self.alive(True)

        w = cold_start.witnesses(MON, None, now=BOOT + 100)

        self.assertEqual(w["status"], "UNKNOWN")
        self.assertIn("boot time unreadable", w["why"])


class StaleLocksAreDatedNotGuessed(_ColdStartTest):

    def test_a_lock_older_than_the_boot_is_stale(self):
        old = self.write_lock("reply_watch.lock", BOOT - 100)
        new = self.write_lock("digest.lock", BOOT + 100)

        survey = cold_start.lock_survey(BOOT, lock_dir=self.lock_dir)

        self.assertEqual(survey["stale"], [old])
        self.assertEqual(survey["live"], [new])

    def test_without_a_boot_time_nothing_is_stale(self):
        """Clearing a live monitor's lock is worse than leaving a dead one's,
        so an unreadable boot time clears nothing at all."""
        self.write_lock("reply_watch.lock", BOOT - 100)

        survey = cold_start.lock_survey(None, lock_dir=self.lock_dir)

        self.assertEqual(survey["stale"], [])
        self.assertEqual(len(survey["unknown"]), 1)

    def test_clear_stale_locks_removes_only_the_stale_ones(self):
        old = self.write_lock("reply_watch.lock", BOOT - 100)
        new = self.write_lock("digest.lock", BOOT + 100)
        plan = {"locks": cold_start.lock_survey(BOOT, lock_dir=self.lock_dir)}

        removed = cold_start.clear_stale_locks(plan)

        self.assertEqual(removed, [old])
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(new), "a live lock was deleted")

    def test_a_dry_run_deletes_nothing(self):
        old = self.write_lock("reply_watch.lock", BOOT - 100)
        plan = {"locks": cold_start.lock_survey(BOOT, lock_dir=self.lock_dir)}

        removed = cold_start.clear_stale_locks(plan, dry_run=True)

        self.assertEqual(removed, [old])
        self.assertTrue(os.path.exists(old), "--dry-run deleted a lock")


class OneInstanceEach(_ColdStartTest):

    def test_it_refuses_to_start_when_a_supervisor_is_already_up(self):
        plan = {"monitors": [{"name": "a", "witness_process": True},
                             {"name": "b", "witness_process": False}]}
        self.assertTrue(cold_start.supervisor_already_running(plan))

    def test_it_starts_when_nothing_is_running(self):
        plan = {"monitors": [{"name": "a", "witness_process": False},
                             {"name": "b", "witness_process": False}]}
        self.assertFalse(cold_start.supervisor_already_running(plan))

    def test_main_with_start_refuses_rather_than_spawning_twins(self):
        """The refusal must happen BEFORE the supervisor is touched. A second
        supervisor spawns a second copy of every monitor, and two reply
        watchers on one cursor is what `singlewalker` exists to prevent."""
        plan = {
            "booted_at": BOOT, "uptime_seconds": 10, "boot_time_readable": True,
            "locks": {"stale": [], "live": [], "unknown": []},
            "monitors": [dict(cold_start.witnesses(MON, BOOT, now=BOOT + 1),
                              witness_process=True)],
            "up": [], "not_up": ["probe_watch"], "cursors": [],
            "work_dir": self.tmp,
        }
        with mock.patch.object(cold_start, "build_plan", lambda: plan), \
             mock.patch.object(supervisor, "_run") as run:
            rc = cold_start.main(["--start"])

        self.assertEqual(rc, 1)
        run.assert_not_called()


class TheRecoveryTimeIsMeasuredFromTheBoot(_ColdStartTest):

    def test_verify_returns_when_every_monitor_has_two_witnesses(self):
        plans = [
            {"not_up": ["probe_watch"]},
            {"not_up": []},
        ]
        with mock.patch.object(cold_start, "build_plan", lambda: plans.pop(0)), \
             mock.patch.object(time, "sleep", lambda *_: None):
            ok, elapsed, _ = cold_start.verify(
                deadline=60, poll=0, started_at=time.time() - 42,
                out=lambda *_: None)

        self.assertTrue(ok)
        self.assertGreaterEqual(elapsed, 42)

    def test_verify_gives_up_rather_than_waiting_forever(self):
        with mock.patch.object(cold_start, "build_plan",
                               lambda: {"not_up": ["probe_watch"]}), \
             mock.patch.object(time, "sleep", lambda *_: None):
            ok, _elapsed, plan = cold_start.verify(
                deadline=0, poll=0, out=lambda *_: None)

        self.assertFalse(ok)
        self.assertEqual(plan["not_up"], ["probe_watch"])


class ThePlanTouchesNothing(_ColdStartTest):

    def test_a_plain_run_starts_nothing_and_removes_nothing(self):
        old = self.write_lock("reply_watch.lock", BOOT - 100)
        with mock.patch.object(cold_start, "boot_time", lambda: BOOT), \
             mock.patch.object(supervisor, "_run") as run:
            rc = cold_start.main([])

        self.assertEqual(rc, 0)
        run.assert_not_called()
        self.assertTrue(os.path.exists(old),
                        "the default run deleted a lock")


class TheAutostartCommandSurvivesTheMigration(unittest.TestCase):

    def test_it_uses_sys_executable_and_not_the_py_launcher(self):
        """`py -3` is a Windows shim that does not exist on Linux, and this
        registration has to survive the server migration unchanged."""
        from scripts import install_autostart
        import sys

        cmd = install_autostart.command()
        self.assertEqual(cmd[0], sys.executable)
        self.assertNotIn("py", os.path.basename(cmd[0]).split(".")[0:1])
        self.assertEqual(cmd[1:], ["-m", "scripts.cold_start", "--start"])

    def test_it_asks_for_no_elevation(self):
        """/RL HIGHEST would make registration fail for a non-admin rather
        than degrade, and hardening item 7 is already blocked on an elevated
        shell."""
        from scripts import install_autostart

        argv = install_autostart.install_argv()
        self.assertIn("/RL", argv)
        self.assertEqual(argv[argv.index("/RL") + 1], "LIMITED")
        self.assertIn("ONLOGON", argv)

    def test_the_systemd_unit_runs_the_same_command(self):
        """Increment F should write the unit from the command known to work,
        not from a second reading of the docs."""
        from scripts import install_autostart

        unit = install_autostart.systemd_unit()
        self.assertIn("-m scripts.cold_start --start", unit)


if __name__ == "__main__":
    unittest.main()
