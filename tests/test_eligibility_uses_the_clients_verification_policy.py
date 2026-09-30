#!/usr/bin/env python3
"""The send gate asks the CLIENT's verification policy, not the default one.

The same defect as `test_approval_uses_the_clients_verification_policy`, one
gate further along, found 2026-09-30.

Productive moved its verification roles on 2026-09-21 - primary Deliverable,
secondary Reoon, ContactOut removed from verification entirely. `approve.why_not`
was corrected that day; `push.py` and `campaigns.py` had it right already. The
caller nobody checked was `eligibility._email_checks`, which asked
`verification.resolve(contact)` and `lint.sendable(contact)` with no policy at
all, so the send gate answered under `DEFAULT_POLICY`, where ContactOut is
primary, about a client that no longer uses ContactOut.

Measured on the live queue the day it was found: **804 of 1,308 contacts
carrying an address were refused `held:verification_unknown` by a policy their
own client had cleared** - while `lint.check`, two lines below in the same
function, was already asking under `policy_for_record`. The send gate and the
lint gate disagreed about what verified means.

WHAT THIS IS NOT. It does not change either policy, and it does not clear
anybody the client's own policy refuses. The direction of the fallback is
asserted below: a record with no resolvable client keeps the conservative
default, never the looser one.

No real person appears in this file. The addresses are synthetic.
"""
import unittest

from src import clients, eligibility, lint, verification


def _contact(providers, status="valid", key="someone",
             email="someone@example.test"):
    return {
        "key": key,
        "name": "Someone Example",
        "first_name": "Someone",
        "email": email,
        "title": "Chief Financial Officer",
        "persona": "economic_buyer",
        "angle": "finance",
        "sendable": True,
        "primary": True,
        "verification": {
            "state": "verified",
            "sendable": True,
            "evidence": [{"provider": name, "status": status, "email": email,
                          "at": "2026-09-30T12:00:00+00:00"}
                         for name in providers],
        },
    }


def _record(contact, client="productive", excluded=()):
    return {
        "id": "example-test",
        "client": client,
        "lane": "domains",
        "company": "Example Agency",
        "domain": "example.test",
        "state": "ready",
        "contacts": [contact],
        "excluded": list(excluded),
        "cadence": {contact["key"]: {"em1": {
            "channel": "email",
            "subject": "margin visibility while projects are active",
            "body": ("Someone, I work with Marketing teams on margin "
                     "visibility while projects are active, and I do not know "
                     "how Example Agency handles it\n\nIs that roughly how it "
                     "works at Example Agency today, or have you already put "
                     "something in place for it?"),
        }}},
    }


def _verdict(record, contact, config=None):
    return eligibility.decide(
        record, contact, "em1", config=config,
        step=record["cadence"][contact["key"]]["em1"])


VERIFICATION_REASONS = {eligibility.HELD_VERIFICATION_UNKNOWN,
                        eligibility.HELD_INSUFFICIENT_CONFIRMATIONS,
                        eligibility.BLOCKED_NOT_SENDABLE}


class ThePremise(unittest.TestCase):
    """If these change, the rest of this file is about nothing."""

    def test_the_two_policies_differ_on_the_primary(self):
        productive = verification.policy_for(clients.load("productive"))
        self.assertEqual(productive["primary"], "deliverable")
        self.assertEqual(verification.policy_for({})["primary"], "contactout")


class ThePositiveControl(unittest.TestCase):
    """The pair Productive actually requires clears the send gate."""

    def test_deliverable_and_reoon_pass_verification_for_productive(self):
        contact = _contact(("deliverable", "reoon"))
        reasons = set(_verdict(_record(contact), contact)["reasons"])
        self.assertFalse(reasons & VERIFICATION_REASONS,
                         f"refused on verification: {sorted(reasons)}")

    def test_the_same_contact_is_refused_under_the_default_policy(self):
        """The defect itself, stated as the difference between the policies."""
        contact = _contact(("deliverable", "reoon"))
        self.assertTrue(verification.is_sendable(contact, lint.policy_for_record(
            _record(contact))))
        self.assertFalse(verification.is_sendable(contact))


class TheNegativeControls(unittest.TestCase):

    def test_a_contact_the_clients_own_policy_refuses_is_still_refused(self):
        """Operator condition 1. An address Deliverable calls invalid is not
        cleared by asking a different policy about it."""
        contact = _contact(("deliverable", "reoon"), status="invalid")
        reasons = set(_verdict(_record(contact), contact)["reasons"])
        self.assertTrue(reasons & VERIFICATION_REASONS,
                        f"an invalid address was not refused: {sorted(reasons)}")

    def test_a_single_confirmation_is_still_refused(self):
        """Productive requires two. One is not made into two by this change."""
        contact = _contact(("deliverable",))
        reasons = set(_verdict(_record(contact), contact)["reasons"])
        self.assertTrue(reasons & VERIFICATION_REASONS,
                        f"one confirmation was accepted: {sorted(reasons)}")

    def test_the_pair_the_client_dropped_no_longer_clears(self):
        """The fix cuts both ways: ContactOut plus Reoon passed under the
        default and must now be refused for this client."""
        contact = _contact(("contactout", "reoon"))
        self.assertTrue(verification.is_sendable(contact))
        reasons = set(_verdict(_record(contact), contact)["reasons"])
        self.assertTrue(reasons & VERIFICATION_REASONS,
                        f"a dropped pair still cleared: {sorted(reasons)}")

    def test_an_excluded_contact_stays_refused(self):
        """Operator condition 2. Exclusion is decided before verification and
        does not become reachable because the address now clears."""
        contact = _contact(("deliverable", "reoon"))
        record = _record(contact, excluded=[dict(contact)])
        verdict = _verdict(record, contact)
        self.assertEqual(verdict["verdict"], eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_NOT_SELECTED, verdict["reasons"])

    def test_a_record_with_no_client_keeps_the_default_on_the_send_path(self):
        """Operator condition 3, and the direction of the fallback. A record
        whose client cannot be resolved must behave exactly as before - the
        conservative default - and never fall back to the looser policy.

        Productive's own config is handed in, because `decide` builds a cadence
        before it reaches verification and a client-less record has none to
        build one from. That sharpens the assertion rather than weakening it:
        even handed the permissive client's config, the policy is taken from
        `policy_for_record(rec)` - which reads the RECORD's client, resolves to
        None here, and so refuses."""
        contact = _contact(("deliverable", "reoon"))
        record = _record(contact, client=None)
        self.assertIsNone(lint.policy_for_record(record))
        reasons = set(_verdict(record, contact,
                               config=clients.load("productive"))["reasons"])
        self.assertTrue(reasons & VERIFICATION_REASONS,
                        f"an unresolvable client was cleared: {sorted(reasons)}")

    def test_an_unreadable_client_config_resolves_to_the_default(self):
        """`policy_for_record` swallows a ConfigError and returns None, and
        None is the conservative policy rather than an absent one."""
        record = _record(_contact(("deliverable", "reoon")),
                         client="no-such-client")
        lint.forget_policies()
        try:
            self.assertIsNone(lint.policy_for_record(record))
        finally:
            lint.forget_policies()

    def test_the_default_policy_refuses_what_this_change_would_otherwise_clear(self):
        """The fallback stated as behaviour rather than as a None check: under
        no policy, the pair Productive requires does not clear."""
        contact = _contact(("deliverable", "reoon"))
        self.assertFalse(verification.is_sendable(contact, None))


if __name__ == "__main__":
    unittest.main()
