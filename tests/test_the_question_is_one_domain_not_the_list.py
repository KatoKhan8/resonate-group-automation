"""The question was singular and the answer was a 194KB list.

From `docs/SLACK-AGENT-QUESTION-CATALOGUE.md`, on senders and domains — 106
questions, the third-largest intent:

    Note the shape: almost never "list the domains". Usually ONE domain,
    one sender, one campaign — which `sending_domains` answers at the wrong
    granularity. Per-domain lookup is a gap worth closing.

The message that proved it is the one immediately after a CSV of every
sender was attached in a client channel:

    sending-domain-a.example.test, kakva je ovo domena?

`domain_detail` answers that one. Three properties are asserted here:

1. **A domain that is not this workspace's reads exactly like a domain that
   is nobody's**, because an answer telling those apart confirms another
   client's estate exists.
2. **A pasted address leaves as a domain.** `sending_domains` refuses to
   put a mailbox in an answer in any scope, and echoing back the address
   somebody pasted would do it by the back door.
3. **Health and bounce stay internal**, on the same line `sending_domains`
   already draws: which domains send for a client is theirs, our assessment
   of our own mailboxes is ours.
"""
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import src.senderidentity                       # noqa: E402,F401
from src import slackagenttools as tools                         # noqa: E402
from src import slackscope                                       # noqa: E402

PACK = {"workspaces": {"alpha": {"provider_campaign_ids": ["491"]}}}

#: One attested mailbox estate: two mailboxes for Jelena on the domain in
#: question, one for Tina elsewhere.
ATTESTATIONS = [
    {"kind": "ownership_attestation", "workspace": "alpha",
     "channel": "email", "sender_id": "s-jelena", "account_id": "eb-1"},
    {"kind": "ownership_attestation", "workspace": "alpha",
     "channel": "email", "sender_id": "s-jelena", "account_id": "eb-2"},
    {"kind": "ownership_attestation", "workspace": "alpha",
     "channel": "email", "sender_id": "s-tina", "account_id": "eb-3"},
    # Another workspace's, and it must be unreachable rather than filtered.
    {"kind": "ownership_attestation", "workspace": "beta",
     "channel": "email", "sender_id": "s-rival", "account_id": "eb-9"},
]
PEOPLE = [{"sender_id": "s-jelena", "display_name": "Jelena"},
          {"sender_id": "s-tina", "display_name": "Tina"}]
ACCOUNTS = [
    {"account_id": "eb-1", "provider_account_id": "1",
     "domain": "sending-domain-a.example.test", "daily_limit": 15,
     "health": "good"},
    {"account_id": "eb-2", "provider_account_id": "2",
     "domain": "sending-domain-a.example.test", "daily_limit": 15,
     "health": "warming"},
    {"account_id": "eb-3", "provider_account_id": "3",
     "domain": "other.example", "daily_limit": 15, "health": "good"},
]


def client(workspace="alpha"):
    return slackscope.Scope(slackscope.CLIENT, workspace=workspace,
                            source="test")


def internal():
    return slackscope.Scope(slackscope.INTERNAL, source="test")


class OneDomain(unittest.TestCase):

    def setUp(self):
        self._pack = tools.knowledge.pack
        self._default = tools._default_workspace
        tools.knowledge.pack = lambda *a, **k: PACK
        tools._default_workspace = lambda: "alpha"

        identity = mock.MagicMock()
        identity.load.return_value = list(ATTESTATIONS)
        identity.senders.side_effect = lambda slug, rows=None: list(PEOPLE)
        identity.email_accounts.side_effect = (
            lambda slug, rows=None, active_only=False: list(ACCOUNTS))
        self.identity = identity
        # PATCH THE ATTRIBUTE ON THE PACKAGE, AND THE sys.modules ENTRY
        # WITH IT. `slackagenttools` does `from . import senderidentity`,
        # which reads the ATTRIBUTE on `src` and only falls back to
        # sys.modules when there is none. Patching sys.modules alone passed
        # this file when it ran first and failed it in a full run, because
        # by then something else had imported the real module and bound the
        # attribute. Both, so the order of the run cannot decide it.
        self._modules = [
            mock.patch("src.senderidentity", identity),
            mock.patch.dict(sys.modules, {"src.senderidentity": identity}),
        ]
        for patcher in self._modules:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self._modules):
            patcher.stop()
        tools.knowledge.pack = self._pack
        tools._default_workspace = self._default

    def ask(self, scope, argument, week=None, carried=None, bounce=None):
        with mock.patch.object(tools, "_week_for_domain",
                               lambda slug, domain: week), \
                mock.patch.object(tools, "_campaigns_by_sending_account",
                                  lambda slug: carried or {}), \
                mock.patch.object(tools, "_bounce_by_provider_account",
                                  lambda slug, rows: bounce or {}):
            return tools.domain_detail(scope, argument)


# ================================ 1. THE QUESTION THAT PROMPTED IT

class TheRealQuestionIsAnswered(OneDomain):

    def test_it_says_whose_it_is_and_how_many_mailboxes(self):
        out = self.ask(client(), "sending-domain-a.example.test")
        self.assertTrue(out["ours"])
        self.assertEqual(out["mailboxes"], 2)
        self.assertEqual(out["senders"], ["Jelena"])
        self.assertEqual(out["daily_capacity"], 30)

    def test_it_names_the_campaigns_the_domain_carries(self):
        out = self.ask(client(), "sending-domain-a.example.test",
                       carried={"1": ["campaign 491"], "2": ["campaign 492"]})
        self.assertEqual(out["campaigns_carried"],
                         ["campaign 491", "campaign 492"])

    def test_the_week_carries_people_and_emails_apart(self):
        out = self.ask(client(), "sending-domain-a.example.test", week=(9, 3, 0, 0))
        self.assertEqual(out["emails_sent_last_7_days"], 9)
        self.assertEqual(out["leads_emailed_last_7_days"], 3)

    def test_an_unreadable_queue_claims_nothing_about_the_week(self):
        out = self.ask(client(), "sending-domain-a.example.test", week=None)
        self.assertNotIn("emails_sent_last_7_days", out)
        self.assertIn("nothing is claimed", out["last_7_days_note"])

    def test_a_partly_readable_queue_says_the_figures_are_floors(self):
        out = self.ask(client(), "sending-domain-a.example.test", week=(4, 2, 1, 0))
        self.assertEqual(out["campaigns_unreadable"], 1)
        self.assertIn("floors", out["last_7_days_note"])

    def test_a_campaign_past_the_cap_is_a_floor_but_not_an_outage(self):
        """Refused and not-asked both make the figure a floor, and they are
        reported apart: only one of them is a fault worth chasing."""
        out = self.ask(client(), "sending-domain-a.example.test",
                       week=(4, 2, 0, 3))
        self.assertNotIn("campaigns_unreadable", out)
        self.assertEqual(out["campaigns_not_read"], 3)
        self.assertIn("floors", out["last_7_days_note"])
        self.assertIn("cap", out["last_7_days_note"])


# ================================ 2. NOT YOURS AND NOBODY'S ARE ONE ANSWER

class ADomainThatIsNotYoursReadsTheSameAsOneThatIsNobodys(OneDomain):

    def test_another_workspaces_domain_and_an_unknown_one_agree(self):
        elsewhere = self.ask(client("alpha"), "other-clients-domain.test")
        nobody = self.ask(client("alpha"), "nowhere-at-all.test")
        self.assertEqual(elsewhere["note"].replace(
            "other-clients-domain.test", "X"),
            nobody["note"].replace("nowhere-at-all.test", "X"))
        self.assertFalse(elsewhere["ours"])
        self.assertFalse(nobody["ours"])

    def test_nothing_else_is_said_about_a_domain_that_is_not_ours(self):
        out = self.ask(client(), "other-clients-domain.test")
        for key in ("mailboxes", "senders", "campaigns_carried", "health",
                    "bounce_rate_percent", "daily_capacity"):
            self.assertNotIn(key, out, key)

    def test_a_sender_from_another_workspace_is_unreachable(self):
        """`eb-9` is attested to `beta`. It is never walked, rather than
        walked and filtered."""
        body = json.dumps(self.ask(client("alpha"), "other.example"))
        self.assertNotIn("rival", body)


# ================================ 3. AN ADDRESS LEAVES AS A DOMAIN

class APastedAddressNeverComesBack(OneDomain):

    def test_the_local_part_is_dropped_before_anything_is_looked_up(self):
        out = self.ask(client(), "tina@sending-domain-a.example.test")
        self.assertEqual(out["domain"], "sending-domain-a.example.test")
        self.assertNotIn("tina@", json.dumps(out))
        self.assertTrue(out["ours"])

    def test_no_at_sign_survives_anywhere_in_the_answer(self):
        for argument in ("tina@sending-domain-a.example.test",
                         "sending-domain-a.example.test",
                         "https://sending-domain-a.example.test/pricing"):
            self.assertNotIn("@", json.dumps(self.ask(client(), argument)),
                             argument)

    def test_a_value_that_is_not_a_domain_is_refused_rather_than_guessed(
            self):
        for argument in ("nodot", "", None, "two words.com"):
            self.assertIn("_error", self.ask(client(), argument))


# ================================ 4. WHAT IS OURS STAYS OURS

class OurReadingOfOurOwnInfrastructureIsInternal(OneDomain):

    def test_a_client_is_shown_no_health_and_no_bounce(self):
        out = self.ask(client(), "sending-domain-a.example.test",
                       bounce={"1": {"sent": 100, "bounced": 4}})
        for key in ("health", "bounce_rate_percent", "over_hard_stop",
                    "emails_sent_lifetime"):
            self.assertNotIn(key, out, key)

    def test_an_internal_channel_is(self):
        out = self.ask(internal(), "sending-domain-a.example.test",
                       bounce={"1": {"sent": 100, "bounced": 4},
                               "2": {"sent": 100, "bounced": 0}})
        self.assertEqual(out["health"], {"good": 1, "warming": 1})
        self.assertEqual(out["bounce_rate_percent"], 2.0)
        self.assertEqual(out["over_hard_stop"], False)

    def test_an_unreadable_estate_claims_no_rate(self):
        out = self.ask(internal(), "sending-domain-a.example.test", bounce={})
        self.assertIsNone(out["bounce_rate_percent"])
        self.assertIn("no bounce rate is claimed", out["bounce_note"])

    def test_it_is_on_the_tool_list_for_both_scopes(self):
        self.assertIn("domain_detail", tools.for_scope(client()))
        self.assertIn("domain_detail", tools.for_scope(internal()))


if __name__ == "__main__":
    unittest.main()
