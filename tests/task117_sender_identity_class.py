"""TASK-117: the class of sender-identity claims that escape the rule.

The claims rule has been extended four times, each time by one phrase.
This test documents the CLASS of claim that escapes: sender-identity
assertions that imply shared category with the recipient but use syntactic
forms the phrase-based patterns do not match.

These tests assert on what `claims.implies_prior_contact` and `claims.check`
RETURN, not on the text of the source. They are split into:

  1. A measurement of what currently escapes (documented, not fixed here).
  2. Safe pattern additions that catch 7 more with zero false refusals.
  3. Guards ensuring must-pass sender-identity copy stays clean.

The task explicitly says: do not add a fifth literal phrase and call it
fixed. The real fix is a config-level check against sender identity, not
more pattern matching. The safe patterns here are a partial improvement.
"""
import unittest

from src import claims


def bare_record():
    return {
        "id": "probe", "client": "productive",
        "company": "Acme", "domain": "acme.test",
        "company_facts": {"name": "Acme", "industry": "marketing",
                          "employees": 40},
        "contacts": [{"key": "ck-1", "name": "Jane", "title": "COO"}],
        "events": [], "research": [],
    }


def contact_of(rec):
    return rec["contacts"][0]


class TheEscapingClassIsMeasured(unittest.TestCase):
    """These phrases ARE sender-identity claims. They currently pass.

    This is a MEASUREMENT, not a desired state. Each test documents a
    phrase that the rule cannot catch without false refusals. If a future
    fix catches these, these tests should be moved to TheCaughtClass.
    """

    def test_as_a_role_without_fellow_passes(self):
        """'as a founder myself' escapes because 'as a' is not matched."""
        for sentence in (
            "as a founder myself i understand the pressure",
            "as an agency owner i know how resourcing works",
            "as a bootstrapped ceo i know every dollar counts",
        ):
            with self.subTest(sentence=sentence):
                self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_present_perfect_experience_passes(self):
        """'i have built two agencies' escapes - no number, no event word."""
        for sentence in (
            "i have built two agencies from scratch and know the pain",
            "i have scaled a team myself and understand the pressure",
            "i have run agencies for years and know the space well",
        ):
            with self.subTest(sentence=sentence):
                self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_i_know_what_its_like_passes(self):
        """'i know what it is like to run an agency' escapes."""
        for sentence in (
            "i know what it is like to run an agency at your size",
            "i know the founder journey well and wanted to connect",
        ):
            with self.subTest(sentence=sentence):
                self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_possessive_identity_passes(self):
        """'my agency has 20 people' escapes - no pattern matches."""
        for sentence in (
            "my agency has 20 people so i understand the scaling challenge",
            "my team is the same size as yours so i get it",
        ):
            with self.subTest(sentence=sentence):
                self.assertIsNone(claims.implies_prior_contact(sentence))


class TheSafePatternsCatchMore(unittest.TestCase):
    """Patterns that catch escaping phrases with zero false refusals.

    Each pattern is tested against both the should-catch set and the
    must-pass set. A pattern that refuses legitimate copy is NOT safe
    and must not be added.
    """

    def test_having_identity_verb_is_caught(self):
        """'having run/built/scaled/founded' is an experience claim."""
        for sentence in (
            "having run a team your size i know the pressure",
            "having scaled an agency myself i understand the challenge",
            "having built two companies from zero i know what it takes",
        ):
            with self.subTest(sentence=sentence):
                found = claims.implies_prior_contact(sentence)
                self.assertIsNotNone(found,
                                     f"experience claim passed: {sentence!r}")

    def test_like_you_first_person_is_caught(self):
        """'like you ... i' asserts shared identity."""
        for sentence in (
            "like you i am a founder and i understand the journey",
            "like you i run an agency and face the same challenges",
        ):
            with self.subTest(sentence=sentence):
                found = claims.implies_prior_contact(sentence)
                self.assertIsNotNone(found,
                                     f"shared-identity claim passed: {sentence!r}")

    def test_also_a_an_is_caught(self):
        """'i am also a founder' asserts shared category."""
        found = claims.implies_prior_contact(
            "i am also a founder so i understand the pressure")
        self.assertIsNotNone(found)

    def test_role_too_is_caught(self):
        """'i am an agency owner too' asserts shared category."""
        found = claims.implies_prior_contact(
            "i am an agency owner too so i get the challenge")
        self.assertIsNotNone(found)


class TheMustPassSetStaysClean(unittest.TestCase):
    """Legitimate sender-identity copy must NOT be refused.

    This is the TASK-075 guard. These phrases are what the ladder requires
    and what the prompt instructs. A rule that refuses them makes the
    ladder unsatisfiable.
    """

    def test_sender_identity_from_config_passes(self):
        """'i am Ivan, founder of Productive' states identity from config."""
        sentence = "i am Ivan, founder of Productive, working on project profitability"
        self.assertIsNone(claims.implies_prior_contact(sentence))
        rec = bare_record()
        self.assertEqual(claims.check(sentence, rec, contact_of(rec)), [])

    def test_work_with_agencies_passes(self):
        """'i work with agencies on resourcing' states what the sender does."""
        sentence = "i work with agencies on resourcing"
        self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_our_platform_passes(self):
        """'our platform connects budgets' is about our software."""
        sentence = "our platform connects budgets and time tracking"
        self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_we_built_productive_passes(self):
        """'we built productive' states what we did."""
        sentence = "we built productive so budgets and resourcing talk to each other"
        self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_curious_how_you_handle_passes(self):
        """'curious how you handle resourcing at your size' asks, not asserts."""
        sentence = "curious how you handle resourcing at your size"
        self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_as_a_result_passes(self):
        """'as a result' is a connective, not an identity claim."""
        sentence = "as a result we improved visibility across the board"
        self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_as_a_reminder_passes(self):
        """'as a reminder' is a discourse marker, not an identity claim."""
        sentence = "as a reminder the deadline is Friday"
        self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_having_said_that_passes(self):
        """'having said that' is a discourse marker, not an experience claim."""
        sentence = "having said that i understand the timing may not work"
        self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_sender_role_statement_passes(self):
        """'i lead the growth team at Productive' states a role, not shared identity."""
        sentence = "i lead the growth team at Productive and work with agency founders"
        self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_internal_discussion_passes(self):
        """'we discussed our roadmap internally' says nothing about the recipient."""
        sentence = "we discussed our roadmap internally and thought of you"
        self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_most_agencies_we_work_with_passes(self):
        """Population relative clause - about us, not about them."""
        sentence = "most agencies we work with track time in spreadsheets"
        self.assertIsNone(claims.implies_prior_contact(sentence))

    def test_publication_citation_passes(self):
        """'you mentioned in your talk' cites a publication, not correspondence."""
        sentence = "you mentioned in your talk that utilisation was the issue"
        self.assertIsNone(claims.implies_prior_contact(sentence))


class TheExistingPatternsStillWork(unittest.TestCase):
    """Guard against regression of the four existing patterns."""

    def test_as_a_fellow_founder_still_caught(self):
        found = claims.implies_prior_contact(
            "as a fellow founder i thought it would be good to connect")
        self.assertIsNotNone(found)

    def test_as_someone_who_runs_still_caught(self):
        found = claims.implies_prior_contact(
            "as someone who also runs an agency i understand the challenge")
        self.assertIsNotNone(found)

    def test_speaking_as_a_fellow_still_caught(self):
        found = claims.implies_prior_contact(
            "speaking as a fellow founder i wanted to connect")
        self.assertIsNotNone(found)

    def test_as_someone_who_founded_still_caught(self):
        found = claims.implies_prior_contact(
            "as someone who founded a marketing agency i know the space")
        self.assertIsNotNone(found)


if __name__ == "__main__":
    unittest.main()
