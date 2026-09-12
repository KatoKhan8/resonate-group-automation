#!/usr/bin/env python3
"""Apify wrote it, Apify billed for it, and this system threw it away.

MEASURED over four real Productive batches: 248 started runs, 35 failures
(14.1%), of which 28 were client-side `TIMEOUT` and 7 were the actor's own
`TIMED-OUT`. Separately, 23.4% of all runs were duplicates - a second actor
started for a domain whose first run had already produced something, because
the record was left empty and so looked untried.

Two defects produced that, and both are arithmetic or a status check rather
than anything subtle.

## The wait was shorter than the run was allowed to be

`POLL_ATTEMPTS` was `int(RUN_TIMEOUT / POLL_INTERVAL)` = `int(180/9)` = 20,
and the loop sleeps BETWEEN polls rather than after the last one - so twenty
attempts waited 19 x 9 = 171 seconds against an actor whose own `timeout` is
180. Every run finishing in that nine-second gap, and every run the actor
itself killed at its deadline, came back as a client-side TIMEOUT.

The attempt count is capped at twenty by `tests/test_invariants.py` and must
stay capped: the ceiling is what keeps a bounded wait bounded. So the
interval is derived from the window instead, and the window runs past the
actor's deadline far enough to observe its own verdict.

## The dataset id was dropped on the way out

`wait_for` returned `{"status": "TIMEOUT", "dataset_id": None}` while the
last `run_status` had just handed one over, and `research.run` then required
`SUCCEEDED`. So a partial crawl - three of five pages, already fetched,
already billed - was discarded with its dataset id in hand, and the next
batch started a second actor for the same domain.
"""
import unittest
from unittest import mock

from src import events, research
from src.providers import apify


class TheWaitOutlastsTheRun(unittest.TestCase):

    def test_the_poll_window_covers_the_actors_own_deadline(self):
        waited = (apify.POLL_ATTEMPTS - 1) * apify.POLL_INTERVAL
        self.assertGreater(
            waited, apify.RUN_TIMEOUT,
            "the wait gives up before the actor is even obliged to stop, so a "
            "run that succeeds at the end of its window is discarded")

    def test_and_leaves_room_for_the_run_to_finalise(self):
        waited = (apify.POLL_ATTEMPTS - 1) * apify.POLL_INTERVAL
        self.assertGreaterEqual(waited,
                                apify.RUN_TIMEOUT + apify.FINALISE_MARGIN - 1)

    def test_without_widening_the_number_of_polls(self):
        """The invariant that keeps a bounded wait bounded. Widening the
        window must not widen the poll count."""
        self.assertLessEqual(apify.POLL_ATTEMPTS, 20)


class ATimeoutKeepsTheDatasetId(unittest.TestCase):

    def statuses(self, *rows):
        """`run_status` answers each call in turn."""
        return mock.patch.object(apify, "run_status", side_effect=list(rows))

    def test_a_client_timeout_reports_the_dataset_it_was_told_about(self):
        running = {"id": "r1", "status": "RUNNING", "dataset_id": "d1"}
        with self.statuses(*[dict(running)] * apify.POLL_ATTEMPTS):
            out = apify.wait_for("r1", sleep=lambda _s: None)
        self.assertEqual(out["status"], "TIMEOUT")
        self.assertEqual(out["dataset_id"], "d1",
                         "the id was known on every poll and thrown away at "
                         "the end")

    def test_with_no_dataset_it_still_reports_none(self):
        running = {"id": "r1", "status": "RUNNING", "dataset_id": None}
        with self.statuses(*[dict(running)] * apify.POLL_ATTEMPTS):
            out = apify.wait_for("r1", sleep=lambda _s: None)
        self.assertEqual(out["status"], "TIMEOUT")
        self.assertIsNone(out["dataset_id"])

    def test_a_finished_run_is_returned_as_it_is(self):
        done = {"id": "r1", "status": "SUCCEEDED", "dataset_id": "d1"}
        with self.statuses(done):
            self.assertEqual(apify.wait_for("r1", sleep=lambda _s: None), done)

    def test_the_actors_own_timeout_is_a_verdict_not_a_wait(self):
        """TIMED-OUT is terminal: the actor stopped it. Polling on would waste
        the rest of the window."""
        killed = {"id": "r1", "status": "TIMED-OUT", "dataset_id": "d1"}
        with self.statuses(killed):
            self.assertEqual(apify.wait_for("r1", sleep=lambda _s: None),
                             killed)


class APartialCrawlIsEvidence(unittest.TestCase):
    """`research.run` required SUCCEEDED, so a dataset it could read was
    discarded because of the status beside it."""

    def test_the_partial_event_exists_in_the_vocabulary(self):
        self.assertIn(events.SCRAPE_PARTIAL, events.KNOWN)

    def test_it_is_not_the_same_event_as_a_failure(self):
        """"three of five pages" and "nothing" are different facts about a
        company, and only one of them is worth re-running."""
        self.assertNotEqual(events.SCRAPE_PARTIAL, events.SCRAPE_FAILED)

    def test_the_consumer_decides_on_the_dataset_not_the_status(self):
        import inspect
        source = inspect.getsource(research.run)
        self.assertIn('if not finished.get("dataset_id")', source,
                      "the gate is back on the status, so a partial crawl is "
                      "discarded again")


if __name__ == "__main__":
    unittest.main()
