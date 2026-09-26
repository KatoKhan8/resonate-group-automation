"""TASK-307: ContactOut email -> LinkedIn URL route.

The route is ``GET /v1/people/person?email=``, confirmed live 2026-09-26.
A hit returns 200 with ``{"profile": {"email": ..., "linkedin": ...}}``.
A miss returns 404 with ``{"message": "Not Found"}``. The 404 is a valid
outcome (no profile found), not a client error - which is why this does NOT
go through ``call()``: that function raises ProviderError on any 4xx.
"""
import json
import unittest

from src.providers import contactout
from tests.base import ProviderTest

HIT = {
    "status_code": 200,
    "profile": {
        "email": "satya@microsoft.com",
        "linkedin": "https://www.linkedin.com/in/satya-lokam-68b1307",
    },
}

MISS = {"message": "Not Found", "status_code": 404}


class Wire:
    def __init__(self, payload, status=None):
        self.payload = payload
        self.calls = []
        self._status = status

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "body": body})
        s = self._status if self._status is not None else (
            self.payload.get("status_code", 200) if isinstance(self.payload, dict) else 200
        )
        return s, json.dumps(self.payload)


class WireTest(ProviderTest):
    def wire(self, payload, status=None):
        w = Wire(payload, status)
        self.providers.set_transport(w)
        return w


class TestTheRoute(WireTest):
    def test_the_route_exists_in_ROUTES(self):
        self.assertIn("linkedin-url-from-email", contactout.ROUTES)

    def test_the_route_points_at_people_person(self):
        self.assertEqual(
            contactout.ROUTES["linkedin-url-from-email"],
            ("GET", "/people/person"))

    def test_the_function_exists(self):
        self.assertTrue(hasattr(contactout, "linkedin_from_email"))
        self.assertTrue(callable(contactout.linkedin_from_email))

    def test_the_route_is_not_the_bare_operation_name(self):
        _, path = contactout.ROUTES["linkedin-url-from-email"]
        self.assertNotEqual(path, "/linkedin-url-from-email")


class TestHit(WireTest):
    def test_a_hit_returns_the_linkedin_url(self):
        self.wire(HIT)
        got = contactout.linkedin_from_email("satya@microsoft.com")
        self.assertEqual(got, {
            "email": "satya@microsoft.com",
            "linkedin": "https://www.linkedin.com/in/satya-lokam-68b1307",
        })

    def test_the_request_is_a_GET_with_email_in_the_query(self):
        wire = self.wire(HIT)
        contactout.linkedin_from_email("satya@microsoft.com")
        self.assertEqual(wire.calls[0]["method"], "GET")
        self.assertIn("/people/person?email=", wire.calls[0]["url"])
        self.assertIn("satya%40microsoft.com", wire.calls[0]["url"])
        self.assertIsNone(wire.calls[0]["body"])

    def test_the_url_contains_people_person_not_linkedin_url_from_email(self):
        wire = self.wire(HIT)
        contactout.linkedin_from_email("satya@microsoft.com")
        self.assertIn("/people/person", wire.calls[0]["url"])
        self.assertNotIn("linkedin-url-from-email", wire.calls[0]["url"])

    def test_the_trim_keeps_only_email_and_linkedin(self):
        self.wire(HIT)
        got = contactout.linkedin_from_email("satya@microsoft.com")
        self.assertEqual(set(got), {"email", "linkedin"})

    def test_the_full_name_does_not_escape(self):
        """The /email/enrich endpoint returns fullName, headline, etc.
        The /people/person endpoint returns only email and linkedin, but
        if the response ever widens, the trim must keep it out."""
        self.wire({
            "status_code": 200,
            "profile": {
                "email": "satya@microsoft.com",
                "linkedin": "https://www.linkedin.com/in/satya-lokam-68b1307",
                "fullName": "Satya Lokam",
                "headline": "Principal Researcher",
            },
        })
        got = contactout.linkedin_from_email("satya@microsoft.com")
        self.assertNotIn("fullName", got)
        self.assertNotIn("headline", got)


class TestMiss(WireTest):
    def test_a_404_returns_none(self):
        self.wire(MISS)
        got = contactout.linkedin_from_email("nobody@nonexistent.test")
        self.assertIsNone(got)

    def test_a_404_does_not_raise(self):
        """A miss is not an error. This is the defect the task guards against."""
        self.wire(MISS)
        try:
            got = contactout.linkedin_from_email("nobody@nonexistent.test")
        except contactout.ProviderError:
            self.fail("linkedin_from_email raised on a 404 miss; "
                      "it should return None")

    def test_a_200_with_no_profile_returns_none(self):
        self.wire({"status_code": 200, "profile": {}})
        got = contactout.linkedin_from_email("someone@example.test")
        self.assertIsNone(got)

    def test_a_200_with_empty_linkedin_returns_none(self):
        self.wire({
            "status_code": 200,
            "profile": {"email": "someone@example.test", "linkedin": ""},
        })
        got = contactout.linkedin_from_email("someone@example.test")
        self.assertIsNone(got)


class TestErrorHandling(WireTest):
    def test_a_401_raises_immediately(self):
        self.wire({"message": "Unauthorized"}, status=401)
        with self.assertRaises(contactout.ProviderError):
            contactout.linkedin_from_email("someone@example.test")

    def test_a_403_raises_immediately(self):
        self.wire({"message": "Forbidden"}, status=403)
        with self.assertRaises(contactout.ProviderError):
            contactout.linkedin_from_email("someone@example.test")

    def test_a_500_retries_then_raises(self):
        self.wire({"message": "Internal Server Error"}, status=500)
        with self.assertRaises(contactout.ProviderError):
            contactout.linkedin_from_email(
                "someone@example.test", _sleep=lambda _: None)

    def test_a_429_retries_then_raises(self):
        self.wire({"message": "Rate limit exceeded"}, status=429)
        with self.assertRaises(contactout.ProviderError):
            contactout.linkedin_from_email(
                "someone@example.test", _sleep=lambda _: None)

    def test_none_email_returns_none_without_calling(self):
        got = contactout.linkedin_from_email(None)
        self.assertIsNone(got)

    def test_empty_email_returns_none_without_calling(self):
        got = contactout.linkedin_from_email("")
        self.assertIsNone(got)

    def test_whitespace_is_trimmed(self):
        wire = self.wire(HIT)
        contactout.linkedin_from_email("  satya@microsoft.com  ")
        self.assertIn("satya%40microsoft.com", wire.calls[0]["url"])


class TestCostEntry(unittest.TestCase):
    def test_the_cost_is_in_the_provider_cost_dict(self):
        self.assertIn("linkedin-url-from-email", contactout.COST)

    def test_the_cost_is_in_the_enrich_cost_dict(self):
        from src import enrich
        self.assertIn("linkedin-url-from-email", enrich.COSTS)
        self.assertEqual(enrich.COSTS["linkedin-url-from-email"], 1)

    def test_the_call_stage_is_assigned(self):
        from src import enrich
        self.assertIn("linkedin-url-from-email", enrich.CALL_STAGE)


class TestClassifyFailure(unittest.TestCase):
    """classify_failure already exists; confirm it covers this route's errors."""

    def test_a_rate_limit_is_classified(self):
        self.assertEqual(
            contactout.classify_failure(429, "rate limit exceeded"),
            "contactout_rate_limited")

    def test_a_500_is_classified(self):
        self.assertEqual(
            contactout.classify_failure(500, "internal server error"),
            "contactout_error")

    def test_a_timeout_is_classified(self):
        self.assertEqual(
            contactout.classify_failure(None, "connection timed out"),
            "contactout_timeout")


if __name__ == "__main__":
    unittest.main()
