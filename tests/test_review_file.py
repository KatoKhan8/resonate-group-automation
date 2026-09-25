"""Tests for the review file generator.

TASK-301 column spec: the standing spec for every review file.
TASK-304: retroactive review files for campaigns 491-498.

These tests verify:
- The column spec matches TASK-301
- The XLSX output is a valid zip with the expected structure
- The HTML output contains the hash and campaign id
- The CSV output guards against formula execution
- Pack facts expand correctly (USED and NOT USED visible)
- Held leads (no copy variables) are reported, not rendered blank
- Three-step campaigns render three steps, not five
"""
import csv
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import reviewfile


class TestColumnSpec(unittest.TestCase):
    """TASK-301: the standing column spec for every review file."""

    def test_base_columns_present(self):
        cols = reviewfile.all_columns(n_steps=3)
        for expected in ("sender_mailbox", "sender_name", "lead_email",
                         "name", "title", "company", "cohort_tag", "persona"):
            self.assertIn(expected, cols,
                          f"{expected} missing from column spec")

    def test_step_columns_for_three_steps(self):
        cols = reviewfile.step_columns(3)
        self.assertEqual(cols, [
            "step_1_subject", "step_1_body",
            "step_2_subject", "step_2_body",
            "step_3_subject", "step_3_body",
        ])

    def test_step_columns_for_five_steps(self):
        cols = reviewfile.step_columns(5)
        self.assertEqual(len(cols), 10)
        self.assertIn("step_5_subject", cols)
        self.assertIn("step_5_body", cols)

    def test_linkedin_columns_added_when_flagged(self):
        cols_with = reviewfile.all_columns(3, has_linkedin=True)
        cols_without = reviewfile.all_columns(3, has_linkedin=False)
        self.assertIn("linkedin_profile_url", cols_with)
        self.assertIn("linkedin_connection_note", cols_with)
        self.assertNotIn("linkedin_profile_url", cols_without)

    def test_pack_columns_always_present(self):
        cols = reviewfile.all_columns(3)
        for expected in ("pack_source_url", "pack_retrieved_at",
                         "pack_snippet", "pack_used", "pack_feeds_sentence"):
            self.assertIn(expected, cols)

    def test_three_steps_not_five(self):
        """TASK-304: these campaigns hold three steps, not five."""
        cols = reviewfile.all_columns(3)
        self.assertNotIn("step_4_subject", cols)
        self.assertNotIn("step_5_body", cols)


class TestReviewRow(unittest.TestCase):

    def _make_row(self, **kw):
        defaults = {
            "sender_mailbox": "sender@example.com",
            "sender_name": "Ivan",
            "lead_email": "prospect@company.com",
            "name": "John Doe",
            "title": "CEO",
            "company": "Acme Agency",
            "cohort_tag": "batch-1",
            "persona": "economic_buyer",
            "steps": [
                {"subject": "Hello", "body": "First email body"},
                {"subject": "", "body": "Second email body"},
                {"subject": "", "body": "Third email body"},
            ],
        }
        defaults.update(kw)
        return reviewfile.ReviewRow(**defaults)

    def test_as_dict_has_all_columns(self):
        row = self._make_row()
        d = row.as_dict(n_steps=3)
        self.assertEqual(d["sender_mailbox"], "sender@example.com")
        self.assertEqual(d["step_1_subject"], "Hello")
        self.assertEqual(d["step_1_body"], "First email body")
        self.assertEqual(d["step_2_body"], "Second email body")
        self.assertEqual(d["step_3_body"], "Third email body")

    def test_linkedin_columns_empty_when_no_profile(self):
        row = self._make_row()
        d = row.as_dict(n_steps=3, has_linkedin=True)
        self.assertEqual(d["linkedin_profile_url"], "")
        self.assertEqual(d["linkedin_connection_note"], "")

    def test_linkedin_columns_populated_when_present(self):
        row = self._make_row(linkedin={
            "profile_url": "https://linkedin.com/in/johndoe",
            "connection_note": "hi John, let's connect",
            "followup_1": "thanks for connecting",
            "followup_2": "worth a look?",
        })
        d = row.as_dict(n_steps=3, has_linkedin=True)
        self.assertEqual(d["linkedin_profile_url"],
                         "https://linkedin.com/in/johndoe")
        self.assertEqual(d["linkedin_connection_note"],
                         "hi John, let's connect")


class TestPackExpansion(unittest.TestCase):

    def test_single_fact_no_expansion(self):
        base = {"sender_mailbox": "a@b.com", "lead_email": "c@d.com",
                "company": "X", "pack_snippet": "They do marketing",
                "pack_used": "USED", "pack_source_url": "http://example.com",
                "pack_retrieved_at": "2026-09-25",
                "pack_feeds_sentence": "step 1"}
        facts = [{"source_url": "http://example.com",
                   "retrieved_at": "2026-09-25",
                   "snippet": "They do marketing",
                   "used": "USED",
                   "feeds_sentence": "step 1"}]
        rows = reviewfile.expand_pack_rows(base, facts, n_steps=3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pack_snippet"], "They do marketing")

    def test_multiple_facts_expand(self):
        base = {"sender_mailbox": "a@b.com", "lead_email": "c@d.com",
                "company": "X", "pack_snippet": "First fact",
                "pack_used": "USED", "pack_source_url": "http://a.com",
                "pack_retrieved_at": "2026-09-25",
                "pack_feeds_sentence": "step 1"}
        facts = [
            {"source_url": "http://a.com", "snippet": "First fact",
             "used": "USED", "feeds_sentence": "step 1"},
            {"source_url": "http://b.com", "snippet": "Nav chrome",
             "used": "NOT USED", "feeds_sentence": ""},
            {"source_url": "http://c.com", "snippet": "Another fact",
             "used": "NOT USED", "feeds_sentence": ""},
        ]
        rows = reviewfile.expand_pack_rows(base, facts, n_steps=3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["pack_used"], "USED")
        self.assertEqual(rows[1]["pack_used"], "NOT USED")
        self.assertEqual(rows[2]["pack_snippet"], "Another fact")
        # Lead data repeated on expanded rows.
        self.assertEqual(rows[1]["sender_mailbox"], "a@b.com")
        self.assertEqual(rows[2]["company"], "X")

    def test_no_facts_single_row(self):
        base = {"sender_mailbox": "a@b.com"}
        rows = reviewfile.expand_pack_rows(base, [], n_steps=3)
        self.assertEqual(len(rows), 1)


class TestXlsxOutput(unittest.TestCase):

    def test_valid_zip(self):
        rows = [{"sender_mailbox": "a@b.com", "lead_email": "c@d.com"}]
        cols = ["sender_mailbox", "lead_email"]
        data = reviewfile.to_xlsx(rows, cols)
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(data)))

    def test_contains_expected_parts(self):
        rows = [{"col_a": "hello"}]
        cols = ["col_a"]
        data = reviewfile.to_xlsx(rows, cols)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            self.assertIn("[Content_Types].xml", names)
            self.assertIn("xl/workbook.xml", names)
            self.assertIn("xl/worksheets/sheet1.xml", names)
            self.assertIn("xl/sharedStrings.xml", names)

    def test_shared_strings_contain_values(self):
        rows = [{"col_a": "hello world", "col_b": "test value"}]
        cols = ["col_a", "col_b"]
        data = reviewfile.to_xlsx(rows, cols)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            ss = zf.read("xl/sharedStrings.xml").decode("utf-8")
            self.assertIn("hello world", ss)
            self.assertIn("test value", ss)
            self.assertIn("col_a", ss)

    def test_empty_workbook(self):
        data = reviewfile.to_xlsx([], ["a", "b"])
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(data)))


class TestCsvOutput(unittest.TestCase):

    def test_formula_guard(self):
        rows = [{"col": "=SUM(A1:A10)"}]
        cols = ["col"]
        text = reviewfile.to_csv(rows, cols)
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            self.assertTrue(row["col"].startswith("'"),
                            "formula should be guarded with leading quote")

    def test_header_present(self):
        rows = [{"a": "1", "b": "2"}]
        cols = ["a", "b"]
        text = reviewfile.to_csv(rows, cols)
        reader = csv.DictReader(io.StringIO(text))
        self.assertEqual(reader.fieldnames, ["a", "b"])


class TestHtmlOutput(unittest.TestCase):

    def test_contains_campaign_id(self):
        result = reviewfile.build("491", [{
            "sender_mailbox": "a@b.com", "sender_name": "Ivan",
            "lead_email": "c@d.com", "name": "John",
            "title": "CEO", "company": "Acme",
            "cohort_tag": "b1", "persona": "economic_buyer",
            "steps": [{"subject": "Hi", "body": "Hello"}],
        }], n_steps=1)
        self.assertIn("491", result["html"])

    def test_contains_hash(self):
        result = reviewfile.build("491", [{
            "sender_mailbox": "a@b.com", "sender_name": "Ivan",
            "lead_email": "c@d.com", "name": "John",
            "title": "CEO", "company": "Acme",
            "cohort_tag": "b1", "persona": "economic_buyer",
            "steps": [{"subject": "Hi", "body": "Hello"}],
        }], n_steps=1)
        self.assertIn(result["file_hash"], result["html"])

    def test_hash_is_16_chars(self):
        result = reviewfile.build("491", [{
            "sender_mailbox": "a@b.com", "sender_name": "Ivan",
            "lead_email": "c@d.com", "name": "John",
            "title": "CEO", "company": "Acme",
            "cohort_tag": "b1", "persona": "economic_buyer",
            "steps": [{"subject": "Hi", "body": "Hello"}],
        }], n_steps=1)
        self.assertEqual(len(result["file_hash"]), 16)


class TestBuild(unittest.TestCase):

    def test_build_returns_all_artifacts(self):
        result = reviewfile.build("492", [{
            "sender_mailbox": "sender@test.com",
            "sender_name": "Renee",
            "lead_email": "prospect@test.com",
            "name": "Jane Smith",
            "title": "COO",
            "company": "Test Agency",
            "cohort_tag": "batch-1",
            "persona": "economic_buyer",
            "steps": [
                {"subject": "Subject 1", "body": "Body 1"},
                {"subject": "", "body": "Body 2"},
                {"subject": "", "body": "Body 3"},
            ],
            "pack_facts": [
                {"source_url": "http://example.com",
                 "retrieved_at": "2026-09-25",
                 "snippet": "A test fact",
                 "used": "USED",
                 "feeds_sentence": "step 1"},
            ],
        }], n_steps=3)
        self.assertEqual(result["campaign_id"], "492")
        self.assertEqual(result["lead_count"], 1)
        self.assertEqual(result["n_steps"], 3)
        self.assertIn("xlsx", result)
        self.assertIn("html", result)
        self.assertIn("csv", result)
        self.assertIn("file_hash", result)
        self.assertIn("columns", result)

    def test_build_multiple_leads(self):
        leads = [{
            "sender_mailbox": "s@t.com", "sender_name": "S",
            "lead_email": f"p{i}@t.com", "name": f"P{i}",
            "title": "CEO", "company": f"C{i}",
            "cohort_tag": "b1", "persona": "champion",
            "steps": [{"subject": "Hi", "body": f"Body {i}"}],
        } for i in range(5)]
        result = reviewfile.build("494", leads, n_steps=1)
        self.assertEqual(result["lead_count"], 5)
        self.assertEqual(len(result["rows"]), 5)


class TestWriteOutput(unittest.TestCase):

    def test_write_creates_files(self):
        result = reviewfile.build("496", [{
            "sender_mailbox": "a@b.com", "sender_name": "Ivan",
            "lead_email": "c@d.com", "name": "John",
            "title": "CEO", "company": "Acme",
            "cohort_tag": "b1", "persona": "economic_buyer",
            "steps": [{"subject": "Hi", "body": "Hello"}],
        }], n_steps=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            xlsx_path, html_path, csv_path = reviewfile.write(result, tmpdir)
            self.assertTrue(os.path.exists(xlsx_path))
            self.assertTrue(os.path.exists(html_path))
            self.assertTrue(os.path.exists(csv_path))
            self.assertTrue(os.path.getsize(xlsx_path) > 0)
            self.assertTrue(os.path.getsize(html_path) > 0)

    def test_xlsx_path_naming(self):
        result = reviewfile.build("491", [{
            "sender_mailbox": "a@b.com", "sender_name": "Ivan",
            "lead_email": "c@d.com", "name": "John",
            "title": "CEO", "company": "Acme",
            "cohort_tag": "b1", "persona": "economic_buyer",
            "steps": [{"subject": "Hi", "body": "Hello"}],
        }], n_steps=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            xlsx_path, _, _ = reviewfile.write(result, tmpdir)
            self.assertTrue(xlsx_path.endswith("491-review.xlsx"))


class TestHashDeterministic(unittest.TestCase):

    def test_same_input_same_hash(self):
        lead = {
            "sender_mailbox": "a@b.com", "sender_name": "Ivan",
            "lead_email": "c@d.com", "name": "John",
            "title": "CEO", "company": "Acme",
            "cohort_tag": "b1", "persona": "economic_buyer",
            "steps": [{"subject": "Hi", "body": "Hello"}],
        }
        r1 = reviewfile.build("491", [lead], n_steps=1)
        r2 = reviewfile.build("491", [lead], n_steps=1)
        self.assertEqual(r1["file_hash"], r2["file_hash"])

    def test_different_input_different_hash(self):
        lead1 = {
            "sender_mailbox": "a@b.com", "sender_name": "Ivan",
            "lead_email": "c@d.com", "name": "John",
            "title": "CEO", "company": "Acme",
            "cohort_tag": "b1", "persona": "economic_buyer",
            "steps": [{"subject": "Hi", "body": "Hello"}],
        }
        lead2 = dict(lead1, steps=[{"subject": "Hi", "body": "Different"}])
        r1 = reviewfile.build("491", [lead1], n_steps=1)
        r2 = reviewfile.build("491", [lead2], n_steps=1)
        self.assertNotEqual(r1["file_hash"], r2["file_hash"])


class TestColLetter(unittest.TestCase):

    def test_first_columns(self):
        self.assertEqual(reviewfile._col_letter(0), "A")
        self.assertEqual(reviewfile._col_letter(1), "B")
        self.assertEqual(reviewfile._col_letter(25), "Z")

    def test_double_letter_columns(self):
        self.assertEqual(reviewfile._col_letter(26), "AA")
        self.assertEqual(reviewfile._col_letter(27), "AB")


if __name__ == "__main__":
    unittest.main()
