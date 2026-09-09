"""A membership cannot be created for somebody who does not exist.

`workspaces.assign` says why in its own docstring: "a membership row pointing
at nobody is a row that grants a permission to whoever registers that address
next". That is a privilege escalation with a delay on it - write the row for
an address nobody holds, wait for somebody to sign up with it, and they
inherit the role without anyone granting it to them.

The guard is one line and the mutation audit found nothing testing it:
"workspaces: create a membership for a user who does not exist" replaces
`if user(email) is None: raise NoSuchUser` with `if False:` and
`tests.test_web_security` stayed green.

`invite` is the sanctioned path for somebody who has never signed in - it
records a pending invitation rather than an active membership, so access is
granted on acceptance rather than on registration. The last two tests hold
that line: an invitation must not itself become a membership.
"""
import unittest

from src import workspaces as ws
from tests.test_repo import RepoTest

GHOST = "ghost@nowhere.test"


class AMembershipNeedsAUser(RepoTest):

    def memberships_of(self, email):
        return [m for m in ws.memberships(email)] \
            if hasattr(ws, "memberships") else \
            [r for r in ws.load() if r.get("kind") == "membership"
             and r.get("email") == email]

    # ----------------------------------------------------------- the guard

    def test_assigning_a_nonexistent_user_is_refused(self):
        with self.assertRaises(ws.NoSuchUser):
            ws.assign(GHOST, "productive", ws.OPERATOR)

    def test_no_membership_row_is_left_behind(self):
        try:
            ws.assign(GHOST, "productive", ws.OPERATOR)
        except ws.NoSuchUser:
            pass
        self.assertEqual(self.memberships_of(GHOST), [])

    def test_the_delayed_escalation_does_not_happen(self):
        """The attack the docstring describes, run end to end.

        Write the row for an address nobody holds, then let that person
        register. They must arrive with nothing.
        """
        try:
            ws.assign(GHOST, "productive", ws.WORKSPACE_ADMIN)
        except ws.NoSuchUser:
            pass
        ws.add_user(GHOST, "Ghost")
        self.assertEqual(self.memberships_of(GHOST), [])
        with self.assertRaises(Exception):
            ws.membership(GHOST, "productive")

    def test_the_refusal_names_the_address(self):
        try:
            ws.assign(GHOST, "productive", ws.OPERATOR)
        except ws.NoSuchUser as e:
            self.assertIn(GHOST, str(e))
        else:
            self.fail("assign was not refused")

    # ------------------------------------------------- and the real path

    def test_an_existing_user_can_still_be_assigned(self):
        """Otherwise the guard refuses everybody and proves nothing."""
        ws.add_user("real@x.test", "Real")
        ws.assign("real@x.test", "productive", ws.REVIEWER)
        self.assertTrue(self.memberships_of("real@x.test"))

    def test_an_invitation_is_not_a_membership(self):
        """`invite` is the sanctioned path for somebody who has never signed
        in. It must record an invitation, not an active membership."""
        ws.invite(GHOST, "productive", ws.OPERATOR, actor="op@x.test")
        self.assertEqual(self.memberships_of(GHOST), [],
                         "an invitation became a membership")


if __name__ == "__main__":
    unittest.main()
