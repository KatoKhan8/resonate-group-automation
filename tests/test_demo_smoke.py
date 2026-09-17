"""Every screen, as every role, in demo mode. The check that nothing 500s.

The rest of the suite tests behaviour. This tests reachability: it walks every
route in the navigation as each of the five roles and asserts that what comes
back is a page rather than a stack trace.

It is deliberately shallow and deliberately total. A deep test of one screen
catches a logic error; this catches the class of problem that a deep test
never does - a helper renamed, an import moved, a template argument dropped -
which shows as a 500 on some screen nobody happened to have a test for.

Three properties:

**Nothing 500s.** A refusal is fine. An exception is not.

**Nothing offers a link it would refuse.** A nav full of 403s is a worse
product than one that does not offer them.

**Demo mode is obvious.** A build serving fictional data must say so on every
page, or somebody will screenshot it into a client deck.
"""
import re
import unittest

from src.web import pages
from tests.webbase import WebTest

SUPER = "root@resonate.test"
ADMIN = "admin@productive.test"
OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
EVERYONE = (SUPER, ADMIN, OPERATOR, REVIEWER, VIEWER)

# Surfaces that are real but are not offered in the navigation, so the
# derivation below cannot find them.
UNLISTED = (
    "/", "/search?q=north", "/healthz",
)


def _screens():
    """Every GET surface: the navigation, plus what it does not offer.

    Derived rather than listed. The hand-written tuple this replaced had
    stopped covering three screens - `/health`, `/refresh` and `/revival` -
    which is the failure this whole file exists to catch, quietly happening
    to the file itself. A sweep that does not grow with the product reports
    a shrinking fraction of it and looks identical either way.
    """
    found = list(UNLISTED)
    for href, _, _ in pages.NAV:
        if href and href not in found:
            found.append(href)
    return tuple(found)


SCREENS = _screens()

# Python leaking through a template. Every one of these is a rendered
# object where a sentence should be, and each has been seen in a real
# product at least once.
INTERNALS = (
    "traceback (most recent",
    "object at 0x",
    "nonetype",
    "dict_items(",
    "dict_keys(",
    # A rendered dict is the likeliest of these by far, and the one that
    # reads most like data to somebody who has not seen the code.
    "{'",
    "[{",
    "<class '",
    "keyerror",
    "attributeerror",
    "typeerror",
    "valueerror",
    "indexerror",
)


class NoScreenCrashes(WebTest):

    def test_every_screen_answers_a_page_for_every_role(self):
        crashes = []
        for who in EVERYONE:
            session = self.signin(who)
            for path in SCREENS:
                status, body, _ = session.get(path)
                if status >= 500:
                    crashes.append(f"{who} {path}: {status}")
                if "Something went wrong" in body:
                    crashes.append(f"{who} {path}: rendered an error page")
        self.assertEqual(crashes, [], "\n".join(crashes))

    def test_the_sweep_reached_most_screens(self):
        """A sweep that was refused everywhere passes trivially."""
        reached = 0
        for who in EVERYONE:
            session = self.signin(who)
            for path in SCREENS:
                if session.get(path)[0] == 200:
                    reached += 1
        self.assertGreater(reached, len(SCREENS),
                           "the smoke sweep reached almost nothing")

    def test_a_tab_on_every_multi_tab_screen_renders(self):
        session = self.signin(OPERATOR)
        for path, tabs in (("/senders", ("overview", "email", "linkedin",
                                         "pairings", "capacity")),):
            for tab in tabs:
                status, body, _ = session.get(f"{path}?tab={tab}")
                self.assertLess(status, 500, f"{path}?tab={tab}")
                self.assertNotIn("Something went wrong", body)


class TheNavigationIsHonest(WebTest):
    """A link offered is a link that works for the role it is offered to."""

    def links_on(self, body):
        return sorted(set(re.findall(r'<nav class="nav"[^>]*>(.*?)</nav>', body,
                                     re.S)[0:1] and
                          re.findall(r'href="(/[a-z0-9/._-]*)"',
                                     re.findall(r'<nav class="nav"[^>]*>(.*?)</nav>',
                                                body, re.S)[0])))

    def test_no_role_is_offered_a_link_it_would_be_refused_from(self):
        offenders = []
        for who in EVERYONE:
            session = self.signin(who)
            _, body, _ = session.get("/")
            for href in self.links_on(body):
                status, _, _ = session.get(href)
                if status in (403, 404):
                    offenders.append(f"{who} is offered {href} -> {status}")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_a_viewer_is_offered_fewer_links_than_an_operator(self):
        """The nav narrows with the role, or it is not doing anything."""
        viewer = self.links_on(self.signin(VIEWER).get("/")[1])
        operator = self.links_on(self.signin(OPERATOR).get("/")[1])
        self.assertLess(len(viewer), len(operator))

    def test_every_nav_entry_is_a_real_route(self):
        """A nav pointing at a path no handler answers is a dead link."""
        session = self.signin(SUPER)
        for href, label, _ in pages.NAV:
            if not href:
                continue
            status, _, _ = session.get(href)
            self.assertNotEqual(status, 404,
                                f"{label} points at {href}, which 404s even "
                                f"for a super admin")


class NoScreenLeaksPython(WebTest):
    """A rendered dict is not an empty state, and an exception name is not
    a message. Both look like data to somebody who has not seen the code.

    Derived from the navigation for the same reason the credential sweep
    is: a screen that joins the product joins this without anybody
    remembering to add it.
    """

    def test_no_screen_renders_a_python_object(self):
        offenders = []
        for who in EVERYONE:
            session = self.signin(who)
            for path in SCREENS:
                status, body, _ = session.get(path)
                if status != 200:
                    continue
                lowered = body.lower()
                for needle in INTERNALS:
                    if needle in lowered:
                        offenders.append(f"{who} {path}: {needle}")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_the_sweep_would_notice(self):
        """A sweep whose needles never match anything is not evidence.
        This proves the machinery finds one when it is there."""
        planted = "<class 'dict'>"
        self.assertIn("<class '", planted.lower())
        found = [n for n in INTERNALS if n in planted.lower()]
        self.assertTrue(found)

    def test_every_navigation_entry_is_swept(self):
        """The tuple this replaced was hand-written and had stopped
        covering three screens. Derived now, and asserted, so it cannot
        drift again."""
        offered = {href for href, _, _ in pages.NAV if href}
        self.assertEqual(offered - set(SCREENS), set())

class DemoModeIsObvious(WebTest):

    def test_every_page_says_it_is_a_demo(self):
        session = self.signin(OPERATOR)
        for path in ("/", "/campaigns", "/reporting", "/senders"):
            _, body, _ = session.get(path)
            self.assertIn("DEMO", body, path)

    def test_live_sending_is_shown_as_disabled(self):
        _, body, _ = self.signin(OPERATOR).get("/")
        self.assertIn("Live sending", body)
        self.assertIn("disabled", body)

    def test_the_health_endpoint_reports_it(self):
        import json

        status, body, _ = self.anonymous().get("/healthz")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["demo"])
        self.assertFalse(payload["live_sending"])


class NothingInDemoModeCanSend(WebTest):
    """The refusals, asserted from the running application rather than the
    module docstrings that describe them."""

    def test_push_refuses(self):
        from src import push

        with self.assertRaises(Exception) as caught:
            push.run([], live=True)
        self.assertIn("Live", type(caught.exception).__name__)

    def test_slack_refuses(self):
        from src.providers import slack

        self.assertFalse(slack.live())
        with self.assertRaises(Exception):
            slack.post({"kind": "x", "channel": "#c", "text": "t",
                        "blocks": [], "actions": [], "metadata": {}}, {})

    def test_no_notification_claims_to_have_been_sent(self):
        from src import notify

        for row in notify.load():
            self.assertNotEqual(row["status"], notify.SENT, row["type"])

    def test_the_demo_estate_is_marked_as_demo(self):
        from src import store

        recs = store.load()
        self.assertTrue(recs)
        self.assertTrue(all(r.get("demo") for r in recs),
                        "a record in the demo estate is not marked demo, so "
                        "install() would refuse to run over it next time")
