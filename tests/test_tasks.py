"""Outstanding work, assembled from canonical state rather than stored.

The property worth defending is that a task has no life of its own. It exists
while its condition is true and stops existing when somebody fixes the thing -
never because a status field was ticked.

A stored queue drifts in both directions and neither is detectable from
inside it: it says "handled" about a campaign still sitting at
`awaiting_approval`, or keeps demanding attention for a job that was re-run an
hour ago. So the tests below approve a campaign and expect the row to be gone,
rather than asserting that some resolve() marked it done.

The other property is that one module decides. The dashboard's count and the
work queue's row count come from the same call, so they cannot disagree about
how much work there is - which they would, eventually, as two lists.
"""
import unittest

from tests.webbase import WebTest

from src import campaigns as campaign_store, notify, store, tasks


class TheShape(unittest.TestCase):

    def test_every_kind_has_a_label_and_a_severity(self):
        for kind in tasks.KINDS:
            with self.subTest(kind=kind):
                self.assertIn(kind, tasks.LABEL)
                self.assertIn(kind, tasks.SEVERITY)
                self.assertIn(tasks.SEVERITY[kind], tasks.ORDER)

    def test_severity_then_due_then_size(self):
        rows = [
            tasks.task(tasks.VERIFICATION_PENDING, "w", "", "/x", count=2),
            tasks.task(tasks.REPLY_PROTECTION, "w", "", "/x"),
            tasks.task(tasks.OOO_RETURN, "w", "", "/x", due="2026-12-01"),
            tasks.task(tasks.OOO_RETURN, "w", "", "/x", due="2026-01-01"),
            tasks.task(tasks.VERIFICATION_PENDING, "w", "", "/x", count=9),
        ]
        found = tasks.order(rows)
        self.assertEqual(found[0]["kind"], tasks.REPLY_PROTECTION)
        self.assertEqual([r["due"] for r in found[1:3]],
                         ["2026-01-01", "2026-12-01"])
        self.assertEqual([r["count"] for r in found[3:]], [9, 2])

    def test_a_population_is_not_pretended_to_be_one_thing(self):
        row = tasks.task(tasks.VERIFICATION_PENDING, "w", "", "/contacts",
                         object_type=tasks.POPULATION, count=40)
        self.assertEqual(row["object_type"], tasks.POPULATION)
        self.assertIsNone(row["object_id"])
        self.assertEqual(row["count"], 40)

    def test_the_label_travels_with_the_task(self):
        """`web/pages` imports nothing from the domain, so it cannot look
        the label up for itself."""
        row = tasks.task(tasks.FAILED_JOB, "w", "", "/jobs")
        self.assertEqual(row["kind_label"], tasks.LABEL[tasks.FAILED_JOB])

    def test_the_severities_are_notifys(self):
        for kind in tasks.KINDS:
            self.assertIn(tasks.SEVERITY[kind],
                          (notify.CRITICAL, notify.ACTION_REQUIRED,
                           notify.WARNING, notify.INFO))


class ItIsDerived(WebTest):

    def collect(self, workspace="productive"):
        return tasks.collect(workspace)

    def kinds(self, workspace="productive"):
        return [row["kind"] for row in self.collect(workspace)]

    def test_the_estate_has_real_work_waiting(self):
        self.assertIn(tasks.CAMPAIGN_APPROVAL, self.kinds())

    def test_approving_the_campaign_removes_its_row(self):
        """The whole design in one test. Nothing marks the task done - the
        campaign stops being one, so the row stops existing."""
        before = [r for r in self.collect()
                  if r["kind"] == tasks.CAMPAIGN_APPROVAL]
        self.assertTrue(before)
        target = before[0]["object_id"]

        rows = campaign_store.load()
        for row in rows:
            if row.get("campaign_id") == target:
                row["status"] = campaign_store.APPROVED
        campaign_store.save(rows)
        try:
            after = [r for r in self.collect()
                     if r["kind"] == tasks.CAMPAIGN_APPROVAL]
            self.assertEqual(len(after), len(before) - 1)
            self.assertNotIn(target, [r["object_id"] for r in after])
        finally:
            for row in rows:
                if row.get("campaign_id") == target:
                    row["status"] = campaign_store.AWAITING_APPROVAL
            campaign_store.save(rows)

    def test_nothing_is_written_by_collecting(self):
        import copy
        before = copy.deepcopy(store.load())
        self.collect()
        self.assertEqual(store.load(), before)

    def test_another_workspace_is_another_list(self):
        mine = {r["object_id"] for r in self.collect("productive")
                if r["object_type"] == "campaign"}
        theirs = {r["object_id"] for r in self.collect("demo-client")
                  if r["object_type"] == "campaign"}
        self.assertTrue(mine)
        self.assertFalse(mine & theirs)

    def test_every_row_carries_somewhere_to_go(self):
        for row in self.collect():
            with self.subTest(kind=row["kind"]):
                self.assertTrue(row["where"].startswith("/"))
                self.assertTrue(row["why"])


class OneListTwoViews(WebTest):

    def test_the_dashboard_count_matches_the_queue(self):
        """The reason this module exists. Two lists would drift; one list
        grouped two ways cannot."""
        from src import repo as repo_module
        from src.web import api
        repo = repo_module.Repo.for_user("ops@productive.test", "productive")

        queue = api.task_queue(repo)
        summary = api.dashboard(repo)["attention"]

        by_kind = {}
        for row in queue["tasks"]:
            by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + row["count"]
        self.assertEqual({row["key"]: row["count"] for row in summary},
                         by_kind)

    def test_the_page_lists_the_work(self):
        session = self.signin("ops@productive.test")
        status, body, _ = session.get("/tasks")
        self.assertEqual(status, 200)
        self.assertIn("Work queue", body)
        self.assertIn("Campaign waiting for approval", body)

    def test_a_viewer_is_refused(self):
        session = self.signin("client@productive.test")
        self.assertEqual(session.get("/tasks")[0], 403)

    def test_the_link_is_in_the_nav_for_an_operator(self):
        session = self.signin("ops@productive.test")
        self.assertIn('"/tasks"', session.get("/")[1])

    def test_every_destination_on_the_page_resolves(self):
        session = self.signin("ops@productive.test")
        from src import repo as repo_module
        from src.web import api
        repo = repo_module.Repo.for_user("ops@productive.test", "productive")
        for row in api.task_queue(repo)["tasks"]:
            with self.subTest(where=row["where"]):
                self.assertEqual(session.get(row["where"])[0], 200)


if __name__ == "__main__":
    unittest.main()
