"""The first administrator: how one gets created, and what cannot create one.

A fresh production deployment is a circle. Nobody can sign in because no
user exists; no user can be created because signing in is how you reach
the screen that would create one. Something has to break it, and the only
interesting question is what that something is allowed to trust.

**It trusts the audit log.** An address in an environment variable is
somebody's claim, and this system does not accept claims - that is the
whole argument of `PRODUCTION-AUTH.md`. An address in the audit log under
`auth.identity_proved` has completed a real authorization code exchange:
state, nonce, audience, issuer, expiry, `email_verified` and domain, all
checked. The variable chooses among proved identities. It cannot invent
one.

So the tests that matter here are the ones where the variable is set to
something and nothing happens.
"""
import os
import shutil
import tempfile
import unittest

from src import store, workspaces
from src.web import app


class Fresh(unittest.TestCase):
    """An empty store, as a newly mounted volume would be."""

    ENV = ("QUEUE", "APP_MODE", "MX_CACHE", "OUT", "CLIENTS_DIR",
           app.BOOTSTRAP_EMAIL_VAR,
           app.BOOTSTRAP_WORKSPACE_VAR) + store.STATE_OVERRIDES

    PROVED = "operator@resonate.test"
    STRANGER = "someone.else@resonate.test"

    def setUp(self):
        self._prev = {k: os.environ.get(k) for k in self.ENV}
        self.root = tempfile.mkdtemp(prefix="rga-bootstrap-")
        store.use_directory(os.path.join(self.root, "work"))
        os.environ["OUT"] = os.path.join(self.root, "out")
        # A real client config has to exist for the workspace to be usable,
        # so the tests use the one that ships.
        os.environ.pop("CLIENTS_DIR", None)

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.root, ignore_errors=True)

    def prove(self, email):
        """What `/auth/callback` writes when a provider proved somebody it
        then had to refuse for having no user row."""
        workspaces.record(email, None, workspaces.IDENTITY_PROVED,
                          resource_type="sign_in",
                          resource_id="unknown_identity",
                          metadata={"kind": "unknown_identity"})

    def refuse(self, email):
        """What it writes when the proof itself failed."""
        workspaces.record(email, None, workspaces.IDENTITY_REFUSED,
                          resource_type="sign_in",
                          resource_id="provider_sign_in_failed",
                          metadata={"kind": "provider_sign_in_failed"})


class ItReadsTheAuditLog(Fresh):

    def test_a_proved_address_is_offered(self):
        self.prove(self.PROVED)
        self.assertEqual(workspaces.proved_addresses(), [self.PROVED])

    def test_a_failed_sign_in_is_not(self):
        """Somebody who could not prove who they are never becomes eligible.

        This is the distinction the audit action carries, and it was wrong
        once: every sign-in event was written as `security.refused`, so a
        successful proof and a failed one were the same row.
        """
        self.refuse(self.STRANGER)
        self.assertEqual(workspaces.proved_addresses(), [])

    def test_nothing_proved_means_nothing_offered(self):
        self.assertEqual(workspaces.proved_addresses(), [])


class WhatCannotCreateAnAdministrator(Fresh):

    def test_an_address_that_never_signed_in(self):
        """The attack this exists to stop: naming somebody in a variable."""
        with self.assertRaises(workspaces.BootstrapRefused) as caught:
            workspaces.bootstrap_super_admin(self.STRANGER, "productive")
        self.assertIn("never proved itself", str(caught.exception))
        self.assertEqual(workspaces.users(), [])

    def test_an_address_whose_sign_in_failed(self):
        self.refuse(self.STRANGER)
        with self.assertRaises(workspaces.BootstrapRefused):
            workspaces.bootstrap_super_admin(self.STRANGER, "productive")
        self.assertEqual(workspaces.users(), [])

    def test_naming_a_different_address_than_the_one_that_proved_itself(self):
        """Somebody with the deployment's variables but not the mailbox."""
        self.prove(self.PROVED)
        with self.assertRaises(workspaces.BootstrapRefused):
            workspaces.bootstrap_super_admin(self.STRANGER, "productive")
        self.assertEqual(workspaces.users(), [])

    def test_no_address_at_all(self):
        with self.assertRaises(workspaces.BootstrapRefused):
            workspaces.bootstrap_super_admin("", "productive")

    def test_no_workspace(self):
        """A super admin with none cannot enter the console, and nothing in
        the application creates one."""
        self.prove(self.PROVED)
        with self.assertRaises(workspaces.BootstrapRefused) as caught:
            workspaces.bootstrap_super_admin(self.PROVED, "")
        # Specific to *this* refusal. "workspace" alone also appears in the
        # missing-client-config message, so the loose assertion passed while
        # the guard under test was disabled - a different guard firing first,
        # which is the failure mode the audit exists to expose.
        self.assertIn("cannot enter", str(caught.exception))
        self.assertEqual(workspaces.users(), [])

    def test_a_workspace_with_no_client_config(self):
        """It fails before writing, not after.

        A workspace whose config is missing is one whose every screen
        raises, and a half-finished bootstrap is worse than none: the
        second attempt would find a user and go inert.
        """
        self.prove(self.PROVED)
        with self.assertRaises(workspaces.BootstrapRefused):
            workspaces.bootstrap_super_admin(self.PROVED, "no-such-client")
        self.assertEqual(workspaces.users(), [])
        self.assertEqual(workspaces.workspaces(), [])


class WhatDoes(Fresh):

    def bootstrap(self):
        self.prove(self.PROVED)
        return workspaces.bootstrap_super_admin(self.PROVED, "productive")

    def test_it_creates_the_user_the_workspace_and_the_grant(self):
        result = self.bootstrap()
        self.assertEqual(result["email"], self.PROVED)
        self.assertEqual(result["workspace"], "productive")

        person = workspaces.user(self.PROVED)
        self.assertIsNotNone(person)
        self.assertTrue(person["super_admin"])
        self.assertTrue(workspaces.workspace("productive"))

    def test_the_grant_is_auditable(self):
        """An escalation nobody can find afterwards is not auditable."""
        self.bootstrap()
        actions = [r["action"] for r in workspaces.audit()]
        self.assertIn(workspaces.BOOTSTRAP_ACTION, actions)
        entry = next(r for r in workspaces.audit()
                     if r["action"] == workspaces.BOOTSTRAP_ACTION)
        self.assertEqual(entry["resource_id"], self.PROVED)
        self.assertTrue(entry["metadata"]["super_admin"])

    def test_the_admin_can_now_reach_a_workspace(self):
        """The 403 the owner saw was `workspaces_for` returning nothing."""
        self.assertEqual(workspaces.workspaces_for(self.PROVED), [])
        self.bootstrap()
        self.assertTrue(workspaces.workspaces_for(self.PROVED))

    def test_the_role_resolved_for_them_is_super_admin(self):
        self.bootstrap()
        found = workspaces.membership_of(self.PROVED, "productive")
        self.assertEqual(found["role"], workspaces.SUPER_ADMIN)
        self.assertEqual(found["via"], "super_admin")


class ItIsInertAfterwards(Fresh):

    def test_a_second_run_changes_nothing(self):
        self.prove(self.PROVED)
        workspaces.bootstrap_super_admin(self.PROVED, "productive")
        before = workspaces.load()
        self.assertIsNone(
            workspaces.bootstrap_super_admin(self.PROVED, "productive"))
        self.assertEqual(workspaces.load(), before)

    def test_it_cannot_promote_a_second_person(self):
        """The escalation route: wait until somebody signs in, then name
        yourself. Any existing user closes it."""
        self.prove(self.PROVED)
        workspaces.bootstrap_super_admin(self.PROVED, "productive")
        self.prove(self.STRANGER)
        self.assertIsNone(
            workspaces.bootstrap_super_admin(self.STRANGER, "productive"))
        self.assertIsNone(workspaces.user(self.STRANGER))

    def test_it_cannot_re_promote_somebody_who_was_demoted(self):
        """A user existing at all is what makes it inert - not that user
        being an administrator."""
        self.prove(self.PROVED)
        workspaces.bootstrap_super_admin(self.PROVED, "productive")
        rows = workspaces.load()
        for row in rows:
            if row.get("kind") == "user":
                row["super_admin"] = False
        workspaces.save(rows)

        self.assertIsNone(
            workspaces.bootstrap_super_admin(self.PROVED, "productive"))
        self.assertFalse(workspaces.user(self.PROVED)["super_admin"])


class TheStartupHook(Fresh):

    def test_it_does_nothing_when_the_variable_is_unset(self):
        self.prove(self.PROVED)
        self.assertIsNone(app.run_bootstrap())
        self.assertEqual(workspaces.users(), [])

    def test_it_runs_when_the_variable_is_set(self):
        self.prove(self.PROVED)
        os.environ[app.BOOTSTRAP_EMAIL_VAR] = self.PROVED
        os.environ[app.BOOTSTRAP_WORKSPACE_VAR] = "productive"
        said = []
        result = app.run_bootstrap(say=said.append)
        self.assertEqual(result["email"], self.PROVED)
        self.assertTrue(any("SUPER_ADMIN" in line for line in said))

    def test_a_refusal_is_reported_and_does_not_stop_the_process(self):
        """Refusing to serve as well would take away the sign-in screen
        that produces the proof the bootstrap is asking for."""
        os.environ[app.BOOTSTRAP_EMAIL_VAR] = self.STRANGER
        os.environ[app.BOOTSTRAP_WORKSPACE_VAR] = "productive"
        said = []
        self.assertIsNone(app.run_bootstrap(say=said.append))
        self.assertTrue(any("refused" in line.lower() for line in said))
        self.assertEqual(workspaces.users(), [])

    def test_it_says_so_when_it_is_inert(self):
        self.prove(self.PROVED)
        workspaces.bootstrap_super_admin(self.PROVED, "productive")
        os.environ[app.BOOTSTRAP_EMAIL_VAR] = self.PROVED
        os.environ[app.BOOTSTRAP_WORKSPACE_VAR] = "productive"
        said = []
        app.run_bootstrap(say=said.append)
        self.assertTrue(any("inert" in line for line in said))


if __name__ == "__main__":
    unittest.main()
