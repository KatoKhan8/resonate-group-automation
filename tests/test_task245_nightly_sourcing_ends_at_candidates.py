"""TASK-245: nightly sourcing ends at candidates.

Five tests covering the acceptance criteria:
1. The full pipeline produces candidates, not enriched records.
2. Every AI-ARK call is faked - no real provider call.
3. The pipeline REFUSES to advance a candidate past the candidate list.
4. A rejected-then-resourced domain does not reappear as new.
5. The weekly export has the exact columns in the exact order.
"""
import datetime
import json
import os
import shutil
import tempfile
import unittest

from src import (candidatelist, candidateexport, geo, icp, store,
                 nightlysourcing)
from src.providers import aiark


class _TempDir:
    """Isolate file state for each test."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-task245-")
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(self.work, exist_ok=True)
        self._prev = {}
        for key in ("QUEUE", "CANDIDATES", "MX_CACHE"):
            self._prev[key] = os.environ.get(key)
        os.environ["QUEUE"] = os.path.join(self.work, "queue.jsonl")
        os.environ["CANDIDATES"] = os.path.join(self.work, "candidates.jsonl")
        os.environ["MX_CACHE"] = os.path.join(self.work, "mx-cache.json")
        # Create an empty queue file so store.load() works.
        with open(os.environ["QUEUE"], "w") as f:
            pass

    def tearDown(self):
        for key, val in self._prev.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        shutil.rmtree(self.tmp, ignore_errors=True)


# ----------------------------------------------------------- fake AI-ARK

def _fake_company(domain, company="Acme", headcount=50, industry="Marketing",
                  country="United Kingdom", website=None, description=None,
                  services=None, specialties=None):
    desc = description or (
        f"{company} is a digital marketing agency specialising in "
        f"SEO, content delivery and project management for clients"
    )
    return {
        "domain": domain,
        "company": company,
        "headcount": headcount,
        "industry": industry,
        "country": country,
        "website": website or f"https://{domain}",
        "description": desc,
        "services": services or ["digital marketing", "seo",
                                 "project delivery"],
        "specialties": specialties or ["campaign management",
                                       "client portfolio"],
    }


def _fake_search(rows_per_page=None):
    """A fake company_search that returns canned data."""
    if rows_per_page is None:
        rows_per_page = [
            _fake_company("alpha.test", "Alpha Corp", 50, "Marketing",
                          "United Kingdom"),
            _fake_company("beta.test", "Beta Ltd", 30, "Consulting",
                          "Germany"),
            _fake_company("gamma.test", "Gamma GmbH", 10, "Software",
                          "Germany"),
        ]
    calls = []

    def search(**kwargs):
        calls.append(kwargs)
        return list(rows_per_page)

    search.calls = calls
    return search


def _fake_mx_resolve(domain):
    """A fake MX resolve that always returns Google."""
    return ["aspmx.l.google.com"]


def _fake_mx_resolve_blocked(domain):
    """A fake MX resolve that returns a blocked gateway."""
    return ["mx.proofpoint.com"]


def _fake_mx_resolve_dns_failure(domain):
    """A fake MX resolve that raises (DNS failure)."""
    raise OSError("DNS timeout")


# ----------------------------------------------------------- the tests

class TestPipelineProducesCandidates(_TempDir, unittest.TestCase):
    """The full pipeline produces candidates with the right shape."""

    def test_full_pipeline_dry_run(self):
        search = _fake_search()
        report = nightlysourcing.run(
            config={"icp": {"markets": ["UK", "Germany"]}},
            search_fn=search,
            resolve_fn=_fake_mx_resolve,
            live=False,
        )
        self.assertIn("stages", report)
        self.assertEqual(report["stages"]["source"]["output"], 3)
        self.assertGreaterEqual(report["stages"]["candidate"]["output"], 0)
        self.assertFalse(report["live"])

    def test_full_pipeline_live_appends(self):
        search = _fake_search()
        report = nightlysourcing.run(
            config={"icp": {"markets": ["UK", "Germany"]}},
            search_fn=search,
            resolve_fn=_fake_mx_resolve,
            live=True,
        )
        self.assertTrue(report["live"])
        candidates = candidatelist.load()
        self.assertGreater(len(candidates), 0)
        for c in candidates:
            self.assertIn("domain", c)
            self.assertIn("why_matched", c)
            self.assertIn("prior_touch_status", c)
            self.assertEqual(c["state"], "new")

    def test_every_aiark_call_is_faked(self):
        """No real AI-ARK call escapes the test. The search_fn is injected."""
        search = _fake_search()
        nightlysourcing.run(
            search_fn=search,
            resolve_fn=_fake_mx_resolve,
            live=False,
        )
        self.assertGreater(len(search.calls), 0)


class TestPipelineRefusesToAdvancePastCandidates(_TempDir, unittest.TestCase):
    """The pipeline REFUSES to advance a candidate past the candidate list.

    This is the central acceptance test: the run() function's source must
    not reference any person-level or verification endpoint.
    """

    def test_pipeline_refuses_to_advance(self):
        ok, violations = nightlysourcing.pipeline_refuses_to_advance_past_candidates()
        self.assertTrue(ok, f"pipeline references forbidden names: "
                            f"{violations}")

    def test_no_person_search_in_stages(self):
        """None of the five stages calls a people endpoint."""
        import inspect
        for stage_fn_name in ("_source_companies", "_icp_verdict",
                              "_mx_classify", "_local_collision",
                              "_to_candidate"):
            fn = getattr(nightlysourcing, stage_fn_name)
            source = inspect.getsource(fn)
            for forbidden in ("people_search", "email_finder", "find_email",
                              "contactout", "verification.verify"):
                self.assertNotIn(forbidden, source,
                                 f"{stage_fn_name} references {forbidden}")

    def test_candidate_has_no_contacts(self):
        """A candidate row has no contacts, no email, no LinkedIn."""
        search = _fake_search()
        nightlysourcing.run(
            search_fn=search,
            resolve_fn=_fake_mx_resolve,
            live=True,
        )
        for c in candidatelist.load():
            self.assertNotIn("contacts", c)
            self.assertNotIn("email", c)
            self.assertNotIn("linkedin", c)


class TestRejectedDomainDoesNotReappear(_TempDir, unittest.TestCase):
    """A rejected-then-resourced domain does not reappear as new."""

    def test_rejected_domain_stays_on_list(self):
        # Pre-populate the candidate list with a rejected domain.
        candidatelist.append({
            "domain": "alpha.test",
            "company": "Alpha Corp",
            "state": "rejected",
            "added_at": "2026-09-20T02:00:00+00:00",
        })
        # Now source it again.
        search = _fake_search()
        nightlysourcing.run(
            search_fn=search,
            resolve_fn=_fake_mx_resolve,
            live=True,
        )
        # The domain should appear exactly once on the list.
        all_candidates = candidatelist.load()
        alpha_rows = [c for c in all_candidates
                      if c.get("domain") == "alpha.test"]
        self.assertEqual(len(alpha_rows), 1,
                         "rejected domain reappeared as a second row")
        self.assertEqual(alpha_rows[0]["state"], "rejected",
                         "the original row was overwritten")

    def test_duplicate_domain_is_not_appended(self):
        candidatelist.append({
            "domain": "beta.test",
            "company": "Beta Ltd",
            "state": "new",
        })
        result = candidatelist.append({
            "domain": "beta.test",
            "company": "Beta Ltd v2",
            "state": "new",
        })
        self.assertFalse(result)
        rows = [c for c in candidatelist.load()
                if c.get("domain") == "beta.test"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["company"], "Beta Ltd")


class TestWeeklyExportColumns(_TempDir, unittest.TestCase):
    """The weekly export has the exact columns in the exact order."""

    def test_export_columns(self):
        expected = ["domain", "company", "headcount", "industry", "country",
                    "website", "why it matched", "prior-touch status"]
        self.assertEqual(candidateexport.EXPORT_COLUMNS, expected)

    def test_export_csv_shape(self):
        candidatelist.append({
            "domain": "export.test",
            "company": "Export Co",
            "headcount": 42,
            "industry": "Consulting",
            "country": "United Kingdom",
            "website": "https://export.test",
            "why_matched": "agency fit; 42 people",
            "prior_touch_status": "never_touched",
            "state": "new",
        })
        csv_text = candidateexport.build_csv()
        lines = csv_text.strip().split("\n")
        self.assertGreaterEqual(len(lines), 2)
        header = lines[0]
        self.assertIn("domain", header)
        self.assertIn("why it matched", header)
        self.assertIn("prior-touch status", header)

    def test_export_json_payload(self):
        candidatelist.append({
            "domain": "json.test",
            "company": "JSON Co",
            "headcount": 20,
            "industry": "Tech",
            "country": "Germany",
            "website": "https://json.test",
            "why_matched": "tech fit",
            "prior_touch_status": "never_touched",
            "state": "new",
        })
        payload = candidateexport.to_json_payload()
        self.assertEqual(len(payload), 1)
        row = payload[0]
        self.assertEqual(row["domain"], "json.test")
        self.assertIn("why it matched", row)
        self.assertIn("prior-touch status", row)

    def test_export_marks_candidates(self):
        candidatelist.append({
            "domain": "mark.test",
            "company": "Mark Co",
            "state": "new",
        })
        report, _csv = candidateexport.run(live=True,
                                           output_dir=self.work)
        self.assertEqual(report.get("marked_exported"), 1)
        rows = candidatelist.load()
        self.assertEqual(rows[0]["state"], "exported")


class TestDSTScheduling(_TempDir, unittest.TestCase):
    """The schedule is stated in Zagreb time and moves with DST."""

    def test_nightly_utc_moment_is_zagreb_0200(self):
        # 2026-07-15 is CEST (UTC+2), so 02:00 Zagreb = 00:00 UTC.
        date = datetime.date(2026, 7, 15)
        utc = nightlysourcing.nightly_utc_moment(date)
        self.assertEqual(utc.hour, 0)
        self.assertEqual(utc.minute, 0)

    def test_nightly_utc_moment_winter(self):
        # 2026-12-15 is CET (UTC+1), so 02:00 Zagreb = 01:00 UTC.
        date = datetime.date(2026, 12, 15)
        utc = nightlysourcing.nightly_utc_moment(date)
        self.assertEqual(utc.hour, 1)
        self.assertEqual(utc.minute, 0)

    def test_export_utc_moment_is_zagreb_0700(self):
        # 2026-09-21 is CEST (UTC+2), so 07:00 Zagreb = 05:00 UTC.
        date = datetime.date(2026, 9, 21)
        utc = nightlysourcing.export_utc_moment(date)
        self.assertEqual(utc.hour, 5)
        self.assertEqual(utc.minute, 0)

    def test_is_export_day_monday(self):
        # 2026-09-21 is a Monday.
        self.assertTrue(nightlysourcing.is_export_day(
            datetime.date(2026, 9, 21)))

    def test_is_export_day_not_tuesday(self):
        # 2026-09-22 is a Tuesday.
        self.assertFalse(nightlysourcing.is_export_day(
            datetime.date(2026, 9, 22)))

    def test_no_hardcoded_utc_hour(self):
        """The UTC hour is derived from geo.zone, never a literal."""
        import inspect
        source = inspect.getsource(nightlysourcing.nightly_utc_moment)
        self.assertNotIn("= 0", source.split("tzinfo=tz")[0].split("\n")[-1])
        self.assertIn("geo.zone", source)


class TestMXStageDiscipline(_TempDir, unittest.TestCase):
    """S4b MX: known_allowed and unknown_provider survive; others do not.

    THE ICP VERDICT IS STUBBED TO QUALIFIED HERE, DELIBERATELY. These tests are
    about the MX stage, and MX only ever sees what ICP passed. Under the real
    default config the fixture agency scores 44.0 and lands on REVIEW, which
    since ISSUE-019 no longer survives S3 - so without this stub nothing would
    reach MX and every assertion below would pass or fail for the wrong reason.
    Stubbing the upstream verdict keeps these tests measuring MX rather than
    silently measuring the ICP threshold.
    """

    def setUp(self):
        super().setUp()
        self._real_score = icp.score
        icp.score = lambda rec, config=None: {
            "icp_status": icp.QUALIFIED, "icp_score": 90.0, "criteria": {}}

    def tearDown(self):
        icp.score = self._real_score
        super().tearDown()

    def test_known_allowed_survives(self):
        search = _fake_search([
            _fake_company("good.test", "Good Co", 50, "Marketing",
                          "United Kingdom"),
        ])
        report = nightlysourcing.run(
            search_fn=search,
            resolve_fn=_fake_mx_resolve,
            live=True,
        )
        self.assertGreater(report["stages"]["mx"]["output"], 0)

    def test_blocked_does_not_survive(self):
        search = _fake_search([
            _fake_company("blocked.test", "Blocked Co", 50, "Marketing",
                          "United Kingdom"),
        ])
        report = nightlysourcing.run(
            search_fn=search,
            resolve_fn=_fake_mx_resolve_blocked,
            live=True,
        )
        self.assertEqual(report["stages"]["mx"]["output"], 0)

    def test_dns_failure_is_held_not_dropped(self):
        search = _fake_search([
            _fake_company("dnsfail.test", "DNS Co", 50, "Marketing",
                          "United Kingdom"),
        ])
        report = nightlysourcing.run(
            search_fn=search,
            resolve_fn=_fake_mx_resolve_dns_failure,
            live=True,
        )
        self.assertEqual(report["stages"]["mx"]["output"], 0)
        # dns_failure is HELD, not silently dropped.
        self.assertEqual(report["stages"]["mx"]["dropped"], 1)


class TestICPStageDiscipline(_TempDir, unittest.TestCase):
    """S3 ICP: **only QUALIFIED survives.** REVIEW is routed to enrichment.

    Was "only qualified/review survive" until ISSUE-019, where passing REVIEW
    put a 130,377-employee bank at `icp_score 0.0` into a client export.
    """

    def test_small_company_rejected(self):
        """Headcount < 20 should be rejected by ICP."""
        search = _fake_search([
            _fake_company("tiny.test", "Tiny Co", 5, "Marketing",
                          "United Kingdom"),
        ])
        report = nightlysourcing.run(
            search_fn=search,
            resolve_fn=_fake_mx_resolve,
            live=True,
        )
        # Tiny company should not survive ICP.
        candidates = candidatelist.load()
        tiny = [c for c in candidates if c["domain"] == "tiny.test"]
        self.assertEqual(len(tiny), 0)


class TestCostReporting(_TempDir, unittest.TestCase):
    """Credit spend is REPORTED, NEVER GATED."""

    def test_report_includes_credits(self):
        search = _fake_search()
        report = nightlysourcing.run(
            search_fn=search,
            resolve_fn=_fake_mx_resolve,
            live=False,
        )
        self.assertIn("credits_spent", report)
        self.assertIn("credits_per_candidate", report)

    def test_rate_limit_does_not_halt(self):
        """A ProviderError in sourcing stops sourcing, not the pipeline."""
        call_count = [0]

        def flaky_search(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                from src.providers import ProviderError
                raise ProviderError("rate limited")
            return []

        report = nightlysourcing.run(
            search_fn=flaky_search,
            resolve_fn=_fake_mx_resolve,
            live=False,
        )
        self.assertIn("stages", report)
        self.assertIn("completed_at", report)


if __name__ == "__main__":
    unittest.main()
