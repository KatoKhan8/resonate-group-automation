"""Pre-authorising an address, and everything that must not become access.

An administrator has to be able to grant access to somebody who has never
signed in. The obvious way to do that - write the membership row now - is
the one thing `assign` has always refused, and its reason is right: a
membership pointing at nobody grants a permission to whoever registers that
address next.

So an invitation is a different kind of row. It grants nothing, appears in
no permission check, and `membership_of` cannot see it. It is a standing
instruction about what to do *if* an identity provider ever proves a
particular address, and the only thing that reads it is the OAuth callback,
after the proof.

Which makes the interesting tests the ones where an invitation exists and
somebody still gets nothing: the wrong address, a similar address, the same
domain, another workspace, a revoked offer, or a form with an email typed
into it.
"""
import os
import shutil
import tempfile
import unittest

from src import store, workspaces as ws

ADMIN = "admin@resonate.test"
INVITEE = "tina@resonate.test"
OTHER = "someone@resonate.test"


class Estate(unittest.TestCase):
    """Two workspaces, so tenancy is a real question rather than a claim."""

    ENV = ("QUEUE", "OUT", "CLIENTS_DIR") + store.STATE_OVERRIDES

    def setUp(self):
        self._prev = {k: os.environ.get(k) for k in self.ENV}
        self.root = tempfile.mkdtemp(prefix="rga-invite-")
        store.use_directory(os.path.join(self.root, "work"))
        os.environ["OUT"] = os.path.join(self.root, "out")
        ws.ensure("productive", "Productive", "productive")
        ws.ensure("demo-client", "Demo Client", "demo")
        ws.add_user(ADMIN, "Admin")
        ws.assign(ADMIN, "productive", ws.WORKSPACE_ADMIN)

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.root, ignore_errors=True)

    def pending(self, email=INVITEE, workspace="productive"):
        return ws.invitations(workspace_slug=workspace, email=email,
                              status=ws.PENDING)


class InvitingSomebodyWhoHasNeverSignedIn(Estate):

    def test_it_creates_a_pending_invitation_and_nothing_else(self):
        result = ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)
        self.assertEqual(result["outcome"], "invited")
        self.assertEqual(len(self.pending()), 1)

        # The whole point: no user, no membership, no access.
        self.assertIsNone(ws.user(INVITEE))
        self.assertIsNone(ws.membership_of(INVITEE, "productive"))
        self.assertEqual(ws.workspaces_for(INVITEE), [])

    def test_it_is_audited(self):
        ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)
        actions = [r["action"] for r in ws.audit()]
        self.assertIn("invitation.invited", actions)

    def test_inviting_twice_leaves_one_invitation(self):
        ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)
        result = ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)
        self.assertEqual(result["outcome"], "already_pending")
        self.assertEqual(len(self.pending()), 1)

    def test_re_inviting_at_a_new_role_updates_rather_than_stacks(self):
        """Two standing instructions for one address is one nobody can see."""
        ws.invite(INVITEE, "productive", ws.VIEWER, actor=ADMIN)
        result = ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)
        self.assertEqual(result["outcome"], "pending_role_changed")
        self.assertEqual(len(self.pending()), 1)
        self.assertEqual(self.pending()[0]["role"], ws.OPERATOR)

    def test_an_address_that_is_not_one_is_refused(self):
        for bad in ("", "   ", "not-an-address", "nobody"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    ws.invite(bad, "productive", ws.OPERATOR, actor=ADMIN)

    def test_an_unknown_workspace_is_refused(self):
        with self.assertRaises(ws.NotAMember):
            ws.invite(INVITEE, "no-such-workspace", ws.OPERATOR, actor=ADMIN)


class SuperAdminIsNotOnOffer(Estate):

    def test_it_cannot_be_invited(self):
        """An account-level fact, not a workspace role."""
        with self.assertRaises(ws.RoleNotAssignable):
            ws.invite(INVITEE, "productive", ws.SUPER_ADMIN, actor=ADMIN)
        self.assertEqual(self.pending(), [])

    def test_it_is_not_in_the_assignable_set(self):
        self.assertNotIn(ws.SUPER_ADMIN, ws.assignable_roles())
        for role in ws.assignable_roles():
            self.assertIn(role, ws.ROLES)

    def test_an_invented_role_is_refused(self):
        with self.assertRaises(ws.RoleNotAssignable):
            ws.invite(INVITEE, "productive", "owner", actor=ADMIN)
        self.assertEqual(self.pending(), [])


class InvitingSomebodyWhoAlreadyExists(Estate):

    def setUp(self):
        super().setUp()
        ws.add_user(OTHER, "Other")
        ws.assign(OTHER, "demo-client", ws.VIEWER)

    def test_they_are_added_rather_than_invited(self):
        result = ws.invite(OTHER, "productive", ws.OPERATOR, actor=ADMIN)
        self.assertEqual(result["outcome"], "added")
        self.assertEqual(
            ws.membership_of(OTHER, "productive")["role"], ws.OPERATOR)
        self.assertEqual(self.pending(email=OTHER), [])

    def test_no_duplicate_user_is_created(self):
        ws.invite(OTHER, "productive", ws.OPERATOR, actor=ADMIN)
        self.assertEqual(len([u for u in ws.users()
                              if u["email"] == OTHER]), 1)

    def test_an_existing_member_at_the_same_role_is_idempotent(self):
        ws.invite(OTHER, "productive", ws.OPERATOR, actor=ADMIN)
        result = ws.invite(OTHER, "productive", ws.OPERATOR, actor=ADMIN)
        self.assertEqual(result["outcome"], "already_member")
        self.assertEqual(len(ws.memberships(OTHER, "productive")), 1)

    def test_their_other_workspace_is_untouched(self):
        ws.invite(OTHER, "productive", ws.OPERATOR, actor=ADMIN)
        self.assertEqual(
            ws.membership_of(OTHER, "demo-client")["role"], ws.VIEWER)


class OnlyAProvedAddressConsumesIt(Estate):

    def setUp(self):
        super().setUp()
        ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)

    def test_the_exact_address_gets_the_intended_membership(self):
        done = ws.consume_invitations(INVITEE, subject="google-sub-1")
        self.assertEqual(done, [{"workspace": "productive",
                                 "role": ws.OPERATOR}])
        self.assertIsNotNone(ws.user(INVITEE))
        self.assertEqual(
            ws.membership_of(INVITEE, "productive")["role"], ws.OPERATOR)

    def test_the_new_user_is_not_a_super_admin(self):
        ws.consume_invitations(INVITEE, subject="google-sub-1")
        self.assertFalse(ws.user(INVITEE)["super_admin"])

    def test_the_role_comes_from_the_stored_invitation(self):
        """Nothing about the callback decides it. The role was written by an
        administrator before this person ever appeared."""
        ws.consume_invitations(INVITEE, subject="s")
        self.assertEqual(
            ws.membership_of(INVITEE, "productive")["role"], ws.OPERATOR)

    def test_another_address_at_the_same_domain_gets_nothing(self):
        self.assertEqual(ws.consume_invitations(OTHER, subject="s"), [])
        self.assertIsNone(ws.user(OTHER))
        self.assertEqual(len(self.pending()), 1, "the invitation was spent")

    def test_a_plus_addressed_variant_gets_nothing(self):
        self.assertEqual(
            ws.consume_invitations("tina+work@resonate.test"), [])
        self.assertIsNone(ws.membership_of("tina+work@resonate.test",
                                           "productive"))

    def test_a_prefix_of_the_address_gets_nothing(self):
        for near in ("tina@resonat.test", "tin@resonate.test",
                     "tina@resonate.test.evil.test"):
            with self.subTest(near=near):
                self.assertEqual(ws.consume_invitations(near), [])

    def test_case_and_padding_are_normalised_the_same_on_both_sides(self):
        """An invitation stored lower-case must match what a provider
        returns however it is cased, or it silently never matches."""
        done = ws.consume_invitations("  TINA@Resonate.TEST  ")
        self.assertEqual(done, [{"workspace": "productive",
                                 "role": ws.OPERATOR}])
        self.assertIsNotNone(ws.user(INVITEE))

    def test_it_is_consumed_once(self):
        ws.consume_invitations(INVITEE, subject="s")
        self.assertEqual(self.pending(), [])
        self.assertEqual(ws.consume_invitations(INVITEE, subject="s"), [])

    def test_consumption_is_audited_with_the_subject(self):
        ws.consume_invitations(INVITEE, subject="google-sub-42")
        entry = next(r for r in ws.audit()
                     if r["action"] == "invitation.accepted")
        self.assertEqual(entry["resource_id"], INVITEE)
        self.assertEqual(entry["metadata"]["subject"], "google-sub-42")


class RevocationIsImmediate(Estate):

    def setUp(self):
        super().setUp()
        ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)

    def test_a_revoked_invitation_cannot_be_consumed(self):
        self.assertTrue(ws.revoke_invitation(INVITEE, "productive",
                                             actor=ADMIN))
        self.assertEqual(ws.consume_invitations(INVITEE, subject="s"), [])
        self.assertIsNone(ws.user(INVITEE))
        self.assertIsNone(ws.membership_of(INVITEE, "productive"))

    def test_revoking_is_audited(self):
        ws.revoke_invitation(INVITEE, "productive", actor=ADMIN)
        self.assertIn("invitation.revoked",
                      [r["action"] for r in ws.audit()])

    def test_revoking_nothing_says_so(self):
        self.assertFalse(ws.revoke_invitation(OTHER, "productive",
                                              actor=ADMIN))

    def test_revoking_in_one_workspace_leaves_another(self):
        """Revocation is scoped, like everything else about a workspace."""
        ws.invite(INVITEE, "demo-client", ws.VIEWER, actor=ADMIN)
        ws.revoke_invitation(INVITEE, "productive", actor=ADMIN)

        self.assertEqual(self.pending(workspace="productive"), [])
        self.assertEqual(len(self.pending(workspace="demo-client")), 1)

        # And the surviving one still works.
        self.assertEqual(ws.consume_invitations(INVITEE),
                         [{"workspace": "demo-client", "role": ws.VIEWER}])
        self.assertIsNone(ws.membership_of(INVITEE, "productive"))


class OneWorkspaceIsNotAnother(Estate):

    def test_an_invitation_activates_only_the_workspace_it_names(self):
        ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)
        ws.consume_invitations(INVITEE, subject="s")
        self.assertIsNotNone(ws.membership_of(INVITEE, "productive"))
        self.assertIsNone(ws.membership_of(INVITEE, "demo-client"))
        self.assertEqual([w["slug"] for w in ws.workspaces_for(INVITEE)],
                         ["productive"])

    def test_two_invitations_activate_both_and_only_both(self):
        ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)
        ws.invite(INVITEE, "demo-client", ws.VIEWER, actor=ADMIN)
        done = ws.consume_invitations(INVITEE, subject="s")
        self.assertEqual(
            sorted((d["workspace"], d["role"]) for d in done),
            [("demo-client", ws.VIEWER), ("productive", ws.OPERATOR)])
        self.assertEqual(
            ws.membership_of(INVITEE, "productive")["role"], ws.OPERATOR)
        self.assertEqual(
            ws.membership_of(INVITEE, "demo-client")["role"], ws.VIEWER)


class AnInvitationIsNotAnIdentity(Estate):

    def test_it_creates_no_session_and_no_user_by_itself(self):
        ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)
        self.assertIsNone(ws.user(INVITEE))
        self.assertEqual(ws.workspaces_for(INVITEE), [])

    def test_it_is_invisible_to_the_permission_check(self):
        """`membership_of` is what every authorised request resolves through.
        An invitation must not be visible to it at all."""
        ws.invite(INVITEE, "productive", ws.WORKSPACE_ADMIN, actor=ADMIN)
        self.assertIsNone(ws.membership_of(INVITEE, "productive"))
        self.assertEqual(ws.memberships(INVITEE), [])

    def test_an_invited_address_does_not_appear_as_a_user(self):
        ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)
        self.assertNotIn(INVITEE, [u["email"] for u in ws.users()])


class ExistingStateStillLoads(Estate):
    """Production already holds users, workspaces and memberships written
    before invitations existed. Adding a new row kind must not disturb them."""

    def test_rows_written_without_invitations_are_unaffected(self):
        before = ws.load()
        self.assertTrue(before)
        ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)

        after = {r.get("kind") for r in ws.load()}
        self.assertIn("invitation", after)
        # Everything that was there is still there, unchanged.
        for row in before:
            self.assertIn(row, ws.load())

    def test_the_existing_admin_still_resolves(self):
        ws.invite(INVITEE, "productive", ws.OPERATOR, actor=ADMIN)
        self.assertEqual(
            ws.membership_of(ADMIN, "productive")["role"], ws.WORKSPACE_ADMIN)

    def test_a_store_with_no_invitations_reads_as_none(self):
        self.assertEqual(ws.invitations(workspace_slug="productive"), [])


if __name__ == "__main__":
    unittest.main()
