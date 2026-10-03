#!/usr/bin/env python3
"""The phase-2 assumption table checks itself.

A number nobody can trace is a number nobody can correct, so every figure in
`config/simulation-assumptions-2026-10.json` carries its source and its sample
size - and this module asserts that the figures REPRODUCE from the n printed
beside them. A config file that merely claims a provenance is a config file
whose provenance has never been read.

The test that matters most here is the last one. The brief's instruction was:
"if the classifier moves again, the assumptions are stale and say so". Saying
so in prose is a note somebody has to remember to read. Asserting it makes the
staleness a RED TEST on the commit that moves the classifier.
"""
import json
import os
import unittest

from src import clients, replies, store

PATH = os.path.join(store.ROOT, "config", "simulation-assumptions-2026-10.json")

# Every derived rate in the file, as (dotted path, numerator key, denominator
# key). Written out rather than discovered, because a test that walks whatever
# it finds would pass on an empty file.
DERIVED = (
    ("bounce_rate.estate_lifetime", "bounced", "sends"),
    ("bounce_rate.resonate_os_rows", "bounced", "terminal"),
    ("unsubscribe_rate.share_of_replies", "unsubscribe", "replies"),
    ("reply_rate_per_send.step_1", "replies", "sends"),
    ("reply_class_share.automated_share_as_a_separate_witness",
     "automated", "replies"),
    ("reply_class_share.provider_interested_flag", "interested", "replies"),
)

UNKNOWNS = (
    "unsubscribe_rate.per_send",
    "reply_rate_per_send.step_2_and_later",
    "reply_rate_by_persona",
    "reply_latency_per_step",
    "recontact_windows.cold_lead_gap_since_manual_touch",
    "reply_class_share.the_other_fourteen_classes",
)


def at(data, dotted):
    node = data
    for part in dotted.split("."):
        node = node[part]
    return node


class TheTable(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(PATH, "r", encoding="utf-8") as handle:
            cls.data = json.load(handle)

    def test_it_parses_with_the_standard_library(self):
        """No PyYAML, no clients.parse, no third-party reader."""
        self.assertIsInstance(self.data, dict)
        self.assertIn("classifier_identity", self.data)

    def test_the_project_config_parser_would_corrupt_it(self):
        """THE MEASUREMENT BEHIND THE FORMAT CHOICE.

        The lane's instruction was to use `clients.parse` rather than PyYAML.
        `clients.scalar` promotes only integers - `text.isdigit()` - so a rate
        comes back as a STRING, and every figure in this table is a rate. JSON
        is not a way around the instruction; it is the reading that survives
        the measurement, and this is the measurement.
        """
        got = clients.parse("rate: 0.009792\nn: 200674\n")
        self.assertEqual(got["n"], 200674)
        self.assertIsInstance(got["n"], int)
        self.assertEqual(got["rate"], "0.009792")
        self.assertIsInstance(
            got["rate"], str,
            "clients.parse now carries floats; the format note in the "
            "assumptions file is out of date and should be revisited")

    def test_every_derived_rate_reproduces_from_its_own_sample(self):
        for dotted, over, under in DERIVED:
            with self.subTest(dotted):
                cell = at(self.data, dotted)
                self.assertIn("source", cell)
                counts = cell["n"]
                self.assertIn(over, counts, f"{dotted} lost its numerator")
                self.assertIn(under, counts, f"{dotted} lost its denominator")
                self.assertAlmostEqual(
                    cell["value"], counts[over] / counts[under], places=6,
                    msg=f"{dotted}: {cell['value']} does not reproduce from "
                        f"{counts[over]}/{counts[under]}")

    def test_every_derived_rate_carries_a_source_and_a_sample_size(self):
        for dotted, _, _ in DERIVED:
            with self.subTest(dotted):
                cell = at(self.data, dotted)
                self.assertTrue(str(cell.get("source") or "").strip())
                self.assertTrue(cell.get("n"))

    def test_the_class_shares_sum_to_the_accounted_share(self):
        """Three of seventeen classes are recorded and 221 replies are not.
        The file says so in two places and they have to agree."""
        share = self.data["reply_class_share"]
        corpus = share["n_corpus"]
        counted = sum(c["n"] for c in share["classes"].values())
        self.assertEqual(counted, share["accounted_for"]["n"])
        self.assertEqual(share["accounted_for"]["of"], corpus)
        self.assertAlmostEqual(share["accounted_for"]["share"],
                               counted / corpus, places=6)
        residual = share["the_other_fourteen_classes"]["n_unaccounted"]
        self.assertEqual(counted + residual, corpus)
        for name, cell in share["classes"].items():
            with self.subTest(name):
                self.assertAlmostEqual(cell["value"], cell["n"] / cell["of"],
                                       places=6)

    def test_no_unknown_was_quietly_given_a_number(self):
        """UNKNOWN never becomes zero, and it always says what would fix it.

        The specific failure this guards is in the file itself:
        `pc-lead-sends.jsonl` reports `replies: 0` on all 20,221 rows because
        the field was never populated, and read naively that is a 0.0% reply
        rate over 13,874 sends.
        """
        for dotted in UNKNOWNS:
            with self.subTest(dotted):
                cell = at(self.data, dotted)
                self.assertEqual(cell.get("value", "UNKNOWN"), "UNKNOWN")
                self.assertTrue(str(cell.get("why") or "").strip(),
                                f"{dotted} is UNKNOWN with no reason")
                self.assertTrue(str(cell.get("would_derive") or "").strip(),
                                f"{dotted} does not say what would derive it")

    def test_the_scheduler_inputs_match_the_code_they_claim(self):
        """Not the text of the source - the values the modules expose."""
        from src import eligibility, revival, senderheadroom

        inputs = self.data["scheduler_inputs"]
        self.assertEqual(inputs["forward_book_staleness_hours"]["value"],
                         senderheadroom.STALE_AFTER_HOURS)
        self.assertEqual(tuple(inputs["sending_days"]["value"]),
                         senderheadroom.WEEKDAYS)
        self.assertEqual(inputs["horizon_days"]["value"],
                         senderheadroom.DEFAULT_HORIZON_DAYS)

        windows = self.data["recontact_windows"]
        self.assertEqual(windows["revival_cooling_days"]["value"],
                         revival.DEFAULTS["cooling_days"])
        self.assertEqual(windows["min_separation_days"]["value"],
                         eligibility.DEFAULT_MIN_SEPARATION_DAYS)

    def test_the_cold_lead_gap_really_has_no_implementation(self):
        """The UNKNOWN above rests on this, so it is measured rather than
        asserted in prose. CLAUDE.md rule 2 requires a configured gap since
        the last manual or internal touch before a COLD LEAD is contacted."""
        import glob

        names = ("gap_days", "min_days_since", "min_gap", "recontact_days")
        hits = []
        for path in glob.glob(os.path.join(store.ROOT, "src", "**", "*.py"),
                              recursive=True):
            if os.path.basename(path) == "outcomes.py":
                continue          # reporting buckets, named in the file
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                body = handle.read()
            hits += [f"{os.path.basename(path)}:{n}" for n in names
                     if n in body]
        self.assertEqual(hits, [],
                         "a cold-lead recontact gap now exists in code; the "
                         "assumptions file still records it as UNKNOWN")

    def test_the_table_goes_stale_the_moment_the_classifier_moves(self):
        """THE STALENESS ALARM, as a test rather than a note.

        Every class share in this file was measured at one rule hash. The hash
        is sha256 over every pattern list, the RULES order and the thresholds,
        so any rule edit moves it - and TASK-941 is already pending with a
        change that takes `unknown` from 278 to 274 on the same corpus.

        When this fails, the fix is NOT to update the hash. It is to re-derive
        the class shares at the new hash, or to mark them UNKNOWN until
        somebody does.
        """
        self.assertEqual(
            self.data["classifier_identity"]["rule_hash"], replies.RULE_HASH,
            "the reply classifier has moved since this table was derived, so "
            "every figure under reply_class_share and unsubscribe_rate."
            "share_of_replies is STALE. Re-derive them against the new hash "
            "or mark them UNKNOWN - do not edit the hash in the file.")
        self.assertEqual(self.data["classifier_identity"]["version"],
                         replies.VERSION)


if __name__ == "__main__":
    unittest.main()
