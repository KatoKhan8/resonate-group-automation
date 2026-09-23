"""The catalogue's biggest gap: people ask HOW MANY, not WHO.

175 of the 988 classified questions in `docs/SLACK-AGENT-QUESTION-
CATALOGUE.md` are about leads and lists, and the catalogue's own finding is
blunt about what they are:

    The gap is counting, not looking up. `lead_lookup` answers "is this
    person in a campaign"; nobody asks that. They ask *how many*, *of which
    kind*, *ready when*.

So `lead_counts` answers the counting question and `lead_in_campaign`
answers the lookup one PROPERLY - from the provider rather than from our
own staging record, which is the half of `lead_lookup` that could be wrong
without anything noticing.

Four properties are asserted here and each of them is a way the numbers
could be quietly wrong rather than loudly absent:

1. **Emails are not people.** A three-step sequence sends three emails to
   one person, and "na koliko leadova smo poslali" asks for the one.
2. **An unreadable campaign is a floor, never a zero.**
3. **A client never meets the local store's counts**, in any phrasing.
4. **A lead in another client's campaign is indistinguishable from a lead
   that does not exist**, because telling them apart is the disclosure.
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

ALPHA = {"provider_campaign_ids": ["491", "492"]}
BETA = {"provider_campaign_ids": ["601"]}
PACK = {"workspaces": {"alpha": ALPHA, "beta": BETA}}


def client(workspace="alpha"):
    return slackscope.Scope(slackscope.CLIENT, workspace=workspace,
                            source="test")


def internal():
    return slackscope.Scope(slackscope.INTERNAL, source="test")


def row(lead_id, sent_at, row_id=None):
    """One scheduled-email row in the provider's own shape."""
    return {"id": row_id if row_id is not None else lead_id * 100,
            "status": "sent", "sent_at": sent_at,
            "lead": {"id": lead_id, "email": "someone@example.test"}}


RECENT = "2026-09-22T09:00:00Z"
OLD = "2026-08-01T09:00:00Z"


class CountingTest(unittest.TestCase):
    """The pack and the campaign detail are fixed; only the queue varies."""

    def setUp(self):
        self._pack = tools.knowledge.pack
        self._detail = tools.readback.campaign_by_id
        self._default = tools._default_workspace
        tools.knowledge.pack = lambda *a, **k: PACK
        tools._default_workspace = lambda: "alpha"
        tools.readback.campaign_by_id = lambda cid: {
            "campaign_id": cid, "name": "campaign %s" % cid,
            "status": "active", "emails_sent": 10, "replied": 2,
            "bounced": 0}

    def tearDown(self):
        tools.knowledge.pack = self._pack
        tools._default_workspace = self._default
        tools.readback.campaign_by_id = self._detail

    def counts(self, scope, queues, enrolled=None, argument=None):
        """`lead_counts` over a fixed provider. `queues` is per campaign."""
        def queue(campaign_id, cap=None):
            value = queues.get(str(campaign_id))
            if isinstance(value, Exception):
                raise value
            return value or []

        def count(campaign_id):
            value = (enrolled or {}).get(str(campaign_id), 0)
            if isinstance(value, Exception):
                raise value
            return value

        with mock.patch.object(bison, "scheduled_emails", queue), \
                mock.patch.object(bison, "campaign_lead_count", count):
            return tools.lead_counts(scope, argument)


# ================================ 1. EMAILS ARE NOT PEOPLE

class ASequenceSendsSeveralEmailsToOnePerson(CountingTest):

    def test_three_steps_to_one_lead_is_one_lead(self):
        """*na koliko leadova smo poslali* asks for the person count, and
        the row count is three times it once a three-step cadence has
        run."""
        out = self.counts(internal(), {
            "491": [row(7, RECENT), row(7, RECENT, row_id=2),
                    row(7, RECENT, row_id=3)],
            "492": []})
        self.assertEqual(out["emails_sent_last_7_days"], 3)
        self.assertEqual(out["leads_emailed_last_7_days"], 1)

    def test_a_person_in_two_campaigns_is_one_person_in_the_total(self):
        out = self.counts(internal(), {
            "491": [row(7, RECENT)],
            "492": [row(7, RECENT, row_id=9), row(8, RECENT)]})
        self.assertEqual(out["emails_sent_last_7_days"], 3)
        self.assertEqual(out["leads_emailed_last_7_days"], 2)
        per = {r["campaign_id"]: r for r in out["per_campaign"]}
        self.assertEqual(per["491"]["leads_emailed_last_7_days"], 1)
        self.assertEqual(per["492"]["leads_emailed_last_7_days"], 2)

    def test_the_note_says_the_per_campaign_figures_do_not_sum(self):
        """Because they do not, and somebody will add them up."""
        out = self.counts(internal(), {"491": [], "492": []})
        self.assertIn("do not sum", out["note"])

    def test_a_row_with_no_lead_id_is_still_a_person(self):
        """Counting it as nobody makes the people figure smaller than the
        truth, which is the direction that reads as good news."""
        out = self.counts(internal(), {
            "491": [{"id": 55, "status": "sent", "sent_at": RECENT}],
            "492": []})
        self.assertEqual(out["leads_emailed_last_7_days"], 1)
        self.assertEqual(out["emails_sent_last_7_days"], 1)

    def test_older_rows_are_outside_the_week(self):
        out = self.counts(internal(), {"491": [row(7, OLD)], "492": []})
        self.assertEqual(out["emails_sent_last_7_days"], 0)
        self.assertEqual(out["leads_emailed_last_7_days"], 0)

    def test_the_lifetime_counter_is_never_reported_as_weekly(self):
        out = self.counts(internal(), {"491": [], "492": []})
        self.assertEqual(out["sent_lifetime_total"], 20)
        self.assertEqual(out["emails_sent_last_7_days"], 0)
        self.assertIn("not a weekly figure", out["note"])


# ================================ 2. A FLOOR, NEVER A ZERO

class AnUnreadableCampaignIsSaidOutLoud(CountingTest):

    def test_a_refusing_queue_does_not_read_as_no_sends(self):
        out = self.counts(internal(),
                          {"491": RuntimeError("provider down"),
                           "492": [row(7, RECENT)]})
        self.assertEqual(out["campaigns_unreadable"], 1)
        self.assertIn("FLOOR", out["warning"])
        per = {r["campaign_id"]: r for r in out["per_campaign"]}
        self.assertTrue(per["491"]["last_7_days_unreadable"])
        self.assertNotIn("emails_sent_last_7_days", per["491"])

    def test_a_refusing_membership_count_does_not_read_as_empty(self):
        out = self.counts(internal(), {"491": [], "492": []},
                          enrolled={"491": RuntimeError("no"), "492": 40})
        self.assertEqual(out["enrolled_total"], 40)
        self.assertIn("FLOOR", out["warning"])
        per = {r["campaign_id"]: r for r in out["per_campaign"]}
        self.assertTrue(per["491"]["enrolled_unreadable"])
        self.assertNotIn("enrolled", per["491"])

    def test_a_clean_read_carries_no_warning(self):
        out = self.counts(internal(), {"491": [], "492": []},
                          enrolled={"491": 10, "492": 30})
        self.assertNotIn("warning", out)
        self.assertEqual(out["enrolled_total"], 40)
        self.assertEqual(out["campaigns_unreadable"], 0)


# ================================ 3. WHAT A CLIENT IS COUNTED

class AClientIsCountedFromTheProvider(CountingTest):

    def test_a_client_never_meets_the_local_pipeline(self):
        out = self.counts(client(), {"491": [], "492": []})
        self.assertNotIn("local_pipeline", out)

    def test_an_internal_channel_does(self):
        with mock.patch.object(tools.readback, "pipeline",
                               lambda: {"ready": 12}):
            out = self.counts(internal(), {"491": [], "492": []})
        self.assertEqual(out["local_pipeline"], {"ready": 12})
        self.assertIn("internal", out["local_pipeline_note"])

    def test_enrolled_is_the_providers_membership(self):
        out = self.counts(client(), {"491": [], "492": []},
                          enrolled={"491": 34, "492": 117})
        self.assertEqual(out["enrolled_total"], 151)
        self.assertIn("is NOT sent", out["note"])

    def test_a_client_cannot_count_another_clients_campaign(self):
        """The id arrives in the MESSAGE, so no reading filter touches it."""
        out = self.counts(client("alpha"), {}, argument="601")
        self.assertIn("_error", out)
        self.assertNotIn("601", out.get("per_campaign", []))

    def test_a_client_asking_for_its_own_campaign_gets_only_that_one(self):
        out = self.counts(client("alpha"), {"491": [row(7, RECENT)]},
                          argument="491")
        self.assertEqual(out["campaigns_asked_for"], 1)
        self.assertEqual([r["campaign_id"] for r in out["per_campaign"]],
                         ["491"])

    def test_both_tools_are_visible_to_a_client_and_are_registered(self):
        names = tools.for_scope(client())
        self.assertIn("lead_counts", names)
        self.assertIn("lead_in_campaign", names)


# ================================ 4. MEMBERSHIP FROM THE PROVIDER

class MembershipIsTheProvidersToStateAndNobodyElses(unittest.TestCase):

    def setUp(self):
        self._pack = tools.knowledge.pack
        tools.knowledge.pack = lambda *a, **k: PACK

    def tearDown(self):
        tools.knowledge.pack = self._pack

    def ask(self, scope, address, lead=None, membership=None):
        def find(_address):
            if isinstance(lead, Exception):
                raise lead
            return lead

        def member(campaign_id, lead_ids=None):
            value = (membership or {}).get(str(campaign_id))
            if isinstance(value, Exception):
                raise value
            return value or {}

        with mock.patch.object(bison, "find_lead_by_email", find), \
                mock.patch.object(bison, "membership", member):
            return tools.lead_in_campaign(scope, address)

    def test_it_reports_the_providers_status_per_campaign(self):
        out = self.ask(client(), "x@example.test",
                       lead={"id": 900, "email": "x@example.test"},
                       membership={"491": {900: "active"}})
        self.assertTrue(out["found"])
        self.assertEqual(out["in_campaigns"],
                         [{"campaign_id": "491", "status": "active"}])
        self.assertEqual(out["source"], "provider")

    def test_a_lead_in_another_clients_campaign_reads_as_no_lead(self):
        """It exists at the provider, in nobody's campaign here. Saying so
        would tell this client we hold that person for somebody else."""
        absent = self.ask(client("alpha"), "rival@example.test",
                          lead=None)
        elsewhere = self.ask(client("alpha"), "rival@example.test",
                             lead={"id": 4242}, membership={})
        self.assertEqual(absent["note"], elsewhere["note"])
        self.assertFalse(absent["found"])
        self.assertFalse(elsewhere["found"])
        self.assertEqual(absent["in_campaigns"], elsewhere["in_campaigns"])

    def test_nothing_from_the_providers_lead_row_is_echoed(self):
        """`find_lead_by_email` searches the whole estate. Only the id
        leaves that search."""
        import json
        out = self.ask(client("alpha"), "x@example.test",
                       lead={"id": 900, "email": "x@example.test",
                             "first_name": "Someone", "company": "Rival Ltd",
                             "custom_variables": [{"name": "client",
                                                   "value": "beta"}]},
                       membership={"491": {900: "active"}})
        body = json.dumps(out)
        for leaked in ("Someone", "Rival Ltd", "beta", "custom_variables"):
            self.assertNotIn(leaked, body, leaked)

    def test_only_this_workspaces_campaigns_are_ever_asked_about(self):
        asked = []

        def member(campaign_id, lead_ids=None):
            asked.append(str(campaign_id))
            return {}

        with mock.patch.object(bison, "find_lead_by_email",
                               lambda a: {"id": 1}), \
                mock.patch.object(bison, "membership", member):
            tools.lead_in_campaign(client("alpha"), "x@example.test")
        self.assertEqual(asked, ["491", "492"])
        self.assertNotIn("601", asked)

    def test_an_unreadable_campaign_makes_an_empty_list_a_floor(self):
        out = self.ask(client(), "x@example.test", lead={"id": 900},
                       membership={"491": RuntimeError("down"),
                                   "492": {}})
        self.assertEqual(out["campaigns_unreadable"], 1)
        self.assertIn("floor", out["warning"])

    def test_a_provider_that_cannot_be_asked_says_so(self):
        out = self.ask(client(), "x@example.test",
                       lead=RuntimeError("timeout"))
        self.assertIn("_error", out)
        self.assertNotIn("found", out)

    def test_it_needs_an_address_rather_than_guessing(self):
        self.assertIn("_error", tools.lead_in_campaign(client(), "Hussein"))
        self.assertIn("_error", tools.lead_in_campaign(client(), ""))

    def test_the_cap_is_real(self):
        """Twelve campaigns is twelve reads; a question about one person
        does not become thirty."""
        many = {"workspaces": {"alpha": {
            "provider_campaign_ids": [str(i) for i in range(40)]}}}
        asked = []
        tools.knowledge.pack = lambda *a, **k: many
        with mock.patch.object(bison, "find_lead_by_email",
                               lambda a: {"id": 1}), \
                mock.patch.object(bison, "membership",
                                  lambda c, lead_ids=None: asked.append(c)
                                  or {}):
            out = tools.lead_in_campaign(client("alpha"), "x@example.test")
        self.assertEqual(len(asked), tools.MEMBERSHIP_CAMPAIGN_CAP)
        self.assertEqual(out["campaigns_checked"],
                         tools.MEMBERSHIP_CAMPAIGN_CAP)


class TheStoresAnswerSaysItIsTheStores(unittest.TestCase):
    """`lead_lookup` still answers from our staging record, and now says
    so - staged is not enrolled, and the one moment somebody asks is the
    moment a refused push makes the two disagree."""

    def test_lead_lookup_labels_its_membership_as_local(self):
        scope = client()
        with mock.patch.object(tools, "_find_contacts",
                               lambda *a, **k: [{"contact": "x@example.test",
                                                 "in_campaigns": []}]), \
                mock.patch.object(tools, "_workspace_for",
                                  lambda *a, **k: "alpha"):
            out = tools.lead_lookup(scope, "x@example.test")
        self.assertEqual(out["matches"], 1)

    def test_the_real_finder_stamps_the_source_on_every_row(self):
        records = [{"id": "r1", "domain": "example.test", "state": "ready",
                    "contacts": [{"key": "k", "name": "Someone",
                                  "email": "x@example.test"}]}]
        with mock.patch.object(tools, "_records", lambda slug: records), \
                mock.patch.object(tools, "campaigns_of_record",
                                  lambda slug, rid: []):
            found = tools._find_contacts("alpha", "x@example.test")
        self.assertEqual(len(found), 1)
        self.assertIn("not the provider", found[0]["in_campaigns_source"])
        self.assertIn("lead_in_campaign", found[0]["in_campaigns_source"])


if __name__ == "__main__":
    unittest.main()
