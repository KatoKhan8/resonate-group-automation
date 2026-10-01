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
5. Plan-level sender is covered - AS A PROPERTY OF `approval_hash`, over a
   hand-written plan. See the correction below for what that does NOT prove.

CORRECTED 2026-09-30. Acceptance 5 was labelled "the production path" and
was not one: it injected `plan["sender"]` by hand, and `bisonfactory._plan` -
the only thing that builds a plan in production - never assigned that key.
Measured before the fix: the hash did not move across three different sender
identities on the real plan shape, while this file stayed green. A test that
supplies the very field the code under test fails to supply cannot fail for
the reason it exists.

The coverage is KEPT and RELABELLED - `approval_hash` reading a plan-level
sender is a real property of that function and worth pinning - and
`ProductionPlanShape` at the bottom of this file is the honest version:
it builds the plan through `bisonfactory._plan` and asserts the hash moves
across two sender identities with nothing injected.
"""
import copy
import unittest

from src import bisonfactory, sequenceplan, store
from tests.test_staging_a_campaign_twice_builds_one import CONFIG, record
from tests.test_staging_hands_the_sequence_gate_its_inputs import _StagingCase


def _config_with_sender(name, email):
    """The staging fixture's client file, with a sending identity.

    `CONFIG` declares no `sender:` block at all, which is the one case where
    the plan legitimately carries nothing - so a test about the sender has to
    supply a client that actually has one.
    """
    return dict(CONFIG, sender={"mode": "client_rep", "name": name,
                                "role": "founder", "company": "Productive",
                                "email": email})


ADA = _config_with_sender("Ada Lovelace", "ada@productive.test")
GRACE = _config_with_sender("Grace Hopper", "grace@productive.test")


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
        """Acceptance 5, CORRECTED LABEL: a property of `approval_hash` only.

        This injects `plan["sender"]`, so it proves the hash READS a
        plan-level sender. It proves nothing about whether anything in
        production WRITES one - see `ProductionPlanShape` below, which is
        the test that can fail when nothing does.
        """
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


class ProductionPlanShape(_StagingCase):
    """The honest version of Acceptance 5: nothing is injected.

    The plan is built by `bisonfactory._plan`, which is the only function
    that builds one on the way to EmailBison, and the hash asserted is the
    one `_plan` itself returns - the value a caller would compare. Two
    client configs differing ONLY in the sending identity must produce two
    different hashes.
    """

    def _plan_under(self, config):
        store.save([record("rec-1", "one@example.com", "Ada")])
        row = self._campaign(["rec-1"], config=config)
        return bisonfactory._plan(row, store.load(), config)

    def test_the_plan_carries_the_sender_it_was_built_from(self):
        """The key the hash reads is actually on the canonical plan.

        Asserted on `sequence_plan` - the dict `approval_hash` is computed
        over - and not only on `_plan`'s own return, because the defect was
        exactly that those two were different dicts and only one had it.
        """
        plan = self._plan_under(ADA)
        self.assertEqual(plan["sequence_plan"]["sender"],
                         {"name": "Ada Lovelace", "role": "founder",
                          "company": "Productive"})
        self.assertEqual(plan["sender"], plan["sequence_plan"]["sender"],
                         "the signed identity and the hashed one must be one "
                         "resolution, not two")

    def test_the_hash_moves_across_two_sender_identities(self):
        """THE TEST THAT USED TO LIE. No hand-injected `sender` key."""
        self.assertNotEqual(
            self._plan_under(ADA)["approval_hash"],
            self._plan_under(GRACE)["approval_hash"],
            "the production plan's approval hash must move when the sending "
            "identity does")

    def test_the_hash_is_stable_for_the_same_sender(self):
        """The control. A hash that moved on every call would pass the test
        above while covering nothing."""
        self.assertEqual(self._plan_under(ADA)["approval_hash"],
                         self._plan_under(ADA)["approval_hash"])

    def test_a_client_with_no_sender_still_plans_and_still_hashes(self):
        """`CONFIG` declares no sender. That must stay a plan, not a refusal.

        `sender_identity` returns `{}` for it, which is a real answer and not
        a missing one - the starter config is shaped exactly this way.
        """
        plan = self._plan_under(CONFIG)
        self.assertEqual(plan["sequence_plan"]["sender"], {})
        self.assertTrue(plan["approval_hash"])


if __name__ == "__main__":
    unittest.main()
