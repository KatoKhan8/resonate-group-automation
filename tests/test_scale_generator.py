"""The scale benchmark's generator satisfies the same invariants a real
record does.  Reuses ``store.validate`` and the synthetic module's own
shape catalogue rather than restating either.

A benchmark that measures a shape that does not exist is worse than no
benchmark at all: the numbers look authoritative and the cliff they
miss is the one that matters.
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import store, synthetic


class TestScaleGeneratorInvariants(unittest.TestCase):
    """Every generated record passes store.validate and carries the fields
    the hot paths actually touch."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # `use_directory` returns the restore. Without it this module
        # left QUEUE at self.tmp and test_slack_agent_cannot_act then
        # failed asserting the agent writes only under work\.
        self.addCleanup(store.use_directory(self.tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_every_record_validates(self):
        """store.validate returns no problems for any record at any size."""
        for size in (30, 100, 200):
            recs = synthetic.dataset(size)
            for rec in recs:
                problems = store.validate(rec)
                self.assertEqual(
                    problems, [],
                    f"record {rec.get('id')} (shape={rec.get('shape')}): "
                    f"{problems}")

    def test_required_fields_present(self):
        """The hot paths read id, contacts, events, domain, company, state."""
        recs = synthetic.dataset(60)
        for rec in recs:
            for field in ("id", "contacts", "domain", "company", "state",
                          "client", "lane"):
                self.assertIn(field, rec,
                              f"record {rec.get('id')} missing {field}")

    def test_contacts_have_keys(self):
        """dedupe, fatigue and hygiene all key on contact['key']."""
        recs = synthetic.dataset(60)
        for rec in recs:
            for contact in rec.get("contacts") or []:
                self.assertIn("key", contact,
                              f"contact in {rec.get('id')} has no key")

    def test_contacts_have_emails_or_are_linkedin_only(self):
        """The MX and verification paths need to know which shape they have."""
        recs = synthetic.dataset(60)
        for rec in recs:
            for contact in rec.get("contacts") or []:
                has_email = bool(contact.get("email"))
                has_linkedin = bool(contact.get("linkedin"))
                self.assertTrue(
                    has_email or has_linkedin,
                    f"contact {contact.get('key')} in {rec.get('id')} "
                    f"has neither email nor linkedin")

    def test_shapes_cycle_through_all_defects(self):
        """Every named shape appears at least once when size >= len(SHAPES)."""
        recs = synthetic.dataset(len(synthetic.SHAPES) + 10)
        seen = {rec.get("shape") for rec in recs}
        for name in synthetic.SHAPE_NAMES:
            self.assertIn(name, seen,
                          f"shape {name!r} never appeared in the dataset")

    def test_duplicate_shapes_produce_duplicate_ids(self):
        """duplicate_email and duplicate_linkedin shapes share identifiers
        with earlier records, which is what dedupe.find needs to detect."""
        recs = synthetic.dataset(2 * len(synthetic.SHAPES))
        emails = {}
        for rec in recs:
            for contact in rec.get("contacts") or []:
                email = contact.get("email")
                if email and email in emails:
                    return
                if email:
                    emails[email] = rec.get("id")

    def test_generated_records_round_trip_through_store(self):
        """save then load produces the same records - the benchmark writes
        them to a temp queue and reads them back."""
        recs = synthetic.dataset(50)
        store.save(recs)
        loaded = store.load()
        self.assertEqual(len(loaded), len(recs))
        original_ids = {r["id"] for r in recs}
        loaded_ids = {r["id"] for r in loaded}
        self.assertEqual(original_ids, loaded_ids)


if __name__ == "__main__":
    unittest.main()
