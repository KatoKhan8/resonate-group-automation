"""A preview parsed in one workspace does not commit into another.

`/upload/commit` holds the parsed batch in `STATE["uploads"]`, keyed by the
session token alone. The route then re-resolves `repo` from the session, so a
member of two workspaces who parses a file in one, switches with
`/select-workspace`, and commits, lands those rows in the other.

Everything inside `upload.commit` scopes to that fresh `repo`: `repo.records()`
builds the merge index and `repo.client` stamps each new record. So the rows
are written into a workspace whose suppression list, engagement history and
hygiene index they were never checked against - which is exactly the check
`upload.parse` is handed `history` and `suppress` to perform, made worthless
by a switch between the two calls.

The guard is in the service rather than in the route, so a second caller
cannot reintroduce the hole by forgetting it.
"""
import unittest

from src.web import upload
from tests.test_workspace_isolation_attacks import (Estate, ALPHA, BRAVO)

CSV = (b"company,domain\r\n"
       b"Northwind Ltd,northwind.test\r\n"
       b"Contoso Ltd,contoso.test\r\n")


class APreviewIsBoundToTheWorkspaceItWasParsedIn(Estate):

    def parsed_in_alpha(self):
        report = upload.parse(CSV, client=ALPHA, batch="march")
        self.assertEqual(report["client"], ALPHA)
        self.assertTrue(report["rows"])
        return report

    def domains_of(self, repo):
        return {str(r.get("domain") or "").lower() for r in repo.records()}

    # ----------------------------------------------------------- the defect

    def test_committing_alphas_preview_through_bravo_is_refused(self):
        with self.assertRaises(upload.UploadRefused):
            upload.commit(self.b, self.parsed_in_alpha())

    def test_bravo_gains_nothing_from_the_attempt(self):
        before = self.domains_of(self.b)
        try:
            upload.commit(self.b, self.parsed_in_alpha())
        except upload.UploadRefused:
            pass
        self.assertEqual(self.domains_of(self.b), before)
        self.assertNotIn("northwind.test", self.domains_of(self.b))

    def test_alpha_gains_nothing_either_because_nothing_was_written(self):
        """The refusal is not a redirect: it writes into neither workspace."""
        before = self.domains_of(self.a)
        try:
            upload.commit(self.b, self.parsed_in_alpha())
        except upload.UploadRefused:
            pass
        self.assertEqual(self.domains_of(self.a), before)

    def test_the_refusal_says_which_problem_it_is(self):
        try:
            upload.commit(self.b, self.parsed_in_alpha())
        except upload.UploadRefused as e:
            self.assertIn("workspace", str(e).lower())
        else:
            self.fail("commit was not refused")

    # ------------------------------------------- and the path still works

    def test_alpha_can_still_commit_its_own_preview(self):
        """Otherwise the guard refuses everything and proves nothing."""
        upload.commit(self.a, self.parsed_in_alpha())
        self.assertIn("northwind.test", self.domains_of(self.a))
        self.assertIn("contoso.test", self.domains_of(self.a))

    def test_bravo_can_commit_a_preview_parsed_in_bravo(self):
        report = upload.parse(CSV, client=BRAVO, batch="march")
        upload.commit(self.b, report)
        self.assertIn("northwind.test", self.domains_of(self.b))

    def test_the_same_company_may_be_committed_by_both_workspaces(self):
        """Two clients talking to one company is the normal case, not a leak.

        The guard must refuse a misdirected *preview*, not a shared domain.
        """
        upload.commit(self.a, self.parsed_in_alpha())
        upload.commit(self.b, upload.parse(CSV, client=BRAVO, batch="march"))
        self.assertIn("northwind.test", self.domains_of(self.a))
        self.assertIn("northwind.test", self.domains_of(self.b))

    def test_the_already_committed_guard_still_fires(self):
        """The new refusal sits beside it and must not have displaced it."""
        report = self.parsed_in_alpha()
        upload.commit(self.a, report)
        report["committed"] = True
        with self.assertRaises(upload.UploadRefused):
            upload.commit(self.a, report)


if __name__ == "__main__":
    unittest.main()
