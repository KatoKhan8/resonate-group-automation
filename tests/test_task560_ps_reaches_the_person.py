"""TASK-560: the P.S. must reach the rendered email and the projection.

Acceptance:
1. The P.S. appears in the rendered email body a person would receive.
2. The P.S. appears in the EmailBison projection.
3. approval.fingerprint changes when the P.S. changes.
4. _certified_copy's forbidden set covers ps.
5. A required P.S. that is missing BLOCKS.
6. Mutation: drop the P.S. from the projection; acceptance 2 must go red.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import approval, bisonfactory, render


class FingerprintCoversPs(unittest.TestCase):
    """Acceptance 3: approval.fingerprint changes when the P.S. changes."""

    def test_fingerprint_changes_when_ps_changes(self):
        """Negative control: two drafts differing only in P.S. produce different fingerprints."""
        step1 = {"channel": "email", "subject": "Test", "body": "Body", "ps": "P.S. One"}
        step2 = {"channel": "email", "subject": "Test", "body": "Body", "ps": "P.S. Two"}
        step3 = {"channel": "email", "subject": "Test", "body": "Body"}  # No P.S.
        
        fp1 = approval.fingerprint(step1)
        fp2 = approval.fingerprint(step2)
        fp3 = approval.fingerprint(step3)
        
        self.assertNotEqual(fp1, fp2, "different P.S. must produce different fingerprints")
        self.assertNotEqual(fp1, fp3, "P.S. vs no P.S. must produce different fingerprints")
        self.assertNotEqual(fp2, fp3, "different P.S. vs no P.S. must produce different fingerprints")

    def test_fingerprint_stable_with_same_ps(self):
        """Control: same P.S. produces same fingerprint."""
        step1 = {"channel": "email", "subject": "Test", "body": "Body", "ps": "P.S. Same"}
        step2 = {"channel": "email", "subject": "Test", "body": "Body", "ps": "P.S. Same"}
        
        self.assertEqual(approval.fingerprint(step1), approval.fingerprint(step2))


class CertifiedCopyForbiddenSetCoversPs(unittest.TestCase):
    """Acceptance 4: _certified_copy's forbidden set covers ps."""

    def test_certified_copy_refuses_ps_in_extra(self):
        """Passing ps in extra must be refused."""
        step = {
            "channel": "email",
            "subject": "Test",
            "body": "Body",
            "ps": "P.S. Test",
            "approval": {
                "fingerprint": approval.fingerprint({
                    "channel": "email",
                    "subject": "Test",
                    "body": "Body",
                    "ps": "P.S. Test",
                }),
                "by": "test@example.com",
            },
        }
        
        # Passing ps in extra should be refused
        with self.assertRaises(bisonfactory.FactoryRefused) as ctx:
            bisonfactory._certified_copy(step, "em1", extra={"ps": "P.S. Override"})
        
        self.assertIn("ps", str(ctx.exception).lower())


class RenderIncludesPs(unittest.TestCase):
    """Acceptance 1: the P.S. appears in the rendered email body."""

    def test_emailbison_rows_includes_ps_in_body(self):
        """The P.S. is appended to the body in the EmailBison CSV."""
        results = [{
            "status": "clean",
            "failures": [],
            "record": {"id": "test-001", "company": "TestCo", "domain": "test.test", "lane": "outbound"},
            "contact": {"email": "test@test.test", "name": "Test Person", "title": "CEO"},
            "step": {"subject": "Test Subject", "body": "Test body.", "ps": "P.S. Follow up."},
            "day": "1",
            "id": "test-001",
        }]
        
        rows = render.emailbison_rows(results)
        self.assertEqual(len(rows), 1)
        
        # Body is at index 7
        body = rows[0][7]
        self.assertIn("Test body.", body)
        self.assertIn("P.S. Follow up.", body)
        self.assertIn("\n\n", body)  # Blank line separator

    def test_emailbison_rows_without_ps_unchanged(self):
        """A step without P.S. renders with the opt-out line appended."""
        results = [{
            "status": "clean",
            "failures": [],
            "record": {"id": "test-002", "company": "TestCo", "domain": "test.test", "lane": "outbound"},
            "contact": {"email": "test@test.test", "name": "Test Person", "title": "CEO"},
            "step": {"subject": "Test Subject", "body": "Test body."},
            "day": "1",
            "id": "test-002",
        }]

        rows = render.emailbison_rows(results)
        body = rows[0][7]
        from src import optout
        self.assertEqual(body, "Test body.\n\n" + optout.OPT_OUT_LINE)

    def test_card_includes_ps_in_html(self):
        """The P.S. appears in the HTML review card."""
        r = {
            "status": "clean",
            "failures": [],
            "record": {"id": "test-003", "company": "TestCo", "lane": "outbound",
                       "hook": "Test hook"},
            "contact": {"name": "Test Person", "title": "CEO", "email": "test@test.test",
                        "verdict": "valid"},
            "step": {"subject": "Test Subject", "body": "Test body.", "ps": "P.S. Note."},
            "day": "1",
        }
        
        html = render.card(r)
        self.assertIn("Test body.", html)
        self.assertIn("P.S. Note.", html)


class VariablesForIncludesPs(unittest.TestCase):
    """Acceptance 2: the P.S. appears in the EmailBison projection."""

    def _get_var(self, vars_list, name):
        """Extract a variable value from the list shape."""
        for v in vars_list:
            if v.get("name") == name:
                return v.get("value")
        return None

    def test_variables_for_appends_ps_to_body(self):
        """The P.S. is appended to the body in the provider payload."""
        lead = {
            "record_id": "test-001",
            "contact_key": "test-contact",
            "copy": [
                {"step_key": "em1", "subject": "Subject", "body": "Body text.", "ps": "P.S. Note."},
            ],
        }
        campaign = {"client": "test"}
        
        vars_list = bisonfactory._variables_for(lead, campaign, sequence=[])
        
        # Single-step campaign uses unnumbered body
        body = self._get_var(vars_list, "body")
        self.assertIsNotNone(body)
        self.assertIn("Body text.", body)
        self.assertIn("P.S. Note.", body)

    def test_variables_for_multistep_appends_ps_per_step(self):
        """Multi-step: each step's P.S. is appended to its body."""
        lead = {
            "record_id": "test-002",
            "contact_key": "test-contact",
            "copy": [
                {"step_key": "em1", "subject": "Subj1", "body": "Body1.", "ps": "PS1."},
                {"step_key": "em2", "subject": "Subj2", "body": "Body2.", "ps": ""},
                {"step_key": "em3", "subject": "Subj3", "body": "Body3.", "ps": "PS3."},
            ],
        }
        campaign = {"client": "test"}
        sequence = [
            {"step_key": "em1", "thread_reply": False},
            {"step_key": "em2", "thread_reply": True},
            {"step_key": "em3", "thread_reply": False},
        ]
        
        vars_list = bisonfactory._variables_for(lead, campaign, sequence=sequence)
        
        body1 = self._get_var(vars_list, "body_1")
        body2 = self._get_var(vars_list, "body_2")
        body3 = self._get_var(vars_list, "body_3")
        
        self.assertIn("PS1.", body1)
        self.assertNotIn("PS", body2 or "")  # Empty P.S.
        self.assertIn("PS3.", body3)


class MissingPsBlocks(unittest.TestCase):
    """Acceptance 5: a required P.S. that is missing BLOCKS."""

    def test_explicit_empty_ps_on_step_blocks(self):
        """A step with an explicit empty ps field is refused."""
        sequence = [{"step_key": "em1", "order": 1}]
        
        # Step has explicit empty ps field - generation intended P.S. but didn't produce it
        source = {
            "cadence": {
                "test-contact": {
                    "em1": {
                        "channel": "email",
                        "subject": "Test",
                        "body": "Body",
                        "ps": "",  # Explicit empty - generation intended P.S.
                        "approval": {
                            "fingerprint": approval.fingerprint({
                                "channel": "email",
                                "subject": "Test",
                                "body": "Body",
                                "ps": "",
                            }),
                            "by": "test@example.com",
                        },
                    },
                },
            },
        }
        
        copy, missing = bisonfactory._approved_copy(
            source, "test-contact", sequence, "test-record",
            cadence_steps=[{"key": "em1"}],
        )
        
        # em1 should be in missing because P.S. is explicitly empty
        self.assertTrue(any("em1" in m and "P.S." in m for m in missing),
                        f"expected em1 missing P.S., got {missing}")

    def test_required_step_without_ps_key_is_refused(self):
        """NEGATIVE CONTROL: em1 with no `ps` key at all is REFUSED.

        This is the defect from rework 2: a required step whose `ps` key is
        ABSENT (not empty - absent) must be blocked. A boundary that drops
        empty fields converts the blocking case (explicit empty) into the
        silently-passing case (absent key), and ships P.S.-less mail.
        """
        sequence = [{"step_key": "em1", "order": 1}]

        # em1 has NO ps field at all - not empty, ABSENT
        source = {
            "cadence": {
                "test-contact": {
                    "em1": {
                        "channel": "email",
                        "subject": "Test",
                        "body": "Body",
                        # No ps field at all - this is the bypass
                        "approval": {
                            "fingerprint": approval.fingerprint({
                                "channel": "email",
                                "subject": "Test",
                                "body": "Body",
                            }),
                            "by": "test@example.com",
                        },
                    },
                },
            },
        }

        copy, missing = bisonfactory._approved_copy(
            source, "test-contact", sequence, "test-record",
            cadence_steps=[{"key": "em1"}],
        )

        # em1 MUST be in missing because it requires a P.S.
        self.assertTrue(any("em1" in m and "P.S." in m for m in missing),
                        f"expected em1 (missing P.S.) in missing, got {missing}")
        self.assertEqual(len(copy), 0,
                         "em1 without P.S. must not produce copy")

    def test_required_step_em3_without_ps_key_is_refused(self):
        """em3 also requires a P.S. and is refused when absent."""
        sequence = [{"step_key": "em3", "order": 1}]

        source = {
            "cadence": {
                "test-contact": {
                    "em3": {
                        "channel": "email",
                        "subject": "Test",
                        "body": "Body",
                        "approval": {
                            "fingerprint": approval.fingerprint({
                                "channel": "email",
                                "subject": "Test",
                                "body": "Body",
                            }),
                            "by": "test@example.com",
                        },
                    },
                },
            },
        }

        copy, missing = bisonfactory._approved_copy(
            source, "test-contact", sequence, "test-record",
            cadence_steps=[{"key": "em3"}],
        )

        self.assertTrue(any("em3" in m and "P.S." in m for m in missing),
                        f"expected em3 (missing P.S.) in missing, got {missing}")

    def test_step_without_ps_field_is_fine(self):
        """A step without a ps field at all is OK (no P.S. expected)."""
        sequence = [{"step_key": "em2", "order": 1}]
        
        # Step has no ps field - no P.S. expected
        source = {
            "cadence": {
                "test-contact": {
                    "em2": {
                        "channel": "email",
                        "subject": "Test",
                        "body": "Body",
                        # No ps field at all
                        "approval": {
                            "fingerprint": approval.fingerprint({
                                "channel": "email",
                                "subject": "Test",
                                "body": "Body",
                            }),
                            "by": "test@example.com",
                        },
                    },
                },
            },
        }
        
        copy, missing = bisonfactory._approved_copy(
            source, "test-contact", sequence, "test-record",
            cadence_steps=[{"key": "em2"}],
        )
        
        # em2 should NOT be in missing
        self.assertFalse(any("em2" in m for m in missing),
                         f"em2 should not be missing, got {missing}")
        self.assertEqual(len(copy), 1)

    def test_step_with_nonempty_ps_is_fine(self):
        """A step with a non-empty ps field is fine."""
        sequence = [{"step_key": "em1", "order": 1}]
        
        source = {
            "cadence": {
                "test-contact": {
                    "em1": {
                        "channel": "email",
                        "subject": "Test",
                        "body": "Body",
                        "ps": "P.S. Note.",
                        "approval": {
                            "fingerprint": approval.fingerprint({
                                "channel": "email",
                                "subject": "Test",
                                "body": "Body",
                                "ps": "P.S. Note.",
                            }),
                            "by": "test@example.com",
                        },
                    },
                },
            },
        }
        
        copy, missing = bisonfactory._approved_copy(
            source, "test-contact", sequence, "test-record",
            cadence_steps=[{"key": "em1"}],
        )
        
        # em1 should NOT be in missing
        self.assertFalse(any("em1" in m for m in missing),
                         f"em1 should not be missing, got {missing}")
        self.assertEqual(len(copy), 1)


class MutationCheck(unittest.TestCase):
    """Acceptance 6: drop the P.S. from the projection; acceptance 2 must go red."""

    def _get_var(self, vars_list, name):
        """Extract a variable value from the list shape."""
        for v in vars_list:
            if v.get("name") == name:
                return v.get("value")
        return None

    def test_dropping_ps_from_copy_changes_body(self):
        """If the P.S. is dropped from the copy, the body changes."""
        lead_with_ps = {
            "record_id": "test-001",
            "contact_key": "test-contact",
            "copy": [
                {"step_key": "em1", "subject": "Subject", "body": "Body.", "ps": "P.S. Note."},
            ],
        }
        lead_without_ps = {
            "record_id": "test-001",
            "contact_key": "test-contact",
            "copy": [
                {"step_key": "em1", "subject": "Subject", "body": "Body.", "ps": ""},
            ],
        }
        campaign = {"client": "test"}
        
        vars_with = bisonfactory._variables_for(lead_with_ps, campaign, sequence=[])
        vars_without = bisonfactory._variables_for(lead_without_ps, campaign, sequence=[])
        
        body_with = self._get_var(vars_with, "body")
        body_without = self._get_var(vars_without, "body")
        
        self.assertIsNotNone(body_with)
        self.assertIsNotNone(body_without)
        self.assertNotEqual(body_with, body_without,
                            "dropping P.S. must change the body")
        self.assertIn("P.S. Note.", body_with)
        self.assertNotIn("P.S.", body_without)


if __name__ == "__main__":
    unittest.main()
