"""The dashboard opens with what to do, not with what we have.

It used to open with how many companies are in the workspace, which is not a
question anybody starts the day with. The counts are still there; they are no
longer the first thing.

Two rules carry the section:

  nothing renders at zero, because a list that always shows nine rows with
  six of them empty is a list people skim past, and then miss the one that
  mattered;

  every row goes somewhere, because a card with a number and no destination
  makes somebody hunt for the screen it came from.
"""
import unittest

from tests.webbase import WebTest

from src import notify, tasks
from src.web import api, pages


class Ordering(unittest.TestCase):

    def row(self, severity, count=1):
        return {"key": severity, "count": count, "severity": severity,
                "label": severity, "why": "", "where": "/x"}

    def test_severity_decides_the_order(self):
        """Handed to the real function, deliberately out of order. The
        first version of this test sorted a list itself and asserted the
        list was sorted, which proved `list.sort` works."""
        found = tasks.order([
            self.row(notify.WARNING), self.row(notify.INFO),
            self.row(notify.CRITICAL), self.row(notify.ACTION_REQUIRED)])
        self.assertEqual([r["severity"] for r in found],
                         [notify.CRITICAL, notify.ACTION_REQUIRED,
                          notify.WARNING, notify.INFO])

    def test_the_larger_number_comes_first_within_a_severity(self):
        found = tasks.order([
            self.row(notify.WARNING, 2), self.row(notify.WARNING, 9)])
        self.assertEqual([r["count"] for r in found], [9, 2])

    def test_the_severity_words_are_notifys_words(self):
        """One vocabulary across Slack, the task list and every screen."""
        for severity in (notify.CRITICAL, notify.ACTION_REQUIRED,
                         notify.WARNING, notify.INFO):
            self.assertIn(severity, pages.SEVERITY_CLASS)
            self.assertIn(severity, pages.SEVERITY_WORD)
            self.assertIn(severity, tasks.ORDER)
        for kind in tasks.KINDS:
            self.assertIn(tasks.SEVERITY[kind], tasks.ORDER)


class Rendering(unittest.TestCase):

    def test_an_empty_list_says_so_rather_than_rendering_nothing(self):
        html = pages.attention_panel([])
        self.assertIn("Nothing is waiting", html)

    def test_a_row_carries_its_count_reason_and_destination(self):
        html = pages.attention_panel([{
            "key": "approvals", "count": 3,
            "severity": notify.ACTION_REQUIRED,
            "label": "campaign approval waiting",
            "why": "nothing goes out until somebody approves it",
            "where": "/approvals"}])
        self.assertIn("campaign approval waiting", html)
        self.assertIn("nothing goes out until somebody approves it", html)
        self.assertIn('href="/approvals"', html)
        self.assertIn(">3<", html)

    def test_critical_and_warning_do_not_look_the_same(self):
        critical = pages.attention_panel([{
            "key": "k", "count": 1, "severity": notify.CRITICAL,
            "label": "l", "why": "", "where": "/health"}])
        warning = pages.attention_panel([{
            "key": "k", "count": 1, "severity": notify.WARNING,
            "label": "l", "why": "", "where": "/health"}])
        self.assertIn("block", critical)
        self.assertNotIn("block", warning)


class OnTheRealDashboard(WebTest):

    def dashboard(self, email):
        session = self.signin(email)
        status, body, _ = session.get("/")
        self.assertEqual(status, 200)
        return body

    def rows(self):
        from src import repo as repo_module
        repo = repo_module.Repo.for_user("ops@productive.test", "productive")
        return api.dashboard(repo)["attention"]

    def test_the_operator_sees_it_before_the_counts(self):
        """Measured against a tile label rather than the word "companies",
        which also appears in the breadcrumb above everything."""
        body = self.dashboard("ops@productive.test")
        self.assertIn("Needs attention", body)
        self.assertIn("multichannel", body, "the counts wall is still there")
        self.assertLess(body.index("Needs attention"),
                        body.index("multichannel"),
                        "what to do comes before what we have")

    def test_the_client_cut_does_not_carry_it(self):
        """A viewer has no approvals to grant and no jobs to re-run. A
        panel of things they cannot act on is worse than no panel."""
        body = self.dashboard("client@productive.test")
        self.assertNotIn("Needs attention", body)

    def test_the_rows_come_from_canonical_state(self):
        found = self.rows()
        self.assertTrue(found, "the fictional estate has real work waiting")
        for row in found:
            with self.subTest(row=row["key"]):
                self.assertGreater(row["count"], 0, "nothing renders at zero")
                self.assertTrue(row["label"])
                self.assertTrue(row["why"])

    def test_every_row_goes_somewhere_that_exists(self):
        """No dead cards. A destination that 404s is worse than a number
        with no link, because it looks like the product is broken."""
        session = self.signin("ops@productive.test")
        for row in self.rows():
            with self.subTest(where=row["where"]):
                status, _, _ = session.get(row["where"])
                self.assertEqual(status, 200, row["where"])

    def test_a_count_that_falls_to_zero_removes_the_row(self):
        """Asserted by construction rather than by editing the estate: the
        builder only appends when the count is truthy."""
        found = {row["key"] for row in self.rows()}
        self.assertNotIn("failed_jobs", found,
                         "the estate has no failed jobs, so no row")


if __name__ == "__main__":
    unittest.main()
