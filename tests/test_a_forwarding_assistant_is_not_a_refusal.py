"""A secretary forwarding your email is not a buyer and not a refusal.

## The measurement that produced this file

`assistant_redirect` already existed, with patterns, with precedence above
POSITIVE, and inside `AUTOMATED_CATEGORIES`. It was asked to verify rather
than invert, and verifying is what found the hole: **every existing pattern
requires the writer to identify as an assistant** ("I'm the EA to..."). Most
of them never do. They just forward.

Measured 2026-09-23, before the fix:

    "I'll pass this along to him."            negative            0.80
    "Forwarded to our CEO."                   unclassified
    "I've forwarded your email to our CEO,
     he'll be in touch if interested."        POSITIVE            0.75
    "Thanks, I'll pass this along to the
     right person."                           negative            0.80
    "I have passed this on to our Head
     of Marketing."                           unclassified

Three different wrong answers for one reply shape. **The POSITIVE is the one
that mattered**: it fires the first-human-reply client trigger, so a secretary
forwarding an email would have told the client they had a buying signal.

## The root cause was in NEGATIVE, not in ASSISTANT_REDIRECT

`NEGATIVE_PATTERNS` carried a bare `\\bpass\\b`. NEGATIVE outranks
ASSISTANT_REDIRECT deliberately - a refusal written by an assistant is still a
refusal - so the broad pattern won every time and the redirect never got a
chance. Adding forwarding patterns alone would have fixed nothing.

The distinction is word order and nothing else:

    "I'll pass this on"     forward
    "I'll pass on this"     decline

Both halves are pinned below, because narrowing a stop-word is exactly the
kind of change that quietly stops catching refusals.
"""
import unittest

from src import replies


def verdict(text):
    found = replies.classify_rules(text)
    return found.get("classification") if isinstance(found, dict) else found


FORWARDING = (
    "I'll pass this along to him.",
    "Forwarded to our CEO.",
    "I've forwarded your email to our CEO, he'll be in touch if interested.",
    "Thanks, I'll pass this along to the right person.",
    "I have passed this on to our Head of Marketing.",
    "I'll forward this on to our finance lead.",
    "Passing this along to the person who owns it.",
)

DECLINING = (
    "I'll pass, thanks.",
    "We'll pass on this one.",
    "I'll pass for now.",
    "Not a good fit for us, we'll pass.",
)


class TheForwardingAssistantIsARedirect(unittest.TestCase):

    def test_every_forwarding_shape_is_assistant_redirect(self):
        for text in FORWARDING:
            with self.subTest(text=text):
                self.assertEqual(verdict(text), replies.ASSISTANT_REDIRECT)

    def test_none_of_them_is_positive(self):
        """The operator's rule: this must never fire the client trigger."""
        for text in FORWARDING:
            with self.subTest(text=text):
                self.assertNotEqual(verdict(text), replies.POSITIVE)

    def test_none_of_them_is_negative(self):
        """A forward is not a refusal, and stopping the account would be wrong."""
        for text in FORWARDING:
            with self.subTest(text=text):
                self.assertNotEqual(verdict(text), replies.NEGATIVE)


class NarrowingPassDidNotLoseTheRefusal(unittest.TestCase):
    """The half that is easy to break and hard to notice."""

    def test_the_decline_sense_still_stops(self):
        for text in DECLINING:
            with self.subTest(text=text):
                self.assertIn(verdict(text),
                              (replies.NEGATIVE, replies.UNSUBSCRIBE,
                               replies.NOT_RELEVANT))

    def test_pass_on_this_is_a_decline_and_pass_this_on_is_not(self):
        """One word of order, two opposite outcomes. Both asserted."""
        self.assertEqual(verdict("I'll pass on this."), replies.NEGATIVE)
        self.assertEqual(verdict("I'll pass this on."),
                         replies.ASSISTANT_REDIRECT)

    def test_an_explicit_refusal_from_an_assistant_stays_a_refusal(self):
        """NEGATIVE outranks ASSISTANT_REDIRECT, and that ordering stands."""
        text = "I'm his assistant, and he's not interested."
        self.assertEqual(verdict(text), replies.NEGATIVE)


class ItCannotReachTheClientTrigger(unittest.TestCase):

    def test_assistant_redirect_counts_as_automated(self):
        """`is_automated` is what the client-trigger gate reads."""
        self.assertIn(replies.ASSISTANT_REDIRECT, replies.AUTOMATED_CATEGORIES)
        self.assertTrue(replies.is_automated(replies.ASSISTANT_REDIRECT))

    def test_it_is_not_in_the_positive_family(self):
        self.assertNotEqual(replies.ASSISTANT_REDIRECT, replies.POSITIVE)


if __name__ == "__main__":
    unittest.main()
