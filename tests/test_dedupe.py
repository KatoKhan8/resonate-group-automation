"""Recognising one person twice, and refusing to guess.

The tests that matter most are the ones asserting what does NOT happen: two
people with the same name are not merged, two clients targeting the same person
is not a duplicate unless somebody says so, and nothing is ever deleted.
"""
import unittest

from src import dedupe, eligibility, store
from tests.campaignbase import CampaignTest, contact

PROFILE = "https://www.linkedin.com/in/jan-novak"


def rec(rid, client="demo", company=None, domain=None, contacts=()):
    record = store.new_record(rid, "cold", client, company or f"{rid} Co",
                              domain or f"{rid}.test")
    record["contacts"] = list(contacts)
    return record


class TestIdentity(unittest.TestCase):
    def test_an_email_is_normalised_by_case_only(self):
        self.assertEqual(dedupe.normalise_email("  John@Example.TEST "),
                         "john@example.test")

    def test_plus_addressing_is_not_stripped(self):
        """Same mailbox on Gmail, not everywhere. A wrong merge suppresses a
        real person, so this stays conservative."""
        self.assertNotEqual(dedupe.normalise_email("john+a@example.test"),
                            dedupe.normalise_email("john@example.test"))

    def test_junk_is_none(self):
        for junk in ("", None, "not-an-address", "@", 5):
            self.assertIsNone(dedupe.normalise_email(junk), repr(junk))

    def test_provider_ids_are_namespaced_so_they_cannot_collide(self):
        ids = dedupe.provider_ids({"contactout_id": 7, "heyreach_lead_id": 7})
        self.assertEqual(ids, ["contactout_id:7", "heyreach_lead_id:7"])

    def test_a_contact_with_no_strong_identifier_has_no_identity(self):
        self.assertIsNone(dedupe.identity_of({"id": "r"}, {"name": "Jan Novak"}))

    def test_email_is_preferred_over_linkedin(self):
        identity = dedupe.identity_of(
            {"id": "r"}, {"email": "a@b.test", "linkedin": PROFILE})
        self.assertTrue(identity.startswith("email:"))


class TestStrongDuplicates(CampaignTest):
    def test_the_same_email_twice_in_one_batch(self):
        records = [rec("a", contacts=[contact("c1", "One", "same@x.test")]),
                   rec("b", contacts=[contact("c2", "Two", "same@x.test")])]
        findings = dedupe.find(records, dedupe.BATCH)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["kind"], dedupe.BY_EMAIL)
        self.assertTrue(findings[0]["strong"])

    def test_the_same_profile_twice_however_it_is_spelled(self):
        records = [rec("a", contacts=[contact("c1", "One", "a@x.test",
                                              linkedin=PROFILE)]),
                   rec("b", contacts=[contact("c2", "Two", "b@x.test",
                                              linkedin=PROFILE + "/?trk=x")])]
        findings = dedupe.find(records, dedupe.BATCH)
        self.assertTrue(any(f["kind"] == dedupe.BY_LINKEDIN for f in findings))

    def test_the_same_person_through_two_domains(self):
        records = [rec("a", domain="company.test",
                       contacts=[contact("c1", "One", "jan@company.test")]),
                   rec("b", domain="company-group.test",
                       contacts=[contact("c2", "One", "jan@company.test")])]
        self.assertTrue(dedupe.find(records, dedupe.BATCH))

    def test_the_same_provider_lead_id(self):
        left = contact("c1", "One", "a@x.test")
        right = contact("c2", "Two", "b@y.test")
        left["heyreach_lead_id"] = 4242
        right["heyreach_lead_id"] = 4242
        records = [rec("a", contacts=[left]), rec("b", contacts=[right])]
        findings = dedupe.find(records, dedupe.BATCH)
        self.assertTrue(any(f["kind"] == dedupe.BY_PROVIDER_ID for f in findings))

    def test_a_contact_does_not_collide_with_itself(self):
        records = [rec("a", contacts=[contact("c1", "One", "a@x.test")])]
        self.assertEqual([f for f in dedupe.find(records, dedupe.BATCH)
                          if f["strong"]], [])


class TestNothingIsGuessedOrDeleted(CampaignTest):
    def test_two_people_with_one_name_are_not_merged(self):
        records = [rec("a", company="Novak Consulting",
                       contacts=[contact("c1", "Jan Novak", "jan@a.test")]),
                   rec("b", company="Novak Consulting",
                       contacts=[contact("c2", "Jan Novak", "jan@b.test")])]
        findings = dedupe.find(records, dedupe.BATCH)
        strong = [f for f in findings if f["strong"]]
        self.assertEqual(strong, [], "a name is not identity")
        weak = [f for f in findings if f["kind"] == dedupe.POSSIBLE]
        self.assertEqual(len(weak), 1, "it is flagged for a human instead")

    def test_a_possible_match_never_sets_duplicate_of(self):
        records = [rec("a", company="Novak Consulting",
                       contacts=[contact("c1", "Jan Novak", "jan@a.test")]),
                   rec("b", company="Novak Consulting GmbH",
                       contacts=[contact("c2", "Jan Novak", "jan@b.test")])]
        dedupe.mark(records, dedupe.find(records, dedupe.BATCH))
        target = records[1]["contacts"][0]
        self.assertIsNone(target.get("duplicate_of"))
        self.assertIn("possible_duplicate", target)

    def test_a_possible_match_does_not_block_anything(self):
        records = [rec("a", company="Novak Consulting",
                       contacts=[contact("c1", "Jan Novak", "jan@a.test")]),
                   rec("b", company="Novak Consulting",
                       contacts=[contact("c2", "Jan Novak", "jan@b.test")])]
        dedupe.mark(records, dedupe.find(records, dedupe.BATCH))
        self.assertFalse(dedupe.is_duplicate(records[1]["contacts"][0]))

    def test_marking_deletes_nothing(self):
        records = [rec("a", contacts=[contact("c1", "One", "same@x.test")]),
                   rec("b", contacts=[contact("c2", "Two", "same@x.test")])]
        before = [len(r["contacts"]) for r in records]
        dedupe.mark(records, dedupe.find(records, dedupe.BATCH))
        self.assertEqual([len(r["contacts"]) for r in records], before)

    def test_the_audit_fields_are_written(self):
        records = [rec("a", contacts=[contact("c1", "One", "same@x.test")]),
                   rec("b", contacts=[contact("c2", "Two", "same@x.test")])]
        dedupe.mark(records, dedupe.find(records, dedupe.BATCH))
        marked = records[1]["contacts"][0]
        for field in ("duplicate_of", "duplicate_scope", "duplicate_reason"):
            self.assertIn(field, marked, field)

    def test_no_module_merges_contacts(self):
        import inspect
        source = inspect.getsource(dedupe)
        for banned in ("def merge", "contacts.remove", "del contacts",
                       "SequenceMatcher", "difflib"):
            self.assertNotIn(banned, source, banned)


class TestScopes(CampaignTest):
    def two_clients(self):
        return [rec("a", client="demo",
                    contacts=[contact("c1", "One", "same@x.test")]),
                rec("b", client="productive",
                    contacts=[contact("c2", "One", "same@x.test")])]

    def test_cross_client_is_off_by_default(self):
        self.assertFalse(dedupe.DEFAULTS["cross_client"])

    def test_two_clients_are_not_a_batch_duplicate(self):
        findings = dedupe.find(self.two_clients(), dedupe.BATCH)
        self.assertEqual([f for f in findings if f["strong"]], [])

    def test_two_clients_are_found_when_that_scope_is_asked_for(self):
        findings = dedupe.find(self.two_clients(), dedupe.CROSS_CLIENT)
        self.assertTrue([f for f in findings if f["strong"]])

    def test_the_scope_is_recorded_on_the_finding(self):
        findings = dedupe.find(self.two_clients(), dedupe.CROSS_CLIENT)
        self.assertEqual(findings[0]["scope"], dedupe.CROSS_CLIENT)

    def test_every_scope_is_named(self):
        for scope in dedupe.SCOPES:
            self.assertIsInstance(scope, str)


class TestCompanyCollision(CampaignTest):
    def test_www_and_mail_prefixes_are_the_same_site(self):
        self.assertTrue(dedupe.same_company("www.company.test",
                                            "company.test"))
        self.assertTrue(dedupe.same_company("mail.company.test",
                                            "company.test"))

    def test_a_different_tld_is_not_automatically_the_same_company(self):
        """company.test and company-uk.test are frequently separate entities
        with separate buyers. Merging them would silently halve a campaign."""
        self.assertFalse(dedupe.same_company("company.test", "company-uk.test"))

    def test_two_records_on_one_domain_are_flagged(self):
        records = [rec("a", domain="company.test"),
                   rec("b", domain="www.company.test")]
        findings = dedupe.company_collisions(records)
        self.assertTrue(any(f["kind"] == "same_domain" for f in findings))

    def test_a_differing_mail_domain_is_flagged_not_merged(self):
        record = rec("a", domain="company.test")
        record["company_facts"] = {"email_domain": "company-mail.test"}
        findings = dedupe.company_collisions([record])
        self.assertTrue(any(f["kind"] == "mail_domain_differs" for f in findings))
        self.assertIn("review", findings[0]["reason"])


class TestDuplicatesBlockSending(CampaignTest):
    def test_a_marked_duplicate_cannot_be_sent_to(self):
        recs = self.seed_records()
        rec_a = recs[0]
        rec_a["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        self.draft_everything(recs)
        self.approve_drafts(recs)
        rec_a["contacts"][0]["duplicate_of"] = {"record_id": "other",
                                                "contact_key": "x"}
        decision = eligibility.decide(rec_a, rec_a["contacts"][0], "day1",
                                      recs=recs, config=self.config)
        self.assertFalse(decision.eligible)
        self.assertIn(eligibility.BLOCKED_DUPLICATE, decision["reasons"])

    def test_a_possible_duplicate_does_not_block(self):
        recs = self.seed_records()
        rec_a = recs[0]
        rec_a["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test")]
        self.draft_everything(recs)
        self.approve_drafts(recs)
        rec_a["contacts"][0]["possible_duplicate"] = {"of": {}, "reason": "name"}
        decision = eligibility.decide(rec_a, rec_a["contacts"][0], "day1",
                                      recs=recs, config=self.config)
        self.assertNotIn(eligibility.BLOCKED_DUPLICATE, decision["reasons"])


if __name__ == "__main__":
    unittest.main()
