"""A verification stopped by the budget does not look like one that finished.

`verify()` has two stops. The per-contact cost cap records
`PROVIDER_CALL_SKIPPED` and breaks; the batch budget used to break with no
event at all. So a contact the batch budget cut short - one vendor asked, the
second never reached - was indistinguishable on the record from a contact the
waterfall had genuinely finished with, and the event log said a run had
completed when it had run out of money.

That is the same shape as the incident this session opened with: a stopped
thing reading as a finished thing because nothing wrote down the difference.

The distinction is not cosmetic. "One confirmation of a required two" and
"we stopped before asking the second" both leave the address unsendable, but
only the second is fixed by raising the budget and re-running.
"""
import unittest

from src import enrich, events, verification as V
from tests.base import ProviderTest


class AStoppedRunSaysSo(ProviderTest):

    def contact(self):
        return {"key": "c1", "name": "A Person", "email": "a@example.test"}

    def record(self):
        return {"id": "r1", "client": "c", "domain": "example.test",
                "contacts": [self.contact()], "events": []}

    def skips(self, rec):
        return [e for e in rec.get("events") or []
                if e.get("type") == events.PROVIDER_CALL_SKIPPED
                and e.get("operation") == "verify"]

    def test_an_exhausted_batch_budget_is_recorded(self):
        rec = self.record()
        V.verify(rec["contacts"][0], V.DEFAULT_POLICY, live=True, rec=rec,
                 budget=enrich.Budget(0))
        skipped = self.skips(rec)
        self.assertTrue(skipped, "the batch budget stopped silently")
        self.assertIn("budget", (skipped[0].get("reason") or "").lower())

    def test_the_reason_distinguishes_it_from_the_per_contact_cap(self):
        """Two different stops. One is raise-the-budget, the other is not."""
        rec = self.record()
        V.verify(rec["contacts"][0], V.DEFAULT_POLICY, live=True, rec=rec,
                 budget=enrich.Budget(0))
        reason = (self.skips(rec)[0].get("reason") or "").lower()
        self.assertIn("batch", reason)
        self.assertNotIn("cost cap for this contact", reason)

    def test_a_run_with_room_records_no_budget_skip(self):
        """Otherwise the event fires always and distinguishes nothing."""
        rec = self.record()
        V.verify(rec["contacts"][0], V.DEFAULT_POLICY, live=False, rec=rec,
                 budget=enrich.Budget(10))
        self.assertEqual(
            [e for e in self.skips(rec)
             if "budget" in (e.get("reason") or "").lower()], [])


class ACatchAllCannotBeClearedAlone(unittest.TestCase):
    """Why no further credit was spent on this cohort.

    `CONFIRMING_STATUSES` is `('valid',)`. A catch-all is the absence of a
    confirmation, not one - so on a catch-all domain Reoon can supply at most
    one of the two the policy requires, and the only other vendor is
    Deliverable, whose contract gate refuses before any HTTP call. The address
    is therefore structurally unreachable rather than merely unverified, and
    buying another Reoon answer cannot change it.
    """

    def evidence(self, safe):
        return [{"provider": "contactout", "status": "accept_all",
                 "email": "x@catchall.test"},
                {"provider": "reoon", "status": "accept_all",
                 "email": "x@catchall.test", "is_safe_to_send": safe}]

    def test_a_catch_all_is_not_a_confirmation(self):
        self.assertNotIn("accept_all", V.CONFIRMING_STATUSES)

    def test_even_a_cleared_catch_all_is_not_sendable(self):
        decision = V.decide(self.evidence(True), V.DEFAULT_POLICY)
        self.assertFalse(decision["sendable"])

    def test_a_declined_catch_all_is_not_sendable_either(self):
        decision = V.decide(self.evidence(False), V.DEFAULT_POLICY)
        self.assertFalse(decision["sendable"])


if __name__ == "__main__":
    unittest.main()
