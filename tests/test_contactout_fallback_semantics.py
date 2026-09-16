"""TASK-207: an error is not a miss, and only a miss licenses a fallback.

Five ContactOut outcome classes, three of them transient. A transient
failure must never license paying a second provider for data ContactOut
has and was simply not asked properly. The tests prove this at the
waterfall seam (may_fall_back), at the adapter seam (classify_failure,
bounded retry), and at the telemetry seam (counters).
"""
import unittest

from src import enrich, waterfall
from src import providers
from src.providers import contactout


class TestOutcomeClasses(unittest.TestCase):
    """The five classes exist as named constants and every known reason
    maps to exactly one."""

    def test_five_classes_exist(self):
        self.assertEqual(waterfall.CONTACTOUT_CONFIRMED_MISS,
                         "contactout_confirmed_miss")
        self.assertEqual(waterfall.CONTACTOUT_CAPABILITY_UNAVAILABLE,
                         "contactout_capability_unavailable")
        self.assertEqual(waterfall.CONTACTOUT_ERROR, "contactout_error")
        self.assertEqual(waterfall.CONTACTOUT_TIMEOUT, "contactout_timeout")
        self.assertEqual(waterfall.CONTACTOUT_RATE_LIMITED,
                         "contactout_rate_limited")

    def test_every_known_reason_maps_to_a_class(self):
        for reason in enrich.FALLBACK_REASONS:
            cls = waterfall.classify(reason)
            self.assertIsNotNone(cls, f"{reason} has no class")
            self.assertIn(cls, (
                waterfall.CONTACTOUT_CONFIRMED_MISS,
                waterfall.CONTACTOUT_CAPABILITY_UNAVAILABLE,
                waterfall.CONTACTOUT_ERROR,
                waterfall.CONTACTOUT_TIMEOUT,
                waterfall.CONTACTOUT_RATE_LIMITED,
            ))

    def test_transient_reasons_map_to_their_own_classes(self):
        self.assertEqual(waterfall.classify(waterfall.CONTACTOUT_ERROR),
                         waterfall.CONTACTOUT_ERROR)
        self.assertEqual(waterfall.classify(waterfall.CONTACTOUT_TIMEOUT),
                         waterfall.CONTACTOUT_TIMEOUT)
        self.assertEqual(waterfall.classify(waterfall.CONTACTOUT_RATE_LIMITED),
                         waterfall.CONTACTOUT_RATE_LIMITED)

    def test_confirmed_miss_reasons_are_not_transient(self):
        for reason in (enrich.CONTACTOUT_NO_PEOPLE,
                       enrich.CONTACTOUT_NO_TARGET_PERSONA,
                       enrich.CONTACTOUT_RESULT_COLLISION,
                       enrich.CONTACTOUT_REBRAND_DETECTED,
                       enrich.DOMAIN_UNSTAFFED,
                       enrich.CONTACTOUT_INCOMPLETE,
                       enrich.CONTACTOUT_NO_COMPANY_LINKEDIN,
                       enrich.CONTACTOUT_MISSING_COMPANY_DATA):
            self.assertFalse(waterfall.is_transient(reason), reason)
            self.assertEqual(waterfall.classify(reason),
                             waterfall.CONTACTOUT_CONFIRMED_MISS)

    def test_capability_unavailable_reasons(self):
        self.assertEqual(
            waterfall.classify(enrich.PUBLIC_EVIDENCE_REQUIRED),
            waterfall.CONTACTOUT_CAPABILITY_UNAVAILABLE)
        self.assertEqual(
            waterfall.classify(enrich.CONTACTOUT_NO_EMAIL_DOMAIN),
            waterfall.CONTACTOUT_CAPABILITY_UNAVAILABLE)


class TestTransientRefused(unittest.TestCase):
    """An error, timeout or rate limit must NOT license a paid fallback.

    This is the core invariant: may_fall_back refuses every transient
    reason, regardless of which stage or provider is asked.
    """

    def test_error_refused_for_aiark(self):
        ok, why = waterfall.may_fall_back(
            "people_discovery", waterfall.AIARK,
            waterfall.CONTACTOUT_ERROR, "aiark-people-search")
        self.assertFalse(ok)
        self.assertIn("transient", why)

    def test_timeout_refused_for_aiark(self):
        ok, why = waterfall.may_fall_back(
            "people_discovery", waterfall.AIARK,
            waterfall.CONTACTOUT_TIMEOUT, "aiark-people-search")
        self.assertFalse(ok)
        self.assertIn("transient", why)

    def test_rate_limited_refused_for_aiark(self):
        ok, why = waterfall.may_fall_back(
            "people_discovery", waterfall.AIARK,
            waterfall.CONTACTOUT_RATE_LIMITED, "aiark-people-search")
        self.assertFalse(ok)
        self.assertIn("transient", why)

    def test_error_refused_for_blitz(self):
        ok, _ = waterfall.may_fall_back(
            "company_information", waterfall.BLITZ,
            waterfall.CONTACTOUT_ERROR, "blitz-company")
        self.assertFalse(ok)

    def test_timeout_refused_for_apify(self):
        ok, _ = waterfall.may_fall_back(
            "company_research", waterfall.APIFY,
            waterfall.CONTACTOUT_TIMEOUT, "apify-research")
        self.assertFalse(ok)

    def test_error_refused_for_deliverable(self):
        ok, _ = waterfall.may_fall_back(
            "email_verification", waterfall.DELIVERABLE,
            waterfall.CONTACTOUT_ERROR)
        self.assertFalse(ok)

    def test_confirmed_miss_permits_aiark(self):
        ok, _ = waterfall.may_fall_back(
            "people_discovery", waterfall.AIARK,
            enrich.CONTACTOUT_NO_PEOPLE, "aiark-people-search")
        self.assertTrue(ok)

    def test_confirmed_miss_permits_blitz(self):
        ok, _ = waterfall.may_fall_back(
            "company_information", waterfall.BLITZ,
            enrich.CONTACTOUT_NO_COMPANY_LINKEDIN, "blitz-domain-to-linkedin")
        self.assertTrue(ok)

    def test_capability_unavailable_permits_blitz(self):
        ok, _ = waterfall.may_fall_back(
            "company_information", waterfall.BLITZ,
            enrich.CONTACTOUT_NO_EMAIL_DOMAIN, "blitz-linkedin-to-domain")
        self.assertTrue(ok)

    def test_transient_reason_cannot_be_recorded_as_a_step(self):
        """record_step enforces may_fall_back; a transient reason raises."""
        rec = {"id": "test"}
        with self.assertRaises(waterfall.WaterfallViolation):
            waterfall.record_step(rec, "people_discovery", waterfall.AIARK,
                                  "aiark-people-search",
                                  reason=waterfall.CONTACTOUT_TIMEOUT)
        self.assertEqual(waterfall.ledger(rec), [],
                         "a refused step must leave no trace")


class TestClassifyFailure(unittest.TestCase):
    """The adapter classifies HTTP failures into the five outcome classes."""

    def test_429_is_rate_limited(self):
        self.assertEqual(contactout.classify_failure(429),
                         "contactout_rate_limited")

    def test_timeout_is_timeout(self):
        self.assertEqual(
            contactout.classify_failure(None, "TimeoutError: timed out"),
            "contactout_timeout")

    def test_500_is_error(self):
        self.assertEqual(contactout.classify_failure(500),
                         "contactout_error")

    def test_503_is_error(self):
        self.assertEqual(contactout.classify_failure(503),
                         "contactout_error")

    def test_network_error_is_error(self):
        self.assertEqual(
            contactout.classify_failure(None, "OSError: Network unreachable"),
            "contactout_error")

    def test_401_is_error_not_rate_limited(self):
        self.assertEqual(contactout.classify_failure(401),
                         "contactout_error")

    def test_rate_limit_in_text_is_rate_limited(self):
        self.assertEqual(
            contactout.classify_failure(200, "rate limit exceeded"),
            "contactout_rate_limited")


class TestBoundedRetry(unittest.TestCase):
    """The ContactOut adapter retries transient failures with a bound."""

    def _patch(self, fake_request):
        """Replace contactout.request and contactout.headers with fakes."""
        orig_request = contactout.request
        orig_headers = contactout.headers
        contactout.request = fake_request
        contactout.headers = lambda: {"authorization": "basic",
                                       "token": "fake-test-token"}
        self.addCleanup(lambda: setattr(contactout, "request", orig_request))
        self.addCleanup(lambda: setattr(contactout, "headers", orig_headers))

    def test_retry_on_500_succeeds_on_second_attempt(self):
        attempts = []

        def fake_request(method, url, headers, body=None, timeout=None):
            attempts.append(1)
            if len(attempts) < 2:
                return 500, None
            return 200, {"status": 200, "data": {"total_results": 5}}

        self._patch(fake_request)
        result = contactout.call("people-count", _sleep=lambda _: None)
        self.assertEqual(result["total_results"], 5)
        self.assertEqual(len(attempts), 2)

    def test_retry_exhausted_raises(self):
        attempts = []

        def fake_request(method, url, headers, body=None, timeout=None):
            attempts.append(1)
            return 500, None

        self._patch(fake_request)
        with self.assertRaises(providers.ProviderError):
            contactout.call("people-count", _sleep=lambda _: None)
        self.assertEqual(len(attempts), contactout.MAX_RETRIES + 1)

    def test_401_is_not_retried(self):
        attempts = []

        def fake_request(method, url, headers, body=None, timeout=None):
            attempts.append(1)
            return 401, "unauthorized"

        self._patch(fake_request)
        with self.assertRaises(providers.ProviderError):
            contactout.call("people-count", _sleep=lambda _: None)
        self.assertEqual(len(attempts), 1,
                         "a 401 must not be retried")

    def test_429_is_retried(self):
        attempts = []

        def fake_request(method, url, headers, body=None, timeout=None):
            attempts.append(1)
            if len(attempts) < 3:
                return 429, "rate limited"
            return 200, {"status": 200, "data": {"total_results": 0}}

        self._patch(fake_request)
        result = contactout.call("people-count", _sleep=lambda _: None)
        self.assertEqual(len(attempts), 3)

    def test_max_retries_is_bounded(self):
        self.assertLessEqual(contactout.MAX_RETRIES, 5,
                             "retry bound must be small and visible")


class TestCounters(unittest.TestCase):
    """Telemetry counters aggregate from the ledger."""

    def test_empty_records(self):
        c = waterfall.counters([])
        self.assertEqual(c["CONTACTOUT_CALLS"], 0)
        self.assertEqual(c["CONTACTOUT_CONFIRMED_MISSES"], 0)
        self.assertEqual(c["CONTACTOUT_ERRORS"], 0)

    def test_contactout_call_counted(self):
        rec = {"id": "test"}
        waterfall.record_step(rec, "people_discovery", waterfall.CONTACTOUT,
                              "people-count")
        c = waterfall.counters([rec])
        self.assertEqual(c["CONTACTOUT_CALLS"], 1)

    def test_confirmed_miss_counted(self):
        rec = {"id": "test"}
        waterfall.record_step(rec, "people_discovery", waterfall.CONTACTOUT,
                              "people-count")
        waterfall.record_step(rec, "people_discovery", waterfall.AIARK,
                              "aiark-people-search",
                              reason=enrich.CONTACTOUT_NO_PEOPLE)
        c = waterfall.counters([rec])
        self.assertEqual(c["CONTACTOUT_CONFIRMED_MISSES"], 1)
        self.assertEqual(c["OTHER_PROVIDER_ESCALATIONS"], 1)

    def test_escalation_carries_its_reason(self):
        rec = {"id": "test"}
        waterfall.record_step(rec, "people_discovery", waterfall.CONTACTOUT,
                              "people-count")
        waterfall.record_step(rec, "people_discovery", waterfall.AIARK,
                              "aiark-people-search",
                              reason=enrich.CONTACTOUT_NO_PEOPLE)
        c = waterfall.counters([rec])
        self.assertEqual(len(c["escalation_reasons"]), 1)
        self.assertEqual(c["escalation_reasons"][0]["reason"],
                         enrich.CONTACTOUT_NO_PEOPLE)

    def test_cache_hits_are_passed_through(self):
        c = waterfall.counters([], cache_hits=42)
        self.assertEqual(c["CONTACTOUT_CACHE_HITS"], 42)


if __name__ == "__main__":
    unittest.main()
