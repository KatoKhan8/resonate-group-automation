#!/usr/bin/env python3
"""Every material change after approval must invalidate the approval.

An approval is a human saying yes to a SPECIFIC thing. If any part of that
thing can be edited afterwards while the approval still reads as current, then
what the human approved and what would be sent are two different objects, and
the approval is decoration.

These are attacks rather than unit tests. Each one mutates exactly one field
that a person would consider part of what they approved, and asserts the
approval stops being current. The list is the operator's own: sender,
recipient, note, delay, list, provider campaign, channel, angle, second lead.

WHAT IS DELIBERATELY NOT HERE. A change that cannot alter what is sent or when
must NOT invalidate an approval - re-approving a campaign because somebody
edited an unrelated note would train people to click through the dialog, which
is worse than not having it. `test_a_cosmetic_change_does_not` pins that
direction, and it is the reason `material()` is a named list rather than a
digest of the whole row.
"""
import copy
import unittest

from src import campaigns
from tests.campaignbase import CampaignTest


class AnyMaterialChangeInvalidatesIt(CampaignTest):

    def setUp(self):
        super().setUp()
        self.campaign, self.recs, _ = self.approved_campaign()
        # The premise. If this is false every assertion below passes vacuously.
        self.assertTrue(
            campaigns.approval_is_current(self.campaign, self.recs, self.config),
            "the fixture is not approved, so these attacks prove nothing")

    def still_current(self):
        return campaigns.approval_is_current(self.campaign, self.recs,
                                             self.config)

    def assertRevoked(self, what):
        self.assertFalse(
            self.still_current(),
            "%s was changed after approval and the approval still reads as "
            "current: what was approved and what would be sent are now two "
            "different things" % what)

    # ---------------------------------------------------------- the senders

    def test_changing_the_linkedin_sender(self):
        self.campaign["senders"]["linkedin"] = [{"account_id": "li-999999"}]
        self.assertRevoked("the LinkedIn sender")

    def test_changing_the_email_sender(self):
        self.campaign["senders"]["email"] = [{"account_id": "someone-else"}]
        self.assertRevoked("the email sender")

    def test_adding_a_second_sender(self):
        self.campaign["senders"]["linkedin"].append({"account_id": "li-2"})
        self.assertRevoked("a second sender")

    # ------------------------------------------------------- the recipients

    def test_adding_a_second_lead(self):
        self.campaign["record_ids"] = list(self.campaign["record_ids"]) + ["x"]
        self.assertRevoked("a second record")

    def test_removing_a_lead(self):
        self.campaign["record_ids"] = list(self.campaign["record_ids"])[:-1]
        self.assertRevoked("a record")

    def test_changing_the_recipient_email_address(self):
        for rec in self.recs:
            for contact in rec.get("contacts") or []:
                contact["email"] = "somebody-else@example.test"
        self.assertRevoked("the recipient address")

    def test_changing_the_recipient_linkedin_profile(self):
        for rec in self.recs:
            for contact in rec.get("contacts") or []:
                contact["linkedin"] = "https://www.linkedin.com/in/someone-else"
        self.assertRevoked("the recipient profile")

    # ------------------------------------------------------------ the words

    def test_adding_a_connection_note_where_there_was_none(self):
        """Aimed at what the fixture has, not at what I assumed it had.

        A first version rewrote `step["note"]` only `if step.get("note")` - and
        every step in this fixture is email with an empty note, so it mutated
        nothing and passed while proving nothing. Setting a note where there
        was none is the same material change and actually happens.
        """
        for rec in self.recs:
            for by_step in (rec.get("cadence") or {}).values():
                for step in by_step.values():
                    step["note"] = "hi, would love to connect"
        self.assertRevoked("a connection note")

    def test_changing_the_subject(self):
        for rec in self.recs:
            for by_step in (rec.get("cadence") or {}).values():
                for step in by_step.values():
                    if step.get("subject"):
                        step["subject"] = "an entirely different subject"
        self.assertRevoked("the subject line")

    def test_changing_the_body(self):
        for rec in self.recs:
            for by_step in (rec.get("cadence") or {}).values():
                for step in by_step.values():
                    if step.get("body"):
                        step["body"] = "a different email entirely"
        self.assertRevoked("the email body")

    def test_changing_the_angle(self):
        for rec in self.recs:
            for contact in rec.get("contacts") or []:
                contact["angle"] = "finance"
        self.assertRevoked("the angle")

    def test_changing_the_persona(self):
        for rec in self.recs:
            for contact in rec.get("contacts") or []:
                contact["persona"] = "blocker"
        self.assertRevoked("the persona")

    # -------------------------------------------------- the provider binding

    def test_changing_the_heyreach_campaign(self):
        self.campaign["heyreach_campaign_id"] = "999999"
        self.assertRevoked("the HeyReach campaign")

    def test_changing_the_heyreach_list(self):
        self.campaign["heyreach_list_id"] = "999999"
        self.assertRevoked("the HeyReach list")

    def test_changing_the_bison_campaign(self):
        self.campaign["bison_campaign_id"] = "999999"
        self.assertRevoked("the EmailBison campaign")

    def test_changing_the_workspace(self):
        self.campaign["workspace"] = "somebody-elses-estate"
        self.assertRevoked("the workspace")

    def test_changing_the_org_unit(self):
        self.campaign["org_unit"] = "another-organisation"
        self.assertRevoked("the LinkedIn organisation")

    # -------------------------------------------------------- timing and size

    def test_changing_a_provider_delay(self):
        self.campaign["provider_delays"] = {"day3": 999}
        self.assertRevoked("a step delay")

    def test_changing_the_daily_volume(self):
        self.campaign["daily_volume"] = {"linkedin": 500, "email": 500}
        self.assertRevoked("the daily volume")

    def test_changing_the_cadence_version(self):
        self.campaign["cadence_version"] = "v99"
        self.assertRevoked("the cadence version")

    def test_changing_the_expected_provider_status(self):
        self.campaign["provider_status_expected"] = "RUNNING"
        self.assertRevoked("the expected provider status")

    # ------------------------------------------------------ the client config

    def test_changing_the_verification_policy(self):
        config = copy.deepcopy(self.config)
        config["verification"] = {"required_confirmations": 1}
        self.assertFalse(
            campaigns.approval_is_current(self.campaign, self.recs, config),
            "the verification policy was loosened after approval and the "
            "approval still stands")

    def test_changing_the_linkedin_note_mode(self):
        """Through the accessor's own key. `sending_config` stores the RESULT
        of `clients.linkedin_note_mode`, so a top-level key it never reads
        changes nothing - which is what a first version of this asserted."""
        config = copy.deepcopy(self.config)
        config["linkedin_connection_note"] = {"mode": "llm"}
        self.assertFalse(
            campaigns.approval_is_current(self.campaign, self.recs, config),
            "the note generation mode changed and the approval still stands")

    # ------------------------------------------------------- the other way

    def test_a_cosmetic_change_does_not_revoke_it(self):
        """Not everything is material, and pretending otherwise has a cost.

        An approval that dies on any edit at all teaches people to re-approve
        without reading, which is how a real change gets waved through.
        """
        self.campaign["notes_for_humans"] = "checked with the client on Friday"
        self.campaign["last_viewed_at"] = "2026-09-10T00:00:00+00:00"
        self.assertTrue(self.still_current(),
                        "an unrelated field revoked the approval")

    def test_re_approving_after_a_change_makes_it_current_again(self):
        """The remedy has to work, or the guard is a dead end."""
        self.campaign["heyreach_list_id"] = "999999"
        self.assertRevoked("the list")
        self.campaign["approval"]["fingerprint"] = campaigns.fingerprint(
            self.campaign, self.recs, self.config)
        self.assertTrue(self.still_current())


class AnApprovalIsNotAStatus(CampaignTest):
    """`is_approved` must consult the fingerprint, not just the status word."""

    def test_a_campaign_marked_approved_with_a_stale_fingerprint_is_not(self):
        campaign, recs, _ = self.approved_campaign()
        campaign["status"] = campaigns.APPROVED
        campaign["heyreach_list_id"] = "999999"
        self.assertFalse(campaigns.is_approved(campaign, recs, self.config))

    def test_a_campaign_with_no_approval_at_all_is_not_approved(self):
        campaign, recs, _ = self.approved_campaign()
        campaign["approval"] = None
        self.assertFalse(campaigns.is_approved(campaign, recs, self.config))

    def test_a_rejection_is_not_an_approval(self):
        campaign, recs, _ = self.approved_campaign()
        campaign["approval"]["action"] = "reject"
        self.assertFalse(campaigns.approval_is_current(campaign, recs,
                                                       self.config))


if __name__ == "__main__":
    unittest.main()
