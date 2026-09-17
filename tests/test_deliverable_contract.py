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
import os
import unittest
from unittest import mock

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


class TheContractGateHasTwoSides(unittest.TestCase):
    """The gate is the OPERATOR's, and the test is that it is closed by default.

    This class was `TheContractGateIsNowOpen` and asserted
    `result_shape_confirmed()` is True with nothing set. TASK-196 had changed
    that function to return True whenever `CONFIRMED_RESPONSE_SHAPE` was
    populated - a literal in the same file, so always - and the change was
    reverted on 2026-09-16 as a gate opening itself. **These tests were not
    reverted with it**, so three of them have asserted a falsehood ever since,
    and worse, they encoded the intent that was rejected: a suite that goes
    green only when the gate is open is a suite arguing for it to be open.

    The gate's own docstring says what it is for: opening it "admits the whole
    verification waterfall for 159 contacts with no evidence, at up to three
    credits each - which is the spend the gate exists to make somebody
    choose". So the contract under test is the gate's BEHAVIOUR, which is a
    stronger thing to pin than either previous version:

        unset  -> refuses, and `contract_gaps` names the shape as missing
        set    -> opens, and the parser is allowed to run

    Neither direction depends on the operator's actual decision, so this
    stays green whichever way they go.
    """

    def test_the_gate_is_closed_when_the_operator_has_not_opened_it(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(deliverable.SHAPE_VAR, None)
            self.assertFalse(deliverable.result_shape_confirmed())

    def test_a_closed_gate_refuses_before_any_network_call(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(deliverable.SHAPE_VAR, None)
            with self.assertRaises(deliverable.ContractNotVerified):
                deliverable.require_contract()

    def test_a_closed_gate_says_which_half_is_missing(self):
        """A refusal that does not name the gap is a refusal nobody can act
        on, and the shape half is the one an operator resolves."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(deliverable.SHAPE_VAR, None)
            gaps = " ".join(deliverable.contract_gaps()).lower()
        self.assertIn("shape", gaps)

    def test_the_operator_opens_it_with_one_variable(self):
        with mock.patch.dict(os.environ,
                             {deliverable.SHAPE_VAR: "confirmed"}):
            self.assertTrue(deliverable.result_shape_confirmed())
            deliverable.require_contract()      # no longer raises

    def test_the_word_is_checked_rather_than_the_variable_existing(self):
        """`DELIVERABLE_RESULT_SHAPE=maybe` is not consent."""
        with mock.patch.dict(os.environ, {deliverable.SHAPE_VAR: "maybe"}):
            self.assertFalse(deliverable.result_shape_confirmed())


if __name__ == "__main__":
    unittest.main()
