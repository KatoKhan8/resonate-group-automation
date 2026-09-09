"""Ceilings a configuration cannot raise.

The failure this guards against is not exotic. It is somebody typing 2000
where they meant 20, in a field that accepts it, on a screen with no idea a
pilot is happening. The system does exactly what it was told, and the first
live run stops being a pilot.

Two properties carry the file. The smaller number wins, always. And a plan
that asks for too much is refused rather than trimmed - somebody who asked
for two hundred and silently got twenty has been told the system did what
they asked, and it did not.
"""
import unittest

from src import pilotcaps


BIG = {"campaign": {"daily_volume": {"email": 2000, "linkedin": 900}},
       "fatigue": {"account": {"max_touches_per_week": 40}}}

SMALL = {"campaign": {"daily_volume": {"email": 5, "linkedin": 2}}}


class TheCeilingWins(unittest.TestCase):

    def test_a_configuration_cannot_raise_a_ceiling(self):
        limits = pilotcaps.effective(BIG)
        self.assertEqual(limits["email_per_day"]["limit"],
                         pilotcaps.CEILING["email_per_day"])
        self.assertEqual(limits["linkedin_per_day"]["limit"],
                         pilotcaps.CEILING["linkedin_per_day"])

    def test_a_smaller_configuration_is_respected(self):
        """A ceiling is not a default. Somebody who asked for five gets
        five, because the smaller number wins in both directions."""
        limits = pilotcaps.effective(SMALL)
        self.assertEqual(limits["email_per_day"]["limit"], 5)
        self.assertEqual(limits["email_per_day"]["source"], "configured")

    def test_the_row_says_which_number_applied_and_why(self):
        row = pilotcaps.effective(BIG)["email_per_day"]
        self.assertTrue(row["capped"])
        self.assertEqual(row["configured"], 2000)
        self.assertEqual(row["ceiling"], 20)
        self.assertEqual(row["source"], "ceiling")
        self.assertTrue(row["why"])

    def test_it_names_the_setting_it_constrains(self):
        """Two numbers meet here. A reader must not have to guess which
        one applied, or where the other one lives."""
        row = pilotcaps.effective(BIG)["email_per_day"]
        self.assertEqual(row["constrains"], "campaign.daily_volume.email")

    def test_a_key_nobody_configured_gets_the_ceiling(self):
        row = pilotcaps.effective({})["companies"]
        self.assertEqual(row["limit"], pilotcaps.CEILING["companies"])
        self.assertEqual(row["source"], "ceiling")
        self.assertFalse(row["capped"])

    def test_every_key_has_a_label_and_a_reason(self):
        for key in pilotcaps.KEYS:
            self.assertTrue(pilotcaps.LABELS[key], key)
            self.assertTrue(pilotcaps.WHY[key], key)

    def test_the_ceilings_are_pilot_sized(self):
        """Deliberately smaller than anybody would choose for a real
        campaign. A pilot that quietly grew is a pilot nobody watched."""
        self.assertLessEqual(pilotcaps.CEILING["companies"], 20)
        self.assertLessEqual(pilotcaps.CEILING["contacts"], 40)
        self.assertLessEqual(pilotcaps.CEILING["email_per_day"], 20)


class AbsenceMeansTheCapsApply(unittest.TestCase):
    """Inverted on purpose. Every other switch here defaults to off
    because off is safe; this one defaults to on for the same reason."""

    def test_no_configuration_at_all_is_pilot_mode(self):
        self.assertTrue(pilotcaps.enabled(None))
        self.assertTrue(pilotcaps.enabled({}))

    def test_an_empty_pilot_block_is_still_pilot_mode(self):
        self.assertTrue(pilotcaps.enabled({"pilot": {}}))

    def test_turning_it_off_is_explicit(self):
        self.assertFalse(pilotcaps.enabled({"pilot": {"enabled": "off"}}))
        self.assertFalse(pilotcaps.enabled({"pilot": {"enabled": "false"}}))

    def test_with_it_off_a_large_configuration_applies(self):
        config = dict(BIG, pilot={"enabled": "off"})
        self.assertEqual(
            pilotcaps.effective(config)["email_per_day"]["limit"], 2000)

    def test_with_it_off_an_unconfigured_key_still_has_the_ceiling(self):
        """Turning pilot mode off lifts the cap on what was configured. It
        does not invent a number for what was not."""
        config = {"pilot": {"enabled": "off"}}
        row = pilotcaps.effective(config)["companies"]
        self.assertEqual(row["limit"], pilotcaps.CEILING["companies"])


class TooMuchIsRefusedNotTrimmed(unittest.TestCase):

    def test_a_plan_that_fits_passes(self):
        found = pilotcaps.check({"companies": 12, "contacts": 24})
        self.assertTrue(found["ok"])
        self.assertEqual(found["breaches"], [])

    def test_a_plan_that_does_not_fit_is_refused(self):
        found = pilotcaps.check({"companies": 500})
        self.assertFalse(found["ok"])
        self.assertEqual(found["breaches"][0]["asked"], 500)
        self.assertEqual(found["breaches"][0]["limit"], 20)
        self.assertEqual(found["breaches"][0]["over_by"], 480)

    def test_require_raises_rather_than_returning_a_smaller_number(self):
        with self.assertRaises(pilotcaps.PilotCapExceeded):
            pilotcaps.require({"contacts": 900})

    def test_the_exception_says_what_was_asked_and_what_is_allowed(self):
        try:
            pilotcaps.require({"contacts": 900})
        except pilotcaps.PilotCapExceeded as e:
            self.assertIn("900", str(e))
            self.assertIn("40", str(e))
        else:
            self.fail("it should have raised")

    def test_a_key_the_plan_does_not_name_is_reported_as_unchecked(self):
        """A plan that named nothing would otherwise come back clean."""
        found = pilotcaps.check({"companies": 1})
        self.assertEqual(found["checked"], ["companies"])
        self.assertIn("contacts", found["unchecked"])

    def test_an_empty_plan_checks_nothing_and_says_so(self):
        found = pilotcaps.check({})
        self.assertTrue(found["ok"])
        self.assertEqual(found["checked"], [])
        self.assertEqual(sorted(found["unchecked"]), sorted(pilotcaps.KEYS))

    def test_the_note_explains_why_it_refuses(self):
        self.assertIn("rather than trimmed", pilotcaps.check({})["note"])


class NothingHereLiftsACeiling(unittest.TestCase):

    def test_the_module_exposes_no_way_to_change_a_ceiling(self):
        """Structural rather than a search of the source. A test that
        greps for names is a test that fails on a comment, which has
        happened four times in this repository already."""
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(pilotcaps))
        functions = {node.name for node in ast.walk(tree)
                     if isinstance(node, ast.FunctionDef)}
        self.assertEqual(
            {f for f in functions
             if f.startswith(("set_", "raise_", "enable_", "lift_"))}, set())

    def test_it_reads_no_environment(self):
        """An environment variable would be a way to raise a ceiling from
        outside a code review."""
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(pilotcaps))
        names = {node.id for node in ast.walk(tree)
                 if isinstance(node, ast.Name)}
        self.assertNotIn("os", names)
        self.assertNotIn("getenv", names)

    def test_effective_takes_only_the_configuration_being_constrained(self):
        """Nothing to pass that raises a ceiling is what makes it one."""
        import inspect

        args = inspect.signature(pilotcaps.effective).parameters
        self.assertEqual(list(args), ["config"])

    def test_the_ceiling_table_is_the_only_source_of_the_numbers(self):
        for key in pilotcaps.KEYS:
            self.assertIsInstance(pilotcaps.CEILING[key], int)
            self.assertGreater(pilotcaps.CEILING[key], 0)


if __name__ == "__main__":
    unittest.main()
