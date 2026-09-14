#!/usr/bin/env python3
"""Staging into EmailBison checked who approved the words, never whether the
words were true.

`bisonfactory._approved_copy` proves a human blessed these exact words - the
fingerprint is per step key and `executionguard` checks the payload against
it. That is a different question from whether the words are true of this
person, and this module asked only the first. `grep -n "claims" src/
bisonfactory.py` returned nothing but the English word "claims" in a comment.

WHY THERE IS NO LATER GATE. `executionguard` runs `claims.check` before a
SEND, and it never sees these. `_ensure_leads` writes the copy into per-lead
custom variables and the campaign sends on its own afterwards, so for email
this is the last gate there is. The HeyReach side got the same gate on the
same day, for the same reason, after eight of fifteen pushable contacts
turned out to be carrying unsupported claims.

Measured 2026-09-14: the nine live leads on campaign 481 are CLEAN, checked
against the words actually held at the provider rather than against the local
store. They are clean because they were regenerated after `claims.check` was
added to `generate.draft` - not because anything in the staging path checked.
Seventeen stored email steps elsewhere in the estate still assert something
unsupported, and the only thing keeping them off a provider is a collision
gate that is answering an entirely different question.
"""
import unittest

from src import bisonfactory
from tests.test_two_campaigns_do_not_collide_at_the_provider import (
    FactoryTest, record)


def approved(step_key, subject, body):
    return {"channel": "email", "subject": subject, "body": body,
            "approval": {"by": "operator", "at": "2026-09-13T00:00:00Z",
                         "fingerprint": f"fp-{step_key}"}}


def entry(step_key, subject, body):
    """One `_approved_copy` row, which is what the gate reads."""
    return {"step_key": step_key, "subject": subject, "body": body}


def claims_record(**over):
    rec = {"id": "acme", "client": "productive", "domain": "example.com",
           "company": "Example", "company_facts": {"name": "Example"},
           "contacts": [{"key": "acme-c1", "email": "ada@example.com",
                         "first_name": "Ada", "last_name": "Tester"}]}
    rec.update(over)
    return rec


def contact():
    return {"key": "acme-c1", "email": "ada@example.com",
            "first_name": "Ada", "last_name": "Tester", "name": "Ada Tester"}


class TheGateReadsTheWordsAndNotTheApproval(unittest.TestCase):

    def test_a_claim_of_prior_contact_is_caught(self):
        """The exact shape that reached the provider once already: lead 203708
        carried the subject "Final note on our previous discussions" for a
        contact this system has never written to."""
        found = bisonfactory._unsupported_copy(
            claims_record(), contact(),
            [entry("em5", "Final note on our previous discussions",
                   "<p>Closing the loop as promised.</p>")])
        self.assertTrue(found)
        self.assertEqual(found[0][0], "em5")
        self.assertTrue(found[0][1])

    def test_an_approved_step_is_not_exempt(self):
        """An approval is the thing this gate deliberately does not trust."""
        step = approved("em5", "Following up on our previous call", "<p>Hi</p>")
        found = bisonfactory._unsupported_copy(
            claims_record(), contact(),
            [entry("em5", step["subject"], step["body"])])
        self.assertTrue(found, "an approval must not exempt copy from claims")

    def test_clean_copy_passes(self):
        """A gate that refuses everything would be found by a caller rather
        than by this test."""
        found = bisonfactory._unsupported_copy(
            claims_record(), contact(),
            [entry("em1", "A question about project margin",
                   "<p>How do you see margin while a project is running?</p>")])
        self.assertEqual(found, [])

    def test_every_step_is_checked_not_only_the_first(self):
        """`_variables_for` carries subject_1..body_5, so a claim in step four
        reaches a person exactly as easily as one in step one."""
        found = bisonfactory._unsupported_copy(
            claims_record(), contact(),
            [entry("em1", "A question about project margin", "<p>Hello.</p>"),
             entry("em4", "As we discussed on our previous call",
                   "<p>Picking this back up.</p>")])
        self.assertEqual([f[0] for f in found], ["em4"])

    def test_one_reason_per_step_not_one_per_phrase(self):
        """The refusal names the step a person can go and regenerate. Listing
        every offending phrase in a step makes the message long and the action
        no clearer."""
        found = bisonfactory._unsupported_copy(
            claims_record(), contact(),
            [entry("em5", "Our previous discussions",
                   "<p>Following up on our previous call and our earlier "
                   "conversation.</p>")])
        self.assertEqual(len(found), 1)


class StagingRefusesRatherThanReporting(unittest.TestCase):
    """`_approved_copy` reports and `_ensure_leads` refuses. The new check has
    to sit on the refusing side or it is a field nobody reads - which is the
    defect this repository keeps rediscovering."""

    def plan_with(self, unsupported):
        return {"leads": [{"record_id": "acme", "contact_key": "acme-c1",
                           "missing_copy": [],
                           "unsupported_copy": unsupported}],
                "sequence": [{"step_key": "em1"}]}

    def test_a_lead_with_unsupported_copy_stops_the_whole_stage(self):
        """Not "skip that lead". A campaign meant for nine that quietly stages
        eight is a campaign whose reach nobody stated."""
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._refuse_unsupported(
                self.plan_with([("em5", "asserts prior contact")]))
        message = str(caught.exception)
        self.assertIn("does not support", message)
        self.assertIn("em5", message)
        self.assertIn("REGENERATE", message)

    def test_a_clean_plan_raises_nothing(self):
        bisonfactory._refuse_unsupported(self.plan_with([]))


class TheGateIsActuallyWiredIntoStaging(FactoryTest):
    """The test the ones above cannot be.

    Every test in this file up to here passes with the call to
    `_refuse_unsupported` DELETED from `_ensure_leads` - they exercise the
    function, not the wiring, and a correct function nothing calls is the
    defect this repository keeps rediscovering. Verified by deleting the call
    and watching all seven stay green.

    So this one drives the real `stage()` against the fake provider and asks
    what happens to a contact whose approved copy claims a conversation that
    never took place.
    """

    def unsupported_record(self, rid="r1"):
        """The harness's own record, with one approved step made untrue.

        The contact key AND the step key are read off the record rather than
        assumed. The two factory test modules build different records - one
        five steps, one a single step - and hard-coding either is how this
        test breaks for a reason that has nothing to do with claims.
        """
        rec = record(rid, f"{rid}@example.test")
        key = next(iter(rec["cadence"]))
        step = next(iter(rec["cadence"][key]))
        rec["cadence"][key][step]["subject"] = (
            "Final note on our previous discussions")
        return rec

    def test_staging_refuses_a_contact_who_was_never_contacted(self):
        self.estate(rids=("r1",), records=[self.unsupported_record()])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()
        self.assertIn("does not support", str(caught.exception))

    def test_nothing_was_written_to_the_provider(self):
        """A refusal after the leads are created is not a refusal."""
        self.estate(rids=("r1",), records=[self.unsupported_record()])
        with self.assertRaises(bisonfactory.FactoryRefused):
            self.stage()
        self.assertEqual(
            [c for c in self.bison.calls if c[1] == "/leads"], [],
            "a lead was created before the claim gate refused")

    def test_a_clean_record_still_stages(self):
        """The gate must not refuse the campaign this cohort is for - the nine
        live leads on campaign 481 pass it against the words actually held at
        the provider."""
        self.estate(rids=("r1",))
        report = self.stage()
        self.assertTrue(report["provider"]["campaign_id"])


if __name__ == "__main__":
    unittest.main()
