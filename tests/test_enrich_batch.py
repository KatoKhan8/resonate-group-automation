"""One bad record used to cost the whole batch, credits included.

`enrich.run` calls `enrich_record` for every target and saves once, after
the loop. Every provider call is wrapped in `except ProviderError`, which is
the right handler for a provider that fails - and the wrong one for a
provider that succeeds and returns a shape nobody expected. A JSON array
where an object belonged raised `AttributeError`, which is not a
`ProviderError`, so it left the loop, skipped `store.save`, and threw away
the enrichment of every record already processed. The credits were spent;
the results were not written; running it again spends them again.

Two changes, and both are asserted here because either alone leaves the
hole open. The provider modules now read a body through `mapping` and raise
`ProviderError` for a non-object, so the known case is classified. And the
loop contains anything else, so the *next* unexpected shape costs one
record rather than the batch.

Containment is not silence. The record is marked, the reason is on the
record and in `notes`, and the report row says `failed` - because a batch
that reports nothing about a record it could not enrich is how a run that
half-worked looks identical to one that worked.
"""
import unittest

from src import enrich, events, store
from src import providers

# Through the module at call time. A reload in `tests/test_audit.py`
# replaces this class, and a bound name stops matching what is raised.
# This file happened to survive because `src.enrich` is reloaded before
# `src.providers` and so holds the old class too - luck, not design,
# and `tests/test_invariants.py` now refuses it.
from tests.base import QueueTest


class Batch(QueueTest):

    def seeded(self, n=3):
        recs = []
        for i in range(n):
            rec = store.new_record(f"co{i}", "domains", "demo", f"Co {i}",
                                   f"co{i}.test")
            rec["state"] = "queued"
            recs.append(rec)
        store.save(recs)
        return recs

    def breaking_on(self, bad_id, error):
        """Replace `enrich_record` with one that fails for a single record."""
        real = enrich.enrich_record

        # `**kw` so this stands in for the real signature rather than a
        # snapshot of it: `enrich_record` gained `scrape_budget`, and a stub
        # that names every argument turns any future parameter into a fake
        # TypeError attributed to the record under test.
        def fake(rec, budget, live=False, log=None, config=None, **kw):
            if rec["id"] == bad_id:
                raise error
            rec["company_facts"] = {"name": rec["company"]}
            return [{"call": "people-count", "why": "test", "cost": 0,
                     "provider": "contactout"}]

        self.addCleanup(setattr, enrich, "enrich_record", real)
        enrich.enrich_record = fake

    def enriched(self):
        return {r["id"]: r for r in store.load()}


class OneRecordDoesNotCostTheBatch(Batch):

    def test_the_records_before_the_failure_are_saved(self):
        """The defect. `co0` was enriched, paid for, and discarded."""
        self.seeded()
        self.breaking_on("co1", AttributeError(
            "'list' object has no attribute 'get'"))
        enrich.run(live=True)
        self.assertEqual(self.enriched()["co0"].get("company_facts"),
                         {"name": "Co 0"})

    def test_and_so_are_the_records_after_it(self):
        """It continues rather than stopping at the first bad one."""
        self.seeded()
        self.breaking_on("co1", AttributeError("boom"))
        enrich.run(live=True)
        self.assertEqual(self.enriched()["co2"].get("company_facts"),
                         {"name": "Co 2"})

    def test_the_failed_record_is_not_left_looking_enriched(self):
        self.seeded()
        self.breaking_on("co1", AttributeError("boom"))
        enrich.run(live=True)
        # `new_record` starts this as `{}`, so "empty" is the assertion
        # and "absent" would pass for the wrong reason.
        self.assertEqual(self.enriched()["co1"].get("company_facts"), {})

    def test_a_provider_error_is_contained_the_same_way(self):
        """Not only the unexpected ones. `enrich_record` catches
        `ProviderError` per call; one raised outside a call site would
        otherwise still take the batch."""
        self.seeded()
        self.breaking_on("co1", providers.ProviderError("contactout: 500"))
        enrich.run(live=True)
        self.assertEqual(self.enriched()["co2"].get("company_facts"),
                         {"name": "Co 2"})


class ItIsContainedNotSwallowed(Batch):

    def result(self, error=None):
        self.seeded()
        self.breaking_on("co1", error or AttributeError("boom"))
        return enrich.run(live=True)

    def test_the_report_names_the_record_that_failed(self):
        rows = {r["id"]: r for r in self.result()["records"]}
        self.assertIn("failed", rows["co1"])
        self.assertNotIn("failed", rows["co0"])

    def test_the_report_says_what_went_wrong(self):
        rows = {r["id"]: r for r in self.result()["records"]}
        self.assertIn("AttributeError", rows["co1"]["failed"])

    def test_it_is_in_the_notes_the_operator_reads(self):
        out = self.result()
        self.assertTrue(any("co1" in n and "failed" in n
                            for n in out["notes"]), out["notes"])

    def test_it_is_on_the_record_as_an_event(self):
        """The durable half. `notes` are for this run; the record is what a
        person looks at tomorrow."""
        self.result()
        rec = self.enriched()["co1"]
        failures = [e for e in rec.get("events") or []
                    if e.get("type") == events.PROVIDER_CALL_FAILED]
        self.assertEqual(len(failures), 1)
        self.assertIn("AttributeError", failures[0]["reason"])

    def test_a_clean_batch_marks_nothing_as_failed(self):
        """So the assertions above are about failure, not about the field
        always being there."""
        self.seeded()
        self.breaking_on("nobody", AttributeError("boom"))
        out = enrich.run(live=True)
        self.assertEqual([r for r in out["records"] if "failed" in r], [])
        for rec in store.load():
            self.assertEqual(
                [e for e in rec.get("events") or []
                 if e.get("type") == events.PROVIDER_CALL_FAILED], [])


if __name__ == "__main__":
    unittest.main()
