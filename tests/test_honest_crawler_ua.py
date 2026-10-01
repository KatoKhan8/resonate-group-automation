"""The crawler's User-Agent, and robots on every path rather than the first one.

Measured against bigfish.co.uk on 2026-10-01, one variable at a time. The
previous session's claim was "403 because of the User-Agent, even though
robots.txt allows the path". The second half was false: robots.txt ITSELF
answered 403 to our UA, so nothing had read it. The first half was true but
imprecise - the host denies the literal `Mozilla/5.0 (compatible;` prefix, and
serves 200 to `compatible` without `Mozilla/5.0`, to `Mozilla/5.0` without
`compatible`, and to a bare product token plus a `+https://` URL.

Three defects this pins, none of which is about one host:

  1. `webfetch.USER_AGENT` claimed a `+` contact that was not a URL, so it
     announced a bot and offered nobody a way to reach it - and it was the one
     HTTP client in this repo that `test_wire_contracts` never checked.
  2. `respect_robots` was enforced on the FIRST url only. `urllib` follows
     redirects itself, so an allowed page redirecting to a disallowed one was
     read anyway. The paid Apify leg had no robots check at all, while sending
     `useApifyProxy: True`.
  3. Nothing was a rate limit. `request_timeout`, `domain_timeout` and
     `max_pages` bound one read; none of them put a gap between two requests,
     and a stated `Crawl-delay` was parsed and read by nobody.

Every robots assertion below is run twice - once with a file that disallows and
once with a file that allows - because a fetch that is blocked for some other
reason looks exactly like a robots check that works.
"""
import re
import unittest
import urllib.error
import urllib.request
from unittest import mock

from src import research, store, webfetch
from tests.base import QueueTest

ALLOW_ALL = "User-agent: *\nDisallow:\n"
DISALLOW_ALL = "User-agent: *\nDisallow: /\n"
DISALLOW_ABOUT = "User-agent: *\nDisallow: /about\n"
WITH_CRAWL_DELAY = "User-agent: *\nDisallow: /wp-admin/\nCrawl-delay: 10\n"
HUGE_CRAWL_DELAY = "User-agent: *\nDisallow:\nCrawl-delay: 3600\n"

# The string that shipped, kept as the negative control for every assertion
# about the new one. A test that only ever sees the good value cannot fail.
OLD_USER_AGENT = ("Mozilla/5.0 (compatible; ResonateResearch/1.0; "
                  "+company qualification, respects robots.txt)")


def names_a_browser(agent):
    """The rule `tests/test_wire_contracts.py` already applies to providers."""
    agent = (agent or "").lower()
    return any(b in agent for b in ("mozilla", "chrome", "safari", "gecko",
                                    "webkit", "edge/", "opera"))


def offers_a_contact_url(agent):
    """`+` in a UA introduces a dereferenceable URI, not a sentence."""
    return bool(re.search(r"\+https?://[^\s)]+", agent or ""))


class _Headers:
    def __init__(self, content_type):
        self._ct = content_type

    def get_content_type(self):
        return self._ct

    def get_content_charset(self):
        return "utf-8"


class _Answer:
    """Enough of an http.client.HTTPResponse for these paths."""

    def __init__(self, body=b"", status=200, content_type="text/html"):
        self._body = body
        self.status = status
        self.headers = _Headers(content_type)

    def read(self, n=None):
        return self._body if n is None else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Robots:
    """Serves one robots.txt body for any host, and counts the requests."""

    def __init__(self, body, status=200):
        self.body = body
        self.status = status
        self.calls = []

    def __call__(self, request, timeout=None):
        self.calls.append(request.full_url)
        if self.status != 200:
            raise urllib.error.HTTPError(request.full_url, self.status,
                                         "Forbidden", {}, None)
        return _Answer(self.body.encode("utf-8"), 200, "text/plain")


class _Opener:
    """A build_opener stand-in returning one canned answer."""

    def __init__(self, answer_factory):
        self._make = answer_factory
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        return self._make()


class RobotsHarness(unittest.TestCase):
    """Serve a chosen robots.txt, never a socket, and never leak the cache."""

    def setUp(self):
        webfetch.robots_cache_clear()
        self.addCleanup(webfetch.robots_cache_clear)
        # Pacing is real behaviour and is asserted on directly below; here it
        # only has to not make the suite sleep.
        self.slept = []
        patch = mock.patch("src.webfetch.time.sleep", self.slept.append)
        self.addCleanup(patch.stop)
        patch.start()

    def serve_robots(self, body, status=200):
        robots = _Robots(body, status)
        patch = mock.patch("src.webfetch.urllib.request.urlopen", robots)
        self.addCleanup(patch.stop)
        patch.start()
        return robots

    def conf(self, **over):
        out = dict(webfetch.DEFAULTS)
        out.update(over)
        return out


# ------------------------------------------------------ 1. the user agent

class TheUserAgentIsHonestAndIdentifying(unittest.TestCase):

    def test_the_user_agent_does_not_claim_to_be_a_browser(self):
        self.assertFalse(names_a_browser(webfetch.USER_AGENT),
                         webfetch.USER_AGENT)

    def test_and_the_string_that_shipped_would_have_failed_that(self):
        """NEGATIVE CONTROL. Without this the assertion above is unfalsified."""
        self.assertTrue(names_a_browser(OLD_USER_AGENT))

    def test_the_user_agent_offers_a_dereferenceable_contact_url(self):
        self.assertTrue(offers_a_contact_url(webfetch.USER_AGENT),
                        webfetch.USER_AGENT)

    def test_and_the_string_that_shipped_offered_prose_instead(self):
        """NEGATIVE CONTROL. `+company qualification` reaches nobody."""
        self.assertFalse(offers_a_contact_url(OLD_USER_AGENT))

    def test_the_user_agent_still_names_this_product(self):
        """Honest is not anonymous: an operator must be able to identify us."""
        self.assertIn("resonate", webfetch.USER_AGENT.lower())

    def test_it_is_not_the_urllib_default(self):
        self.assertNotIn("python-urllib", webfetch.USER_AGENT.lower())

    def test_no_module_in_this_repo_sends_a_browser_user_agent(self):
        """By import rather than by grep, so a new client that copies the old
        string is caught by this test and not by somebody's 403."""
        from src import providers
        for name, agent in (("webfetch", webfetch.USER_AGENT),
                            ("providers", providers.USER_AGENT)):
            with self.subTest(module=name):
                self.assertFalse(names_a_browser(agent), agent)
                self.assertTrue(offers_a_contact_url(agent), agent)

    def test_the_agent_actually_sent_on_the_wire_is_that_string(self):
        """Not the constant - the header. A constant nothing sends is a comment."""
        webfetch.robots_cache_clear()
        self.addCleanup(webfetch.robots_cache_clear)
        opener = _Opener(lambda: _Answer(b"<html><body>hi</body></html>"))
        with mock.patch("src.webfetch.urllib.request.build_opener",
                        return_value=opener), \
                mock.patch("src.webfetch.time.sleep"):
            conf = dict(webfetch.DEFAULTS, respect_robots=False)
            outcome, status, markup, size = webfetch.fetch(
                "https://example.test/", "example.test", conf)
        self.assertEqual(outcome, webfetch.HTTP_SUCCESS)
        sent = {k.lower(): v for k, v in opener.requests[0].header_items()}
        self.assertEqual(sent.get("user-agent"), webfetch.USER_AGENT)
        self.assertFalse(names_a_browser(sent.get("user-agent")))


# ------------------------------------------- 2. robots on the first request

class RobotsGatesTheFirstRequest(RobotsHarness):

    def test_a_robots_that_disallows_blocks_the_read(self):
        """NEGATIVE CONTROL for the pair below."""
        self.serve_robots(DISALLOW_ALL)
        self.assertFalse(webfetch.robots_allows(
            "https://example.test/", "example.test", self.conf()))

    def test_a_robots_that_allows_permits_the_read(self):
        """POSITIVE CONTROL. Without this, a check that always said no passes."""
        self.serve_robots(ALLOW_ALL)
        self.assertTrue(webfetch.robots_allows(
            "https://example.test/", "example.test", self.conf()))

    def test_research_returns_BLOCKED_and_makes_no_page_request(self):
        self.serve_robots(DISALLOW_ALL)
        with mock.patch("src.webfetch.fetch") as page:
            got = webfetch.research("example.test")
        self.assertEqual(got["outcome"], webfetch.BLOCKED)
        self.assertIn("robots", got["stats"]["outcomes"])
        page.assert_not_called()

    def test_an_unreadable_robots_states_no_rule_rather_than_refusal(self):
        """bigfish.co.uk answered 403 to robots.txt itself. A WAF refusing to
        serve the file has not stated a rule, and calling that a disallow
        reported 30% of a real batch as 'asked us not to'."""
        self.serve_robots("", status=403)
        self.assertTrue(webfetch.robots_allows(
            "https://example.test/", "example.test", self.conf()))

    def test_respect_robots_false_asks_nothing(self):
        robots = self.serve_robots(DISALLOW_ALL)
        self.assertTrue(webfetch.robots_allows(
            "https://example.test/", "example.test",
            self.conf(respect_robots=False)))
        self.assertEqual(robots.calls, [])


# ----------------------------------------------- 3. robots on the redirect

class RobotsGatesEveryRedirect(RobotsHarness):
    """The defect: the check ran once and `urllib` then followed redirects."""

    def redirect_to(self, newurl, limit=3):
        handler = webfetch._BoundedRedirects("example.test", limit, self.conf())
        request = urllib.request.Request("https://example.test/about")
        return handler.redirect_request(request, None, 301, "Moved",
                                        {"Location": newurl}, newurl)

    def test_a_redirect_to_a_disallowed_path_is_refused(self):
        """NEGATIVE CONTROL: /about is disallowed, so the hop must not happen."""
        self.serve_robots(DISALLOW_ABOUT)
        self.assertIsNone(self.redirect_to("https://example.test/about-us"))

    def test_a_redirect_to_an_allowed_path_is_followed(self):
        """POSITIVE CONTROL: same handler, same host, allowed target."""
        self.serve_robots(ALLOW_ALL)
        self.assertIsNotNone(self.redirect_to("https://example.test/team"))

    def test_a_redirect_off_the_domain_is_still_refused(self):
        self.serve_robots(ALLOW_ALL)
        self.assertIsNone(self.redirect_to("https://elsewhere.test/team"))

    def test_the_chain_is_still_bounded(self):
        self.serve_robots(ALLOW_ALL)
        handler = webfetch._BoundedRedirects("example.test", 1, self.conf())
        request = urllib.request.Request("https://example.test/")
        first = handler.redirect_request(request, None, 301, "m", {},
                                         "https://example.test/a")
        second = handler.redirect_request(request, None, 301, "m", {},
                                          "https://example.test/b")
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_a_refused_redirect_is_classified_not_silently_successful(self):
        """`redirect_request` returning None surfaces the 3xx itself, which
        `fetch` classifies NON_2XX. It must never look like a page we read."""
        self.serve_robots(DISALLOW_ABOUT)
        opener = _Opener(lambda: _Answer(b"", 301, "text/html"))
        with mock.patch("src.webfetch.urllib.request.build_opener",
                        return_value=opener):
            outcome, status, markup, size = webfetch.fetch(
                "https://example.test/x", "example.test", self.conf())
        self.assertEqual(outcome, webfetch.NON_2XX)
        self.assertEqual(markup, "")


# --------------------------------------------------- 4. rate limiting

class RequestsArePacedPerHost(RobotsHarness):

    def test_a_stated_crawl_delay_is_read(self):
        """thirstcraft.com declares `Crawl-delay: 10` and nothing read it."""
        self.serve_robots(WITH_CRAWL_DELAY)
        self.assertEqual(webfetch.robots_crawl_delay("example.test",
                                                     self.conf()), 10.0)

    def test_a_robots_without_one_states_no_rule_rather_than_zero(self):
        """NEGATIVE CONTROL. None is 'said nothing'; 0.0 would be 'said go'."""
        self.serve_robots(ALLOW_ALL)
        self.assertIsNone(webfetch.robots_crawl_delay("example.test",
                                                      self.conf()))

    def test_the_first_request_to_a_host_does_not_wait(self):
        """NEGATIVE CONTROL on the waiter itself: nothing to wait behind."""
        self.assertEqual(webfetch._wait("example.test", 1.0), 0.0)

    def test_the_second_request_to_the_same_host_waits(self):
        self.serve_robots(ALLOW_ALL)
        webfetch._pace("example.test", self.conf())
        waited = webfetch._pace("example.test", self.conf())
        self.assertGreater(waited, 0.0)
        self.assertLessEqual(waited, webfetch.DEFAULTS["min_request_interval"])

    def test_a_different_host_is_not_made_to_wait(self):
        """Pacing is per host. One shared gap would be a throttle on us."""
        webfetch._wait("example.test", 1.0)
        self.assertEqual(webfetch._wait("other.test", 1.0), 0.0)

    def test_reading_robots_txt_counts_as_a_request_to_that_host(self):
        """It is a request, so the page after it is paced against it. This is
        also the reentrancy that `_pace` calling `_robots_for` calling `_pace`
        got wrong: a host's first page request was charged for its own robots
        read, and the fix split the waiter out from the question."""
        self.serve_robots(ALLOW_ALL)
        self.assertEqual(webfetch._LAST_REQUEST_AT, {})
        webfetch.robots_allows("https://example.test/", "example.test",
                               self.conf())
        self.assertIn("example.test", webfetch._LAST_REQUEST_AT)
        self.assertGreater(webfetch._pace("example.test", self.conf()), 0.0)

    def test_the_gap_is_the_floor_when_the_site_states_nothing(self):
        self.serve_robots(ALLOW_ALL)
        conf = self.conf()
        self.assertEqual(webfetch._gap_for("example.test", conf),
                         conf["min_request_interval"])

    def test_a_stated_crawl_delay_lengthens_the_gap(self):
        self.serve_robots(WITH_CRAWL_DELAY)
        conf = self.conf()
        webfetch._pace("example.test", conf)
        waited = webfetch._pace("example.test", conf)
        self.assertGreater(waited, conf["min_request_interval"])

    def test_an_absurd_crawl_delay_is_capped(self):
        """A site asking for an hour must not turn one company into a day."""
        self.serve_robots(HUGE_CRAWL_DELAY)
        conf = self.conf()
        webfetch._pace("example.test", conf)
        waited = webfetch._pace("example.test", conf)
        self.assertLessEqual(waited, conf["max_crawl_delay"])

    def test_the_bounds_are_configurable_and_clamped(self):
        got = webfetch.settings({"research": {"local_http": {
            "min_request_interval": 2.0, "max_crawl_delay": 5.0}}})
        self.assertEqual(got["min_request_interval"], 2.0)
        self.assertEqual(got["max_crawl_delay"], 5.0)
        wild = webfetch.settings({"research": {"local_http": {
            "min_request_interval": 10000}}})
        self.assertLessEqual(wild["min_request_interval"],
                             webfetch.DEFAULTS["min_request_interval"] * 4)

    def test_the_page_fetch_actually_calls_the_pacer(self):
        """Behaviour, not the presence of a helper: a pacer nothing calls is
        exactly the computed-and-never-read shape this repo keeps finding."""
        self.serve_robots(ALLOW_ALL)
        seen = []
        opener = _Opener(lambda: _Answer(b"<html><body>hi</body></html>"))

        def spy(host, conf):
            seen.append(host)
            return 0.0

        with mock.patch("src.webfetch._pace", side_effect=spy), \
                mock.patch("src.webfetch.urllib.request.build_opener",
                           return_value=opener):
            webfetch.fetch("https://example.test/", "example.test", self.conf())
        self.assertEqual(seen, ["example.test"])


# ------------------------------------------- 5. robots on the paid fallback

class RobotsGatesThePaidCrawl(QueueTest):
    """Apify's docstring said it was "not a way past a robots restriction" and
    listed that among the things "the code enforces every line of". Nothing in
    that module reads robots.txt, and `start_run` sends `useApifyProxy: True`."""

    def setUp(self):
        super().setUp()
        research.crawl_cache_clear()
        research._reset_persisted_cache()
        webfetch.robots_cache_clear()
        self.addCleanup(webfetch.robots_cache_clear)
        rec = store.new_record("meridian", "cold", "demo", "Meridian",
                               "meridian.test")
        rec["hook"] = None
        rec["company_facts"] = {}
        store.save([rec])
        self.rec = rec
        self.assertEqual(research.why(rec), research.NEED_HOOK_EVIDENCE)
        self.spent = []
        # The free leg must not settle it, or the paid leg is never reached.
        free = mock.patch("src.research._from_the_site_itself",
                          return_value=None)
        self.addCleanup(free.stop)
        free.start()
        sleep = mock.patch("src.webfetch.time.sleep")
        self.addCleanup(sleep.stop)
        sleep.start()

    def spend(self, call, reason, provider=None, reason_code=None):
        self.spent.append(call)
        return True

    def run_paid(self, robots_body):
        robots = _Robots(robots_body)
        config = {"research": {"apify": {"enabled": True}}}
        with mock.patch("src.webfetch.urllib.request.urlopen", robots), \
                mock.patch("src.providers.apify.start_run") as started:
            started.return_value = {"id": "r1", "status": "SUCCEEDED",
                                    "dataset_id": "d1"}
            out = research.run(self.rec, config, live=True, spend=self.spend)
        return out, started

    def test_a_robots_that_disallows_everything_refuses_the_paid_run(self):
        """NEGATIVE CONTROL, and it must refuse BEFORE the ledger is touched."""
        out, started = self.run_paid(DISALLOW_ALL)
        self.assertEqual(out, [])
        started.assert_not_called()
        self.assertEqual(self.spent, [],
                         "a refused run must not have been paid for")

    def test_a_robots_that_allows_lets_the_paid_run_start(self):
        """POSITIVE CONTROL. Without it, a gate refusing everything passes."""
        out, started = self.run_paid(ALLOW_ALL)
        self.assertTrue(started.called,
                        "an allowed domain must still reach the actor")
        self.assertEqual(self.spent, ["apify-research"])

    def test_only_the_allowed_candidate_urls_are_sent(self):
        """`candidate_urls` GUESSES paths, so robots is the only consent signal
        for a page the site never linked."""
        out, started = self.run_paid(DISALLOW_ABOUT)
        self.assertTrue(started.called)
        sent = [u["url"] for u in started.call_args[0][1]]
        self.assertTrue(sent, "something must still be crawlable")
        for url in sent:
            self.assertNotIn("/about", url)


if __name__ == "__main__":
    unittest.main()
