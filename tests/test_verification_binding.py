"""Two vendors must have approved *this* address, not a previous one.

The invariant is not "this contact has two confirmations". It is that two
independent vendors explicitly approved the exact normalised mailbox we are
about to write to. Evidence lives on the contact and outlives the address it
was obtained for, so those are different claims the moment an address
changes - a corrected typo, a re-enrichment that finds a better mailbox, an
operator fixing a bounced address.

Before this was bound, a contact whose two confirmations were obtained for
`old@acme.test` reported `verified` and `sendable` after its address became
`new@acme.test`, an address no vendor had ever seen. Both gates read
`verification.resolve`, so saying it twice in `push.verify_before_payload`
did not help: the second guard asked the same question and got the same
wrong answer.

Evidence that records no address at all cannot be shown to be about this one,
so it does not count either. That is the fail-closed reading, and it costs a
re-verification - the cheap half of the trade against sending to an
unverified mailbox.
"""
import unittest

from src import verification as v


def confirmed(email, providers=("contactout", "reoon")):
    """Two independent vendors, both saying valid, for one address."""
    return [v.result(p, "valid", email=email) for p in providers]


def contact_with(email, evidence):
    return {"key": "acme-champ", "email": email,
            "verification": {"evidence": evidence}}


class EvidenceIsBoundToTheAddress(unittest.TestCase):

    def setUp(self):
        self.policy = v.policy_for(None)

    def test_two_confirmations_for_this_address_are_enough(self):
        contact = contact_with("champ@acme.test", confirmed("champ@acme.test"))
        self.assertTrue(v.is_sendable(contact, self.policy))
        self.assertEqual(v.resolve(contact, self.policy)["state"], "verified")

    def test_confirmations_for_a_different_address_do_not_carry_over(self):
        """The defect. Two vendors approved the old mailbox; the contact's
        address has since changed, and nobody has checked the new one."""
        contact = contact_with("new@acme.test", confirmed("old@acme.test"))
        self.assertFalse(v.is_sendable(contact, self.policy))
        resolved = v.resolve(contact, self.policy)
        self.assertEqual(resolved["confirmation_count"], 0)
        self.assertNotEqual(resolved["state"], "verified")

    def test_one_matching_and_one_stale_confirmation_is_still_one(self):
        """The partial case, which is the one that would slip through a
        count that merely ignored the mismatch instead of excluding it."""
        contact = contact_with("new@acme.test",
                               confirmed("old@acme.test", ("contactout",))
                               + confirmed("new@acme.test", ("reoon",)))
        resolved = v.resolve(contact, self.policy)
        self.assertEqual(resolved["confirmation_count"], 1)
        self.assertFalse(resolved["sendable"])

    def test_evidence_with_no_address_recorded_does_not_count(self):
        """Unknown is not a match. It cannot be shown to be about this
        mailbox, so it fails closed rather than being assumed."""
        contact = contact_with("champ@acme.test",
                               [v.result("contactout", "valid", email=None),
                                v.result("reoon", "valid", email=None)])
        self.assertFalse(v.is_sendable(contact, self.policy))
        self.assertEqual(
            v.resolve(contact, self.policy)["confirmation_count"], 0)

    def test_case_and_padding_are_not_a_different_address(self):
        """No mail system treats these as significant, and refusing them
        would burn credits re-verifying an address we have already checked."""
        contact = contact_with("  Champ@Acme.TEST ",
                               confirmed("champ@acme.test"))
        self.assertTrue(v.is_sendable(contact, self.policy))

    def test_a_contact_with_no_address_confirms_nothing(self):
        """Two guards, asserted separately on purpose.

        `is_sendable` refuses an addressless contact outright, which is
        older than this binding and would mask it - so the binding is
        asserted where it actually lives. Evidence cannot be about an
        address that does not exist.
        """
        contact = contact_with(None, confirmed("champ@acme.test"))
        self.assertEqual(v.evidence_for(contact), [])
        self.assertEqual(v.all_evidence(contact), [])
        self.assertFalse(v.is_sendable(contact, self.policy))

    def test_the_legacy_fields_still_describe_the_current_address(self):
        """Records written before this module carry `verdict` and `reoon`
        rather than evidence. Those are read against the contact's own
        address, so they were never able to drift - and must keep working."""
        contact = {"key": "acme-champ", "email": "champ@acme.test",
                   "verdict": "valid",
                   "reoon": {"is_safe_to_send": True, "is_catch_all": False}}
        self.assertEqual(len(v.all_evidence(contact)), 2)
        self.assertTrue(v.is_sendable(contact, self.policy))

    def test_stale_stored_evidence_does_not_fall_through_to_the_legacy_fields(
            self):
        """The record old enough to carry both is the one that would slip.

        Stored evidence takes precedence over the legacy verdict fields.
        If binding merely emptied the stored list, the fall-through would
        hand back legacy evidence stamped with the *current* address and
        the contact would be sendable again - drift restored by the
        fallback that exists for a different purpose.
        """
        contact = {"key": "acme-champ", "email": "new@acme.test",
                   "verdict": "valid",
                   "reoon": {"is_safe_to_send": True, "is_catch_all": False},
                   "verification": {"evidence": confirmed("old@acme.test")}}
        self.assertEqual(v.resolve(contact, self.policy)["confirmation_count"],
                         0)
        self.assertFalse(v.is_sendable(contact, self.policy))

    def test_a_vendor_answering_twice_for_this_address_is_one_vote(self):
        """Binding must not accidentally reintroduce per-call counting."""
        contact = contact_with("champ@acme.test",
                               confirmed("champ@acme.test", ("contactout",))
                               + confirmed("champ@acme.test", ("contactout",)))
        self.assertEqual(
            v.resolve(contact, self.policy)["confirmation_count"], 1)
        self.assertFalse(v.is_sendable(contact, self.policy))


class TheExecutionBoundaryAsksTheSameQuestion(unittest.TestCase):
    """`push.verify_before_payload` re-checks rather than trusting upstream.

    It reads `verification.resolve`, so the binding has to hold there too -
    that is the whole reason the duplicated guard did not catch this.
    """

    def test_the_boundary_reads_a_bound_answer(self):
        from src import push
        contact = contact_with("new@acme.test", confirmed("old@acme.test"))
        policy = v.policy_for(None)
        resolved = v.resolve(contact, policy)
        self.assertLess(resolved["confirmation_count"],
                        resolved["required_confirmations"],
                        "the payload gate compares exactly these two numbers")
        self.assertTrue(hasattr(push, "verify_before_payload"))


if __name__ == "__main__":
    unittest.main()
