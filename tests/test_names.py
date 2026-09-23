"""tests/test_names.py: TASK-269 honorific stripping and greeting derivation.

The defect: a contact named "Ing Christoph Lemmer" greets "Ing" because the
first token of the name is an honorific. Three call sites derived a greeting
first name three different ways; now they all go through names.greeting_first_name.

Required tests from the task:
- "Ing Christoph Lemmer" greets "Christoph"
- A single-token name "Ing" is left alone rather than emptied
- "Mags Bennett" greets "Mags" and is not stripped
- The cleaned value reaches the rendered template via cadence.py
- _names_match now refuses a greeting that is only an honorific
- DE and AT samples from the real CSV
"""
import unittest

from src import names


class TestStripHonorific(unittest.TestCase):
    """The closed-list honorific stripper."""

    def test_strips_ing_from_german_name(self):
        """The repro case: Ing Christoph Lemmer -> Christoph Lemmer."""
        self.assertEqual(names.strip_honorific("Ing Christoph Lemmer"),
                         "Christoph Lemmer")

    def test_strips_dr_from_name(self):
        self.assertEqual(names.strip_honorific("Dr Khan"), "Khan")

    def test_strips_prof_from_name(self):
        self.assertEqual(names.strip_honorific("Prof. Müller"), "Müller")

    def test_strips_dipl_ing(self):
        self.assertEqual(names.strip_honorific("Dipl.-Ing. Schmidt"), "Schmidt")

    def test_strips_di_from_australian(self):
        """The Australian repro case: DI Chen -> Chen."""
        self.assertEqual(names.strip_honorific("DI Chen"), "Chen")

    def test_case_insensitive(self):
        self.assertEqual(names.strip_honorific("DR Smith"), "Smith")
        self.assertEqual(names.strip_honorific("prof jones"), "jones")

    def test_punctuation_insensitive(self):
        self.assertEqual(names.strip_honorific("Dr. Smith"), "Smith")
        self.assertEqual(names.strip_honorific("Ing. Schmidt"), "Schmidt")

    def test_does_not_strip_unknown_prefix(self):
        """Mags is not an honorific. Over-stripping is the worse failure."""
        self.assertEqual(names.strip_honorific("Mags Bennett"), "Mags Bennett")

    def test_single_token_is_not_stripped(self):
        """Never strip the only token. Let _refuse_bad_greetings handle it."""
        self.assertEqual(names.strip_honorific("Ing"), "Ing")
        self.assertEqual(names.strip_honorific("Dr"), "Dr")

    def test_empty_and_none(self):
        self.assertEqual(names.strip_honorific(""), "")
        self.assertEqual(names.strip_honorific(None), None)
        self.assertEqual(names.strip_honorific("   "), "   ")


class TestGreetingFirstName(unittest.TestCase):
    """The unified derivation for every call site that renders a greeting."""

    def test_derives_from_name_with_honorific(self):
        """The repro case: name="Ing Christoph Lemmer" -> "Christoph"."""
        contact = {"name": "Ing Christoph Lemmer"}
        self.assertEqual(names.greeting_first_name(contact), "Christoph")

    def test_derives_from_name_without_honorific(self):
        contact = {"name": "Petra Horvat"}
        self.assertEqual(names.greeting_first_name(contact), "Petra")

    def test_single_token_first_name_is_not_stripped(self):
        """If only first_name is available (single token), leave it alone."""
        contact = {"first_name": "Ing"}
        self.assertEqual(names.greeting_first_name(contact), "Ing")

    def test_mags_bennett_is_not_stripped(self):
        """Mags is not an honorific. The task pins this case."""
        contact = {"name": "Mags Bennett"}
        self.assertEqual(names.greeting_first_name(contact), "Mags")

    def test_prefers_name_over_first_name(self):
        """name gives context for stripping; first_name alone cannot strip."""
        contact = {"name": "Ing Christoph Lemmer", "first_name": "Ing"}
        self.assertEqual(names.greeting_first_name(contact), "Christoph")

    def test_falls_back_to_first_name_when_no_name(self):
        contact = {"first_name": "Petra"}
        self.assertEqual(names.greeting_first_name(contact), "Petra")

    def test_empty_contact(self):
        self.assertEqual(names.greeting_first_name({}), "")
        self.assertEqual(names.greeting_first_name(None), "")

    def test_no_name_returns_empty(self):
        """A contact with only a key returns empty; the caller adds 'there'."""
        contact = {"key": "petra-horvat"}
        self.assertEqual(names.greeting_first_name(contact), "")

    def test_dr_khan_from_name(self):
        """The US repro case."""
        contact = {"name": "Dr Khan"}
        self.assertEqual(names.greeting_first_name(contact), "Khan")

    def test_di_chen_from_name(self):
        """The Australian repro case."""
        contact = {"name": "DI Chen"}
        self.assertEqual(names.greeting_first_name(contact), "Chen")


class TestDEAndATSamples(unittest.TestCase):
    """DE and AT samples from the real CSV.

    The task says HR has no leads (Croatia 0 in the CSV), so we test DE and AT.
    The CSV file is not present in this worktree, but the task documents three
    honorific-prefixed rows:
        Germany:  First_Name="Ing"  Last_Name="Lemmer"  Full_Name="Ing Christoph Lemmer"
        US:       First_Name="Dr"   Last_Name="Khan"    Full_Name="Dr Khan"
        Australia: First_Name="DI"  Last_Name="Chen"    Full_Name="DI Chen"

    We test the German case (DE) and construct AT-equivalent cases from the
    honorific vocabulary (Dipl.-Ing., Mag.) which are DE/AT-specific.
    """

    def test_german_ing_christoph_lemmer(self):
        """The real row from the CSV: Germany, Ing Christoph Lemmer."""
        contact = {"name": "Ing Christoph Lemmer", "first_name": "Ing"}
        self.assertEqual(names.greeting_first_name(contact), "Christoph")

    def test_german_dipl_ing(self):
        """DE/AT honorific: Dipl.-Ing. Schmidt."""
        contact = {"name": "Dipl.-Ing. Schmidt"}
        self.assertEqual(names.greeting_first_name(contact), "Schmidt")

    def test_austrian_mag(self):
        """AT honorific: Mag. Müller."""
        contact = {"name": "Mag. Müller"}
        self.assertEqual(names.greeting_first_name(contact), "Müller")

    def test_austrian_dipl_ing_variant(self):
        """AT variant: Dipl.Ing. (no hyphen)."""
        contact = {"name": "Dipl.Ing. Wagner"}
        self.assertEqual(names.greeting_first_name(contact), "Wagner")


class TestNamesMatchRefusesHonorific(unittest.TestCase):
    """TASK-269: _names_match now refuses a greeting that is only an honorific.

    The defect: "Ing" greeting "Ing Christoph Lemmer" passed lint because
    "Ing" was a token of the full name. Now it is refused.
    """

    def test_honorific_greeting_is_refused(self):
        from src.lint import _names_match
        self.assertFalse(_names_match("Ing", "Ing Christoph Lemmer"))

    def test_dr_greeting_is_refused(self):
        from src.lint import _names_match
        self.assertFalse(_names_match("Dr", "Dr Khan"))

    def test_normal_greeting_still_passes(self):
        from src.lint import _names_match
        self.assertTrue(_names_match("Christoph", "Ing Christoph Lemmer"))
        self.assertTrue(_names_match("Khan", "Dr Khan"))
        self.assertTrue(_names_match("Petra", "Petra Horvat"))

    def test_wrong_person_still_refused(self):
        from src.lint import _names_match
        self.assertFalse(_names_match("Ivana", "Petra Horvat"))


class TestCadenceIntegration(unittest.TestCase):
    """The cleaned value reaches the rendered template via cadence.py.

    This is the test that fails on the no-op implementation. The task says:
    "A cleaner attached to contact['first_name'] would clean nothing that
    ships, because the path that renders every template does not read that
    field."

    We test that template_vars uses names.greeting_first_name and that an
    honorific-prefixed name produces a cleaned first_name in the output.
    """

    def test_template_vars_strips_honorific(self):
        from src import cadence
        rec = {
            "id": "test-record",
            "company": "TestCo",
            "domain": "testco.test",
            "company_facts": {"industry": "software", "name": "TestCo"},
            "evidence": {},
        }
        contact = {"name": "Ing Christoph Lemmer", "key": "ing-lemmer"}
        config = {}
        values = cadence.template_vars(rec, contact, config)
        self.assertEqual(values["first_name"], "Christoph")

    def test_template_vars_normal_name(self):
        from src import cadence
        rec = {
            "id": "test-record",
            "company": "TestCo",
            "domain": "testco.test",
            "company_facts": {"industry": "software", "name": "TestCo"},
            "evidence": {},
        }
        contact = {"name": "Petra Horvat", "key": "petra-horvat"}
        config = {}
        values = cadence.template_vars(rec, contact, config)
        self.assertEqual(values["first_name"], "Petra")

    def test_template_vars_no_name_falls_back_to_there(self):
        from src import cadence
        rec = {
            "id": "test-record",
            "company": "TestCo",
            "domain": "testco.test",
            "company_facts": {"industry": "software", "name": "TestCo"},
            "evidence": {},
        }
        contact = {"key": "unknown"}
        config = {}
        values = cadence.template_vars(rec, contact, config)
        self.assertEqual(values["first_name"], "there")


if __name__ == "__main__":
    unittest.main()
