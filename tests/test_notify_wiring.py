"""The call sites. Not "the router works" but "the router is actually called".

`test_notify.py` proves the routing table. `test_notify_pipeline.py` proves a
positive reply reaches its own workspace's room. Neither would fail if nobody
ever called them, which is the failure mode that matters most for a
notification layer: it is silent, it looks exactly like a quiet week, and it
is discovered by somebody asking why they never heard about a failed job.

So each test here starts from a real engine action - a job aborting, a reply
that matches nothing, a campaign asking for approval - and asserts the row
appeared.

The second property every one of them checks is that the action survived the
notification. `notify.notify` cannot raise, and these are the paths where that
matters: a Slack problem must never be able to unwind a pause, lose a job's
final state, or fail an approval request.
"""
import os
import unittest

from src import events, inbound, jobs, notify, orchestrator, store
from src import workspaces as ws
from tests.campaignbase import CampaignTest

MINE = "productive"
OPS = "#resonate-outbound-ops"


class OpsChannelTest(CampaignTest):

    def setUp(self):
        super().setUp()
        self._prev = os.environ.get(notify.OPS_CHANNEL_VAR)
        os.environ[notify.OPS_CHANNEL_VAR] = OPS
        ws.ensure(MINE, "Productive", client=MINE)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(notify.OPS_CHANNEL_VAR, None)
        else:
            os.environ[notify.OPS_CHANNEL_VAR] = self._prev
        super().tearDown()

    def rows_of(self, event_type):
        return [r for r in notify.load() if r["type"] == event_type]


class AFailedJobIsAnnounced(OpsChannelTest):

    def failing_job(self, count=30, batch="b1"):
        items = [f"r{i}" for i in range(count)]
        job = jobs.new("qa", MINE, batch=batch, total=count)

        def blow_up(item):
            raise RuntimeError("the provider is down")

        return jobs.run_step(job, items, blow_up)

    def test_an_aborted_job_reaches_the_operations_channel(self):
        job = self.failing_job()
        self.assertEqual(job["status"], jobs.FAILED)
        rows = self.rows_of(notify.FAILED_JOB)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], OPS)
        self.assertEqual(rows[0]["destination"], notify.GLOBAL)

    def test_it_never_reaches_the_clients_channel(self):
        ws.set_policy(MINE, {notify.WORKSPACE_CHANNEL_KEY: "#client-room"},
                      actor="test")
        self.failing_job()
        rows = self.rows_of(notify.FAILED_JOB)
        self.assertNotEqual(rows[0]["channel"], "#client-room")

    def test_the_alert_says_what_broke_without_a_stack_trace(self):
        self.failing_job()
        payload = self.rows_of(notify.FAILED_JOB)[0]["payload"]
        self.assertIn("job_type", payload)
        self.assertIn("failed", payload)
        self.assertIn("error", payload)

    def test_the_job_still_ended_failed_even_with_no_channel(self):
        """A notification layer cannot be allowed to lose a job's outcome."""
        os.environ.pop(notify.OPS_CHANNEL_VAR, None)
        job = self.failing_job()
        self.assertEqual(job["status"], jobs.FAILED)
        self.assertEqual(self.rows_of(notify.FAILED_JOB)[0]["status"],
                         notify.UNCONFIGURED)

    def test_a_job_that_finished_is_not_announced(self):
        job = jobs.new("qa", MINE, batch="b2", total=2)
        jobs.run_step(job, ["a", "b"], lambda item: "ok")
        self.assertNotEqual(job["status"], jobs.FAILED)
        self.assertEqual(self.rows_of(notify.FAILED_JOB), [])


class AnUnmatchedReplyIsAnnounced(OpsChannelTest):

    def event(self, record_id="nobody"):
        return {"type": events.REPLY_RECEIVED, "record_id": record_id,
                "contact_key": "k", "provider": "emailbison",
                "provider_event_id": "bison-unmatched-1",
                "channel": "email", "text": "who is this?"}

    def test_a_reply_for_no_record_reaches_the_operations_channel(self):
        outcome = inbound.handle(self.event(), [])
        self.assertEqual(outcome["applied"]["status"], "unmatched")
        rows = self.rows_of(notify.UNMATCHED_REPLY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], OPS)

    def test_the_alert_does_not_carry_the_prospects_words(self):
        """Nobody can say whose words these are, so they go to nobody."""
        inbound.handle(self.event(), [])
        payload = self.rows_of(notify.UNMATCHED_REPLY)[0]["payload"]
        self.assertNotIn("who is this?", str(payload))

    def test_it_is_idempotent_on_the_providers_own_event_id(self):
        inbound.handle(self.event(), [])
        inbound.handle(self.event(), [])
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    def test_an_unknown_event_type_is_announced_too(self):
        event = dict(self.event(), type="something_nobody_defined",
                     provider_event_id="bison-unknown-1")
        outcome = inbound.handle(event, [])
        self.assertEqual(outcome["applied"]["status"], "unknown")
        self.assertEqual(len(self.rows_of(notify.UNMATCHED_REPLY)), 1)

    def test_nothing_is_announced_when_the_event_matched(self):
        rec = store.new_record("acme", "domains", MINE, "Acme", "acme.test")
        rec["contacts"] = [{"key": "k", "name": "A", "email": "a@acme.test",
                            "selected": True}]
        store.save([rec])
        inbound.handle(dict(self.event(record_id="acme"),
                            provider_event_id="bison-matched-1"), [rec])
        self.assertEqual(self.rows_of(notify.UNMATCHED_REPLY), [])


class AnApprovalRequestReachesTheOperationsChannel(OpsChannelTest):

    def campaign(self):
        from src import campaigns as campaign_store

        rec = store.new_record("acme", "domains", MINE, "Acme", "acme.test")
        rec["contacts"] = [{"key": "k", "name": "A", "title": "COO",
                            "email": "a@acme.test", "selected": True,
                            "verification": {"status": "valid"}}]
        store.save([rec])
        campaign = campaign_store.new_campaign("c1", MINE, "C1")
        campaign["record_ids"] = ["acme"]
        campaign["status"] = campaign_store.READY_FOR_REVIEW
        return campaign, [rec]

    def test_it_is_planned_on_the_same_path_that_builds_the_request(self):
        campaign, recs = self.campaign()
        result = orchestrator.request_approval(campaign, recs, self.config)
        self.assertIsNotNone(result["routed"])
        self.assertEqual(result["routed"]["channel"], OPS)
        self.assertEqual(result["routed"]["destination"], notify.GLOBAL)

    def test_it_carries_the_fingerprint_the_decision_is_bound_to(self):
        campaign, recs = self.campaign()
        result = orchestrator.request_approval(campaign, recs, self.config)
        self.assertEqual(result["routed"]["ids"]["fingerprint"],
                         result["summary"]["fingerprint"])

    def test_the_same_request_twice_is_one_notification(self):
        campaign, recs = self.campaign()
        orchestrator.request_approval(campaign, recs, self.config)
        orchestrator.request_approval(campaign, recs, self.config)
        self.assertEqual(
            len(self.rows_of(notify.CAMPAIGN_APPROVAL_REQUIRED)), 1)

    def test_a_changed_campaign_is_a_different_notification(self):
        """The fingerprint is in the id, so a re-approval is a new ask."""
        campaign, recs = self.campaign()
        first = orchestrator.request_approval(campaign, recs, self.config)
        recs[0]["contacts"].append({"key": "k2", "name": "B", "title": "CFO",
                                    "email": "b@acme.test", "selected": True,
                                    "verification": {"status": "valid"}})
        store.save(recs)
        second = orchestrator.request_approval(campaign, recs, self.config)
        self.assertNotEqual(first["summary"]["fingerprint"],
                            second["summary"]["fingerprint"])
        self.assertNotEqual(first["routed"]["id"], second["routed"]["id"])

    def test_the_request_still_succeeds_with_no_operations_channel(self):
        os.environ.pop(notify.OPS_CHANNEL_VAR, None)
        campaign, recs = self.campaign()
        result = orchestrator.request_approval(campaign, recs, self.config)
        self.assertIn("summary", result)
        self.assertEqual(result["routed"]["status"], notify.UNCONFIGURED)

    def test_the_client_channel_is_never_the_destination(self):
        ws.set_policy(MINE, {notify.WORKSPACE_CHANNEL_KEY: "#client-room"},
                      actor="test")
        campaign, recs = self.campaign()
        result = orchestrator.request_approval(campaign, recs, self.config)
        self.assertNotEqual(result["routed"]["channel"], "#client-room")


class OneRouterNotTwo(OpsChannelTest):
    """The client config must not be able to name a different room.

    Before the workspace mapping existed, a positive reply's channel came from
    `slack.positive_replies_channel` in the client YAML. Both mechanisms
    resolving a channel is two routers with two answers, and the one that
    wins is whichever caller was written last.
    """

    def config_with_channel(self, channel):
        config = dict(self.config)
        config["slack"] = dict(config.get("slack") or {},
                               enabled=True,
                               positive_replies_channel=channel,
                               notify={"positive_reply": True})
        return config

    def record(self):
        rec = store.new_record("acme", "domains", MINE, "Acme", "acme.test")
        rec["contacts"] = [{"key": "k", "name": "Sarah", "title": "COO",
                            "email": "s@acme.test", "selected": True}]
        store.save([rec])
        return rec

    def test_the_workspace_mapping_wins(self):
        ws.set_policy(MINE, {notify.WORKSPACE_CHANNEL_KEY: "#workspace-room"},
                      actor="test")
        result = orchestrator.positive_reply_notification(
            self.record(), "k", {"classification": "positive",
                                 "excerpt": "yes please"},
            self.config_with_channel("#config-room"))
        self.assertEqual(result["payload"]["channel"], "#workspace-room")

    def test_an_unmapped_workspace_does_not_fall_back_to_the_config(self):
        """The absence of a fallback is the property, so it is asserted."""
        result = orchestrator.positive_reply_notification(
            self.record(), "k", {"classification": "positive",
                                 "excerpt": "yes please"},
            self.config_with_channel("#config-room"))
        self.assertIsNone(result["payload"]["channel"])
        self.assertFalse(result["notification"]["planned"])
        self.assertIn("no Slack channel", result["notification"]["why"])

    def test_the_pause_is_untouched_either_way(self):
        rec = self.record()
        rec["paused"] = {"since": store.now(), "reason": "reply_received"}
        result = orchestrator.positive_reply_notification(
            rec, "k", {"classification": "positive", "excerpt": "yes"},
            self.config_with_channel("#config-room"))
        self.assertTrue(result["paused"])
        self.assertTrue(rec["paused"])


class NothingIsPosted(OpsChannelTest):

    def test_slack_is_not_live(self):
        from src.providers import slack

        self.assertFalse(slack.live())

    def test_every_row_this_module_created_is_planned(self):
        job = jobs.new("qa", MINE, batch="b", total=1)
        jobs.run_step(job, ["a"], lambda item: "ok")
        inbound.handle({"type": events.REPLY_RECEIVED, "record_id": "nobody",
                        "provider_event_id": "x"}, [])
        for row in notify.load():
            self.assertIn(row["status"],
                          (notify.PLANNED, notify.UNCONFIGURED,
                           notify.SUPPRESSED))


if __name__ == "__main__":
    unittest.main()
