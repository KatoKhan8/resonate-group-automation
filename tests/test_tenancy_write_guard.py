"""A repo cannot write a record it does not own - including a new one.

`Repo.save_records` has two tenancy guards and the mutation audit found that
only one of them is load-bearing under test:

    for rec in records:                     # guard 1: is the row I was handed mine
        if not self._mine(rec): raise
    ...
        if not self._mine(existing): raise  # guard 2: was it re-tenanted under me

`test_repo.test_saving_a_record_that_is_not_yours_is_refused` hands over a
record that *already exists* in the queue under another client. With guard 1
disabled, guard 2 still fires on the existing row, so the test passes and the
mutation "let a write touch a record this repo does not own" survives.

The uncovered path is a record that does not exist yet. Nothing in the queue
matches its id, so guard 2 never runs and `rows.extend(by_id.values())`
appends it: one tenant creating a record owned by another. That is the write
side of the boundary, and it was the half nothing tested.

This is redundancy masking a gap rather than providing depth - two guards
where the test only ever exercises the path the second one covers.
"""
import unittest

from src import repo as repo_module, store
from tests.test_repo import RepoTest

FOREIGN = "contactout"


class ARepoCannotWriteWhatItDoesNotOwn(RepoTest):

    def ids(self):
        return [r["id"] for r in store.load()]

    # ------------------------------------------------ the uncovered path

    def test_it_cannot_create_a_record_owned_by_another_client(self):
        """No existing row to compare against, so only guard 1 stands here."""
        new = store.new_record("invented-by-the-wrong-tenant", "domains",
                               FOREIGN, "Theirs Ltd", "theirs.test")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.mine().save_records([new])
        self.assertNotIn("invented-by-the-wrong-tenant", self.ids())

    def test_the_refusal_names_the_record_rather_than_the_client(self):
        new = store.new_record("invented-2", "domains", FOREIGN, "T", "t.test")
        try:
            self.mine().save_records([new])
        except repo_module.CrossClientAccess as e:
            self.assertIn("invented-2", str(e))
        else:
            self.fail("the write was not refused")

    def test_one_foreign_row_refuses_the_whole_batch(self):
        """All or nothing: a partial write is a breach that also corrupts."""
        before = self.ids()
        mine = [r for r in store.load() if r["client"] == "productive"]
        mine[0]["company"] = "Legitimately renamed"
        foreign = store.new_record("smuggled", "domains", FOREIGN, "T", "t.test")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.mine().save_records(mine + [foreign])
        self.assertEqual(self.ids(), before)
        self.assertNotIn("Legitimately renamed",
                         [r["company"] for r in store.load()])

    def test_a_record_carrying_no_client_is_refused(self):
        """Absent is not mine. Missing evidence is never positive evidence."""
        orphan = store.new_record("orphan", "domains", "productive", "O",
                                  "o.test")
        orphan.pop("client")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.mine().save_records([orphan])
        self.assertNotIn("orphan", self.ids())

    def test_relabelling_a_foreign_record_does_not_capture_it(self):
        """The obvious attack: take their row, stamp it mine, write it back."""
        stolen = [r for r in store.load() if r["client"] == FOREIGN][0]
        stolen = dict(stolen, client="productive",
                      company="Captured by the wrong tenant")
        with self.assertRaises(repo_module.CrossClientAccess):
            self.mine().save_records([stolen])
        after = {r["id"]: r for r in store.load()}
        self.assertEqual(after[stolen["id"]]["client"], FOREIGN)
        self.assertNotIn("Captured by the wrong tenant",
                         [r["company"] for r in store.load()])

    # ------------------------------------------- and the honest path works

    def test_a_repo_can_still_write_its_own_records(self):
        """Otherwise the guard refuses everything and proves nothing."""
        mine = [r for r in store.load() if r["client"] == "productive"]
        mine[0]["company"] = "Renamed by its owner"
        self.mine().save_records(mine)
        self.assertIn("Renamed by its owner",
                      [r["company"] for r in store.load()])

    def test_a_repo_can_create_its_own_new_record(self):
        new = store.new_record("mine-and-new", "domains", "productive", "M",
                               "m.test")
        self.mine().save_records([new])
        self.assertIn("mine-and-new", self.ids())

    def test_the_other_tenants_rows_are_carried_through_untouched(self):
        before = {r["id"]: dict(r) for r in store.load()
                  if r["client"] == FOREIGN}
        mine = [r for r in store.load() if r["client"] == "productive"]
        self.mine().save_records(mine)
        after = {r["id"]: r for r in store.load() if r["client"] == FOREIGN}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
