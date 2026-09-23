"""The knowledge pack must be able to FAIL at answering its own questions.

TASK-274: an operator asked "explain in three sentences how the cross-channel
stop works" and the agent answered correctly from its own limits - "I am
reasoning, not reporting" - because the pack carried no mechanism section.
The answer was right; the pack was the defect.

This test walks the mechanism catalogue and asserts the pack contains the
material to answer each question it lists. A section that is removed fails
here before it fails in front of a human.
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import slackknowledge as knowledge


class ThePackAnswersWhatItClaims(unittest.TestCase):

    def setUp(self):
        self.pack = knowledge.build()

    def test_the_mechanisms_section_exists(self):
        self.assertIn("mechanisms", self.pack,
                       "the knowledge pack carries no 'mechanisms' section. "
                       "An operator asked about the cross-channel stop and "
                       "the agent had to reason from first principles "
                       "rather than report. TASK-274.")

    def test_the_cross_channel_stop_mechanism_is_present(self):
        mechanisms = self.pack.get("mechanisms") or {}
        self.assertIn("cross_channel_stop", mechanisms,
                       "the cross-channel stop mechanism is not in the pack. "
                       "This is the gap TASK-274 found.")

    def test_the_cross_channel_stop_cites_both_source_files(self):
        section = (self.pack.get("mechanisms") or {}).get(
            "cross_channel_stop") or {}
        body = json.dumps(section, default=str)
        self.assertIn("src/inbound.py", body)
        self.assertIn("src/leadstop.py", body)

    def test_the_cross_channel_stop_names_the_flow_steps(self):
        section = (self.pack.get("mechanisms") or {}).get(
            "cross_channel_stop") or {}
        steps = section.get("flow") or []
        self.assertTrue(steps,
                        "the cross-channel stop mechanism has no flow steps")
        step_names = [s.get("step") for s in steps]
        for expected in ("provider stop, both channels",
                         "classification",
                         "summary and refusals"):
            self.assertIn(expected, step_names,
                          "the flow is missing the step %r" % expected)

    def test_the_cross_channel_stop_names_the_refusal_cases(self):
        section = (self.pack.get("mechanisms") or {}).get(
            "cross_channel_stop") or {}
        cases = section.get("refusal_cases") or []
        self.assertTrue(cases)
        case_names = [c.get("case") for c in cases]
        for expected in ("no lead on that channel", "already stopped",
                         "REFUSED with reason"):
            self.assertIn(expected, case_names)

    def test_the_cross_channel_stop_cites_file_and_line(self):
        section = (self.pack.get("mechanisms") or {}).get(
            "cross_channel_stop") or {}
        body = json.dumps(section, default=str)
        import re
        citations = re.findall(r"src/\w+\.py:\d+", body)
        self.assertTrue(citations,
                        "the cross-channel stop mechanism has no file:line "
                        "citations. Every claim must trace to a line.")

    def test_every_catalogue_entry_has_material_in_the_pack(self):
        """The catalogue is the contract. Each entry must be answerable."""
        mechanisms = self.pack.get("mechanisms") or {}
        for section_key, question in knowledge.MECHANISM_CATALOGUE:
            section = mechanisms.get(section_key)
            self.assertIsNotNone(
                section,
                "the pack claims to answer %r via mechanisms.%s but that "
                "section is missing" % (question, section_key))
            body = json.dumps(section, default=str)
            self.assertTrue(
                len(body) > 50,
                "the pack's mechanisms.%s is too thin to answer %r"
                % (section_key, question))


class ThePackFailsWhenTheSectionIsRemoved(unittest.TestCase):
    """A scope test that cannot fail is not a test. Removing the mechanism
    section must break the catalogue walk."""

    def test_removing_the_mechanism_section_fails_the_catalogue(self):
        pack = knowledge.build()
        pack["mechanisms"] = {}
        mechanisms = pack.get("mechanisms") or {}
        failures = []
        for section_key, question in knowledge.MECHANISM_CATALOGUE:
            section = mechanisms.get(section_key)
            if section is None:
                failures.append(question)
        self.assertTrue(
            failures,
            "removing the mechanism section did not break the catalogue "
            "walk. The test cannot fail, which means it cannot find a gap.")


if __name__ == "__main__":
    unittest.main()
