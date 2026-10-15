#!/usr/bin/env python3
"""bisonfactory consults the STOP-SENDING brake before each transport - 0210.

WHY THIS MODULE EXISTS SEPARATELY FROM THE DOOR TESTS. `bisonfactory`
does not route its writes through `providerwrites.perform` - pilotcaps'
0160 finding, and the reason TASK 0210 wired eight `haltfile.
require_released()` consults directly into it (limits :1817, schedule
:1851, senders :1883, the custom-variables declaration :2384, the
in-loop update :2469, create_lead :2479, the copy write :2538, the
pre-attach check :2576). The structural test
(`test_no_path_reaches_a_transport_without_passing_the_stop_sending_brake`)
proves those consults EXIST on the path. This module proves they
BEHAVE:

  1. the file present -> the stage dies with OperatorStop and NOTHING
     reaches the provider - no campaign, no lead, no member;
  2. the brake pulled MID-STAGE still stops the next transport. The
     seam is `bison.ensure_custom_variables`, the fake provider's own
     method: the wrapper runs the real one and then pulls the brake, so
     every later consult (create_lead, the copy write, the attach) sees
     it. A brake consulted only at the top of `stage` would pass this
     test's premise and fail its assertion;
  3. no file -> the stage completes, two leads created, campaign left
     paused - the control that proves the fixture reaches transports
     and the refusals above are the brake;
  4. the factory's own STOP still lands with the brake pulled.
     `_ensure_stopped` pauses the campaign directly, not through the
     door, and is exempt on purpose: pulling STOP-SENDING must never
     disable another brake (the 481 blank-content watch lesson). The
     exemption is pinned structurally in the call-graph test; here it
     is pinned behaviourally.

NO TEST CREATES THE REAL FILE. `haltfile.STOP_SENDING_PATH` is patched
to a throwaway for every test.

Born-red at HEAD (pre-0210): ImportError on `src.haltfile`. The
mutation proof re-derives the true born-red: with `haltfile` present
and the eight factory consults byte-reverted, tests 1 and 2 fail on
REACH - the transports run with the file present.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import bisonfactory, cadence, campaigns, haltfile, store, workspaces
from src.providers import bison                      # noqa: F401 (tripwire)
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import (
    CONFIG, FakeBison, CID, record)
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty


class BrakeTestCase(QueueTest):

    def setUp(self):
        super().setUp()
        self.brake_tmp = tempfile.mkdtemp(prefix="rga-brake-factory-")
        self.addCleanup(shutil.rmtree, self.brake_tmp, ignore_errors=True)
        self.brake_path = os.path.join(self.brake_tmp, "STOP-SENDING")

        self.bison = FakeBison()
        self.bison.DAYS = FakeBison.DAYS
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)
        patch_collision_empty(self)

        # The workspace killswitch ON, because the property under test is
        # the OPERATOR's brake: it must fire when every machine gate says
        # yes, so every machine gate is made to say yes.
        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

        store.save([record("rec-1", "one@example.com", "Ada"),
                    record("rec-2", "two@example.com", "Grace")])
        row = campaigns.new_campaign(CID, "productive", "Factory test")
        row["cadence_steps"] = [dict(s) for s in cadence.steps_for(
            None, config=CONFIG)]
        row["record_ids"] = ["rec-1", "rec-2"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

    def _pull_brake(self):
        with open(self.brake_path, "wb") as handle:
            handle.write(b"")


class TheBrakeStopsTheFactory(BrakeTestCase):

    def test_the_file_present_stops_the_stage_before_any_transport(self):
        """The first consult a live stage reaches is the create-campaign
        door itself, so with the file present nothing is built at all."""
        self._pull_brake()
        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.brake_path), \
                self.assertRaises(haltfile.OperatorStop):
            bisonfactory.stage(CID, config=CONFIG, live=True)
        self.assertEqual(self.bison.created_campaigns, 0,
                         "a provider campaign was built with the brake "
                         "pulled")
        self.assertEqual(self.bison.created_leads, 0,
                         "a provider lead was created with the brake pulled")

    def test_the_brake_pulled_mid_stage_stops_before_the_next_transport(self):
        """Not at entry. `ensure_custom_variables` runs between the
        declaration consult and the lead loop; pulling the brake inside
        it means every later transport - create_lead, the copy write, the
        attach - must be refused. A check only at the top of `stage`
        would let all of them through."""
        real_declaration = self.bison.ensure_custom_variables

        def declare_then_pull(names=None):
            real_declaration(names)
            self._pull_brake()          # the operator's hand, mid-stage

        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.brake_path), \
                mock.patch.object(self.bison, "ensure_custom_variables",
                                  declare_then_pull), \
                self.assertRaises(haltfile.OperatorStop):
            bisonfactory.stage(CID, config=CONFIG, live=True)

        self.assertEqual(self.bison.created_leads, 0,
                         "the brake appeared before the lead loop and a "
                         "lead was still created: the consults are not "
                         "before the transports")
        self.assertEqual(sum(len(m) for m in self.bison.members.values()), 0,
                         "a lead was attached after the brake was pulled")

    def test_no_file_and_the_factory_stages(self):
        """The control. The same fixture with no brake file completes: two
        leads created, campaign left paused - so the refusals above are
        the brake and not the fixture."""
        report = bisonfactory.stage(CID, config=CONFIG, live=True)
        self.assertEqual(self.bison.created_leads, 2)
        self.assertEqual(report["provider"]["readback"]["status"], "paused")


class TheFactorysOwnStopStillLands(BrakeTestCase):

    def test_the_factory_pause_is_exempt_and_still_pauses(self):
        """`_ensure_stopped` pauses directly, not through the door, and is
        exempt from STOP-SENDING on purpose: the operator's brake must
        never disable a stop. With the file present the pause still lands."""
        self.bison.create_campaign("brake-exempt-test")
        self._pull_brake()
        report = {"did": [], "provider": {}}
        with mock.patch.object(haltfile, "STOP_SENDING_PATH",
                               self.brake_path):
            bisonfactory._ensure_stopped(501, report)
        self.assertEqual(self.bison.campaigns[501]["status"], "paused",
                         "the factory's own stop was silenced by the "
                         "operator's brake: pulling one brake must never "
                         "release another")


if __name__ == "__main__":
    unittest.main()
