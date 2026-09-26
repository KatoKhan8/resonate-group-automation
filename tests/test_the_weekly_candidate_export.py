"""The weekly candidate export. TASK-245.

Monday 07:00 Europe/Zagreb. Columns, exactly these, in this order:

    domain, company, headcount, industry, country, website,
    why it matched, prior-touch status

The export is the input to TASK-244's approval intake. Written so that task's
sheet writer and Slack poster can both consume it without reshaping.
"""
import csv
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import candidatelist, candidateexport, store


class ExportTestBase(unittest.TestCase):
    """Store isolation for export tests."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="rga-export-")
        self._restore_store = store.use_directory(
            os.path.join(self._tmp, "work"))
        self._candidates_env = os.environ.get("CANDIDATES")
        os.environ["CANDIDATES"] = os.path.join(
            self._tmp, "work", "candidates.jsonl")

    def tearDown(self):
        if self._candidates_env is None:
            os.environ.pop("CANDIDATES", None)
        else:
            os.environ["CANDIDATES"] = self._candidates_env
        self._restore_store()
        shutil.rmtree(self._tmp, ignore_errors=True)


def _qualified_candidate(domain, **overrides):
    base = {
        "domain": domain,
        "company": domain.split(".")[0].title(),
        "headcount": 45,
        "industry": "marketing",
        "country": "United Kingdom",
        "website": f"https://{domain}",
        "why_matched": "matches ICP criteria",
        "prior_touch_status": "never_touched",
        "state": "new",
        "icp_status": "qualified",
        "icp_score": 0.9,
        "_sourced_at": "2026-09-22T17:48:00Z",
    }
    base.update(overrides)
    return base


class TestExportColumns(ExportTestBase):
    """The export has exactly the right columns in the right order."""

    def test_the_columns_are_exact(self):
        expected = [
            "domain", "company", "headcount", "industry", "country",
            "website", "why it matched", "prior-touch status",
        ]
        self.assertEqual(candidateexport.EXPORT_COLUMNS, expected)

    def test_the_csv_header_matches(self):
        candidatelist.append(_qualified_candidate("header.test"))
        csv_text = candidateexport.build_csv()
        reader = csv.reader(io.StringIO(csv_text))
        header = next(reader)
        self.assertEqual(header, candidateexport.EXPORT_COLUMNS)


class TestExportContent(ExportTestBase):
    """The export carries the right data."""

    def test_a_single_candidate_renders_correctly(self):
        candidatelist.append(_qualified_candidate(
            "acme.test", company="Acme Corp", headcount=42,
            industry="advertising", country="United Kingdom",
            website="https://acme.test",
            why_matched="45-person ad agency in London"))
        csv_text = candidateexport.build_csv()
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["domain"], "acme.test")
        self.assertEqual(row["company"], "Acme Corp")
        self.assertEqual(row["headcount"], "42")
        self.assertEqual(row["industry"], "advertising")
        self.assertEqual(row["country"], "United Kingdom")
        self.assertEqual(row["website"], "https://acme.test")
        self.assertEqual(row["why it matched"],
                         "45-person ad agency in London")

    def test_prior_touch_status_appears_in_the_export(self):
        candidatelist.append(_qualified_candidate(
            "touched.test", prior_touch_status="touched 2026-08-15"))
        csv_text = candidateexport.build_csv()
        reader = csv.DictReader(io.StringIO(csv_text))
        row = next(reader)
        self.assertEqual(row["prior-touch status"], "touched 2026-08-15")

    def test_multiple_candidates_render(self):
        for i in range(3):
            candidatelist.append(_qualified_candidate(f"multi-{i}.test"))
        csv_text = candidateexport.build_csv()
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        self.assertEqual(len(rows), 3)


class TestExportableCandidates(ExportTestBase):
    """Only QUALIFIED, NEW, sourced-chain candidates are exportable."""

    def test_only_qualified_new_sourced_candidates_are_exportable(self):
        candidatelist.append(_qualified_candidate("good.test"))
        candidates = candidateexport.exportable_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["domain"], "good.test")

    def test_review_is_not_exportable(self):
        candidatelist.append(_qualified_candidate(
            "review.test", icp_status="review"))
        candidates = candidateexport.exportable_candidates()
        self.assertEqual(len(candidates), 0)

    def test_already_exported_is_not_exportable(self):
        candidatelist.append(_qualified_candidate(
            "done.test", state="exported"))
        candidates = candidateexport.exportable_candidates()
        self.assertEqual(len(candidates), 0)

    def test_legacy_without_provenance_refuses(self):
        """The retired pool raises, not returns empty."""
        candidatelist.append({
            "domain": "legacy.test", "state": "new",
            "icp_status": "qualified", "icp_score": 0.0,
            "headcount": 100000,
        })
        with self.assertRaises(candidateexport.RetiredCandidatePool):
            candidateexport.exportable_candidates()


class TestJSONPayload(ExportTestBase):
    """TASK-244's sheet writer consumes JSON."""

    def test_json_payload_has_the_right_keys(self):
        candidatelist.append(_qualified_candidate("json.test"))
        payload = candidateexport.to_json_payload()
        self.assertEqual(len(payload), 1)
        row = payload[0]
        expected_keys = set(candidateexport.EXPORT_COLUMNS)
        self.assertEqual(set(row.keys()), expected_keys)

    def test_json_payload_values_match(self):
        candidatelist.append(_qualified_candidate(
            "jsonval.test", company="JSON Corp"))
        payload = candidateexport.to_json_payload()
        self.assertEqual(payload[0]["company"], "JSON Corp")
        self.assertEqual(payload[0]["domain"], "jsonval.test")


class TestRunExport(ExportTestBase):
    """The run() function."""

    def test_dry_run_returns_csv_without_writing(self):
        candidatelist.append(_qualified_candidate("dryrun.test"))
        report, csv_text = candidateexport.run(live=False)
        self.assertEqual(report["candidates"], 1)
        self.assertIn("domain", csv_text)
        self.assertNotIn("path", report)

    def test_live_run_writes_csv_and_marks_exported(self):
        candidatelist.append(_qualified_candidate("liverun.test"))
        output_dir = os.path.join(self._tmp, "exports")
        report, csv_text = candidateexport.run(
            live=True, output_dir=output_dir)
        self.assertEqual(report["candidates"], 1)
        self.assertIn("path", report)
        self.assertTrue(os.path.exists(report["path"]))
        self.assertEqual(report["marked_exported"], 1)
        rows = candidatelist.load()
        self.assertEqual(rows[0]["state"], "exported")


class TestFormulaGuard(ExportTestBase):
    """A cell starting with = must not be evaluated by a spreadsheet."""

    def test_a_formula_leading_domain_is_guarded(self):
        candidatelist.append(_qualified_candidate(
            "=cmd.test", company="Normal"))
        csv_text = candidateexport.build_csv()
        reader = csv.DictReader(io.StringIO(csv_text))
        row = next(reader)
        domain = row["domain"]
        self.assertFalse(domain.startswith("="),
                         f"formula guard failed: {domain!r}")


if __name__ == "__main__":
    unittest.main()
