#!/usr/bin/env/python3
"""Lead writes consult the killswitch, and the campaign is stopped FRESH.

`_ensure_leads` calls `bison.create_lead` and `bison.attach_leads` directly,
bypassing `providerwrites.perform`. The write door's killswitch gate does not
cover it. This test module pins the two checks that close the gap:

  1. The workspace killswitch is consulted before any lead is created or
     attached. A workspace whose `sending.live` is off - or absent, which
     means the same thing - stops the whole lead write.

  2. The campaign's provider status is re-read immediately before the attach.
     `_ensure_stopped` established that the campaign was paused earlier in
     `stage`, but the invariant that makes attachment safe is "the campaign
     is stopped at the provider RIGHT NOW", not "it was stopped four calls
     ago". A campaign resumed by hand in the provider UI between the two
     reads is caught here.

The done condition for this task is: somebody can answer "what stops this
system putting a person into a live EmailBison campaign while the killswitch
is tripped?" by naming a test.
"""
import unittest
from unittest import mock

from src import bisonfactory, cadence, campaigns, killswitch, store, workspaces
from src import providers
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import (
    CONFIG, FakeBison, CID)
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty


class KillswitchStopsLeadWrites(QueueTest):

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        self.bison.DAYS = FakeBison.DAYS
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)
        patch_collision_empty(self)

        store.save([self._record("rec-1", "one@example.com", "Ada"),
                    self._record("rec-2", "two@example.com", "Grace")])
        row = campaigns.new_campaign(CID, "productive", "Factory test")
        # DECLARED, NOT INHERITED. `bisonfactory._plan` refuses a
        # campaign carrying no `cadence_steps`: the fallback through
        # the client config is what let a live campaign be staged
        # against a cadence it never chose. This is exactly what the
        # fallback would have produced, so the behaviour under test is
        # unchanged - the campaign now SAYS what it runs.
        row["cadence_steps"] = [dict(s) for s in cadence.steps_for(
            None, config=CONFIG)]
        row["record_ids"] = ["rec-1", "rec-2"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

    @staticmethod
    def _record(rid, email, first):
        from src import approval as _approval

        key = f"{rid}-c1"
        # THE STAMP COVERS THE WORDS. A placeholder fingerprint was enough
        # while staging checked only that an approval existed;
        # `bisonfactory._certified_copy` now hashes the words it is about to
        # stage and compares, so a stamp that covers nothing is refused.
        step = {"channel": "email", "subject": f"Hello {first}",
                "body": "<p>A real approved body.</p>"}
        step["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                            "fingerprint": _approval.fingerprint(step)}
        return {"id": rid, "client": "productive", "domain": "example.com",
                "company": "Example", "state": "ready",
                "cadence": {key: {"day1": step}},
                "contacts": [{"key": key, "email": email,
                              "first_name": first, "last_name": "Tester",
                              "sendable": True, "verified": True}]}

    def _set_workspace(self, sending_live):
        """Write a workspace row with the given `sending.live` policy."""
        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": sending_live}}
        workspaces.save([ws])

    def test_a_tripped_killswitch_stops_lead_creation(self):
        """A workspace whose sending.live is off gets no leads.

        The workspace killswitch is the meaningful tenant-level control at
        staging time. `_ensure_leads` does not go through
        `providerwrites.perform`, so the write door's killswitch gate does
        not cover it. This test pins the direct check.
        """
        self._set_workspace("off")
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory.stage(CID, config=CONFIG, live=True)
        self.assertIn("killswitch", str(caught.exception).lower())
        self.assertEqual(self.bison.created_leads, 0,
                         "leads were created despite the killswitch being off")

    def test_an_absent_workspace_setting_stops_lead_creation(self):
        """No `sending.live` is the same as off. Absence is not permission.

        The failure this prevents is a new workspace created for a demo
        where nobody remembers whether the switch was ever set.
        `killswitch.workspace_state` says so, and this test holds it.
        """
        # No workspace row at all - the workspace does not exist.
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory.stage(CID, config=CONFIG, live=True)
        self.assertIn("killswitch", str(caught.exception).lower())
        self.assertEqual(self.bison.created_leads, 0)

    def test_the_killswitch_check_is_what_stops_the_leads(self):
        """Remove the enforcement and the leads go through.

        This proves the killswitch check is load-bearing: with it bypassed,
        a workspace whose sending.live is off would have leads created.
        The enforcement is what stands between a tripped switch and a
        populated campaign.
        """
        self._set_workspace("off")
        # Bypass the killswitch at the module level: _ensure_leads imports
        # killswitch from src, so patching src.killswitch.workspace_state
        # replaces the function it sees.
        permissive = lambda ws: {"layer": killswitch.WORKSPACE,
                                 "sending": True, "why": "bypassed for test"}
        with mock.patch("src.killswitch.workspace_state", permissive):
            bisonfactory.stage(CID, config=CONFIG, live=True)
        self.assertEqual(self.bison.created_leads, 2,
                         "with the killswitch bypassed, no leads were "
                         "created - the check is not load-bearing")

    def test_a_running_campaign_is_caught_fresh_before_attach(self):
        """The provider status is re-read immediately before the attach.

        `_ensure_stopped` paused the campaign earlier in `stage`, but the
        invariant is "the campaign is stopped RIGHT NOW". A campaign resumed
        by hand between the two reads is caught here rather than discovered
        from a readback that agrees with a send already in flight.
        """
        self._set_workspace("on")
        # Stage normally first to create the campaign at the fake provider.
        # Then set the campaign to active and re-stage. The fresh read
        # inside `_ensure_leads` must catch it.
        #
        # But re-staging a running campaign is refused by `_ensure_stopped`
        # (it leaves it running and returns). So the test sets the campaign
        # to active AFTER _ensure_stopped has run, which means we need to
        # test _ensure_leads more directly.
        #
        # The direct path: stage normally, then set the campaign to active
        # at the provider, then call _ensure_leads with the same plan.
        report = bisonfactory.stage(CID, config=CONFIG, live=True)
        provider_id = report["provider"]["campaign_id"]
        # Simulate the campaign being resumed by hand between _ensure_stopped
        # and _ensure_leads.
        self.bison.campaigns[int(provider_id)]["status"] = "active"
        # Build a fresh plan to pass to _ensure_leads.
        row = campaigns.get(CID, campaigns.load())
        config = CONFIG
        plan = bisonfactory._plan(row, store.load(), config)
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._ensure_leads(provider_id, row, plan,
                                       {"did": []})
        self.assertIn("active", str(caught.exception).lower())

    def test_an_active_campaign_with_leads_already_created_refuses_attach(self):
        """Even if leads were created, the attach is refused if the campaign
        became active in the meantime.

        The fresh read is immediately before `attach_leads`, so leads may
        have been created already but they are NOT attached to a running
        campaign. The campaign is paused, the leads exist but are not in
        any active sequence.
        """
        self._set_workspace("on")
        report = bisonfactory.stage(CID, config=CONFIG, live=True)
        provider_id = report["provider"]["campaign_id"]
        # The campaign is paused with leads attached from the first stage.
        # Set it to active, then try _ensure_leads again.
        self.bison.campaigns[int(provider_id)]["status"] = "active"
        row = campaigns.get(CID, campaigns.load())
        plan = bisonfactory._plan(row, store.load(), CONFIG)
        with self.assertRaises(bisonfactory.FactoryRefused):
            bisonfactory._ensure_leads(provider_id, row, plan,
                                       {"did": []})
        # The leads were NOT attached to the active campaign.
        members = self.bison.members.get(int(provider_id), [])
        # The original attach from the first stage is there, but the second
        # _ensure_leads did not add to it.
        self.assertEqual(len(members), 2)


if __name__ == "__main__":
    unittest.main()
