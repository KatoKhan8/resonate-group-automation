"""Two channels, two verdicts, and a contact that is never dropped for losing one.

The four cases in the brief are the four tests that matter here: behind a
gateway is LinkedIn-only, no verified address is LinkedIn-only, no usable
profile is email-only, both is multichannel. Neither is held, not deleted.
"""
import unittest

from src import channels, mx, verification
from tests.campaignbase import CampaignTest, contact

GOOGLE = ["aspmx.l.google.com"]
PROOFPOINT = ["mx1-us1.ppe-hosted.com"]
PROFILE = "https://www.linkedin.com/in/ann-smith"


class ChannelTest(CampaignTest):
    def person(self, email="ann@acme.test", linkedin=PROFILE, hosts=GOOGLE,
               verified=True, **extra):
        person = contact("acme-c0", "Ann Smith", email, linkedin=linkedin)
        # The helper fills in a default profile for None; these tests need the
        # absence itself, so it is set back explicitly.
        person["linkedin"] = linkedin
        # Two independent confirmations when verified: that is what the
        # default policy requires and therefore what a really-verified contact
        # carries. One provider used to be enough here only because the state
        # was written by hand and believed.
        if verified:
            evidence = [
                verification.result("contactout", verification.S_VALID, email,
                                    deliverable=True, safe_to_send=True),
                verification.result("deliverable", verification.S_VALID, email,
                                    deliverable=True, safe_to_send=True),
            ]
        else:
            evidence = [verification.result("deliverable",
                                            verification.S_UNKNOWN, email)]
        verification.apply(person, verification.decide(evidence), evidence)
        if email and hosts is not None:
            person["mx"] = mx.decide(hosts, mx.settings(self.config),
                                     domain="acme.test")
        person.update(extra)
        return person

    def rec(self, **extra):
        record = {"id": "acme", "client": "demo", "domain": "acme.test",
                  "company": "Acme", "state": "drafted", "contacts": []}
        record.update(extra)
        return record


class TestTheFourCases(ChannelTest):
    def test_verified_address_and_profile_is_multichannel(self):
        verdict = channels.evaluate(self.rec(), self.person(), self.config,
                                    suppressed=set())
        self.assertEqual(verdict["mode"], channels.MULTICHANNEL)
        self.assertTrue(verdict["email_eligible"])
        self.assertTrue(verdict["linkedin_eligible"])
        self.assertFalse(verdict["held"])

    def test_behind_a_gateway_is_linkedin_only(self):
        verdict = channels.evaluate(self.rec(), self.person(hosts=PROOFPOINT),
                                    self.config, suppressed=set())
        self.assertEqual(verdict["mode"], channels.LINKEDIN_ONLY)
        self.assertEqual(verdict["email_excluded_reason"],
                         "mx_protection:proofpoint")
        self.assertTrue(verdict["linkedin_eligible"])

    def test_no_verified_address_but_a_profile_is_linkedin_only(self):
        verdict = channels.evaluate(self.rec(), self.person(verified=False),
                                    self.config, suppressed=set())
        self.assertEqual(verdict["mode"], channels.LINKEDIN_ONLY)
        self.assertEqual(verdict["email_excluded_reason"],
                         channels.NOT_VERIFIED)

    def test_no_address_at_all_but_a_profile_is_linkedin_only(self):
        verdict = channels.evaluate(self.rec(),
                                    self.person(email=None, hosts=None),
                                    self.config, suppressed=set())
        self.assertEqual(verdict["mode"], channels.LINKEDIN_ONLY)
        self.assertEqual(verdict["email_excluded_reason"], channels.NO_ADDRESS)

    def test_a_verified_address_and_no_profile_is_email_only(self):
        verdict = channels.evaluate(self.rec(), self.person(linkedin=None),
                                    self.config, suppressed=set())
        self.assertEqual(verdict["mode"], channels.EMAIL_ONLY)
        self.assertEqual(verdict["linkedin_excluded_reason"],
                         channels.NO_PROFILE)

    def test_neither_channel_is_held_rather_than_dropped(self):
        verdict = channels.evaluate(self.rec(),
                                    self.person(email=None, hosts=None,
                                                linkedin=None),
                                    self.config, suppressed=set())
        self.assertEqual(verdict["mode"], channels.NONE)
        self.assertTrue(verdict["held"])
        # Both reasons present: a held contact must say what would fix it.
        self.assertTrue(verdict["email_excluded_reason"])
        self.assertTrue(verdict["linkedin_excluded_reason"])


class TestTheReasons(ChannelTest):
    def test_an_unsubscribe_closes_both_channels(self):
        person = self.person(unsubscribed={"at": "2026-08-01"})
        verdict = channels.evaluate(self.rec(), person, self.config,
                                    suppressed=set())
        self.assertEqual(verdict["mode"], channels.NONE)
        self.assertEqual(verdict["email_excluded_reason"],
                         channels.UNSUBSCRIBED)
        self.assertEqual(verdict["linkedin_excluded_reason"],
                         channels.UNSUBSCRIBED)

    def test_a_suppressed_domain_closes_both_channels(self):
        verdict = channels.evaluate(self.rec(), self.person(), self.config,
                                    suppressed={"acme.test"})
        self.assertEqual(verdict["mode"], channels.NONE)
        self.assertEqual(verdict["email_excluded_reason"], channels.SUPPRESSED)
        self.assertEqual(verdict["linkedin_excluded_reason"],
                         channels.SUPPRESSED)

    def test_a_company_page_url_is_not_a_profile(self):
        for url in ("https://www.linkedin.com/company/acme",
                    "https://www.linkedin.com/search/results/people/?q=x",
                    "https://example.test/ann"):
            verdict = channels.evaluate(self.rec(), self.person(linkedin=url),
                                        self.config, suppressed=set())
            self.assertFalse(verdict["linkedin_eligible"], url)

    def test_a_duplicate_is_not_approached_on_linkedin(self):
        person = self.person(duplicate_of={"record_id": "other",
                                           "contact_key": "x"})
        verdict = channels.evaluate(self.rec(), person, self.config,
                                    suppressed=set())
        self.assertEqual(verdict["linkedin_excluded_reason"],
                         channels.DUPLICATE)

    def test_every_reason_can_be_explained_to_a_human(self):
        for reason in channels.REASONS:
            self.assertTrue(channels.explain(reason))
            self.assertNotEqual(channels.explain(reason), reason)

    def test_an_mx_reason_can_be_explained_too(self):
        self.assertIn("Proofpoint", channels.explain("mx_protection:proofpoint"))
        self.assertIn("no MX", channels.explain("mx_no_mx"))

    def test_an_unknown_code_is_passed_through_rather_than_swallowed(self):
        self.assertEqual(channels.explain("something_new"), "something_new")


class TestNothingIsTrusted(ChannelTest):
    def test_a_tampered_verdict_on_the_contact_changes_nothing(self):
        person = self.person(hosts=PROOFPOINT)
        person["email_eligible"] = True
        person["channels"] = {"email_eligible": True, "mode": "multichannel"}
        verdict = channels.evaluate(self.rec(), person, self.config,
                                    suppressed=set())
        self.assertFalse(verdict["email_eligible"])

    def test_a_tampered_mx_status_does_not_open_the_channel(self):
        person = self.person(hosts=PROOFPOINT)
        person["mx"]["status"] = mx.KNOWN_ALLOWED
        person["mx"]["email_cadence_allowed"] = True
        person["mx"]["email_eligible"] = True
        verdict = channels.evaluate(self.rec(), person, self.config,
                                    suppressed=set())
        self.assertFalse(verdict["email_eligible"])
        self.assertEqual(verdict["email_excluded_reason"],
                         "mx_protection:proofpoint")

    def test_applying_to_a_record_stores_but_does_not_decide(self):
        rec = self.rec(contacts=[self.person(hosts=PROOFPOINT)])
        channels.apply_to_record(rec, self.config, suppressed=set())
        stored = rec["contacts"][0]
        self.assertFalse(stored["email_eligible"])
        self.assertEqual(stored["email_excluded_reason"],
                         "mx_protection:proofpoint")
        self.assertEqual(stored["channels"]["mode"], channels.LINKEDIN_ONLY)


class TestCoverage(ChannelTest):
    def batch(self):
        return [
            self.rec(id="a", contacts=[self.person()]),
            self.rec(id="b", contacts=[self.person(hosts=PROOFPOINT)]),
            self.rec(id="c", contacts=[self.person(linkedin=None)]),
            self.rec(id="d", contacts=[self.person(email=None, hosts=None,
                                                   linkedin=None)]),
        ]

    def test_the_modes_add_up_to_the_contact_count(self):
        result = channels.summarise(self.batch(), self.config,
                                    selected_only=False, suppressed=set())
        self.assertEqual(sum(result[mode] for mode in channels.MODES),
                         result["contacts"])

    def test_coverage_is_a_share_not_a_count(self):
        result = channels.summarise(self.batch(), self.config,
                                    selected_only=False, suppressed=set())
        self.assertEqual(result["email_coverage"], 0.5)
        self.assertEqual(result["linkedin_coverage"], 0.5)
        self.assertEqual(result["multichannel_coverage"], 0.25)

    def test_coverage_is_none_rather_than_zero_with_nothing_to_divide(self):
        result = channels.summarise([], self.config, suppressed=set())
        self.assertIsNone(result["email_coverage"])
        self.assertIsNone(result["multichannel_coverage"])

    def test_reasons_are_counted_per_channel(self):
        result = channels.summarise(self.batch(), self.config,
                                    selected_only=False, suppressed=set())
        self.assertEqual(result["reasons"]["email"]["mx_protection:proofpoint"], 1)
        self.assertEqual(result["reasons"]["linkedin"][channels.NO_PROFILE], 2)

    def test_it_calls_no_provider(self):
        channels.summarise(self.batch(), self.config, selected_only=False,
                           suppressed=set())
        self.assertEqual(self.cassette.calls, [])


if __name__ == "__main__":
    unittest.main()
