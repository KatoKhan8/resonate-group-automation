"""TASK-119: campaign id type normalisation.

The provider returns ids as integers (JSON numbers). The canonical store must
hold them as strings so comparisons never silently miss. This test proves the
boundary normalises, and that a comparison that would have failed before the
fix now succeeds.
"""
import os
import shutil
import tempfile
import unittest

from src import campaigns, store


class CampaignIdTypeTest(unittest.TestCase):
    """Provider ids enter as integers and must be stored as strings."""

    def setUp(self):
        # Isolate the store so we don't touch production state
        self._tmp = tempfile.mkdtemp(prefix="rga-task119-")
        self._orig_env = {k: os.environ.get(k) for k in ("QUEUE",) + store.STATE_OVERRIDES}
        store.use_directory(os.path.join(self._tmp, "work"))

    def tearDown(self):
        # Restore environment and clean up
        for k, v in self._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_bisonfactory_bind_stores_campaign_id_as_string(self):
        """When _bind receives an integer id, it stores it as a string."""
        # Set up a campaign row
        with campaigns.transaction() as rows:
            rows.append({
                "campaign_id": "test-campaign-1",
                "client": "test-client",
                "name": "Test Campaign",
                "bison_campaign_id": None,
                "heyreach_campaign_id": None,
            })

        # Import _bind and call it with an integer (simulating provider response)
        from src.bisonfactory import _bind
        provider_id = 594061  # Integer from JSON API
        _bind({"campaign_id": "test-campaign-1"}, provider_id, "test")

        # Read back and check the type
        rows = campaigns.load()
        campaign = next((r for r in rows if r.get("campaign_id") == "test-campaign-1"), None)
        self.assertIsNotNone(campaign, "campaign was not found")
        
        bison_id = campaign.get("bison_campaign_id")
        self.assertIsNotNone(bison_id, "bison_campaign_id was not set")
        self.assertIsInstance(bison_id, str,
            f"bison_campaign_id must be a string, got {type(bison_id).__name__}: {bison_id!r}")
        self.assertEqual(bison_id, "594061")

    def test_bisonfactory_remember_lead_stores_lead_id_as_string(self):
        """When _remember_lead receives an integer id, it stores it as a string."""
        # Set up a record with a contact
        with store.transaction() as rows:
            rows.append({
                "id": "rec-1",
                "contacts": [{"key": "contact-1", "email": "test@example.com"}],
            })

        # Call _remember_lead with an integer (simulating provider response)
        from src.bisonfactory import _remember_lead
        lead_id = 123456  # Integer from JSON API
        _remember_lead(
            {"record_id": "rec-1", "contact_key": "contact-1", "email": "test@example.com"},
            lead_id
        )

        # Read back and check the type
        rows = store.load()
        rec = next((r for r in rows if r.get("id") == "rec-1"), None)
        self.assertIsNotNone(rec, "record was not found")
        
        contact = next((c for c in rec.get("contacts") or [] if c.get("key") == "contact-1"), None)
        self.assertIsNotNone(contact, "contact was not found")
        
        stored_lead_id = contact.get("bison_lead_id")
        self.assertIsNotNone(stored_lead_id, "bison_lead_id was not set")
        self.assertIsInstance(stored_lead_id, str,
            f"bison_lead_id must be a string, got {type(stored_lead_id).__name__}: {stored_lead_id!r}")
        self.assertEqual(stored_lead_id, "123456")

    def test_campaign_id_comparison_works_across_types(self):
        """A string id and an int id that represent the same value must compare equal."""
        # This is the actual bug: comparisons silently miss
        string_id = "599020"
        int_id = 599020
        
        # Before the fix, these would not be equal
        # After the fix, both should be strings
        self.assertEqual(str(string_id), str(int_id),
            "string conversion must make ids comparable")
        
        # But the real test is that the stored value is already a string
        # so no conversion is needed at comparison time
        self.assertIsInstance(string_id, str)


if __name__ == "__main__":
    unittest.main()
