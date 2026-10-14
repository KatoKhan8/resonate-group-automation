#!/usr/bin/env python3
"""The §6a snapshot is assembled from stored state, and a missing file FAILS.

TASK 0010. `scripts/suppression_snapshot.py` is new. It exists because §6a of
`docs/SUPPRESSION-MEASUREMENT-2026-10-14.md` said the reconciliation "is tested,
never measured, because no snapshot has been taken", and it reads six files
that an earlier provider read left on disk.

THE DEFECT THIS FILE IS AGAINST is not a wrong number, it is a SILENT SMALL
one. `store.read_jsonl` answers a missing file with an empty list. A reader
built on that would turn "the stage walk was never run here" into "nobody is
suppressed at the provider", which is invariant 0 - an unreadable authority
read as a clean one. It is not hypothetical: the first production run of this
script resolved `work/` to an empty worktree copy, because
`store.main_checkout_work()` returns `None` when `git rev-parse` fails and it
was failing on a broken `GIT_CONFIG_VALUE_0`. The refusal is what stopped a
snapshot of zero being written and believed.

So every refusal below is paired with a positive control on the same tree, and
the refusal itself is MUTATED - `required` flipped to False - to prove it is
the refusal doing the work and not the fixture.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

from src import store, suppression
from tests.base import QueueTest

import scripts.suppression_snapshot as snap


#: One lead, in one campaign, with one status - the smallest tree the
#: assembler accepts. The addresses are `.test`, which cannot receive mail.
LEAD = 204562
EMAIL = "dana@acme.test"
OBSERVED = "mo@other.test"


def a_tree(root, *, omit=()):
    """Write every declared source. `omit` leaves one out, by relative path."""
    stage = os.path.join(root, "stage")
    os.makedirs(stage, exist_ok=True)
    files = {
        "stage/pc-leads.jsonl": [
            {"lead_id": LEAD, "memberships": [
                {"campaign_id": 491, "status": "in_sequence"},
                {"campaign_id": 492, "status": "stopped"}]}],
        "stage/pc-sends.jsonl": [
            {"lead_id": LEAD, "campaign_id": 491, "status": "sent"}],
        "stage/pc-lead-sends.jsonl": [
            {"lead_id": LEAD, "campaign_id": 491, "status": "sent"}],
        "stage/reengagement-inventory.jsonl": [
            {"lead_id": str(LEAD), "campaign_id": 491, "state": "in_sequence"}],
    }
    # The one stored source that carries an ADDRESS beside a status, so it
    # needs no join. A different person, so the joined assertions stay crisp.
    files["lead-observations.jsonl"] = [
        {"provider": "emailbison", "campaign_id": "451", "email": OBSERVED,
         "raw_status": "bounced", "state": "bounced"}]
    for rel, rows in files.items():
        if rel in omit:
            continue
        with open(os.path.join(root, *rel.split("/")), "w",
                  encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
    if "queue.jsonl" not in omit:
        with open(os.path.join(root, "queue.jsonl"), "w", encoding="utf-8",
                  newline="\n") as handle:
            handle.write(json.dumps({
                "id": "acme-test", "domain": "acme.test", "state": "verified",
                "contacts": [
                    {"key": "dana", "email": EMAIL, "bison_lead_id": LEAD},
                    # No lead id. The join cannot reach them and the census
                    # must say so rather than counting them as covered.
                    {"key": "sam", "email": "sam@acme.test"}]}) + "\n")
    return root


class TheAssemblerRefusesAMissingSource(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def test_the_positive_control_a_complete_tree_assembles(self):
        """Without this, every refusal below is unattributable."""
        a_tree(self.root)
        snapshot, provenance = snap.assemble(self.root)
        self.assertEqual(sorted(snapshot), [EMAIL, OBSERVED])
        self.assertEqual(sorted(snapshot[EMAIL]),
                         ["in_sequence", "sent", "stopped"])
        # The address-keyed source needed no lead id to land.
        self.assertEqual(sorted(snapshot[OBSERVED]), ["bounced"])
        self.assertIsNone(snapshot[OBSERVED]["bounced"][0]["bison_lead_id"])
        self.assertEqual(provenance["absent"], [])
        self.assertEqual(provenance["coverage"]["emails_in_snapshot"], 2)
        # Four joined sources, one address-keyed source, and the queue.
        self.assertEqual(len(provenance["sources"]), 6)
        for entry in provenance["sources"]:
            self.assertIn("bytes", entry)
            self.assertIn("mtime", entry)
            self.assertEqual(entry["damaged_lines"], 0)

    def test_a_missing_source_refuses_and_names_the_file(self):
        """THE WHOLE POINT. An absent authority is not an empty one."""
        a_tree(self.root, omit=("stage/pc-leads.jsonl",))
        with self.assertRaises(snap.MissingSource) as caught:
            snap.assemble(self.root)
        self.assertIn("pc-leads.jsonl", str(caught.exception))

    def test_a_missing_queue_refuses_too(self):
        """The join key is a source like any other."""
        a_tree(self.root, omit=("queue.jsonl",))
        with self.assertRaises(snap.MissingSource) as caught:
            snap.assemble(self.root)
        self.assertIn("join key", str(caught.exception))

    def test_the_refusal_is_load_bearing(self):
        """THE MUTATION. Make the source optional and the silence returns.

        Not an argument that the guard matters - the guard removed, and the
        defect it exists against reproduced: a tree missing the membership
        walk assembles anyway, reports a SMALLER snapshot, and the only trace
        is a line in `absent` that no count contradicts.
        """
        a_tree(self.root, omit=("stage/pc-leads.jsonl",))
        softened = tuple(dict(source, required=False)
                         for source in snap.SOURCES)
        with mock.patch.object(snap, "SOURCES", softened):
            snapshot, provenance = snap.assemble(self.root)
        self.assertEqual(provenance["absent"], ["stage/pc-leads.jsonl"])
        # Still an entry, and nothing about it says a whole witness is gone.
        self.assertEqual(provenance["coverage"]["emails_in_snapshot"], 2)
        self.assertNotIn("stopped", snapshot[EMAIL])

    def test_a_damaged_line_is_counted_not_dropped(self):
        """A line that will not parse is reported. Silence would be the same
        defect one line smaller."""
        a_tree(self.root)
        path = os.path.join(self.root, "stage", "pc-sends.jsonl")
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write("{not json\n")
        _, provenance = snap.assemble(self.root)
        entry = [s for s in provenance["sources"]
                 if s["path"] == "stage/pc-sends.jsonl"][0]
        self.assertEqual(entry["damaged_lines"], 1)

    def test_the_join_ceiling_is_reported_not_the_covered_part_alone(self):
        """A contact with no `bison_lead_id` is UNREACHABLE, and counted."""
        a_tree(self.root)
        _, provenance = snap.assemble(self.root)
        self.assertEqual(provenance["join"]["contacts"], 2)
        self.assertEqual(provenance["join"]["with_bison_lead_id"], 1)
        self.assertEqual(provenance["join"]["with_email"], 2)


class TheMeasurementNeverTurnsAbsenceIntoAgreement(QueueTest):
    """`UNKNOWN_IS_NOT_A_PASS` through the measurement, not just `reconcile`.

    `reconcile`'s own absence test lives in
    `test_a_suppressed_address_cannot_reach_a_provider`. This one is about the
    FAN-OUT around it: `measure` asks `reconcile` once per status a person
    carries and keeps the most severe answer, and a reduction that kept the
    FIRST answer would clear somebody the second one holds.
    """

    def setUp(self):
        super().setUp()
        suppression.reset_consultations()
        self.addCleanup(suppression.reset_consultations)

    def a_record(self):
        return {"id": "acme-test", "domain": "acme.test", "state": "verified",
                "contacts": [{"key": "dana", "email": EMAIL,
                              "sendable": True, "verdict": "valid"}]}

    def test_an_address_the_snapshot_omits_is_unknown_never_agree(self):
        result = snap.measure([self.a_record()], {})
        self.assertEqual(result["findings"],
                         {suppression.UNKNOWN_THERE: 1})
        # And it was ASKED, rather than skipped for want of a status.
        self.assertEqual(result["reconcile_calls"], 1)
        self.assertEqual(len(suppression.consultations()), 1)

    def test_the_fan_out_keeps_the_most_severe_not_the_first(self):
        """`in_sequence` alone would AGREE; `stopped` beside it must not."""
        alone = snap.measure([self.a_record()], {EMAIL: {"in_sequence": []}})
        self.assertEqual(alone["findings"], {suppression.AGREE: 1})

        both = snap.measure([self.a_record()],
                            {EMAIL: {"in_sequence": [], "stopped": []}})
        self.assertEqual(both["findings"], {suppression.UNKNOWN_THERE: 1})
        self.assertEqual(both["reconcile_calls"], 2)

    def test_reconcile_all_is_handed_the_same_status_and_agrees(self):
        """The control §6a's estate entry point gets. Not independent, and
        named that way: it checks `reconcile_all`'s key normalisation, which
        is the one thing it does that `reconcile` does not."""
        records = [self.a_record()]
        result = snap.measure(records, {EMAIL: {"bounced": []}})
        self.assertEqual(result["findings"],
                         {suppression.BLOCKED_THERE_ONLY: 1})
        counts = snap.control(records, result["worst_status_by_email"])
        self.assertEqual(counts[suppression.BLOCKED_THERE_ONLY], 1)
        self.assertEqual(counts[suppression.AGREE], 0)

    def test_an_uppercased_address_still_reconciles(self):
        """`reconcile_all` normalises its key; the snapshot must too, or a
        capitalised address would silently land in UNKNOWN."""
        records = [self.a_record()]
        result = snap.measure(records, {EMAIL: {"bounced": []}})
        counts = snap.control(records, {"DANA@Acme.Test ": "bounced"})
        self.assertEqual(counts[suppression.BLOCKED_THERE_ONLY], 1)
        self.assertEqual(result["findings"],
                         {suppression.BLOCKED_THERE_ONLY: 1})


class TheCommittedArtifactCarriesNoAddress(unittest.TestCase):
    """`work/` is gitignored because it is real people. The sanitised artifact
    is committed, so it may hold digests and counts and nothing else."""

    def test_no_plaintext_address_survives_sanitisation(self):
        record = {"id": "acme-test", "domain": "acme.test",
                  "state": "verified",
                  "contacts": [{"key": "dana", "email": EMAIL}]}
        result = snap.measure([record], {EMAIL: {"bounced": []}})
        report = snap.sanitise({EMAIL: {"bounced": []}},
                               {"sources": [], "absent": []},
                               result,
                               snap.control([record],
                                            result["worst_status_by_email"]))
        text = json.dumps(report)
        self.assertNotIn(EMAIL, text)
        self.assertNotIn("@", text)
        self.assertEqual(report["snapshot"]["entries"], 1)
        self.assertFalse(report["provider_call_made"])
        self.assertTrue(report["unknown_is_not_a_pass"])
        self.assertTrue(report["measurement"]["control_agrees"])

    def test_the_fingerprint_is_the_one_the_dnc_ledger_already_uses(self):
        """A second digest scheme for one identifier is how two lists stop
        being joinable. `agencydnc.fingerprint` is the existing one."""
        from src import agencydnc
        report = snap.sanitise(
            {EMAIL: {"bounced": []}}, {"sources": [], "absent": []},
            {"reconcile_calls": 0, "findings": {}, "people": [],
             "worst_status_by_email": {}}, {})
        self.assertIn(agencydnc.fingerprint("email", EMAIL),
                      report["snapshot"]["by_email_fingerprint"])


if __name__ == "__main__":
    unittest.main()
