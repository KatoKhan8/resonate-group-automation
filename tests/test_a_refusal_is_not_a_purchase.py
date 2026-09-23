#!/usr/bin/env python3
"""A verifier that declines to call is not billed for calling.

Deliverable IS the declared local refusal, and the header that used to say
otherwise was stale. TASK-196 confirmed the contract on the grounds that the
response shape had been read live on 2026-09-07 and documented in
`CONFIRMED_RESPONSE_SHAPE`; that was reverted on 2026-09-16 as a gate opening
itself, and this paragraph was not updated with it. `deliverable.verify` DOES
still raise `ContractNotVerified` locally until the operator sets
`DELIVERABLE_RESULT_SHAPE`, which is what makes it the live example of the
principle rather than a retired one.

The original defect: `call()` flattened every `providers.ProviderError` into
`status: error`, and `verify()` charged the spend ledger unconditionally
afterwards. Measured on the live estate 2026-09-13: 41 ledger rows and 41
credits for deliverable, and 32 of 32 stored evidence rows with
`status: error`. Not one call had happened.

A timeout or a 500 stays charged. The provider may have done the work before
failing to tell us, and guessing in the cheap direction is how a ledger starts
under-reporting a real bill.
"""
import os
import unittest
from unittest import mock

from src import verification
from src import providers
from src.providers import deliverable


# This module exercises code that writes `os.environ` ITSELF - `deliverable.configure()` sets its contract variables in `os.environ` - so
# restoring only what the tests set is not enough. Measured 2026-09-23: it
# left DELIVERABLE_AUTH set for every module that ran afterwards.
#
# Module-level, because the writes happen inside the code under test rather
# than in any one setUp, and a module is responsible for the side effects of
# what it exercises.
_ENV_BEFORE_MODULE = None


def setUpModule():
    global _ENV_BEFORE_MODULE
    _ENV_BEFORE_MODULE = dict(os.environ)


def tearDownModule():
    from tests.envisolation import restore
    restore(_ENV_BEFORE_MODULE)


class ALocalRefusalIsFree(unittest.TestCase):

    def test_the_deliverable_contract_waits_on_the_operator(self):
        """This asserted `contract_verified()` with nothing set, on TASK-196's
        reasoning that documenting the shape confirmed the contract. That
        reasoning was reverted on 2026-09-16 and the test was not, so it has
        asserted a falsehood since. Both sides of the gate are pinned here
        instead, so it stays green whichever way the operator decides."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(deliverable.SHAPE_VAR, None)
            self.assertFalse(deliverable.contract_verified())
        with mock.patch.dict(os.environ,
                             {deliverable.SHAPE_VAR: "confirmed"}):
            self.assertTrue(deliverable.contract_verified())

    def test_a_local_refusal_from_a_configured_provider_is_free(self):
        """The mechanism still works. A provider that refuses locally (e.g.
        broken transport contract) is not billed."""
        deliverable.configure(auth="telepathy")
        try:
            entry = verification.call("deliverable", "somebody@example.test")
            self.assertEqual(entry["status"], verification.S_ERROR)
            self.assertIs(entry["charged"], False)
        finally:
            deliverable.configure(auth="header")

    def test_a_network_failure_is_still_charged(self):
        """The provider may have done the work before failing to tell us."""
        with mock.patch.dict(verification.verifiers(),
                             {"reoon": mock.Mock(
                                 verify=mock.Mock(
                                     side_effect=providers.ProviderError("read timed out")))},
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
        self.assertIn(deliverable.ContractNotVerified, refusals)
        # A bare providers.ProviderError must NOT be exempt, or every provider failure
        # becomes free and the ledger stops tracking the bill.
        self.assertNotIn(providers.ProviderError, refusals)

    def test_a_subclass_that_is_not_declared_is_still_charged(self):
        class SomethingElse(providers.ProviderError):
            pass

        self.assertFalse(isinstance(SomethingElse("x"),
                                    verification._local_refusals()))


if __name__ == "__main__":
    unittest.main()
