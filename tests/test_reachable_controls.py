"""Two working things nothing on a page could reach.

The first is the referral workflow. `GET /replies/context/<record>/<contact>`
is routed, rendered, and is the *only* place `POST /replies/referral/add` is
offered - and nothing linked to it. It is not in the navigation, and the
Inbox rows linked to the company instead. Meanwhile `src/tasks.py` files a
REVIEW_REFERRAL row pointing at `/replies?carries=referral` and the Inbox
prints a chip counting them, so the product told an operator a referral
needed a person and then offered no control to act on it.

The second is smaller and is about honesty rather than reach: the upload
preview lists `excluded[:100]` immediately above the sentence "Nothing
disappears. Every excluded row is listed with its reason." On a file with
more than a hundred bad rows those two disagreed, and the operator had no
way to see that they did.

Both are asserted the only way that means anything for this class of
defect: by driving the real page over real HTTP and reading the links and
the table out of the returned HTML, never by asserting that a route exists.
"""
import io
import re
import unittest
import urllib.error
import urllib.request
import uuid

from tests.webbase import WebTest

OPERATOR = "ops@productive.test"

CONTEXT_HREF = re.compile(r'href="(/replies/context/[^"]+)"')


def hrefs(html):
    return re.findall(r'href="([^"]+)"', html)


def rows_of(html, header):
    """The `<tr>`s of the one table on the page carrying this header."""
    table = re.search(r"<table[^>]*>(?:(?!</table>).)*?" + re.escape(header)
                      + r".*?</table>", html, re.S)
    if not table:
        return []
    return re.findall(r"<tr>(?:(?!</tr>).)*</tr>", table.group(0), re.S)[1:]


# ------------------------------------------- the referral workflow is reachable


class TheInboxReachesTheReplyPage(WebTest):
    """The Inbox is the only screen that lists replies, so it is the only
    screen that can lead to one."""

    def setUp(self):
        self.session = self.signin(OPERATOR)
        self.switch(self.session, "productive")

    def page(self, path="/replies"):
        status, body, _ = self.session.get(path)
        self.assertEqual(status, 200, body[:300])
        return body

    def matched(self):
        """The reply rows the page could legitimately link out of."""
        from src import repo as repo_module
        from src.web import api

        repo = repo_module.Repo.for_user(OPERATOR, "productive")
        rows = api.reply_inbox(repo)["rows"]
        self.assertTrue(rows, "the demo estate has no replies to assert on")
        return [r for r in rows if r["matched"]]

    # ------------------------------------------------------- the defect

    def test_the_inbox_links_to_the_reply_context_page(self):
        found = CONTEXT_HREF.findall(self.page())
        self.assertTrue(
            found,
            "the Inbox links no reply to /replies/context/: the page that "
            "renders the referral control cannot be reached from anywhere")

    def test_every_matched_reply_row_carries_its_own_link(self):
        """Not one link somewhere on the page - the row for that person."""
        found = set(CONTEXT_HREF.findall(self.page()))
        for row in self.matched():
            self.assertIn(
                f'/replies/context/{row["record_id"]}/{row["contact_key"]}',
                found)

    def test_the_link_the_page_offers_actually_renders(self):
        """Posting the URL shape from the route is not the same test: this
        follows what the page printed."""
        found = CONTEXT_HREF.findall(self.page())
        self.assertTrue(found, "the Inbox offers no such link to follow")
        status, body, _ = self.session.get(found[0])
        self.assertEqual(status, 200, body[:300])
        self.assertIn("What this does", body)

    def test_the_needs_attention_panel_links_too(self):
        """The panel above the list is where a reply that still needs a
        person appears, so it is the first place somebody clicks."""
        body = self.page()
        panel = re.search(r"Needs attention.*?</table>", body, re.S)
        self.assertTrue(panel, "no needs-attention table on the Inbox")
        rows = [r for r in self.matched()
                if f'>{r["name"] or r["contact_key"]}<' in panel.group(0)
                or r["contact_key"] in panel.group(0)]
        self.assertTrue(rows, "no matched reply is waiting on a person")
        self.assertTrue(
            CONTEXT_HREF.search(panel.group(0)),
            "a reply is listed as needing a person with no link to the page "
            "where a person could do anything about it")

    def test_an_unmatched_reply_is_text_rather_than_a_dead_link(self):
        """`/replies/context/` resolves the contact and 404s when it
        cannot. A reply whose problem is that nobody knows who it is has
        nothing to link to, and offering a 404 would be worse than
        offering nothing."""
        from src.web import pages

        row = {"record_id": "rec-1", "company": "Northwind", "at": "2026-01-01",
               "contact_key": "ghost", "name": "", "channel": "email",
               "classification": "unknown", "paused": False, "matched": False,
               "handled": None, "follow_up": None, "referral": None}
        html = pages.replies([row])
        self.assertNotIn("/replies/context/", html)
        self.assertIn("ghost", html)


class TheReferralChainIsWalkable(WebTest):
    """The chain the work queue promises, walked end to end.

    `tasks.py` files REVIEW_REFERRAL pointing at `/replies?carries=referral`
    and the Inbox prints a chip counting them. From there an operator has to
    reach `_referred_panel`, which is the only renderer of
    `/replies/referral/add` anywhere in the product. Every link in that
    chain is followed here out of the HTML the previous one returned.
    """

    def setUp(self):
        import re as _re
        import zlib

        from src import replies as reply_model
        from src import repo as repo_module

        self.session = self.signin(OPERATOR)
        self.switch(self.session, "productive")
        self.repo = repo_module.Repo.for_user(OPERATOR, "productive")
        self.rec = next(r for r in self.repo.records() if r.get("contacts"))
        self.who = self.rec["contacts"][0]["key"]
        # A referral of this test's own, addressed and timed from its name:
        # the estate is shared across the class and an event id is a hash
        # of the reply's coordinates rather than of its text.
        name = self.id().rsplit(".", 1)[-1]
        self.address = _re.sub(r"[^a-z]", "", name) + "@newperson.test"
        minutes = zlib.crc32(name.encode("utf-8")) % 600
        reply_model.apply(
            self.rec, self.who,
            f"You should email {self.address} instead.",
            at="2026-09-02T{:02d}:{:02d}:00+00:00".format(
                9 + minutes // 60, minutes % 60),
            channel="email")
        self.repo.save_records([self.rec])

    def page(self, path):
        status, body, _ = self.session.get(path)
        self.assertEqual(status, 200, body[:300])
        return body

    def test_the_chip_the_work_queue_points_at_reaches_the_add_control(self):
        listing = self.page("/replies?carries=referral")
        targets = [t for t in CONTEXT_HREF.findall(listing)
                   if t.endswith(f'/{self.rec["id"]}/{self.who}')]
        self.assertTrue(
            targets,
            "the referral view lists the reply and does not link it to the "
            "page that can add the person it named")
        control = self.page(targets[0])
        self.assertIn("Who they pointed us at", control)
        self.assertIn('action="/replies/referral/add"', control)
        self.assertIn(self.address, control)


# ------------------------------------------ the preview says what it hides


def multipart(fields, filename, blob):
    """A real multipart body: the route reads files, not fields."""
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


class ThePreviewStatesTheCapItApplies(WebTest):

    HEADER = "Company Name,Company Website\r\n"

    def setUp(self):
        self.tag = uuid.uuid4().hex[:8]
        self.session = self.signin(OPERATOR)
        self.switch(self.session, "productive")

    def upload(self, text):
        content_type, body = multipart(
            {"csrf": self.session.csrf("/upload"),
             "batch": "b-" + self.tag},
            "leads.csv", text.encode())
        request = urllib.request.Request(
            self.session.base + "/upload", body,
            headers={"Content-Type": content_type})
        try:
            with self.session.opener.open(request, timeout=60) as r:
                status, page = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            with e:
                status, page = e.code, e.read().decode("utf-8", "replace")
        self.assertEqual(status, 200, page[:300])
        return page

    def bad(self, count):
        """Rows with no usable domain. Excluded, cheaply and locally."""
        return self.HEADER + "".join(
            f"Nowhere {n},\r\n" for n in range(count))

    # ------------------------------------------------------- the defect

    def test_a_long_exclusion_list_says_how_much_it_is_showing(self):
        page = self.upload(self.bad(130))
        self.assertEqual(len(rows_of(page, "why excluded")), 100,
                         "the table is not capped at a hundred any more; "
                         "this test is asserting about the wrong thing")
        self.assertIn("Showing the first 100 of 130 excluded rows.", page,
                      "the preview lists a hundred rows under a sentence "
                      "promising all of them, and says nothing about the "
                      "difference")

    def test_the_promise_underneath_is_still_made(self):
        """The line qualifies that sentence, so it has to be beside it."""
        page = self.upload(self.bad(130))
        self.assertIn("Every excluded row is listed with its", page)
        self.assertIn("Showing the first 100 of 130", page)
        self.assertLess(page.index("Showing the first 100 of 130"),
                        page.index("Every excluded row is listed"))

    def test_a_short_list_claims_nothing(self):
        """A file that fits is not told it was truncated."""
        page = self.upload(self.bad(3))
        self.assertEqual(len(rows_of(page, "why excluded")), 3)
        self.assertNotIn("Showing the first 100", page)


if __name__ == "__main__":
    unittest.main()
