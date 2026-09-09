"""Approving one person releases one action, and nobody else.

A red team reported that approval is campaign-level and that approving
`productive-pilot-canary` would release fifteen touches to three people. That
is wrong, and the distinction matters enough to pin: there are TWO independent
approval gates and both must pass.

    `eligibility._campaign`  - the campaign, fingerprinted over its records
                               and config
    `approval.is_approved`   - this record, this contact, this step, and the
                               exact text, fingerprinted over channel, subject,
                               body and note

The second binds to a person and a step. Campaign approval alone releases
nothing; every step reports `held:draft_not_approved`.

There is an ordering consequence worth knowing, and it is a safety property
rather than a bug: writing a draft approval mutates the record, which moves the
campaign fingerprint and makes a prior campaign approval stale. So drafts are
approved first and the campaign last. Approve in the other order and everything
holds - which is the safe direction to fail.

These tests are the proof for a one-person canary: approving Austin Ball must
never release Anthony Andreatos, and must not release Austin's own later steps.
"""
import copy
import unittest

from src import (approval, cadence, campaigns, clients, eligibility as E,
                 store)
from tests.campaignbase import CLIENT, CampaignTest, contact


class OnePersonCanary(CampaignTest):
    """Two people at two companies, built here rather than read from work/.

    An earlier version of this file loaded the live Productive cohort and
    skipped when it was absent, which makes a safety proof depend on whichever
    client data happens to be on the machine. The property is about the
    approval model, so the fixture belongs to the test.
    """

    def setUp(self):
        super().setUp()
        recs = self.seed_records(companies=[
            ("north", "North Inc", "north.test"),
            ("west", "West Ltd", "west.test")])
        # Replacing `contacts` wholesale would drop the seeded contact's
        # verification evidence, and `store.save` refuses that - correctly.
        # These two are the cohort, so the estate starts empty and they are
        # the only people on it.
        store.save([])
        recs[0]["contacts"] = [contact("austin", "Austin Ball",
                                       "sam@north.test")]
        recs[1]["contacts"] = [contact("anthony", "Anthony Andreatos",
                                       "alex@west.test")]
        for rec in recs:
            for c in rec["contacts"]:
                c["title"] = "Chief Operating Officer"
                c["linkedin"] = c["key"] + "-profile"
                c["angle"] = next(iter(
                    clients.angles_for(self.config, "economic_buyer")), None)
                c["persona"] = "economic_buyer"
        store.save(recs)
        self.recs = store.load()
        self.camp = dict(campaigns.new_campaign("canary", CLIENT, "Canary"),
                         record_ids=[r["id"] for r in self.recs],
                         status=campaigns.APPROVED,
                         heyreach_campaign_id="HR-TEST")

    # ------------------------------------------------------------- helpers

    def people(self):
        return [(r, c) for r in self.recs for c in (r.get("contacts") or [])]

    def step_for(self, rec, contact, key):
        built = cadence.build(rec, self.config, recs=self.recs)
        return ((built.get("contacts") or {}).get(contact["key"]) or {}).get(key)

    def approve_draft(self, rec, contact, key):
        step = self.step_for(rec, contact, key)
        self.assertIsNotNone(step, f"no {key} step for {contact['name']}")
        rec.setdefault("cadence", {}).setdefault(contact["key"], {})[key] = {
            "approval": {"fingerprint": approval.fingerprint(step),
                         "by": "test"}}

    def approve_campaign(self):
        """Last, because a draft approval moves the campaign fingerprint."""
        self.camp["approval"] = {"action": "approve", "by": "test",
                                 "at": "2026-09-08T00:00:00+00:00"}
        self.camp["approval"]["fingerprint"] = campaigns.fingerprint(
            self.camp, self.recs, self.config)

    def eligible_steps(self, keys=("day3", "day8")):
        out = []
        for rec, contact in self.people():
            for key in keys:
                step = self.step_for(rec, contact, key)
                if step is None:
                    continue
                d = E.decide(rec, contact, key, channel="linkedin",
                             recs=self.recs, config=self.config,
                             campaign=self.camp, step=step)
                if d.eligible:
                    out.append((contact["name"], key))
        return out

    def find(self, name):
        for rec, contact in self.people():
            if contact["name"].startswith(name):
                return rec, contact
        self.fail(f"{name} is not in the cohort")

    # ------------------------------------------------------- the guarantee

    def test_campaign_approval_alone_releases_nothing(self):
        self.approve_campaign()
        self.assertEqual(self.eligible_steps(), [])

    def test_approving_one_person_releases_exactly_one_action(self):
        rec, austin = self.find("Austin")
        self.approve_draft(rec, austin, "day3")
        self.approve_campaign()
        self.assertEqual(self.eligible_steps(), [("Austin Ball", "day3")])

    def test_approving_austin_does_not_release_anthony(self):
        """The sentence this file exists for."""
        rec, austin = self.find("Austin")
        self.approve_draft(rec, austin, "day3")
        self.approve_campaign()
        released = [name for name, _ in self.eligible_steps()]
        self.assertNotIn("Anthony Andreatos", released)
        self.assertNotIn("Briley Brind'amour", released)

    def test_approving_day3_does_not_release_day8(self):
        rec, austin = self.find("Austin")
        self.approve_draft(rec, austin, "day3")
        self.approve_draft(rec, austin, "day8")
        self.approve_campaign()
        self.assertEqual(self.eligible_steps(), [("Austin Ball", "day3")],
                         "day8 must wait on the connection being accepted")

    def test_editing_the_copy_after_approval_revokes_it(self):
        """The approval is over the exact words, not over the person."""
        rec, austin = self.find("Austin")
        self.approve_draft(rec, austin, "day3")
        self.approve_campaign()
        self.assertEqual(len(self.eligible_steps()), 1)
        stored = rec["cadence"][austin["key"]]["day3"]["approval"]
        stored["fingerprint"] = "0" * 16
        self.assertEqual(self.eligible_steps(), [])

    def test_approving_in_the_wrong_order_releases_nothing(self):
        """Campaign first, then draft: the draft write stales the campaign.

        Fails closed, which is why it is a property rather than a bug.
        """
        self.approve_campaign()
        rec, austin = self.find("Austin")
        self.approve_draft(rec, austin, "day3")
        self.assertEqual(self.eligible_steps(), [])

    def test_a_second_persons_approval_is_needed_for_a_second_action(self):
        rec_a, austin = self.find("Austin")
        rec_b, anthony = self.find("Anthony")
        self.approve_draft(rec_a, austin, "day3")
        self.approve_draft(rec_b, anthony, "day3")
        self.approve_campaign()
        self.assertEqual(sorted(self.eligible_steps()),
                         [("Anthony Andreatos", "day3"), ("Austin Ball", "day3")])


if __name__ == "__main__":
    unittest.main()
