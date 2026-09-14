#!/usr/bin/env python3
"""Tests for the ladder impact analysis script.

Drives the analysis through the real entry point (analyze_record) with
fixture records that mirror the production data structure. Asserts on
counts, not source text.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.ladder_impact import (
    analyze_record, analyze_queue, _ladder_changed, _position_in_channel,
    EMAIL_CHANGED_RUNGS, LINKEDIN_CHANGED_RUNGS,
)
from src import cadencelibrary, approval


def _make_record(rec_id, contacts, cadence_data, sequence=None):
    """Build a minimal record matching the production structure."""
    rec = {
        "id": rec_id,
        "state": "approved",
        "client": "productive",
        "cadence": cadence_data,
        "contacts": contacts,
        "events": [],
    }
    return rec


def _make_contact(key, name="Test Contact", linkedin=None, email=None):
    c = {"key": key, "name": name}
    if linkedin:
        c["linkedin"] = linkedin
    if email:
        c["email"] = email
    return c


def _make_step(channel, approval_fingerprint=None, **kwargs):
    step = {"channel": channel}
    step.update(kwargs)
    if approval_fingerprint:
        step["approval"] = {"fingerprint": approval_fingerprint}
    return step


class TestLadderChanged(unittest.TestCase):
    """Which rungs changed."""

    def test_email_rung_1_changed(self):
        self.assertTrue(_ladder_changed("email", 1))

    def test_email_rung_2_unchanged(self):
        self.assertFalse(_ladder_changed("email", 2))

    def test_email_rung_3_changed(self):
        self.assertTrue(_ladder_changed("email", 3))

    def test_email_rung_4_changed(self):
        self.assertTrue(_ladder_changed("email", 4))

    def test_email_rung_5_unchanged(self):
        self.assertFalse(_ladder_changed("email", 5))

    def test_linkedin_all_rungs_changed(self):
        for rung in range(1, 7):
            self.assertTrue(
                _ladder_changed("linkedin", rung),
                f"LinkedIn rung {rung} should be changed")

    def test_unknown_channel_not_changed(self):
        self.assertFalse(_ladder_changed("sms", 1))


class TestPositionInChannel(unittest.TestCase):
    """Step position resolution within a sequence."""

    def test_email_position(self):
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        channel, ordinal = _position_in_channel(seq, "em1")
        self.assertEqual(channel, "email")
        self.assertEqual(ordinal, 1)

    def test_email_position_em3(self):
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        channel, ordinal = _position_in_channel(seq, "em3")
        self.assertEqual(channel, "email")
        self.assertEqual(ordinal, 3)

    def test_linkedin_position(self):
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        channel, ordinal = _position_in_channel(seq, "li2")
        self.assertEqual(channel, "linkedin")
        self.assertEqual(ordinal, 2)

    def test_missing_step_returns_none(self):
        seq = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1
        channel, ordinal = _position_in_channel(seq, "nonexistent")
        self.assertIsNone(channel)
        self.assertIsNone(ordinal)


class TestAnalyzeRecord(unittest.TestCase):
    """Full record analysis with fixture data."""

    def test_affected_email_steps_detected(self):
        """Email steps on changed rungs (1, 3, 4) are flagged."""
        rec = _make_record(
            "test-1",
            [_make_contact("alice")],
            {"alice": {
                "em1": _make_step("email", "fp1", subject="s1", body="b1"),
                "em2": _make_step("email", "fp2", subject="s2", body="b2"),
                "em3": _make_step("email", "fp3", subject="s3", body="b3"),
            }})
        result = analyze_record(rec)
        affected_keys = {s["step"] for s in result["affected"]}
        # em1 (rung 1) and em3 (rung 3) changed; em2 (rung 2) did not
        self.assertIn("em1", affected_keys)
        self.assertIn("em3", affected_keys)
        self.assertNotIn("em2", affected_keys)

    def test_unaffected_email_rung_5(self):
        """Email rung 5 was NOT changed (TASK-047 invariant)."""
        rec = _make_record(
            "test-2",
            [_make_contact("bob")],
            {"bob": {
                "em5": _make_step("email", "fp5", subject="s5", body="b5"),
            }})
        result = analyze_record(rec)
        affected_keys = {s["step"] for s in result["affected"]}
        self.assertNotIn("em5", affected_keys)

    def test_all_linkedin_steps_affected(self):
        """All 6 LinkedIn rungs changed."""
        steps = {}
        for i in range(1, 7):
            steps[f"li{i}"] = _make_step(
                "linkedin", f"fpli{i}", note=f"note {i}")
        rec = _make_record(
            "test-3",
            [_make_contact("carol", linkedin="linkedin.com/carol")],
            {"carol": steps})
        result = analyze_record(rec)
        affected_keys = {s["step"] for s in result["affected"]}
        for i in range(1, 7):
            self.assertIn(f"li{i}", affected_keys)

    def test_approval_counting(self):
        """Steps with current approvals are counted separately."""
        rec = _make_record(
            "test-4",
            [_make_contact("dave")],
            {"dave": {
                "em1": _make_step("email", "fp1", subject="s", body="b"),
                "em3": _make_step("email", None, subject="s", body="b"),
            }})
        result = analyze_record(rec)
        with_approval = [s for s in result["affected"] if s["has_approval"]]
        # em1 has approval, em3 does not
        self.assertEqual(len(with_approval), 1)
        self.assertEqual(with_approval[0]["step"], "em1")

    def test_template_steps_not_counted(self):
        """Steps without stored copy (templates) are not counted."""
        rec = _make_record(
            "test-5",
            [_make_contact("eve")],
            {"eve": {
                "li1": _make_step("linkedin"),  # no note = template
            }})
        result = analyze_record(rec)
        self.assertEqual(len(result["affected"]), 0)
        self.assertEqual(len(result["non_generated"]), 1)

    def test_full_campaign_481_shape(self):
        """9 contacts x 5 email steps, 3 rungs changed = 27 affected."""
        cadence_data = {}
        for i in range(9):
            contact_key = f"contact-{i}"
            cadence_data[contact_key] = {
                f"em{j}": _make_step(
                    "email", f"fp{j}",
                    subject=f"subject {j}", body=f"body {j}")
                for j in range(1, 6)
            }
        contacts = [_make_contact(f"contact-{i}", email=f"c{i}@test.test")
                     for i in range(9)]
        rec = _make_record("campaign-481-sim", contacts, cadence_data)
        result = analyze_record(rec)
        # 9 contacts x 3 changed rungs (1, 3, 4) = 27
        self.assertEqual(len(result["affected"]), 27)

    def test_full_linkedin_shape(self):
        """15 contacts x 5 generated LinkedIn steps (li2-li6) = 75."""
        cadence_data = {}
        for i in range(15):
            contact_key = f"contact-{i}"
            steps = {}
            # li1 is template (no note) for the connect path
            steps["li1"] = _make_step("linkedin")
            for j in range(2, 7):
                steps[f"li{j}"] = _make_step(
                    "linkedin", f"fp{j}", note=f"note {j}")
            cadence_data[contact_key] = steps
        contacts = [_make_contact(f"contact-{i}",
                                   linkedin=f"linkedin.com/in/c{i}")
                     for i in range(15)]
        rec = _make_record("heyreach-599020-sim", contacts, cadence_data)
        result = analyze_record(rec)
        # 15 contacts x 5 generated steps (li2-li6) = 75
        self.assertEqual(len(result["affected"]), 75)


class TestAnalyzeQueue(unittest.TestCase):
    """Queue-level analysis."""

    def test_queue_summary(self):
        """Summary counts are correct across multiple records."""
        recs = [
            _make_record(
                "r1",
                [_make_contact("a")],
                {"a": {"em1": _make_step("email", "fp", subject="s", body="b")}}),
            _make_record(
                "r2",
                [_make_contact("b")],
                {"b": {"em5": _make_step("email", "fp", subject="s", body="b")}}),
        ]
        result = analyze_queue(recs)
        self.assertEqual(result["summary"]["total_records"], 2)
        self.assertEqual(result["summary"]["records_with_affected_steps"], 1)
        self.assertEqual(result["summary"]["total_affected_steps"], 1)

    def test_empty_queue(self):
        result = analyze_queue([])
        self.assertEqual(result["summary"]["total_records"], 0)
        self.assertEqual(result["summary"]["total_affected_steps"], 0)


class TestCallerChain(unittest.TestCase):
    """Verify the analysis uses the real cadence resolution path.

    QWEN.md rule: existence is not function. The analysis must go through
    cadencelibrary sequences, not a parallel representation.
    """

    def test_uses_cadencelibrary_sequence(self):
        """analyze_record resolves steps against the real sequence."""
        rec = _make_record(
            "chain-test",
            [_make_contact("x")],
            {"x": {
                "em1": _make_step("email", "fp", subject="s", body="b"),
                "li2": _make_step("linkedin", "fp", note="n"),
            }})
        result = analyze_record(rec)
        # The sequence keys should match PRODUCTIVE_LI_HEAVY_V1
        expected_keys = [s["key"] for s in cadencelibrary.PRODUCTIVE_LI_HEAVY_V1]
        self.assertEqual(result["sequence_keys"], expected_keys)

    def test_ladder_registry_is_the_source(self):
        """The changed rung constants match the actual ladder lengths."""
        self.assertEqual(
            len(cadencelibrary.EMAIL_FIVE_LADDER), 5)
        self.assertEqual(
            len(cadencelibrary.LINKEDIN_DEFAULT_LADDER), 6)
        # Changed rungs are within bounds
        for rung in EMAIL_CHANGED_RUNGS:
            self.assertLessEqual(rung, len(cadencelibrary.EMAIL_FIVE_LADDER))
        for rung in LINKEDIN_CHANGED_RUNGS:
            self.assertLessEqual(rung,
                                 len(cadencelibrary.LINKEDIN_DEFAULT_LADDER))


if __name__ == "__main__":
    unittest.main()
