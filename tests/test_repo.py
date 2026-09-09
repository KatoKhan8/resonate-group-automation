"""The persistence seam, and the boundary it is there to make unforgettable.

WEB-READINESS names the gap this closes by name: *client isolation is a filter,
not a boundary*. A filter is applied by a caller and can therefore be omitted by
a caller. What `Repo` provides instead is an object that has **no unscoped
call on it** - so a handler cannot forget the filter, because there is nothing
to forget.

Every test here is really the same test asked a different way: is there any
route through this class that returns another tenant's row?
"""
import os
import shutil
import tempfile
import unittest

from src import clients, repo as repo_module, store, workspaces


class RepoTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-repo-")
        self._prev = {k: os.environ.get(k)
                      for k in ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES",
                                "AUDIT", "CLIENTS_DIR")}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")

        from src.web import demodata
        demodata.install_configs()

        workspaces.ensure("productive", "Productive", client="productive")
        workspaces.ensure("contactout", "ContactOut", client="contactout")
        workspaces.add_user("op@x.test", "Op")
        workspaces.add_user("root@x.test", "Root", super_admin=True)
        workspaces.assign("op@x.test", "productive", workspaces.OPERATOR)

        rows = []
        for client, batch in (("productive", "uk"), ("contactout", "apac")):
            for i in range(3):
                rec = store.new_record(f"{batch}-{i}", "domains", client,
                                       f"Company {batch} {i}",
                                       f"{batch}{i}.test")
                rec["batch"] = batch
                rec["contacts"] = [{"key": f"{batch}-{i}-a",
                                    "name": "A Person"}]
                rows.append(rec)
        store.save(rows)

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def mine(self):
        return repo_module.Repo.for_user("op@x.test", "productive")


class Scoping(RepoTest):

    def test_a_repo_returns_only_its_own_records(self):
        self.assertEqual(sorted(r["id"] for r in self.mine().records()),
                         ["uk-0", "uk-1", "uk-2"])

    def test_reaching_for_another_tenants_record_raises_rather_than_returning_none(self):
        """None reads as "nothing there". This is not nothing; it is not yours,
        and the caller must not be able to mistake the two."""
        with self.assertRaises(repo_module.CrossClientAccess):
            self.mine().record("apac-0")

    def test_a_record_that_does_not_exist_returns_none(self):
        self.assertIsNone(self.mine().record("nope"))

    def test_reaching_for_another_tenants_contact_raises(self):
        with self.assertRaises(repo_module.CrossClientAccess):
            self.mine().contact("apac-0", "apac-0-a")

    def test_saving_a_record_that_is_not_yours_is_refused(self):
        """The write side of the same boundary. A repo that reads safely and
        writes anywhere has closed one door and left the other open."""
        stolen = [r for r in store.load() if r["client"] == "contactout"]
        stolen[0]["company"] = "Renamed by the wrong tenant"
        with self.assertRaises(repo_module.CrossClientAccess):
            self.mine().save_records(stolen)
        self.assertNotIn("Renamed by the wrong tenant",
                         [r["company"] for r in store.load()])

    def test_batches_and_stats_are_scoped_too(self):
        """The aggregate is where a filter is most often forgotten, because
        the result is a number rather than a row and nothing looks wrong."""
        self.assertEqual(list(self.mine().batches()), ["uk"])
        self.assertEqual(self.mine().stats()["records"], 3)


class Construction(RepoTest):

    def test_for_user_requires_a_membership(self):
        with self.assertRaises(workspaces.NotAMember):
            repo_module.Repo.for_user("op@x.test", "contactout")

    def test_an_unknown_workspace_is_the_same_refusal(self):
        with self.assertRaises(workspaces.NotAMember):
            repo_module.Repo.for_user("op@x.test", "no-such-thing")

    def test_a_super_admin_may_enter_any_workspace(self):
        repo = repo_module.Repo.for_user("root@x.test", "contactout")
        self.assertEqual(sorted(r["id"] for r in repo.records()),
                         ["apac-0", "apac-1", "apac-2"])
        self.assertEqual(repo.role(), workspaces.SUPER_ADMIN)

    def test_a_slug_cannot_walk_out_of_the_config_directory(self):
        """The slug pattern is also the path-traversal guard, which is why it
        is a pattern and not a `not in` check."""
        for hostile in ("../../etc/passwd", "..\\..\\windows", "a/b",
                        "Productive", "", "x" * 200):
            with self.assertRaises((repo_module.UnknownClient,
                                    workspaces.NotAMember)):
                repo_module.Repo.for_client(hostile)

    def test_the_cli_constructor_still_works_without_a_user(self):
        repo = repo_module.Repo.for_client("productive")
        self.assertEqual(len(repo.records()), 3)
        self.assertIsNone(repo.membership)

    def test_a_cli_repo_carries_no_permission(self):
        """It is scoped but unauthenticated, so `require` must refuse rather
        than pass. A CLI that inherits a web permission check by accident is
        a permission check that means nothing."""
        repo = repo_module.Repo.for_client("productive")
        with self.assertRaises(workspaces.NotPermitted):
            repo.require(workspaces.CONTACTS_VIEW)


class Permissions(RepoTest):

    def test_require_reflects_the_membership_role(self):
        repo = self.mine()
        self.assertTrue(repo.require(workspaces.CONTACTS_VIEW))
        with self.assertRaises(workspaces.NotPermitted):
            repo.require(workspaces.USERS_MANAGE)

    def test_an_audit_entry_is_attributed_to_the_user_and_the_workspace(self):
        self.mine().audit("export.contacts", "workspace", "productive")
        entry = workspaces.audit(workspace_slug="productive")[0]
        self.assertEqual(entry["actor"], "op@x.test")
        self.assertEqual(entry["workspace"], "productive")


class TheAdminDoor(RepoTest):

    def test_admin_repo_is_unscoped_and_is_the_only_one_that_is(self):
        """Named so a reader auditing "what can cross a boundary" has one
        place to look, and so a grep for it finds every caller."""
        self.assertEqual(len(repo_module.admin_repo().records()), 6)
        self.assertIsNone(repo_module.admin_repo().client)
