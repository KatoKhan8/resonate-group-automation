#!/usr/bin/env python3
"""An authorization proves one action, in one wording. Not a channel.

Both holes here were demonstrated end to end against the live guard before
they were closed, and both end with a prospect receiving something nobody
approved:

  - a token minted to ADD A LEAD drove ACTIVATE, because the only identity
    check was the channel and both are linkedin;
  - a token minted for approved copy transported different copy, because the
    payload was never compared to the approval it travelled under.

These tests drive `providerwrites.perform` itself rather than asserting on the
text of the source, and each one checks that the transport was never called -
a refusal that happens after the provider acts is not a refusal.
"""
import unittest

from src import actionledger, approval, executionguard, providerwrites
from tests.base import QueueTest


class Transport:
    """Records what would have reached the provider."""

    def __init__(self):
        self.calls = []

    def __call__(self, payload):
        self.calls.append(payload)
        return {"ok": True}


APPROVED = {"channel": "linkedin", "note": "Saw your delivery hiring - worth a word?"}
OTHER = {"channel": "linkedin", "note": "BUY MY THING, unapproved text"}


def token(operation, *, fingerprint=None, key="k1"):
    """An Authorization built directly.

    Legitimate here: these tests are about what `perform` checks on a token,
    and building one directly is exactly how a caller could bypass `authorize`.
    """
    return executionguard.Authorization(
        key=key, operation=operation, channel="linkedin",
        workspace="productive", campaign_id="c1", sender_id="s1",
        rec_id="r1", contact_key="ck1", step_key="day3",
        fingerprint=fingerprint or approval.fingerprint(APPROVED),
        gates=("tenancy", "approval"), at="2026-09-12T00:00:00Z")


class TheTokenNamesOneOperation(QueueTest):

    def setUp(self):
        super().setUp()
        # Both operations must be performable for the test to be about the
        # binding rather than about `require_supported` firing first.
        self._supported = providerwrites.SUPPORTED
        providerwrites.SUPPORTED = tuple(self._supported) + (
            providerwrites.LINKEDIN_ADD_LEAD, providerwrites.LINKEDIN_ACTIVATE)
        self.addCleanup(self._restore)

    def _restore(self):
        providerwrites.SUPPORTED = self._supported

    def test_an_add_lead_token_cannot_activate_the_campaign(self):
        """The escalation: one lead-add's approval starting the sequence."""
        transport = Transport()
        with self.assertRaises(providerwrites.WriteRefused) as caught:
            providerwrites.perform(
                providerwrites.LINKEDIN_ACTIVATE,
                authorization=token(providerwrites.LINKEDIN_ADD_LEAD),
                payload={"note": APPROVED["note"]}, step=APPROVED,
                transport=transport, readback=lambda: {}, expected={})
        self.assertIn("add_lead", str(caught.exception))
        self.assertEqual(transport.calls, [],
                         "the provider was called despite the refusal")

    def test_the_matching_operation_is_not_refused_for_this_reason(self):
        """The guard must refuse the mismatch, not every write.

        Without this, a check that refused everything would pass the test
        above while proving nothing.
        """
        transport = Transport()
        with self.assertRaises(Exception) as caught:
            providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                authorization=token(providerwrites.LINKEDIN_ADD_LEAD),
                payload={"note": APPROVED["note"]}, step=APPROVED,
                transport=transport, readback=lambda: {}, expected={})
        # It still fails - there is no open reservation - but not for the
        # operation-mismatch reason, which is what is being pinned here.
        self.assertNotIn("is for 'heyreach.add_lead' and this is",
                         str(caught.exception))


class TheTokenNamesOneWording(QueueTest):

    def setUp(self):
        super().setUp()
        self._supported = providerwrites.SUPPORTED
        providerwrites.SUPPORTED = tuple(self._supported) + (
            providerwrites.LINKEDIN_ADD_LEAD,)
        self.addCleanup(self._restore)

    def _restore(self):
        providerwrites.SUPPORTED = self._supported

    def _refusal(self, **kwargs):
        transport = Transport()
        with self.assertRaises(providerwrites.WriteRefused) as caught:
            providerwrites.perform(
                providerwrites.LINKEDIN_ADD_LEAD,
                authorization=token(providerwrites.LINKEDIN_ADD_LEAD),
                transport=transport, readback=lambda: {}, expected={},
                **kwargs)
        self.assertEqual(transport.calls, [],
                         "the provider was called despite the refusal")
        return str(caught.exception)

    def test_unapproved_copy_cannot_ride_an_approved_token(self):
        """The payload carries words the authorization never blessed."""
        why = self._refusal(payload={"note": OTHER["note"]}, step=APPROVED)
        self.assertIn("approved note does not appear", why)

    def test_declaring_a_different_step_is_refused(self):
        """And the caller cannot simply relabel the step to match."""
        why = self._refusal(payload={"note": OTHER["note"]}, step=OTHER)
        self.assertIn("changed after it was approved", why)

    def test_a_facing_write_with_no_step_cannot_be_compared(self):
        """Omitting the step must fail closed, not skip the comparison."""
        why = self._refusal(payload={"note": OTHER["note"]})
        self.assertIn("no `step`", why)


if __name__ == "__main__":
    unittest.main()
