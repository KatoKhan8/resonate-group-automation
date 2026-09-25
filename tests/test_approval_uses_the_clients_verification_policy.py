#!/usr/bin/env python3
"""Approval asks the CLIENT's verification policy, not the default one.

Found on batch 1, 2026-09-21, and it was backwards in both directions.

The Productive workspace moved its verification roles that morning - primary
Deliverable, secondary Reoon, ContactOut removed from verification entirely -
and `policy_for` scoped it correctly. But `approve.why_not` asked
`lint.sendable(contact)`, which asks `verification.is_sendable` with no
policy, which falls back to `DEFAULT_POLICY` where ContactOut is primary.

Measured on the real batch: **168 contacts verified by (contactout, reoon)
were approved under a policy their client no longer uses, and 189 verified by
(deliverable, reoon) - the pair the client now requires - were refused as
"recipient is not sendable".**

The push path had it right all along: `push.py` and `campaigns.py` both pass
`policy_for(config)`. So the approval gate and the push gate disagreed about
what verified means, which is worse than either being wrong alone.

UPDATED 2026-09-25 for the new order. The client's roles moved again -
primary CheapVerifier, secondary Deliverable, Reoon the third opinion - so
the PAIR this file uses to demonstrate the difference moved with them. What
the file is ABOUT is unchanged and is not a claim about any particular
provider: the client's policy and the default policy answer differently, and
every gate must ask the client's.
"""
import unittest

from src import approve, clients, verification


def _contact(providers, email="someone@example.test"):
    """A contact whose evidence names each provider as valid for its address."""
    return {
        "key": "someone",
        "name": "Someone Example",
        "first_name": "Someone",
        "email": email,
        "title": "Chief Operating Officer",
        "persona": "economic_buyer",
        "angle": "operations",
        "sendable": True,
        "primary": True,
        "verification": {
            "state": "verified",
            "sendable": True,
            "evidence": [{"provider": name, "status": "valid",
                          "email": email, "at": "2026-09-21T12:00:00+00:00"}
                         for name in providers],
        },
    }


class ThePolicyThatDecides(unittest.TestCase):

    def setUp(self):
        self.productive = clients.load("productive")
        self.policy = verification.policy_for(self.productive)

    def test_productive_requires_cheapverifier_as_primary(self):
        """The premise. If this changes, the rest of this file is about
        nothing."""
        self.assertEqual(self.policy["primary"], "cheapverifier")
        self.assertNotIn("contactout", (self.policy["primary"],
                                        self.policy["secondary"],
                                        self.policy["catch_all"]))

    def test_the_clients_pair_clears_under_the_client_policy(self):
        contact = _contact(("cheapverifier", "deliverable"))
        self.assertTrue(verification.is_sendable(contact, self.policy))

    def test_the_same_contact_does_not_clear_under_the_default(self):
        """The defect, stated as the difference between the two policies.

        Under `DEFAULT_POLICY` the primary is ContactOut, which never
        answered for this contact, so the same evidence does not clear.
        """
        contact = _contact(("cheapverifier", "deliverable"))
        self.assertFalse(verification.is_sendable(contact))

    def test_the_pair_the_client_used_yesterday_no_longer_clears(self):
        """THE MIGRATION CONSEQUENCE, asserted rather than discovered.

        `(deliverable, reoon)` was Productive's required pair from 09-21
        until 09-25. Every address cleared under it is held by the new
        policy, because the new primary has never answered for it. That is
        correct - the operator moved the primary - and it is the single
        biggest operational effect of the change, so it is pinned here
        rather than found in production.
        """
        contact = _contact(("deliverable", "reoon"))
        self.assertFalse(verification.is_sendable(contact, self.policy))

    def test_contactout_and_reoon_no_longer_clear_for_this_client(self):
        contact = _contact(("contactout", "reoon"))
        self.assertTrue(verification.is_sendable(contact))
        self.assertFalse(verification.is_sendable(contact, self.policy))


class WhyNotAsksTheRightOne(unittest.TestCase):
    """`approve.why_not` is the gate that was reading the wrong policy."""

    def _record(self, providers):
        contact = _contact(providers)
        return {
            "id": "example-test",
            "client": "productive",
            "lane": "domains",
            "company": "Example Agency",
            "domain": "example.test",
            "state": "verified",
            "contacts": [contact],
            "cadence": {contact["key"]: {"em1": {
                "channel": "email",
                "subject": "utilisation and capacity across live projects",
                "body": ("Someone, I work with Marketing teams on utilisation "
                         "and capacity across live projects, and I do not know "
                         "how Example Agency handles it\n\nIs that roughly how "
                         "it works at Example Agency today?"),
            }}},
        }

    def test_the_clients_pair_is_approvable(self):
        record = self._record(("cheapverifier", "deliverable"))
        why = approve.why_not(record, "someone", "em1",
                              step=record["cadence"]["someone"]["em1"],
                              config=clients.load("productive"))
        self.assertNotEqual(why, "recipient is not sendable")

    def test_a_pair_the_client_dropped_is_not_approvable(self):
        record = self._record(("contactout", "reoon"))
        why = approve.why_not(record, "someone", "em1",
                              step=record["cadence"]["someone"]["em1"],
                              config=clients.load("productive"))
        self.assertEqual(why, "recipient is not sendable")

    def test_a_client_with_no_verification_block_is_unaffected(self):
        """`policy_for` overlays config over the defaults, so a workspace
        that has chosen nothing keeps the conservative default exactly."""
        record = self._record(("contactout", "reoon"))
        record["client"] = "demo"
        why = approve.why_not(record, "someone", "em1",
                              step=record["cadence"]["someone"]["em1"],
                              config={})
        self.assertNotEqual(why, "recipient is not sendable")


if __name__ == "__main__":
    unittest.main()
