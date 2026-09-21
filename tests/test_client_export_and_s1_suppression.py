#!/usr/bin/env python3
"""The export / clean / import pipeline and S1 suppression that sticks.

Three things this module proves:

1. SUPPRESSION AT S1.  A domain the client removed from a snapshot is
   dropped by `hygiene.check` on every future sourcing run, for that client
   only.  The failure this prevents: 600 domains deleted by the client,
   re-sourced the next nightly run because they still match ICP, appearing
   in the next export.  The client deletes them again and concludes we do
   not listen.

2. THE EXPORT IS A REAL CSV FROM CANDIDATES.  The builder selects domains
   that passed S3 ICP, S4b MX and local collision, minus suppressed and
   already-approved.  Columns are exactly domain, company, headcount,
   industry, country, website.  No contacts, no emails, no person names.

3. CONFIG IS CONFIG.  A second client is onboardable by adding a config
   block, not by editing logic.  No `if client == "productive"` anywhere.
"""
import csv
import io
import os
import tempfile
import unittest

from src import (clientapproval as ca, clientexport, clients, hygiene,
                 icp, mx as mx_mod, store)


def _mx_cache_for(*domains):
    """Pre-populate an MX cache so tests do not hit DNS."""
    import time
    cache = {}
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for domain in domains:
        cache[domain] = {
            "mx_records": [("mx.example.com", 10)],
            "status": mx_mod.KNOWN_ALLOWED,
            "checked_at": now,
        }
    return cache


def _make_record(domain, company="Acme", client="productive",
                 icp_status=icp.QUALIFIED, industry="Marketing Agency",
                 country="United Kingdom", employees=50, website=None):
    """A record that has passed S3 ICP, with company facts for the export."""
    rec = store.new_record(
        id=f"rec-{domain}", lane="cold", client=client,
        company=company, domain=domain)
    rec["company_facts"] = {
        "industry": industry,
        "employees": employees,
        "country": country,
        "name": company,
        "description": f"{company} is a {industry.lower()}",
    }
    rec["qualification"] = {
        "verdict": {"icp_status": icp_status, "icp_score": 70.0,
                    "icp_tier": "b", "icp_confidence": "high"},
    }
    return rec


class _ApprovalTempDir:
    """Mixin: redirect the approval store to a temp directory."""

    def setUp(self):
        super().setUp()
        self._dir = tempfile.TemporaryDirectory()
        self._previous = os.environ.get("CLIENT_APPROVAL")
        os.environ["CLIENT_APPROVAL"] = os.path.join(
            self._dir.name, "client-approval.jsonl")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._previous is None:
            os.environ.pop("CLIENT_APPROVAL", None)
        else:
            os.environ["CLIENT_APPROVAL"] = self._previous
        self._dir.cleanup()


# --------------------------------------------------------- S1 suppression
#
# The failure: a client deletes 600 domains, the next nightly run sources
# them again because they still match ICP, they appear in the next export.


class SuppressionAppliesAtS1(_ApprovalTempDir, unittest.TestCase):

    def _empty_history(self):
        return {"by_identity": {}, "by_domain": {}, "records": 0}

    def test_a_suppressed_domain_is_dropped_by_hygiene_for_this_client(self):
        """The core test.  Suppress, re-source, assert it does not pass."""
        ca.record("removed.example", client="productive",
                  state=ca.SUPPRESSED, who="client",
                  source="snapshot SNAP-1",
                  reason="removed by client in snapshot SNAP-1")

        candidate = {"domain": "removed.example", "company": "Acme"}
        result = hygiene.check(candidate, self._empty_history(),
                               client="productive")
        self.assertEqual(result["verdict"], hygiene.SUPPRESSED_ACCOUNT)
        self.assertEqual(result["action"], hygiene.SUPPRESS)
        self.assertIn("suppressed by the client", result["why"])

    def test_the_same_domain_passes_hygiene_for_a_different_client(self):
        """Cross-client isolation.  Suppression is per workspace."""
        ca.record("shared.example", client="productive",
                  state=ca.SUPPRESSED, who="client", source="snapshot S1")

        candidate = {"domain": "shared.example", "company": "Acme"}
        result = hygiene.check(candidate, self._empty_history(),
                               client="contactout")
        self.assertNotEqual(result["verdict"], hygiene.SUPPRESSED_ACCOUNT)

    def test_a_non_suppressed_domain_passes_hygiene_with_client_set(self):
        """Passing `client` does not break domains the client has not seen."""
        candidate = {"domain": "fresh.example", "company": "Acme"}
        result = hygiene.check(candidate, self._empty_history(),
                               client="productive")
        self.assertEqual(result["verdict"], hygiene.FRESH)

    def test_hygiene_without_client_does_not_check_approval(self):
        """Backwards compatible: no `client` means no approval check."""
        ca.record("removed.example", client="productive",
                  state=ca.SUPPRESSED, who="client", source="snapshot S1")
        candidate = {"domain": "removed.example", "company": "Acme"}
        result = hygiene.check(candidate, self._empty_history())
        self.assertNotEqual(result["verdict"], hygiene.SUPPRESSED_ACCOUNT)

    def test_suppressed_domain_reaches_neither_candidate_list_nor_export(
            self):
        """The exact failure the task prevents.

        Suppress a domain, build the candidate list, assert it is absent.
        This is the end-to-end version: not just hygiene.check, but the
        whole export pipeline.
        """
        ca.record("gone.example", client="productive",
                  state=ca.SUPPRESSED, who="client", source="snapshot S1")

        recs = [
            _make_record("gone.example"),
            _make_record("kept.example", company="OtherCo"),
        ]
        mx_cache = _mx_cache_for("gone.example", "kept.example")
        rows, note = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        domains = [r["domain"] for r in rows]
        self.assertNotIn("gone.example", domains)
        self.assertIn("kept.example", domains)
        self.assertIn("suppressed=1", note)


# --------------------------------------------------------- the export
#
# Columns, PII, supply, and the snapshot record.


class ExportColumnsAndPII(_ApprovalTempDir, unittest.TestCase):

    def test_export_columns_are_exactly_the_six_named(self):
        self.assertEqual(clientexport.EXPORT_COLUMNS,
                         ("domain", "company", "headcount", "industry",
                          "country", "website"))

    def test_the_csv_carries_no_contact_or_email_column(self):
        """A person's name in a client export is a new leak."""
        recs = [_make_record("acme.example", company="Acme Corp")]
        mx_cache = _mx_cache_for("acme.example")
        rows, _ = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        csv_text = clientexport.to_csv(rows)
        reader = csv.DictReader(io.StringIO(csv_text))
        for field in reader.fieldnames:
            self.assertNotIn("contact", field.lower())
            self.assertNotIn("email", field.lower())
            self.assertNotIn("name", field.lower())
            self.assertNotIn("linkedin", field.lower())
            self.assertNotIn("phone", field.lower())
            self.assertNotIn("title", field.lower())

    def test_the_csv_header_matches_export_columns(self):
        recs = [_make_record("acme.example")]
        mx_cache = _mx_cache_for("acme.example")
        rows, _ = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        csv_text = clientexport.to_csv(rows)
        reader = csv.DictReader(io.StringIO(csv_text))
        self.assertEqual(list(reader.fieldnames),
                         list(clientexport.EXPORT_COLUMNS))

    def test_each_row_carries_the_company_fields(self):
        recs = [_make_record("acme.example", company="Acme Corp",
                             industry="Digital Marketing Agency",
                             country="United Kingdom", employees=42)]
        mx_cache = _mx_cache_for("acme.example")
        rows, _ = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["domain"], "acme.example")
        self.assertEqual(row["company"], "Acme Corp")
        self.assertEqual(row["headcount"], 42)
        self.assertEqual(row["industry"], "Digital Marketing Agency")
        self.assertEqual(row["country"].lower(), "united kingdom")
        self.assertEqual(row["website"], "acme.example")


class ExportExcludesAlreadyApproved(_ApprovalTempDir, unittest.TestCase):

    def test_an_already_approved_domain_is_not_re_exported(self):
        """Do not re-ask a client a question they have answered."""
        ca.record("done.example", client="productive", state=ca.APPROVED,
                  who="client", source="snapshot SNAP-0")

        recs = [
            _make_record("done.example"),
            _make_record("new.example", company="OtherCo"),
        ]
        mx_cache = _mx_cache_for("done.example", "new.example")
        rows, note = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        domains = [r["domain"] for r in rows]
        self.assertNotIn("done.example", domains)
        self.assertIn("new.example", domains)
        self.assertIn("already_approved=1", note)


class SnapshotIdRecordedOnce(_ApprovalTempDir, unittest.TestCase):

    def test_a_snapshot_id_cannot_be_reused(self):
        recs = [_make_record("acme.example")]
        mx_cache = _mx_cache_for("acme.example")
        rows, _ = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        domains = [r["domain"] for r in rows]
        ca.record_snapshot("SNAP-1", domains, client="productive")
        with self.assertRaises(ValueError):
            ca.record_snapshot("SNAP-1", domains, client="productive")


class ShortSupplyReportsHonestCount(_ApprovalTempDir, unittest.TestCase):

    def test_a_small_export_reports_its_count_rather_than_padding(self):
        """A 4,000-row snapshot is a supply finding, not a failure."""
        recs = [_make_record(f"small-{i}.example") for i in range(5)]
        mx_cache = _mx_cache_for(*(f"small-{i}.example" for i in range(5)))
        rows, note = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        self.assertEqual(len(rows), 5)
        self.assertIn("supply below target", note)
        self.assertIn("5 candidate(s)", note)

    def test_zero_supply_is_reported_honestly(self):
        recs = [_make_record("x.example", icp_status=icp.REJECTED)]
        rows, note = clientexport.build_candidate_list(recs, {}, "productive")
        self.assertEqual(len(rows), 0)
        self.assertIn("0 candidate(s)", note)


class ExportSelectionFilters(_ApprovalTempDir, unittest.TestCase):

    def test_non_qualified_records_are_excluded(self):
        recs = [
            _make_record("rejected.example", icp_status=icp.REJECTED),
            _make_record("review.example", icp_status=icp.REVIEW),
            _make_record("unknown.example", icp_status=icp.UNKNOWN),
            _make_record("qualified.example"),
        ]
        mx_cache = _mx_cache_for("qualified.example")
        rows, note = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        domains = [r["domain"] for r in rows]
        self.assertEqual(domains, ["qualified.example"])
        self.assertIn("icp=3", note)

    def test_records_from_other_clients_are_excluded(self):
        recs = [
            _make_record("productive.example", client="productive"),
            _make_record("contactout.example", client="contactout"),
        ]
        mx_cache = _mx_cache_for("productive.example")
        rows, _ = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        domains = [r["domain"] for r in rows]
        self.assertEqual(domains, ["productive.example"])

    def test_duplicate_domains_are_deduplicated(self):
        recs = [
            _make_record("same.example"),
            _make_record("same.example"),
        ]
        recs[1]["id"] = "rec-same-2"
        mx_cache = _mx_cache_for("same.example")
        rows, _ = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        self.assertEqual(len(rows), 1)


# --------------------------------------------------------- cross-client
#
# The same domain suppressed for one client, approved for another.


class CrossClientIsolation(_ApprovalTempDir, unittest.TestCase):

    def test_suppressed_for_one_approved_for_another_stays_both(self):
        """The exact cross-client test the task requires."""
        ca.record("shared.example", client="productive",
                  state=ca.SUPPRESSED, who="client", source="snapshot P1")
        ca.record("shared.example", client="contactout",
                  state=ca.APPROVED, who="client", source="snapshot C1")

        self.assertTrue(ca.is_suppressed("shared.example", "productive"))
        self.assertFalse(ca.is_suppressed("shared.example", "contactout"))
        self.assertTrue(ca.is_approved("shared.example", "contactout"))
        self.assertFalse(ca.is_approved("shared.example", "productive"))

        # And hygiene agrees.
        history = {"by_identity": {}, "by_domain": {}, "records": 0}
        candidate = {"domain": "shared.example"}

        productive = hygiene.check(candidate, history, client="productive")
        self.assertEqual(productive["verdict"], hygiene.SUPPRESSED_ACCOUNT)

        contactout = hygiene.check(candidate, history, client="contactout")
        self.assertNotEqual(contactout["verdict"], hygiene.SUPPRESSED_ACCOUNT)


# --------------------------------------------------------- config
#
# A second client is onboardable by adding config, not editing logic.


class ExportConfig(unittest.TestCase):

    def test_defaults_are_sane_when_no_block_exists(self):
        settings = clients.export_settings({})
        self.assertEqual(settings["columns"], list(clientexport.EXPORT_COLUMNS))
        self.assertEqual(settings["cadence"]["frequency"], "weekly")
        self.assertEqual(settings["cadence"]["day_of_week"], "monday")
        self.assertEqual(settings["cadence"]["timezone"], "Europe/Zagreb")

    def test_productive_config_is_readable(self):
        config = clients.load("productive")
        settings = clients.export_settings(config)
        self.assertIn("domain", settings["columns"])
        self.assertIn("website", settings["columns"])
        self.assertEqual(settings["cadence"]["frequency"], "weekly")
        self.assertEqual(settings["cadence"]["timezone"], "Europe/Zagreb")

    def test_columns_from_config_override_defaults(self):
        config = {"client_approval_export": {
            "columns": ["domain", "company", "country"]}}
        settings = clients.export_settings(config)
        self.assertEqual(settings["columns"], ["domain", "company", "country"])

    def test_no_client_specific_branching(self):
        """The engine does not branch on the client name."""
        import inspect
        source = inspect.getsource(clientexport)
        self.assertNotIn('"productive"', source)
        self.assertNotIn("'productive'", source)


# --------------------------------------------------------- CSV output


class CSVOutput(_ApprovalTempDir, unittest.TestCase):

    def test_write_csv_creates_a_readable_file(self):
        recs = [_make_record("acme.example", company="Acme Corp",
                             industry="Marketing", country="UK",
                             employees=30)]
        mx_cache = _mx_cache_for("acme.example")
        rows, _ = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv",
                                         delete=False) as f:
            path = f.name
        try:
            clientexport.write_csv(rows, path)
            with open(path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                data = list(reader)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["domain"], "acme.example")
            self.assertEqual(data[0]["company"], "Acme Corp")
        finally:
            os.unlink(path)

    def test_formula_cells_are_guarded(self):
        """A company name starting with = must not execute in Excel."""
        recs = [_make_record("evil.example", company="=CMD|'/C calc'!A0")]
        mx_cache = _mx_cache_for("evil.example")
        rows, _ = clientexport.build_candidate_list(
            recs, {}, "productive", mx_cache=mx_cache)
        csv_text = clientexport.to_csv(rows)
        self.assertIn("'=CMD", csv_text)


if __name__ == "__main__":
    unittest.main()
