#!/usr/bin/env python3
"""A pause row that follows a real provider stop may not deny it.

FOUND on 2026-10-15 (GLM-B, TASK 0080, pilotcaps D3). `api.pause_campaign`
still writes the row `test_a_pause_says_what_it_paused` pinned on 2026-09-11,
word for word, after the world it described ended on 2026-09-13:

    after={"status": ..., "provider_stopped": False}

That False was once a measurement: on 2026-09-11 `providerwrites.SUPPORTED`
was empty and both pause verbs refused by name. Since 09cf9b7c8 the tuple
carries 16 verbs, `bison.pause` among them, and `orchestrator.pause` defaults
to `provider=True` (1f62182bc), so for a campaign whose canonical row binds a
`bison_campaign_id` the ledger records as Resonate OS, this handler runs a
real provider write through the single door - transport, read-back,
classification - and then records that no provider was stopped.

The direction of the lie is the defect: the row hides an action that
happened. The audit trail is what somebody reads afterwards to find out what
was done to a campaign, and `pages._audit_change` renders every `after` key
on the /audit page, so the denial is displayed, not merely stored.

The truthful outcome already exists at the moment of the write: the
CAMPAIGN_PAUSED event carries `provider_stop` with the per-channel result.
The row just never reads it.

NOTHING HERE CALLS A PROVIDER. The transport and read-back are injected: the
fixture binds a synthetic provider id (987001, ours only because this test's
ledger row says so) and patches `bison.pause_campaign` / `bison.campaign`, so
the write leaves this process.
"""
import unittest
from unittest import mock

from src import campaigns, providerwrites
from src.providers import bison
from src.web import api
from tests.webbase import WebTest

# Synthetic, bound to this fixture's campaign only. Deliberately not one of
# the operator-declared internal ids (274, 327, 328, 352) or a live campaign
# (487, 489, 493, 418...): the classifier must pass it because OUR row
# claims it, and nothing outside this test's temp ledger ever sees it.
PROVIDER = "987001"


class TheRowCannotDenyAStopThatHappened(WebTest):

    def setUp(self):
        super().setUp()
        from src import repo as repo_module

        self.repo = repo_module.Repo.for_user("ops@productive.test",
                                              "productive")
        # Its own campaign per test: a pause is one-way and WebTest shares
        # one estate across the class. Approved rather than running - the
        # local status is orthogonal; what matters is the provider binding.
        name = self.id().rsplit(".", 1)[-1][:40]
        self.campaign = campaigns.new_campaign(
            f"stoprow-{name}", "productive", "A stop-row test",
            created_by="ops@productive.test")
        self.campaign["status"] = campaigns.APPROVED
        self.campaign["bison_campaign_id"] = PROVIDER
        self.repo.save_campaign(self.campaign)

        # The two premises of this file, asserted so the test fails loudly
        # as a fixture and not quietly as a green no-op if the world moves
        # again: the pause verb is supported, and this provider campaign is
        # positively ours in the ledger. Without the second, every write
        # below would be exercising the ownership refusal, not a stop.
        self.assertTrue(providerwrites.is_supported(providerwrites.EMAIL_PAUSE),
                        "bison.pause left SUPPORTED; this test no longer "
                        "measures a provider stop")
        self.assertEqual(providerwrites.classify_campaign("email", PROVIDER),
                         providerwrites.RESONATE_OS,
                         "fixture is not resonate_os; the pause would be a "
                         "refusal, not a stop")

    def test_the_row_must_not_say_false_when_the_vendor_was_paused(self):
        called = []
        with mock.patch.object(bison, "pause_campaign",
                               lambda pid: called.append(pid)
                               or {"ok": True}), \
             mock.patch.object(bison, "campaign",
                               lambda pid: {"status": "paused"}):
            api.pause_campaign(self.repo, self.campaign["campaign_id"],
                               why="a test", by="ops@productive.test")

        # THE PREMISE, measured not assumed: the provider leg really ran
        # through this handler. If it did not, the row's False is true and
        # this test is measuring nothing.
        self.assertEqual(called, [PROVIDER],
                         "the provider pause was never asked for; the "
                         "hardcoded False would be correct and this failure "
                         "is a fixture problem, not the defect")

        # THE INVARIANT: the row records what happened. A provider was
        # stopped in this very call; the row may not say otherwise.
        row = self.last_pause_row()
        stopped = (row.get("after") or {}).get("provider_stopped")
        self.assertTrue(stopped,
                        "the audit row says provider_stopped: %r while the "
                        "provider was paused in the same call" % (stopped,))

    def test_the_reason_must_not_say_the_provider_was_not_asked(self):
        """The row's prose denies the stop in words a human reads first."""
        with mock.patch.object(bison, "pause_campaign",
                               lambda pid: {"ok": True}), \
             mock.patch.object(bison, "campaign",
                               lambda pid: {"status": "paused"}):
            api.pause_campaign(self.repo, self.campaign["campaign_id"],
                               why="a test", by="ops@productive.test")
        said = (self.last_pause_row().get("reason") or "").lower()
        self.assertNotIn("provider was not asked", said,
                         "the reason still says the provider was not asked, "
                         "in a call that asked it")

    def last_pause_row(self):
        from src import workspaces as ws

        rows = ws.audit(workspace_slug="productive", action="campaign.paused")
        self.assertTrue(rows, "no campaign.paused audit row was written")
        return rows[-1]


if __name__ == "__main__":
    unittest.main()
