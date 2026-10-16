#!/usr/bin/env python3
"""The STOP-SENDING brake fails closed when it cannot be read - TASK 0210.

PROPERTY UNDER TEST (the second of four, tested alone):

    Fail-closed on unreadable. If the check cannot determine whether the
    file exists - permissions, I/O error, anything - it refuses to send.

The distinction that matters is between THREE states, not two:

    absent            the operator has not pulled the brake -> send
    present           the operator has pulled it -> refuse
    UNREADABLE        the brake state is UNKNOWN -> refuse

`os.path.exists` collapses the third state into the first: it answers
False for a path it cannot stat, which is how an unreadable brake becomes
permission to send in one function. `haltfile.require_released` uses
`os.lstat` and treats every unreadable outcome as UNKNOWN, and UNKNOWN
refuses - the same law the estate runs on everywhere else (invariant 0:
an unreadable authority means UNKNOWN, which never becomes PASS, zero,
idle, complete or safe).

THE WINDOWS MAPPING, measured 2026-10-15: `lstat` of a path whose parent
is a file does NOT raise NotADirectoryError on this platform - it raises
FileNotFoundError carrying winerror 3 (ERROR_PATH_NOT_FOUND), the same
exception class Python gives a genuinely missing leaf (winerror 2). The
first draft of `haltfile` therefore read parent-is-a-file as ABSENT and
this module caught it: two tests failed on a real defect, not on a
fixture. The module now splits FileNotFoundError on winerror - 3 is a
component the path could not resolve, which is a brake state it cannot
determine, so it refuses; 2 is a missing leaf, which is absence. On
POSIX the same case arrives as NotADirectoryError, an OSError, and
refuses through the general branch without any split.

Two ways an unreadable state is produced here, on purpose:

    REAL    a path whose PARENT IS A FILE, no mocking at all - the
            operating system answers for itself, whatever exception it
            actually raises on this platform, and the assertion is on
            the refusal, not on the exception class.

    MOCKED  `os.lstat` patched to raise PermissionError. The parent-is-a-
            file trick cannot produce a permission error on demand, so
            that class of unreadable is injected at the one seam the
            module owns.

And the refusal is asserted AT THE DOOR, not only at the function: with
the brake state unknown, `providerwrites.perform` must raise OperatorStop
with the transport unreached - a check that fails closed in isolation but
not in the write path would be a brake that only works in its unit tests.
The door test uses `heyreach.create_list` (LINKEDIN_CREATE_LIST), not a
pause: the four REPEATABLE stops are EXEMPT from the brake at the door,
so a pause can never test this branch - the first draft used one and
proved nothing.

NO TEST CREATES OR STATTS THE REAL FILE. The path constant is patched to
a throwaway for every test.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import haltfile, providerwrites
from src.providers import bison                      # noqa: F401 (tripwire)
from tests.campaignbase import CampaignTest

CAMP = "camp-stop-unreadable"


class _UnreadableBrakeBase:
    """A base that builds an unreadable brake path and nothing else."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-brake-unreadable-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # A FILE at `blocker`, so any child path under it is unreadable in
        # the way that matters: lstat cannot even ask whether it exists.
        self.blocker = os.path.join(self.tmp, "blocker")
        with open(self.blocker, "wb") as handle:
            handle.write(b"")
        self.unreadable = os.path.join(self.blocker, "STOP-SENDING")


class AtTheFunction(_UnreadableBrakeBase, unittest.TestCase):

    def test_a_path_it_cannot_stat_refuses_rather_than_sends(self):
        """REAL NotADirectoryError, no mocks: the parent is a file."""
        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.unreadable), \
                self.assertRaises(haltfile.OperatorStop) as raised:
            haltfile.require_released()
        text = str(raised.exception)
        self.assertIn("UNKNOWN", text)
        self.assertIn("refuses", text)
        self.assertIn(self.unreadable, text,
                      "the refusal names the path, so the operator reads "
                      "which brake is unreadable")

    def test_a_permission_error_on_lstat_refuses_rather_than_sends(self):
        """MOCKED PermissionError at the one seam the module owns."""
        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.unreadable), \
                mock.patch.object(
                    haltfile.os, "lstat",
                    side_effect=PermissionError(
                        13, "Permission denied")), \
                self.assertRaises(haltfile.OperatorStop) as raised:
            haltfile.require_released()
        self.assertIn("UNKNOWN", str(raised.exception))

    def test_any_os_error_refuses_not_only_the_two_we_thought_of(self):
        """The contract is ANY unreadable state, so an OSError nobody
        predicted must refuse too. Pinning only NotADirectoryError and
        PermissionError would re-derive the exists() defect one error
        class at a time."""
        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.unreadable), \
                mock.patch.object(
                    haltfile.os, "lstat",
                    side_effect=OSError(121, "The semaphore timeout period "
                                            "has expired")), \
                self.assertRaises(haltfile.OperatorStop):
            haltfile.require_released()

    def test_absent_still_sends_and_present_still_refuses(self):
        """The two readable states bracket the unreadable one: fail-closed
        must not become fail-always. Absent at a readable temp path returns
        None; a real file at that path raises the operator's refusal."""
        released = os.path.join(self.tmp, "STOP-SENDING")
        with mock.patch.object(haltfile, "STOP_SENDING_PATH", released):
            self.assertIsNone(haltfile.require_released())
        with open(released, "wb") as handle:
            handle.write(b"")
        with mock.patch.object(haltfile, "STOP_SENDING_PATH", released), \
                self.assertRaises(haltfile.OperatorStop) as raised:
            haltfile.require_released()
        self.assertIn("STOP-SENDING is present", str(raised.exception))
        self.assertNotIn("UNKNOWN", str(raised.exception),
                         "a readable, present brake is the operator's "
                         "refusal, not an unknown state")


class AtTheWriteDoor(_UnreadableBrakeBase, CampaignTest):

    def test_an_unreadable_brake_refuses_the_transport(self):
        """The unreadable state asserted where it counts: inside
        `providerwrites.perform`, before the transport. The real
        unreadable path - no mocked lstat - so the door is exercised
        against the operating system. `heyreach.create_list` because the
        REPEATABLE stops are brake-exempt and can never reach this
        branch."""
        recs = self.seed_records()
        self.make_campaign(recs, campaign_id=CAMP)

        reached = []
        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.unreadable), \
                self.assertRaises(haltfile.OperatorStop) as raised:
            providerwrites.perform(
                providerwrites.LINKEDIN_CREATE_LIST,
                campaign=CAMP,
                payload={"name": "unreadable-brake-list"},
                transport=lambda payload: reached.append(payload),
                readback=lambda: {"campaignIds": []},
                expected={"campaignIds": []})

        self.assertEqual(reached, [],
                         "the brake state was UNKNOWN and the transport "
                         "fired anyway")
        self.assertIn("UNKNOWN", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
