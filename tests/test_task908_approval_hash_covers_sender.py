"""TASK-908: the approval hash must cover the sender.

The approval hash binds what the operator approved.  TASK-906 composed
a signature into every prospect-facing body, so two plans with the same
hash but different senders now produce different copy.  The hash must
move when the sender changes.

Acceptance:
1. Hash CHANGES when the sender changes (per-contact).
2. Hash is STABLE when nothing changes.
3. P.S. coverage still works (change P.S., hash changes).
4. Negative control: a plan with no sender still hashes; two senderless
   plans that are otherwise identical hash identically.
5. Plan-level sender is also covered (the production path).
"""
import copy
import unittest

from src import sequenceplan


def _base_plan():
    return {
        "client": "c",
        "account": {"company": "A", "domain": "a.test"},
        "strategy": {"strategy_id": "s"},
        "contacts": [{
            "email": "x@y.z",
            "sequences": {"em1": "body", "ps_em1": "P.S. one"},
            "subjects": {"em1": "subj"},
        }],
    }


class TestApprovalHashCoversSender(unittest.TestCase):

    def test_sender_change_moves_hash_per_contact(self):
        """Acceptance 1: different sender on the contact -> different hash."""
        a = _base_plan()
        a["contacts"][0]["sender"] = "anna@productive.io"
        b = _base_plan()
        b["contacts"][0]["sender"] = "other@productive.io"
        self.assertNotEqual(
            sequenceplan.approval_hash(a),
            sequenceplan.approval_hash(b),
            "hash must change when the per-contact sender changes")

    def test_stable_when_nothing_changes(self):
        """Acceptance 2: same plan twice, same hash."""
        p = _base_plan()
        p["contacts"][0]["sender"] = "anna@productive.io"
        h1 = sequenceplan.approval_hash(p)
        h2 = sequenceplan.approval_hash(copy.deepcopy(p))
        self.assertEqual(h1, h2, "hash must be stable across identical plans")

    def test_ps_still_moves_hash(self):
        """Acceptance 3: P.S. coverage that already works must keep working."""
        a = _base_plan()
        b = copy.deepcopy(a)
        b["contacts"][0]["sequences"]["ps_em1"] = "P.S. two"
        self.assertNotEqual(
            sequenceplan.approval_hash(a),
            sequenceplan.approval_hash(b),
            "changing the P.S. must still change the hash")

    def test_no_sender_still_hashes(self):
        """Acceptance 4: a plan with no sender must still hash."""
        p = _base_plan()
        h = sequenceplan.approval_hash(p)
        self.assertTrue(h, "hash must be non-empty for a senderless plan")

    def test_two_senderless_plans_hash_identically(self):
        """Acceptance 4: two senderless plans, same hash."""
        a = _base_plan()
        b = copy.deepcopy(a)
        self.assertEqual(
            sequenceplan.approval_hash(a),
            sequenceplan.approval_hash(b),
            "two senderless identical plans must hash the same")

    def test_plan_level_sender_moves_hash(self):
        """Acceptance 5 (production path): plan-level sender is covered."""
        a = _base_plan()
        a["sender"] = {"name": "Anna Kowalski"}
        b = copy.deepcopy(a)
        b["sender"] = {"name": "Other Person"}
        self.assertNotEqual(
            sequenceplan.approval_hash(a),
            sequenceplan.approval_hash(b),
            "hash must change when the plan-level sender changes")

    def test_plan_level_sender_stable(self):
        """Plan-level sender: same plan, same hash."""
        a = _base_plan()
        a["sender"] = {"name": "Anna Kowalski"}
        h1 = sequenceplan.approval_hash(a)
        h2 = sequenceplan.approval_hash(copy.deepcopy(a))
        self.assertEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()
