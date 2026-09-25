"""The Second Brain returns only what the task needs and writes nothing."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import secondbrain


class TestSecondBrainRetrieval(unittest.TestCase):
    """for_task returns only the sections a task needs."""

    def test_two_tasks_receive_different_sections(self):
        cold = secondbrain.for_task("cold_email_writing", "productive")
        li = secondbrain.for_task("linkedin_writing", "productive")
        cold_keys = set(cold.keys())
        li_keys = set(li.keys())
        self.assertNotEqual(cold_keys, li_keys,
                            "two different tasks must not receive the same sections")
        self.assertIn("offers", cold_keys)
        self.assertNotIn("offers", li_keys)

    def test_every_fact_has_source_and_date(self):
        for task in secondbrain.TASK_SECTIONS:
            result = secondbrain.for_task(task, "productive")
            for section, facts in result.items():
                if section == "_meta":
                    continue
                for fact in facts:
                    self.assertTrue(fact.get("source"),
                                    f"fact in {task}/{section} has no source")
                    self.assertTrue(fact.get("date"),
                                    f"fact in {task}/{section} has no date")

    def test_market_not_returned_for_cold_email_writing(self):
        result = secondbrain.for_task("cold_email_writing", "productive")
        self.assertNotIn("market", result,
                         "cold_email_writing does not need market structure")

    def test_unknown_task_raises(self):
        with self.assertRaises(ValueError):
            secondbrain.for_task("nonexistent_task", "productive")

    def test_missing_sections_are_empty_lists(self):
        result = secondbrain.for_task("campaign_strategy", "productive")
        for section in secondbrain.MISSING_SECTIONS:
            if section in result:
                self.assertEqual(result[section], [],
                                 f"{section} should be empty (MISSING)")

    def test_competitors_always_missing(self):
        result = secondbrain.for_task("account_research", "productive")
        competitors = result.get("competitors", [])
        self.assertEqual(competitors, [],
                         "competitor intelligence must not be invented")

    def test_writes_no_client_fact_anywhere(self):
        """secondbrain must not open any file for writing under config/."""
        original_open = open
        writes_under_config = []

        def tracking_open(path, mode="r", *args, **kwargs):
            if any(m in mode for m in ("w", "a", "x", "+")):
                resolved = os.path.abspath(str(path))
                config_dir = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..", "config"))
                if resolved.startswith(config_dir + os.sep) or resolved == config_dir:
                    writes_under_config.append(resolved)
            return original_open(path, mode, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=tracking_open):
            secondbrain.for_task("cold_email_writing", "productive")
            secondbrain.for_task("campaign_strategy", "productive")
            secondbrain.all_sections("productive")

        self.assertEqual(writes_under_config, [],
                         f"secondbrain wrote to config/: {writes_under_config}")

    def test_for_task_does_not_return_all_sections(self):
        result = secondbrain.for_task("cold_email_writing", "productive")
        keys = set(result.keys())
        self.assertNotEqual(keys, set(secondbrain.SECTIONS),
                            "for_task must not return every section")


class TestSecondBrainIndex(unittest.TestCase):
    """The index page includes the missing-information section."""

    def test_index_contains_missing_section(self):
        html = secondbrain.index_html("productive")
        self.assertIn("Missing Information", html)
        self.assertIn("Competitor intelligence", html)
        self.assertIn("Research Priorities", html)

    def test_index_contains_all_section_titles(self):
        html = secondbrain.index_html("productive")
        self.assertIn("Client Profile", html)
        self.assertIn("Market Intelligence", html)
        self.assertIn("Messaging Intelligence", html)


if __name__ == "__main__":
    unittest.main()
