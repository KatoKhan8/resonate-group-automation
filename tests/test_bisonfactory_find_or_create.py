#!/usr/bin/env python3
"""`_find_or_create` named and pinned directly, branch by branch.

WHY THIS MODULE EXISTS
======================
Every other test that exercises this control reaches it through `stage()`
(`tests/test_crash_restart_idempotency.py` drives the whole pipeline), so no
test names it and no test pins its REFUSAL branches at all: the stale-binding
refusal, the pending-deletion refusal and the two-orphans ambiguity had
never been asserted by anything. `docs/MERGE-REQUEST-2026-09-25` section 9.3
records the neighbouring fact from a real mutation run: disabling idempotent
reuse through `bound` made **no test go red**, because recovery-by-name was
holding the property up - each mechanism was unguarded on its own.

The control under test is the idempotency decision at the top of the staging
path: given a campaign row, answer REUSE, RECOVER, REFUSE or CREATE such
that no second provider campaign is ever built behind a binding that may
still be valid. A wrong answer here duplicates a campaign that holds real
people - measured twice on 2026-09-13.

EVERY TEST USES A FAKE TRANSPORT. Nothing reaches the network.

WHAT MAKES THESE TESTS ABLE TO FAIL
===================================
Each test wraps the fake's methods with call counters and asserts the
counter moved. A test that passes because the code never consulted the
provider is a test that passes vacuously - the exact defect class this
repository keeps finding - so "the stub was actually called" is an assertion
here, not an assumption. The counters are armed AFTER the fixture builds its
provider state, so a count can only come from the code under test.
"""
import unittest

from src import (bisonfactory, campaigns, providerwrites, store,
                 workspaces)
from src.providers.bison import PENDING_DELETION
from tests.base import QueueTest
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty
from tests.test_staging_a_campaign_twice_builds_one import (
    FakeBison, CONFIG, CID, record,
)


class FindOrCreate(QueueTest):
    """One test per branch of `bisonfactory._find_or_create`.

    The fixtures are the ones `test_crash_restart_idempotency` proved drive
    a real `stage()` run, trimmed to what this one function reads.
    """

    def setUp(self):
        super().setUp()
        self.bison = FakeBison()
        self._real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", self._real)
        patch_collision_empty(self)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

        store.save([record("rec-1", "one@example.com", "Ada")])
        row = campaigns.new_campaign(CID, "productive", "Factory test")
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

        self.calls = {}

    def _count(self, *method_names):
        """Wrap FakeBison methods so `self.calls[name]` counts their calls.

        THE STUB-WAS-CALLED CONTROL. Armed after the fixture builds its
        state, so a non-zero count can only mean the code under test made
        the call. Every assertion below that depends on the provider being
        consulted also asserts the counter moved.
        """
        for method_name in method_names:
            original = getattr(self.bison, method_name)

            # Bound per iteration: a bare closure would late-bind `original`
            # to whatever the loop touched last, turning `campaign` into a
            # call to `create_campaign` - a bug this file's own first run
            # had, reported by these tests themselves.
            def counting(*args, _original=original, _name=method_name,
                         **kwargs):
                self.calls[_name] = self.calls.get(_name, 0) + 1
                return _original(*args, **kwargs)

            setattr(self.bison, method_name, counting)

    def _bind(self, provider_id):
        row = self._row()
        row["bison_campaign_id"] = provider_id
        campaigns.save([row])

    def _call(self, name="Factory test"):
        """`_find_or_create` over the real campaign row, as `stage` calls it."""
        campaign = campaigns.get(CID, campaigns.load())
        report = {"campaign": CID, "client": "productive", "live": True,
                  "workspace": None, "plan": {"name": name},
                  "did": [], "provider": {}}
        return bisonfactory._find_or_create(campaign, report), report

    def _row(self):
        return campaigns.get(CID, campaigns.load())

    # ---------------------------------------------------------- bound reuse

    def test_a_live_bound_campaign_is_reused_not_recreated(self):
        """REUSE. The bound id is checked against the PROVIDER, not the row."""
        made = self.bison.create_campaign("Factory test")
        self._bind(made["id"])
        self._count("campaign", "create_campaign")

        (provider_id, _provider_name), report = self._call()

        self.assertEqual(made["id"], provider_id)
        self.assertEqual(1, self.bison.created_campaigns,
                         "a second provider campaign was built for a row "
                         "already bound to a live one (the one counted here "
                         "is the fixture's own)")
        self.assertGreaterEqual(self.calls["campaign"], 1,
                                "reuse was answered without consulting the "
                                 "provider: the binding was trusted blind")
        self.assertEqual(0, self.calls.get("create_campaign", 0))
        self.assertTrue(any("reused" in d for d in report["did"]),
                        report["did"])

    def test_a_stale_binding_refuses_rather_than_creates_behind_it(self):
        """REFUSE. `bison.campaign` raising is NOT permission to re-create.

        The provider refusing to return the bound campaign means the binding
        may still be valid - a second campaign beside it would attach leads
        to nothing and duplicate everybody.
        """
        self._bind(4341)                       # not in the fake
        self._count("campaign", "create_campaign")

        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self._call()
        self.assertIn("may still be valid", str(caught.exception))
        self.assertEqual(1, self.calls["campaign"],
                         "the stale binding was never checked against the "
                         "provider")
        self.assertEqual(0, self.calls.get("create_campaign", 0),
                         "a new campaign was created behind a binding the "
                         "provider would not confirm")

    def test_a_campaign_pending_deletion_is_refused(self):
        """REFUSE. Delete is asynchronous and the row answers 200 for seconds.

        Measured 2026-09-13: staging into that window writes a cap, a
        schedule, a sequence and leads into a campaign that is about to stop
        existing, and every readback in between looks correct.
        """
        made = self.bison.create_campaign("Factory test")
        self.bison.campaigns[made["id"]]["status"] = PENDING_DELETION
        self._bind(made["id"])
        self._count("campaign", "create_campaign")

        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self._call()
        self.assertIn("on its way out", str(caught.exception))
        self.assertGreaterEqual(self.calls["campaign"], 1)
        self.assertEqual(0, self.calls.get("create_campaign", 0))

    # ------------------------------------------------------- orphan recovery

    def test_one_orphan_is_recovered_and_bound_not_duplicated(self):
        """RECOVER. The crash-between-POST-and-persist case: bind, don't build.

        This is the branch `test_crash_after_find_or_create_before_bind`
        reaches only through a full `stage()` run; here it is named and
        direct.
        """
        orphan = self.bison.create_campaign("Factory test")   # unbound row
        self._count("find_campaigns_by_name", "create_campaign")

        (provider_id, _name), report = self._call()

        self.assertEqual(orphan["id"], provider_id)
        self.assertEqual(1, self.bison.created_campaigns,
                         "a second provider campaign was built beside an "
                         "orphan this row should have recovered")
        self.assertGreaterEqual(self.calls["find_campaigns_by_name"], 1,
                                "the orphan lookup never ran: recovery "
                                "cannot have happened through this branch")
        self.assertEqual(0, self.calls.get("create_campaign", 0))
        self.assertEqual(orphan["id"], self._row().get("bison_campaign_id"),
                         "the recovered campaign was not bound to the row")
        self.assertTrue(report["provider"].get("recovered"))

    def test_two_orphans_are_an_ambiguity_not_a_choice(self):
        """REFUSE. Two campaigns that can hold real people are not sorted."""
        first = self.bison.create_campaign("Factory test")
        second = self.bison.create_campaign("Factory test")
        self._count("find_campaigns_by_name", "create_campaign")

        with self.assertRaises(bisonfactory.FactoryAmbiguous) as caught:
            self._call()
        self.assertIn("bind the right one", str(caught.exception).lower())
        self.assertEqual(2, self.bison.created_campaigns,
                         "a third campaign was created beside two orphans")
        self.assertGreaterEqual(self.calls["find_campaigns_by_name"], 1)
        self.assertFalse(self._row().get("bison_campaign_id"),
                         "an arbitrary orphan was bound by force")
        self.assertEqual({first["id"], second["id"]},
                         set(self.bison.campaigns))

    # --------------------------------------------------------------- create

    def test_with_nothing_to_reuse_it_creates_through_the_write_door(self):
        """CREATE. The POST goes through `providerwrites.perform` - the one
        door that carries the ledger, the readback contract and the gates -
        and the returned id is bound to the row."""
        self._count("create_campaign")
        real_perform = bisonfactory.providerwrites.perform
        performed = []

        def counting_perform(operation, **kw):
            performed.append(operation)
            return real_perform(operation, **kw)

        bisonfactory.providerwrites.perform = counting_perform
        self.addCleanup(setattr, bisonfactory.providerwrites,
                        "perform", real_perform)

        (provider_id, _name), _report = self._call()

        self.assertTrue(provider_id)
        self.assertEqual([providerwrites.EMAIL_CREATE_CAMPAIGN], performed,
                         "the campaign POST did not go through the write "
                         "door: " + repr(performed))
        self.assertGreaterEqual(self.calls["create_campaign"], 1)
        self.assertEqual(provider_id, self._row().get("bison_campaign_id"))

    def test_a_provider_answer_with_no_id_is_refused(self):
        """REFUSE. The provider accepted the POST but nothing can name the
        result; re-running would build a second one.

        Two doors refuse in order: `perform`'s readback contract first
        (`exists: True` was promised and not delivered), and the factory's
        own no-id check beneath it. Either refusal is correct; what may NOT
        happen is a silent success with an unnamed campaign left behind.
        """
        original = self.bison.create_campaign

        def nameless(name):
            row = original(name)
            row.pop("id")
            return row

        self.bison.create_campaign = nameless
        with self.assertRaises((providerwrites.WriteUnverified,
                                bisonfactory.FactoryAmbiguous)):
            self._call()
        self.assertFalse(self._row().get("bison_campaign_id"),
                         "nothing was bound, so a re-run would POST again")


if __name__ == "__main__":
    unittest.main()
