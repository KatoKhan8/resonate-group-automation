"""The import had no second step, so nothing could be imported.

`POST /upload/commit` has existed for as long as the upload page has: it
reads the parsed preview, writes the records and redirects to the batch.
Nothing ever rendered a form that posted to it. The preview ended at
"Parsed, nothing committed" and stayed there - while the dashboard offered
importing leads as the first thing an operator does, and the acceptance
suite posted to `/upload/commit` to prove a viewer could not reach it,
which is true of a route nobody could reach.

This is the file that would have caught it, and it catches it the only way
that means anything: by driving the real page over real HTTP, reading the
button out of the returned HTML, and posting what the button offers rather
than what the route is known to be called.

The second defect is smaller and was found looking for the first. An import
is the largest single change anybody makes to a workspace, and it was the
one durable write with no audit entry - so the log could not say that it
happened, who did it, or how much of it there was.
"""
import io
import re
import unittest
import urllib.request
import uuid

from src import workspaces
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"

CSV = ("Company Name,Company Website,First Name,Last Name,Work Email\r\n"
       "Northwind Trading,northwind-{t}.test,Ada,Rowe,ada@northwind-{t}.test\r\n"
       "Northwind Trading,northwind-{t}.test,Bo,Vale,bo@northwind-{t}.test\r\n"
       "Cairn Systems,cairn-{t}.test,Cass,Ng,cass@cairn-{t}.test\r\n")


def multipart(fields, filename, blob):
    """A real multipart body.

    The route reads `files`, not `fields`, so a urlencoded post would
    exercise a path no browser takes and prove nothing about the one that
    ships.
    """
    line = "b" + uuid.uuid4().hex
    out = io.BytesIO()
    for key, value in fields.items():
        out.write(("--%s\r\n" % line).encode())
        out.write(('Content-Disposition: form-data; name="%s"\r\n\r\n'
                   % key).encode())
        out.write(("%s\r\n" % value).encode())
    out.write(("--%s\r\n" % line).encode())
    out.write(('Content-Disposition: form-data; name="csv"; '
               'filename="%s"\r\n' % filename).encode())
    out.write(b"Content-Type: text/csv\r\n\r\n")
    out.write(blob + b"\r\n")
    out.write(("--%s--\r\n" % line).encode())
    return "multipart/form-data; boundary=" + line, out.getvalue()


class TheImportCompletes(WebTest):
    """One estate per class, so each test brings its own domains and batch."""

    def setUp(self):
        self.tag = uuid.uuid4().hex[:8]
        self.batch = "b-" + self.tag
        self.session = self.signin(OPERATOR)
        self.switch(self.session, "productive")

    def upload(self, text=None):
        """POST the file the way the browser does. Returns the page."""
        blob = (CSV.format(t=self.tag) if text is None else text).encode()
        content_type, body = multipart(
            {"csrf": self.session.csrf("/upload"), "batch": self.batch},
            "leads.csv", blob)
        request = urllib.request.Request(
            self.session.base + "/upload", body,
            headers={"Content-Type": content_type})
        try:
            with self.session.opener.open(request, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode("utf-8", "replace")

    def domains(self):
        return {r.get("domain") for r in self.records_of("productive")}

    def commit(self, token=None):
        return self.session.post(
            "/upload/commit", {"csrf": token or self.session.csrf()})

    # --------------------------------------------------- the missing step

    def test_the_preview_offers_a_way_to_commit(self):
        """The defect. Everything below depends on this being true."""
        status, body = self.upload()
        self.assertEqual(status, 200)
        self.assertIn("Parsed, nothing committed", body)
        self.assertIn('action="/upload/commit"', body,
                      "the preview is a dead end: nothing on the page posts "
                      "to the route that writes the records")

    def test_the_button_says_what_it_will_write(self):
        """Two companies and three people, not the four rows uploaded and
        not the two the second person shares a company with."""
        _, body = self.upload()
        form = body[body.index('action="/upload/commit"'):]
        button = re.search(r"<button[^>]*>(.*?)</button>", form, re.S)
        self.assertTrue(button, "no button in the commit form")
        label = re.sub(r"\s+", " ", button.group(1)).strip()
        self.assertEqual(label, "Import 2 companies and 3 people")

    def test_posting_what_the_page_offers_imports_the_leads(self):
        """The whole chain: parse, render, submit, records on disk."""
        _, body = self.upload()
        before = self.domains()
        self.assertNotIn("northwind-%s.test" % self.tag, before)

        token = re.search(
            r'action="/upload/commit"[^>]*>'
            r'<input type="hidden" name="csrf" value="([^"]+)"', body)
        self.assertTrue(token, "the commit form carries no csrf token")
        status, _, _ = self.commit(token.group(1))
        self.assertEqual(status, 200)

        after = self.domains()
        self.assertIn("northwind-%s.test" % self.tag, after)
        self.assertIn("cairn-%s.test" % self.tag, after)
        self.assertEqual(len(after - before), 2)

    def test_the_people_arrive_with_the_companies(self):
        self.upload()
        self.commit()
        rows = {r["domain"]: r for r in self.records_of("productive")}
        northwind = rows["northwind-%s.test" % self.tag]
        self.assertEqual(
            {c["email"] for c in northwind.get("contacts") or []},
            {"ada@northwind-%s.test" % self.tag,
             "bo@northwind-%s.test" % self.tag})

    def test_nothing_is_written_by_previewing(self):
        before = self.domains()
        self.upload()
        self.assertEqual(self.domains(), before, "the preview wrote records")

    def test_a_file_with_nothing_usable_offers_no_button(self):
        """Absent rather than present and inert. An operator who clicks
        Import and is given a batch of nothing has been told something
        untrue about their file."""
        status, body = self.upload(
            "Company Name,Company Website\r\nNowhere Ltd,not a domain\r\n")
        self.assertEqual(status, 200)
        self.assertNotIn('action="/upload/commit"', body)
        self.assertIn("Nothing here can be imported", body)

    def test_committing_twice_does_not_import_twice(self):
        self.upload()
        self.commit()
        count = len(self.records_of("productive"))
        status, again, _ = self.commit()
        self.assertEqual(len(self.records_of("productive")), count)
        self.assertEqual(status, 400)
        self.assertIn("Nothing to commit", again)

    # ------------------------------------------------------- and audited

    def entries(self):
        return [e for e in workspaces.audit("productive", limit=5000)
                if e.get("action") == "batch.committed"]

    def test_the_import_is_in_the_audit_log(self):
        before = len(self.entries())
        self.upload()
        self.commit()
        self.assertEqual(len(self.entries()) - before, 1)

    def test_it_records_who_and_how_much(self):
        self.upload()
        self.commit()
        mine = [e for e in self.entries()
                if e.get("resource_id") == self.batch]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["actor"], OPERATOR)
        self.assertEqual(mine[0]["workspace"], "productive")
        self.assertEqual(mine[0]["after"], {"companies": 2, "contacts": 3})

    def test_a_refused_commit_is_not_audited_as_one(self):
        """Only the write is the event."""
        before = len(self.entries())
        self.commit()
        self.assertEqual(len(self.entries()), before)


if __name__ == "__main__":
    unittest.main()
