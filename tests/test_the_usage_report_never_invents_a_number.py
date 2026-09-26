#!/usr/bin/env python3
"""The usage report never invents a number.

TASK-359. The report has five states and each one is tested:

    READ_OK              a real number from the provider
    NEEDS_CONSOLE_READ   no programmatic endpoint exists
    AUTH_FAILED          endpoint exists, credentials rejected
    UNREACHABLE          transport failure - NOT the same as AUTH_FAILED
    NOT_CONFIGURED       we hold no credential for this provider

The critical test: when an endpoint FAILS, the row is UNREACHABLE with no
value - not 0, not null-treated-as-zero, and not yesterday's figure. A report
that carries a number it could not read is worse than one that reports
nothing.

These tests do NOT call any provider. They inject failures through the
existing transport seam (`providers.set_transport`) and assert the report's
shape.
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts import usage_report                              # noqa: E402
from src.providers import (                                    # noqa: E402
    HttpTimeout, HttpTransportError, MissingKey, ProviderError,
    set_transport,
)


def _fake_transport(status, response_body):
    """A transport that always returns (status, response_body)."""
    def _t(method, url, headers, body, timeout):
        return status, response_body
    return _t


def _failing_transport(exception_class):
    """A transport that always raises the given exception."""
    def _t(method, url, headers, body, timeout):
        raise exception_class(f"test: {exception_class.__name__}")
    return _t


class TestNeverInventsANumber(unittest.TestCase):
    """When the endpoint fails, the row has no value."""

    def setUp(self):
        os.environ["CONTACTOUT_TOKEN"] = "test-token-value-12345"

    def tearDown(self):
        os.environ.pop("CONTACTOUT_TOKEN", None)
        set_transport(None)

    def test_transport_failure_produces_unreachable_with_no_value(self):
        """The critical test: endpoint fails -> UNREACHABLE, no value."""
        set_transport(_failing_transport(HttpTransportError))
        rows = usage_report._read_contactout()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["state"], usage_report.UNREACHABLE)
        self.assertIsNone(row["value"])
        self.assertIsNone(row["limit"])
        self.assertIsNone(row["percent"])

    def test_timeout_produces_unreachable_with_no_value(self):
        """A timeout is UNREACHABLE, not AUTH_FAILED, and carries no value."""
        set_transport(_failing_transport(HttpTimeout))
        rows = usage_report._read_contactout()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["state"], usage_report.UNREACHABLE)
        self.assertIsNone(row["value"])

    def test_auth_failure_is_distinct_from_unreachable(self):
        """401 -> AUTH_FAILED, not UNREACHABLE. They are different states."""
        set_transport(_fake_transport(401, '{"error": "unauthorized"}'))
        rows = usage_report._read_contactout()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["state"], usage_report.AUTH_FAILED)
        self.assertIsNone(row["value"])

    def test_not_configured_when_credential_absent(self):
        """No credential -> NOT_CONFIGURED, no value."""
        os.environ.pop("CONTACTOUT_TOKEN", None)
        rows = usage_report._read_contactout()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["state"], usage_report.NOT_CONFIGURED)
        self.assertIsNone(row["value"])

    def test_read_ok_carries_a_value(self):
        """A successful read carries a real value from the provider."""
        import json
        # ContactOut /v1/stats returns:
        # {"status_code": 200, "period": {...},
        #  "usage": {"count": N, "quota": N, ...}}
        body = json.dumps({
            "status_code": 200,
            "period": {"start": "2026-09-01", "end": "2026-09-30"},
            "usage": {
                "count": 42,
                "quota": 1000,
                "search_count": 958,
                "search_quota": 10000,
            }
        })
        set_transport(_fake_transport(200, body))
        rows = usage_report._read_contactout()
        self.assertTrue(len(rows) >= 1)
        values = [r["value"] for r in rows]
        self.assertIn(42, values)
        self.assertIn(958, values)
        for r in rows:
            self.assertEqual(r["state"], usage_report.READ_OK)


class TestAuthFailedVsUnreachable(unittest.TestCase):
    """AUTH_FAILED and UNREACHABLE are distinguishable."""

    def setUp(self):
        os.environ["BLITZ_API_KEY"] = "test-blitz-key-12345"

    def tearDown(self):
        os.environ.pop("BLITZ_API_KEY", None)
        set_transport(None)

    def test_401_is_auth_failed(self):
        """A 401 from Blitz is AUTH_FAILED."""
        set_transport(_fake_transport(401, '{"error": "invalid api key"}'))
        rows = usage_report._read_blitz()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], usage_report.AUTH_FAILED)
        self.assertIsNone(rows[0]["value"])

    def test_connection_error_is_unreachable(self):
        """A connection error from Blitz is UNREACHABLE, not AUTH_FAILED."""
        set_transport(_failing_transport(HttpTransportError))
        rows = usage_report._read_blitz()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], usage_report.UNREACHABLE)
        self.assertIsNone(rows[0]["value"])

    def test_timeout_is_unreachable_not_auth_failed(self):
        """A timeout is UNREACHABLE. The two states must not collapse."""
        set_transport(_failing_transport(HttpTimeout))
        rows = usage_report._read_blitz()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], usage_report.UNREACHABLE)
        self.assertNotEqual(rows[0]["state"], usage_report.AUTH_FAILED)


class TestCredentialSafety(unittest.TestCase):
    """No credential value appears in the report output."""

    def test_no_credential_in_markdown_output(self):
        """The generated markdown contains no configured credential value."""
        os.environ["CONTACTOUT_TOKEN"] = "supersecretcontactout123"
        os.environ["BLITZ_API_KEY"] = "supersecretblitzkey456"
        try:
            # Mock transport so no real HTTP calls are made
            import json
            empty = json.dumps({})
            set_transport(_fake_transport(200, empty))
            rows = usage_report.read_all()
            content = usage_report.format_markdown(rows, "2026-09-26")
            leaks = usage_report.verify_no_credential_leak(content)
            self.assertEqual(
                leaks, [],
                f"credential values found in report: {leaks}")
        finally:
            os.environ.pop("CONTACTOUT_TOKEN", None)
            os.environ.pop("BLITZ_API_KEY", None)
            set_transport(None)

    def test_error_detail_does_not_leak_key(self):
        """Even on failure, the detail field does not contain the key."""
        os.environ["CONTACTOUT_TOKEN"] = "supersecretcontactout789"
        try:
            set_transport(_failing_transport(HttpTransportError))
            rows = usage_report._read_contactout()
            for r in rows:
                self.assertNotIn(
                    "supersecretcontactout789", r.get("detail", ""),
                    "credential value leaked in error detail")
        finally:
            os.environ.pop("CONTACTOUT_TOKEN", None)
            set_transport(None)


class TestConsoleOnlyProviders(unittest.TestCase):
    """Providers with no endpoint get NEEDS_CONSOLE_READ."""

    def test_glm_without_key_is_not_configured(self):
        os.environ.pop("ZAI_API_KEY", None)
        rows = usage_report.read_all()
        glm = [r for r in rows if r["provider"] == "GLM (Z.ai)"]
        self.assertTrue(len(glm) >= 1)
        self.assertEqual(glm[0]["state"], usage_report.NOT_CONFIGURED)

    def test_glm_with_key_needs_console_read(self):
        os.environ["ZAI_API_KEY"] = "test-zai-key-12345"
        try:
            rows = usage_report.read_all()
            glm = [r for r in rows if r["provider"] == "GLM (Z.ai)"]
            self.assertTrue(len(glm) >= 1)
            self.assertEqual(glm[0]["state"],
                              usage_report.NEEDS_CONSOLE_READ)
            self.assertIsNone(glm[0]["value"])
        finally:
            os.environ.pop("ZAI_API_KEY", None)

    def test_xai_without_key_is_not_configured(self):
        os.environ.pop("XAI_API_KEY", None)
        rows = usage_report.read_all()
        xai = [r for r in rows if r["provider"] == "Grok (xAI)"]
        self.assertTrue(len(xai) >= 1)
        self.assertEqual(xai[0]["state"], usage_report.NOT_CONFIGURED)

    def test_xai_with_key_needs_console_read(self):
        os.environ["XAI_API_KEY"] = "test-xai-key-12345"
        try:
            rows = usage_report.read_all()
            xai = [r for r in rows if r["provider"] == "Grok (xAI)"]
            self.assertTrue(len(xai) >= 1)
            self.assertEqual(xai[0]["state"],
                              usage_report.NEEDS_CONSOLE_READ)
        finally:
            os.environ.pop("XAI_API_KEY", None)

    def test_reoon_without_key_is_not_configured(self):
        os.environ.pop("REOON_KEY", None)
        rows = usage_report.read_all()
        reoon = [r for r in rows
                  if r["provider"] == "Reoon (CheapVerifier)"]
        self.assertTrue(len(reoon) >= 1)
        self.assertEqual(reoon[0]["state"], usage_report.NOT_CONFIGURED)

    def test_reoon_with_key_needs_console_read(self):
        os.environ["REOON_KEY"] = "test-reoon-key-12345"
        try:
            rows = usage_report.read_all()
            reoon = [r for r in rows
                      if r["provider"] == "Reoon (CheapVerifier)"]
            self.assertTrue(len(reoon) >= 1)
            self.assertEqual(reoon[0]["state"],
                              usage_report.NEEDS_CONSOLE_READ)
        finally:
            os.environ.pop("REOON_KEY", None)


class TestReportFormat(unittest.TestCase):
    """The markdown report has the expected structure."""

    def test_report_has_table(self):
        rows = [usage_report._row("TestProvider", "credits", value=42,
                                    state=usage_report.READ_OK)]
        md = usage_report.format_markdown(rows, "2026-09-26")
        self.assertIn("# Daily Usage Report - 2026-09-26", md)
        self.assertIn("| TestProvider | credits | 42 |", md)

    def test_report_lists_console_needed(self):
        rows = [usage_report._row("TestProvider", "credits",
                                    state=usage_report.NEEDS_CONSOLE_READ,
                                    detail="read console")]
        md = usage_report.format_markdown(rows, "2026-09-26")
        self.assertIn("## NEEDS_CONSOLE_READ", md)
        self.assertIn("TestProvider", md)

    def test_report_lists_not_configured(self):
        rows = [usage_report._row("TestProvider", "credits",
                                    state=usage_report.NOT_CONFIGURED,
                                    detail="KEY not set")]
        md = usage_report.format_markdown(rows, "2026-09-26")
        self.assertIn("## NOT_CONFIGURED", md)
        self.assertIn("TestProvider", md)

    def test_unreachable_row_has_no_value_in_table(self):
        rows = [usage_report._row("TestProvider", "credits",
                                    state=usage_report.UNREACHABLE)]
        md = usage_report.format_markdown(rows, "2026-09-26")
        self.assertIn("**UNREACHABLE**", md)
        self.assertIn("- |", md)


class TestWriteReport(unittest.TestCase):
    """write_report creates the file in the right place."""

    def test_dry_run_writes_nothing(self, ):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            rows = [usage_report._row("Test", "x", state=usage_read_ok())]
            path, content = usage_report.write_report(
                rows, output_dir=td, date="2026-09-26", dry_run=True)
            self.assertFalse(os.path.exists(path))
            self.assertIn("2026-09-26", content)

    def test_real_write_creates_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            rows = [usage_report._row("Test", "x", state=usage_read_ok())]
            path, content = usage_report.write_report(
                rows, output_dir=td, date="2026-09-26")
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                self.assertEqual(f.read(), content)


def usage_read_ok():
    return usage_report.READ_OK


if __name__ == "__main__":
    unittest.main()
