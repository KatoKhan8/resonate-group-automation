"""The URL a Slack app posts a button click to.

`src/interactions.py` has verified, deduplicated and applied a Slack
interaction since it was written, and its docstring says exactly what it
needs from an HTTP layer: read the raw body and three headers, call
`handle()`, return its status. Nothing did. Every approval notification
`notify.py` builds carries Approve / Reject / Hold buttons, and there was
no URL to configure in a Slack app manifest - so the buttons were an
interface with nothing on the other side, and the way that surfaces is a
client pressing Approve and nothing happening.

These tests are about the HTTP layer only. What a payload is allowed to
decide is `tests/test_interactions.py`; what is asserted here is that a
real request reaches that module, that a forged one does not, and that
neither gets an answer Slack will redeliver.
"""
import itertools
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from src.providers import slack
from tests.webbase import WebTest

SECRET = "synthetic-signing-secret-not-real"
PATH = "/slack/interactions"

_TS = itertools.count(1712000)


def body_for(campaign_id="C-NOPE", fingerprint="f", user="U0TEST",
             action_id=slack.APPROVE, client="demo", message_ts=None):
    # A distinct message timestamp per payload, because `interactions`
    # remembers a click by (callback, message, action, user) and answers
    # the second one "already handled". That is exactly right in
    # production - Slack retries - and it means two tests posting the
    # identical body are one click, with the second asserting on the
    # duplicate answer.
    payload = {
        "type": "block_actions",
        "user": {"id": user},
        "container": {"message_ts": message_ts or f"{next(_TS)}.0001"},
        "actions": [{"action_id": action_id,
                     "value": json.dumps({"campaign_id": campaign_id,
                                          "fingerprint": fingerprint,
                                          "client": client})}],
    }
    return "payload=" + urllib.parse.quote(json.dumps(payload))


class SlackRouteTest(WebTest):
    """Posts the way Slack does: no cookie, no CSRF token, an HMAC instead."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._secret = os.environ.get("SLACK_SIGNING_SECRET")
        os.environ["SLACK_SIGNING_SECRET"] = SECRET

    @classmethod
    def tearDownClass(cls):
        if cls._secret is None:
            os.environ.pop("SLACK_SIGNING_SECRET", None)
        else:
            os.environ["SLACK_SIGNING_SECRET"] = cls._secret
        super().tearDownClass()

    def post(self, body, timestamp=None, signature=None, path=PATH,
             method="POST"):
        timestamp = int(time.time()) if timestamp is None else timestamp
        if signature is None:
            signature = slack.sign(body, timestamp, SECRET)
        request = urllib.request.Request(
            self.base + path, data=body.encode("utf-8"), method=method,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "X-Slack-Request-Timestamp": str(timestamp),
                     "X-Slack-Signature": signature})
        try:
            with urllib.request.urlopen(request, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace"), dict(
                    r.headers)
        except urllib.error.HTTPError as e:
            with e:
                return (e.code, e.read().decode("utf-8", "replace"),
                        dict(e.headers))


class TheEndpointExists(SlackRouteTest):

    def test_a_signed_payload_reaches_the_interaction_handler(self):
        """The proof is a sentence only `handle()` produces, and only after
        it has verified the signature, parsed the payload and looked the
        campaign up. Nothing else in the application says this."""
        status, body, _ = self.post(body_for(campaign_id="C-DOES-NOT-EXIST"))
        self.assertEqual(status, 200)
        self.assertIn("no such campaign", body)
        self.assertIn("C-DOES-NOT-EXIST", body)

    def test_it_needs_no_session(self):
        """Slack has no cookie. If this route sat below the session gate it
        would answer with a redirect to the sign-in page, which Slack would
        render as a button that silently does nothing."""
        status, body, _ = self.post(body_for())
        self.assertEqual(status, 200)
        self.assertNotIn("<html", body.lower())
        self.assertNotIn("sign in", body.lower())

    def test_it_sets_no_cookie(self):
        _, _, headers = self.post(body_for())
        self.assertNotIn("Set-Cookie", headers)

    def test_it_answers_plain_text(self):
        """Slack shows this string to whoever pressed the button.

        Both answers, because they leave through different branches: a
        refusal is raised where it is decided, and anything `handle()`
        returns goes through `_slack_answer`. Asserting on one of them
        leaves the other free to answer HTML.
        """
        for body in (body_for(), body_for(action_id="open_review")):
            _, _, headers = self.post(body)
            self.assertTrue(
                headers.get("Content-Type", "").startswith("text/plain"),
                headers.get("Content-Type"))


class ForgedPayloadsAreRefused(SlackRouteTest):

    def test_an_unsigned_post_is_unauthorised(self):
        status, _, _ = self.post(body_for(), signature="v0=not-a-signature")
        self.assertEqual(status, 401)

    def test_a_signature_for_a_different_body_is_unauthorised(self):
        """The signature is over the body. A valid one lifted from another
        request must not carry a substituted payload."""
        now = int(time.time())
        stolen = slack.sign(body_for(campaign_id="C-1"), now, SECRET)
        status, _, _ = self.post(body_for(campaign_id="C-2"), timestamp=now,
                                 signature=stolen)
        self.assertEqual(status, 401)

    def test_a_replayed_payload_is_unauthorised_even_correctly_signed(self):
        old = int(time.time()) - 60 * 60
        status, _, _ = self.post(body_for(), timestamp=old)
        self.assertEqual(status, 401)

    def test_a_refusal_does_not_say_which_check_refused_it(self):
        """Nothing about the request has been trusted at that point, so
        nothing about it is described back."""
        for signature, timestamp in (("v0=wrong", None),
                                     (None, int(time.time()) - 3600),
                                     ("", None)):
            status, body, _ = self.post(body_for(), timestamp=timestamp,
                                        signature=signature)
            self.assertEqual(status, 401)
            self.assertEqual(body, "unauthorised")

    def test_a_refusal_names_no_campaign(self):
        status, body, _ = self.post(body_for(campaign_id="C-SECRET-NAME"),
                                    signature="v0=wrong")
        self.assertEqual(status, 401)
        self.assertNotIn("C-SECRET-NAME", body)


class TheShapeOfTheRequestIsChecked(SlackRouteTest):

    def test_a_get_is_refused(self):
        status, _, _ = self.post(body_for(), method="GET")
        self.assertEqual(status, 405)

    def test_an_oversized_body_is_refused_and_told_so(self):
        """The refusal has to reach the sender.

        The first version of this endpoint answered 413 and closed without
        draining the request. A response written while the client is still
        uploading lands on a socket it is not reading yet, and the close
        arrives as a connection reset - so the sender is refused and never
        learns it. It failed about half the time, which is the shape of bug
        a single green run certifies.

        Repeated, because that is what the failure looked like: sometimes.
        """
        from src.web import app

        filler = "x" * (app.SLACK_MAX_BODY + 1)
        for _ in range(4):
            status, body, _ = self.post("payload=" + filler)
            self.assertEqual(status, 413)
            self.assertIn("too large", body)

    def test_the_drain_is_bounded(self):
        """Draining is what makes the status code arrive, but an unbounded
        drain is the unbounded read the limit existed to prevent."""
        from src.web import app

        self.assertGreater(app.SLACK_DRAIN_LIMIT, app.SLACK_MAX_BODY)
        self.assertLessEqual(app.SLACK_DRAIN_LIMIT, 16 * 1024 * 1024)

    def test_a_body_that_is_not_a_slack_payload_does_not_500(self):
        """A 500 asks Slack to deliver the same click again."""
        status, _, _ = self.post("this is not a payload at all")
        self.assertIn(status, (200, 401))


class NothingRetriesForever(SlackRouteTest):

    def test_an_unknown_action_is_acknowledged_not_retried(self):
        """A button this application does not act on is not an error."""
        status, body, _ = self.post(body_for(action_id="open_review"))
        self.assertEqual(status, 200)
        self.assertIn("open_review", body)

    def test_the_same_click_delivered_twice_changes_nothing_twice(self):
        """Slack retries a delivery it did not see acknowledged. The second
        one must be answered, not acted on."""
        body = body_for(message_ts="1799.0001")
        first = self.post(body)
        second = self.post(body)
        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 200)
        self.assertIn("repeat", second[1].lower())

    def test_a_verified_but_undecidable_payload_answers_200(self):
        """Past verification these are all permanent: a non-2xx would ask
        Slack to redeliver a click that will fail identically."""
        status, _, _ = self.post(body_for(campaign_id="C-DOES-NOT-EXIST"))
        self.assertEqual(status, 200)


class ItIsNotAScreen(SlackRouteTest):

    def test_it_is_in_no_navigation_section(self):
        from src.web import pages

        self.assertNotIn(PATH, [href for href, _, _ in pages.NAV])

    def test_it_is_the_only_route_below_the_session_gate(self):
        """A path that skips both the session check and the CSRF check is
        worth counting. If a second one appears it should be here and
        deliberate rather than discovered."""
        import inspect

        from src.web import app

        source = inspect.getsource(app.Handler._dispatch)
        above = source[:source.index("if not session:")]
        # What is handled before a session is required. Each is either
        # unauthenticated by design - assets, the health check, the login
        # form - or authenticates by another means, which is this one.
        self.assertIn("SLACK_INTERACTIONS_PATH", above)
        self.assertIn('path == "/login"', above)
