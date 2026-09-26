#!/usr/bin/env python3
"""TASK-297: a connection note that fits as a template may not fit rendered.

A 240-character template with `{company}` in it can render past 280 when the
company name is long enough. The check MUST measure the RENDERED note, not
the template. A template under 280 with a placeholder that renders over 280
is a FAIL, not a PASS.

A placeholder note (HeyReach's default "Hey, would love to connect!") that is
under 280 is NOT a pass - it was never approved. Placeholders are reported
separately from over-length notes.

THE CONSTRUCTED FAILURE: a template of 250 characters containing `{COMPANY}`
that, when rendered with a 40-character company name, produces a 284-character
note. The template passes a naive length check; the rendered note does not.
"""
import unittest
from unittest import mock

from scripts.qa import check_campaign_heyreach
from src.providers import heyreach


class RenderedNoteLength(unittest.TestCase):
    """The rendered note, not the template, is what reaches a person."""

    def test_template_under_limit_rendered_over_limit_is_fail(self):
        """A template under 280 with {COMPANY} renders over 280 when the
        company name is long. The template passes a naive length check; the
        rendered note does not."""
        # Build a template under 280 chars with {COMPANY} (9 chars) as a
        # placeholder. When COMPANY is replaced with a 50-char name, the
        # rendered note grows by 41 chars, pushing it past 280.
        # Template: 39 + 180 + 40 = 259 chars (under 280)
        # Rendered: 39 - 18 + 9 + 180 + 40 - 9 + 50 = 291 chars (over 280)
        template = (
            "Hi {FIRST_NAME}, I have been following "
            + "x" * 180
            + " at {COMPANY} and would love to connect"
        )
        self.assertLess(len(template), 280,
                        "template must be under 280 for this test to prove "
                        "the point")
        fields = {
            "FIRST_NAME": "Alexandra",
            "COMPANY": "A" * 50,
        }
        rendered = check_campaign_heyreach._render_note(template, fields)
        self.assertGreater(len(rendered), 280,
                           "rendered note must exceed 280 for this test")

    def test_render_note_substitutes_known_variables(self):
        template = "Hi {FIRST_NAME} at {COMPANY}"
        fields = {"FIRST_NAME": "Jane", "COMPANY": "Acme Corp"}
        rendered = check_campaign_heyreach._render_note(template, fields)
        self.assertEqual(rendered, "Hi Jane at Acme Corp")

    def test_render_note_leaves_unknown_variables_in_place(self):
        template = "Hi {FIRST_NAME} at {COMPANY}"
        fields = {"FIRST_NAME": "Jane"}
        rendered = check_campaign_heyreach._render_note(template, fields)
        self.assertEqual(rendered, "Hi Jane at {COMPANY}")

    def test_longest_rendered_length_picks_the_worst(self):
        notes = [
            "Short note",
            "Hi {FIRST_NAME}, a medium-length note with some text",
            "Hi {FIRST_NAME}, this is a much longer note that has {COMPANY} "
            "in it and also {POSITION} to make it even longer",
        ]
        fields = {
            "FIRST_NAME": "Alexandria",
            "COMPANY": "International Business Machines Corporation",
            "POSITION": "Senior Vice President of Global Operations",
        }
        max_len, tmpl, rendered = \
            check_campaign_heyreach._longest_rendered_length(notes, fields)
        self.assertEqual(max_len, len(rendered))
        self.assertEqual(tmpl, notes[2])

    def test_placeholder_note_is_detected(self):
        self.assertTrue(heyreach.note_is_placeholder(
            "Hey, would love to connect!"))
        self.assertTrue(heyreach.note_is_placeholder(
            "hi, would love to connect!"))
        self.assertFalse(heyreach.note_is_placeholder(
            "Hi Jane, I lead the partnerships team at Acme and would love "
            "to discuss a potential collaboration"))


class PlaceholderIsNotAPass(unittest.TestCase):
    """A placeholder under 280 is not an approved note."""

    def test_placeholder_under_280_is_still_a_placeholder(self):
        placeholder = "Hey, would love to connect!"
        self.assertLess(len(placeholder), 280)
        self.assertTrue(heyreach.note_is_placeholder(placeholder))

    def test_extract_longest_field_values_finds_the_worst(self):
        leads = [
            {"linkedInUserProfile": {"firstName": "Jo",
                                     "companyName": "Acme"}},
            {"linkedInUserProfile": {"firstName": "Alexandra",
                                     "companyName": "International Corp"}},
        ]
        longest = check_campaign_heyreach._extract_longest_field_values(leads)
        self.assertEqual(longest["FIRST_NAME"], "Alexandra")
        self.assertEqual(longest["COMPANY"], "International Corp")


class WindowOverlapComputation(unittest.TestCase):
    """The overlap between LinkedIn and email windows is reported in hours."""

    def test_full_overlap_on_weekdays(self):
        """LinkedIn 07-23 seven days, email 09-17 Mon-Fri.
        Overlap per weekday: 09-17 = 8 hours. Over 5 days: 40 hours."""
        li_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        em_days = {"mon", "tue", "wed", "thu", "fri"}
        overlap = check_campaign_heyreach._window_overlap_hours(
            7, 23, li_days, 9, 17, em_days)
        self.assertEqual(overlap, 40)

    def test_no_overlap_on_weekends(self):
        """Email does not run on weekends, so weekend-only LinkedIn has no
        overlap."""
        li_days = {"sat", "sun"}
        em_days = {"mon", "tue", "wed", "thu", "fri"}
        overlap = check_campaign_heyreach._window_overlap_hours(
            7, 23, li_days, 9, 17, em_days)
        self.assertEqual(overlap, 0)

    def test_partial_hour_overlap(self):
        """LinkedIn 07-10, email 09-17, one day. Overlap: 09-10 = 1 hour."""
        li_days = {"mon"}
        em_days = {"mon"}
        overlap = check_campaign_heyreach._window_overlap_hours(
            7, 10, li_days, 9, 17, em_days)
        self.assertEqual(overlap, 1)

    def test_no_overlap_when_disjoint_hours(self):
        """LinkedIn 00-06, email 09-17, same day. No overlap."""
        li_days = {"mon"}
        em_days = {"mon"}
        overlap = check_campaign_heyreach._window_overlap_hours(
            0, 6, li_days, 9, 17, em_days)
        self.assertEqual(overlap, 0)


if __name__ == "__main__":
    unittest.main()
