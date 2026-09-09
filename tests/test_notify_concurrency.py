"""Two writers planning the same notification must produce one row.

`plan` checks the id inside `notify.transaction()`, and only there. That is
deliberate: a check before the transaction is free to write and impossible to
test, because either check alone keeps the behaviour identical and no test can
fail for removing one.

The check that survives is the one that holds under a race. A provider poller
replaying an EmailBison page from two threads, or two operators approving from
two tabs, is exactly the window between reading the file and appending to it -
and a duplicate row there is a second Slack message about one event.

The threaded tests here are what make that guard removable-and-caught by
`tools/mutation_audit.py`.
"""
import os
import shutil
import tempfile
import threading
import unittest

from src import notify, store
from src import workspaces as ws

MINE = "productive"


class OneEventOneRow(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-notify-lock-")
        self._prev = {k: os.environ.get(k)
                      for k in ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES",
                                "AUDIT", "SENDERS", "NOTIFICATIONS",
                                notify.OPS_CHANNEL_VAR)}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ[notify.OPS_CHANNEL_VAR] = "#resonate-outbound-ops"
        ws.ensure(MINE, "Productive", client=MINE)
        ws.set_policy(MINE, {notify.WORKSPACE_CHANNEL_KEY: "#client-room"},
                      actor="test")

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan_many(self, count, ids=None, event_type=None):
        """`count` threads, one identical notification, released together."""
        start = threading.Event()
        results, errors = [], []

        def go():
            start.wait(5)
            try:
                results.append(notify.plan(
                    event_type or notify.POSITIVE_REPLY, MINE,
                    fields={"company": "Acme", "contact_name": "Sarah"},
                    ids=ids or {"provider_event_id": "bison-race-1"}))
            except Exception as e:                          # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=go) for _ in range(count)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join(30)
        self.assertEqual(errors, [], f"a writer raised: {errors[:1]}")
        return results

    def test_eight_writers_produce_one_notification(self):
        self.plan_many(8)
        self.assertEqual(len(notify.load()), 1)

    def test_every_writer_is_handed_the_same_row(self):
        """The loser of the race gets the winner's row, not None."""
        results = self.plan_many(8)
        self.assertEqual(len(results), 8)
        self.assertEqual(len({r["id"] for r in results}), 1)

    def test_the_one_row_is_routed_correctly(self):
        """A race must not be able to produce a row with no channel."""
        self.plan_many(8)
        row = notify.load()[0]
        self.assertEqual(row["channel"], "#client-room")
        self.assertEqual(row["destination"], notify.WORKSPACE)

    def test_two_different_events_are_two_rows(self):
        """The guard has to be about the id, not about refusing to write."""
        self.plan_many(4, ids={"provider_event_id": "bison-a"})
        self.plan_many(4, ids={"provider_event_id": "bison-b"})
        self.assertEqual(len(notify.load()), 2)

    def test_a_second_pass_after_the_race_still_adds_nothing(self):
        self.plan_many(8)
        notify.plan(notify.POSITIVE_REPLY, MINE,
                    fields={"company": "Acme", "contact_name": "Sarah"},
                    ids={"provider_event_id": "bison-race-1"})
        self.assertEqual(len(notify.load()), 1)

    def test_racing_operational_events_are_deduped_too(self):
        """Not a property of one event type."""
        self.plan_many(8, ids={"job_id": "job-1"},
                       event_type=notify.FAILED_JOB)
        self.assertEqual(len(notify.load()), 1)


if __name__ == "__main__":
    unittest.main()
