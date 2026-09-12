#!/usr/bin/env python3
"""The same CampaignSpec staged twice must not build two provider campaigns.

`providerwrites.perform` reserves a ledger key for every prospect-facing
operation, and refuses one that is already SENT. For everything else - create
campaign, create list, set sequence, assign sender, set limits - `key` was
None and NOTHING refused a repeat. Two calls with identical material built
two provider campaigns, and a crash between the POST and the response left a
campaign nobody could find plus a retry that made another.

## Why not the action ledger

`actionledger.reserve` refuses a row that cannot name a record, a contact, a
sender and a step: "an action nobody can attribute is an action nobody can
reconcile". A staging write has none of those - it is a fact about a CAMPAIGN
rather than about a person. Bending that attribution rule to fit would weaken
the guard that makes the ledger worth having, so the campaign row remembers
what has been staged onto it instead, keyed by a fingerprint of the material.

Restage the same material and it refuses. Change the material and the
fingerprint moves, so it is a different write rather than a repeat - which is
what a spec fingerprint is for.
"""
import os
import unittest

from src import campaigns, providerwrites, store
from tests.base import QueueTest

OP = "heyreach.pause"          # the one declared, non-prospect-facing verb
PAYLOAD = {"campaignId": 594061}


class Spy:
    """Records every transport call; answers the read-back as asked."""

    def __init__(self, status="PAUSED"):
        self.calls = []
        self.status = status

    def transport(self, payload):
        self.calls.append(payload)
        return {"status": 200}

    def readback(self):
        return {"status": self.status}


class StagingIsIdempotent(QueueTest):

    def setUp(self):
        super().setUp()
        self._pinned = {k: os.environ.pop(k, None)
                        for k in ("CAMPAIGNS", "ACTION_LEDGER")}
        row = campaigns.new_campaign("camp-1", "productive", "CLIENT - CANARY",
                                     created_by="operator")
        row["heyreach_campaign_id"] = 594061
        campaigns.save(campaigns.load() + [row])

    def tearDown(self):
        for key, value in self._pinned.items():
            if value is not None:
                os.environ[key] = value
        super().tearDown()

    def perform(self, spy, payload=PAYLOAD, expected=None):
        with mock_supported():
            return providerwrites.perform(
                OP, tenant="productive", campaign="camp-1", payload=payload,
                transport=spy.transport, readback=spy.readback,
                expected=expected if expected is not None
                else {"status": "PAUSED"})

    def test_the_first_staging_write_reaches_the_provider(self):
        spy = Spy()
        out = self.perform(spy)
        self.assertEqual(out["class"], providerwrites.ACCEPTED)
        self.assertEqual(spy.calls, [PAYLOAD])

    def test_and_it_is_recorded_on_the_campaign(self):
        self.perform(Spy())
        entry = (campaigns.get("camp-1").get("provider_staged") or {}).get(OP)
        self.assertIsNotNone(entry, "nothing remembers that this was staged")
        self.assertTrue(entry.get("fingerprint"))
        self.assertTrue(entry.get("at"))

    def test_the_second_with_the_same_material_is_refused(self):
        self.perform(Spy())
        second = Spy()
        with self.assertRaises(providerwrites.WriteRefused) as caught:
            self.perform(second)
        self.assertIn("already staged", str(caught.exception))
        self.assertEqual(second.calls, [],
                         "the provider was asked to build it a second time")

    def test_different_material_is_a_different_write(self):
        """Not a repeat: a changed spec is a new thing to stage, which is what
        makes the fingerprint the right key rather than the operation name."""
        self.perform(Spy())
        other = Spy()
        self.perform(other, payload={"campaignId": 999999})
        self.assertEqual(other.calls, [{"campaignId": 999999}])

    def test_a_refused_write_is_not_recorded_as_staged(self):
        """An UNVERIFIED write must stay re-attemptable once a human has read
        provider truth. Recording it would refuse that retry on the strength
        of a write nobody could confirm."""
        spy = Spy(status="IN_PROGRESS")        # read-back disagrees
        with self.assertRaises(providerwrites.WriteUnverified):
            self.perform(spy)
        self.assertEqual(spy.calls, [PAYLOAD], "the transport never ran")
        entry = (campaigns.get("camp-1").get("provider_staged") or {}).get(OP)
        self.assertIsNone(entry,
                          "a write nobody could confirm was recorded as done")

    def test_and_so_it_can_be_attempted_again(self):
        with self.assertRaises(providerwrites.WriteUnverified):
            self.perform(Spy(status="IN_PROGRESS"))
        again = Spy()
        out = self.perform(again)
        self.assertEqual(out["class"], providerwrites.ACCEPTED)
        self.assertEqual(again.calls, [PAYLOAD])

    def test_the_fingerprint_ignores_key_order(self):
        """A payload that round-trips through JSON comes back reordered, and
        an ordering difference is not a different campaign."""
        one = providerwrites.material_fingerprint({"a": 1, "b": 2})
        two = providerwrites.material_fingerprint({"b": 2, "a": 1})
        self.assertEqual(one, two)


import contextlib
from unittest import mock


@contextlib.contextmanager
def mock_supported():
    """`heyreach.pause` is declared; this keeps the test independent of that."""
    with mock.patch.object(providerwrites, "SUPPORTED",
                           (providerwrites.LINKEDIN_PAUSE,)):
        yield


if __name__ == "__main__":
    unittest.main()
