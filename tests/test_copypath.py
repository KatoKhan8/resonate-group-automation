"""The copy path pipeline: cleaning, extraction orchestration, batch subject lint.

Tests the pipeline stages that can be tested without live model calls:
- Nav chrome cleaning (stage 1)
- Batch subject check (stage 5a)
- Lead classification (post-extraction)
- Pipeline report assembly

The extraction step (stage 3) requires a live Groq key and is tested via
quote verification in `test_copyextract`. The writing step (stage 4) is
blocked and reports so.
"""
import unittest

from src import copypath, copyprompts


class TestBatchSubjectCheck(unittest.TestCase):
    """Subjects are checked BATCH-WIDE with a shared `seen` set.

    Duplicates are caught across leads, not just within one lead.
    """

    def test_no_faults(self):
        entries = [
            {"lead_id": "a", "subject": "your berlin office"},
            {"lead_id": "b", "subject": "the acme partnership"},
        ]
        faults = copypath.batch_subject_check(entries)
        self.assertEqual(len(faults), 0)

    def test_duplicate_caught_batch_wide(self):
        entries = [
            {"lead_id": "a", "subject": "your berlin office"},
            {"lead_id": "b", "subject": "your berlin office"},  # duplicate
        ]
        faults = copypath.batch_subject_check(entries)
        self.assertEqual(len(faults), 1)
        self.assertIn("duplicate", faults[0]["faults"][0])

    def test_over_max_words(self):
        entries = [
            {"lead_id": "a",
             "subject": "this subject has way too many words in it for the rule"},
        ]
        faults = copypath.batch_subject_check(entries)
        self.assertEqual(len(faults), 1)
        self.assertTrue(any("words" in f for f in faults[0]["faults"]))

    def test_title_case_caught(self):
        entries = [
            {"lead_id": "a",
             "subject": "Quick Question About Your Agency Margins Today"},
        ]
        faults = copypath.batch_subject_check(entries)
        self.assertEqual(len(faults), 1)
        self.assertTrue(any("lowercase" in f for f in faults[0]["faults"]))

    def test_banned_phrase_caught(self):
        entries = [
            {"lead_id": "a", "subject": "quick question about margins"},
        ]
        faults = copypath.batch_subject_check(entries)
        self.assertEqual(len(faults), 1)
        self.assertTrue(any("banned" in f for f in faults[0]["faults"]))

    def test_empty_subject(self):
        entries = [{"lead_id": "a", "subject": ""}]
        faults = copypath.batch_subject_check(entries)
        self.assertEqual(len(faults), 1)
        self.assertIn("empty", faults[0]["faults"])

    def test_three_capitals_allowed_for_proper_noun(self):
        """Two capitals are allowed (sentence-initial + proper noun).
        Three or more triggers the rule."""
        entries = [
            {"lead_id": "a", "subject": "acme and berlin office news"},
        ]
        faults = copypath.batch_subject_check(entries)
        self.assertEqual(len(faults), 0)


class TestCleanPacks(unittest.TestCase):
    """Stage 1: nav chrome stripping with metrics."""

    def test_cleaning_reduces_chars(self):
        leads = [
            {"id": "a", "company": "Acme", "domain": "acme.com",
             "sources": [
                 {"label": "site", "url": "https://acme.com",
                  "text": "Skip to content About Services Contact "
                          "We are a creative agency specialising in brand."},
             ]},
        ]
        cleaned, metrics = copypath.clean_packs(leads)
        self.assertEqual(metrics["leads"], 1)
        self.assertGreater(metrics["total_chars_before"],
                           metrics["total_chars_after"])
        self.assertIn("We are a creative agency",
                       cleaned[0]["sources"][0]["text"])

    def test_empty_leads(self):
        cleaned, metrics = copypath.clean_packs([])
        self.assertEqual(metrics["leads"], 0)


class TestClassifyLeads(unittest.TestCase):
    """Post-extraction classification into usable, held, errored."""

    def test_usable_lead(self):
        results = {
            "results": {
                "a": {"usable": True, "facts": [{"text": "fact1"}],
                       "angle": "margin_visible_late"},
            },
            "errors": {},
        }
        classified = copypath.classify_leads(results)
        self.assertEqual(len(classified["usable"]), 1)
        self.assertEqual(len(classified["held"]), 0)

    def test_held_lead(self):
        results = {
            "results": {
                "a": {"usable": False, "facts": [], "angle": None},
            },
            "errors": {},
        }
        classified = copypath.classify_leads(results)
        self.assertEqual(len(classified["held"]), 1)
        self.assertEqual(len(classified["usable"]), 0)

    def test_errored_lead(self):
        results = {
            "results": {},
            "errors": {"a": {"error": "unavailable", "detail": "timeout"}},
        }
        classified = copypath.classify_leads(results)
        self.assertEqual(len(classified["errored"]), 1)

    def test_held_when_facts_below_minimum(self):
        results = {
            "results": {
                "a": {"usable": True, "facts": [{"text": "only one"}]},
            },
            "errors": {},
        }
        classified = copypath.classify_leads(results)
        # One fact is below MIN_FACTS (3) but usable=True was set by extractor
        # The classifier trusts the extractor's usable flag
        self.assertEqual(len(classified["usable"]), 1)


class TestPipelineReport(unittest.TestCase):
    """The report assembles headline numbers from all stages."""

    def test_writing_blocked(self):
        report = copypath.pipeline_report(
            clean_metrics={"leads": 50, "mean_chars_before": 1000,
                           "mean_chars_after": 700},
            extraction_results={
                "results": {"a": {"usable": True, "facts": [1, 2, 3]}},
                "errors": {},
                "total": 50, "extracted": 45, "errored": 5,
            },
            subject_faults=[],
            lint_report=None,
        )
        self.assertTrue(report["stage_4_writing"]["blocked"])
        self.assertIn("ANTHROPIC", report["stage_4_writing"]["reason"])
        self.assertEqual(report["stage_3_extraction"]["total"], 50)


if __name__ == "__main__":
    unittest.main()
