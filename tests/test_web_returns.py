"""The out-of-office returns screen, over real HTTP.

Three things are worth asserting about a view like this and only one of them
is the HTML. A screen that surfaces who is on leave can leak one tenant's
people into another's browser, and hiding a link in the sidebar is not
authorisation - the refusal has to come from the server when the path is
typed directly.

The third is the safety property the module underneath rests on: rendering
this page must not lift anybody's stop. A view that quietly reopened a
contact would be the worst possible place to put that behaviour, because
nobody would look for it here.

Assertions are made against a named panel rather than the whole page. The
first version of this file asserted that a name and a date appeared
somewhere in the body, and passed while the person was sitting in the
"Not yet" table - the page was right and the test was measuring nothing.
"""
from tests.webbase import WebTest

from src import account, events, store

RECORDED_AT = "2026-09-02T09:00:00+00:00"
RETURN_DATE = "2026-09-01"


def panel_of(body, title):
    """The one panel, so a row in another table cannot satisfy a check."""
    marker = "<h3>" + title + "</h3>"
    if marker not in body:
        return ""
    return body.split(marker, 1)[1].split("<div class=\"panel\">", 1)[0]


class ReturnsView(WebTest):

    def seed_absence(self, client="productive", return_date=RETURN_DATE,
                     status="resolved"):
        recs = store.load()
        # A contact who has not replied. The demo estate stamps its replies
        # with `store.now()`, so anybody who has replied is always "more
        # recent" than a fixed fixture timestamp and correctly reads as
        # having come back to us since - true, and not this screen.
        rec = next(r for r in recs
                   if r.get("client") == client and r.get("contacts")
                   and not account.replies(r))
        contact = rec["contacts"][0]
        events.record(rec, events.OUT_OF_OFFICE_RECORDED,
                      contact_key=contact["key"], channel="email",
                      at=RECORDED_AT, provider="emailbison",
                      absence_kind="autoresponder",
                      return_date=return_date, return_status=status,
                      reason="a named month and day")
        store.save(recs)
        return rec, contact

    def clear_absences(self):
        recs = store.load()
        for rec in recs:
            rec["events"] = [e for e in (rec.get("events") or [])
                             if e.get("type") != events.OUT_OF_OFFICE_RECORDED]
        # Taking back this class's own writes to a shared estate, which is the
        # only sanctioned use of the flag - `store.save` says why, and
        # `test_invariants` forbids any `src/` module from reaching for it.
        store.save(recs, allow_history_loss=True)

    def tearDown(self):
        self.clear_absences()
        super().tearDown()

    def name_of(self, contact):
        return contact.get("name") or contact["key"]

    # ------------------------------------------------------------- rendering

    def test_an_operator_sees_somebody_who_is_back(self):
        rec, contact = self.seed_absence()
        session = self.signin("ops@productive.test")
        status, body, _ = session.get("/replies/returns")
        self.assertEqual(status, 200)
        self.assertIn("Out-of-office returns", body)
        back = panel_of(body, "Back now")
        self.assertIn(self.name_of(contact), back)
        self.assertIn(RETURN_DATE, back)

    def test_the_page_renders_with_nothing_recorded(self):
        """An empty queue is a normal state, not a blank page."""
        session = self.signin("ops@productive.test")
        status, body, _ = session.get("/replies/returns")
        self.assertEqual(status, 200)
        self.assertIn("Nobody is due back today",
                      panel_of(body, "Back now"))

    def test_somebody_not_due_yet_is_not_in_the_back_now_table(self):
        """The distinction the whole screen turns on."""
        rec, contact = self.seed_absence(return_date="2099-01-01")
        session = self.signin("ops@productive.test")
        _, body, _ = session.get("/replies/returns")
        self.assertNotIn(self.name_of(contact), panel_of(body, "Back now"))
        self.assertIn(self.name_of(contact), panel_of(body, "Not yet"))

    def test_an_unreadable_date_is_shown_rather_than_hidden(self):
        """The queue that would otherwise be invisible."""
        rec, contact = self.seed_absence(return_date=None,
                                         status="unknown:vague_period")
        session = self.signin("ops@productive.test")
        status, body, _ = session.get("/replies/returns")
        self.assertEqual(status, 200)
        asked = panel_of(body, "They did not say when")
        self.assertIn(self.name_of(contact), asked)
        self.assertIn("unknown:vague_period", asked)

    # ------------------------------------------------------------------ RBAC

    def test_a_viewer_is_refused_by_the_server(self):
        """Not merely un-linked. A viewer who types the path gets nothing."""
        rec, contact = self.seed_absence()
        session = self.signin("client@productive.test")
        status, body, _ = session.get("/replies/returns")
        self.assertEqual(status, 403)
        self.assertNotIn(RETURN_DATE, body)

    def test_an_anonymous_request_never_reaches_the_data(self):
        """The opener follows the redirect to sign-in, so the status is
        200 and the body is the login page. What matters is that no
        absence reached it."""
        rec, contact = self.seed_absence()
        _, body, _ = self.anonymous().get("/replies/returns")
        self.assertNotIn(RETURN_DATE, body)
        self.assertNotIn(self.name_of(contact), body)
        self.assertIn("Sign in", body)

    def test_the_link_is_absent_for_a_viewer(self):
        session = self.signin("client@productive.test")
        _, body, _ = session.get("/")
        self.assertNotIn("/replies/returns", body)

    def test_the_link_is_present_for_an_operator(self):
        session = self.signin("ops@productive.test")
        _, body, _ = session.get("/")
        self.assertIn("/replies/returns", body)

    # --------------------------------------------------------------- tenancy

    def test_another_workspace_does_not_see_these_people(self):
        """The leak this screen could cause: who is on leave, at whose
        client. Scoped in the view, asserted from another tenant."""
        rec, contact = self.seed_absence(client="productive")
        session = self.signin("ops@demo-client.test")
        status, body, _ = session.get("/replies/returns")
        self.assertEqual(status, 200)
        self.assertNotIn(self.name_of(contact), body)
        self.assertNotIn(rec["company"], body)

    # ---------------------------------------------------------- it only reads

    def test_rendering_does_not_lift_the_stop(self):
        """The property the module rests on, asserted where somebody would
        least think to look for a write."""
        rec, contact = self.seed_absence()
        recs = store.load()
        person = next(c for c in
                      next(r for r in recs if r["id"] == rec["id"])["contacts"]
                      if c["key"] == contact["key"])
        person["stopped"] = {"since": RECORDED_AT, "reason": "not_now",
                             "why": "out of office"}
        store.save(recs)

        session = self.signin("ops@productive.test")
        self.assertEqual(session.get("/replies/returns")[0], 200)

        after = next(c for c in
                     next(r for r in store.load() if r["id"] == rec["id"])
                     ["contacts"] if c["key"] == contact["key"])
        self.assertEqual((after.get("stopped") or {}).get("reason"), "not_now",
                         "the stop is still there after rendering")


class TheViewGuardsItself(WebTest):
    """Two guards cover this path and each one alone is sufficient.

    The route table refuses `/replies/returns` without `operations.view`,
    and `returns_view` requires it again. Removing either leaves the HTTP
    tests green, which is what defence in depth looks like from outside -
    and also means neither of those tests proves the guard it names. This
    calls the view directly so the second one is held down on its own.
    """

    def test_a_viewer_cannot_call_the_view_at_all(self):
        from src import repo as repo_module, workspaces
        from src.web import api
        repo = repo_module.Repo.for_user("client@productive.test",
                                         "productive")
        with self.assertRaises(workspaces.NotPermitted):
            api.returns_view(repo)

    def test_an_operator_can(self):
        from src import repo as repo_module
        from src.web import api
        repo = repo_module.Repo.for_user("ops@productive.test", "productive")
        view = api.returns_view(repo)
        self.assertEqual(view["workspace"], "productive")
        self.assertIn("due", view)
