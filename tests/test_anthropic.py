"""Anthropic provider, offline.  TASK-308.

Every test replays a hand-written cassette.  No test reaches the Anthropic
API, spends a dollar, or writes a real ledger row.

The acceptance command from the task file:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import spendledger as s;\\
    rows=[r for r in s.load() if r.get('provider')=='anthropic'];\
    print(len(rows),'rows', sum(r.get('amount',0) for r in rows),'in', \
    {r.get('unit') for r in rows}); assert rows and all(r.get('unit')=='usd' for r in rows)"
"""
import json
import os
import unittest

from src import providers, spendledger
from src.providers import anthropic
from tests.base import ProviderTest


class TestKeyReading(ProviderTest):
    """The key MUST come through providers.model_key("anthropic"), not
    through a bare os.environ.get.  That is the whole point of a230771e."""

    def test_model_key_returns_the_test_key(self):
        value, name = providers.model_key("anthropic")
        self.assertEqual(value, "test-key-not-real")
        self.assertEqual(name, "ANTHROPIC_API_KEY")

    def test_missing_key_raises_classified(self):
        self.clear_keys()
        with self.assertRaises(providers.MissingKey):
            anthropic._headers()

    def test_check_without_key_reports_failure(self):
        self.clear_keys()
        result = anthropic.check()
        self.assertFalse(result["ok"])
        self.assertIn("ANTHROPIC_API_KEY", result["note"])

    def test_check_with_key_skips_by_default(self):
        result = anthropic.check()
        self.assertIsNone(result["ok"])
        self.assertTrue(result["skipped"])
        self.assertIn("claude-sonnet-5", result["note"])


class TestHeaders(ProviderTest):
    """Anthropic uses x-api-key, not Bearer tokens."""

    def test_headers_use_x_api_key(self):
        hdrs = anthropic._headers()
        self.assertEqual(hdrs["x-api-key"], "test-key-not-real")
        self.assertNotIn("authorization", hdrs)

    def test_headers_include_anthropic_version(self):
        hdrs = anthropic._headers()
        self.assertIn("anthropic-version", hdrs)
        self.assertEqual(hdrs["anthropic-version"], "2023-06-01")

    def test_no_key_leaks_into_redact_output(self):
        """Even if an error message quotes headers, the key is redacted."""
        hdrs = anthropic._headers()
        redacted = providers.redact(hdrs)
        self.assertNotIn("test-key-not-real", str(redacted))


class TestComplete(ProviderTest):
    """Single-message completion through the Messages API."""

    def test_complete_returns_content_and_usage(self):
        result = anthropic.complete(
            system="You write cold outreach.",
            user="Write to: Ivana Saric, CEO at Meridian (meridian.test)",
        )
        self.assertIn("margin visibility", result["content"])
        self.assertEqual(result["model"], "claude-sonnet-5")
        self.assertEqual(result["stop_reason"], "end_turn")
        self.assertIsInstance(result["usage"], dict)
        self.assertIsInstance(result["cost_usd"], float)
        self.assertGreater(result["cost_usd"], 0)
        self.assertIn("seconds", result)

    def test_complete_sends_system_separately(self):
        """Anthropic's API puts `system` at the top level, not in messages."""
        anthropic.complete(
            system="You write cold outreach.",
            user="simple test prompt",
        )
        call = self.cassette.calls[-1]
        body = call["body"]
        self.assertEqual(body["system"], "You write cold outreach.")
        roles = [m["role"] for m in body["messages"]]
        self.assertNotIn("system", roles)
        self.assertEqual(roles, ["user"])

    def test_complete_sends_x_api_key_header(self):
        anthropic.complete(system="s", user="simple test prompt")
        call = self.cassette.calls[-1]
        self.assertEqual(call["headers"]["x-api-key"], "test-key-not-real")
        self.assertNotIn("authorization", call["headers"])

    def test_complete_calls_the_anthropic_endpoint(self):
        anthropic.complete(system="s", user="simple test prompt")
        call = self.cassette.calls[-1]
        self.assertTrue(call["url"].endswith("/v1/messages"))
        self.assertIn("api.anthropic.com", call["url"])

    def test_complete_usage_includes_cache_tokens(self):
        result = anthropic.complete(
            system="You write cold outreach.",
            user="Write to: Ivana Sarac, CEO at Meridian (meridian.test)",
        )
        usage = result["usage"]
        self.assertEqual(usage["input_tokens"], 1200)
        self.assertEqual(usage["output_tokens"], 350)
        self.assertEqual(usage["cache_creation_input_tokens"], 800)
        self.assertEqual(usage["cache_read_input_tokens"], 400)

    def test_complete_rejects_unknown_model(self):
        with self.assertRaises(ValueError):
            anthropic.complete(
                system="s", user="u", model="no-such-model")


class TestCostCalculation(unittest.TestCase):
    """Cost comes from the response's own usage block, priced from the table.

    An estimated cost presented as a measured one is worse than no number.
    """

    def test_standard_pricing(self):
        usage = {"input_tokens": 1_000_000, "output_tokens": 100_000,
                 "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0}
        cost = anthropic.cost_from_usage(usage, batch=False)
        # 1M input * $2/MTok + 100k output * $10/MTok = $2 + $1 = $3
        self.assertAlmostEqual(cost, 3.0, places=6)

    def test_batch_pricing_is_half(self):
        usage = {"input_tokens": 1_000_000, "output_tokens": 100_000,
                 "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0}
        cost = anthropic.cost_from_usage(usage, batch=True)
        # 1M input * $1/MTok + 100k output * $5/MTok = $1 + $0.5 = $1.5
        self.assertAlmostEqual(cost, 1.5, places=6)

    def test_cache_tokens_are_priced_separately(self):
        usage = {"input_tokens": 0, "output_tokens": 0,
                 "cache_creation_input_tokens": 1_000_000,
                 "cache_read_input_tokens": 1_000_000}
        cost = anthropic.cost_from_usage(usage, batch=False)
        # 1M cache write * $2.50/MTok + 1M cache read * $0.20/MTok
        self.assertAlmostEqual(cost, 2.70, places=6)

    def test_none_usage_is_zero(self):
        self.assertEqual(anthropic.cost_from_usage(None), 0.0)
        self.assertEqual(anthropic.cost_from_usage({}), 0.0)

    def test_missing_tokens_are_not_zero_claims(self):
        """Missing evidence is never positive evidence."""
        usage = {"input_tokens": 100}
        cost = anthropic.cost_from_usage(usage, batch=False)
        # Only input: 100 / 1M * $2 = $0.0002
        self.assertAlmostEqual(cost, 0.0002, places=8)

    def test_pricing_source_is_recorded(self):
        self.assertIn("platform.claude.com", anthropic._PRICE_SOURCE)
        self.assertEqual(anthropic._PRICE_DATE, "2026-09-25")


class TestBatchPath(ProviderTest):
    """Batch creation, polling, and result collection."""

    def test_create_batch_sends_requests(self):
        requests = [
            {"custom_id": "lead-1", "system": "sys", "user": "hello"},
            {"custom_id": "lead-2", "system": "sys", "user": "world"},
        ]
        batch = anthropic.create_batch(requests)
        self.assertEqual(batch["id"], "batch_01ABC123")
        self.assertEqual(batch["processing_status"], "in_progress")

        call = self.cassette.calls[-1]
        self.assertIn("/v1/messages/batches", call["url"])
        self.assertEqual(call["method"], "POST")
        body = call["body"]
        self.assertEqual(len(body["requests"]), 2)
        self.assertEqual(body["requests"][0]["custom_id"], "lead-1")

    def test_get_batch_returns_status(self):
        batch = anthropic.get_batch("batch_01ABC123")
        self.assertEqual(batch["processing_status"], "ended")
        self.assertEqual(batch["request_counts"]["succeeded"], 2)
        self.assertEqual(batch["request_counts"]["errored"], 1)

    def test_get_batch_results_parses_jsonl(self):
        results = anthropic.get_batch_results("batch_01ABC123")
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["custom_id"], "lead-1")
        self.assertEqual(results[0]["result"]["type"], "succeeded")
        self.assertEqual(results[2]["custom_id"], "lead-3")
        self.assertEqual(results[2]["result"]["type"], "errored")

    def test_poll_batch_returns_status_and_results(self):
        batch, results = anthropic.poll_batch(
            "batch_01ABC123", poll_interval=0)
        self.assertEqual(batch["processing_status"], "ended")
        self.assertEqual(len(results), 3)

    def test_batch_results_report_both_succeeded_and_errored(self):
        """A batch that returns 2 of 3 is not a batch that failed.
        Both are reported.  A silent drop of 1 lead would look exactly
        like 2 leads having been the plan."""
        _, results = anthropic.poll_batch(
            "batch_01ABC123", poll_interval=0)
        succeeded = [r for r in results
                     if r["result"]["type"] == "succeeded"]
        errored = [r for r in results
                   if r["result"]["type"] == "errored"]
        self.assertEqual(len(succeeded), 2)
        self.assertEqual(len(errored), 1)


class TestErrorClassification(ProviderTest):
    """Failures are classified, never swallowed."""

    def test_auth_failure(self):
        with self.assertRaises(anthropic.AnthropicAuthFailed) as ctx:
            anthropic.complete(system="s", user="auth-test prompt")
        self.assertEqual(ctx.exception.classification, "auth")

    def test_rate_limit_failure(self):
        with self.assertRaises(anthropic.AnthropicRateLimited) as ctx:
            anthropic.complete(
                system="s", user="rate-test prompt", max_attempts=1)
        self.assertEqual(ctx.exception.classification, "rate_limit")

    def test_server_error_failure(self):
        with self.assertRaises(anthropic.AnthropicServerError) as ctx:
            anthropic.complete(
                system="s", user="server-test prompt", max_attempts=1)
        self.assertEqual(ctx.exception.classification, "server_error")


class TestSpendLedger(ProviderTest):
    """Dollar-denominated rows with explicit unit."""

    def test_record_spend_writes_usd_row(self):
        row = anthropic.record_spend(
            client="productive", run_id="test-run",
            cost_usd=0.01234, call="complete")
        self.assertEqual(row["provider"], "anthropic")
        self.assertEqual(row["unit"], "usd")
        self.assertAlmostEqual(row["amount"], 0.01234)
        self.assertEqual(row["expected_cost"], 0)
        self.assertEqual(row["client"], "productive")
        self.assertEqual(row["run_id"], "test-run")

    def test_record_spend_does_not_pollute_credits(self):
        """expected_cost is 0 so the credit-based spent() does not
        double-count dollar rows as credit rows."""
        row = anthropic.record_spend(
            client="productive", run_id="test-run",
            cost_usd=1.50, call="batch")
        self.assertEqual(row["expected_cost"], 0)

    def test_acceptance_command(self):
        """The exact acceptance command from the task file."""
        anthropic.record_spend(
            client="productive", run_id="accept",
            cost_usd=0.05, call="complete")
        anthropic.record_spend(
            client="productive", run_id="accept",
            cost_usd=0.03, call="batch")
        rows = [r for r in spendledger.load()
                if r.get("provider") == "anthropic"]
        self.assertGreaterEqual(len(rows), 2)
        self.assertTrue(all(r.get("unit") == "usd" for r in rows))
        total = sum(r.get("amount", 0) for r in rows)
        self.assertAlmostEqual(total, 0.08, places=6)


class TestNotRoutedThroughOpenRouter(ProviderTest):
    """The whole point of this module: direct to Anthropic, not OpenRouter."""

    def test_endpoint_is_anthropic_not_openrouter(self):
        anthropic.complete(system="s", user="simple test prompt")
        call = self.cassette.calls[-1]
        self.assertIn("api.anthropic.com", call["url"])
        self.assertNotIn("openrouter", call["url"].lower())

    def test_auth_is_x_api_key_not_bearer(self):
        anthropic.complete(system="s", user="simple test prompt")
        call = self.cassette.calls[-1]
        self.assertIn("x-api-key", call["headers"])
        self.assertNotIn("authorization", call["headers"])


class TestParseBatchResults(unittest.TestCase):
    """The JSONL parser handles the shapes the API returns."""

    def test_string_input(self):
        data = '{"custom_id":"a","result":{"type":"succeeded"}}\n{"custom_id":"b","result":{"type":"errored"}}'
        results = anthropic._parse_batch_results(data)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["custom_id"], "a")

    def test_list_input(self):
        data = [{"custom_id": "a", "result": {"type": "succeeded"}}]
        results = anthropic._parse_batch_results(data)
        self.assertEqual(len(results), 1)

    def test_empty_string(self):
        self.assertEqual(anthropic._parse_batch_results(""), [])

    def test_none_returns_empty(self):
        self.assertEqual(anthropic._parse_batch_results(None), [])

    def test_malformed_lines_are_skipped(self):
        data = '{"custom_id":"a","result":{"type":"succeeded"}}\nNOT JSON\n{"custom_id":"b","result":{"type":"errored"}}'
        results = anthropic._parse_batch_results(data)
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
