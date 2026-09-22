#!/usr/bin/env python3
"""Somebody who told Resonate to stop must not be contacted by any client.

REPRODUCED on 2026-09-11. `src/agencydnc.py` is the whole mechanism and it is
carefully built: a one-way hash per identifier so the file cannot be read as a
directory of other clients' prospects, a closed reason vocabulary so nobody
writes "replied to Productive" in a free-text note, and a lookup that answers
yes and nothing else.

Its callers were the web layer and referral promotion. Nothing on the SEND path
asked it. So a person on the agency-wide list reached
`held:draft_not_approved` - an APPROVAL gate - and approving the copy would have
sent to them:

    agencydnc.lookup       suppressed by agency safety policy (asked us directly)
    eligibility.decide     held  ['held:draft_not_approved']

That is the strongest suppression this agency has, and it was the one no send
consulted. The failure mode is the one this repository names in its own
contributing rules: a correct module nothing calls.

It is checked in `_suppressed`, beside the client list, and read from disk on
every call for the same reason that one is - a cached suppression is a
suppression that arrived after the cache. Adding the reason to
`eligibility.BLOCKED_*` puts it in `executionguard`'s suppression gate for
free, because that tuple is built from these constants so the two cannot drift.
"""
import os
import tempfile
import unittest

from src import agencydnc, eligibility, executionguard, store, verification
from tests.base import pin_client_config


class TheSendGateHonoursTheAgencyList(unittest.TestCase):

    EMAIL = "dana@acme.test"
    PROFILE = "https://www.linkedin.com/in/dana-reed"

    def setUp(self):
        # `use_directory` sets QUEUE and clears every STATE_OVERRIDE for the
        # whole process, so a test that does not put them back hands its temp
        # directory to whatever runs next. That is not cosmetic: it silently
        # disarmed `TestTheBarrierCoversEveryWriter`, whose `spendledger` case
        # resolves its path from `store.queue_path()` and so was writing to
        # this leaked temp directory instead of being refused. The barrier
        # test passed alone and failed only in a full run, which is exactly
        # the shape of a guard that has stopped guarding.
        # ONCE, even though `test_every_reason_category_blocks` calls setUp
        # again inside its loop. A second capture would record the temp
        # directory the first one created and "restore" that, which is how
        # this leaked even with a cleanup in place.
        if not hasattr(self, "_env"):
            self._env = {k: os.environ.get(k)
                         for k in ("QUEUE", "OUT") + store.STATE_OVERRIDES}
            self.addCleanup(self._restore_environment)
        store.use_directory(tempfile.mkdtemp(prefix="rga-dnc-"))
        # Pinned, not loaded. This module is about the agency DNC reaching the
        # send gate, not about which cadence Productive currently runs - and
        # the fixture below stores `day5` and `day3` steps, which is what the
        # gate is asked about. Under the live LinkedIn-heavy cadence the gate
        # correctly answered `skipped:no_such_step` for both.
        pin_client_config(self)
        rec = store.new_record("acme", "domains", "productive", "Acme",
                               "acme.test")
        rec["state"] = "verified"
        rec["contacts"] = [{
            "key": "acme-1", "name": "Dana Reed", "email": self.EMAIL,
            "linkedin": self.PROFILE, "selected": True, "verdict": "valid",
            "sendable": True, "persona": "champion", "angle": "operations",
            "verification": {"evidence": [
                verification.result("deliverable", "valid", self.EMAIL),
                verification.result("reoon", "valid", self.EMAIL)]}}]
        rec["cadence"] = {"acme-1": {
            "day5": {"channel": "email", "subject": "resourcing at Acme",
                     "body": "I work with design teams on resourcing. " * 5},
            "day3": {"channel": "linkedin", "note": "hello, worth a word?"}}}
        store.save([rec])


    def _restore_environment(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def decide(self, step="day5", channel="email"):
        rec = store.load()[0]
        return eligibility.decide(rec, rec["contacts"][0], step,
                                  channel=channel, recs=[rec])

    def test_an_address_on_the_list_blocks_the_email(self):
        agencydnc.add("email", self.EMAIL, reason=agencydnc.REQUESTED)
        self.assertEqual(self.decide()["verdict"], "blocked")
        self.assertIn(eligibility.BLOCKED_AGENCY_DNC, self.decide()["reasons"])

    def test_a_profile_on_the_list_blocks_the_linkedin_step(self):
        agencydnc.add("linkedin", self.PROFILE, reason=agencydnc.REQUESTED)
        found = self.decide("day3", "linkedin")
        self.assertIn(eligibility.BLOCKED_AGENCY_DNC, found["reasons"])

    def test_an_address_on_the_list_blocks_the_other_channel_too(self):
        """One identifier is the person. A do-not-contact is not per channel."""
        agencydnc.add("email", self.EMAIL, reason=agencydnc.REQUESTED)
        self.assertIn(eligibility.BLOCKED_AGENCY_DNC,
                      self.decide("day3", "linkedin")["reasons"])

    def test_every_reason_category_blocks(self):
        """A closed vocabulary, and none of its values is advisory."""
        for reason in agencydnc.REASONS:
            with self.subTest(reason=reason):
                store.use_directory(tempfile.mkdtemp(prefix="rga-dnc-"))
                self.setUp()
                agencydnc.add("email", self.EMAIL, reason=reason)
                self.assertIn(eligibility.BLOCKED_AGENCY_DNC,
                              self.decide()["reasons"])

    def test_somebody_not_on_the_list_is_unaffected(self):
        """The control. A guard that blocks everybody is an outage."""
        agencydnc.add("email", "somebody.else@acme.test",
                      reason=agencydnc.REQUESTED)
        self.assertNotIn(eligibility.BLOCKED_AGENCY_DNC,
                         self.decide()["reasons"])

    def test_an_empty_list_blocks_nobody(self):
        self.assertNotIn(eligibility.BLOCKED_AGENCY_DNC,
                         self.decide()["reasons"])


class TheGuardKnowsItIsASuppression(unittest.TestCase):
    """`executionguard`'s suppression gate is built from these constants so the
    two cannot drift apart - the tuple says so. A new reason that was not added
    there would be a block eligibility reported and the guard did not name."""

    def test_the_execution_guard_counts_it_as_suppression(self):
        self.assertIn(eligibility.BLOCKED_AGENCY_DNC,
                      executionguard.SUPPRESSION_REASONS)

    def test_it_sits_beside_the_other_do_not_contact_reasons(self):
        for reason in (eligibility.BLOCKED_SUPPRESSED,
                       eligibility.BLOCKED_CLIENT_SUPPRESSED,
                       eligibility.BLOCKED_UNSUBSCRIBED):
            self.assertIn(reason, executionguard.SUPPRESSION_REASONS)


if __name__ == "__main__":
    unittest.main()
