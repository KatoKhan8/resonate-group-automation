"""The Productive verification roles are exactly Deliverable + Reoon.

Operator decision, Zvonimir, 2026-09-21: ContactOut is removed from
VERIFICATION and stays first for ENRICHMENT. Those are different questions
about the same address and the distinction is easy to lose, which is why it
is asserted here rather than left to a comment in a YAML file.

The roles live on the client config and reach the waterfall through
`verification.policy_for`. A silent revert - someone "tidying" the YAML, or a
merge dropping the block - would restore ContactOut as primary and every
address would quietly be verified by a provider the operator removed. That is
the failure this file exists to make loud.
"""

import unittest

from src import clients, verification


class ProductiveVerificationRoles(unittest.TestCase):

    def setUp(self):
        self.policy = verification.policy_for(clients.load("productive"))

    def test_the_roles_are_exactly_deliverable_and_reoon(self):
        self.assertEqual(self.policy["primary"], "deliverable")
        self.assertEqual(self.policy["secondary"], "reoon")
        self.assertEqual(self.policy["catch_all"], "reoon")

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
