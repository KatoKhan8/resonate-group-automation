"""The adapter read fields this provider does not send.

A live canary on 2026-09-07 captured the real response. The verdict arrives as
`data.email_status`, with the vocabulary `deliverable | undeliverable | risky
| unknown`, and the task state as `data.processing_status`. `classify` looked
for `status / result / state / verdict / deliverability` and `pending` for
`status / state / task_status / result` - none of which this provider sends.

So every real answer classified as `unknown`, and `pending` returned False on
a body that said pending, which made `collect` return on the first poll with
no verdict and no address on it. Armed, the adapter would have spent a credit
per address and confirmed nothing, for ever. It failed closed - `unknown`
holds an address and never sends - which is why nothing unsafe shipped and
why nothing announced the problem either. That is the shape this repository
keeps finding: computed correctly, consumed by nobody.

The bodies below are the ones the canary actually returned, replayed offline.
No credit is spent by this file.
"""
import unittest

from src.providers import deliverable


def answer(email_status, catch_all=False, processing="completed"):
    """The real envelope, as recorded from a live call."""
    return {
        "message": {"status": "success", "statusCode": 200,
                    "description": "Email task status fetched successfully"},
        "data": {"processing_status": processing, "task_id": "t-1",
                 "email": "someone@example.test", "email_status": email_status,
                 "is_catch_all": catch_all, "provider": "Private"},
    }


class TheVerdictIsReadFromTheFieldItArrivesIn(unittest.TestCase):

    def classify(self, *a, **kw):
        return deliverable.classify(deliverable.unwrap(answer(*a, **kw)))

    def test_deliverable_is_valid(self):
        self.assertEqual(self.classify("deliverable"), "valid")

    def test_undeliverable_is_invalid_not_valid(self):
        """The whole reason `words_of` exists. `deliverable` is a substring of
        `undeliverable`, and a substring match here turns the one word meaning
        "do not send" into a confirmation."""
        self.assertEqual(self.classify("undeliverable"), "invalid")

    def test_risky_is_unknown(self):
        self.assertEqual(self.classify("risky"), "unknown")

    def test_unknown_is_unknown(self):
        self.assertEqual(self.classify("unknown"), "unknown")

    def test_a_catch_all_is_reported_as_one(self):
        self.assertEqual(self.classify("deliverable", catch_all=True),
                         "accept_all")

    def test_a_status_this_provider_never_sends_is_still_unknown(self):
        """The fail-closed direction has to survive the fix."""
        self.assertEqual(self.classify("something_new_they_invented"),
                         "unknown")


class ThePollKnowsWhenToWait(unittest.TestCase):

    def test_a_running_task_is_pending(self):
        self.assertTrue(deliverable.pending(answer("unknown",
                                                   processing="pending")))

    def test_a_settled_task_is_not(self):
        self.assertFalse(deliverable.pending(answer("deliverable")))


class NothingInTheAnswerIsUnaccountedFor(unittest.TestCase):

    def test_every_field_the_provider_sends_is_known(self):
        """`unmapped_fields` is the tripwire for the next contract change.
        It reported three fields before this fix, and nobody was reading it."""
        self.assertEqual(deliverable.unmapped_fields(answer("deliverable")), [])


class TheContractGateIsStillShut(unittest.TestCase):
    """Reading the shape is not the same as arming the provider.

    Only the negative branch has been proven live. Arming is a human decision
    and needs one confirmation of the positive branch against an address
    somebody controls.
    """

    def test_a_call_is_still_refused_until_a_human_confirms(self):
        import os
        previous = os.environ.pop("DELIVERABLE_RESULT_SHAPE", None)
        try:
            with self.assertRaises(deliverable.ContractNotVerified):
                deliverable.require_contract()
        finally:
            if previous is not None:
                os.environ["DELIVERABLE_RESULT_SHAPE"] = previous


if __name__ == "__main__":
    unittest.main()
