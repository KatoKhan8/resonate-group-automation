"""BlitzAPI, offline. No test here may reach the API or spend a record.

Blitz is the second structured provider and the first one whose error codes
mean something unusual, so most of this file is about the difference between
three things a lazy adapter would flatten into one:

  found        HTTP 200, `found: true`
  a miss       HTTP 200, `found: false`   - confirmed, and cheap to trust
  confusion    anything else              - and 404 above all

404 from Blitz means the API key does not exist. A waterfall that read it as a
miss would send a paid fallback after every record in the batch and the spend
audit would report the run clean, because every step would carry a reason the
policy accepts. That one test is the reason this file exists.

The transports below are hand written rather than cassette files: each test
needs a *different* status or body for the same URL, which a shared cassette
cannot express. They go through `providers.set_transport`, the same seam
`tests/base.Cassette` uses, so the tripwire in `ProviderTest` still fails any
call that tries to leave the process.
"""
import json
import os
import unittest

from src import providers
from src.providers import blitz
from tests.base import ProviderTest

# A metered answer. `fair_usage.records_used` is the real cost of the call.
FOUND = {
    "found": True,
    "data": {
        "name": "Meridian",
        "linkedin_url": "https://www.linkedin.com/company/meridian",
        "domain": "meridian.test",
        "email_domain": "mail.meridian.test",
        "employees": 17,
        "industry": "IT Services",
        "location": "Zagreb, Croatia",
        # Noise, on purpose. None of it may escape the module.
        "logo_url": "https://cdn.blitz.test/logo/redacted.png",
        "description": "a very long description nobody asked for",
        "raw_profile": {"followers": 4210, "skills": ["accounting"]},
    },
    "fair_usage": {"records_used": 1, "records_remaining": 4999,
                   "request_id": "req-abc-123", "plan": "growth"},
}

MISS = {
    "found": False,
    "fair_usage": {"records_used": 0, "records_remaining": 5000,
                   "request_id": "req-abc-124"},
}

KEY_INFO = {
    "allowed_apis": ["domain-to-linkedin", "linkedin-to-domain", "company",
                     "employee-finder", "email"],
    "max_requests_per_seconds": 10,
    "plan": "growth",
    "records_remaining": 5000,
}

PEOPLE = {
    "results": [
        {"full_name": "Ivana Saric", "title": "Head of Finance",
         "company_name": "Meridian",
         "linkedin_url": "https://www.linkedin.com/in/ivana-saric",
         "location": "Zagreb, Croatia",
         "skills": ["accounting"], "personal_email": "i.saric@example.com",
         "phone": "+385000000000"},
    ],
    "results_length": 1,
    "fair_usage": {"records_used": 1, "records_remaining": 4998,
                   "request_id": "req-abc-125"},
}

EMPTY_SEARCH = {"results": [], "results_length": 0,
                "fair_usage": {"records_used": 0, "records_remaining": 4998,
                               "request_id": "req-abc-126"}}


class Wire:
    """One canned answer for every call, and a record of what was asked.

    `raises` simulates the transport failing the way `providers.request` does
    on a socket timeout: a `ProviderError`, resolved at call time because
    `tests/test_audit.py` reloads `src.providers` and a class bound at import
    would no longer be the one being raised.
    """

    def __init__(self, payload=None, status=200, raises=None):
        self.payload, self.status, self.raises = payload, status, raises
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url,
                           "headers": dict(headers), "body": body})
        if self.raises:
            raise providers.ProviderError(self.raises)
        return self.status, json.dumps(self.payload)


class BlitzTest(ProviderTest):
    """`ProviderTest` plus the one credential it does not know about yet.

    Redundant once BLITZ_API_KEY is in `tests/base.KEY_VARS`, which
    INTEGRATION.md asks for; harmless either way, and it means this file does
    not depend on that edit having been made.
    """

    def setUp(self):
        super().setUp()
        self._blitz_key = os.environ.get("BLITZ_API_KEY")
        os.environ["BLITZ_API_KEY"] = "test-key-not-real"

    def tearDown(self):
        if self._blitz_key is None:
            os.environ.pop("BLITZ_API_KEY", None)
        else:
            os.environ["BLITZ_API_KEY"] = self._blitz_key
        super().tearDown()

    def wire(self, payload=None, status=200, raises=None):
        w = Wire(payload, status, raises)
        self.providers.set_transport(w)
        return w

    def raises(self):
        return self.assertRaises(providers.ProviderError)


class TheWireContract(BlitzTest):

    def test_the_base_is_the_documented_host(self):
        self.assertEqual(blitz.BASE, "https://api.blitz-api.ai")

    def test_every_operation_the_matrix_names_has_a_route(self):
        for op in ("key-info", "domain-to-linkedin", "linkedin-to-domain",
                   "company", "waterfall-icp-keyword", "employee-finder",
                   "email", "phone"):
            self.assertIn(op, blitz.ROUTES, op)

    def test_every_path_is_under_v2(self):
        for op, (_, path) in blitz.ROUTES.items():
            self.assertTrue(path.startswith("/v2/"), f"{op}: {path}")

    def test_key_info_is_the_free_one(self):
        self.assertEqual(blitz.ROUTES["key-info"],
                         ("GET", "/v2/account/key-info"))
        self.assertEqual(set(blitz.FREE), {"key-info"})

    def test_an_operation_without_a_route_is_refused_not_guessed(self):
        with self.raises():
            blitz.call("no-such-operation")

    def test_the_key_travels_raw_under_x_api_key(self):
        wire = self.wire(KEY_INFO)
        blitz.key_info()
        sent = wire.calls[0]["headers"]
        self.assertEqual(sent["x-api-key"], "test-key-not-real")
        self.assertNotIn("authorization", {k.lower() for k in sent})
        self.assertNotIn("Bearer", json.dumps(sent))

    def test_the_credential_is_read_at_call_time_not_at_import(self):
        wire = self.wire(KEY_INFO)
        os.environ["BLITZ_API_KEY"] = "second-key-not-real"
        blitz.key_info()
        self.assertEqual(wire.calls[-1]["headers"]["x-api-key"],
                         "second-key-not-real")

    def test_a_missing_key_raises_before_any_request(self):
        os.environ.pop("BLITZ_API_KEY", None)
        wire = self.wire(KEY_INFO)
        with self.assertRaises(providers.MissingKey):
            blitz.domain_to_linkedin("meridian.test")
        self.assertEqual(wire.calls, [])

    def test_every_route_has_a_ledger_name_that_says_who_charged(self):
        for op in blitz.ROUTES:
            self.assertEqual(blitz.CALLS[op], f"blitz-{op}")


class AFoundSubject(BlitzTest):

    def test_a_found_subject_comes_back_found(self):
        self.wire(FOUND)
        got = blitz.domain_to_linkedin("meridian.test")
        self.assertIs(got["found"], True)
        self.assertEqual(got["company_linkedin"],
                         "https://www.linkedin.com/company/meridian")

    def test_the_email_domain_contactout_never_returns(self):
        self.wire(FOUND)
        got = blitz.linkedin_to_domain(
            "https://www.linkedin.com/company/meridian")
        self.assertEqual(got["email_domain"], "mail.meridian.test")

    def test_the_company_call_is_trimmed_to_a_fixed_field_set(self):
        """`employee_range` joined the set once a live response was seen.

        The wire carries both `employees_on_linkedin` (a measured count) and
        `size` (a band, "1-10"). Reading the band into `employees` would
        understate a company; dropping it loses what the ICP scorer already
        stores as `employee_range` elsewhere. So both are kept, separately.
        Confirmed live 2026-09-09 - see tests/test_blitz_against_the_wire.py.
        """
        self.wire(FOUND)
        got = blitz.company("https://www.linkedin.com/company/meridian")
        self.assertEqual(set(got),
                         {"found", "company_linkedin", "name", "domain",
                          "employees", "employee_range", "industry",
                          "location", "founded", "fair_usage"})
        self.assertEqual(got["employees"], 17)

    def test_the_subject_travels_in_the_body_of_a_post(self):
        wire = self.wire(FOUND)
        blitz.domain_to_linkedin("meridian.test")
        self.assertEqual(wire.calls[0]["method"], "POST")
        self.assertTrue(wire.calls[0]["url"]
                        .endswith("/v2/enrichment/domain-to-linkedin"))
        self.assertEqual(wire.calls[0]["body"], {"domain": "meridian.test"})


class AConfirmedMiss(BlitzTest):
    """`found: false` at HTTP 200. The only miss there is."""

    def test_a_miss_is_an_answer_and_does_not_raise(self):
        self.wire(MISS)
        got = blitz.domain_to_linkedin("nobody.test")
        self.assertIs(got["found"], False)
        self.assertIsNone(got["company_linkedin"])

    def test_a_miss_still_reports_what_it_cost(self):
        self.wire(MISS)
        got = blitz.email("https://www.linkedin.com/in/nobody")
        self.assertEqual(got["fair_usage"]["records_used"], 0)
        self.assertEqual(got["fair_usage"]["request_id"], "req-abc-124")

    def test_a_miss_carries_no_invented_fields(self):
        self.wire(MISS)
        got = blitz.company("https://www.linkedin.com/company/nobody")
        for field in ("name", "domain", "industry", "location"):
            self.assertIsNone(got[field], field)

    def test_a_search_with_no_results_is_a_miss_not_a_failure(self):
        self.wire(EMPTY_SEARCH)
        got = blitz.employee_finder(
            "https://www.linkedin.com/company/meridian")
        self.assertEqual(got["people"], [])
        self.assertEqual(got["count"], 0)


class A404IsAnAuthError(BlitzTest):
    """The one that would have cost real money.

    404 from Blitz means the API key does not exist. Read as a miss, a dead
    key looks like a world in which no subject is ever found: every record in
    the batch falls through to a paid provider with a reason the waterfall
    accepts, and `waterfall.audit` reports nothing unjustified.
    """

    def test_a_404_raises_rather_than_answering(self):
        self.wire({"detail": "not found"}, status=404)
        with self.raises():
            blitz.domain_to_linkedin("meridian.test")

    def test_the_message_says_it_is_authentication_and_not_a_miss(self):
        self.wire({"detail": "not found"}, status=404)
        try:
            blitz.email("https://www.linkedin.com/in/ivana-saric")
        except providers.ProviderError as e:
            message = str(e).lower()
            self.assertIn("api key does not exist", message)
            self.assertIn("authentication error", message)
            self.assertIn("not a data miss", message)
        else:
            self.fail("a 404 was not raised")

    def test_a_404_never_arrives_as_found_false(self):
        """The failure mode itself, stated as behaviour rather than as text."""
        self.wire({"found": False}, status=404)
        with self.raises():
            blitz.domain_to_linkedin("meridian.test")

    def test_key_info_refuses_a_404_the_same_way(self):
        self.wire({"detail": "not found"}, status=404)
        with self.raises():
            blitz.key_info()

    def test_a_404_turns_the_health_check_red_rather_than_green(self):
        self.wire({"detail": "not found"}, status=404)
        report = blitz.check()
        self.assertFalse(report["ok"])
        self.assertIn("api key does not exist", report["note"].lower())

    def test_401_and_403_are_refused_as_well(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.wire({"detail": "denied"}, status=status)
                with self.raises():
                    blitz.company("https://www.linkedin.com/company/meridian")


class ConfusionIsNotAMiss(BlitzTest):
    """A 200 that does not say `found` has not said anything."""

    def test_a_200_without_found_raises(self):
        self.wire({"data": {"name": "Meridian"},
                   "fair_usage": {"records_used": 1}})
        with self.raises():
            blitz.domain_to_linkedin("meridian.test")

    def test_the_message_names_the_missing_field(self):
        self.wire({"data": {}})
        try:
            blitz.company("https://www.linkedin.com/company/meridian")
        except providers.ProviderError as e:
            self.assertIn("found", str(e))
            self.assertIn("confusion is not a miss", str(e))
        else:
            self.fail("a body with no found key was accepted")

    def test_an_empty_body_is_not_read_as_a_miss(self):
        self.wire({})
        with self.raises():
            blitz.email("https://www.linkedin.com/in/ivana-saric")

    def test_a_truthy_found_that_is_not_a_boolean_raises(self):
        for value in ("true", 1, "yes"):
            with self.subTest(value=value):
                self.wire({"found": value, "data": {}})
                with self.raises():
                    blitz.domain_to_linkedin("meridian.test")

    def test_a_body_of_the_wrong_type_raises(self):
        self.wire([{"found": True}])
        with self.raises():
            blitz.domain_to_linkedin("meridian.test")

    def test_a_search_with_no_results_list_raises(self):
        """Distinct from results_length 0, which is a real empty answer."""
        self.wire({"results_length": 0,
                   "fair_usage": {"records_used": 0}})
        with self.raises():
            blitz.employee_finder("https://www.linkedin.com/company/meridian")

    def test_key_info_without_allowed_apis_raises(self):
        self.wire({"plan": "growth", "max_requests_per_seconds": 10})
        with self.raises():
            blitz.key_info()


class RateLimiting(BlitzTest):

    def test_a_429_raises_and_is_not_read_as_a_miss(self):
        self.wire({"detail": "too many requests"}, status=429)
        with self.raises():
            blitz.domain_to_linkedin("meridian.test")

    def test_the_message_says_it_was_rate_limited(self):
        self.wire({"detail": "too many requests"}, status=429)
        try:
            blitz.employee_finder(
                "https://www.linkedin.com/company/meridian")
        except providers.ProviderError as e:
            self.assertIn("429", str(e))
            self.assertIn("rate limited", str(e).lower())
        else:
            self.fail("a 429 was not raised")

    def test_a_429_is_not_retried(self):
        """No idempotency: a retry is a second billable call, not a repair."""
        wire = self.wire({"detail": "too many requests"}, status=429)
        with self.raises():
            blitz.domain_to_linkedin("meridian.test")
        self.assertEqual(len(wire.calls), 1)

    def test_the_documented_ceiling_is_per_endpoint_and_key_info_is_the_authority(self):
        self.wire(KEY_INFO)
        self.assertEqual(blitz.DEFAULT_RATE_LIMIT, 10)
        self.assertEqual(blitz.key_info()["max_requests_per_seconds"], 10)

    def test_an_unstated_rate_limit_is_unknown_rather_than_the_default(self):
        self.wire({"allowed_apis": ["company"]})
        self.assertIsNone(blitz.key_info()["max_requests_per_seconds"])


class ATimeoutIsNotRetried(BlitzTest):
    """The server may already have billed the call whose answer was lost."""

    def test_a_timeout_propagates(self):
        self.wire(raises="TimeoutError: the read timed out")
        with self.raises():
            blitz.email("https://www.linkedin.com/in/ivana-saric")

    def test_a_timeout_makes_exactly_one_call(self):
        wire = self.wire(raises="TimeoutError: the read timed out")
        with self.raises():
            blitz.email("https://www.linkedin.com/in/ivana-saric")
        self.assertEqual(len(wire.calls), 1)

    def test_no_accessor_retries_a_lost_answer(self):
        for name, args in (("domain_to_linkedin", ("meridian.test",)),
                           ("linkedin_to_domain", ("https://x.test/c",)),
                           ("company", ("https://x.test/c",)),
                           ("employee_finder", ("https://x.test/c",)),
                           ("icp_keyword_search", ()),
                           ("email", ("https://x.test/in",)),
                           ("phone", ("https://x.test/in",)),
                           ("key_info", ())):
            with self.subTest(call=name):
                wire = self.wire(raises="TimeoutError: the read timed out")
                with self.raises():
                    getattr(blitz, name)(*args)
                self.assertEqual(len(wire.calls), 1, name)

    def test_a_failed_call_is_never_turned_into_an_empty_answer(self):
        """A swallowed timeout would read as "nobody works here"."""
        self.wire(raises="TimeoutError: the read timed out")
        with self.raises():
            blitz.employee_finder("https://www.linkedin.com/company/meridian")


class WhatTheCallCost(BlitzTest):
    """`fair_usage.records_used` is the only true cost, and None is honest."""

    def test_it_trims_to_exactly_three_fields(self):
        self.assertEqual(
            set(blitz._fair_usage(FOUND)),
            {"records_used", "records_remaining", "request_id"})

    def test_it_reads_the_records_the_call_actually_used(self):
        self.assertEqual(blitz._fair_usage(FOUND)["records_used"], 1)
        self.assertEqual(blitz._fair_usage(FOUND)["records_remaining"], 4999)

    def test_the_plan_and_anything_else_in_the_block_stays_out(self):
        self.assertNotIn("plan", blitz._fair_usage(FOUND))

    def test_every_metered_accessor_returns_what_it_cost(self):
        self.wire(FOUND)
        for got in (blitz.domain_to_linkedin("meridian.test"),
                    blitz.linkedin_to_domain("https://x.test/c"),
                    blitz.company("https://x.test/c"),
                    blitz.email("https://x.test/in"),
                    blitz.phone("https://x.test/in")):
            self.assertEqual(got["fair_usage"]["records_used"], 1)
        self.wire(PEOPLE)
        self.assertEqual(
            blitz.employee_finder("https://x.test/c")["fair_usage"]
            ["records_used"], 1)

    def test_a_missing_block_is_unknown_and_never_zero(self):
        """A metered call reported as free is worse than one reported at all."""
        for body in ({"found": True, "data": {}},
                     {"found": True, "data": {}, "fair_usage": None},
                     {"found": True, "data": {}, "fair_usage": "later"}):
            with self.subTest(body=body):
                self.assertIsNone(blitz._fair_usage(body)["records_used"])

    def test_an_unreadable_count_is_unknown_rather_than_zero(self):
        self.assertIsNone(
            blitz._fair_usage({"fair_usage": {"records_used": "lots"}})
            ["records_used"])

    def test_a_numeric_string_is_still_a_count(self):
        self.assertEqual(
            blitz._fair_usage({"fair_usage": {"records_used": "3"}})
            ["records_used"], 3)

    def test_a_boolean_is_not_a_count(self):
        """`True` is an int in Python; billed as one record it is a number
        nobody typed."""
        self.assertIsNone(
            blitz._fair_usage({"fair_usage": {"records_used": True}})
            ["records_used"])

    def test_the_request_id_is_kept_but_cannot_deduplicate_anything(self):
        usage = blitz._fair_usage(FOUND)
        self.assertEqual(usage["request_id"], "req-abc-123")
        # Server-generated per response: two calls with the same subject get
        # two different ids, so it can never identify a repeated *request*.
        wire = self.wire(FOUND)
        blitz.domain_to_linkedin("meridian.test")
        blitz.domain_to_linkedin("meridian.test")
        for call in wire.calls:
            self.assertNotIn("idempotency", json.dumps(call).lower())


class NoRawPayloadEscapes(BlitzTest):
    """BUILD-SPEC section 9, trap 8: one payload can dominate an LLM context."""

    def test_the_noise_in_an_enrichment_body_never_leaves_the_module(self):
        self.wire(FOUND)
        blob = json.dumps(blitz.company("https://x.test/c"))
        for noise in ("logo_url", "description", "raw_profile", "followers",
                      "skills", "nobody asked for"):
            self.assertNotIn(noise, blob, noise)

    def test_a_person_is_five_fields_and_no_contact_details(self):
        self.wire(PEOPLE)
        person = blitz.employee_finder("https://x.test/c")["people"][0]
        self.assertEqual(set(person),
                         {"name", "title", "company", "linkedin", "location"})
        blob = json.dumps(person)
        for noise in ("skills", "i.saric@example.com", "+385"):
            self.assertNotIn(noise, blob, noise)

    def test_a_search_result_set_is_trimmed_row_by_row(self):
        self.wire(PEOPLE)
        got = blitz.employee_finder("https://x.test/c")
        self.assertEqual(set(got), {"people", "count", "fair_usage"})
        self.assertEqual(got["count"], 1)

    def test_icp_search_rows_are_trimmed_too(self):
        self.wire({"results": [{"name": "Meridian", "domain": "meridian.test",
                                "employees": 17, "industry": "IT",
                                "logo_url": "https://cdn.test/x.png",
                                "about": "x" * 4000}],
                   "results_length": 1,
                   "fair_usage": {"records_used": 1}})
        got = blitz.icp_keyword_search(keyword="fractional cfo")
        self.assertEqual(set(got["companies"][0]),
                         {"name", "domain", "linkedin", "employees",
                          "industry"})
        self.assertNotIn("logo_url", json.dumps(got))
        self.assertLess(len(json.dumps(got)), 500)

    def test_no_accessor_returns_the_body_it_was_given(self):
        self.wire(FOUND)
        for got in (blitz.domain_to_linkedin("meridian.test"),
                    blitz.linkedin_to_domain("https://x.test/c"),
                    blitz.company("https://x.test/c"),
                    blitz.email("https://x.test/in"),
                    blitz.phone("https://x.test/in")):
            self.assertNotIn("data", got)
            self.assertNotIn("raw_profile", json.dumps(got))


class TheHealthCheck(BlitzTest):
    """Free, and it reports the only authority on what this key may do."""

    def test_it_calls_key_info_and_nothing_else(self):
        wire = self.wire(KEY_INFO)
        blitz.check()
        self.assertEqual(len(wire.calls), 1)
        self.assertTrue(wire.calls[0]["url"]
                        .endswith("/v2/account/key-info"), wire.calls[0]["url"])
        self.assertEqual(wire.calls[0]["method"], "GET")

    def test_it_reports_the_allowed_apis(self):
        self.wire(KEY_INFO)
        note = blitz.check()["note"]
        self.assertIn("allowed_apis", note)
        self.assertIn("domain-to-linkedin", note)

    def test_allowed_apis_is_a_list_of_names(self):
        self.wire(KEY_INFO)
        self.assertEqual(blitz.key_info()["allowed_apis"],
                         KEY_INFO["allowed_apis"])

    def test_a_missing_key_turns_it_red_without_a_request(self):
        os.environ.pop("BLITZ_API_KEY", None)
        wire = self.wire(KEY_INFO)
        report = blitz.check()
        self.assertFalse(report["ok"])
        self.assertIn("BLITZ_API_KEY", report["note"])
        self.assertEqual(wire.calls, [])

    def test_no_key_leaks_into_the_report(self):
        self.wire(KEY_INFO)
        self.assertNotIn("test-key-not-real", str(blitz.check()))

    def test_a_key_shaped_header_is_redacted_wherever_it_is_printed(self):
        self.assertEqual(providers.redact({"x-api-key": "abc"}),
                         {"x-api-key": "***"})


class TheSpendGate(BlitzTest):
    """The link this module cannot enforce alone.

    Every Blitz call that returns a person or their contact details has to be
    in `enrich.PERSON_LEVEL`, because that tuple is what `enrich.spend`
    checks before a company has an ICP verdict. A call that is not in it is a
    person credit spent on a company nobody assessed.

    RED UNTIL INTEGRATION.md IS APPLIED, deliberately: this is the test that
    proves the gate covers Blitz rather than the comment that claims it does.
    """

    def test_every_person_level_operation_is_gated_in_enrich(self):
        from src import enrich

        for op in blitz.PERSON_LEVEL_OPS:
            self.assertIn(blitz.CALLS[op], enrich.PERSON_LEVEL, op)

    def test_every_wired_call_has_a_cost_and_a_stage(self):
        """A call in the cost table but not in the stage table would be
        filed under the default stage and audited against the wrong policy."""
        from src import enrich

        for op, name in blitz.CALLS.items():
            if name in enrich.COSTS:
                self.assertIn(name, enrich.CALL_STAGE, name)

    def test_blitz_is_never_the_first_provider_at_any_stage(self):
        from src import waterfall

        for stage in waterfall.STAGE_NAMES:
            self.assertTrue(waterfall.contactout_is_first(stage), stage)
            for step in waterfall.STAGES[stage]["providers"]:
                if step["call"].startswith("blitz-"):
                    self.assertTrue(step.get("requires_reason"),
                                    f"{stage}/{step['call']} may run without "
                                    "a stated ContactOut miss")


if __name__ == "__main__":
    unittest.main()
