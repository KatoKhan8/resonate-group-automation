"""store.py: the queue invariants."""
import json
import os
import unittest

from src import store
from tests.base import QueueTest


def rec(rid="meridian", **kw):
    r = store.new_record(rid, "domains", "productive", "Meridian", "meridian.test")
    r.update(kw)
    return r


class TestRecordShape(QueueTest):
    def test_new_record_has_every_schema_field(self):
        r = rec()
        for field in ("id", "lane", "client", "company", "domain", "context", "signal",
                      "state", "drop_reason", "company_facts", "contacts", "excluded",
                      "diagnosis", "hook", "sizing", "cadence", "log"):
            self.assertIn(field, r)
        self.assertEqual(r["state"], "queued")
        self.assertIsNone(r["drop_reason"])

    def test_unknown_lane_rejected(self):
        with self.assertRaises(ValueError):
            store.new_record("x", "newsletter", "productive", "X", "x.com")

    def test_validate_catches_bad_state_and_reasonless_drop(self):
        self.assertEqual(store.validate(rec()), [])
        self.assertIn("unknown state: sent", store.validate(rec(state="sent")))
        self.assertIn("dropped record with no drop_reason",
                      store.validate(rec(state="dropped")))


class TestWrites(QueueTest):
    def test_append_writes_and_logs(self):
        store.append([rec()])
        r = store.get("meridian")
        self.assertEqual(r["state"], "queued")
        self.assertEqual(len(r["log"]), 1)
        self.assertEqual(r["log"][0]["step"], "queued")

    def test_append_refuses_duplicate_id(self):
        store.append([rec()])
        with self.assertRaises(ValueError):
            store.append([rec()])
        self.assertEqual(len(self.lines()), 1)

    def test_patch_deep_merges_without_clobbering_siblings(self):
        store.append([rec(company_facts={"employees": 26, "revenue": "$3.6M"})])
        store.patch("meridian", {"company_facts": {"employees": 30}, "state": "enriched"})
        r = store.get("meridian")
        self.assertEqual(r["company_facts"], {"employees": 30, "revenue": "$3.6M"})
        self.assertEqual(r["state"], "enriched")
        self.assertEqual(len(r["log"]), 2)

    def test_patch_to_unknown_state_rejected_and_queue_untouched(self):
        store.append([rec()])
        with self.assertRaises(ValueError):
            store.patch("meridian", {"state": "sent"})
        self.assertEqual(store.get("meridian")["state"], "queued")

    def test_drop_keeps_the_line(self):
        store.append([rec(), rec("lumen", company="Lumen", domain="lumen.test")])
        before = len(self.lines())
        store.drop("meridian", "suppressed (live account)")
        self.assertEqual(len(self.lines()), before)
        r = store.get("meridian")
        self.assertEqual(r["state"], "dropped")
        self.assertEqual(r["drop_reason"], "suppressed (live account)")

    def test_drop_needs_a_reason(self):
        store.append([rec()])
        with self.assertRaises(ValueError):
            store.drop("meridian", "")

    def test_write_is_atomic_and_leaves_no_temp_file(self):
        store.append([rec()])
        self.assertFalse(os.path.exists(self.queue + ".tmp"))

    def test_unicode_round_trips_as_utf8(self):
        store.append([rec(company="Šarić d.o.o.")])
        with open(self.queue, "rb") as f:
            raw = f.read()
        self.assertIn("Šarić".encode("utf-8"), raw)
        self.assertEqual(store.get("meridian")["company"], "Šarić d.o.o.")


class TestReads(QueueTest):
    def test_list_and_stats_filter(self):
        store.append([rec(), rec("lumen", company="Lumen", domain="lumen.test"),
                      rec("five", company="Five", domain="fivepoint.test", lane="cold")])
        store.drop("five", "no signal")
        # `client` is now REQUIRED - TASK-032 made the tenant a boundary
        # rather than an optional filter, so an unscoped read has to say so.
        # `store.ALL` is that saying-so, and this test genuinely wants every
        # tenant: it is asserting the state and lane filters, not tenancy.
        self.assertEqual(
            len(store.list_records(client=store.ALL, state="queued")), 2)
        self.assertEqual(
            len(store.list_records(client=store.ALL, lane="cold")), 1)
        s = store.stats()
        self.assertEqual(s["records"], 3)
        self.assertEqual(s["states"], {"queued": 2, "dropped": 1})


if __name__ == "__main__":
    unittest.main()
