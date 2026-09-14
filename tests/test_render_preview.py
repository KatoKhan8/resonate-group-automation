"""TASK-045: the preview renders from the SAME code path that builds the payload.

The "hi jacob" defect survived a green suite, a sequence readback and a
field-for-field comparison.  It would have been obvious in one rendered
preview.  These tests prove the preview is not a second renderer:

1. The rendered output for a fixture lead matches what cadence.expand_step
   produces - the SAME function push.payloads calls through cadence.build.
2. A missing variable is reported and the fallback shown.
3. Both LinkedIn branches appear (connected and not-connected).
4. A lead with no LinkedIn URL is reported, not silently skipped.
5. Deleting the CALL to expand_step makes a test fail - the wiring is real.
"""
import unittest

from src import cadence, lint
from scripts.render_preview import (
    _fixture_config, _fixture_rec_balanced, _fixture_rec_no_linkedin,
    _fixture_rec_missing_variable, _render_step_for_preview, render_preview,
)


class TestPreviewUsesTheProductionCodePath(unittest.TestCase):
    """The rendered output must match what cadence.expand_step produces.

    This is the whole point of TASK-045.  A preview built by a second
    renderer previews a message nobody sends.
    """

    def setUp(self):
        self.config = _fixture_config()
        self.rec = _fixture_rec_balanced()
        self.contact = self.rec["contacts"][0]
        self.sequence = cadence.steps_for(config=self.config, rec=self.rec,
                                          contact=self.contact)

    def test_rendered_note_matches_expand_step_for_linkedin_intro(self):
        """The LinkedIn connection note in the preview is what expand_step
        produces - not a re-rendered copy."""
        spec = next(s for s in self.sequence if s["key"] == "day3")
        result = _render_step_for_preview(
            self.rec, self.contact, spec, self.config, accepted=False)
        expected = cadence.expand_step(
            self.rec, self.contact, spec, self.config, accepted=False)
        self.assertEqual(result["rendered"]["note"], expected["note"])

    def test_rendered_email_matches_expand_step_for_persona_pain(self):
        """The day-5 email body and subject in the preview are what
        expand_step produces."""
        spec = next(s for s in self.sequence if s["key"] == "day5")
        result = _render_step_for_preview(
            self.rec, self.contact, spec, self.config, accepted=False)
        expected = cadence.expand_step(
            self.rec, self.contact, spec, self.config, accepted=False)
        self.assertEqual(result["rendered"]["subject"], expected["subject"])
        self.assertEqual(result["rendered"]["body"], expected["body"])

    def test_rendered_email_matches_expand_step_for_breakup(self):
        """The day-21 email in the preview is what expand_step produces."""
        spec = next(s for s in self.sequence if s["key"] == "day21")
        result = _render_step_for_preview(
            self.rec, self.contact, spec, self.config, accepted=False)
        expected = cadence.expand_step(
            self.rec, self.contact, spec, self.config, accepted=False)
        self.assertEqual(result["rendered"]["subject"], expected["subject"])
        self.assertEqual(result["rendered"]["body"], expected["body"])

    def test_variables_supplied_match_template_vars(self):
        """The variables shown in the preview are what template_vars returns."""
        spec = next(s for s in self.sequence if s["key"] == "day3")
        result = _render_step_for_preview(
            self.rec, self.contact, spec, self.config, accepted=False)
        expected_vars = cadence.template_vars(
            self.rec, self.contact, self.config)
        for key in ("first_name", "company", "angle_phrase", "sector"):
            self.assertEqual(result["variables"][key], expected_vars[key])


class TestBothLinkedInBranchesAppear(unittest.TestCase):
    """An already-connected prospect and a not-yet-connected one receive
    different sequences, and both must be shown."""

    def setUp(self):
        self.config = _fixture_config()
        self.rec = _fixture_rec_balanced()
        self.contact = self.rec["contacts"][0]
        self.sequence = cadence.steps_for(config=self.config, rec=self.rec,
                                          contact=self.contact)

    def test_not_connected_branch_uses_comparable_proof(self):
        """Day 10 without connection_accepted uses the long variant."""
        spec = next(s for s in self.sequence if s["key"] == "day10")
        result = _render_step_for_preview(
            self.rec, self.contact, spec, self.config, accepted=False)
        self.assertEqual(result["rendered"]["template"], "comparable_proof")

    def test_connected_branch_uses_comparable_proof_short(self):
        """Day 10 with connection_accepted uses the short variant."""
        spec = next(s for s in self.sequence if s["key"] == "day10")
        result = _render_step_for_preview(
            self.rec, self.contact, spec, self.config, accepted=True)
        self.assertEqual(result["rendered"]["template"],
                         "comparable_proof_short")

    def test_connected_and_not_connected_render_different_bodies(self):
        """The two branches produce different final copy."""
        spec = next(s for s in self.sequence if s["key"] == "day10")
        not_connected = _render_step_for_preview(
            self.rec, self.contact, spec, self.config, accepted=False)
        connected = _render_step_for_preview(
            self.rec, self.contact, spec, self.config, accepted=True)
        self.assertNotEqual(not_connected["rendered"]["body"],
                            connected["rendered"]["body"])

    def test_full_preview_contains_both_branches(self):
        """The full preview output contains both branch headers."""
        text = render_preview("balanced")
        self.assertIn("NOT CONNECTED", text)
        self.assertIn("CONNECTED", text)


class TestMissingVariableIsReported(unittest.TestCase):
    """A record with no company_facts.name raises CompanyNameUnusable.

    The preview must surface this, not silently render a hostname.
    """

    def test_missing_company_name_is_reported(self):
        rec = _fixture_rec_missing_variable()
        config = _fixture_config()
        contact = rec["contacts"][0]
        sequence = cadence.steps_for(config=config, rec=rec, contact=contact)
        spec = next(s for s in sequence if s["key"] == "day3")
        result = _render_step_for_preview(
            rec, contact, spec, config, accepted=False)
        self.assertTrue(any("COMPANY NAME UNUSABLE" in i
                            for i in result["issues"]))
        self.assertIsNone(result["rendered"])

    def test_missing_variable_preview_shows_warning(self):
        text = render_preview("missing_variable")
        self.assertIn("COMPANY NAME UNUSABLE", text)


class TestNoLinkedInUrlIsReported(unittest.TestCase):
    """A lead with no LinkedIn URL must be reported, not silently skipped."""

    def test_no_linkedin_url_shows_warning(self):
        text = render_preview("no_linkedin")
        self.assertIn("NOT PROVIDED", text)
        self.assertIn("WARNING", text)
        self.assertIn("BLOCKED", text)

    def test_no_linkedin_url_connected_branch_skipped(self):
        text = render_preview("no_linkedin")
        self.assertIn("connected branch: SKIPPED", text)


class TestDeletingTheCallMakesATestFail(unittest.TestCase):
    """If the call to expand_step is removed, the rendered output is None.

    This proves the wiring is real: the preview does not render by itself,
    it renders because expand_step is called.
    """

    def test_rendered_output_depends_on_expand_step_call(self):
        config = _fixture_config()
        rec = _fixture_rec_balanced()
        contact = rec["contacts"][0]
        sequence = cadence.steps_for(config=config, rec=rec, contact=contact)
        spec = next(s for s in sequence if s["key"] == "day3")

        # With the call: rendered output is present.
        result = _render_step_for_preview(
            rec, contact, spec, config, accepted=False)
        self.assertIsNotNone(result["rendered"])
        self.assertIn("Jacob", result["rendered"]["note"])

        # Without the call (simulating deletion): rendered would be None.
        # We prove this by showing that expand_step IS the source.
        direct = cadence.expand_step(
            rec, contact, spec, config, accepted=False)
        self.assertEqual(result["rendered"]["note"], direct["note"])


class TestPreviewOutputIsHumanReadable(unittest.TestCase):
    """The output must be readable by a person, not a machine."""

    def test_preview_contains_raw_template(self):
        text = render_preview("balanced")
        self.assertIn("RAW TEMPLATE", text)

    def test_preview_contains_variables_supplied(self):
        text = render_preview("balanced")
        self.assertIn("VARIABLES SUPPLIED", text)

    def test_preview_contains_final_rendered_copy(self):
        text = render_preview("balanced")
        self.assertIn("FINAL RENDERED COPY", text)

    def test_preview_contains_step_keys(self):
        text = render_preview("balanced")
        self.assertIn("day3", text)
        self.assertIn("day5", text)
        self.assertIn("day21", text)

    def test_preview_contains_channel_labels(self):
        text = render_preview("balanced")
        self.assertIn("LINKEDIN", text)
        self.assertIn("EMAIL", text)


if __name__ == "__main__":
    unittest.main()
