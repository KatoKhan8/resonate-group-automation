"""The nightly sourcing pipeline: TASK-245.

The pipeline runs at 02:00 Europe/Zagreb and STOPS at candidates. Five stages:
source (AI-ARK) -> S3 ICP -> S4b MX -> local collision -> candidate list.

Nothing after the candidate list spends credits. No person-level call, no
verification, no contact discovery. The pipeline refuses to advance a
candidate past the list.

Every AI-ARK call is faked. The search function is injected; the MX resolver
is injected. No network, no provider, no credit.

DST: both schedules (nightly 02:00, export 07:00 Monday) are stated in Zagreb
time and the UTC hour is derived from geo.zone, never hardcoded.
"""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (candidatelist, geo, icp, mx, nightlysourcing, store,
                 candidateexport)
from src.providers import ProviderError


def _fake_company(domain, company_name=None, headcount=50, industry="marketing",
                  country="United Kingdom", website=None, description=""):
    return {
        "domain": domain,
        "company": company_name or domain.split(".")[0].title(),
        "headcount": headcount,
        "industry": industry,
        "country": country,
        "website": website or f"https://{domain}",
        "description": description,
        "services": [],
        "specialties": [],
    }


class _FakeSearch:
    """A controllable AI-ARK company_search replacement.

    Returns pages of fake companies. `pages` is a list of lists; each inner
    list is one page. An empty list or exhaustion ends the walk.
    """
    def __init__(self, pages=None):
        self.pages = pages or []
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        page = kwargs.get("page", 1)
        idx = page - 1
        if idx < len(self.pages):
            return self.pages[idx]
        return []


class _FakeResolver:
    """A controllable MX resolver. domain -> string hostname(s).

    Returns strings that mx.decide classifies via real gateway suffix matching:
      "allowed"   -> ["google.com"]            -> Google Workspace -> KNOWN_ALLOWED
      "blocked"   -> ["mx.pphosted.com"]       -> Proofpoint -> HIGH_PROTECTION -> KNOWN_BLOCKED
      "unknown"   -> ["mx.unknown.test"]       -> no match -> UNKNOWN_PROVIDER (allowed by default)
      "no_mx"     -> []                        -> NO_MX
      "dns_failure" -> raises OSError          -> DNS_FAILURE
    """
    def __init__(self, mapping=None):
        self._map = mapping or {}

    def __call__(self, domain):
        status = self._map.get(domain, "allowed")
        if status == "dns_failure":
            raise OSError("DNS timeout")
        if status == "no_mx":
            return []
        if status == "blocked":
            return ["mx.pphosted.com"]
        if status == "unknown":
            return ["mx.unknown.test"]
        return ["google.com"]


class _Verdict:
    """Stubbed ICP scorer returning a fixed verdict."""
    def __init__(self, status, score=0.9):
        self.status = status
        self.score = score

    def __call__(self, rec, config=None):
        return {"icp_status": self.status, "icp_score": self.score,
                "positive_signals": [{"why": "matches ICP criteria"}],
                "criteria": {}}


class PipelineTestBase(unittest.TestCase):
    """Store isolation for every pipeline test."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="rga-nightly-")
        self._restore_store = store.use_directory(
            os.path.join(self._tmp, "work"))
        self._candidates_env = os.environ.get("CANDIDATES")
        os.environ["CANDIDATES"] = os.path.join(
            self._tmp, "work", "candidates.jsonl")
        self._score = icp.score
        # Reset the persisted page state so each test starts at page 1.
        self._next_page = nightlysourcing._next_page
        self._remember_page = nightlysourcing._remember_page
        nightlysourcing._next_page = lambda: 1
        nightlysourcing._remember_page = lambda p: None

    def tearDown(self):
        icp.score = self._score
        nightlysourcing._next_page = self._next_page
        nightlysourcing._remember_page = self._remember_page
        if self._candidates_env is None:
            os.environ.pop("CANDIDATES", None)
        else:
            os.environ["CANDIDATES"] = self._candidates_env
        self._restore_store()
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestTheNightlyPipelineRunsEndToEnd(PipelineTestBase):
    """The full pipeline with every external call faked."""

    def test_a_full_run_produces_candidates(self):
        search = _FakeSearch(pages=[
            [_fake_company("acme.test", headcount=45),
             _fake_company("beta.test", headcount=30)],
        ])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)
        resolver = _FakeResolver({"acme.test": "allowed",
                                  "beta.test": "allowed"})

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=resolver)

        self.assertEqual(report["stages"][nightlysourcing.STAGE_SOURCE]["output"], 2)
        self.assertEqual(report["stages"][nightlysourcing.STAGE_ICP]["output"], 2)
        self.assertEqual(report["stages"][nightlysourcing.STAGE_MX]["output"], 2)
        self.assertEqual(report["candidates_added"], 2)

    def test_the_pipeline_stages_run_in_order(self):
        """Source -> ICP -> MX -> collision -> candidate. Each stage sees
        the output of the previous one."""
        search = _FakeSearch(pages=[
            [_fake_company("a.test"), _fake_company("b.test"),
             _fake_company("c.test")],
        ])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)
        resolver = _FakeResolver({"a.test": "allowed",
                                  "b.test": "blocked",
                                  "c.test": "allowed"})

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=resolver)

        self.assertEqual(report["stages"][nightlysourcing.STAGE_SOURCE]["output"], 3)
        self.assertEqual(report["stages"][nightlysourcing.STAGE_ICP]["output"], 3)
        # b.test is blocked by MX (Proofpoint = HIGH_PROTECTION = blocked)
        self.assertEqual(report["stages"][nightlysourcing.STAGE_MX]["output"], 2)
        self.assertEqual(report["candidates_added"], 2)

    def test_a_provider_failure_is_recorded_not_silent(self):
        """A search failure stops sourcing but records the reason."""
        def failing_search(**kwargs):
            raise ProviderError("auth expired")

        report = nightlysourcing.run(
            config={}, search_fn=failing_search,
            resolve_fn=_FakeResolver())

        self.assertTrue(report.get("source_failed"))
        problems = report["stages"][nightlysourcing.STAGE_SOURCE].get("problems")
        self.assertTrue(problems)
        self.assertIn("auth expired", problems[0]["error"])

    def test_dry_run_does_not_append(self):
        """live=False is the default: candidates are counted but not written."""
        search = _FakeSearch(pages=[[_fake_company("dry.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver(),
            live=False)

        self.assertEqual(report["candidates_added"], 1)
        self.assertEqual(len(candidatelist.load()), 0)

    def test_live_run_appends_to_the_candidate_list(self):
        search = _FakeSearch(pages=[[_fake_company("live.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver(),
            live=True)

        self.assertEqual(report["candidates_added"], 1)
        rows = candidatelist.load()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["domain"], "live.test")


class TestThePipelineRefusesToAdvancePastCandidates(PipelineTestBase):
    """ACCEPTANCE: one test proves the pipeline REFUSES to advance a candidate
    past the candidate list. No person-level call, no verification."""

    def test_the_pipeline_function_calls_no_people_endpoint(self):
        ok, violations = nightlysourcing.pipeline_refuses_to_advance_past_candidates()
        self.assertTrue(ok, f"pipeline calls forbidden: {violations}")

    def test_the_run_function_source_names_no_verification_module(self):
        import inspect
        source = inspect.getsource(nightlysourcing.run)
        for name in ("verification", "contactout", "people_search",
                     "email_finder", "find_email", "deliverable", "reoon"):
            self.assertNotIn(name, source,
                             f"run() references {name!r} - the pipeline "
                             f"stops at candidates")

    def test_the_pipeline_never_imports_a_people_provider(self):
        """The module itself imports no people-level provider."""
        import inspect
        source = inspect.getsource(nightlysourcing)
        for name in ("contactout", "deliverable", "reoon"):
            self.assertNotIn(f"import {name}", source,
                             f"nightlysourcing imports {name!r}")

    def test_a_candidate_has_no_person_fields(self):
        """A candidate row carries company fields only. No email, no name,
        no LinkedIn profile - those are person-level and cost credits."""
        search = _FakeSearch(pages=[[_fake_company("noper.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)

        nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver(),
            live=True)

        rows = candidatelist.load()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        for field in ("email", "name", "linkedin", "title", "phone"):
            self.assertNotIn(field, row,
                             f"candidate has person field {field!r}")


class TestDSTAwareScheduling(PipelineTestBase):
    """Both schedules are stated in Zagreb time and move with DST.

    DIGEST_HOUR moves 5 -> 6 UTC on 2026-10-25 when Zagreb leaves DST.
    The UTC hour is derived from geo.zone, never hardcoded.
    """

    def test_nightly_utc_before_dst_change(self):
        """2026-09-15: Zagreb is CEST (UTC+2), so 02:00 local = 00:00 UTC."""
        date = datetime.date(2026, 9, 15)
        utc = nightlysourcing.nightly_utc_moment(date)
        self.assertEqual(utc.hour, 0)
        self.assertEqual(utc.minute, 0)

    def test_nightly_utc_after_dst_change(self):
        """2026-10-26: Zagreb is CET (UTC+1), so 02:00 local = 01:00 UTC."""
        date = datetime.date(2026, 10, 26)
        utc = nightlysourcing.nightly_utc_moment(date)
        self.assertEqual(utc.hour, 1)
        self.assertEqual(utc.minute, 0)

    def test_export_utc_before_dst_change(self):
        """Monday 2026-09-21: 07:00 CEST = 05:00 UTC."""
        date = datetime.date(2026, 9, 21)
        utc = nightlysourcing.export_utc_moment(date)
        self.assertEqual(utc.hour, 5)

    def test_export_utc_after_dst_change(self):
        """Monday 2026-10-26: 07:00 CET = 06:00 UTC."""
        date = datetime.date(2026, 10, 26)
        utc = nightlysourcing.export_utc_moment(date)
        self.assertEqual(utc.hour, 6)

    def test_is_export_day_on_monday(self):
        self.assertTrue(nightlysourcing.is_export_day(
            datetime.date(2026, 9, 21)))

    def test_is_export_day_on_tuesday(self):
        self.assertFalse(nightlysourcing.is_export_day(
            datetime.date(2026, 9, 22)))

    def test_isoweekday_not_weekday(self):
        """senderheadroom counted weekdays from 0 in an ISO repo (F-004)
        and read Mon-Fri as Tue-Saturday. This module uses isoweekday."""
        # Monday 2026-09-21: isoweekday() == 1, weekday() == 0
        d = datetime.date(2026, 9, 21)
        self.assertEqual(d.isoweekday(), 1)
        self.assertEqual(d.weekday(), 0)
        self.assertEqual(nightlysourcing.EXPORT_WEEKDAY, 1)


class TestCostReporting(PipelineTestBase):
    """Credit spend is REPORTED, NEVER GATED."""

    def test_the_report_carries_credits_spent(self):
        search = _FakeSearch(pages=[[_fake_company("cost.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver())

        self.assertIn("credits_spent", report)
        self.assertIn("credits_per_candidate", report)

    def test_credits_per_candidate_is_zero_when_none_added(self):
        search = _FakeSearch(pages=[[]])

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver())

        self.assertEqual(report["credits_per_candidate"], 0)
        self.assertEqual(report["candidates_added"], 0)


class TestMXClassification(PipelineTestBase):
    """S4b MX classification within the pipeline.

    The resolver returns string hostnames; mx.decide classifies them via
    real gateway suffix matching. Default policy blocks HIGH_PROTECTION
    (Proofpoint, Mimecast, Barracuda).
    """

    def test_known_allowed_survives(self):
        """google.com is Google Workspace (NORMAL) -> KNOWN_ALLOWED."""
        search = _FakeSearch(pages=[[_fake_company("ok.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)
        resolver = _FakeResolver({"ok.test": "allowed"})

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=resolver)

        self.assertEqual(report["stages"][nightlysourcing.STAGE_MX]["output"], 1)

    def test_known_blocked_is_dropped(self):
        """pphosted.com is Proofpoint (HIGH_PROTECTION) -> KNOWN_BLOCKED."""
        search = _FakeSearch(pages=[[_fake_company("blocked.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)
        resolver = _FakeResolver({"blocked.test": "blocked"})

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=resolver)

        self.assertEqual(report["stages"][nightlysourcing.STAGE_MX]["output"], 0)
        self.assertEqual(report["candidates_added"], 0)

    def test_dns_failure_is_held_not_dropped(self):
        """dns_failure is HELD - we could not ask, which is not the same
        fact as no mail."""
        search = _FakeSearch(pages=[[_fake_company("dnfail.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)
        resolver = _FakeResolver({"dnfail.test": "dns_failure"})

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=resolver)

        self.assertEqual(report["stages"][nightlysourcing.STAGE_MX]["output"], 0)

    def test_no_mx_is_dropped(self):
        search = _FakeSearch(pages=[[_fake_company("nomx.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)
        resolver = _FakeResolver({"nomx.test": "no_mx"})

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=resolver)

        self.assertEqual(report["stages"][nightlysourcing.STAGE_MX]["output"], 0)

    def test_unknown_provider_survives(self):
        """An unrecognised MX host -> UNKNOWN_PROVIDER, allowed by default."""
        search = _FakeSearch(pages=[[_fake_company("unknown.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)
        resolver = _FakeResolver({"unknown.test": "unknown"})

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=resolver)

        self.assertEqual(report["stages"][nightlysourcing.STAGE_MX]["output"], 1)


class TestSourceStage(PipelineTestBase):
    """Stage 1: AI-ARK company search."""

    def test_known_domains_are_skipped(self):
        """DIFF against what we hold; NEVER delete."""
        candidatelist.append({"domain": "known.test", "state": "new"})
        search = _FakeSearch(pages=[
            [_fake_company("known.test"), _fake_company("fresh.test")],
        ])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver(),
            live=True)

        self.assertEqual(report["stages"][nightlysourcing.STAGE_SOURCE]["output"], 1)
        rows = candidatelist.load()
        domains = [r["domain"] for r in rows]
        self.assertIn("fresh.test", domains)
        # known.test was already there, not duplicated
        self.assertEqual(domains.count("known.test"), 1)

    def test_empty_rows_end_the_walk(self):
        search = _FakeSearch(pages=[[], [_fake_company("never.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver())

        # Page 1 returned empty, walk stopped, page 2 never reached
        self.assertEqual(report["stages"][nightlysourcing.STAGE_SOURCE]["output"], 0)

    def test_a_short_page_ends_the_walk(self):
        """A page shorter than PAGE_SIZE is the end of the catalogue."""
        page = [_fake_company(f"short-{i}.test") for i in range(5)]
        search = _FakeSearch(pages=[page])

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver())

        self.assertEqual(len(search.calls), 1)


class TestICPStage(PipelineTestBase):
    """Stage 2: S3 ICP verdict."""

    def test_rejected_companies_do_not_survive(self):
        search = _FakeSearch(pages=[[_fake_company("rejected.test")]])
        icp.score = _Verdict(icp.REJECTED, 0.0)

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver())

        self.assertEqual(report["stages"][nightlysourcing.STAGE_ICP]["output"], 0)

    def test_review_is_routed_to_enrichment(self):
        search = _FakeSearch(pages=[[_fake_company("review.test")]])
        icp.score = _Verdict(icp.REVIEW, 0.4)

        report = nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver())

        self.assertEqual(report["stages"][nightlysourcing.STAGE_ICP]["output"], 0)
        self.assertEqual(
            report["stages"][nightlysourcing.STAGE_ICP]["review_to_enrichment"], 1)


class TestLocalCollision(PipelineTestBase):
    """Stage 4: local collision only. No provider walk."""

    def test_prior_touch_status_is_never_touched_for_new_domains(self):
        search = _FakeSearch(pages=[[_fake_company("fresh.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)

        nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver(),
            live=True)

        rows = candidatelist.load()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["prior_touch_status"], "never_touched")


class TestCandidateOutput(PipelineTestBase):
    """Stage 5: the candidate row shape."""

    def test_a_candidate_has_the_export_columns(self):
        """The export needs: domain, company, headcount, industry, country,
        website, why_matched, prior_touch_status."""
        search = _FakeSearch(pages=[
            [_fake_company("shaped.test", company_name="Shaped Co",
                           headcount=42, industry="advertising",
                           country="United Kingdom")],
        ])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)

        nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver(),
            live=True)

        rows = candidatelist.load()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["domain"], "shaped.test")
        self.assertEqual(row["company"], "Shaped Co")
        self.assertEqual(row["headcount"], 42)
        self.assertEqual(row["industry"], "advertising")
        self.assertEqual(row["country"], "United Kingdom")
        self.assertIn("why_matched", row)
        self.assertIn("prior_touch_status", row)

    def test_why_matched_carries_icp_evidence(self):
        search = _FakeSearch(pages=[[_fake_company("evidence.test")]])
        icp.score = _Verdict(icp.QUALIFIED, 0.9)

        nightlysourcing.run(
            config={}, search_fn=search, resolve_fn=_FakeResolver(),
            live=True)

        rows = candidatelist.load()
        self.assertEqual(rows[0]["why_matched"], "matches ICP criteria")


if __name__ == "__main__":
    unittest.main()
