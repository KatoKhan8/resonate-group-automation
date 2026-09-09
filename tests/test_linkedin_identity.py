"""The LinkedIn URL as an identity key, and what happens when it cannot answer.

HeyReach's inbox carries none of our identifiers - `customFields` is empty on
every conversation, and `/lead/GetLead` exposes no custom fields either. The
profile URL is what correlates a reply to a record, so its canonical form is a
safety property: collapse two spellings of one person or you miss a reply and
keep sequencing someone who answered; merge two people and you pause the wrong
company.
"""
import unittest

from src import cadence, events, linkedin
from tests.campaignbase import CampaignTest, contact

ONE = "https://www.linkedin.com/in/jan-novak"


class TestOneProfileManySpellings(unittest.TestCase):
    def test_every_equivalent_form_collapses_to_one(self):
        for spelling in (
            "https://www.linkedin.com/in/jan-novak",
            "http://www.linkedin.com/in/jan-novak",
            "https://www.linkedin.com/in/jan-novak/",
            "https://linkedin.com/in/jan-novak",
            "https://LinkedIn.com/in/jan-novak",
            "https://WWW.LINKEDIN.COM/IN/JAN-NOVAK",
            "https://de.linkedin.com/in/jan-novak",
            "https://uk.linkedin.com/in/jan-novak/",
            "https://www.linkedin.com/in/Jan-Novak",
            "https://www.linkedin.com/in/jan-novak?utm_source=newsletter",
            "https://www.linkedin.com/in/jan-novak?trk=abc&originalSubdomain=de",
            "https://www.linkedin.com/in/jan-novak#experience",
            "https://www.linkedin.com/in/jan-novak/detail/contact-info/",
            "www.linkedin.com/in/jan-novak",
            "linkedin.com/in/jan-novak/",
            "  https://www.linkedin.com/in/jan-novak  ",
            "jan-novak",
        ):
            self.assertEqual(linkedin.canonical(spelling), ONE, spelling)

    def test_a_trailing_slash_alone(self):
        self.assertEqual(linkedin.canonical(ONE + "/"), ONE)

    def test_a_query_string_alone(self):
        self.assertEqual(linkedin.canonical(ONE + "?trk=x"), ONE)

    def test_a_fragment_alone(self):
        self.assertEqual(linkedin.canonical(ONE + "#about"), ONE)

    def test_host_casing_alone(self):
        self.assertEqual(linkedin.canonical("https://LINKEDIN.com/in/jan-novak"), ONE)

    def test_path_casing_alone(self):
        self.assertEqual(linkedin.canonical("https://www.linkedin.com/IN/jan-novak"),
                         ONE)

    def test_percent_encoding_is_decoded(self):
        self.assertEqual(linkedin.canonical("https://www.linkedin.com/in/jan%2Dnovak"),
                         ONE)

    def test_the_pub_form_is_recognised(self):
        self.assertEqual(linkedin.canonical("https://www.linkedin.com/pub/jan-novak"),
                         ONE)


class TestDifferentPeopleStayDifferent(unittest.TestCase):
    def test_two_actual_profiles_never_merge(self):
        a = linkedin.canonical("https://www.linkedin.com/in/jan-novak")
        b = linkedin.canonical("https://www.linkedin.com/in/jan-novak-2")
        self.assertNotEqual(a, b)

    def test_a_numeric_suffix_is_part_of_someones_identity(self):
        """LinkedIn appends one when a vanity is taken. It is not noise."""
        for other in ("jan-novak-2", "jan-novak-1a2b3c", "jan-novakova",
                      "jannovak", "jan-novak-jr"):
            self.assertNotEqual(linkedin.canonical(f"https://linkedin.com/in/{other}"),
                                ONE, other)

    def test_a_near_miss_is_never_a_match(self):
        """The behavioural statement of "no fuzzy matching": profiles that
        merely look similar stay separate, however close they get."""
        near = ["jan-novak2", "jan-nova", "jan-novakk", "jan_novak",
                "jan-novak-", "-jan-novak", "jannovak", "jan-novak-abc123"]
        for other in near:
            self.assertFalse(
                linkedin.same_profile(ONE, f"https://linkedin.com/in/{other}"),
                other)

    def test_no_similarity_library_is_imported(self):
        import inspect
        source = inspect.getsource(linkedin)
        for banned in ("import difflib", "SequenceMatcher", "levenshtein",
                       "rapidfuzz", "thefuzz"):
            self.assertNotIn(banned, source, banned)

    def test_same_profile_is_exact_not_approximate(self):
        self.assertTrue(linkedin.same_profile(ONE, ONE + "/?trk=x"))
        self.assertFalse(linkedin.same_profile(ONE, ONE + "-2"))


class TestWhatIsNotAProfile(unittest.TestCase):
    def test_a_company_page_is_not_a_profile(self):
        self.assertIsNone(linkedin.canonical(
            "https://www.linkedin.com/company/acme"))

    def test_another_host_is_not_a_profile(self):
        self.assertIsNone(linkedin.canonical("https://example.com/in/jan-novak"))
        self.assertIsNone(linkedin.canonical("https://linkedin.com.evil.test/in/x"))

    def test_junk_is_none_rather_than_an_exception(self):
        for junk in ("", "   ", None, 123, [], "not a url",
                     "https://www.linkedin.com/feed/", "https://linkedin.com/in/"):
            self.assertIsNone(linkedin.canonical(junk), repr(junk))


class TestTheIndex(unittest.TestCase):
    def test_it_maps_a_canonical_url_to_its_contact(self):
        recs = [{"id": "r1", "contacts": [{"key": "c1", "linkedin": ONE + "/"}]}]
        found = linkedin.index(recs)
        self.assertIn(ONE, found)
        self.assertEqual(found[ONE][1]["key"], "c1")

    def test_a_url_two_people_share_is_dropped_rather_than_resolved(self):
        recs = [{"id": "r1", "contacts": [{"key": "c1", "linkedin": ONE}]},
                {"id": "r2", "contacts": [{"key": "c2", "linkedin": ONE}]}]
        self.assertEqual(linkedin.index(recs), {})


class TestInboundCorrelation(CampaignTest):
    def records(self, url=ONE):
        recs = self.seed_records()
        recs[0]["contacts"] = [contact("acme-champ", "Champ", "champ@acme.test",
                                       linkedin=url)]
        return recs

    def test_a_reply_matches_however_the_url_is_spelled(self):
        recs = self.records()
        for spelling in ("https://linkedin.com/in/Jan-Novak/",
                         "https://de.linkedin.com/in/jan-novak?trk=x",
                         "jan-novak"):
            event = events.neutral(type=events.REPLY_RECEIVED, channel="linkedin",
                                   linkedin=spelling)
            self.assertEqual((events.match_record(recs, event) or {}).get("id"),
                             "acme", spelling)

    def test_a_different_profile_does_not_match(self):
        recs = self.records()
        event = events.neutral(type=events.REPLY_RECEIVED, channel="linkedin",
                               linkedin="https://www.linkedin.com/in/jan-novak-2")
        self.assertIsNone(events.match_record(recs, event))

    def test_an_ambiguous_url_is_held_rather_than_guessed(self):
        recs = self.seed_records()
        for rec in recs:
            rec["contacts"] = [contact(f"{rec['id']}-c", "Person",
                                       f"p@{rec['domain']}", linkedin=ONE)]
        event = events.neutral(type=events.REPLY_RECEIVED, channel="linkedin",
                               linkedin=ONE)
        self.assertIsNone(events.match_record(recs, event))
        for rec in recs:
            self.assertFalse(rec.get("paused"))

    def test_an_event_with_no_usable_identity_matches_nothing(self):
        recs = self.records()
        event = events.neutral(type=events.REPLY_RECEIVED, channel="linkedin",
                               linkedin="https://www.linkedin.com/feed/")
        self.assertIsNone(events.match_record(recs, event))


class TestDayEightNeverAssumesAcceptance(CampaignTest):
    """HeyReach exposes no connection-accepted signal, confirmed live. The
    day-8 step is gated on a real acceptance event, so with no signal it simply
    never becomes eligible - which is the safe outcome and must stay that way.
    """

    def test_day_eight_requires_an_acceptance_event(self):
        spec = next(s for s in cadence.STEPS if s["key"] == "day8")
        self.assertEqual(spec.get("requires"), cadence.ACCEPT_EVENT)

    def test_without_an_acceptance_it_waits_rather_than_sending(self):
        recs = self.seed_records()
        self.draft_everything(recs)
        timeline = cadence.build(recs[0], self.config, recs=recs)
        day8 = timeline["contacts"]["acme-champ"]["day8"]
        self.assertEqual(day8["status"], "waiting")

    def test_it_is_never_eligible_no_matter_how_much_else_is_approved(self):
        recs = self.seed_records()
        self.draft_everything(recs)
        self.approve_drafts(recs)
        timeline = cadence.build(recs[0], self.config, recs=recs)
        self.assertNotEqual(timeline["contacts"]["acme-champ"]["day8"]["status"],
                            "eligible")

    def test_a_real_acceptance_event_is_what_unlocks_it(self):
        recs = self.seed_records()
        self.draft_everything(recs)
        cadence.record_event(recs[0], "connection_accepted",
                             contact_key="acme-champ")
        timeline = cadence.build(recs[0], self.config, recs=recs)
        self.assertNotEqual(timeline["contacts"]["acme-champ"]["day8"]["status"],
                            "waiting")

    def test_a_follower_count_is_never_read_as_acceptance(self):
        """correspondentProfile.connections is an integer. It is not a status."""
        from src import adapters
        from src.providers import heyreach
        self.assertFalse(heyreach.CONNECTION_STATUS_AVAILABLE)
        page = {"items": [{"id": "t", "linkedInAccountId": 1,
                           "correspondentProfile": {"connections": 12000,
                                                    "profileUrl": ONE},
                           "messages": [{"sender": "CORRESPONDENT", "body": "hi",
                                         "createdAt": "2026-08-26T10:00:00Z"}]}]}
        kinds = {e["type"] for e in adapters.from_heyreach(page)}
        self.assertNotIn(events.LINKEDIN_CONNECTED, kinds)


if __name__ == "__main__":
    unittest.main()
