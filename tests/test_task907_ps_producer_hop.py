"""TASK-907: the P.S. producer hop in _candidate_steps.

Tests that _candidate_steps carries ps_em1/ps_em3 from the generation
result's sequences onto the step dict, so TASK-560's consumer can read it.

THE PRODUCTION PATH:
    generate_campaign.py produces ps_em1/ps_em3 in sequences
    -> _candidate_steps puts ps on the step dict   <-- THIS HOP
    -> bisonfactory._approved_copy reads step["ps"] (TASK-560)
    -> render / variables_for append it to the body
"""
import unittest


class CandidateStepsCarriesPs(unittest.TestCase):
    """_candidate_steps puts ps from sequences onto the step dict."""

    def _make_sequence(self):
        """A five-step email cadence sequence."""
        return [
            {"key": "em1", "channel": "email", "day": 1,
             "generated": True},
            {"key": "em2", "channel": "email", "day": 4,
             "generated": True},
            {"key": "em3", "channel": "email", "day": 8,
             "generated": True},
            {"key": "em4", "channel": "email", "day": 12,
             "generated": True},
            {"key": "em5", "channel": "email", "day": 21,
             "generated": True},
        ]

    def _make_contact_result(self, with_ps=True):
        """A writer result with bodies and optionally P.S. values."""
        sequences = {
            "em1": "Jacob, the visibility gap at Northbridge.",
            "em2": "Jacob, a different angle on the numbers.",
            "em3": "Jacob, Productive joins up the view.",
            "em4": "Jacob, following up on visibility.",
            "em5": "Jacob, should I close the file?",
        }
        if with_ps:
            sequences["ps_em1"] = (
                "P.S. A live project view might help."
            )
            sequences["ps_em3"] = (
                "P.S. Productive is the name."
            )
        return {
            "contact_key": "jacob-hartley",
            "sequences": sequences,
            "subjects": {"A": "Your visibility gap", "B": "What joins up",
                         "C": "Should I close?"},
        }

    def _make_contact(self):
        return {
            "key": "jacob-hartley",
            "email": "j.hartley@example.com",
            "linkedin": "https://linkedin.example.com/in/jh",
        }

    def _make_rec(self):
        return {
            "id": "rec-001",
            "contacts": [self._make_contact()],
        }

    def test_em1_carries_ps_value_from_sequences(self):
        """END TO END: em1 step dict has the P.S. VALUE from sequences."""
        from src.generate import _candidate_steps
        cr = self._make_contact_result(with_ps=True)
        seq = self._make_sequence()
        pairs = _candidate_steps(cr, seq)
        steps = {k: v for k, v in pairs}
        em1 = steps["em1"]
        self.assertIn("ps", em1)
        self.assertEqual(em1["ps"],
                         "P.S. A live project view might help.")

    def test_em3_carries_ps_value_from_sequences(self):
        """em3 step dict has the P.S. VALUE, not just a key."""
        from src.generate import _candidate_steps
        cr = self._make_contact_result(with_ps=True)
        seq = self._make_sequence()
        pairs = _candidate_steps(cr, seq)
        steps = {k: v for k, v in pairs}
        em3 = steps["em3"]
        self.assertIn("ps", em3)
        self.assertEqual(em3["ps"], "P.S. Productive is the name.")

    def test_em2_has_no_ps_key(self):
        """em2 never had a P.S. - the key must be ABSENT, not empty."""
        from src.generate import _candidate_steps
        cr = self._make_contact_result(with_ps=True)
        seq = self._make_sequence()
        pairs = _candidate_steps(cr, seq)
        steps = {k: v for k, v in pairs}
        em2 = steps["em2"]
        self.assertNotIn("ps", em2)

    def test_em4_em5_have_no_ps_key(self):
        """em4 and em5 also have no P.S. - absent, not empty."""
        from src.generate import _candidate_steps
        cr = self._make_contact_result(with_ps=True)
        seq = self._make_sequence()
        pairs = _candidate_steps(cr, seq)
        steps = {k: v for k, v in pairs}
        self.assertNotIn("ps", steps["em4"])
        self.assertNotIn("ps", steps["em5"])

    def test_no_ps_in_sequences_means_no_ps_on_step(self):
        """When sequences has no ps_em1/ps_em3, steps have no ps key."""
        from src.generate import _candidate_steps
        cr = self._make_contact_result(with_ps=False)
        seq = self._make_sequence()
        pairs = _candidate_steps(cr, seq)
        steps = {k: v for k, v in pairs}
        self.assertNotIn("ps", steps["em1"])
        self.assertNotIn("ps", steps["em3"])

    def test_empty_ps_in_sequences_means_no_ps_on_step(self):
        """An empty ps_em1 in sequences does NOT put an empty ps on step."""
        from src.generate import _candidate_steps
        cr = self._make_contact_result(with_ps=True)
        cr["sequences"]["ps_em1"] = ""
        cr["sequences"]["ps_em3"] = ""
        seq = self._make_sequence()
        pairs = _candidate_steps(cr, seq)
        steps = {k: v for k, v in pairs}
        self.assertNotIn("ps", steps["em1"])
        self.assertNotIn("ps", steps["em3"])


class EndToEndPsReachesTheRenderedBody(unittest.TestCase):
    """Through the production path, P.S. reaches what a person receives.

    The full path (fixture -> bisonfactory._approved_copy -> _variables_for)
    is proven by test_render_preview.test_email_preview_renders_through_
    bisonfactory_variables_for and test_task560_ps_reaches_the_person.
    These tests prove the producer half of the chain.
    """

    def test_five_step_produces_ps_with_correct_fingerprint(self):
        """Five-step _candidate_steps produces ps with valid fingerprints.

        Uses five steps so _PLAN_EMAIL_ORDER applies (1:1 source mapping).
        The fingerprint computed over the step (including ps) is what
        _certified_copy will verify - proving the chain holds.
        """
        from src import approval as _approval
        from src.generate import _candidate_steps

        sequence = [
            {"key": "em1", "channel": "email", "day": 1,
             "generated": True},
            {"key": "em2", "channel": "email", "day": 4,
             "generated": True},
            {"key": "em3", "channel": "email", "day": 8,
             "generated": True},
            {"key": "em4", "channel": "email", "day": 12,
             "generated": True},
            {"key": "em5", "channel": "email", "day": 21,
             "generated": True},
        ]
        contact_result = {
            "contact_key": "test-contact",
            "sequences": {
                "em1": "Body one.",
                "em2": "Body two.",
                "em3": "Body three.",
                "em4": "Body four.",
                "em5": "Body five.",
                "ps_em1": "P.S. appended to one.",
                "ps_em3": "P.S. appended to three.",
            },
            "subjects": {"A": "Subject A", "B": "Subject B",
                         "C": "Subject C"},
        }
        pairs = _candidate_steps(contact_result, sequence)
        steps = {k: v for k, v in pairs}

        self.assertEqual(steps["em1"]["ps"], "P.S. appended to one.")
        self.assertEqual(steps["em3"]["ps"], "P.S. appended to three.")
        self.assertNotIn("ps", steps["em2"])
        self.assertNotIn("ps", steps["em4"])
        self.assertNotIn("ps", steps["em5"])

        fp_em1_with_ps = _approval.fingerprint(steps["em1"])
        step_without_ps = dict(steps["em1"])
        del step_without_ps["ps"]
        fp_em1_without_ps = _approval.fingerprint(step_without_ps)
        self.assertNotEqual(fp_em1_with_ps, fp_em1_without_ps,
                            "fingerprint must change when ps changes")


class FingerprintChangesWithPs(unittest.TestCase):
    """Acceptance 5: approval.fingerprint changes when P.S. changes."""

    def test_different_ps_different_fingerprint(self):
        from src import approval
        step_a = {"channel": "email", "subject": "S", "body": "B",
                  "ps": "P.S. version A"}
        step_b = {"channel": "email", "subject": "S", "body": "B",
                  "ps": "P.S. version B"}
        self.assertNotEqual(approval.fingerprint(step_a),
                            approval.fingerprint(step_b))

    def test_same_ps_same_fingerprint(self):
        from src import approval
        step = {"channel": "email", "subject": "S", "body": "B",
                "ps": "P.S. stable"}
        self.assertEqual(approval.fingerprint(step),
                         approval.fingerprint(step))

    def test_no_ps_vs_empty_ps_same_fingerprint(self):
        """Backward compat: no ps key and empty ps hash the same."""
        from src import approval
        step_no = {"channel": "email", "subject": "S", "body": "B"}
        step_empty = {"channel": "email", "subject": "S", "body": "B",
                      "ps": ""}
        self.assertEqual(approval.fingerprint(step_no),
                         approval.fingerprint(step_empty))


if __name__ == "__main__":
    unittest.main()
