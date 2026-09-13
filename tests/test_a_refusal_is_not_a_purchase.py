#!/usr/bin/env python3
"""A verifier that declines to call is not billed for calling.

`deliverable.verify` raises `ContractNotVerified` BEFORE it touches the
network: its response shape has never been read from a real answer, so it
declines rather than spending a credit to find out. That is the right call.

What was wrong is what happened next. `call()` flattened every `ProviderError`
into `status: error`, and `verify()` charged the spend ledger unconditionally
afterwards. Measured on the live estate 2026-09-13: 41 ledger rows and 41
credits for deliverable, and 32 of 32 stored evidence rows with
`status: error`. Not one call had happened.

It matters beyond the accounting. `spendledger.check` enforces the client's
declared ceiling against recorded spend, so phantom rows consume a real
budget; and `max_verification_cost_per_contact` is three, so a verifier that
never runs was eating a third of the per-contact allowance that the verifier
which WOULD have answered needed.

A timeout or a 500 stays charged. The provider may have done the work before
failing to say so, and guessing in the cheap direction is how a ledger starts
under-reporting a real bill.
"""
import unittest
from unittest import mock

from src import verification
from src.providers import ProviderError
from src.providers.deliverable import ContractNotVerified


class ALocalRefusalIsFree(unittest.TestCase):

    def test_deliverable_declines_and_says_it_was_not_charged(self):
        entry = verification.call("deliverable", "somebody@example.test")
        self.assertEqual(entry["status"], verification.S_ERROR)
        self.assertIs(entry["charged"], False)

    def test_a_network_failure_is_still_charged(self):
        """The provider may have done the work before failing to tell us."""
        with mock.patch.dict(verification.verifiers(),
                             {"reoon": mock.Mock(
                                 verify=mock.Mock(
                                     side_effect=ProviderError("read timed out")))},
                             clear=False):
            entry = verification.call("reoon", "somebody@example.test")
        self.assertEqual(entry["status"], verification.S_ERROR)
        self.assertIsNot(entry["charged"], False,
                         "a timeout was treated as free")

    def test_nobody_saying_means_charged(self):
        """The default has to be the expensive reading.

        `charged` is None on every ordinary answer, and None must not mean
        free - otherwise a provider that simply stops reporting quietly stops
        being billed.
        """
        entry = verification.result("contactout", verification.S_VALID,
                                    "somebody@example.test")
        self.assertIsNone(entry["charged"])
        self.assertIsNot(entry["charged"], False)


class TheRefusalClassIsNamedNotGuessed(unittest.TestCase):

    def test_only_a_declared_local_refusal_is_exempt(self):
        refusals = verification._local_refusals()
        self.assertIn(ContractNotVerified, refusals)
        # A bare ProviderError must NOT be exempt, or every provider failure
        # becomes free and the ledger stops tracking the bill.
        self.assertNotIn(ProviderError, refusals)

    def test_a_subclass_that_is_not_declared_is_still_charged(self):
        class SomethingElse(ProviderError):
            pass

        self.assertFalse(isinstance(SomethingElse("x"),
                                    verification._local_refusals()))


if __name__ == "__main__":
    unittest.main()
