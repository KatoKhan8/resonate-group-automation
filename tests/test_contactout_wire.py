"""The ContactOut wire contract, as observed against the live API.

Recorded 2026-08-26 from a one-credit validation run against a domain the
operator owns. The payloads below are that run's real structure with the
identifying values replaced: the company is fictional, the domain is a .test
one, and the logo hash and follower count are gone. What is kept is exactly the
shape, because the shape is what these tests exist to pin.

Two assumptions this replaced, both of which had the adapter returning nothing
useful in production while every offline test passed:

  1. the routes were the MCP *tool* names ("/v1/people-count"), which are not
     REST paths. Every call 404ed.
  2. the answers were assumed to arrive in a {"status", "data"} envelope. They
     do not: people/count is flat, and domain/enrich keys its companies by the
     domain that was requested.
"""
import unittest

from src.providers import contactout
from tests.base import ProviderTest

# Real structure, fictional values.
COUNT = {
    "status_code": 200,
    "total_results": 7,
    "estimated_personal_emails": 1,
    "estimated_work_emails": 7,
    "estimated_phones": 1,
}

ENRICH = {
    "status_code": 200,
    "companies": {
        "mine.test": {
            "li_vanity": "https://www.linkedin.com/company/example",
            "name": "Example Group",
            "domain": "mine.test",
            "description": "",
            "website": "https://www.mine.test",
            "logo_url": "https://images.contactout.com/companies/redacted",
            "type": "",
            "headquarter": "",
            "country": "",
            "size": 2,
            "founded_at": 0,
            "locations": [],
            "industry": "IT Services and IT Consulting",
            "specialties": [],
            "revenue": "N/A",
            "employees": 17,
            "followers": 0,
            "funding": None,
            "technologies": [],
        }
    },
}


class Wire:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        import json
        self.calls.append({"method": method, "url": url, "body": body})
        return 200, json.dumps(self.payload)


class WireTest(ProviderTest):
    def wire(self, payload):
        w = Wire(payload)
        self.providers.set_transport(w)
        return w


class TestTheRoutes(ProviderTest):
    """The paths are REST routes, not the names of the MCP tools."""

    def test_every_operation_has_an_explicit_route(self):
        for name in ("people-count", "people-search", "decision-makers",
                     "email-verifier", "company-information-from-domain"):
            self.assertIn(name, contactout.ROUTES, name)

    def test_the_routes_are_the_ones_the_api_actually_serves(self):
        self.assertEqual(contactout.ROUTES["people-count"],
                         ("POST", "/people/count"))
        self.assertEqual(contactout.ROUTES["company-information-from-domain"],
                         ("POST", "/domain/enrich"))
        self.assertEqual(contactout.ROUTES["people-search"],
                         ("POST", "/people/search"))
        self.assertEqual(contactout.ROUTES["decision-makers"],
                         ("GET", "/people/decision-makers"))
        self.assertEqual(contactout.ROUTES["email-verifier"],
                         ("GET", "/email/verify"))

    def test_no_route_is_the_bare_operation_name(self):
        """The 404 that started all this: "/v1/people-count" is not a route."""
        for name, (_, path) in contactout.ROUTES.items():
            self.assertNotEqual(path, f"/{name}", name)

    def test_an_operation_without_a_route_is_refused_not_guessed(self):
        with self.assertRaises(contactout.ProviderError):
            contactout.call("no-such-operation")


class TestPeopleCount(WireTest):
    def test_the_real_response_is_flat_with_no_data_envelope(self):
        wire = self.wire(COUNT)
        got = contactout.people_count(domain="mine.test")
        self.assertEqual(got, {"query": "mine.test", "profiles": 7, "mobiles": 1})
        self.assertEqual(wire.calls[0]["method"], "POST")
        self.assertTrue(wire.calls[0]["url"].endswith("/people/count"))

    def test_the_filters_travel_in_the_body(self):
        wire = self.wire(COUNT)
        contactout.people_count(job_title="Founder", domain="mine.test")
        self.assertEqual(wire.calls[0]["body"],
                         {"job_title": ["Founder"], "domain": ["mine.test"]})

    def test_the_count_reads_total_results_not_a_profiles_key(self):
        self.wire(COUNT)
        self.assertEqual(contactout.people_count(domain="mine.test")["profiles"], 7)

    def test_the_estimates_we_do_not_keep_stay_out_of_the_trim(self):
        self.wire(COUNT)
        got = contactout.people_count(domain="mine.test")
        for ignored in ("estimated_personal_emails", "estimated_work_emails",
                        "status_code"):
            self.assertNotIn(ignored, got)


class TestCompanyFromDomain(WireTest):
    def trimmed(self):
        self.wire(ENRICH)
        return contactout.company_info("mine.test")

    def test_the_company_is_found_under_the_domain_it_was_asked_for(self):
        self.assertEqual(self.trimmed()["name"], "Example Group")

    def test_the_request_posts_a_domains_array(self):
        wire = self.wire(ENRICH)
        contactout.company_info("mine.test")
        self.assertEqual(wire.calls[0]["method"], "POST")
        self.assertTrue(wire.calls[0]["url"].endswith("/domain/enrich"))
        self.assertEqual(wire.calls[0]["body"], {"domains": ["mine.test"]})

    def test_the_head_count_comes_from_employees_not_the_size_bucket(self):
        """size read 2 where employees read 17. size is a bucket code."""
        self.assertEqual(self.trimmed()["employees"], 17)

    def test_a_founding_year_is_read_from_founded_at(self):
        self.wire(dict(ENRICH))
        payload = {"status_code": 200,
                   "companies": {"mine.test": dict(ENRICH["companies"]["mine.test"],
                                                   founded_at=2016)}}
        self.wire(payload)
        self.assertEqual(contactout.company_info("mine.test")["founded"], 2016)

    def test_a_zero_founding_year_is_absent_rather_than_the_year_zero(self):
        self.assertIsNone(self.trimmed()["founded"])

    def test_the_literal_n_a_revenue_is_absent_rather_than_a_string(self):
        self.assertIsNone(self.trimmed()["revenue"])

    def test_offices_are_read_from_locations(self):
        payload = {"status_code": 200,
                   "companies": {"mine.test": dict(ENRICH["companies"]["mine.test"],
                                                   locations=["Zagreb", "London"])}}
        self.wire(payload)
        self.assertEqual(contactout.company_info("mine.test")["offices"],
                         ["Zagreb", "London"])

    def test_the_stack_is_read_from_technologies(self):
        payload = {"status_code": 200,
                   "companies": {"mine.test": dict(ENRICH["companies"]["mine.test"],
                                                   technologies=["HubSpot"])}}
        self.wire(payload)
        self.assertEqual(contactout.company_info("mine.test")["stack"], ["HubSpot"])

    def test_contactout_never_supplies_a_mail_domain(self):
        """Section 9 trap 3 needs one and this provider does not have it."""
        self.assertIsNone(self.trimmed()["email_domain"])
        self.assertNotIn("email_domain", ENRICH["companies"]["mine.test"])

    def test_the_trim_keeps_its_eleven_fields_and_no_more(self):
        self.assertEqual(set(self.trimmed()),
                         {"name", "domain", "email_domain", "employees", "revenue",
                          "founded", "industry", "offices", "specialties", "stack",
                          # `li_vanity`, normalised. Kept from 2026-09-08: it is
                          # the address every Blitz search is keyed by, and while
                          # it was dropped a missing company LinkedIn URL could
                          # not be stated as a ContactOut miss - so the Blitz
                          # fallback behind it could never be justified either.
                          "linkedin"})

    def test_the_noise_the_response_carries_never_escapes(self):
        blob = str(self.trimmed())
        # `li_vanity` was on this list and is deliberately no longer: its
        # value is now kept as `linkedin`. It is removed rather than left to
        # pass on the technicality that the trim renames the key - a test that
        # calls a field noise while the code keeps it on purpose is a test
        # passing for the wrong reason, and the next person to read it would
        # believe the wrong thing.
        for noise in ("logo_url", "followers", "description",
                      "funding", "status_code", "images.contactout.com"):
            self.assertNotIn(noise, blob, noise)

    def test_an_empty_answer_does_not_become_a_company(self):
        self.wire({"status_code": 200, "companies": {}})
        got = contactout.company_info("mine.test")
        self.assertIsNone(got["name"])


# email-verifier, the real structure of two live 2026-09-07 exchanges against
# `GET /v1/email/verify?email=`: one catch-all domain the operator owns and one
# dead mailbox. Unlike people/count and domain/enrich, this route DOES nest its
# answer under `data`, and the verdict is the only field in it.
VERIFY_ACCEPT_ALL = {"status_code": 200, "data": {"status": "accept_all"}}
VERIFY_INVALID = {"status_code": 200, "data": {"status": "invalid"}}


class TestEmailVerifier(WireTest):
    """The route that 404ed for nine contacts out of nine, now answering.

    "/email-verifier/verify" was the MCP tool name with a verb bolted on; the
    REST route is "/email/verify". Both facts were established live, so both
    are pinned: the path here, the vocabulary below.
    """

    def test_the_verdict_is_read_from_the_nested_data_envelope(self):
        self.wire(VERIFY_ACCEPT_ALL)
        self.assertEqual(contactout.email_verifier("someone@mine.test"),
                         {"email": "someone@mine.test", "verdict": "accept_all"})

    def test_a_dead_mailbox_comes_back_invalid(self):
        self.wire(VERIFY_INVALID)
        self.assertEqual(
            contactout.email_verifier("gone@mine.test")["verdict"], "invalid")

    def test_the_address_travels_in_the_query_string_of_the_rest_route(self):
        wire = self.wire(VERIFY_ACCEPT_ALL)
        contactout.email_verifier("someone@mine.test")
        self.assertEqual(wire.calls[0]["method"], "GET")
        self.assertIn("/email/verify?email=", wire.calls[0]["url"])
        self.assertNotIn("email-verifier", wire.calls[0]["url"])
        self.assertIsNone(wire.calls[0]["body"])

    def test_a_verdict_outside_the_vocabulary_becomes_unknown(self):
        """Not free text downstream: a word nobody has a rule for is unknown."""
        self.wire({"status_code": 200, "data": {"status": "risky"}})
        self.assertEqual(
            contactout.email_verifier("someone@mine.test")["verdict"], "unknown")

    def test_a_missing_verdict_becomes_unknown_rather_than_none(self):
        self.wire({"status_code": 200, "data": {}})
        self.assertEqual(
            contactout.email_verifier("someone@mine.test")["verdict"], "unknown")

    def test_every_live_verdict_is_in_the_declared_vocabulary(self):
        for payload in (VERIFY_ACCEPT_ALL, VERIFY_INVALID):
            self.assertIn(payload["data"]["status"], contactout.VERDICTS)


# decision-makers, real structure with every identifying value replaced.
# Confirmed live 2026-08-26: no data envelope, page/page_size/total_results
# live under `metadata`, and `profiles` is a MAP KEYED BY LINKEDIN URL, not a
# list. The company object embedded in each profile carries an email_domain,
# which is the field domain/enrich does not return at all.
DECISION_MAKERS = {
    "status_code": 200,
    "metadata": {"page": 1, "page_size": 25, "total_results": 1},
    "profiles": {
        "https://www.linkedin.com/in/example-person": {
            "full_name": "Example Person",
            "title": "Managing Director",
            "headline": "Managing Director at Example Group",
            "li_vanity": "example-person",
            "location": "Zagreb, Croatia",
            "country": "Croatia",
            "industry": "IT Services and IT Consulting",
            "seniority": "cxo",
            "job_function": "Operations",
            "work_status": None,
            "updated_at": "2026-01-01",
            "followers": 0,
            "summary": "",
            "profile_picture_url": "https://images.contactout.com/redacted",
            "experience": ["Managing Director at Example Group"],
            "education": [],
            "skills": [],
            "languages": [],
            "projects": [],
            "publications": [],
            "certifications": [],
            "volunteering_experiences": [],
            "contact_availability": {"work_email": True, "personal_email": False,
                                     "phone": False},
            "contact_info": {"emails": [], "work_emails": [], "personal_emails": [],
                             "phones": [], "work_email_status": None},
            "company": {"name": "Example Group", "domain": "mine.test",
                        "email_domain": "mail.mine.test", "employees": 17,
                        "industry": "IT Services and IT Consulting",
                        "linkedin_company_id": 0, "size": 2, "founded_at": 0,
                        "locations": [], "headquarter": "", "country": "",
                        "revenue": "N/A", "specialties": [], "type": "",
                        "url": "", "website": "https://www.mine.test",
                        "logo_url": "", "overview": "", "followers": 0,
                        "funding": None},
        }
    },
}


class TestDecisionMakers(WireTest):
    def people(self):
        self.wire(DECISION_MAKERS)
        return contactout.decision_makers("mine.test")

    def test_profiles_arrive_keyed_by_linkedin_url_not_as_a_list(self):
        self.assertIsInstance(DECISION_MAKERS["profiles"], dict)
        self.assertEqual(len(self.people()), 1)

    def test_the_person_is_trimmed_to_the_eight_agreed_fields(self):
        self.assertEqual(set(self.people()[0]),
                         {"name", "title", "company", "linkedin", "email",
                          "location", "seniority", "current"})

    def test_the_paging_metadata_is_nested_under_metadata(self):
        """It is not at the top level, which is where an earlier read looked."""
        self.assertIsNone(DECISION_MAKERS.get("total_results"))
        self.assertEqual(DECISION_MAKERS["metadata"]["page_size"], 25)

    def test_the_page_size_is_what_makes_a_cap_unenforceable(self):
        """25 per page, and no page-size parameter exists to lower it."""
        self.assertEqual(DECISION_MAKERS["metadata"]["page_size"], 25)

    def test_no_address_arrives_when_contact_info_was_not_bought(self):
        self.assertIsNone(self.people()[0]["email"])

    def test_current_is_never_populated_by_this_endpoint(self):
        """A phantom field: no `current` or `is_current` key exists on a
        profile, so the trim has always produced None here. Recorded rather
        than quietly dropped, because the record schema still names it."""
        profile = list(DECISION_MAKERS["profiles"].values())[0]
        self.assertNotIn("current", profile)
        self.assertNotIn("is_current", profile)
        self.assertIsNone(self.people()[0]["current"])

    def test_the_embedded_company_carries_the_mail_domain(self):
        """What domain/enrich does not return, this does. Section 9 trap 3."""
        profile = list(DECISION_MAKERS["profiles"].values())[0]
        self.assertEqual(profile["company"]["email_domain"], "mail.mine.test")

    def test_the_profile_noise_never_escapes_the_trim(self):
        blob = str(self.people())
        for noise in ("profile_picture_url", "contact_availability", "summary",
                      "volunteering", "followers", "updated_at", "job_function",
                      "images.contactout.com"):
            self.assertNotIn(noise, blob, noise)


class TestTheAbsentMarkers(unittest.TestCase):
    def test_the_spellings_of_nothing_all_normalise_to_none(self):
        for value in ("", "  ", "N/A", "n/a", "None", "-", 0):
            self.assertIsNone(contactout._present(value), repr(value))

    def test_a_real_value_survives(self):
        self.assertEqual(contactout._present("  Example Group  "), "Example Group")
        self.assertEqual(contactout._present(17), 17)


if __name__ == "__main__":
    unittest.main()
