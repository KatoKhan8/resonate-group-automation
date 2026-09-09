"""The ContactOut validation harness.

The point of these tests is that the harness cannot spend money by accident.
Every one of them runs against a cassette; none performs a paid call.
"""
import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from src import validate
from tests.base import ProviderTest


class ValidateTest(ProviderTest):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-validate-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = validate.main(list(argv))
        return code, buf.getvalue()


class TestDryRunIsTheDefault(ValidateTest):
    def test_a_bare_run_calls_nothing(self):
        result = validate.run()
        self.assertFalse(result["live"])
        self.assertEqual(self.cassette.calls, [])

    def test_the_cli_defaults_to_dry_and_says_so(self):
        code, out = self.cli()
        self.assertEqual(code, 0)
        self.assertIn("DRY RUN", out)
        self.assertIn("Nothing was called and nothing was spent", out)
        self.assertEqual(self.cassette.calls, [])

    def test_the_cost_is_shown_before_anything_could_be_called(self):
        code, out = self.cli("--domain", "mine.test")
        self.assertIn("planned calls and cost", out)
        self.assertIn("TOTAL", out)
        for check in ("decision-makers", "people-search",
                      "company-information-from-domain"):
            self.assertIn(check, out)

    def test_the_estimate_prices_every_paid_check(self):
        priced = validate.estimate(validate.ORDER, email="a@mine.test")
        by_check = {r["check"]: r["credits"] for r in priced["rows"]}
        self.assertEqual(by_check["people-count"], 0)
        self.assertGreater(by_check["decision-makers"], 0)
        self.assertGreater(by_check["email-verifier"], 0)
        self.assertEqual(priced["total"], sum(by_check.values()))

    def test_the_verifier_is_skipped_when_no_address_is_supplied(self):
        priced = validate.estimate(validate.ORDER, email=None)
        self.assertNotIn("email-verifier", [r["check"] for r in priced["rows"]])


class TestTheGuards(ValidateTest):
    def test_live_without_a_domain_is_refused(self):
        with self.assertRaises(validate.Refused) as e:
            validate.run(live=True, max_credits=100)
        self.assertIn("--domain is required", str(e.exception))

    def test_live_without_max_credits_is_refused(self):
        with self.assertRaises(validate.Refused) as e:
            validate.run(domain="mine.test", live=True)
        self.assertIn("--max-credits is required", str(e.exception))

    def test_an_estimate_over_the_ceiling_is_refused_before_any_call(self):
        with self.assertRaises(validate.Refused) as e:
            validate.run(domain="mine.test", live=True, max_credits=2)
        self.assertIn("over your --max-credits", str(e.exception))
        self.assertEqual(self.cassette.calls, [])

    def test_a_suppressed_domain_is_refused_outright(self):
        from src import ingest
        suppressed = sorted(ingest.load_suppress())[0]
        with self.assertRaises(validate.Refused) as e:
            validate.run(domain=suppressed, live=True, max_credits=100)
        self.assertIn("suppression list", str(e.exception))
        self.assertEqual(self.cassette.calls, [])

    def test_the_cli_reports_a_refusal_and_exits_non_zero(self):
        code, out = self.cli("--live-validation", "--max-credits", "1",
                             "--domain", "mine.test")
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", out)
        self.assertEqual(self.cassette.calls, [])

    def test_there_is_no_default_domain_anywhere_in_the_module(self):
        """The operator supplies the domain. Nothing is baked in."""
        import inspect

        from tests.test_fixture_hygiene import FORBIDDEN_DOMAINS
        source = inspect.getsource(validate).lower()
        for real in FORBIDDEN_DOMAINS:
            self.assertNotIn(real, source)
        self.assertIsNone(inspect.signature(validate.run).parameters["domain"].default)


class TestLiveValidationBehaviour(ValidateTest):
    """Exercised against cassettes: the shape of a real run, at zero cost."""

    def test_a_run_that_would_exceed_the_ceiling_is_refused_whole(self):
        """Not a partial spend: the estimate is checked before the first call."""
        with self.assertRaises(validate.Refused):
            validate.run(domain="meridian.test", live=True, max_credits=11,
                         raw_sink=os.path.join(self.tmp, "raw"))
        self.assertEqual(self.cassette.calls, [])

    def test_a_run_inside_the_ceiling_spends_exactly_the_estimate(self):
        checks = ["people-count", "company-information-from-domain"]
        priced = validate.estimate(checks)
        result = validate.run(domain="meridian.test", checks=checks, live=True,
                              max_credits=priced["total"],
                              raw_sink=os.path.join(self.tmp, "raw"))
        self.assertEqual(result["spent"], priced["total"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["findings"]), 2)

    def test_the_per_call_ceiling_is_a_second_line_of_defence(self):
        """If a call ever costs more than its estimate, the loop still stops."""
        import inspect
        self.assertIn("would exceed --max-credits", inspect.getsource(validate.run))

    def test_the_free_check_costs_nothing_against_the_ceiling(self):
        result = validate.run(domain="meridian.test", checks=["people-count"],
                              live=True, max_credits=0,
                              raw_sink=os.path.join(self.tmp, "raw"))
        self.assertEqual(result["spent"], 0)
        self.assertTrue(result["findings"])

    def test_raw_output_goes_to_a_gitignored_directory_not_the_queue(self):
        sink = os.path.join(self.tmp, "raw")
        validate.run(domain="meridian.test", checks=["people-count"], live=True,
                     max_credits=0, raw_sink=sink)
        self.assertTrue(os.listdir(sink))
        self.assertFalse(os.path.exists(self.queue))

    def test_the_default_sink_is_under_work_which_git_ignores(self):
        self.assertIn("work", validate.output_dir())
        self.assertIn("validation", validate.output_dir())

    def test_it_reports_a_field_our_trim_expects_but_never_gets(self):
        result = validate.run(domain="meridian.test", checks=["people-count"],
                              live=True, max_credits=0,
                              raw_sink=os.path.join(self.tmp, "raw"))
        finding = result["findings"][0]
        self.assertEqual(finding["check"], "people-count")
        self.assertIn("verdict", finding)
        self.assertEqual(finding["expected_fields"], ["mobiles", "profiles", "query"])

    def test_a_trim_that_comes_back_empty_is_called_out(self):
        finding = validate.compare("email-verifier",
                                   {"email": "a@b.test", "verdict": None}, {})
        self.assertIn("verdict", finding["trimmed_but_empty"])
        self.assertEqual(finding["verdict"], "differs")

    def test_a_matching_trim_is_reported_as_matching(self):
        finding = validate.compare("email-verifier",
                                   {"email": "a@b.test", "verdict": "valid"}, {})
        self.assertEqual(finding["verdict"], "matches")

    def test_raw_keys_we_ignore_are_listed_for_review(self):
        raw = {"data": {"company": {"name": "X", "surprise_field": 1}}}
        finding = validate.compare("company-information-from-domain", {}, raw)
        self.assertIn("surprise_field", finding["raw_keys_we_ignore"])


class TestScopingAValidationToTwoChecks(ValidateTest):
    """A one-credit ceiling must scope the run, not just refuse it.

    The whole plan is 16 credits, so a bare --max-credits 1 is refused outright
    and should be: the ceiling is not a licence to silently drop calls. Naming
    the checks is how a cheap run is asked for, and the two named here are the
    free count and the single-credit company lookup.
    """

    CHEAP = ["people-count", "company-information-from-domain"]

    def test_the_whole_plan_is_refused_at_a_one_credit_ceiling(self):
        with self.assertRaises(validate.Refused):
            validate.run(domain="meridian.test", live=True, max_credits=1,
                         raw_sink=os.path.join(self.tmp, "raw"))
        self.assertEqual(self.cassette.calls, [])

    def test_the_two_cheap_checks_price_at_exactly_one_credit(self):
        self.assertEqual(validate.estimate(self.CHEAP)["total"], 1)

    def test_scoping_to_them_calls_nothing_else(self):
        validate.run(domain="meridian.test", checks=self.CHEAP, live=True,
                     max_credits=1, raw_sink=os.path.join(self.tmp, "raw"))
        urls = " ".join(self.cassette.urls())
        for forbidden in ("decision-makers", "people-search", "email-verifier"):
            self.assertNotIn(forbidden, urls, forbidden)

    def test_an_unknown_check_name_is_dropped_rather_than_called(self):
        result = validate.run(domain="meridian.test",
                              checks=["people-count", "nonsense"], live=True,
                              max_credits=0, raw_sink=os.path.join(self.tmp, "raw"))
        self.assertEqual(result["checks"], ["people-count"])

    def test_the_cli_passes_repeated_check_flags_through(self):
        code, out = self.cli("--domain", "meridian.test",
                             "--check", "people-count",
                             "--check", "company-information-from-domain")
        self.assertEqual(code, 0)
        self.assertIn("TOTAL", out)
        self.assertNotIn("decision-makers", out)
        self.assertIn("DRY RUN", out)


class TestTheRawResponseIsActuallyCompared(ValidateTest):
    """compare() was always handed an empty raw, so it could never report one."""

    def test_a_finding_names_the_fields_the_real_response_carried(self):
        result = validate.run(domain="meridian.test",
                              checks=["company-information-from-domain"],
                              live=True, max_credits=1,
                              raw_sink=os.path.join(self.tmp, "raw"))
        finding = result["findings"][0]
        self.assertTrue(finding["raw_keys_we_ignore"],
                        "the real response was not compared against the trim")

    def test_the_recorded_exchange_reaches_the_sink(self):
        sink = os.path.join(self.tmp, "raw")
        validate.run(domain="meridian.test", checks=["people-count"], live=True,
                     max_credits=0, raw_sink=sink)
        import json as _json
        with open(os.path.join(sink, "people-count.json"), encoding="utf-8") as f:
            saved = _json.load(f)
        self.assertIn("exchanges", saved)
        self.assertTrue(saved["exchanges"])
        self.assertIn("payload", saved["exchanges"][0])

    def test_no_key_is_written_into_the_sink(self):
        sink = os.path.join(self.tmp, "raw")
        validate.run(domain="meridian.test", checks=["people-count"], live=True,
                     max_credits=0, raw_sink=sink)
        with open(os.path.join(sink, "people-count.json"), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("test-key-not-real", text)

    def test_the_transport_is_put_back_afterwards(self):
        before = self.providers._transport
        validate.run(domain="meridian.test", checks=["people-count"], live=True,
                     max_credits=0, raw_sink=os.path.join(self.tmp, "raw"))
        self.assertIs(self.providers._transport, before)

    def test_the_transport_is_put_back_even_when_a_call_raises(self):
        before = self.providers._transport

        def explode(*a, **kw):
            raise self.providers.ProviderError("boom")

        original = validate.call
        validate.call = explode
        try:
            validate.run(domain="meridian.test", checks=["people-count"],
                         live=True, max_credits=0,
                         raw_sink=os.path.join(self.tmp, "raw"))
        finally:
            validate.call = original
        self.assertIs(self.providers._transport, before)

    def test_a_provider_is_priced_from_its_own_spec_not_contactouts(self):
        """deliverable-verify is not in CHECKS; pricing it there was a KeyError."""
        self.confirm_deliverable_contract()
        cost = validate.specs_for("deliverable")["deliverable-verify"]["credits"]
        self.assertEqual(cost, 1)
        import inspect
        source = inspect.getsource(validate.run)
        self.assertNotIn("CHECKS[name]", source)


class TestTheEstimateFollowsTheProfileCount(ValidateTest):
    """The two per-profile checks bill by results, so a fixed guess is wrong.

    people-count is free and reports the real number. These pin that the
    estimate uses it, and that turning contact info off actually halves the
    decision-makers figure rather than only changing the wording.
    """

    def test_the_published_figures_assume_five_profiles(self):
        self.assertEqual(validate.ASSUMED_PROFILES, 5)
        self.assertEqual(validate.estimate(["decision-makers"])["total"], 10)
        self.assertEqual(validate.estimate(["people-search"])["total"], 5)

    def test_a_real_count_replaces_the_assumption(self):
        priced = validate.estimate(["decision-makers", "people-search"],
                                   profiles=7)
        self.assertEqual(priced["total"], 7 * 2 + 7)

    def test_declining_contact_info_halves_the_decision_makers_cost(self):
        with_info = validate.estimate(["decision-makers"], profiles=7)["total"]
        without = validate.estimate(["decision-makers"], profiles=7,
                                    reveal=False)["total"]
        self.assertEqual(with_info, 14)
        self.assertEqual(without, 7)

    def test_people_search_is_unaffected_by_reveal(self):
        self.assertEqual(
            validate.estimate(["people-search"], profiles=7, reveal=False)["total"],
            validate.estimate(["people-search"], profiles=7)["total"])

    def test_the_free_and_fixed_checks_do_not_scale(self):
        priced = validate.estimate(["people-count",
                                    "company-information-from-domain"],
                                   profiles=50)
        self.assertEqual(priced["total"], 1)

    def test_a_bigger_real_count_can_push_a_plan_over_the_ceiling(self):
        """The 15-credit plan that fit at five profiles does not fit at seven."""
        checks = ["decision-makers", "people-search"]
        self.assertEqual(validate.estimate(checks)["total"], 15)
        with self.assertRaises(validate.Refused):
            validate.run(domain="meridian.test", checks=checks, live=True,
                         max_credits=15, profiles=7,
                         raw_sink=os.path.join(self.tmp, "raw"))
        self.assertEqual(self.cassette.calls, [])


class TestContactInfoIsADecision(ValidateTest):
    def test_reveal_is_on_by_default_as_it_always_was(self):
        validate.run(domain="meridian.test", checks=["decision-makers"],
                     live=True, max_credits=10,
                     raw_sink=os.path.join(self.tmp, "raw"))
        self.assertIn("reveal_info=true", self.cassette.urls()[-1])

    def test_no_reveal_asks_for_no_contact_info(self):
        validate.run(domain="meridian.test", checks=["decision-makers"],
                     live=True, max_credits=5, reveal=False,
                     raw_sink=os.path.join(self.tmp, "raw"))
        self.assertIn("reveal_info=false", self.cassette.urls()[-1])

    def test_the_cli_flag_reaches_the_estimate(self):
        code, out = self.cli("--domain", "meridian.test",
                             "--check", "decision-makers",
                             "--expect-profiles", "7", "--no-reveal")
        self.assertEqual(code, 0)
        self.assertIn("NOT bought", out)
        self.assertIn("7 profile(s) expected", out)

    def test_the_run_says_the_estimate_is_not_the_bill(self):
        """These bill per profile returned, and no cap can stop that."""
        code, out = self.cli("--domain", "meridian.test",
                             "--check", "decision-makers",
                             "--expect-profiles", "7", "--no-reveal",
                             "--live-validation", "--max-credits", "7")
        self.assertIn("bill per profile RETURNED", out)


class TestWhatWasActuallyBilled(ValidateTest):
    """The estimate is a plan. The response says what was really charged."""

    ANSWER = {"status_code": 200,
              "metadata": {"page": 1, "page_size": 25, "total_results": 1},
              "profiles": {"https://www.linkedin.com/in/x": {"full_name": "X"}}}

    def test_the_profile_count_is_read_from_the_profiles_map(self):
        self.assertEqual(validate.profiles_returned(self.ANSWER), 1)

    def test_a_list_of_profiles_is_counted_too(self):
        self.assertEqual(validate.profiles_returned({"profiles": [1, 2, 3]}), 3)

    def test_the_metadata_total_is_the_fallback(self):
        self.assertEqual(
            validate.profiles_returned({"metadata": {"total_results": 4}}), 4)

    def test_an_answer_that_says_nothing_gives_no_figure_rather_than_a_guess(self):
        self.assertIsNone(validate.profiles_returned({"status_code": 200}))
        self.assertIsNone(validate.profiles_returned(None))

    def test_the_billed_cost_follows_the_profiles_returned(self):
        self.assertEqual(validate.observed_cost("decision-makers", self.ANSWER), 2)
        self.assertEqual(
            validate.observed_cost("decision-makers", self.ANSWER, reveal=False), 1)
        self.assertEqual(validate.observed_cost("people-search", self.ANSWER), 1)

    def test_a_check_that_does_not_bill_per_profile_reports_nothing(self):
        self.assertIsNone(validate.observed_cost("people-count", self.ANSWER))
        self.assertIsNone(validate.observed_cost("email-verifier", self.ANSWER))

    def test_a_run_records_what_the_response_said_it_billed(self):
        result = validate.run(domain="meridian.test", checks=["decision-makers"],
                              live=True, max_credits=10,
                              raw_sink=os.path.join(self.tmp, "raw"))
        self.assertTrue(result["counted"])
        self.assertEqual(result["counted"][0]["check"], "decision-makers")
        self.assertIsNotNone(result["counted"][0]["profiles"])

    def test_the_observed_total_is_reported_separately_from_the_estimate(self):
        result = validate.run(domain="meridian.test", checks=["decision-makers"],
                              live=True, max_credits=10,
                              raw_sink=os.path.join(self.tmp, "raw"))
        self.assertIn("observed", result)
        self.assertNotEqual(result["observed"], result["estimate"]["total"],
                            "the cassette returns fewer profiles than assumed")


class TestRedaction(ValidateTest):
    def test_an_address_is_redacted(self):
        self.assertEqual(validate.redact("write to someone@mine.test now"),
                         "write to so***@mine.test now")

    def test_a_token_in_a_url_is_redacted(self):
        self.assertIn("token=***",
                      validate.redact("https://api.example.com/x?token=abc123"))

    def test_the_cli_never_prints_the_address_in_full(self):
        _, out = self.cli("--domain", "mine.test", "--email", "someone@mine.test")
        self.assertNotIn("someone@mine.test", out)
        self.assertIn("so***@mine.test", out)


class TestNothingIsWrittenToTheQueue(ValidateTest):
    def test_the_module_never_touches_the_queue(self):
        import inspect
        source = inspect.getsource(validate)
        self.assertNotIn("store.save", source)
        self.assertNotIn("store.append", source)
        self.assertNotIn("store.patch", source)

    def test_a_live_validation_leaves_no_record_behind(self):
        validate.run(domain="meridian.test", checks=["people-count"], live=True,
                     max_credits=0, raw_sink=os.path.join(self.tmp, "raw"))
        from src import store
        self.assertEqual(store.load(), [])


if __name__ == "__main__":
    unittest.main()
