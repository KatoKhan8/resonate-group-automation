#!/usr/bin/env python3
"""The stop button does not reach the provider, and the audit row must say so.

FOUND on 2026-09-11. `api.pause_campaign` wrote:

    before={"status": "running"}
    after={"status": "paused"}

Two false statements in one row on a safety control.

`before` was hardcoded, so a draft or an approved-but-unlaunched campaign
recorded a transition from "running" that never happened. And `after` asserts
outreach stopped, while `orchestrator.pause` makes no provider call of any kind
- `providerwrites.SUPPORTED` is empty and both `heyreach.pause` and
`bison.pause` refuse by name. A campaign already running at the vendor keeps
running after this returns.

That is the worst place in the system for a claim to be wrong. It is the control
somebody reaches for when they want something to stop, and the audit trail is
where they would check afterwards that it had. At the time this was found there
were three campaigns active in the client's own email workspace with six figures
of sent mail between them, none of which this system could stop.

The pause itself is not the problem and is not weakened here: stopping this
system from planning further steps is real, useful, and correctly available from
reviewer upward. What changed is that the row now records the scope of what
happened instead of leaving a reader to infer a stop that did not occur.
"""
import unittest

from src import campaigns, orchestrator, roles
from src.web import api
from tests.webbase import WebTest


class TheAuditRowRecordsTheRealPriorStatus(WebTest):

    def setUp(self):
        super().setUp()
        from src import repo as repo_module

        self.repo = repo_module.Repo.for_user("ops@productive.test",
                                              "productive")
        # ITS OWN CAMPAIGN PER TEST. `WebTest` shares one estate across the
        # class and a pause is one-way, so the first test would consume the only
        # unpaused campaign and the rest would find none. Approved rather than
        # running, which is also the case the hardcoded "running" got wrong.
        name = self.id().rsplit(".", 1)[-1][:40]
        self.campaign = campaigns.new_campaign(
            f"pause-{name}", "productive", "A pause test",
            created_by="ops@productive.test")
        self.campaign["status"] = campaigns.APPROVED
        self.repo.save_campaign(self.campaign)

    def test_before_is_the_status_it_actually_had(self):
        was = self.campaign.get("status")
        api.pause_campaign(self.repo, self.campaign["campaign_id"],
                           why="a test", by="ops@productive.test")
        row = self.last_pause_row()
        self.assertEqual((row.get("before") or {}).get("status"), was)

    def test_and_it_is_not_the_word_running(self):
        """The specific fabrication: a campaign that was never running recorded
        a transition out of `running`."""
        was = self.campaign.get("status")
        if was == "running":
            self.skipTest("this fixture campaign really is running")
        api.pause_campaign(self.repo, self.campaign["campaign_id"],
                           why="a test", by="ops@productive.test")
        row = self.last_pause_row()
        self.assertNotEqual((row.get("before") or {}).get("status"), "running")

    def test_the_row_says_the_provider_was_not_stopped(self):
        api.pause_campaign(self.repo, self.campaign["campaign_id"],
                           why="a test", by="ops@productive.test")
        row = self.last_pause_row()
        self.assertIs((row.get("after") or {}).get("provider_stopped"), False)

    def test_the_reason_explains_it_in_words(self):
        """A reader deciding whether outreach has stopped needs the answer in
        the row, not in a module docstring."""
        api.pause_campaign(self.repo, self.campaign["campaign_id"],
                           why="a test", by="ops@productive.test")
        said = (self.last_pause_row().get("reason") or "").lower()
        self.assertIn("provider was not asked", said)
        self.assertIn("vendor ui", said)

    def last_pause_row(self):
        from src import workspaces as ws

        rows = ws.audit(workspace_slug="productive", action="campaign.paused")
        self.assertTrue(rows, "no campaign.paused audit row was written")
        return rows[-1]


class ThePauseStillDoesWhatItSaysLocally(unittest.TestCase):
    """The control. This must not weaken the pause - only its claim."""

    def test_canonical_state_is_paused(self):
        campaign = {"campaign_id": "c1", "client": "productive",
                    "status": campaigns.APPROVED, "log": []}
        orchestrator.pause(campaign, why="because", by="ops",
                           role=roles.ADMIN)
        self.assertEqual(campaign["status"], campaigns.PAUSED)
        self.assertTrue((campaign.get("pause") or {}).get("since"))

    def test_the_reason_and_who_survive(self):
        campaign = {"campaign_id": "c1", "client": "productive",
                    "status": campaigns.APPROVED, "log": []}
        orchestrator.pause(campaign, why="a bad note", by="ops",
                           role=roles.ADMIN)
        self.assertEqual(campaign["pause"]["reason"], "a bad note")
        self.assertEqual(campaign["pause"]["by"], "ops")


if __name__ == "__main__":
    unittest.main()
