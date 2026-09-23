"""The weekly question, answered - and the three states it must not merge.

`docs/SLACK-AGENT-EXPECTATIONS.md` calls the weekly update "a habit with a
shape", asked every Monday and Tuesday. The agent could answer each piece
of it separately and none of it as the question people actually ask, which
is *what is happening this week*.

Two things make `weekly_plan` honest rather than merely useful:

1. **The forward half is three days long and says so.** The provider
   answers `today`, `tomorrow` and `day_after_tomorrow` and nothing beyond.
   A week's plan that implied Thursday would be our inference wearing the
   provider's clothes.

2. **Nothing scheduled, zero scheduled and unreadable are three different
   answers.** The provider's empty result arrives as an HTTP 400 carrying
   "No emails scheduled for this period"; reading that as a transport
   failure alarms every weekend and reading it as zero reports a healthy
   campaign as silent. `src/providers/bison.py` says so at length, and this
   asserts the agent kept the distinction.
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackagenttools as tools                         # noqa: E402
from src import slackscope                                       # noqa: E402
from src.providers import bison                                  # noqa: E402

PACK = {"workspaces": {"alpha": {"provider_campaign_ids": ["491", "492"]},
                       "beta": {"provider_campaign_ids": ["601"]}}}
RECENT = "2026-09-22T09:00:00Z"


def client(workspace="alpha"):
    return slackscope.Scope(slackscope.CLIENT, workspace=workspace,
                            source="test")


def internal():
    return slackscope.Scope(slackscope.INTERNAL, source="test")


class PlanningTest(unittest.TestCase):

    def setUp(self):
        self._pack = tools.knowledge.pack
        self._detail = tools.readback.campaign_by_id
        self._default = tools._default_workspace
        tools.knowledge.pack = lambda *a, **k: PACK
        tools._default_workspace = lambda: "alpha"
        tools.readback.campaign_by_id = lambda cid: {
            "campaign_id": cid, "name": "campaign %s" % cid,
            "status": "active", "emails_sent": 5}

    def tearDown(self):
        tools.knowledge.pack = self._pack
        tools._default_workspace = self._default
        tools.readback.campaign_by_id = self._detail

    def plan(self, scope, schedule=None, queue=None):
        """`weekly_plan` over a fixed provider.

        `schedule` is `{(campaign, day): value}` where a value may be an
        int, an Exception to raise, or absent for "nothing configured".
        """
        def sending_schedule(campaign_id, day):
            value = (schedule or {}).get((str(campaign_id), day))
            if isinstance(value, Exception):
                raise value
            if value is None:
                raise bison.SendingScheduleEmpty("nothing for %s" % day)
            return {"emails_being_sent": value, "day": day}

        def scheduled_emails(campaign_id, cap=None):
            return (queue or {}).get(str(campaign_id)) or []

        with mock.patch.object(bison, "sending_schedule", sending_schedule), \
                mock.patch.object(bison, "scheduled_emails",
                                  scheduled_emails):
            return tools.weekly_plan(scope)


# ================================ 1. THE HORIZON IS NAMED

class TheForwardHalfIsThreeDaysAndSaysSo(PlanningTest):

    def test_the_provider_is_asked_for_its_own_three_days_and_no_more(self):
        asked = []

        def sending_schedule(campaign_id, day):
            asked.append(day)
            raise bison.SendingScheduleEmpty("none")

        with mock.patch.object(bison, "sending_schedule", sending_schedule), \
                mock.patch.object(bison, "scheduled_emails",
                                  lambda c, cap=None: []):
            out = tools.weekly_plan(internal())
        self.assertEqual(sorted(set(asked)),
                         sorted(set(tools.FORWARD_DAYS)))
        self.assertEqual(sorted(out["forward"]),
                         sorted(tools.FORWARD_DAYS))

    def test_the_horizon_is_stated_in_the_material(self):
        out = self.plan(internal())
        self.assertIn("nothing beyond", out["forward_horizon"])

    def test_the_note_says_it_is_not_a_commitment(self):
        out = self.plan(internal())
        self.assertIn("not a commitment", out["note"])


# ================================ 2. THREE STATES, NEVER TWO

class NothingScheduledIsNotZeroAndNeitherIsUnreadable(PlanningTest):

    def test_the_providers_empty_answer_is_its_own_state(self):
        out = self.plan(internal(), schedule={("491", "today"): 40})
        self.assertEqual(out["forward"]["today"]["491"], 40)
        self.assertEqual(out["forward"]["today"]["492"], "none scheduled")

    def test_a_transport_failure_is_not_an_empty_answer(self):
        out = self.plan(internal(),
                        schedule={("491", "today"): RuntimeError("502")})
        self.assertEqual(out["forward"]["today"]["491"], "unreadable")

    def test_a_real_zero_is_a_real_zero(self):
        """The provider saying "0" and the provider saying "nothing here"
        are both legitimate and they are not the same sentence."""
        out = self.plan(internal(), schedule={("491", "tomorrow"): 0})
        self.assertEqual(out["forward"]["tomorrow"]["491"], 0)
        self.assertEqual(out["forward"]["tomorrow"]["492"], "none scheduled")

    def test_a_non_integer_count_is_not_believed(self):
        with mock.patch.object(
                bison, "sending_schedule",
                lambda c, d: {"emails_being_sent": "lots"}), \
                mock.patch.object(bison, "scheduled_emails", lambda c, cap=None: []):
            out = tools.weekly_plan(internal())
        self.assertEqual(out["forward"]["today"]["491"], "unreadable")


# ================================ 3. THE BACKWARD HALF

class WhatAlreadyHappenedTravelsWithThePlan(PlanningTest):

    def test_people_and_emails_are_counted_apart(self):
        rows = [{"id": 1, "sent_at": RECENT, "lead": {"id": 7}},
                {"id": 2, "sent_at": RECENT, "lead": {"id": 7}},
                {"id": 3, "sent_at": RECENT, "lead": {"id": 8}}]
        out = self.plan(internal(), queue={"491": rows})
        self.assertEqual(out["emails_sent_last_7_days"], 3)
        self.assertEqual(out["leads_emailed_last_7_days"], 2)

    def test_an_unreadable_campaign_makes_it_a_partial_picture(self):
        tools.readback.campaign_by_id = lambda cid: (
            {"_error": "down"} if cid == "491"
            else {"campaign_id": cid, "status": "active"})
        out = self.plan(internal())
        self.assertEqual(out["campaigns_unreadable"], 1)
        self.assertIn("partial picture", out["warning"])


# ================================ 4. SCOPE

class AClientGetsTheWeekWithoutOurMachinery(PlanningTest):

    def test_a_client_is_never_shown_what_the_week_waits_on(self):
        out = self.plan(client())
        self.assertNotIn("waiting_on_a_decision", out)
        self.assertNotIn("campaigns_awaiting_decision", out)

    def test_an_internal_channel_is(self):
        one = [{"id": "r1"}]
        with mock.patch.object(tools, "_open_tickets", lambda: one), \
                mock.patch.object(tools, "_awaiting_decision", lambda: []):
            out = self.plan(internal())
        self.assertEqual(out["waiting_on_a_decision"], [{"id": "r1"}])

    def test_a_client_sees_only_its_own_campaigns(self):
        out = self.plan(client("alpha"))
        ids = {row["campaign_id"] for row in out["campaigns"]}
        self.assertEqual(ids, {"491", "492"})
        self.assertNotIn("601", ids)

    def test_it_is_on_the_tool_list_for_both_scopes(self):
        self.assertIn("weekly_plan", tools.for_scope(client()))
        self.assertIn("weekly_plan", tools.for_scope(internal()))

    def test_a_campaign_name_reaches_a_client_without_our_experiment(self):
        """`for_client` is the pass that does this, and the plan goes
        through `run` like every other tool."""
        tools.readback.campaign_by_id = lambda cid: {
            "campaign_id": cid, "status": "active",
            "name": "RESONATE - ALPHA - EMAIL - US-HOURS - CONTROL"}
        with mock.patch.object(bison, "sending_schedule",
                               side_effect=bison.SendingScheduleEmpty("x")), \
                mock.patch.object(bison, "scheduled_emails", lambda c, cap=None: []):
            out = tools.run(client(), "weekly_plan")
        for row in out["campaigns"]:
            self.assertNotIn("CONTROL", row["name"])
            self.assertNotIn("US-HOURS", row["name"])


if __name__ == "__main__":
    unittest.main()
