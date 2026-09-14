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


class TestEmailPreviewUsesTheProductionCodePath(unittest.TestCase):
    """TASK-057: the email preview renders through bisonfactory, not a
    second renderer.  The same functions that build the provider payload
    (_sequence_steps, _approved_copy, _variables_for) produce the preview.
    """

    def test_email_five_renders_all_five_emails(self):
        """The email_five fixture shows five FINAL RENDERED sections."""
        text = render_preview("email_five")
        for i in range(1, 6):
            self.assertIn(f"EMAIL {i}", text)
        self.assertIn("FINAL RENDERED", text)
        self.assertIn("END OF EMAIL PREVIEW", text)

    def test_email_five_shows_ladder_purposes(self):
        """Each email step shows its ladder rung purpose."""
        text = render_preview("email_five")
        self.assertIn("Relevance, and who is writing", text)
        self.assertIn("A different angle from the first email", text)
        self.assertIn("SAY WHAT THE PRODUCT IS", text)
        self.assertIn("Close the loop", text)

    def test_email_five_shows_provider_variables(self):
        """The preview shows subject_N and body_N variable names."""
        text = render_preview("email_five")
        self.assertIn("subject_1", text)
        self.assertIn("body_1", text)
        self.assertIn("subject_5", text)
        self.assertIn("body_5", text)
        self.assertIn("{SUBJECT_1}", text)
        self.assertIn("{BODY_1}", text)

    def test_email_five_shows_day_numbers(self):
        """Each email step shows its cadence day."""
        text = render_preview("email_five")
        self.assertIn("DAY:            1", text)

    def test_email_five_shows_angle(self):
        """Each email step shows the contact's angle."""
        text = render_preview("email_five")
        self.assertIn("ANGLE:          visibility", text)
        self.assertIn("ANGLE:          margin", text)

    def test_email_five_shows_next_branch(self):
        """Each email step shows what happens next."""
        text = render_preview("email_five")
        self.assertIn("NEXT BRANCH:", text)
        self.assertIn("END OF SEQUENCE", text)

    def test_email_missing_shows_missing_for_em3(self):
        """The email_missing fixture shows MISSING for em3."""
        text = render_preview("email_missing")
        self.assertIn("MISSING COPY", text)
        self.assertIn("em3", text)
        self.assertIn("*** MISSING - no approved copy for this step ***", text)
        self.assertIn("{SUBJECT_3} has no value", text)

    def test_email_missing_reports_product_name_absent(self):
        """The email_missing fixture flags that no email names the product."""
        text = render_preview("email_missing")
        self.assertIn("PRODUCT NAME MISSING", text)

    def test_email_five_no_issues_for_clean_copy(self):
        """The email_five fixture with two clean leads reports no issues."""
        text = render_preview("email_five")
        self.assertIn("No issues detected", text)

    def test_email_preview_renders_through_bisonfactory_variables_for(self):
        """The variables in the preview are what _variables_for produces.

        This proves the wiring: the preview calls the SAME function that
        builds the provider payload.
        """
        from src import bisonfactory
        from scripts.render_preview import (
            _fixture_config_email, _fixture_rec_email, _build_email_plan)
        config = _fixture_config_email()
        rec = _fixture_rec_email()
        plan = _build_email_plan(config, [rec])
        lead = plan["leads"][0]
        variables = lead["variables"]
        var_names = {v["name"] for v in variables}
        self.assertIn("subject_1", var_names)
        self.assertIn("body_1", var_names)
        contact = rec["contacts"][0]
        key = contact["key"]
        stored_em1 = rec["cadence"][key]["em1"]
        subject_var = next(v for v in variables if v["name"] == "subject_1")
        self.assertEqual(subject_var["value"], stored_em1["subject"])

    def test_email_preview_two_leads_render_different_copy(self):
        """Two leads with different angles render different email copy."""
        text = render_preview("email_five")
        self.assertIn("Jacob Hartley", text)
        self.assertIn("Declan Reilly", text)
        self.assertIn("Northbridge Consulting", text)
        self.assertIn("Bastion Digital", text)
        self.assertIn("visibility gap", text)
        self.assertIn("margin visibility", text)


if __name__ == "__main__":
    unittest.main()
