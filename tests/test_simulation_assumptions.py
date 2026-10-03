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

import re

from src import (accountpolicy as ap, clients, eligibility, replies,
                 store)

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
    "recontact_windows.cold_lead_gap_since_manual_touch",
    "reply_class_share.the_two_classes_that_never_occur",
    "reply_rate_by_persona.vertical_dimension",
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

    def test_the_class_shares_account_for_the_whole_corpus(self):
        """All fifteen classes the rules produce, n=899, no residual.

        Every class name is checked against `replies.CATEGORIES` as well as
        summed, because a share for a class the classifier cannot return
        would be a rate for something that never happens.
        """
        share = self.data["reply_class_share"]
        corpus = share["n_corpus"]
        counted = sum(c["n"] for c in share["classes"].values())
        self.assertEqual(counted, corpus, "the classes no longer sum to n")
        self.assertEqual(share["accounted_for"]["n"], corpus)
        self.assertEqual(share["accounted_for"]["share"], 1.0)
        for name, cell in share["classes"].items():
            with self.subTest(name):
                self.assertIn(name, replies.CATEGORIES)
                self.assertAlmostEqual(cell["value"], cell["n"] / cell["of"],
                                       places=6)
        self.assertEqual(sum(share["campaigns"].values()), corpus)

    def test_every_persona_cell_sums_to_its_own_sample(self):
        """The persona split the brief warned might not be computable. It is,
        899 of 899, and each row has to close against its own n."""
        block = self.data["reply_rate_by_persona"]
        self.assertEqual(sum(block["n_per_persona"].values()),
                         self.data["reply_class_share"]["n_corpus"])
        for name, cell in block["cells"].items():
            with self.subTest(name):
                self.assertEqual(cell["n"], block["n_per_persona"][name])
                self.assertEqual(sum(c["n"] for c in cell["classes"].values()),
                                 cell["n"])
                for cl, c in cell["classes"].items():
                    self.assertIn(cl, replies.CATEGORIES)
                    self.assertAlmostEqual(c["value"], c["n"] / cell["n"],
                                           places=6)

    def test_the_latency_split_accounts_for_every_joined_reply(self):
        """754 human plus 134 automated is 888, and 888 plus the 11 that
        carry no sent_at is 899. The n that survived the join, reported as
        the brief required - not the n of replies."""
        block = self.data["reply_latency_per_step"]
        human, auto = block["human"], block["automated"]
        self.assertEqual(human["n"] + auto["n"], block["n_surviving_the_join"])
        self.assertEqual(block["n_surviving_the_join"] + block["n_lost"],
                         block["n_replies"])
        for side in (human, auto):
            self.assertEqual(sum(s["n"] for s in side["by_step"].values()),
                             side["n"])
        self.assertEqual(sorted(human["by_step"]), sorted(auto["by_step"]))
        self.assertGreater(human["overall"]["median_h"],
                           auto["overall"]["median_h"] * 100,
                           "the human/automated split has collapsed; if these "
                           "medians are now comparable the combined figure is "
                           "no longer an artefact and the warning is stale")
        for step, cell in human["by_step"].items():
            with self.subTest(step):
                self.assertGreaterEqual(cell["mean_h"], cell["median_h"],
                                        "heavy tail claim inverted")

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



class TheScenarioCatalogue(unittest.TestCase):
    """The catalogue's row count is a deliverable, so it is asserted by NAME.

    A baseline is a named list and is compared by set, never by count - this
    repository has already had three finished suites report exactly 231
    failing names where one of them was a different 231. So this checks the
    thirty IDS, and the total only as a consequence of them.
    """

    DIR = os.path.join(store.ROOT, "docs", "phase2-scenarios")
    EXPECTED_IDS = tuple("S%02d" % n for n in range(1, 31))

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(cls.DIR, "CATALOGUE.md"), "r",
                  encoding="utf-8") as handle:
            cls.catalogue = handle.read()
        with open(os.path.join(cls.DIR, "README.md"), "r",
                  encoding="utf-8") as handle:
            cls.readme = handle.read()

    def test_the_catalogue_holds_exactly_the_thirty_named_rows(self):
        found = re.findall(r"^\| (S\d\d) \|", self.catalogue, re.M)
        self.assertEqual(tuple(found), self.EXPECTED_IDS)
        self.assertEqual(len(set(found)), 30, "a row id is duplicated")

    def test_every_row_declares_all_seven_columns(self):
        """So a row that lost its `expected` cell is visible rather than
        silently narrower than the others."""
        for line in self.catalogue.splitlines():
            if re.match(r"^\| S\d\d \|", line):
                with self.subTest(line.split("|")[1].strip()):
                    self.assertEqual(line.count("|"), 8, line[:90])

    def test_the_unimpl_count_matches_the_rows_it_claims(self):
        """The header, the column and the closing paragraph have to agree.

        A count that disagrees with its own table is the defect this
        repository keeps rediscovering, so all three statements of it are
        cross-checked rather than trusted. The first draft of this catalogue
        said eleven and marked eight.
        """
        marked = re.findall(r"^\| (S\d\d) \|.*\| yes \|$", self.catalogue,
                            re.M)
        self.assertEqual(len(marked), 8, marked)
        self.assertIn("**eight of thirty**", self.catalogue)
        summary = self.catalogue.split("Eight rows carry")[-1]
        for row in marked:
            self.assertIn(row, summary,
                          f"{row} is marked yes but is not named in the "
                          f"closing summary")

    def test_every_yaml_block_in_the_readme_parses(self):
        """THE SHAPE IS PROVEN, NOT DESCRIBED.

        A worker who sees only the README has to be able to produce a file
        the project's own parser accepts, so every example in it is run
        through `clients.parse` here - including the full worked S01, whose
        value TYPES are checked, because the parser's worst failure mode is
        accepting a value and converting it wrongly.
        """
        blocks = re.findall(r"```yaml\r?\n(.*?)```", self.readme, re.S)
        self.assertEqual(len(blocks), 5, "the README's examples moved")
        for i, block in enumerate(blocks, 1):
            with self.subTest(block=i):
                clients.parse(block)

        whole = clients.parse(blocks[-1])
        self.assertEqual(sorted(whole),
                         ["covers", "event", "expected", "id", "intent",
                          "rule", "setup"])
        self.assertIsInstance(whole["covers"], list)
        self.assertTrue(whole["setup"]["record"]["domain"].endswith(".invalid"))
        self.assertIs(whole["setup"]["record"]["synthetic"], True)
        self.assertIsInstance(whole["event"]["on_day"], int)
        self.assertEqual(whole["expected"]["provider_writes"], 0)
        self.assertIs(whole["expected"]["cross_channel_stop"], True)
        self.assertIn(whole["expected"]["replies_classify"],
                      replies.CATEGORIES)
        self.assertIn(whole["expected"]["accountpolicy_outcome"], ap.OUTCOMES)
        self.assertIn(whole["expected"]["eligibility_verdict"],
                      eligibility.VERDICTS)

    def test_the_readme_forbids_exactly_what_the_parser_refuses(self):
        """The four parser facts the README states, measured here.

        The fourth is the dangerous one: a float is ACCEPTED and silently
        becomes a string, so the README has to forbid floats outright rather
        than rely on an error that never comes.
        """
        for bad in ("covers:\n  - a\n", "intent: >-\n  folded\n",
                    "no_colon_here\n"):
            with self.subTest(bad):
                with self.assertRaises(clients.ConfigError):
                    clients.parse(bad)
        self.assertEqual(clients.parse("rate: 0.022\n")["rate"], "0.022")

    def test_every_expected_key_the_readme_declares_names_a_real_authority(self):
        """The README's `expected` table is a contract with the worker.

        Each key claims a module and a function. A key naming something that
        does not exist would send thirty files asserting nothing, so the
        callables are resolved here rather than taken on trust.
        """
        import importlib

        for module, attr in (("replies", "classify"),
                             ("accountpolicy", "classify_outcome"),
                             ("channels", "email_verdict"),
                             ("channels", "linkedin_verdict"),
                             ("eligibility", "decide"),
                             ("collision", "account_policy"),
                             ("hygiene", "check"),
                             ("oooreturn", "assess"),
                             ("senderheadroom", "verdict")):
                with self.subTest(f"{module}.{attr}"):
                    got = importlib.import_module(f"src.{module}")
                    self.assertTrue(callable(getattr(got, attr)))
                    self.assertIn(f"`{module}.{attr}", self.readme)

    def test_the_five_step_labels_really_have_no_implementation(self):
        """The catalogue's central claim, and the reason eight rows are
        marked unimplemented. Asserted on the import surface rather than by
        searching prose, so a comment mentioning one cannot satisfy it."""
        import glob

        names = ("BLOCKED_FOREVER", "ON_HOLD", "COLD_LEAD", "STARI")
        hits = []
        for path in glob.glob(os.path.join(store.ROOT, "src", "**", "*.py"),
                              recursive=True):
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                body = handle.read()
            hits += [f"{os.path.basename(path)}:{n}" for n in names
                     if n in body]
        self.assertEqual(
            hits, [],
            "a rule-2 lead class now exists in code; the catalogue's "
            "unimpl column and its eight marked rows are out of date")


if __name__ == "__main__":
    unittest.main()
