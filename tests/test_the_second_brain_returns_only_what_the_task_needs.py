"""The Second Brain returns only what the task needs, with honest provenance."""
import os
import sys
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
            secondbrain.all_sections("productive", reason="test")

        self.assertEqual(writes_under_config, [],
                         f"secondbrain wrote to config/: {writes_under_config}")

    def test_for_task_does_not_return_all_sections(self):
        result = secondbrain.for_task("cold_email_writing", "productive")
        keys = set(result.keys())
        self.assertNotEqual(keys, set(secondbrain.SECTIONS),
                            "for_task must not return every section")


class TestProvenanceIsClientSpecific(unittest.TestCase):
    """Every fact's source reflects the client config actually read."""

    def test_productive_sources_cite_productive(self):
        result = secondbrain.for_task("cold_email_writing", "productive")
        for section, facts in result.items():
            for fact in facts:
                self.assertIn("productive", fact["source"],
                              f"fact in {section} cites wrong client: "
                              f"{fact['source']}")

    def test_demo_sources_do_not_cite_productive(self):
        result = secondbrain.for_task("cold_email_writing", "demo")
        for section, facts in result.items():
            for fact in facts:
                self.assertNotIn("productive", fact["source"],
                                 f"demo fact cites productive: {fact['source']}")
                self.assertIn("demo", fact["source"],
                              f"demo fact does not cite demo: {fact['source']}")

    def test_sources_differ_between_clients(self):
        prod = secondbrain.for_task("cold_email_writing", "productive")
        demo = secondbrain.for_task("cold_email_writing", "demo")
        prod_srcs = {f["source"] for s in prod.values() for f in s}
        demo_srcs = {f["source"] for s in demo.values() for f in s}
        self.assertFalse(prod_srcs & demo_srcs,
                         "sources must not overlap between clients: "
                         f"{prod_srcs & demo_srcs}")


class TestVerifiedIsHonest(unittest.TestCase):
    """Facts are unverified unless a verification step has run."""

    def test_facts_are_unverified_by_default(self):
        result = secondbrain.for_task("cold_email_writing", "productive")
        for section, facts in result.items():
            for fact in facts:
                self.assertFalse(
                    fact.get("verified", True),
                    f"fact in {section} is marked verified but nothing "
                    f"verified it: {fact['text']!r}")


class TestTaskSectionsIsImmutable(unittest.TestCase):
    """TASK_SECTIONS cannot be mutated to bypass the gate."""

    def test_assignment_raises(self):
        with self.assertRaises((TypeError, KeyError)):
            secondbrain.TASK_SECTIONS["cold_email_writing"] = ("profile",)

    def test_new_key_raises(self):
        with self.assertRaises((TypeError, KeyError)):
            secondbrain.TASK_SECTIONS["new_task"] = ("profile",)

    def test_mutation_does_not_widen_gate(self):
        """Even if someone tries to mutate, for_task still narrows."""
        original_keys = set(secondbrain.TASK_SECTIONS["cold_email_writing"])
        try:
            secondbrain.TASK_SECTIONS["cold_email_writing"] = secondbrain.SECTIONS
        except (TypeError, KeyError):
            pass
        result = secondbrain.for_task("cold_email_writing", "productive")
        actual_keys = set(result.keys())
        self.assertEqual(actual_keys, original_keys,
                         "TASK_SECTIONS mutation widened the gate: "
                         f"expected {original_keys}, got {actual_keys}")


class TestAllSectionsRequiresReason(unittest.TestCase):
    """all_sections is gated by a mandatory reason= argument."""

    def test_without_reason_raises(self):
        with self.assertRaises((TypeError, ValueError)):
            secondbrain.all_sections("productive")

    def test_empty_reason_raises(self):
        with self.assertRaises(ValueError):
            secondbrain.all_sections("productive", reason="")

    def test_with_reason_succeeds(self):
        result = secondbrain.all_sections("productive", reason="test index")
        self.assertIn("profile", result)
        self.assertIn("market", result)


class TestConsumerWiring(unittest.TestCase):
    """copystages.business_context_for calls secondbrain.for_task."""

    def test_business_context_for_returns_text(self):
        from src import copystages
        ctx = copystages.business_context_for("cold_email_writing", "productive")
        self.assertIsNotNone(ctx)
        self.assertIn("[profile]", ctx)
        self.assertIn("config/clients/productive.yaml", ctx)

    def test_business_context_for_demo_cites_demo(self):
        from src import copystages
        ctx = copystages.business_context_for("cold_email_writing", "demo")
        self.assertIsNotNone(ctx)
        self.assertIn("config/clients/demo.yaml", ctx)
        self.assertNotIn("productive", ctx)

    def test_breaking_wiring_fails_the_test(self):
        """If business_context_for stops calling for_task, this catches it."""
        from src import copystages
        real_for_task = secondbrain.for_task
        calls = []

        def tracking_for_task(task, client):
            calls.append((task, client))
            return real_for_task(task, client)

        with mock.patch.object(secondbrain, "for_task",
                               side_effect=tracking_for_task):
            copystages.business_context_for("campaign_strategy", "productive")

        self.assertEqual(len(calls), 1,
                         "business_context_for did not call secondbrain.for_task")
        self.assertEqual(calls[0], ("campaign_strategy", "productive"))


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

    def test_index_says_unverified_not_verified(self):
        html = secondbrain.index_html("productive")
        self.assertIn("unverified", html)


if __name__ == "__main__":
    unittest.main()
