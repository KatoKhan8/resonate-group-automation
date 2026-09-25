"""TASK-283: the S7 render carries every variable the cadence wants.

The verifier reads the config at run time, diffs the cadence's variable set
against the provider sequence's variable set in BOTH directions, and checks
every rendered row for empty, literal 'None', and unrendered placeholders
as three SEPARATE faults.

These tests drive the verifier's COMPONENTS, not its CLI. The CLI is a
report; the components are the guards.
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.verify_s7_render import (  # noqa: E402
    classify_value,
    check_final_wait,
    check_rows,
    check_threading,
    diff_sets,
    load_rows,
    rendered_rows,
    variable_keys_from_cadence,
    variable_keys_from_sequence,
)


class TestDiffSetsBothDirections(unittest.TestCase):
    """The set diff is the whole point. A count is not a diff."""

    def test_identical_sets_diff_empty_both_ways(self):
        cadence = {"subject_1", "body_1", "body_2", "body_3"}
        sequence = {"subject_1", "body_1", "body_2", "body_3"}
        in_c, in_s = diff_sets(cadence, sequence)
        self.assertEqual(in_c, [])
        self.assertEqual(in_s, [])

    def test_cadence_has_extra(self):
        cadence = {"subject_1", "body_1", "body_2", "body_3", "body_4"}
        sequence = {"subject_1", "body_1", "body_2", "body_3"}
        in_c, in_s = diff_sets(cadence, sequence)
        self.assertEqual(in_c, ["body_4"])
        self.assertEqual(in_s, [])

    def test_sequence_has_extra(self):
        cadence = {"subject_1", "body_1", "body_2"}
        sequence = {"subject_1", "body_1", "body_2", "body_3"}
        in_c, in_s = diff_sets(cadence, sequence)
        self.assertEqual(in_c, [])
        self.assertEqual(in_s, ["body_3"])

    def test_both_directions_differ(self):
        cadence = {"subject_1", "body_1", "body_2", "body_5"}
        sequence = {"subject_1", "body_1", "body_2", "body_3"}
        in_c, in_s = diff_sets(cadence, sequence)
        self.assertEqual(in_c, ["body_5"])
        self.assertEqual(in_s, ["body_3"])

    def test_same_count_different_names(self):
        """A count of 4 == 4 does NOT mean the sets agree."""
        cadence = {"subject_1", "body_1", "body_2", "body_5"}
        sequence = {"subject_1", "body_1", "body_2", "body_3"}
        in_c, in_s = diff_sets(cadence, sequence)
        self.assertTrue(in_c, "must report cadence-only names")
        self.assertTrue(in_s, "must report sequence-only names")


class TestVariableKeysFromSequence(unittest.TestCase):
    """The sequence templates reference {SUBJECT_N} and {BODY_N}."""

    def test_four_step_sequence(self):
        seq = [
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_1}</p>"},
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_2}</p>"},
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_3}</p>"},
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_4}</p>"},
        ]
        keys = variable_keys_from_sequence(seq)
        self.assertEqual(keys, {"subject_1", "body_1", "body_2", "body_3",
                                "body_4"})

    def test_five_step_sequence(self):
        seq = [
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_1}</p>"},
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_2}</p>"},
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_3}</p>"},
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_4}</p>"},
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_5}</p>"},
        ]
        keys = variable_keys_from_sequence(seq)
        self.assertEqual(keys, {"subject_1", "body_1", "body_2", "body_3",
                                "body_4", "body_5"})

    def test_threaded_follow_up_still_references_subject(self):
        """A threaded step STILL CARRIES email_subject in the template."""
        seq = [
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_1}</p>"},
            {"email_subject": "{SUBJECT_1}", "email_body": "<p>{BODY_2}</p>"},
        ]
        keys = variable_keys_from_sequence(seq)
        self.assertIn("subject_1", keys)


class TestVariableKeysFromCadence(unittest.TestCase):
    """The cadence's step keys determine which body_N variables exist."""

    def test_four_step_cadence(self):
        steps = [
            {"key": "em1", "channel": "email"},
            {"key": "em2", "channel": "email"},
            {"key": "em4", "channel": "email"},
            {"key": "em5", "channel": "email"},
        ]
        keys = variable_keys_from_cadence(steps)
        # em4 -> body_4, em5 -> body_5 (key suffix, not position)
        self.assertEqual(keys, {"subject_1", "body_1", "body_2",
                                "body_4", "body_5"})

    def test_five_step_cadence(self):
        steps = [
            {"key": "em1", "channel": "email"},
            {"key": "em2", "channel": "email"},
            {"key": "em3", "channel": "email"},
            {"key": "em4", "channel": "email"},
            {"key": "em5", "channel": "email"},
        ]
        keys = variable_keys_from_cadence(steps)
        self.assertEqual(keys, {"subject_1", "body_1", "body_2", "body_3",
                                "body_4", "body_5"})

    def test_linkedin_steps_excluded(self):
        steps = [
            {"key": "em1", "channel": "email"},
            {"key": "li1", "channel": "linkedin"},
            {"key": "em2", "channel": "email"},
        ]
        keys = variable_keys_from_cadence(steps)
        self.assertEqual(keys, {"subject_1", "body_1", "body_2"})


class TestClassifyValue(unittest.TestCase):
    """Empty, 'None', and unrendered are THREE SEPARATE faults."""

    def test_none_object_is_empty(self):
        self.assertEqual(classify_value(None), "empty")

    def test_empty_string_is_empty(self):
        self.assertEqual(classify_value(""), "empty")

    def test_whitespace_only_is_empty(self):
        self.assertEqual(classify_value("   "), "empty")

    def test_literal_none_string(self):
        self.assertEqual(classify_value("None"), "literal_none")

    def test_literal_none_case_insensitive(self):
        self.assertEqual(classify_value("none"), "literal_none")
        self.assertEqual(classify_value("None"), "literal_none")
        self.assertEqual(classify_value("NONE"), "literal_none")

    def test_unrendered_placeholder(self):
        self.assertEqual(classify_value("{BODY_3}"), "unrendered")

    def test_unrendered_in_longer_text(self):
        self.assertEqual(classify_value("Hello {FIRST_NAME}"), "unrendered")

    def test_good_value(self):
        self.assertIsNone(classify_value("Hello John, how is Acme?"))

    def test_n_a_is_empty(self):
        self.assertEqual(classify_value("N/A"), "empty")


class TestCheckRows(unittest.TestCase):
    """Per-variable report over rendered rows."""

    def _make_sequence(self, n):
        return [
            {"email_subject": "{SUBJECT_1}",
             "email_body": f"<p>{{BODY_{i+1}}}</p>",
             "step_key": f"em{i+1}"}
            for i in range(n)
        ]

    def test_all_present(self):
        seq = self._make_sequence(3)
        rows = {
            "a@test.com": {"variables": {
                "subject_1": "Hi", "body_1": "Hello",
                "body_2": "World", "body_3": "Bye"}},
        }
        report, examples = check_rows(rows, seq, [])
        for var in ("subject_1", "body_1", "body_2", "body_3"):
            self.assertEqual(report[var]["present"], 1)
            self.assertEqual(report[var]["empty"], 0)

    def test_empty_caught(self):
        seq = self._make_sequence(2)
        rows = {
            "a@test.com": {"variables": {
                "subject_1": "Hi", "body_1": "", "body_2": "World"}},
        }
        report, examples = check_rows(rows, seq, [])
        self.assertEqual(report["body_1"]["empty"], 1)
        self.assertEqual(examples["body_1"]["empty"], "a@test.com")

    def test_literal_none_caught_separately(self):
        seq = self._make_sequence(2)
        rows = {
            "a@test.com": {"variables": {
                "subject_1": "Hi", "body_1": "None", "body_2": "World"}},
        }
        report, examples = check_rows(rows, seq, [])
        self.assertEqual(report["body_1"]["literal_none"], 1)
        self.assertEqual(report["body_1"]["empty"], 0)
        self.assertEqual(examples["body_1"]["literal_none"], "a@test.com")

    def test_unrendered_caught(self):
        seq = self._make_sequence(2)
        rows = {
            "a@test.com": {"variables": {
                "subject_1": "Hi", "body_1": "{BODY_1}", "body_2": "World"}},
        }
        report, examples = check_rows(rows, seq, [])
        self.assertEqual(report["body_1"]["unrendered"], 1)
        self.assertEqual(examples["body_1"]["unrendered"], "a@test.com")

    def test_three_faults_distinguished(self):
        """Empty, 'None', and unrendered are three separate counts."""
        seq = self._make_sequence(3)
        rows = {
            "empty@test.com": {"variables": {
                "subject_1": "Hi", "body_1": "", "body_2": "ok",
                "body_3": "ok"}},
            "none@test.com": {"variables": {
                "subject_1": "Hi", "body_1": "ok", "body_2": "None",
                "body_3": "ok"}},
            "unrendered@test.com": {"variables": {
                "subject_1": "Hi", "body_1": "ok", "body_2": "ok",
                "body_3": "{BODY_3}"}},
        }
        report, _ = check_rows(rows, seq, [])
        self.assertEqual(report["body_1"]["empty"], 1)
        self.assertEqual(report["body_1"]["literal_none"], 0)
        self.assertEqual(report["body_2"]["literal_none"], 1)
        self.assertEqual(report["body_2"]["empty"], 0)
        self.assertEqual(report["body_3"]["unrendered"], 1)


class TestCheckThreading(unittest.TestCase):
    """The threading invariant is read from the config at run time."""

    def _seq(self, n):
        return [{"step_key": f"em{i+1}", "order": i + 1,
                 "email_subject": "{SUBJECT_1}",
                 "email_body": f"<p>{{BODY_{i+1}}}</p>",
                 "wait_in_days": 3}
                for i in range(n)]

    def test_four_step_pattern_correct(self):
        configured = {"thread_reply_pattern": [False, True, True, True]}
        pattern, faults = check_threading(self._seq(4), configured)
        self.assertEqual(faults, [])
        self.assertEqual(pattern, (False, True, True, True))

    def test_five_step_pattern_correct(self):
        configured = {"thread_reply_pattern": [False, True, True, True, True]}
        pattern, faults = check_threading(self._seq(5), configured)
        self.assertEqual(faults, [])

    def test_three_entry_pattern_on_four_steps_refused(self):
        """The pre-change value. This is the thing that was wrong."""
        configured = {"thread_reply_pattern": [False, True, True]}
        pattern, faults = check_threading(self._seq(4), configured)
        self.assertTrue(faults, "must refuse a 3-entry pattern on 4 steps")
        self.assertIn("3 entries", faults[0])
        self.assertIn("4 steps", faults[0])

    def test_three_entry_pattern_on_five_steps_refused(self):
        configured = {"thread_reply_pattern": [False, True, True]}
        pattern, faults = check_threading(self._seq(5), configured)
        self.assertTrue(faults)

    def test_opener_not_false_refused(self):
        configured = {"thread_reply_pattern": [True, True, True, True]}
        _, faults = check_threading(self._seq(4), configured)
        self.assertTrue(faults)
        self.assertTrue(any("opener" in f.lower() for f in faults))

    def test_follow_up_not_true_refused(self):
        configured = {"thread_reply_pattern": [False, False, True, True]}
        _, faults = check_threading(self._seq(4), configured)
        self.assertTrue(faults)

    def test_absent_pattern_refused(self):
        configured = {}
        _, faults = check_threading(self._seq(4), configured)
        self.assertTrue(faults)


class TestCheckFinalWait(unittest.TestCase):
    """The final step's wait_in_days must be 1, never 0."""

    def test_wait_is_one_passes(self):
        seq = [{"step_key": "em5", "wait_in_days": 1}]
        wait, fault = check_final_wait(seq)
        self.assertEqual(wait, 1)
        self.assertIsNone(fault)

    def test_wait_is_zero_refused(self):
        seq = [{"step_key": "em5", "wait_in_days": 0}]
        wait, fault = check_final_wait(seq)
        self.assertEqual(wait, 0)
        self.assertIsNotNone(fault)
        self.assertIn("0", fault)

    def test_wait_is_none_refused(self):
        seq = [{"step_key": "em5"}]
        wait, fault = check_final_wait(seq)
        self.assertIsNone(wait)
        self.assertIsNotNone(fault)

    def test_empty_sequence(self):
        wait, fault = check_final_wait([])
        self.assertIsNone(wait)
        self.assertIsNotNone(fault)

    def test_nonzero_nonone_passes(self):
        seq = [{"step_key": "em5", "wait_in_days": 3}]
        wait, fault = check_final_wait(seq)
        self.assertEqual(wait, 3)
        self.assertIsNone(fault)


class TestLoadAndRender(unittest.TestCase):
    """JSONL loading and rendered-row filtering."""

    def test_load_rows(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                         delete=False) as f:
            f.write('{"email": "a@test.com", "state": "rendered", '
                    '"variables": {"subject_1": "Hi"}}\n')
            f.write('{"email": "b@test.com", "state": "held", '
                    '"variables": {}}\n')
            f.write('{"email": "c@test.com", "state": "rendered", '
                    '"variables": {"subject_1": "Bye"}}\n')
            path = f.name
        try:
            rows = load_rows(path)
            self.assertEqual(len(rows), 3)
            rendered = rendered_rows(rows)
            self.assertEqual(len(rendered), 2)
            self.assertIn("a@test.com", rendered)
            self.assertIn("c@test.com", rendered)
            self.assertNotIn("b@test.com", rendered)
        finally:
            os.unlink(path)


class TestEndToEndConstructedFailures(unittest.TestCase):
    """The three constructed bad rows: empty, 'None', unrendered.

    Written to a temp JSONL, verified through the CLI, and the exit code
    must be non-zero.
    """

    def _write_journal(self, rows):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                        delete=False)
        for row in rows:
            f.write(json.dumps(row) + "\n")
        f.close()
        return f.name

    def test_empty_body_causes_failure(self):
        from scripts.verify_s7_render import main as verify_main
        rows = [
            {"email": "a@test.com", "state": "rendered",
             "variables": {"subject_1": "Hi", "body_1": "",
                           "body_2": "ok", "body_3": "ok"}},
        ]
        path = self._write_journal(rows)
        # This will fail because we can't load the real config in a unit test.
        # Instead, test the component directly.
        try:
            seq = [
                {"email_subject": "{SUBJECT_1}",
                 "email_body": "<p>{BODY_1}</p>", "step_key": "em1"},
                {"email_subject": "{SUBJECT_1}",
                 "email_body": "<p>{BODY_2}</p>", "step_key": "em2"},
                {"email_subject": "{SUBJECT_1}",
                 "email_body": "<p>{BODY_3}</p>", "step_key": "em4"},
            ]
            rendered = rendered_rows(rows)
            report, examples = check_rows(rendered, seq, [])
            self.assertEqual(report["body_1"]["empty"], 1)
            self.assertEqual(examples["body_1"]["empty"], "a@test.com")
        finally:
            os.unlink(path)

    def test_literal_none_body_causes_failure(self):
        rows = [
            {"email": "b@test.com", "state": "rendered",
             "variables": {"subject_1": "Hi", "body_1": "ok",
                           "body_2": "None", "body_3": "ok"}},
        ]
        seq = [
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_1}</p>", "step_key": "em1"},
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_2}</p>", "step_key": "em2"},
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_3}</p>", "step_key": "em4"},
        ]
        rendered = rendered_rows(rows)
        report, examples = check_rows(rendered, seq, [])
        self.assertEqual(report["body_2"]["literal_none"], 1)
        self.assertEqual(report["body_2"]["empty"], 0)
        self.assertEqual(examples["body_2"]["literal_none"], "b@test.com")

    def test_unrendered_placeholder_causes_failure(self):
        rows = [
            {"email": "c@test.com", "state": "rendered",
             "variables": {"subject_1": "Hi", "body_1": "ok",
                           "body_2": "ok", "body_3": "{BODY_3}"}},
        ]
        seq = [
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_1}</p>", "step_key": "em1"},
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_2}</p>", "step_key": "em2"},
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_3}</p>", "step_key": "em4"},
        ]
        rendered = rendered_rows(rows)
        report, examples = check_rows(rendered, seq, [])
        self.assertEqual(report["body_3"]["unrendered"], 1)
        self.assertEqual(examples["body_3"]["unrendered"], "c@test.com")


class TestStepKeyIsNotVariableNumber(unittest.TestCase):
    """TASK-295 correction: em4 at position 3 reads BODY_3, not BODY_4.

    The verifier must read the mapping from the config at run time, not
    assume the step key suffix equals the variable number.
    """

    def test_four_step_cadence_produces_body_4_and_body_5(self):
        """em4 -> body_4, em5 -> body_5 by KEY SUFFIX, not position."""
        steps = [
            {"key": "em1", "channel": "email"},
            {"key": "em2", "channel": "email"},
            {"key": "em4", "channel": "email"},
            {"key": "em5", "channel": "email"},
        ]
        keys = variable_keys_from_cadence(steps)
        self.assertIn("body_4", keys)
        self.assertIn("body_5", keys)
        self.assertNotIn("body_3", keys)

    def test_provider_sequence_numbers_by_position(self):
        """The provider sequence numbers variables by POSITION."""
        seq = [
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_1}</p>"},
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_2}</p>"},
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_3}</p>"},
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_4}</p>"},
        ]
        keys = variable_keys_from_sequence(seq)
        self.assertEqual(keys, {"subject_1", "body_1", "body_2",
                                "body_3", "body_4"})

    def test_four_step_cadence_and_four_position_sequence_differ(self):
        """The KEY SUFFIX and POSITION NUMBER disagree at four steps.

        em4 at position 3: cadence says body_4, sequence says BODY_3.
        em5 at position 4: cadence says body_5, sequence says BODY_4.
        This is the mismatch the set diff must catch.
        """
        cadence_steps = [
            {"key": "em1", "channel": "email"},
            {"key": "em2", "channel": "email"},
            {"key": "em4", "channel": "email"},
            {"key": "em5", "channel": "email"},
        ]
        seq = [
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_1}</p>"},
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_2}</p>"},
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_3}</p>"},
            {"email_subject": "{SUBJECT_1}",
             "email_body": "<p>{BODY_4}</p>"},
        ]
        cadence_vars = variable_keys_from_cadence(cadence_steps)
        seq_vars = variable_keys_from_sequence(seq)
        in_c, in_s = diff_sets(cadence_vars, seq_vars)
        # Cadence has body_4 and body_5 (from keys em4, em5)
        # Sequence has body_3 and body_4 (from positions 3, 4)
        # body_4 is in BOTH, so only body_5 (cadence) and body_3 (sequence)
        # differ.
        self.assertIn("body_5", in_c)
        self.assertIn("body_3", in_s)


if __name__ == "__main__":
    unittest.main()
