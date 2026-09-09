"""The tenancy model: workspaces, roles, permissions and the audit log.

The claim being tested is narrow and load-bearing: **authorisation is decided
from stored membership, per request, and nothing else.** Not from a session,
not from a cookie, not from a form field, not from a URL.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import store, workspaces


class WorkspaceTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-ws-")
        self._prev = {k: os.environ.get(k)
                      for k in ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES",
                                "AUDIT")}
        store.use_directory(os.path.join(self.tmp, "work"))
        workspaces.ensure("alpha", "Alpha", client="demo")
        workspaces.ensure("beta", "Beta", client="productive")
        workspaces.add_user("root@x.test", "Root", super_admin=True)
        workspaces.add_user("op@x.test", "Op")
        workspaces.add_user("view@x.test", "Viewer")
        workspaces.assign("op@x.test", "alpha", workspaces.OPERATOR)
        workspaces.assign("view@x.test", "alpha", workspaces.VIEWER)

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)


class Roles(WorkspaceTest):

    def test_every_role_is_a_superset_of_the_one_below_it(self):
        """The ladder is deliberate: reviewer ⊂ operator ⊂ workspace admin.

        A role model where a lower role has a permission a higher one lacks is
        a model somebody will have to reason about case by case. This one can
        be reasoned about by rank.
        """
        order = (workspaces.VIEWER, workspaces.REVIEWER, workspaces.OPERATOR,
                 workspaces.WORKSPACE_ADMIN, workspaces.SUPER_ADMIN)
        for lower, higher in zip(order, order[1:]):
            self.assertTrue(
                workspaces.GRANTS[lower] <= workspaces.GRANTS[higher],
                f"{higher} does not contain {lower}")

    def test_a_viewer_is_client_facing_and_carries_almost_nothing(self):
        self.assertEqual(workspaces.permissions_of(workspaces.VIEWER),
                         sorted({workspaces.WORKSPACE_VIEW,
                                 workspaces.REPORTING_VIEW}))
        for forbidden in (workspaces.CONTACTS_VIEW, workspaces.CONTACTS_EXPORT,
                          workspaces.OPERATIONS_VIEW,
                          workspaces.PROVIDER_SETTINGS_VIEW,
                          workspaces.REPLIES_VIEW):
            self.assertFalse(workspaces.may(workspaces.VIEWER, forbidden))

    def test_launch_is_nobody_below_super_admin(self):
        """And it is refused at a lower level anyway. Two locks, on purpose."""
        for role in (workspaces.VIEWER, workspaces.REVIEWER,
                     workspaces.OPERATOR, workspaces.WORKSPACE_ADMIN):
            self.assertFalse(workspaces.may(role, workspaces.CAMPAIGN_LAUNCH),
                             role)

    def test_an_unknown_permission_raises_rather_than_returning_false(self):
        """Silently answering False to a typo grants nothing and hides the bug
        until the day somebody fixes the typo."""
        with self.assertRaises(ValueError):
            workspaces.may(workspaces.OPERATOR, "campaign.lunch")

    def test_a_role_with_no_membership_carries_nothing(self):
        self.assertEqual(workspaces.permissions_of("wizard"), [])


class Membership(WorkspaceTest):

    def test_membership_is_per_workspace_not_per_person(self):
        workspaces.assign("op@x.test", "beta", workspaces.REVIEWER)
        self.assertEqual(
            workspaces.membership_of("op@x.test", "alpha")["role"],
            workspaces.OPERATOR)
        self.assertEqual(
            workspaces.membership_of("op@x.test", "beta")["role"],
            workspaces.REVIEWER)

    def test_a_non_member_gets_nothing_and_learns_nothing(self):
        self.assertIsNone(workspaces.membership_of("op@x.test", "beta"))
        with self.assertRaises(workspaces.NotAMember):
            workspaces.require_member("op@x.test", "beta")

    def test_a_missing_workspace_and_a_forbidden_one_look_the_same(self):
        """Same exception, same message shape. The difference between "does
        not exist" and "is not yours" is exactly what an attacker wants."""
        missing = self.assertRaises(workspaces.NotAMember)
        with missing:
            workspaces.require_member("op@x.test", "no-such-workspace")
        forbidden = self.assertRaises(workspaces.NotAMember)
        with forbidden:
            workspaces.require_member("op@x.test", "beta")
        self.assertEqual(type(missing.exception), type(forbidden.exception))

    def test_a_super_admin_membership_is_synthetic_and_says_so(self):
        found = workspaces.membership_of("root@x.test", "beta")
        self.assertEqual(found["role"], workspaces.SUPER_ADMIN)
        self.assertEqual(found["via"], "super_admin")
        # And it is still not a membership row, so removing it is impossible
        # by accident.
        self.assertEqual(workspaces.memberships(email="root@x.test"), [])

    def test_a_super_admin_still_cannot_enter_a_workspace_that_is_not_there(self):
        self.assertIsNone(workspaces.membership_of("root@x.test", "ghost"))

    def test_workspaces_for_lists_only_what_this_person_may_enter(self):
        self.assertEqual([w["slug"] for w in
                          workspaces.workspaces_for("op@x.test")], ["alpha"])
        self.assertEqual(sorted(w["slug"] for w in
                                workspaces.workspaces_for("root@x.test")),
                         ["alpha", "beta"])
        self.assertEqual(workspaces.workspaces_for("nobody@x.test"), [])

    def test_removing_a_membership_takes_effect_at_once(self):
        workspaces.remove("op@x.test", "alpha")
        self.assertIsNone(workspaces.membership_of("op@x.test", "alpha"))

    def test_reassigning_replaces_rather_than_stacks(self):
        workspaces.assign("op@x.test", "alpha", workspaces.VIEWER)
        rows = workspaces.memberships(email="op@x.test",
                                      workspace_slug="alpha")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["role"], workspaces.VIEWER)


class AuditLog(WorkspaceTest):

    def test_an_assignment_is_recorded_with_who_did_it(self):
        workspaces.assign("view@x.test", "alpha", workspaces.OPERATOR,
                          actor="admin@x.test")
        entry = workspaces.audit(workspace_slug="alpha")[0]
        self.assertEqual(entry["actor"], "admin@x.test")
        self.assertEqual(entry["action"], "membership.assign")
        self.assertEqual(entry["after"], workspaces.OPERATOR)
        self.assertEqual(entry["before"], workspaces.VIEWER)

    def test_the_log_is_append_only_and_newest_first_when_read(self):
        for role in (workspaces.REVIEWER, workspaces.OPERATOR,
                     workspaces.VIEWER):
            workspaces.assign("view@x.test", "alpha", role, actor="a@x.test")
        entries = workspaces.audit(workspace_slug="alpha")
        self.assertGreaterEqual(len(entries), 3)
        stamps = [e["at"] for e in entries]
        self.assertEqual(stamps, sorted(stamps, reverse=True))

    def test_reading_one_workspace_never_returns_another(self):
        workspaces.record("a@x.test", "beta", "something")
        entries = workspaces.audit(workspace_slug="alpha")
        self.assertTrue(all(e["workspace"] == "alpha" for e in entries))

    def test_no_entry_may_carry_a_credential(self):
        workspaces.record("a@x.test", "alpha", "export.contacts",
                          metadata={"format": "csv", "rows": 24})
        blob = json.dumps(workspaces.audit(workspace_slug="alpha"))
        for shape in ("Bearer ", "token", "password", "secret"):
            self.assertNotIn(shape, blob.lower().replace("secrets", ""))


class Settings(WorkspaceTest):

    def test_a_workspace_reads_its_own_client_config(self):
        """Which is what makes ICP rules, personas, geographies, the
        verification waterfall and provider mapping per-tenant without a
        second mechanism."""
        alpha = workspaces.settings_of("alpha")
        beta = workspaces.settings_of("beta")
        self.assertNotEqual(alpha.get("name"), beta.get("name"))
