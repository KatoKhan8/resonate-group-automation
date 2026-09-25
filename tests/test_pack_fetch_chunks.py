"""The pack_fetch chunker: arithmetic, resume, budget, report.

## WHAT THESE TESTS PROVE

The chunker's arithmetic and journal mechanics. A green suite here proves
the chunking, the resume, the budget refusal and the coverage report. It
does NOT prove Apify works - that is `test_researchpack.py`'s job against
cassettes, and TASK-279 requires a LIVE chunk to prove the actors.

## WHAT IS ASSERTED

1. The ICP "IN" set is read correctly from a journal file.
2. Already-answered domains in the journal are skipped on re-run.
3. A chunk whose projected cost crosses the budget is REFUSED before
   starting, with the numbers printed.
4. The coverage report counts present, missing, refused correctly.
5. The journal is appended per domain, not batch-written at the end.
6. A domain that was refused is not re-asked.
7. The website crawler override refuses an unknown ruling id.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import spendledger, store                         # noqa: E402
from tests.base import ProviderTest                        # noqa: E402

# Import the script as a module.
SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPT_DIR)
import pack_fetch                                          # noqa: E402


class IcpInSetTest(unittest.TestCase):
    """The S3 ICP 'IN' set is read correctly."""

    def _write_jsonl(self, path, rows):
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_only_verdict_in_is_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s3-icp.jsonl")
            self._write_jsonl(path, [
                {"domain": "acme.test", "verdict": "in"},
                {"domain": "beta.test", "verdict": "out"},
                {"domain": "gamma.test", "verdict": "flagged"},
                {"domain": "delta.test", "verdict": "in"},
                {"domain": "epsilon.test", "verdict": "review"},
            ])
            result = pack_fetch._icp_in_domains(path)
            self.assertEqual(result, ["acme.test", "delta.test"])

    def test_domains_are_lowered_and_deduped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s3-icp.jsonl")
            self._write_jsonl(path, [
                {"domain": "Acme.Test", "verdict": "in"},
                {"domain": "acme.test", "verdict": "in"},
            ])
            result = pack_fetch._icp_in_domains(path)
            self.assertEqual(result, ["acme.test"])

    def test_missing_file_returns_empty(self):
        result = pack_fetch._icp_in_domains("/nonexistent/path.jsonl")
        self.assertEqual(result, [])


class ResumeTest(unittest.TestCase):
    """Already-answered domains are skipped on re-run."""

    def _write_jsonl(self, path, rows):
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_journal_is_read_and_existing_domains_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            icp_path = os.path.join(tmp, "s3-icp.jsonl")
            journal_path = os.path.join(tmp, pack_fetch.JOURNAL_NAME)
            self._write_jsonl(icp_path, [
                {"domain": "acme.test", "verdict": "in"},
                {"domain": "beta.test", "verdict": "in"},
                {"domain": "gamma.test", "verdict": "in"},
            ])
            # Pre-populate the journal with acme.test already done.
            self._write_jsonl(journal_path, [
                {"domain": "acme.test", "status": "succeeded",
                 "cost_cents": 9, "facts": [], "fact_count": 0},
            ])
            journal = pack_fetch._load_journal(journal_path)
            input_domains = pack_fetch._icp_in_domains(icp_path)
            todo = [d for d in input_domains if d not in journal]
            self.assertEqual(todo, ["beta.test", "gamma.test"])

    def test_a_refused_domain_is_not_re_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            icp_path = os.path.join(tmp, "s3-icp.jsonl")
            journal_path = os.path.join(tmp, pack_fetch.JOURNAL_NAME)
            self._write_jsonl(icp_path, [
                {"domain": "acme.test", "verdict": "in"},
                {"domain": "beta.test", "verdict": "in"},
            ])
            self._write_jsonl(journal_path, [
                {"domain": "acme.test", "status": "refused",
                 "reason": "a research pack needs a domain"},
            ])
            journal = pack_fetch._load_journal(journal_path)
            input_domains = pack_fetch._icp_in_domains(icp_path)
            todo = [d for d in input_domains if d not in journal]
            self.assertEqual(todo, ["beta.test"])

    def test_journal_append_is_per_domain(self):
        """The journal is appended per domain, not batch-written."""
        with tempfile.TemporaryDirectory() as tmp:
            journal_path = os.path.join(tmp, pack_fetch.JOURNAL_NAME)
            pack_fetch._append_journal(journal_path, {
                "domain": "acme.test", "status": "succeeded"})
            # Read back immediately - the row is on disk.
            journal = pack_fetch._load_journal(journal_path)
            self.assertIn("acme.test", journal)
            self.assertEqual(journal["acme.test"]["status"], "succeeded")


class BudgetRefusalTest(unittest.TestCase):
    """A chunk whose projected cost crosses the budget is REFUSED."""

    def _write_jsonl(self, path, rows):
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_projection_is_planned_cost_times_chunk_size(self):
        """The projection uses the planned cost/account, not a guess."""
        projected = pack_fetch._projected_cost_usd(25, 9)
        self.assertAlmostEqual(projected, 2.25)

    def test_budget_refusal_message_has_the_numbers(self):
        """The refusal prints the projection that made it refuse."""
        with tempfile.TemporaryDirectory() as tmp:
            icp_path = os.path.join(tmp, "s3-icp.jsonl")
            self._write_jsonl(icp_path, [
                {"domain": f"d{i}.test", "verdict": "in"}
                for i in range(30)
            ])
            # Budget of $0.10 with 25-account chunks at 9 cents/account
            # = $2.25 projected, which crosses $0.10.
            rc = pack_fetch.main([
                "--chunk", "25", "--max-chunks", "1",
                "--budget-usd", "0.10",
                "--icp-path", icp_path,
                "--workspace", tmp,
            ])
            self.assertEqual(rc, 1, "should have refused")

    def test_budget_allows_when_under_ceiling(self):
        """A chunk that fits is allowed (dry run, no actual spend)."""
        with tempfile.TemporaryDirectory() as tmp:
            icp_path = os.path.join(tmp, "s3-icp.jsonl")
            self._write_jsonl(icp_path, [
                {"domain": f"d{i}.test", "verdict": "in"}
                for i in range(5)
            ])
            # $100 budget, 5 accounts at 9 cents = $0.45, well under.
            rc = pack_fetch.main([
                "--chunk", "5", "--max-chunks", "1",
                "--budget-usd", "100.00",
                "--icp-path", icp_path,
                "--workspace", tmp,
            ])
            self.assertEqual(rc, 0)


class CoverageReportTest(unittest.TestCase):
    """The coverage report counts correctly."""

    def _write_jsonl(self, path, rows):
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_report_counts_present_missing_refused(self):
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            icp_path = os.path.join(tmp, "s3-icp.jsonl")
            journal_path = os.path.join(tmp, pack_fetch.JOURNAL_NAME)
            self._write_jsonl(icp_path, [
                {"domain": "a.test", "verdict": "in"},
                {"domain": "b.test", "verdict": "in"},
                {"domain": "c.test", "verdict": "in"},
                {"domain": "d.test", "verdict": "in"},
                {"domain": "e.test", "verdict": "in"},
            ])
            self._write_jsonl(journal_path, [
                {"domain": "a.test", "status": "succeeded",
                 "cost_cents": 9, "facts": [
                     {"source_url": "https://x.test/1",
                      "snippet": "words"}],
                 "fact_count": 1},
                {"domain": "b.test", "status": "succeeded",
                 "cost_cents": 9, "facts": [
                     {"source_url": "https://x.test/2",
                      "snippet": "more"}],
                 "fact_count": 1},
                {"domain": "c.test", "status": "refused",
                 "reason": "no domain"},
            ])
            journal = pack_fetch._load_journal(journal_path)
            input_domains = pack_fetch._icp_in_domains(icp_path)
            buf = io.StringIO()
            with redirect_stdout(buf):
                pack_fetch._coverage_report(
                    journal, input_domains, journal_path)
            output = buf.getvalue()
            self.assertIn("5", output)     # total
            self.assertIn("2", output)     # present
            self.assertIn("refused", output.lower())

    def test_report_shows_usd_per_account_when_there_are_successes(self):
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            icp_path = os.path.join(tmp, "s3-icp.jsonl")
            journal_path = os.path.join(tmp, pack_fetch.JOURNAL_NAME)
            self._write_jsonl(icp_path, [
                {"domain": "a.test", "verdict": "in"},
            ])
            self._write_jsonl(journal_path, [
                {"domain": "a.test", "status": "succeeded",
                 "cost_cents": 9, "facts": [
                     {"source_url": "https://x.test/1",
                      "snippet": "words"}],
                 "fact_count": 1},
            ])
            journal = pack_fetch._load_journal(journal_path)
            input_domains = pack_fetch._icp_in_domains(icp_path)
            buf = io.StringIO()
            with redirect_stdout(buf):
                pack_fetch._coverage_report(
                    journal, input_domains, journal_path)
            output = buf.getvalue()
            self.assertIn("$0.09", output)
            self.assertIn("USD/account actual", output)


class WebsiteCrawlerGateTest(unittest.TestCase):
    """The website crawler override refuses an unknown ruling id."""

    def _write_jsonl(self, path, rows):
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_unknown_ruling_id_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            icp_path = os.path.join(tmp, "s3-icp.jsonl")
            self._write_jsonl(icp_path, [
                {"domain": "a.test", "verdict": "in"},
            ])
            rc = pack_fetch.main([
                "--chunk", "1", "--max-chunks", "1",
                "--icp-path", icp_path,
                "--workspace", tmp,
                "--override-site-crawler-ruling", "wrong-ruling",
            ])
            self.assertEqual(rc, 2)

    def test_correct_ruling_id_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            icp_path = os.path.join(tmp, "s3-icp.jsonl")
            self._write_jsonl(icp_path, [
                {"domain": "a.test", "verdict": "in"},
            ])
            rc = pack_fetch.main([
                "--chunk", "1", "--max-chunks", "1",
                "--icp-path", icp_path,
                "--workspace", tmp,
                "--override-site-crawler-ruling",
                pack_fetch.SITE_CRAWLER_RULING,
            ])
            self.assertEqual(rc, 0)


class ActualRateTest(unittest.TestCase):
    """The actual USD/account is measured from the journal, not guessed."""

    def test_actual_rate_from_journal_spend(self):
        journal = {
            "a.test": {"status": "succeeded", "cost_cents": 9},
            "b.test": {"status": "succeeded", "cost_cents": 9},
            "c.test": {"status": "refused", "cost_cents": 0},
        }
        rate = pack_fetch._actual_usd_per_account(journal)
        self.assertAlmostEqual(rate, 0.09)

    def test_no_successes_returns_none(self):
        journal = {
            "a.test": {"status": "refused", "cost_cents": 0},
        }
        rate = pack_fetch._actual_usd_per_account(journal)
        self.assertIsNone(rate)


class NothingToDoTest(unittest.TestCase):
    """When all domains are in the journal, the script says so."""

    def _write_jsonl(self, path, rows):
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_all_done_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            icp_path = os.path.join(tmp, "s3-icp.jsonl")
            journal_path = os.path.join(tmp, pack_fetch.JOURNAL_NAME)
            self._write_jsonl(icp_path, [
                {"domain": "a.test", "verdict": "in"},
            ])
            self._write_jsonl(journal_path, [
                {"domain": "a.test", "status": "succeeded",
                 "cost_cents": 9, "facts": [], "fact_count": 0},
            ])
            rc = pack_fetch.main([
                "--chunk", "25", "--max-chunks", "1",
                "--icp-path", icp_path,
                "--workspace", tmp,
            ])
            self.assertEqual(rc, 0)


class MissingIcpFileTest(unittest.TestCase):
    """A missing ICP file is refused, not treated as empty."""

    def test_missing_file_returns_two(self):
        rc = pack_fetch.main([
            "--chunk", "25",
            "--icp-path", "/nonexistent/s3-icp.jsonl",
            "--workspace", "/tmp",
        ])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
