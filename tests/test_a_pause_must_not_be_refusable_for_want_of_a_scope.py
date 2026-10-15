#!/usr/bin/env python3
"""The stop button's provider leg is refused by the write guard, every time.

TASK 0030 finding, measured 2026-10-15. `api.pause_campaign` ->
`orchestrator.pause` -> `_pause_at_provider` -> `_perform_pause` calls
`providerwrites.perform` with `transport=lambda _p: bison.pause_campaign(
provider_id)` (orchestrator.py:604), and nothing anywhere on that path
opens an `allow_writes` scope. The transport guard refuses every provider
write without one - "no RESONATE_PROVIDER_WRITES and no allow_writes()
scope", the same refusal the blank-content halt recorded in
`work/provider-write-refusals.jsonl` at 2026-09-23T20:18:58Z before it
carried `only=PAUSE_ROUTES`. `_pause_at_provider` then classifies the
refusal into `{"stopped": False}` and never raises, so the vendor campaign
keeps sending while canonical state says paused, and the audit row calls
it "no pause route is supported" - stale words over a live refusal.

A stop is a safety write. The local leg correctly fails open and is
asserted here as well, because the property is not "pause louder", it is
"the pause reaches the provider unless the provider itself is down".

This is born red BY DESIGN: the fix - the pause path carrying its own
route-scoped authorization, exactly as the watcher halt does - is a
production change this task is forbidden to make. The second test is the
proof that the missing scope is the single cause: identical fixture,
identical fakes, identical call, one pause-route scope open, and the
pause performs.
"""
import os
import tempfile
import unittest

from src import campaigns, orchestrator, providerwrites, roles, store


PAUSE_URL = "https://send.example.test/api/campaigns/%s/pause"
ATTACH_URL = "https://send.example.test/api/campaigns/%s/leads/attach-leads"


class TheProviderLegOfAPauseIsNotRefusedForWantOfAScope(unittest.TestCase):
    PROVIDER_ID = 9001

    def bind(self):
        """One bound Resonate OS campaign, in a redirected store.

        The binding is asserted the way the blank-halt test asserts it, so
        that a red below can only mean the write guard and never the
        ownership gate firing first.
        """
        tmp = tempfile.mkdtemp(prefix="rga-pause-scope-")
        self.addCleanup(store.use_directory(tmp))
        self.assertTrue(store.queue_path().startswith(os.path.abspath(tmp)),
                        "the store was not redirected, so this test would "
                        "write the operator's real state")
        row = campaigns.new_campaign("pause-scope-fixture", "productive",
                                     "pause scope test", created_by="test")
        row["status"] = campaigns.APPROVED
        row["bison_campaign_id"] = str(self.PROVIDER_ID)
        campaigns.save([row])
        self.assertEqual(
            providerwrites.classify_campaign("email", self.PROVIDER_ID),
            providerwrites.RESONATE_OS,
            f"{self.PROVIDER_ID} did not bind, so the pause below would be "
            f"refused on ownership and this test would measure the wrong "
            f"gate")
        return row

    def fake_bison(self, seen):
        """The pause adapter with the REAL guard decision inside it.

        The production transport refuses at the guard before any HTTP; the
        fake consults the same decision function so red and green differ
        only by what the guard answers.
        """
        from src import providers as _providers
        from src.providers import bison as _bison

        def _pause(campaign_id):
            allowed, why = _providers.writes_allowed(
                PAUSE_URL % campaign_id)
            seen["allowed"], seen["why"] = allowed, why
            if not allowed:
                raise RuntimeError(why)
            # And the scope must NOT reach a route it was not given.
            seen["attach_allowed"], _ = _providers.writes_allowed(
                ATTACH_URL % campaign_id)
            seen["paused"] = campaign_id
            return {"campaign_id": campaign_id, "status": "paused"}

        real_pause, real_campaign = (_bison.pause_campaign,
                                     _bison.campaign)
        _bison.pause_campaign = _pause
        _bison.campaign = lambda _cid: {"status": "paused"}
        self.addCleanup(setattr, _bison, "pause_campaign", real_pause)
        self.addCleanup(setattr, _bison, "campaign", real_campaign)

    def test_the_pause_performs_at_the_provider_without_a_hand_added_scope(self):
        row = self.bind()
        seen = {}
        self.fake_bison(seen)
        orchestrator.pause(row, why="a test pause", by="test",
                           role=roles.ADMIN)
        # The local leg fails open independently and must keep doing so:
        # the property is the provider leg, not a weaker local one. It is
        # asserted FIRST so a red run shows exactly this split - local
        # pause written, provider pause refused.
        self.assertEqual(row["status"], campaigns.PAUSED)
        self.assertTrue((row.get("pause") or {}).get("since"))
        self.assertTrue(seen.get("allowed"),
                        "the pause was refused before it reached the "
                        f"provider: {seen.get('why')}")
        self.assertEqual(seen.get("paused"), str(self.PROVIDER_ID),
                         "the stop button did not stop anything at the "
                         "vendor")

    def test_with_a_pause_route_scope_the_same_pause_performs(self):
        """The single-cause proof. One scope, pause route alone, and the
        identical call performs: the missing scope is the whole defect."""
        from src import providers as _providers

        row = self.bind()
        seen = {}
        self.fake_bison(seen)
        with _providers.allow_writes(
                "simulated fix: the pause path carries its own scope",
                only=("/pause",)):
            orchestrator.pause(row, why="a test pause", by="test",
                               role=roles.ADMIN)
        self.assertTrue(seen.get("allowed"),
                        f"the scoped pause was still refused: {seen.get('why')}")
        self.assertEqual(seen.get("paused"), str(self.PROVIDER_ID))
        # And the scope reaches ONLY the pause route - the simulated fix
        # is the scoped one, not a blanket authorization.
        self.assertFalse(seen.get("attach_allowed"),
                         "the pause scope reached a route it was not given")
        self.assertEqual(row["status"], campaigns.PAUSED)


if __name__ == "__main__":
    unittest.main()
