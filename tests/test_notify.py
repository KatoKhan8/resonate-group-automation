"""Where a notification goes, and the one place it must never go.

Two destinations exist and mixing them is the failure this module was written
to prevent. Putting internal diagnostics in a client's channel is a bad day;
putting ContactOut's prospect in Productive's channel is the kind that ends an
account. So most of this file is about the second kind.

The other half is about Slack not mattering. A reply pauses a company before
anything is routed, and if the transport then fails the pause has to stand -
a notification layer that can unwind business state is not a notification
layer.
"""
import os
import unittest

from src import notify, store, workspaces as ws
from tests.campaignbase import CampaignTest

MINE = "productive"
THEIRS = "contactout"
OPS = "#resonate-outbound-ops"


class RoutingIsATable(CampaignTest):

    def test_every_event_type_has_a_destination_and_a_severity(self):
        for event_type in notify.EVENT_TYPES:
            where, severity = notify.route(event_type)
            self.assertIn(where, notify.DESTINATIONS, event_type)
            self.assertIn(severity, notify.SEVERITIES, event_type)

    def test_an_unknown_type_goes_nowhere_rather_than_to_the_ops_channel(self):
        """A layer whose default is "tell everybody" becomes noise, and noise
        gets muted, and a muted channel is worse than none."""
        where, _ = notify.route("something_nobody_defined")
        self.assertEqual(where, notify.NOWHERE)

    def test_only_three_kinds_reach_a_client_channel(self):
        workspace_bound = {t for t, (d, _) in notify.ROUTES.items()
                           if d == notify.WORKSPACE}
        self.assertEqual(workspace_bound,
                         {notify.POSITIVE_REPLY, notify.CAMPAIGN_MILESTONE,
                          notify.REPORT_AVAILABLE})

    def test_approvals_and_operations_go_to_the_global_channel(self):
        for event_type in (notify.CAMPAIGN_APPROVAL_REQUIRED,
                           notify.CAMPAIGN_QA_FAILED, notify.FAILED_JOB,
                           notify.PROVIDER_HEALTH_ISSUE,
                           notify.UNMATCHED_REPLY):
            self.assertEqual(notify.route(event_type)[0], notify.GLOBAL,
                             event_type)

    def test_neutral_and_negative_replies_are_explicitly_nowhere(self):
        """Explicit rather than absent, so a reader can see it was decided."""
        for event_type in (notify.NEUTRAL_REPLY, notify.NEGATIVE_REPLY,
                           notify.UNSUBSCRIBE):
            self.assertIn(event_type, notify.ROUTES)
            self.assertEqual(notify.route(event_type)[0], notify.NOWHERE)

    def test_a_provider_health_issue_is_critical(self):
        self.assertEqual(notify.route(notify.PROVIDER_HEALTH_ISSUE)[1],
                         notify.CRITICAL)


class NothingFallsBackToAnotherWorkspace(CampaignTest):
    """The property the whole module exists for."""

    def setUp(self):
        super().setUp()
        ws.ensure(MINE, "Productive", client=MINE)
        ws.ensure(THEIRS, "ContactOut", client=THEIRS)
        ws.set_policy(MINE, {"slack.workspace_channel": "#client-productive"},
                      actor="test")
        # ContactOut deliberately has no channel.

    def test_a_configured_workspace_routes_to_its_own_channel(self):
        decision = notify.destination_for(notify.POSITIVE_REPLY, MINE)
        self.assertEqual(decision["channel"], "#client-productive")
        self.assertEqual(decision["status"], notify.PLANNED)

    def test_an_unconfigured_workspace_routes_nowhere_at_all(self):
        decision = notify.destination_for(notify.POSITIVE_REPLY, THEIRS)
        self.assertIsNone(decision["channel"])
        self.assertEqual(decision["status"], notify.UNCONFIGURED)
        self.assertIn("never a fallback", decision["why"])

    def test_an_unconfigured_workspace_never_gets_the_other_ones_channel(self):
        decision = notify.destination_for(notify.POSITIVE_REPLY, THEIRS)
        self.assertNotEqual(decision["channel"], "#client-productive")

    def test_the_channel_lookup_reads_one_workspace_and_no_other(self):
        self.assertEqual(notify.workspace_channel(MINE), "#client-productive")
        self.assertIsNone(notify.workspace_channel(THEIRS))
        self.assertIsNone(notify.workspace_channel("a-workspace-that-is-not"))
        self.assertIsNone(notify.workspace_channel(None))

    def test_a_forged_workspace_slug_cannot_redirect_a_notification(self):
        for forged in ("../productive", "productive ", "PRODUCTIVE",
                       "productive\n", "'productive'"):
            self.assertIsNone(notify.workspace_channel(forged), forged)

    def test_a_workspace_event_with_no_workspace_goes_nowhere(self):
        decision = notify.destination_for(notify.POSITIVE_REPLY, None)
        self.assertIsNone(decision["channel"])
        self.assertEqual(decision["status"], notify.UNCONFIGURED)

    def test_two_workspaces_with_channels_stay_separate(self):
        ws.set_policy(THEIRS, {"slack.workspace_channel": "#client-contactout"},
                      actor="test")
        self.assertEqual(
            notify.destination_for(notify.POSITIVE_REPLY, MINE)["channel"],
            "#client-productive")
        self.assertEqual(
            notify.destination_for(notify.POSITIVE_REPLY, THEIRS)["channel"],
            "#client-contactout")


class TheGlobalChannel(CampaignTest):

    def setUp(self):
        super().setUp()
        self._prev = os.environ.get(notify.OPS_CHANNEL_VAR)
        os.environ[notify.OPS_CHANNEL_VAR] = OPS

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(notify.OPS_CHANNEL_VAR, None)
        else:
            os.environ[notify.OPS_CHANNEL_VAR] = self._prev
        super().tearDown()

    def test_operational_events_route_to_it(self):
        decision = notify.destination_for(notify.FAILED_JOB, MINE)
        self.assertEqual(decision["destination"], notify.GLOBAL)
        self.assertEqual(decision["channel"], OPS)

    def test_it_is_the_same_channel_whichever_workspace_the_event_names(self):
        first = notify.destination_for(notify.CAMPAIGN_QA_FAILED, MINE)
        second = notify.destination_for(notify.CAMPAIGN_QA_FAILED, THEIRS)
        self.assertEqual(first["channel"], second["channel"])

    def test_with_none_configured_it_is_unconfigured_not_a_guess(self):
        os.environ.pop(notify.OPS_CHANNEL_VAR, None)
        decision = notify.destination_for(notify.FAILED_JOB, MINE)
        self.assertIsNone(decision["channel"])
        self.assertEqual(decision["status"], notify.UNCONFIGURED)

    def test_a_global_event_never_lands_in_a_client_channel(self):
        ws.ensure(MINE, "Productive", client=MINE)
        ws.set_policy(MINE, {"slack.workspace_channel": "#client-productive"},
                      actor="test")
        for event_type in (notify.CAMPAIGN_APPROVAL_REQUIRED,
                           notify.PROVIDER_HEALTH_ISSUE,
                           notify.UNMATCHED_REPLY, notify.FAILED_JOB):
            decision = notify.destination_for(event_type, MINE)
            self.assertNotEqual(decision["channel"], "#client-productive",
                                event_type)


class WorkspaceMessagesAreClientSafe(CampaignTest):

    def setUp(self):
        super().setUp()
        ws.ensure(MINE, "Productive", client=MINE)
        ws.set_policy(MINE, {"slack.workspace_channel": "#client-productive"},
                      actor="test")

    def plan_positive(self, **fields):
        return notify.plan(notify.POSITIVE_REPLY, MINE, fields=fields,
                           ids={"record_id": "acme", "contact_key": "k"})

    def test_the_payload_is_an_allowlist(self):
        """A field added upstream cannot appear in a client's channel."""
        row = self.plan_positive(
            company="Example Agency", contact_name="Sarah Smith",
            # None of these are on the list.
            internal_qa_note="lint failed twice",
            raw_provider_payload={"folder": "Sent"},
            mx_provider="proofpoint", other_workspace="contactout",
            credit_cost=42)
        self.assertEqual(set(row["payload"]),
                         {"company", "contact_name"})

    def test_a_credential_shaped_field_is_refused_rather_than_stripped(self):
        """Stripping would mean nobody found out somebody put one there."""
        with self.assertRaises(notify.NotifyError):
            notify.plan(notify.POSITIVE_REPLY, MINE,
                        fields={"company": "X", "api_key": "abc123"},
                        ids={"record_id": "r"})

    def test_a_credential_is_refused_on_the_global_side_too(self):
        os.environ[notify.OPS_CHANNEL_VAR] = OPS
        try:
            with self.assertRaises(notify.NotifyError):
                notify.plan(notify.FAILED_JOB, MINE,
                            fields={"job": "j1", "bearer": "xyz"},
                            ids={"job_id": "j1"})
        finally:
            os.environ.pop(notify.OPS_CHANNEL_VAR, None)

    def test_the_rendered_text_carries_no_forbidden_word(self):
        row = self.plan_positive(company="Example Agency",
                                 reply_excerpt="Sounds interesting.")
        text = notify.render(row).lower()
        for word in notify.FORBIDDEN:
            self.assertNotIn(word, text)

    def test_the_global_payload_may_carry_operational_detail(self):
        os.environ[notify.OPS_CHANNEL_VAR] = OPS
        try:
            row = notify.plan(notify.PROVIDER_HEALTH_ISSUE, MINE,
                              fields={"provider": "reoon",
                                      "consecutive_failures": 4},
                              ids={"provider": "reoon"})
            self.assertEqual(row["payload"]["provider"], "reoon")
            self.assertEqual(row["payload"]["consecutive_failures"], 4)
        finally:
            os.environ.pop(notify.OPS_CHANNEL_VAR, None)


class PerWorkspaceToggles(CampaignTest):

    def setUp(self):
        super().setUp()
        ws.ensure(MINE, "Productive", client=MINE)
        ws.set_policy(MINE, {"slack.workspace_channel": "#client-productive"},
                      actor="test")

    def test_positive_replies_are_on_by_default(self):
        allowed, why = notify.workspace_allows(MINE, notify.POSITIVE_REPLY)
        self.assertTrue(allowed)
        self.assertIn("default is on", why)

    def test_milestones_and_reports_are_off_by_default(self):
        for event_type in (notify.CAMPAIGN_MILESTONE, notify.REPORT_AVAILABLE):
            allowed, _ = notify.workspace_allows(MINE, event_type)
            self.assertFalse(allowed, event_type)

    def test_turning_positive_replies_off_suppresses_rather_than_sends(self):
        ws.set_policy(MINE, {"slack.notify_positive_replies": "off"},
                      actor="test")
        decision = notify.destination_for(notify.POSITIVE_REPLY, MINE)
        self.assertEqual(decision["status"], notify.SUPPRESSED)
        self.assertIsNone(decision["channel"])

    def test_a_suppressed_notification_is_still_recorded(self):
        ws.set_policy(MINE, {"slack.notify_positive_replies": "off"},
                      actor="test")
        row = notify.plan(notify.POSITIVE_REPLY, MINE,
                          fields={"company": "X"}, ids={"record_id": "r"})
        self.assertEqual(row["status"], notify.SUPPRESSED)
        self.assertTrue(notify.get(row["id"]))


class Idempotency(CampaignTest):

    def setUp(self):
        super().setUp()
        ws.ensure(MINE, "Productive", client=MINE)
        ws.set_policy(MINE, {"slack.workspace_channel": "#client-productive"},
                      actor="test")

    def test_the_same_reply_twice_is_one_notification(self):
        ids = {"record_id": "acme", "contact_key": "k",
               "provider_event_id": "bison-99"}
        first = notify.plan(notify.POSITIVE_REPLY, MINE,
                            fields={"company": "Acme"}, ids=ids)
        second = notify.plan(notify.POSITIVE_REPLY, MINE,
                             fields={"company": "Acme"}, ids=ids)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(notify.load()), 1)

    def test_a_replayed_poller_page_produces_nothing_new(self):
        ids = {"record_id": "acme", "contact_key": "k",
               "provider_event_id": "hr-42"}
        for _ in range(5):
            notify.plan(notify.POSITIVE_REPLY, MINE,
                        fields={"company": "Acme"}, ids=ids)
        self.assertEqual(len(notify.load()), 1)

    def test_two_different_replies_are_two_notifications(self):
        for event_id in ("bison-1", "bison-2"):
            notify.plan(notify.POSITIVE_REPLY, MINE,
                        fields={"company": "Acme"},
                        ids={"record_id": "acme", "contact_key": "k",
                             "provider_event_id": event_id})
        self.assertEqual(len(notify.load()), 2)

    def test_the_same_approval_twice_is_one_notification(self):
        os.environ[notify.OPS_CHANNEL_VAR] = OPS
        try:
            ids = {"campaign_id": "uk-digital", "fingerprint": "abc123"}
            notify.plan(notify.CAMPAIGN_APPROVAL_REQUIRED, MINE, ids=ids)
            notify.plan(notify.CAMPAIGN_APPROVAL_REQUIRED, MINE, ids=ids)
            self.assertEqual(len(notify.load()), 1)
        finally:
            os.environ.pop(notify.OPS_CHANNEL_VAR, None)

    def test_the_id_is_stable_across_processes(self):
        """Built from the facts, not from a clock or a counter."""
        first = notify.notification_id(notify.POSITIVE_REPLY, MINE,
                                       record_id="r", contact_key="k")
        second = notify.notification_id(notify.POSITIVE_REPLY, MINE,
                                        contact_key="k", record_id="r")
        self.assertEqual(first, second)

    def test_the_same_reply_in_two_workspaces_is_two_notifications(self):
        """A workspace is part of the identity, so one cannot mask the other."""
        first = notify.notification_id(notify.POSITIVE_REPLY, MINE,
                                       provider_event_id="x")
        second = notify.notification_id(notify.POSITIVE_REPLY, THEIRS,
                                        provider_event_id="x")
        self.assertNotEqual(first, second)


class SlackFailureChangesNothing(CampaignTest):

    def setUp(self):
        super().setUp()
        ws.ensure(MINE, "Productive", client=MINE)
        ws.set_policy(MINE, {"slack.workspace_channel": "#client-productive"},
                      actor="test")

    def paused_record(self):
        rec = store.new_record("acme", "domains", MINE, "Acme", "acme.test")
        rec["contacts"] = [{"key": "k", "name": "Sarah", "selected": True,
                            "email": "s@acme.test"}]
        rec["paused"] = {"since": "now", "reason": "reply_received"}
        rec["suppression"] = {"unsubscribed": False}
        store.save([rec])
        return rec

    def test_a_transport_refusal_leaves_the_pause_alone(self):
        rec = self.paused_record()
        row = notify.plan(notify.POSITIVE_REPLY, MINE,
                          fields={"company": "Acme"},
                          ids={"record_id": "acme", "contact_key": "k"})
        notify.deliver(row["id"])

        after = store.get("acme")
        self.assertTrue(after["paused"], "a Slack failure unpaused a company")
        self.assertEqual(after["paused"]["reason"], "reply_received")

    def test_the_refusal_is_recorded_and_stays_retryable(self):
        self.paused_record()
        row = notify.plan(notify.POSITIVE_REPLY, MINE,
                          fields={"company": "Acme"},
                          ids={"record_id": "acme"})
        delivered = notify.deliver(row["id"])
        self.assertEqual(delivered["status"], notify.FAILED)
        self.assertEqual(delivered["attempts"], 1)
        self.assertTrue(delivered["last_error"])
        self.assertIn("retryable", delivered["why"])

    def test_a_retry_does_not_duplicate(self):
        self.paused_record()
        row = notify.plan(notify.POSITIVE_REPLY, MINE,
                          fields={"company": "Acme"},
                          ids={"record_id": "acme"})
        notify.deliver(row["id"])
        notify.retry(row["id"])
        notify.retry(row["id"])
        self.assertEqual(len(notify.load()), 1)
        self.assertEqual(notify.get(row["id"])["attempts"], 3)

    def test_notify_never_raises_into_a_caller(self):
        """The contract: this layer cannot break the engine."""
        row = notify.notify(notify.POSITIVE_REPLY, MINE,
                            fields={"company": "X", "api_key": "leak"},
                            ids={"record_id": "r"})
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], notify.FAILED)
        self.assertIn("could not be built", row["why"])

    def test_a_failure_to_build_carries_no_payload(self):
        row = notify.notify(notify.POSITIVE_REPLY, MINE,
                            fields={"company": "X", "bearer": "leak"},
                            ids={"record_id": "r2"})
        self.assertEqual(row["payload"], {})
        self.assertNotIn("leak", str(row))


class NothingIsPosted(CampaignTest):

    def test_slack_posting_is_off_in_this_build(self):
        from src.providers import slack
        self.assertFalse(slack.live())

    def test_delivery_can_never_reach_sent_here(self):
        ws.ensure(MINE, "Productive", client=MINE)
        ws.set_policy(MINE, {"slack.workspace_channel": "#c"}, actor="test")
        row = notify.plan(notify.POSITIVE_REPLY, MINE,
                          fields={"company": "Acme"}, ids={"record_id": "r"})
        self.assertEqual(notify.deliver(row["id"])["status"], notify.FAILED)
        self.assertNotEqual(notify.get(row["id"])["status"], notify.SENT)


if __name__ == "__main__":
    unittest.main()


class AProspectsOwnWordsAreNotAKeywordScan(CampaignTest):
    """The trap the scrub avoids.

    The obvious implementation greps the whole serialised payload for
    credential words. `reply_excerpt` is text a prospect wrote, so a prospect
    who mentions authorization, tokens or passwords would have their positive
    reply silently refused - a filter that fails on exactly the message you
    most wanted to receive.
    """

    def setUp(self):
        super().setUp()
        ws.ensure(MINE, "Productive", client=MINE)
        ws.set_policy(MINE, {"slack.workspace_channel": "#client-productive"},
                      actor="test")

    def test_a_reply_mentioning_a_credential_word_still_gets_through(self):
        for excerpt in (
                "we would need to sort out authorization first",
                "our SSO token expires monthly, is that a problem?",
                "send me the password reset flow and I will take a look",
                "happy to chat - who handles your api_key rotation?"):
            row = notify.plan(
                notify.POSITIVE_REPLY, MINE,
                fields={"company": "Acme", "reply_excerpt": excerpt},
                ids={"record_id": "acme", "excerpt": excerpt})
            self.assertEqual(row["status"], notify.PLANNED, excerpt)
            self.assertEqual(row["payload"]["reply_excerpt"], excerpt)

    def test_a_field_named_like_a_credential_is_still_refused(self):
        with self.assertRaises(notify.NotifyError):
            notify.plan(notify.POSITIVE_REPLY, MINE,
                        fields={"company": "Acme", "slack_bot_token": "x"},
                        ids={"record_id": "r"})

    def test_a_nested_credential_field_is_refused_too(self):
        with self.assertRaises(notify.NotifyError):
            notify.plan(notify.POSITIVE_REPLY, MINE,
                        fields={"company": "Acme",
                                "detail": {"inner": {"api_key": "x"}}},
                        ids={"record_id": "r2"})

    def test_a_deeply_nested_structure_does_not_hang(self):
        deep = {"a": 1}
        for _ in range(50):
            deep = {"nested": deep}
        row = notify.plan(notify.POSITIVE_REPLY, MINE,
                          fields={"company": "Acme", "detail": deep},
                          ids={"record_id": "r3"})
        self.assertEqual(row["status"], notify.PLANNED)
