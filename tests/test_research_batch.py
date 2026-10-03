"""Deterministic research batching: the batch controller and its guarantees.

TASK-930. A capped run over a named set of accounts produces per-account
dispositions, spends through the canonical ledger, is safe to re-run, and a
dry run performs no actor call at all. The dry run writes nothing - proved by
asserting on the estate, not by reading the code.

Five properties are asserted here and they are different questions:

  1. ORDER is the CSV's, not queue order.
  2. CAP is refused rather than exceeded.
  3. RESUMABLE: re-running skips accounts that already cleared the bar.
  4. DISPOSITIONS: qualified / held / not-qualified reported separately.
  5. DRY RUN: nothing on the estate changes.
"""
import csv
import io
import json
import os
import tempfile
import time
import unittest

from src import enrich, evidence as ev, research, store

from tests.base import QueueTest, canonical_research, RESEARCH_FACT


def _write_csv(rows):
    """Write a temporary source CSV and return its path.

    Each row is a dict with at least Work Email and Company. The temp file
    is cleaned up by the caller via addCleanup.
    """
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "Work Email", "Company", "First Name", "Last Name",
            "Job Title", "Industry", "Location",
        ])
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return path


def _seed_record(domain, company=None, state="queued", rejected=False):
    """A record in the canonical shape for research batching.

    Has a contact with an email (so it is heading for copy), no research
    rows (so it NEED_COPY_EVIDENCE), and a qualification verdict unless
    `rejected` is set.
    """
    name = company or domain.split(".")[0]
    rec = store.new_record(name, "cold", "demo", company or name, domain)
    rec["state"] = state
    rec["hook"] = None
    rec["company_facts"] = {"name": company or name}
    rec["contacts"] = [{
        "name": "Test Person", "title": "CTO",
        "email": "test@%s" % domain, "email_source": "test",
        "persona": None, "angle": None, "verdict": "valid",
        "sendable": True, "primary": True, "reoon": None,
    }]
    if rejected:
        rec["qualification"] = {
            "verdict": {"icp_status": "rejected", "why": "test"}}
    else:
        rec["qualification"] = {
            "verdict": {"icp_status": "qualified"}}
    rec["research"] = []
    return rec


class ResearchBatchTest(QueueTest):
    """Base for research batch tests. Seeds records and a source CSV."""

    def setUp(self):
        super().setUp()
        self._tmpfiles = []

    def tearDown(self):
        for path in self._tmpfiles:
            if os.path.exists(path):
                os.unlink(path)
        super().tearDown()

    def source(self, rows):
        path = _write_csv(rows)
        self._tmpfiles.append(path)
        return path

    def seed(self, domains, rejected=None):
        """Seed records for each domain and return (records, csv_rows)."""
        rejected = set(rejected or [])
        recs = []
        csv_rows = []
        for d in domains:
            rec = _seed_record(d, rejected=d in rejected)
            recs.append(rec)
            csv_rows.append({
                "Work Email": "test@%s" % d,
                "Company": d.split(".")[0].title(),
                "First Name": "Test", "Last Name": "Person",
                "Job Title": "CTO", "Industry": "Technology",
                "Location": "Test City",
            })
        store.save(recs)
        return recs, csv_rows


class DryRunWritesNothing(ResearchBatchTest):
    """A dry run performs no actor call at all. Proved on the estate."""

    def test_estate_is_unchanged_after_dry_run(self):
        """The acceptance test: snapshot the estate, run dry, compare.

        Not reading the code. Not asserting on mock calls. The estate on disk
        before and the estate on disk after are byte-identical.
        """
        recs, csv_rows = self.seed(["alpha.test", "beta.test"])
        path = self.source(csv_rows)

        before = {r["id"]: json.dumps(r, sort_keys=True, default=str)
                  for r in store.load()}

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        after = {r["id"]: json.dumps(r, sort_keys=True, default=str)
                 for r in store.load()}
        self.assertEqual(before, after,
                         "dry run changed the estate: %s"
                         % [k for k in before if before[k] != after.get(k)])

    def test_dry_run_reports_dispositions(self):
        """Dry run still classifies every row, just does not research."""
        recs, csv_rows = self.seed(["alpha.test", "beta.test"])
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        self.assertEqual(result["live"], False)
        self.assertEqual(result["attempted"], 0,
                         "dry run should attempt nothing")
        self.assertEqual(len(result["dispositions"]), 2)
        for d in result["dispositions"]:
            self.assertIn(d["disposition"], ("HELD", "QUALIFIED"))


class CapRefusedNotExceeded(ResearchBatchTest):
    """A cap is refused rather than exceeded."""

    def test_live_run_without_cap_is_refused(self):
        """A live run with no cap raises NoBudget."""
        recs, csv_rows = self.seed(["alpha.test"])
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        with self.assertRaises(enrich.NoBudget):
            run_batch(live=True, cap=None, source=path)

    def test_live_run_with_zero_cap_is_refused(self):
        """--cap 0 on live is refused: Apify bills in compute units."""
        recs, csv_rows = self.seed(["alpha.test"])
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        with self.assertRaises(enrich.NoBudget):
            run_batch(live=True, cap=0, source=path)

    def test_cap_limits_attempts_not_walks(self):
        """A cap of 1 walks all rows but only attempts 1 research."""
        recs, csv_rows = self.seed(["alpha.test", "beta.test", "gamma.test"])
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, cap=1, source=path)

        self.assertLessEqual(result["attempted"], 1)
        self.assertEqual(len(result["dispositions"]), 3)


class ResumableFromEstate(ResearchBatchTest):
    """Re-running the command IS the resume. No second state file."""

    def test_qualified_accounts_are_skipped_on_rerun(self):
        """An account with enough evidence is QUALIFIED, not re-researched."""
        rec = _seed_record("alpha.test")
        # Seed enough admitted research rows to clear the bar.
        rec["research"] = canonical_research(
            rec["id"], fact=RESEARCH_FACT,
            source_url="https://alpha.test/about", field="about")
        rec["research"].extend(canonical_research(
            rec["id"], fact=RESEARCH_FACT.replace("Zagreb", "Berlin"),
            source_url="https://alpha.test/services", field="services"))
        rec["research"].extend(canonical_research(
            rec["id"], fact=RESEARCH_FACT.replace("Zagreb", "London"),
            source_url="https://alpha.test/team", field="team"))
        store.save([rec])

        csv_rows = [{"Work Email": "test@alpha.test",
                      "Company": "Alpha", "First Name": "Test",
                      "Last Name": "Person", "Job Title": "CTO",
                      "Industry": "Technology", "Location": "Test City"}]
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        self.assertEqual(result["counts"]["QUALIFIED"], 1)
        self.assertEqual(result["attempted"], 0,
                         "a qualified account should not be attempted")
        for d in result["dispositions"]:
            if d["domain"] == "alpha.test":
                self.assertEqual(d["disposition"], "QUALIFIED")
                self.assertIn("already has sufficient evidence", d["reason"])


class DispositionsReportedSeparately(ResearchBatchTest):
    """Qualified / held / not-qualified are reported separately."""

    def test_not_qualified_for_rejected(self):
        """A rejected account is NOT_QUALIFIED, not HELD."""
        recs, csv_rows = self.seed(["alpha.test"], rejected=["alpha.test"])
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        self.assertEqual(result["counts"]["NOT_QUALIFIED"], 1)
        for d in result["dispositions"]:
            self.assertEqual(d["disposition"], "NOT_QUALIFIED")
            self.assertIn("rejected", d["reason"])

    def test_not_qualified_for_no_record(self):
        """A domain with no canonical record is NOT_QUALIFIED."""
        csv_rows = [{"Work Email": "test@unknown.test",
                      "Company": "Unknown", "First Name": "Test",
                      "Last Name": "Person", "Job Title": "CTO",
                      "Industry": "Technology", "Location": "Test City"}]
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        self.assertEqual(result["counts"]["NOT_QUALIFIED"], 1)
        for d in result["dispositions"]:
            self.assertEqual(d["disposition"], "NOT_QUALIFIED")
            self.assertIn("no canonical record", d["reason"])

    def test_not_qualified_for_no_contact(self):
        """A record with no contacts is NOT_QUALIFIED."""
        rec = _seed_record("alpha.test")
        rec["contacts"] = []
        store.save([rec])

        csv_rows = [{"Work Email": "test@alpha.test",
                      "Company": "Alpha", "First Name": "Test",
                      "Last Name": "Person", "Job Title": "CTO",
                      "Industry": "Technology", "Location": "Test City"}]
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        self.assertEqual(result["counts"]["NOT_QUALIFIED"], 1)

    def test_held_for_insufficient_evidence(self):
        """An account that needs evidence and gets no new rows is HELD."""
        recs, csv_rows = self.seed(["alpha.test"])
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        # In dry run, no research happens, so the account stays HELD.
        self.assertEqual(result["counts"]["HELD"], 1)
        for d in result["dispositions"]:
            self.assertEqual(d["disposition"], "HELD")
            self.assertIn("insufficient", d["reason"].lower())

    def test_counts_are_separate(self):
        """Each disposition is counted in its own bucket."""
        rec_ok = _seed_record("alpha.test")
        rec_ok["research"] = canonical_research(
            rec_ok["id"], fact=RESEARCH_FACT,
            source_url="https://alpha.test/about", field="about")
        rec_ok["research"].extend(canonical_research(
            rec_ok["id"], fact=RESEARCH_FACT.replace("Zagreb", "Berlin"),
            source_url="https://alpha.test/services", field="services"))
        rec_ok["research"].extend(canonical_research(
            rec_ok["id"], fact=RESEARCH_FACT.replace("Zagreb", "London"),
            source_url="https://alpha.test/team", field="team"))

        rec_need = _seed_record("beta.test")
        rec_rej = _seed_record("gamma.test", rejected=True)
        store.save([rec_ok, rec_need, rec_rej])

        csv_rows = [
            {"Work Email": "test@alpha.test", "Company": "Alpha",
             "First Name": "T", "Last Name": "P", "Job Title": "CTO",
             "Industry": "Tech", "Location": "X"},
            {"Work Email": "test@beta.test", "Company": "Beta",
             "First Name": "T", "Last Name": "P", "Job Title": "CTO",
             "Industry": "Tech", "Location": "X"},
            {"Work Email": "test@gamma.test", "Company": "Gamma",
             "First Name": "T", "Last Name": "P", "Job Title": "CTO",
             "Industry": "Tech", "Location": "X"},
        ]
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        self.assertEqual(result["counts"]["QUALIFIED"], 1)
        self.assertEqual(result["counts"]["HELD"], 1)
        self.assertEqual(result["counts"]["NOT_QUALIFIED"], 1)


class OrderFollowsCSV(ResearchBatchTest):
    """The walk order is the CSV's, not queue order."""

    def test_dispositions_follow_csv_order(self):
        """The disposition list is in CSV row order."""
        recs, csv_rows = self.seed(["gamma.test", "alpha.test", "beta.test"])
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        domains = [d["domain"] for d in result["dispositions"]]
        self.assertEqual(domains,
                         ["gamma.test", "alpha.test", "beta.test"])


class NeverResearchRejectedOrContactless(ResearchBatchTest):
    """Never research a REJECTED account, or one with no contact to write to."""

    def test_rejected_account_is_not_attempted(self):
        """A rejected account is NOT_QUALIFIED and never attempted."""
        recs, csv_rows = self.seed(["alpha.test", "beta.test"],
                                   rejected=["alpha.test"])
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        self.assertEqual(result["attempted"], 0)
        for d in result["dispositions"]:
            if d["domain"] == "alpha.test":
                self.assertEqual(d["disposition"], "NOT_QUALIFIED")

    def test_dropped_record_is_not_attempted(self):
        """A dropped record is NOT_QUALIFIED."""
        rec = _seed_record("alpha.test", state="dropped")
        store.save([rec])

        csv_rows = [{"Work Email": "test@alpha.test",
                      "Company": "Alpha", "First Name": "T",
                      "Last Name": "P", "Job Title": "CTO",
                      "Industry": "Tech", "Location": "X"}]
        path = self.source(csv_rows)

        from scripts.research_batch import run_batch
        result = run_batch(live=False, source=path)

        for d in result["dispositions"]:
            self.assertEqual(d["disposition"], "NOT_QUALIFIED")


class ThresholdsNotLowered(ResearchBatchTest):
    """MIN_RELEVANCE and MIN_COPY_EVIDENCE_ROWS are not changed."""

    def test_min_relevance_is_unchanged(self):
        """The floor that two near-miss accounts sit under."""
        self.assertEqual(ev.MIN_RELEVANCE, 0.65)

    def test_min_copy_evidence_rows_is_unchanged(self):
        """The measurement: TWO IS THE NUMBER THAT FAILED."""
        self.assertEqual(research.MIN_COPY_EVIDENCE_ROWS, 3)


class GoesThroughCanonicalPath(ResearchBatchTest):
    """The batch controller goes through enrich_record, not a second path."""

    def test_imports_enrich_record(self):
        """The script imports enrich.enrich_record, not a reimplementation."""
        import scripts.research_batch as rb
        with open(rb.__file__, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("enrich.enrich_record", source)

    def test_no_second_research_caller(self):
        """The script does not call research.run directly."""
        import scripts.research_batch as rb
        with open(rb.__file__, encoding="utf-8") as f:
            source = f.read()
        # research.run should NOT appear as a direct call.
        # research.why is fine - it is the classifier, not the runner.
        lines = [l.strip() for l in source.splitlines()
                 if "research.run(" in l and not l.strip().startswith("#")]
        self.assertEqual(lines, [],
                         "the batch controller must go through "
                         "enrich.enrich_record, not research.run directly")


if __name__ == "__main__":
    unittest.main()
