#!/usr/bin/env python3
"""The suite lock's holder is a PROCESS, not a number - TASK 0399.

`_alive` is correct about a PID and a PID is not an identity. Windows
recycles process ids, so the number written into the lock can be handed to
an unrelated process at any moment. `suppression/0395` measured both
answers for one number four minutes apart: 79548 read dead, then read alive,
because it had been recycled onto one of its own shell's transient
processes.

BOTH DIRECTIONS ARE WRONG, and the first one blocks the whole estate:

* a DEAD holder whose number has been reused reads `_alive` -> True ->
  "held, keep waiting", so every lane queues behind a ghost until its
  timeout. The suite is the merge gate's only instrument.
* the same coincidence in reverse lets a LIVE holder's lock be taken the
  moment a recycled process exits, and two suites then write one evidence
  path - which is how 91 of 227 names were destroyed with neither writer
  learning.

THE FIX. The lock records `pid_created`, an opaque process start stamp read
from the OS - the creation FILETIME on Windows, `/proc/<pid>/stat` field 22
on Linux - and `holder_state` has a THIRD answer. `UNIDENTIFIABLE` is never
takeable AT ANY AGE, because a legitimate run may take 150 minutes and age
is therefore evidence of nothing.

NO LOCK IN THIS MODULE IS THE REAL ONE. Every test passes an explicit
`file_path` inside a temp directory; nothing calls `path()` for real, no
suite is started, and the machine-wide lock is never acquired. The child
processes are `sleep` processes of our own, killed in cleanup.

WHAT THE FIXTURE CANNOT DO, said plainly: the OS cannot be told to reuse a
chosen PID, so the recycled-number STATE is constructed - a live pid paired
with a different real process's start stamp. That is exactly what a reader
sees after a recycle, and a reader is all this module tests.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import suitelock                                      # noqa: E402


class _Locks(unittest.TestCase):
    """A scratch directory, and live throwaway processes to point at."""

    def setUp(self):
        self.scratch = tempfile.mkdtemp(prefix="rga-0399-")
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self._children = []

    def child(self):
        """A live process of our own, killed in cleanup."""
        proc = subprocess.Popen([sys.executable, "-c",
                                 "import time; time.sleep(900)"])
        self._children.append(proc)
        self.addCleanup(self._reap, proc)
        # Give it a moment to exist before anyone asks about it. The wait
        # uses `_alive`, NOT `process_identity`: a fixture that waits on the
        # function under test cannot set up a case that breaks it.
        for _ in range(50):
            if suitelock._alive(proc.pid):
                break
            time.sleep(0.05)
        return proc

    @staticmethod
    def _reap(proc):
        try:
            proc.kill()
            proc.wait(timeout=30)
        except Exception:                                      # noqa: BLE001
            pass

    def dead_pid(self):
        """A pid that is not running, found rather than guessed.

        FOUND WITH `_alive`, NEVER WITH `process_identity`. The first
        version of this helper searched with `process_identity`, which is
        the function several of these tests exist to test - so mutation N5,
        which made a nonexistent pid read UNKNOWN instead of GONE, caused
        the helper to find nothing, call `skipTest`, and the mutation read
        as killed by nobody. A skip is not a failure and a fixture built on
        the subject cannot set up a case against it.
        """
        for candidate in range(999000, 999900, 2):
            if not suitelock._alive(candidate):
                return candidate
        self.fail("no unused pid could be found in the probe range, so this "
                  "case was never set up - that is a broken fixture, not a "
                  "skip")

    def lock(self, name, payload, age=None):
        path = os.path.join(self.scratch, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
        if age is not None:
            when = time.time() - age
            os.utime(path, (when, when))
        return path

    def holder(self, pid, created="match", branch="a-run", age=None,
               name=None):
        """A lock naming `pid`. `created` may be 'match', None, or a value."""
        if created == "match":
            created = suitelock.process_identity(pid)[1]
        payload = {"pid": pid, "branch": branch,
                   "worktree": self.scratch,
                   "queued_at": "2026-10-16T12:00:00",
                   "started_at": "2026-10-16T12:00:00"}
        if created is not None:
            payload["pid_created"] = created
        path = self.lock(name or ("h-%s.lock" % pid), payload, age=age)
        payload["lock_path"] = path
        return path, payload

    def verdict(self, path):
        held = suitelock.read(path) or {}
        return suitelock.holder_state(held, path)


# --------------------------------------------------------------------- the
# primitive, measured rather than assumed


class TheIdentityPrimitiveAnswersWhatItClaims(_Locks):
    """`process_identity` is the whole basis of the fix, so it is measured."""

    def test_this_process_is_alive_and_carries_a_start_stamp(self):
        state, created, detail = suitelock.process_identity(os.getpid())
        self.assertEqual(state, "ALIVE", detail)
        self.assertIsNotNone(created,
                             "a reader that cannot obtain a start stamp for "
                             "its OWN process cannot obtain one at all")

    def test_a_live_process_this_reader_did_not_create_also_answers(self):
        """The case the fix depends on: the holder is somebody else."""
        proc = self.child()
        state, created, detail = suitelock.process_identity(proc.pid)
        self.assertEqual(state, "ALIVE", detail)
        self.assertIsNotNone(created)

    def test_a_pid_that_does_not_exist_is_GONE_not_unknown(self):
        state, created, _detail = suitelock.process_identity(self.dead_pid())
        self.assertEqual(state, "GONE")
        self.assertIsNone(created)

    def test_the_start_stamp_does_not_move_while_the_process_lives(self):
        proc = self.child()
        first = suitelock.process_identity(proc.pid)[1]
        time.sleep(0.4)
        self.assertEqual(suitelock.process_identity(proc.pid)[1], first,
                         "an identity that drifts would make every holder "
                         "look recycled")

    def test_the_same_pid_reads_GONE_once_the_process_exits(self):
        proc = self.child()
        self.assertEqual(suitelock.process_identity(proc.pid)[0], "ALIVE")
        proc.kill()
        proc.wait(timeout=30)
        for _ in range(100):
            if suitelock.process_identity(proc.pid)[0] != "ALIVE":
                break
            time.sleep(0.05)
        self.assertEqual(suitelock.process_identity(proc.pid)[0], "GONE",
                         "a handle outlives its process and GetProcessTimes "
                         "still answers for a corpse, which is why the exit "
                         "code is consulted")

    def test_two_processes_do_not_share_an_identity(self):
        one, two = self.child(), self.child()
        self.assertNotEqual(suitelock.process_identity(one.pid)[1],
                            suitelock.process_identity(two.pid)[1],
                            "two processes of the same executable must not "
                            "be indistinguishable, or the pair identifies "
                            "nothing")

    def test_a_nonsense_pid_is_GONE_rather_than_raising(self):
        for value in (None, "", "abc", 0, -1):
            self.assertEqual(suitelock.process_identity(value)[0], "GONE",
                             "a damaged lock must not crash the reader")


# --------------------------------------------------------------------- C1


class ARecycledNumberIsNotTheHolder(_Locks):
    """C1. The defect, and the whole reason this task exists."""

    def test_a_live_pid_with_a_different_identity_is_STALE(self):
        victim, other = self.child(), self.child()
        wrong = suitelock.process_identity(other.pid)[1]
        path, _payload = self.holder(victim.pid, created=wrong)
        state, why = self.verdict(path)
        self.assertEqual(state, suitelock.STALE, why)
        self.assertTrue(suitelock._takeable(path, suitelock.read(path)))
        self.assertIn("recycled", why)

    def test_the_old_reader_called_that_same_lock_HELD(self):
        """The negative leg: `_alive` alone answers the other way.

        `_alive` is not wrong - it is answering a different question - and
        this test pins that the OLD basis of the decision really did keep
        waiting for a ghost. Without it, C1 proves only that the new reader
        says something.
        """
        victim, other = self.child(), self.child()
        wrong = suitelock.process_identity(other.pid)[1]
        path, _payload = self.holder(victim.pid, created=wrong)
        self.assertTrue(suitelock._alive(victim.pid),
                        "the recycled number IS alive; that is the trap")
        self.assertEqual(self.verdict(path)[0], suitelock.STALE)

    def test_takeable_says_yes_through_the_SHARED_api(self):
        """The one test here that is a BEHAVIOURAL red on the old code.

        Every other test in this module calls `process_identity` or
        `holder_state`, which do not exist before this change, so on the old
        source they ERROR - which says the fix is absent, not that the guard
        is. `_takeable` exists on BOTH, takes the same two arguments on
        both, and is what `acquire` actually consults. On `b1f290c84` this
        assertion FAILS, because that reader answers False for a live
        number whoever owns it.

        NOTHING in this test calls the new API - not even through the
        `child` helper, which waits on `process_identity`. The recorded
        stamp is a literal 1, which no process has, so the lock is in
        exactly the state a recycle leaves: a live number carrying an
        identity that is not its own.
        """
        victim = subprocess.Popen([sys.executable, "-c",
                                   "import time; time.sleep(900)"])
        self.addCleanup(self._reap, victim)
        time.sleep(1.0)
        self.assertTrue(suitelock._alive(victim.pid),
                        "the fixture process must be running, or this test "
                        "is vacuous")
        payload = {"pid": victim.pid, "pid_created": 1,
                   "branch": "a-run-that-died", "worktree": self.scratch,
                   "queued_at": "2026-10-16T12:00:00",
                   "started_at": "2026-10-16T12:00:00"}
        path = self.lock("shared-api.lock", payload)
        self.assertTrue(
            suitelock._takeable(path, suitelock.read(path)),
            "a lock whose recorded process is gone and whose NUMBER has "
            "been recycled onto something else must be takeable. The old "
            "reader consulted `_alive(pid)` alone and answered False, so "
            "every lane queued behind a ghost until its timeout.")

    def test_the_reason_names_both_stamps_so_a_human_can_check_it(self):
        victim, other = self.child(), self.child()
        wrong = suitelock.process_identity(other.pid)[1]
        real = suitelock.process_identity(victim.pid)[1]
        path, _payload = self.holder(victim.pid, created=wrong)
        why = self.verdict(path)[1]
        self.assertIn(str(wrong), why)
        self.assertIn(str(real), why)


# --------------------------------------------------------------------- C2


class AGenuinelyLiveHolderIsRespected(_Locks):
    """C2. An instrument that breaks every lock is worse than one that
    breaks none."""

    def test_a_matching_identity_is_HELD_and_not_takeable(self):
        proc = self.child()
        path, _payload = self.holder(proc.pid)
        state, why = self.verdict(path)
        self.assertEqual(state, suitelock.HELD, why)
        self.assertFalse(suitelock._takeable(path, suitelock.read(path)))

    def test_our_own_freshly_written_lock_is_HELD_by_us(self):
        """Through `acquire`, so the payload is the production one."""
        path = os.path.join(self.scratch, "acquired.lock")
        said = []
        payload = suitelock.acquire(branch="b", timeout=5, file_path=path,
                                    poll=0.01, say=said.append)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        self.assertEqual(payload["pid"], os.getpid())
        self.assertIsNotNone(payload["pid_created"],
                             "acquire must RECORD the identity or no reader "
                             "can ever use it")
        self.assertEqual(payload["pid_created"],
                         suitelock.process_identity(os.getpid())[1])
        self.assertEqual(self.verdict(path)[0], suitelock.HELD)

    def test_a_second_acquire_still_refuses_rather_than_running(self):
        path = os.path.join(self.scratch, "serial.lock")
        suitelock.acquire(branch="b", timeout=5, file_path=path, poll=0.01,
                          say=lambda _m: None)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        with self.assertRaises(suitelock.SuiteBusy):
            suitelock.acquire(branch="c", timeout=0.2, file_path=path,
                              poll=0.05, say=lambda _m: None)


# --------------------------------------------------------------------- C3


class DiedAtStartIsReachableAndNamed(_Locks):
    """C3. `exit_code=3221225794`, `wall_seconds=0.0`, a 0-byte log: a
    process that never reached any code that could release anything."""

    def test_a_gone_pid_is_STALE_with_the_reason_named(self):
        path, _payload = self.holder(self.dead_pid(), created=1234567890,
                                     age=5)
        state, why = self.verdict(path)
        self.assertEqual(state, suitelock.STALE, why)
        self.assertIn("not running", why,
                      "the reason must name the cause, not the age")

    def test_it_is_stale_at_five_seconds_old_so_age_is_not_the_answer(self):
        path, _payload = self.holder(self.dead_pid(), created=1, age=5)
        self.assertEqual(self.verdict(path)[0], suitelock.STALE)

    def test_a_legacy_lock_whose_pid_is_dead_is_still_recovered(self):
        """The old behaviour, deliberately kept: a machine that lost power
        mid-suite must not need a human, and a lock written before this
        change records no identity."""
        path, _payload = self.holder(self.dead_pid(), created=None, age=5)
        self.assertIsNone(suitelock.read(path).get("pid_created"))
        self.assertEqual(self.verdict(path)[0], suitelock.STALE)


# --------------------------------------------------------------------- C4


class AnUnobtainableIdentityFailsClosed(_Locks):
    """C4. If the reader cannot establish whether the holder is alive, it
    WAITS. Fail-open here means two suites writing one evidence path."""

    def _access_denied_pid(self):
        """A live pid whose identity this reader may not read.

        Measured 2026-10-16: all eight SYSTEM-owned processes probed answer
        `OpenProcess ERROR_ACCESS_DENIED (5)`. This finds one rather than
        hardcoding a number, and skips rather than passing vacuously if the
        reader turns out to be privileged.
        """
        if os.name != "nt":
            self.skipTest("the ACCESS_DENIED branch is win32-specific")
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process | Where-Object { $_.Name -in "
             "'services.exe','lsass.exe','csrss.exe','smss.exe' }).ProcessId"],
            capture_output=True, text=True, timeout=120, check=False)
        for token in (out.stdout or "").split():
            if token.isdigit():
                pid = int(token)
                if suitelock.process_identity(pid)[0] == "UNKNOWN":
                    return pid
        self.skipTest("no process with an unreadable identity was found; "
                      "this reader may be privileged")

    def test_an_unreadable_identity_is_UNIDENTIFIABLE_and_not_takeable(self):
        pid = self._access_denied_pid()
        path, _payload = self.holder(pid, created=999, age=6 * 3600)
        state, why = self.verdict(path)
        self.assertEqual(state, suitelock.UNIDENTIFIABLE, why)
        self.assertFalse(suitelock._takeable(path, suitelock.read(path)),
                         "UNIDENTIFIABLE must never be takeable; waiting "
                         "costs time, stealing costs a corrupted run")
        self.assertIn("UNKNOWN", why)

    def test_a_live_pid_with_no_recorded_identity_is_UNIDENTIFIABLE(self):
        proc = self.child()
        path, _payload = self.holder(proc.pid, created=None, age=6 * 3600)
        state, why = self.verdict(path)
        self.assertEqual(state, suitelock.UNIDENTIFIABLE, why)
        self.assertFalse(suitelock._takeable(path, suitelock.read(path)))

    def test_the_waiting_message_says_a_human_has_to_look(self):
        proc = self.child()
        path, _payload = self.holder(proc.pid, created=None,
                                     name="unident.lock")
        said = []
        with self.assertRaises(suitelock.SuiteBusy):
            suitelock.acquire(branch="b", timeout=0.2, file_path=path,
                              poll=0.05, say=said.append)
        text = "\n".join(said)
        self.assertIn(suitelock.UNIDENTIFIABLE, text)
        self.assertIn("a human has to look", text,
                      "fail-closed has a cost and the message has to name "
                      "it, or an UNIDENTIFIABLE lock silently parks the "
                      "machine")

    def test_the_refusal_carries_the_verdict_not_only_the_pid(self):
        proc = self.child()
        path, _payload = self.holder(proc.pid)
        with self.assertRaises(suitelock.SuiteBusy) as raised:
            suitelock.acquire(branch="b", timeout=0.2, file_path=path,
                              poll=0.05, say=lambda _m: None)
        self.assertIn(suitelock.HELD, str(raised.exception))

    def test_a_damaged_lock_keeps_its_grace_unchanged(self):
        """The one age-based leg there is, and it is not the holder's age -
        it is how long the CONTENT has been unreadable."""
        path = os.path.join(self.scratch, "damaged.lock")
        with open(path, "wb") as handle:
            handle.write(b"")
        fresh = time.time() - 1
        os.utime(path, (fresh, fresh))
        self.assertEqual(self.verdict(path)[0], suitelock.HELD)
        old = time.time() - (suitelock.DAMAGED_GRACE + 5)
        os.utime(path, (old, old))
        self.assertEqual(self.verdict(path)[0], suitelock.STALE)


# --------------------------------------------------------------------- C5


class AgeAloneIsNeverSufficient(_Locks):
    """C5. 89 minutes was nearly a legitimate run; a run may take 150."""

    def test_a_live_matching_holder_is_HELD_at_every_age(self):
        proc = self.child()
        for seconds in (0, 89 * 60, 150 * 60, 24 * 3600):
            path, _payload = self.holder(
                proc.pid, age=seconds, name="age-%d.lock" % seconds)
            state, why = self.verdict(path)
            self.assertEqual(state, suitelock.HELD,
                             "a %ds-old lock held by a live, matching "
                             "process was not HELD: %s" % (seconds, why))
            self.assertFalse(suitelock._takeable(path, suitelock.read(path)))

    def test_a_recycled_number_is_stale_at_ZERO_age(self):
        """The other half: staleness does not need age either."""
        victim, other = self.child(), self.child()
        wrong = suitelock.process_identity(other.pid)[1]
        path, _payload = self.holder(victim.pid, created=wrong, age=0)
        self.assertEqual(self.verdict(path)[0], suitelock.STALE)


# -------------------------------------------------------- the reader itself


class TheReaderProducesAllThreeVerdicts(_Locks):
    """A reader that can only say one thing is watching nothing."""

    def test_three_distinct_verdicts_are_reachable_in_one_run(self):
        victim, other = self.child(), self.child()
        wrong = suitelock.process_identity(other.pid)[1]
        held = self.holder(victim.pid, name="v-held.lock")[0]
        stale = self.holder(victim.pid, created=wrong,
                            name="v-stale.lock")[0]
        unident = self.holder(victim.pid, created=None,
                              name="v-unident.lock")[0]
        got = {self.verdict(p)[0] for p in (held, stale, unident)}
        self.assertEqual(got, {suitelock.HELD, suitelock.STALE,
                               suitelock.UNIDENTIFIABLE})

    def test_only_STALE_is_takeable(self):
        victim, other = self.child(), self.child()
        wrong = suitelock.process_identity(other.pid)[1]
        cases = {
            suitelock.HELD: self.holder(victim.pid, name="t-held.lock")[0],
            suitelock.STALE: self.holder(victim.pid, created=wrong,
                                         name="t-stale.lock")[0],
            suitelock.UNIDENTIFIABLE: self.holder(victim.pid, created=None,
                                                  name="t-un.lock")[0],
        }
        for state, path in cases.items():
            self.assertEqual(
                suitelock._takeable(path, suitelock.read(path)),
                state == suitelock.STALE,
                "%s must%s be takeable" % (state,
                                           "" if state == suitelock.STALE
                                           else " not"))


if __name__ == "__main__":
    unittest.main()
