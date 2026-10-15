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


class TheThreeBucketsArePartitionAndAbsenceIsNotADecision(QueueTest):
    """TASK 0060. The four `reconcile` findings do not say whether the
    SNAPSHOT had an answer - `UNKNOWN_THERE` covers both "we never heard of
    them" and "we heard a word that decides nothing", and those have
    different fixes and different prices.

    THE DEFECT THIS IS AGAINST is a decidability bucket that lets absence
    count as a decision. If `decidability` returned `DECIDED` for an address
    the snapshot does not hold, `cannot_decide_total` would shrink and the
    gap would be reported as smaller than it is - the same shape as an
    unreadable authority read as a clean one, moved up a layer.
    """

    def a_record(self, email=EMAIL, key="dana"):
        contact = {"key": key, "sendable": True, "verdict": "valid"}
        if email:
            contact["email"] = email
        return {"id": "acme-test", "domain": "acme.test", "state": "verified",
                "contacts": [contact]}

    def test_a_word_in_neither_vocabulary_is_undecidable_not_decided(self):
        """`stopped`, `sent`, `replied` and `sequence_finished` are the words
        the production snapshot actually carries most, and NONE of them is in
        `PROVIDER_STOPPED` or `PROVIDER_ACTIVE`."""
        for word in ("stopped", "sent", "replied", "sequence_finished",
                     "sending_paused"):
            self.assertNotIn(word, suppression.PROVIDER_STOPPED, word)
            self.assertNotIn(word, suppression.PROVIDER_ACTIVE, word)
            self.assertEqual(snap.decidability(EMAIL, [word]),
                             snap.UNDECIDABLE, word)

    def test_one_recognised_word_among_several_decides(self):
        """A person carrying `bounced` beside three unknown words IS decided -
        otherwise the recognised half of the vocabulary would be wasted."""
        self.assertEqual(
            snap.decidability(EMAIL, ["sent", "stopped", "bounced"]),
            snap.DECIDED)
        self.assertEqual(snap.decidability(EMAIL, ["in_sequence"]),
                         snap.DECIDED)

    def test_absence_and_a_missing_address_are_never_decided(self):
        self.assertEqual(snap.decidability(EMAIL, []), snap.NOT_IN_SNAPSHOT)
        self.assertEqual(snap.decidability(None, []), snap.NO_EMAIL)
        # The order matters: no address loses to nothing, because there is no
        # key to have looked them up with in the first place.
        self.assertEqual(snap.decidability(None, ["bounced"]), snap.NO_EMAIL)

    def test_the_buckets_partition_the_estate(self):
        """Every contact lands in exactly one, and the four sum to the whole.
        A bucket that silently dropped somebody would make the gap look
        smaller without any number looking wrong."""
        records = [self.a_record(email="a@acme.test", key="a"),
                   self.a_record(email="b@acme.test", key="b"),
                   self.a_record(email="c@acme.test", key="c"),
                   self.a_record(email=None, key="d")]
        result = snap.measure(records, {"a@acme.test": {"bounced": []},
                                        "b@acme.test": {"stopped": []}})
        self.assertEqual(result["decidability"],
                         {snap.DECIDED: 1, snap.UNDECIDABLE: 1,
                          snap.NOT_IN_SNAPSHOT: 1, snap.NO_EMAIL: 1})
        self.assertEqual(sum(result["decidability"].values()), len(records))
        self.assertEqual(
            sorted(p["decidability"] for p in result["people"]),
            sorted(snap.DECIDABILITY))

    def test_the_cost_of_the_gap_counts_the_allows_we_cannot_decide(self):
        """`cannot_decide_and_allow_here` is the number the report exists to
        produce: people our own gate passes and the snapshot cannot speak
        for. It must count the undecidable ones too, not only the absent."""
        records = [self.a_record(email="a@acme.test", key="a"),
                   self.a_record(email="b@acme.test", key="b"),
                   self.a_record(email="c@acme.test", key="c")]
        result = snap.measure(records, {"a@acme.test": {"bounced": []},
                                        "b@acme.test": {"stopped": []}})
        buckets = snap._by_name(result["people"])
        self.assertEqual(buckets["cannot_decide_total"], 2)
        self.assertEqual(buckets["cannot_decide_and_allow_here"], 2)
        self.assertEqual(buckets[snap.DECIDED]["people"], 1)
        # And the words are carried, because this bucket is a VOCABULARY gap
        # and naming the words is the only actionable part of it.
        self.assertEqual(buckets[snap.UNDECIDABLE]["undecided_words"],
                         {"stopped": 1})

    def test_every_person_in_a_bucket_is_named(self):
        """A count without names cannot be checked later and cannot be
        applied. Each bucket carries one identifier per person."""
        records = [self.a_record(email="a@acme.test", key="a"),
                   self.a_record(email=None, key="d")]
        buckets = snap._by_name(snap.measure(records, {})["people"])
        for bucket in snap.DECIDABILITY:
            named = (len(buckets[bucket]["by_email_fingerprint"])
                     + len(buckets[bucket]["no_email_fingerprint"]))
            self.assertEqual(named, buckets[bucket]["people"], bucket)


class TheBucketsPublishNoNameEither(unittest.TestCase):
    """The sanitised artifact is committed. `test_fixture_hygiene` polices
    ADDRESSES, so a contact key - which is a real person name slug - would
    have gone into git unnoticed. It did, in the first cut of this change.
    """

    def test_a_contact_with_no_address_is_published_as_a_digest(self):
        from src import agencydnc
        record = {"id": "acme-test", "domain": "acme.test", "state": "verified",
                  "contacts": [{"key": "dana-prentice", "sendable": True}]}
        result = snap.measure([record], {})
        report = snap.sanitise({}, {"sources": [], "absent": []}, result,
                               snap.control([record], {}))
        text = json.dumps(report)
        self.assertNotIn("dana-prentice", text)
        self.assertNotIn("@", text)
        bucket = report["measurement"]["decidability"][snap.NO_EMAIL]
        # The committed artifact gets a digest OF the list, not the list.
        self.assertEqual(bucket["no_email_fingerprint"]["people"], 1)
        self.assertEqual(
            bucket["no_email_fingerprint"]["sha256_of_the_sorted_list"],
            agencydnc.fingerprint(
                "bucket",
                agencydnc.fingerprint("contact_key",
                                      "acme-test/dana-prentice")))
        # ...and the full artifact, which is gitignored, gets the list.
        full = snap._by_name(result["people"])
        self.assertEqual(
            full[snap.NO_EMAIL]["no_email_fingerprint"],
            [agencydnc.fingerprint("contact_key", "acme-test/dana-prentice")])

    def test_the_committed_artifact_holds_no_roster_of_the_estate(self):
        """THE REASON THIS SPLIT EXISTS, stated as a test.

        A bucketed list of every production contact is close enough to the
        prospect list that `work/` is gitignored for it - and separately,
        `test_fixture_hygiene` greps the tracked corpus for forbidden
        figures as SUBSTRINGS, so a long enough list of sha256 digests will
        eventually contain one by chance. It did, at 2,130 digests. The fix
        is fewer digests in git, not a looser hygiene rule - and the figure
        is not quoted here, because quoting it failed the same test again.
        """
        records = [{"id": "acme-test", "domain": "acme.test",
                    "state": "verified",
                    "contacts": [{"key": "dana", "email": EMAIL}]}]
        result = snap.measure(records, {EMAIL: {"bounced": []}})
        report = snap.sanitise({EMAIL: {"bounced": []}},
                               {"sources": [], "absent": []}, result,
                               snap.control(records,
                                            result["worst_status_by_email"]))
        for bucket in snap.DECIDABILITY:
            for key in ("by_email_fingerprint", "no_email_fingerprint"):
                published = report["measurement"]["decidability"][bucket][key]
                self.assertIsInstance(published, dict, (bucket, key))
                self.assertEqual(sorted(published),
                                 ["people", "sha256_of_the_sorted_list"])


class TheTimeRangeIsTakenFromTheRowsNotTheMtime(unittest.TestCase):
    """An mtime says when a reader last wrote the file. It says nothing about
    how old the facts inside are, and a file written yesterday out of a
    three-week-old read is three weeks stale with a fresh mtime. The drift
    question needs the second number, so the provenance records it."""

    def test_the_range_comes_from_the_declared_fields(self):
        covers = snap._covers(
            [{"sent_at": "2026-04-04T22:22:08Z"},
             {"sent_at": "2026-09-30T14:04:00Z"},
             {"sent_at": "2026-07-01T00:00:00Z"}],
            ("sent_at", "scheduled_date"))
        self.assertEqual(covers["earliest"], "2026-04-04T22:22:08Z")
        self.assertEqual(covers["latest"], "2026-09-30T14:04:00Z")
        self.assertEqual(covers["rows_with_a_timestamp"], 3)
        self.assertEqual(covers["rows_without_one"], 0)

    def test_the_first_field_present_wins_and_the_fallback_is_used(self):
        covers = snap._covers(
            [{"scheduled_date": "2026-05-05T00:00:00Z"},
             {"sent_at": "2026-06-06T00:00:00Z",
              "scheduled_date": "2026-01-01T00:00:00Z"}],
            ("sent_at", "scheduled_date"))
        # The second row has both; `sent_at` is what happened and wins, so
        # the January scheduling never reaches the range.
        self.assertEqual(covers["earliest"], "2026-05-05T00:00:00Z")
        self.assertEqual(covers["latest"], "2026-06-06T00:00:00Z")

    def test_rows_with_no_timestamp_are_counted_not_dropped(self):
        """A range computed from four rows out of twenty thousand is not a
        range, and only the denominator shows it."""
        covers = snap._covers(
            [{"sent_at": "2026-06-06T00:00:00Z"}, {}, {"sent_at": None}],
            ("sent_at",))
        self.assertEqual(covers["rows_with_a_timestamp"], 1)
        self.assertEqual(covers["rows_without_one"], 2)

    def test_no_timestamps_at_all_is_none_rather_than_a_guess(self):
        covers = snap._covers([{}, {}], ("sent_at",))
        self.assertIsNone(covers["earliest"])
        self.assertIsNone(covers["latest"])
        self.assertEqual(covers["rows_without_one"], 2)

    def test_the_assembler_records_a_range_for_every_source(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        a_tree(tmp.name)
        _, provenance = snap.assemble(tmp.name)
        self.assertTrue(provenance["sources"])
        for entry in provenance["sources"]:
            self.assertIn("covers", entry, entry["path"])
            self.assertIn("time_fields", entry["covers"], entry["path"])


if __name__ == "__main__":
    unittest.main()
