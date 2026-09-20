"""A running monitor whose output nobody can read is indistinguishable from
a dead one, and is worse, because its PID says it is fine.

Found 2026-09-20: six monitors alive by PID, five of them provider watchers
whose `emit` was `print(line, flush=True)` into a pipe whose shell had exited
with the session that launched them. 487's ten openers were two days out. The
SEND line for the first real batch this system would ever send was going to be
printed into nothing.

The tests are about the two halves that make silence readable:

  - an EVENT is durable, attributable, and survives six watchers writing at
    once - which it only does because the measurement below forced one file
    per watcher
  - a HEARTBEAT is rewritten every poll, including the polls that emit
    nothing, so an empty event log can be read as "unchanged" rather than
    "died an hour ago" - and an unreadable or undated beat counts as STALE,
    never as fresh

No network and no provider module: this is a file-discipline test.
"""
import os
import shutil
import sys
import tempfile
import threading
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import store, watchsink  # noqa: E402


class WatchSinkTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # Snapshot and restore, the way `tests/base.py` does. `use_directory`
        # sets QUEUE for the PROCESS, so a class that only points it away
        # leaves every later class in the same run pointed at a deleted temp
        # directory - which turned three unrelated `test_invariants` cases red
        # the first time these two modules were run together.
        self._env = {k: os.environ.get(k)
                     for k in ("QUEUE", "OUT") + store.STATE_OVERRIDES}
        self.addCleanup(self._restore_env)
        store.use_directory(self.tmp)

    def _restore_env(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # ---------------------------------------------------------- events

    def test_an_event_is_readable_after_the_process_that_wrote_it_is_gone(self):
        watchsink.record("bison", "SEND 487 queue rows sent 0 -> 10",
                         campaign=487)
        rows = watchsink.events()
        self.assertEqual(1, len(rows))
        self.assertEqual("SEND", rows[0]["kind"])
        self.assertEqual(487, rows[0]["campaign"])
        self.assertEqual("bison", rows[0]["source"])
        self.assertEqual("bison:487", rows[0]["watcher"])
        self.assertTrue(rows[0]["at"].endswith("Z"))

    def test_the_kind_is_the_head_of_the_line_so_it_is_not_restated(self):
        watchsink.record("bison", "SCHEDULE-MOVED 487 first send a -> b")
        self.assertEqual("SCHEDULE-MOVED", watchsink.events()[0]["kind"])

    def test_events_filter_by_source_kind_and_time(self):
        watchsink.record("bison", "SEND 487 x", campaign=487)
        watchsink.record("heyreach", "REPLY 605732 y", campaign=605732)
        watchsink.record("bison", "TOUCHED 487 z", campaign=487)
        self.assertEqual(2, len(watchsink.events(source="bison")))
        self.assertEqual(1, len(watchsink.events(kind="REPLY")))
        self.assertEqual(0, len(watchsink.events(since="2999-01-01T00:00:00Z")))
        self.assertEqual(3, len(watchsink.events(since="2000-01-01T00:00:00Z")))

    def test_six_watchers_writing_at_once_lose_nothing(self):
        """THE TEST THAT CORRECTED THE DESIGN.

        The first version had all six append to one shared file with a single
        `os.write` to an `O_APPEND` descriptor, on the reasoning that this is
        one atomic call into the OS. On POSIX it is. On Windows the CRT
        implements `O_APPEND` as seek-to-end THEN write, and this assertion
        read 193 of 240 - rows LOST, not torn. One file per watcher removes
        the sharing rather than fighting the race.

        Six is the real number of monitors on this estate. Threads reach the
        same file discipline as processes and can be asserted on in one test.
        """
        def hammer(n):
            for i in range(40):
                watchsink.record("w%d" % n, "TICK %d-%d" % (n, i))

        threads = [threading.Thread(target=hammer, args=(n,))
                   for n in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(6, len(os.listdir(watchsink.events_dir())))
        rows = watchsink.events()
        self.assertEqual(240, len(rows))
        self.assertFalse([r for r in rows if r.get("torn")])
        self.assertEqual(6, len({r["source"] for r in rows}))

    def test_two_campaigns_on_one_provider_are_two_watchers(self):
        """`bison:487` and `bison:489` are two processes. A name that
        collapsed them would put two writers back on one file."""
        watchsink.record("bison", "SEND 487 x", campaign=487)
        watchsink.record("bison", "SEND 489 y", campaign=489)
        self.assertEqual({"bison-487.jsonl", "bison-489.jsonl"},
                         set(os.listdir(watchsink.events_dir())))
        self.assertEqual(2, len(watchsink.events(source="bison")))
        self.assertEqual(1, len(watchsink.events(campaign=487)))

    def test_the_merged_read_is_one_timeline_oldest_first(self):
        watchsink.record("bison", "SEND 487 a", campaign=487, at=300.0)
        watchsink.record("heyreach", "REPLY 605732 b", at=100.0)
        watchsink.record("bison", "TOUCHED 489 c", campaign=489, at=200.0)
        self.assertEqual(["REPLY", "TOUCHED", "SEND"],
                         [r["kind"] for r in watchsink.events()])

    def test_two_processes_on_one_watcher_name_are_named_as_contended(self):
        """The split only removes the race while the NAMES stay distinct, and
        on 2026-09-20 they did not: one watcher ran `--campaign 487` and
        another took 487 from the default."""
        watchsink.record("bison", "WATCHING 487 a", campaign=487)
        self.assertEqual({}, watchsink.contenders())
        # A second process, same identity, same file.
        path = watchsink.events_path("bison", 487)
        with open(path, "a", encoding="utf-8") as f:
            f.write('{"at": "2026-09-20T12:00:00Z", "source": "bison", '
                    '"watcher": "bison:487", "kind": "WATCHING", '
                    '"line": "WATCHING 487 b", "campaign": 487, '
                    '"pid": 999999}' + "\n")
        self.assertEqual({"bison:487": sorted([os.getpid(), 999999])},
                         watchsink.contenders())

    def test_a_replaced_watcher_is_not_a_contended_one(self):
        """The event files outlive a restart, so a watcher that was stopped
        and replaced leaves its pid behind and reads as contended for ever.
        Measured on the live fleet 2026-09-20: the unscoped call named both
        bison watchers an hour after they were restarted onto new code.
        The window is the caller's to state."""
        watchsink.record("bison", "WATCHING 487 old", campaign=487, at=100.0)
        path = watchsink.events_path("bison", 487)
        with open(path, "a", encoding="utf-8") as f:
            f.write('{"at": "2026-09-20T12:59:00Z", "source": "bison", '
                    '"watcher": "bison:487", "kind": "WATCHING", '
                    '"line": "WATCHING 487 new", "campaign": 487, '
                    '"pid": 999999}' + "\n")
        self.assertIn("bison:487", watchsink.contenders())
        self.assertEqual({}, watchsink.contenders(
            since="2026-09-20T12:58:00Z"))

    def test_a_torn_line_is_reported_rather_than_dropped(self):
        """Dropping it would hide the evidence that a second writer had
        reached this file, which is the failure the split prevents."""
        watchsink.record("bison", "SEND 487 real", campaign=487)
        with open(watchsink.events_path("bison", 487), "a",
                  encoding="utf-8") as f:
            f.write('{"at": "2026-09-20T00:00:0' + "\n")
        rows = watchsink.events()
        self.assertEqual(2, len(rows))
        self.assertTrue(rows[-1].get("torn"))
        self.assertEqual("TORN", rows[-1]["kind"])

    def test_a_long_line_loses_its_tail_and_never_its_attribution(self):
        watchsink.record("bison", "SEND " + ("x" * 20000), campaign=487)
        row = watchsink.events()[0]
        self.assertTrue(row["truncated"])
        self.assertEqual("bison", row["source"])
        self.assertEqual(487, row["campaign"])
        self.assertTrue(row["at"])

    # ------------------------------------------------------- heartbeats

    def test_a_beat_separates_unchanged_from_died_an_hour_ago(self):
        watchsink.beat("bison", campaign=487, state={"sent": 0})
        beats = watchsink.heartbeats()
        self.assertEqual(1, len(beats))
        self.assertEqual("bison:487", beats[0]["watcher"])
        self.assertEqual(0, beats[0]["state"]["sent"])
        self.assertEqual(os.getpid(), beats[0]["pid"])
        self.assertEqual([], watchsink.stale(3600))

    def test_a_beat_that_stopped_is_stale_and_says_how_long_ago(self):
        watchsink.beat("bison", campaign=487, at=1000.0)
        rows = watchsink.stale(600, now=2000.0)
        self.assertEqual(1, len(rows))
        self.assertEqual("bison:487", rows[0]["watcher"])
        self.assertAlmostEqual(1000.0, rows[0]["age"])

    def test_an_unreadable_beat_is_stale_and_not_fresh(self):
        """The question is "may I read silence as unchanged". For a beat that
        cannot be parsed the only safe answer is no."""
        watchsink.beat("bison", campaign=487)
        with open(watchsink.heartbeat_path("bison", 487), "w",
                  encoding="utf-8") as f:
            f.write("{not json")
        rows = watchsink.stale(3600)
        self.assertEqual(1, len(rows))
        self.assertIsNone(rows[0]["age"])
        self.assertIn("unreadable", rows[0])

    def test_each_watcher_owns_its_own_file_so_there_is_no_lost_update(self):
        watchsink.beat("bison", campaign=487)
        watchsink.beat("bison", campaign=489)
        watchsink.beat("heyreach", campaign=605732)
        self.assertEqual({"bison-487.json", "bison-489.json",
                          "heyreach-605732.json"},
                         set(os.listdir(watchsink.heartbeat_dir())))
        self.assertEqual(3, len(watchsink.heartbeats()))

    def test_a_blind_watcher_beats_with_a_note_rather_than_looking_healthy(self):
        """Alive-and-cannot-read-the-provider is a different incident from
        alive-and-nothing-changed, and must not report as the second."""
        watchsink.beat("bison", campaign=487,
                       note="READ-ERROR HTTPError 3x")
        self.assertIn("READ-ERROR", watchsink.heartbeats()[0]["note"])

    def test_a_nameless_watcher_is_refused_rather_than_written_unattributed(self):
        with self.assertRaises(ValueError):
            watchsink.beat("")

    # ------------------------------------------------------ the emitter

    def test_the_emitter_still_prints_and_additionally_records(self):
        emit = watchsink.emitter("bison", campaign=487, stream=False)
        emit("SEND 487 queue rows sent 0 -> 10")
        rows = watchsink.events()
        self.assertEqual(1, len(rows))
        self.assertEqual("SEND", rows[0]["kind"])
        self.assertEqual("bison:487", rows[0]["watcher"])

    def test_a_sink_failure_does_not_kill_the_watcher(self):
        """A monitor that dies because its log is unwritable has turned a
        logging fault into a monitoring outage."""
        blocker = os.path.join(self.tmp, "blocker")
        with open(blocker, "w") as f:
            f.write("")
        os.environ["WATCH_EVENTS"] = blocker      # a FILE where a dir must be
        try:
            emit = watchsink.emitter("bison", campaign=487, stream=False)
            emit("SEND 487 x")                    # must not raise
        finally:
            os.environ.pop("WATCH_EVENTS", None)

    # --------------------------------------------------- the guard rail

    def test_a_test_cannot_append_a_fabricated_send_to_the_real_log(self):
        """The file an operator reads to answer "has it sent yet".

        Unpointing the store is the only way to aim a writer at the real
        `work/`. `setUp` restores the whole environment afterwards, which is
        what this test's first version did not do: it left QUEUE cleared and
        turned three unrelated `test_invariants` cases red in the same
        process.
        """
        os.environ.pop("QUEUE", None)
        for override in store.STATE_OVERRIDES:
            os.environ.pop(override, None)
        with self.assertRaises(store.ProductionStateUnderTest):
            watchsink.record("bison", "SEND 487 fabricated", campaign=487)
        with self.assertRaises(store.ProductionStateUnderTest):
            watchsink.beat("bison", campaign=487)


if __name__ == "__main__":
    unittest.main()
