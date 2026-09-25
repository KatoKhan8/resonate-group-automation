"""The Productive verification roles are CheapVerifier, Deliverable, Reoon.

Operator decision, Zvonimir, 2026-09-25, and it REPLACES the 2026-09-21
arrangement this file was written for (primary deliverable, secondary reoon).
The order is now:

    stored lookup   free, before any paid call, inside the CheapVerifier
                    adapter rather than as a role here
    cheapverifier   primary, bulk quick mode
    deliverable     secondary, on valid / catch_all / unknown
    reoon           the third opinion only, on a disagreement or a
                    Deliverable `unknown`

ContactOut is still removed from VERIFICATION and still stays first for
ENRICHMENT. Those are different questions about the same address and the
distinction is easy to lose, which is why it is asserted here rather than
left to a comment in a YAML file.

The roles live on the client config and reach the waterfall through
`verification.policy_for`. A silent revert - someone "tidying" the YAML, or a
merge dropping the block - would change who verifies every address without
anybody choosing it. That is the failure this file exists to make loud, and
it is why the roles are RESTATED here on each operator change rather than
loosened into "whatever the config says".

WHAT THE 2026-09-25 CHANGE DID NOT TOUCH, each asserted below: two
independent confirmations, a disagreement holding, a silent primary not
being waved through by the secondary, and only Reoon clearing a catch-all.
"""

import unittest

from src import clients, verification


class ProductiveVerificationRoles(unittest.TestCase):

    def setUp(self):
        self.policy = verification.policy_for(clients.load("productive"))

    def test_the_roles_are_cheapverifier_deliverable_reoon(self):
        self.assertEqual(self.policy["primary"], "cheapverifier")
        self.assertEqual(self.policy["secondary"], "deliverable")
        self.assertEqual(self.policy["catch_all"], "reoon")

    def test_both_verification_pairs_are_accepted(self):
        """`(cheapverifier, deliverable)` and `(cheapverifier, reoon)`.

        The second is accepted because Deliverable is the rung most likely
        to be unavailable, and a cohort that fell back to Reoon for its
        second opinion is verified rather than half-verified.
        """
        self.assertTrue(verification.pair_accepted(
            ["cheapverifier", "deliverable"], self.policy))
        self.assertTrue(verification.pair_accepted(
            ["cheapverifier", "reoon"], self.policy))

    def test_a_pair_without_the_primary_is_not_accepted(self):
        """The pair policy is not a rubber stamp for any two providers."""
        self.assertFalse(verification.pair_accepted(
            ["deliverable", "reoon"], self.policy))

    def test_contactout_holds_no_verification_role(self):
        """The whole point of the change, stated as its own assertion."""
        roles = [self.policy["primary"], self.policy["secondary"],
                 self.policy["catch_all"]]
        self.assertNotIn("contactout", roles)

    def test_two_independent_confirmations_are_still_required(self):
        """Removing a provider must not become removing the second opinion.

        With two roles filled by two distinct providers, two confirmations
        means BOTH must answer and BOTH must agree - there is no third
        opinion left to fall back on. Dropping this to 1 would turn a
        stricter policy into a weaker one while looking like a tidy-up.
        """
        self.assertEqual(self.policy["required_confirmations"], 2)

    def test_a_disagreement_still_holds(self):
        self.assertEqual(self.policy["disagreement"], "hold")

    def test_the_secondary_is_not_trusted_when_the_primary_is_silent(self):
        """A missing primary must not be waved through by the secondary.

        This is what held 93% of the 2026-09-21 run when ContactOut was
        rate-limited, and the answer then was to fix the rate rather than
        relax the rule. It must stay false.
        """
        self.assertIs(self.policy["trust_secondary_when_primary_unknown"],
                      False)

    def test_only_reoon_clears_a_catch_all(self):
        """Reoon's catch-all job survives the reordering.

        `accept_all_clears_on` is a capability rather than a position:
        BUILD-SPEC 5.3 says only Reoon's `is_safe_to_send` clears an
        accept-all, and Deliverable alone does not. Reoon moving from
        catch-all-only to secondary must not quietly hand that job to
        whoever now sits in the catch-all slot.
        """
        self.assertEqual(list(self.policy["accept_all_clears_on"]), ["reoon"])

    def test_the_defaults_are_untouched_for_every_other_workspace(self):
        """Scoped to Productive, by using the mechanism built for scoping.

        `policy_for` overlays the client config over `DEFAULT_POLICY`
        precisely so one workspace's roles are not every workspace's. If this
        fails, the change was made globally and another client silently
        inherited it.
        """
        self.assertEqual(verification.DEFAULT_POLICY["primary"], "contactout")
        self.assertEqual(verification.DEFAULT_POLICY["secondary"],
                         "deliverable")
        self.assertEqual(verification.DEFAULT_POLICY["catch_all"], "reoon")


if __name__ == "__main__":
    unittest.main()
