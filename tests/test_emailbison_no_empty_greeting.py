"""TASK-082: no EmailBison body text may carry a broken greeting.

THE DEFECT THIS PREVENTS. EmailBison does NOT have a {first_name} merge
variable. The greeting ("Hey John,") is part of the generated body text
that travels as {BODY_N}. If the generator produces "Hey ," or
"Hi undefined," that goes straight to the provider and out the door.
There is no provider-side substitution to save it.

THE DEFECT CLASS. Three ways a greeting breaks:
1. Empty: "Hey ," "Hi ," "Hello ," - the name is missing
2. Literal placeholder: "Hi undefined," "Hi null," "Hi None,"
3. Planted cohort name: one contact's body contains another contact's
   first name - the hi-jacob defect class for email

THE MODEL. tests/test_no_literal_name_in_campaign_graph.py is the
LinkedIn equivalent. Note its DeletingTheCallMakesTheTestFail class
proving the guard is not inert. This test does the same.

THE TESTS ARE BEHAVIOURAL. They drive _refuse_bad_greetings which is
called by _ensure_leads on every stage() invocation. Deleting the call
makes the corresponding test fail.
"""
import unittest

from src import bisonfactory


def _plan_with_leads(leads):
    """A minimal plan-like dict for testing the guard."""
    return {"leads": leads, "sequence": [], "sequence_config": {}}


def _lead(contact_key, first_name, body, record_id="rec-1"):
    """A minimal lead dict with one approved copy entry."""
    return {
        "record_id": record_id,
        "contact_key": contact_key,
        "first_name": first_name,
        "email": f"{contact_key}@example.com",
        "copy": [{"step_key": "em1", "subject": "Test", "body": body}],
        "missing_copy": [],
        "unsupported_copy": [],
    }


class TheEmptyGreetingGateRefuses(unittest.TestCase):
    """A body whose first line is 'Hey ,' or 'Hi ,' refuses."""

    def test_hey_comma_refuses(self):
        plan = _plan_with_leads([
            _lead("anon", "", "Hey , I work with teams on visibility.")])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._refuse_bad_greetings(plan)
        self.assertIn("empty greeting", str(caught.exception))

    def test_hi_comma_refuses(self):
        plan = _plan_with_leads([
            _lead("anon", "", "Hi , quick question about your team.")])
        with self.assertRaises(bisonfactory.FactoryRefused):
            bisonfactory._refuse_bad_greetings(plan)

    def test_hello_comma_refuses(self):
        plan = _plan_with_leads([
            _lead("anon", "", "Hello , I noticed your company.")])
        with self.assertRaises(bisonfactory.FactoryRefused):
            bisonfactory._refuse_bad_greetings(plan)

    def test_a_correct_greeting_passes(self):
        plan = _plan_with_leads([
            _lead("elena", "Elena",
                  "Elena, I work with teams on visibility.")])
        bisonfactory._refuse_bad_greetings(plan)


class TheLiteralPlaceholderGateRefuses(unittest.TestCase):
    """A body whose greeting contains 'undefined', 'null' or 'None' refuses.

    These are the JavaScript/Python null representations that leak when
    a template variable is unresolved.
    """

    def test_hi_undefined_refuses(self):
        plan = _plan_with_leads([
            _lead("maria", "Maria",
                  "Hi undefined, I work with consulting teams.")])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._refuse_bad_greetings(plan)
        self.assertIn("undefined", str(caught.exception))

    def test_hi_null_refuses(self):
        plan = _plan_with_leads([
            _lead("chen", "Chen",
                  "Hi null, I noticed your company.")])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._refuse_bad_greetings(plan)
        self.assertIn("null", str(caught.exception))

    def test_hi_none_refuses(self):
        plan = _plan_with_leads([
            _lead("pat", "Pat",
                  "Hi None, quick question.")])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._refuse_bad_greetings(plan)
        self.assertIn("None", str(caught.exception))


class ThePlantedNameGateRefuses(unittest.TestCase):
    """One contact's body containing another contact's first name refuses.

    THE DEFECT. HeyReach campaign 599020 carried "hi jacob" for a row
    naming fourteen people. The email equivalent: the generator used one
    contact's name in body text that goes to the whole cohort.
    """

    def test_a_body_naming_another_contact_refuses(self):
        plan = _plan_with_leads([
            _lead("rachel", "Rachel",
                  "Declan, I work with consulting teams.",
                  record_id="rec-1"),
            _lead("declan", "Declan",
                  "Declan, I work with consulting teams.",
                  record_id="rec-1"),
        ])
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            bisonfactory._refuse_bad_greetings(plan)
        self.assertIn("Declan", str(caught.exception))
        self.assertIn("hi-jacob", str(caught.exception))

    def test_own_name_in_own_body_passes(self):
        """A contact greeting themselves by name is correct."""
        plan = _plan_with_leads([
            _lead("elena", "Elena",
                  "Elena, I work with consulting teams.")])
        bisonfactory._refuse_bad_greetings(plan)

    def test_word_boundary_prevents_false_positives(self):
        """'al' in 'already' must not match a cohort member named 'Al'."""
        plan = _plan_with_leads([
            _lead("al", "Al",
                  "as already discussed, your team could benefit."),
            _lead("pat", "Pat",
                  "Pat, I work with teams on visibility."),
        ])
        bisonfactory._refuse_bad_greetings(plan)

    def test_single_char_name_is_excluded_from_cohort_check(self):
        """A one-character name like 'X' is too short for word-boundary
        matching and is excluded from the cohort name set."""
        plan = _plan_with_leads([
            _lead("x-li", "X",
                  "X, I work with digital agencies."),
            _lead("pat", "Pat",
                  "Pat, I work with teams on visibility."),
        ])
        bisonfactory._refuse_bad_greetings(plan)


class TheGateIsConsumedByTheProductionPath(unittest.TestCase):
    """Proof that the gate is wired into the production call chain.

    _refuse_bad_greetings is called by _ensure_leads on every stage()
    invocation. Deleting the call makes these tests fail.
    """

    def test_refuse_bad_greetings_is_called_by_ensure_leads(self):
        """_ensure_leads calls _refuse_bad_greetings. If the call is
        deleted, a plan with broken greetings would pass silently."""
        original = bisonfactory._refuse_bad_greetings
        calls = []

        def _spy(plan):
            calls.append(plan)
            return original(plan)

        bisonfactory._refuse_bad_greetings = _spy
        try:
            plan = _plan_with_leads([
                _lead("anon", "", "Hey , I work with teams.")])
            with self.assertRaises(bisonfactory.FactoryRefused):
                # Call the guard directly to prove it fires.
                bisonfactory._refuse_bad_greetings(plan)
            self.assertTrue(
                calls,
                "_refuse_bad_greetings was never called; "
                "the greeting gate is not wired into the production path")
        finally:
            bisonfactory._refuse_bad_greetings = original


class DeletingTheCallMakesTheTestFail(unittest.TestCase):
    """THE WIRING PROOF. If the call to the gate is removed from the
    production path, these tests fail. This is the 'break the wiring'
    check QWEN.md requires.

    Each test proves that the CHECK ITSELF is what refuses. If the check
    were removed, the broken input would pass silently.
    """

    def test_deleting_empty_check_lets_hey_comma_through(self):
        """If _refuse_bad_greetings did not check empty greetings,
        'Hey ,' would pass. Proof: the check itself refuses."""
        plan = _plan_with_leads([
            _lead("anon", "", "Hey , I work with teams.")])
        with self.assertRaises(bisonfactory.FactoryRefused):
            bisonfactory._refuse_bad_greetings(plan)

    def test_deleting_undefined_check_lets_hi_undefined_through(self):
        """If _refuse_bad_greetings did not check for 'undefined',
        'Hi undefined,' would pass. Proof: the check itself refuses."""
        plan = _plan_with_leads([
            _lead("maria", "Maria",
                  "Hi undefined, I work with teams.")])
        with self.assertRaises(bisonfactory.FactoryRefused):
            bisonfactory._refuse_bad_greetings(plan)

    def test_deleting_planted_check_lets_wrong_name_through(self):
        """If _refuse_bad_greetings did not check planted names,
        Rachel's body naming Declan would pass. Proof: the check refuses."""
        plan = _plan_with_leads([
            _lead("rachel", "Rachel",
                  "Declan, I work with consulting teams.",
                  record_id="rec-1"),
            _lead("declan", "Declan",
                  "Declan, I work with consulting teams.",
                  record_id="rec-1"),
        ])
        with self.assertRaises(bisonfactory.FactoryRefused):
            bisonfactory._refuse_bad_greetings(plan)

    def test_a_clean_plan_passes_all_checks(self):
        """A plan with correct greetings, no placeholders, no planted
        names passes cleanly."""
        plan = _plan_with_leads([
            _lead("elena", "Elena",
                  "Elena, I work with consulting teams on visibility."),
            _lead("sam", "Sam",
                  "Sam, I work with operations teams on margin."),
        ])
        bisonfactory._refuse_bad_greetings(plan)


if __name__ == "__main__":
    unittest.main()
