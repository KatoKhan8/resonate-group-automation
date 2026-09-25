"""Tests for the review file build script.

TASK-304: the 491-498 retroactive review files.

Tests the provider data rendering, held-lead detection, and pack fact
joining that the script performs before handing off to reviewfile.build().
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Import the script's functions by path since it's not in src/.
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "build_review_file",
    os.path.join(ROOT, "scripts", "build_review_file.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_render = _mod._render_provider_step
_join = _mod._join_pack_facts
_build = _mod.build_from_provider_data


class TestRenderProviderStep(unittest.TestCase):

    def test_simple_substitution(self):
        step = {"email_subject": "{SUBJECT_1}",
                "email_body": "<p>{BODY_1}</p>"}
        variables = {"subject_1": "Hello there",
                     "body_1": "This is the body"}
        result = _render(step, variables)
        self.assertEqual(result["subject"], "Hello there")
        # HTML tags stripped.
        self.assertEqual(result["body"], "This is the body")

    def test_empty_variable_renders_empty(self):
        step = {"email_subject": "{SUBJECT_1}",
                "email_body": "<p>{BODY_1}</p>"}
        variables = {"subject_1": "", "body_1": ""}
        result = _render(step, variables)
        self.assertEqual(result["subject"], "")
        self.assertEqual(result["body"], "")

    def test_missing_variable_renders_empty(self):
        step = {"email_subject": "{SUBJECT_1}",
                "email_body": "<p>{BODY_1}</p>"}
        variables = {}
        result = _render(step, variables)
        self.assertEqual(result["subject"], "")
        self.assertEqual(result["body"], "")

    def test_threaded_followup_empty_subject(self):
        """Threaded follow-ups carry an empty subject variable."""
        step = {"email_subject": "{SUBJECT_1}",
                "email_body": "<p>{BODY_2}</p>"}
        variables = {"subject_1": "Original subject",
                     "body_2": "Follow-up body"}
        result = _render(step, variables)
        self.assertEqual(result["subject"], "Original subject")
        self.assertEqual(result["body"], "Follow-up body")

    def test_html_preserved_when_no_tags(self):
        step = {"email_subject": "Test",
                "email_body": "Plain text body"}
        result = _render(step, {})
        self.assertEqual(result["body"], "Plain text body")


class TestJoinPackFacts(unittest.TestCase):

    def test_used_fact_detected(self):
        record = {"facts": [
            {"source_url": "http://example.com",
             "retrieved_at": "2026-09-25",
             "snippet": "They specialise in brand strategy and digital marketing"},
        ]}
        variables = {
            "body_1": "I noticed they specialise in brand strategy and "
                      "digital marketing at scale",
        }
        facts = _join(record, variables)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["used"], "USED")
        self.assertIn("step 1", facts[0]["feeds_sentence"])

    def test_not_used_fact(self):
        record = {"facts": [
            {"source_url": "http://example.com",
             "retrieved_at": "2026-09-25",
             "snippet": "Order your favorite dishes in seconds"},
        ]}
        variables = {
            "body_1": "I work with agencies on profitability",
        }
        facts = _join(record, variables)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["used"], "NOT USED")

    def test_empty_record_no_facts(self):
        facts = _join({}, {"body_1": "test"})
        self.assertEqual(facts, [])

    def test_multiple_facts_mixed(self):
        record = {"facts": [
            {"source_url": "http://a.com",
             "snippet": "profitability visible on Monday"},
            {"source_url": "http://b.com",
             "snippet": "Order online skip to main content"},
        ]}
        variables = {
            "body_1": "I help teams get profitability visible on Monday "
                      "not two weeks late",
        }
        facts = _join(record, variables)
        self.assertEqual(len(facts), 2)
        self.assertEqual(facts[0]["used"], "USED")
        self.assertEqual(facts[1]["used"], "NOT USED")


class TestBuildFromProviderData(unittest.TestCase):

    def _make_provider_data(self, campaign_id="491", n_leads=2,
                            with_copy=True):
        leads = []
        for i in range(n_leads):
            lead = {
                "lead_id": 10000 + i,
                "record_id": f"rec-{i}",
                "contact_key": f"contact-{i}",
                "persona": "economic_buyer" if i % 2 == 0 else "champion",
                "profile": {
                    "email": f"prospect{i}@agency.com",
                    "first_name": f"First{i}",
                    "last_name": f"Last{i}",
                    "title": "CEO" if i % 2 == 0 else "COO",
                    "company": f"Agency {i}",
                },
            }
            if with_copy:
                lead["custom_variables"] = {
                    "subject_1": f"Subject for {i}",
                    "body_1": f"Body for {i}",
                    "subject_2": "",
                    "body_2": f"Follow-up {i}",
                    "subject_3": "",
                    "body_3": f"Final {i}",
                    "record_id": f"rec-{i}",
                    "contact_key": f"contact-{i}",
                    "client": "productive",
                }
            else:
                lead["custom_variables"] = {
                    "headline": "CEO",
                    "location": "London",
                }
            leads.append(lead)
        return {
            str(campaign_id): {
                "campaign": {
                    "campaign_id": str(campaign_id),
                    "client": "productive",
                    "batch_id": "batch-1",
                    "name": "Test Campaign",
                },
                "senders": [
                    {"email": "reneE@productive.test", "name": "Renee"},
                ],
                "sequence_steps": [
                    {"step_key": "em1", "email_subject": "{SUBJECT_1}",
                     "email_body": "<p>{BODY_1}</p>", "thread_reply": False},
                    {"step_key": "em2", "email_subject": "{SUBJECT_2}",
                     "email_body": "<p>{BODY_2}</p>", "thread_reply": True},
                    {"step_key": "em3", "email_subject": "{SUBJECT_3}",
                     "email_body": "<p>{BODY_3}</p>", "thread_reply": True},
                ],
                "leads": leads,
            }
        }

    def test_build_renders_leads_with_copy(self):
        data = self._make_provider_data(n_leads=3)
        result = _build("491", data)
        self.assertEqual(result["rendered_count"], 3)
        self.assertEqual(result["held_count"], 0)
        self.assertEqual(result["n_steps"], 3)

    def test_build_held_leads_without_copy(self):
        data = self._make_provider_data(n_leads=2, with_copy=False)
        result = _build("491", data)
        self.assertEqual(result["rendered_count"], 0)
        self.assertEqual(result["held_count"], 2)
        self.assertEqual(result["held"][0]["reason"],
                         "no copy variables - needs Stage 2 provider write")

    def test_build_mixed_held_and_rendered(self):
        data = self._make_provider_data(n_leads=4, with_copy=True)
        # Make two leads have no copy.
        data["491"]["leads"][2]["custom_variables"] = {"headline": "X"}
        data["491"]["leads"][3]["custom_variables"] = {}
        result = _build("491", data)
        self.assertEqual(result["rendered_count"], 2)
        self.assertEqual(result["held_count"], 2)

    def test_build_produces_file_hash(self):
        data = self._make_provider_data(n_leads=1)
        result = _build("491", data)
        self.assertEqual(len(result["file_hash"]), 16)
        self.assertIsInstance(result["file_hash"], str)

    def test_build_three_steps_not_five(self):
        data = self._make_provider_data(n_leads=1)
        result = _build("491", data)
        # Three step columns, not five.
        step_cols = [c for c in result["columns"] if c.startswith("step_")]
        self.assertEqual(len(step_cols), 6)  # 3 subjects + 3 bodies

    def test_build_missing_campaign_raises(self):
        with self.assertRaises(ValueError):
            _build("999", {"491": {}})

    def test_sender_assignment_deterministic(self):
        data = self._make_provider_data(n_leads=3)
        r1 = _build("491", data)
        r2 = _build("491", data)
        for i in range(3):
            self.assertEqual(r1["rows"][i]["sender_mailbox"],
                             r2["rows"][i]["sender_mailbox"])


class TestScriptCLI(unittest.TestCase):

    def test_main_with_provider_data(self):
        data = {
            "491": {
                "campaign": {
                    "campaign_id": "491",
                    "client": "productive",
                    "batch_id": "batch-1",
                    "name": "Test",
                },
                "senders": [{"email": "s@t.com", "name": "S"}],
                "sequence_steps": [
                    {"step_key": "em1", "email_subject": "{SUBJECT_1}",
                     "email_body": "<p>{BODY_1}</p>"},
                    {"step_key": "em2", "email_subject": "{SUBJECT_2}",
                     "email_body": "<p>{BODY_2}</p>"},
                    {"step_key": "em3", "email_subject": "{SUBJECT_3}",
                     "email_body": "<p>{BODY_3}</p>"},
                ],
                "leads": [{
                    "lead_id": 12345,
                    "record_id": "rec-1",
                    "contact_key": "john",
                    "persona": "economic_buyer",
                    "profile": {
                        "email": "john@test.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "title": "CEO",
                        "company": "TestCo",
                    },
                    "custom_variables": {
                        "subject_1": "Hello",
                        "body_1": "World",
                        "body_2": "Follow up",
                        "body_3": "Final",
                    },
                }],
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "provider.json")
            with open(data_path, "w") as f:
                json.dump(data, f)
            out_dir = os.path.join(tmpdir, "output")
            rc = _mod.main(["491", "--provider-data", data_path,
                            "--output-dir", out_dir])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(
                os.path.join(out_dir, "491-review.xlsx")))
            self.assertTrue(os.path.exists(
                os.path.join(out_dir, "491-review.html")))
            self.assertTrue(os.path.exists(
                os.path.join(out_dir, "491-review.csv")))


if __name__ == "__main__":
    unittest.main()
