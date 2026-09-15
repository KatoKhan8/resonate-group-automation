"""The opening detector must not be reading the closing.

## The bug this pins

`_opening_shape` took the first LINE of a message and asked whether it ended
with a question mark. A LinkedIn message is ONE PARAGRAPH, so the "first line"
is the entire message, and its last character is the CLOSING punctuation. The
function therefore returned exactly what `_cta_shape` returned, on every
single-paragraph message ever measured.

That is why TASK-087 reported every LinkedIn arm as `opening=question
cta=question` and concluded the arms had collapsed into one shape. The arms
had not been measured: one property was read twice and reported as two.

A diversity check whose two structural dimensions are the same dimension can
only ever see half the structure, and two genuinely different arms - one
opening with a statement, one with a question - look identical to it as long
as both happen to close the same way.

These tests assert on RETURNED VALUES, never on the text of the source, so
they survive somebody rewording a comment.
"""

import unittest

from src import variantgen


# One paragraph, no newlines - the real shape of a LinkedIn message, and the
# shape the old implementation could not read.
OPENS_STATEMENT_CLOSES_QUESTION = (
    "hi jacob, this is a quick note from someone working with agencies on "
    "resourcing visibility. how do you currently handle it?"
)
OPENS_QUESTION_CLOSES_QUESTION = (
    "hi jacob, how do you currently handle resourcing visibility? most "
    "agencies rebuild it by hand. worth comparing notes?"
)
OPENS_QUESTION_CLOSES_STATEMENT = (
    "hi jacob, how do you currently handle resourcing visibility? happy to "
    "share what other agencies your size settled on."
)
OPENS_STATEMENT_CLOSES_STATEMENT = (
    "hi jacob, Productive joins up budgets, time tracking and resourcing in "
    "one place. happy to send over a short walkthrough."
)


class TheOpeningIsReadFromTheOpening(unittest.TestCase):

    def test_a_statement_opening_that_closes_on_a_question_reads_as_statement(self):
        # The exact case the old code got wrong: it saw the trailing "?" of the
        # whole paragraph and called the OPENING a question.
        self.assertEqual(
            variantgen._opening_shape(OPENS_STATEMENT_CLOSES_QUESTION),
            "statement")

    def test_a_question_opening_that_closes_on_a_statement_reads_as_question(self):
        self.assertEqual(
            variantgen._opening_shape(OPENS_QUESTION_CLOSES_STATEMENT),
            "question")

    def test_opening_and_cta_are_independent_on_a_single_paragraph(self):
        """The property the old implementation could not have had.

        If these two ever agree on all four fixtures again, one of them has
        gone back to reading the other's input.
        """
        pairs = [
            (variantgen._opening_shape(m), variantgen._cta_shape(m))
            for m in (OPENS_STATEMENT_CLOSES_QUESTION,
                      OPENS_QUESTION_CLOSES_QUESTION,
                      OPENS_QUESTION_CLOSES_STATEMENT,
                      OPENS_STATEMENT_CLOSES_STATEMENT)
        ]
        # All four combinations must be reachable; that is only possible if the
        # two functions read different parts of the message.
        self.assertEqual(len(set(pairs)), 4, pairs)

    def test_every_combination_is_reported_exactly_as_written(self):
        expected = {
            OPENS_STATEMENT_CLOSES_QUESTION: ("statement", "question"),
            OPENS_QUESTION_CLOSES_QUESTION: ("question", "question"),
            OPENS_QUESTION_CLOSES_STATEMENT: ("question", "statement"),
            OPENS_STATEMENT_CLOSES_STATEMENT: ("statement", "statement"),
        }
        for message, want in expected.items():
            got = (variantgen._opening_shape(message),
                   variantgen._cta_shape(message))
            self.assertEqual(got, want, message[:48])


class TheDetectorStillHandlesTheEasyShapes(unittest.TestCase):
    """Fixing the paragraph case must not break the multi-line case, which is
    what email looks like and which the old code read correctly."""

    def test_a_multi_line_message_reads_its_first_line_and_its_last(self):
        msg = "How are you handling resourcing today?\n\nHappy to share notes."
        self.assertEqual(variantgen._opening_shape(msg), "question")
        self.assertEqual(variantgen._cta_shape(msg), "statement")

    def test_empty_is_empty_and_not_a_statement(self):
        # "no copy" and "copy that happens not to end in a question mark" are
        # different facts and must not collapse into one.
        self.assertEqual(variantgen._opening_shape(""), "empty")
        self.assertEqual(variantgen._cta_shape(""), "empty")
        self.assertEqual(variantgen._opening_shape("   \n  "), "empty")


if __name__ == "__main__":
    unittest.main()
