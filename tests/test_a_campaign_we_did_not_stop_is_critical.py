"""A campaign stopped and nobody was told.

MEASURED 2026-09-23. EmailBison 495 went `active` -> `archived` at 15:57:22Z
with 59 of its 60 leads reading `stopped` and 42 of 60 ever contacted.
Nothing in this system did it: no action-ledger row, no write refusal, and
our own campaign row's last log entry is from 09-21. It was found hours later
by reading a heartbeat file by hand while looking at something else.

A campaign stopping is the difference between sending and not sending. It was
the one state change in this watcher with no alert on it.

WHAT THIS DOES NOT CLAIM. The provider names no actor - its event feed
carries delivery events only and holds ZERO rows mentioning an archive - so
"who" is not answerable from the API. The alert reports the transition and
whether OUR OWN canonical state can account for it, and never asserts a third
party.

The asymmetry below is the load-bearing part: positive evidence makes it
ours, absence never makes it somebody else's. Telling an operator a third
party archived their campaign when our own process did it four minutes
earlier is the expensive mistake here.
"""
import importlib.util
import unittest


def _load():
    spec = importlib.util.spec_from_file_location(
        "_bwl_stop", "scripts/bison_watch_loop.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheTransitionIsDetected(unittest.TestCase):

    def setUp(self):
        self.watch = _load()
        self.lines = []
        self.notified = []
        real = self.watch._we_did_it
        self.addCleanup(setattr, self.watch, "_we_did_it", real)

    def _fire(self, status, ours, was="active"):
        self.watch._we_did_it = lambda *a, **k: (
            ours, "our campaign row logs 'pause'" if ours
            else "our campaign row logs no pause, archive or stop")
        from src import notify
        real_notify = notify.notify
        notify.notify = lambda *a, **k: self.notified.append((a, k))
        self.addCleanup(setattr, notify, "notify", real_notify)
        self.watch._alert_if_stopped_by_someone_else(
            495, "495", was,
            {"status": status, "emails_sent": 42, "leads": 60},
            self.lines.append)

    def test_the_495_case_alerts(self):
        self._fire("archived", ours=False)
        self.assertEqual(len(self.notified), 1)
        self.assertIn("CAMPAIGN-STOPPED", self.lines[0])
        self.assertIn("NOT ATTRIBUTABLE TO US", self.lines[0])

    def test_it_is_critical_and_global(self):
        from src import notify
        self.assertEqual(
            notify.ROUTES[notify.CAMPAIGN_STOPPED_EXTERNALLY],
            (notify.GLOBAL, notify.CRITICAL))

    def test_our_own_routine_pause_is_not_made_critical(self):
        """Raising CAMPAIGN_PAUSED's severity instead would have made every
        deliberate pause critical, which is how a critical channel stops
        being read."""
        from src import notify
        self.assertEqual(notify.ROUTES[notify.CAMPAIGN_PAUSED],
                         (notify.GLOBAL, notify.WARNING))

    def test_paused_and_stopped_alert_too_not_only_archived(self):
        for status in ("paused", "stopped", "archived"):
            with self.subTest(status=status):
                self.notified, self.lines = [], []
                self._fire(status, ours=False)
                self.assertEqual(len(self.notified), 1)

    def test_a_stop_we_can_account_for_does_not_alert(self):
        """Absence of evidence is not evidence; PRESENCE of it is. When our
        own row logs the pause, this must stay quiet."""
        self._fire("archived", ours=True)
        self.assertEqual(self.notified, [])
        self.assertIn("ours", self.lines[0])

    def test_an_ordinary_transition_does_not_alert(self):
        self.notified, self.lines = [], []
        self._fire("active", ours=False, was="draft")
        self.assertEqual(self.notified, [])
        self.assertEqual(self.lines, [])

    def test_a_failing_notification_does_not_kill_the_watcher(self):
        from src import notify
        real = notify.notify
        notify.notify = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
        self.addCleanup(setattr, notify, "notify", real)
        self.watch._we_did_it = lambda *a, **k: (False, "no")
        self.watch._alert_if_stopped_by_someone_else(
            495, "495", "active",
            {"status": "archived", "emails_sent": 42, "leads": 60},
            self.lines.append)
        self.assertTrue(any("ALERT-FAILED" in l for l in self.lines))


class TestAttributionIsPositiveEvidenceOnly(unittest.TestCase):

    def setUp(self):
        self.watch = _load()

    def test_an_unreadable_canonical_state_is_not_ours(self):
        """It must not claim WE did it just because it could not look."""
        import src.campaigns as campaigns
        real = campaigns.load
        campaigns.load = lambda *a, **k: (_ for _ in ()).throw(OSError("gone"))
        self.addCleanup(setattr, campaigns, "load", real)
        ours, why = self.watch._we_did_it(495)
        self.assertFalse(ours)
        self.assertIn("unreadable", why)

    def test_a_campaign_with_no_local_row_is_not_ours(self):
        ours, why = self.watch._we_did_it(99999999)
        self.assertFalse(ours)
        self.assertIn("no local campaign row", why)

    def test_495_today_is_not_attributable_to_us(self):
        """The live measurement, asserted. If this ever turns green-as-ours,
        somebody has added a log line and the finding needs re-reading."""
        ours, why = self.watch._we_did_it(495)
        self.assertFalse(ours, f"495 now reads as ours: {why}")


if __name__ == "__main__":
    unittest.main()
