#!/usr/bin/env python3
"""The machine-wide suite lock, and the state this estate had no name for.

WHAT THIS IS ABOUT, measured 2026-10-16 and not hypothesised. At 04:40 a
session inside the `suppression` watcher took the machine-wide suite lock and
launched that branch's full suite under pid 79556. At 04:45:37 the watcher
logged `DONE 0220-...md -> exit0` and the session ended. Two states follow and
they need opposite things from a person - the lock held by nobody who will ever
release it, or a 40-minute suite whose result nobody read - and NEITHER was
visible anywhere in this estate.

`suitelock` itself has only two answers, because it only ever needs two: a
lock it may take, and a lock it must wait for. A READER needs a third. A lock
whose holder is dead is not HELD - nothing is running and nothing will release
it - and it is not FREE either, because until something tries, every waiter
queues behind a holder that no longer exists. That is ORPHAN, and failure
family 6 is exactly an instrument meeting a result it has no name for and
picking the nearest name it has. The nearest name here is HELD.

FIVE CONTROLS, AND EACH IS PROVEN ABLE TO FAIL. A control that cannot go red
licenses nothing, and this repository has shipped two that could not.

    C1  a lock held by a pid that is ALIVE renders HELD and names the pid
    C2  a lock held by a pid that CANNOT EXIST renders ORPHAN - and with the
        liveness probe mutated to always-true, C2 goes red while C1 stays
        green, which is what proves the probe is watched
    C3  the lock's PATH removed entirely renders UNKNOWN and prints the path.
        Not FREE: a listing that fails proves nothing
    C4  a lock file that exists and does not parse renders UNKNOWN - not FREE
        and not HELD
    C5  a lock that is GENUINELY free renders FREE. Without this one the panel
        can only ever say "something is wrong", which is the same defect in
        the other direction

AND THE BOUNDARY. Two tests walk the estate's `queue\\` and `logs\\` and the
lock's own directory and ticket queue before and after a render and require
every file byte-identical. The ticket one is the sharp one: the obvious reader
for the waiter queue is `suitelock._live_tickets`, which UNLINKS a dead
owner's ticket as it walks. An instrument that prunes what it measures is not
one, and nothing but a test keeps that true.
"""
import datetime
import hashlib
import json
import os
import shutil
import socket
import tempfile
import unittest

from src import laneprovenance as lp
from src import lanes
from src import suitelock
from src.web import api
from src.web import pages


#: A pid that cannot be a live process on this machine. Windows pids are
#: bounded well below this, and it is used against the REAL `SystemProbe` so
#: that C2 rests on a reading of the actual process table and not only on
#: fixture arithmetic.
IMPOSSIBLE_PID = 0x7FFFFFF0


class Probe:
    """A process table presented without starting processes.

    One seam, the same one `src.lanes` already reads through, so a test can
    put a pid in the table or take it out. `table=None` is the platform this
    has no reader for, which must make liveness UNKNOWN rather than dead.
    """

    def __init__(self, table=None, cpu=None, readable=True):
        self._table = {} if table is None else dict(table)
        self._cpu = dict(cpu or {})
        self._readable = readable

    def table(self):
        return dict(self._table) if self._readable else None

    def cpu(self, pid):
        return self._cpu.get(int(pid))


class Lock:
    """A lock file on disk, under a directory this test owns."""

    def setUp(self):                                           # noqa: N802
        self.home = tempfile.mkdtemp(prefix="locktest-")
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.work = os.path.join(self.home, "work")
        os.makedirs(self.work)
        self.lock = os.path.join(self.work, "suite.lock")
        self.samples = {}

    def write_lock(self, **fields):
        """A holder's payload, in `suitelock.acquire`'s own shape."""
        payload = {"pid": 4242, "branch": "task-something",
                   "worktree": os.path.join("C:\\", "trees", "wt-thing"),
                   "queued_at": "2026-10-16T04:30:27",
                   "started_at": "2026-10-16T04:40:27",
                   "lock_path": self.lock}
        payload.update(fields)
        with open(self.lock, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return payload

    def write_raw(self, text):
        with open(self.lock, "w", encoding="utf-8") as handle:
            handle.write(text)

    def ticket(self, pid, stamp="00000001760000000.000000"):
        directory = self.lock + suitelock.QUEUE_SUFFIX
        os.makedirs(directory, exist_ok=True)
        name = "%s-%d.json" % (stamp, pid)
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"pid": pid}, handle)
        return path

    def row(self, probe=None, now=None, file_path=False):
        probe = probe if probe is not None else Probe()
        return lanes.lock_row(
            probe=probe, table=probe.table(),
            now=now or datetime.datetime(2026, 10, 16, 5, 40, 27),
            samples=self.samples,
            file_path=self.lock if file_path is False else file_path)

    def rendered(self, row):
        """The panel's HTML for one row, through the real renderer."""
        return pages.lane_locks({"locks": {
            "at": datetime.datetime(2026, 10, 16, 5, 40, 27),
            "table_read": True, "rows": [row], "held": 0, "free": 0,
            "orphan": 0, "held_unknown": 0, "unknown": 0,
            "glossary": [{"state": k, "label": a, "why": b}
                         for k, (a, b) in sorted(lanes.LOCK_TEXT.items())]}})


# --------------------------------------------------------------------------
# C1 AND C2: THE TWO THAT MUST BE ABLE TO DISAGREE


class AHolderThatIsAliveAndOneThatIsNot(unittest.TestCase, Lock):
    """The whole panel turns on telling these two apart."""

    setUp = Lock.setUp

    def test_C1_a_live_holder_renders_HELD_and_names_the_pid(self):
        self.write_lock(pid=4242)
        row = self.row(Probe(table={4242: (1, "python.exe")}))
        self.assertEqual(lanes.LOCK_HELD, row["state"])
        self.assertEqual("HELD", row["state_label"])
        self.assertIs(True, row["alive"])
        self.assertEqual(4242, row["pid"])
        body = self.rendered(row)
        self.assertIn("HELD", body)
        self.assertIn("pid 4242", body)
        self.assertIn("in the process table", body)

    def test_C2_a_holder_that_cannot_exist_renders_ORPHAN(self):
        """THE STATE THE ESTATE HAD NO NAME FOR.

        The pid is checked against the REAL process table, so this rests on
        a reading of this machine rather than on a fixture that simply left
        it out.
        """
        self.write_lock(pid=IMPOSSIBLE_PID)
        probe = lanes.SystemProbe()
        table = probe.table()
        self.assertIsNotNone(
            table, "this platform has no process-table reader, so C2 cannot "
                   "be measured here at all - which is UNKNOWN and is not a "
                   "pass")
        self.assertNotIn(IMPOSSIBLE_PID, table,
                         "the control's impossible pid is in this machine's "
                         "process table, so it proves nothing. Pick another")
        row = self.row(probe)
        self.assertEqual(lanes.LOCK_ORPHAN, row["state"])
        self.assertEqual("ORPHAN", row["state_label"])
        self.assertIs(False, row["alive"])
        self.assertEqual(IMPOSSIBLE_PID, row["pid"])

    def test_C2_the_fixture_half_so_the_two_mutations_share_a_table(self):
        """The same claim through the injected seam, which is what the
        always-true mutation acts on. Kept beside the real-table half so
        neither stands alone."""
        self.write_lock(pid=4242)
        row = self.row(Probe(table={1: ("x", "other.exe")}))
        self.assertEqual(lanes.LOCK_ORPHAN, row["state"])
        self.assertIs(False, row["alive"])

    def test_ORPHAN_is_rendered_as_ORPHAN_and_never_as_held(self):
        """Family 6 on the instrument itself: the nearest name available for
        a lock whose holder is dead is HELD, and it would hide the fact that
        nothing will ever release it."""
        self.write_lock(pid=4242)
        body = self.rendered(self.row(Probe(table={1: ("x", "o.exe")})))
        self.assertIn("ORPHAN", body)
        self.assertIn("NOT in the process table", body)
        self.assertIn("nothing will ever release", body)
        # The remedy is PROSE for a person. Not a button, not a route.
        self.assertIn("Remove-Item", body)
        self.assertNotIn("<form", body)
        self.assertNotIn("<button", body)

    def test_an_unreadable_table_is_HELD_UNKNOWN_and_never_ORPHAN(self):
        """A holder is never called dead on a failed read. That is how a
        running suite's lock was stolen on 2026-10-02."""
        self.write_lock(pid=4242)
        row = self.row(Probe(readable=False))
        self.assertEqual(lanes.LOCK_HELD_UNKNOWN, row["state"])
        self.assertIsNone(row["alive"])
        body = self.rendered(row)
        self.assertIn("HELD, HOLDER UNKNOWN", body)
        self.assertNotIn("ORPHAN</span>", body.split("What each state")[0])

    def test_the_cpu_delta_is_progress_and_never_the_liveness_answer(self):
        """A holder burning no CPU is alive. Rendering it ORPHAN would report
        a suite blocked on a socket as dead - and a first look has no delta
        at all, which would hide ORPHAN on every first page load."""
        self.write_lock(pid=4242)
        probe = Probe(table={4242: (1, "python.exe")}, cpu={4242: 100.0})
        first = self.row(probe, now=datetime.datetime(2026, 10, 16, 5, 0, 0))
        self.assertEqual(lanes.LOCK_HELD, first["state"])
        self.assertIsNone(first["cpu"]["delta_seconds"],
                          "a first sample has no delta and must not invent "
                          "one")
        self.assertIsNone(first["cpu"]["progressing"])
        # Second look, same CPU: no progress, and STILL HELD.
        second = self.row(probe, now=datetime.datetime(2026, 10, 16, 5, 0,
                                                       30))
        self.assertEqual(lanes.LOCK_HELD, second["state"])
        self.assertEqual(0.0, second["cpu"]["delta_seconds"])
        self.assertIs(False, second["cpu"]["progressing"])
        body = self.rendered(second)
        self.assertIn("no CPU movement", body)

    def test_cpu_that_moved_renders_as_progress(self):
        self.write_lock(pid=4242)
        probe = Probe(table={4242: (1, "python.exe")}, cpu={4242: 100.0})
        self.row(probe, now=datetime.datetime(2026, 10, 16, 5, 0, 0))
        probe._cpu[4242] = 118.5
        row = self.row(probe, now=datetime.datetime(2026, 10, 16, 5, 0, 30))
        self.assertEqual(18.5, row["cpu"]["delta_seconds"])
        self.assertEqual(30, row["cpu"]["wall_seconds"])
        self.assertIs(True, row["cpu"]["progressing"])

    def test_a_refused_cpu_handle_is_alive_and_unmeasured_never_zero(self):
        self.write_lock(pid=4242)
        row = self.row(Probe(table={4242: (1, "python.exe")}, cpu={}))
        self.assertEqual(lanes.LOCK_HELD, row["state"])
        self.assertIsNone(row["cpu"]["seconds"])
        self.assertIn("never as zero", row["cpu"]["why"])

    def test_how_long_it_has_been_held_and_how_long_it_queued(self):
        """Two different facts. Merging them overstated one hold by 39
        minutes on 2026-10-02, and the obvious response to that figure is to
        kill a healthy run."""
        self.write_lock(pid=4242, queued_at="2026-10-16T04:30:27",
                        started_at="2026-10-16T04:40:27")
        row = self.row(Probe(table={4242: (1, "python.exe")}),
                       now=datetime.datetime(2026, 10, 16, 5, 40, 27))
        self.assertEqual(3600, row["held_seconds"])
        self.assertEqual(4200, row["queue_wait_seconds"])
        self.assertIn("it waited 10m in the queue first", self.rendered(row))

    def test_an_unparseable_stamp_is_UNKNOWN_and_not_a_zero_duration(self):
        self.write_lock(pid=4242, started_at="right about now")
        row = self.row(Probe(table={4242: (1, "python.exe")}))
        self.assertIsNone(row["held_seconds"])

    def test_a_stamp_in_the_future_is_reported_not_clamped(self):
        """A clock that moved is a real condition, and a clamp to zero would
        hide it behind a plausible number."""
        self.write_lock(pid=4242, started_at="2026-10-17T04:40:27")
        row = self.row(Probe(table={4242: (1, "python.exe")}))
        self.assertLess(row["held_seconds"], 0)
        self.assertIn("stamped in the future", self.rendered(row))

    def test_a_lock_published_to_a_different_path_is_named(self):
        """A per-worktree lock serialises nothing. That is the defect this
        lock exists to prevent, and it is measured rather than assumed."""
        self.write_lock(pid=4242, lock_path=os.path.join(
            "C:\\", "trees", "wt-thing", "work", "suite.lock"))
        row = self.row(Probe(table={4242: (1, "python.exe")}))
        self.assertIs(False, row["path_agrees"])
        self.assertIn("PATH DISAGREES", self.rendered(row))

    def test_a_lock_published_to_this_path_agrees(self):
        self.write_lock(pid=4242)
        row = self.row(Probe(table={4242: (1, "python.exe")}))
        self.assertIs(True, row["path_agrees"])
        self.assertNotIn("PATH DISAGREES", self.rendered(row))


# --------------------------------------------------------------------------
# C3, C4, C5: ABSENT, DAMAGED, AND GENUINELY FREE


class AnUnreadableLockIsNotAFreeOne(unittest.TestCase, Lock):
    """The three the brief requires not to merge."""

    setUp = Lock.setUp

    def test_C3_the_path_removed_entirely_is_UNKNOWN_and_prints_the_path(self):
        """A listing that FAILS proves nothing. `os.path.exists` answers the
        same False for "not there" and "cannot be reached", and those are the
        two facts this panel may not merge."""
        shutil.rmtree(self.work)
        row = self.row()
        self.assertEqual(lanes.LOCK_UNKNOWN, row["state"])
        self.assertNotEqual(lanes.LOCK_FREE, row["state"])
        self.assertIn("could not be listed", row["why"])
        self.assertIn("never", row["why"].lower())
        # THE PATH IS PRINTED. An UNKNOWN with no path is unactionable.
        self.assertEqual(os.path.join("work", "suite.lock"),
                         lanes._lock_path_tail(self.lock, 2))
        body = self.rendered(row)
        self.assertIn("UNKNOWN", body)
        self.assertIn("suite.lock", body)

    def test_C3b_the_listing_is_what_proves_absence_not_a_failed_open(self):
        """The guard itself, observed directly: with the directory gone the
        listing answers None, and None may never become FREE."""
        shutil.rmtree(self.work)
        self.assertIsNone(lanes._lock_listing(self.lock))
        os.makedirs(self.work)
        self.assertIs(False, lanes._lock_listing(self.lock))
        self.write_lock()
        self.assertIs(True, lanes._lock_listing(self.lock))

    def test_C4_a_lock_that_does_not_parse_is_UNKNOWN(self):
        """Not FREE and not HELD. A damaged lock may belong to a running
        suite, which is what `DAMAGED_GRACE` exists for."""
        self.write_raw("{not json at all")
        row = self.row()
        self.assertEqual(lanes.LOCK_UNKNOWN, row["state"])
        self.assertIsNone(row["pid"])
        self.assertIn("did not parse", row["why"])
        body = self.rendered(row)
        self.assertIn("UNKNOWN", body)
        self.assertIn("Get-Content", body)

    def test_C4b_json_that_is_not_an_object_is_UNKNOWN(self):
        """`suitelock.read` hands a list straight back and every `.get`
        downstream would raise. A page that 500s is also not FREE, but it is
        not an answer either."""
        for text in ("[1, 2, 3]", '"a string"', "17"):
            with self.subTest(text=text):
                self.write_raw(text)
                row = self.row()
                self.assertEqual(lanes.LOCK_UNKNOWN, row["state"])
                self.assertIn("not as an object", row["why"])

    def test_C4c_json_null_is_UNKNOWN_rather_than_absent(self):
        """`json.load` of `null` returns None, which is exactly what
        `suitelock.read` returns for a MISSING file. The listing is what
        tells those apart."""
        self.write_raw("null")
        row = self.row()
        self.assertEqual(lanes.LOCK_UNKNOWN, row["state"])
        self.assertIn("IS in the directory listing", row["why"])

    def test_C4d_a_lock_naming_no_usable_pid_is_UNKNOWN(self):
        for pid in (None, 0, -1, "4242", True, 3.5):
            with self.subTest(pid=pid):
                self.write_lock(pid=pid)
                row = self.row(Probe(table={4242: (1, "python.exe")}))
                self.assertEqual(lanes.LOCK_UNKNOWN, row["state"],
                                 "pid %r must not produce a holder" % (pid,))
                self.assertIsNone(row["pid"])

    def test_C5_a_genuinely_free_lock_renders_FREE(self):
        """Without this the panel can only ever say "something is wrong",
        which is the same defect in the other direction."""
        row = self.row()
        self.assertEqual(lanes.LOCK_FREE, row["state"])
        self.assertEqual("FREE", row["state_label"])
        self.assertIsNone(row["pid"])
        self.assertIsNone(row["why"])
        body = self.rendered(row)
        self.assertIn("FREE", body)
        self.assertIn("would get the lock immediately", body)

    def test_an_unresolvable_path_is_UNKNOWN_and_guesses_nothing(self):
        """A reader that guessed a path would be reading a DIFFERENT lock
        from the one every suite takes."""
        row = self.row(file_path=None)
        # `file_path=None` lets the production resolver run; the state must
        # be a real one either way, and `path_resolved` says which happened.
        self.assertIn(row["state"], lanes.LOCK_TEXT)
        self.assertIn(row["path_resolved"], (True, False))
        if row["path_resolved"] is False:
            self.assertEqual(lanes.LOCK_UNKNOWN, row["state"])
            self.assertIn("could not be resolved", row["why"])

    def test_the_five_states_never_collapse_into_three(self):
        """Every state the reader can produce has words, and the five are
        distinct. A sixth would arrive unlabelled rather than be filed into
        whichever bucket is first."""
        self.assertEqual(5, len(lanes.LOCK_TEXT))
        labels = [label for label, _why in lanes.LOCK_TEXT.values()]
        self.assertEqual(len(labels), len(set(labels)))
        for _label, why in lanes.LOCK_TEXT.values():
            self.assertTrue(why.strip())

    def test_the_lock_vocabulary_cannot_collide_with_the_other_two(self):
        """A third glossary on the same page. The verdict and outcome ones
        already share exactly one word on purpose; this one shares none, so
        no state can be absorbed into a lane verdict."""
        self.assertEqual(set(), set(lanes.LOCK_TEXT) & set(lanes.VERDICT_TEXT))
        self.assertEqual(set(), set(lanes.LOCK_TEXT) & set(lanes.OUTCOME_TEXT))
        for key in lanes.LOCK_TEXT:
            self.assertTrue(key.startswith("lock_"), key)

    def test_every_state_the_page_can_meet_has_a_colour(self):
        for key in lanes.LOCK_TEXT:
            self.assertIn(key, pages.LOCK_KIND,
                          "%s would render with the fallback colour" % key)


# --------------------------------------------------------------------------
# THE WAITERS, AND WHAT THIS READER WILL NOT DO TO THEM


class TheQueueIsCountedAndNeverPruned(unittest.TestCase, Lock):
    """`suitelock._live_tickets` is the obvious reader and is refused."""

    setUp = Lock.setUp

    def test_live_and_dead_tickets_are_counted_apart(self):
        self.write_lock(pid=4242)
        self.ticket(5555, "00000001760000001.000000")
        self.ticket(6666, "00000001760000002.000000")
        row = self.row(Probe(table={4242: (1, "p.exe"), 5555: (1, "p.exe")}))
        waiters = row["waiters"]
        self.assertEqual(lanes.PRESENT, waiters["state"])
        self.assertEqual(1, waiters["alive_count"])
        self.assertEqual(1, waiters["dead_count"])
        self.assertIn("1 dead ticket(s)", self.rendered(row))

    def test_an_unreadable_table_makes_every_waiter_UNKNOWN_not_zero(self):
        self.write_lock(pid=4242)
        self.ticket(5555)
        row = self.row(Probe(readable=False))
        self.assertEqual(1, row["waiters"]["unknown_count"])
        self.assertEqual(0, row["waiters"]["alive_count"])

    def test_a_missing_queue_directory_is_a_measurement(self):
        """Nothing has ever waited here. That is different from a directory
        that could not be listed."""
        row = self.row()
        self.assertEqual(lanes.ABSENT, row["waiters"]["state"])
        self.assertEqual(0, row["waiters"]["alive_count"])

    def test_a_file_that_is_not_a_ticket_is_counted_and_not_interpreted(self):
        self.write_lock(pid=4242)
        directory = self.lock + suitelock.QUEUE_SUFFIX
        os.makedirs(directory)
        with open(os.path.join(directory, "README.txt"), "w",
                  encoding="utf-8") as handle:
            handle.write("not ours")
        row = self.row(Probe(table={4242: (1, "p.exe")}))
        self.assertEqual(1, row["waiters"]["foreign"])
        self.assertEqual([], row["waiters"]["tickets"])


# --------------------------------------------------------------------------
# THE BOUNDARY. TWO WALKS, AND THE SHARP ONE IS THE TICKET QUEUE.


class ReadingThisPanelChangesNothingOnDisk(unittest.TestCase, Lock):
    """Read-only, measured rather than claimed."""

    setUp = Lock.setUp

    def _snapshot(self, root):
        found = {}
        for base, dirs, names in os.walk(root):
            dirs.sort()
            for name in sorted(names):
                path = os.path.join(base, name)
                with open(path, "rb") as handle:
                    found[os.path.relpath(path, root)] = hashlib.md5(
                        handle.read()).hexdigest()
        return found

    def test_the_lock_directory_and_its_ticket_queue_are_untouched(self):
        """THE SHARP ONE. `suitelock._live_tickets` unlinks a dead owner's
        ticket as it walks, and it is the obvious reader for this column. An
        instrument that prunes the thing it measures is not one, and nothing
        but this test keeps that true.
        """
        self.write_lock(pid=4242)
        dead = self.ticket(6666, "00000001760000002.000000")
        self.ticket(5555, "00000001760000001.000000")
        probe = Probe(table={4242: (1, "p.exe"), 5555: (1, "p.exe")})
        before = self._snapshot(self.home)
        for _ in range(3):
            row = self.row(probe)
            self.rendered(row)
        self.assertEqual(before, self._snapshot(self.home))
        self.assertTrue(os.path.exists(dead),
                        "the dead owner's ticket was removed. This reader "
                        "names it and removes nothing - pruning belongs to "
                        "`acquire`")
        self.assertTrue(os.path.exists(self.lock))

    def test_the_estate_queue_and_logs_folders_are_untouched(self):
        """The same walk `0110` did, over the two folders a lane owns: a
        render may not create, move, rename or rewrite a brief or a log.
        """
        root = os.path.join(self.home, "ops")
        for lane in ("webapp", "solo"):
            os.makedirs(os.path.join(root, "queue", lane, "RUNNING"))
            os.makedirs(os.path.join(root, "queue", lane, "DONE"))
            with open(os.path.join(root, "queue", lane, "0001.md"), "w",
                      encoding="utf-8") as handle:
                handle.write("# a brief\n")
        os.makedirs(os.path.join(root, "logs"))
        with open(os.path.join(root, "logs", "watcher-solo.log"), "w",
                  encoding="utf-8") as handle:
            handle.write("[2026-10-16 01:00:00] [solo]  START 0001.md\n")
        self.write_lock(pid=4242)
        probe = Probe(table={4242: (1, "p.exe")})

        watched = [os.path.join(root, "queue"), os.path.join(root, "logs")]
        before = [self._snapshot(path) for path in watched]
        for _ in range(3):
            data = api.lane_board(
                now=datetime.datetime(2026, 10, 16, 5, 40, 27),
                probe=probe, samples=self.samples, root=root,
                lock_path=self.lock)
            pages.lane_board(data)
        self.assertEqual(before, [self._snapshot(path) for path in watched])
        # And the lock really was read on that path, so this is not a walk
        # over a render that never looked.
        self.assertEqual(4242, data["locks"]["rows"][0]["pid"])

    def test_it_opens_no_socket(self):
        self.write_lock(pid=4242)
        original = socket.socket

        def refuse(*_a, **_k):
            raise AssertionError("the lock reader opened a socket")

        socket.socket = refuse
        try:
            self.row(Probe(table={4242: (1, "p.exe")}))
        finally:
            socket.socket = original


# --------------------------------------------------------------------------
# EVERY FIGURE HAS A SOURCE, IN EVERY STATE


class EveryLockFigureNamesItsAuthority(unittest.TestCase, Lock):
    """An unregistered figure renders UNKNOWN, which is correct and is not a
    resting state. Checked in every state, because HELD produces keys FREE
    does not."""

    setUp = Lock.setUp

    def _covered(self, row):
        paths = lp.paths_of({"locks": {
            "at": None, "table_read": True, "rows": [row], "held": 0,
            "free": 0, "orphan": 0, "held_unknown": 0, "unknown": 0,
            "glossary": [{"state": "x", "label": "y", "why": "z"}]}},
            "lane_board")
        return lp.table(paths)

    def test_every_figure_in_every_lock_state_has_a_provenance_row(self):
        probe = Probe(table={4242: (1, "p.exe")}, cpu={4242: 12.0})
        cases = {}
        self.write_lock(pid=4242)
        cases["held"] = self.row(probe)
        cases["held_twice"] = self.row(probe)
        cases["orphan"] = self.row(Probe(table={1: ("x", "o.exe")}))
        cases["held_unknown"] = self.row(Probe(readable=False))
        self.write_raw("{broken")
        cases["damaged"] = self.row(probe)
        os.unlink(self.lock)
        cases["free"] = self.row(probe)
        for name, row in cases.items():
            with self.subTest(state=name):
                found = self._covered(row)
                self.assertEqual(
                    [], [r["path"] for r in found["rows"]
                         if r["state"] == "unknown"],
                    "%s renders figure(s) with no provenance row" % name)
                self.assertEqual(0, found["uncovered"])

    def test_the_three_lock_authorities_are_registered_apart(self):
        """The bytes, the listing and the ticket directory are three
        authorities with three failure modes. Merging the first two is the
        defect: only a LISTING can prove a lock free."""
        for key in (lp.S_SUITE_LOCK, lp.S_LOCK_DIR_LISTING, lp.S_LOCK_QUEUE):
            self.assertIn(key, lp.SOURCES)
            self.assertTrue(lp.SOURCES[key]["why"].strip())
            self.assertTrue(lp.SOURCES[key]["can_be_false"],
                            "%s is a file or a listing and can be stale" % key)
        self.assertEqual(
            lp.S_LOCK_DIR_LISTING,
            lp.figure_for("lane_board.locks.rows[].state")["source"],
            "the lock's STATE must be charged to the listing: FREE is the "
            "one state only a listing can prove")
        self.assertEqual(
            lp.S_PROCESS_TABLE,
            lp.figure_for("lane_board.locks.rows[].alive")["source"])
        self.assertEqual(
            lp.S_SUITE_LOCK,
            lp.figure_for("lane_board.locks.rows[].pid")["source"])


# --------------------------------------------------------------------------
# AND IT IS NOT HIDDEN BY AN UNRELATED ABSENCE


class ThePanelSurvivesAnUnconfiguredEstate(unittest.TestCase, Lock):
    """The lock is a fact about the MACHINE. A lock panel that vanished
    because `LANE_OPS_DIR` was unset would be one more invisible state - and
    this page exists because of one."""

    setUp = Lock.setUp

    def test_an_unconfigured_estate_still_renders_the_lock(self):
        self.write_lock(pid=4242)
        probe = Probe(table={4242: (1, "p.exe")})
        data = api.lane_board(now=datetime.datetime(2026, 10, 16, 5, 40, 27),
                              probe=probe, samples=self.samples, root=None,
                              lock_path=self.lock)
        self.assertEqual(lanes.UNCONFIGURED, data["state"])
        self.assertEqual(4242, data["locks"]["rows"][0]["pid"])
        body = pages.lane_board(data)
        self.assertIn("The machine-wide suite lock", body)
        self.assertIn("HELD", body)

    def test_a_payload_with_no_lock_reading_says_UNKNOWN_not_free(self):
        """Absence of the whole block is not an empty board.

        The FREE claim is a rendered TAG, and that is what is asserted on -
        the panel's own sentence contains the word "FREE" while denying it,
        so a substring match here would read as a pass for the wrong reason
        and then fail when somebody rewrote the sentence.
        """
        body = pages.lane_locks({})
        self.assertIn("UNKNOWN", body)
        self.assertNotIn(">FREE<", body)
        self.assertIn("is UNKNOWN", body)


if __name__ == "__main__":                                 # pragma: no cover
    unittest.main()
