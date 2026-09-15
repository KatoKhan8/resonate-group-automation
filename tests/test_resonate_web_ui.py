"""The control center renders scoped facts through the existing HTTP boundary."""
import html
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.parse import urlencode

from src import store, workspaces
from src.web import api, assets, pages
from tests.webbase import WebTest


class ControlCenter(WebTest):
    def setUp(self):
        self.session = self.signin("ops@productive.test")

    def test_shell_has_branded_keyboard_navigation_and_scoped_search(self):
        status, body, _ = self.session.get("/")
        self.assertEqual(status, 200)
        self.assertIn('/assets/resonate-logo.png?v=', body)
        self.assertIn('href="#main-content"', body)
        self.assertIn('aria-controls="sidebar"', body)
        self.assertIn('aria-current="page"', body)
        self.assertIn('name="workspace" value="productive"', body)
        self.assertIn('role="status" aria-live="polite"', body)
        self.assertIn("Live sending <b>disabled</b>", body)

    def test_html_is_not_cached_and_csp_still_refuses_inline_code(self):
        _, _, headers = self.session.get("/")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])

    def test_static_assets_are_public_but_arbitrary_paths_are_not(self):
        for path, content, mime in (
            ("app.css", assets.CSS.encode(), "text/css"),
            ("app.js", assets.JS.encode(), "application/javascript"),
            ("resonate-logo.png", assets.LOGO, "image/png"),
        ):
            with self.subTest(path=path):
                status, data, headers = self.anonymous().get_bytes("/assets/" + path)
                self.assertEqual(status, 200)
                self.assertEqual(data, content)
                self.assertIn(mime, headers["Content-Type"])
                self.assertIn("public", headers["Cache-Control"])
        self.assertEqual(self.session.get("/assets/../api.py")[0], 404)

    def test_search_happens_before_pagination_and_retains_the_query(self):
        original = store.load()
        try:
            rows = [store.new_record(f"ui-{i}", "ui-search", "productive",
                                     f"Needle & Sons {i:03d}", f"ui-{i}.test")
                    for i in range(105)]
            store.save(original + rows)
            status, body, _ = self.session.get("/companies?" + urlencode({
                "batch": "ui-search", "q": "Needle & Sons", "page": 2}))
            self.assertEqual(status, 200)
            self.assertIn("Needle &amp; Sons 104", body)
            self.assertNotIn("Needle &amp; Sons 000</a>", body)
            self.assertIn("q=Needle+%26+Sons", body)
            status, body, _ = self.session.get("/companies?" + urlencode({
                "q": "Needle & Sons 104"}))
            self.assertEqual(status, 200)
            self.assertIn("Needle &amp; Sons 104</a>", body)
        finally:
            store.save(original)

    def test_company_search_cannot_reveal_a_foreign_company(self):
        foreign = self.a_record("contactout")
        status, body, _ = self.session.get("/companies?" + urlencode({"q": foreign["domain"]}))
        self.assertEqual(status, 200)
        self.assertNotIn(f'/companies/{foreign["id"]}', body)
        self.assertIn("No companies match", body)

    def test_contact_search_keeps_batch_scope_and_empty_controls(self):
        _, body, _ = self.session.get("/contacts?q=unfindable-ui-probe&batch=uk-digital")
        self.assertIn("No contacts match", body)
        self.assertIn('name="batch" value="uk-digital"', body)
        self.assertIn('id="contact-search"', body)
        self.assertIn('name="mode"', body)
        self.assertIn('name="flag"', body)

    def test_search_query_is_escaped_on_empty_pages(self):
        attack = '<img src=x onerror=alert(1)>'
        for path in ("/companies", "/contacts"):
            _, body, _ = self.session.get(path + "?" + urlencode({"q": attack}))
            self.assertNotIn(attack, body)
            self.assertIn(html.escape(attack, quote=True), body)

    def test_foreign_batch_and_nonexistent_batch_both_answer_not_found(self):
        own = {r["batch"] for r in self.records_of("productive")}
        foreign = next(r["batch"] for r in self.records_of("contactout") if r["batch"] not in own)
        for batch in (foreign, "ui-batch-does-not-exist"):
            status, body, _ = self.session.get("/batches/" + batch)
            self.assertEqual(status, 404)
            self.assertIn("Not found", body)
            self.assertNotIn("Pre-flight:", body)

    def test_batch_execution_is_backed_by_jobs(self):
        status, body, _ = self.session.get("/batches/uk-digital")
        self.assertEqual(status, 200)
        self.assertIn("Batch execution", body)
        self.assertIn('/jobs?batch=uk-digital', body)

    def test_dashboard_activity_is_workspace_scoped(self):
        workspaces.record("ui-test", "productive", "ui.own-event")
        workspaces.record("ui-test", "contactout", "ui.foreign-event")
        _, body, _ = self.session.get("/")
        self.assertIn("ui.own-event", body)
        self.assertNotIn("ui.foreign-event", body)

    def test_dashboard_polling_uses_health_verdict_without_secret_details(self):
        with mock.patch.object(api.replywatch, "health", return_value=[{
            "provider": "emailbison", "state": "stale", "label": "STALE TEST POLLER",
            "last_succeeded": "2026-01-01", "last_error": "PRIVATE-ERROR-CANARY",
            "checkpoint": {"foreign_workspace": "SECRET-WORKSPACE"},
        }]):
            _, body, _ = self.session.get("/")
        self.assertIn("STALE TEST POLLER", body)
        self.assertNotIn("PRIVATE-ERROR-CANARY", body)
        self.assertNotIn("SECRET-WORKSPACE", body)

    def test_viewer_sees_reports_without_operator_control_plane(self):
        viewer = self.signin("client@productive.test")
        _, body, _ = viewer.get("/")
        self.assertNotIn("Safety &amp; runtime", body)
        self.assertNotIn("Recent workspace activity", body)
        self.assertNotIn('href="/upload"', body)
        status, body, _ = viewer.get("/companies")
        self.assertEqual(status, 403)
        self.assertIn("Permission denied", body)
        self.assertIn('role="alert"', body)

    def test_failed_reads_offer_a_safe_retry_without_exception_details(self):
        with mock.patch.object(api, "company_rows", side_effect=RuntimeError("PRIVATE-ERROR")):
            status, body, _ = self.session.get("/companies")
        self.assertEqual(status, 500)
        self.assertIn("Something went wrong", body)
        self.assertNotIn("PRIVATE-ERROR", body)
        self.assertNotIn("Nothing changed", body)
        self.assertIn('href="/companies"', body)

    def test_upload_remains_a_csrf_protected_native_preview_form(self):
        _, body, _ = self.session.get("/upload")
        self.assertIn('enctype="multipart/form-data"', body)
        self.assertIn('data-dropzone', body)
        self.assertIn('name="csrf"', body)
        before = store.load()
        self.assertEqual(self.session.post("/upload", {"batch": "forged"})[0], 403)
        self.assertEqual(store.load(), before)


class PresentationContracts(unittest.TestCase):
    def test_release_manifest_matches_the_bytes_served_by_the_application(self):
        from src.web.build import build

        with tempfile.TemporaryDirectory() as directory:
            manifest = build(directory)
            self.assertEqual(set(manifest), {"app.css", "app.js", "resonate-logo.png"})
            for name, entry in manifest.items():
                data = (Path(directory) / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
                self.assertEqual(len(data), entry["bytes"])
            self.assertEqual(json.loads((Path(directory) / "manifest.json").read_text()), manifest)

    def test_progress_uses_a_native_accessible_element_under_strict_csp(self):
        markup = pages.progress(0.42)
        self.assertIn('<progress', markup)
        self.assertIn('value="42', markup)
        self.assertIn('max="100"', markup)
        self.assertIn('aria-label=', markup)
        self.assertNotIn('style=', markup)

    def test_empty_company_filter_is_still_usable_without_javascript(self):
        markup = pages.company_list([], query="absent")
        self.assertIn('method="get"', markup)
        self.assertIn('value="absent"', markup)
        self.assertIn("No companies match", markup)

    def test_search_only_reads_allowlisted_serialized_fields(self):
        rows = [{"company": "Visible", "private": "sensitive"}]
        self.assertEqual(api.search_rows(rows, "sensitive", ("company",)), [])
        self.assertEqual(api.search_rows(rows, "VISIBLE", ("company",)), rows)

    def test_provider_login_does_not_enumerate_members(self):
        markup = pages.provider_login_page()
        self.assertIn("Resonate OS", markup)
        self.assertIn('/auth/start', markup)
        self.assertNotIn('name="email"', markup)
        self.assertNotIn("@productive.test", markup)


if __name__ == "__main__":
    unittest.main()
