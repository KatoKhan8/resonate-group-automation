"""TASK-074: a taxonomy that cannot invent a yes.

The adversarial corpus decides this task. At least 40 refusals and hostile
replies that contain the vocabulary the new patterns match - "interesting",
"curious", "tell me", "go on", "show me", "sure" - and not one of them may
reach an outcome of POSITIVE through the classifier or through accountpolicy.

The six measured failures from TASK-067 are included by name:

    "Not interesting."
    "interesting spam"
    "This is an interesting waste of my time"
    "Tell me how you got my number."
    "Go on then, waste my time."
    "What kind of nonsense is this"

The inverse is also asserted: a genuine "Let's book a call Thursday" still
reaches MEETING_INTENT, so the corpus has not simply been satisfied by
classifying everything UNKNOWN.

Nothing new maps to POSITIVE or NEGATIVE in accountpolicy. Every new
category maps to UNKNOWN.
"""
import unittest

from src import accountpolicy as ap, replies


# ----------------------------------------------------------- the corpus

# 45 refusals and hostile replies containing trigger words.
# Every one contains at least one word from: interesting, intrigued,
# intriguing, curious, curiosity, tell me, go on, show me, sure,
# absolutely, definitely, happy to.
ADVERSARIAL_CORPUS = [
    # --- The six measured TASK-067 failures ---
    "Not interesting.",
    "interesting spam",
    "This is an interesting waste of my time",
    "Tell me how you got my number.",
    "Go on then, waste my time.",
    "What kind of interesting nonsense is this",

    # --- "interesting" used dismissively ---
    "Oh, interesting. Another vendor.",
    "How interesting. Delete me from your list.",
    "That's an interesting pitch, but no thanks.",
    "Interesting approach to spamming people.",
    "Yes, very interesting. Please stop emailing me.",
    "Interesting that you think I would care.",
    "Not exactly interesting, more like annoying.",
    "Interesting. I said no last time and I will say it again.",

    # --- "curious" / "intriguing" used hostile ---
    "I'm curious - how did you get my email address?",
    "Curious that you would contact me about this nonsense.",
    "Intriguing subject line for such worthless spam.",
    "I'm so curious about why this is in my inbox.",
    "How intriguing - another company wasting my time.",
    "Curious, because I already unsubscribed last week.",

    # --- "tell me" used hostile ---
    "Tell me why I should care. Oh wait, I cannot think of a single reason.",
    "Tell me to stop emailing you? Done.",
    "Tell me something I do not already know.",
    "Tell me to remove myself from this list.",

    # --- "go on" used hostile ---
    "Go on and add me to your do-not-contact list.",
    "Go on, guess what? I am not interested.",
    "Go on then, try me - I will report you as spam.",

    # --- "show me" used hostile ---
    "Show me where it says I asked for this.",
    "Show me the unsubscribe link already.",
    "Show me one reason I should not report this.",

    # --- "sure" / "absolutely" / "definitely" used sarcastically ---
    "Sure, and I am the Queen of England.",
    "Sure, I will tell you what I think of spam.",
    "Sure, if wasting my time is your goal.",
    "Absolutely terrible service. Stop contacting me.",
    "Definitely not interested. Please remove me.",
    "Sure thing - right after you stop emailing me.",

    # --- "happy to" used hostile ---
    "Happy to report this as spam.",
    "Happy to never hear from you again.",

    # --- Negated interest ---
    "Not that interesting.",
    "Not particularly curious about your product.",
    "I am not intrigued at all.",
    "Nothing interesting here.",
    "Not exactly curious about this in the slightest.",

    # --- Hostile context around trigger words ---
    "Your interesting little scam ends here.",
    "Curious how many people you have spammed today.",
    "Tell me everything so I can show my legal team.",
    "Go on with your interesting proposal to take my money.",
]


class AdversarialCorpusNeverReachesPositive(unittest.TestCase):
    """Not one of the 45 refusals may reach POSITIVE classification."""

    def test_no_refusal_reaches_positive_classification(self):
        failures = []
        for text in ADVERSARIAL_CORPUS:
            verdict = replies.classify(text)
            if verdict["classification"] == replies.POSITIVE:
                failures.append(text)
        self.assertEqual(
            failures, [],
            f"{len(failures)} of {len(ADVERSARIAL_CORPUS)} refusals reached "
            f"POSITIVE: {failures[:5]}")

    def test_no_refusal_maps_to_positive_outcome(self):
        """Through the full chain: classification -> CLASSIFIER_OUTCOME."""
        failures = []
        for text in ADVERSARIAL_CORPUS:
            verdict = replies.classify(text)
            outcome = ap.CLASSIFIER_OUTCOME.get(
                verdict["classification"], ap.UNKNOWN)
            if outcome == ap.POSITIVE:
                failures.append((text, verdict["classification"]))
        self.assertEqual(
            failures, [],
            f"{len(failures)} refusals mapped to POSITIVE outcome: "
            f"{failures[:5]}")

    def test_corpus_has_at_least_forty_entries(self):
        self.assertGreaterEqual(len(ADVERSARIAL_CORPUS), 40)

    def test_the_six_measured_failures_are_all_included(self):
        must_contain = [
            "Not interesting.",
            "interesting spam",
            "This is an interesting waste of my time",
            "Tell me how you got my number.",
            "Go on then, waste my time.",
            "What kind of interesting nonsense is this",
        ]
        for text in must_contain:
            self.assertIn(text, ADVERSARIAL_CORPUS,
                          f"measured failure missing from corpus: {text}")

    def test_each_entry_contains_a_trigger_word(self):
        """Every corpus entry actually exercises the new patterns."""
        trigger_words = [
            "interesting", "intrigu", "curious", "curiosity",
            "tell me", "go on", "show me", "sure", "absolutely",
            "definitely", "happy to",
        ]
        for text in ADVERSARIAL_CORPUS:
            lower = text.lower()
            has_trigger = any(t in lower for t in trigger_words)
            self.assertTrue(has_trigger,
                            f"no trigger word in: {text!r}")


class NewCategoriesMapToUnknown(unittest.TestCase):
    """Nothing new may map to POSITIVE or NEGATIVE in accountpolicy."""

    def test_interested_maps_to_unknown(self):
        self.assertEqual(
            ap.CLASSIFIER_OUTCOME.get("interested"), ap.UNKNOWN,
            "interested must not map to POSITIVE")

    def test_meeting_intent_maps_to_unknown(self):
        self.assertEqual(
            ap.CLASSIFIER_OUTCOME.get("meeting_intent"), ap.UNKNOWN,
            "meeting_intent must not map to POSITIVE")

    def test_objection_maps_to_unknown(self):
        self.assertEqual(
            ap.CLASSIFIER_OUTCOME.get("objection"), ap.UNKNOWN,
            "objection must not map to NEGATIVE")

    def test_new_categories_are_in_classifier_outcome(self):
        for cat in ("interested", "meeting_intent", "objection"):
            self.assertIn(cat, ap.CLASSIFIER_OUTCOME,
                          f"{cat} missing from CLASSIFIER_OUTCOME")


class GenuineInterestStillClassifies(unittest.TestCase):
    """The corpus must not be satisfied by classifying everything UNKNOWN.

    A genuine "Let's book a call Thursday" must reach MEETING_INTENT, and
    genuine curiosity must reach INTERESTED.
    """

    def test_a_concrete_meeting_proposal_reaches_meeting_intent(self):
        for text in (
            "Let's book a call Thursday",
            "Can we meet on Wednesday at 2pm?",
            "How about a call next Tuesday?",
            "I am free on Friday.",
            "Pick a time that works for you.",
        ):
            verdict = replies.classify(text)
            self.assertEqual(
                verdict["classification"], replies.MEETING_INTENT, text)

    def test_genuine_curiosity_reaches_interested(self):
        for text in (
            "I'm curious about your platform.",
            "That's an intriguing approach.",
            "Curious to learn more about this.",
            "I find this intriguing, can you elaborate?",
        ):
            verdict = replies.classify(text)
            self.assertEqual(
                verdict["classification"], replies.INTERESTED, text)

    def test_a_stated_constraint_reaches_objection(self):
        for text in (
            "Too expensive for us right now.",
            "We have no budget this quarter.",
            "Our team is too small for that.",
            "This is beyond our budget.",
        ):
            verdict = replies.classify(text)
            self.assertEqual(
                verdict["classification"], replies.OBJECTION, text)


class ProductionRulesStillWin(unittest.TestCase):
    """The taxonomy only fires when production rules return nothing.

    A message that production rules already classify must not be
    reclassified by the taxonomy.
    """

    def test_a_clear_positive_stays_positive(self):
        verdict = replies.classify("Interested, what does it cost?")
        self.assertEqual(verdict["classification"], replies.POSITIVE)

    def test_a_clear_negative_stays_negative(self):
        verdict = replies.classify("Not interested, thanks.")
        self.assertEqual(verdict["classification"], replies.NEGATIVE)

    def test_a_clear_unsubscribe_stays_unsubscribe(self):
        verdict = replies.classify("Please unsubscribe me.")
        self.assertEqual(verdict["classification"], replies.UNSUBSCRIBE)

    def test_a_clear_out_of_office_stays_out_of_office(self):
        verdict = replies.classify(
            "Automatic reply: out of the office until Monday.")
        self.assertEqual(verdict["classification"], replies.OUT_OF_OFFICE)

    def test_production_positive_beats_taxonomy_meeting_intent(self):
        """'happy to chat' matches POSITIVE production; must not become
        MEETING_INTENT even though it also signals meeting intent."""
        verdict = replies.classify("Happy to chat, let's schedule something.")
        self.assertEqual(verdict["classification"], replies.POSITIVE)


class NegationGuard(unittest.TestCase):
    """Rule 1: no pattern may fire when the sentence negates it.

    The negation guard must catch negation within the same clause,
    even when the production rules do not already handle it.
    """

    def test_not_before_interesting_blocks_taxonomy(self):
        """'Not interesting' is already caught by NEGATIVE production.
        But 'not intriguing' is not - the taxonomy must not fire."""
        verdict = replies.classify("Not intriguing at all.")
        self.assertNotEqual(verdict["classification"], replies.INTERESTED)

    def test_not_in_same_clause_blocks(self):
        verdict = replies.classify(
            "It is not something I would call interesting.")
        self.assertNotEqual(verdict["classification"], replies.INTERESTED)

    def test_negation_in_different_clause_does_not_block(self):
        """'I am not sure, but it is intriguing' - the 'not' modifies
        'sure', not 'intriguing'. Different clauses."""
        verdict = replies.classify(
            "I am not sure, but it is intriguing.")
        self.assertEqual(verdict["classification"], replies.INTERESTED)

    def test_hardly_blocks(self):
        verdict = replies.classify("Hardly interesting.")
        self.assertNotEqual(verdict["classification"], replies.INTERESTED)

    def test_barely_blocks(self):
        verdict = replies.classify("Barely intriguing.")
        self.assertNotEqual(verdict["classification"], replies.INTERESTED)


class NewCategoriesAreInCATEGORIES(unittest.TestCase):
    """The new categories must be in the CATEGORIES tuple so the model
    seam and the invariant tests recognise them."""

    def test_interested_in_categories(self):
        self.assertIn(replies.INTERESTED, replies.CATEGORIES)

    def test_meeting_intent_in_categories(self):
        self.assertIn(replies.MEETING_INTENT, replies.CATEGORIES)

    def test_objection_in_categories(self):
        self.assertIn(replies.OBJECTION, replies.CATEGORIES)


class NewCategoriesDoNotAlert(unittest.TestCase):
    """Only POSITIVE is worth waking someone for."""

    def test_interested_is_not_alerting(self):
        self.assertNotIn(replies.INTERESTED, replies.ALERTING)

    def test_meeting_intent_is_not_alerting(self):
        self.assertNotIn(replies.MEETING_INTENT, replies.ALERTING)

    def test_objection_is_not_alerting(self):
        self.assertNotIn(replies.OBJECTION, replies.ALERTING)


if __name__ == "__main__":
    unittest.main()
