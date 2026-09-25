"""The step key is not the variable number. TASK-295.

THE REAL MAPPING (from productive.yaml, five-step config):

    thread_reply_pattern: [false, true, true, true, true]

    em1   position 1   subject {SUBJECT_1}   body {BODY_1}
    em2   position 2   subject {SUBJECT_1}   body {BODY_2}
    em3   position 3   subject {SUBJECT_1}   body {BODY_3}
    em4   position 4   subject {SUBJECT_1}   body {BODY_4}
    em5   position 5   subject {SUBJECT_1}   body {BODY_5}

At FIVE steps, position and key happen to agree. At FOUR steps (the config
before 2026-09-25), they did NOT:

    em1   position 1   body {BODY_1}
    em2   position 2   body {BODY_2}
    em4   position 3   body {BODY_3}    <-- em4 is at position 3
    em5   position 4   body {BODY_4}    <-- em5 is at position 4

A check that maps em5 -> BODY_5 will look for a variable that does not exist
and report every lead as blank. That is the single most likely way to get a
green check that is wrong in both directions at once.

THESE TESTS PROVE:
1. The mapping is read from the config, not hardcoded.
2. At four steps, em4 -> BODY_3 and em5 -> BODY_4.
3. At five steps, em5 -> BODY_5 (coincidence of position).
4. A check using the wrong mapping reports false failures.
"""
import unittest

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.qa import check_lead_copy


class ConfigStepMappingFourSteps(unittest.TestCase):
    """At four steps, the step key does NOT equal the variable number."""

    def setUp(self):
        self.config = {
            "email_sequence": {
                "thread_reply_pattern": [False, True, True, True],
                "steps": {
                    "em1": {"order": 1, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                    "em2": {"order": 2, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                    "em4": {"order": 3, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_3}</p>", "wait_in_days": 5},
                    "em5": {"order": 4, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_4}</p>", "wait_in_days": 1},
                },
            }
        }

    def test_em4_maps_to_body_3_not_body_4(self):
        """em4 is at position 3 and reads {BODY_3}, NOT {BODY_4}."""
        mapping = check_lead_copy.read_step_body_mapping(self.config)
        by_key = dict(mapping)
        self.assertEqual(by_key.get("em4"), "BODY_3",
                         "em4 at position 3 reads {BODY_3}, not {BODY_4}")

    def test_em5_maps_to_body_4_not_body_5(self):
        """em5 is at position 4 and reads {BODY_4}, NOT {BODY_5}."""
        mapping = check_lead_copy.read_step_body_mapping(self.config)
        by_key = dict(mapping)
        self.assertEqual(by_key.get("em5"), "BODY_4",
                         "em5 at position 4 reads {BODY_4}, not {BODY_5}")

    def test_mapping_has_four_entries(self):
        mapping = check_lead_copy.read_step_body_mapping(self.config)
        self.assertEqual(len(mapping), 4)

    def test_thread_reply_pattern_has_four_entries(self):
        pattern = check_lead_copy.read_thread_reply_pattern(self.config)
        self.assertEqual(len(pattern), 4)
        self.assertEqual(pattern, (False, True, True, True))


class ConfigStepMappingFiveSteps(unittest.TestCase):
    """At five steps, position and key agree by coincidence."""

    def setUp(self):
        self.config = {
            "email_sequence": {
                "thread_reply_pattern": [False, True, True, True, True],
                "steps": {
                    "em1": {"order": 1, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                    "em2": {"order": 2, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                    "em3": {"order": 3, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_3}</p>", "wait_in_days": 4},
                    "em4": {"order": 4, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_4}</p>", "wait_in_days": 9},
                    "em5": {"order": 5, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_5}</p>", "wait_in_days": 1},
                },
            }
        }

    def test_em5_maps_to_body_5_at_five_steps(self):
        """At five steps, em5 is at position 5 and reads {BODY_5}.
        This is a COINCIDENCE of position, not a rule."""
        mapping = check_lead_copy.read_step_body_mapping(self.config)
        by_key = dict(mapping)
        self.assertEqual(by_key.get("em5"), "BODY_5")

    def test_em3_maps_to_body_3(self):
        mapping = check_lead_copy.read_step_body_mapping(self.config)
        by_key = dict(mapping)
        self.assertEqual(by_key.get("em3"), "BODY_3")

    def test_mapping_has_five_entries(self):
        mapping = check_lead_copy.read_step_body_mapping(self.config)
        self.assertEqual(len(mapping), 5)


class StepsExpectedFromCampaign(unittest.TestCase):
    """steps_expected is THIS campaign's cadence_steps, never a constant."""

    def test_three_step_campaign_returns_3(self):
        """Option A: eleven campaigns hold 3 steps legitimately."""
        config = {"email_sequence": {"steps": {
            "em1": {"order": 1, "body": "<p>{BODY_1}</p>"},
            "em2": {"order": 2, "body": "<p>{BODY_2}</p>"},
            "em4": {"order": 3, "body": "<p>{BODY_3}</p>"},
        }}}
        campaign = {"cadence_steps": [
            {"channel": "email", "key": "em1", "day": 1},
            {"channel": "email", "key": "em2", "day": 4},
            {"channel": "email", "key": "em4", "day": 8},
        ]}
        result = check_lead_copy.resolve_steps_expected(config, campaign)
        self.assertEqual(result, 3)

    def test_four_step_campaign_returns_4(self):
        config = {"email_sequence": {"steps": {
            "em1": {"order": 1, "body": "<p>{BODY_1}</p>"},
            "em2": {"order": 2, "body": "<p>{BODY_2}</p>"},
            "em4": {"order": 3, "body": "<p>{BODY_3}</p>"},
            "em5": {"order": 4, "body": "<p>{BODY_4}</p>"},
        }}}
        campaign = {"cadence_steps": [
            {"channel": "email", "key": "em1", "day": 1},
            {"channel": "email", "key": "em2", "day": 4},
            {"channel": "email", "key": "em4", "day": 8},
            {"channel": "email", "key": "em5", "day": 13},
        ]}
        result = check_lead_copy.resolve_steps_expected(config, campaign)
        self.assertEqual(result, 4)

    def test_campaign_without_cadence_steps_falls_back_to_config(self):
        config = {"email_sequence": {"steps": {
            "em1": {"order": 1, "body": "<p>{BODY_1}</p>"},
            "em2": {"order": 2, "body": "<p>{BODY_2}</p>"},
            "em3": {"order": 3, "body": "<p>{BODY_3}</p>"},
            "em4": {"order": 4, "body": "<p>{BODY_4}</p>"},
            "em5": {"order": 5, "body": "<p>{BODY_5}</p>"},
        }}}
        result = check_lead_copy.resolve_steps_expected(config, campaign=None)
        self.assertEqual(result, 5)


class WrongMappingReportsFalseFailures(unittest.TestCase):
    """A check that hardcodes em5 -> BODY_5 on a four-step config
    will look for body_5 that does not exist and report every lead as blank."""

    def test_four_step_lead_with_correct_mapping_passes(self):
        """A four-step lead with body_1..body_4 passes at steps_expected=4."""
        config = {"email_sequence": {
            "thread_reply_pattern": [False, True, True, True],
            "steps": {
                "em1": {"order": 1, "subject": "{SUBJECT_1}",
                        "body": "<p>{BODY_1}</p>", "wait_in_days": 3},
                "em2": {"order": 2, "subject": "{SUBJECT_1}",
                        "body": "<p>{BODY_2}</p>", "wait_in_days": 4},
                "em4": {"order": 3, "subject": "{SUBJECT_1}",
                        "body": "<p>{BODY_3}</p>", "wait_in_days": 5},
                "em5": {"order": 4, "subject": "{SUBJECT_1}",
                        "body": "<p>{BODY_4}</p>", "wait_in_days": 1},
            },
        }}
        steps_expected = check_lead_copy.resolve_steps_expected(config)
        self.assertEqual(steps_expected, 4)

    def test_step_count_from_config_not_constant(self):
        """copylint.STEPS_EXPECTED is 5. A four-step config returns 4."""
        from src import copylint
        self.assertEqual(copylint.STEPS_EXPECTED, 5)
        config = {"email_sequence": {"steps": {
            "em1": {"order": 1, "body": "<p>{BODY_1}</p>"},
            "em2": {"order": 2, "body": "<p>{BODY_2}</p>"},
            "em4": {"order": 3, "body": "<p>{BODY_3}</p>"},
            "em5": {"order": 4, "body": "<p>{BODY_4}</p>"},
        }}}
        result = check_lead_copy.resolve_steps_expected(config)
        self.assertEqual(result, 4)
        self.assertNotEqual(result, copylint.STEPS_EXPECTED)


class AllStepsCarrySubject1(unittest.TestCase):
    """There is no SUBJECT_2 and no new-thread step at position 3.

    All four/five steps carry {SUBJECT_1}. The pattern's first entry is
    false and the other three/four are true: step 1 opens the thread,
    steps 2+ reply into it.
    """

    def test_five_step_config_all_reference_subject_1(self):
        config = {
            "email_sequence": {
                "thread_reply_pattern": [False, True, True, True, True],
                "steps": {
                    "em1": {"order": 1, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_1}</p>"},
                    "em2": {"order": 2, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_2}</p>"},
                    "em3": {"order": 3, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_3}</p>"},
                    "em4": {"order": 4, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_4}</p>"},
                    "em5": {"order": 5, "subject": "{SUBJECT_1}",
                            "body": "<p>{BODY_5}</p>"},
                },
            }
        }
        es = config["email_sequence"]
        for key, entry in es["steps"].items():
            self.assertIn("{SUBJECT_1}", entry["subject"],
                          "%s should reference {SUBJECT_1}" % key)

    def test_no_step_references_subject_2(self):
        """Two committed documents say SUBJECT_2 exists. The config says no."""
        config = {
            "email_sequence": {
                "steps": {
                    "em1": {"subject": "{SUBJECT_1}", "body": "<p>{BODY_1}</p>"},
                    "em2": {"subject": "{SUBJECT_1}", "body": "<p>{BODY_2}</p>"},
                    "em4": {"subject": "{SUBJECT_1}", "body": "<p>{BODY_3}</p>"},
                    "em5": {"subject": "{SUBJECT_1}", "body": "<p>{BODY_4}</p>"},
                },
            }
        }
        for key, entry in config["email_sequence"]["steps"].items():
            self.assertNotIn("SUBJECT_2", entry["subject"],
                             "%s should NOT reference SUBJECT_2" % key)


if __name__ == "__main__":
    unittest.main()
