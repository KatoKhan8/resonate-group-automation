"""TASK-281: the UK/EU re-engagement age comes from the provider, not the cache.

The inventory's `last_touch` is a cached value that can be months stale.
The provider's confirmed send history is the truth. This test proves the
comparison reads the provider, not the cache.

THE KEY TEST: a lead with a provider-confirmed send yesterday can never
read as untouched. Feed the checker an inventory row claiming 111 days
and a provider row from yesterday; the answer must be "touched yesterday",
and deleting the provider read must make that test fail.
"""
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import reengagement_provider_read as rpr                          # noqa: E402


def _now():
    return datetime.datetime(2026, 9, 25, 12, 0, 0,
                             tzinfo=datetime.timezone.utc)


def _days_ago(n, now=None):
    now = now or _now()
    return now - datetime.timedelta(days=n)


def _iso(dt):
    return dt.isoformat()


def _inv_row(lead_id="12345", last_touch_days=111, country_code="GB",
             provider="emailbison", **kw):
    """An inventory row with a last_touch `last_touch_days` before now."""
    stamp = _iso(_days_ago(last_touch_days))
    row = {"provider": provider, "campaign_id": 262, "lead_id": lead_id,
           "state": "stopped", "last_touch": stamp,
           "country_code": country_code}
    row.update(kw)
    return row


def _bison_send(campaign_id=491, sent_at_days=1):
    """A confirmed EmailBison send `sent_at_days` before now."""
    return {"campaign_id": campaign_id,
            "sent_at": _iso(_days_ago(sent_at_days)), "step": 1}


def _hr_touch(campaign_id=56000, sent_at_days=5):
    """A confirmed HeyReach outbound message `sent_at_days` before now."""
    return {"campaign_id": campaign_id,
            "sent_at": _iso(_days_ago(sent_at_days))}


class TestProviderAgeOverridesTheCache(unittest.TestCase):
    """THE KEY TEST. A provider-confirmed send yesterday means touched
    yesterday, whatever the cache says."""

    def test_yesterday_send_reads_as_touched_not_111_days(self):
        """Lead with inventory claiming 111 days and provider confirming 1.

        The answer must be provider_age_days=1, NOT 111. The cache is wrong
        and the provider read is the truth.
        """
        row = _inv_row(last_touch_days=111)
        sends = [_bison_send(sent_at_days=1)]
        comp = rpr.compare_row(row, sends, [], now=_now())
        self.assertEqual(comp["provider_age_days"], 1)
        self.assertNotEqual(comp["provider_age_days"], 111)
        self.assertEqual(comp["delta_days"], 110)

    def test_deleting_the_provider_read_makes_the_test_fail(self):
        """Without the provider read, the comparison has no provider age.

        This proves the test above depends on the provider data, not on
        the inventory value. Removing the provider read makes the row HELD,
        not "111 days untouched".
        """
        row = _inv_row(last_touch_days=111)
        comp = rpr.compare_row(row, [], [], now=_now())
        self.assertIsNone(comp["provider_age_days"])
        lane, reason = rpr.reengage_predicate(row, comp["provider_age_days"])
        self.assertEqual(lane, "HELD")
        self.assertIn("provider", reason.lower())

    def test_the_provider_age_drives_the_predicate_not_the_inventory(self):
        """111 days in the cache, 1 day at the provider -> TOO_RECENT.

        The cache would have said REENGAGE. The provider says the lead was
        touched yesterday, which is firmly inside the 90-day window.
        """
        row = _inv_row(last_touch_days=111)
        sends = [_bison_send(sent_at_days=1)]
        comp = rpr.compare_row(row, sends, [], now=_now())
        lane, _reason = rpr.reengage_predicate(row, comp["provider_age_days"])
        self.assertEqual(lane, "TOO_RECENT")
        self.assertNotEqual(lane, "REENGAGE")


class TestReengagePredicate(unittest.TestCase):
    """The REENGAGE lane against provider figures."""

    def test_90_days_no_reply_no_unsub_no_bounce_is_reengage(self):
        row = _inv_row()
        lane, reason = rpr.reengage_predicate(row, 91)
        self.assertEqual(lane, "REENGAGE")

    def test_exactly_90_is_not_yet(self):
        row = _inv_row()
        lane, _reason = rpr.reengage_predicate(row, 90)
        self.assertEqual(lane, "TOO_RECENT")

    def test_89_days_is_too_recent(self):
        row = _inv_row()
        lane, _reason = rpr.reengage_predicate(row, 89)
        self.assertEqual(lane, "TOO_RECENT")

    def test_none_provider_age_is_held(self):
        row = _inv_row()
        lane, reason = rpr.reengage_predicate(row, None)
        self.assertEqual(lane, "HELD")
        self.assertIn("provider", reason.lower())

    def test_reply_is_revive(self):
        row = _inv_row()
        lane, _reason = rpr.reengage_predicate(row, 100, has_reply=True)
        self.assertEqual(lane, "REVIVE")

    def test_unsubscribe_is_never(self):
        row = _inv_row()
        lane, _reason = rpr.reengage_predicate(row, 100, has_unsubscribe=True)
        self.assertEqual(lane, "NEVER")

    def test_bounce_is_never(self):
        row = _inv_row()
        lane, _reason = rpr.reengage_predicate(row, 100, has_bounce=True)
        self.assertEqual(lane, "NEVER")


class TestAutomatedReplyIsNotAHumanReply(unittest.TestCase):
    """`replies.is_automated` decides. An automated reply does NOT move
    the row to REVIVE."""

    def test_out_of_office_does_not_block_reengage(self):
        from src.replies import OUT_OF_OFFICE
        row = _inv_row()
        lane, _reason = rpr.reengage_predicate(
            row, 100, has_reply=True, reply_is_automated=True)
        self.assertEqual(lane, "REENGAGE")

    def test_human_reply_does_block_reengage(self):
        row = _inv_row()
        lane, _reason = rpr.reengage_predicate(
            row, 100, has_reply=True, reply_is_automated=False)
        self.assertEqual(lane, "REVIVE")


class TestUKEUFilter(unittest.TestCase):
    """UK/EU selection by ISO code."""

    def test_gb_is_uk_eu(self):
        self.assertTrue(rpr.is_uk_eu("GB"))

    def test_de_is_uk_eu(self):
        self.assertTrue(rpr.is_uk_eu("DE"))

    def test_us_is_not_uk_eu(self):
        self.assertFalse(rpr.is_uk_eu("US"))

    def test_none_is_not_uk_eu(self):
        self.assertFalse(rpr.is_uk_eu(None))

    def test_empty_is_not_uk_eu(self):
        self.assertFalse(rpr.is_uk_eu(""))

    def test_filter_selects_uk_eu_rows(self):
        rows = [_inv_row(lead_id="1", country_code="GB"),
                _inv_row(lead_id="2", country_code="US"),
                _inv_row(lead_id="3", country_code="DE"),
                _inv_row(lead_id="4", country_code="")]
        uk_eu, non_uk_eu, no_country = rpr.filter_uk_eu(rows, {})
        self.assertEqual(len(uk_eu), 2)
        self.assertEqual(non_uk_eu, 1)
        self.assertEqual(no_country, 1)

    def test_store_map_fills_missing_country(self):
        rows = [_inv_row(lead_id="1", country_code="")]
        country_map = {"1": "FR"}
        uk_eu, non_uk_eu, no_country = rpr.filter_uk_eu(rows, country_map)
        self.assertEqual(len(uk_eu), 1)
        self.assertEqual(uk_eu[0]["country_code"], "FR")


class TestDeriveLastTouch(unittest.TestCase):
    """The most recent send across both providers wins."""

    def test_emailbison_only(self):
        stamp, cid, source = rpr.derive_last_touch(
            [_bison_send(sent_at_days=5)], [])
        self.assertEqual(source, "emailbison")
        self.assertEqual(cid, 491)

    def test_heyreach_only(self):
        stamp, cid, source = rpr.derive_last_touch(
            [], [_hr_touch(sent_at_days=3)])
        self.assertEqual(source, "heyreach")

    def test_most_recent_wins(self):
        """HeyReach at 2 days beats EmailBison at 10."""
        stamp, cid, source = rpr.derive_last_touch(
            [_bison_send(sent_at_days=10)],
            [_hr_touch(sent_at_days=2)])
        self.assertEqual(source, "heyreach")
        self.assertEqual(stamp.day, _days_ago(2).day)

    def test_empty_both(self):
        stamp, cid, source = rpr.derive_last_touch([], [])
        self.assertIsNone(stamp)
        self.assertIsNone(cid)
        self.assertIsNone(source)


class TestDeltaDistribution(unittest.TestCase):
    """Bucket the deltas correctly."""

    def test_buckets(self):
        comps = [
            {"delta_days": 0},
            {"delta_days": 3},
            {"delta_days": 15},
            {"delta_days": 60},
            {"delta_days": None},
        ]
        dist = rpr.delta_distribution(comps)
        self.assertEqual(dist["0"], 1)
        self.assertEqual(dist["1-6"], 1)
        self.assertEqual(dist["7-30"], 1)
        self.assertEqual(dist["30+"], 1)
        self.assertEqual(dist["unknown"], 1)


class TestRunComparison(unittest.TestCase):
    """End-to-end comparison with fixture data."""

    def test_full_pipeline(self):
        rows = [_inv_row(lead_id="1", last_touch_days=111, country_code="GB"),
                _inv_row(lead_id="2", last_touch_days=100, country_code="DE")]
        bison_data = {"1": [_bison_send(sent_at_days=1)],
                       "2": [_bison_send(sent_at_days=95)]}
        comps, lanes, excluded = rpr.run_comparison(
            rows, bison_data, {}, now=_now())
        self.assertEqual(len(comps), 2)
        self.assertEqual(lanes["TOO_RECENT"], 1)
        self.assertEqual(lanes["REENGAGE"], 1)

    def test_held_on_provider_error(self):
        rows = [_inv_row(lead_id="1", country_code="GB")]
        bison_data = {"1": "READ_ERROR: HttpTimeout: timed out"}
        comps, lanes, _excl = rpr.run_comparison(rows, bison_data, {})
        self.assertEqual(lanes["HELD"], 1)
        self.assertEqual(comps[0]["status"], "HELD")


class TestNoLastTouchInScript(unittest.TestCase):
    """The script must not read work/stage/last-touch.json.

    That file is the defect. If the script imports, opens, or transitively
    reads it, the measurement is the same wrong one.
    """

    def test_no_last_touch_reference_in_source(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts", "reengagement_provider_read.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        for line_no, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            self.assertNotIn("last-touch", line,
                             f"line {line_no} references last-touch: {line}")


if __name__ == "__main__":
    unittest.main()
