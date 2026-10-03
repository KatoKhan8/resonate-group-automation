"""A lead with a provider-confirmed send yesterday can never read as untouched.

TASK-281. The re-engagement inventory cached a `last_touch` that went stale
by up to 111 days. Lead 133283 read as 111 days untouched while its last
confirmed send was two days earlier from our own campaign 491.

This test feeds the checker an inventory row claiming 111 days and a
provider row from yesterday. The answer MUST be "touched yesterday".
Deleting the provider read from the assessment MUST make the test fail,
proving the provider read is load-bearing, not decorative.
"""
import datetime
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from scripts.reengagement_provider_read import (       # noqa: E402
    REENGAGE_AFTER_DAYS,
    _exclusion_reason,
    _hash,
    _parse,
    assess_row,
    cohort_of,
)


def _now():
    return datetime.datetime(2026, 9, 25, 12, 0, 0,
                             tzinfo=datetime.timezone.utc)


def _inv_row(last_touch_iso, lead_id="133283", record_id="rec-abc",
             country="United Kingdom", **overrides):
    """An inventory-shaped row with a stale last_touch."""
    row = {
        "provider": "emailbison",
        "campaign_id": 491,
        "lead_id": lead_id,
        "state": "finished",
        "last_touch": last_touch_iso,
        "record_id": record_id,
        "country": country,
        "cohort": cohort_of(country),
    }
    row.update(overrides)
    return row


def _provider_send(sent_at_iso, campaign_id=491):
    """A confirmed send row from the provider."""
    return {
        "campaign_id": campaign_id,
        "lead_id": "133283",
        "status": "sent",
        "sent_at": sent_at_iso,
    }


class TestProviderReadBeatsCache(unittest.TestCase):
    """The core invariant: provider age overrides cache age."""

    def test_yesterday_send_never_reads_as_111_days(self):
        """The acceptance test from TASK-281.

        Inventory says 111 days. Provider says yesterday. The answer is
        "touched yesterday", NOT "111 days untouched".
        """
        now = _now()
        inv = _inv_row(
            last_touch_iso="2026-06-06T12:00:00Z",   # 111 days ago
        )
        sends = [_provider_send(
            sent_at_iso="2026-09-24T10:00:00Z",       # yesterday
            campaign_id=491,
        )]
        result = assess_row(inv, sends, None, now=now)

        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["provider_age_days"], 1)
        self.assertEqual(result["inventory_age_days"], 111)
        self.assertEqual(result["delta_days"], 110)
        self.assertEqual(result["provider_touch_campaign"], 491)
        self.assertEqual(result["provider_touch_provider"], "emailbison")
        # The REENGAGE predicate against provider figures must say NO:
        # 1 day is not > 90.
        self.assertFalse(result["reengage_provider"])
        # The REENGAGE predicate against cache figures would say YES:
        # 111 days IS > 90.
        self.assertTrue(result["reengage_cache"])

    def test_deleting_the_provider_read_breaks_the_test(self):
        """Wiring check: without the provider read, the answer is wrong.

        This is the "break the wiring" test from QWEN.md. If the provider
        sends are removed, the row reads as HELD (no confirmed send), and
        the REENGAGE predicate cannot fire correctly.
        """
        now = _now()
        inv = _inv_row(
            last_touch_iso="2026-06-06T12:00:00Z",   # 111 days ago
        )
        # NO provider sends.
        result = assess_row(inv, [], None, now=now)

        # Without provider data, the row is HELD, not "111 days untouched".
        self.assertEqual(result["status"], "HELD")
        self.assertIsNone(result["provider_age_days"])
        self.assertFalse(result["reengage_provider"])

    def test_ninety_one_days_at_provider_is_reengage(self):
        """91 days at the provider, no reply: REENGAGE is correct."""
        now = _now()
        inv = _inv_row(
            last_touch_iso="2026-06-06T12:00:00Z",
        )
        sends = [_provider_send(
            sent_at_iso="2026-06-26T12:00:00Z",       # 91 days ago
        )]
        result = assess_row(inv, sends, None, now=now)

        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["provider_age_days"], 91)
        self.assertTrue(result["reengage_provider"])

    def test_ninety_days_at_provider_is_not_reengage(self):
        """Exactly 90 days is NOT REENGAGE. The threshold is strict >."""
        now = _now()
        inv = _inv_row(
            last_touch_iso="2026-06-06T12:00:00Z",
        )
        sends = [_provider_send(
            sent_at_iso="2026-06-27T12:00:00Z",       # 90 days ago
        )]
        result = assess_row(inv, sends, None, now=now)

        self.assertEqual(result["provider_age_days"], 90)
        self.assertFalse(result["reengage_provider"])

    def test_reply_excludes_from_reengage(self):
        """A row with a reply flag is excluded, regardless of age."""
        now = _now()
        inv = _inv_row(
            last_touch_iso="2026-01-01T12:00:00Z",   # very old
            replied=True,
        )
        sends = [_provider_send(
            sent_at_iso="2026-01-01T12:00:00Z",
        )]
        result = assess_row(inv, sends, None, now=now)

        self.assertIsNotNone(result["excluded_reason"])
        self.assertFalse(result["reengage_provider"])
        self.assertFalse(result["reengage_cache"])

    def test_unsubscribe_excludes_from_reengage(self):
        """A row with an unsubscribe is excluded, regardless of age."""
        now = _now()
        inv = _inv_row(
            last_touch_iso="2026-01-01T12:00:00Z",
            unsubscribed=True,
        )
        sends = [_provider_send(
            sent_at_iso="2026-01-01T12:00:00Z",
        )]
        result = assess_row(inv, sends, None, now=now)

        self.assertIsNotNone(result["excluded_reason"])
        self.assertFalse(result["reengage_provider"])

    def test_bounce_excludes_from_reengage(self):
        """A bounced row is excluded."""
        now = _now()
        inv = _inv_row(
            last_touch_iso="2026-01-01T12:00:00Z",
            state="bounced",
        )
        sends = [_provider_send(
            sent_at_iso="2026-01-01T12:00:00Z",
        )]
        result = assess_row(inv, sends, None, now=now)

        self.assertIsNotNone(result["excluded_reason"])
        self.assertFalse(result["reengage_provider"])

    def test_heyreach_touch_counts(self):
        """A HeyReach touch is a touch. It can override a stale cache."""
        now = _now()
        inv = _inv_row(
            last_touch_iso="2026-06-06T12:00:00Z",   # 111 days ago
        )
        hr_touch = {
            "sent_at": datetime.datetime(2026, 9, 24, 10, 0, 0,
                                         tzinfo=datetime.timezone.utc),
            "campaign_id": None,
        }
        result = assess_row(inv, [], hr_touch, now=now)

        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["provider_age_days"], 1)
        self.assertEqual(result["provider_touch_provider"], "heyreach")
        self.assertFalse(result["reengage_provider"])

    def test_heyreach_and_emailbison_latest_wins(self):
        """When both providers have touches, the latest one is the age."""
        now = _now()
        inv = _inv_row(
            last_touch_iso="2026-01-01T12:00:00Z",
        )
        sends = [_provider_send(
            sent_at_iso="2026-08-01T12:00:00Z",       # 55 days ago
        )]
        hr_touch = {
            "sent_at": datetime.datetime(2026, 9, 20, 10, 0, 0,
                                         tzinfo=datetime.timezone.utc),
            "campaign_id": None,
        }
        result = assess_row(inv, sends, hr_touch, now=now)

        self.assertEqual(result["provider_age_days"], 5)
        self.assertEqual(result["provider_touch_provider"], "heyreach")


class TestUKEUDetermination(unittest.TestCase):
    """UK/EU is decided by the stored ISO country, not a TLD guess."""

    def test_uk_countries(self):
        self.assertEqual(cohort_of("United Kingdom"), "uk")
        self.assertEqual(cohort_of("Ireland"), "uk")

    def test_eu_countries(self):
        self.assertEqual(cohort_of("Germany"), "eu")
        self.assertEqual(cohort_of("France"), "eu")
        self.assertEqual(cohort_of("Croatia"), "eu")

    def test_us_is_not_uk_eu(self):
        self.assertIsNone(cohort_of("United States"))

    def test_unknown_country_is_not_uk_eu(self):
        self.assertIsNone(cohort_of(None))
        self.assertIsNone(cohort_of(""))


class TestExclusionReason(unittest.TestCase):
    """The REVIVE lane stays out. Replies and unsubs are excluded."""

    def test_no_exclusion_for_clean_row(self):
        row = {"state": "finished"}
        self.assertIsNone(_exclusion_reason(row))

    def test_reply_excluded(self):
        row = {"state": "finished", "replied": True}
        self.assertIsNotNone(_exclusion_reason(row))

    def test_replied_state_excluded(self):
        row = {"state": "replied"}
        self.assertIsNotNone(_exclusion_reason(row))

    def test_unsubscribed_excluded(self):
        row = {"state": "finished", "unsubscribed": True}
        self.assertIsNotNone(_exclusion_reason(row))

    def test_bounced_excluded(self):
        row = {"state": "finished", "bounced": True}
        self.assertIsNotNone(_exclusion_reason(row))

    def test_bounce_state_excluded(self):
        row = {"state": "bounced"}
        self.assertIsNotNone(_exclusion_reason(row))


class TestHashedOutput(unittest.TestCase):
    """No prospect data in the output. Only hashed IDs."""

    def test_hash_is_deterministic(self):
        self.assertEqual(_hash("133283"), _hash("133283"))

    def test_hash_is_short(self):
        self.assertEqual(len(_hash("133283")), 12)

    def test_hash_differs_for_different_inputs(self):
        self.assertNotEqual(_hash("133283"), _hash("133284"))


if __name__ == "__main__":
    unittest.main()
