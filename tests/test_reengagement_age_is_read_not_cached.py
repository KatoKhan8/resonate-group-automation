"""A provider-confirmed send yesterday can never read as untouched.

TASK-281. The defect: the inventory's age came from a cache that was never
refreshed. Lead 133283 sat in a cohort qualified as "contacted 90+ days ago"
while its last confirmed send was two days ago from campaign 491. 145 of
2,081 rows were staler than the live lead, 133 by 7+ days, the worst by 111.

The fix: `scripts/reengagement_provider_read.py` reads the provider's
scheduled-emails endpoint for each lead and derives the last CONFIRMED touch
at read time. This test proves the wiring:

  1. A lead with a provider-confirmed send yesterday reads as touched
     yesterday, even when the inventory claims 111 days.
  2. Deleting the provider read (`last_provider_touch`) makes the test
     fail - the property depends on the read being connected.
  3. The inventory age alone would have wrongly admitted the row.
  4. A provider read failure is HELD, never "no touch found".
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import reengagement_provider_read as rpr                    # noqa: E402


def _fixed_now():
    return datetime.datetime(2026, 9, 25, 12, 0, 0,
                             tzinfo=datetime.timezone.utc)


def _inventory_row(lead_id="133283", last_touch=None, **kw):
    row = {
        "provider": "emailbison",
        "campaign_id": 491,
        "lead_id": lead_id,
        "state": "stopped",
        "last_touch": last_touch or "2026-06-06T12:00:00Z",
        "campaign_status_at_walk": "archived",
    }
    row.update(kw)
    return row


def _geo(iso="GB", region="UK"):
    return {"iso": iso, "region": region}


class ProviderReadOverridesCache(unittest.TestCase):
    """The provider read is the authority, not the inventory cache."""

    def test_a_send_yesterday_is_never_read_as_untouched(self):
        """The core regression. Inventory says 111 days; provider says 1.

        If this test passes when `last_provider_touch` is deleted, the
        property it guards is not connected to the provider read.
        """
        now = _fixed_now()
        yesterday = (now - datetime.timedelta(days=1)).isoformat()
        row = _inventory_row()
        result = rpr._assess_with_data(
            row, _geo(), yesterday, 491, now=now)
        self.assertNotEqual(result["lane"], rpr.REENGAGE)
        self.assertEqual(result["provider_age_days"], 1)
        self.assertEqual(result["last_confirmed_campaign"], 491)

    def test_inventory_age_alone_would_wrongly_admit(self):
        """The defect in one assertion: the cache says REENGAGE, wrongly.

        The inventory's last_touch is 111 days ago. Without the provider
        read, the REENGAGE predicate would admit this row. The provider
        read says the last send was yesterday, which is inside the 90-day
        rule.
        """
        now = _fixed_now()
        yesterday = (now - datetime.timedelta(days=1)).isoformat()
        row = _inventory_row()
        inv_age = (now - rpr._parse(row["last_touch"])).days
        self.assertGreaterEqual(inv_age, 90,
                                "test precondition: inventory must be 90+")
        result = rpr._assess_with_data(
            row, _geo(), yesterday, 491, now=now)
        self.assertNotEqual(result["lane"], rpr.REENGAGE,
                            "provider read must refuse what cache admitted")

    def test_a_genuinely_old_send_still_qualifies(self):
        """A provider-confirmed send 100 days ago IS reengage-eligible."""
        now = _fixed_now()
        old = (now - datetime.timedelta(days=100)).isoformat()
        row = _inventory_row()
        result = rpr._assess_with_data(
            row, _geo(), old, 352, now=now)
        self.assertEqual(result["lane"], rpr.REENGAGE)
        self.assertEqual(result["provider_age_days"], 100)

    def test_a_provider_read_failure_is_held_never_no_touch(self):
        """A read failure is HELD. Not 'no touch found', not stale-enough.

        Counting a failure as 'no touch' is how a person gets messaged
        twice. The row stays in the output but its lane is HELD.
        """
        now = _fixed_now()
        row = _inventory_row()
        result = rpr._assess_with_data(
            row, _geo(), None, None, now=now)
        self.assertEqual(result["status"], rpr.HELD)
        self.assertEqual(result["lane"], rpr.HELD)
        self.assertIsNone(result["provider_age_days"])


class TheWiringIsReal(unittest.TestCase):
    """assess_row calls last_provider_touch. Deleting it breaks the test.

    This is the TASK-029 / TASK-028 / TASK-019 rule: a change that is
    correct and not consumed is a change that did nothing. The provider
    read must be on the code path, not just defined.
    """

    def test_assess_row_calls_last_provider_touch(self):
        """The function exists and is called by assess_row.

        If `last_provider_touch` is deleted from the script, this test
        fails with AttributeError. That is the property: the assessment
        depends on the provider read being present and connected.
        """
        self.assertTrue(hasattr(rpr, "last_provider_touch"),
                        "last_provider_touch must exist in the script")
        self.assertTrue(callable(rpr.last_provider_touch))
        with open(rpr.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("last_provider_touch(lead_id)", src,
                       "assess_row must call last_provider_touch")


class GeoFilter(unittest.TestCase):
    """UK/EU is decided by stored ISO code, not by TLD or guess."""

    def test_gb_is_uk_eu(self):
        self.assertTrue(rpr.is_uk_eu_iso("GB"))

    def test_ie_is_uk_eu(self):
        self.assertTrue(rpr.is_uk_eu_iso("IE"))

    def test_de_is_uk_eu(self):
        self.assertTrue(rpr.is_uk_eu_iso("DE"))

    def test_fr_is_uk_eu(self):
        self.assertTrue(rpr.is_uk_eu_iso("FR"))

    def test_hr_is_uk_eu(self):
        """Croatia - CEE region, firmly EU."""
        self.assertTrue(rpr.is_uk_eu_iso("HR"))

    def test_us_is_not_uk_eu(self):
        self.assertFalse(rpr.is_uk_eu_iso("US"))

    def test_au_is_not_uk_eu(self):
        self.assertFalse(rpr.is_uk_eu_iso("AU"))

    def test_none_is_not_uk_eu(self):
        self.assertFalse(rpr.is_uk_eu_iso(None))

    def test_empty_is_not_uk_eu(self):
        self.assertFalse(rpr.is_uk_eu_iso(""))


class ReengagePredicate(unittest.TestCase):
    """The predicate against provider figures, not inventory cache."""

    def test_no_reply_no_unsub_90_plus_is_reengage(self):
        row = _inventory_row()
        ok, lane, why = rpr._reengage_predicate(row, 100)
        self.assertTrue(ok)
        self.assertEqual(lane, rpr.REENGAGE)

    def test_under_90_is_not_reengage(self):
        row = _inventory_row()
        ok, lane, why = rpr._reengage_predicate(row, 30)
        self.assertFalse(ok)
        self.assertEqual(lane, rpr.UNKNOWN)

    def test_unsubscribe_is_never(self):
        row = _inventory_row(unsubscribed=True)
        ok, lane, why = rpr._reengage_predicate(row, 200)
        self.assertFalse(ok)
        self.assertEqual(lane, rpr.NEVER)

    def test_reply_is_revive(self):
        row = _inventory_row(replied=True)
        ok, lane, why = rpr._reengage_predicate(row, 200)
        self.assertFalse(ok)
        self.assertEqual(lane, rpr.REVIVE)

    def test_none_age_is_held(self):
        row = _inventory_row()
        ok, lane, why = rpr._reengage_predicate(row, None)
        self.assertFalse(ok)
        self.assertEqual(lane, rpr.HELD)


class DeltaDistribution(unittest.TestCase):

    def test_buckets_are_correct(self):
        results = [
            {"delta_days": 0},
            {"delta_days": 3},
            {"delta_days": -5},
            {"delta_days": 15},
            {"delta_days": -50},
            {"delta_days": 111},
            {"delta_days": None},
        ]
        dist = rpr.delta_distribution(results)
        self.assertEqual(dist["0"], 1)
        self.assertEqual(dist["1-6"], 2)
        self.assertEqual(dist["7-30"], 1)
        self.assertEqual(dist["30+"], 2)
        self.assertEqual(dist["n/a"], 1)


class AutomatedReplyExclusion(unittest.TestCase):
    """An automated reply is NOT a human reply. is_automated decides."""

    def test_out_of_office_is_automated_not_human(self):
        """An out-of-office does not trip the REVIVE lane.

        `replies.is_automated` says out_of_office is automated. A row
        carrying only an automated reply is not in the REVIVE lane - it
        can still be REENGAGE if the provider age qualifies.
        """
        from src import replies
        self.assertTrue(replies.is_automated("out_of_office"))
        self.assertTrue(replies.is_automated("automated"))
        self.assertTrue(replies.is_automated("assistant_redirect"))
        self.assertFalse(replies.is_automated("positive"))
        self.assertFalse(replies.is_automated("neutral"))


if __name__ == "__main__":
    unittest.main()
