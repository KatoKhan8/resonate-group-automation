"""One provider's yes is not enough to send.

`verification._verdict` applies the confirmation rule to EVERY branch of
`decide` - a decision may only be sendable if enough independent providers
confirmed it - and the downgrading is one-way. That is the whole difference
between a rule and a convention: a new branch cannot forget it, and no
policy knob plumbed through can turn a held address into a sendable one.

The default policy requires TWO independent confirmations (ContactOut
primary, Deliverable secondary). The property under test is the invariant on
the primary-says-valid branch: one valid answer arrives as VERIFIED and
sendable from the branch, and the rule holds it - state HELD, sendable
False, the reason naming the shortfall, the decision carrying the
insufficient-confirmations mark.

The control arm is the same evidence plus one more DISTINCT provider: the
address clears, which proves the hold is the confirmation rule doing its
job and not a fixture that could never pass. Asking ContactOut twice would
not clear it - `confirmations` counts providers, not calls - but that is
`confirmations`' own property; this test asserts the gate, with the
two-provider case as its control.
"""
import unittest

from src import verification

EMAIL = "champion@acme.test"


class OneYesIsNotEnoughToSend(unittest.TestCase):

    def test_one_valid_confirmation_is_held_and_two_distinct_providers_clear(
            self):
        one = [verification.result("contactout", verification.S_VALID,
                                   EMAIL)]
        held = verification.decide(one)
        self.assertFalse(
            held["sendable"],
            "one provider's valid made the address sendable: "
            f"{held}")
        self.assertTrue(held.get("insufficient_confirmations"),
                        f"the hold did not name the confirmation shortfall: "
                        f"{held}")
        self.assertIn("1 of 2", held["reason"])
        self.assertIn("contactout", held["reason"])

        two = one + [verification.result("deliverable",
                                         verification.S_VALID, EMAIL)]
        cleared = verification.decide(two)
        self.assertTrue(
            cleared["sendable"],
            f"two distinct confirming providers should clear: {cleared}")


if __name__ == "__main__":
    unittest.main()
