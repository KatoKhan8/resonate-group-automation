"""`/api/events` gets the same strictness the reply feed already had.

`src/stoppedcause.py` takes an injectable `events_fetch` and has never been
given a real one, because `bison.fetch_events` did not exist. This adds it,
and the tests here are mostly about the ways a feed reader can quietly report
that nothing happened:

  - a 200 whose `data` array is missing, renamed or re-nested is a CONTRACT
    CHANGE, not an empty feed. Flattening it to `[]` would make a resolver
    record STILL_UNKNOWN - an answer that looks like evidence of nothing
    rather than an unread feed.
  - an empty `data` array IS a real "no events" and passes through.
  - a walk that stopped because it hit its limit must not be reported as a
    walk that reached the end of the feed. On this feed the difference is
    "no such event exists", which is a finding, versus "I stopped reading",
    which is not.
  - a repeating cursor is the end. This instance hands back the same token
    rather than a null one on some routes, and asking again loops forever.

No network: the transport is replaced.
"""
import json
import unittest

from src import providers
from src.providers import bison
from tests.base import ProviderTest


class TheFeedIsReadStrictly(ProviderTest):

    def wire(self, payload, status=200):
        def transport(method, url, headers, body, timeout):
            return status, json.dumps(payload)
        self.providers.set_transport(transport)

    def test_a_missing_data_array_raises_rather_than_reading_as_no_events(self):
        self.wire({"meta": {"next_cursor": None}, "results": []})
        with self.assertRaises(providers.ProviderError) as caught:
            bison.fetch_events()
        self.assertIn("refusing to read that as no events",
                      str(caught.exception))

    def test_a_renested_collection_raises(self):
        self.wire({"data": {"events": [{"id": 1}]}})
        with self.assertRaises(providers.ProviderError):
            bison.fetch_events()

    def test_an_empty_data_array_is_a_real_none(self):
        self.wire({"data": [], "meta": {}})
        rows, cursor = bison.fetch_events()
        self.assertEqual(rows, [])
        self.assertIsNone(cursor)

    def test_a_non_200_raises(self):
        self.wire({"data": []}, status=503)
        with self.assertRaises(providers.ProviderError):
            bison.fetch_events()

    def test_the_cursor_is_returned_for_the_caller_to_hold(self):
        self.wire({"data": [{"id": 1}], "meta": {"next_cursor": "abc"}})
        rows, cursor = bison.fetch_events()
        self.assertEqual(cursor, "abc")
        self.assertEqual(len(rows), 1)


class Paging(ProviderTest):
    """A walk that stopped early must never look like a feed that ended."""

    def pages(self, pages):
        self.sent = []

        def transport(method, url, headers, body, timeout):
            self.sent.append(url)
            payload = pages[min(len(self.sent) - 1, len(pages) - 1)]
            return 200, json.dumps(payload)
        self.providers.set_transport(transport)

    def test_a_walk_that_reached_the_end_is_exhausted(self):
        self.pages([{"data": [{"id": 1}], "meta": {"next_cursor": "b"}},
                    {"data": [{"id": 2}], "meta": {"next_cursor": None}}])
        rows, pages, exhausted = bison.walk_events()
        self.assertEqual(len(rows), 2)
        self.assertEqual(pages, 2)
        self.assertTrue(exhausted)

    def test_a_walk_cut_short_by_its_limit_is_not_exhausted(self):
        self.pages([{"data": [{"id": 1}], "meta": {"next_cursor": "b"}},
                    {"data": [{"id": 2}], "meta": {"next_cursor": "c"}},
                    {"data": [{"id": 3}], "meta": {"next_cursor": "d"}}])
        rows, pages, exhausted = bison.walk_events(limit=2)
        self.assertFalse(exhausted,
                         "a limited walk claimed it had read the whole feed")
        self.assertEqual(len(rows), 2)

    def test_a_repeating_cursor_is_treated_as_the_end(self):
        """Otherwise the walk never terminates."""
        self.pages([{"data": [{"id": 1}], "meta": {"next_cursor": "same"}},
                    {"data": [{"id": 2}], "meta": {"next_cursor": "same"}}])
        rows, pages, exhausted = bison.walk_events()
        self.assertTrue(exhausted)
        self.assertEqual(pages, 2)

    def test_an_empty_page_ends_the_walk(self):
        self.pages([{"data": [], "meta": {"next_cursor": "b"}}])
        rows, pages, exhausted = bison.walk_events()
        self.assertEqual(rows, [])
        self.assertTrue(exhausted)

    def test_cursor_pagination_is_requested_every_time(self):
        """Offset mode carries no next_cursor and refuses page beyond 1000."""
        self.pages([{"data": [{"id": 1}], "meta": {"next_cursor": None}}])
        bison.walk_events()
        self.assertIn("pagination_type=cursor", self.sent[0])


class TheWindowIsMeasuredNotAssumed(unittest.TestCase):
    """What the feed can answer about is a measurement, not a constant."""

    def test_the_window_is_the_oldest_and_newest_created_at(self):
        rows = [{"created_at": "2026-09-18T14:25:53.000000Z"},
                {"created_at": "2026-09-19T09:33:34.000000Z"},
                {"created_at": "2026-09-19T01:00:00.000000Z"}]
        oldest, newest, n = bison.events_window(rows)
        self.assertEqual(oldest, "2026-09-18T14:25:53.000000Z")
        self.assertEqual(newest, "2026-09-19T09:33:34.000000Z")
        self.assertEqual(n, 3)

    def test_rows_with_no_stamp_are_not_counted_as_a_window(self):
        oldest, newest, n = bison.events_window([{"id": 1}, {"id": 2}])
        self.assertIsNone(oldest)
        self.assertIsNone(newest)
        self.assertEqual(n, 0)

    def test_an_empty_feed_has_no_window_rather_than_a_zero_one(self):
        self.assertEqual(bison.events_window([]), (None, None, 0))

    def test_the_retention_is_recorded_as_a_documented_constant(self):
        """Ten days is the feed's retention, not a pagination limit."""
        self.assertEqual(bison.EVENTS_RETENTION_DAYS, 10)


if __name__ == "__main__":
    unittest.main()
