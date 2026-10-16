"""`suitelock.status()`: is this lock REAL, and if so how much longer?

MEASURED 2026-10-15 (qwen TASK 0150). The suite lock was HELD for 82.4% of the
day and **60.5% of that by a process that no longer existed** - 659 minutes in
total, one dead holder sitting there for 402 of them.

That costs a lane calling `acquire()` nothing: the stale takeover self-heals in
one poll, and six runs did exactly that the same day. It is a MISINFORMATION
cost, and it is paid only by a lane that reads `work/suite.lock` and decides by
hand - which is what `webapp` and `suppression` were told to do. `webapp/0040`
wrote `SUITE: NOT OBTAINED` at ~23:52 against a holder that released at
23:55:33, with 38 minutes of its own budget left.

So returning the file's contents is not an answer. The file is the authority on
who CLAIMED the lock and no authority at all on whether anything is running,
which is invariant 0: reality is not evidence about reality.

THE THREE STATES THESE TESTS COVER, each with its own way of going wrong:

    a live holder       must be WAIT, with its remaining budget or an explicit
                        UNKNOWN - never an invented number
    a dead holder       must be STALE and say so in the one field a hurried
                        reader looks at, not HELD
    a malformed file    must be UNKNOWN and never FREE. Absence of a readable
                        authority is a refusal.

And one property that is not a state: `status()` WRITES NOTHING. A reader that
prunes the queue it is reporting on is not a reader.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

from src import lanedeadline, suitelock


def lockfile():
    return os.path.join(tempfile.mkdtemp(), "work", "suite.lock")


def write(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        if isinstance(payload, str):
            handle.write(payload)
        else:
            json.dump(payload, handle)
    return path


class AFreeLockSaysSo(unittest.TestCase):

    def test_no_file_is_FREE_and_acquire_would_take_it(self):
        report = suitelock.status(lockfile())
        self.assertEqual("FREE", report["state"])
        self.assertEqual("TAKE_IT", report["would_acquire"])
        self.assertFalse(report["exists"])
        self.assertIsNone(report["holder"])
        self.assertEqual("NO_HOLDER", report["liveness"])


class ALiveHolderIsReportedAsHeldWithWhatIsKnownAboutIt(unittest.TestCase):

    def test_a_live_holder_is_HELD_and_acquire_would_wait(self):
        path = write(lockfile(), {"pid": os.getpid(), "branch": "mine",
                                  "started_at": "2026-10-16T01:00:00"})
        report = suitelock.status(path)
        self.assertEqual("HELD", report["state"])
        self.assertEqual("ALIVE", report["liveness"])
        self.assertEqual("WAIT", report["would_acquire"])
        self.assertEqual("mine", report["branch"])

    def test_held_since_and_held_for_are_both_reported(self):
        """`started_at` alone is a timestamp a reader has to subtract by hand,
        and 0150 found a lane doing that subtraction wrong by six minutes in its
        own record."""
        import datetime
        started = datetime.datetime.now() - datetime.timedelta(minutes=37)
        path = write(lockfile(),
                     {"pid": os.getpid(), "branch": "mine",
                      "started_at": started.strftime("%Y-%m-%dT%H:%M:%S")})
        report = suitelock.status(path)
        self.assertEqual(started.strftime("%Y-%m-%dT%H:%M:%S"),
                         report["held_since"])
        self.assertAlmostEqual(37.0, report["held_minutes"], places=1)

    def test_an_unreadable_started_at_is_UNKNOWN_not_a_duration(self):
        """A wrong duration is worse than a missing one."""
        path = write(lockfile(), {"pid": os.getpid(), "started_at": "T01"})
        self.assertIsNone(suitelock.status(path)["held_minutes"])

    def test_a_live_holder_with_a_deadline_reports_how_much_longer(self):
        """The question `webapp/0040` had and could not answer. 38 minutes."""
        import datetime
        end = lanedeadline.now() + datetime.timedelta(minutes=38)
        path = write(lockfile(),
                     {"pid": os.getpid(), "branch": "mine",
                      "started_at": "2026-10-16T01:00:00",
                      "lane_deadline": end.isoformat(timespec="seconds")})
        report = suitelock.status(path)
        self.assertAlmostEqual(38.0, report["remaining_minutes"], places=1)
        self.assertIn("38.0", report["remaining"])

    def test_a_live_holder_without_a_deadline_reports_UNKNOWN(self):
        """THE CONTROL FOR THE FIELD ABOVE. Every holder written before this
        field existed has no deadline, and the honest answer for those is
        UNKNOWN - never zero, and never a number derived from something else."""
        path = write(lockfile(), {"pid": os.getpid(), "branch": "mine",
                                  "started_at": "2026-10-16T01:00:00"})
        report = suitelock.status(path)
        self.assertIsNone(report["remaining_minutes"])
        self.assertEqual("UNKNOWN", report["remaining"])

    def test_an_unparseable_deadline_is_UNKNOWN_rather_than_believed(self):
        path = write(lockfile(), {"pid": os.getpid(),
                                  "lane_deadline": "150 minutes"})
        report = suitelock.status(path)
        self.assertIsNone(report["remaining_minutes"])
        self.assertEqual("UNKNOWN", report["remaining"])

    def test_acquire_records_the_deadline_so_status_can_read_it(self):
        """The two halves of this change meet here: the watcher publishes
        `LANE_DEADLINE`, `acquire` copies it into the lock, and a WAITING lane
        can then answer "how much longer" from the lock alone. A field nothing
        writes is this repository's named recurring defect."""
        import datetime
        end = lanedeadline.now() + datetime.timedelta(minutes=55)
        path = lockfile()
        with mock.patch.dict(
                os.environ,
                {lanedeadline.ENV_VAR: end.isoformat(timespec="seconds")}):
            mine = suitelock.acquire(branch="x", timeout=5, file_path=path,
                                     poll=0.01, say=lambda *_: None)
        self.addCleanup(suitelock.release, path)
        self.assertEqual(end.isoformat(timespec="seconds"),
                         mine["lane_deadline"])
        self.assertAlmostEqual(55.0, suitelock.status(path)["remaining_minutes"],
                               places=1)

    def test_a_holder_outside_a_lane_records_no_deadline_and_still_works(self):
        """The control: the operator's own shell has no `LANE_DEADLINE`, and the
        lock must still be takeable, writable and readable there."""
        path = lockfile()
        env = {k: v for k, v in os.environ.items()
               if k != lanedeadline.ENV_VAR}
        with mock.patch.dict(os.environ, env, clear=True):
            mine = suitelock.acquire(branch="x", timeout=5, file_path=path,
                                     poll=0.01, say=lambda *_: None)
        self.addCleanup(suitelock.release, path)
        self.assertIsNone(mine["lane_deadline"])
        self.assertEqual("HELD", suitelock.status(path)["state"])


class ADeadHolderIsNotReportedAsHolding(unittest.TestCase):
    """The 659 minutes. A hurried reader looks at ONE field, so that field has
    to be the one that is not misleading."""

    def test_a_dead_holder_is_STALE_and_not_HELD(self):
        path = write(lockfile(), {"pid": 999999999, "branch": "died-mid-suite",
                                  "started_at": "2026-10-15T04:06:55"})
        report = suitelock.status(path)
        self.assertEqual("STALE", report["state"])
        self.assertNotEqual("HELD", report["state"])
        self.assertEqual("DEAD", report["liveness"])
        self.assertEqual("TAKE_OVER_STALE", report["would_acquire"])

    def test_the_dead_holder_is_still_named_rather_than_hidden(self):
        """A takeover must be attributable. 0150 had to reconstruct who held the
        lock for 402 minutes from prose in other lanes' records."""
        path = write(lockfile(), {"pid": 999999999, "branch": "died-mid-suite",
                                  "worktree": "C:\\somewhere",
                                  "started_at": "2026-10-15T04:06:55"})
        report = suitelock.status(path)
        self.assertEqual(999999999, report["pid"])
        self.assertEqual("died-mid-suite", report["branch"])
        self.assertEqual("C:\\somewhere", report["worktree"])
        self.assertIn("999999999", report["explain"])

    def test_a_dead_holder_claims_no_remaining_budget(self):
        path = write(lockfile(), {"pid": 999999999,
                                  "lane_deadline": "2099-01-01T00:00:00+02:00"})
        report = suitelock.status(path)
        self.assertIsNone(report["remaining_minutes"],
                          "a dead holder's deadline is not a remaining budget")
        self.assertEqual("UNKNOWN", report["remaining"])


class AMalformedLockIsUnknownAndNeverFree(unittest.TestCase):
    """Fail-closed. An unreadable authority is a refusal, never a pass."""

    def test_bytes_that_are_not_json_are_UNKNOWN(self):
        path = write(lockfile(), "this is not json")
        report = suitelock.status(path)
        self.assertEqual("UNKNOWN", report["state"])
        self.assertNotEqual("FREE", report["state"])
        self.assertTrue(report["damaged"])
        self.assertTrue(report["exists"])

    def test_an_empty_file_is_UNKNOWN(self):
        """The window the atomic publish exists to close: `O_CREAT|O_EXCL` plus
        a separate write leaves the lock briefly EMPTY, and an empty lock read
        as free is how a live holder's lock was stolen on 2026-10-02."""
        report = suitelock.status(write(lockfile(), ""))
        self.assertEqual("UNKNOWN", report["state"])
        self.assertEqual("WAIT", report["would_acquire"],
                         "inside DAMAGED_GRACE it is not takeable either")

    def test_valid_json_that_is_not_an_object_is_UNKNOWN_and_does_not_crash(self):
        """`[]`, `"x"` and `3` all parse. `read()` hands them straight back, so
        anything calling `.get` on the result raises - which is a latent defect
        in `acquire`, named in the explain line rather than quietly swallowed."""
        for blob in ("[]", '"x"', "3"):
            report = suitelock.status(write(lockfile(), blob))
            self.assertEqual("UNKNOWN", report["state"], blob)
            self.assertEqual("UNKNOWN", report["would_acquire"], blob)
            self.assertEqual("UNKNOWN", report["liveness"], blob)
            self.assertIn("AttributeError", report["explain"], blob)

    def test_a_malformed_lock_never_claims_a_remaining_budget(self):
        report = suitelock.status(write(lockfile(), "{"))
        self.assertIsNone(report["remaining_minutes"])
        self.assertEqual("UNKNOWN", report["remaining"])


class LivenessIsAnEvidenceClassAndTheReaderChecksItself(unittest.TestCase):

    def test_three_states_and_unknown_is_not_dead(self):
        self.assertEqual("ALIVE", suitelock._liveness(os.getpid()))
        self.assertEqual("DEAD", suitelock._liveness(999999999))
        self.assertEqual("UNKNOWN", suitelock._liveness("not-a-pid"))
        self.assertEqual("UNKNOWN", suitelock._liveness(None))

    def test_a_reader_that_cannot_see_itself_reports_UNKNOWN_not_DEAD(self):
        """`CLAUDE.md`, measured: `tasklist` typed into the bash tool returns
        zero rows for EVERY query, so a live pid reads as GONE. A reader in that
        state must not report a holder dead - it must report that it cannot
        tell, and it establishes that by looking for itself first."""
        with mock.patch.object(suitelock, "_liveness",
                               lambda pid: "DEAD"):
            report = suitelock.status(
                write(lockfile(), {"pid": os.getpid(), "branch": "mine"}))
        self.assertFalse(report["reader_self_check"])
        self.assertEqual("UNKNOWN", report["liveness"])
        self.assertIn("could not even see this process",
                      report["liveness_evidence"])

    def test_a_working_reader_records_that_it_checked(self):
        report = suitelock.status(
            write(lockfile(), {"pid": os.getpid(), "branch": "mine"}))
        self.assertTrue(report["reader_self_check"])
        self.assertEqual("ALIVE", report["liveness"])


class WhatAcquireWouldDoHasOneAuthority(unittest.TestCase):
    """There is no second decision path. `status` asks `_takeable` - the
    function `acquire` itself calls - so the report cannot drift from the
    behaviour, which is how a status tool becomes the next thing that
    misinforms a lane."""

    def test_would_acquire_follows_takeable_and_not_liveness(self):
        path = write(lockfile(), {"pid": os.getpid(), "branch": "mine"})
        with mock.patch.object(suitelock, "_takeable", lambda *a: True):
            report = suitelock.status(path)
        self.assertEqual("TAKE_OVER_STALE", report["would_acquire"])
        self.assertEqual("ALIVE", report["liveness"],
                         "liveness reports; it does not decide")

    def test_the_disagreement_is_shown_rather_than_resolved(self):
        """A pid that cannot be parsed is UNKNOWN to the reporter and not-alive
        to `_alive`, so `liveness=UNKNOWN` can sit beside
        `would_acquire=TAKE_OVER_STALE`. That pair is the D6 defect made
        visible; smoothing it over would hide the one thing worth seeing."""
        report = suitelock.status(write(lockfile(), {"pid": "nonsense"}))
        self.assertEqual("UNKNOWN", report["liveness"])
        self.assertEqual("TAKE_OVER_STALE", report["would_acquire"])
        self.assertEqual("STALE", report["state"])


class StatusWritesNothing(unittest.TestCase):
    """D5's condition, and it is not decoration: `_live_tickets` deletes a dead
    waiter's ticket as it walks, which is right for `acquire` and wrong for a
    read. A reader that changes what it reports on cannot be trusted twice."""

    def snapshot(self, root):
        out = {}
        for base, _, names in os.walk(root):
            for name in names:
                full = os.path.join(base, name)
                out[full] = os.path.getsize(full)
        return out

    def test_a_dead_waiters_ticket_survives_a_status_read(self):
        path = write(lockfile(), {"pid": os.getpid(), "branch": "mine"})
        queue = suitelock._queue_dir(path)
        os.makedirs(queue, exist_ok=True)
        ticket = os.path.join(queue, suitelock._ticket_name(pid=999999999))
        write(ticket, {"pid": 999999999})
        root = os.path.dirname(os.path.dirname(path))
        before = self.snapshot(root)
        suitelock.status(path)
        self.assertEqual(before, self.snapshot(root))
        self.assertTrue(os.path.exists(ticket),
                        "status must not prune the queue it reports on")

    def test_a_dead_waiter_is_not_counted_in_the_queue_depth(self):
        path = write(lockfile(), {"pid": os.getpid(), "branch": "mine"})
        queue = suitelock._queue_dir(path)
        os.makedirs(queue, exist_ok=True)
        write(os.path.join(queue, suitelock._ticket_name(pid=999999999)),
              {"pid": 999999999})
        self.assertEqual(0, suitelock.status(path)["queue_depth"])
        write(os.path.join(queue, suitelock._ticket_name(pid=os.getpid())),
              {"pid": os.getpid()})
        self.assertEqual(1, suitelock.status(path)["queue_depth"])

    def test_reading_a_free_lock_creates_no_lock_file(self):
        path = lockfile()
        suitelock.status(path)
        self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
