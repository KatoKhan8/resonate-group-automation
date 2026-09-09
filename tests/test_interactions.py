"""A forged Slack payload must never approve a campaign.

Everything here attacks the approval path. The happy case is one test; the rest
are attempts to get past it - wrong signature, replayed signature, expired
timestamp, wrong user, stale fingerprint, another client's campaign, the same
click twice. Each must be refused, and refused without being retried.
"""
import json
import time
import unittest
import urllib.parse

from src import campaigns, events, interactions, observability, orchestrator, store
from src.providers import slack
from tests.campaignbase import CampaignTest

SECRET = "synthetic-signing-secret-not-real"
ADMIN = "U0DEMOADMIN1"
STRANGER = "U0STRANGER99"


def payload_body(campaign_id, fingerprint, user=ADMIN,
                 action_id=slack.APPROVE, client="demo", message_ts="1712.0001"):
    """The body Slack posts: `payload=<url-encoded json>`."""
    payload = {
        "type": "block_actions",
        "user": {"id": user},
        "container": {"message_ts": message_ts},
        "actions": [{"action_id": action_id,
                     "value": json.dumps({"campaign_id": campaign_id,
                                          "fingerprint": fingerprint,
                                          "client": client})}],
    }
    return "payload=" + urllib.parse.quote(json.dumps(payload))


class InteractionTest(CampaignTest):
    def setUp(self):
        super().setUp()
        interactions.reset_seen()
        observability.reset()
        self.campaign, self.recs = self.ready_campaign()
        orchestrator.prepare(self.campaign, self.recs, self.config)
        orchestrator.request_approval(self.campaign, self.recs, self.config)
        self.fingerprint = campaigns.fingerprint(self.campaign, self.recs,
                                                 self.config)
        self.save_campaign(self.campaign)
        self.now = int(time.time())

    def send(self, body=None, timestamp=None, signature=None, **kw):
        body = body if body is not None else payload_body(
            self.campaign["campaign_id"], self.fingerprint, **kw)
        timestamp = self.now if timestamp is None else timestamp
        signature = (signature if signature is not None
                     else slack.sign(body, timestamp, SECRET))
        # rows is left to handle(), so it loads and saves in one transaction,
        # exactly as an HTTP handler would.
        result = interactions.handle(body, timestamp, signature, secret=SECRET,
                                     now=self.now, config=self.config,
                                     recs=self.recs)
        return result, campaigns.load()


class TestTheHappyPath(InteractionTest):
    def test_a_properly_signed_approval_from_an_approver_works(self):
        result, rows = self.send()
        self.assertEqual(result["status"], "approved")
        self.assertEqual(campaigns.get(self.campaign["campaign_id"], rows)["status"],
                         campaigns.APPROVED)

    def test_the_approval_records_who_and_which_interaction(self):
        result, rows = self.send()
        given = campaigns.get(self.campaign["campaign_id"], rows)["approval"]
        self.assertEqual(given["by"], ADMIN)
        self.assertEqual(given["interaction_id"], result["interaction_id"])
        self.assertEqual(given["fingerprint"], self.fingerprint)

    def test_a_rejection_works_the_same_way(self):
        result, rows = self.send(action_id=slack.REJECT)
        self.assertEqual(result["status"], "rejected")

    def test_an_action_we_do_not_act_on_is_ignored_not_refused(self):
        result, _ = self.send(action_id=slack.OPEN_REVIEW)
        self.assertEqual(result["status"], "ignored")


class TestForgery(InteractionTest):
    def test_an_unsigned_payload_is_refused(self):
        with self.assertRaises(interactions.Rejected):
            self.send(signature="")

    def test_a_wrong_signature_is_refused(self):
        with self.assertRaises(interactions.Rejected) as e:
            self.send(signature="v0=" + "0" * 64)
        self.assertIn("signature", str(e.exception))

    def test_a_signature_from_another_secret_is_refused(self):
        body = payload_body(self.campaign["campaign_id"], self.fingerprint)
        forged = slack.sign(body, self.now, "the-attackers-own-secret")
        with self.assertRaises(interactions.Rejected):
            self.send(body=body, signature=forged)

    def test_a_tampered_body_is_refused_even_with_a_real_signature(self):
        """Sign an innocent body, then send a different one."""
        honest = payload_body(self.campaign["campaign_id"], self.fingerprint,
                              action_id=slack.OPEN_REVIEW)
        signature = slack.sign(honest, self.now, SECRET)
        evil = payload_body(self.campaign["campaign_id"], self.fingerprint,
                            action_id=slack.APPROVE)
        with self.assertRaises(interactions.Rejected):
            self.send(body=evil, signature=signature)

    def test_a_forged_payload_never_reaches_the_campaign(self):
        try:
            self.send(signature="v0=" + "f" * 64)
        except interactions.Rejected:
            pass
        self.assertIsNone(campaigns.require(self.campaign["campaign_id"])["approval"])

    def test_a_rejection_is_counted_but_the_payload_is_not_stored(self):
        try:
            self.send(signature="v0=" + "f" * 64)
        except interactions.Rejected:
            pass
        self.assertEqual(observability.counts().get(events.WEBHOOK_REJECTED), 1)
        for entry in observability.recent():
            self.assertNotIn("payload=", json.dumps(entry))

    def test_the_body_is_not_parsed_before_the_signature_is_checked(self):
        """A body that would crash the parser must be refused first."""
        with self.assertRaises(interactions.Rejected) as e:
            self.send(body="this is not a form at all", signature="v0=bad")
        self.assertIn("signature", str(e.exception))


class TestReplay(InteractionTest):
    def test_an_expired_timestamp_is_refused(self):
        old = self.now - 10_000
        body = payload_body(self.campaign["campaign_id"], self.fingerprint)
        signature = slack.sign(body, old, SECRET)
        with self.assertRaises(interactions.Rejected) as e:
            self.send(body=body, timestamp=old, signature=signature)
        self.assertIn("old", str(e.exception))

    def test_the_same_click_delivered_twice_changes_state_once(self):
        first, _ = self.send()
        second, rows = self.send()
        self.assertEqual(first["status"], "approved")
        self.assertEqual(second["status"], "duplicate")
        approvals = [e for e in campaigns.get(self.campaign["campaign_id"], rows)["events"]
                     if e["type"] == events.CAMPAIGN_APPROVED]
        self.assertEqual(len(approvals), 1)

    def test_a_replayed_body_within_the_window_is_still_one_decision(self):
        """A valid signature replayed inside five minutes is caught by the
        interaction id, which is derived from the click rather than delivery."""
        body = payload_body(self.campaign["campaign_id"], self.fingerprint)
        signature = slack.sign(body, self.now, SECRET)
        self.send(body=body, signature=signature)
        again, _ = self.send(body=body, signature=signature)
        self.assertEqual(again["status"], "duplicate")

    def test_two_different_clicks_are_two_interactions(self):
        first, _ = self.send(message_ts="1712.0001")
        interactions.reset_seen()          # a fresh process
        self.assertNotEqual(
            first["interaction_id"],
            interactions.interaction_id(json.loads(urllib.parse.unquote(
                payload_body(self.campaign["campaign_id"], self.fingerprint,
                             message_ts="1712.9999").split("=", 1)[1]))))


class TestReplayAfterARestart(InteractionTest):
    """The in-process cache dies with the process. The campaign's own record
    of the interaction id is what actually makes this safe."""

    def test_a_replay_is_still_caught_once_the_cache_is_gone(self):
        first, _ = self.send()
        self.assertEqual(first["status"], "approved")

        interactions.reset_seen()          # as if the process restarted
        second, rows = self.send()
        self.assertEqual(second["status"], "duplicate")
        approvals = [e for e in campaigns.get(self.campaign["campaign_id"], rows)["events"]
                     if e["type"] == events.CAMPAIGN_APPROVED]
        self.assertEqual(len(approvals), 1, "the campaign is the durable record")

    def test_the_durable_check_lives_on_the_campaign_not_in_memory(self):
        first, rows = self.send()
        campaign = campaigns.get(self.campaign["campaign_id"], rows)
        recorded = [e.get("interaction_id") for e in campaign["events"]
                    if e.get("interaction_id")]
        self.assertIn(first["interaction_id"], recorded)


class TestAuthorisation(InteractionTest):
    def test_a_stranger_with_a_perfect_signature_cannot_approve(self):
        with self.assertRaises(slack.NotPermitted):
            self.send(user=STRANGER)
        self.assertIsNone(campaigns.require(self.campaign["campaign_id"])["approval"])

    def test_a_stale_fingerprint_is_refused(self):
        result, _ = self.send(body=payload_body(
            self.campaign["campaign_id"], "a-fingerprint-from-yesterday"))
        self.assertEqual(result["status"], "stale")

    def test_a_campaign_that_changed_since_the_message_is_refused(self):
        orchestrator.set_daily_volume(self.campaign, email=999)
        self.save_campaign(self.campaign)
        result, _ = self.send()
        self.assertEqual(result["status"], "stale")

    def test_a_payload_for_another_client_is_refused(self):
        with self.assertRaises(interactions.Rejected) as e:
            self.send(client="somebody-else")
        self.assertIn("client", str(e.exception))

    def test_a_payload_naming_no_campaign_is_refused(self):
        body = payload_body(None, self.fingerprint)
        with self.assertRaises(interactions.Rejected) as e:
            self.send(body=body)
        self.assertIn("campaign", str(e.exception))

    def test_a_payload_naming_an_unknown_campaign_is_refused(self):
        body = payload_body("no-such-campaign", self.fingerprint)
        with self.assertRaises(interactions.Rejected):
            self.send(body=body)

    def test_the_decision_is_taken_from_metadata_not_the_message_text(self):
        import inspect
        source = inspect.getsource(interactions)
        self.assertIn("metadata_of", source)
        self.assertNotIn('payload.get("text")', source)


class TestTheLocalHarness(InteractionTest):
    """The whole approval loop, signed, with no workspace involved."""

    def test_a_campaign_goes_from_ready_to_launch_ready_over_slack(self):
        request = orchestrator.request_approval(self.campaign, self.recs,
                                                self.config)
        fingerprint = request["summary"]["fingerprint"]
        self.save_campaign(self.campaign)

        body = payload_body(self.campaign["campaign_id"], fingerprint)
        signature = slack.sign(body, self.now, SECRET)
        rows = campaigns.load()
        result = interactions.handle(body, self.now, signature, secret=SECRET,
                                     now=self.now, rows=rows, config=self.config,
                                     recs=self.recs)
        self.assertEqual(result["status"], "approved")

        campaign = campaigns.get(self.campaign["campaign_id"], rows)
        readiness = orchestrator.launch_readiness(campaign, self.recs, self.config)
        self.assertTrue(readiness["ok"], readiness["blockers"])
        self.assertEqual(campaign["status"], campaigns.LAUNCH_READY)

    def test_no_network_was_touched_anywhere_in_that_loop(self):
        self.test_a_campaign_goes_from_ready_to_launch_ready_over_slack()
        self.assertEqual(self.cassette.calls, [])


if __name__ == "__main__":
    unittest.main()
