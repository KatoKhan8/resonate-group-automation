"""Three things the offline suite could not have caught, and now cannot lose.

Every one of these was a real failure against the live providers, found by the
health check on the day the credentials were first configured. A cassette
replays whatever it was recorded with, so none of them could show up offline:
they live in the headers and the query string, which is exactly what these tests
pin down.

  1. urllib identifies itself as "Python-urllib/x.y", and ContactOut sits behind
     a WAF that answers 403 Cloudflare 1010 to it.
  2. Streamable-HTTP MCP wants `Accept: application/json, text/event-stream`.
     AI Ark answers 400 with an empty body to anything less.
  3. ContactOut's `period` is a YYYY-MM month. The literal word "month" earns
     "Invalid date format".
"""
import unittest
import urllib.request

from src import providers
from src.providers import aiark, contactout
from tests.base import ProviderTest


class TestTheClientIdentifiesItself(unittest.TestCase):
    """The header is added in the transport, below every provider module."""

    def setUp(self):
        self.captured = {}

        def fake_urlopen(req, timeout=None):
            self.captured["headers"] = dict(req.header_items())
            self.captured["method"] = req.get_method()
            self.captured["url"] = req.full_url
            raise urllib.error.HTTPError(req.full_url, 200, "OK", {},
                                         _Body(b'{"ok":true}'))

        self._real = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen

    def tearDown(self):
        urllib.request.urlopen = self._real

    def headers(self):
        return {k.lower(): v for k, v in self.captured["headers"].items()}

    def test_a_user_agent_is_always_sent(self):
        providers._urllib_transport("GET", "https://example.test/x", {}, None, 5)
        self.assertIn("user-agent", self.headers())
        self.assertNotIn("python-urllib", self.headers()["user-agent"].lower())

    def test_the_user_agent_names_this_tool_rather_than_a_browser(self):
        agent = providers.USER_AGENT.lower()
        self.assertIn("resonate", agent)
        for browser in ("mozilla", "chrome", "safari", "gecko", "webkit"):
            self.assertNotIn(browser, agent, "it must not pretend to be a browser")

    def test_a_provider_that_sets_its_own_user_agent_keeps_it(self):
        providers._urllib_transport("GET", "https://example.test/x",
                                    {"User-Agent": "custom/9"}, None, 5)
        self.assertEqual(self.headers()["user-agent"], "custom/9")

    def test_an_explicit_accept_is_not_overwritten(self):
        providers._urllib_transport(
            "GET", "https://example.test/x",
            {"Accept": "application/json, text/event-stream"}, None, 5)
        self.assertEqual(self.headers()["accept"],
                         "application/json, text/event-stream")

    def test_a_body_is_still_sent_as_json(self):
        providers._urllib_transport("POST", "https://example.test/x", {},
                                    {"a": 1}, 5)
        self.assertEqual(self.headers()["content-type"], "application/json")


class _Body:
    """The minimum HTTPError needs to hand back a body - and to be closed.

    `closed` is part of that minimum: `HTTPError.close()` reads it, so a
    stub without it turns a caller that correctly closes the response into
    an AttributeError.
    """

    def __init__(self, data):
        self._data = data
        self.closed = False

    def read(self):
        return self._data

    def close(self):
        self.closed = True


class TestTheMcpAcceptHeader(ProviderTest):
    def test_every_rpc_call_asks_for_both_content_types(self):
        aiark.rpc("tools/list")
        accept = self.cassette.calls[-1]["headers"].get("Accept", "")
        self.assertIn("application/json", accept)
        self.assertIn("text/event-stream", accept)

    def test_the_header_is_declared_once_rather_than_per_call_site(self):
        self.assertIn("text/event-stream", aiark.RPC_HEADERS["Accept"])


class TestTheContactOutStatsCall(ProviderTest):
    def test_the_health_check_sends_no_literal_word_as_a_period(self):
        contactout.check()
        url = self.cassette.urls()[-1]
        self.assertNotIn("period=month", url)

    def test_it_asks_for_stats_and_nothing_that_costs(self):
        contactout.check()
        url = self.cassette.urls()[-1]
        self.assertTrue(url.endswith("/stats"), url)
        for paid in ("people-search", "decision-makers", "email-verifier",
                     "company-information-from-domain"):
            self.assertNotIn(paid, url)

    def test_a_period_that_is_ever_sent_again_must_be_a_year_month(self):
        import inspect
        import re
        source = inspect.getsource(contactout)
        for match in re.finditer(r'"period":\s*"([^"]*)"', source):
            self.assertRegex(match.group(1), r"^\d{4}-\d{2}$|^\{",
                             "period is a YYYY-MM month, not a word")


if __name__ == "__main__":
    unittest.main()
