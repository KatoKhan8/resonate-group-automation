"""The arity rule is right about ACTIONS and stricter than it needs to be about INBOXES.

`executionguard._sender_for` refuses any campaign whose canonical row names
more than one sender - "a guarded action is attributed to exactly one". The
failure it prevents is concrete: a prospect hearing from Human A in the opener
and Human B in the follow-up because the provider rotated mailboxes.

That failure is now measured rather than assumed, and it does not happen
within one human's inboxes:

- EmailBison DOCUMENTS per-lead stickiness - "once a lead has been sent an
  email in a campaign, the same Sender Email will send the remaining steps for
  that lead" (docs.emailbison.com/campaigns/overview).
- This estate's own queue agrees: 243 leads across campaigns holding 59 and
  222 attached senders, zero rotations
  (`scripts/bison_sender_stickiness.py`).

So `senderownership.one_attested_human` answers the question the arity rule
was approximating: do ALL of these inboxes belong to exactly one attested
human? The cost of getting it wrong is a real person receiving a conversation
from two people, so every way of failing it raises with its reason rather than
returning None.

**The predicate has no caller yet and these tests do not add one.** Adopting
it inside `_sender_for` requires deciding what the action ledger records as
`sender_id` - today a provider inbox, and honestly a human once a campaign
holds several. That is a change to what a durable column MEANS and is not a
side effect of a predicate.
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import senderidentity as si, senderownership as so, store  # noqa: E402

WS = "productive"


class Roster(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        restore = store.use_directory(self.tmp.name)
        if callable(restore):
            self.addCleanup(restore)
        # The constructors BUILD a row; `add` persists it. Two calls, because
        # a roster row that was never written is a roster row nothing resolves.
        si.add(si.new_sender(WS, "ada", display_name="Ada", title="AE"))
        si.add(si.new_sender(WS, "bo", display_name="Bo", title="AE"))

    def inbox(self, account_id, provider_id, owner=None, workspace=WS):
        si.add(si.new_email_account(
            workspace, account_id, sender_id=owner,
            email_address=f"{account_id}@example.test",
            provider="emailbison", provider_account_id=str(provider_id)))
        return str(provider_id)


class OneHumanMayOwnSeveral(Roster):

    def test_three_inboxes_of_one_human_resolve_to_that_human(self):
        ids = [self.inbox(f"eb-{n}", n, owner="ada") for n in (1, 2, 3)]
        self.assertEqual(
            so.one_attested_human(ids, WS, si.EMAIL), "ada")

    def test_one_inbox_still_resolves(self):
        ids = [self.inbox("eb-1", 1, owner="ada")]
        self.assertEqual(so.one_attested_human(ids, WS, si.EMAIL), "ada")

    def test_an_attestation_counts_as_ownership(self):
        """The common path once a backfill happens: the account carries no
        `sender_id` and a person said who operates it."""
        ids = [self.inbox("eb-9", 9)]
        so.attest(WS, si.EMAIL, "eb-9", "ada", by="operator@example.test")
        self.assertEqual(so.one_attested_human(ids, WS, si.EMAIL), "ada")


class EveryRefusalIsLoudAndReasoned(Roster):

    def test_two_humans_are_refused(self):
        """The failure the arity rule exists to prevent."""
        ids = [self.inbox("eb-1", 1, owner="ada"),
               self.inbox("eb-2", 2, owner="bo")]
        with self.assertRaises(so.NotOneHuman) as caught:
            so.one_attested_human(ids, WS, si.EMAIL)
        self.assertIn("2 humans", str(caught.exception))

    def test_an_unattested_inbox_is_refused_even_beside_attested_ones(self):
        """The common case today: zero of 225 productive inboxes are
        attested. One unowned inbox in the set poisons the whole set, because
        a send from it could not be attributed to anybody."""
        ids = [self.inbox("eb-1", 1, owner="ada"), self.inbox("eb-2", 2)]
        with self.assertRaises(so.NotOneHuman) as caught:
            so.one_attested_human(ids, WS, si.EMAIL)
        self.assertIn("no attested owner", str(caught.exception))

    def test_an_inbox_this_workspace_cannot_name_is_refused(self):
        ids = [self.inbox("eb-1", 1, owner="ada"), "99999"]
        with self.assertRaises(so.NotOneHuman) as caught:
            so.one_attested_human(ids, WS, si.EMAIL)
        self.assertIn("roster", str(caught.exception))

    def test_no_senders_at_all_is_refused(self):
        with self.assertRaises(so.NotOneHuman):
            so.one_attested_human([], WS, si.EMAIL)

    def test_blank_ids_do_not_count_as_senders(self):
        """`[None, ""]` is not one sender and must not read as one."""
        with self.assertRaises(so.NotOneHuman):
            so.one_attested_human([None, ""], WS, si.EMAIL)

    def test_a_refusal_is_never_a_none(self):
        """`resolve_owner` returns None because 'nobody has said' is a real
        answer about ONE account. This asks about a SET, and a None here
        would be read by a caller as 'no constraint'."""
        ids = [self.inbox("eb-1", 1)]
        with self.assertRaises(so.NotOneHuman):
            so.one_attested_human(ids, WS, si.EMAIL)


class TenancyIsNotOptional(Roster):

    def test_another_workspaces_inbox_does_not_resolve(self):
        """`by_provider_account` is workspace-scoped because a provider id is
        somebody else's namespace. An id that exists in another tenant must
        read as unknown here, not as theirs."""
        si.add(si.new_sender("other", "cy", display_name="Cy"))
        self.inbox("eb-7", 7, owner="cy", workspace="other")
        with self.assertRaises(so.NotOneHuman) as caught:
            so.one_attested_human(["7"], WS, si.EMAIL)
        self.assertIn("roster", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
