#!/usr/bin/env python3
"""Scratch copy of the bindings assertion — ARM B: RUNTIME MUTATION.

Mock `campaigns.get` to provide fake bison_campaign_id bindings. If the
assertion then PASSES, it proves that red 3 (`bindings` dict empty) is caused
by missing canonical data, not by broken test logic → UNDETERMINED (runtime
data under work/ unknown).
"""
import unittest
from unittest import mock

from src import providerwrites
from src.providers import bison


class TestBindingsInjection(unittest.TestCase):
    """ARM B: inject a binding into the runtime."""

    def setUp(self):
        self.original_request = bison.request
        bison.request = lambda *a, **k: (200, {"id": "451"})

    def tearDown(self):
        bison.request = self.original_request

    def test_with_mocked_binding_passes_the_assertion(self):
        """Inject bison_campaign_id → bindings no longer empty → assert True passes."""
        fake_get = mock.Mock(side_effect=lambda cid, rows=None: {
            "campaign_id": str(cid),
            "client": "productive",
            "bison_campaign_id": "487",
        } if cid == "productive-email-control-v3" else None)

        # Patch campaigns.get
        import src.campaigns as _campaigns
        orig_get = _campaigns.get
        try:
            _campaigns.get = fake_get

            authorized = [c for _, c in providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS]
            bindings = {}
            for want_canonical in ("productive-email-control-v3",):
                bound = (_campaigns.get(want_canonical) or {}).get("bison_campaign_id")
                if bound:
                    bindings[want_canonical] = str(bound)

            self.assertTrue(bindings,
                            f"bindings is empty even after injection: {bindings}")
        finally:
            _campaigns.get = orig_get


if __name__ == "__main__":
    unittest.main()
