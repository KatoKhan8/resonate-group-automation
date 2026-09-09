"""The reply feed runs newest first, so a resumed cursor points at history.

EmailBison's `/api/replies` is descending by `created_at`, and the cursor
it hands back is a bound on *older* items - it decodes to
`{"created_at": ..., "_pointsToNextItems": true}`. Storing that cursor and
resuming from it therefore walks backwards through history and never
returns to the head, so a reply that arrives after the checkpoint was
written is never seen. On the path whose only job is to stop a cadence
when somebody replies, that is the worst possible failure, and it is
invisible: the poll succeeds, reports pages and events, and misses the
one row that mattered.

So the checkpoint is a high-water mark rather than a provider cursor.
Every run starts at the head and pages down only until it reaches
something already seen.

The rule that governs the awkward case: never advance past a gap. If the
page budget runs out before the run reaches the high-water mark, the mark
is left where it was and the backlog is re-read next time. Re-reading is
free - ingestion is idempotent on the provider's own id - while skipping
is a reply nobody answers.
"""
import unittest

from src import poller


def row(stamp, ident=None):
    return {"id": ident or stamp, "created_at": stamp, "type": "Tracked Reply"}


def feed(pages):
    """A fake `fetch` serving fixed pages, newest first."""
    calls = []

    def fetch(cursor=None, per_page=None):
        calls.append(cursor)
        index = 0 if cursor is None else int(cursor)
        rows = pages[index] if index < len(pages) else []
        nxt = str(index + 1) if index + 1 < len(pages) else None
        return rows, nxt

    fetch.calls = calls
    return fetch


class TheCheckpointIsAHighWaterMark(unittest.TestCase):

    def test_a_fresh_poll_marks_the_newest_row_it_saw(self):
        fetch = feed([[row("2026-09-02T10:00:00Z"), row("2026-09-01T10:00:00Z")]])
        pages, mark = poller.poll_emailbison(fetch=fetch, cursor=None)
        self.assertEqual(mark, "2026-09-02T10:00:00Z")
        self.assertEqual(sum(len(p["data"]) for p in pages), 2)

    def test_the_next_run_starts_at_the_head_not_at_the_stored_cursor(self):
        """The defect in one test. A reply that arrives after the mark is
        newer than it, so it sits at the head - which is exactly where a
        resumed provider cursor would never look."""
        fetch = feed([[row("2026-09-03T10:00:00Z"),      # arrived since
                       row("2026-09-02T10:00:00Z")]])    # the mark itself
        pages, mark = poller.poll_emailbison(
            fetch=fetch, cursor="2026-09-02T10:00:00Z")
        got = [r["created_at"] for p in pages for r in p["data"]]
        self.assertEqual(got, ["2026-09-03T10:00:00Z"])
        self.assertEqual(mark, "2026-09-03T10:00:00Z")
        self.assertEqual(fetch.calls, [None], "it asked for the head first")

    def test_nothing_new_means_nothing_ingested(self):
        fetch = feed([[row("2026-09-02T10:00:00Z")]])
        pages, mark = poller.poll_emailbison(
            fetch=fetch, cursor="2026-09-02T10:00:00Z")
        self.assertEqual(sum(len(p["data"]) for p in pages), 0)
        self.assertEqual(mark, "2026-09-02T10:00:00Z")

    def test_it_stops_paging_once_it_reaches_what_it_has_seen(self):
        fetch = feed([[row("2026-09-05T00:00:00Z")],
                      [row("2026-09-04T00:00:00Z"), row("2026-09-01T00:00:00Z")],
                      [row("2026-08-01T00:00:00Z")]])
        pages, _ = poller.poll_emailbison(
            fetch=fetch, cursor="2026-09-03T00:00:00Z", max_pages=10)
        self.assertEqual(fetch.calls, [None, "1"], "the third page was history")
        got = [r["created_at"] for p in pages for r in p["data"]]
        self.assertEqual(got, ["2026-09-05T00:00:00Z", "2026-09-04T00:00:00Z"])

    def test_a_backlog_bigger_than_the_page_budget_does_not_advance_the_mark(self):
        """Advancing here would jump the gap and lose every reply inside
        it. Re-reading is idempotent; skipping is not recoverable."""
        fetch = feed([[row("2026-09-09T00:00:00Z")],
                      [row("2026-09-08T00:00:00Z")],
                      [row("2026-09-07T00:00:00Z")]])
        pages, mark = poller.poll_emailbison(
            fetch=fetch, cursor="2026-01-01T00:00:00Z", max_pages=2)
        self.assertEqual(mark, "2026-01-01T00:00:00Z", "the mark held")
        self.assertEqual(sum(len(p["data"]) for p in pages), 2)

    def test_a_legacy_opaque_cursor_is_not_compared_against_a_timestamp(self):
        """Older builds stored EmailBison's base64 cursor in this slot.
        Comparing a timestamp against it would order arbitrarily, so it is
        treated as no mark at all - which re-reads, and re-reading is safe.
        """
        legacy = "eyJjcmVhdGVkX2F0IjoiMjAyNi0wOC0zMSJ9"
        self.assertIsNone(poller.high_water(legacy))
        fetch = feed([[row("2026-09-02T10:00:00Z")]])
        pages, mark = poller.poll_emailbison(fetch=fetch, cursor=legacy)
        self.assertEqual(sum(len(p["data"]) for p in pages), 1)
        self.assertEqual(mark, "2026-09-02T10:00:00Z")

    def test_a_row_with_no_timestamp_is_kept_rather_than_dropped(self):
        """Unreadable is not the same as old. Dropping it would be a silent
        fallback on the reply path."""
        fetch = feed([[{"id": "x", "type": "Tracked Reply"},
                       row("2026-09-02T10:00:00Z")]])
        pages, _ = poller.poll_emailbison(
            fetch=fetch, cursor="2026-09-01T00:00:00Z")
        ids = [r["id"] for p in pages for r in p["data"]]
        self.assertIn("x", ids)


if __name__ == "__main__":
    unittest.main()
