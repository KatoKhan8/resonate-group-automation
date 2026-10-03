"""A lead with a provider-confirmed send yesterday can never read as untouched.

TASK-281. The defect: the inventory's age field is a cached copy that is
never refreshed. 145 of 2,081 inventory rows were staler than the live lead,
133 by 7+ days, the worst by 111 days. Lead 133283 had an inventory age of
111 days but was actually contacted 2 days ago by our own campaign 491.

This test feeds the checker an inventory row claiming 111 days and a
provider row from yesterday; the answer must be "touched yesterday", and
deleting the provider read must make that test fail.

Three rules:

  1. provider_age_days reads the provider timestamp, not the inventory one.
  2. assess_row integrates the provider read - removing it changes the
     reengage_qualifies answer, which is what the test asserts.
  3. A provider read failure is HELD (provider_age_days returns -1),
     never defaulted to the inventory value and never treated as stale.
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.reengagement_provider_read import (                     # noqa: E402
    REENGAGE_AFTER_DAYS,
    assess_row,
    build_iso_lookup,
    delta_distribution,
    filter_uk_eu,
    inventory_age_days,
    iso_is_uk_eu,
    provider_age_days,
    reengage_qualifies,
)


def _inventory_row_111_days_old():
    """An inventory row whose cached last_touch is 111 days ago."""
    now = datetime.datetime.now(datetime.timezone.utc)
    cached = now - datetime.timedelta(days=111)
    return {
        "lead_id": "133283",
        "record_id": "999",
        "provider": "emailbison",
        "campaign_id": 491,
        "state": "stopped",
        "last_touch": cached.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "replied": False,
        "unsubscribed": False,
        "bounced": False,
        "_iso": "GB",
    }


def _provider_stamp_yesterday():
    """A provider-confirmed send from yesterday."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now - datetime.timedelta(days=1)


class TestProviderAgeIsReadNotCached(unittest.TestCase):
    """The regression: provider read overrides the stale cache."""

    def test_provider_age_reads_the_provider_stamp(self):
        """provider_age_days returns 1 for a send yesterday, not 111."""
        yesterday = _provider_stamp_yesterday()
        age = provider_age_days(yesterday)
        self.assertIn(age, (0, 1))

    def test_inventory_age_reads_the_cache(self):
        """inventory_age_days returns 111 for the cached value."""
        row = _inventory_row_111_days_old()
        age = inventory_age_days(row)
        self.assertIn(age, (110, 111, 112))

    def test_assess_row_uses_provider_age_for_reengage(self):
        """THE REGRESSION. An inventory row claiming 111 days with a
        provider-confirmed send yesterday must NOT qualify for REENGAGE.

        If you delete the provider read from assess_row - the call to
        provider_age_days that integrates the provider stamp into the
        decision - this test fails. That is the whole point: the test
        proves the provider read is wired into the decision, not just
        present in the codebase.
        """
        row = _inventory_row_111_days_old()
        yesterday = _provider_stamp_yesterday()
        result = assess_row(row, provider_stamp=yesterday,
                            provider_campaign_id=491)
        self.assertFalse(
            result["reengage_qualifies"],
            "A lead contacted yesterday must NEVER qualify for REENGAGE. "
            "If this fails, the provider read is not wired into the "
            "reengage_qualifies decision - which is the exact defect "
            "TASK-281 exists to fix.")
        self.assertIn(result["provider_age_days"], (0, 1))
        self.assertIsNotNone(result["delta_days"])
        self.assertGreater(result["delta_days"], 100)
        self.assertEqual(result["provider_campaign"], 491)

    def test_without_provider_data_the_same_row_would_qualify(self):
        """Without the provider read, the 111-day row DOES qualify.

        This proves the cache is wrong: the inventory says 111 days and
        the REENGAGE predicate passes. The provider read is what stops
        the wrong admission.
        """
        row = _inventory_row_111_days_old()
        result = assess_row(row, provider_stamp=None,
                            provider_campaign_id=None)
        self.assertTrue(
            result["reengage_qualifies"],
            "Without provider data, the 111-day inventory row should "
            "qualify for REENGAGE - proving the cache is wrong.")
        self.assertIsNone(result["provider_age_days"])

    def test_provider_read_failure_is_held_never_defaulted(self):
        """A provider read failure is HELD, never treated as stale-enough.

        Counting a provider read failure as "no touch found" is how a
        person gets messaged twice. The failure must be HELD and the
        row must NOT qualify for REENGAGE.
        """
        row = _inventory_row_111_days_old()
        result = assess_row(row, provider_stamp="HELD",
                            provider_error="ProviderError")
        self.assertEqual(result["status"], "HELD")
        self.assertEqual(result["provider_age_days"], -1)
        self.assertFalse(
            result["reengage_qualifies"],
            "A HELD row must NEVER qualify for REENGAGE. Missing "
            "evidence is never positive evidence.")

    def test_delta_distribution_buckets(self):
        """Delta distribution sorts into the right buckets."""
        now = datetime.datetime.now(datetime.timezone.utc)
        assessments = [
            {"delta_days": 0},
            {"delta_days": 3},
            {"delta_days": 15},
            {"delta_days": 60},
            {"delta_days": None},
        ]
        dist = delta_distribution(assessments)
        self.assertEqual(dist["0"], 1)
        self.assertEqual(dist["1-6"], 1)
        self.assertEqual(dist["7-30"], 1)
        self.assertEqual(dist["30+"], 1)
        self.assertEqual(dist["unresolvable"], 1)


class TestUKEUFilter(unittest.TestCase):
    """UK/EU selection from the stored ISO field, not a TLD guess."""

    def test_gb_is_uk_eu(self):
        self.assertTrue(iso_is_uk_eu("GB"))

    def test_de_is_uk_eu(self):
        self.assertTrue(iso_is_uk_eu("DE"))

    def test_us_is_not_uk_eu(self):
        self.assertFalse(iso_is_uk_eu("US"))

    def test_filter_uk_eu_selects_correctly(self):
        rows = [
            {"lead_id": "1", "record_id": "r1", "_iso": "GB"},
            {"lead_id": "2", "record_id": "r2", "_iso": "DE"},
            {"lead_id": "3", "record_id": "r3", "_iso": "US"},
            {"lead_id": "4", "record_id": "r4", "_iso": "FR"},
        ]
        iso_lookup = {"r1": "GB", "r2": "DE", "r3": "US", "r4": "FR"}
        uk_eu, non_uk_eu, unresolvable = filter_uk_eu(rows, iso_lookup)
        self.assertEqual(len(uk_eu), 3)
        self.assertEqual(non_uk_eu, 1)
        self.assertEqual(unresolvable, 0)

    def test_build_iso_lookup_from_segment(self):
        records = [
            {"record_id": "r1", "segment": {"country_code": "GB"}},
            {"record_id": "r2", "segment": {"country_code": "DE"}},
            {"record_id": "r3", "country_code": "US"},
        ]
        lookup = build_iso_lookup(records)
        self.assertEqual(lookup["r1"], "GB")
        self.assertEqual(lookup["r2"], "DE")
        self.assertEqual(lookup["r3"], "US")


class TestReengagePredicate(unittest.TestCase):
    """The REENGAGE predicate against provider figures."""

    def _lead(self, **kw):
        base = {
            "replied": False,
            "unsubscribed": False,
            "bounced": False,
            "state": "stopped",
        }
        base.update(kw)
        return base

    def test_91_days_provider_age_qualifies(self):
        lead = self._lead()
        self.assertTrue(reengage_qualifies(lead, inv_age=200, prov_age=91))

    def test_90_days_provider_age_does_not_qualify(self):
        lead = self._lead()
        self.assertFalse(reengage_qualifies(lead, inv_age=200, prov_age=90))

    def test_held_never_qualifies(self):
        lead = self._lead()
        self.assertFalse(reengage_qualifies(lead, inv_age=200, prov_age=-1))

    def test_reply_excludes(self):
        lead = self._lead(replied=True)
        self.assertFalse(reengage_qualifies(lead, inv_age=200, prov_age=100))

    def test_unsubscribe_excludes(self):
        lead = self._lead(unsubscribed=True)
        self.assertFalse(reengage_qualifies(lead, inv_age=200, prov_age=100))

    def test_bounce_excludes(self):
        lead = self._lead(bounced=True)
        self.assertFalse(reengage_qualifies(lead, inv_age=200, prov_age=100))


if __name__ == "__main__":
    unittest.main()
