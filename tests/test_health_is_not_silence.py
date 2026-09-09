"""Screens that reported health by not looking.

Five of these are the same defect wearing different clothes: a window is
read, the thing being counted is rarer than the window, and what comes back
is presented as the answer rather than as the page. The sixth is a constant
sentence beside a derived state, which is the same lie told differently.

They matter more than an ordinary display bug because each one is the
surface somebody checks *before* deciding it is safe to proceed. A health
screen that is clean because it was not watching is worse than no health
screen, which is a thing `operational_health` says in its own docstring
while doing it.
"""
import os
import unittest

from src import campaigns, killswitch, notify, workspaces as ws
from src.web import api, pages
from tests.base import QueueTest


class TheNotificationWindow(QueueTest):
    """`notify.history` filters by status *before* it slices.

    `operational_health` took the newest 500 rows of any status and looked
    for failures in Python, so a workspace whose failures were older than
    its last 500 notifications reported clean.
    """

    def rows(self, failures=3, noise=600):
        out = []
        for i in range(failures):
            out.append({"workspace": "demo", "type": "reply",
                        "status": notify.FAILED, "destination": "slack",
                        "severity": "high", "at": f"2026-01-01T00:{i:02d}:00Z"})
        for i in range(noise):
            out.append({"workspace": "demo", "type": "reply",
                        "status": notify.SENT, "destination": "slack",
                        "severity": "low", "at": f"2026-09-0{i % 9 + 1}T00:00:00Z"})
        return out

    def test_a_failure_older_than_the_window_is_still_found(self):
        found = notify.history("demo", status=notify.FAILED, limit=500,
                               rows=self.rows())
        self.assertEqual(len(found), 3)

    def test_without_the_filter_it_would_have_been_missed(self):
        """The discriminator: the old call shape, on the same rows."""
        window = notify.history("demo", limit=500, rows=self.rows())
        self.assertEqual([r for r in window if r["status"] == notify.FAILED],
                         [], "the fixture must hide the failures to be about "
                             "the defect")

    def test_the_limit_still_bounds_what_comes_back(self):
        many = [{"workspace": "demo", "type": "reply", "status": notify.FAILED,
                 "destination": "slack", "severity": "high",
                 "at": f"2026-01-01T00:00:{i:02d}Z"} for i in range(20)]
        self.assertEqual(
            len(notify.history("demo", status=notify.FAILED, limit=5,
                               rows=many)), 5)


class TheHealthScreenAsksForFailures(unittest.TestCase):
    """Asserted at the seam, deliberately.

    The behaviour that matters is which question `operational_health` puts
    to `notify.history`, and building an estate with more than five hundred
    notifications to observe it end to end would test the fixture rather
    than the code. So this records the call and asserts the argument -
    which is still what the function *does* when it runs, not what its
    source says. `TheNotificationWindow` above proves the argument changes
    the answer.
    """

    def test_it_narrows_by_status_rather_than_filtering_afterwards(self):
        from src import notify as notify_module
        from src.web import api as api_module

        seen = {}
        real = notify_module.history

        def recording(workspace=None, event_type=None, status=None,
                      limit=200, rows=None):
            seen["status"] = status
            return []

        notify_module.history = recording
        self.addCleanup(setattr, notify_module, "history", real)

        class Repo:
            workspace = "demo"
            client = "demo"

            def require(self, permission):
                return True

            def records(self):
                return []

            def campaigns(self):
                return []

            def config(self):
                return {}

        try:
            api_module.operational_health(Repo())
        except Exception:
            # Other sections of the screen need more of an estate than this
            # stub has. The notification question is asked first, and it is
            # the only thing being asserted.
            pass
        self.assertEqual(seen.get("status"), notify_module.FAILED)


class TheAuditWindow(QueueTest):
    """A refusal is rare next to routine writes, so a fixed window of
    audit rows loses refusals first - and the total fell as a workspace
    got busier, which is backwards."""

    def seed(self, refusals=2, noise=50):
        for i in range(refusals):
            ws.record("attacker@x.test", "demo", "security.refused",
                      resource_type="request", resource_id=f"GET /x{i}",
                      metadata={"kind": "cross_workspace"}, reason="no")
        for i in range(noise):
            ws.record("ops@demo.test", "demo", "campaign.created",
                      resource_type="campaign", resource_id=f"c{i}")

    def test_the_action_filter_runs_before_the_limit(self):
        self.seed()
        found = ws.audit("demo", limit=10, action="security.refused")
        self.assertEqual(len(found), 2)
        self.assertTrue(all(e["action"] == "security.refused" for e in found))

    def test_without_it_the_window_would_have_hidden_them(self):
        self.seed()
        window = ws.audit("demo", limit=10)
        self.assertEqual(
            [e for e in window if e["action"] == "security.refused"], [],
            "the fixture must bury the refusals to be about the defect")

    def test_the_total_counts_all_of_them_not_the_page(self):
        self.seed()
        self.assertEqual(ws.audit_total("demo", action="security.refused"), 2)

    def test_the_total_is_not_capped_by_a_limit(self):
        self.seed(refusals=0, noise=400)
        self.assertEqual(ws.audit_total("demo"), 400)


class TheAuditPageSaysHowManyItIsShowing(unittest.TestCase):
    """"300 entries" was the page size reporting itself as the answer."""

    def entries(self, n):
        return [{"at": "2026-09-01T00:00:00Z", "actor": "a@b.test",
                 "workspace": "demo", "action": "campaign.created",
                 "resource_type": "campaign", "resource_id": f"c{i}",
                 "before": None, "after": None, "reason": None,
                 "metadata": None} for i in range(n)]

    def test_it_says_so_when_there_are_more(self):
        body = pages.audit_log(self.entries(300), "demo", total=4000)
        self.assertIn("showing the newest 300 of 4000", body)

    def test_it_does_not_when_there_are_not(self):
        body = pages.audit_log(self.entries(12), "demo", total=12)
        self.assertIn("12 entries", body)
        self.assertNotIn("showing the newest", body)

    def test_an_unknown_total_reads_as_it_always_did(self):
        body = pages.audit_log(self.entries(5), "demo")
        self.assertIn("5 entries", body)


class TheSlackFlagAgreesWithItself(unittest.TestCase):
    """`state` was derived and `why` was a constant saying the switch was
    off, so with it on the row read "on" beside "SLACK_LIVE is unset"."""

    def flag(self):
        found = [f for f in api.feature_flags()
                 if f["flag"] == "slack_posting"]
        self.assertEqual(len(found), 1)
        return found[0]

    def setUp(self):
        self._prev = os.environ.get("SLACK_LIVE")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._prev is None:
            os.environ.pop("SLACK_LIVE", None)
        else:
            os.environ["SLACK_LIVE"] = self._prev

    def test_off_says_off(self):
        os.environ.pop("SLACK_LIVE", None)
        flag = self.flag()
        self.assertFalse(flag["state"])
        self.assertIn("unset", flag["why"])

    def test_on_does_not_say_unset(self):
        os.environ["SLACK_LIVE"] = "1"
        flag = self.flag()
        self.assertTrue(flag["state"])
        self.assertNotIn("unset", flag["why"],
                         "the flag says it is on and explains that it is off")


class APausedInboxIsNotAllocated(unittest.TestCase):
    """`senderidentity` defines five health states and two of them say the
    account must not be used. Neither `assignment` nor `push` mentioned the
    field, so an inbox somebody had marked `paused` was allocated
    prospects and written into a payload exactly like a healthy one."""

    def rows(self, health):
        return [
            {"kind": "sender", "workspace": "demo", "sender_id": "anna",
             "active": True, "name": "Anna"},
            {"kind": "email_account", "workspace": "demo",
             "account_id": "anna01", "sender_id": "anna", "active": True,
             "provider": "emailbison", "health": health,
             "email_address": "anna@demo.test", "domain": "demo.test"},
        ]

    def eligible(self, health):
        from src import assignment

        return assignment.eligible_senders("demo", "email",
                                           rows=self.rows(health))

    def test_a_paused_inbox_makes_its_owner_ineligible(self):
        self.assertEqual(self.eligible("paused"), [])

    def test_a_blocked_inbox_does_too(self):
        self.assertEqual(self.eligible("blocked"), [])

    def test_a_healthy_inbox_is_still_eligible(self):
        """Otherwise the guard refuses everybody and proves nothing."""
        self.assertEqual(len(self.eligible("ok")), 1)

    def test_a_warming_inbox_is_still_eligible(self):
        """Warming sends, at low volume. Refusing it would take a new
        inbox out of rotation for the period it exists to work through."""
        self.assertEqual(len(self.eligible("warming")), 1)

    def test_an_unknown_health_is_still_eligible(self):
        """The default a real roster starts in. Treating "nobody has said"
        as "do not use" would empty a roster rather than protect it."""
        self.assertEqual(len(self.eligible("unknown")), 1)

    def test_an_absent_health_field_is_still_eligible(self):
        from src import assignment

        rows = self.rows("ok")
        rows[1].pop("health")
        self.assertEqual(
            len(assignment.eligible_senders("demo", "email", rows=rows)), 1)


class TheKillSwitchReadsTheFreeze(unittest.TestCase):
    """`eligibility._campaign` checks the freeze before anything else,
    because it is the stop button. The screen an operator opens to ask
    whether a campaign would send did not check it at all."""

    def campaign(self, **extra):
        return dict({"campaign_id": "c", "client": "demo",
                     "status": campaigns.RUNNING}, **extra)

    def test_a_frozen_running_campaign_would_not_send(self):
        state = killswitch.campaign_state(
            self.campaign(freeze={"why": "a client asked us to stop"}))
        self.assertFalse(state["sending"])

    def test_it_says_frozen_rather_than_something_vaguer(self):
        state = killswitch.campaign_state(
            self.campaign(freeze={"why": "stop"}))
        self.assertIn("frozen", str(state).lower())

    def test_a_running_campaign_still_sends(self):
        """Otherwise the guard refuses everything and proves nothing."""
        state = killswitch.campaign_state(self.campaign())
        self.assertTrue(state["sending"])

    def test_a_paused_campaign_is_unchanged(self):
        state = killswitch.campaign_state(
            self.campaign(status=campaigns.PAUSED))
        self.assertFalse(state["sending"])


if __name__ == "__main__":
    unittest.main()
