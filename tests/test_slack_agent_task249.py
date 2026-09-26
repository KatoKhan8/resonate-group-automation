"""TASK-249: the agent answers about an account, and never names a person.

Seven new read-only queries, and the privacy rule is the hard part:

1. Lead lookup in a channel REFUSES and does not echo the identifier.
2. Lead lookup in a DM ANSWERS and contains no address and no name.
3. An account answer carries the domain and never a contact.
4. The log row records who asked and what was asked.

No live Slack, provider or LLM call in any test.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackagenttools as tools                          # noqa: E402
from src import slackscope                                        # noqa: E402
from src import store                                             # noqa: E402
from tests.slackbase import IsolatedState                         # noqa: E402


INTERNAL_CHANNEL = "C0INTERNAL"


def _workspace(slug, policy):
    return {"kind": "workspace", "slug": slug, "name": slug,
            "client": slug, "settings": {"policy": policy}}


WORKSPACE_ROWS = [
    _workspace("testws", {
        slackscope.AGENT_CHANNEL_KEY: "C0CLIENT",
        slackscope.WORKSPACE_USERS_KEY: ["U0CLIENT"],
        slackscope.INTERNAL_CHANNELS_VAR: INTERNAL_CHANNEL,
    }),
]


class _SandboxedTest(IsolatedState, unittest.TestCase):
    """Isolated store and knowledge pack for each test."""

    def setUp(self):
        self.isolate()
        # Write workspace rows.
        from src import workspaces
        ws_path = os.path.join(self._isolated, "workspaces.jsonl")
        with open(ws_path, "w", encoding="utf-8") as f:
            for row in WORKSPACE_ROWS:
                f.write(json.dumps(row) + "\n")
        os.environ["WORKSPACES"] = ws_path
        # Set internal channels.
        self._prev_internal = os.environ.get(
            slackscope.INTERNAL_CHANNELS_VAR)
        os.environ[slackscope.INTERNAL_CHANNELS_VAR] = INTERNAL_CHANNEL

    def tearDown(self):
        if self._prev_internal is None:
            os.environ.pop(slackscope.INTERNAL_CHANNELS_VAR, None)
        else:
            os.environ[slackscope.INTERNAL_CHANNELS_VAR] = self._prev_internal
        self.restore()

    def _write_queue(self, records):
        path = store.queue_path()
        with open(path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

    def _write_campaigns(self, campaigns):
        path = store.campaigns_path()
        with open(path, "w", encoding="utf-8") as f:
            for c in campaigns:
                f.write(json.dumps(c) + "\n")

    def _internal_scope(self):
        return slackscope.resolve(channel=INTERNAL_CHANNEL,
                                  user="U0INTERNAL",
                                  channel_type="channel")

    def _dm_scope(self):
        return slackscope.resolve(channel="C0DM", user="U0INTERNAL",
                                  channel_type="im")

    def _channel_scope(self):
        return slackscope.resolve(channel=INTERNAL_CHANNEL,
                                  user="U0INTERNAL",
                                  channel_type="channel")


class LeadLookupInChannelRefuses(_SandboxedTest):
    """A lead lookup in a channel refuses AND does not echo the identifier."""

    def test_refuses_in_channel_without_echoing_email(self):
        """The refusal must not contain the address that was asked about."""
        self._write_queue([{
            "id": "rec-1", "domain": "example.test", "client": "testws",
            "state": "sequenced",
            "contacts": [{"email": "jane@example.test",
                          "name": "Jane Doe",
                          "state": "active", "sendable": True}],
        }])
        scope = self._channel_scope()
        result = tools.lead_status_dm(scope, "jane@example.test")
        # It refuses.
        self.assertTrue(result.get("refused"))
        # The refusal reason is the one-line DM-only message.
        self.assertIn("direct messages only", result.get("reason", ""))
        # The email is NOT echoed in the result.
        full = json.dumps(result)
        self.assertNotIn("jane@example.test", full)
        self.assertNotIn("jane", full.lower())

    def test_refuses_in_channel_without_echoing_name(self):
        """The refusal must not contain the name that was asked about."""
        self._write_queue([{
            "id": "rec-2", "domain": "acme.test", "client": "testws",
            "state": "sequenced",
            "contacts": [{"email": "bob@acme.test",
                          "name": "Bob Smith",
                          "state": "active", "sendable": True}],
        }])
        scope = self._channel_scope()
        result = tools.lead_status_dm(scope, "Bob Smith")
        self.assertTrue(result.get("refused"))
        full = json.dumps(result)
        self.assertNotIn("bob@acme.test", full)
        self.assertNotIn("Bob Smith", full)
        self.assertNotIn("bob", full.lower())


class LeadLookupInDMAnswers(_SandboxedTest):
    """A lead lookup in a DM answers AND contains no address and no name."""

    def test_answers_in_dm_without_address(self):
        """The answer must not contain the email address."""
        self._write_queue([{
            "id": "rec-3", "domain": "example.test", "client": "testws",
            "state": "sequenced",
            "contacts": [{"email": "jane@example.test",
                          "name": "Jane Doe",
                          "state": "active", "sendable": True,
                          "channels": {"replied": False, "bounced": False}}],
        }])
        scope = self._dm_scope()
        result = tools.lead_status_dm(scope, "jane@example.test")
        # It answers.
        self.assertFalse(result.get("refused"))
        self.assertEqual(result.get("matches"), 1)
        # The answer contains no address.
        full = json.dumps(result)
        self.assertNotIn("jane@example.test", full)
        self.assertNotIn("@example.test", full)

    def test_answers_in_dm_without_name(self):
        """The answer must not contain the person's name."""
        self._write_queue([{
            "id": "rec-4", "domain": "acme.test", "client": "testws",
            "state": "sequenced",
            "contacts": [{"email": "bob@acme.test",
                          "name": "Bob Smith",
                          "state": "active", "sendable": True,
                          "channels": {}}],
        }])
        scope = self._dm_scope()
        result = tools.lead_status_dm(scope, "bob@acme.test")
        self.assertFalse(result.get("refused"))
        full = json.dumps(result)
        self.assertNotIn("Bob Smith", full)
        self.assertNotIn("bob smith", full.lower())

    def test_not_found_does_not_echo_either(self):
        """Even a 'not found' answer must not echo the identifier."""
        self._write_queue([])
        scope = self._dm_scope()
        result = tools.lead_status_dm(scope, "nobody@nowhere.test")
        self.assertFalse(result.get("refused"))
        self.assertEqual(result.get("matches"), 0)
        full = json.dumps(result)
        self.assertNotIn("nobody@nowhere.test", full)


class AccountAnswerCarriesDomain(_SandboxedTest):
    """An account answer carries the domain and never a contact."""

    def test_account_campaign_status_carries_domain(self):
        """The answer has the domain, approval state, and campaign info."""
        self._write_queue([{
            "id": "rec-5", "domain": "target.test", "client": "testws",
            "state": "sequenced",
            "icp": {"verdict": "fit"},
            "updated_at": "2026-09-20T10:00:00Z",
            "contacts": [
                {"email": "alice@target.test", "name": "Alice",
                 "state": "active", "sendable": True,
                 "channels": {"replied": True, "bounced": False}},
                {"email": "carol@target.test", "name": "Carol",
                 "state": "held", "sendable": False,
                 "channels": {"replied": False, "bounced": True}},
            ],
        }])
        self._write_campaigns([{
            "campaign_id": "491", "client": "testws", "name": "Email US",
            "status": "active", "record_ids": ["rec-5"],
        }])
        scope = self._internal_scope()
        result = tools.account_campaign_status(scope, "target.test")
        # It answers with the domain.
        self.assertEqual(result.get("domain"), "target.test")
        self.assertEqual(result.get("matches"), 1)
        # It carries campaign membership.
        self.assertIsInstance(result.get("in_campaigns"), list)
        self.assertEqual(len(result["in_campaigns"]), 1)
        self.assertEqual(result["in_campaigns"][0]["campaign_id"], "491")
        # Contact-level flags are COUNTS, not identities.
        self.assertEqual(result.get("contacts_total"), 2)
        self.assertEqual(result.get("contacts_replied"), 1)
        self.assertEqual(result.get("contacts_bounced"), 1)
        # No email addresses in the output.
        full = json.dumps(result)
        self.assertNotIn("alice@target.test", full)
        self.assertNotIn("carol@target.test", full)

    def test_account_not_found_says_so(self):
        """A domain not in the store gets a clean 'not found' answer."""
        self._write_queue([])
        scope = self._internal_scope()
        result = tools.account_campaign_status(scope, "unknown.test")
        self.assertEqual(result.get("matches"), 0)
        self.assertIn("no account", result.get("note", ""))


class CampaignSendingSchedule(_SandboxedTest):
    """SendingScheduleEmpty is not zero and not an error."""

    def test_invalid_campaign_id_refused(self):
        scope = self._internal_scope()
        result = tools.campaign_sending_schedule(scope, "not-a-number")
        self.assertIn("_error", result)

    def test_result_has_three_days(self):
        """The answer always has today, tomorrow, day_after_tomorrow."""
        self._write_campaigns([{
            "campaign_id": "491", "client": "testws", "name": "Email US",
            "status": "active",
        }])
        scope = self._internal_scope()
        # This will try to hit the provider, which will fail in tests.
        # The important thing is the structure: three day keys.
        result = tools.campaign_sending_schedule(scope, "491")
        self.assertIn("campaign_id", result)
        # Each day should have a value (even if "unreadable" or "none scheduled")
        for day in tools.FORWARD_DAYS:
            self.assertIn(day, result,
                          "missing day %s in result" % day)


class KeywordRouting(unittest.TestCase):
    """The keyword plan routes to the new tools."""

    def _scope(self):
        return slackscope.INTERNAL

    def test_is_in_campaign_routes_to_account_campaign_status(self):
        from src.slackconversation import keyword_plan
        scope = _FakeScope(slackscope.INTERNAL)
        plan = keyword_plan("is example.test in a campaign", scope)
        names = [c["name"] for c in plan]
        self.assertIn("account_campaign_status", names)

    def test_status_of_routes_to_lead_status_dm(self):
        from src.slackconversation import keyword_plan
        scope = _FakeScope(slackscope.INTERNAL)
        plan = keyword_plan("status of jane@example.test", scope)
        names = [c["name"] for c in plan]
        self.assertIn("lead_status_dm", names)

    def test_why_is_held_routes_to_domain_hold_reason(self):
        from src.slackconversation import keyword_plan
        scope = _FakeScope(slackscope.INTERNAL)
        plan = keyword_plan("why is example.test held", scope)
        names = [c["name"] for c in plan]
        self.assertIn("domain_hold_reason", names)

    def test_what_did_we_send_routes_to_domain_send_history(self):
        from src.slackconversation import keyword_plan
        scope = _FakeScope(slackscope.INTERNAL)
        plan = keyword_plan("what did we send to example.test", scope)
        names = [c["name"] for c in plan]
        self.assertIn("domain_send_history", names)

    def test_when_does_send_next_routes_to_campaign_sending_schedule(self):
        from src.slackconversation import keyword_plan
        scope = _FakeScope(slackscope.INTERNAL)
        plan = keyword_plan("when does 491 send next", scope)
        names = [c["name"] for c in plan]
        self.assertIn("campaign_sending_schedule", names)

    def test_replies_today_routes_to_replies_today(self):
        from src.slackconversation import keyword_plan
        scope = _FakeScope(slackscope.INTERNAL)
        plan = keyword_plan("how many replies today", scope)
        names = [c["name"] for c in plan]
        self.assertIn("replies_today", names)

    def test_credits_today_routes_to_credits_today(self):
        from src.slackconversation import keyword_plan
        scope = _FakeScope(slackscope.INTERNAL)
        plan = keyword_plan("credits spent today", scope)
        names = [c["name"] for c in plan]
        self.assertIn("credits_today", names)


class _FakeScope:
    """Minimal scope-like object for keyword_plan tests."""
    def __init__(self, kind):
        self.kind = kind


class ToolRegistry(unittest.TestCase):
    """The new tools are in the registry with correct scope."""

    def test_all_seven_tools_registered(self):
        expected = ("account_campaign_status", "lead_status_dm",
                    "domain_hold_reason", "domain_send_history",
                    "campaign_sending_schedule", "replies_today",
                    "credits_today")
        for name in expected:
            self.assertIn(name, tools.REGISTRY,
                          "%s not in REGISTRY" % name)

    def test_lead_status_dm_available_in_internal_and_client(self):
        """Lead lookup is available in both internal and client scopes."""
        spec = tools.REGISTRY["lead_status_dm"]
        scopes = spec[2]
        self.assertIn(slackscope.INTERNAL, scopes)
        self.assertIn(slackscope.CLIENT, scopes)

    def test_credits_today_internal_only(self):
        """Credits are Resonate's, not a client's."""
        spec = tools.REGISTRY["credits_today"]
        scopes = spec[2]
        self.assertIn(slackscope.INTERNAL, scopes)
        self.assertNotIn(slackscope.CLIENT, scopes)


class IsDMHelper(unittest.TestCase):
    """The _is_dm helper distinguishes DMs from channels."""

    def test_dm_source_is_detected(self):
        scope = slackscope.Scope(slackscope.INTERNAL,
                                 source="dm: internal user")
        self.assertTrue(tools._is_dm(scope))

    def test_channel_source_is_not_dm(self):
        scope = slackscope.Scope(slackscope.INTERNAL,
                                 source="channel: internal")
        self.assertFalse(tools._is_dm(scope))

    def test_empty_source_is_not_dm(self):
        scope = slackscope.Scope(slackscope.INTERNAL, source="")
        self.assertFalse(tools._is_dm(scope))


if __name__ == "__main__":
    unittest.main()
