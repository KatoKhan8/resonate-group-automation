"""Search answered questions the pages refuse.

`/search` is gated on `WORKSPACE_VIEW`, and the comment beside that gate
reasons entirely about tenancy: it reads only workspaces the caller is a
member of. That is true, and it is the wrong question. Tenancy says *whose*
data; a role says *which* data, and search never asked.

So a viewer - the client-facing role that `CONTACTS_VIEW` deliberately
denies, and which is refused `/contacts`, `/companies` and `/campaigns` -
could read contact names, titles and addresses, company names and domains,
every campaign id and status, and the record and contact ids embedded in
the result links. Matching on `contact.email` made it an
address-confirmation oracle as well: a prefix long enough to be unique
returns the person it belongs to.

The permission is asked per workspace rather than once, because somebody
may be an operator in one and a viewer in another and the role follows the
workspace, not the person.
"""
import unittest

from src.web import api
from tests.webbase import WebTest

VIEWER = "client@productive.test"
OPERATOR = "ops@productive.test"
ADMIN = "admin@productive.test"
BOTH = "ops@contactout.test"      # operator in one workspace, reviewer in another

TERM = "Lindqvist"


class SearchAsksWhatTheRoleMaySee(WebTest):

    def counts(self, email, term=TERM, workspace=None):
        return api.search(email, term, workspace=workspace)["counts"]

    def kinds(self, email, term=TERM):
        return {hit["kind"] for hit in api.search(email, term)["results"]}

    # ------------------------------------------------------- the defect

    def test_a_viewer_gets_no_contacts(self):
        self.assertNotIn("contact", self.counts(VIEWER))

    def test_a_viewer_gets_no_companies(self):
        self.assertNotIn("company", self.counts(VIEWER, "productive"))

    def test_a_viewer_gets_no_campaigns(self):
        self.assertNotIn("campaign", self.counts(VIEWER, "Productive"))

    def test_a_viewer_cannot_confirm_an_address(self):
        """The oracle. The address is the search term."""
        rec = self.a_record("productive")
        contacts = [c for c in rec.get("contacts") or [] if c.get("email")]
        if not contacts:
            self.skipTest("the estate has no addressed contact")
        address = contacts[0]["email"]
        self.assertEqual(self.counts(VIEWER, address), {})

    # ---------------------------------------------- and it still works

    def test_an_operator_still_finds_contacts(self):
        """Otherwise the guard denies everybody and proves nothing."""
        self.assertIn("contact", self.counts(OPERATOR))

    def test_an_operator_still_finds_campaigns(self):
        self.assertIn("campaign", self.counts(OPERATOR, "Productive"))

    def test_the_same_term_returns_more_to_an_operator_than_a_viewer(self):
        self.assertGreater(sum(self.counts(OPERATOR).values()),
                           sum(self.counts(VIEWER).values()))

    def test_a_viewer_can_still_find_their_own_workspace(self):
        """`WORKSPACE_VIEW` is what the route is gated on, and it is what a
        viewer has. Narrowing the results must not have emptied the
        feature for them."""
        self.assertIn("workspace", self.kinds(VIEWER, "productive"))

    def test_the_role_follows_the_workspace(self):
        """One person, two workspaces, two roles. Asking once would have
        applied the wrong answer to one of them."""
        spaces = {}
        for slug in ("contactout", "productive"):
            spaces[slug] = api.search(BOTH, TERM, workspace=slug)["counts"]
        self.assertNotEqual(spaces["contactout"], spaces["productive"])


class TheRouteStillRefusesTheRightPeople(WebTest):
    """The page-level gates, unchanged by this."""

    def test_a_viewer_is_still_refused_the_pages_themselves(self):
        viewer = self.signin(VIEWER)
        self.switch(viewer, "productive")
        for path in ("/contacts", "/companies", "/campaigns"):
            self.assertEqual(viewer.get(path)[0], 403, path)

    def test_and_search_itself_still_answers_them(self):
        """It is not refused outright - a viewer may search their own
        workspaces. It answers with less."""
        viewer = self.signin(VIEWER)
        self.switch(viewer, "productive")
        self.assertEqual(viewer.get("/search?q=productive")[0], 200)

    def test_the_page_renders_no_contact_for_a_viewer(self):
        """Asserted through the rendered page, not only the api, because
        the page is what a person reads.

        Not "the term is absent from the HTML": the page echoes the query
        back in its no-matches line, and that is the viewer's own input.
        What must be absent is a result - a link to a contact, and any
        count above zero.
        """
        viewer = self.signin(VIEWER)
        self.switch(viewer, "productive")
        _, body, _ = viewer.get("/search?q=" + TERM)
        self.assertIn("0 match(es)", body)
        self.assertNotIn("/contacts/", body)

    def test_and_it_renders_them_for_an_operator(self):
        """The same page, the same term, a role that may see them."""
        operator = self.signin(OPERATOR)
        self.switch(operator, "productive")
        _, body, _ = operator.get("/search?q=" + TERM)
        self.assertNotIn("0 match(es)", body)
        self.assertIn("/contacts/", body)


if __name__ == "__main__":
    unittest.main()
