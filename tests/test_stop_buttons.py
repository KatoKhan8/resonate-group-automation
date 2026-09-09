"""Two ways to stop this system, and neither of them stopped it.

**Pausing a campaign did not stop sending.** `orchestrator.pause` sets
`status` to `paused` and `eligibility._campaign` - the function that
decides whether a payload may be built - asked about the freeze, the
rejection, the launch state and the approval, and never about the status.
So a campaign an operator paused because a reply had arrived returned
`None` from the gate and `verify_before_payload` passed it.
`campaigns.UNLAUNCHABLE` knows these statuses and is consulted only by
`validate`, at launch and resume time, which is too late to be a stop
button. This is the shape the repository keeps producing: the state was
recorded correctly and the thing that had to read it did not.

**An unattributable removal request was dropped entirely.**
`events.apply` returns `contact_key = None` whenever the reply's address
matches no contact - an alias, a forward, somebody writing from their
phone - and every branch that acts on the replier was guarded by
`replier is not None`. `UNSUBSCRIBE` plans `replier=SUPPRESS,
account=CONTINUE`, so with nobody to aim it at, nothing at all was
written: no suppression, no contact state, nothing in the hygiene index
and nothing in the agency index. The generic hold every reply produces
was the only trace, and an operator clears that once they have read it.

The fix widens rather than narrows, which is what this module already
says it does about uncertainty. We cannot aim a removal request at a
person we are unable to name, and the only alternative to aiming it at
the whole account is losing it.
"""
import unittest

from src import accountpolicy as ap, campaigns, eligibility, store
from tests.base import QueueTest

AT = "2026-09-01T00:00:00+00:00"


class APausedCampaignSends(QueueTest):
    """The gate, asked directly. `_campaign` is what `decide` consults."""

    def campaign(self, status):
        base = {"campaign_id": "x", "client": "demo", "record_ids": []}
        fingerprint = campaigns.fingerprint(base, [], None)
        base["fingerprint"] = fingerprint
        base["approval"] = {"action": "approve", "by": "a@b.test",
                            "fingerprint": fingerprint}
        base["status"] = status
        return base

    def verdict(self, status):
        return eligibility._campaign(self.campaign(status), [], None)

    def test_a_paused_campaign_is_blocked(self):
        """The defect."""
        self.assertEqual(self.verdict(campaigns.PAUSED),
                         eligibility.BLOCKED_CAMPAIGN_STOPPED)

    def test_a_completed_campaign_is_blocked(self):
        self.assertEqual(self.verdict(campaigns.COMPLETED),
                         eligibility.BLOCKED_CAMPAIGN_STOPPED)

    def test_a_failed_campaign_is_blocked(self):
        self.assertEqual(self.verdict(campaigns.FAILED),
                         eligibility.BLOCKED_CAMPAIGN_STOPPED)

    def test_a_running_campaign_is_not(self):
        """Otherwise the guard blocks everything and proves nothing."""
        self.assertIsNone(self.verdict(campaigns.RUNNING))

    def test_an_approved_campaign_is_not(self):
        self.assertIsNone(self.verdict(campaigns.APPROVED))

    def test_it_is_a_block_and_not_a_hold(self):
        """A hold is something a later step may satisfy. A campaign that
        was running and is not any more is not waiting for anything."""
        self.assertTrue(
            self.verdict(campaigns.PAUSED).startswith("blocked:"))

    def test_the_reason_has_a_sentence_a_person_can_read(self):
        self.assertIn(eligibility.BLOCKED_CAMPAIGN_STOPPED,
                      eligibility.HUMAN)

    def test_a_draft_still_reads_as_unapproved_rather_than_stopped(self):
        """The pre-approval statuses were already answered, and more
        precisely. Widening the new guard over them would have made the
        reason worse."""
        draft = self.campaign(campaigns.DRAFT)
        draft.pop("approval")
        self.assertEqual(eligibility._campaign(draft, [], None),
                         eligibility.HELD_CAMPAIGN_UNAPPROVED)


class ARemovalRequestFromNobodyWeKnow(QueueTest):

    def record(self):
        rec = store.new_record("acme", "domains", "demo", "Acme", "acme.test")
        rec["contacts"] = [
            {"key": "champ", "name": "A", "email": "champ@acme.test"},
            {"key": "other", "name": "B", "email": "other@acme.test"}]
        return rec

    def applied(self, outcome, contact_key=None):
        rec = self.record()
        out = ap.apply_reply(rec, contact_key, outcome, at=AT, channel="email",
                             reason="an address we do not know",
                             workspace="demo")
        return rec, out

    def test_an_unattributable_unsubscribe_stops_the_account(self):
        """The defect. Nothing at all used to be written."""
        rec, _ = self.applied(ap.UNSUBSCRIBE)
        self.assertTrue(rec.get("suppression"))

    def test_it_is_reported_as_a_change_rather_than_silently(self):
        _, out = self.applied(ap.UNSUBSCRIBE)
        self.assertIn("account_suppressed_unattributed", out["changed"])

    def test_an_unattributable_company_stop_still_stops_the_account(self):
        rec, _ = self.applied(ap.ACCOUNT_DNC)
        self.assertTrue(rec.get("suppression"))

    def test_a_named_unsubscribe_still_only_stops_that_person(self):
        """The discriminator. Widening is what we do when we cannot name
        the person - not instead of naming them."""
        rec, _ = self.applied(ap.UNSUBSCRIBE, contact_key="champ")
        self.assertFalse(rec.get("suppression"),
                         "a named removal request suppressed the whole "
                         "company")
        self.assertTrue(rec["contacts"][0].get("unsubscribed"))
        self.assertFalse(rec["contacts"][1].get("unsubscribed"))

    def test_an_unattributable_refusal_does_not_suppress(self):
        """Only a removal request widens. "Not interested" from an address
        we cannot place must not burn the account."""
        rec, _ = self.applied(ap.NEGATIVE)
        self.assertFalse(rec.get("suppression"))

    def test_an_unattributable_positive_still_only_holds(self):
        rec, out = self.applied(ap.POSITIVE)
        self.assertFalse(rec.get("suppression"))
        self.assertIn("account_held", out["changed"])

    def test_the_suppression_is_recorded_as_an_event(self):
        """It has to be visible to somebody reading the record, not only
        in a flag."""
        from src import events

        rec, _ = self.applied(ap.UNSUBSCRIBE)
        kinds = [e.get("type") for e in rec.get("events") or []]
        self.assertIn(events.ACCOUNT_SUPPRESSED, kinds)


if __name__ == "__main__":
    unittest.main()
