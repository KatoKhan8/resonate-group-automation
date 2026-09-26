"""Every producer names a consumer or is DISCONNECTED.

This test enforces the Phase 1 policy from OPERATOR-DIRECTIVES-2026-09-26:
no intelligence component is complete unless every producer has a named
production consumer. A module whose only caller is its own test, or a
comment, or a re-export that nothing follows through, is DISCONNECTED.

The test does NOT fail on DISCONNECTED modules — that would block every
merge until wiring is done. Instead it ASSERTS that known-disconnected
modules ARE disconnected (the guard works), and that the audit tool
correctly classifies the four verified cases from the task spec.

A separate integration check (the probe test) proves the guard can
detect a NEW disconnected module.
"""
import ast
import json
import os
import sys
import tempfile
import textwrap
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import consumer_audit as ca


class KnownDisconnected(unittest.TestCase):
    """The four components verified on master at 4268197a must come out
    DISCONNECTED (or CONNECTED for contextpack, which is a display module
    consumed by src/web/api.py)."""

    @classmethod
    def setUpClass(cls):
        cls.rows = ca.audit()
        cls.by_component = {r["component"]: r for r in cls.rows}

    def test_secondbrain_is_disconnected(self):
        row = self.by_component.get("src/secondbrain.py")
        self.assertIsNotNone(row, "secondbrain.py not found in audit")
        self.assertEqual(row["verdict"], "DISCONNECTED")

    def test_sequencegate_is_disconnected(self):
        row = self.by_component.get("src/sequencegate.py")
        self.assertIsNotNone(row, "sequencegate.py not found in audit")
        self.assertEqual(row["verdict"], "DISCONNECTED")

    def test_copystages_is_disconnected(self):
        row = self.by_component.get("src/copystages.py")
        self.assertIsNotNone(row, "copystages.py not found in audit")
        self.assertEqual(row["verdict"], "DISCONNECTED")

    def test_contextpack_is_connected_via_web_api(self):
        row = self.by_component.get("src/contextpack.py")
        self.assertIsNotNone(row, "contextpack.py not found in audit")
        self.assertEqual(row["verdict"], "CONNECTED")
        consumer_modules = [c["module"] for c in row["consumers"]]
        self.assertIn("src.web.api", consumer_modules)


class CommentIsNotACaller(unittest.TestCase):
    """A string match on a module name inside a comment must NOT count
    as a caller. This is the TASK-324 restatement of the CLAUDE.md rule:
    'Searching source for words produces a test that fails when somebody
    writes a comment.'"""

    def test_comment_mention_does_not_connect(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src")
            os.makedirs(src)

            prod = os.path.join(src, "producer.py")
            with open(prod, "w") as f:
                f.write("def useful():\n    return 42\n")

            cons = os.path.join(src, "consumer.py")
            with open(cons, "w") as f:
                f.write(textwrap.dedent("""\
                    # This module mentions producer in a comment
                    # producer.useful() is what we would call
                    # but we never actually import it
                    def other():
                        return 99
                """))

            init = os.path.join(src, "__init__.py")
            with open(init, "w") as f:
                f.write("")

            tree_p = ca._parse(prod)
            tree_c = ca._parse(cons)

            pub = ca._public_names(tree_p)
            self.assertIn("useful", pub)

            used_bare, used_dotted = ca._collect_used_names(tree_c)
            self.assertNotIn("useful", used_bare,
                "A comment should not produce a bare-name usage")
            self.assertNotIn("producer", used_bare,
                "A comment should not produce a module-name usage")


class CommentIsNotACallerDirect(unittest.TestCase):
    """Direct AST proof: a comment containing 'producer.useful()' does
    not appear in the AST at all."""

    def test_ast_ignores_comments(self):
        code = textwrap.dedent("""\
            # producer.useful() is called here
            x = 1
        """)
        tree = ast.parse(code)
        bare, dotted = ca._collect_used_names(tree)
        self.assertNotIn("producer", bare)
        self.assertNotIn("useful", bare)
        self.assertEqual(dotted, {})


class ProbeTest(unittest.TestCase):
    """Prove the guard works: a throwaway module with no caller must be
    detected as DISCONNECTED. This is the TASK-317 acceptance defect —
    a guard that has never been seen to fail is not known to work."""

    def test_probe_is_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src")
            os.makedirs(src)

            init = os.path.join(src, "__init__.py")
            with open(init, "w") as f:
                f.write("")

            probe = os.path.join(src, "_probe_unused.py")
            with open(probe, "w") as f:
                f.write("def orphan_function():\n    return None\n")

            other = os.path.join(src, "other.py")
            with open(other, "w") as f:
                f.write("def used_function():\n    return 1\n")

            consumer = os.path.join(src, "consumer.py")
            with open(consumer, "w") as f:
                f.write(textwrap.dedent("""\
                    from . import other
                    def call_other():
                        return other.used_function()
                """))

            orig_src = ca.SRC_DIR
            try:
                ca.SRC_DIR = src
                rows = ca.audit()
            finally:
                ca.SRC_DIR = orig_src

            by_name = {}
            for r in rows:
                short = r["component"].split("/")[-1]
                by_name[short] = r

            probe_row = by_name.get("_probe_unused.py")
            self.assertIsNotNone(probe_row,
                "Probe module not found in audit results")
            self.assertEqual(probe_row["verdict"], "DISCONNECTED",
                "Probe module with no caller should be DISCONNECTED")

            other_row = by_name.get("other.py")
            self.assertIsNotNone(other_row,
                "Other module not found in audit results")
            self.assertEqual(other_row["verdict"], "CONNECTED",
                "Module with a real caller should be CONNECTED")


class ReexportIsNotAConsumer(unittest.TestCase):
    """A re-export through __init__.py that nothing then calls keeps a
    module alive in the import graph while nothing consumes it."""

    def test_reexport_only_is_disconnected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src")
            os.makedirs(src)

            init = os.path.join(src, "__init__.py")
            with open(init, "w") as f:
                f.write("from . import orphan\n")

            orphan = os.path.join(src, "orphan.py")
            with open(orphan, "w") as f:
                f.write("def useful():\n    return 42\n")

            orig_src = ca.SRC_DIR
            try:
                ca.SRC_DIR = src
                rows = ca.audit()
            finally:
                ca.SRC_DIR = orig_src

            by_name = {}
            for r in rows:
                short = r["component"].split("/")[-1]
                by_name[short] = r

            orphan_row = by_name.get("orphan.py")
            self.assertIsNotNone(orphan_row)
            self.assertEqual(orphan_row["verdict"], "DISCONNECTED",
                "A module only re-exported through __init__ with no "
                "downstream caller is DISCONNECTED")


class TestExclusion(unittest.TestCase):
    """tests/ modules are not production consumers."""

    def test_test_only_caller_is_disconnected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src")
            tests = os.path.join(tmpdir, "tests")
            os.makedirs(src)
            os.makedirs(tests)

            init = os.path.join(src, "__init__.py")
            with open(init, "w") as f:
                f.write("")

            prod = os.path.join(src, "lonely.py")
            with open(prod, "w") as f:
                f.write("def only_called_by_test():\n    return 1\n")

            test_file = os.path.join(tests, "test_lonely.py")
            with open(test_file, "w") as f:
                f.write(textwrap.dedent("""\
                    from src import lonely
                    def test_it():
                        assert lonely.only_called_by_test() == 1
                """))

            orig_src = ca.SRC_DIR
            try:
                ca.SRC_DIR = src
                rows = ca.audit()
            finally:
                ca.SRC_DIR = orig_src

            by_name = {}
            for r in rows:
                short = r["component"].split("/")[-1]
                by_name[short] = r

            lonely_row = by_name.get("lonely.py")
            self.assertIsNotNone(lonely_row)
            self.assertEqual(lonely_row["verdict"], "DISCONNECTED",
                "A module only called from tests/ is DISCONNECTED")


if __name__ == "__main__":
    unittest.main()
