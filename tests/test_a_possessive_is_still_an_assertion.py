#!/usr/bin/env python3
"""A second-person possessive is still an assertion about them.

THE DEFECT, MEASURED 2026-09-28.

`claims.SECOND_PERSON_ASSERTIONS` is a phrase list of verb forms ("you are ",
"you track ", "your team is " ...) and a bare possessive matches none of it:

    "You have margin visibility on every project."      REFUSED   (correct)
    "Your margin visibility slips between projects."    SUPPORTED (wrong)

Same assertion, different phrasing, one ships unexamined.

THE FIX adds a second path in `asserts_about_them`: if "your " is immediately
followed by an operational term, that is a second-person assertion and the
operational terms in the sentence must be supported. "Your margin visibility"
contains "margin" (operational), so the sentence is caught.

WHAT STAYS ALLOWED:

- "your time" and "your call" - "time" and "call" are not operational terms.
- Questions - "How do you track margin today?" has "?" and `is_claim` exempts
  questions before `asserts_about_them` is ever consulted.
- Hedged possessives - "if your margin slips" is caught by the HEDGES check
  that runs before the possessive branch.

THE MUTATION at the bottom removes the possessive branch and proves control 1
goes red for that reason and no other, then restores byte-identical source.
"""
import hashlib
import unittest

from src import claims


def a_contact(**over):
    contact = {"key": "vesna", "name": "Vesna Pallant",
               "title": "Operations Director", "persona": "operations",
               "angle": "operations", "email": "vesna@fernwick.test",
               "linkedin": "https://www.linkedin.com/in/vesna-p"}
    contact.update(over)
    return contact


def a_record(contact=None, **over):
    contact = contact or a_contact()
    rec = {"id": "fernwick", "client": "productive", "lane": "domains",
           "company": "Fernwick Studio", "domain": "fernwick.test",
           "company_facts": {"industry": "design", "employees": 48},
           "contacts": [contact]}
    rec.update(over)
    return rec


class NegativeControlPossessiveIsRefused(unittest.TestCase):
    """Control 1: 'Your margin visibility slips between projects.' REFUSED."""

    def test_possessive_assertion_with_no_evidence_is_refused(self):
        sentence = "Your margin visibility slips between projects."
        problems = claims.check(sentence, a_record(), a_contact())
        self.assertTrue(problems,
                        "expected REFUSED for possessive assertion with no "
                        "evidence, got clean")
        why = problems[0]["why"]
        self.assertIn("margin", why.lower())


class PositiveControlQuestionIsAllowed(unittest.TestCase):
    """Control 2: 'How do you track margin today?' is ALLOWED."""

    def test_question_asserts_nothing_and_passes(self):
        sentence = "How do you track margin today?"
        problems = claims.check(sentence, a_record(), a_contact())
        self.assertFalse(problems,
                         f"question should be ALLOWED, got: {problems}")


class PossessiveAllowedWhenLicensed(unittest.TestCase):
    """Control 3: the possessive IS allowed when evidence supports it."""

    def test_possessive_with_matching_research_is_clean(self):
        sentence = "Your margin visibility slips between projects."
        rec = a_record(research=[
            {"fact": "margin visibility slips between projects at Fernwick",
             "published_at": "2026-09-20"}
        ])
        problems = claims.check(sentence, rec, a_contact())
        self.assertFalse(problems,
                         f"possessive with matching evidence should pass, "
                         f"got: {problems}")


class OrdinaryPossessivesStillPass(unittest.TestCase):
    """Control 4: 'your time', 'your call' are not operational, still pass."""

    def test_your_time_is_not_caught(self):
        sentence = "I know your time is valuable."
        problems = claims.check(sentence, a_record(), a_contact())
        self.assertFalse(problems,
                         f"'your time' should pass, got: {problems}")

    def test_your_call_is_not_caught(self):
        sentence = "The next move is your call."
        problems = claims.check(sentence, a_record(), a_contact())
        self.assertFalse(problems,
                         f"'your call' should pass, got: {problems}")


class NearMissControl(unittest.TestCase):
    """A near-miss: 'your team' without an operational term still passes."""

    def test_your_team_without_operational_term(self):
        sentence = "Your team seems great."
        problems = claims.check(sentence, a_record(), a_contact())
        self.assertFalse(problems,
                         f"'your team' with no operational term should pass, "
                         f"got: {problems}")

    def test_hedged_possessive_still_passes(self):
        sentence = "If your margin visibility is a concern, let me know."
        problems = claims.check(sentence, a_record(), a_contact())
        self.assertFalse(problems,
                         f"hedged possessive should pass, got: {problems}")


class AssertsAboutThemDirectly(unittest.TestCase):
    """Drive asserts_about_them directly to prove the possessive path."""

    def test_possessive_with_operational_term_returns_terms(self):
        low = "your margin visibility slips between projects"
        result = claims.asserts_about_them(low)
        self.assertTrue(result,
                        "expected operational terms returned for possessive")
        self.assertIn("margin", result)
        self.assertIn("visibility", result)

    def test_possessive_without_operational_term_returns_false(self):
        low = "your time is valuable"
        result = claims.asserts_about_them(low)
        self.assertFalse(result,
                         "'your time' should not trigger asserts_about_them")

    def test_existing_verb_form_still_works(self):
        low = "you are running utilisation by hand"
        result = claims.asserts_about_them(low)
        self.assertTrue(result)
        self.assertIn("utilisation", result)


class MutationCheck(unittest.TestCase):
    """Control 5: remove the possessive branch, control 1 must go red.

    Reads the source, removes the possessive branch, reloads, runs control 1,
    proves it fails FOR THE INTENDED REASON (no assertion detected, so the
    sentence passes clean when it should not), then restores byte-identical.
    """

    def test_mutation_makes_control_1_pass_wrong(self):
        import importlib
        import src.claims as claims_mod

        src_path = claims_mod.__file__
        with open(src_path, "rb") as f:
            original_bytes = f.read()
        original_sha = hashlib.sha256(original_bytes).hexdigest()
        original_text = original_bytes.decode("utf-8")

        # The possessive branch is the block starting with the comment
        # "A POSSESSIVE + OPERATIONAL TERM" and ending before the final
        # `if not has_assertion` / `return False`.
        # We replace the possessive detection with a no-op.
        mutated_text = original_text.replace(
            '    if not has_assertion:\r\n'
            '        has_assertion = any(\r\n'
            '            f"your {t}" in low for t in evidence.OPERATIONAL_TERMS\r\n'
            '        )\r\n',
            '    # MUTATED: possessive branch removed\r\n'
        )
        # If CRLF replacement failed, try LF
        if mutated_text == original_text:
            mutated_text = original_text.replace(
                '    if not has_assertion:\n'
                '        has_assertion = any(\n'
                '            f"your {t}" in low for t in evidence.OPERATIONAL_TERMS\n'
                '        )\n',
                '    # MUTATED: possessive branch removed\n'
            )
        self.assertNotEqual(mutated_text, original_text,
                            "mutation did not change the source - line "
                            "endings may not match")

        with open(src_path, "w", newline="") as f:
            f.write(mutated_text)

        try:
            importlib.reload(claims_mod)
            # After mutation, "Your margin visibility slips..." should NOT be
            # caught - asserts_about_them returns False because no verb-form
            # marker matches and the possessive branch is gone.
            low = "your margin visibility slips between projects"
            result = claims_mod.asserts_about_them(low)
            self.assertFalse(result,
                             "MUTATION FAILED: asserts_about_them still "
                             "caught the possessive after branch removal")

            # And the full check should now pass clean (wrong!)
            problems = claims_mod.check(
                "Your margin visibility slips between projects.",
                a_record(), a_contact())
            self.assertFalse(problems,
                             "MUTATION FAILED: claim still refused after "
                             "removing the possessive branch - a different "
                             "guard fired first")
        finally:
            with open(src_path, "wb") as f:
                f.write(original_bytes)
            importlib.reload(claims_mod)
            # Verify byte-identical restore
            with open(src_path, "rb") as f:
                restored_sha = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(original_sha, restored_sha,
                             "source not restored byte-identical after "
                             "mutation")


if __name__ == "__main__":
    unittest.main()
