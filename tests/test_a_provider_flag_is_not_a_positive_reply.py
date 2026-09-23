"""The provider's counters are not our classifier, and a client was told they were.

## What happened

2026-09-23, 13:28-13:51, in the client channel: the agent reported **three
positive replies**. `replies.classify` over the same period says **zero**.

Nothing lied. The `replies` tool handed the model two true numbers side by
side - `replies_counted_by_provider`, which counts every inbound row, and a
feed of replies our classifier had categorised - and "replies" next to
"positive" is a short walk for a sentence generator.

Two provider signals are involved and neither means what it looks like:

    `replied` counter    every inbound row, autoresponders and bounces too
    `interested` flag    a human clicking a star in the vendor's UI, on rows
                         nobody here ever classified

## What is asserted

That the answer to "how many positive" has exactly one source, that the
source is ours, and that a reply the provider flags but our classifier calls
automated is never counted. The last one is the operator's own test.
"""
import unittest

from src import replies


class OurClassifierIsTheOnlySource(unittest.TestCase):

    def test_an_out_of_office_is_not_positive_however_it_is_flagged(self):
        """The operator's test: provider-flagged, classifier says automated."""
        text = ("Thank you for your message. I am currently out of the "
                "office and will return on 28 September.")
        verdict = replies.classify(text)
        found = verdict.get("classification")
        self.assertNotEqual(found, replies.POSITIVE)
        self.assertTrue(
            replies.is_automated(found),
            f"{found!r} should be automated; a provider `interested` flag on "
            "this row must not be able to make it a positive reply")

    def test_the_non_english_autoresponders_are_not_positive_either(self):
        """All four languages seen in the live feed on 2026-09-22."""
        for text in (
            "Vielen Dank für Ihre Nachricht. Ich bin derzeit nicht im Büro.",
            "Hej, Jeg er til European Agency Awards, til og med torsdag.",
            "Dobry den, z duvodu dovolene poprosim urgentni veci resit s kolegy.",
            "Kedves Levelirо! Ezuton szeretnelek tajekoztatni.",
        ):
            with self.subTest(text=text[:40]):
                found = replies.classify(text).get("classification")
                self.assertNotEqual(found, replies.POSITIVE)

    def test_an_assistant_forwarding_is_not_positive(self):
        """The 0b78fd68 case, pinned here too because it reaches a client."""
        found = replies.classify(
            "I've forwarded your email to our CEO, he'll be in touch if "
            "interested.").get("classification")
        self.assertEqual(found, replies.ASSISTANT_REDIRECT)
        self.assertNotEqual(found, replies.POSITIVE)
        self.assertTrue(replies.is_automated(found))


class TheToolNamesItsSource(unittest.TestCase):
    """The material handed to the model must not be ambiguous."""

    def fields(self):
        import inspect
        from src import slackagenttools
        return inspect.getsource(slackagenttools.replies)

    def test_it_reports_a_positive_count_of_its_own(self):
        self.assertIn("positive_replies_our_classifier", self.fields())

    def test_it_says_where_that_count_came_from(self):
        source = self.fields()
        self.assertIn("positive_count_source", source)
        self.assertIn("replies.classify", source)

    def test_it_says_the_provider_counter_is_not_positive(self):
        """Stated in the material, not only in a comment a model never sees."""
        self.assertIn("provider_counter_is_not_positive", self.fields())


class TheClassifierSaysZeroForThatDay(unittest.TestCase):
    """The specific claim: 'three positive' against our own reading."""

    LIVE_2026_09_22 = (
        "Thanks for reaching out! As I work through my inbox, please know "
        "my response may be delayed.",
        "After 20 years of building the agency, Diane and I have officially "
        "retired.",
        "I'll pass this along to him.",
        "no. stop.",
        "Not interested, please stop contacting me.",
    )

    def test_none_of_the_live_replies_is_positive(self):
        for text in self.LIVE_2026_09_22:
            with self.subTest(text=text[:40]):
                found = replies.classify(text).get("classification")
                self.assertNotEqual(
                    found, replies.POSITIVE,
                    f"{text[:40]!r} classified positive; the client was told "
                    "three of these were")


if __name__ == "__main__":
    unittest.main()
