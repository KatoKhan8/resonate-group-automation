"""Witness 1 was unsatisfiable on this deployment, and nothing said so.

`supervisor.witnesses` wants two:

    process    a live pid from a state file written AFTER the boot
    heartbeat  a beat written after the boot and no older than its interval

Only `supervise.py` ever wrote the state file, and this estate is started by
`scripts/start_monitors.py`. So `work/supervisor/` did not exist, NO monitor
could hold witness 1, and `cold_start --verify` answered

    0 of 20 monitors have two witnesses.
    gave up after 3m; still not up: <all 20>

while `start_monitors --status` reported `20 UP, 0 not UP` on `beat+process`
and the table `--verify` prints directly underneath showed every monitor
beating within a minute. Four handoffs read that as a broken drill. It was a
broken instrument, and the drill was correctly refused each time.

Adopting infra `46474c6c` fixed the NAME half - the monitor-name to
heartbeat-file map - and left this half exactly as it was, which is why the
first verify after that merge still answered 0 of 20.

These tests are about the CALL SITE. `record_started` on its own is easy to
keep green; what failed for four days is that nobody called it.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import supervisor                                     # noqa: E402


def _load():
    import importlib.util
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "start_monitors.py")
    spec = importlib.util.spec_from_file_location("_sm_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RecordStartedWritesTheFileWitnessOneReads(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_it_writes_the_pid_under_the_monitor_name(self):
        supervisor.record_started("bison_watch_493", 4242, state_dir=self.dir)
        path = os.path.join(self.dir, "bison_watch_493.json")
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
        self.assertEqual(state["pid"], 4242)
        self.assertEqual(state["name"], "bison_watch_493")
        self.assertIn("started_at", state)

    def test_the_name_is_the_monitor_name_not_the_script_name(self):
        """Nine watchers share one script and differ only by --campaign."""
        for name in ("bison_watch_491", "bison_watch_493"):
            supervisor.record_started(name, 1, state_dir=self.dir)
        self.assertEqual(
            sorted(os.listdir(self.dir)),
            ["bison_watch_491.json", "bison_watch_493.json"])

    def test_a_read_after_a_write_round_trips(self):
        supervisor.record_started("digest", 777, state_dir=self.dir)
        self.assertEqual(
            supervisor._read_state("digest", state_dir=self.dir)["pid"], 777)


class SpawnMustRecordOrWitnessOneIsUnSatisfiable(unittest.TestCase):
    """The call site. This is the assertion that was missing for four days."""

    def test_spawn_takes_a_name_and_records_it(self):
        sm = _load()
        recorded = []
        real = supervisor.record_started
        supervisor.record_started = lambda n, p, **k: recorded.append((n, p))
        self.addCleanup(setattr, supervisor, "record_started", real)

        class _Proc:
            pid = 31337

        real_popen = sm.subprocess.Popen
        sm.subprocess.Popen = lambda *a, **k: _Proc()
        self.addCleanup(setattr, sm.subprocess, "Popen", real_popen)

        sm.spawn(["scripts/bison_watch_loop.py", "--campaign", "493"],
                 "bison_watch_493")
        self.assertEqual(recorded, [("bison_watch_493", 31337)],
                         "a monitor started and not recorded holds one "
                         "witness at most and reads DOWN for ever")

    def test_both_call_sites_pass_the_name(self):
        """`start` and `restart` each spawn; neither may drop the name."""
        import ast
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts", "start_monitors.py")
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "spawn"]
        self.assertEqual(len(calls), 2, "start() and restart()")
        for call in calls:
            self.assertEqual(
                len(call.args), 2,
                "spawn(argv) without a name records nothing and the monitor "
                "reads DOWN however healthy it is")
            self.assertEqual(call.args[1].id, "name")

    def test_a_failed_state_write_does_not_stop_the_monitor(self):
        """A monitoring tool must not cause the outage it reports."""
        sm = _load()
        real = supervisor.record_started

        def _boom(*a, **k):
            raise OSError("disk full")

        supervisor.record_started = _boom
        self.addCleanup(setattr, supervisor, "record_started", real)

        class _Proc:
            pid = 99

        real_popen = sm.subprocess.Popen
        sm.subprocess.Popen = lambda *a, **k: _Proc()
        self.addCleanup(setattr, sm.subprocess, "Popen", real_popen)
        self.assertEqual(sm.spawn(["scripts/digest_loop.py"], "digest").pid, 99)


class TheTwoWitnessVerdictNeedsBoth(unittest.TestCase):

    def test_a_beating_monitor_nobody_recorded_is_not_UP(self):
        """The exact state of this estate before today: all beats, no state."""
        mon = {"name": "digest", "module": "scripts.digest_loop",
               "interval": 300, "heartbeat": {"source": "digest"}}
        empty = tempfile.mkdtemp()
        verdict = supervisor.witnesses(mon, booted_at=0, state_dir=empty)
        self.assertNotEqual(verdict.get("status"), "UP")


if __name__ == "__main__":
    unittest.main()
