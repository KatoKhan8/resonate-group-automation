#!/usr/bin/env python3
"""TASK-0190. A present-but-EMPTY authority is UNKNOWN, never PASS.

## THE HAZARD, MEASURED BEFORE ANY OF IT WAS WRITTEN

`src/preflight.py` shipped an authority gate that asked exactly one
question: IS THE FILE THERE. TASK-0170 had already measured, and written
into that module's own docstring, the two facts that make one question not
enough:

    store.PRODUCTION_WORK resolves against the CALLING tree's root
    store.load() answers 0 rows, NO RAISE, with work/queue.jsonl absent

So a rotated, truncated, half-written or wrong-tree `queue.jsonl` came out
PRESENT. **FOURTEEN** of the twenty-two rules read the queue - the brief and
every earlier note said thirteen, and
`test_fourteen_rules_read_the_queue_not_the_thirteen_everybody_typed` is why
that number is now measured. Every one of them would have been asked, found
nothing, and reported PASS - and the report's headline sentence, `CANARY-01
IS CLEARED TO SEND`, is computed from exactly those cells. The operator's
next action was to run that preflight from the main checkout.

**Nothing in the instrument could tell that world from one where the queue
was read and this person genuinely is not in it.** Nor could its three
controls: control 2 plants a read that RAISES, which is the one failure
mode an empty file does not have, and control 3 planted - in its own words -
"present, empty, readable authority files" and asserted PASS on four rules.
The instrument's proof that a PASS was reachable was a demonstration of the
defect.

## WHAT IS PINNED HERE

    ABSENT               no file at the resolved absolute path
    PRESENT_UNREADABLE   resolving, opening or parsing raises
    PRESENT_EMPTY        opens, parses, yields ZERO records
    PRESENT_POPULATED    opens, parses, yields at least one record
    OUTSIDE_TREE         a hard refusal: not this tree's file at all

Both halves, as always: the hazard, so nobody assumes the readers were
changed - they were not, and they must not be, because they sit on send
paths - and the compensation, so nobody removes it.

## AND THE ASYMMETRY, WHICH IS NOT SYMMETRICAL ON PURPOSE

An EXCLUSION found on an empty or partial authority is still an exclusion; a
rule that did not fire against one has not been answered. `senderheadroom`'s
rule: a walk can only undercount, so FULL is provable from any walk and ROOM
is not.

## NO REAL ADDRESS IS IN THIS FILE

Reserved domains only, and this module asserts it on its own bytes.
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import agencydnc, ingest, operatorexclusion, preflight   # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "canary_preflight.py")

#: Reserved domains only. A contact with a record, so the FOURTEEN
#: record-needing rules do not answer UNKNOWN for a different reason and
#: leave a test green by accident.
CONTACT = {"key": "empty-1", "name": "A Person", "company": "A Co",
           "email": "someone@example.invalid", "domain": "example.invalid",
           "record": {"id": "r-1", "domain": "example.invalid"}}


class _Plant(unittest.TestCase):
    """A temp tree of authority files, populated or empty by name."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-0190-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(operatorexclusion.forget)
        operatorexclusion.forget()

    def plant(self, empty=(), where=None):
        """(state, paths). `root` is the temp tree, so OUTSIDE_TREE is not
        what is being measured unless a test asks for it."""
        where = where or self.tmp
        os.makedirs(where, exist_ok=True)
        return preflight._planted_state(where, empty=empty)

    def pointed(self, paths):
        return preflight._pointed(paths)


class APresentFileCanStillBeEmpty(_Plant):
    """The four states, measured on planted bytes."""

    def test_an_empty_authority_file_is_present_empty_not_populated(self):
        state, paths = self.plant(empty=("agency_dnc",))
        row = state["agency_dnc"]
        self.assertTrue(os.path.exists(row["path"]), row["path"])
        self.assertEqual(preflight.PRESENT_EMPTY, row["state"])
        self.assertEqual(0, row["records"])
        self.assertEqual(0, row["bytes"])
        # AND IT IS NOT ANSWERABLE. The state name alone is a label; this is
        # the fact that licenses or refuses a PASS.
        self.assertNotIn(row["state"], preflight.ANSWERABLE)
        self.assertIn("agency_dnc", preflight.unanswerable(state))

    def test_a_populated_authority_file_is_present_populated(self):
        """The control on the test above: the SAME plant, one record in, so
        PRESENT_EMPTY above is about the record count and not about a
        counter that returns zero for everything."""
        state, _ = self.plant()
        row = state["agency_dnc"]
        self.assertEqual(preflight.PRESENT_POPULATED, row["state"])
        self.assertEqual(1, row["records"])
        self.assertEqual([], preflight.unanswerable(state))

    def test_a_comment_only_authority_is_empty_not_populated(self):
        """THE EXACT BYTES THE OLD CONTROL PLANTED. `_planted_state` used to
        write `# planted by preflight.controls` into every authority file,
        and `agencydnc.load` skips `#` lines - so that file held nothing and
        read as PRESENT."""
        state, paths = self.plant()
        with io.open(paths["agency_dnc"], "w", encoding="utf-8",
                     newline="\n") as handle:
            handle.write("# planted by preflight.controls\n")
        state = preflight._planted_state(self.tmp, paths=paths)[0]
        self.assertGreater(state["agency_dnc"]["bytes"], 0)
        self.assertEqual(0, state["agency_dnc"]["records"])
        self.assertEqual(preflight.PRESENT_EMPTY, state["agency_dnc"]["state"])

    def test_a_whitespace_only_authority_is_empty_not_populated(self):
        """A half-written file: the newlines landed, the rows did not."""
        state, paths = self.plant()
        with io.open(paths["queue"], "w", encoding="utf-8",
                     newline="\n") as handle:
            handle.write("\n\n   \n")
        state = preflight._planted_state(self.tmp, paths=paths)[0]
        self.assertGreater(state["queue"]["bytes"], 0)
        self.assertEqual(preflight.PRESENT_EMPTY, state["queue"]["state"])

    def test_a_damaged_authority_is_unreadable_and_not_empty(self):
        """Three different incidents, three states. A file that parses to
        nothing is not a file that would not parse."""
        state, paths = self.plant()
        with io.open(paths["queue"], "w", encoding="utf-8",
                     newline="\n") as handle:
            handle.write("{not json at all\n")
        state = preflight._planted_state(self.tmp, paths=paths)[0]
        self.assertEqual(preflight.PRESENT_UNREADABLE, state["queue"]["state"])
        self.assertIsNone(state["queue"]["records"])
        self.assertIn("could not be read", state["queue"]["why"])

    def test_a_damaged_dnc_line_is_unreadable_rather_than_fewer_people(self):
        """`agencydnc.load(strict=True)` exists for "a caller that would
        rather refuse than suppress fewer people than the file names". The
        preflight is that caller; the send path keeps the lenient default,
        and this test is also the proof that the counter goes through the
        module that owns the format."""
        state, paths = self.plant()
        agencydnc.add("email", "another-control@other.invalid",
                      file_path=paths["agency_dnc"])
        with io.open(paths["agency_dnc"], "a", encoding="utf-8",
                     newline="\n") as handle:
            handle.write('{"fingerprint": "truncated-ro\n')
        state = preflight._planted_state(self.tmp, paths=paths)[0]
        self.assertEqual(preflight.PRESENT_UNREADABLE,
                         state["agency_dnc"]["state"])
        # The lenient reader on the send path is UNCHANGED, and that is the
        # division of labour this task was explicitly told to keep.
        self.assertEqual(2, len(agencydnc.load(
            file_path=paths["agency_dnc"])))


class AnEmptyAuthorityIsUnknownAndNeverPass(_Plant):
    """The compensation, against the exact hazard in this module's header."""

    def test_a_present_but_empty_authority_is_unknown_not_pass(self):
        """THE ONE CELL THIS WHOLE TASK IS ABOUT.

        Everything else populated, the contact's record supplied, so the
        agency-DNC cell is UNKNOWN for its OWN reason and not because a
        different guard fired first - which is the trap that left control 2
        green under a blinded gate. The sibling assertion is the control:
        `suppression_domain_list`, whose authorities are populated, is PASS
        in the same row, so this test cannot pass vacuously by everything
        being UNKNOWN.
        """
        state, paths = self.plant(empty=("agency_dnc",))
        with self.pointed(paths):
            row = preflight.evaluate(CONTACT, state=state)
        self.assertEqual(preflight.PRESENT_EMPTY,
                         state["agency_dnc"]["state"])
        cell = row["cells"]["agency_dnc"]
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("PRESENT_EMPTY", cell["why"])
        self.assertIn("WHICH MEANS", cell["why"])
        # THE CONTROL INSIDE THE TEST.
        self.assertEqual(preflight.PRESENT_POPULATED,
                         state["suppression_template"]["state"])
        self.assertEqual(preflight.PASS,
                         row["cells"]["suppression_domain_list"]["cell"])

    def test_the_same_rule_is_asked_when_that_authority_is_populated(self):
        """The other direction. Without it, an instrument answering UNKNOWN
        to everything would satisfy the test above."""
        state, paths = self.plant()
        with self.pointed(paths):
            row = preflight.evaluate(CONTACT, state=state)
        self.assertEqual(preflight.PASS, row["cells"]["agency_dnc"]["cell"])
        self.assertEqual("asked, did not fire",
                         row["cells"]["agency_dnc"]["why"])

    def test_a_populated_authority_really_fires_on_a_planted_match(self):
        """And a real verdict out of it, not just a PASS: the rule finds the
        one record the authority holds."""
        state, paths = self.plant()
        planted = "asked-to-stop@example.test"
        agencydnc.add("email", planted, file_path=paths["agency_dnc"])
        state = preflight._planted_state(self.tmp, paths=paths)[0]
        with self.pointed(paths):
            row = preflight.evaluate(
                dict(CONTACT, email=planted, domain="example.test"),
                state=state)
        self.assertEqual(preflight.PRESENT_POPULATED,
                         state["agency_dnc"]["state"])
        self.assertEqual(preflight.EXCLUDED,
                         row["cells"]["agency_dnc"]["cell"])

    def test_fourteen_rules_read_the_queue_not_the_thirteen_everybody_typed(
            self):
        """THE NUMBER, MEASURED, AND IT IS NOT THE ONE IN THE BRIEF.

        TASK-0190 says "Thirteen of the twenty-two rules read
        `work/queue.jsonl`". It is FOURTEEN: all fourteen consulted on the
        email path, eleven on the linkedin path, because
        `client_own_domain`, `bounce_history` and `mx_and_verification` are
        email-only. A number typed rather than derived is this lane's own
        signature defect, so it is asserted here in both directions - if a
        rule is added or removed, this test fails and the prose has to be
        corrected with it.
        """
        state, paths = self.plant(empty=("queue",))
        with self.pointed(paths):
            row = preflight.evaluate(CONTACT, state=state)
        queue_rules = [r["name"] for r in preflight.RULES
                       if "queue" in r["needs"]]
        self.assertEqual(14, len(queue_rules))
        self.assertEqual(22, len(preflight.RULES))
        self.assertEqual(11, len([n for n in queue_rules
                                  if [r for r in preflight.RULES
                                      if r["name"] == n][0]["channel"]
                                  != "email"]))
        for name in queue_rules:
            with self.subTest(rule=name):
                self.assertEqual(preflight.UNKNOWN,
                                 row["cells"][name]["cell"])
        self.assertFalse(row["cleared"])

    def test_an_empty_authority_cannot_clear_a_cohort_and_exits_two(self):
        state, paths = self.plant(empty=("agency_dnc",))
        with self.pointed(paths):
            out = preflight.assess([CONTACT], state=state,
                                   control_rows=[{"ok": True}])
        self.assertEqual(0, out["totals"]["cleared"])
        self.assertEqual(1, out["totals"]["not_cleared_because_unknown"])
        self.assertEqual(preflight.EXIT_UNKNOWN, out["exit_code"])
        self.assertIn("NOT CLEARED", out["sentence"])

    def test_not_one_pass_survives_when_every_authority_is_empty(self):
        """TASK-0190 section 2's plant, as a test. Every authority present,
        parsing, holding nothing: no rule that could be asked may report
        PASS. A `not_applicable` PASS - a rule not consulted on this
        channel - is counted apart and is not one."""
        state, paths = self.plant(empty=preflight.AUTHORITY_NAMES)
        with self.pointed(paths):
            out = preflight.assess([CONTACT, dict(CONTACT, key="empty-2")],
                                   state=state, control_rows=[{"ok": True}])
        real = [(name, row["key"]) for row in out["rows"]
                for name, cell in row["cells"].items()
                if cell["cell"] == preflight.PASS
                and not cell.get("not_applicable")]
        self.assertEqual([], real)
        self.assertEqual(0, out["totals"]["cleared"])
        self.assertEqual(preflight.EXIT_UNKNOWN, out["exit_code"])


class TheAsymmetryIsKept(_Plant):
    """An exclusion on an empty or partial authority is still an exclusion."""

    def test_an_exclusion_from_the_populated_half_survives_an_empty_half(self):
        state, paths = self.plant(empty=("suppression_local_roster",))
        with io.open(paths["suppression_template"], "w", encoding="utf-8",
                     newline="\n") as handle:
            handle.write("example.test\n")
        state = preflight._planted_state(self.tmp, paths=paths)[0]
        self.assertEqual(preflight.PRESENT_EMPTY,
                         state["suppression_local_roster"]["state"])
        with self.pointed(paths):
            row = preflight.evaluate(
                dict(CONTACT, email="x@example.test", domain="example.test"),
                state=state)
        cell = row["cells"]["suppression_domain_list"]
        self.assertEqual(preflight.EXCLUDED, cell["cell"])
        self.assertIn("missing one cannot change it", cell["why"])

    def test_but_not_firing_against_an_empty_half_is_not_an_answer(self):
        state, paths = self.plant(empty=("suppression_local_roster",))
        with self.pointed(paths):
            row = preflight.evaluate(CONTACT, state=state)
        cell = row["cells"]["suppression_domain_list"]
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("readable half WAS asked and did not fire", cell["why"])


class AnAuthorityOutsideTheTreeIsAHardRefusal(_Plant):
    """The per-tree resolution this module documents is how a preflight
    reads the wrong `work/`. It is refused, with both paths, non-zero."""

    def test_a_path_outside_the_asked_tree_is_refused_with_both_paths(self):
        state, paths = self.plant()
        elsewhere = tempfile.mkdtemp(prefix="rga-0190-other-tree-")
        self.addCleanup(shutil.rmtree, elsewhere, ignore_errors=True)
        stray = os.path.join(elsewhere, "queue.jsonl")
        with io.open(stray, "w", encoding="utf-8", newline="\n") as handle:
            handle.write('{"id": "another-trees-record"}\n')
        resolvers = {name: (lambda _p=path: _p)
                     for name, path in paths.items()}
        resolvers["queue"] = (lambda: stray)
        state = preflight.authorities(resolvers=resolvers, root=self.tmp)
        row = state["queue"]
        self.assertEqual(preflight.OUTSIDE_TREE, row["state"])
        # BOTH PATHS PRINTED. Naming only one is how somebody looks in the
        # wrong tree for the file that was wrong about the tree.
        self.assertIn(stray, row["why"])
        self.assertIn(self.tmp, row["why"])
        self.assertIn("HARD REFUSAL", row["why"])
        # AND IT IS POPULATED, which is the point: a readable, populated,
        # perfectly good file from the wrong checkout.
        self.assertIsNone(row["records"])

    def test_the_refusal_exits_non_zero_and_names_the_authority(self):
        state, paths = self.plant()
        resolvers = {name: (lambda _p=path: _p)
                     for name, path in paths.items()}
        resolvers["queue"] = (lambda: os.path.join(ROOT, "work",
                                                   "queue.jsonl"))
        state = preflight.authorities(resolvers=resolvers, root=self.tmp)
        with self.pointed(paths):
            out = preflight.assess([CONTACT], state=state,
                                   control_rows=[{"ok": True}])
        self.assertEqual(["queue"], out["authority_refusals"])
        self.assertEqual(preflight.EXIT_UNKNOWN, out["exit_code"])
        self.assertIn("could not determine the state of queue",
                      out["sentence"])

    def test_the_real_tree_resolves_all_five_inside_itself(self):
        """The control on the two above: in this checkout, with no plant,
        every authority path IS inside the tree - so OUTSIDE_TREE above is
        about the planted path and not about a containment check that
        refuses everything."""
        state = preflight.authorities()
        for name in preflight.AUTHORITY_NAMES:
            with self.subTest(authority=name):
                self.assertNotEqual(preflight.OUTSIDE_TREE,
                                    state[name]["state"])
                self.assertTrue(preflight._inside(preflight.tree_root(),
                                                  state[name]["path"]))


class AnUndeterminedAuthorityIsNotAPass(_Plant):

    def test_an_unreadable_authority_exits_non_zero_with_no_rule_reading_it(
            self):
        """§3: "Any authority whose state cannot be determined is
        PRESENT_UNREADABLE, and every rule depending on it is UNKNOWN, and
        the run exits non-zero." The cells alone cannot deliver the last
        clause for an authority no rule happens to read, so `assess` counts
        the refusals itself."""
        state, paths = self.plant(empty=())
        state = preflight._planted_state(self.tmp, raising=("queue",),
                                         paths=paths)[0]
        only = dict(preflight.RULES[3], name="reads_the_dnc_only",
                    needs=("agency_dnc",))
        with mock.patch.object(preflight, "RULES", (only,)), \
                mock.patch.object(preflight, "RULE_NAMES",
                                  ("reads_the_dnc_only",)):
            with self.pointed(paths):
                out = preflight.assess([CONTACT], state=state,
                                       control_rows=[{"ok": True}])
        self.assertEqual(preflight.PASS,
                         out["rows"][0]["cells"]["reads_the_dnc_only"]["cell"])
        self.assertEqual(["queue"], out["authority_refusals"])
        self.assertEqual(preflight.EXIT_UNKNOWN, out["exit_code"])
        self.assertIn("does not know what it did not read", out["sentence"])

    def test_every_declared_authority_is_read_by_at_least_one_rule(self):
        """Which closes the same hole by construction rather than by the
        guard above: an authority nobody reads could go ABSENT or EMPTY
        without moving a single cell."""
        unread = [name for name in preflight.AUTHORITY_NAMES
                  if not any(name in r["needs"] for r in preflight.RULES)]
        self.assertEqual([], unread)

    def test_a_rule_declaring_no_authority_cannot_report_pass(self):
        """§3 again: there is nothing whose state could make its PASS true.
        The ask would NOT have fired, so without the floor this is a PASS."""
        rule = dict(preflight.RULES[3], name="declares_nothing", needs=(),
                    ask=lambda ctx: None)
        rule.pop("needs_provider_read", None)
        rule.pop("needs_record", None)
        state, paths = self.plant()
        with mock.patch.object(preflight, "RULES", (rule,)), \
                mock.patch.object(preflight, "RULE_NAMES",
                                  ("declares_nothing",)):
            with self.pointed(paths):
                row = preflight.evaluate(CONTACT, state=state)
        cell = row["cells"]["declares_nothing"]
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertIn("declares no authority", cell["why"])

    def test_the_undeclared_list_holds_only_the_provider_read_rules(self):
        """The list is printed rather than tolerated, and a name on it that
        is not a provider-read rule is a declaration defect."""
        self.assertEqual(("hold_active_sequence", "hold_recent_touch",
                          "hold_total_sends", "cooling_90_days"),
                         preflight.RULES_WITHOUT_DECLARED_AUTHORITY)
        for name in preflight.RULES_WITHOUT_DECLARED_AUTHORITY:
            rule = [r for r in preflight.RULES if r["name"] == name][0]
            with self.subTest(rule=name):
                self.assertTrue(rule.get("needs_provider_read"))


class TheFiveControlsAndWhyFourAndFiveAreAPair(unittest.TestCase):

    def test_there_are_five_controls_and_every_one_holds(self):
        rows = preflight.controls()
        self.assertEqual(5, len(rows))
        for row in rows:
            with self.subTest(control=row["control"]):
                self.assertTrue(row["ok"], "%s: expected %r observed %r"
                                % (row["control"], row["expected"],
                                   row["observed"]))

    def test_control_four_observes_the_state_the_count_and_the_exit(self):
        """A control that watched only the cell could be right for the wrong
        reason - which happened to control 2 under a blinded gate."""
        row = preflight.controls()[3]
        self.assertIn("EMPTY", row["control"])
        self.assertEqual([preflight.PRESENT_EMPTY, 0, preflight.UNKNOWN,
                          True], row["observed"])
        self.assertIn("DISCRIMINATOR", row["note"])

    def test_control_five_is_control_four_with_exactly_one_record(self):
        """Why it exists, stated in the row itself: control 4 and a non-zero
        exit are both passed by an instrument that answers UNKNOWN to
        everything."""
        four, five = preflight.controls()[3], preflight.controls()[4]
        self.assertEqual([preflight.PRESENT_POPULATED, 1, preflight.EXCLUDED],
                         five["observed"])
        self.assertEqual(0, four["observed"][1])
        self.assertEqual(1, five["observed"][1])
        self.assertIn("UNKNOWN TO EVERYTHING", five["note"])

    def test_control_three_no_longer_plants_the_hazard(self):
        """It planted "present, empty, readable authority files" and
        asserted PASS. That exact sentence must not come back."""
        row = preflight.controls()[2]
        self.assertIn("POPULATED", row["planted"])
        self.assertNotIn("present, empty", row["planted"])
        self.assertEqual([preflight.PASS] * 4, row["observed"])

    def test_an_empty_authority_gate_blinded_to_populated_breaks_control_four(
            self):
        """THE CONTROL ON CONTROL 4, and the one the brief demanded: weaken
        the state check so PRESENT_EMPTY maps to PRESENT_POPULATED, and
        control 4 must go red while control 3 stays green. If control 4
        stayed green it would be watching the wrong cell."""
        real = preflight.authorities

        def blind(*a, **kw):
            state = real(*a, **kw)
            for row in state.values():
                if row["state"] == preflight.PRESENT_EMPTY:
                    row["state"] = preflight.PRESENT_POPULATED
            return state

        with mock.patch.object(preflight, "authorities", blind):
            rows = preflight.controls()
        self.assertFalse(rows[3]["ok"],
                         "a gate blind to PRESENT_EMPTY passed control 4")
        self.assertTrue(rows[2]["ok"],
                        "control 3 should not move: its plant is populated")

    def test_an_instrument_answering_unknown_to_everything_fails_five(self):
        """And the other direction, which is why 5 exists at all."""
        real = preflight.evaluate

        def always_unknown(contact, state=None, channel="email"):
            row = real(contact, state=state, channel=channel)
            for cell in row["cells"].values():
                cell["cell"] = preflight.UNKNOWN
            row["cleared"] = False
            return row

        with mock.patch.object(preflight, "evaluate", always_unknown):
            rows = preflight.controls()
        self.assertFalse(rows[4]["ok"],
                         "an all-UNKNOWN instrument passed control 5")
        self.assertTrue(rows[3]["ok"],
                        "control 4 is satisfied by UNKNOWN, which is the "
                        "whole reason control 5 had to be added")


class TheReportSaysWhichStateAndHowManyRecords(unittest.TestCase):

    def script(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("_cp0190", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_the_markdown_names_the_state_the_count_the_path_and_the_tree(
            self):
        module = self.script()
        tmp = tempfile.mkdtemp(prefix="rga-0190-report-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.addCleanup(operatorexclusion.forget)
        state, paths = preflight._planted_state(tmp, empty=("agency_dnc",))
        with preflight._pointed(paths):
            out = preflight.assess([CONTACT], state=state,
                                   control_rows=preflight.controls())
        text = module.markdown(out, cohort_path="a/plant.json")
        self.assertIn("PRESENT_EMPTY", text)
        self.assertIn("| records |", text.replace(" state |", " state |"))
        self.assertIn(paths["agency_dnc"], text)
        self.assertIn(tmp, text)
        # The empty authority's consequence, in the report, in words.
        self.assertIn("returns {} for an EMPTY file", text)

    def test_the_authorities_run_counts_populated_rather_than_present(self):
        module = self.script()
        printed = []
        code = module.main(["--authorities"])
        self.assertEqual(preflight.EXIT_UNKNOWN, code)
        self.assertEqual([], printed)

    def test_every_authority_declares_what_an_empty_one_means(self):
        for entry in preflight.AUTHORITIES:
            with self.subTest(authority=entry["name"]):
                self.assertTrue(entry["empty_means"].strip())
                self.assertTrue(entry["absent_means"].strip())
                self.assertNotEqual(entry["empty_means"],
                                    entry["absent_means"])
                self.assertTrue(callable(entry["counter"]))


class NothingHereCarriesARealAddress(unittest.TestCase):

    ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
    RESERVED = ("example.test", "example.invalid", "other.invalid",
                "example.com", "example.org", "test", "invalid", "localhost")

    def test_no_real_address_in_this_file_or_the_module(self):
        for path in (os.path.abspath(__file__),
                     os.path.join(ROOT, "src", "preflight.py")):
            text = io.open(path, encoding="utf-8").read()
            found = []
            for match in self.ADDRESS.finditer(text):
                domain = match.group(1).lower()
                if any(domain == r or domain.endswith("." + r)
                       for r in self.RESERVED):
                    continue
                found.append(match.group(0))
            with self.subTest(file=os.path.basename(path)):
                self.assertEqual([], found)

    def test_the_plant_writes_only_inside_the_directory_it_was_given(self):
        """A plant that escaped its temp directory would be writing into
        this repository, or worse into production `work/`."""
        tmp = tempfile.mkdtemp(prefix="rga-0190-scope-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.addCleanup(operatorexclusion.forget)
        paths = preflight.plant_authority_files(tmp)
        for name, path in paths.items():
            with self.subTest(authority=name):
                self.assertTrue(preflight._inside(tmp, path), path)
                self.assertTrue(os.path.exists(path))
        # And the real resolvers were not touched on the way.
        self.assertNotIn(tmp, ingest.SUPPRESS)
        self.assertNotIn(tmp, agencydnc.path())

    def test_the_queue_plant_is_a_record_the_real_reader_accepts(self):
        """Through store's own line reader, so a plant the real parser would
        reject cannot make a control green."""
        from src import store
        tmp = tempfile.mkdtemp(prefix="rga-0190-fmt-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.addCleanup(operatorexclusion.forget)
        paths = preflight.plant_authority_files(tmp)
        rows = store.read_jsonl(paths["queue"])
        self.assertEqual(1, len(rows))
        self.assertTrue(json.dumps(rows[0]))
        self.assertEqual(1, len(operatorexclusion.rows(
            paths["operator_exclusion_register"])[0]))
        self.assertEqual(1, len(agencydnc.load(
            file_path=paths["agency_dnc"], strict=True)))
        self.assertEqual(
            1, len(ingest.load_suppress(path=paths["suppression_template"])))


if __name__ == "__main__":
    unittest.main()
