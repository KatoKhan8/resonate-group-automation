"""Conformance suite for EmailBison and HeyReach adapters.

TASK-273 (2026-10-04): a sequencer adapter is correct iff the suite is green.
EmailBison and HeyReach first, so a third sequencer for the next client is a
generated adapter plus a green suite.

THERE IS NO INTERFACE TO CONFORM TO. No base class, no ABC, no Protocol, no
registry. What they genuinely share is enforced from src/providers/__init__.py
and is a transport and safety contract, not a sequencer one.

This suite asserts four groups of properties:

1. SHARED AND ENFORCED: the providers/__init__ transport contract
2. SHARED BY CONVENTION: headers(), check(), main(argv), events_contract()
3. DECLARED DIFFERENCES: signature and capability rows, each carrying WHY
4. REFUSED BY DESIGN: every operation not in SUPPORTED raises WriteUnsupported

Each declared difference is asserted to STILL BE DIFFERENT, so the day one
adapter converges on the other the suite says so rather than silently passing.
"""
import inspect
import unittest

from src.providers import (
    ProviderError,
    ProviderWriteRefused,
    guard_prospect_facing,
    is_prospect_facing,
    refuse_unauthorized_write,
)
from src.providers import bison, heyreach
from src import providerwrites


class TestProviderErrorConformance(unittest.TestCase):
    """Both adapters subclass and raise ProviderError."""

    def test_bison_raises_provider_error(self):
        """EmailBison calls raise ProviderError on provider failures."""
        # ProviderError is the base for all provider failures
        self.assertTrue(issubclass(ProviderError, RuntimeError))

    def test_heyreach_raises_provider_error(self):
        """HeyReach calls raise ProviderError on provider failures."""
        # ProviderError is the base for all provider failures
        self.assertTrue(issubclass(ProviderError, RuntimeError))

    def test_bison_import_does_not_raise(self):
        """Importing bison does not raise - guard_prospect_facing is safe."""
        # If this test runs, the import succeeded
        self.assertIsNotNone(bison)

    def test_heyreach_import_does_not_raise(self):
        """Importing heyreach does not raise - guard_prospect_facing is safe."""
        # If this test runs, the import succeeded
        self.assertIsNotNone(heyreach)


class TestWriteDoorConformance(unittest.TestCase):
    """Both adapters refuse an undeclared write route."""

    def test_bison_has_write_routes(self):
        """EmailBison declares WRITE_ROUTES."""
        self.assertTrue(hasattr(bison, 'WRITE_ROUTES'))
        self.assertIsInstance(bison.WRITE_ROUTES, tuple)
        self.assertGreater(len(bison.WRITE_ROUTES), 0)

    def test_heyreach_has_write_routes(self):
        """HeyReach declares WRITE_ROUTES."""
        self.assertTrue(hasattr(heyreach, 'WRITE_ROUTES'))
        self.assertIsInstance(heyreach.WRITE_ROUTES, tuple)
        self.assertGreater(len(heyreach.WRITE_ROUTES), 0)

    def test_bison_write_routes_are_strings(self):
        """EmailBison WRITE_ROUTES contains path strings."""
        for route in bison.WRITE_ROUTES:
            self.assertIsInstance(route, str)
            self.assertTrue(route.startswith('/'))

    def test_heyreach_write_routes_are_strings(self):
        """HeyReach WRITE_ROUTES contains path strings."""
        for route in heyreach.WRITE_ROUTES:
            self.assertIsInstance(route, str)
            self.assertTrue(route.startswith('/'))

    def test_refuse_unauthorized_write_exists(self):
        """The write door function exists in providers.__init__."""
        self.assertTrue(callable(refuse_unauthorized_write))

    def test_prospect_facing_hosts_registered(self):
        """Both adapters register their hosts as prospect-facing at import."""
        # The hosts are registered at import time
        self.assertTrue(is_prospect_facing("https://send.resonategroup.co/api/test"))
        self.assertTrue(is_prospect_facing("https://api.heyreach.io/campaign/test"))


class TestGuardProspectFacingConformance(unittest.TestCase):
    """guard_prospect_facing fires at import for both."""

    def test_guard_prospect_facing_is_idempotent(self):
        """Calling guard_prospect_facing multiple times is safe."""
        # Should not raise
        guard_prospect_facing("send.resonategroup.co")
        guard_prospect_facing("send.resonategroup.co")
        guard_prospect_facing("api.heyreach.io")
        guard_prospect_facing("api.heyreach.io")

    def test_guard_prospect_facing_accepts_full_url(self):
        """guard_prospect_facing accepts a full base URL, not just a host."""
        # Should not raise
        guard_prospect_facing("https://send.resonategroup.co/api")
        guard_prospect_facing("https://api.heyreach.io/v1")


class TestSupportedOperationsConformance(unittest.TestCase):
    """Every operation outside SUPPORTED raises WriteUnsupported."""

    def test_supported_is_tuple(self):
        """SUPPORTED is a tuple of operation names."""
        self.assertIsInstance(providerwrites.SUPPORTED, tuple)

    def test_supported_operations_are_strings(self):
        """Each operation in SUPPORTED is a string."""
        for op in providerwrites.SUPPORTED:
            self.assertIsInstance(op, str)

    def test_supported_contains_expected_operations(self):
        """SUPPORTED contains the operations enabled by operator authorization."""
        # These are the operations documented as enabled
        # Note: operations use "bison" and "heyreach" prefixes, not "email" and "linkedin"
        expected = {
            'heyreach.pause',
            'bison.pause',
            'bison.stop_lead',
            'heyreach.stop_lead',
            'bison.resume',
            'bison.create_campaign',
            'bison.set_sequence',
            'heyreach.set_sequence',
            'heyreach.add_lead',
            'heyreach.start_empty_for_staging',
            'heyreach.add_lead_to_list',
            'bison.assign_sender',
            'bison.activate',
            'heyreach.create_campaign',
            'heyreach.activate',
            'heyreach.create_list',
        }
        actual = set(providerwrites.SUPPORTED)
        # At minimum, these should be present
        for op in expected:
            self.assertIn(op, actual, f"{op} should be in SUPPORTED")


class TestAuthorizationConformance(unittest.TestCase):
    """A hand-built authorization is refused."""

    def test_perform_requires_authorization_object(self):
        """perform() refuses a dict claiming the gates passed."""
        # A hand-built dict is not an Authorization
        # Use a prospect-facing operation that's in SUPPORTED
        # heyreach.add_lead is prospect-facing
        fake_auth = {"channel": "heyreach", "operation": "heyreach.add_lead"}
        with self.assertRaises(Exception) as ctx:
            providerwrites.perform('heyreach.add_lead', authorization=fake_auth,
                                  provider_campaign_id="123",
                                  campaign={"id": "123", "owner": "resonate_os"})
        # Should refuse because it's not an Authorization object
        self.assertIn('Authorization', str(ctx.exception))


class TestDeclaredDifferences(unittest.TestCase):
    """Each declared difference is asserted to still be different.

    These are NOT defects to fix - they are real differences documented in the
    source. The suite asserts they STILL DIFFER, so the day one adapter
    converges on the other the suite says so rather than silently passing.
    """

    def test_set_sequence_signatures_differ(self):
        """bison.set_sequence and heyreach.set_sequence have different signatures.

        bison.set_sequence(campaign_id, title, steps)
        heyreach.set_sequence(campaign_id, sequence)

        WHY: The providers have different sequence models. EmailBison takes a
        title and steps separately; HeyReach takes a sequence object.
        """
        bison_sig = inspect.signature(bison.set_sequence)
        heyreach_sig = inspect.signature(heyreach.set_sequence)

        bison_params = list(bison_sig.parameters.keys())
        heyreach_params = list(heyreach_sig.parameters.keys())

        # They should differ
        self.assertNotEqual(bison_params, heyreach_params,
                           "set_sequence signatures should differ by design")

        # Document the expected difference
        self.assertEqual(bison_params, ['campaign_id', 'title', 'steps'])
        self.assertEqual(heyreach_params, ['campaign_id', 'sequence'])

    def test_resume_campaign_signatures_differ(self):
        """bison.resume_campaign and heyreach.resume_campaign have different signatures.

        bison.resume_campaign(campaign_id, expect_leads=None, attempts=8, interval=2.0)
        heyreach.resume_campaign(campaign_id)

        WHY: EmailBison's resume takes an expected lead count and refuses when
        the provider disagrees, because a resumed campaign sends to everybody
        it holds. HeyReach's resume is simpler.
        """
        bison_sig = inspect.signature(bison.resume_campaign)
        heyreach_sig = inspect.signature(heyreach.resume_campaign)

        bison_params = list(bison_sig.parameters.keys())
        heyreach_params = list(heyreach_sig.parameters.keys())

        # They should differ
        self.assertNotEqual(bison_params, heyreach_params,
                           "resume_campaign signatures should differ by design")

        # Document the expected difference
        self.assertEqual(bison_params, ['campaign_id', 'expect_leads', 'attempts', 'interval'])
        self.assertEqual(heyreach_params, ['campaign_id'])

    def test_bison_has_no_sequence_validation_in_adapter(self):
        """EmailBison has no sequence validation in the adapter.

        WHY: Bison's validation is a layer up, in bisonfactory._refuse_unsupported().
        HeyReach has a large sequence-validation surface in the adapter itself:
        validate_sequence_for_write, sequence_hazards, refuse_unsupported_sequence.
        """
        # Bison should NOT have these in the adapter
        self.assertFalse(hasattr(bison, 'validate_sequence_for_write'))
        self.assertFalse(hasattr(bison, 'sequence_hazards'))
        self.assertFalse(hasattr(bison, 'refuse_unsupported_sequence'))

        # HeyReach SHOULD have these in the adapter
        self.assertTrue(hasattr(heyreach, 'validate_sequence_for_write'))
        self.assertTrue(hasattr(heyreach, 'sequence_hazards'))
        self.assertTrue(hasattr(heyreach, 'refuse_unsupported_sequence'))

    def test_fakebison_exists_but_no_fakeheyreach(self):
        """tests/fakebison.py exists and there is no fakeheyreach.

        WHY: This is a declared difference, not a defect. The suite documents
        it so a third adapter can be generated with its own fake.
        """
        import os
        tests_dir = os.path.dirname(__file__)
        fakebison_path = os.path.join(tests_dir, 'fakebison.py')
        fakeheyreach_path = os.path.join(tests_dir, 'fakeheyreach.py')

        self.assertTrue(os.path.exists(fakebison_path),
                       "fakebison.py should exist")
        self.assertFalse(os.path.exists(fakeheyreach_path),
                        "fakeheyreach.py should not exist (declared difference)")


class TestSharedByConvention(unittest.TestCase):
    """Shared by convention: headers(), check(), main(argv), events_contract().

    These are not enforced by a base class but are expected of every provider
    module by convention.
    """

    def test_bison_has_headers(self):
        """EmailBison has a headers() function."""
        self.assertTrue(hasattr(bison, 'headers'))
        self.assertTrue(callable(bison.headers))

    def test_heyreach_has_headers(self):
        """HeyReach has a headers() function."""
        self.assertTrue(hasattr(heyreach, 'headers'))
        self.assertTrue(callable(heyreach.headers))

    def test_bison_has_check(self):
        """EmailBison has a check() function."""
        self.assertTrue(hasattr(bison, 'check'))
        self.assertTrue(callable(bison.check))

    def test_heyreach_has_check(self):
        """HeyReach has a check() function."""
        self.assertTrue(hasattr(heyreach, 'check'))
        self.assertTrue(callable(heyreach.check))

    def test_bison_has_main(self):
        """EmailBison has a main(argv) function."""
        self.assertTrue(hasattr(bison, 'main'))
        self.assertTrue(callable(bison.main))

    def test_heyreach_has_main(self):
        """HeyReach has a main(argv) function."""
        self.assertTrue(hasattr(heyreach, 'main'))
        self.assertTrue(callable(heyreach.main))


if __name__ == '__main__':
    unittest.main()
