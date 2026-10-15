#!/usr/bin/env python3
"""The as-sent total is RECORDED beside the gated figure, never derived.

THE RULE THIS PINS. Operator, 2026-10-15 23:00, TASK 0071:

    message words     gated at 90, certification bound 88, opt-out EXCLUDED
    as-sent total     RECORDED, not gated, opt-out INCLUDED

The ceiling governs what we wrote. The opt-out is required, identical on
every email, and not ours to shorten. But every count from now carries
both figures, because the defect this closes was not the ceiling - it was
a number on a signed sheet (`canary/APPROVAL-SHEET-2026-10-15.md`) that
was not the number that leaves: `lint.countable_words` deletes the opt-out
line before counting, so both printed counts on every approved row sat 11
words under what the prospect receives, and the widest approved body
carries 100 words against a ceiling of 90 while the sheet said 91.

WHAT EACH TEST HERE IS FOR, and none of them reads the source:

  - PRESENCE, not size: a body inside the ceiling on the message count
    must not pass the gate without its as-sent total being recorded - on
    the pure check's result and on the staging gate's `length_gate`
    report, which is the exact object the approval sheet was built from.
    An absent number is the defect; the figure's VALUE is asserted only
    to prove the recorded number is the one that leaves, not a copy of
    the gated one;
  - the EXEMPTION, both directions: the opt-out does not count toward
    the gated figure (a body AT 90 message words carrying the opt-out
    passes; folding the opt-out back in would read 101 and refuse bodies
    the operator approved), and the two figures on the same text differ
    by exactly the opt-out line - never by a constant somebody typed.

The counts in every fixture are re-counted here with the repo's own
counters rather than trusted, the convention of
`test_the_word_ceiling_is_enforced_on_the_composed_body`.
"""
import unittest
from unittest import mock

from src import bisonfactory, lint, optout, sequencegate
from tests.test_the_word_ceiling_is_enforced_on_the_composed_body import (
    OFFER_WITH_LINK, _plan, countable, words)


class TestTheAsSentTotalIsRecordedNotDerived(unittest.TestCase):
    """Point 3: the absent number was the defect, so presence is the test."""

    def test_a_body_inside_the_ceiling_records_both_figures(self):
        """90 MESSAGE words with the opt-out line present - inside the
        ceiling, and carrying the eleven words the gated figure deletes.
        The control runs first: the body PASSES today's ceiling, so if
        this test fails it is because a figure is absent, not because the
        body is over."""
        body = optout.append_opt_out(words(90))
        self.assertEqual(90, countable(body))  # the opt-out is exempt
        result = sequencegate.check_composed_length({"em1": body})
        self.assertTrue(result["passed"], result["failures"])
        rows = {row["step"]: row for row in result["measured"]}
        self.assertEqual({"step", "message_words", "as_sent_words"},
                         set(rows["em1"]))
        self.assertEqual(90, rows["em1"]["message_words"])
        self.assertEqual(101, rows["em1"]["as_sent_words"])

    def test_the_staging_report_carries_both_figures_for_every_lead(self):
        """The sheet was built from `report['length_gate']`; the missing
        column lived there. A passing push must leave the figures on the
        report: em1 in the starter shape (+CTA, +signature) and em2 in
        the reply shape (+signature, no CTA), both composed by the real
        `_variables_for` with the real opt-out appended."""
        report = {}
        bodies = {"em1": words(86), "em2": words(87)}
        with mock.patch.object(bisonfactory, "_offer_for",
                               return_value=("OFFER-TEST", OFFER_WITH_LINK)):
            bisonfactory._refuse_composed_ceiling(
                {"client": "productive"}, _plan(bodies), [], report)
        self.assertTrue(report["length_gate"]["passed"])
        rows = {row["step"]: row
                for row in report["length_gate"]["leads"][0]["measured"]}
        self.assertEqual({"em1", "em2"}, set(rows))
        # both shapes sit AT the ceiling on the gated figure: 86+4 and 87+3
        self.assertEqual(90, rows["em1"]["message_words"])
        self.assertEqual(90, rows["em2"]["message_words"])
        # and both carry the opt-out the gated figure deletes: 90 + 11
        self.assertEqual(101, rows["em1"]["as_sent_words"])
        self.assertEqual(101, rows["em2"]["as_sent_words"])

    def test_the_refusal_names_both_figures(self):
        """A count that is printed is printed as the pair. The old refusal
        called the gated figure 'words AS SENT' - the sheet's defect in
        one line, a number labelled as the other number."""
        result = sequencegate.check_composed_length(
            {"em1": optout.append_opt_out(words(91))})
        self.assertFalse(result["passed"])
        why = result["failures"][0]["why"]
        self.assertIn("91", why)   # message words, the gated figure
        self.assertIn("102", why)  # as sent, the opt-out counted
        self.assertIn("90", why)   # the ceiling, still on the gated figure


class TestTheOptOutIsExemptFromTheCeiling(unittest.TestCase):
    """Point 4: the exemption, pinned in both directions."""

    def test_the_opt_out_line_is_eleven_words_and_entirely_exempt(self):
        """The gated figure of the opt-out alone is ZERO - the counter
        deletes it - and its as-sent figure is ELEVEN. The wording is
        PROVISIONAL operator content: if it is ever changed, this pin goes
        red on purpose, because the sheet and every recorded delta must be
        re-measured, not absorbed."""
        self.assertEqual(0, len(lint.countable_words(optout.OPT_OUT_LINE)))
        self.assertEqual(11, len(lint.as_sent_words(optout.OPT_OUT_LINE)))

    def test_a_body_at_the_ceiling_with_the_opt_out_passes(self):
        """90 message words and the opt-out line present is AT the
        ceiling, not over it. If the opt-out is ever folded back into the
        gated figure this reads 101 and refuses - it would start refusing
        bodies the operator approved, which is the red direction this
        test exists to catch."""
        result = sequencegate.check_composed_length(
            {"em1": optout.append_opt_out(words(90))})
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual([], result["failures"])

    def test_the_exemption_is_the_only_difference_between_the_figures(self):
        """The delta between the two figures is the opt-out line's own
        as-sent count - measured on the text, never a constant. On the
        composed shape (plain name-and-company signature, no sign-off
        block) nothing else differs."""
        body = optout.append_opt_out(words(50))
        self.assertEqual(countable(words(50)), countable(body))
        delta = len(lint.as_sent_words(body)) - countable(body)
        self.assertEqual(len(lint.as_sent_words(optout.OPT_OUT_LINE)), delta)


if __name__ == "__main__":
    unittest.main()
