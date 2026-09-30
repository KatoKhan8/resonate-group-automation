#!/usr/bin/env python3
"""em2 and em4 are replies, not new arguments.

OPERATOR DECISION, Zvonimir, 2026-09-30, recorded with his name:

    em2 and em4 are replies inside threads A and B. They are short follow-ups
    that build on em1 and em3 and do NOT need their own new rung. Distinct
    rungs are required only for em1, em3 and em5... em2/em4 must still add
    something (a question, a clarification, a Productive capability) rather
    than repeat the previous email. Keep all claim, figure and copy gates.

WHY IT WAS COSTING CONTACTS. `sequencegate` demanded every email carry its
own rung's vocabulary, so a genuine two-line reply inside a thread was
refused for "pursues none of the offer's step objectives" - measured on
2026-09-30 as `em2 (step_objectives)` and `em4 (step_objectives)` failures
across most candidates in the queue.

THE OBJECTIVES ARE NOT DELETED. Rungs 2 and 4 remain in the offer as the
reason a follow-up exists and the writer still reads them. What stops is the
DEMAND that the step carry that vocabulary and take part in the ladder order
comparison. The list is read from the offer's own `thread_reply_rungs`, so a
different offer with a different shape is not forced into Offer A's.

AND THE REPLACEMENT RULE IS ENFORCED, NOT ASSUMED: `followup_adds_value`
refuses a step that repeats an earlier one, which is exactly "must still add
something".
"""
import unittest

from src import offers, sequencegate

OFFER = offers.load().get("OFFER-A-ECONOMIC-BUYER")
RULES = offers.messaging_rules()

#: em1, em3, em5 carry their rungs. em2 and em4 deliberately carry NONE of
#: theirs and say something different instead - which is what a reply is.
SEQ = {
    "em1": "margin visibility while the work is still running",
    "em2": "a short follow up asking one different practical question about "
           "scheduling next week",
    "em3": "resource decisions that move margin",
    "em4": "a brief note on a separate operational topic, staffing calendars",
    "em5": "reframe and close",
}


def _failures(emails, check="step_objectives"):
    verdict = sequencegate.check({"emails": emails}, offer=OFFER,
                                 messaging_rules=RULES)
    return [f.get("step") for f in (verdict.get("failures") or ())
            if f.get("check") == check]


class AReplyNeedsNoRung(unittest.TestCase):
    def test_em2_and_em4_may_carry_none_of_their_rung(self):
        self.assertEqual([], _failures(SEQ),
                         "a thread reply was refused for not carrying a rung")

    def test_the_offer_declares_which_rungs_those_are(self):
        """Read from data, not spelled in the gate."""
        self.assertEqual({"2", "4"},
                         {str(r) for r in OFFER.get("thread_reply_rungs")})

    def test_the_objectives_themselves_are_still_there(self):
        """The writer still reads rung 2 and 4 as the reason to follow up."""
        objectives = OFFER.get("step_objectives") or {}
        self.assertEqual(5, len(objectives))
        self.assertTrue(str(objectives.get("2") or objectives.get(2)))


class THE_REAL_RUNGS_STILL_BITE(unittest.TestCase):
    """If any of these passes, the ladder has stopped being a gate."""

    def test_em1_missing_its_rung_is_refused(self):
        self.assertIn("em1", _failures(dict(SEQ, em1="office plants and tea")))

    def test_em3_missing_its_rung_is_refused(self):
        self.assertIn("em3", _failures(dict(SEQ, em3="office plants and tea")))

    def test_em5_missing_its_rung_is_refused(self):
        self.assertIn("em5", _failures(dict(SEQ, em5="office plants and tea")))

    def test_the_order_of_the_real_rungs_is_still_checked(self):
        """rung 1's words on em3 while em1 carries none of them."""
        rotated = dict(SEQ, em1="a general note about scheduling",
                       em3="margin visibility while the work is still running")
        self.assertTrue(_failures(rotated),
                        "the ladder stopped checking order")


class A_REPLY_MUST_STILL_ADD_SOMETHING(unittest.TestCase):
    """The operator's replacement rule, enforced by `followup_adds_value`."""

    def test_em2_repeating_em1_is_refused(self):
        self.assertIn("em2",
                      _failures(dict(SEQ, em2=SEQ["em1"]),
                                check="followup_adds_value"))

    def test_em4_repeating_em3_is_refused(self):
        self.assertIn("em4",
                      _failures(dict(SEQ, em4=SEQ["em3"]),
                                check="followup_adds_value"))


class TheOtherGatesAreUntouched(unittest.TestCase):
    def test_an_ai_capability_at_a_non_mechanism_rung_is_still_refused(self):
        bad = dict(SEQ, em1="Report Intelligence answers questions, margin "
                             "visibility while the work is still running")
        self.assertTrue(_failures(bad, check="ai_is_supporting"))


if __name__ == "__main__":
    unittest.main()
