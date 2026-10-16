#!/usr/bin/env python3
"""Every figure on the lane pages, its source, and whether that source can lie.

THE QUESTION THESE TESTS ANSWER. A `DONE\\` filename in this estate can be
positively false - nine entries stamped 2026-10-16 read `exit1` for briefs the
provider refused, and 21 of the 152 files across the seven lanes were written
by somebody other than a watcher. If any count, throughput, timestamp or
success rate on the lane board, the criteria page or the breach ledger
descends from one of those names, the pages are counting work that did not
happen.

FOUR CONTROLS, AND EACH IS PROVEN ABLE TO FAIL. A control that cannot go red
licenses nothing, and this repository has shipped two that could not:

    C1  a `DONE\\` file with no watcher line behind it moves no figure that
        claims the log as its source
    C2  a `DONE ... -> exit1` whose `.out` is the 429 classifies REFUSED
    C3  a `DONE ... -> exit1` whose `.out` is a real traceback classifies
        FAILED - without this, the new classifier launders every failure in
        the estate into the more comfortable answer
    C4  the hand-close rule cannot swallow a brief the log DOES name

C1 has a second half, C1b, which is the mutation C1 cannot see: the one way
`DONE\\` is read at all is a path BUILT from the watcher's own stamp, and a
file planted at exactly that name IS believed. That is proven rather than
argued, because an unproven limit is one a reader assumes away.
"""
import datetime
import os
import shutil
import tempfile
import unittest

from src import laneprovenance as lp
from src import lanes
from src.web import api


#: The 429 as the estate measured it: the two harness notices this model
#: prints and the provider's own line, 713 bytes in all eight real files.
#: Reproduced here rather than read from the estate, because a test that
#: needs `resonate-ops` on disk is not a test.
REFUSAL_OUT = (
    '"glm-5.3" is not a model this version of Claude Code recognizes, so '
    "auto-compact will keep this session within 200k tokens (the context "
    "window it assumes). If the model accepts more, append [1m] to the model "
    "name for 1M, or set CLAUDE_CODE_MAX_CONTEXT_TOKENS to its real window; "
    "to make it recognized, map it in the modelOverrides setting or update "
    "Claude Code; CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1 "
    "restores the previous wait-for-the-API behavior.\n"
    '[claude-code:unrecognized_model] {"model":"glm-5.3",'
    '"query_source":"generate_session_title"}\n'
    "API Error: Request rejected (429) \u00b7 [1308][Usage limit reached for "
    "5 hour. Your limit will reset at 2026-10-16 08:07:16]"
    "[20261016074449ab70f419de93438a]\n")

#: A REAL failure's output. C3's plant, and it must stay recognisably a
#: report rather than an error line, because a traceback alone would let a
#: classifier pass C3 by looking for the word `Traceback`.
FAILED_OUT = (
    '"glm-5.3" is not a model this version of Claude Code recognizes, so '
    "auto-compact will keep this session within 200k tokens.\n"
    "Read the brief and started on the provider-write guard.\n"
    "Traceback (most recent call last):\n"
    '  File "scripts/measure.py", line 41, in <module>\n'
    "    main()\n"
    "KeyError: 'owned_by_resonate'\n"
    "The measurement did not complete. Nothing committed.\n")


#: One shared sentinel for "this path is not in that payload". A fresh
#: `object()` per lookup compares unequal to itself, which made the first
#: version of C1 report 215 figures as having moved when none had - a control
#: that goes red for its own reason proves nothing about the code, and it
#: would have been read as the result.
_ABSENT = object()


class FixtureEstate:
    """A lane estate on disk: `queue\\<lane>\\`, `RUNNING\\`, `DONE\\`, a
    watcher log and `.out` files. The real one is a person's home directory
    and holds real prospect work; nothing here touches it."""

    def __init__(self, root):
        self.root = root
        os.makedirs(os.path.join(root, "logs"))
        os.makedirs(os.path.join(root, "queue"))
        with open(os.path.join(root, "queue", "README.md"), "w",
                  encoding="utf-8") as handle:
            handle.write("**Floor: never leave a lane below 3 queued "
                         "briefs.**\n")

    def lane(self, name):
        for part in ("", "RUNNING", "DONE"):
            path = os.path.join(self.root, "queue", name, part)
            if not os.path.isdir(path):
                os.makedirs(path)
        with open(os.path.join(self.root, "LANE-%s.md" % name), "w",
                  encoding="utf-8") as handle:
            handle.write("## 2026-10-16 entry\n")
        return name

    def log(self, lane, lines):
        path = os.path.join(self.root, "logs", "watcher-%s.log" % lane)
        with open(path, "a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")

    def up(self, lane, at, timeout=150):
        self.log(lane, ["[%s] [%s] watcher up. tree=C:\\x "
                        "mode=bypassPermissions timeout=%dm"
                        % (at, lane, timeout)])

    def task(self, lane, brief, start, done, suffix, out=None, moved=True):
        """One START..DONE pair, its MOVED line, its `.out` and its `DONE\\`
        entry - built exactly the way the watcher builds them, from ONE
        stamp."""
        stamp = datetime.datetime.strptime(
            start, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d-%H%M%S")
        name = "%s-%s-%s" % (stamp, suffix, brief)
        self.log(lane, ["[%s] [%s] START %s" % (start, lane, brief),
                        "[%s] [%s] DONE  %s -> %s" % (done, lane, brief,
                                                      suffix)]
                 + (["[%s] [%s] MOVED %s -> %s" % (done, lane, brief, name)]
                    if moved else []))
        if out is not None:
            # `newline=""` so a line feed stays ONE byte. Text mode on
            # Windows would translate it to a carriage-return pair and the
            # fixture's refusal would be 716 bytes where the estate's eight
            # are 713 - and that byte count is the signature a person
            # recognises this by, so the fixture reproduces it exactly.
            with open(os.path.join(self.root, "logs",
                                   "task-%s-%s.out" % (lane, stamp)), "w",
                      encoding="utf-8", newline="") as handle:
                handle.write(out)
        with open(os.path.join(self.root, "queue", lane, "DONE", name), "w",
                  encoding="utf-8") as handle:
            handle.write("# %s\n" % brief)
        return name

    def queued(self, lane, *briefs):
        for brief in briefs:
            with open(os.path.join(self.root, "queue", lane, brief), "w",
                      encoding="utf-8") as handle:
                handle.write("# %s\n" % brief)

    def plant_done(self, lane, name, body="# planted\n"):
        """A file in `DONE\\` with no watcher line behind it. C1's plant."""
        path = os.path.join(self.root, "queue", lane, "DONE", name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path


class EmptyProbe:
    """No process table at all, so liveness is UNKNOWN everywhere and the
    fixture's figures do not move with whatever is running on the machine
    this test is on."""

    def table(self):
        return None

    def cpu(self, pid):
        return None


class TheProvenanceOfEveryFigure(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="lane-provenance-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.estate = FixtureEstate(self.dir)
        self.previous = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = self.dir
        self.addCleanup(self._restore)
        self.now = datetime.datetime(2026, 10, 16, 2, 0, 0)

    def _restore(self):
        if self.previous is None:
            os.environ.pop(lanes.OPS_DIR, None)
        else:
            os.environ[lanes.OPS_DIR] = self.previous

    def board(self):
        """The board as the route builds it, on the fixture, with its own
        sample store so one test's CPU reading cannot reach another's."""
        return api.lane_board(now=self.now, probe=EmptyProbe(), samples={})

    # -- the estate the controls are run against ---------------------------

    def three_tasks(self):
        """One refusal, one real failure, one completion. The smallest estate
        in which all three of `exit1`'s meanings can be told apart."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        self.estate.task(lane, "0010-refused.md", "2026-10-16 00:10:00",
                         "2026-10-16 01:09:00", "exit1", out=REFUSAL_OUT)
        self.estate.task(lane, "0020-failed.md", "2026-10-16 01:10:00",
                         "2026-10-16 01:20:00", "exit1", out=FAILED_OUT)
        self.estate.task(lane, "0030-done.md", "2026-10-16 01:21:00",
                         "2026-10-16 01:30:00", "exit0", out="all good\n")
        self.estate.queued(lane, "0040-next.md", "0050-after.md")
        return lane

    # ------------------------------------------------------------------ C1
    #
    # A planted `DONE\` file moves nothing it should not.

    def test_c1_a_planted_done_file_moves_no_figure(self):
        """C1. Every figure the registry attributes to the log, the queue, a
        `.out` or the process table is byte-identical before and after a
        `DONE\\` file with no watcher line is planted beside the real ones."""
        lane = self.three_tasks()
        before = self.board()
        self.estate.plant_done(
            lane, "20261016-021500-exit1-0999-never-existed.md")
        after = self.board()

        # TWO EXCLUSIONS, BOTH NAMED, AND BOTH ASSERTED ELSEWHERE. The audit
        # block is REQUIRED to move - that is the next test - and excluding
        # it without checking it would be excluding the only reader, which is
        # how a control ends up passing because nothing reads anything. The
        # provenance table describes the payload, so its own figure count
        # legitimately follows it.
        def kept(payload):
            return {path: value
                    for path, value in _leaves(payload, "lane_board").items()
                    if not path.startswith("lane_board.done_folders")
                    and not path.startswith("lane_board.provenance")}

        first, second = kept(before), kept(after)
        self.assertTrue(first, "the comparison read no figures at all, so it "
                               "could not have detected one moving")
        moved = sorted(path for path in set(first) | set(second)
                       if first.get(path, _ABSENT)
                       != second.get(path, _ABSENT))
        self.assertEqual(
            [], moved,
            "a file planted in DONE\\ with no watcher line moved %d figure(s) "
            "that are supposed to descend from the log, the queue, a .out or "
            "the process table: %s" % (len(moved), moved[:20]))

    def test_c1_can_fail_a_counter_that_reads_the_done_listing_moves(self):
        """C1 CAN FAIL. The same plant, against a counter that DOES read the
        folder - which is what C1 would look like if a figure regressed."""
        lane = self.three_tasks()
        done_dir = os.path.join(self.dir, "queue", lane, "DONE")
        before = len(os.listdir(done_dir))
        self.estate.plant_done(
            lane, "20261016-021500-exit1-0999-never-existed.md")
        after = len(os.listdir(done_dir))
        self.assertEqual(before + 1, after,
                         "the plant did not land, so C1 proved nothing")
        self.assertNotEqual(
            before, after,
            "a count of the DONE folder did NOT move when a false entry was "
            "planted, which would mean this control cannot detect the thing "
            "it exists to detect")

    def test_the_audit_block_does_see_the_planted_file(self):
        """The other half of C1. The one block that lists the folder must
        move, or the estate's 21 untraceable entries are invisible and C1 is
        passing because nothing reads anything."""
        lane = self.three_tasks()
        before = self.board()["done_folders"]
        self.estate.plant_done(
            lane, "20261016-021500-exit1-0999-never-existed.md")
        after = self.board()["done_folders"]
        self.assertEqual(before["files"] + 1, after["files"])
        self.assertEqual(before["untraceable"] + 1, after["untraceable"])
        self.assertEqual(
            before["counts"][lp.R_HAND_UNDECLARED] + 1,
            after["counts"][lp.R_HAND_UNDECLARED],
            "a watcher-shaped name with no log line behind it is the "
            "dangerous shape and must be counted as the undeclared hand "
            "close it is")
        self.assertEqual(before["counts"][lp.R_LOGGED],
                         after["counts"][lp.R_LOGGED],
                         "planting a file must not change how many entries "
                         "trace to a watcher line")

    # ----------------------------------------------------------------- C1b
    #
    # The one way the `DONE\` path CAN lie, proven rather than asserted.

    def test_c1b_a_file_planted_at_the_derived_name_is_believed(self):
        """C1b. `consumed` is the only figure that touches `DONE\\`, by a
        path BUILT from the watcher's own stamp - so a file planted at
        exactly that name reads PRESENT. Proven here because the provenance
        table claims this limit in prose, and a claimed limit nobody
        exercised is the kind this repository keeps finding."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        # `moved=False` and then the DONE entry removed, so the row's
        # `consumed` starts ABSENT with the watcher's own stamp still known
        # from its START.
        name = self.estate.task(lane, "0010-refused.md",
                                "2026-10-16 01:00:00",
                                "2026-10-16 01:05:00", "exit1",
                                out=REFUSAL_OUT)
        os.remove(os.path.join(self.dir, "queue", lane, "DONE", name))
        row = self.board()["refusals"][0]
        self.assertEqual(lanes.ABSENT, row["consumed"]["state"])

        self.estate.plant_done(lane, name, body="not the brief at all\n")
        row = self.board()["refusals"][0]
        self.assertEqual(
            lanes.PRESENT, row["consumed"]["state"],
            "the one DONE\\ read on these pages is an existence test on a "
            "derived name, so a file planted at that name IS believed. If "
            "this assertion ever fails the limit has been closed and the "
            "provenance table's prose has to be corrected")
        self.assertEqual(
            lp.SOURCES[lp.S_DONE_PATH]["authority"], lp.REFUSED_BY_LIST,
            "a source that can be made to lie by planting one file must not "
            "be described as being on the authority list")

    # ------------------------------------------------------------------ C2
    #
    # The refusal classifier catches a refusal.

    def test_c2_the_429_classifies_as_refused(self):
        """C2. The plant the brief names: a `DONE ... -> exit1` whose `.out`
        is the 713-byte 429."""
        lane = self.three_tasks()
        rows = {r["brief"]: r for r in
                self.board()["lanes"][0]["closed_failures"]}
        self.assertEqual(lanes.O_REFUSED, rows["0010-refused.md"]["outcome"])
        self.assertEqual("429", rows["0010-refused.md"]["status_code"])
        self.assertEqual(len(REFUSAL_OUT.encode("utf-8")),
                         rows["0010-refused.md"]["out_bytes"])
        self.assertEqual(1, self.board()["refused_total"])

    def test_c2_can_fail_classifying_on_the_exit_code_alone(self):
        """C2 CAN FAIL. The brief's own mutation: classify on the exit code
        and C2 must go red. `exit1` is the word for BOTH, so a code-only
        classifier calls the real failure a refusal too."""
        self.three_tasks()
        rows = self.board()["lanes"][0]["closed_failures"]
        by_code = [r for r in rows if r["suffix"] == "exit1"]
        self.assertEqual(
            2, len(by_code),
            "the fixture must hold two exit1 rows for this mutation to mean "
            "anything - one refused and one genuinely failed")
        self.assertEqual(
            {lanes.O_REFUSED, lanes.O_FAILED},
            {r["outcome"] for r in by_code},
            "two rows carrying the SAME suffix came out with the same "
            "outcome, so a classifier reading only the suffix would agree "
            "with this one and C2 would pass while proving nothing")

    # ------------------------------------------------------------------ C3
    #
    # A real failure is still a failure.

    def test_c3_a_real_traceback_classifies_as_failed(self):
        """C3. Without this the classifier may launder every failure in the
        estate into REFUSED, which is the comfortable answer and therefore
        the dangerous one."""
        self.three_tasks()
        rows = {r["brief"]: r for r in
                self.board()["lanes"][0]["closed_failures"]}
        self.assertEqual(lanes.O_FAILED, rows["0020-failed.md"]["outcome"])
        self.assertIsNone(rows["0020-failed.md"]["refusal_line"])
        self.assertEqual(
            1, self.board()["refused_total"],
            "a real failure was counted as a refusal, which is the whole "
            "failure mode C3 exists for")

    def test_c3_can_fail_when_a_refusal_line_sits_on_top_of_output(self):
        """C3 CAN FAIL. A refusal line WITH other output below it is an
        ordinary failure, and this is the shape that separates the two
        readings: the task ran, then was refused."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        self.estate.task(lane, "0010-both.md", "2026-10-16 01:00:00",
                         "2026-10-16 01:05:00", "exit1",
                         out=REFUSAL_OUT + "and then I committed abc1234\n")
        row = self.board()["lanes"][0]["closed_failures"][0]
        self.assertEqual(
            lanes.O_FAILED, row["outcome"],
            "a refusal line with real output below it must read FAILED. If "
            "it reads REFUSED the classifier is matching the line and not "
            "the whole output, and every failure that happens to mention a "
            "429 becomes a refusal")
        self.assertIsNotNone(
            row["refusal_line"],
            "the refusal line is still shown - the stricter reading must not "
            "hide the evidence it declined to act on")
        self.assertTrue(row["refusal_line_but_also_output"])

    # ------------------------------------------------------------------ C4
    #
    # The hand-close rule cannot swallow a logged task.

    def test_c4_a_logged_entry_is_never_hand_closed(self):
        """C4. Every entry the watcher wrote classifies LOGGED, including the
        two shapes that look hand-made: a suffix the watcher does write
        (`NOWORK`, `TIMEOUT`) and a DONE with no MOVED line behind it."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        self.estate.task(lane, "0010-plain.md", "2026-10-16 00:10:00",
                         "2026-10-16 00:20:00", "exit0", out="fine\n")
        self.estate.task(lane, "0020-nowork.md", "2026-10-16 00:21:00",
                         "2026-10-16 00:30:00", "NOWORK", out="a plan\n")
        self.estate.task(lane, "0030-timeout.md", "2026-10-16 00:31:00",
                         "2026-10-16 00:40:00", "TIMEOUT", out="killed\n")
        # No MOVED line: `glm-b` wrote none at all on 2026-10-16 and its
        # entries are still in DONE\, so the stamp has to come from the
        # paired START or every one of that lane's files reads hand-made.
        self.estate.task(lane, "0040-nomoved.md", "2026-10-16 00:41:00",
                         "2026-10-16 00:50:00", "exit1", out="broke\n",
                         moved=False)
        found = self.board()["done_folders"]
        self.assertEqual(4, found["counts"][lp.R_LOGGED])
        self.assertEqual(0, found["untraceable"],
                         "a watcher-written entry was classified as "
                         "untraceable: %s"
                         % [r for lane_row in found["lanes"]
                            for r in lane_row["rows"]
                            if r["rule"] != lp.R_LOGGED])
        self.assertEqual(0, found["counts"][lp.R_HAND_DECLARED])
        self.assertEqual(0, found["counts"][lp.R_HAND_UNDECLARED])

    def test_c4_can_fail_a_declared_hand_close_is_still_caught(self):
        """C4 CAN FAIL. The hand-close rule must still FIRE on a real hand
        close - a rule that classified everything LOGGED would pass C4 and
        be useless, which is C4's own version of the laundering C3 guards."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        self.estate.task(lane, "0010-plain.md", "2026-10-16 00:10:00",
                         "2026-10-16 00:20:00", "exit0", out="fine\n")
        self.estate.plant_done(lane,
                               "20261016-0045-HANDCLOSED-0020-by-a-person.md")
        found = self.board()["done_folders"]
        self.assertEqual(1, found["counts"][lp.R_LOGGED])
        self.assertEqual(
            1, found["counts"][lp.R_HAND_DECLARED],
            "a file whose name says HANDCLOSED and whose brief no log line "
            "names must be classified as a hand close. If it reads LOGGED "
            "the rule is inert and C4 above passes for the wrong reason")

    def test_a_hand_label_on_a_logged_brief_does_not_become_a_hand_close(self):
        """The inverse of C4, and the reason the declared rule asks the log
        BEFORE it believes the label. A person who writes `HANDCLOSED` into
        the name of a task the watcher really did run must not thereby erase
        the watcher's record of it."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        self.estate.task(lane, "0010-plain.md", "2026-10-16 00:10:00",
                         "2026-10-16 00:20:00", "exit0", out="fine\n")
        self.estate.plant_done(
            lane, "20261016-001000-HANDCLOSED-0010-plain.md")
        found = self.board()["done_folders"]
        self.assertEqual(
            0, found["counts"][lp.R_HAND_DECLARED],
            "the log names 0010-plain.md, so a second file claiming a hand "
            "close on it is a logged task wearing a hand label - not a brief "
            "nobody has a record of")
        self.assertEqual(1, found["counts"][lp.R_SELF_WRITTEN],
                         "it is a second entry for a task the log DOES name, "
                         "which is the duplicate-entry shape")

    # ------------------------------------- every rule, including the zeros

    def test_every_rule_is_reported_even_when_it_matches_nothing(self):
        """A rule that matched nothing may be a clean estate or a broken
        pattern, and a dropped row cannot tell a reader which."""
        self.three_tasks()
        found = self.board()["done_folders"]
        self.assertEqual(sorted(lp.RULE_ORDER), sorted(found["counts"]),
                         "a rule is missing from the counts")
        self.assertEqual([r["rule"] for r in found["rules"]],
                         list(lp.RULE_ORDER),
                         "the rules must be published in order, each with "
                         "its own sentence, whatever it matched")
        zero = [r for r in lp.RULE_ORDER if found["counts"][r] == 0]
        self.assertTrue(zero, "this fixture must leave at least one rule at "
                              "zero for this test to be about anything")
        for rule in zero:
            self.assertIn(rule, found["counts"])
            self.assertTrue(
                any(r["rule"] == rule and r["why"] for r in found["rules"]),
                "rule %s matched nothing and was not published with its "
                "reason, so a reader cannot tell a clean estate from a "
                "broken pattern" % rule)

    def test_the_rule_counts_sum_to_the_files_on_disk(self):
        """One rule per file, first match wins. If the counts do not add up
        a file is being classified twice or not at all, and either way the
        untraceable total is wrong."""
        lane = self.three_tasks()
        self.estate.plant_done(lane, "0999-no-stamp-at-all.md")
        self.estate.plant_done(lane,
                               "20261016-0045-HANDCLOSED-0998-by-hand.md")
        self.estate.plant_done(lane, "20261016-021500-exit1-0997-shaped.md")
        found = self.board()["done_folders"]
        on_disk = len(os.listdir(os.path.join(self.dir, "queue", lane,
                                              "DONE")))
        self.assertEqual(
            on_disk,
            sum(found["counts"][r] for r in lp.RULE_ORDER
                if r != lp.R_LOGGED_NO_FILE),
            "the per-file rules must partition the folder exactly")
        self.assertEqual(1, found["counts"][lp.R_UNSHAPED])
        self.assertEqual(1, found["counts"][lp.R_HAND_DECLARED])
        self.assertEqual(1, found["counts"][lp.R_HAND_UNDECLARED])

    def test_a_logged_done_with_no_file_is_the_direction_a_count_cannot_see(self):
        """The reverse rule. A `DONE` line whose entry is not in the folder is
        work the authority recorded and the folder does not hold - and a
        count of the folder can never produce it."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        name = self.estate.task(lane, "0010-plain.md", "2026-10-16 00:10:00",
                                "2026-10-16 00:20:00", "exit0", out="fine\n")
        self.assertEqual(0, self.board()["done_folders"]
                         ["counts"][lp.R_LOGGED_NO_FILE])
        os.remove(os.path.join(self.dir, "queue", lane, "DONE", name))
        found = self.board()["done_folders"]
        self.assertEqual(1, found["counts"][lp.R_LOGGED_NO_FILE])
        self.assertEqual(0, found["counts"][lp.R_LOGGED])
        self.assertEqual(
            0, found["untraceable"],
            "a logged DONE with no file is not an untraceable FILE - there "
            "is no file. Counting it there would double-count the problem")

    def test_an_unreadable_done_folder_is_unknown_and_never_zero(self):
        """An unreadable directory holds no information about how many files
        are in it, and 0 reads as a clean lane."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        done = os.path.join(self.dir, "queue", lane, "DONE")
        os.rmdir(done)
        with open(done, "w", encoding="utf-8") as handle:
            handle.write("not a directory")
        found = self.board()["done_folders"]
        self.assertIsNone(found["lanes"][0]["files"])
        self.assertIsNone(found["files"],
                          "a total over the lanes that could be read is not "
                          "the total and must not be printed as one")
        self.assertEqual([lane], found["unreadable_lanes"])

    # ------------------------------------------- the never-ran claim itself

    def test_the_glossary_no_longer_claims_a_refusal_never_ran(self):
        """The one figure on these pages that was measurably false. It
        asserted 'so this task NEVER RAN' on every refusal, and three of the
        eight of 2026-10-16 ran for 24.4, 59.1 and 59.3 minutes."""
        _label, implies = lanes.OUTCOME_TEXT[lanes.O_REFUSED]
        self.assertNotIn("NEVER RAN", implies)
        self.assertIn("elapsed_seconds", implies,
                      "the glossary must name the figure that answers the "
                      "question it stopped answering, or the claim is simply "
                      "gone rather than corrected")

    def test_a_refusal_after_an_hour_cannot_be_called_never_ran(self):
        """The measurement that refutes it, on a row whose session was alive
        for 59 minutes before its 429 arrived."""
        self.three_tasks()
        row = self.board()["refusals"][0]
        self.assertEqual(59 * 60, row["elapsed_seconds"])
        self.assertIs(
            False, row["never_ran_supportable"],
            "a session alive for 59 minutes is not one that never ran, and "
            "the board must not say it was")
        self.assertEqual(0, self.board()["refused_never_ran"])
        self.assertEqual(1, self.board()["refused_ran_unknown"])
        self.assertEqual(59 * 60,
                         self.board()["refused_unaccounted_seconds"])

    def test_a_refusal_inside_the_inter_task_sleep_may_still_be_called_that(self):
        """The other side, so the field is not a constant False dressed as a
        measurement. A refusal whose whole interval fits inside the watcher's
        5s inter-task sleep IS provably instantaneous."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        self.estate.task(lane, "0010-instant.md", "2026-10-16 01:00:00",
                         "2026-10-16 01:00:03", "exit1", out=REFUSAL_OUT)
        row = self.board()["refusals"][0]
        self.assertEqual(3, row["elapsed_seconds"])
        self.assertIs(True, row["never_ran_supportable"])
        self.assertEqual(1, self.board()["refused_never_ran"])
        self.assertEqual(0, self.board()["refused_ran_unknown"])

    def test_an_unmeasurable_interval_is_unknown_and_not_never_ran(self):
        """None is NOT True. A refusal whose START line is missing has no
        interval, and an unmeasured interval must not license the stronger
        claim - the shape `glm-b` was in with no MOVED lines at all."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        # A DONE with no START above it at all.
        self.estate.log(lane, ["[2026-10-16 01:00:05] [alpha] DONE  "
                               "0010-orphan.md -> exit1"])
        with open(os.path.join(self.dir, "queue", lane, "DONE",
                               "20261016-010000-exit1-0010-orphan.md"), "w",
                  encoding="utf-8") as handle:
            handle.write("# orphan\n")
        rows = self.board()["lanes"][0]["closed_failures"]
        self.assertEqual(1, len(rows))
        self.assertIsNone(rows[0]["elapsed_seconds"])
        self.assertIsNone(
            rows[0]["never_ran_supportable"],
            "an interval that could not be measured must be UNKNOWN. False "
            "would be a claim and True would be the old defect")
        self.assertEqual(0, self.board()["refused_never_ran"],
                         "UNKNOWN never becomes 'it never ran'")

    def test_the_three_never_ran_buckets_account_for_every_refusal(self):
        """Exhaustive and disjoint. A refusal that fell out of the split
        would make the page's three numbers quietly fail to add up to the
        total beside them."""
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        self.estate.task(lane, "0010-instant.md", "2026-10-16 01:00:00",
                         "2026-10-16 01:00:03", "exit1", out=REFUSAL_OUT)
        self.estate.task(lane, "0020-long.md", "2026-10-16 01:01:00",
                         "2026-10-16 01:40:00", "exit1", out=REFUSAL_OUT)
        board = self.board()
        self.assertEqual(2, board["refused_total"])
        self.assertEqual(
            board["refused_total"],
            board["refused_never_ran"] + board["refused_ran_unknown"]
            + board["refused_elapsed_unknown"])
        self.assertEqual(3 + 39 * 60, board["refused_unaccounted_seconds"])
        self.assertEqual(39 * 60, board["refused_longest_seconds"])

    def test_an_unmeasurable_interval_makes_the_total_unknown_not_partial(self):
        """A total over the rows that could be read is not the total.

        One measurable refusal, then a second whose START line does not
        exist. The total must go from a number to None - NOT stay at the
        first row's value, which is the shape that reads as "that is all of
        it" and is the hand-kept denominator in miniature.
        """
        lane = self.estate.lane("alpha")
        self.estate.up(lane, "2026-10-16 00:00:00")
        self.estate.task(lane, "0010-long.md", "2026-10-16 01:00:00",
                         "2026-10-16 01:40:00", "exit1", out=REFUSAL_OUT)
        self.assertEqual(40 * 60,
                         self.board()["refused_unaccounted_seconds"])
        # A DONE with no START above it, and its `.out` stamped from the
        # MOVED line so the refusal is still classified.
        self.estate.log(lane, ["[2026-10-16 01:50:05] [alpha] DONE  "
                               "0020-orphan.md -> exit1",
                               "[2026-10-16 01:50:05] [alpha] MOVED "
                               "0020-orphan.md -> "
                               "20261016-014500-exit1-0020-orphan.md"])
        with open(os.path.join(self.dir, "logs",
                               "task-alpha-20261016-014500.out"), "w",
                  encoding="utf-8", newline="") as handle:
            handle.write(REFUSAL_OUT)
        board = self.board()
        self.assertEqual(2, board["refused_total"],
                         "the second refusal must be classified, or this "
                         "test is about one row and proves nothing")
        self.assertEqual(1, board["refused_elapsed_unknown"])
        self.assertIsNone(
            board["refused_unaccounted_seconds"],
            "one unmeasurable interval makes the TOTAL unknown. Leaving it "
            "at the measurable rows' sum would print a partial total as the "
            "whole one")
        self.assertEqual(
            40 * 60, board["refused_longest_seconds"],
            "the longest measured interval is still a fact and is still "
            "reported - 'the total is unknown' does not make every figure "
            "beside it unknown too")

    # ----------------------------------------------- the provenance table

    def test_every_figure_on_every_page_has_a_source(self):
        """THE COMPLETENESS GATE. Run against the LIVE payloads, so a figure
        added to any of the three pages with no row in the registry fails
        here rather than rendering unsourced."""
        self.three_tasks()
        for name, blob in (("lane board", self.board()),
                           ("criteria page", api.exit_criteria(now=self.now)),
                           ("breach ledger",
                            api.floor_ledger(now=self.now,
                                             probe=EmptyProbe(), samples={},
                                             write=False))):
            found = blob["provenance"]
            self.assertEqual(
                [], [r["path"] for r in found["rows"]
                     if r["state"] == "unknown"],
                "%s renders figure(s) with no provenance row. Add one to "
                "src/laneprovenance.py - they are rendering UNKNOWN until "
                "somebody does, which is correct and is not a resting state"
                % name)
            self.assertEqual(found["paths"], found["covered"])
            self.assertEqual(0, found["uncovered"])

    def test_an_unregistered_figure_renders_unknown_and_is_named(self):
        """The gate above can only be trusted if an unsourced figure really
        does come out UNKNOWN. Proven by asking the table about a path no
        pattern covers, rather than by trusting the registry to be complete.
        """
        found = lp.table({"lane_board.a_figure_nobody_registered"})
        self.assertEqual(1, found["uncovered"])
        row = found["rows"][0]
        self.assertEqual("unknown", row["state"])
        self.assertIsNone(row["source"])
        self.assertIsNone(row["authority"])
        self.assertIsNone(
            row["can_be_false"],
            "an unsourced figure must not report `can_be_false` False - that "
            "is a reassurance about a file nobody has identified")
        self.assertIn("PROVENANCE UNKNOWN", row["can_be_false_why"])

    def test_no_figure_about_the_work_reads_a_done_folder_listing(self):
        """THE RESULT OF THIS TASK, as one assertion.

        `work_figures` is the figure count minus the one block that lists a
        `DONE\\` folder on purpose in order to audit it. Zero here means no
        task count, throughput, timestamp or success rate on any of the three
        pages descends from a filename in that folder."""
        self.three_tasks()
        pages_seen = 0
        for blob in (self.board(), api.exit_criteria(now=self.now),
                     api.floor_ledger(now=self.now, probe=EmptyProbe(),
                                      samples={}, write=False)):
            rows = {r["source"]: r for r in blob["provenance"]["sources"]}
            self.assertIn(lp.S_DONE_LISTING, rows,
                          "the DONE-listing row must be PRESENT and say "
                          "zero. An absent row cannot be told from a broken "
                          "pattern")
            self.assertEqual(
                0, rows[lp.S_DONE_LISTING]["work_figures"],
                "a figure about the WORK now reads a DONE folder listing: "
                "%s" % rows[lp.S_DONE_LISTING]["patterns"])
            pages_seen += 1
        self.assertEqual(3, pages_seen)

    def test_the_audit_block_is_the_only_thing_excluded_from_that_claim(self):
        """The exclusion is what makes the claim above survivable, so it is
        bounded: exactly one pattern, and it is the audit block's."""
        self.assertEqual(("lane_board.done_folders.*",), lp.ABOUT_THE_FOLDER)
        self.three_tasks()
        rows = {r["source"]: r
                for r in self.board()["provenance"]["sources"]}
        self.assertEqual(
            1, rows[lp.S_DONE_LISTING]["figures"],
            "the DONE listing is read by exactly one block. A second reader "
            "is a figure that has to be looked at before this claim stands")

    def test_a_source_that_matched_nothing_is_a_row_saying_zero(self):
        """A source matching nothing may be a refusal working or a pattern
        broken. Both are reported; neither is dropped."""
        self.three_tasks()
        rows = {r["source"]: r
                for r in self.board()["provenance"]["sources"]}
        self.assertEqual(sorted(lp.SOURCES), sorted(rows),
                         "every source must have a row on every page")
        for key in (lp.S_OUT_MTIME, lp.S_LANE_FILE_MTIME):
            self.assertEqual(
                0, rows[key]["figures"],
                "%s is on the board's own refused list and must read zero "
                "figures. If it does not, something started reading it" % key)
            self.assertTrue(rows[key]["why"])

    def test_the_sources_section_three_refuses_are_marked_as_such(self):
        """A source `CONTINUITY.md` section 3 names as NOT the authority must
        not be presented as being on the list - and must carry the reason it
        is read at all."""
        for key in (lp.S_DONE_LISTING, lp.S_DONE_PATH, lp.S_OUT_BYTES,
                    lp.S_QUEUE_LISTING, lp.S_LANE_FILE_MTIME):
            source = lp.SOURCES[key]
            self.assertEqual(lp.REFUSED_BY_LIST, source["authority"], key)
            self.assertTrue(source["quote"],
                            "%s is refused by section 3 and must quote the "
                            "sentence that refuses it" % key)
            self.assertTrue(source["why"])

    def test_a_source_claiming_it_cannot_be_false_must_say_why(self):
        """Only one source does, and it is the only one whose failure mode is
        absence rather than falsehood. A second one appearing here without
        that property is the thing to catch."""
        honest = [key for key, source in lp.SOURCES.items()
                  if not source["can_be_false"]]
        self.assertEqual([lp.S_CPU_DELTA], honest)
        self.assertIn("ABSENCE", lp.SOURCES[lp.S_CPU_DELTA]["why"])

    def test_the_longest_pattern_wins_so_registry_order_is_not_load_bearing(self):
        """A leaf and the subtree containing it both match. The leaf's own
        row is the one with something to say, and a subtree row written above
        its leaves must not swallow them."""
        found = lp.figure_for(
            "lane_board.lanes[].closed_failures[].elapsed_seconds")
        self.assertEqual(
            "lane_board.lanes[].closed_failures[].elapsed_seconds",
            found["pattern"])
        self.assertEqual(lp.S_DERIVED, found["source"])
        # And the subtree still covers a sibling nobody wrote a row for.
        self.assertEqual("lane_board.lanes[].owed.*",
                         lp.figure_for("lane_board.lanes[].owed.heading")
                         ["pattern"])

    def test_a_pattern_dot_is_literal_and_cannot_match_a_sibling(self):
        """`re.escape` before the glob, or `lane_board.floor` would cover
        `lane_board.floorX` and a trailing `.*` would reach a sibling key."""
        self.assertIsNone(lp.figure_for("lane_boardXfloor"))
        self.assertIsNone(lp.figure_for("lane_board.lanes[].owedXheading"))
        self.assertIsNotNone(lp.figure_for("lane_board.lanes[].owed.state"))

    def test_a_subtree_pattern_covers_its_own_node_and_not_a_prefix_sibling(self):
        """`x.*` must match `x` itself - the list node as well as its leaves -
        and must not match `xy`."""
        self.assertIsNotNone(lp.figure_for("lane_board.lanes[].owed"))
        self.assertIsNone(lp.figure_for("lane_board.lanes[].owedly"))

    def test_the_merge_column_names_what_exit1_is_adding_together(self):
        """The brief's question 3 as a field: for each figure, which of
        `exit1`'s three meanings is it merging."""
        self.three_tasks()
        rows = {r["path"]: r for r in self.board()["provenance"]["rows"]}
        self.assertEqual(
            lp.M_RAN_AND_REFUSED,
            rows["lane_board.lanes[].median_task_minutes"]["merges"],
            "the median is taken over every paired START..DONE, so a refusal "
            "is in it")
        self.assertEqual(
            lp.M_REFUSAL_SUBSTATES,
            rows["lane_board.refused_total"]["merges"])
        self.assertEqual(
            lp.M_HANDCLOSED_INVISIBLE,
            rows["lane_board.lanes[].queue_depth"]["merges"],
            "a hand-closed brief has left the queue with no record anywhere "
            "this page reads, so the depth is short by that many")
        for row in rows.values():
            self.assertIn(row["merges"], lp.MERGE_TEXT)
            self.assertTrue(row["merges_why"])

    def test_the_refusal_panel_renders_the_elapsed_column(self):
        """The column that refutes the claim the panel used to make. Asserted
        on the rendered page, not on the data - a figure computed correctly
        that nothing renders is this repository's named defect."""
        from src.web import pages
        self.three_tasks()
        html = pages.lane_board(self.board())
        self.assertIn("How long the session was alive, unrecorded", html)
        self.assertIn("UNRECORDED", html)
        self.assertNotIn("None of them ran", html)
        self.assertIn("Who wrote the names in DONE", html)
        self.assertIn("Where every number on this page comes from", html)

    def test_the_page_names_an_unsourced_figure_rather_than_hiding_it(self):
        """A figure rendering UNKNOWN has to be NAMED on the page, or a
        reader cannot tell a complete table from a quiet one."""
        from src.web import pages
        self.three_tasks()
        board = self.board()
        board["provenance"] = lp.table(
            lp.paths_of(board, "lane_board")
            | {"lane_board.a_figure_nobody_registered"})
        html = pages.lane_board(board)
        self.assertIn("a_figure_nobody_registered", html)
        self.assertIn("have no row in", html)

    def test_the_board_is_unconfigured_rather_than_empty_without_the_variable(self):
        """UNCONFIGURED is not 'there are no lanes', and the reconciliation
        must not report a clean folder set when it opened none."""
        os.environ.pop(lanes.OPS_DIR, None)
        found = lp.reconcile(None)
        self.assertEqual(lanes.UNCONFIGURED, found["state"])
        self.assertIsNone(found["files"])
        self.assertIsNone(found["untraceable"],
                          "0 untraceable entries over 0 folders opened is a "
                          "clean verdict on nothing")
        self.assertEqual([r["rule"] for r in found["rules"]],
                         list(lp.RULE_ORDER),
                         "the rules are published even when no folder was "
                         "read")


def _leaves(blob, prefix):
    """`{path: repr(value)}` for every leaf, list indices INCLUDED.

    Indices are kept rather than collapsed to `[]`, so a row appearing,
    disappearing or changing order counts as a figure moving. The values are
    `repr` strings so two payloads can be diffed by path and the failure
    names the figure instead of printing both payloads.
    """
    found = {}

    def walk(node, path):
        if isinstance(node, dict):
            for key in sorted(node):
                walk(node[key], "%s.%s" % (path, key))
        elif isinstance(node, (list, tuple)):
            found[path + ".__len__"] = len(node)
            for index, item in enumerate(node):
                walk(item, "%s[%d]" % (path, index))
        else:
            found[path] = repr(node)

    walk(blob, prefix)
    return found
