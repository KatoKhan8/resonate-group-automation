"""A reply poller that has stopped must not look like one that is working.

`replywatch` wrote a detailed status file from the day it existed and
nothing read it, which is this repository's usual way of losing a computed
value: the poller could have been dead for a week and every screen would
have looked calm.

The rule these hold down is that silence is never health. Never run, ran
and failed, ran and went quiet - each is a row an operator sees, not an
absence they have to notice.
"""
import unittest

from tests.webbase import WebTest

from src import replywatch


NOW = "2026-09-03T12:00:00+00:00"
ENABLED = {"REPLY_POLL_ENABLED": "1", "REPLY_POLL_PROVIDERS": "emailbison"}


class TheVerdict(unittest.TestCase):

    def health(self, status, env=ENABLED, now=NOW):
        return replywatch.health(now=now, env=env, status=status)[0]

    def test_off_is_reported_as_off_not_as_working(self):
        got = self.health({}, env={"REPLY_POLL_PROVIDERS": "emailbison"})
        self.assertEqual(got["state"], replywatch.OFF)

    def test_never_run_is_a_problem_not_an_absence(self):
        self.assertEqual(self.health({})["state"], replywatch.NEVER_RUN)

    def test_a_recent_success_is_working(self):
        got = self.health({"emailbison": {
            "last_succeeded": "2026-09-03T11:58:00+00:00"}})
        self.assertEqual(got["state"], replywatch.WORKING)

    def test_a_success_older_than_the_allowance_is_stale(self):
        got = self.health({"emailbison": {
            "last_succeeded": "2026-09-03T06:00:00+00:00"}})
        self.assertEqual(got["state"], replywatch.STALE)
        self.assertEqual(got["seconds_since_success"], 6 * 3600)

    def test_a_failure_outranks_a_recent_success(self):
        """It succeeded a minute ago and has failed every attempt since.
        Reporting that as working is how a dead poller stays hidden."""
        got = self.health({"emailbison": {
            "last_succeeded": "2026-09-03T11:59:00+00:00",
            "consecutive_failures": 4, "last_error": "ProviderError: 401"}})
        self.assertEqual(got["state"], replywatch.FAILING)
        self.assertEqual(got["consecutive_failures"], 4)

    def test_an_unreadable_timestamp_does_not_read_as_fresh(self):
        got = self.health({"emailbison": {"last_succeeded": "nonsense"}})
        self.assertIsNone(got["seconds_since_success"])
        self.assertNotEqual(got["state"], replywatch.STALE)

    def test_naive_and_aware_timestamps_are_refused_rather_than_guessed(self):
        """Subtracting them raises, and assuming one is UTC would report a
        confident number that is wrong by hours."""
        got = self.health({"emailbison": {
            "last_succeeded": "2026-09-03T06:00:00"}}, now=NOW)
        self.assertIsNone(got["seconds_since_success"])

    def test_problems_leaves_out_the_working_ones(self):
        working = {"emailbison": {
            "last_succeeded": "2026-09-03T11:58:00+00:00"}}
        self.assertEqual(
            replywatch.problems(now=NOW, env=ENABLED, status=working), [])

    def test_off_is_ordinary_here_and_a_problem_in_production(self):
        """On a laptop or in the fictional estate, polling being off is the
        normal state; listing it would make "nothing is wrong" impossible to
        say. On the deployed service it means replies are not being ingested
        at all, which is exactly the silent-health failure."""
        env = {"REPLY_POLL_PROVIDERS": "emailbison"}
        self.assertEqual(
            replywatch.problems(now=NOW, env=env, status={}, mode="demo"), [])
        production = replywatch.problems(now=NOW, env=env, status={},
                                         mode="production")
        self.assertEqual(len(production), 1)
        self.assertEqual(production[0]["state"], replywatch.OFF)

    def test_a_stale_poller_is_a_problem_in_either_mode(self):
        stale = {"emailbison": {"last_succeeded": "2026-09-03T06:00:00+00:00"}}
        for where in ("demo", "production"):
            with self.subTest(mode=where):
                found = replywatch.problems(now=NOW, env=ENABLED,
                                            status=stale, mode=where)
                self.assertEqual([r["state"] for r in found],
                                 [replywatch.STALE])

    def test_the_verdict_never_names_a_workspace(self):
        """It is rendered inside one tenant's pages. The status file knows
        which workspaces the events landed in; this must not repeat it."""
        status = {"emailbison": {"last_succeeded": NOW,
                                 "workspaces": {"productive": 3}}}
        got = self.health(status)
        self.assertNotIn("workspaces", got)
        self.assertNotIn("productive", str(got))


class ItReachesTheOperator(WebTest):

    def test_the_health_page_reads_reply_protection(self):
        """In the fictional estate polling is off, which is not a failure,
        so the page is expected to stay clean. What is asserted is that the
        page renders with the check wired in - the verdict itself is held
        down above, where the mode can be chosen."""
        session = self.signin("ops@productive.test")
        status, body, _ = session.get("/health")
        self.assertEqual(status, 200)
        self.assertNotIn("reply protection", body,
                         "polling is off here, and off is not a failure")

    def test_a_failing_poller_reaches_the_health_page(self):
        import os
        from src import replywatch as rw
        previous = {k: os.environ.get(k) for k in
                    ("REPLY_POLL_ENABLED", "REPLY_POLL_PROVIDERS")}
        os.environ["REPLY_POLL_ENABLED"] = "1"
        os.environ["REPLY_POLL_PROVIDERS"] = "emailbison"
        rw._write_status("emailbison", {
            "last_succeeded": "2020-01-01T00:00:00+00:00",
            "consecutive_failures": 5,
            "last_error": "ProviderError: unauthorised"})
        try:
            session = self.signin("ops@productive.test")
            status, body, _ = session.get("/health")
            self.assertEqual(status, 200)
            self.assertIn("reply protection", body)
            self.assertIn("unauthorised", body)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            path = rw.status_path()
            if os.path.exists(path):
                os.remove(path)

    def test_a_viewer_still_cannot_read_it(self):
        session = self.signin("client@productive.test")
        self.assertEqual(session.get("/health")[0], 403)


class ItSaysSoOnce(WebTest):
    """A provider outage is one alert, not one every few minutes.

    The channel that carries "reply protection has stopped" is the one
    nobody may learn to ignore: it is the only failure here that means
    somebody is still being written to after they answered.
    """

    def setUp(self):
        super().setUp()
        import os
        from src import notify, replywatch as rw
        self.notify = notify
        self.rw = rw
        self._env = {k: os.environ.get(k) for k in
                     ("REPLY_POLL_ENABLED", "REPLY_POLL_PROVIDERS")}
        # The estate is built once per class, so notifications written by
        # an earlier test are still here. Each of these counts alerts, so
        # each needs to start from none.
        self._before = [n for n in notify.load()
                        if n.get("type") != notify.REPLY_PROTECTION_FAILED]
        notify.save(self._before)
        path = rw.status_path()
        if os.path.exists(path):
            os.remove(path)

    def tearDown(self):
        import os
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        path = self.rw.status_path()
        if os.path.exists(path):
            os.remove(path)
        super().tearDown()

    def alerts(self):
        return [n for n in self.notify.load()
                if n.get("type") == self.notify.REPLY_PROTECTION_FAILED]

    def test_it_is_critical_and_goes_to_the_operations_channel(self):
        destination, severity = self.notify.ROUTES[
            self.notify.REPLY_PROTECTION_FAILED]
        self.assertEqual(destination, self.notify.GLOBAL)
        self.assertEqual(severity, self.notify.CRITICAL)

    def test_nothing_is_said_for_the_first_two_failures(self):
        """The counts are written out rather than derived from the
        constant. Deriving the loop bound from `ALERT_AFTER_FAILURES` made
        this test empty the moment somebody lowered it to 1, which is
        exactly the change it is supposed to catch."""
        for failures in (1, 2):
            self.assertIsNone(
                self.rw._alert("emailbison", failures, "ProviderError"),
                f"failure {failures} must not alert")
        self.assertEqual(self.alerts(), [])

    def test_it_is_said_on_the_third(self):
        self.assertIsNotNone(
            self.rw._alert("emailbison", 3, "ProviderError: refused"))
        self.assertEqual(len(self.alerts()), 1)

    def test_it_is_not_said_again_while_the_outage_continues(self):
        """Asserted on the call, not only on the stored rows.

        `notify` already deduplicates by notification id, so counting rows
        cannot tell "we stopped calling" from "we kept calling and it
        merged them". The second is a message built and discarded every
        interval for as long as the outage lasts.
        """
        self.rw._alert("emailbison", 3, "ProviderError: refused")
        for failures in range(4, 24):
            self.assertIsNone(
                self.rw._alert("emailbison", failures, "ProviderError"),
                f"failure {failures} must not alert again")
        self.assertEqual(len(self.alerts()), 1)

    def test_a_failing_poll_raises_the_alert_by_itself(self):
        """The chain, not the helper. Nothing above proves `poll_once`
        actually calls it."""
        import os
        from src.providers import bison
        os.environ["BISON_KEY"] = "test-key-not-real"
        real = bison.fetch_replies

        def broken(cursor=None, per_page=None):
            raise bison.ProviderError("unreachable")
        bison.fetch_replies = broken
        try:
            for _ in range(3):
                self.rw.poll_once("emailbison")
        finally:
            bison.fetch_replies = real
        self.assertEqual(len(self.alerts()), 1)

    def test_it_never_carries_a_credential(self):
        from src.web import security
        self.rw._alert("emailbison", self.rw.ALERT_AFTER_FAILURES,
                       "ProviderError: bad key abcd1234")
        body = str(self.alerts())
        for name in security.SECRET_ENV:
            self.assertNotIn(name, body)
