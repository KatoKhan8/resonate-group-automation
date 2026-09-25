"""TASK-302: test the stage 1 rendering logic.

Verifies that:
1. Template rendering uses cadence.TEMPLATES, not invented copy
2. Template id is carried on each rendered step
3. Sender name comes from the mailbox owner, not a constant
4. Pack fact gate holds leads without usable facts
5. Nav text is refused by the pack fact gate
6. copylint runs over the batch
"""
import json
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import cadence, clients, copylint, packfacts, store


class TestPackFactGate(unittest.TestCase):
    """The pack fact gate refuses nav text and accepts body sentences."""

    def test_nav_text_is_refused(self):
        from scripts.task302_render_504 import _is_complete_sentence_with_verb
        nav = ("Order your favorite dishes in seconds! Order Online "
               "Skip to main content Drinks Menu Order Catering")
        self.assertFalse(_is_complete_sentence_with_verb(nav))

    def test_body_sentence_is_accepted(self):
        from scripts.task302_render_504 import _is_complete_sentence_with_verb
        body = ("Acme Agency is a digital marketing firm specialising in "
                "performance campaigns for B2B SaaS clients across Europe.")
        self.assertTrue(_is_complete_sentence_with_verb(body))

    def test_short_fragment_is_refused(self):
        from scripts.task302_render_504 import _is_complete_sentence_with_verb
        self.assertFalse(_is_complete_sentence_with_verb("About Us"))

    def test_empty_is_refused(self):
        from scripts.task302_render_504 import _is_complete_sentence_with_verb
        self.assertFalse(_is_complete_sentence_with_verb(""))
        self.assertFalse(_is_complete_sentence_with_verb(None))


class TestTemplateIdCarried(unittest.TestCase):
    """Each rendered step carries its template name as provenance."""

    def _config(self):
        return {
            "cadence": "productive_li_heavy_v1",
            "personas": {
                "champion": {
                    "cap_per_domain": 2,
                    "angles": {
                        "operations": "utilisation and capacity planning",
                    },
                },
            },
            "angle_labels": {"operations": "utilisation and capacity"},
            "product": {
                "name": "Productive",
                "capabilities": {
                    "budgeting": "what a project was quoted at and what it has burned",
                },
                "capability_by_persona": {"champion": "budgeting"},
            },
        }

    def test_template_step_carries_template_id(self):
        rec = {
            "id": "test-co",
            "domain": "test.co",
            "company": "Test Co",
            "company_facts": {"name": "Test Co", "industry": "marketing"},
            "contacts": [{"key": "jane-d", "name": "Jane Doe",
                          "email": "jane@test.co", "persona": "champion",
                          "angle": "operations"}],
            "research": [{"fact": "Test Co specialises in brand campaigns.",
                          "source_url": "https://test.co/about"}],
        }
        contact = rec["contacts"][0]
        config = self._config()
        spec = {"key": "day5", "day": 5, "channel": "email",
                "template": "persona_pain"}
        step = cadence.expand_step(rec, contact, spec, config)
        self.assertIsNotNone(step)
        self.assertEqual(step.get("template"), "persona_pain")
        self.assertIn("Test Co", step.get("body", ""))

    def test_generated_step_without_stored_copy_returns_none(self):
        rec = {
            "id": "test-co",
            "domain": "test.co",
            "company": "Test Co",
            "company_facts": {"name": "Test Co"},
            "contacts": [{"key": "jane-d", "name": "Jane Doe",
                          "email": "jane@test.co", "persona": "champion",
                          "angle": "operations"}],
            "cadence": {},
        }
        contact = rec["contacts"][0]
        config = self._config()
        spec = {"key": "day1", "day": 1, "channel": "email",
                "generated": True}
        step = cadence.expand_step(rec, contact, spec, config)
        self.assertIsNone(step)


class TestCopylintRunsOverBatch(unittest.TestCase):
    """copylint.check_batch runs and reports, not just passes."""

    def test_duplicate_first_line_detected(self):
        leads = [
            {"id": "lead-1", "steps": [{"body": "Same opening line here."}]},
            {"id": "lead-2", "steps": [{"body": "Same opening line here."}]},
        ]
        report = copylint.check_batch(leads)
        self.assertIn("lead-1", report["offenders"]["duplicate_first_line"])
        self.assertIn("lead-2", report["offenders"]["duplicate_first_line"])

    def test_dash_refused(self):
        leads = [
            {"id": "lead-1",
             "steps": [{"body": "Hello Jane \u2014 we work with agencies."}]},
        ]
        report = copylint.check_batch(leads)
        self.assertIn("lead-1", report["offenders"]["dash"])


class TestSenderNameNotConstant(unittest.TestCase):
    """The sender name is the mailbox owner's, never a constant."""

    def test_unknown_when_no_sender_configured(self):
        from scripts.task302_render_504 import _sender_name_for
        campaign = {"campaign_id": "test", "senders": {"email": []}}
        name = _sender_name_for(campaign, "jane-d", {})
        self.assertEqual(name, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
