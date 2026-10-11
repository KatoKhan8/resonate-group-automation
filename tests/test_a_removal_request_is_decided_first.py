"""A removal request is decided first, and neither pattern set can be lost.

THREE FAULTS, ONE FILE, ALL THREE MEASURED OVER THE 559 REAL INBOUND
REPLIES IN THE EMAILBISON FEED ON 2026-10-12.

1. TWO BARE-PATTERN SETS THAT ARE NOT NESTED.
   `task-reply-classification-clean` (36445185) grew its own version of
   `BARE_REMOVAL_LINE_PATTERNS` from the same corpus, one commit off a
   merge-base 80 commits behind master. Measured against the 559 rows it
   fixed 13 replies master got wrong AND BROKE 7 MASTER GETS RIGHT - every
   bare one-word case, because it carried `^unsubscribe$` without
   `^unsub$` and had dropped `^remove$` entirely.

   Merging it would also have deleted 7,385 lines, including four whole
   test files. So its source changes were ported onto master's file
   instead, and the bare set is the STRICT UNION of both: seven from
   master, four from the branch, nothing lost in either direction. These
   tests count the union and name every member, so a future edit that
   drops either side fails here rather than on the live estate.

2. A REMOVAL PHRASE WITH WORDS AROUND IT WAS INVISIBLE.
   Eleven of the 559 carried unmistakable removal language and came back
   `unknown 0.0` with empty evidence, because every pattern that could
   have read them needed the line to be EXACTLY the phrase. All eleven are
   named below in the words they were written in. Two of them are the same
   person replying twice; one arrived with "Sent from my iPhone" under it.
   None was on any suppression list.

3. A REMOVAL SIGNAL WAS RANKED, NOT DECIDED.
   `RULES` already put UNSUBSCRIBE and ACCOUNT_DNC above POSITIVE, and a
   priority table only decides between the categories that MATCHED. A
   removal request written in the plural matched nothing at all, so
   "could you remove us from your distribution list? Not something we are
   interested in" was announced to the client as `positive 0.75` on the
   evidence `interested`. `replies.removal_request` now settles a removal
   before any other reading is attempted, so the precedence is a property
   of the control flow rather than of a table somebody might reorder.

NO EMAIL ADDRESS FROM THE LIVE FEED APPEARS HERE. Every phrase below is
the human's own wording with any address or company name replaced; the
fixture itself is never copied into this file.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import replies                                        # noqa: E402

REMOVAL = (replies.UNSUBSCRIBE, replies.ACCOUNT_DNC)

#: The eleven rows of fault 2, as their authors wrote them.
THE_ELEVEN = (
    "Remove from your list.",
    "Remove my email now",
    "Please remove from all mailing lists.",
    "remove from list\n\nSent from my iPhone",
    "You can remove us from this list!",
    "please remove us from your list",
    "Hi,\n\nThis company has been closed permanently, so please remove us "
    "from all the mailing lists.",
    "No remove from list",
    "Wrong company. Please remove.",
    "No thx, plse remove…",
    "No thx please remove.",
)

#: Every bare one-word form. The first five are the seven rows the branch
#: broke; the rest are master's own and the branch's four additions.
THE_BARE_FORMS = (
    "remove", "Remove", "REMOVE",
    "unsub", "Unsub", "UNSUB",
    "unsubscribe", "Unsubscribe", "UNSUBSCRIBE",
    "stop", "Stop", "STOP", "stop.", "Stop!",
    "remove me", "Remove us",
    "take me off", "Take us off",
    "opt out", "Opt-out", "opt - out",
    "dnc", "DNC",
    "stop please", "Stop please",
    "please stop", "Please stop",
    "do not contact", "Do not contact",
    "no contact", "No contact",
)


def verdict_for(text):
    return replies.classify(text, model=None)


class TheBarePatternSetsAreAUnion(unittest.TestCase):
    """Fault 1. Counted and named, so neither side can be dropped again."""

    MASTER_SEVEN = (
        r"^remove[\s.!]*$",
        r"^remove\s+(?:me|us)[\s.!]*$",
        r"^take\s+(?:me|us)\s+off[\s.!]*$",
        r"^stop[\s.!]*$",
        r"^unsub(?:scribe)?[\s.!]*$",
        r"^opt\s*-?\s*out[\s.!]*$",
        r"^dnc[\s.!]*$",
    )
    BRANCH_FOUR = (
        r"^stop\s+please[\s.!]*$",
        r"^please\s+stop[\s.!]*$",
        r"^do\s+not\s+contact[\s.!]*$",
        r"^no\s+contact[\s.!]*$",
    )

    def test_the_union_has_eleven_patterns(self):
        self.assertEqual(len(replies.BARE_REMOVAL_LINE_PATTERNS), 11)

    def test_every_pattern_master_had_is_still_there(self):
        for pattern in self.MASTER_SEVEN:
            self.assertIn(pattern, replies.BARE_REMOVAL_LINE_PATTERNS,
                          "master's bare pattern was dropped: %r" % pattern)

    def test_every_pattern_the_branch_added_is_there(self):
        for pattern in self.BRANCH_FOUR:
            self.assertIn(pattern, replies.BARE_REMOVAL_LINE_PATTERNS,
                          "the branch's bare pattern is missing: %r" % pattern)

    def test_the_union_is_exactly_those_eleven_and_nothing_else(self):
        self.assertEqual(set(replies.BARE_REMOVAL_LINE_PATTERNS),
                         set(self.MASTER_SEVEN) | set(self.BRANCH_FOUR))

    def test_the_abbreviation_is_covered_as_well_as_the_whole_word(self):
        """`^unsub$` is the pattern the branch lost. Both forms, one regex."""
        import re
        pattern = r"^unsub(?:scribe)?[\s.!]*$"
        self.assertIn(pattern, replies.BARE_REMOVAL_LINE_PATTERNS)
        self.assertTrue(re.match(pattern, "unsub", re.I))
        self.assertTrue(re.match(pattern, "unsubscribe", re.I))


class EveryBareOneWordFormIsStillARemoval(unittest.TestCase):
    """Fault 1, read through `classify` rather than through the tuple.

    The seven regressions the branch introduced were all of this shape, and
    a reply whose entire content is one of these words is the least
    ambiguous message in the corpus - 45 of the 559 are exactly this.
    """

    def test_the_bare_word_alone(self):
        for word in THE_BARE_FORMS:
            with self.subTest(word=word):
                v = verdict_for(word)
                self.assertIn(v["classification"], REMOVAL,
                              "%r was read as %s" % (word,
                                                     v["classification"]))
                self.assertGreaterEqual(v["confidence"], 0.95)

    def test_the_bare_word_over_a_signature_block(self):
        """`normalise` collapses newlines, so the whole-message anchor
        cannot see a one-word reply once a signature follows it. The first
        CONTENT LINE is tested separately, which is what reaches these.
        """
        signature = ("\n\nKind regards\n\nA Person\nHead of Something\n"
                     "Some Company Ltd\n+44 000 000 0000\n"
                     "www.example.invalid\n")
        for word in THE_BARE_FORMS:
            with self.subTest(word=word):
                v = verdict_for(word + signature)
                self.assertIn(v["classification"], REMOVAL,
                              "%r over a signature was read as %s"
                              % (word, v["classification"]))

    def test_the_same_words_inside_a_sentence_are_not_a_removal(self):
        """The whole-line anchor is the only guard and it has to hold.

        This is the distinction that got the old bare `\\bstop\\b` removed:
        a sharp question is a refusal, not a request for removal, and an
        unsubscribe suppresses globally and for good.
        """
        for text in ("Stop guessing, what does it cost?",
                     "please stop asking and send me a price",
                     "Can you remove the second option from the proposal?"):
            with self.subTest(text=text):
                v = verdict_for(text)
                self.assertNotIn(v["classification"], REMOVAL,
                                 "%r was escalated to %s"
                                 % (text, v["classification"]))


class TheElevenWithWordsAroundThePhrase(unittest.TestCase):
    """Fault 2. Each of these was `unknown 0.0` with empty evidence."""

    def test_every_one_of_the_eleven_is_a_removal(self):
        for text in THE_ELEVEN:
            with self.subTest(text=text.split("\n")[0]):
                v = verdict_for(text)
                self.assertIn(v["classification"], REMOVAL,
                              "%r was read as %s %.2f"
                              % (text, v["classification"], v["confidence"]))
                self.assertTrue(v["evidence"],
                                "a removal verdict with no evidence: %r"
                                % (text,))

    def test_the_implied_object(self):
        """"remove from list" - no pronoun, no determiner, still a request."""
        v = verdict_for("remove from list\n\nSent from my iPhone")
        self.assertIn(v["classification"], REMOVAL)

    def test_the_qualified_list(self):
        """"all mailing lists" put two words between the preposition and
        the noun, which `\\s+` could not reach across."""
        v = verdict_for("Please remove from all mailing lists.")
        self.assertIn(v["classification"], REMOVAL)

    def test_the_contact_detail_named_instead_of_the_person(self):
        v = verdict_for("Remove my email now")
        self.assertIn(v["classification"], REMOVAL)

    def test_the_polite_bare_imperative_at_a_clause_end(self):
        """Two sentences, and the request is the second one."""
        for text in ("Wrong company. Please remove.",
                     "No thx please remove.",
                     "No thx, plse remove…"):
            with self.subTest(text=text):
                self.assertIn(verdict_for(text)["classification"], REMOVAL)

    def test_a_typo_is_not_an_ambiguity(self):
        """One live row spells it `plse`."""
        self.assertIn(verdict_for("No thx, plse remove.")["classification"],
                      REMOVAL)

    def test_the_company_named_in_parentheses(self):
        """The aside sat between the pronoun and the preposition, so the
        whole sentence read `negative` on "not interested" instead."""
        v = verdict_for("Sorry, but we are not interested. Please remove us "
                        "(Some Company) from your contact list")
        self.assertIn(v["classification"], REMOVAL)
        self.assertNotIn("Some Company", " ".join(v["evidence"]),
                         "the aside leaked into the evidence")


class ARemovalSignalIsDecidedNotRanked(unittest.TestCase):
    """Fault 3. The warm word in the same sentence must not win."""

    def test_the_row_that_was_announced_as_a_buying_signal(self):
        v = verdict_for("could you remove us from your distribution list? "
                        "Not something we are interested in.")
        self.assertIn(v["classification"], REMOVAL,
                      "a removal request came back as %s"
                      % v["classification"])
        self.assertNotEqual(v["classification"], replies.POSITIVE)

    def test_a_refusal_carrying_an_erasure_demand_is_a_removal(self):
        """Two live rows, the same person twice. `negative` is the softer
        reading and softening a stop is the one thing this module may not
        do."""
        v = verdict_for("not interested please delete my data and dont "
                        "email me again")
        self.assertIn(v["classification"], REMOVAL)

    def test_removal_request_is_callable_on_its_own(self):
        """The decision is a function, not a position in a table."""
        self.assertIsNone(replies.removal_request(""))
        self.assertIsNone(replies.removal_request("sounds great, Thursday?"))
        found = replies.removal_request("please remove us from your list")
        self.assertIsNotNone(found)
        self.assertTrue(found["removal_request"])
        self.assertEqual(found["confidence"], 0.95)

    def test_a_company_wide_stop_still_outranks_a_personal_one(self):
        """ACCOUNT_DNC is tested before UNSUBSCRIBE inside the decision,
        which is the ordering TASK-939 argued for: reading "remove us" as
        "remove me" leaves colleagues contactable."""
        v = verdict_for("Please remove our whole company and do not contact "
                        "anyone here again.")
        self.assertEqual(v["classification"], replies.ACCOUNT_DNC)

    def test_classify_rules_decides_it_before_the_table(self):
        v = replies.classify_rules("remove us from your mailing list, "
                                   "this sounds interesting though")
        self.assertIn(v["classification"], REMOVAL)
        self.assertTrue(v.get("removal_request"))


class PrecisionDidNotMove(unittest.TestCase):
    """The expensive direction: a real buying signal silently suppressed.

    Measured over all 559 rows - 12 positives before, 12 after, and not one
    of them changed category. These are the shapes that measurement covers,
    asserted by name so a later pattern cannot take them.
    """

    def test_a_warm_reply_is_still_positive(self):
        for text in ("sounds great, let's chat",
                     "Sounds good - happy to chat next week",
                     "Interested - what does it cost?",
                     "Yes please, tell me more"):
            with self.subTest(text=text):
                v = verdict_for(text)
                self.assertNotIn(v["classification"], REMOVAL,
                                 "%r was suppressed as %s"
                                 % (text, v["classification"]))

    def test_a_real_meeting_request_is_not_a_removal(self):
        for text in ("Happy to meet - can we set up a call on Thursday at "
                     "10am? I will send an invite.",
                     "Let's talk. Book a time here: "
                     "https://example.invalid/book",
                     "If you want to set up a phone call to chat, we can "
                     "certainly do that."):
            with self.subTest(text=text):
                v = verdict_for(text)
                self.assertNotIn(v["classification"], REMOVAL,
                                 "%r was suppressed as %s"
                                 % (text, v["classification"]))

    def test_a_legal_disclaimer_is_not_a_removal_request(self):
        """Reply 1602466. With `systems?` in the list-noun alternation the
        evidence was "remove from your system" - the tail of the standard
        confidentiality footer - and the human's own sentence had told us
        which tool they already use.
        """
        v = verdict_for(
            "Hi, we are in year one of using a one stop tool and it is "
            "going well.\n\nThis message is confidential. If received in "
            "error, please notify us and remove from your system.")
        self.assertNotIn(v["classification"], REMOVAL,
                         "a footer was read as a removal request (%s)"
                         % v["classification"])

    def test_an_object_after_the_verb_blocks_the_bare_imperative(self):
        """The clause end is the whole guard on pattern 3."""
        for text in ("Please remove the second slide before you send it.",
                     "If you received this in error please delete it from "
                     "your computer.",
                     "Please remove any duplicates from the attached deck."):
            with self.subTest(text=text):
                v = verdict_for(text)
                self.assertNotIn(v["classification"], REMOVAL,
                                 "%r was read as %s"
                                 % (text, v["classification"]))

    def test_an_out_of_office_is_untouched(self):
        v = verdict_for("Automatic reply: I am out of the office until the "
                        "5th with limited access to email.")
        self.assertEqual(v["classification"], replies.OUT_OF_OFFICE)


class TheRulesIdentityMoved(unittest.TestCase):
    """A verdict stored before this change must not compare equal to one
    stored after it. `_rule_material` walks every `*_PATTERNS` tuple, so
    adding to two of them is enough on its own."""

    #: The digest master carried before the union, measured 2026-10-12.
    BEFORE = "rules-4+ca10b3cccdcb"

    def test_the_digest_is_no_longer_the_one_master_had(self):
        self.assertNotEqual(replies.RULE_HASH, self.BEFORE)

    def test_the_release_name_did_not_move(self):
        self.assertTrue(replies.RULE_HASH.startswith("rules-4+"))

    def test_the_digest_is_derived_from_the_patterns(self):
        """Not remembered. Mutate a tuple and the digest must follow."""
        original = replies.BARE_REMOVAL_LINE_PATTERNS
        before = replies.rule_digest()
        try:
            replies.BARE_REMOVAL_LINE_PATTERNS = original + (r"^xyzzy$",)
            self.assertNotEqual(replies.rule_digest(), before)
        finally:
            replies.BARE_REMOVAL_LINE_PATTERNS = original
        self.assertEqual(replies.rule_digest(), before)


if __name__ == "__main__":
    unittest.main()
