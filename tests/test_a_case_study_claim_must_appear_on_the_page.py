"""TASK-365: every case-study claim must trace to the stored page.

The operator's rule: copy may name a case study and quote only what the
page itself states. The lint traces every case-study claim to the stored
page text and refuses anything not on it.

Acceptance criteria from the task:
  1. All 11 studies fetched (verified by the fetch script output).
  2. A claim that IS on the page passes.
  3. A claim that is NOT on the page REFUSES.
  4. An operator_summary figure alone is not sufficient.
  5. Two case studies in one email REFUSE.
  6. The guard is seen to fail (revert/restore - manual acceptance step).

Rework acceptance:
  1. With no stored page, a claim naming a study is REFUSED (fail-closed).
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src.copylint import (
    case_study_violations,
    check_batch,
    _claim_supported,
    _split_sentences,
)
from src import casestudies


class TestFailClosed(unittest.TestCase):
    """Rework acceptance 1: with no stored studies, every claim REFUSES."""

    def test_empty_store_refuses_claim(self):
        """With no stored page, a body naming a study with a figure REFUSES."""
        with mock.patch.object(casestudies, '_STUDIES_DIR',
                               tempfile.mkdtemp()):
            violations = case_study_violations(
                "Infinum grew from 70 to 350 people using Productive.")
        self.assertTrue(len(violations) > 0,
                        "Expected refusal with empty store, got pass")
        rules = [v[0] for v in violations]
        self.assertIn("case_study_unsupported", rules)
        messages = [v[1] for v in violations]
        self.assertTrue(any("No stored page" in m for m in messages),
                        "Refusal should name the missing page")

    def test_empty_store_names_the_study(self):
        """The refusal says WHICH study has no page."""
        with mock.patch.object(casestudies, '_STUDIES_DIR',
                               tempfile.mkdtemp()):
            violations = case_study_violations(
                "BICG achieved a 360-degree view.")
        messages = [v[1] for v in violations]
        self.assertTrue(any("BICG" in m for m in messages),
                        "Refusal should name BICG")


class TestClaimOnPagePasses(unittest.TestCase):
    """Acceptance 2: a claim that IS on the page passes."""

    def test_infinum_350_passes(self):
        """The Infinum page states 350+ people. A claim citing it passes."""
        study = casestudies.load_study("infinum")
        if study is None:
            self.skipTest("Infinum page not stored")
        page = study["page_text"]
        self.assertIn("350", page.lower().replace("+", " "),
                       "Precondition: 350 must be on the Infinum page")
        violations = case_study_violations(
            "Infinum plans resources for 350 people.")
        cs_unsupported = [v for v in violations
                          if v[0] == "case_study_unsupported"]
        self.assertEqual(cs_unsupported, [],
                         "Claim with figure from the page should pass")

    def test_claim_supported_by_single_sentence(self):
        """The binding is to ONE page sentence, not scattered tokens."""
        page = "Infinum has 420 employees. They are based in Zagreb."
        result = _claim_supported(
            "test", page, ["420"])
        self.assertIsNotNone(result)
        self.assertIn("420", result)


class TestClaimNotOnPageRefuses(unittest.TestCase):
    """Acceptance 3: a claim NOT on the page REFUSES."""

    def test_infinum_500_refuses(self):
        """Infinum page does not say 500. A claim asserting it REFUSES."""
        study = casestudies.load_study("infinum")
        if study is None:
            self.skipTest("Infinum page not stored")
        violations = case_study_violations(
            "Infinum achieved 500 percent ROI in the first quarter.")
        cs_unsupported = [v for v in violations
                          if v[0] == "case_study_unsupported"]
        self.assertTrue(len(cs_unsupported) > 0,
                        "500 is not on the Infinum page - should refuse")

    def test_infinum_70_from_operator_summary_refuses(self):
        """Acceptance 4 / Finding 1: operator_summary says 'grew from 70 to
        350' but 70 is not on the page. The claim REFUSES."""
        study = casestudies.load_study("infinum")
        if study is None:
            self.skipTest("Infinum page not stored")
        page_norm = " ".join(
            c for c in study["page_text"].lower() if c.isalnum() or c.isspace())
        tokens = set(page_norm.split())
        self.assertNotIn("70", tokens,
                         "Precondition: 70 must NOT be on the Infinum page")
        violations = case_study_violations(
            "Infinum grew from 70 to 350 people.")
        cs_unsupported = [v for v in violations
                          if v[0] == "case_study_unsupported"]
        self.assertTrue(len(cs_unsupported) > 0,
                        "70 is not on the page - should refuse even though "
                        "operator_summary says so")


class TestTwoStudiesRefuse(unittest.TestCase):
    """Acceptance 5: two case studies in one email REFUSE."""

    def test_two_studies_in_one_body(self):
        violations = case_study_violations(
            "Infinum grew to 350 people. BICG improved resource planning "
            "across 92 consultants.")
        rules = [v[0] for v in violations]
        self.assertIn("case_study_multiple", rules,
                       "Two studies in one body should refuse")

    def test_one_study_passes_the_multiple_check(self):
        """Naming only one study does not fire case_study_multiple."""
        violations = case_study_violations(
            "Infinum grew to 350 people using Productive.")
        rules = [v[0] for v in violations]
        self.assertNotIn("case_study_multiple", rules)


class TestNoMentionPasses(unittest.TestCase):
    """A body with no case-study mention passes this rule."""

    def test_no_study_mentioned(self):
        violations = case_study_violations(
            "Our platform helps teams manage resources effectively.")
        self.assertEqual(violations, [])


class TestStudyNameAlonePasses(unittest.TestCase):
    """Naming a study without specifics is allowed - nothing to trace."""

    def test_name_only_no_specifics(self):
        violations = case_study_violations(
            "Companies like Infinum use our platform.")
        cs_unsupported = [v for v in violations
                          if v[0] == "case_study_unsupported"]
        self.assertEqual(cs_unsupported, [],
                         "Name without specifics should not refuse")


class TestCaseStudyInCheckBatch(unittest.TestCase):
    """The rule is wired into check_batch, not just the standalone function."""

    def test_batch_refuses_unsupported_claim(self):
        """A lead with an unsupported case-study claim is in offenders."""
        leads = [{
            "id": "lead-1",
            "steps": [
                {"body": "Infinum achieved 500 percent ROI.",
                 "subject": "Test"},
                {"body": "Step 2.", "subject": "S2"},
                {"body": "Step 3.", "subject": "S3"},
                {"body": "Step 4.", "subject": "S4"},
                {"body": "Step 5.", "subject": "S5"},
            ],
        }]
        report = check_batch(leads, packs={"lead-1": {"facts": []}})
        self.assertIn("lead-1",
                       report["offenders"].get("case_study_unsupported", []))

    def test_batch_refuses_two_studies(self):
        """A lead naming two studies fires case_study_multiple."""
        leads = [{
            "id": "lead-2",
            "steps": [
                {"body": "Infinum grew to 350. BICG has 92 people.",
                 "subject": "Test"},
                {"body": "Step 2.", "subject": "S2"},
                {"body": "Step 3.", "subject": "S3"},
                {"body": "Step 4.", "subject": "S4"},
                {"body": "Step 5.", "subject": "S5"},
            ],
        }]
        report = check_batch(leads, packs={"lead-2": {"facts": []}})
        self.assertIn("lead-2",
                       report["offenders"].get("case_study_multiple", []))


class TestCloneTest(unittest.TestCase):
    """Rework acceptance 3: from a clean checkout, the rule still has its
    evidence and still refuses."""

    def test_studies_dir_is_in_docs_not_work(self):
        """The evidence is under docs/, not work/."""
        self.assertTrue(
            casestudies._STUDIES_DIR.endswith(
                os.path.join("docs", "evidence", "case-studies")),
            "Studies dir should be under docs/evidence/case-studies")

    def test_infinum_page_exists_in_tracked_path(self):
        """The Infinum page file exists in the tracked path."""
        path = os.path.join(casestudies._STUDIES_DIR, "infinum.json")
        self.assertTrue(os.path.isfile(path),
                        "Infinum page should exist at %s" % path)

    def test_infinum_500_still_refuses_from_stored_data(self):
        """Using the committed stored data, 500 is still refused."""
        violations = case_study_violations(
            "Infinum achieved 500 percent ROI.")
        cs_unsupported = [v for v in violations
                          if v[0] == "case_study_unsupported"]
        self.assertTrue(len(cs_unsupported) > 0)


class TestSentenceSplitting(unittest.TestCase):
    """The sentence splitter handles the formats we need."""

    def test_splits_on_period(self):
        sentences = _split_sentences("First. Second. Third.")
        self.assertEqual(len(sentences), 3)

    def test_splits_on_newline(self):
        sentences = _split_sentences("Line one\nLine two\nLine three")
        self.assertEqual(len(sentences), 3)

    def test_empty_input(self):
        self.assertEqual(_split_sentences(""), [])
        self.assertEqual(_split_sentences(None), [])


class TestRedaction(unittest.TestCase):
    """Stored pages have been redacted before committing."""

    def test_no_email_in_stored_pages(self):
        """No stored page contains an email address."""
        import re
        email_re = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
        for key in casestudies.KNOWN_STUDIES:
            study = casestudies.load_study(key)
            if study is None:
                continue
            emails = email_re.findall(study.get("page_text", ""))
            self.assertEqual(emails, [],
                             "Email found in %s: %s" % (key, emails))


if __name__ == "__main__":
    unittest.main()
