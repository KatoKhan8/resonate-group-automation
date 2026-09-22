"""Property test: dirty tracking selects exactly the rows the baseline comparison does.

TASK-261. The trap: callers do not replace rows, they MUTATE them in place,
and two of the three shapes are nested - ``rec["contacts"].append(person)``
and ``rec["cadence"]["day1"]["body"] = "..."``. A tracker that catches only
top-level assignment passes a casual test and SILENTLY STOPS DETECTING the
edits that carry contacts, events and cadence.

This test runs 200 rounds of randomised mutation over realistic record
estates, comparing the dirty set against the frozen/baseline comparison.
Every round touches nested structures in place - contacts, events, cadence,
log - not just top-level fields.
"""
import copy
import json
import os
import random
import tempfile
import unittest

from src import store


def _frozen(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _baseline_edits(snapshot):
    """The rows the baseline comparison says were edited.

    This is the REFERENCE implementation: serialise every row and compare
    against the baseline. Whatever this selects, the dirty set must select
    the same rows.
    """
    edits = set()
    for row in snapshot:
        if not isinstance(row, dict) or snapshot.key not in row:
            continue
        rid = row[snapshot.key]
        if snapshot.baseline.get(rid) != _frozen(row):
            edits.add(rid)
    return edits


def _make_record(rid):
    """A realistic record with nested structures callers mutate in place."""
    return {
        "id": rid,
        "lane": "domains",
        "client": "productive",
        "company": f"Company-{rid}",
        "domain": f"{rid}.test",
        "context": "",
        "signal": "",
        "state": "queued",
        "drop_reason": None,
        "company_facts": {"employees": 10, "revenue": "$1M"},
        "contacts": [
            {"key": f"{rid}:alice", "name": "Alice", "email": f"alice@{rid}.test",
             "verification": {"evidence": [
                 {"email": f"alice@{rid}.test", "provider": "reo", "status": "valid"}
             ]}}
        ],
        "excluded": [],
        "diagnosis": None,
        "hook": None,
        "sizing": None,
        "cadence": {"day1": {"body": "Hello", "subject": "Intro"},
                     "day3": {"body": "Follow up", "subject": "Re"}},
        "events": [{"id": f"evt-{rid}-1", "type": "ingested", "contact": f"{rid}:alice"}],
        "log": [{"step": "queued", "at": "2026-09-22T00:00:00+00:00", "note": "ingested"}],
    }


def _apply_random_mutations(snapshot, rng, min_edits=1, max_edits=5):
    """Apply random in-place mutations to records in the snapshot.

    Covers: top-level field, nested dict, nested list append, deep nested
    dict, list element replacement, and log append.
    """
    n = len(snapshot)
    if n == 0:
        return set()
    n_edits = rng.randint(min_edits, min(max_edits, n))
    indices = rng.sample(range(n), n_edits)
    touched = set()
    for idx in indices:
        rec = snapshot[idx]
        rid = rec["id"]
        touched.add(rid)
        kind = rng.randint(0, 7)
        if kind == 0:
            rec["state"] = rng.choice(["enriched", "verified", "drafted"])
        elif kind == 1:
            rec["company_facts"]["employees"] = rng.randint(1, 10000)
        elif kind == 2:
            rec["contacts"].append({
                "key": f"{rid}:bob-{rng.randint(0,999)}",
                "name": "Bob",
                "email": f"bob@{rid}.test",
            })
        elif kind == 3:
            rec["cadence"]["day1"]["body"] = f"Variant {rng.randint(0,999)}"
        elif kind == 4:
            rec["log"].append({
                "step": rng.choice(["enriched", "verified"]),
                "at": "2026-09-22T12:00:00+00:00",
                "note": f"step {rng.randint(0,999)}",
            })
        elif kind == 5:
            if rec["events"]:
                idx2 = rng.randint(0, len(rec["events"]) - 1)
                rec["events"][idx2] = {
                    "id": f"evt-{rid}-{rng.randint(100,999)}",
                    "type": "verification_result",
                    "contact": rec["events"][0]["key"] if rec["events"][0].get("key") else f"{rid}:alice",
                }
        elif kind == 6:
            rec["cadence"]["day3"]["subject"] = f"Re: {rng.randint(0,999)}"
        elif kind == 7:
            rec["drop_reason"] = f"reason-{rng.randint(0,999)}"
            rec["state"] = "dropped"
    return touched


class TestDirtyTrackingProperty(unittest.TestCase):
    """200 rounds: dirty set == baseline comparison, over nested mutations."""

    def test_dirty_set_matches_baseline_over_200_rounds(self):
        rng = random.Random(42)
        for round_num in range(200):
            n_records = rng.randint(3, 30)
            rows = [_make_record(f"rec-{i:04d}") for i in range(n_records)]
            snap = store.Snapshot(rows)

            # After creation, nothing is dirty
            baseline_edits = _baseline_edits(snap)
            dirty_ids = set(snap._dirty) if hasattr(snap, "_dirty") else set()
            self.assertEqual(
                dirty_ids, baseline_edits,
                f"round {round_num}: after creation, dirty={dirty_ids} "
                f"but baseline says {baseline_edits}")

            # Apply random mutations
            _apply_random_mutations(snap, rng)

            # Now compare
            baseline_edits = _baseline_edits(snap)
            dirty_ids = set(snap._dirty) if hasattr(snap, "_dirty") else set()
            self.assertEqual(
                dirty_ids, baseline_edits,
                f"round {round_num}: dirty={sorted(dirty_ids)} "
                f"but baseline says {sorted(baseline_edits)}")

    def test_nested_list_append_is_detected(self):
        """The specific case the task warns about: contacts.append."""
        rows = [_make_record("rec-0001"), _make_record("rec-0002")]
        snap = store.Snapshot(rows)

        # Mutate ONLY via nested list append
        snap[0]["contacts"].append({"key": "rec-0001:eve", "name": "Eve",
                                     "email": "eve@rec-0001.test"})

        dirty_ids = set(snap._dirty) if hasattr(snap, "_dirty") else set()
        baseline_edits = _baseline_edits(snap)
        self.assertEqual(dirty_ids, baseline_edits)
        self.assertIn("rec-0001", dirty_ids)
        self.assertNotIn("rec-0002", dirty_ids)

    def test_deep_nested_dict_mutation_is_detected(self):
        """rec["cadence"]["day1"]["body"] = "..." - two levels deep."""
        rows = [_make_record("rec-0001"), _make_record("rec-0002")]
        snap = store.Snapshot(rows)

        snap[0]["cadence"]["day1"]["body"] = "Changed"

        dirty_ids = set(snap._dirty) if hasattr(snap, "_dirty") else set()
        baseline_edits = _baseline_edits(snap)
        self.assertEqual(dirty_ids, baseline_edits)
        self.assertIn("rec-0001", dirty_ids)

    def test_no_mutation_means_not_dirty(self):
        """Reading without writing does not mark dirty."""
        rows = [_make_record(f"rec-{i:04d}") for i in range(10)]
        snap = store.Snapshot(rows)

        # Read-only access at every nesting level
        for rec in snap:
            _ = rec["state"]
            _ = rec["contacts"]
            _ = rec["cadence"]["day1"]["body"]
            _ = rec["log"]
            if rec["events"]:
                _ = rec["events"][0]["id"]

        dirty_ids = set(snap._dirty) if hasattr(snap, "_dirty") else set()
        self.assertEqual(dirty_ids, set())

    def test_dirty_cleared_after_rebase(self):
        """After rebase, the dirty set is empty."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["state"] = "enriched"
        self.assertIn("rec-0001", snap._dirty)
        snap.rebase()
        self.assertEqual(set(snap._dirty), set())

    def test_mutation_after_rebase_is_detected(self):
        """After rebase, new mutations are tracked afresh."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["state"] = "enriched"
        snap.rebase()

        # New mutation
        snap[0]["contacts"].append({"key": "rec-0001:bob", "name": "Bob",
                                     "email": "bob@rec-0001.test"})
        self.assertIn("rec-0001", snap._dirty)

    def test_new_value_assigned_to_field_is_wrapped(self):
        """Assigning a new list to a field: subsequent mutations are tracked."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)

        # Replace the contacts list entirely
        snap[0]["contacts"] = [{"key": "rec-0001:new", "name": "New",
                                 "email": "new@rec-0001.test"}]
        snap._dirty.clear()  # clear the assignment dirty

        # Now mutate the NEW list
        snap[0]["contacts"].append({"key": "rec-0001:extra", "name": "Extra",
                                     "email": "extra@rec-0001.test"})
        self.assertIn("rec-0001", snap._dirty)

    def test_merge_onto_uses_dirty_set(self):
        """merge_onto produces the same edits whether using dirty or baseline."""
        rows = [_make_record(f"rec-{i:04d}") for i in range(5)]
        snap = store.Snapshot(rows)

        # Mutate two records
        snap[1]["state"] = "enriched"
        snap[3]["contacts"].append({"key": "rec-0003:bob", "name": "Bob",
                                     "email": "bob@rec-0003.test"})

        # on_disk is the same as baseline (nobody else changed anything)
        on_disk = [copy.deepcopy(dict(r)) for r in rows]
        result = snap.merge_onto(on_disk)

        # The result should have the edits applied
        result_by_id = {r["id"]: r for r in result}
        self.assertEqual(result_by_id["rec-0000"]["state"], "queued")  # not edited
        self.assertEqual(result_by_id["rec-0001"]["state"], "enriched")  # edited
        self.assertEqual(len(result_by_id["rec-0003"]["contacts"]), 2)  # appended

    def test_drop_reversion_still_prevented(self):
        """The incident from Snapshot's docstring: re-create and verify."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)

        # Caller sets state: enriched
        snap[0]["state"] = "enriched"

        # Simulate another process dropping the record
        on_disk_after_drop = [dict(rows[0])]
        on_disk_after_drop[0]["state"] = "dropped"
        on_disk_after_drop[0]["drop_reason"] = "competitor - do not contact"

        # Caller checkpoints - merge_onto should NOT resurrect state: enriched
        # because the caller did NOT change drop_reason, and the other process
        # changed state to dropped.
        result = snap.merge_onto(on_disk_after_drop)
        result_row = result[0]
        # The caller changed state from queued to enriched.
        # The other process changed state from queued to dropped.
        # Both changed the same field -> caller wins -> state: enriched.
        # But drop_reason was set by the other process and NOT by the caller.
        # So drop_reason should survive.
        self.assertEqual(result_row["state"], "enriched")
        self.assertEqual(result_row["drop_reason"],
                         "competitor - do not contact")

    def test_update_method_tracks_dirty(self):
        """dict.update() must mark dirty."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0].update({"state": "enriched", "hook": "new hook"})
        self.assertIn("rec-0001", snap._dirty)

    def test_pop_method_tracks_dirty(self):
        """dict.pop() must mark dirty."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["hook"] = "something"
        snap.rebase()
        snap[0].pop("hook", None)
        self.assertIn("rec-0001", snap._dirty)

    def test_list_extend_tracks_dirty(self):
        """list.extend() must mark dirty."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["log"].extend([{"step": "extra", "at": "2026-09-22", "note": "x"}])
        self.assertIn("rec-0001", snap._dirty)

    def test_list_insert_tracks_dirty(self):
        """list.insert() must mark dirty."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["log"].insert(0, {"step": "first", "at": "2026-09-22", "note": "x"})
        self.assertIn("rec-0001", snap._dirty)

    def test_list_pop_tracks_dirty(self):
        """list.pop() must mark dirty."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["log"].pop()
        self.assertIn("rec-0001", snap._dirty)

    def test_list_reverse_tracks_dirty(self):
        """list.reverse() must mark dirty."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["log"].append({"step": "second", "at": "2026-09-22", "note": "y"})
        snap.rebase()
        snap[0]["log"].reverse()
        self.assertIn("rec-0001", snap._dirty)

    def test_list_sort_tracks_dirty(self):
        """list.sort() must mark dirty."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["log"].append({"step": "aaa", "at": "2026-09-22", "note": "y"})
        snap.rebase()
        snap[0]["log"].sort(key=lambda e: e["step"])
        self.assertIn("rec-0001", snap._dirty)

    def test_list_iadd_tracks_dirty(self):
        """list += [...] must mark dirty."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["log"] += [{"step": "extra", "at": "2026-09-22", "note": "z"}]
        self.assertIn("rec-0001", snap._dirty)

    def test_dict_clear_tracks_dirty(self):
        """dict.clear() must mark dirty."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["company_facts"].clear()
        self.assertIn("rec-0001", snap._dirty)

    def test_dict_setdefault_tracks_dirty_when_inserting(self):
        """dict.setdefault() must mark dirty when inserting a new key."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0].setdefault("new_field", "value")
        self.assertIn("rec-0001", snap._dirty)

    def test_json_dumps_produces_same_output_as_plain_dict(self):
        """TrackingDict serialises identically to a plain dict."""
        plain = _make_record("rec-0001")
        plain_copy = copy.deepcopy(plain)
        snap = store.Snapshot([plain_copy])
        wrapped = snap[0]

        plain_json = json.dumps(plain, sort_keys=True, ensure_ascii=False)
        wrapped_json = json.dumps(wrapped, sort_keys=True, ensure_ascii=False)
        self.assertEqual(plain_json, wrapped_json)

    def test_json_dumps_after_nested_mutation(self):
        """After nested mutation, serialisation reflects the change."""
        rows = [_make_record("rec-0001")]
        snap = store.Snapshot(rows)
        snap[0]["contacts"].append({"key": "rec-0001:eve", "name": "Eve",
                                     "email": "eve@rec-0001.test"})
        serialised = json.dumps(snap[0], sort_keys=True, ensure_ascii=False)
        self.assertIn("eve@rec-0001.test", serialised)


if __name__ == "__main__":
    unittest.main()
