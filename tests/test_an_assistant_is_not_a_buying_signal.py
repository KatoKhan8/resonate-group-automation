r"""Automated is never positive, and an EA redirect is its own thing.

OPERATOR DECISION, Zvonimir Bešlić, 2026-09-22, recorded in
`docs/REPLY-CLASSIFICATION-POLICY-2026-09-22.md`:

> add class "automated" (out-of-office, auto-acknowledgement, ticketing,
> assistant or EA redirect, "thanks for your email" with no content).
> Automated is never positive_reply. Assistant redirects get their own
> class "assistant_redirect": logged as a new contact candidate at that
> account, routed to internal review only. Positive requires intent: a
> question, interest, a meeting ask, a request for more.

## THE REPLY THIS WAS WRITTEN ABOUT

Re-running the classifier over the 26 replies EmailBison recorded on
2026-09-22 found exactly one `positive` in the whole day, and it was an
executive assistant explaining that she manages her principal's inbox. It
matched `POSITIVE_PATTERNS` on the warmth of the prose. Nobody at that
account had expressed any interest in anything.

    BEFORE   positive 1     automated umbrella 7
    AFTER    positive 0     automated umbrella 9

The two named tests below are the operator's. The rest guard the edges the
first implementation of this got wrong.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import accountpolicy                                    # noqa: E402
from src import replies                                          # noqa: E402

#: Today's EA redirect, in shape and tone, with the principal's name
#: replaced. The emoji and the exclamation marks are kept because they are
#: what made the old classifier read it as warmth.
EA_REDIRECT = (
    "Hi there!\n\nThanks so much for your email! [Principal]'s inbox can "
    "get a little extra at times \U0001f605, so I help keep things moving. "
    "I look after her calendar, so anything time-sensitive is best sent "
    "through me.\n\nHappy to help!\n\n[Assistant], Executive Assistant"
)


def verdict(text):
    return replies.classify(text)["classification"]


class TheOperatorsTwoNamedTests(unittest.TestCase):

    def test_an_ea_redirect_is_assistant_redirect_not_positive(self):
        """The operator's first named test, on today's actual reply."""
        self.assertEqual(verdict(EA_REDIRECT), replies.ASSISTANT_REDIRECT)
        self.assertNotEqual(verdict(EA_REDIRECT), replies.POSITIVE)

    def test_an_assistant_redirect_never_reaches_a_positive_outcome(self):
        """And the classification may not become POSITIVE downstream either.

        A class is only never-positive if the outcome map agrees. This is
        the half a pattern test cannot cover.
        """
        for category in (replies.ASSISTANT_REDIRECT, replies.AUTOMATED,
                         replies.OUT_OF_OFFICE):
            outcome = accountpolicy.CLASSIFIER_OUTCOME[category]
            self.assertNotEqual(outcome, accountpolicy.POSITIVE, category)


class AutomatedIsNeverPositive(unittest.TestCase):

    def test_the_umbrella_names_all_three(self):
        for category in (replies.OUT_OF_OFFICE, replies.AUTOMATED,
                         replies.ASSISTANT_REDIRECT):
            self.assertTrue(replies.is_automated(category), category)

    def test_a_human_classification_is_not_automated(self):
        for category in (replies.POSITIVE, replies.NEGATIVE, replies.NEUTRAL,
                         replies.REFERRAL, replies.NOT_NOW, replies.UNKNOWN,
                         replies.NOT_RELEVANT):
            self.assertFalse(replies.is_automated(category), category)

    def test_a_ticketing_acknowledgement_is_automated(self):
        """The second reply today's re-run moved, `unknown` -> `automated`."""
        self.assertEqual(verdict(
            "Hello,\n\nYour request has been received and is being reviewed "
            "by our support team. Someone will be in touch within 2 business "
            "days.\n\nTicket #48213"), replies.AUTOMATED)

    def test_a_bare_thanks_with_no_content_is_automated(self):
        for text in ("Thanks for your email!",
                     "Thank you for your message.",
                     "Received, thanks.",
                     "Noted, thank you."):
            self.assertEqual(verdict(text), replies.AUTOMATED, text)

    def test_a_thanks_that_carries_a_question_is_not_automated(self):
        """"With no content" is the whole of the rule. A person who thanks
        you and then asks something has asked something."""
        self.assertNotEqual(
            verdict("Thanks for your email! What does it cost?"),
            replies.AUTOMATED)

    def test_a_do_not_reply_autoresponder_is_automated(self):
        self.assertEqual(verdict(
            "This is an automated response. Please do not reply to this "
            "message."), replies.AUTOMATED)


class ARefusalIsNeverSoftenedByTheNewClasses(unittest.TestCase):
    """THE BUG THE FIRST IMPLEMENTATION HAD, kept as a test.

    The bare-acknowledgement check was first placed before the rule table.
    "No, thank you.", "Not for me, thanks." and "No interest, thanks." are
    all short, carry no intent and end in a thanks, so every one of them
    became `automated` - a classification softening a refusal, which this
    module's own docstring forbids. Three existing tests caught it; these
    keep it caught.
    """

    def test_a_short_refusal_ending_in_thanks_stays_a_refusal(self):
        for text in ("No, thank you.", "Not for me, thanks.",
                     "No interest, thanks.", "No thanks!"):
            self.assertIn(verdict(text),
                          (replies.NEGATIVE, replies.NOT_NOW), text)

    def test_an_unsubscribe_outranks_everything_new(self):
        self.assertEqual(
            verdict("Please remove me from your list. Thanks for your email."),
            replies.UNSUBSCRIBE)

    def test_an_assistant_who_refuses_is_a_refusal(self):
        """"Not interested - I'm his assistant" is a refusal that happens
        to be written by an assistant."""
        self.assertEqual(
            verdict("Not interested. I'm his executive assistant and he "
                    "isn't looking at anything like this."),
            replies.NEGATIVE)

    def test_a_person_who_has_left_still_reads_as_not_relevant(self):
        self.assertEqual(
            verdict("Thank you for reaching out. Please note that [Person] "
                    "is no longer with the company."),
            replies.NOT_RELEVANT)


class PositiveRequiresIntent(unittest.TestCase):

    def test_a_bare_calendar_mention_is_not_positive(self):
        """The EA phrasing, reduced to the pattern that carried it."""
        self.assertNotEqual(verdict("I look after her calendar."),
                            replies.POSITIVE)

    def test_a_bare_pricing_mention_is_not_positive(self):
        self.assertNotEqual(
            verdict("Our pricing team handles that sort of thing."),
            replies.POSITIVE)

    def test_a_weak_pattern_with_a_question_is_positive(self):
        """Corroborated by intent, the same word is a real signal."""
        self.assertEqual(verdict("What is your pricing?"), replies.POSITIVE)

    def test_a_weak_pattern_with_a_meeting_ask_is_positive(self):
        self.assertEqual(
            verdict("Send me your availability and let's talk."),
            replies.POSITIVE)

    def test_the_gate_applies_only_to_the_bare_nouns(self):
        """THE OTHER HALF OF THE FIRST IMPLEMENTATION'S BUG.

        Applying the intent gate to every positive pattern dropped "Yes
        please", "Show me" and "Sure, happy to discuss" to `unknown`. A
        false negative on a real buying signal costs a meeting, so the gate
        is narrow by construction and this asserts the narrowness.
        """
        for text in ("Yes please.", "Show me", "Sure, happy to discuss.",
                     "Send the info.", "I'm interested."):
            self.assertNotEqual(verdict(text), replies.UNKNOWN, text)

    def test_every_weak_pattern_is_a_real_positive_pattern(self):
        """A typo in the weak list would silently gate nothing."""
        for pattern in replies.WEAK_POSITIVE_PATTERNS:
            self.assertIn(pattern, replies.POSITIVE_PATTERNS, pattern)
        self.assertEqual(
            len(replies.STRONG_POSITIVE_PATTERNS)
            + len(replies.WEAK_POSITIVE_PATTERNS),
            len(replies.POSITIVE_PATTERNS))


class TheNewClassesAreWiredEverywhereTheOldOnesAre(unittest.TestCase):

    def test_both_are_recognised_categories(self):
        for category in (replies.AUTOMATED, replies.ASSISTANT_REDIRECT):
            self.assertIn(category, replies.CATEGORIES, category)

    def test_both_have_an_outcome(self):
        """An unmapped classification reads as UNKNOWN by accident rather
        than by decision, and the two are impossible to tell apart later."""
        for category in (replies.AUTOMATED, replies.ASSISTANT_REDIRECT):
            self.assertIn(category, accountpolicy.CLASSIFIER_OUTCOME, category)

    def test_neither_alerts(self):
        """`ALERTING` is what wakes somebody up. Neither of these is worth
        it, which is the point of classifying them apart."""
        self.assertNotIn(replies.AUTOMATED, replies.ALERTING)
        self.assertNotIn(replies.ASSISTANT_REDIRECT, replies.ALERTING)

    def test_an_assistant_redirect_goes_to_review_not_to_referral(self):
        """The operator's words are "internal review only". REFERRAL was
        the tempting mapping and it carries a policy some workspace may set
        to keep contacting; a new class may not inherit a permission nobody
        granted it."""
        self.assertEqual(
            accountpolicy.CLASSIFIER_OUTCOME[replies.ASSISTANT_REDIRECT],
            accountpolicy.UNKNOWN)


class AClientChannelNeverReceivesAnInternalCampaignName(unittest.TestCase):
    """The operator's second named test, 2026-09-22.

    It is written now, before the thing it will guard exists. Item 2 of the
    decision - routing a positive reply into the client channel as
    "company, contact role, one-line quote, which of their senders received
    it, suggested next step" - is explicitly gated on item 1 being live and
    tested, so it is NOT built in this increment.

    The property it depends on is built, and locking it first is the
    cheaper order: when the renderer lands it inherits a test that already
    says what it may not do.
    """

    #: The shape of this estate's live campaign names, with the sender's
    #: own name replaced. The operator's instruction is that a client hears
    #: "<sender>, US cohort" and never this.
    INTERNAL_NAMES = (
        "BATCH1 - SENDERNAME",
        "RESONATE - CLIENT - EMAIL - US-HOURS - CONTROL - COHORT B",
        "RESONATE PRODUCTIVE LI B1 SEAT 174845",
    )

    def test_the_client_label_carries_none_of_the_internal_name(self):
        from src import slackclientview as clientview
        for name in self.INTERNAL_NAMES:
            label = clientview.plain_campaign_label(name, "491")
            for word in ("BATCH1", "CONTROL", "COHORT", "SEAT", "RESONATE",
                         "US-HOURS", "SENDERNAME"):
                self.assertNotIn(word, label.upper(),
                                 "%r survived into %r" % (word, label))

    def test_the_label_still_says_the_useful_part(self):
        """Stripping is not the goal; a client still has to know which
        campaign is meant and on which channel."""
        from src import slackclientview as clientview
        self.assertIn("491", clientview.plain_campaign_label(
            "BATCH1 - SENDERNAME", "491"))
        self.assertIn("LinkedIn", clientview.plain_campaign_label(
            "RESONATE PRODUCTIVE LI B1 SEAT 174845", "613761"))

    def test_an_internal_name_is_recognised_as_internal(self):
        """The detector the renderer will call. A name it fails to flag is
        a name that reaches a client."""
        from src import slackclientview as clientview
        for name in self.INTERNAL_NAMES:
            self.assertTrue(clientview.carries_internal_label(name), name)

    def test_a_persons_name_is_never_mistaken_for_a_campaign(self):
        """THE REGRESSION THIS FIX FIRST CAUSED, kept as a test.

        `slackagenttools._plain_labels` rewrites ANY dict key called
        `name` that `carries_internal_label` flags - a sender's as readily
        as a campaign's. Adding the bare word `seat` to the word list to
        catch `... SEAT 174845` therefore renamed a client's own sender,
        whose name carries "seat-holder", to "email campaign". A client
        seeing their own sender named is the rule increment 2 established.

        The leak is the seat ID's SHAPE, not the word, and this asserts
        the difference in both directions.
        """
        from src import slackclientview as clientview
        for person in ("Kresimir <seat-holder-b>", "Seat Holder",
                       "Resonate Ops", "Ana Seaton"):
            self.assertFalse(clientview.carries_internal_label(person),
                             "%r was mistaken for an internal label" % person)
        self.assertTrue(clientview.carries_internal_label(
            "RESONATE PRODUCTIVE LI B1 SEAT 174845"))


if __name__ == "__main__":
    unittest.main()
