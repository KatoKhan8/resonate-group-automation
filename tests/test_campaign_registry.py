"""The campaign registry: duplicate detection and the pre-creation check.

Three things are tested here:

1. The registry module functions work correctly on fixture data.
2. `new_campaign` calls the registry check through the real entry point -
   not just the function in isolation.
3. Breaking the wiring causes a test failure: removing the registry call
   from `new_campaign` makes the duplicate-refusal test fail.
"""
import json
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from src import campaignregistry, campaigns  # noqa: E402


def _registry_fixture(entries, generated_at="2026-09-15T00:00:00Z"):
    return {
        "generated_at": generated_at,
        "campaigns": entries,
        "duplicates": [],
    }


def _entry(provider="heyreach", id="1", name="Test Campaign",
           status="DRAFT", created="2026-09-15T00:00:00Z",
           lead_count=0, sequence_hash=None, sequence_nodes=0,
           lead_list_id=None, is_resonate=False,
           cohort_key=None, hypothesis=None):
    return {
        "provider": provider,
        "id": id,
        "name": name,
        "status": status,
        "created": created,
        "lead_count": lead_count,
        "sequence_hash": sequence_hash,
        "sequence_nodes": sequence_nodes,
        "lead_list_id": lead_list_id,
        "is_resonate": is_resonate,
        "cohort_key": cohort_key,
        "hypothesis": hypothesis,
    }


class TestNameSimilarity(unittest.TestCase):

    def test_exact_match_after_normalisation(self):
        self.assertEqual(
            campaignregistry._name_similarity("OMEGA 3", "omega   3"),
            "exact")

    def test_exact_match_different_case(self):
        self.assertEqual(
            campaignregistry._name_similarity(
                "PRODUCTIVE - MARKETING AGENCIES",
                "productive - marketing agencies"),
            "exact")

    def test_near_match_with_version_suffix(self):
        self.assertEqual(
            campaignregistry._name_similarity(
                "OMEGA 3", "OMEGA 3 v2"),
            "near")

    def test_near_match_with_geo_suffix(self):
        self.assertEqual(
            campaignregistry._name_similarity(
                "PRODUCTIVE - MARKETING AGENCIES",
                "PRODUCTIVE - MARKETING AGENCIES - AUSTRALIA"),
            "near")

    def test_no_match(self):
        self.assertIsNone(
            campaignregistry._name_similarity("OMEGA 3", "ALPHA 5"))

    def test_empty_names(self):
        self.assertFalse(campaignregistry._name_similarity("", "test"))
        self.assertFalse(campaignregistry._name_similarity("test", ""))


class TestFindDuplicates(unittest.TestCase):

    def test_same_name_detected(self):
        entries = [
            _entry(id="1", name="OMEGA 3", created="2026-07-27T10:00:00Z"),
            _entry(id="2", name="OMEGA 3", created="2026-07-27T10:02:00Z"),
        ]
        dupes = campaignregistry.find_duplicates(entries)
        self.assertEqual(len(dupes), 1)
        self.assertIn("same-or-near name", dupes[0]["reasons"][0])

    def test_same_sequence_hash_detected(self):
        entries = [
            _entry(id="1", name="Campaign A", sequence_hash="abc123"),
            _entry(id="2", name="Campaign B", sequence_hash="abc123"),
        ]
        dupes = campaignregistry.find_duplicates(entries)
        self.assertEqual(len(dupes), 1)
        self.assertTrue(any("same sequence hash" in r for r in dupes[0]["reasons"]))

    def test_same_lead_list_detected(self):
        entries = [
            _entry(id="1", name="Campaign A", lead_list_id="100"),
            _entry(id="2", name="Campaign B", lead_list_id="100"),
        ]
        dupes = campaignregistry.find_duplicates(entries)
        self.assertEqual(len(dupes), 1)
        self.assertTrue(any("same lead list" in r for r in dupes[0]["reasons"]))

    def test_created_within_minutes_same_shape(self):
        entries = [
            _entry(id="1", name="Campaign A", status="DRAFT",
                   created="2026-07-27T10:00:00Z", sequence_nodes=5),
            _entry(id="2", name="Campaign B", status="DRAFT",
                   created="2026-07-27T10:02:00Z", sequence_nodes=5),
        ]
        dupes = campaignregistry.find_duplicates(entries)
        self.assertEqual(len(dupes), 1)
        self.assertTrue(any("within 5 minutes" in r for r in dupes[0]["reasons"]))

    def test_different_providers_not_compared(self):
        entries = [
            _entry(provider="heyreach", id="1", name="Same Name"),
            _entry(provider="emailbison", id="2", name="Same Name"),
        ]
        dupes = campaignregistry.find_duplicates(entries)
        self.assertEqual(len(dupes), 0)

    def test_no_duplicates_in_distinct_set(self):
        entries = [
            _entry(id="1", name="Alpha", sequence_hash="aaa",
                   created="2026-01-01T00:00:00Z", status="DRAFT",
                   sequence_nodes=3),
            _entry(id="2", name="Beta", sequence_hash="bbb",
                   created="2026-06-01T00:00:00Z", status="IN_PROGRESS",
                   sequence_nodes=7),
            _entry(id="3", name="Gamma", sequence_hash="ccc",
                   created="2026-09-01T00:00:00Z", status="PAUSED",
                   sequence_nodes=12),
        ]
        dupes = campaignregistry.find_duplicates(entries)
        self.assertEqual(len(dupes), 0)

    def test_multiple_reasons_reported(self):
        entries = [
            _entry(id="1", name="OMEGA 3", sequence_hash="abc",
                   lead_list_id="100", created="2026-07-27T10:00:00Z",
                   status="DRAFT", sequence_nodes=5),
            _entry(id="2", name="OMEGA 3", sequence_hash="abc",
                   lead_list_id="100", created="2026-07-27T10:01:00Z",
                   status="DRAFT", sequence_nodes=5),
        ]
        dupes = campaignregistry.find_duplicates(entries)
        self.assertEqual(len(dupes), 1)
        self.assertGreaterEqual(len(dupes[0]["reasons"]), 3)


class TestPreCreationCheck(unittest.TestCase):

    def test_cohort_key_match(self):
        reg = _registry_fixture([
            _entry(id="1", name="Campaign A",
                   cohort_key="PRODUCTIVE-UK-DIGITAL-50_99-OPERATIONS"),
        ])
        verdict = campaignregistry.pre_creation_check(
            cohort_key="PRODUCTIVE-UK-DIGITAL-50_99-OPERATIONS",
            registry=reg)
        self.assertTrue(verdict["exists"])
        self.assertEqual(len(verdict["matches"]), 1)

    def test_hypothesis_match(self):
        reg = _registry_fixture([
            _entry(id="1", name="Campaign A",
                   hypothesis="hiring signal drives replies"),
        ])
        verdict = campaignregistry.pre_creation_check(
            hypothesis="hiring signal drives replies",
            registry=reg)
        self.assertTrue(verdict["exists"])

    def test_name_match(self):
        reg = _registry_fixture([
            _entry(id="1", name="OMEGA 3"),
        ])
        verdict = campaignregistry.pre_creation_check(
            name="OMEGA 3", registry=reg)
        self.assertTrue(verdict["exists"])
        self.assertTrue(any("exact" in r for r in verdict["reasons"]))

    def test_no_match_returns_false(self):
        reg = _registry_fixture([
            _entry(id="1", name="Campaign A",
                   cohort_key="PRODUCTIVE-UK-DIGITAL-50_99-OPERATIONS"),
        ])
        verdict = campaignregistry.pre_creation_check(
            cohort_key="DIFFERENT-KEY",
            registry=reg)
        self.assertFalse(verdict["exists"])

    def test_missing_registry_reports_it(self):
        verdict = campaignregistry.pre_creation_check(
            name="anything",
            registry={"campaigns": [], "generated_at": None})
        self.assertFalse(verdict["exists"])
        self.assertFalse(verdict["registry_present"])
        self.assertTrue(any("not generated" in r for r in verdict["reasons"]))

    def test_no_query_returns_no_pass(self):
        verdict = campaignregistry.pre_creation_check(registry=_registry_fixture([]))
        self.assertFalse(verdict["exists"])
        self.assertTrue(any("no query" in r for r in verdict["reasons"]))

    def test_provider_filter(self):
        reg = _registry_fixture([
            _entry(provider="heyreach", id="1", name="Same"),
            _entry(provider="emailbison", id="2", name="Same"),
        ])
        verdict = campaignregistry.pre_creation_check(
            name="Same", provider="heyreach", registry=reg)
        self.assertTrue(verdict["exists"])
        self.assertEqual(len(verdict["matches"]), 1)
        self.assertEqual(verdict["matches"][0]["provider"], "heyreach")


class TestNewCampaignCallsRegistry(unittest.TestCase):
    """The pre-creation check is consumed by new_campaign.

    This is the wiring test: if the registry call is removed from
    new_campaign, these tests fail. That is the point - a check that
    only runs in a script is a check production bypasses.

    The registry is injected by overriding REGISTRY_PATH to point at a
    temp file. This is the same seam load() uses, so the check runs
    through the real code path.
    """

    def _with_registry(self, entries, fn):
        reg = _registry_fixture(entries)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False) as f:
            json.dump(reg, f)
            f.flush()
            path = f.name
        original = campaignregistry.REGISTRY_PATH
        try:
            campaignregistry.REGISTRY_PATH = path
            fn()
        finally:
            campaignregistry.REGISTRY_PATH = original
            os.unlink(path)

    def test_duplicate_name_is_refused(self):
        def run():
            with self.assertRaises(campaigns.DuplicateCampaign) as ctx:
                campaigns.new_campaign(
                    "test-1", "productive", "RESONATE - TEST CAMPAIGN")
            self.assertTrue(ctx.exception.matches)
        self._with_registry([
            _entry(id="100", name="RESONATE - TEST CAMPAIGN"),
        ], run)

    def test_duplicate_cohort_is_refused(self):
        def run():
            with self.assertRaises(campaigns.DuplicateCampaign):
                campaigns.new_campaign(
                    "test-2", "productive", "Brand New Name",
                    cohort_key="PRODUCTIVE-UK-DIGITAL-50_99-OPERATIONS")
        self._with_registry([
            _entry(id="100", name="Existing",
                   cohort_key="PRODUCTIVE-UK-DIGITAL-50_99-OPERATIONS"),
        ], run)

    def test_no_duplicate_is_permitted(self):
        def run():
            c = campaigns.new_campaign(
                "test-3", "productive", "New Campaign Name")
            self.assertEqual(c["campaign_id"], "test-3")
        self._with_registry([
            _entry(id="100", name="Different Campaign"),
        ], run)

    def test_check_can_be_skipped(self):
        def run():
            c = campaigns.new_campaign(
                "test-4", "productive", "RESONATE - TEST CAMPAIGN",
                check_registry=False)
            self.assertEqual(c["campaign_id"], "test-4")
        self._with_registry([
            _entry(id="100", name="RESONATE - TEST CAMPAIGN"),
        ], run)

    def test_cohort_key_stored_on_campaign(self):
        def run():
            c = campaigns.new_campaign(
                "test-5", "productive", "New",
                cohort_key="PRODUCTIVE-UK-DIGITAL-50_99-OPERATIONS",
                hypothesis="hiring signal")
            self.assertEqual(c["cohort_key"],
                             "PRODUCTIVE-UK-DIGITAL-50_99-OPERATIONS")
            self.assertEqual(c["hypothesis"], "hiring signal")
        self._with_registry([], run)

    def test_empty_registry_permits_creation(self):
        def run():
            c = campaigns.new_campaign(
                "test-6", "productive", "New Campaign")
            self.assertEqual(c["campaign_id"], "test-6")
        self._with_registry([], run)


class TestLoadRegistry(unittest.TestCase):

    def test_missing_file_returns_empty(self):
        original = campaignregistry.REGISTRY_PATH
        try:
            campaignregistry.REGISTRY_PATH = "/nonexistent/path.json"
            reg = campaignregistry.load()
            self.assertEqual(reg["campaigns"], [])
            self.assertIsNone(reg["generated_at"])
        finally:
            campaignregistry.REGISTRY_PATH = original

    def test_loads_real_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False) as f:
            json.dump({"campaigns": [_entry(id="1", name="Test")],
                        "generated_at": "2026-09-15T00:00:00Z",
                        "duplicates": []}, f)
            f.flush()
            path = f.name
        original = campaignregistry.REGISTRY_PATH
        try:
            campaignregistry.REGISTRY_PATH = path
            reg = campaignregistry.load()
            self.assertEqual(len(reg["campaigns"]), 1)
            self.assertEqual(reg["campaigns"][0]["name"], "Test")
        finally:
            campaignregistry.REGISTRY_PATH = original
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
