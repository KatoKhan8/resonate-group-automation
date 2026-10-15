"""A refused pause pauses nothing, and records nothing.

`api.pause_campaign` refuses an already-paused campaign before it calls
`orchestrator.pause`, and that early refusal is the whole control. The
route's own docstring says why this is the worst place in the system for a
wrong record: `pause` is the control somebody reaches for when they want
something to stop, it does not reach the provider, so the local record is
the only place the truth can live.

A route that paused an already-paused campaign anyway would overwrite the
pause that was already there - its `since`, its reason, its author - and
write a second `campaign.paused` audit row over the first. The trail would
then describe two pauses where there was one, and the original reason (the
thing somebody reads to decide whether outreach has actually stopped)
would be gone.

This is the pause twin of `test_a_refused_resume_resumes_nothing`: that
test proved a refused resume records nothing; this proves the same for the
pause side's own guard. No provider is contacted - the refusal precedes
`orchestrator.pause`, which is itself provider-free, and that ordering is
part of what is pinned.
"""
import unittest

from src import campaigns
from src.web import api
from tests.webbase import WebTest

PAUSED_SINCE = "2026-10-14T00:00:00Z"


class ARefusedPausePausesNothing(WebTest):

    def setUp(self):
        super().setUp()
        from src import repo as repo_module

        self.repo = repo_module.Repo.for_user("ops@productive.test",
                                              "productive")
        name = self.id().rsplit(".", 1)[-1][:40]
        row = campaigns.new_campaign(
            f"pause-{name}", "productive", "A pause-refusal test",
            created_by="ops@productive.test")
        row["status"] = campaigns.PAUSED
        row["pause"] = {"since": PAUSED_SINCE,
                        "reason": "paused by hand for this test"}
        self.repo.save_campaign(row)
        self.campaign_id = row["campaign_id"]

    def test_the_refusal_reaches_the_caller_and_nothing_is_recorded(self):
        with self.assertRaises(api.ActionRefused) as raised:
            api.pause_campaign(self.repo, self.campaign_id,
                               by="ops@productive.test")
        self.assertIn(
            "already paused", str(raised.exception),
            "the route must refuse an already-paused campaign by name, not "
            f"swallow or reword it: {raised.exception}")

        after = self.repo.campaign(self.campaign_id)
        self.assertEqual(
            after.get("status"), campaigns.PAUSED,
            "a refused pause changed the campaign status anyway")
        self.assertEqual(
            (after.get("pause") or {}).get("since"), PAUSED_SINCE,
            "a refused pause overwrote the pause that was already there")

        from src import workspaces as ws

        paused = [row for row in ws.audit(workspace_slug="productive",
                                          action="campaign.paused")
                  if row.get("resource_id") == self.campaign_id]
        self.assertEqual(
            paused, [],
            "a campaign.paused audit row was written for a pause that did "
            "not happen")


if __name__ == "__main__":
    unittest.main()
