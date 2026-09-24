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
       "args": [], "interval": 300,
       "heartbeat": {"file": "probe.json"}}

#: A monitor that writes no heartbeat at all, like the real
#: `bison_mailbox_utilisation`. It can never have a second witness.
MON_NO_BEAT = {"name": "probe_silent", "module": "scripts.probe_silent",
               "args": [], "interval": 300, "heartbeat": None}

BOOT = 1_000_000.0


#: Injected registry for the derived half of the table, so these tests assert
#: the heartbeat CONTRACT and not which campaigns happen to be live today.
TABLE_ROWS = [
    {"campaign_id": "c491", "status": "running", "bison_campaign_id": 491},
    {"campaign_id": "hr", "status": "running", "heyreach_campaign_id": 605732},
]


def _table():
    """The real table over an injected registry.

    Built from `STATIC_MONITORS` + `campaign_monitors` rather than by calling
    `supervisor.monitors()`, because tests below PATCH `supervisor.monitors`
    with this function - calling it here would recurse into the patch."""
    return list(supervisor.STATIC_MONITORS) + supervisor.campaign_monitors(
        rows=TABLE_ROWS, sequence_source=lambda p, c: 0)


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
            mock.patch("src.watchsink.heartbeat_dir", lambda: self.tmp),
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

    def write_beat(self, epoch, filename="probe.json"):
        path = os.path.join(self.tmp, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"epoch": epoch, "state": "ok"}, f)
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

        w = supervisor.witnesses(MON, BOOT, now=BOOT + 100)

        self.assertEqual(w["status"], "UP")
        self.assertTrue(w["witness_process"])
        self.assertTrue(w["witness_heartbeat"])

    def test_a_live_pid_from_a_pre_boot_state_file_is_not_a_witness(self):
        """The forged UP. The pid is alive; it is not this monitor's pid."""
        self.write_state(pid=999, written_at=BOOT - 500)
        self.write_beat(BOOT + 60)
        self.alive(True)

        w = supervisor.witnesses(MON, BOOT, now=BOOT + 100)

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
        w = supervisor.witnesses(MON, BOOT, now=BOOT + 720)

        self.assertEqual(w["status"], "DOWN")
        self.assertTrue(w["witness_process"])
        self.assertFalse(w["witness_heartbeat"])

    def test_a_beat_from_before_the_boot_is_not_a_witness(self):
        """A heartbeat from the machine's previous life proves nothing."""
        self.write_state(pid=999, written_at=BOOT + 10)
        self.write_beat(BOOT - 30)
        self.alive(True)

        w = supervisor.witnesses(MON, BOOT, now=BOOT + 60)

        self.assertFalse(w["witness_heartbeat"],
                         "a pre-boot beat was accepted as a witness")
        # STARTING rather than DOWN: the process is up, it was started less
        # than one interval ago, and it has legitimately not beaten yet. The
        # assertion that matters is the one above - the OLD beat did not
        # count. A monitor still silent after two intervals is DOWN, and
        # `test_a_live_process_with_no_fresh_beat_is_not_up` covers that.
        self.assertEqual(w["status"], "STARTING")

    def test_a_fresh_beat_with_a_dead_process_is_not_up(self):
        self.write_state(pid=999, written_at=BOOT + 10)
        self.write_beat(BOOT + 60)
        self.alive(False)

        w = supervisor.witnesses(MON, BOOT, now=BOOT + 100)

        self.assertEqual(w["status"], "DOWN")
        self.assertIn("started and died", w["why"])

    def test_an_unreadable_boot_time_confirms_nothing(self):
        """Fail closed. Without a boot time neither witness can be dated."""
        self.write_state(pid=999, written_at=BOOT + 10)
        self.write_beat(BOOT + 60)
        self.alive(True)

        w = supervisor.witnesses(MON, None, now=BOOT + 100)

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
            "monitors": [dict(supervisor.witnesses(MON, BOOT, now=BOOT + 1),
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
             mock.patch.object(supervisor, "monitors", _table), \
             mock.patch.object(supervisor, "_run") as run:
            rc = cold_start.main([])

        self.assertEqual(rc, 0)
        run.assert_not_called()
        self.assertTrue(os.path.exists(old),
                        "the default run deleted a lock")

    def test_an_unreadable_registry_refuses_instead_of_reporting_an_estate(self):
        """The derived half of the table comes from the campaign registry,
        and `campaigns.load()` answers an ABSENT file with an empty snapshot
        rather than an error.

        Read straight, that turns "I cannot see the registry" into "there are
        no campaigns": cold start would come up, find the five static loops,
        find them healthy, and report the estate recovered while every
        campaign watcher was missing. Measured 2026-09-23 - this is why
        `campaign_monitors` checks the file exists before trusting the load.
        """
        old = self.write_lock("reply_watch.lock", BOOT - 100)

        def refuse():
            raise supervisor.RegistryUnreadable("no registry in this test")

        with mock.patch.object(cold_start, "boot_time", lambda: BOOT), \
             mock.patch.object(supervisor, "monitors", refuse), \
             mock.patch.object(supervisor, "_run") as run:
            rc = cold_start.main([])

        self.assertEqual(rc, 2, "an unreadable registry must not exit 0")
        run.assert_not_called()
        self.assertTrue(os.path.exists(old),
                        "the refusal deleted a lock")


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


class TheSupervisorHoldsThePowerRequest(unittest.TestCase):
    """`docs/MACHINE-HARDENING-2026-09-23.md` 6 specified this one line and
    could not write it, because `src/supervisor.py` lives on `infra`.

    Without it `powercfg /requests` names nothing, and the adoption checklist
    asks for it to name python.exe - a step that would simply fail, with the
    keep-awake module sitting on master with no caller and every test in
    `test_keepawake.py` green. Existence is not function.
    """

    def test_run_acquires_the_request_around_the_loop(self):
        """Order matters: acquired BEFORE the monitors start, released AFTER
        they stop. A request taken after the loop returns holds nothing."""
        from src import keepawake, supervisor

        order = []

        with mock.patch.object(keepawake, "acquire",
                               lambda **k: order.append("acquire") or True),              mock.patch.object(keepawake, "release",
                               lambda **k: order.append("release")),              mock.patch.object(keepawake, "status",
                               lambda: {"error": None}),              mock.patch.object(supervisor, "_supervise",
                               lambda *a, **k: order.append("loop")
                               or "loop ran"):
            result = supervisor._run(table=[])

        self.assertEqual(result, "loop ran")
        self.assertEqual(order, ["acquire", "loop", "release"])

    def test_the_request_is_released_even_when_the_loop_raises(self):
        """The supervisor crashing must not leave the machine pinned awake."""
        from src import keepawake, supervisor

        released = []

        def boom(*a, **k):
            raise RuntimeError("loop blew up")

        with mock.patch.object(keepawake, "acquire", lambda **k: True),              mock.patch.object(keepawake, "release",
                               lambda **k: released.append(1)),              mock.patch.object(keepawake, "status",
                               lambda: {"error": None}),              mock.patch.object(supervisor, "_supervise", boom):
            with self.assertRaises(RuntimeError):
                supervisor._run(table=[])

        self.assertEqual(released, [1],
                         "a crash left the power request held")

    def test_a_refused_request_does_not_stop_the_supervisor(self):
        """A supervisor that cannot take a power request must still
        supervise - loudly, not not-at-all."""
        from src import keepawake, supervisor

        with mock.patch.object(keepawake, "acquire",
                               lambda **k: False),              mock.patch.object(supervisor, "_supervise",
                               lambda *a, **k: "loop ran anyway"):
            result = supervisor._run(table=[])

        self.assertEqual(result, "loop ran anyway")


class EveryMonitorSaysWhereItsBeatLands(unittest.TestCase):
    """The declaration that stops witness 2 being a guess.

    Measured 2026-09-23: NOT ONE of the eight monitors writes its heartbeat
    under its own monitor name. reply_watch beats as "replies",
    heyreach_watch as "heyreach" campaign 605732, and three loops bypass
    `watchsink` and write `work/heartbeat/<name>.json` themselves. A liveness
    check that guessed `heartbeat_path(mon["name"])` found nothing for all
    eight and would have reported the whole estate down forever - which is
    exactly what the first version of cold_start did.
    """

    def test_every_monitor_declares_where_its_beat_lands(self):
        missing = [m["name"] for m in _table()
                   if "heartbeat" not in m]
        self.assertEqual(
            missing, [],
            "monitor(s) with no `heartbeat` declaration: %r. None is allowed "
            "and must be written down - it means 'this monitor cannot have a "
            "second witness', which is a finding, not a default." % (missing,))

    def test_a_declared_beat_resolves_to_a_path(self):
        for mon in _table():
            path = supervisor.heartbeat_file(mon)
            if mon["heartbeat"] is None:
                self.assertIsNone(path, mon["name"])
            else:
                self.assertTrue(path and path.endswith(".json"), mon["name"])

    def test_a_monitor_with_no_heartbeat_cannot_reach_up(self):
        """`bison_mailbox_utilisation` is real and it is one of these."""
        w = supervisor.witnesses(MON_NO_BEAT, BOOT, now=BOOT + 10)
        self.assertNotEqual(w["status"], "UP")
        self.assertFalse(w["heartbeat_available"])
        self.assertIn("writes no heartbeat", w["why"])

    def test_one_witness_is_reported_as_one_witness_not_as_up(self):
        import shutil as _sh
        tmp = tempfile.mkdtemp(prefix="rga-onewitness-")
        self.addCleanup(_sh.rmtree, tmp, ignore_errors=True)
        with mock.patch.object(supervisor, "_state_dir", lambda: tmp),              mock.patch("src.singlewalker._alive", lambda pid: True):
            path = os.path.join(tmp, "%s.json" % MON_NO_BEAT["name"])
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"pid": 999}, f)
            os.utime(path, (BOOT + 10, BOOT + 10))
            w = supervisor.witnesses(MON_NO_BEAT, BOOT, now=BOOT + 20)
        self.assertEqual(w["status"], "UP_ONE_WITNESS")

    def test_the_real_table_resolves_to_the_files_the_loops_write(self):
        """Pinned from the loops as they are on 2026-09-23. If a loop changes
        where it beats, this fails rather than the estate silently reporting
        every monitor down."""
        expected = {
            "reply_watch": "replies.json",
            "notify_deliver": "notify-deliver.json",
            "digest": "digest.json",
            "slack_agent": "slack-agent.json",
            "slack_followup": "slack-followup.json",
            # `WATCHER = "weekly-report"` in the loop, so the beat does NOT
            # land under the monitor name. Pinned here for the same reason
            # every other row is: a mismatch makes `--verify` poll a file
            # nothing writes and call the monitor down for ever.
            "weekly_report": "weekly-report.json",
            # DERIVED, from TABLE_ROWS above - the campaign watchers are no
            # longer hand-listed, but where their beat lands is still pinned.
            "bison_watch_491": "bison-491.json",
            "heyreach_watch_605732": "heyreach-605732.json",
        }
        for mon in _table():
            path = supervisor.heartbeat_file(mon)
            want = expected[mon["name"]]
            got = os.path.basename(path) if path else None
            self.assertEqual(got, want, mon["name"])


if __name__ == "__main__":
    unittest.main()
