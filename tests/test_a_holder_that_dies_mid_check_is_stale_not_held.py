#!/usr/bin/env python3
"""A holder that dies MID-CHECK is STALE, not held - the missing L323 witness.

THE GAP THIS CLOSES. canary/0130, finding 1, measured on the 483-line test
blob `2ac8a921` of branch `task-suppression-0399-lock-identity-2026-10-16`:
grep for "stronger witness" and for "disagreed" returns 0 hits over the whole
file. The GONE-after-alive return in `holder_state` (L322-325 of identity
blob `ea0dbdd8`; the return statement starts at L323) - where `_alive` says
the pid is running, `process_identity` says GONE, and "the identity reader
is the stronger witness" - is reachable in production whenever a holder dies
between the two reads, and it had only ever been produced by a 57-attempt
timing race, never by a test.

DETERMINISTIC SHAPE. This test PLANTS both readers: `_alive` -> True (the
tasklist snapshot still lists a pid that has already exited - that is the
race window, frozen) and `process_identity` -> ("GONE", <start stamp>,
"exited with code 0") (the real handle-outlives-the-process GONE shape,
measured 2026-10-16). No timing loop, no real process lookup, no race to
win. Both plants carry a marker attribute and are witnessed by name, because
a plant that lands nowhere reads as a dead row. Cleanup restores the
originals.

NO LOCK IN THIS MODULE IS THE REAL ONE. Every call passes an explicit
`file_path` inside a private temp directory; `path()` is never invoked, so
the live machine lock is never read or stat'd. The pid and its start stamp
are synthetic bytes, and the planted readers mean no fixture ever asks the
OS about a process.

BORN-RED CONTROL. The same file, byte-for-byte, runs against both
`src/suitelock.py` blobs:

* master blob `12de2433` (of `b1f290c84`): no verdict vocabulary exists -
  `_takeable` consults bare `_alive` (L246 there), so with `_alive` planted
  True it answers not-takeable - "held" - for the whole window. The verdict
  assertion below fails with observed 'held'. That failure is the point:
  this is a regression test born red against the pre-fix blob.
* identity blob `ea0dbdd8` (of `c85724df0`): `holder_state` reaches the
  GONE branch and answers STALE with the stronger-witness reason. Green.

CHERRY-PICK NOTE. Standalone by construction - stdlib plus `src.suitelock`
and nothing else - so it drops into the identity branch unchanged and runs
module-scoped (`py -3 tests/test_a_holder_that_dies_mid_check_is_stale_not_held.py -v`)
or under discovery like every other file in `tests/`.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import suitelock                                      # noqa: E402

#: The synthetic holder. The pid is shaped like a Windows pid (a multiple of
#: 4) but is never looked up: both readers are planted. The start stamp is
#: shaped like a creation FILETIME (100ns ticks since 1601) and is synthetic;
#: the GONE branch never compares it, it only has to be present and plausible.
SYNTHETIC_PID = 424244
SYNTHETIC_CREATED = 130000000000000000
GONE_DETAIL = "exited with code 0"
WITNESS_PHRASE = "stronger witness"
PLANT_MARK = "_l323_plant"


def _planted_alive(pid):
    """The tasklist snapshot inside the race window: the pid is still listed.

    This is not a guess about the world - it is the world at t0 of the
    measured race (canary/0130, F7): the snapshot taken first, the process
    gone by the second read.
    """
    return True


def _planted_identity(pid):
    """The identity reader one beat later: the process HAS exited.

    The shape mirrors the real handle-outlives-the-process answer recorded in
    the identity blob's own `_identity_nt` comment and observed twice by
    canary/0130 (F4, F7): OpenProcess still succeeds on the open handle, the
    exit-code check refuses to call the corpse ALIVE, and the answer is GONE
    with the exit code as its detail - not the ERROR_INVALID_PARAMETER (87)
    answer OpenProcess gives for a number nothing holds.
    """
    return ("GONE", SYNTHETIC_CREATED, GONE_DETAIL)


_planted_alive._l323_plant = True
_planted_identity._l323_plant = True


class AHolderThatDiesMidCheck(unittest.TestCase):
    """One frozen window: `_alive` says alive, the identity reader says GONE."""

    def setUp(self):
        self.scratch = tempfile.mkdtemp(prefix="rga-l323-")
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)
        self.lock_path = os.path.join(self.scratch, "suite.lock")
        payload = {"pid": SYNTHETIC_PID, "pid_created": SYNTHETIC_CREATED}
        with open(self.lock_path, "wb") as handle:
            handle.write(json.dumps(payload, sort_keys=True).encode("utf-8"))
        self._orig_alive = suitelock._alive
        self._orig_identity = getattr(suitelock, "process_identity", None)
        suitelock._alive = _planted_alive
        if self._orig_identity is not None:
            # Only a blob that HAS the identity reader gets it planted; on a
            # pre-0399 blob the absence of the reader is the defect under test
            # and must not be papered over with an attribute it never had.
            suitelock.process_identity = _planted_identity
        self.addCleanup(self._restore)

    def _restore(self):
        suitelock._alive = self._orig_alive
        if self._orig_identity is not None:
            suitelock.process_identity = self._orig_identity

    def _verdict(self, holder):
        """`(state, reason)` in the blob's own vocabulary.

        An identity blob answers through `holder_state` directly. A pre-0399
        blob has no verdict vocabulary, so its binary `_takeable` is
        translated: takeable is 'stale', not-takeable is 'held' - the answer
        a waiter behind that lock actually receives.
        """
        if hasattr(suitelock, "holder_state"):
            return suitelock.holder_state(holder, self.lock_path)
        takeable = suitelock._takeable(self.lock_path, holder)
        return (("stale" if takeable else "held"),
                "(no verdict vocabulary in this blob; derived from "
                "_takeable=%r)" % (takeable,))

    def test_the_plants_land_where_the_readers_are(self):
        """Witness the plants by identity and marker, not by behaviour."""
        self.assertIs(suitelock._alive, _planted_alive)
        self.assertTrue(getattr(suitelock._alive, PLANT_MARK, False))
        if hasattr(suitelock, "holder_state"):
            self.assertIs(suitelock.process_identity, _planted_identity)
            self.assertTrue(getattr(suitelock.process_identity,
                                    PLANT_MARK, False))
        else:
            self.assertFalse(hasattr(suitelock, "process_identity"),
                             "a blob with no holder_state must have no "
                             "identity reader either")

    def test_a_holder_that_dies_mid_check_is_stale_not_held(self):
        holder = suitelock.read(self.lock_path)
        self.assertEqual(holder.get("pid"), SYNTHETIC_PID,
                         "the fixture must round-trip through read()")
        state, reason = self._verdict(holder)
        expected = getattr(suitelock, "STALE", "stale")
        self.assertEqual(
            state, expected,
            "a holder whose pid exited between the two readers must answer "
            "STALE - the identity reader is the stronger witness - but this "
            "blob answered %r. reason: %s" % (state, reason))
        # The three assertions below pin WHICH return produced the STALE:
        # the phrase is unique to the GONE branch, the detail is the planted
        # one, and the plain dead-pid return says "is not running".
        self.assertIn(WITNESS_PHRASE, reason,
                      "the STALE must come from the GONE branch whose reason "
                      "names the disagreement, not from another return: %s"
                      % reason)
        self.assertIn(GONE_DETAIL, reason)
        self.assertNotIn("is not running", reason,
                         "the plain dead-pid return fired, not the mid-check "
                         "window: %s" % reason)
        self.assertTrue(suitelock._takeable(self.lock_path, holder),
                        "STALE is the only takeable verdict")


if __name__ == "__main__":
    unittest.main()
