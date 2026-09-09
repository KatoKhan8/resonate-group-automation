"""Re-importing a list must not touch what the account already said.

The same spreadsheet coming back next month with more people on it is the
normal case. `parse` deliberately keeps a row whose hygiene verdict has
something to say - so an operator can read *why* a company is not
cold-eligible rather than watching it vanish - which means a suppressed
company reaches `commit` by design.

`commit` then built a fresh `store.new_record` for it. That skeleton has no
suppression, no events and no unsubscribed flags, and `save_records`
upserts by id, so a company that had asked to stop came back clean: the
removal request, the event log and the per-contact flag all gone, with
nothing anywhere recording that it was ever made. "Never delete a queue
record" was being violated by an import.

Two things had to be true to fix it and only one of them is obvious.
Colliding ids had to stop overwriting - `slug` truncates at 40 characters
and this path had none of the de-collision `ingest.run` has always carried,
so two different companies could share an id. But de-collision alone turns
an overwrite into a *duplicate*: two records for one domain, one suppressed
and one not, which is a different wrong answer to the same question. The
account is the unit of outreach, so an existing account is merged into and
never rebuilt. An import may add people. It may not have an opinion about
suppression, events, state or anybody's unsubscribed flag.
"""
import unittest

from src import accountpolicy as ap, hygiene, identity, ingest, store
from src.repo import Repo
from src.web import upload
from tests.base import QueueTest

AT = "2026-09-01T00:00:00+00:00"
ONE = "company,domain,email\r\nAcme,acme.test,champ@acme.test\r\n"
TWO = ("company,domain,email\r\nAcme,acme.test,champ@acme.test\r\n"
       "Acme,acme.test,newperson@acme.test\r\n")


class Reimport(QueueTest):

    def setUp(self):
        super().setUp()
        self.repo = Repo.for_client("demo")
        self.repo.actor = "ops@demo.test"

    def imported(self, csv, batch="b1"):
        mine = self.repo.records()
        parsed = upload.parse(
            csv.encode(), existing_domains={r.get("domain") for r in mine},
            batch=batch, client="demo",
            history=hygiene.index(mine, workspace="demo"))
        upload.commit(self.repo, parsed)
        return parsed

    def rows(self):
        return store.load()

    def acme(self):
        found = [r for r in self.rows() if r.get("domain") == "acme.test"]
        self.assertEqual(len(found), 1,
                         f"expected one record for acme.test, got {len(found)}")
        return found[0]

    def suppress(self):
        with store.transaction() as rows:
            rec = rows[0]
            ap.apply_reply(rec, rec["contacts"][0]["key"], ap.ACCOUNT_DNC,
                           at=AT, channel="email", reason="test",
                           workspace="demo")


class AnAccountKeepsItsHistory(Reimport):

    def test_a_removal_request_survives_a_re_import(self):
        """The defect. The company had asked to stop."""
        self.imported(ONE)
        self.suppress()
        self.assertTrue(self.acme().get("suppression"))
        self.imported(TWO, batch="b2")
        self.assertTrue(self.acme().get("suppression"),
                        "re-importing the list erased a do-not-contact")

    def test_the_events_survive_it(self):
        """Not only the flag. Without the log, nobody can show it was
        ever asked for."""
        self.imported(ONE)
        self.suppress()
        before = len(self.acme().get("events") or [])
        self.assertGreater(before, 0)
        self.imported(TWO, batch="b2")
        self.assertEqual(len(self.acme().get("events") or []), before)

    def test_the_persons_own_flag_survives_it(self):
        self.imported(ONE)
        self.suppress()
        self.imported(TWO, batch="b2")
        champ = [c for c in self.acme()["contacts"]
                 if c.get("email") == "champ@acme.test"][0]
        self.assertTrue(champ.get("unsubscribed"))

    def test_there_is_still_exactly_one_record_for_the_company(self):
        """De-collision alone would have duplicated rather than
        overwritten, which answers the same question wrongly in the other
        direction."""
        self.imported(ONE)
        self.suppress()
        self.imported(TWO, batch="b2")
        self.assertEqual(
            [r["id"] for r in self.rows() if r["domain"] == "acme.test"],
            [ingest.slug("acme.test")])

    def test_the_record_id_does_not_change_under_it(self):
        """Every id-addressed route and every campaign membership list
        refers to the record by id."""
        self.imported(ONE)
        before = self.acme()["id"]
        self.imported(TWO, batch="b2")
        self.assertEqual(self.acme()["id"], before)


class AnImportMayStillAddPeople(Reimport):
    """The other half. A merge that adds nothing is not a merge."""

    def test_a_new_person_at_a_known_company_is_added(self):
        self.imported(ONE)
        self.imported(TWO, batch="b2")
        self.assertIn("newperson@acme.test",
                      [c.get("email") for c in self.acme()["contacts"]])

    def test_a_person_already_on_the_record_is_not_duplicated(self):
        self.imported(ONE)
        self.imported(TWO, batch="b2")
        emails = [c.get("email") for c in self.acme()["contacts"]]
        self.assertEqual(sorted(emails),
                         ["champ@acme.test", "newperson@acme.test"])

    def test_every_contact_still_has_a_key(self):
        self.imported(ONE)
        self.imported(TWO, batch="b2")
        keys = [c.get("key") for c in self.acme()["contacts"]]
        self.assertTrue(all(keys), keys)
        self.assertEqual(len(set(keys)), len(keys), "duplicate contact keys")

    def test_a_company_that_is_genuinely_new_is_still_created(self):
        self.imported(ONE)
        self.imported("company,domain,email\r\nCairn,cairn.test,a@cairn.test\r\n",
                      batch="b3")
        self.assertEqual(
            sorted(r["domain"] for r in self.rows()),
            ["acme.test", "cairn.test"])


class TwoCompaniesAreNeverOneRecord(Reimport):
    """`slug` truncates at 40 characters and this path had no de-collision,
    so two different companies could arrive under one id - and the second
    silently replaced the first while the audit recorded both."""

    LONG = ("company,domain\r\n"
            "Northwind Holdings,northwind-industrial-holdings-europe-gmbh.test\r\n"
            "Northwind Holdings DE,northwind-industrial-holdings-europe-gmbh.de\r\n")

    def test_both_companies_are_written(self):
        self.imported(self.LONG)
        self.assertEqual(len(self.rows()), 2)

    def test_they_do_not_share_an_id(self):
        self.imported(self.LONG)
        ids = [r["id"] for r in self.rows()]
        self.assertEqual(len(set(ids)), 2, ids)

    def test_the_ids_in_the_queue_are_unique_overall(self):
        self.imported(self.LONG)
        ids = [r["id"] for r in self.rows()]
        self.assertEqual(len(set(ids)), len(ids))


if __name__ == "__main__":
    unittest.main()
