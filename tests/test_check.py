"""src/check.py: seven providers, three outcomes.

The outcome that matters most is SKIP. A provider that would have to spend a
credit to prove it is alive is not called, and the report says so rather than
quietly showing a green tick nobody paid for.
"""
import io
import unittest
from contextlib import redirect_stdout

from src import check, providers
from tests.base import ProviderTest


def run_cli(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = check.main(list(argv))
    return code, buf.getvalue()


class TestAllNineProviders(ProviderTest):
    def test_every_provider_is_reported_in_a_fixed_order(self):
        results = check.run()
        self.assertEqual([r["provider"] for r in results], list(check.PROVIDERS))
        # Eight, which is what the documentation has always
        # claimed. Slack was absent from the sweep, so
        # `python -m src.check` never touched the one
        # integration whose health nobody could otherwise see.
        self.assertEqual(len(results), 9)
        self.assertEqual(len(results), len(check.PROVIDERS))

    def test_the_four_free_health_calls_succeed(self):
        by_name = {r["provider"]: r for r in check.run()}
        for name in ("ContactOut", "Blitz", "AI Ark", "EmailBison",
                     "HeyReach", "Apify"):
            self.assertTrue(by_name[name]["ok"], name)

    def test_the_two_that_would_cost_money_are_skipped_not_called(self):
        by_name = {r["provider"]: r for r in check.run()}
        for name in ("Reoon", "Deliverable"):
            self.assertTrue(by_name[name]["skipped"], name)
            self.assertIsNone(by_name[name]["ok"], name)

    def test_the_cli_prints_a_line_per_provider_and_a_summary(self):
        code, out = run_cli()
        self.assertEqual(code, 0)
        for name in check.PROVIDERS:
            self.assertIn(name, out)
        self.assertIn("6 ok, 3 skipped, 0 failed, of 9", out)
        self.assertIn("skipped means not called on purpose", out)

    def test_a_skip_is_not_counted_as_a_failure(self):
        code, _ = run_cli()
        self.assertEqual(code, 0)

    def test_no_key_leaks_into_the_report(self):
        _, out = run_cli()
        self.assertNotIn("test-key-not-real", out)

    def test_a_missing_key_turns_that_provider_red_and_exits_one(self):
        self.clear_keys()
        code, out = run_cli()
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        self.assertIn("no CONTACTOUT_TOKEN", out)

    def test_a_rejected_key_turns_only_that_provider_red(self):
        def unauthorised(method, url, headers, body, timeout):
            if "heyreach" in url:
                return 401, '{"error": "unauthorized"}'
            return self.cassette(method, url, headers, body, timeout)

        providers.set_transport(unauthorised)
        code, out = run_cli()
        self.assertEqual(code, 1)
        self.assertIn("FAIL HeyReach", out)
        self.assertRegex(out, r"ok\s+ContactOut")

    def test_an_unreachable_provider_turns_red_without_raising(self):
        def dead(method, url, headers, body, timeout):
            if "contactout" in url:
                raise providers.ProviderError("URLError: getaddrinfo failed")
            return self.cassette(method, url, headers, body, timeout)

        providers.set_transport(dead)
        code, out = run_cli()
        self.assertEqual(code, 1)
        self.assertIn("FAIL ContactOut", out)
        self.assertIn("getaddrinfo", out)


class TestCheckIsCreditSafe(ProviderTest):
    def test_reoon_is_never_called_by_default(self):
        check.run()
        self.assertEqual([u for u in self.cassette.urls() if "reoon" in u], [])

    def test_deliverable_is_never_called_while_its_contract_is_unconfirmed(self):
        check.run()
        self.assertEqual([u for u in self.cassette.urls() if "deliverable" in u], [])

    def test_live_reoon_is_opt_in_and_says_so(self):
        check.run(live_reoon=True)
        self.assertTrue(any("emailverifier.reoon.com" in u
                            for u in self.cassette.urls()))

    def test_every_default_call_is_a_free_read(self):
        check.run()
        for call in self.cassette.calls:
            if "ai-ark" in call["url"]:
                self.assertEqual(call["body"]["method"], "tools/list")
                continue
            self.assertEqual(call["method"], "GET", call["url"])
        urls = " ".join(self.cassette.urls())
        for paid in ("decision-makers", "people-search", "email-verifier",
                     "company-information-from-domain", "emailverifier.reoon.com"):
            self.assertNotIn(paid, urls, paid)

    def test_check_never_posts_a_lead_or_starts_an_actor(self):
        check.run()
        for call in self.cassette.calls:
            self.assertNotIn("leads", call["url"].lower())
            self.assertNotIn("AddLeads", call["url"])
            self.assertNotIn("/runs", call["url"])

    def test_the_apify_check_reads_account_metadata_only(self):
        check.run()
        apify_calls = [c for c in self.cassette.calls if "apify" in c["url"]]
        self.assertTrue(apify_calls)
        for call in apify_calls:
            self.assertEqual(call["method"], "GET")
            self.assertIn("/users/me", call["url"])


if __name__ == "__main__":
    unittest.main()
