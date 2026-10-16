"""A task can see its own deadline, and a leg that cannot finish is not started.

MEASURED 2026-10-15, and twice in one night (qwen TASK 0150, decision D2):

* `glm 0065` and `pilotcaps 0130` were killed at exactly 90:00 while doing real
  work. Neither was hung. Their real processes carried on for 25 and 64 minutes
  afterwards with no watcher left to record a DONE line, so the work existed and
  the record did not.
* `webapp/0040` read the lock by hand, wrote `SUITE: NOT OBTAINED` at ~23:52
  against a holder that released at 23:55:33, and had 38 minutes of its own
  budget left at that moment. Its arithmetic was invented on the spot, because
  nothing published either number.

The watcher knew the kill time all along (`docs/ops/lane_watcher.ps1` computes
`$deadline`) and told the child nothing. It now exports `LANE_DEADLINE`, and
`src/lanedeadline.py` is the only reader.

WHAT THESE TESTS ARE CAREFUL ABOUT:

* the decision is asserted on RETURNED VALUES and on what `run_suite.main`
  actually calls, never on the text of a source file. An earlier test in this
  repository asserted a flag's presence in the source and could not fail,
  because the docstring carried the same string.
* UNKNOWN is tested as its own state in both directions: it must not read as
  permission, and it must not read as a measured refusal either.
* the OPT-IN is tested. Without `--legs` nothing about `run_suite` changes, and
  that control is what makes this a zero-correctness-cost change rather than a
  new gate on every run anybody makes.
"""
import datetime
import importlib.util
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from src import lanedeadline, suitelock


def at(text):
    return datetime.datetime.fromisoformat(text)


#: A fixed clock, so nothing here depends on when it is run.
NOW = "2026-10-16T01:00:00+02:00"


class TheDeadlineIsAnInstantAndNeverADuration(unittest.TestCase):
    """D2's own condition: "must be the deadline, not the duration, or a restart
    makes it lie". A duration is already wrong by the time the child reads it."""

    def test_the_format_the_watcher_writes_is_the_format_the_reader_parses(self):
        """`$deadline.ToString("yyyy-MM-ddTHH:mm:sszzz")`, verbatim. A format the
        watcher can write and the reader cannot parse is a feature that works
        only in the harness that tested it."""
        parsed = lanedeadline.parse("2026-10-16T02:30:00+02:00")
        self.assertIsNotNone(parsed)
        self.assertEqual(2026, parsed.year)
        self.assertIsNotNone(parsed.tzinfo, "an offset-less instant is ambiguous")

    def test_a_duration_is_not_an_instant(self):
        """Exporting `$TaskTimeoutMinutes` instead of `$deadline` is the named
        failure mode, and it must not parse into a number of minutes left."""
        for duration in ("150", "90", "0.5", "150 minutes"):
            self.assertIsNone(lanedeadline.parse(duration), duration)
            verdict = lanedeadline.decide(legs=1, at=at(NOW),
                                          env={"LANE_DEADLINE": duration})
            self.assertEqual("UNKNOWN", verdict["decision"], duration)
            self.assertEqual("unparseable", verdict["source"], duration)

    def test_a_naive_stamp_is_read_as_local_rather_than_refused(self):
        parsed = lanedeadline.parse("2026-10-16T02:30:00")
        self.assertIsNotNone(parsed)
        self.assertIsNotNone(parsed.tzinfo)


class TheArithmeticComesFromMeasurements(unittest.TestCase):
    """Where the numbers come from matters more than the feature, and all three
    figures are traceable: the pair, the widest single leg, and the reserve that
    is honestly declared rather than dressed up as measured."""

    def test_two_legs_cost_exactly_the_measured_worst_pair(self):
        """78-91 minutes was measured twice: `glm 0065`'s two legs at
        2267.7s + 2355.3s = 77.0 min (TASK 0090), and a leg's measured range of
        2,233-3,456 s (TASK 0150). Nothing is rounded optimistically."""
        self.assertEqual((78.0, 91.0), lanedeadline.PAIR_MINUTES_MEASURED)
        self.assertAlmostEqual(91.0, lanedeadline.leg_cost_minutes(2), places=6)

    def test_one_leg_is_never_quoted_below_the_widest_leg_on_record(self):
        """3,456.1 s = 57.6 min, the complete run `pilotcaps/0170` left behind.
        It is LONGER than the pair-derived average leg, so a one-leg estimate of
        45.5 would have understated a real run by twelve minutes."""
        self.assertAlmostEqual(57.6, lanedeadline.leg_cost_minutes(1), places=6)
        self.assertGreaterEqual(lanedeadline.leg_cost_minutes(1),
                                lanedeadline.WIDEST_LEG_MINUTES)

    def test_the_cost_never_decreases_as_legs_increase(self):
        costs = [lanedeadline.leg_cost_minutes(n) for n in (1, 2, 3, 4)]
        self.assertEqual(costs, sorted(costs))

    def test_zero_legs_cost_nothing(self):
        self.assertEqual(0.0, lanedeadline.leg_cost_minutes(0))

    def test_the_reserve_is_a_named_line_in_every_verdict(self):
        """It is DECLARED, not measured - the write-up has never been timed
        separately on this machine - so every verdict shows it and says so,
        instead of hiding a chosen number inside a conclusion."""
        text = lanedeadline.describe(
            lanedeadline.decide(legs=1, at=at(NOW),
                                env={"LANE_DEADLINE": "2026-10-16T03:00:00+02:00"}))
        self.assertIn("reserve (declared)", text)
        self.assertIn("not measured", text)


class ALegThatFitsRunsAndOneThatDoesNotIsRefused(unittest.TestCase):

    def verdict(self, deadline, legs=1, **kwargs):
        return lanedeadline.decide(legs=legs, at=at(NOW),
                                   env={"LANE_DEADLINE": deadline}, **kwargs)

    def test_room_for_one_leg_is_RUN(self):
        v = self.verdict("2026-10-16T03:00:00+02:00")          # 120 min left
        self.assertEqual("RUN", v["decision"])
        self.assertTrue(v["may_start"])
        self.assertAlmostEqual(120.0, v["minutes_left"], places=6)

    def test_no_room_for_one_leg_is_REFUSE(self):
        v = self.verdict("2026-10-16T01:35:00+02:00")          # 35 min left
        self.assertEqual("REFUSE", v["decision"])
        self.assertFalse(v["may_start"])
        self.assertAlmostEqual(35.0, v["minutes_left"], places=6)
        self.assertAlmostEqual(67.6, v["minutes_needed"], places=6)

    def test_room_for_one_leg_but_not_for_a_pair(self):
        """The exact case that decides a merge gate: 90 minutes is enough for a
        single reference and not for the pair a gate needs."""
        self.assertEqual("RUN", self.verdict("2026-10-16T02:30:00+02:00", 1)["decision"])
        self.assertEqual("REFUSE", self.verdict("2026-10-16T02:30:00+02:00", 2)["decision"])

    def test_the_boundary_is_inclusive_and_stated(self):
        """Exactly enough is enough. 57.6 + 10.0 = 67.6 minutes."""
        v = self.verdict("2026-10-16T02:07:36+02:00")          # 67.6 min
        self.assertAlmostEqual(67.6, v["minutes_left"], places=4)
        self.assertEqual("RUN", v["decision"])

    def test_a_passed_deadline_is_a_refusal_and_not_a_crash(self):
        v = self.verdict("2026-10-16T00:30:00+02:00")
        self.assertEqual("REFUSE", v["decision"])
        self.assertLess(v["minutes_left"], 0)

    def test_the_reserve_is_what_makes_a_tight_fit_a_refusal(self):
        """The control for the reserve: the same remainder, RUN with no reserve
        and REFUSE with the declared one. Without this the reserve could be
        ignored entirely and every test above would still pass."""
        tight = "2026-10-16T02:00:00+02:00"                    # 60 min left
        self.assertEqual("RUN", self.verdict(tight, 1, reserve_minutes=0)["decision"])
        self.assertEqual("REFUSE", self.verdict(tight, 1)["decision"])

    def test_the_arithmetic_is_named_in_the_verdict(self):
        """"The refusal must name the arithmetic: minutes left, minutes the leg
        costs, decision." Asserted on the rendered block a lane pastes."""
        text = lanedeadline.describe(self.verdict("2026-10-16T01:35:00+02:00"))
        self.assertIn("minutes left", text)
        self.assertIn("35.0", text)
        self.assertIn("minutes needed", text)
        self.assertIn("67.6", text)
        self.assertIn("REFUSE", text)


class UnknownIsNotPermissionAndNotAMeasurement(unittest.TestCase):
    """Invariant 0 applied to one number. An unreadable authority is UNKNOWN,
    and UNKNOWN never becomes a pass."""

    def test_an_unset_deadline_is_UNKNOWN(self):
        v = lanedeadline.decide(legs=1, at=at(NOW), env={})
        self.assertEqual("UNKNOWN", v["decision"])
        self.assertEqual("unset", v["source"])

    def test_unknown_never_grants_permission(self):
        for env in ({}, {"LANE_DEADLINE": ""}, {"LANE_DEADLINE": "   "},
                    {"LANE_DEADLINE": "soon"}, {"LANE_DEADLINE": "150"}):
            v = lanedeadline.decide(legs=1, at=at(NOW), env=env)
            self.assertFalse(v["may_start"], env)
            self.assertEqual("UNKNOWN", v["decision"], env)

    def test_unknown_does_not_invent_a_remainder(self):
        v = lanedeadline.decide(legs=1, at=at(NOW), env={})
        self.assertIsNone(v["minutes_left"])
        self.assertIn("UNKNOWN", lanedeadline.describe(v))

    def test_unknown_still_names_what_the_leg_would_have_cost(self):
        """A refusal that cannot say what it was comparing is another
        unexplained NOT OBTAINED line, which is the thing being replaced."""
        v = lanedeadline.decide(legs=2, at=at(NOW), env={})
        self.assertAlmostEqual(101.0, v["minutes_needed"], places=6)
        self.assertIn("LANE_DEADLINE", v["why"])

    def test_remaining_minutes_is_none_rather_than_zero(self):
        """Zero would read as "no time left", which is a measurement. None is
        "I do not know", which is the truth."""
        self.assertIsNone(lanedeadline.remaining_minutes(env={}))


class TheSuiteRunnerRefusesALegThatCannotFinish(unittest.TestCase):
    """`scripts/run_suite.py --legs N`. Asserted on what `main()` CALLS."""

    def runner(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location(
            "run_suite_under_deadline_test",
            os.path.join(here, "scripts", "run_suite.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def run_main(self, argv, deadline="__absent__", on_acquire=None):
        """`main()` with the suite and the lock replaced by recorders.

        Returns (exit code, what was called, printed text). Nothing runs a test
        and nothing touches a lock file.
        """
        runner = self.runner()
        seen = {"acquired": 0, "released": 0, "ran": 0}

        def fake_acquire(branch=None, timeout=None, **kwargs):
            seen["acquired"] += 1
            if on_acquire:
                on_acquire()
            return {"pid": os.getpid()}

        def fake_release(*a, **k):
            seen["released"] += 1
            return True

        def fake_run(*a, **k):
            seen["ran"] += 1
            return 0

        env = dict(os.environ)
        env.pop(lanedeadline.ENV_VAR, None)
        if deadline != "__absent__":
            env[lanedeadline.ENV_VAR] = deadline

        buffer = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(suitelock, "acquire", fake_acquire), \
                mock.patch.object(suitelock, "release", fake_release), \
                mock.patch.object(runner, "run_suite", fake_run), \
                mock.patch.object(sys, "argv", ["run_suite.py"] + argv), \
                redirect_stdout(buffer):
            code = runner.main()
        return code, seen, buffer.getvalue()

    def test_without_the_flag_nothing_changes_at_all(self):
        """THE CONTROL FOR THE WHOLE FEATURE. `LANE_DEADLINE` is absent from
        every shell that is not a lane child, so a default-on check would have
        refused the operator's own runs. Omitting `--legs` must leave this
        script behaving exactly as it did before the flag existed."""
        code, seen, out = self.run_main(["--offline"])
        self.assertEqual(0, code)
        self.assertEqual(1, seen["ran"])
        self.assertEqual(1, seen["acquired"])
        self.assertNotIn("LANE_DEADLINE", out)

    def test_a_leg_that_fits_runs(self):
        far = (lanedeadline.now() + datetime.timedelta(hours=4)).isoformat()
        code, seen, out = self.run_main(["--offline", "--legs", "1"], far)
        self.assertEqual(0, code)
        self.assertEqual(1, seen["ran"])
        self.assertIn("RUN", out)

    def test_a_leg_that_cannot_finish_is_refused_before_the_lock(self):
        """BEFORE the lock, and the order is the point: a leg that cannot finish
        must not first spend hours in the queue to find out."""
        near = (lanedeadline.now() + datetime.timedelta(minutes=20)).isoformat()
        code, seen, out = self.run_main(["--offline", "--legs", "1"], near)
        self.assertEqual(3, code)
        self.assertEqual(0, seen["ran"], "no suite may run")
        self.assertEqual(0, seen["acquired"], "the lock must not even be taken")
        self.assertIn("REFUSE", out)
        self.assertIn("minutes needed", out)

    def test_the_refusal_exit_code_is_not_a_pass_and_not_a_failure_count(self):
        """0 would say the suite passed, 1 is a real failure count and 124 is the
        watchdog kill. A refusal is none of those."""
        runner = self.runner()
        self.assertEqual(3, runner.LANE_DEADLINE_REFUSED)
        self.assertNotIn(runner.LANE_DEADLINE_REFUSED, (0, 1, 124))

    def test_an_unknown_deadline_with_the_flag_refuses(self):
        """FAIL-CLOSED. Asking the question and not being able to answer it is
        not permission - and the message names the variable that would settle
        it, so the reader is not left guessing why."""
        code, seen, out = self.run_main(["--offline", "--legs", "1"])
        self.assertEqual(3, code)
        self.assertEqual(0, seen["ran"])
        self.assertIn("UNKNOWN", out)
        self.assertIn("LANE_DEADLINE", out)

    def test_a_pair_is_refused_where_one_leg_would_have_run(self):
        """The 90-minute watcher cap, as a decision instead of a kill: enough
        for one leg, never for the pair a merge gate needs."""
        ninety = (lanedeadline.now() + datetime.timedelta(minutes=89)).isoformat()
        one, seen_one, _ = self.run_main(["--offline", "--legs", "1"], ninety)
        two, seen_two, out = self.run_main(["--offline", "--legs", "2"], ninety)
        self.assertEqual(0, one)
        self.assertEqual(1, seen_one["ran"])
        self.assertEqual(3, two)
        self.assertEqual(0, seen_two["ran"])
        self.assertIn("101.0", out)

    def test_the_remainder_is_rechecked_after_the_queue_wait(self):
        """The wait spends the same minutes the leg needs. A lane that waited 40
        minutes for the lock and then started a 58-minute leg into a 20-minute
        remainder is the opposite of `webapp/0040`'s error and just as wrong.

        The wait is simulated by moving the deadline nearer while `acquire` is
        running, which is what the passage of time does to it.
        """
        far = (lanedeadline.now() + datetime.timedelta(hours=4)).isoformat()
        near = (lanedeadline.now() + datetime.timedelta(minutes=15)).isoformat()

        def spend_the_remainder():
            os.environ[lanedeadline.ENV_VAR] = near

        code, seen, out = self.run_main(["--offline", "--legs", "1"], far,
                                        on_acquire=spend_the_remainder)
        self.assertEqual(3, code)
        self.assertEqual(1, seen["acquired"], "it did wait for the lock")
        self.assertEqual(0, seen["ran"], "and then refused to start the leg")
        self.assertEqual(1, seen["released"], "and let go of the lock")
        self.assertIn("after the wait", out)

    def test_the_reserve_flag_reads_the_modules_figure(self):
        """One authority for the default. `--lock-wait` once carried its own copy
        of a timeout the module also defined, and the two drifted."""
        runner = self.runner()
        args = runner.build_parser().parse_args(["--legs", "1"])
        self.assertIsNone(args.reserve_minutes,
                          "the flag must not carry a copy of the figure")
        tight = (lanedeadline.now() + datetime.timedelta(minutes=60)).isoformat()
        refused, _, _ = self.run_main(["--offline", "--legs", "1"], tight)
        allowed, seen, _ = self.run_main(
            ["--offline", "--legs", "1", "--reserve-minutes", "0"], tight)
        self.assertEqual(3, refused)
        self.assertEqual(0, allowed)
        self.assertEqual(1, seen["ran"])

    def test_no_verdict_file_is_written_by_a_refusal(self):
        """A run that did not happen has no verdict to give. The last real
        verdict on disk must still be there afterwards, because a lane reading
        `suite_verdict.txt` after a refusal would otherwise read a stale one as
        this run's result."""
        runner = self.runner()
        before = None
        if os.path.exists(runner.VERDICT_FILE):
            with open(runner.VERDICT_FILE, encoding="utf-8",
                      errors="replace") as handle:
                before = handle.read()
        near = (lanedeadline.now() + datetime.timedelta(minutes=5)).isoformat()
        self.assertEqual(3, self.run_main(["--offline", "--legs", "1"], near)[0])
        after = None
        if os.path.exists(runner.VERDICT_FILE):
            with open(runner.VERDICT_FILE, encoding="utf-8",
                      errors="replace") as handle:
                after = handle.read()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
