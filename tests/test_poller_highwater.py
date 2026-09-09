"""Two ways a poll reports a quiet week that never happened.

Both defects live on the path whose only job is to notice that somebody
replied, and both are silent: the run succeeds, prints pages and events,
and is missing the row that mattered.

1. **A stored offset is not a resume point.** `poll_heyreach` checkpointed
   `offset + len(items)` into `POST /inbox/GetConversationsV2` and resumed
   there. An offset only survives to the next run if the collection never
   reorders, and this repository documents no ordering for that endpoint
   whatsoever. Newest-first - the ordinary case - shifts every row down as
   conversations arrive, so resuming at the stored offset steps precisely
   over the replies that came in since, permanently. Ordered by last
   message, threads move and are lost at page seams. This is the same
   defect class already found live and fixed for EmailBison on 2026-09-02
   (`PRODUCT-GAPS.md` 15a).

   The fix is the pattern `poll_emailbison` already uses: a high-water mark
   on the message timestamp, every run starting at offset 0. What it does
   *not* borrow is EmailBison's early stop, because that rests on a
   confirmed descending order and HeyReach has none - so the mark filters
   what has already been read but never truncates the walk, and it is only
   advanced when the run drained the inbox.

2. **A missing collection key is not an empty collection.** Both provider
   modules turned a 200 whose `data`/`items` array was absent, renamed or
   re-nested into `[]`. `poll_emailbison` reads no rows as "caught up", so
   an envelope change becomes `events: 0` with no error at all. An empty
   list is a real "nobody replied"; a missing one is a contract violation
   and is raised, exactly as `providers.mapping` raises on a body of the
   wrong type.
"""
import json
import os
import unittest

from src import poller
from src import providers
from src.providers import bison, heyreach

# `ProviderError` is resolved through the module at call time, never
# bound here. `tests/test_audit.py` reloads `src.providers` to prove no
# module reads a credential at import, and a reload mints a fresh
# exception class - so a name bound at module scope stops matching what
# the reloaded module raises. It passes alone and errors under
# `discover`, which is exactly what this file did. `src/poller.py`
# documents the same hazard for the same reason.
from tests.base import ProviderTest, QueueTest


def thread(ident, stamp, sender="CORRESPONDENT"):
    """One conversation as the live endpoint returns it, trimmed."""
    return {"id": ident, "lastMessageAt": stamp, "lastMessageSender": sender,
            "lastMessageText": "hello", "linkedInAccountId": 55,
            "correspondentProfile": {
                "profileUrl": f"https://www.linkedin.com/in/{ident}"},
            "messages": [{"sender": sender, "body": "hello",
                          "createdAt": stamp}]}


def inbox(threads, page_size=50):
    """A fake `heyreach.conversations` over a list, sliced by offset."""
    asked = []

    def fetch(offset=0, limit=page_size):
        asked.append(offset)
        return threads[offset:offset + limit], len(threads)

    fetch.asked = asked
    return fetch


class TheHeyReachCheckpointIsNotAnOffset(QueueTest):
    """Everything here runs against a throwaway checkpoint file."""

    def setUp(self):
        super().setUp()
        self._prev_checkpoints = os.environ.get("CHECKPOINTS")
        os.environ["CHECKPOINTS"] = os.path.join(self.tmp, "checkpoints.json")

    def tearDown(self):
        if self._prev_checkpoints is None:
            os.environ.pop("CHECKPOINTS", None)
        else:
            os.environ["CHECKPOINTS"] = self._prev_checkpoints
        super().tearDown()

    def stored(self, value):
        poller.save_checkpoint("heyreach", value)

    def checkpoint(self):
        with open(poller.checkpoint_path(), encoding="utf-8") as f:
            return json.load(f)["heyreach"]["cursor"]

    # ------------------------------------------------------- the defect

    def test_a_reply_that_arrived_since_the_last_run_is_not_stepped_over(self):
        """The defect in one test, with a newest-first inbox.

        Run one reads the only thread there is and checkpoints. A reply
        then arrives and lands at the head, pushing the old thread from
        offset 0 to offset 1. Resuming from the stored offset of 1 asks
        for exactly the row already read and never sees the new one - and
        reports a clean, empty, successful poll while doing it.
        """
        first = inbox([thread("old", "2026-09-01T10:00:00Z")])
        pages, mark = poller.poll_heyreach(fetch=first)
        self.assertEqual(first.asked, [0])
        self.stored(mark)               # whatever this build checkpoints

        second = inbox([thread("new", "2026-09-03T09:00:00Z"),
                        thread("old", "2026-09-01T10:00:00Z")])
        pages, mark = poller.poll_heyreach(fetch=second)
        got = [t["id"] for p in pages for t in p["items"]]
        self.assertEqual(got, ["new"], "the reply that arrived since")
        self.assertEqual(second.asked, [0], "the second run started at the head")
        self.assertEqual(mark, "2026-09-03T09:00:00Z")

    def test_a_stored_offset_is_never_resumed_from(self):
        """A checkpoint written by an older build is an integer. Reading it
        as a starting offset is the bug; reading it as a mark would compare
        a number against a timestamp. It is neither: it is no mark at all,
        and no mark means read from the head."""
        self.stored(50)
        self.assertIsNone(poller.high_water(50))
        fetch = inbox([thread("a", "2026-09-02T10:00:00Z")])
        pages, mark = poller.poll_heyreach(fetch=fetch)
        self.assertEqual(fetch.asked, [0])
        self.assertEqual([t["id"] for p in pages for t in p["items"]], ["a"])
        self.assertEqual(mark, "2026-09-02T10:00:00Z")

    def test_the_checkpoint_that_gets_written_is_a_timestamp(self):
        """What `run` persists has to be readable by the next run as a
        mark. An offset written into this slot is the defect made durable.
        """
        fetch = inbox([thread("a", "2026-09-02T10:00:00Z")])
        _, mark = poller.poll_heyreach(fetch=fetch)
        self.stored(mark)
        self.assertEqual(self.checkpoint(), "2026-09-02T10:00:00Z")
        self.assertIsNotNone(poller.high_water(self.checkpoint()))

    # ------------------------------------------- the mark, and its limits

    def test_nothing_new_means_nothing_ingested(self):
        self.stored("2026-09-02T10:00:00Z")
        fetch = inbox([thread("a", "2026-09-02T10:00:00Z")])
        pages, mark = poller.poll_heyreach(fetch=fetch)
        self.assertEqual(sum(len(p["items"]) for p in pages), 0)
        self.assertEqual(mark, "2026-09-02T10:00:00Z")

    def test_a_thread_answered_after_the_mark_comes_back(self):
        """The thread is old; the message in it is not. The mark is asked
        about the newest message, so the thread reappears."""
        self.stored("2026-09-02T10:00:00Z")
        row = thread("a", "2026-09-01T09:00:00Z")
        row["messages"].append({"sender": "CORRESPONDENT", "body": "still keen",
                                "createdAt": "2026-09-04T08:00:00Z"})
        pages, mark = poller.poll_heyreach(fetch=inbox([row]))
        self.assertEqual([t["id"] for p in pages for t in p["items"]], ["a"])
        self.assertEqual(mark, "2026-09-04T08:00:00Z")

    def test_a_thread_with_no_readable_timestamp_is_kept(self):
        """Unreadable is not old. Dropping it would be a silent fallback on
        the reply path; keeping it costs one duplicate at worst."""
        self.stored("2026-09-02T10:00:00Z")
        naked = {"id": "mystery", "correspondentProfile": {},
                 "messages": [{"sender": "CORRESPONDENT", "body": "hi"}]}
        pages, _ = poller.poll_heyreach(fetch=inbox([naked]))
        self.assertEqual([t["id"] for p in pages for t in p["items"]],
                         ["mystery"])

    def test_a_backlog_bigger_than_the_page_budget_does_not_advance_the_mark(self):
        """Never advance across a gap. The run saw newer threads than the
        mark, but it did not reach the end of the inbox, so it cannot claim
        to have read everything up to what it saw."""
        self.stored("2026-01-01T00:00:00Z")
        threads = [thread(f"t{i}", f"2026-09-0{i + 1}T00:00:00Z")
                   for i in range(6)]
        pages, mark = poller.poll_heyreach(
            fetch=inbox(threads, page_size=2), page_size=2, max_pages=2)
        self.assertEqual(mark, "2026-01-01T00:00:00Z", "the mark held")
        self.assertEqual(sum(len(p["items"]) for p in pages), 4)

    def test_an_undrained_first_run_sets_no_mark_at_all(self):
        """No prior mark and a budget that ran out is the same argument.
        Setting one here would declare everything below the last page read,
        which is the skip this whole design exists to refuse."""
        threads = [thread(f"t{i}", f"2026-09-0{i + 1}T00:00:00Z")
                   for i in range(6)]
        _, mark = poller.poll_heyreach(
            fetch=inbox(threads, page_size=2), page_size=2, max_pages=2)
        self.assertIsNone(mark)

    def test_an_unreadable_total_never_counts_as_drained(self):
        """`totalCount` is what says the walk reached the end. If it cannot
        be read, the honest answer is that we do not know."""
        threads = [thread("a", "2026-09-01T00:00:00Z"),
                   thread("b", "2026-09-02T00:00:00Z")]

        def fetch(offset=0, limit=2):
            return threads[offset:offset + limit], "lots"

        _, mark = poller.poll_heyreach(fetch=fetch, page_size=2, max_pages=1)
        self.assertIsNone(mark)
        self.assertFalse(poller._reached("lots", 2))

    def test_a_page_that_looks_old_does_not_stop_the_walk(self):
        """The fail-closed half, and it still is.

        The real inbox was read on 2026-09-07 and is descending -
        `lastMessageAt` non-increasing across 200 conversations, four
        pages, fifteen hours, no inversion - which licenses stopping at
        the mark. `_descending` ties that licence to the page in hand
        rather than to the date it was observed, so a provider that
        reorders its inbox stops satisfying it.

        This page is *ascending*, so the licence does not apply and the
        walk must keep going. It puts the new thread on the second page
        deliberately: an early stop here would skip it.
        """
        self.stored("2026-09-02T00:00:00Z")
        threads = [thread("old1", "2026-08-01T00:00:00Z"),
                   thread("old2", "2026-08-02T00:00:00Z"),
                   thread("new", "2026-09-05T00:00:00Z")]
        fetch = inbox(threads, page_size=2)
        pages, mark = poller.poll_heyreach(fetch=fetch, page_size=2)
        self.assertEqual(fetch.asked, [0, 2], "it kept paging")
        self.assertEqual([t["id"] for p in pages for t in p["items"]], ["new"])
        self.assertEqual(mark, "2026-09-05T00:00:00Z")
        self.assertFalse(poller._descending(threads[:2]),
                         "the fixture must be unordered for this test to be "
                         "about the fail-closed path")

    def test_a_descending_page_does_stop_the_walk(self):
        """The other half, and the reason coverage went from one per cent
        to everything new.

        Without this the walk read `MAX_PAGES x PAGE_SIZE` = 250 of the
        real inbox's 25,473 conversations every run, and the mark never
        advanced because the run never drained anything. Newest-first
        means everything below the first already-seen row is older still,
        so meeting the mark is the end of the work.
        """
        self.stored("2026-09-02T00:00:00Z")
        threads = [thread("new", "2026-09-05T00:00:00Z"),
                   thread("seen", "2026-09-01T00:00:00Z"),
                   thread("older", "2026-08-01T00:00:00Z")]
        self.assertTrue(poller._descending(threads))
        fetch = inbox(threads, page_size=2)
        pages, mark = poller.poll_heyreach(fetch=fetch, page_size=2)
        self.assertEqual(fetch.asked, [0], "it paged past the mark")
        self.assertEqual([t["id"] for p in pages for t in p["items"]],
                         ["new"])
        self.assertEqual(mark, "2026-09-05T00:00:00Z")

    def test_an_unreadable_timestamp_is_not_an_inversion(self):
        """Unreadable is not evidence either way, so it must neither
        license the stop nor forbid it on its own."""
        self.assertTrue(poller._descending([
            thread("a", "2026-09-05T00:00:00Z"),
            thread("b", ""),
            thread("c", "2026-09-01T00:00:00Z")]))

    def test_an_empty_page_is_trivially_descending(self):
        self.assertTrue(poller._descending([]))


class AMissingCollectionIsNotAnEmptyOne(ProviderTest):
    """The provider modules stop being strict one line after they start."""

    def wire(self, payload, status=200):
        def transport(method, url, headers, body, timeout):
            return status, json.dumps(payload)
        self.providers.set_transport(transport)

    # ------------------------------------------------------- EmailBison

    def test_replies_with_no_data_array_raises(self):
        self.wire({"meta": {"next_cursor": None}, "results": []})
        with self.assertRaises(providers.ProviderError):
            bison.fetch_replies()

    def test_a_renamed_or_renested_collection_raises(self):
        self.wire({"data": {"replies": [{"id": 1}]}})
        with self.assertRaises(providers.ProviderError):
            bison.fetch_replies()

    def test_an_empty_data_array_is_still_a_real_none(self):
        self.wire({"data": [], "meta": {}})
        rows, cursor = bison.fetch_replies()
        self.assertEqual(rows, [])
        self.assertIsNone(cursor)

    def test_the_poll_refuses_rather_than_reporting_no_replies(self):
        """The consequence, end to end through the real fetch function:
        `poll_emailbison` reads no rows as caught up, so before the fix
        this returned one empty page and a run reported `events: 0` with no
        error - an envelope change indistinguishable from a quiet week."""
        self.wire({"replies": [], "meta": {}})
        with self.assertRaises(poller.PollError):
            poller.poll_emailbison(cursor="", sleep=lambda *_: None)

    # ---------------------------------------------------------- HeyReach

    def test_conversations_with_no_items_array_raises(self):
        self.wire({"conversations": [], "totalCount": 0})
        with self.assertRaises(providers.ProviderError):
            heyreach.conversations()

    def test_an_empty_items_array_is_still_a_real_none(self):
        self.wire({"items": [], "totalCount": 0})
        items, total = heyreach.conversations()
        self.assertEqual(items, [])
        self.assertEqual(total, 0)

    def test_campaigns_with_no_items_array_raises(self):
        self.wire({"totalCount": 3})
        with self.assertRaises(providers.ProviderError):
            heyreach.campaigns()

    def test_the_inbox_poll_refuses_rather_than_reporting_an_empty_inbox(self):
        self.wire({"conversations": [], "totalCount": 0})
        with self.assertRaises(poller.PollError):
            poller.poll_heyreach(cursor="", sleep=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
