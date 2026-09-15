"""Provider IDs enter as whatever type the provider's JSON response carries.

EmailBison returns integer ids. HeyReach returns integer ids. A hand edit
might write a string. The campaign file on 2026-09-15 held "599020" as a
string on one row and 594061 as an integer on another, and every comparison
that did not normalise silently missed.

The fix is to normalise at the boundary: the three write sites that persist
a provider id onto a row must coerce to string. This test proves the
normalisation is CONSUMED by the fingerprint: json.dumps(594061) and
json.dumps("594061") produce different digests, so a campaign whose
bison_campaign_id was stored as int fingerprints differently from the same
campaign with it stored as string. The test fails when str() is removed
from bisonfactory._bind().
"""
import os
import shutil
import tempfile
import unittest

from src import campaigns, store
from tests.campaignbase import CampaignTest


class TestProviderIdNormalisation(CampaignTest):
    """The fingerprint moves when the type moves, so the normalisation matters."""

    def test_bison_campaign_id_is_stored_as_string_by_bind(self):
        """_bind() must coerce the provider id to string.

        This is the boundary test: the provider returns an integer, and the
        stored value must be a string. If str() is removed from _bind(), this
        test fails because the stored value is an int.
        """
        from src import bisonfactory

        recs = self.seed_records()
        campaign = self.make_campaign(recs, external=False)
        campaigns.save([campaign])

        bisonfactory._bind(campaign, 594061, "test")

        reloaded = campaigns.require(campaign["campaign_id"])
        self.assertIsInstance(
            reloaded.get("bison_campaign_id"), str,
            "bison_campaign_id must be a string after _bind(); "
            "an int here means the boundary normalisation was removed")
        self.assertEqual(reloaded["bison_campaign_id"], "594061")

    def test_fingerprint_is_stable_across_int_and_string_provider_id(self):
        """The same campaign must fingerprint the same regardless of whether
        _bind() received an int or a string.

        This is the CONSUMER test: if _bind() stores the int as-is, the
        fingerprint changes because json.dumps(594061) != json.dumps("594061").
        A campaign approved with one type would be invalidated by a re-bind
        that stores the other type, even though nothing meaningful changed.

        The test uses one campaign, binds via _bind() with an int, records
        the fingerprint, then overwrites with the string equivalent and
        checks the fingerprint matches.
        """
        from src import bisonfactory

        recs = self.seed_records()
        campaign = self.make_campaign(recs, external=False)
        campaign["heyreach_campaign_id"] = "7001"
        campaign["daily_volume"] = {"email": 20, "linkedin": 10}
        campaigns.save([campaign])

        bisonfactory._bind(campaign, 594061, "test")
        reloaded = campaigns.require(campaign["campaign_id"])
        fp_after_bind = campaigns.fingerprint(reloaded, store.load(),
                                              self.config)

        reloaded["bison_campaign_id"] = "594061"
        fp_with_string = campaigns.fingerprint(reloaded, store.load(),
                                               self.config)
        self.assertEqual(
            fp_after_bind, fp_with_string,
            "the fingerprint must not depend on whether _bind() received an "
            "int or a string; if it does, a re-bind from one type to the "
            "other silently invalidates the approval")

    def test_remember_lead_stores_lead_id_as_string(self):
        """_remember_lead() must coerce the provider lead id to string."""
        from src import bisonfactory

        recs = self.seed_records()
        store.save(recs)

        lead = {"record_id": recs[0]["id"],
                "contact_key": recs[0]["contacts"][0]["key"]}
        bisonfactory._remember_lead(lead, 12345)

        reloaded = store.load()
        for rec in reloaded:
            if rec["id"] != recs[0]["id"]:
                continue
            for contact in rec.get("contacts") or []:
                if contact.get("key") != lead["contact_key"]:
                    continue
                self.assertIsInstance(
                    contact.get("bison_lead_id"), str,
                    "bison_lead_id must be a string after _remember_lead(); "
                    "an int here means the boundary normalisation was removed")
                self.assertEqual(contact["bison_lead_id"], "12345")

    def test_remember_leads_stores_lead_ids_as_strings(self):
        """_remember_leads() must coerce every provider lead id to string."""
        from src import bisonfactory

        recs = self.seed_records()
        store.save(recs)

        pairs = []
        for rec in recs[:2]:
            pairs.append((
                {"record_id": rec["id"],
                 "contact_key": rec["contacts"][0]["key"]},
                99900 + recs.index(rec)
            ))
        bisonfactory._remember_leads(pairs)

        reloaded = store.load()
        for lead, expected_id in pairs:
            for rec in reloaded:
                if rec["id"] != lead["record_id"]:
                    continue
                for contact in rec.get("contacts") or []:
                    if contact.get("key") != lead["contact_key"]:
                        continue
                    self.assertIsInstance(
                        contact.get("bison_lead_id"), str,
                        "bison_lead_id must be a string after "
                        "_remember_leads()")
                    self.assertEqual(
                        contact["bison_lead_id"], str(expected_id))


if __name__ == "__main__":
    unittest.main()
