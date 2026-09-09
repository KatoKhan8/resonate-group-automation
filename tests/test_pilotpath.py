"""The path a real company takes, checked rather than described.

A document describing the pipeline is accurate on the day it is written.
This file is what makes the description keep being true: every stage names
the test modules that cover it, and if one of those modules is deleted or
renamed the map stops being a claim and starts being a failure.
"""
import unittest

from src import pilotpath


class TheMapIsComplete(unittest.TestCase):

    def test_every_stage_has_every_field(self):
        for row in pilotpath.STAGES:
            for field in pilotpath.REQUIRED:
                self.assertIn(field, row, row.get("stage"))
            for field in ("canonical", "decision", "failure", "idempotent",
                          "tenancy"):
                self.assertTrue(row[field], f"{row['stage']}.{field}")

    def test_no_stage_is_listed_twice(self):
        names = [row["stage"] for row in pilotpath.STAGES]
        self.assertEqual(len(names), len(set(names)))

    def test_the_whole_pilot_path_is_covered(self):
        """The stages the mission brief names, in one list. A stage that
        quietly leaves this map is a stage nobody is checking."""
        names = {row["stage"] for row in pilotpath.STAGES}
        for required in ("workspace", "import", "dedupe", "ICP",
                         "enrichment", "email verification", "segment",
                         "campaign", "sender assignment", "variant",
                         "context pack", "claim licensing", "message QA",
                         "approval", "provider payload", "pre-send recheck",
                         "confirmed send", "reply ingestion",
                         "classification", "hold, pause and suppression",
                         "Slack", "provider tag sync", "reporting"):
            self.assertIn(required, names, required)

    def test_every_stage_names_at_least_one_test_module(self):
        self.assertEqual(pilotpath.uncovered(), [])

    def test_every_named_test_module_exists(self):
        """The point of the file. A stage naming a deleted test module is a
        stage that reads as covered and is not."""
        self.assertEqual(pilotpath.missing_tests(), [])

    def test_a_missing_module_would_be_reported(self):
        """A checker that never finds anything is not evidence."""
        original = pilotpath.STAGES
        try:
            pilotpath.STAGES = original + (
                pilotpath.stage("invented", "nowhere", "nothing", "nothing",
                                "none", "none", ("test_does_not_exist",)),)
            found = pilotpath.missing_tests()
            self.assertEqual([r["module"] for r in found],
                             ["test_does_not_exist"])
        finally:
            pilotpath.STAGES = original


class TheLiveColumnIsHonest(unittest.TestCase):

    def test_sending_is_blocking_on_both_channels_worth_of_state(self):
        """Not a flag. `push.run(live=True)` raises and `tagsync.send`
        refuses unconditionally."""
        self.assertIn("confirmed send", pilotpath.blocking())
        self.assertIn("provider tag sync", pilotpath.blocking())

    def test_a_blocking_stage_explains_itself(self):
        for row in pilotpath.STAGES:
            if row["live"] == pilotpath.BLOCKING:
                self.assertTrue(row["note"], row["stage"])

    def test_the_provider_stages_are_not_marked_ready(self):
        """Every stage that talks to a provider carries a live class.
        Marking one of these `None` would say a fixture had validated a
        wire."""
        for name in ("enrichment", "email verification", "provider payload",
                     "reply ingestion", "Slack", "provider tag sync",
                     "confirmed send"):
            self.assertIsNotNone(pilotpath.by_name(name)["live"], name)

    def test_a_pure_read_says_so_rather_than_leaving_it_blank(self):
        """An empty idempotency field reads as an oversight. `None` is a
        real answer for a read, and it is spelled out."""
        for row in pilotpath.STAGES:
            self.assertTrue(row["idempotent"], row["stage"])

    def test_the_summary_does_not_claim_correctness(self):
        found = pilotpath.summarise()
        self.assertIn("not the same as", found["note"])


class ItDecidesNothing(unittest.TestCase):
    """A map that could read state could disagree with the thing it maps."""

    def test_it_imports_nothing_from_the_system_it_describes(self):
        """Asserted on the import graph rather than by searching the source
        for names. The module quotes `repo.records()` in a tenancy
        description, and a test that reads prose fails when somebody writes
        some - which has now happened four times in this repository.
        """
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(pilotpath))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
                if node.level:
                    imported.add("src")
        self.assertEqual(imported & {"src", "store", "repo"}, set())

    def test_it_only_imports_the_standard_library(self):
        import ast
        import inspect
        import sys

        tree = ast.parse(inspect.getsource(pilotpath))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    self.assertIn(top, sys.stdlib_module_names, top)
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse(node.level, "no relative imports")


if __name__ == "__main__":
    unittest.main()
