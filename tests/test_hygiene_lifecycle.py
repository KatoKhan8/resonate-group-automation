"""Import-time cleaning is not enough, and this is the file that says why.

A row is checked when it arrives. Then time passes: the person replies to a
different campaign, their company asks to be removed, somebody books a
meeting. The campaign approved on Monday is still holding Monday's answer.

So the question "may this go out" is asked again, at the last possible
moment, by `eligibility.decide` - and these tests are the ones that would
fail if anybody made import-time hygiene authoritative.

The three moments, and what each is for:

    import      what this list looks like against our history, so an
                operator can decide what to buy enrichment for
    campaign    what is still eligible when the audience is resolved
    pre-send    what is still eligible for this exact step, right now

Only the last one may authorise a send.
"""
import unittest

from src import (account, accountpolicy as ap, eligibility, events, hygiene,
                 store)
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN, SARAH = "john", "sarah"


class LifecycleTest(CampaignTest):

    def record(self, rid="acme"):
        rec = store.new_record(rid, "domains", WS, "Acme Ltd", "acme.test")
        rec["contacts"] = [
            {"key": JOHN, "name": "John Smith", "title": "COO",
             "email": "john@acme.test", "selected": True,
             "priority": account.PRIMARY},
            {"key": SARAH, "name": "Sarah Jones", "title": "CEO",
             "email": "sarah@acme.test", "selected": True,
             "priority": account.SECONDARY},
        ]
        store.save([rec])
        return rec

    def contact(self, rec, key):
        return {c["key"]: c for c in rec["contacts"]}[key]

    def classified_reply(self, rec, key, outcome,
                         at="2026-08-05T09:00:00+00:00"):
        events.record(rec, events.REPLY_RECEIVED, contact_key=key,
                      channel="email", at=at,
                      provider_event_id=f"r-{rec['id']}-{key}")
        events.record(rec, events.REPLY_CLASSIFIED, contact_key=key,
                      channel="email", at=at, classification=outcome,
                      provider_event_id=f"r-{rec['id']}-{key}:c")
        ap.apply_reply(rec, key, outcome, at=at, channel="email")
        return rec

    def import_verdict(self, rec, candidate):
        return hygiene.check(candidate, hygiene.index([rec], workspace=WS))


class StaleEligibilityIsRecheckedNotTrusted(LifecycleTest):

    def test_fresh_at_import_then_replies_before_the_send(self):
        """Monday fresh, Tuesday replies, Wednesday must not send."""
        rec = self.record()
        monday = self.import_verdict(rec, {"email": "sarah@acme.test",
                                           "domain": "acme.test"})
        self.assertEqual(monday["verdict"], hygiene.FRESH)

        self.classified_reply(rec, SARAH, ap.NEGATIVE)

        blocked = eligibility._replied(rec, self.contact(rec, SARAH))
        self.assertIsNotNone(blocked,
                             "an import-time verdict authorised a send")

    def test_fresh_at_import_then_the_company_asks_to_be_removed(self):
        rec = self.record()
        self.assertEqual(
            self.import_verdict(rec, {"email": "sarah@acme.test",
                                      "domain": "acme.test"})["verdict"],
            hygiene.FRESH)

        self.classified_reply(rec, JOHN, ap.ACCOUNT_DNC)

        self.assertEqual(
            eligibility._paused(rec, self.contact(rec, SARAH)),
            eligibility.BLOCKED_ACCOUNT_SUPPRESSED)

    def test_the_import_verdict_itself_changes_once_history_exists(self):
        """Re-importing the same list tomorrow gives a different answer."""
        rec = self.record()
        before = self.import_verdict(rec, {"email": "john@acme.test"})
        self.classified_reply(rec, JOHN, ap.UNSUBSCRIBE)
        after = self.import_verdict(rec, {"email": "john@acme.test"})
        self.assertEqual(before["verdict"], hygiene.FRESH)
        self.assertEqual(after["verdict"], hygiene.SUPPRESSED_CONTACT)


class AReplyInOneCampaignReachesAnother(LifecycleTest):
    """Canonical state sits above provider campaigns, so it has to."""

    def test_a_reply_recorded_anywhere_blocks_the_same_person_everywhere(self):
        rec = self.record()
        rec["campaign_ids"] = ["campaign-a", "campaign-b"]
        self.classified_reply(rec, JOHN, ap.UNSUBSCRIBE)
        self.assertEqual(eligibility._replied(rec, self.contact(rec, JOHN)),
                         eligibility.BLOCKED_UNSUBSCRIBED)

    def test_an_account_dnc_reaches_every_campaign_at_that_company(self):
        rec = self.record()
        rec["campaign_ids"] = ["campaign-a", "campaign-b"]
        self.classified_reply(rec, JOHN, ap.ACCOUNT_DNC)
        for key in (JOHN, SARAH):
            self.assertEqual(eligibility._paused(rec, self.contact(rec, key)),
                             eligibility.BLOCKED_ACCOUNT_SUPPRESSED, key)

    def test_a_negative_reply_does_not_reach_the_other_campaign(self):
        """Cross-campaign suppression is the policy's decision, not a blanket."""
        rec = self.record()
        self.classified_reply(rec, JOHN, ap.NEGATIVE)
        self.assertIsNone(eligibility._paused(rec, self.contact(rec, SARAH)))
        self.assertIsNone(eligibility._replied(rec, self.contact(rec, SARAH)))


class TheSameContactAcrossSeveralLists(LifecycleTest):
    """Three CSVs, one person. Provenance is kept; identity is not doubled."""

    def test_the_same_email_in_three_files_matches_one_history(self):
        rec = self.record()
        self.classified_reply(rec, JOHN, ap.NOT_NOW)
        index = hygiene.index([rec], workspace=WS)
        for source in ("august-uk.csv", "founder-list.csv", "icp.csv"):
            out = hygiene.check({"email": "john@acme.test",
                                 "domain": "acme.test",
                                 "source": source}, index)
            self.assertEqual(out["verdict"], hygiene.FUTURE_FOLLOW_UP, source)
            self.assertEqual(len(out["matched"]), 1, source)

    def test_a_new_decision_maker_at_a_worked_account_is_classified(self):
        """Not deleted. The brief is explicit about this one."""
        rec = self.record()
        self.classified_reply(rec, JOHN, ap.POSITIVE)
        out = hygiene.check({"email": "michael@acme.test",
                             "domain": "acme.test"},
                            hygiene.index([rec], workspace=WS))
        self.assertEqual(out["action"], hygiene.HOLD)
        self.assertNotEqual(out["action"], hygiene.SUPPRESS)
        self.assertIn("John Smith", out["why"])


if __name__ == "__main__":
    unittest.main()
