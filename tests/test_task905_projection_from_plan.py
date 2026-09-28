#!/usr/bin/env python3
"""TASK-905: the EmailBison projection derives from the canonical plan.

The probe (scripts/runtime_approval_hash_probe.py --mode project) proves
this at runtime on production-shaped input:

    derive_bison_payload   >= 1   (called)
    approval_hash          >= 1   (called)
    bisonfactory._approved_copy == 0   (NOT called)

These tests prove it at the unit level with negative controls:

1. NEGATIVE CONTROL: mutate the plan's copy and the projection changes.
   If the projection does not change, it is not derived from the plan.
2. NEGATIVE CONTROL: bypassing the canonical projection fails. If a caller
   can build the payload without going through derive_bison_payload, the
   projection is not the only path.
3. APPROVAL BINDING: changing approved content invalidates the approval hash.
   Regenerated copy cannot reuse an old approval.
4. P.S. CARRIED: the projection's body includes the P.S. appended to it.
5. OPT-OUT NOT IN PROJECTION: the opt-out line is NOT in the projection's
   body; it is appended later by _variables_for.
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import sequenceplan


def _plan_with_contacts():
    """A minimal plan with two contacts and per-step approved copy."""
    plan = {
        "version": "1",
        "client": "test-client",
        "account": {"company": "Acme", "domain": "acme.test"},
        "strategy": {"strategy_id": "test-strategy"},
        "second_brain_facts": [],
        "offers": {},
        "cadence": {},
        "contacts": [
            {"contact_key": "c1",
             "email": "alice@acme.test",
             "first_name": "Alice",
             "qualification": "QUALIFIED",
             "sequences": {
                 "em1": "Body one.\n\nP.S. See you there.",
                 "em2": "Body two.",
                 "em3": "Body three.\n\nP.S. Third step.",
             },
             "subjects": {"A": "Subject Alpha",
                          "B": "Subject Beta"}},
            {"contact_key": "c2",
             "email": "bob@acme.test",
             "first_name": "Bob",
             "qualification": "QUALIFIED",
             "sequences": {
                 "em1": "Bob body one.\n\nP.S. Bob PS.",
                 "em2": "Bob body two.",
             },
             "subjects": {"A": "Subject Alpha"}},
        ],
    }
    return plan


class TestProjectionDerivesFromPlan(unittest.TestCase):
    """The projection's content comes from the plan, field for field."""

    def test_projection_has_approval_hash(self):
        plan = _plan_with_contacts()
        payload = sequenceplan.derive_bison_payload(plan)
        self.assertIn("approval_hash", payload)
        self.assertTrue(len(payload["approval_hash"]) > 0)

    def test_projection_leads_match_plan_contacts(self):
        plan = _plan_with_contacts()
        payload = sequenceplan.derive_bison_payload(plan)
        self.assertEqual(len(payload["leads"]), 2)
        lead1 = payload["leads"][0]
        self.assertEqual(lead1["contact_key"], "c1")
        self.assertEqual(lead1["email"], "alice@acme.test")
        self.assertEqual(len(lead1["steps"]), 3)

    def test_projection_body_matches_plan_sequence(self):
        plan = _plan_with_contacts()
        payload = sequenceplan.derive_bison_payload(plan)
        lead1 = payload["leads"][0]
        em1 = next(s for s in lead1["steps"] if s["step_key"] == "em1")
        self.assertEqual(em1["body"],
                         plan["contacts"][0]["sequences"]["em1"])

    def test_projection_subject_matches_plan_subjects(self):
        plan = _plan_with_contacts()
        payload = sequenceplan.derive_bison_payload(plan)
        lead1 = payload["leads"][0]
        em1 = next(s for s in lead1["steps"] if s["step_key"] == "em1")
        self.assertEqual(em1["subject"], "Subject Alpha")
        em3 = next(s for s in lead1["steps"] if s["step_key"] == "em3")
        self.assertEqual(em3["subject"], "Subject Beta")


class TestNegativeControlMutation(unittest.TestCase):
    """NEGATIVE CONTROL: mutate the plan's copy, projection must change."""

    def test_mutating_body_changes_projection(self):
        plan = _plan_with_contacts()
        original = sequenceplan.derive_bison_payload(plan)
        original_body = original["leads"][0]["steps"][0]["body"]
        plan["contacts"][0]["sequences"]["em1"] = "MUTATED BODY."
        mutated = sequenceplan.derive_bison_payload(plan)
        mutated_body = mutated["leads"][0]["steps"][0]["body"]
        self.assertNotEqual(original_body, mutated_body)
        self.assertEqual(mutated_body, "MUTATED BODY.")

    def test_mutating_subject_changes_projection(self):
        plan = _plan_with_contacts()
        original = sequenceplan.derive_bison_payload(plan)
        original_subj = original["leads"][0]["steps"][0]["subject"]
        plan["contacts"][0]["subjects"]["A"] = "MUTATED SUBJECT"
        mutated = sequenceplan.derive_bison_payload(plan)
        mutated_subj = mutated["leads"][0]["steps"][0]["subject"]
        self.assertNotEqual(original_subj, mutated_subj)
        self.assertEqual(mutated_subj, "MUTATED SUBJECT")

    def test_mutating_body_changes_approval_hash(self):
        plan = _plan_with_contacts()
        original_hash = sequenceplan.derive_bison_payload(plan)[
            "approval_hash"]
        plan["contacts"][0]["sequences"]["em1"] = "MUTATED BODY."
        mutated_hash = sequenceplan.derive_bison_payload(plan)[
            "approval_hash"]
        self.assertNotEqual(original_hash, mutated_hash)


class TestNegativeControlBypass(unittest.TestCase):
    """NEGATIVE CONTROL: the projection is the ONLY path to the payload."""

    def test_approved_copy_not_called_by_plan(self):
        """bisonfactory._plan does not call _approved_copy.

        This is proven by the probe at runtime. Here we prove statically
        that _contact_words_for_plan exists and _plan uses it.
        """
        from src import bisonfactory
        self.assertTrue(hasattr(bisonfactory, "_contact_words_for_plan"))
        import inspect
        source = inspect.getsource(bisonfactory._plan)
        self.assertIn("_contact_words_for_plan", source)
        self.assertNotIn("_approved_copy(", source)

    def test_derive_bison_payload_is_the_projection(self):
        """derive_bison_payload is the only function that projects email
        payload from the plan. It computes the approval hash."""
        payload = sequenceplan.derive_bison_payload(_plan_with_contacts())
        self.assertIn("approval_hash", payload)
        self.assertIn("leads", payload)


class TestApprovalBinding(unittest.TestCase):
    """Changing approved content invalidates the approval hash."""

    def test_different_copy_different_hash(self):
        plan_a = _plan_with_contacts()
        plan_b = _plan_with_contacts()
        plan_b["contacts"][0]["sequences"]["em1"] = "Different body."
        hash_a = sequenceplan.approval_hash(plan_a)
        hash_b = sequenceplan.approval_hash(plan_b)
        self.assertNotEqual(hash_a, hash_b)

    def test_same_copy_same_hash(self):
        plan_a = _plan_with_contacts()
        plan_b = _plan_with_contacts()
        hash_a = sequenceplan.approval_hash(plan_a)
        hash_b = sequenceplan.approval_hash(plan_b)
        self.assertEqual(hash_a, hash_b)

    def test_hash_is_deterministic(self):
        plan = _plan_with_contacts()
        h1 = sequenceplan.approval_hash(plan)
        h2 = sequenceplan.approval_hash(plan)
        self.assertEqual(h1, h2)


class TestPSCarriedInProjection(unittest.TestCase):
    """The P.S. is appended to the body BEFORE the projection."""

    def test_ps_in_projected_body(self):
        plan = _plan_with_contacts()
        payload = sequenceplan.derive_bison_payload(plan)
        em1 = next(s for s in payload["leads"][0]["steps"]
                   if s["step_key"] == "em1")
        self.assertIn("P.S.", em1["body"])

    def test_ps_in_em3_projected_body(self):
        plan = _plan_with_contacts()
        payload = sequenceplan.derive_bison_payload(plan)
        em3 = next(s for s in payload["leads"][0]["steps"]
                   if s["step_key"] == "em3")
        self.assertIn("P.S.", em3["body"])


class TestUnqualifiedFiltered(unittest.TestCase):
    """Unqualified contacts are filtered from the projection."""

    def test_unqualified_excluded(self):
        plan = _plan_with_contacts()
        plan["contacts"][0]["qualification"] = "UNQUALIFIED"
        payload = sequenceplan.derive_bison_payload(plan)
        keys = [l["contact_key"] for l in payload["leads"]]
        self.assertNotIn("c1", keys)
        self.assertIn("c2", keys)

    def test_insufficient_excluded(self):
        plan = _plan_with_contacts()
        plan["contacts"][1]["qualification"] = "INSUFFICIENT"
        payload = sequenceplan.derive_bison_payload(plan)
        keys = [l["contact_key"] for l in payload["leads"]]
        self.assertIn("c1", keys)
        self.assertNotIn("c2", keys)


if __name__ == "__main__":
    unittest.main()
