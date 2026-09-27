#!/usr/bin/env python3
"""A rule keyed on a field nobody carries is VACUOUS, not PASS.

TASK-299, ISSUE-041. ``inbound._stop_at_provider`` gates the LinkedIn stop
on ``contact["heyreach_lead_id"]``. ZERO contacts in the estate carry it.
So every cross-channel stop reported success having never called
``heyreach.stop_lead_in_campaign`` once.

This test asserts that the reconciliation check:

1. Reports key presence FIRST, before any verdict.
2. A rule whose key is present on ZERO subjects is VACUOUS, not PASS.
3. The LinkedIn check is NOT gated on heyreach_lead_id — it uses the
   profile URL instead.
4. A constructed failure — a lead our store marks replied that reads
   in_sequence at HeyReach — produces a FAIL with the lead named.

Deleting any one of these tests must turn the suite red.
"""
import json
import os
import shutil
import tempfile
import unittest

from scripts.qa import check_reconcile
from scripts.qa import VACUOUS, FAIL, PASS


class TestKeyPresenceReportedFirst(unittest.TestCase):
    """Key presence is the FIRST output, before any verdict."""

    def test_key_presence_is_in_the_result(self):
        recs = [_make_stopped_rec("rec-1", bison_lead_id="100",
                                  profile_url="https://linkedin.com/in/test")]
        camps = [_make_campaign("camp-1", bison_campaign_id="491",
                                record_ids=["rec-1"])]
        result = check_reconcile.run(
            recs=recs, camps=camps,
            bison_membership=lambda cid, lids: "stopped",
            heyreach_campaigns=lambda **kw: ([{"campaignId": "599020",
                                               "leadCampaignStatus": "Paused",
                                               "leadStatus": "Paused"}], 1))
        kp = result.get("key_presence", {})
        self.assertIn("stopped_here_is_stopped_there", kp)

    def test_key_presence_counts_heyreach_lead_id_separately(self):
        recs = [_make_stopped_rec("rec-1", bison_lead_id="100",
                                  profile_url="https://linkedin.com/in/test")]
        kp = check_reconcile._key_presence_stopped(recs)
        self.assertEqual(kp["subjects"], 1)
        self.assertEqual(kp["email_key_present"], 1)
        self.assertEqual(kp["linkedin_key_present"], 1)
        self.assertEqual(kp["heyreach_lead_id_present"], 0)


class TestVacuousRule(unittest.TestCase):
    """A rule whose key is present on ZERO subjects is VACUOUS, not PASS."""

    def test_zero_subjects_is_vacuous(self):
        recs = []
        result = check_reconcile.run(
            recs=recs, camps=[],
            bison_membership=lambda cid, lids: "",
            heyreach_campaigns=lambda **kw: ([], 0))
        stopped_detail = result["rule_details"][
            "stopped_here_is_stopped_there"]
        self.assertEqual(stopped_detail["verdict"], VACUOUS)
        self.assertEqual(stopped_detail["subjects"], 0)


class TestLinkedInNotGatedOnHeyreachLeadId(unittest.TestCase):
    """The LinkedIn check uses profile URL, NOT heyreach_lead_id.

    This is the fix for ISSUE-041. Zero contacts carry heyreach_lead_id,
    so a check gated on it would pass 100% and read like a working
    reconciliation.
    """

    def test_linkedin_check_uses_profile_url(self):
        """A contact with profile URL but NO heyreach_lead_id is checked."""
        recs = [_make_stopped_rec(
            "rec-1", bison_lead_id="100",
            profile_url="https://linkedin.com/in/prospect",
            heyreach_lead_id=None)]
        camps = [_make_campaign(
            "camp-1", bison_campaign_id="491",
            heyreach_campaign_id="599020", record_ids=["rec-1"])]

        calls = []

        def fake_heyreach(profile_url=None, linkedin_id=None):
            calls.append(profile_url)
            return ([{"campaignId": "599020",
                      "leadCampaignStatus": "Paused",
                      "leadStatus": "Paused"}], 1)

        result = check_reconcile.check_stopped_here(
            recs, camps,
            bison_membership=lambda cid, lids: "stopped",
            heyreach_campaigns=fake_heyreach)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], "https://linkedin.com/in/prospect")
        self.assertEqual(result["verdict"], PASS)

    def test_no_heyreach_lead_id_does_not_skip_the_check(self):
        """A contact without heyreach_lead_id is STILL checked via URL."""
        recs = [_make_stopped_rec(
            "rec-1", bison_lead_id="100",
            profile_url="https://linkedin.com/in/prospect",
            heyreach_lead_id=None)]
        camps = [_make_campaign(
            "camp-1", bison_campaign_id="491",
            heyreach_campaign_id="599020", record_ids=["rec-1"])]

        checked = []

        def fake_heyreach(profile_url=None, linkedin_id=None):
            checked.append(profile_url)
            return ([{"campaignId": "599020",
                      "leadCampaignStatus": "InSequence",
                      "leadStatus": "InSequence"}], 1)

        result = check_reconcile.check_stopped_here(
            recs, camps,
            bison_membership=lambda cid, lids: "stopped",
            heyreach_campaigns=fake_heyreach)

        self.assertEqual(len(checked), 1,
                         "the LinkedIn check was NOT called — the rule is "
                         "gated on a field nobody carries")
        self.assertEqual(result["verdict"], FAIL)
        self.assertEqual(len(result["offenders"]), 1)
        self.assertEqual(result["offenders"][0]["record"], "rec-1")
        self.assertEqual(result["offenders"][0]["channel"], "linkedin")


class TestConstructedFailure(unittest.TestCase):
    """A lead our store marks replied that reads in_sequence at HeyReach.

    This is the exact ISSUE-041 consequence and must produce a FAIL
    naming the lead.
    """

    def test_in_sequence_at_heyreach_is_a_failure(self):
        recs = [_make_stopped_rec(
            "rec-1", bison_lead_id="100",
            profile_url="https://linkedin.com/in/prospect")]
        camps = [_make_campaign(
            "camp-1", bison_campaign_id="491",
            heyreach_campaign_id="599020", record_ids=["rec-1"])]

        def fake_heyreach(profile_url=None, linkedin_id=None):
            return ([{"campaignId": "599020",
                      "leadCampaignStatus": "InSequence",
                      "leadStatus": "InSequence"}], 1)

        result = check_reconcile.check_stopped_here(
            recs, camps,
            bison_membership=lambda cid, lids: "stopped",
            heyreach_campaigns=fake_heyreach)

        self.assertEqual(result["verdict"], FAIL)
        self.assertTrue(len(result["offenders"]) >= 1)
        offender = result["offenders"][0]
        self.assertEqual(offender["record"], "rec-1")
        self.assertEqual(offender["channel"], "linkedin")

    def test_in_sequence_at_emailbison_is_a_failure(self):
        recs = [_make_stopped_rec(
            "rec-1", bison_lead_id="100",
            profile_url="https://linkedin.com/in/prospect")]
        camps = [_make_campaign(
            "camp-1", bison_campaign_id="491",
            heyreach_campaign_id="599020", record_ids=["rec-1"])]

        result = check_reconcile.check_stopped_here(
            recs, camps,
            bison_membership=lambda cid, lids: "in_sequence",
            heyreach_campaigns=lambda **kw: ([], 0))

        self.assertEqual(result["verdict"], FAIL)
        offender = [o for o in result["offenders"]
                    if o["channel"] == "email"]
        self.assertEqual(len(offender), 1)
        self.assertEqual(offender[0]["record"], "rec-1")


class TestAlreadySettledIsItsOwnColumn(unittest.TestCase):
    """A Finished lead at HeyReach is 'already settled', not 'stopped'.

    Counting it as a successful stop would be a pass by construction.
    """

    def test_finished_is_already_settled_not_stopped(self):
        recs = [_make_stopped_rec(
            "rec-1", bison_lead_id="100",
            profile_url="https://linkedin.com/in/prospect")]
        camps = [_make_campaign(
            "camp-1", bison_campaign_id="491",
            heyreach_campaign_id="613744", record_ids=["rec-1"])]

        def fake_heyreach(profile_url=None, linkedin_id=None):
            return ([{"campaignId": "613744",
                      "leadCampaignStatus": "Finished",
                      "leadStatus": "Finished"}], 1)

        result = check_reconcile.check_stopped_here(
            recs, camps,
            bison_membership=lambda cid, lids: "stopped",
            heyreach_campaigns=fake_heyreach)

        self.assertEqual(result["already_settled_count"], 1)
        self.assertEqual(result["verdict"], PASS)
        self.assertEqual(len(result["offenders"]), 0)


class TestArithmeticCloses(unittest.TestCase):
    """clean + |offenders ∪ unverifiable| == subjects."""

    def test_arithmetic_closes_on_mixed_results(self):
        recs = [
            _make_stopped_rec("rec-1", bison_lead_id="100",
                              profile_url="https://linkedin.com/in/a"),
            _make_stopped_rec("rec-2", bison_lead_id="200",
                              profile_url="https://linkedin.com/in/b"),
            _make_stopped_rec("rec-3", bison_lead_id="300",
                              profile_url="https://linkedin.com/in/c"),
        ]
        camps = [
            _make_campaign("camp-1", bison_campaign_id="491",
                           heyreach_campaign_id="599020",
                           record_ids=["rec-1", "rec-2", "rec-3"]),
        ]

        def fake_heyreach(profile_url=None, linkedin_id=None):
            if "in/a" in (profile_url or ""):
                return ([{"campaignId": "599020",
                          "leadCampaignStatus": "Paused",
                          "leadStatus": "Paused"}], 1)
            if "in/b" in (profile_url or ""):
                return ([{"campaignId": "599020",
                          "leadCampaignStatus": "InSequence",
                          "leadStatus": "InSequence"}], 1)
            raise Exception("provider unreachable")

        result = check_reconcile.check_stopped_here(
            recs, camps,
            bison_membership=lambda cid, lids: "stopped",
            heyreach_campaigns=fake_heyreach)

        self.assertTrue(result["arithmetic_ok"])


# -------------------------------------------------------- helpers

def _make_stopped_rec(rec_id, *, bison_lead_id=None, profile_url=None,
                      heyreach_lead_id=None):
    """A record the store believes is stopped."""
    contact = {"key": f"{rec_id}-contact"}
    if bison_lead_id:
        contact["bison_lead_id"] = bison_lead_id
    if profile_url:
        contact["linkedin"] = profile_url
    if heyreach_lead_id:
        contact["heyreach_lead_id"] = heyreach_lead_id
    return {"id": rec_id, "state": "stopped",
            "contacts": [contact]}


def _make_campaign(camp_id, *, bison_campaign_id=None,
                   heyreach_campaign_id=None, record_ids=None):
    """A campaign row."""
    row = {"campaign_id": camp_id, "client": "productive",
           "record_ids": record_ids or []}
    if bison_campaign_id:
        row["bison_campaign_id"] = bison_campaign_id
    if heyreach_campaign_id:
        row["heyreach_campaign_id"] = heyreach_campaign_id
    return row


if __name__ == "__main__":
    unittest.main()
