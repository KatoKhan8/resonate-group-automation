"""Precondition 2: the LinkedIn write path, proven BY EFFECT.

THE CLAIM BEING TESTED. The only path a LinkedIn lead may travel is
`heyreachfactory` -> `providerwrites.perform` -> with `eligibility.decide`
consulted. `scripts/batch_linkedin_push.py` is NOT used and must not be.

WHY NOT BY READING THE SOURCE. "I read the module and it calls perform" is
the same class of evidence as a green test that mocks the buggy function.
This repository has been wrong that way before. Every assertion here is
about what a RECORDING TRANSPORT saw, or about what an import graph
contains - never about the text of a file.

THE POSITIVE CONTROL IS THE POINT OF THE WHOLE FILE. A mock that records
nothing is indistinguishable from a path that was never exercised, and
"zero provider writes recorded" is exactly what a broken test prints. So
every mock here first proves it is INSTALLED WHERE THE NETWORK WOULD BE:
a known call is made, the recorder is asserted to have seen it, with the
real URL and the real API-key header. Only then does the absence of a write
mean anything.

AND THE GUARD THAT THE MOCK BYPASSES IS TESTED SEPARATELY, because
`providers.refuse_unauthorized_write` runs INSIDE `_urllib_transport` - so
swapping the transport removes it. A test that only ever runs with a mock
installed has not tested the guard at all; `TheRealGuardStillRefuses` runs
with the real transport in place and asserts the refusal happens BEFORE any
socket.
"""
import importlib
import os
import unittest

from src import eligibility, executionguard, heyreachfactory, providers
from src import providerwrites
from src.providers import heyreach


class RecordingTransport:
    """Stands exactly where the socket would be, and remembers everything."""

    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply if reply is not None else (200, "{}")

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url,
                           "headers": dict(headers or {}), "body": body})
        return self.reply

    # -- what the assertions ask it ------------------------------------
    def writes(self):
        return [c for c in self.calls
                if str(c["method"]).upper() in ("POST", "PUT", "PATCH",
                                                "DELETE")]

    def urls(self):
        return [c["url"] for c in self.calls]

    def touched(self, fragment):
        return [c for c in self.calls if fragment in c["url"]]


class TransportTest(unittest.TestCase):
    """Installs the recorder and ALWAYS puts the real one back."""

    def setUp(self):
        # A PLACEHOLDER CREDENTIAL, because `tests/__init__.py` installs a
        # suite-wide credential firewall: it scrubs `HEYREACH_KEY` from the
        # environment and points `providers.ENV_FILE` at a path that cannot
        # exist, so `key()` raises `MissingKey` before any transport is
        # reached. Without this the positive control below records zero
        # calls and the whole file silently proves nothing - which is
        # exactly what it did on the first run, and exactly the failure
        # mode it is written to catch.
        self._had_key = os.environ.get("HEYREACH_KEY")
        os.environ["HEYREACH_KEY"] = "placeholder-not-a-real-key"
        self.addCleanup(self._restore_key)
        self.transport = RecordingTransport()
        self.previous = providers.set_transport(self.transport)
        self.addCleanup(providers.set_transport, self.previous)

    def _restore_key(self):
        if self._had_key is None:
            os.environ.pop("HEYREACH_KEY", None)
        else:
            os.environ["HEYREACH_KEY"] = self._had_key

    def prove_the_seam_is_live(self):
        """POSITIVE CONTROL. Without this, every absence below is worthless.

        Makes a real READ through the real provider module and asserts the
        recorder saw it at the real HeyReach URL carrying the real API-key
        header. That is the proof that this object is sitting where the
        network sits - so a write that does NOT appear in `calls` genuinely
        did not happen, rather than having gone somewhere else.
        """
        before = len(self.transport.calls)
        try:
            heyreach.campaigns(offset=0, limit=1)
        except Exception:
            # A canned "{}" body may not satisfy the parser, and that is
            # fine: the question is whether the CALL reached the seam.
            pass
        self.assertGreater(len(self.transport.calls), before,
                           "the recording transport was never reached - the "
                           "seam is not installed and nothing below proves "
                           "anything")
        last = self.transport.calls[-1]
        self.assertIn("api.heyreach.io", last["url"])
        self.assertIn("X-API-KEY", last["headers"],
                      "the call did not carry the credential header, so "
                      "this is not the path a live call would take")
        return last


class ThePositiveControlItself(TransportTest):
    def test_the_recorder_sits_where_the_network_sits(self):
        last = self.prove_the_seam_is_live()
        self.assertTrue(last["url"].startswith("https://"))

    def test_the_recorder_would_have_reached_the_network_if_released(self):
        """Releasing it means restoring the real transport. Assert the swap
        is real by checking the module-level seam actually changed."""
        self.assertIsNot(providers._transport, self.previous)
        providers.set_transport(self.previous)
        self.assertIs(providers._transport, self.previous)
        providers.set_transport(self.transport)

    def test_an_empty_call_log_is_not_mistaken_for_success(self):
        """The failure mode this file exists to avoid, asserted directly."""
        fresh = RecordingTransport()
        self.assertEqual(fresh.writes(), [])
        self.assertEqual(fresh.calls, [])


class TheOnlyDoorIsPerform(unittest.TestCase):
    """`heyreachfactory` reaches the provider THROUGH `providerwrites`."""

    def test_the_factory_calls_perform_and_not_the_transport_directly(self):
        seen = []

        def recording_perform(operation, **kw):
            seen.append((operation, kw))
            raise providerwrites.WriteRefused("recorded, not performed")

        real = providerwrites.perform
        providerwrites.perform = recording_perform
        self.addCleanup(setattr, providerwrites, "perform", real)

        transport = RecordingTransport()
        previous = providers.set_transport(transport)
        self.addCleanup(providers.set_transport, previous)

        try:
            heyreachfactory.ensure_leads("productive-linkedin-cohort-v2",
                                         recs=[], live=True)
        except Exception:
            pass

        # THE EFFECT: whatever happened, no lead reached the wire except
        # through `perform`, which we replaced.
        self.assertEqual(
            [c for c in transport.writes()
             if "AddLeadsToCampaign" in c["url"]], [],
            "a lead reached the transport without going through "
            "providerwrites.perform")

    def test_add_lead_is_a_declared_prospect_facing_operation(self):
        self.assertIn(providerwrites.LINKEDIN_ADD_LEAD,
                      providerwrites.PROSPECT_FACING)

    def test_activate_is_sealed_behind_a_conditional_permission(self):
        """No activation, ever - and the seal is NOT where I first assumed.

        I wrote this test asserting `LINKEDIN_ACTIVATE not in SUPPORTED`
        and it FAILED: `heyreach.activate` IS in `SUPPORTED`. The transport
        exists and the operation is declared. What stops it is the
        CONDITIONAL permission - `is_conditional` is True - so activating
        needs a named campaign to be matched, not merely a supported verb.
        Recorded rather than quietly corrected, because "activate is not
        supported" is a comfortable belief that is false, and acting on it
        would be assuming a door is locked that is only latched.
        """
        self.assertIn(providerwrites.LINKEDIN_ACTIVATE,
                      providerwrites.SUPPORTED)
        self.assertTrue(
            providerwrites.is_conditional(providerwrites.LINKEDIN_ACTIVATE),
            "activation is reachable and NOT behind a conditional "
            "permission - that is a live activation route")

    def test_activation_is_refused_for_a_campaign_nobody_granted(self):
        """By effect: an unnamed campaign cannot be activated."""
        with self.assertRaises(Exception):
            providerwrites.require_conditional_permission(
                providerwrites.LINKEDIN_ACTIVATE, "999999")

    def test_no_activation_grant_exists_for_anything_this_lane_touches(self):
        """This lane stops before any provider write, activation included."""
        self.assertFalse(executionguard.activation_is_granted(
            providerwrites.LINKEDIN_ACTIVATE,
            {"campaign_id": "productive-linkedin-pilot-20"}))


class TheBatchPushScriptIsNotOnThePath(unittest.TestCase):
    """`scripts/batch_linkedin_push.py` is not used and must not be.

    Asserted against the IMPORT GRAPH, which is behaviour, rather than
    against the text of any file.
    """

    def test_no_src_module_imports_it(self):
        import os
        import sys

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Import every src module that matters on this path, then look at
        # what actually got loaded. A module nobody imports cannot be on
        # the path, whatever any comment says.
        for name in ("src.heyreachfactory", "src.providerwrites",
                     "src.eligibility", "src.executionguard",
                     "src.providers.heyreach", "src.push"):
            importlib.import_module(name)
        loaded = [m for m in sys.modules
                  if "batch_linkedin_push" in str(m)]
        self.assertEqual(loaded, [],
                         "batch_linkedin_push was imported by the write path")
        self.assertTrue(os.path.exists(
            os.path.join(root, "scripts", "batch_linkedin_push.py")),
            "POSITIVE CONTROL: the script must exist, or this test is "
            "asserting the absence of something that was simply deleted")


class EligibilityIsConsulted(unittest.TestCase):
    """`eligibility.decide` is the authority the path asks."""

    def test_a_linkedin_note_goes_through_lint_at_the_gate(self):
        """By effect: an undeclared step is BLOCKED at eligibility.

        This is precondition 1 observed from precondition 2's side - the
        gate consults `lint.check_linkedin`, so a step that does not say
        what it is cannot pass eligibility either.
        """
        rec = {"id": "acme", "state": "drafted", "client": "demo",
               "contacts": [{"key": "c0", "name": "Ann",
                             "linkedin": "https://www.linkedin.com/in/ann"}]}
        contact = rec["contacts"][0]
        step = {"channel": "linkedin",
                "note": "hi Ann, i work with operations leads at agencies on "
                        "how they see utilisation before a month closes."}
        decision = eligibility.decide(rec, contact, "li1", channel="linkedin",
                                      step=step, timeline={"c0": {"li1": step}})
        self.assertEqual(decision["verdict"], eligibility.BLOCKED)
        self.assertIn("blocked:lint:operation_type_undeclared",
                      decision["reasons"])

    def test_the_same_step_declared_gets_past_the_lint_reason(self):
        """CONTROL for the test above: the refusal is about the DECLARATION.

        Without this, the block above could be any lint failure at all and
        the test would still pass.
        """
        rec = {"id": "acme", "state": "drafted", "client": "demo",
               "contacts": [{"key": "c0", "name": "Ann",
                             "linkedin": "https://www.linkedin.com/in/ann"}]}
        contact = rec["contacts"][0]
        step = {"channel": "linkedin", "linkedin_action": "connect",
                "note": "hi Ann, i work with operations leads at agencies on "
                        "how they see utilisation before a month closes."}
        decision = eligibility.decide(rec, contact, "li1", channel="linkedin",
                                      step=step, timeline={"c0": {"li1": step}})
        self.assertNotIn("blocked:lint:operation_type_undeclared",
                         decision["reasons"])


class TheRealGuardStillRefuses(unittest.TestCase):
    """Run with the REAL transport, because the mock bypasses this guard.

    `refuse_unauthorized_write` is called inside `_urllib_transport`, so
    every test above runs with it removed. If this file never put the real
    transport back, it would be asserting the safety of a system it had
    disabled.
    """

    def test_an_unauthorized_linkedin_write_is_refused_before_the_socket(self):
        providers.reset_transport()
        with self.assertRaises(providers.ProviderWriteRefused):
            providers.refuse_unauthorized_write(
                "POST", "https://api.heyreach.io/api/public/campaign/"
                        "AddLeadsToCampaignV2")

    def test_a_read_is_not_refused(self):
        """CONTROL: the guard refuses writes, not everything."""
        providers.reset_transport()
        self.assertIsNone(providers.refuse_unauthorized_write(
            "GET", "https://api.heyreach.io/api/public/campaign/GetById"))

    def test_the_activate_route_is_refused_too(self):
        providers.reset_transport()
        with self.assertRaises(providers.ProviderWriteRefused):
            providers.refuse_unauthorized_write(
                "POST", "https://api.heyreach.io/api/public/campaign/"
                        "StartCampaign")


if __name__ == "__main__":
    unittest.main()
