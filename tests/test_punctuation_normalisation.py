"""TASK-055: punctuation normalisation before lint.

A character substitution that changes no word is not a content failure and
must not spend an attempt. The model is told plainly to use ASCII punctuation
and sometimes ignores it; normalising before lint means the draft never fails
on encoding, and the full attempt budget stays available for actual content
issues.

No live model is called. Every model here is scripted.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import generate, lint, llm, store
from tests.base import FIXTURES, pin_client_config


GOOD_NOTE = ("hi Ivana, i work with finance leads at agencies running several "
             "offices, usually around how long the numbers take to settle. "
             "curious how you handle it. happy to connect.")


class TestNormalisePunctuation(unittest.TestCase):
    """The normalise_punctuation function itself."""

    def test_em_dash_becomes_space_hyphen_space(self):
        self.assertEqual(lint.normalise_punctuation("word—word"), "word - word")

    def test_en_dash_becomes_hyphen(self):
        self.assertEqual(lint.normalise_punctuation("word–word"), "word-word")

    def test_non_breaking_hyphen_becomes_hyphen(self):
        self.assertEqual(lint.normalise_punctuation("month‑end"), "month-end")

    def test_curly_apostrophe_becomes_straight(self):
        self.assertEqual(lint.normalise_punctuation("you're"), "you're")
        self.assertEqual(lint.normalise_punctuation("'hello'"), "'hello'")

    def test_no_change_returns_original(self):
        text = "plain ASCII text"
        self.assertIs(lint.normalise_punctuation(text), text)

    def test_empty_string(self):
        self.assertEqual(lint.normalise_punctuation(""), "")

    def test_none(self):
        self.assertIsNone(lint.normalise_punctuation(None))

    def test_multiple_substitutions(self):
        text = "you're—ready? let's go–fast"
        expected = "you're - ready? let's go-fast"
        self.assertEqual(lint.normalise_punctuation(text), expected)

    def test_accented_letters_are_untouched(self):
        # The rule is about typography you substitute, not the alphabet a
        # name is written in. Müller and straße must pass unchanged.
        text = "Müllerstraße"
        self.assertEqual(lint.normalise_punctuation(text), text)


class TestDraftNormalisesPunctuation(unittest.TestCase):
    """A draft whose only defect is punctuation is normalised and stored."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-punct-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = pin_client_config(self, linkedin_connection_note=None)
        generate.reset_model_calls()

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)
        generate.reset_model_calls()

    def _rec(self, rid="harbourline"):
        return store.get(rid)

    def test_an_em_dash_is_normalised_and_the_draft_stored(self):
        """A model whose first answer carries an em dash: assert what gets
        stored, that the stored text contains no SUBSTITUTED_PUNCTUATION
        character, and that the draft was stored on the FIRST attempt
        (not after regeneration)."""
        bad_subject = "the question—we never answered"
        bad_body = ("Rowan, on 17 October Jesse asked to run the key against "
                    "a realistic list of companies—and our reply asked whether "
                    "five thousand credits would do and then pivoted to booking "
                    "a call. That question was never actually answered, which "
                    "is the reason this stopped rather than anything about the "
                    "price.\n\nThe limit on that test key was around fifty "
                    "credits, far too low to test anything real, and we never "
                    "engaged the developer Jesse mentioned had the docs.\n\nIf "
                    "I raise a key with a proper limit and no call attached, is "
                    "the realistic list still the thing you would want to run?")
        # Call draft() directly with a scripted model that returns the bad draft
        # Provide multiple answers in case of regeneration for other reasons
        model = llm.ScriptedModel(
            json.dumps({"subject": bad_subject, "body": bad_body}),
            json.dumps({"subject": bad_subject, "body": bad_body}),
            json.dumps({"subject": bad_subject, "body": bad_body}))
        with store.transaction() as recs:
            rec = store.get("harbourline", recs)
            contact = [c for c in rec["contacts"]
                       if c.get("name") == "Rowan Blake"][0]
            result = generate.draft(rec, contact, "day1", model, self.config)
        # The draft was stored (not None)
        self.assertIsNotNone(result)
        # The stored text contains no SUBSTITUTED_PUNCTUATION character
        for c in lint.SUBSTITUTED_PUNCTUATION:
            self.assertNotIn(c, result["subject"])
            self.assertNotIn(c, result["body"])
        # The em dash was replaced with " - "
        self.assertIn(" - ", result["body"])

    def test_a_curly_apostrophe_is_normalised(self):
        """A curly apostrophe in the subject is normalised."""
        bad_subject = "the question—we never answered"
        good_body = ("Rowan, on 17 October Jesse asked to run the key against "
                     "a realistic list of companies and our reply asked whether "
                     "five thousand credits would do and then pivoted to booking "
                     "a call. That question was never actually answered, which "
                     "is the reason this stopped rather than anything about the "
                     "price.\n\nThe limit on that test key was around fifty "
                     "credits, far too low to test anything real, and we never "
                     "engaged the developer Jesse mentioned had the docs.\n\nIf "
                     "I raise a key with a proper limit and no call attached, is "
                     "the realistic list still the thing you would want to run?")
        model = llm.ScriptedModel(
            json.dumps({"subject": bad_subject, "body": good_body}),
            json.dumps({"subject": bad_subject, "body": good_body}),
            json.dumps({"subject": bad_subject, "body": good_body}))
        with store.transaction() as recs:
            rec = store.get("harbourline", recs)
            contact = [c for c in rec["contacts"]
                       if c.get("name") == "Rowan Blake"][0]
            result = generate.draft(rec, contact, "day1", model, self.config)
        self.assertIsNotNone(result)
        # The subject had an em dash which was normalised
        self.assertNotIn("—", result["subject"])
        self.assertIn(" - ", result["subject"])


class TestLinkedInNoteNormalisesPunctuation(unittest.TestCase):
    """A LinkedIn note whose only defect is punctuation is normalised."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-punct-li-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = pin_client_config(self, linkedin_connection_note=None)
        generate.reset_model_calls()

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)
        generate.reset_model_calls()

    def _rec(self, rid="meridian"):
        return store.get(rid)

    def write(self, *answers):
        model = llm.ScriptedModel(*[json.dumps({"note": a}) for a in answers])
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            return generate.linkedin_note(rec, rec["contacts"][0], model,
                                          self.config)

    def test_an_em_dash_is_normalised_and_the_note_stored(self):
        """A note with an em dash is normalised and stored on the first
        attempt, not regenerated."""
        bad_note = ("hi Ivana, i work with finance leads at agencies running "
                    "several offices—curious how you handle it. happy to "
                    "connect.")
        step = self.write(bad_note)
        self.assertIsNotNone(step)
        # The stored note contains no SUBSTITUTED_PUNCTUATION character
        for c in lint.SUBSTITUTED_PUNCTUATION:
            self.assertNotIn(c, step["note"])
        # The em dash was replaced with " - "
        self.assertIn(" - ", step["note"])

    def test_a_note_with_only_punctuation_issues_does_not_waste_attempts(self):
        """When the only defect is punctuation, the note is stored on the
        first attempt. The model does not get a second chance because there
        was no failure."""
        bad_note = ("hi Ivana, i work with finance leads at agencies running "
                    "several offices—curious how you handle it. happy to "
                    "connect.")
        # Only ONE answer is provided. If the normalisation works, the note
        # is stored on the first attempt and no second answer is needed.
        model = llm.ScriptedModel(json.dumps({"note": bad_note}))
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            step = generate.linkedin_note(rec, rec["contacts"][0], model,
                                          self.config)
        self.assertIsNotNone(step)
        # The model was called exactly once (no regeneration)
        self.assertEqual(len(model.prompts), 1)
        # No retry prompt was generated
        self.assertFalse(any("previous note was refused" in p
                             for p in model.prompts))


if __name__ == '__main__':
    unittest.main()


class TheCodepointsThemselves(unittest.TestCase):
    """A test that reads the characters as NUMBERS, because eyes cannot.

    On 2026-09-14 the change that added `normalise_punctuation` silently
    rewrote both curly apostrophes in `SUBSTITUTED_PUNCTUATION` as straight
    ones (U+0027) somewhere between being written and being committed. The
    tuple still looked right in a diff. The rule then refused every ordinary
    contraction - "don't", "it's" - and stopped catching the character it
    names, and thirteen new tests passed anyway because they used the same
    mangled constant to build their fixtures.

    So this asserts the codepoints, not the appearance, and it builds its
    inputs from escapes rather than from the constant under test.
    """

    EM = "\u2014"
    EN = "\u2013"
    NB_HYPHEN = "\u2011"
    RIGHT_QUOTE = "\u2019"
    LEFT_QUOTE = "\u2018"

    def test_the_rule_names_exactly_these_five_codepoints(self):
        self.assertEqual(
            tuple(lint.SUBSTITUTED_PUNCTUATION),
            (self.EM, self.EN, self.NB_HYPHEN, self.RIGHT_QUOTE, self.LEFT_QUOTE))

    def test_no_ascii_character_is_in_the_rule(self):
        # The failure mode exactly: a straight apostrophe in this tuple makes
        # lint refuse "don't".
        for char in lint.SUBSTITUTED_PUNCTUATION:
            with self.subTest(char=hex(ord(char))):
                self.assertGreater(ord(char), 127)

    def test_the_map_covers_the_rule_and_nothing_else(self):
        self.assertEqual(sorted(lint._PUNCTUATION_MAP),
                         sorted(lint.SUBSTITUTED_PUNCTUATION))

    def test_every_replacement_is_plain_ascii(self):
        for bad, good in lint._PUNCTUATION_MAP.items():
            with self.subTest(char=hex(ord(bad))):
                self.assertTrue(all(ord(c) < 128 for c in good))

    def test_an_ordinary_contraction_is_untouched(self):
        for word in ("don't", "it's", "we'll", "O'Brien"):
            with self.subTest(word=word):
                self.assertEqual(lint.normalise_punctuation(word), word)

    def test_an_accented_name_is_untouched(self):
        # The rule is about typography somebody substituted, not about the
        # alphabet a name is written in.
        for name in ("Ćuk Šimić", "Müller", "梁伟", "Faertz"):
            with self.subTest(name=name):
                self.assertEqual(lint.normalise_punctuation(name), name)
