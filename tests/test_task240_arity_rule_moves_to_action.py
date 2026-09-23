"""TASK-240: the arity rule moves from the campaign to the action.

The old predicate (`_sender_for`) refused when the campaign named != 1 sender.
The new predicate (`_owner_for`) refuses when the campaign's seats do not all
resolve to the same attested human. A campaign may name many seats; an action
is attributed to exactly one human.

These tests exercise `_owner_for` directly, isolating the predicate from the
rest of the guard.
"""
import unittest

from src import executionguard, senderidentity


class OwnerForTests(unittest.TestCase):
    """Direct tests for _owner_for, the predicate that replaced _sender_for."""

    def setUp(self):
        import tempfile, os
        from src import store
        self._tmpdir = tempfile.mkdtemp()
        self.addCleanup(store.use_directory(self._tmpdir))

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _campaign(self, sender_rows, client="productive"):
        return {"client": client, "senders": {"linkedin": sender_rows}}

    def _seed(self, humans_and_seats):
        """Create humans and their seats in the sender store.

        humans_and_seats: list of (sender_id, [(account_id, provider_account_id)])
        """
        with senderidentity.transaction() as rows:
            for sender_id, seats in humans_and_seats:
                rows.append(senderidentity.new_sender(
                    "productive", sender_id, sender_id.title()))
                for acct_id, pid in seats:
                    rows.append(senderidentity.new_linkedin_account(
                        "productive", acct_id, sender_id,
                        f"https://www.linkedin.com/in/{sender_id}-{acct_id}",
                        provider="heyreach", provider_account_id=pid,
                        active=True, daily_limit=40, health="ok"))

    def test_one_seat_one_human_passes(self):
        self._seed([("anna", [("li-100", "100")])])
        campaign = self._campaign([{"provider_account_id": "100"}])
        owner, seats = executionguard._owner_for(campaign, "linkedin")
        self.assertEqual(owner, "anna")
        self.assertEqual(len(seats), 1)

    def test_two_seats_same_human_passes(self):
        self._seed([("anna", [("li-100", "100"), ("li-101", "101")])])
        campaign = self._campaign([
            {"provider_account_id": "100"},
            {"provider_account_id": "101"},
        ])
        owner, seats = executionguard._owner_for(campaign, "linkedin")
        self.assertEqual(owner, "anna")
        self.assertEqual(len(seats), 2)

    def test_two_seats_two_humans_refused(self):
        self._seed([
            ("anna", [("li-100", "100")]),
            ("bob", [("li-200", "200")]),
        ])
        campaign = self._campaign([
            {"provider_account_id": "100"},
            {"provider_account_id": "200"},
        ])
        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard._owner_for(campaign, "linkedin")
        self.assertEqual(ctx.exception.gate, "sender")
        self.assertIn("2 distinct", ctx.exception.why)

    def test_no_senders_refused(self):
        campaign = self._campaign([])
        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard._owner_for(campaign, "linkedin")
        self.assertEqual(ctx.exception.gate, "sender")
        self.assertIn("no linkedin senders", ctx.exception.why)

    def test_unowned_seat_refused(self):
        with senderidentity.transaction() as rows:
            rows.append(senderidentity.new_linkedin_account(
                "productive", "li-100", None,
                "https://www.linkedin.com/in/nobody",
                provider="heyreach", provider_account_id="100",
                active=True, daily_limit=40, health="ok"))
        campaign = self._campaign([{"provider_account_id": "100"}])
        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard._owner_for(campaign, "linkedin")
        self.assertEqual(ctx.exception.gate, "sender")
        self.assertIn("no attested human owner", ctx.exception.why)

    def test_uninventoried_seat_refused(self):
        self._seed([("anna", [("li-100", "100")])])
        campaign = self._campaign([{"provider_account_id": "999"}])
        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard._owner_for(campaign, "linkedin")
        self.assertEqual(ctx.exception.gate, "sender")
        self.assertIn("roster", ctx.exception.why)

    def test_deactivated_seat_refused(self):
        with senderidentity.transaction() as rows:
            rows.append(senderidentity.new_sender(
                "productive", "anna", "Anna"))
            rows.append(senderidentity.new_linkedin_account(
                "productive", "li-100", "anna",
                "https://www.linkedin.com/in/anna",
                provider="heyreach", provider_account_id="100",
                active=False, daily_limit=40, health="ok"))
        campaign = self._campaign([{"provider_account_id": "100"}])
        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard._owner_for(campaign, "linkedin")
        self.assertEqual(ctx.exception.gate, "sender")
        self.assertIn("not active", ctx.exception.why)

    def test_unhealthy_seat_refused(self):
        with senderidentity.transaction() as rows:
            rows.append(senderidentity.new_sender(
                "productive", "anna", "Anna"))
            row = senderidentity.new_linkedin_account(
                "productive", "li-100", "anna",
                "https://www.linkedin.com/in/anna",
                provider="heyreach", provider_account_id="100",
                active=True, daily_limit=40, health="ok")
            row["health"] = "paused"
            rows.append(row)
        campaign = self._campaign([{"provider_account_id": "100"}])
        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard._owner_for(campaign, "linkedin")
        self.assertEqual(ctx.exception.gate, "sender")
        self.assertIn("paused", ctx.exception.why)

    def test_another_client_seat_refused(self):
        self._seed([("anna", [("li-100", "100")])])
        campaign = self._campaign([{"provider_account_id": "100"}],
                                  client="other-client")
        with self.assertRaises(executionguard.NotAuthorized) as ctx:
            executionguard._owner_for(campaign, "linkedin")
        self.assertEqual(ctx.exception.gate, "sender")
        self.assertIn("roster", ctx.exception.why)

    def test_old_sender_for_returns_list(self):
        """_sender_for is deprecated but still returns the raw id list."""
        self._seed([("anna", [("li-100", "100")])])
        campaign = self._campaign([{"provider_account_id": "100"}])
        ids = executionguard._sender_for(campaign, "linkedin")
        self.assertEqual(ids, ["100"])

    def test_old_sender_for_no_arity_check(self):
        """_sender_for no longer enforces arity-1; it returns all ids."""
        self._seed([
            ("anna", [("li-100", "100")]),
            ("bob", [("li-200", "200")]),
        ])
        campaign = self._campaign([
            {"provider_account_id": "100"},
            {"provider_account_id": "200"},
        ])
        ids = executionguard._sender_for(campaign, "linkedin")
        self.assertEqual(sorted(ids), ["100", "200"])


if __name__ == "__main__":
    unittest.main()
