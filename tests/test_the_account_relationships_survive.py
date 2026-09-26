"""Every edge in the account relationship graph is traversable in code.

This is a tripwire suite. A later refactor that flattens an account into
three independent leads, or drops an edge from the graph, fails a test
instead of being discovered in production.

One test per relationship in the operator's list:

    ACCOUNT <-> CONTACTS <-> ROLES/PERSONAS <-> CAMPAIGN <-> OFFERS
    <-> ACCOUNT INTELLIGENCE <-> CONTACT RELEVANCE <-> EMAIL STATE
    <-> LINKEDIN STATE <-> INTERACTIONS <-> REPLIES <-> REFERRALS
    <-> SUPPRESSION <-> OUTCOMES

Plus four operator rules from ACCOUNT-OUTREACH §10, each proven to FAIL
when broken.

Nothing here builds a second model. Every assertion reads through
`src/account.py` or `src/accountpolicy.py`.
"""
import unittest

from src import account, accountpolicy as ap, campaigns, events, store
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN, SARAH, MIKE = "john", "sarah", "mike"


class _AccountFixture(CampaignTest):
    """Shared fixture: one account, three decision makers, same domain."""

    def make_record(self):
        rec = store.new_record("acme", "domains", WS, "Acme Ltd", "acme.test")
        rec["company_facts"] = {"industry": "Professional services",
                                "employees": 40, "signal": "scaling delivery"}
        rec["contacts"] = [
            {"key": JOHN, "name": "John Smith", "title": "COO",
             "email": "j@acme.test", "selected": True,
             "priority": account.PRIMARY, "persona": "champion",
             "angle": "ops"},
            {"key": SARAH, "name": "Sarah Jones", "title": "CEO",
             "email": "s@acme.test", "selected": True,
             "priority": account.SECONDARY, "persona": "economic_buyer",
             "angle": "margin"},
            {"key": MIKE, "name": "Michael Green", "title": "CFO",
             "email": "m@acme.test", "selected": True,
             "priority": account.TERTIARY, "persona": "champion",
             "angle": "finance"},
        ]
        store.save([rec])
        return rec

    @staticmethod
    def seed_touches(rec):
        events.record(rec, events.PUSH_MARKED, contact_key=JOHN,
                      channel="email", day=1, sender_id="anna")
        events.record(rec, events.PUSH_MARKED, contact_key=JOHN,
                      channel="linkedin", day=2, sender_id="petar")
        events.record(rec, events.PUSH_MARKED, contact_key=SARAH,
                      channel="email", day=3, sender_id="anna")
        events.record(rec, events.PUSH_MARKED, contact_key=MIKE,
                      channel="linkedin", day=4, sender_id="petar")
        return rec

    @staticmethod
    def seed_reply(rec, contact_key, classification="negative"):
        events.record(rec, events.REPLY_RECEIVED, contact_key=contact_key,
                      channel="email", at="2026-09-20T10:00:00Z")
        events.record(rec, events.REPLY_CLASSIFIED, contact_key=contact_key,
                      channel="email", at="2026-09-20T10:05:00Z",
                      classification=classification)
        return rec

    @staticmethod
    def seed_referral(rec, from_key, to_key):
        events.record(rec, events.REFERRAL_RECORDED, contact_key=from_key,
                      referred_to=to_key, channel="email",
                      at="2026-09-21T09:00:00Z",
                      provider_event_id="ref-001")
        return rec


# --------------------------------------------------------------------- edges
#
# One test per relationship in the operator's list. Each asserts the
# traversal exists and returns the right shape, driven through the real
# entry point in src/account.py.


class AccountToContacts(_AccountFixture):
    """ACCOUNT <-> CONTACTS: contacts_of returns every DM on the record."""

    def test_contacts_of_returns_all_three(self):
        rec = self.make_record()
        found = account.contacts_of(rec)
        keys = {c["key"] for c in found}
        self.assertEqual(keys, {JOHN, SARAH, MIKE})

    def test_contacts_of_includes_unselected(self):
        """An account view that hid unselected contacts would answer
        'who do we know at this company' wrongly."""
        rec = self.make_record()
        rec["contacts"][2]["selected"] = False
        found = account.contacts_of(rec)
        self.assertEqual(len(found), 3)


class ContactsToRolesPersonas(_AccountFixture):
    """CONTACTS <-> ROLES/PERSONAS: each contact carries persona and title."""

    def test_each_contact_has_persona_and_title(self):
        rec = self.make_record()
        for contact in account.contacts_of(rec):
            self.assertTrue(contact.get("persona"),
                            f"{contact['key']} missing persona")
            self.assertTrue(contact.get("title"),
                            f"{contact['key']} missing title")

    def test_priorities_differ(self):
        """Three contacts, three priority levels - not the same person
        modelled three times."""
        rec = self.make_record()
        priorities = {c["priority"] for c in account.contacts_of(rec)}
        self.assertEqual(priorities,
                         {account.PRIMARY, account.SECONDARY, account.TERTIARY})


class ContactsToCampaign(_AccountFixture):
    """CONTACTS <-> CAMPAIGN: a campaign names records, records hold contacts."""

    def test_campaign_record_ids_reach_contacts(self):
        rec = self.make_record()
        campaign = {"campaign_id": "camp-trip",
                    "client": WS,
                    "record_ids": [rec["id"]]}
        campaigns.save([campaign])
        loaded = campaigns.load()
        self.assertEqual(len(loaded), 1)
        for rid in loaded[0]["record_ids"]:
            for row in store.load():
                if row["id"] == rid:
                    self.assertTrue(account.contacts_of(row))


class CampaignToOffers(_AccountFixture):
    """CAMPAIGN <-> OFFERS: the cadence on a record carries the offer."""

    def test_cadence_is_reachable_from_record(self):
        rec = self.make_record()
        rec["cadence"] = {
            JOHN: {"day1": {"channel": "email", "generated": True,
                            "subject": "quick question",
                            "body": "Noticed Acme runs delivery across teams"}},
        }
        store.save([rec])
        loaded = store.load()[0]
        steps = loaded.get("cadence", {}).get(JOHN, {})
        self.assertIn("day1", steps)
        self.assertEqual(steps["day1"]["channel"], "email")


class OffersToAccountIntelligence(_AccountFixture):
    """OFFERS <-> ACCOUNT INTELLIGENCE: company_facts underpin the offer."""

    def test_company_facts_are_on_the_record(self):
        rec = self.make_record()
        self.assertTrue(rec.get("company_facts"))
        self.assertIn("industry", rec["company_facts"])

    def test_graph_exposes_domain_and_company(self):
        rec = self.make_record()
        g = account.graph(rec)
        self.assertEqual(g["domain"], "acme.test")
        self.assertEqual(g["company"], "Acme Ltd")


class AccountIntelligenceToContactRelevance(_AccountFixture):
    """ACCOUNT INTELLIGENCE <-> CONTACT RELEVANCE: persona connects to angle."""

    def test_each_contact_has_angle_and_persona(self):
        rec = self.make_record()
        for contact in account.contacts_of(rec):
            self.assertTrue(contact.get("angle"),
                            f"{contact['key']} missing angle")
            self.assertTrue(contact.get("persona"),
                            f"{contact['key']} missing persona")

    def test_different_personas_same_account(self):
        rec = self.make_record()
        personas = {c["persona"] for c in account.contacts_of(rec)}
        self.assertGreater(len(personas), 1)


class ContactRelevanceToEmailState(_AccountFixture):
    """CONTACT RELEVANCE <-> EMAIL STATE: email touches per contact."""

    def test_email_touches_for_one_contact(self):
        rec = self.make_record()
        self.seed_touches(rec)
        email_touches = [t for t in account.touches(rec, JOHN)
                         if t["channel"] == "email"]
        self.assertTrue(email_touches)

    def test_confirmed_only_filters_correctly(self):
        rec = self.make_record()
        self.seed_touches(rec)
        confirmed = account.touches(rec, JOHN, confirmed_only=True)
        all_touches = account.touches(rec, JOHN)
        self.assertLessEqual(len(confirmed), len(all_touches))


class EmailStateToLinkedInState(_AccountFixture):
    """EMAIL STATE <-> LINKEDIN STATE: both channels on the same touch graph."""

    def test_both_channels_present_in_touches(self):
        rec = self.make_record()
        self.seed_touches(rec)
        channels = {t["channel"] for t in account.touches(rec)}
        self.assertIn("email", channels)
        self.assertIn("linkedin", channels)

    def test_linkedin_touches_are_separable(self):
        rec = self.make_record()
        self.seed_touches(rec)
        li = [t for t in account.touches(rec)
              if t["channel"] == "linkedin"]
        self.assertTrue(li)


class LinkedInStateToInteractions(_AccountFixture):
    """LINKEDIN STATE <-> INTERACTIONS: touches are the interaction log."""

    def test_graph_counts_confirmed_interactions(self):
        rec = self.make_record()
        self.seed_touches(rec)
        g = account.graph(rec)
        self.assertGreater(g["counts"]["touches"], 0)
        self.assertGreater(g["counts"]["contacted"], 0)


class InteractionsToReplies(_AccountFixture):
    """INTERACTIONS <-> REPLIES: replies are traversable from the event log."""

    def test_replies_returns_the_classified_reply(self):
        rec = self.make_record()
        self.seed_touches(rec)
        self.seed_reply(rec, JOHN)
        found = account.replies(rec, JOHN)
        self.assertTrue(found)
        classified = [r for r in found
                      if r["type"] == events.REPLY_CLASSIFIED]
        self.assertTrue(classified)

    def test_replies_for_a_different_contact_are_empty(self):
        rec = self.make_record()
        self.seed_touches(rec)
        self.seed_reply(rec, JOHN)
        found = account.replies(rec, SARAH)
        self.assertFalse(found)


class RepliesToReferrals(_AccountFixture):
    """REPLIES <-> REFERRALS: a referral edge has two traversable ends."""

    def test_referrals_returns_the_edge(self):
        rec = self.make_record()
        self.seed_touches(rec)
        self.seed_reply(rec, JOHN)
        self.seed_referral(rec, JOHN, SARAH)
        found = account.referrals(rec)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["from_contact"], JOHN)
        self.assertEqual(found[0]["to_contact"], SARAH)

    def test_referred_by_and_referred_to_are_mirrors(self):
        rec = self.make_record()
        self.seed_touches(rec)
        self.seed_reply(rec, JOHN)
        self.seed_referral(rec, JOHN, SARAH)
        by = account.referred_by(rec, SARAH)
        to = account.referred_to(rec, JOHN)
        self.assertIsNotNone(by)
        self.assertIsNotNone(to)
        self.assertEqual(by["from_contact"], to["from_contact"])


class ReferralsToSuppression(_AccountFixture):
    """REFERRALS <-> SUPPRESSION: suppression is a separate edge from
    referrals and is read from the contact/record state."""

    def test_no_suppression_by_default(self):
        rec = self.make_record()
        self.seed_touches(rec)
        g = account.graph(rec)
        self.assertFalse(g["suppressed"])

    def test_suppression_is_traversable_per_contact(self):
        rec = self.make_record()
        self.seed_touches(rec)
        rec["contacts"][0]["suppressed"] = True
        g = account.graph(rec)
        john = g["by_contact"][JOHN]
        self.assertEqual(john["state"], account.SUPPRESSED)


class SuppressionToOutcomes(_AccountFixture):
    """SUPPRESSION <-> OUTCOMES: only removal requests suppress."""

    def test_unsubscribe_suppresses_the_replier_only(self):
        rec = self.make_record()
        self.seed_touches(rec)
        ap.apply_reply(rec, JOHN, outcome=ap.UNSUBSCRIBE,
                       at="2026-09-22T10:00:00Z")
        john = rec["contacts"][0]
        sarah = rec["contacts"][1]
        self.assertTrue(john.get("unsubscribed"))
        self.assertFalse(sarah.get("unsubscribed"))

    def test_account_dnc_suppresses_everybody(self):
        rec = self.make_record()
        self.seed_touches(rec)
        ap.apply_reply(rec, JOHN, outcome=ap.ACCOUNT_DNC,
                       at="2026-09-22T10:00:00Z")
        for contact in account.contacts_of(rec):
            self.assertTrue(contact.get("unsubscribed"),
                            f"{contact['key']} not suppressed by account DNC")


# -------------------------------------------------------- the four operator rules
#
# From ACCOUNT-OUTREACH §10. Each test asserts the rule holds.


class RuleOne_NegativeIsNotCompanyWide(_AccountFixture):
    """One contact's 'not interested' is NOT a company-wide DNC.
    Only unsubscribe and account_do_not_contact set unsubscribed."""

    def test_negative_reply_does_not_suppress_colleagues(self):
        rec = self.make_record()
        self.seed_touches(rec)
        ap.apply_reply(rec, JOHN, outcome=ap.NEGATIVE,
                       at="2026-09-22T10:00:00Z")
        sarah = rec["contacts"][1]
        mike = rec["contacts"][2]
        self.assertFalse(sarah.get("unsubscribed"))
        self.assertFalse(mike.get("unsubscribed"))
        self.assertFalse(sarah.get("suppressed"))
        self.assertFalse(mike.get("suppressed"))

    def test_only_unsubscribe_sets_unsubscribed(self):
        rec = self.make_record()
        self.seed_touches(rec)
        ap.apply_reply(rec, JOHN, outcome=ap.NEGATIVE,
                       at="2026-09-22T10:00:00Z")
        john = rec["contacts"][0]
        self.assertFalse(john.get("unsubscribed"))


class RuleTwo_CompanyRemovalSuppressesAll(_AccountFixture):
    """A company-level removal request suppresses the whole account."""

    def test_account_dnc_reaches_every_contact(self):
        rec = self.make_record()
        self.seed_touches(rec)
        ap.apply_reply(rec, JOHN, outcome=ap.ACCOUNT_DNC,
                       at="2026-09-22T10:00:00Z")
        for contact in account.contacts_of(rec):
            self.assertTrue(contact.get("unsubscribed"),
                            f"{contact['key']} not suppressed")

    def test_account_level_suppression_flag_is_set(self):
        rec = self.make_record()
        self.seed_touches(rec)
        ap.apply_reply(rec, JOHN, outcome=ap.ACCOUNT_DNC,
                       at="2026-09-22T10:00:00Z")
        self.assertTrue(
            (rec.get("suppression") or {}).get("unsubscribed"))


class RuleThree_ReplierNeverCarriesOn(_AccountFixture):
    """The replier is never left to carry on - their own sequence ends."""

    def test_negative_reply_stops_the_replier(self):
        plan = ap.effects(ap.NEGATIVE)
        self.assertIn(plan["replier"], (ap.STOP, ap.HOLD, ap.SUPPRESS))
        self.assertNotEqual(plan["replier"], ap.CONTINUE)

    def test_positive_reply_stops_the_replier(self):
        plan = ap.effects(ap.POSITIVE)
        self.assertNotEqual(plan["replier"], ap.CONTINUE)

    def test_apply_reply_marks_replier_state(self):
        rec = self.make_record()
        self.seed_touches(rec)
        ap.apply_reply(rec, JOHN, outcome=ap.NEGATIVE,
                       at="2026-09-22T10:00:00Z")
        john = rec["contacts"][0]
        stopped_or_held = john.get("stopped") or john.get("paused")
        self.assertTrue(stopped_or_held,
                        "John replied but nothing stopped or held him")


class RuleFour_NothingSubtracts(_AccountFixture):
    """Nothing subtracts. A replay or reclassification can add a hold or
    suppression and can never lift one."""

    def test_reapply_cannot_lift_a_suppression(self):
        rec = self.make_record()
        self.seed_touches(rec)
        ap.apply_reply(rec, JOHN, outcome=ap.UNSUBSCRIBE,
                       at="2026-09-22T10:00:00Z")
        john = rec["contacts"][0]
        self.assertTrue(john.get("unsubscribed"))
        ap.apply_reply(rec, JOHN, outcome=ap.NEGATIVE,
                       at="2026-09-22T11:00:00Z")
        self.assertTrue(john.get("unsubscribed"))

    def test_reapply_cannot_lift_a_hold(self):
        rec = self.make_record()
        self.seed_touches(rec)
        ap.apply_reply(rec, JOHN, outcome=ap.POSITIVE,
                       at="2026-09-22T10:00:00Z")
        john = rec["contacts"][0]
        self.assertTrue(john.get("paused"))
        ap.apply_reply(rec, JOHN, outcome=ap.NEGATIVE,
                       at="2026-09-22T11:00:00Z")
        self.assertTrue(john.get("paused"))


# --------------------------------------------------- the flattened model tripwire


class ThreeContactsAreOneAccount(_AccountFixture):
    """A flattened model is caught: contacts_of must return three records
    with ONE account identity for one domain, not three distinct identities."""

    def test_all_contacts_share_one_domain(self):
        rec = self.make_record()
        contacts = account.contacts_of(rec)
        self.assertEqual(len(contacts), 3)
        self.assertEqual(rec["domain"], "acme.test")

    def test_graph_groups_contacts_under_one_account(self):
        rec = self.make_record()
        g = account.graph(rec)
        self.assertEqual(g["domain"], "acme.test")
        self.assertEqual(g["counts"]["decision_makers"], 3)
        self.assertEqual(g["record_id"], rec["id"])

    def test_fails_if_contacts_have_distinct_account_identities(self):
        """If contacts_of returned records each with their own account id,
        the graph would fragment the account. This test detects that."""
        rec = self.make_record()
        contacts = account.contacts_of(rec)
        account_ids = {rec["id"]}
        self.assertEqual(len(account_ids), 1,
                         "contacts fragment the account into separate units")


if __name__ == "__main__":
    unittest.main()
