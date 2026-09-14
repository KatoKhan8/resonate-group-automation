#!/usr/bin/env python3
"""Every account has an owner, or says UNKNOWN, and never a guess.

The three tests the task requires:

1. A sender with a derivable owner resolves to it.
2. A sender with none resolves to UNKNOWN and never to a guess.
3. `assignment` routes a reply to the owner when there is one and refuses
   when there is not.

Plus the wiring tests QWEN.md now requires: eligible_senders reaches
attested accounts through the real entry point, and deleting the call to
resolve_owner makes a test fail.
"""
from src import assignment, senderidentity as si, senderownership as so
from tests.campaignbase import CampaignTest

WS = "productive"


def _roster_with_owner():
    """A human who owns their inbox the normal way - sender_id is set."""
    return [
        si.new_sender(WS, "anna", "Anna Novak"),
        si.new_email_account(WS, "anna07", "anna", "anna07@productive.test",
                             provider_account_id="eb-101"),
    ]


def _roster_without_owner():
    """An inbox the inventory rebuilt - sender_id is None, no attestation."""
    return [
        si.new_sender(WS, "anna", "Anna Novak"),
        si.new_email_account(WS, "anna07", None, "anna07@productive.test",
                             provider_account_id="eb-101"),
    ]


def _roster_with_attestation():
    """An inbox without sender_id but with an attestation bridging the gap.

    Returns the base rows only; the caller must call so.attest() after
    install, because si.install validates kinds and an attestation is not
    a senderidentity kind.
    """
    return [
        si.new_sender(WS, "anna", "Anna Novak"),
        si.new_email_account(WS, "anna07", None, "anna07@productive.test",
                             provider_account_id="eb-101"),
    ]


class OwnerResolution(CampaignTest):
    """A sender with a derivable owner resolves to it."""

    def test_sender_id_on_the_account_resolves_directly(self):
        si.install(_roster_with_owner())
        acct = si.account(WS, si.EMAIL, "anna07")
        self.assertEqual(so.resolve_owner(acct), "anna")

    def test_resolve_reply_owner_finds_the_human_through_sender_id(self):
        si.install(_roster_with_owner())
        result = assignment.resolve_reply_owner(WS, si.EMAIL, "eb-101")
        self.assertEqual(result["sender_id"], "anna")
        self.assertEqual(result["display_name"], "Anna Novak")
        self.assertEqual(result["source"], "sender_id")

    def test_an_attestation_resolves_when_sender_id_is_absent(self):
        si.install(_roster_with_attestation())
        so.attest(WS, si.EMAIL, "anna07", "anna", by="ops")
        acct = si.account(WS, si.EMAIL, "anna07")
        self.assertIsNone(acct.get("sender_id"))
        self.assertEqual(so.resolve_owner(acct), "anna")

    def test_resolve_reply_owner_finds_the_human_through_attestation(self):
        si.install(_roster_with_attestation())
        so.attest(WS, si.EMAIL, "anna07", "anna", by="ops")
        result = assignment.resolve_reply_owner(WS, si.EMAIL, "eb-101")
        self.assertEqual(result["sender_id"], "anna")
        self.assertEqual(result["source"], "attestation")


class UnknownNeverGuesses(CampaignTest):
    """A sender with no derivable owner resolves to UNKNOWN."""

    def test_no_sender_id_no_attestation_returns_none(self):
        si.install(_roster_without_owner())
        acct = si.account(WS, si.EMAIL, "anna07")
        self.assertIsNone(so.resolve_owner(acct))

    def test_resolve_reply_owner_returns_unknown_not_a_guess(self):
        si.install(_roster_without_owner())
        result = assignment.resolve_reply_owner(WS, si.EMAIL, "eb-101")
        self.assertEqual(result["sender_id"], so.UNKNOWN)
        self.assertNotIn("anna", str(result.get("sender_id")))
        self.assertIn("reason", result)

    def test_an_unknown_provider_account_is_unknown_not_an_error(self):
        si.install(_roster_without_owner())
        result = assignment.resolve_reply_owner(WS, si.EMAIL, "nonexistent")
        self.assertEqual(result["sender_id"], so.UNKNOWN)
        self.assertIn("no email account", result["reason"])

    def test_no_provider_id_at_all_is_unknown(self):
        si.install(_roster_without_owner())
        result = assignment.resolve_reply_owner(WS, si.EMAIL, "")
        self.assertEqual(result["sender_id"], so.UNKNOWN)

    def test_an_orphan_account_stays_unknown_until_attested(self):
        si.install([
            si.new_sender(WS, "anna", "Anna Novak"),
            si.new_email_account(WS, "orphan01", None,
                                 "orphan@productive.test",
                                 provider_account_id="eb-999"),
        ])
        result = assignment.resolve_reply_owner(WS, si.EMAIL, "eb-999")
        self.assertEqual(result["sender_id"], so.UNKNOWN)
        so.attest(WS, si.EMAIL, "orphan01", "anna", by="ops")
        result_after = assignment.resolve_reply_owner(WS, si.EMAIL, "eb-999")
        self.assertEqual(result_after["sender_id"], "anna")


class ReplyRouting(CampaignTest):
    """assignment routes a reply to the owner, or refuses."""

    def setUp(self):
        super().setUp()
        si.install(_roster_with_owner())

    def test_a_reply_is_routed_to_the_named_human(self):
        result = assignment.resolve_reply_owner(WS, si.EMAIL, "eb-101")
        self.assertEqual(result["sender_id"], "anna")
        self.assertEqual(result["account_id"], "anna07")

    def test_a_reply_to_an_unowned_account_is_refused(self):
        si.install(_roster_without_owner())
        result = assignment.resolve_reply_owner(WS, si.EMAIL, "eb-101")
        self.assertEqual(result["sender_id"], so.UNKNOWN)

    def test_eligible_senders_includes_attested_accounts(self):
        """The wiring test: eligible_senders reaches attested accounts.

        Without the call to so.resolve_owner inside eligible_senders, an
        account with sender_id=None is invisible to the allocator regardless
        of any attestation. This test fails when that call is removed.
        """
        si.install(_roster_with_attestation())
        so.attest(WS, si.EMAIL, "anna07", "anna", by="ops")
        pool = assignment.eligible_senders(WS, si.EMAIL)
        sender_ids = {e["sender"]["sender_id"] for e in pool}
        self.assertIn("anna", sender_ids,
                       "anna should be eligible via attested account")
        anna_entry = [e for e in pool
                      if e["sender"]["sender_id"] == "anna"][0]
        account_ids = [a["account_id"] for a in anna_entry["accounts"]]
        self.assertIn("anna07", account_ids)

    def test_eligible_senders_excludes_unowned_accounts(self):
        """Without sender_id AND without attestation, anna has no accounts."""
        si.install(_roster_without_owner())
        pool = assignment.eligible_senders(WS, si.EMAIL)
        sender_ids = {e["sender"]["sender_id"] for e in pool}
        self.assertNotIn("anna", sender_ids,
                         "anna should not be eligible without ownership")


class AttestationMechanism(CampaignTest):
    """The attestation store itself: writes, replaces, refuses bad input."""

    def setUp(self):
        super().setUp()
        si.install([si.new_sender(WS, "anna", "Anna Novak")])

    def test_attest_requires_a_known_sender(self):
        with self.assertRaises(si.UnknownSender):
            so.attest(WS, si.EMAIL, "anna07", "nobody", by="ops")

    def test_attest_requires_an_actor(self):
        with self.assertRaises(ValueError):
            so.attest(WS, si.EMAIL, "anna07", "anna", by="")

    def test_attest_replaces_a_previous_one_for_the_same_account(self):
        si.add(si.new_email_account(WS, "anna07", None,
                                    "anna07@productive.test"))
        so.attest(WS, si.EMAIL, "anna07", "anna", by="ops")
        so.attest(WS, si.EMAIL, "anna07", "anna", by="ops-reassign")
        atts = so._attestations(WS)
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]["by"], "ops-reassign")

    def test_dry_run_report_counts_resolved_and_unresolved(self):
        si.install([
            si.new_sender(WS, "anna", "Anna Novak"),
            si.new_email_account(WS, "anna07", "anna",
                                 "anna07@productive.test",
                                 provider_account_id="eb-1"),
            si.new_email_account(WS, "orphan01", None,
                                 "orphan@productive.test",
                                 provider_account_id="eb-2"),
        ])
        report = so.dry_run_report(WS)
        self.assertEqual(report["total_accounts"], 2)
        self.assertEqual(report["resolved"], 1)
        self.assertEqual(report["needs_attestation"], 1)
        self.assertEqual(report["resolved_accounts"][0]["resolved_owner"],
                         "anna")
        self.assertEqual(report["unresolved_accounts"][0]["account_id"],
                         "orphan01")


if __name__ == "__main__":
    import unittest
    unittest.main()
