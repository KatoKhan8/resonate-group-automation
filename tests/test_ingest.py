"""ingest.py: the Phase 1 test from BUILD-SPEC section 10.

A CSV with a suppressed domain, a duplicate and a missing domain yields the
right queue and the right skip reasons.
"""
import os
import tempfile
import unittest

from src import ingest, store
from tests.base import FIXTURES, QueueTest

CSV = os.path.join(FIXTURES, "phase1.csv")
# A fictional suppression list, so the fixture never names a real client.
SUPPRESS = os.path.join(FIXTURES, "suppress-test.txt")


class TestPhase1Csv(QueueTest):
    def setUp(self):
        super().setUp()
        self.result = ingest.run(CSV, client="productive", lane="domains",
                                 suppress_path=SUPPRESS)

    def test_queue_has_a_record_for_every_row(self):
        self.assertEqual(len(self.lines()), 5)
        self.assertEqual(len(store.list_records(state="queued")), 2)
        self.assertEqual(len(store.list_records(state="dropped")), 3)

    def test_the_right_rows_are_queued(self):
        self.assertEqual(sorted(self.result["queued"]), ["harbourline", "meridian"])

    def test_the_right_skip_reasons(self):
        self.assertEqual(dict(self.result["dropped"]), {
            "blocked-co": "suppressed (live account)",
            "meridian-again": "duplicate domain",
            "some-company": "no domain",
        })

    def test_every_dropped_record_carries_its_reason(self):
        for r in store.list_records(state="dropped"):
            self.assertTrue(r["drop_reason"], f"{r['id']} dropped with no reason")

    def test_every_record_validates_against_the_schema(self):
        for r in store.load():
            self.assertEqual(store.validate(r), [], r["id"])

    def test_domain_is_normalised_and_feeds_the_dedupe(self):
        self.assertEqual(self.by_id()["meridian-again"]["domain"], "meridian.test")

    def test_ids_are_unique(self):
        ids = [r["id"] for r in store.load()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_rerun_adds_nothing_and_never_shrinks_the_queue(self):
        before = self.lines()
        again = ingest.run(CSV, client="productive", lane="domains",
                           suppress_path=SUPPRESS)
        self.assertEqual(again["queued"], [])
        self.assertEqual(again["dropped"], [])
        self.assertEqual(len(again["skipped"]), 5)
        self.assertEqual(self.lines(), before)


class TestNormalisation(unittest.TestCase):
    def test_norm_domain(self):
        for raw, want in [("https://www.Meridian.test/about", "meridian.test"),
                          ("WWW.Lumen.Test/", "lumen.test"),
                          ("lumen.test?utm=x", "lumen.test"),
                          ("  meridian.test  ", "meridian.test"),
                          ("", ""), (None, "")]:
            self.assertEqual(ingest.norm_domain(raw), want, raw)

    def test_slug(self):
        self.assertEqual(ingest.slug("BrightPath Leads"), "brightpath-leads")
        self.assertEqual(ingest.slug("Vantage.ai"), "vantage-ai")
        self.assertEqual(ingest.slug(""), "record")


class TestSuppress(unittest.TestCase):
    """The tracked template is read here, and the real roster is never in it.

    Who is paying us is confidential, so the roster lives in the gitignored
    `config/suppress.local.txt` and the tracked file carries only the mechanism.
    That makes "is the untracked overlay actually read" the thing worth proving:
    a roster nobody loads and a roster that matches nothing look identical from
    the outside, and the first one cold-sequences a live customer.
    """

    def test_comments_stripped_and_entries_normalised(self):
        entries = ingest.load_suppress()
        self.assertTrue(entries, "config/suppress.txt is empty")
        self.assertNotIn("", entries)
        self.assertFalse(any(e.startswith("#") for e in entries))
        self.assertTrue(all(e == ingest.norm_domain(e) for e in entries))

    def test_the_local_roster_is_merged_over_the_tracked_template(self):
        """Section 9, trap 6: this is what stops a live customer being sequenced."""
        with tempfile.TemporaryDirectory() as d:
            local = os.path.join(d, "suppress.local.txt")
            with open(local, "w", encoding="utf-8") as f:
                f.write("# the real roster\nA-Paying-Customer.TEST\n")
            original = ingest.SUPPRESS_LOCAL
            ingest.SUPPRESS_LOCAL = local
            try:
                entries = ingest.load_suppress()
                sources = ingest.suppress_sources()
            finally:
                ingest.SUPPRESS_LOCAL = original
        # The overlay is read, and normalised the same way the template is.
        self.assertIn("a-paying-customer.test", entries)
        # The template is still read, so the overlay adds rather than replaces.
        self.assertIn("example-customer.test", entries)
        self.assertIn(local, sources)

    def test_a_missing_overlay_is_visible_rather_than_silent(self):
        """An absent roster and an empty one are different states."""
        original = ingest.SUPPRESS_LOCAL
        ingest.SUPPRESS_LOCAL = os.path.join(os.sep, "no", "such", "roster.txt")
        try:
            self.assertNotIn(ingest.SUPPRESS_LOCAL, ingest.suppress_sources())
            self.assertIn(ingest.SUPPRESS, ingest.suppress_sources())
        finally:
            ingest.SUPPRESS_LOCAL = original

    def test_the_tracked_template_names_no_real_customer(self):
        """The template ships the format, never the roster."""
        with open(ingest.SUPPRESS, encoding="utf-8") as f:
            body = f.read()
        for entry in ingest.load_suppress(ingest.SUPPRESS):
            self.assertTrue(
                entry.endswith((".test", ".example")),
                f"{entry} in the tracked template is not a reserved domain")
        self.assertIn("suppress.local.txt", body,
                      "the template must say where the real roster lives")

    def test_suppress_matches_a_messy_input_domain(self):
        entries = ingest.load_suppress(SUPPRESS)
        self.assertIn(ingest.norm_domain("https://www.Blocked.test/pricing"), entries)
        self.assertIn("alsoblocked.example", entries)


class TestOtherSources(QueueTest):
    def test_id_collision_gets_a_suffix(self):
        path = self.write_csv("collide.csv",
                              ["company,domain", "Meridian,meridian.test",
                               "Meridian,meridian.example"])
        ingest.run(path, client="productive", lane="domains")
        self.assertEqual(sorted(r["id"] for r in store.load()),
                         ["meridian", "meridian-2"])

    def test_unknown_lane_is_dropped_not_crashed(self):
        path = self.write_csv("lane.csv",
                              ["company,domain,lane", "Meridian,meridian.test,newsletter"])
        result = ingest.run(path, client="productive", lane="domains")
        self.assertEqual(result["dropped"], [("meridian", "unknown lane: newsletter")])

    def test_unknown_client_refuses_the_batch(self):
        path = self.write_csv("noclient.csv", ["company,domain", "Meridian,meridian.test"])
        with self.assertRaises(SystemExit):
            ingest.run(path, client="nosuchclient", lane="domains")


if __name__ == "__main__":
    unittest.main()
