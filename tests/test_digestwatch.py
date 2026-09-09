"""The digest on a schedule, and the four ways that goes wrong.

`digest.build` and `digest.announce` both worked from the day they were
written - as a command somebody types. The whole argument for routing an
ordinary reply to `NOWHERE` is that a digest catches it, and a digest nobody
schedules catches nothing.

What is asserted here is mostly the scheduling, because the summary already
has its own tests:

**One period, one digest.** Proved on the notification log rather than on a
counter: the period's end is part of the notification id, so a second tick
inside the same period finds the row that already exists. If the window were
anchored to `now()` instead, every tick would be a new period and the
idempotency would be real but useless - so that is asserted too.

**A missed day is reported, not dropped.** The window starts where the last
digest for that workspace ended. Beyond `MAX_CATCH_UP_DAYS` it falls back to
one period and says which, rather than implying a fortnight fitted into it.

**A misconfigured schedule is refused, not defaulted.** An hour that cannot
be read would otherwise become 08:00 and look like a working schedule.

**One thread, two independent jobs.** The digest rides the reply watcher's
loop. Reply polling being off must not silence the digest, a failing digest
must not stop polling, and neither may kill the thread.
"""
import datetime
import unittest

from tests.webbase import WebTest

from src import digest, digestwatch as dw, notify, replywatch, store


class TheSettings(unittest.TestCase):

    def read(self, **env):
        return dw.settings(env)

    def test_it_is_off_unless_asked_for(self):
        self.assertFalse(self.read()["enabled"])
        self.assertEqual(self.read()["schedule"], dw.OFF)

    def test_daily_and_weekdays_are_the_two_shapes(self):
        self.assertEqual(self.read(DIGEST_SCHEDULE="daily")["schedule"],
                         dw.DAILY)
        self.assertEqual(self.read(DIGEST_SCHEDULE="WeekDays")["schedule"],
                         dw.WEEKDAYS)

    def test_a_schedule_nobody_implemented_is_refused(self):
        with self.assertRaises(dw.NotConfigured):
            self.read(DIGEST_SCHEDULE="hourly")

    def test_an_unreadable_hour_is_refused_rather_than_defaulted(self):
        """It would otherwise become 08:00 and look like a working
        schedule, which is the failure this build keeps finding."""
        for bad in ("eight", "8pm", "24", "-1", "8.5"):
            with self.subTest(hour=bad):
                with self.assertRaises(dw.NotConfigured):
                    self.read(DIGEST_SCHEDULE="daily", DIGEST_HOUR=bad)

    def test_the_default_hour_is_stated(self):
        self.assertEqual(self.read(DIGEST_SCHEDULE="daily")["hour"],
                         dw.DEFAULT_HOUR)

    def test_the_label_says_the_zone(self):
        """There is no per-workspace timezone in this build, so the one
        used has to be named rather than left to be discovered."""
        self.assertIn("UTC", self.read(DIGEST_SCHEDULE="daily")["label"])


class TheSchedule(unittest.TestCase):
    """2026-09-07 is a Monday. 09-05 and 09-06 are the weekend."""

    def at(self, now, schedule=dw.DAILY, hour=8):
        found = dw.boundary(now, schedule, hour)
        return found.isoformat() if found else None

    def test_before_the_hour_the_period_is_yesterdays(self):
        self.assertEqual(self.at("2026-09-07T07:59:00+00:00"),
                         "2026-09-06T08:00:00+00:00")

    def test_on_the_hour_the_period_is_todays(self):
        self.assertEqual(self.at("2026-09-07T08:00:00+00:00"),
                         "2026-09-07T08:00:00+00:00")

    def test_every_moment_in_one_day_resolves_to_the_same_period(self):
        """The property the idempotency rests on."""
        found = {self.at(f"2026-09-07T{h:02d}:30:00+00:00")
                 for h in range(8, 24)}
        self.assertEqual(found, {"2026-09-07T08:00:00+00:00"})

    def test_a_weekend_resolves_back_to_friday(self):
        for moment in ("2026-09-05T12:00:00+00:00",
                       "2026-09-06T12:00:00+00:00",
                       "2026-09-07T07:00:00+00:00"):
            with self.subTest(now=moment):
                self.assertEqual(self.at(moment, dw.WEEKDAYS),
                                 "2026-09-04T08:00:00+00:00")

    def test_mondays_previous_period_is_friday_not_sunday(self):
        """So Monday's digest covers the weekend rather than nothing."""
        monday = dw.boundary("2026-09-07T09:00:00+00:00", dw.WEEKDAYS, 8)
        self.assertEqual(dw.previous(monday, dw.WEEKDAYS).isoformat(),
                         "2026-09-04T08:00:00+00:00")

    def test_daily_steps_back_one_day(self):
        monday = dw.boundary("2026-09-07T09:00:00+00:00", dw.DAILY, 8)
        self.assertEqual(dw.previous(monday, dw.DAILY).isoformat(),
                         "2026-09-06T08:00:00+00:00")

    def test_a_naive_clock_resolves_to_nothing(self):
        """Assuming UTC would move the whole period by hours."""
        self.assertIsNone(dw.boundary("2026-09-07T09:00:00", dw.DAILY, 8))

    def test_off_schedules_nothing(self):
        self.assertIsNone(dw.boundary("2026-09-07T09:00:00+00:00", dw.OFF, 8))

    def test_another_zone_is_converted_rather_than_read_as_utc(self):
        """09:30+02:00 is 07:30 UTC, which is before an 08:00 boundary."""
        self.assertEqual(self.at("2026-09-07T09:30:00+02:00"),
                         "2026-09-06T08:00:00+00:00")


class TheDelivery(WebTest):

    MONDAY = "2026-09-07T09:00:00+00:00"

    def env(self, schedule="daily", hour="8"):
        return {"DIGEST_SCHEDULE": schedule, "DIGEST_HOUR": hour}

    def tick(self, now=None, **env):
        return dw.tick(now=now or self.MONDAY, env=self.env(**env))

    def digests(self):
        return notify.history(None, notify.OPERATIONS_DIGEST, limit=1000)

    def tearDown(self):
        rows = [r for r in notify.load()
                if r.get("type") != notify.OPERATIONS_DIGEST]
        notify.save(rows)
        super().tearDown()

    def test_nothing_runs_when_the_schedule_is_off(self):
        """And it says that, rather than "the clock could not be read" -
        two different answers to an operator asking why nothing came."""
        result = dw.tick(now=self.MONDAY, env={})
        self.assertFalse(result["ran"])
        self.assertEqual(result["why"], dw.SCHEDULE_LABEL[dw.OFF])
        self.assertEqual(self.digests(), [])

    def test_an_unreadable_clock_says_something_different(self):
        result = dw.tick(now="2026-09-07T09:00:00", env=self.env())
        self.assertFalse(result["ran"])
        self.assertIn("clock", result["why"])

    def test_every_workspace_gets_one(self):
        from src import workspaces as ws

        result = self.tick()
        self.assertTrue(result["ran"])
        delivered = {row["workspace"] for row in result["workspaces"]}
        self.assertEqual(delivered,
                         {w["slug"] for w in ws.workspaces()})
        self.assertTrue(all(row["outcome"] == dw.BUILT
                            for row in result["workspaces"]))

    def test_a_second_tick_in_the_same_period_delivers_nothing_new(self):
        first = self.tick()
        before = len(self.digests())
        second = self.tick(now="2026-09-07T23:59:00+00:00")
        self.assertEqual(len(self.digests()), before)
        self.assertTrue(all(row["outcome"] == dw.SKIPPED
                            for row in second["workspaces"]))
        self.assertEqual({r["notification"] for r in first["workspaces"]},
                         {r["notification"] for r in second["workspaces"]})

    def test_the_next_period_does_deliver(self):
        self.tick()
        before = len(self.digests())
        result = self.tick(now="2026-09-08T09:00:00+00:00")
        self.assertGreater(len(self.digests()), before)
        self.assertTrue(all(row["outcome"] == dw.BUILT
                            for row in result["workspaces"]))

    def test_the_window_is_anchored_to_the_period_not_to_the_clock(self):
        """If it were anchored to `now`, every tick would be a new id and
        the idempotency above would be real but useless."""
        result = self.tick(now="2026-09-07T17:23:41+00:00")
        window = result["workspaces"][0]["window"]
        self.assertEqual(window["until"], "2026-09-07T08:00:00+00:00")

    def test_the_first_digest_covers_one_period(self):
        result = self.tick()
        row = result["workspaces"][0]
        self.assertEqual(row["window"]["since"], "2026-09-06T08:00:00+00:00")
        self.assertIn("first digest", row["basis"])

    def test_a_missed_day_is_reported_rather_than_dropped(self):
        """The process was down on the 7th. The 8th covers both days."""
        self.tick(now="2026-09-06T09:00:00+00:00")
        result = self.tick(now="2026-09-08T09:00:00+00:00")
        row = result["workspaces"][0]
        self.assertEqual(row["window"]["since"], "2026-09-06T08:00:00+00:00")
        self.assertEqual(row["window"]["until"], "2026-09-08T08:00:00+00:00")
        self.assertIn("catching up", row["basis"])

    def test_a_gap_too_large_to_summarise_says_so(self):
        self.tick(now="2026-08-01T09:00:00+00:00")
        result = self.tick(now="2026-09-07T09:00:00+00:00")
        row = result["workspaces"][0]
        self.assertEqual(row["window"]["since"], "2026-09-06T08:00:00+00:00")
        self.assertIn("more than", row["basis"])

    def test_one_workspace_failing_does_not_starve_the_others(self):
        """Isolated the way a provider is in `replywatch`."""
        original = digest.build
        seen = []

        def explode(workspace, *a, **kw):
            seen.append(workspace)
            if len(seen) == 1:
                raise RuntimeError("no")
            return original(workspace, *a, **kw)

        digest.build = explode
        try:
            result = self.tick()
        finally:
            digest.build = original
        outcomes = [row["outcome"] for row in result["workspaces"]]
        self.assertEqual(outcomes.count(dw.FAILED), 1)
        self.assertGreater(outcomes.count(dw.BUILT), 0)
        failed = next(r for r in result["workspaces"]
                      if r["outcome"] == dw.FAILED)
        self.assertIn("RuntimeError", failed["error"])

    def test_delivery_is_attempted_rather_than_left_planned(self):
        """A scheduler that stops at "planned" proves the plan and nothing
        about the delivery. With no Slack configured the attempt records a
        refusal, which is the honest outcome and a recorded one."""
        result = self.tick()
        for row in result["workspaces"]:
            with self.subTest(workspace=row["workspace"]):
                self.assertIn(row["status"],
                              (notify.SENT, notify.FAILED,
                               notify.SUPPRESSED, notify.UNCONFIGURED))
                self.assertNotEqual(row["status"], notify.PLANNED)

    def test_a_concurrent_tick_is_skipped_and_says_so(self):
        with store.lock(for_path=dw.lock_file()):
            result = self.tick()
        self.assertFalse(result["ran"])
        self.assertIn("another process", result["why"])
        self.assertEqual(self.digests(), [])

    def test_the_status_reads_the_notification_log(self):
        self.tick()
        report = dw.status(now=self.MONDAY, env=self.env())
        self.assertTrue(report["enabled"])
        for row in report["workspaces"]:
            with self.subTest(workspace=row["workspace"]):
                self.assertIsNotNone(row["this_period"])
                self.assertEqual(row["last_covered_until"],
                                 "2026-09-07T08:00:00+00:00")

    def test_the_status_of_a_period_nobody_delivered_is_absent(self):
        """Silence reported as silence, not as health."""
        report = dw.status(now=self.MONDAY, env=self.env())
        self.assertTrue(all(row["this_period"] is None
                            for row in report["workspaces"]))


class WhatAnOperatorIsTold(WebTest):
    """A schedule that stopped working has to be visible, and only then."""

    LATE = "2026-09-07T12:00:00+00:00"

    def env(self, schedule="daily"):
        return {"DIGEST_SCHEDULE": schedule, "DIGEST_HOUR": "8"}

    def tearDown(self):
        rows = [r for r in notify.load()
                if r.get("type") != notify.OPERATIONS_DIGEST]
        notify.save(rows)
        super().tearDown()

    def test_off_is_not_a_fault(self):
        """Reply polling off means somebody may be written to after they
        answered. A digest off means nobody asked for one."""
        self.assertEqual(dw.problems(now=self.LATE, env={}), [])

    def test_a_period_nobody_delivered_is_a_row(self):
        found = dw.problems("productive", now=self.LATE, env=self.env())
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["state"], "missing")
        self.assertIn("2026-09-07T08:00:00+00:00", found[0]["detail"])

    def test_a_delivered_period_is_not(self):
        dw.tick(now="2026-09-07T08:30:00+00:00", env=self.env())
        self.assertEqual(dw.problems("productive", now=self.LATE,
                                     env=self.env()), [])

    def test_it_is_not_called_late_before_the_grace_period(self):
        """The watcher ticks on an interval. A digest is never instant."""
        self.assertEqual(
            dw.problems("productive", now="2026-09-07T08:05:00+00:00",
                        env=self.env()), [])

    def test_a_broken_schedule_is_a_row_of_its_own(self):
        found = dw.problems("productive", now=self.LATE,
                            env={"DIGEST_SCHEDULE": "hourly"})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["state"], "misconfigured")

    def test_another_workspace_is_not_this_workspaces_problem(self):
        found = dw.problems("productive", now=self.LATE, env=self.env())
        self.assertEqual({row["workspace"] for row in found}, {"productive"})

    def test_it_reaches_the_health_page(self):
        """The recurring defect: a thing computed correctly that nothing
        downstream reads.

        What is asserted is the *reading*, with `problems` replaced by a
        known answer. The first version of this test set the schedule and
        the hour and trusted the wall clock, so it passed all day and
        failed for the hour after 08:00 UTC - which is exactly the window
        `GRACE_SECONDS` exists to create. The grace period has its own
        test, above, with the time pinned.
        """
        from src import digestwatch, repo as repo_module
        from src.web import api

        original = digestwatch.problems
        digestwatch.problems = lambda *a, **kw: [
            {"workspace": "productive", "state": "missing",
             "period": "2026-09-07T08:00:00+00:00",
             "detail": "no digest for the period ending 2026-09-07T08:00",
             "label": "the scheduled digest did not run"}]
        try:
            repo = repo_module.Repo.for_user("ops@productive.test",
                                             "productive")
            rows = api.operational_health(repo)["rows"]
        finally:
            digestwatch.problems = original
        digests = [r for r in rows if r["what"] == "daily digest"]
        self.assertEqual(len(digests), 1)
        self.assertTrue(digests[0]["retry_safe"])
        self.assertIn("no digest for the period", digests[0]["detail"])

    def test_the_health_page_is_quiet_when_no_digest_was_asked_for(self):
        from src import repo as repo_module
        from src.web import api

        repo = repo_module.Repo.for_user("ops@productive.test", "productive")
        rows = api.operational_health(repo)["rows"]
        self.assertEqual([r for r in rows if r["what"] == "daily digest"], [])


class TheThread(unittest.TestCase):
    """One thread, two jobs, and neither may take the other down."""

    def test_the_hook_is_none_when_the_schedule_is_off(self):
        self.assertIsNone(dw.hook({}))
        self.assertIsNotNone(dw.hook({"DIGEST_SCHEDULE": "daily"}))

    def test_a_bad_schedule_refuses_at_the_hook_rather_than_at_the_tick(self):
        with self.assertRaises(dw.NotConfigured):
            dw.hook({"DIGEST_SCHEDULE": "hourly"})

    def test_the_after_job_runs_on_every_tick(self):
        ran = []
        watcher = replywatch.Watcher(polling=False,
                                     after=(("digest", lambda: ran.append(1)),))
        watcher._tick()
        watcher._tick()
        self.assertEqual(len(ran), 2)

    def test_polling_off_does_not_silence_the_digest(self):
        swept = []
        ran = []
        watcher = replywatch.Watcher(
            polling=False, sweeper=lambda **kw: swept.append(1),
            after=(("digest", lambda: ran.append(1)),))
        watcher._tick()
        self.assertEqual(swept, [])
        self.assertEqual(len(ran), 1)

    def test_a_failing_digest_does_not_stop_polling(self):
        swept = []

        def boom():
            raise RuntimeError("no")

        watcher = replywatch.Watcher(
            sweeper=lambda **kw: swept.append(1),
            after=(("digest", boom),))
        watcher._tick()
        watcher._tick()
        self.assertEqual(len(swept), 2)

    def test_a_failing_digest_is_recorded_under_its_own_name(self):
        recorded = {}

        def boom():
            raise RuntimeError("no")

        original = replywatch._write_status
        replywatch._write_status = (
            lambda name, fields: recorded.setdefault(name, fields))
        try:
            replywatch.Watcher(polling=False,
                               after=(("digest", boom),))._tick()
        finally:
            replywatch._write_status = original
        self.assertIn("digest", recorded)
        self.assertIn("RuntimeError", recorded["digest"]["last_error"])

    def test_the_watcher_starts_for_the_digest_alone(self):
        """Reply polling off, digest on. A thread that refused to start
        because one job was disabled would take the other with it."""
        watcher, why = replywatch.start(
            env={}, after=(("digest", lambda: None),))
        try:
            self.assertIsNotNone(watcher)
            self.assertFalse(watcher.polling)
            self.assertIn("reply polling is off", why)
        finally:
            if watcher is not None:
                watcher.stop()

    def test_nothing_starts_when_neither_job_is_on(self):
        watcher, why = replywatch.start(env={})
        self.assertIsNone(watcher)
        self.assertIn("reply polling is off", why)


if __name__ == "__main__":
    unittest.main()
