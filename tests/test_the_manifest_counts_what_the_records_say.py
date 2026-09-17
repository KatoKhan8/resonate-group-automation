"""The durable manifest is derived, so it has to be derived from the real field.

`docs/state/QUEUE-MANIFEST.json` is what a fresh session on a different
computer reads to learn how much work is in which state, and CLAUDE.md is
explicit that a ledger somebody has to remember to update is worse than none
"because it is believed".

On 2026-09-17 it was believed and it was wrong. `queue_manifest` read
`status`, then `stage`, then fell back to `"unset"`, and counted a record as
dropped when `r["dropped"]` was truthy. A queue record carries NONE of those
three names - the state field is `state` and the drop marker is
`drop_reason` - so a perfectly well-formed manifest was published saying every
one of 550 records was `unset` and that NOTHING had been dropped. 126 records
really were dropped, and the manifest it overwrote had said so.

**`dropped: 0` there did not mean "none were dropped". It meant "I read a key
that does not exist."** Those are the two answers this repository exists to
keep apart, and nothing failed, because reading a missing key never fails.

So these tests do two things. They pin the field names to BEHAVIOUR - build a
queue, assert the counts - so renaming the field breaks a test rather than
silently zeroing a report. And they assert the loud failure: when every record
falls through to `unset`, the manifest must SAY the stage counts mean UNKNOWN,
because the next version of this bug will look exactly like the last one.
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import durable_state                                          # noqa: E402


def record(rid, state, drop_reason=None, contacts=1, client="productive"):
    row = {"id": rid, "client": client, "domain": f"{rid}.example.test",
           "state": state, "drop_reason": drop_reason,
           "contacts": [{"email": f"a{i}@{rid}.example.test"}
                        for i in range(contacts)]}
    return row


class ManifestCounts(unittest.TestCase):
    def manifest_for(self, rows):
        """Run the real function against a queue we control."""
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "work")
            os.makedirs(work)
            with open(os.path.join(work, "queue.jsonl"), "w",
                      encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row) + "\n")
            original = durable_state.ROOT
            durable_state.ROOT = tmp
            try:
                return durable_state.queue_manifest()
            finally:
                durable_state.ROOT = original

    def test_stage_counts_come_from_the_state_field(self):
        man = self.manifest_for([
            record("a", "verified"), record("b", "verified"),
            record("c", "queued"), record("d", "approved"),
        ])
        self.assertEqual(man["stages"],
                         {"verified": 2, "queued": 1, "approved": 1})
        self.assertNotIn("stages_unreadable", man)

    def test_a_dropped_record_is_counted_by_its_reason(self):
        man = self.manifest_for([
            record("a", "dropped", drop_reason="rejected at ICP"),
            record("b", "dropped", drop_reason="no contact found"),
            record("c", "queued"),
        ])
        self.assertEqual(man["dropped"], 2)

    def test_a_record_with_no_reason_is_not_dropped(self):
        """`state` and `drop_reason` are two fields and only one is the marker.

        Counting `state == "dropped"` instead would be a second
        representation of the same truth, and the two would drift the first
        time a record was dropped without a reason - which the queue's own
        rule forbids, and which is exactly why the reason is the marker.
        """
        man = self.manifest_for([record("a", "queued"), record("b", "held")])
        self.assertEqual(man["dropped"], 0)

    def test_everything_unset_says_so_rather_than_reporting_zeros(self):
        """The failure mode that shipped: a confident manifest derived from a
        field nobody carries. It must not be silent."""
        rows = [{"id": "a", "client": "productive", "contacts": []},
                {"id": "b", "client": "productive", "contacts": []}]
        man = self.manifest_for(rows)
        self.assertEqual(man["stages"], {"unset": 2})
        self.assertIn("stages_unreadable", man)
        self.assertIn("UNKNOWN", man["stages_unreadable"])

    def test_a_readable_queue_with_one_unset_record_is_not_flagged(self):
        """The alarm is for a schema that MOVED, not for one odd row."""
        rows = [record("a", "queued"),
                {"id": "b", "client": "productive", "contacts": []}]
        man = self.manifest_for(rows)
        self.assertEqual(man["stages"], {"queued": 1, "unset": 1})
        self.assertNotIn("stages_unreadable", man)

    def test_the_manifest_carries_no_record_identity(self):
        """It is the PII-safe half of durable state. Counts and a fingerprint,
        never a domain."""
        man = self.manifest_for([record("acme", "queued")])
        self.assertNotIn("acme", json.dumps(man))
        self.assertEqual(man["records"], 1)
        self.assertEqual(man["contacts"], 1)


if __name__ == "__main__":
    unittest.main()
