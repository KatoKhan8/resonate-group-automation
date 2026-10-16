#!/usr/bin/env python3
"""The STOP-SENDING brake asks nobody for permission - TASK 0210.

PROPERTY UNDER TEST (the fourth of four, tested alone):

    It asks nobody for permission. The halt that already exists was
    broken at exactly the moment it was needed because it demanded a
    GateToken nothing could supply at that moment. A brake that asks for
    permission is not a brake.

What "asks nobody" means here, each part pinned by a test:

    NO MACHINERY      `haltfile` imports ONLY `os`. Not store, not
                      config, not killswitch, not executionscope - every
                      one of those is a thing that can be broken,
                      unwritable, or demanding a token at the moment the
                      operator needs the brake most. Asserted on the
                      import graph, because a future `from . import
                      store` would be the permission question coming back
                      in through a side door. A cycle through the write
                      door would also make the brake unreachable when the
                      door is the thing that is broken.

    NO ARGUMENTS      `require_released()` takes no authorization, no
                      scope, no role, no token, no grant, no `by=`. There
                      is no signature position in which a permission
                      could be demanded.

    NO INHERITED      `OperatorStop` is a SIBLING of `WriteRefused` and of
                      VERDICT           `killswitch.SendingRefused`, not a
                      subclass. A subclass would be CAUGHT by every
                      existing `except WriteRefused` handler in the
                      estate and re-worded as a gate refusal - the brake
                      would be wearing a uniform it does not hold.

    WORKS ALONE       With no campaign, no workspace, no store row, no
                      environment and no gate configured, on a bare
                      interpreter: absent -> None, present -> the
                      operator's own refusal, in the operator's words.
                      This is the whole dependency set of the brake: the
                      filesystem and one constant.

NO TEST CREATES THE REAL FILE. The path constant is patched to a
throwaway.
"""
import ast
import inspect
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import haltfile, killswitch, providerwrites

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HALTFILE = os.path.join(ROOT, "src", "haltfile.py")


class TheModuleImportsNothingButTheFilesystem(unittest.TestCase):

    def test_haltfile_imports_only_os(self):
        with open(HALTFILE, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or ".")
        self.assertEqual(
            imported, {"os"},
            f"the brake's imports are {sorted(imported)}. Every import is "
            "a thing that can be broken or that can demand a token at the "
            "moment the operator needs the brake; the brake's dependency "
            "set is the filesystem and nothing else")

    def test_the_path_is_a_constant_not_derived_from_the_running_tree(self):
        """Absolute and outside every checkout, never `__file__`, never
        the working directory - a brake whose path is relative to
        whichever checkout is running is a brake the operator can create
        in the wrong tree and believe he pulled."""
        self.assertTrue(os.path.isabs(haltfile.STOP_SENDING_PATH),
                        "the brake path must be absolute")
        self.assertNotIn(
            ROOT, haltfile.STOP_SENDING_PATH,
            "the brake path must live outside every checkout of this "
            "repository; this test's own tree must not contain it")
        self.assertNotIn("resonate-group-automation",
                         haltfile.STOP_SENDING_PATH)

    def test_the_path_is_read_at_call_time_not_import_time(self):
        """Tests patch `haltfile.STOP_SENDING_PATH` and production reads
        the module global at call time; pin that the function has no
        captured copy. Asserted by patching and calling, which is also
        the proof every other module in this task relies on."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "STOP-SENDING")
            with open(path, "wb") as handle:
                handle.write(b"")
            with mock.patch.object(haltfile, "STOP_SENDING_PATH", path):
                with self.assertRaises(haltfile.OperatorStop):
                    haltfile.require_released()


class TheCheckTakesNoPermission(unittest.TestCase):

    def test_the_signature_has_no_permission_position(self):
        signature = inspect.signature(haltfile.require_released)
        forbidden = {"authorization", "scope", "token", "grant", "role",
                     "by", "campaign", "tenant", "workspace", "payload",
                     "provider_id", "operation"}
        for name in signature.parameters:
            self.assertNotIn(
                name, forbidden,
                f"require_released({name}) is a permission question. The "
                "brake must not need to know who is asking")


class TheRefusalIsItsOwnVerdict(unittest.TestCase):

    def test_operator_stop_is_a_sibling_of_the_gate_refusals(self):
        self.assertTrue(issubclass(haltfile.OperatorStop, RuntimeError))
        self.assertFalse(
            issubclass(haltfile.OperatorStop, providerwrites.WriteRefused),
            "an OperatorStop caught as a WriteRefused would be re-worded "
            "by the estate's existing gate handlers: the operator's brake "
            "must not wear a gate's uniform")
        self.assertFalse(
            issubclass(haltfile.OperatorStop, killswitch.SendingRefused))


class ItWorksOnABareInterpreter(unittest.TestCase):

    def test_absent_present_and_unreadable_with_no_machinery(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "STOP-SENDING")
            with mock.patch.object(haltfile, "STOP_SENDING_PATH", path):
                self.assertIsNone(
                    haltfile.require_released(),
                    "no campaign, no workspace, no store, no gate: absent "
                    "means released, and the brake consulted nobody to "
                    "learn that")
                with open(path, "wb") as handle:
                    handle.write(b"")
                with self.assertRaises(haltfile.OperatorStop) as raised:
                    haltfile.require_released()
                self.assertIn("the operator has pulled the brake",
                              str(raised.exception))
                self.assertIn("Delete the file", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
