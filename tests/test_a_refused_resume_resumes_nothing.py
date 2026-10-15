"""A refused resume is reported as refused, and resumes nothing.

`orchestrator.resume` re-runs the full validation rather than clearing the
pause flag, and refuses with `NotReady` when it does not pass - that half is
tested (`test_orchestration`). The ROUTE is the untested half: the operator
clicks the route, not the orchestrator.

`api.resume_campaign` translates the orchestrator's exception into
`ActionRefused` naming it, and only on success saves the campaign and writes
the `campaign.resumed` audit row. A route that swallowed the refusal instead
would report a resume that did not happen - status flipped, audit row
written, operator believing sends have restarted - which on a verb whose
whole job is to put a paused sequence back in front of people is the
expensive direction to be wrong in.

The fixture campaign is paused by hand and fails validation honestly (it has
no records, no approvals, no drafts), so `orchestrator.resume` refuses for
real reasons and the route's translation is the only thing under test. No
provider is contacted: the refusal happens before `_resume_at_providers`,
and that ordering is part of what is being pinned.
"""
import unittest

from src import campaigns
from src.web import api
from tests.webbase import WebTest


class ARefusedResumeResumesNothing(WebTest):

    def setUp(self):
        super().setUp()
        from src import repo as repo_module

        self.repo = repo_module.Repo.for_user("ops@productive.test",
                                              "productive")
        name = self.id().rsplit(".", 1)[-1][:40]
        row = campaigns.new_campaign(
            f"resume-{name}", "productive", "A resume-refusal test",
            created_by="ops@productive.test")
        row["status"] = campaigns.PAUSED
        row["pause"] = {"since": "2026-10-01T00:00:00Z",
                        "reason": "paused by hand for this test"}
        self.repo.save_campaign(row)
        self.campaign_id = row["campaign_id"]

    def test_the_refusal_reaches_the_caller_and_nothing_is_recorded(self):
        with self.assertRaises(api.ActionRefused) as raised:
            api.resume_campaign(self.repo, self.campaign_id,
                                by="ops@productive.test")
        self.assertIn(
            "NotReady: cannot resume", str(raised.exception),
            "the route must name the orchestrator's refusal, not swallow it "
            f"or reword it: {raised.exception}")

        after = self.repo.campaign(self.campaign_id)
        self.assertEqual(
            after.get("status"), campaigns.PAUSED,
            "a refused resume changed the campaign status anyway")
        self.assertTrue(
            (after.get("pause") or {}).get("since"),
            "a refused resume cleared the pause anyway")

        from src import workspaces as ws

        resumed = [row for row in ws.audit(workspace_slug="productive",
                                           action="campaign.resumed")
                   if row.get("resource_id") == self.campaign_id]
        self.assertEqual(
            resumed, [],
            "a campaign.resumed audit row was written for a resume that "
            "did not happen")


if __name__ == "__main__":
    unittest.main()
