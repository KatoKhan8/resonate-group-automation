"""A refused stop is reported, and the reply survives it.

`inbound._stop_one` is the only thing standing between a reply and a lost
reply: `leadstop.stop_contact` refuses several ways before it ever reads a
provider (a contact in no campaign, a record with no lead id, a tenancy
mismatch), and `_stop_one` catches EVERY exception and returns it
classified - attempted, not stopped, error, why - so the reply's
classification, the account hold and the alert all still happen.

The existing `test_a_reply_reaches_the_provider_not_just_the_record`
proves this for a SYNTHETIC failure - a monkeypatched stopper raising
StopUnverified, the failure of a provider read. It does not prove the same
for the REAL refusals that happen before any provider read, which are the
common case for a record whose campaign was closed underneath it. This
test uses the real `leadstop` chain, no monkeypatch, against a record with
a lead id that no campaign claims: `stop_contact` refuses with
StopRefused("... is in no campaign ...") before the first provider call.

The property: the refusal reaches the outcome as a classified error naming
its reason, and the reply is still applied. A handler that let a refused
stop escape would discard the reply event itself - the one thing the
person can still be answered on. No provider is contacted; the campaigns
file is an empty throwaway so the campaign lookup reads no real state.
"""
import os
import shutil
import tempfile
import unittest

from src import inbound, store
from tests.base import QueueTest
from tests.test_a_reply_reaches_the_provider_not_just_the_record import (
    record,
    reply_event,
)


class ARefusedStopDoesNotLoseTheReply(QueueTest):

    def setUp(self):
        super().setUp()
        # QueueTest gives this test a throwaway QUEUE; the campaign file
        # must be one too, or the real campaign lookup would read state
        # outside the test. Empty file: this record is in no campaign.
        tmpdir = tempfile.mkdtemp(prefix="glm-stop-refusal-")
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        campaigns_file = os.path.join(tmpdir, "campaigns.jsonl")
        with open(campaigns_file, "w", encoding="utf-8"):
            pass
        self._prev_campaigns = os.environ.get("CAMPAIGNS")
        os.environ["CAMPAIGNS"] = campaigns_file
        self.addCleanup(self._restore_campaigns)

    def _restore_campaigns(self):
        if self._prev_campaigns is None:
            os.environ.pop("CAMPAIGNS", None)
        else:
            os.environ["CAMPAIGNS"] = self._prev_campaigns

    def test_the_refusal_is_classified_and_the_reply_is_applied(self):
        store.save([record()])
        outcome = inbound.handle(reply_event(), store.load())

        self.assertEqual(
            outcome["applied"]["status"], "applied",
            "a refused stop discarded the reply it was serving")
        self.assertIsNotNone(
            outcome.get("classification"),
            "a refused stop prevented the reply's classification")

        stop = (outcome.get("provider_stop") or {}).get("email") or {}
        self.assertTrue(
            stop.get("attempted"),
            "the stop was not even attempted for this reply")
        self.assertFalse(
            stop.get("stopped"),
            "a refused stop reported itself as stopped")
        self.assertEqual(
            stop.get("error"), "StopRefused",
            f"the refusal class must be StopRefused, was {stop.get('error')!r}")
        self.assertIn(
            "is in no campaign", stop.get("why") or "",
            "the refusal must name its reason: a record with a lead id that "
            "no campaign claims")


if __name__ == "__main__":
    unittest.main()
