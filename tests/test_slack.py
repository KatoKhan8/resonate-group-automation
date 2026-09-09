"""Slack: what it may say, who it obeys, and what it cannot break.

Nothing here posts. The transport refuses in this build, and these tests assert
that refusal is real rather than assumed, then exercise everything around it:
the payloads, the permission checks, and - the important one - the guarantee
that a broken Slack cannot restart a paused company.
"""
import json
import os
import unittest

from src import campaigns, clients, events, orchestrator, roles, store
from src.providers import slack
from tests.campaignbase import CampaignTest

ADMIN = "U0DEMOADMIN1"
STRANGER = "U0STRANGER99"


class TestOffUnlessAskedFor(CampaignTest):
    def test_a_client_with_no_slack_block_posts_nothing(self):
        config = clients.load("productive")
        self.assertFalse(slack.enabled(config))
        allowed, why = slack.should_notify(config, slack.CAMPAIGN_READY)
        self.assertFalse(allowed)
        self.assertIn("not enabled", why)

    def test_enabling_slack_is_not_enough_without_a_channel(self):
        config = {"slack": {"enabled": True, "notify": {"positive_reply": True}}}
        allowed, why = slack.should_notify(config, slack.POSITIVE_REPLY)
        self.assertFalse(allowed)
        self.assertIn("no channel", why)

    def test_a_channel_is_not_enough_without_the_toggle(self):
        config = {"slack": {"enabled": True,
                            "positive_replies_channel": "C1",
                            "notify": {}}}
        allowed, why = slack.should_notify(config, slack.POSITIVE_REPLY)
        self.assertFalse(allowed)
        self.assertIn("off", why)

    def test_there_is_no_default_channel_to_fall_back_on(self):
        self.assertIsNone(slack.channel_for({"slack": {"enabled": True}},
                                            slack.POSITIVE_REPLY))

    def test_the_demo_client_is_fully_configured(self):
        allowed, _ = slack.should_notify(self.config, slack.CAMPAIGN_READY)
        self.assertTrue(allowed)


class TestNothingCanPost(CampaignTest):
    def test_the_transport_refuses(self):
        with self.assertRaises(slack.SlackPostingNotEnabled):
            slack.post({"channel": "C1", "text": "hello"}, self.config)

    def test_the_health_check_calls_nothing(self):
        result = slack.check()
        self.assertTrue(result["skipped"])
        self.assertEqual(self.cassette.calls, [])

    def test_the_module_issues_no_http_request_at_all(self):
        import inspect
        import re
        source = inspect.getsource(slack)
        self.assertIsNone(re.search(r"^\s*request\(", source, re.M))


class TestTheReadIsNotBehindTheWriteSwitch(unittest.TestCase):
    """Proving a token must not require arming the thing that sends.

    `check()` used to return SKIP whenever `SLACK_LIVE` was off - and
    `SLACK_LIVE` is the switch that arms `post()`. `auth.test` is free and
    read-only, and this function's whole job is readiness, so the only way
    to find out whether the token worked was to turn on posting. That made
    a read-only Slack proof a code change rather than a setting, and it is
    the wrong way round for a health check.
    """

    def setUp(self):
        from src import providers

        self.providers = providers
        self.calls = []

        def transport(method, url, headers, body, timeout):
            self.calls.append(url)
            return 200, json.dumps({"ok": True, "team": "resonate",
                                    "user": "resonate-bot"})

        providers.set_transport(transport)
        self.addCleanup(providers.reset_transport)
        self._env = {k: os.environ.get(k)
                     for k in ("SLACK_BOT_TOKEN", "SLACK_LIVE")}
        self.addCleanup(self._restore)
        os.environ["SLACK_BOT_TOKEN"] = "not-a-token-shaped-value"
        os.environ.pop("SLACK_LIVE", None)

    def _restore(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_a_token_alone_is_enough_to_check_it(self):
        """The defect."""
        result = slack.check()
        self.assertFalse(result.get("skipped"))
        self.assertTrue(result["ok"])

    def test_it_really_called_auth_test(self):
        slack.check()
        self.assertEqual(len(self.calls), 1)
        self.assertIn("auth.test", self.calls[0])

    def test_no_token_still_skips_without_calling(self):
        os.environ.pop("SLACK_BOT_TOKEN", None)
        result = slack.check()
        self.assertTrue(result["skipped"])
        self.assertEqual(self.calls, [])

    def test_checking_does_not_arm_posting(self):
        """The whole point of separating them. A successful read must not
        make the send path reachable."""
        slack.check()
        self.assertFalse(slack.live())
        with self.assertRaises(slack.SlackPostingNotEnabled):
            slack.post({"channel": "C1", "text": "hello"}, {})

    def test_slack_is_in_the_health_sweep(self):
        """It was absent while the documentation counted eight providers,
        so `python -m src.check` never touched it."""
        from src import check

        self.assertIn("Slack", check.PROVIDERS)


class TestTheApprovalPayload(CampaignTest):
    def payload(self):
        campaign, recs = self.ready_campaign()
        summary = orchestrator.summarise(campaign, recs, self.config)
        return slack.campaign_approval_request(campaign, summary, self.config), summary

    def test_it_goes_to_the_approvals_channel(self):
        payload, _ = self.payload()
        self.assertEqual(payload["channel"], "C0DEMOAPPROV")

    def test_it_offers_approve_reject_and_review(self):
        payload, _ = self.payload()
        ids = [a["action_id"] for a in payload["actions"]]
        self.assertEqual(ids, [slack.APPROVE, slack.REJECT, slack.OPEN_REVIEW])

    def test_it_carries_ids_rather_than_relying_on_the_words(self):
        payload, summary = self.payload()
        self.assertEqual(payload["metadata"]["campaign_id"], "camp-1")
        self.assertEqual(payload["metadata"]["fingerprint"], summary["fingerprint"])
        self.assertEqual(payload["metadata"]["client"], "demo")

    def test_it_shows_the_numbers_a_reviewer_needs(self):
        payload, _ = self.payload()
        blob = " ".join(payload["blocks"])
        for needed in ("domains", "contacts", "sendable", "held", "dropped",
                       "daily volume", "senders", "estimated spend"):
            self.assertIn(needed, blob, needed)

    def test_the_counts_are_real_rather_than_placeholders(self):
        _, summary = self.payload()
        self.assertEqual(summary["domains"], 2)
        self.assertEqual(summary["contacts"], 2)
        self.assertEqual(summary["sendable"], 2)


class TestPermissions(CampaignTest):
    def setUp(self):
        super().setUp()
        self.campaign, self.recs = self.ready_campaign()
        orchestrator.prepare(self.campaign, self.recs, self.config)
        orchestrator.request_approval(self.campaign, self.recs, self.config)
        self.fingerprint = campaigns.fingerprint(self.campaign, self.recs,
                                                 self.config)

    def decide(self, user, action="approve", fingerprint=None,
               interaction_id="i-1"):
        return orchestrator.decide(
            self.campaign, user, action,
            fingerprint=self.fingerprint if fingerprint is None else fingerprint,
            interaction_id=interaction_id, config=self.config, recs=self.recs)

    def test_a_configured_approver_may_approve(self):
        self.assertEqual(self.decide(ADMIN)["status"], "approved")
        self.assertEqual(self.campaign["status"], campaigns.APPROVED)

    def test_a_stranger_may_not(self):
        with self.assertRaises(slack.NotPermitted):
            self.decide(STRANGER)
        self.assertNotEqual(self.campaign["status"], campaigns.APPROVED)

    def test_an_unidentified_user_may_not(self):
        with self.assertRaises(slack.NotPermitted):
            self.decide(None)

    def test_an_empty_approver_list_permits_nobody(self):
        config = {"slack": {"enabled": True, "allowed_approvers": []}}
        self.assertFalse(slack.may_approve(config, ADMIN))

    def test_a_stale_fingerprint_is_refused(self):
        result = self.decide(ADMIN, fingerprint="not-the-current-one")
        self.assertEqual(result["status"], "stale")
        self.assertNotEqual(self.campaign["status"], campaigns.APPROVED)

    def test_the_same_interaction_twice_changes_state_once(self):
        first = self.decide(ADMIN, interaction_id="i-42")
        second = self.decide(ADMIN, interaction_id="i-42")
        self.assertEqual(first["status"], "approved")
        self.assertEqual(second["status"], "duplicate")
        approvals = [e for e in self.campaign["events"]
                     if e["type"] == events.CAMPAIGN_APPROVED]
        self.assertEqual(len(approvals), 1)

    def test_a_rejection_is_recorded_and_blocks_launch(self):
        self.assertEqual(self.decide(ADMIN, "reject")["status"], "rejected")
        self.assertEqual(self.campaign["status"], campaigns.REJECTED)
        result = campaigns.validate("camp-1", self.recs, self.config,
                                    campaign=self.campaign)
        self.assertFalse(result["ok"])
        self.assertIn("campaign approved", result["blockers"])

    def test_the_approval_records_everything_needed_to_audit_it(self):
        self.decide(ADMIN, interaction_id="i-7")
        given = self.campaign["approval"]
        for field in ("action", "by", "at", "fingerprint", "interaction_id"):
            self.assertIn(field, given, field)
        self.assertEqual(given["by"], ADMIN)
        self.assertEqual(given["interaction_id"], "i-7")

    def test_a_client_supplied_approved_flag_is_not_trusted(self):
        """Setting the field by hand does not make a campaign approved."""
        self.campaign["approval"] = {"action": "approve", "by": "me",
                                     "fingerprint": "made-up"}
        self.assertFalse(campaigns.is_approved(self.campaign, self.recs,
                                               self.config))

    def test_a_reviewer_can_approve_a_campaign_but_not_launch_it(self):
        self.assertTrue(roles.may(roles.REVIEWER, roles.APPROVE_CAMPAIGN))
        self.assertFalse(roles.may(roles.REVIEWER, roles.LAUNCH_CAMPAIGN))

    def test_a_viewer_can_do_nothing_but_read(self):
        self.assertEqual(roles.permissions_of(roles.VIEWER), [roles.READ])


class TestSlackCannotBreakSafety(CampaignTest):
    """The guarantee: a failing notification changes nothing about the engine."""

    def exploding_post(self, payload, config=None):
        raise RuntimeError("slack is down")

    def test_a_failed_notification_leaves_the_company_paused(self):
        recs = self.seed_records()
        rec = recs[0]
        rec["paused"] = {"since": "2026-01-01T00:00:00+00:00",
                         "reason": "reply_received"}
        outcome = orchestrator.positive_reply_notification(
            rec, rec["contacts"][0]["key"],
            {"classification": "positive", "excerpt": "sounds good"},
            self.config, post=self.exploding_post)
        self.assertFalse(outcome["delivery"]["sent"])
        self.assertTrue(outcome["paused"])
        self.assertTrue(rec["paused"])

    def test_a_failure_is_recorded_and_stays_retryable(self):
        recs = self.seed_records()
        rec = recs[0]
        outcome = orchestrator.positive_reply_notification(
            rec, rec["contacts"][0]["key"],
            {"classification": "positive", "excerpt": "x"},
            self.config, post=self.exploding_post)
        self.assertTrue(outcome["delivery"]["retryable"])
        kinds = [e["type"] for e in rec["events"]]
        self.assertIn(events.SLACK_NOTIFICATION_FAILED, kinds)

    def test_a_failure_never_propagates_to_the_caller(self):
        recs = self.seed_records()
        result = orchestrator.deliver({"kind": slack.POSITIVE_REPLY,
                                       "channel": "C1"},
                                      self.config, rec=recs[0],
                                      post=self.exploding_post)
        self.assertFalse(result["sent"])

    def test_slack_being_off_does_not_stop_the_pause_being_recorded(self):
        config = clients.load("productive")           # slack disabled
        recs = self.seed_records()
        rec = recs[0]
        rec["paused"] = {"since": "x", "reason": "reply_received"}
        outcome = orchestrator.positive_reply_notification(
            rec, rec["contacts"][0]["key"],
            {"classification": "positive", "excerpt": "x"}, config)
        self.assertFalse(outcome["notification"]["planned"])
        self.assertTrue(outcome["paused"])

    def test_planning_and_sending_are_two_separate_events(self):
        self.assertNotEqual(events.SLACK_NOTIFICATION_PLANNED,
                            events.SLACK_NOTIFICATION_SENT)
        recs = self.seed_records()
        rec = recs[0]
        orchestrator.positive_reply_notification(
            rec, rec["contacts"][0]["key"],
            {"classification": "positive", "excerpt": "x"},
            self.config, post=self.exploding_post)
        kinds = [e["type"] for e in rec["events"]]
        self.assertIn(events.SLACK_NOTIFICATION_PLANNED, kinds)
        self.assertIn(events.SLACK_NOTIFICATION_FAILED, kinds)
        self.assertNotIn(events.SLACK_NOTIFICATION_SENT, kinds)

    def test_an_approval_cannot_override_a_lint_failure(self):
        """The point of the whole layer: Slack approves, safety still decides."""
        campaign, recs, _ = self.approved_campaign()
        recs = store.load()
        for steps in recs[0]["cadence"].values():
            for step in steps.values():
                if step.get("generated"):
                    step["body"] = "Hi {{first_name}}, quick one.\n"   # placeholder
        store.save(recs)
        result = campaigns.validate("camp-1", store.load(), self.config,
                                    campaign=campaign)
        self.assertFalse(result["ok"])


class TestOperationalAlerts(CampaignTest):
    def test_a_quiet_day_raises_nothing(self):
        self.assertEqual(orchestrator.operational_alerts(self.config,
                                                         held_count=0), [])

    def test_a_held_pile_over_the_threshold_raises_one(self):
        alerts = orchestrator.operational_alerts(self.config, held_count=5)
        self.assertEqual([a["kind"] for a in alerts], [slack.LARGE_HELD_COUNT])

    def test_it_goes_to_the_operational_channel(self):
        alerts = orchestrator.operational_alerts(self.config, held_count=5)
        self.assertEqual(alerts[0]["channel"], "C0DEMOALERTS")

    def test_provider_failures_are_thresholded_too(self):
        self.assertEqual(orchestrator.operational_alerts(self.config,
                                                         provider_failures=1), [])
        alerts = orchestrator.operational_alerts(self.config, provider_failures=3)
        self.assertIn(slack.PROVIDER_FAILURE, [a["kind"] for a in alerts])

    def test_a_client_with_slack_off_gets_no_alerts_at_any_volume(self):
        config = clients.load("productive")
        self.assertEqual(orchestrator.operational_alerts(config, held_count=9999),
                         [])


class TestTheDailySummary(CampaignTest):
    def test_it_reports_only_what_is_known(self):
        payload = slack.daily_summary(
            {"date": "2026-08-26", "campaigns_running": 2, "replies": 3,
             "meetings": None}, self.config)
        blob = " ".join(payload["blocks"])
        self.assertIn("campaigns_running: 2", blob)
        self.assertNotIn("meetings", blob)

    def test_it_does_not_invent_a_zero_for_what_is_not_tracked(self):
        payload = slack.daily_summary({"date": "x", "meetings": None},
                                      self.config)
        self.assertNotIn("meetings: 0", " ".join(payload["blocks"]))


if __name__ == "__main__":
    unittest.main()
