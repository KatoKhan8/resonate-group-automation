#!/usr/bin/env python3
"""`bison.WRITE_ROUTES` must REFUSE, not merely describe.

Until 2026-09-14 it described. The tuple carried a comment claiming "the same
guarantee `heyreach.WRITE_ROUTES` gives" - and HeyReach earns that claim with a
chokepoint, `_write`, which raises on a path not in its list before the request
is built. EmailBison had no equivalent: every write called `request()` with an
f-string URL, so the tuple was a note to the reader.

The proof that a described allowlist drifts is that this one already had.
`update_lead` writes `PATCH /leads/{id}`. That path was not in the tuple, it
had shipped, and nothing in the repository noticed - not the seal tests, which
pinned the tuple's CONTENTS without ever comparing them to the paths the module
writes to, and not `tests/test_nothing_writes_to_a_provider`, which allowlists
EmailBison by (file, verb) and so waves through every route the file names.

So these tests ask the two questions the old ones could not:

  - does an off-list path actually refuse, before anything reaches the wire
  - is every path the shipped write functions use actually on the list

The second is the one that catches the next `update_lead`. It exercises the
real functions against a recording transport and reads the paths back out, so
it fails when somebody adds a write to a new route, and it keeps passing when
somebody writes a comment - which is the distinction CLAUDE.md asks for and
which the tuple-pinning tests do not make.
"""
import unittest

from src.providers import bison
from tests.base import ProviderTest


# RESOLVED AT CALL TIME, NEVER BOUND AT IMPORT. `tests/test_audit.py`
# reloads `src.providers`, which mints a fresh exception class on the same
# module object, so a name bound here would stop matching what the module
# raises and `assertRaises` would miss it. The file would pass alone and
# error under `discover`. `tests/test_invariants.py` asserts this on the
# import graph; it caught this file on the day it was written.
def provider_error():
    from src.providers import ProviderError

    return ProviderError


def missing_key():
    from src.providers import MissingKey

    return MissingKey


class NoTransport(Exception):
    """Raised by the stand-in transport. Reaching it is the failure."""


def refuse_transport(*args, **kwargs):
    raise NoTransport(f"the transport was reached: {args[:2]}")


class Recorder:
    """Stands in for `providers.request` and records what it was asked for."""

    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply if reply is not None else {}

    def __call__(self, method, url, headers=None, body=None, timeout=None):
        self.calls.append((method, url))
        return 200, self.reply

    def writes(self):
        """The path of every MUTATING call recorded, base stripped.

        Reads are excluded deliberately. Every write function here reads the
        provider back afterwards - that is the house rule - and those GETs go
        to routes that are not, and must not be, on the write allowlist.
        """
        base = bison.base()
        return [u[len(base):] if u.startswith(base) else u
                for method, u in self.calls
                if method.upper() in bison.WRITE_METHODS]


class RouteMatching(unittest.TestCase):
    """`route_of` is the whole decision, so it is tested on its own."""

    def test_every_declared_route_matches_a_concrete_instance_of_itself(self):
        """A template nothing can match is a route that is silently disabled."""
        for template in bison.WRITE_ROUTES:
            concrete = "/".join(
                "12345" if part.startswith("{") else part
                for part in template.split("/"))
            with self.subTest(route=template):
                self.assertEqual(bison.route_of(concrete), template)

    def test_a_longer_path_does_not_match_a_shorter_template(self):
        """The segment count is the guard. Without it `/leads` would admit
        `/leads/993/anything`, and a prefix match is how an allowlist becomes
        a suggestion."""
        self.assertIsNone(bison.route_of("/leads/993/delete"))
        self.assertIsNone(bison.route_of("/campaigns/451/leads/attach-leads/x"))

    def test_a_shorter_path_does_not_match_a_longer_template(self):
        self.assertIsNone(bison.route_of("/campaigns/451"))

    def test_a_different_literal_segment_does_not_match(self):
        """`{campaign_id}` is a wildcard; `resume` is not."""
        self.assertEqual(bison.route_of("/campaigns/451/resume"),
                         "/campaigns/{campaign_id}/resume")
        self.assertIsNone(bison.route_of("/campaigns/451/delete"))
        self.assertIsNone(bison.route_of("/campaigns/451/start"))

    def test_a_query_string_does_not_smuggle_a_path_past_the_match(self):
        self.assertIsNone(bison.route_of("/campaigns/451/delete?x=1"))

    def test_an_unrelated_route_is_refused(self):
        self.assertIsNone(bison.route_of("/webhooks"))
        self.assertIsNone(bison.route_of("/"))


class TheDoorRefusesBeforeTheWire(ProviderTest):
    """A refusal that happens after the request is sent is not a refusal.

    `ProviderTest` rather than a plain `TestCase`: the suite-wide credential
    firewall in `tests/__init__.py` removes `BISON_KEY`, so `_json_headers()`
    raises `MissingKey` while the arguments to `request` are being built -
    BEFORE the transport is reached. A test that did not notice would read
    "nothing was sent" as the door working when it was the firewall.
    """

    def setUp(self):
        super().setUp()
        self.original = bison.request
        bison.request = refuse_transport
        self.addCleanup(setattr, bison, "request", self.original)

    def test_post_to_an_off_list_route_refuses_and_sends_nothing(self):
        with self.assertRaises(provider_error()) as caught:
            bison._post("/campaigns/451/delete", {})
        self.assertIn("not a write route", str(caught.exception))

    def test_patch_to_an_off_list_route_refuses_and_sends_nothing(self):
        with self.assertRaises(provider_error()):
            bison._patch("/campaigns/451/start", {})

    def test_put_to_an_off_list_route_refuses_and_sends_nothing(self):
        with self.assertRaises(provider_error()):
            bison._put("/webhooks", {})

    def test_the_refusal_names_the_route_and_the_verb(self):
        """"Refused" without saying what invites somebody to try it again."""
        with self.assertRaises(provider_error()) as caught:
            bison._post("/campaigns/451/delete", {})
        message = str(caught.exception)
        self.assertIn("POST", message)
        self.assertIn("/campaigns/451/delete", message)

    def test_an_on_list_route_reaches_the_transport(self):
        """The door must not refuse everything - a guard that blocks the real
        writes too would be discovered by a caller, not by this test."""
        with self.assertRaises(NoTransport):
            bison._patch("/campaigns/451/pause", {})


class EveryShippedWriteUsesADeclaredRoute(ProviderTest):
    """The test that would have caught `update_lead`.

    Each write function is called for real against a recording transport, and
    the path it chose is looked up in `WRITE_ROUTES`. This asserts on what the
    functions DO, so it survives rewording and fails on a new route.
    """

    def setUp(self):
        super().setUp()
        self.recorder = Recorder()
        self.original = bison.request
        bison.request = self.recorder
        self.addCleanup(setattr, bison, "request", self.original)

    def assert_declared(self):
        paths = self.recorder.writes()
        self.assertTrue(paths, "the write function issued no write")
        for path in paths:
            with self.subTest(path=path):
                self.assertIsNotNone(
                    bison.route_of(path),
                    f"{path} is written to but is not in bison.WRITE_ROUTES")

    def test_update_lead_writes_only_to_a_declared_route(self):
        """THE REGRESSION. This wrote to an undeclared route for a day."""
        try:
            bison.update_lead(993, {"custom_variables": []})
        except missing_key():
            raise
        except provider_error():
            # The readback refuses the recorder's empty reply. The path was
            # already chosen and recorded by then, which is what is under
            # test. `MissingKey` is re-raised above because it is thrown
            # while the request's ARGUMENTS are built, so it means no write
            # was attempted at all - which must never read as one declared.
            pass
        self.assert_declared()

    def test_create_lead_writes_only_to_a_declared_route(self):
        try:
            bison.create_lead({"email": "ada@example.test"})
        except missing_key():
            raise
        except provider_error():
            pass
        self.assert_declared()

    def test_create_campaign_writes_only_to_a_declared_route(self):
        try:
            bison.create_campaign("a name")
        except missing_key():
            raise
        except provider_error():
            pass
        self.assert_declared()

    def test_set_sequence_writes_only_to_a_declared_route(self):
        try:
            bison.set_sequence(451, "t", [{"title": "s"}])
        except missing_key():
            raise
        except provider_error():
            pass
        self.assert_declared()

    def test_pause_campaign_writes_only_to_a_declared_route(self):
        try:
            bison.pause_campaign(451)
        except missing_key():
            raise
        except provider_error():
            pass
        self.assert_declared()

    def test_ensure_custom_variables_writes_only_to_a_declared_route(self):
        """This one needs a readable page before it will write at all.

        It reads the declared variables first and creates only the difference,
        so an unreadable reply means it decides nothing is missing and issues
        no write - which `assert_declared` would report as "issued no write"
        rather than as a pass. An empty PAGE, not an empty reply.
        """
        self.recorder.reply = {"data": [], "meta": {"total": 0}}
        try:
            bison.ensure_custom_variables(("subject_1",))
        except missing_key():
            raise
        except provider_error():
            pass
        self.assert_declared()


class TheDoorDidNotWidenWhatThisModuleMaySend(unittest.TestCase):
    """Enforcement must not have quietly become permission."""

    def test_resume_is_declared_and_authorised_for_one_campaign_only(self):
        """RENAMED from `test_resume_is_declared_but_still_unsupported`.

        The route has been on the allowlist since before any permission
        existed, so that `resume_campaign` would work the day it was
        authorised. It was authorised on 2026-09-16 - so the old name, which
        asserted the verb was unsupported, now states the opposite of the
        truth and would have had to be deleted rather than moved.

        The two facts this test exists to keep apart are unchanged: a ROUTE
        on the allowlist is one this module CAN call, and a PERMISSION is
        what decides whether it does. What has moved is that the permission
        is no longer "no", it is "one campaign" - and that is the thing this
        class must prove did not quietly become a channel. Membership of
        `SUPPORTED` alone would licence activating 481, which holds 23 people
        with 6 to 40 historical touches each under a sequence nobody approved
        here.
        """
        from src import providerwrites

        self.assertIsNotNone(bison.route_of("/campaigns/451/resume"))
        self.assertTrue(
            providerwrites.is_supported(providerwrites.EMAIL_ACTIVATE))
        self.assertTrue(
            providerwrites.is_conditional(providerwrites.EMAIL_ACTIVATE),
            "bison.activate is enabled with no condition, which is a licence "
            "over every campaign in that workspace")

        require = providerwrites.require_conditional_permission
        # THE CANONICAL ROW IS CHECKED FIRST, because the provider slot in the
        # grant is unpinned and the row is what supplies the expected provider
        # id. A write naming any other row is refused before a provider id is
        # even resolved, so no provider campaign is reachable through it.
        for other in ("481", "485", "487", "451", "", None):
            with self.assertRaises(providerwrites.WriteRefused):
                require(providerwrites.EMAIL_ACTIVATE, other,
                        "productive-email-control-v2")
        # And with the RIGHT row named, every provider id but the one that row
        # is actually bound to is still refused - the binding check the `None`
        # in the grant preserves rather than drops. 481 and 485 must never be
        # activated: 481 holds strangers, and 485's sequence violates the
        # threading invariant and `set_sequence` appends, so it cannot be
        # corrected in place.
        #
        # WIDENED 2026-09-18 FROM ONE ROW TO TWO, so this walks EVERY
        # authorized row instead of the single one the grant used to hold. It
        # is the stronger form of the same assertion: each row admits exactly
        # the provider campaign it is bound to and refuses every other, which
        # is the property that has to survive any future widening as well.
        from src import campaigns as _campaigns
        authorized = [c for _, c in providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS]
        self.assertTrue(authorized, "the grant names no canonical row at all")
        bindings = {}
        for want_canonical in authorized:
            for other in ("481", "485", "451", "4870", "48", "", None):
                with self.assertRaises(providerwrites.WriteRefused):
                    require(providerwrites.EMAIL_ACTIVATE, other,
                            want_canonical)
            bound = (_campaigns.get(want_canonical) or {}).get(
                "bison_campaign_id")
            if bound:
                bindings[want_canonical] = str(bound)

        # The pairs that are admitted, resolved from canonical state rather
        # than written down here - so the test cannot drift from the binding.
        # A row with no binding yet is skipped rather than failed: the US
        # cohort's provider campaign does not exist until the factory creates
        # it, and an unbound row is refused by the predicate anyway, which the
        # loop above just proved.
        self.assertTrue(bindings,
                        f"none of {authorized} carries a `bison_campaign_id`, "
                        f"so there is no provider campaign the grant can be "
                        f"checked against")
        for want_canonical, bound in bindings.items():
            self.assertTrue(require(providerwrites.EMAIL_ACTIVATE, bound,
                                    want_canonical))
            # And no row may borrow another's campaign.
            for stranger, other_bound in bindings.items():
                if stranger == want_canonical:
                    continue
                with self.assertRaises(providerwrites.WriteRefused):
                    require(providerwrites.EMAIL_ACTIVATE, other_bound,
                            want_canonical)

        # WHAT DID NOT COME WITH IT. `bison.add_lead` reaches a person on a
        # channel that can now be activated, and `bison.set_limits` is a cap
        # this build could raise on the campaign it just started. Neither was
        # granted.
        self.assertFalse(
            providerwrites.is_supported(providerwrites.EMAIL_ADD_LEAD))
        self.assertFalse(
            providerwrites.is_supported(providerwrites.EMAIL_SET_LIMITS))

    def test_there_is_no_delete_route(self):
        for path in ("/campaigns/451", "/leads/993", "/campaigns"):
            with self.subTest(path=path):
                with self.assertRaises(provider_error()):
                    bison._patch(path + "/delete", {})


if __name__ == "__main__":
    unittest.main()
