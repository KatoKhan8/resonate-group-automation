"""A request that cannot arrive whole is refused, not read short.

`_form` read `min(length, MAX_BYTES + 4096)` from the socket, dropped the
remainder, and never compared what arrived against what was announced.
`upload.parse` re-checks the size afterwards, so the loss was caught only
while the *surviving* CSV was still over `MAX_BYTES` - a margin of 4096
bytes less the multipart framing, about 3.5KB.

The upload form's `notes` field has no `maxlength`, so a long note eats
that margin and the truncated file then passes the size check. Measured
before the fix: a 300,000 row, 77MB export with a 5,000 character note was
accepted as 32,893 rows. The preview said "32,893 uploaded, 0 invalid",
the button offered to import 32,893 companies, and the audit entry
recorded 32,893 - because 32,893 was what survived the socket read, and
nothing anywhere knew that was not the number in the file. 267,107 rows
disappeared leaving one ragged row behind.

"Never silently discard meaningful imported data" is the rule that broke,
and the announced `Content-Length` is enough to refuse on before a single
byte is read.
"""
import io
import unittest
import urllib.error
import urllib.request
import uuid

from src.web import upload
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"


def multipart(fields, filename, blob):
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


class AnOversizedUploadIsRefused(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)
        self.switch(self.session, "productive")

    def rows(self, count):
        head = b"company,domain\r\n"
        body = b"".join(b"Company %d,company%d.test\r\n" % (i, i)
                        for i in range(count))
        return head + body

    def post(self, blob, notes=""):
        content_type, body = multipart(
            {"csrf": self.session.csrf("/upload"), "batch": "big",
             "notes": notes}, "leads.csv", blob)
        request = urllib.request.Request(
            self.session.base + "/upload", body,
            headers={"Content-Type": content_type})
        try:
            with self.session.opener.open(request, timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode("utf-8", "replace")

    def oversized(self):
        """Comfortably past the cap plus its slack."""
        blob = self.rows(400_000)
        self.assertGreater(len(blob), upload.MAX_BYTES + 4096)
        return blob

    # --------------------------------------------------------- the defect

    def test_a_file_past_the_cap_is_refused_rather_than_shortened(self):
        status, body = self.post(self.oversized())
        self.assertEqual(status, 413)
        self.assertIn("too large", body.lower())

    def test_a_long_note_cannot_buy_a_silent_truncation(self):
        """The exact shape that made it silent: the note consumed the
        4096-byte slack, so what survived was under the cap and passed
        `upload.parse`'s own size check."""
        status, body = self.post(self.oversized(), notes="x" * 5000)
        self.assertEqual(status, 413)
        self.assertNotIn("Parsed, nothing committed", body)

    def test_nothing_is_imported_by_the_refusal(self):
        before = {r.get("domain") for r in self.records_of("productive")}
        self.post(self.oversized(), notes="x" * 5000)
        self.assertEqual(
            {r.get("domain") for r in self.records_of("productive")}, before)

    def test_the_refusal_says_what_the_limit_is(self):
        _, body = self.post(self.oversized())
        self.assertIn(str(upload.MAX_BYTES // (1024 * 1024)), body)

    # ------------------------------------------------- and it still works

    def test_a_file_inside_the_cap_is_parsed_as_before(self):
        """Otherwise the guard refuses everything and proves nothing."""
        status, body = self.post(self.rows(200))
        self.assertEqual(status, 200)
        self.assertIn("Parsed, nothing committed", body)

    def test_a_file_just_under_the_cap_is_still_accepted(self):
        blob = self.rows(150_000)
        while len(blob) > upload.MAX_BYTES - 4096:
            blob = blob[:blob.rfind(b"\r\n", 0, len(blob) - 2) + 2]
        self.assertLess(len(blob), upload.MAX_BYTES)
        status, body = self.post(blob)
        self.assertEqual(status, 200)
        self.assertIn("Parsed, nothing committed", body)

    def test_an_ordinary_form_post_is_unaffected(self):
        """`_form` serves every POST, not only the upload."""
        status, _, _ = self.session.post(
            "/select-workspace",
            {"csrf": self.session.csrf(), "workspace": "productive"})
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
