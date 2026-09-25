"""A stop's read-back must ask the provider, not answer itself.

Both stop paths shipped a read-back that could not fail, in opposite
directions, and both were found on 2026-09-25 by reading the action ledger
after a stop that demonstrably worked.

    EMAIL     readback=lambda: {"stopped": True}   expected={"stopped": True}
              The read-back was a constant byte-identical to the expectation,
              so `_classify` compared the literal to itself and answered
              ACCEPTED for every call, whatever the provider had done.

    LINKEDIN  readback returned the raw `campaigns_for_lead` ROWS - a list -
              against a dict expectation, so `_classify` fell through to
              `observed == expected` and answered DRIFTED for every call,
              including the ones that worked.

One recorded success it had not checked; the other recorded failure it had.
An audit that cannot tell a working stop from a broken one is worse than no
audit, because it is believed.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import leadstop                                       # noqa: E402
from src import providerwrites                                 # noqa: E402
from src.providers import heyreach                             # noqa: E402


class FakeHeyreach:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def campaigns_for_lead(self, profile_url=None):
        self.calls += 1
        return self.rows, len(self.rows)


class TestTheLinkedInReadbackAsksTheProvider(unittest.TestCase):

    def setUp(self):
        self._real = heyreach.campaigns_for_lead
        self.addCleanup(setattr, heyreach, "campaigns_for_lead", self._real)

    def _with(self, rows):
        fake = FakeHeyreach(rows)
        heyreach.campaigns_for_lead = fake.campaigns_for_lead
        return fake

    def test_a_lead_still_running_is_NOT_stopped(self):
        """The case that must refuse. `InSequence` is in RUNNING_LEAD_STATUSES."""
        self._with([{"campaignId": 1, "leadStatus": "InSequence"}])
        self.assertFalse(leadstop._linkedin_stop_took("u", 1))

    def test_pending_is_also_still_running(self):
        self._with([{"campaignId": 1, "leadStatus": "Pending"}])
        self.assertFalse(leadstop._linkedin_stop_took("u", 1))

    def test_a_lead_moved_out_of_the_running_set_IS_stopped(self):
        self._with([{"campaignId": 1, "leadStatus": "Paused"}])
        self.assertTrue(leadstop._linkedin_stop_took("u", 1))

    def test_it_is_scoped_to_THIS_campaign(self):
        """Another campaign being finished says nothing about this one.

        A profile sits in many campaigns; the defect being fixed compared the
        WHOLE array, so any shape at all read as drift. Scoping is the fix and
        it must not leak the other way either.
        """
        rows = [{"campaignId": 7, "leadStatus": "Finished"},
                {"campaignId": 9, "leadStatus": "InSequence"}]
        self._with(rows)
        self.assertTrue(leadstop._linkedin_stop_took("u", 7))
        self.assertFalse(leadstop._linkedin_stop_took("u", 9))

    def test_a_lead_absent_from_the_campaign_is_not_proven_stopped(self):
        self._with([{"campaignId": 7, "leadStatus": "Paused"}])
        self.assertFalse(leadstop._linkedin_stop_took("u", 9))

    def test_an_unreadable_provider_is_not_proven_stopped(self):
        def boom(profile_url=None):
            raise RuntimeError("provider down")
        heyreach.campaigns_for_lead = boom
        self.assertFalse(leadstop._linkedin_stop_took("u", 1))

    def test_it_actually_calls_the_provider(self):
        """The property the old code lacked: something is asked."""
        fake = self._with([{"campaignId": 1, "leadStatus": "Paused"}])
        leadstop._linkedin_stop_took("u", 1)
        self.assertEqual(fake.calls, 1)


class TestClassifyWouldHaveAcceptedTheOldConstant(unittest.TestCase):
    """Pins WHY the old email read-back could not fail."""

    def test_a_readback_equal_to_the_expectation_always_accepts(self):
        verdict = providerwrites._classify({"stopped": True}, {"stopped": True})
        self.assertEqual(verdict, providerwrites.ACCEPTED)

    def test_and_a_false_readback_is_what_refusal_looks_like(self):
        verdict = providerwrites._classify({"stopped": False}, {"stopped": True})
        self.assertEqual(verdict, providerwrites.DRIFTED)

    def test_a_list_against_a_dict_always_drifts(self):
        """The LinkedIn defect, pinned: the shape alone decided the verdict."""
        rows = [{"campaignId": 1, "leadStatus": "Paused"}]
        self.assertEqual(providerwrites._classify(rows, {"stopped": True}),
                         providerwrites.DRIFTED)


if __name__ == "__main__":
    unittest.main()
