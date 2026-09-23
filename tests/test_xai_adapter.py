"""xAI (Grok) adapter tests.  TASK-157, migrated to Responses API in TASK-182.

Every test replays a hand-written cassette.  No test reaches a real API,
spends credits, or touches a production path.

The cassette lives at tests/fixtures/cassettes/xai.json.  Each entry carries
a body_contains marker so tests do not consume each other's responses:

    __xai_check__      health-check response
    Hello              regular respond
    Search for news    tool-enabled respond
    __xai_retry__      retry-on-5xx test (three entries: fail, fail, success)
    __xai_auth_error__ 401 authentication error

A cassette-backed suite cannot tell you the provider changed.  The drift test
(TestXaiDrift) pins the endpoint path and tool-type string so a deprecation
surfaces as a red test rather than a green suite against a dead endpoint.
"""
import os
import unittest

from src import providers
from src.providers import xai
from tests.base import ProviderTest


# This module exercises code that writes `os.environ` ITSELF - its own `XaiTest.setUp` sets the key and nothing unsets it - so
# restoring only what the tests set is not enough. Measured 2026-09-23: it
# left XAI_API_KEY set for every module that ran afterwards.
#
# Module-level, because the writes happen inside the code under test rather
# than in any one setUp, and a module is responsible for the side effects of
# what it exercises.
_ENV_BEFORE_MODULE = None


def setUpModule():
    global _ENV_BEFORE_MODULE
    _ENV_BEFORE_MODULE = dict(os.environ)


def tearDownModule():
    from tests.envisolation import restore
    restore(_ENV_BEFORE_MODULE)


class XaiTest(ProviderTest):
    def setUp(self):
        super().setUp()
        os.environ["XAI_API_KEY"] = "test-key-not-real"

    def clear_xai_key(self):
        """Remove XAI_API_KEY from the environment.

        ProviderTest.clear_keys() clears KEY_VARS, which does not include
        XAI_API_KEY (it is new to this module).  Tests that exercise the
        missing-key path must call this explicitly.
        """
        os.environ.pop("XAI_API_KEY", None)


class TestXaiCheck(XaiTest):
    def test_default_check_spends_nothing_and_makes_no_call(self):
        r = xai.check()
        self.assertTrue(r["skipped"])
        self.assertIsNone(r["ok"])
        self.assertEqual(self.cassette.calls, [])
        self.assertIn("no call made", r["note"])

    def test_live_check_calls_the_api(self):
        r = xai.check(live=True)
        self.assertTrue(r["ok"])
        self.assertEqual(len(self.cassette.calls), 1)
        self.assertIn("/v1/responses", self.cassette.calls[0]["url"])

    def test_missing_key_reports_by_name(self):
        self.clear_xai_key()
        r = xai.check()
        self.assertFalse(r["ok"])
        self.assertIn("XAI_API_KEY", r["note"])
        self.assertEqual(self.cassette.calls, [])

    def test_missing_key_raises_on_respond(self):
        self.clear_xai_key()
        with self.assertRaises(providers.MissingKey) as ctx:
            xai.respond([{"role": "user", "content": "hi"}])
        self.assertIn("XAI_API_KEY", str(ctx.exception))

    def test_check_auth_failure_returns_not_ok(self):
        """A 401 from the API is reported, not swallowed."""
        self.clear_keys()
        os.environ["XAI_API_KEY"] = "bad-key"
        with self.assertRaises(providers.ProviderError) as ctx:
            xai.respond([{"role": "user", "content": "__xai_auth_error__"}])
        self.assertIn("401", str(ctx.exception))

    def test_check_does_not_leak_the_key(self):
        r = xai.check(live=True)
        self.assertNotIn("test-key-not-real", str(r))


class TestXaiAuth(XaiTest):
    def test_bearer_token_in_authorization_header(self):
        xai.check(live=True)
        h = self.cassette.calls[0]["headers"]
        self.assertEqual(h["Authorization"], "Bearer test-key-not-real")


class TestXaiRespond(XaiTest):
    def test_request_body_shape(self):
        xai.respond([{"role": "user", "content": "Hello"}])
        call = self.cassette.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertIn("/v1/responses", call["url"])
        self.assertEqual(call["body"]["model"], "grok-4.6")
        self.assertEqual(call["body"]["input"],
                         [{"role": "user", "content": "Hello"}])

    def test_response_is_trimmed(self):
        result = xai.respond([{"role": "user", "content": "Hello"}])
        self.assertEqual(set(result), set(xai.RESPONSE_FIELDS))
        self.assertEqual(result["content"], "Hello! How can I help you today?")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["model"], "grok-4.6")

    def test_no_tools_in_request_by_default(self):
        """web_search and x_search are OPT-IN.  A default call has none."""
        xai.respond([{"role": "user", "content": "Hello"}])
        body = self.cassette.calls[0]["body"]
        self.assertNotIn("tools", body)
        body_text = str(body)
        self.assertNotIn("web_search", body_text)
        self.assertNotIn("x_search", body_text)

    def test_tools_included_when_explicitly_passed(self):
        xai.respond([{"role": "user", "content": "Search for news"}],
                    tools=[{"type": "web_search"}])
        body = self.cassette.calls[0]["body"]
        self.assertIn("tools", body)
        self.assertEqual(body["tools"], [{"type": "web_search"}])

    def test_max_tokens_capped(self):
        xai.respond([{"role": "user", "content": "Hello"}], max_tokens=99999)
        body = self.cassette.calls[0]["body"]
        self.assertEqual(body["max_output_tokens"], xai.MAX_TOKENS_CAP)

    def test_max_tokens_respected_when_under_cap(self):
        xai.respond([{"role": "user", "content": "Hello"}], max_tokens=100)
        body = self.cassette.calls[0]["body"]
        self.assertEqual(body["max_output_tokens"], 100)

    def test_temperature_in_body(self):
        xai.respond([{"role": "user", "content": "Hello"}], temperature=0.5)
        body = self.cassette.calls[0]["body"]
        self.assertEqual(body["temperature"], 0.5)

    def test_model_allowlist_enforced(self):
        with self.assertRaises(ValueError) as ctx:
            xai.respond([{"role": "user", "content": "Hello"}],
                        model="not-a-model")
        self.assertIn("allowlist", str(ctx.exception))
        self.assertEqual(self.cassette.calls, [])

    def test_temperature_bounds(self):
        for bad in (-0.1, 2.1, 5.0):
            with self.assertRaises(ValueError):
                xai.respond([{"role": "user", "content": "Hello"}],
                            temperature=bad)
        self.assertEqual(self.cassette.calls, [])

    def test_tool_cap_enforced(self):
        too_many = [{"type": "web_search"}] * (xai.MAX_TOOL_CALLS + 1)
        with self.assertRaises(ValueError) as ctx:
            xai.respond([{"role": "user", "content": "Hello"}], tools=too_many)
        self.assertIn("tools", str(ctx.exception).lower())
        self.assertEqual(self.cassette.calls, [])

    def test_client_error_raises_immediately(self):
        """A 401 is a client error; no retry, immediate ProviderError."""
        with self.assertRaises(providers.ProviderError) as ctx:
            xai.respond([{"role": "user", "content": "__xai_auth_error__"}])
        self.assertIn("401", str(ctx.exception))
        self.assertEqual(len(self.cassette.calls), 1)


class TestXaiUsage(XaiTest):
    def test_usage_captured(self):
        result = xai.respond([{"role": "user", "content": "Hello"}])
        usage = result["usage"]
        self.assertEqual(usage["prompt_tokens"], 10)
        self.assertEqual(usage["completion_tokens"], 20)
        self.assertEqual(usage["total_tokens"], 30)
        self.assertEqual(usage["cost_in_usd_ticks"], 200000)

    def test_cached_tokens_captured(self):
        result = xai.respond([{"role": "user", "content": "Hello"}])
        self.assertEqual(result["usage"]["cached_tokens"], 2)

    def test_cost_ticks_to_usd(self):
        self.assertAlmostEqual(xai.ticks_to_usd(10_000_000_000), 1.0)
        self.assertAlmostEqual(xai.ticks_to_usd(200_000), 0.00002)
        self.assertIsNone(xai.ticks_to_usd(None))
        self.assertIsNone(xai.ticks_to_usd(-1))

    def test_server_side_tool_usage_captured(self):
        result = xai.respond([{"role": "user", "content": "Search for news"}],
                             tools=[{"type": "web_search"}])
        nsstu = result["usage"].get("num_server_side_tools_used")
        self.assertIsNotNone(nsstu)
        self.assertEqual(nsstu, 1)

    def test_num_sources_used_captured(self):
        result = xai.respond([{"role": "user", "content": "Search for news"}],
                             tools=[{"type": "web_search"}])
        self.assertEqual(result["usage"]["num_sources_used"], 2)

    def test_reasoning_tokens_captured(self):
        result = xai.respond([{"role": "user", "content": "Search for news"}],
                             tools=[{"type": "web_search"}])
        self.assertEqual(result["usage"]["reasoning_tokens"], 5)

    def test_no_server_side_tools_when_absent(self):
        result = xai.respond([{"role": "user", "content": "Hello"}])
        self.assertNotIn("num_server_side_tools_used", result["usage"])


class TestXaiToolCalls(XaiTest):
    def test_tool_calls_returned_when_present(self):
        """If the model returns tool call items, they are captured."""
        result = xai.respond([{"role": "user", "content": "Search for news"}],
                             tools=[{"type": "web_search"}])
        self.assertIsNotNone(result["tool_calls"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["tool_calls"][0]["type"], "web_search_call")
        self.assertEqual(result["tool_calls"][0]["id"], "wsc-1")

    def test_tool_calls_none_when_absent(self):
        result = xai.respond([{"role": "user", "content": "Hello"}])
        self.assertIsNone(result["tool_calls"])

    def test_search_urls_extracted(self):
        result = xai.respond([{"role": "user", "content": "Search for news"}],
                             tools=[{"type": "web_search"}])
        self.assertEqual(len(result["search_urls"]), 2)
        self.assertIn("https://example.com/news1", result["search_urls"])
        self.assertIn("https://example.com/news2", result["search_urls"])

    def test_search_urls_empty_when_no_search(self):
        result = xai.respond([{"role": "user", "content": "Hello"}])
        self.assertEqual(result["search_urls"], [])


class TestXaiRetry(XaiTest):
    def test_retries_on_5xx_then_succeeds(self):
        """Two 500s then a 200.  Three calls total, result is the success."""
        result = xai.respond([{"role": "user", "content": "__xai_retry__"}],
                             max_attempts=3, sleep=lambda s: None)
        self.assertEqual(len(self.cassette.calls), 3)
        self.assertEqual(result["content"], "recovered")

    def test_retries_exhausted_raises(self):
        """All attempts fail: ProviderError, not a silent None."""
        with self.assertRaises(providers.ProviderError):
            xai.respond([{"role": "user", "content": "__xai_retry__"}],
                        max_attempts=2, sleep=lambda s: None)
        self.assertEqual(len(self.cassette.calls), 2)

    def test_no_retry_on_4xx(self):
        """A 401 is a client error; retrying would not help."""
        with self.assertRaises(providers.ProviderError):
            xai.respond([{"role": "user", "content": "__xai_auth_error__"}])
        self.assertEqual(len(self.cassette.calls), 1)


class TestXaiSafety(XaiTest):
    def test_content_is_not_treated_as_evidence(self):
        """The docstring states the rule: a Grok answer is a claim with a
        source, or it is not evidence."""
        self.assertIn("claim", xai.respond.__doc__.lower())
        self.assertIn("evidence", xai.respond.__doc__.lower())

    def test_no_raw_payload_escapes(self):
        """The return dict is trimmed to RESPONSE_FIELDS; nothing else escapes."""
        result = xai.respond([{"role": "user", "content": "Hello"}])
        for field in result:
            self.assertIn(field, xai.RESPONSE_FIELDS)

    def test_module_has_no_send_or_activate_verb(self):
        """The adapter cannot start anything.  It is a read-only intelligence
        endpoint, not a sender."""
        names = [n for n in dir(xai) if not n.startswith("_")]
        for banned in ("send", "push", "activate", "resume", "launch",
                       "start", "add_lead"):
            self.assertNotIn(banned, names)

    def test_refusal_captured_when_present(self):
        """If the model refuses, the refusal reason is in the result."""
        original = providers.request

        def fake_request(method, url, headers=None, body=None, timeout=None):
            return 200, {
                "id": "ref-1", "object": "response", "model": "grok-4.6",
                "status": "completed",
                "output": [{"type": "message", "role": "assistant",
                            "status": "completed",
                            "content": [{"type": "refusal",
                                         "text": "I cannot help with that."}]}],
                "usage": {"input_tokens": 10, "output_tokens": 5,
                          "total_tokens": 15, "cost_in_usd_ticks": 100000}}

        prev = providers.set_transport(fake_request)
        try:
            result = xai.respond([{"role": "user", "content": "something"}])
        finally:
            providers.set_transport(prev)

        self.assertEqual(result["refusal"], "I cannot help with that.")
        self.assertIsNone(result["content"])


class TestXaiBounds(unittest.TestCase):
    """Unit tests for the bound constants themselves."""

    def test_max_tokens_cap_is_positive(self):
        self.assertGreater(xai.MAX_TOKENS_CAP, 0)

    def test_max_tool_calls_is_positive(self):
        self.assertGreater(xai.MAX_TOOL_CALLS, 0)

    def test_max_retries_is_non_negative(self):
        self.assertGreaterEqual(xai.MAX_RETRIES, 0)

    def test_timeout_is_bounded(self):
        self.assertGreater(xai.XAI_TIMEOUT, 0)
        self.assertLessEqual(xai.XAI_TIMEOUT, 300)

    def test_models_is_a_non_empty_tuple(self):
        self.assertIsInstance(xai.MODELS, tuple)
        self.assertGreater(len(xai.MODELS), 0)

    def test_default_model_is_in_allowlist(self):
        self.assertIn(xai.DEFAULT_MODEL, xai.MODELS)

    def test_opt_in_tools_are_named(self):
        self.assertIn("web_search", xai.OPT_IN_TOOLS)
        self.assertIn("x_search", xai.OPT_IN_TOOLS)

    def test_ticks_per_usd_constant(self):
        """10 billion ticks per dollar, per the xAI documentation."""
        self.assertEqual(xai.TICKS_PER_USD, 10_000_000_000)


class TestXaiDrift(XaiTest):
    """A cassette-backed suite cannot tell you the provider changed.

    On 2026-09-15 xAI withdrew the Chat Completions endpoint (HTTP 410 Gone)
    and moved web search to the Responses API.  The adapter's 42 tests kept
    passing because a fake transport faithfully fakes whatever endpoint you
    point it at - including one that no longer exists.

    These tests pin the endpoint path and tool-type string so a future
    deprecation surfaces as a red test, not a silent green suite.
    """

    def test_endpoint_is_responses_api(self):
        """The adapter must call /v1/responses, not /v1/chat/completions.

        A passing fake proves nothing about the provider.  This test pins the
        actual endpoint path so a provider-side deprecation is detected."""
        xai.respond([{"role": "user", "content": "Hello"}])
        url = self.cassette.calls[0]["url"]
        self.assertIn("/v1/responses", url)
        self.assertNotIn("/chat/completions", url)

    def test_web_search_tool_type_string(self):
        """The tool type must be 'web_search', matching the Responses API.

        The Chat Completions API used the same string, but if xAI ever renames
        it (as they have before), this test catches the drift."""
        self.assertEqual(xai.OPT_IN_TOOLS[0], "web_search")
        xai.respond([{"role": "user", "content": "Search for news"}],
                    tools=[{"type": "web_search"}])
        body = self.cassette.calls[0]["body"]
        self.assertIn({"type": "web_search"}, body["tools"])

    def test_request_uses_input_not_messages(self):
        """The Responses API uses 'input', not 'messages'.

        If the adapter drifts back to 'messages', the real API rejects it."""
        xai.respond([{"role": "user", "content": "Hello"}])
        body = self.cassette.calls[0]["body"]
        self.assertIn("input", body)
        self.assertNotIn("messages", body)

    def test_request_uses_max_output_tokens(self):
        """The Responses API uses 'max_output_tokens', not
        'max_completion_tokens'."""
        xai.respond([{"role": "user", "content": "Hello"}], max_tokens=100)
        body = self.cassette.calls[0]["body"]
        self.assertIn("max_output_tokens", body)
        self.assertNotIn("max_completion_tokens", body)


if __name__ == "__main__":
    unittest.main()
