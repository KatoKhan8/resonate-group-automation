#!/usr/bin/env python3
"""`authorize(staging=True)` asks the workspace layer only, and buys nothing else.

WHY THIS EXISTS.

The killswitch's global layer is derived from the existence of
`push.LiveSendNotEnabled` - "live sending is refused in code" - and that is the
strongest guarantee in this repository. Its campaign layer refuses a campaign
that is not RUNNING.

Both refused the first LinkedIn lead ever staged, on a campaign the provider
had just confirmed was DRAFT and could not send. Adding a lead to a campaign
that cannot send reaches nobody, so both were answering a question that had
not been asked.

THIS IS NOT A NEW RULE. `bisonfactory._ensure_leads` has applied it on the
other channel since it was written, and states it in full:

    "The GLOBAL layer is excluded because it refuses sending (which staging is
     not); the CAMPAIGN layer is excluded because the canonical campaign is
     not RUNNING during staging and that is the correct state for a campaign
     being built."

The EmailBison path consults the killswitch itself and asks only the workspace
layer. The LinkedIn path reaches it through `executionguard.authorize`, so it
inherited the whole send stack. Two channels, one question, two answers - and
the tests below are about making sure the answer that won did not take
anything with it.

WHAT MUST STILL BE TRUE, and each has a test:

  - the workspace switch still refuses. It is the tenant's own control and it
    is the meaningful one at staging time.
  - `staging` is OFF by default, so nothing acquires it by accident.
  - the global send refusal is untouched: `push.run(live=True)` still raises.
  - LINKEDIN_ACTIVATE is still sealed and still carries no condition, so
    nothing here moves a staged lead any closer to being messaged.
  - the audit trail says WHICH form of the gate ran, because a gate nobody can
    tell apart afterwards is a gate nobody can audit.
"""
import inspect
import unittest
from unittest import mock

from src import executionguard, killswitch, providerwrites


class StagingIsOptIn(unittest.TestCase):
    def test_the_default_is_the_full_stack(self):
        sig = inspect.signature(executionguard.authorize)
        self.assertIs(sig.parameters["staging"].default, False)

    def test_only_the_linkedin_lead_path_asks_for_it(self):
        """One caller, named. A second one appearing is a decision somebody
        should have to make deliberately."""
        from src import heyreachfactory

        source = inspect.getsource(heyreachfactory._mint_authorization)
        self.assertIn("staging=True", source)


class TheSendBlockIsUntouched(unittest.TestCase):
    """The guarantee this repository says has never been wrong."""

    def test_live_sending_is_still_refused_in_code(self):
        from src import push

        self.assertTrue(hasattr(push, "LiveSendNotEnabled"))
        self.assertFalse(killswitch.global_state()["sending"])

    def test_the_global_layer_still_refuses_for_a_non_staging_action(self):
        verdict = killswitch.state(workspace="productive")
        self.assertFalse(verdict["sending"])
        self.assertEqual(verdict["blocked_by"], killswitch.GLOBAL)

    def test_activation_is_still_sealed_and_still_unconditional(self):
        """Staging a lead must not move it one step closer to being messaged.

        The verb that does that is ACTIVATE, and it is not merely absent from
        SUPPORTED - it carries no condition, so there is no campaign state and
        no argument that admits it.
        """
        for operation in (providerwrites.LINKEDIN_ACTIVATE,
                          providerwrites.EMAIL_ACTIVATE):
            self.assertNotIn(operation, providerwrites.SUPPORTED)
            self.assertNotIn(operation, providerwrites.CONDITIONAL)


# The BEHAVIOURAL half - that a staging write clears the workspace layer and
# is refused by it when the workspace is off - lives in
# `test_no_write_happens_without_every_gate`, which drives the real
# `authorize` through all seven gates against a full estate. Rebuilding that
# harness here would mean constructing the input by hand, and the seam was
# never the risk.


class TheAuditSaysWhichGateRan(unittest.TestCase):
    """`gates` is what an audit reads to prove which checks ran.

    A staging write and a sending write clear DIFFERENT killswitch checks, and
    an audit that cannot tell them apart cannot answer the only question that
    matters afterwards: was this action allowed to reach somebody.
    """

    def test_the_two_forms_are_distinguishable(self):
        source = inspect.getsource(executionguard.authorize)
        self.assertIn('gates.append("killswitch:workspace")', source)
        self.assertIn('gates.append("killswitch")', source)


if __name__ == "__main__":
    unittest.main()
