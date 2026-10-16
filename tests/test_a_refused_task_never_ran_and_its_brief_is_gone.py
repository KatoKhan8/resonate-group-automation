"""The verdict the watcher did not have, and the nine briefs that cost.

WHAT THIS FILE IS FOR. Between 01:41 and 01:48 on 2026-10-16 the `glm`,
`glm-b` and `glm-c` watchers consumed eight briefs in seven minutes and not
one of those tasks ran. Every one was a provider refusal - a rolling
five-hour usage limit - and the watcher has exactly two words for an ended
task, finished and failed. It met a third thing, NEVER STARTED, and wrote the
one it had:

    [2026-10-16 01:41:36] [glm]   DONE  0067b-save-sweep.md -> exit1

A failure consumes the brief. The record now says work was attempted and the
work is no longer in the queue. Two of the eight, `glm/0072` and
`glm-c/0230`, are on the canary critical path and exist today only because a
person copied them back out of the DONE folder by hand at 01:49.

THE INVARIANT UNDER TEST, and it is not the text of any docstring:

    a closed task's outcome is read from THAT TASK'S OWN OUTPUT and from
    nothing else - not the exit code, not the byte count, not the lane, not
    the model, and not how many failures came before it;

    a REFUSED outcome names the brief and where its copy sits, because the
    repair is a person moving a file and a count would not tell them which
    file;

    the detector FAILS TOWARD ORDINARY FAILURE. One that fired on every
    exit1 would tell the operator to restore briefs that really did fail,
    which is worse than the label it replaces;

    and the three states stay apart: a refused task, a failing lane and a
    dead lane need three different things from a person.

WHERE THE FIXTURES COME FROM. Every byte of task output in this file was
copied out of `logs\\` on the operator's machine. The eight refusals share a
559-byte preamble exactly - measured - and differ only in the request id on
the error line, so the preamble is written once and each error line verbatim,
and `test_each_fixture_is_the_measured_713_bytes` proves the reconstruction.
The negative controls are two real reports from the same directory, one of
them 709 bytes: four bytes from the refusal size, same lane, same two harness
notices, and a task's own work instead of an error.

NOTHING HERE REACHES A PROVIDER, A NETWORK OR A REAL LANE. Every estate is a
directory written into a temporary folder and thrown away.
"""
import datetime
import hashlib
import os
import re
import shutil
import socket
import tempfile
import unittest

from src import lanes
from src.web import api, pages

#: A fixed local offset, so a conversion asserted here does not depend on the
#: machine the suite runs on. The real board MEASURES this from the machine at
#: the instant being converted, which is what keeps it right across a DST
#: change; a test that let it be measured would assert a different number in
#: January.
ZAGREB = 2.0

NOW = datetime.datetime(2026, 10, 16, 4, 0, 0)

# ---------------------------------------------------------------- the bytes
#
# Verbatim. The preamble is byte-identical across all eight refusals AND
# across both negative controls, which is the whole reason a size cannot
# decide anything: it is 559 bytes on its own, and 559 is the number
# `CONTINUITY.md` trap 6 gives for a refusal whose error line landed earlier.
# A person keying on 559 could be looking at a file with no error line at all.
PREAMBLE = (
    '"glm-5.3" is not a model this version of Claude Code recognizes, so '
    "auto-compact will keep this session within 200k tokens (the context "
    "window it assumes). If the model accepts more, append [1m] to the model "
    "name for 1M, or set CLAUDE_CODE_MAX_CONTEXT_TOKENS to its real window; "
    "to make it recognized, map it in the modelOverrides setting or update "
    "Claude Code; CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1 "
    "restores the previous wait-for-the-API behavior.\n"
    '[claude-code:unrecognized_model] {"model":"glm-5.3",'
    '"query_source":"generate_session_title"}\n')

#: The provider's error line. The request id is the part that differs between
#: the eight, and its first 14 characters are a timestamp on the PROVIDER'S
#: clock - the second clock the reset conversion is checked against.
ERROR = ("API Error: Request rejected (429) · [1308][Usage limit "
         "reached for 5 hour. Your limit will reset at "
         "2026-10-16 08:07:16][%s]\n")

#: The eight, keyed by the `.out` stamp the watcher gave each one. The request
#: ids are real: each was read out of the file named beside it.
THE_EIGHT = {
    # lane     stamp              request id                        brief
    ("glm", "20261016-004231"): ("20261016074136ea3a0e14ec6e4bf9",
                                 "0067b-save-sweep.md"),
    ("glm", "20261016-014141"): ("20261016074449ab70f419de93438a",
                                 "0072-the-two-prospect-facing-bypasses.md"),
    ("glm", "20261016-014455"): ("20261016074808d1f9efe9aa734eda",
                                 "0073-the-zero-that-means-unknown.md"),
    ("glm-b", "20261016-011843"): ("20261016074307910e2ee2c8404a93",
                                   "0180-the-vertical-slot.md"),
    ("glm-b", "20261016-014312"): ("20261016074622ca995769b369405e",
                                   "0190-finish-0170.md"),
    ("glm-c", "20261016-004232"): ("2026101607415068a92bc9b5c2450e",
                                   "0161-save-sweep.md"),
    ("glm-c", "20261016-014156"): ("20261016074500b101012cec9142b4",
                                   "0220-the-remaining-bypasses-tiered.md"),
    ("glm-c", "20261016-014506"): ("202610160748081fc51e56abba4bae",
                                   "0230-the-ledger-row-with-no-step.md"),
}

#: THE NEGATIVE CONTROL THAT MATTERS, and it is real:
#: `logs\task-glm-b-20261015-022317.out`, 709 bytes, four bytes from the
#: refusal size, the same lane, the same two harness notices - and the task's
#: own sentence instead of an error. A detector keyed on the size, the lane or
#: the preamble would call this a refusal and tell the operator to restore a
#: brief that really did fail.
NEAR_MISS = PREAMBLE + (
    "The baseline run is queued (behind pilotcaps and the suppression lane); "
    "I'll be re-invoked when it completes and will apply the validated edits "
    "then.\n")

#: A second real one, `logs\task-glm-b-20261015-015355.out`, 2943 bytes: a
#: full task report with a premise, a test, a mutation proof and a boundary.
#: Trimmed here to its first paragraphs, because what is under test is that a
#: task's own prose is not a refusal, and the trim is stated rather than
#: passed off as the whole file.
REAL_REPORT = PREAMBLE + (
    "TASK 0030 is closed. Summary:\n\n"
    "**Premise - verified, holds.** `expand_step` returns `None` for a "
    "`generated` step with no stored words; `build`'s None-handling "
    "synthesises a step when the spec carries `requires` and silently "
    "`continue`s when it does not.\n\n"
    "**Mutation proof** (all reverted, `git diff` empty after): flipped the "
    "deleted body to em1, then em5, then restored em3 - the failure message "
    "was byte-identical to the first run.\n")


def line(lane, clock, message, day="2026-10-16"):
    """One watcher record in the exact shape `lane_watcher.ps1` writes.

    Written here rather than imported, so a change to the watcher's format
    shows up as a failure in this file instead of as a board that quietly
    reads every lane UNKNOWN.
    """
    return "[%s %s] [%s] %s" % (day, clock, lane, message)


def refusal_out(request_id):
    return PREAMBLE + ERROR % request_id


class Estate:
    """A disposable lane estate, with task outputs in it."""

    def an_estate(self):
        root = tempfile.mkdtemp(prefix="rga-refusal-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        os.makedirs(os.path.join(root, "logs"))
        os.makedirs(os.path.join(root, "queue"))
        self.root = root
        return root

    def a_lane(self, name, log=(), pid=1, queued=(), inflight=(), done=(),
               outs=(), lane_file="## entry\n", no_queue_dir=False,
               unreadable_queue=False, unreadable_running=False):
        root = self.root
        if not no_queue_dir:
            queue = os.path.join(root, "queue", name)
            os.makedirs(os.path.join(queue, "RUNNING"), exist_ok=True)
            os.makedirs(os.path.join(queue, "DONE"), exist_ok=True)
            for brief in queued:
                self._write(os.path.join(queue, brief), "brief\n")
            for brief in inflight:
                self._write(os.path.join(queue, "RUNNING", brief), "brief\n")
            for brief in done:
                self._write(os.path.join(queue, "DONE", brief), "brief\n")
            if unreadable_running:
                shutil.rmtree(os.path.join(queue, "RUNNING"))
                self._write(os.path.join(queue, "RUNNING"), "not a dir\n")
            if unreadable_queue:
                shutil.rmtree(queue)
                self._write(queue, "not a dir\n")
        self._write(os.path.join(root, "logs", "watcher-%s.log" % name),
                    "\n".join(log) + ("\n" if log else ""))
        if pid is not None:
            self._write(os.path.join(root, "logs", "watcher-%s.pid" % name),
                        "%d\n" % pid)
        if lane_file is not None:
            self._write(os.path.join(root, "LANE-%s.md" % name), lane_file)
        for stamp, text in outs:
            path = os.path.join(root, "logs",
                                "task-%s-%s.out" % (name, stamp))
            if text is None:
                # A directory, which is the portable way to make a path that
                # exists and cannot be read.
                os.makedirs(path, exist_ok=True)
            else:
                self._write(path, text)

    @staticmethod
    def _write(path, text):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    #: pid 1 is the watcher; 2 and 3 are the `cmd.exe` wrapper and the task
    #: under it, which is the shape `lane_watcher.ps1` actually launches. The
    #: walk does not count its own root, so a table holding only the watcher
    #: reads STALLED - which is correct and is not what these fixtures mean.
    ALIVE = {1: (0, "powershell.exe"), 2: (1, "cmd.exe"), 3: (2, "claude.exe")}

    def board(self, now=NOW, probe=None, offset=ZAGREB):
        return lanes.board(root=self.root, now=now,
                           probe=probe or FakeProbe(self.ALIVE,
                                                    {1: 1.0, 2: 1.0, 3: 2.0}),
                           samples={}, local_offset_hours=offset)

    def row(self, lane, **kwargs):
        rows = {r["lane"]: r for r in self.board(**kwargs)["lanes"]}
        self.assertIn(lane, rows, "no row for %r" % lane)
        return rows[lane]

    def page(self, now=NOW, probe=None):
        previous = os.environ.get(lanes.OPS_DIR)
        os.environ[lanes.OPS_DIR] = self.root
        self.addCleanup(self._restore_ops, previous)
        data = api.lane_board(now=now, samples={},
                              probe=probe or FakeProbe(
                                  self.ALIVE, {1: 1.0, 2: 1.0, 3: 2.0}))
        return pages.lane_board(data), data

    @staticmethod
    def _restore_ops(previous):
        if previous is None:
            os.environ.pop(lanes.OPS_DIR, None)
        else:
            os.environ[lanes.OPS_DIR] = previous


class FakeProbe:
    def __init__(self, table=None, cpu=None, unreadable_table=False):
        self._table = None if unreadable_table else (table or {})
        self._cpu = cpu or {}

    def table(self):
        return self._table

    def cpu(self, pid):
        return self._cpu.get(pid)


def the_night_of_the_sixteenth(test):
    """The three GLM lanes exactly as their logs stand, refusals and all.

    One estate, built from the real records, used by every count assertion
    below so a per-lane figure and the estate total cannot be measured on two
    different fixtures.
    """
    test.an_estate()
    plan = {
        "glm": [("00:42:31", "01:41:36", "20261016-004231"),
                ("01:41:41", "01:44:50", "20261016-014141"),
                ("01:44:55", "01:48:09", "20261016-014455")],
        "glm-b": [("01:18:43", "01:43:07", "20261016-011843"),
                  ("01:43:12", "01:46:23", "20261016-014312")],
        "glm-c": [("00:42:32", "01:41:51", "20261016-004232"),
                  ("01:41:56", "01:45:01", "20261016-014156"),
                  ("01:45:06", "01:48:09", "20261016-014506")],
    }
    for lane, runs in plan.items():
        log = [line(lane, "00:30:00", "watcher up. tree=x mode=y timeout=90m")]
        outs, done, queued = [], [], []
        for started, ended, stamp in runs:
            request_id, brief = THE_EIGHT[(lane, stamp)]
            log.append(line(lane, started, "START " + brief))
            log.append(line(lane, ended, "DONE  %s -> exit1" % brief))
            # `glm-b` ran older watcher bytes on the night and logged no
            # MOVED line, so one lane here joins by its START stamp and two
            # by the watcher's own authority. Both paths are exercised by the
            # same fixture.
            if lane != "glm-b":
                log.append(line(lane, ended, "MOVED %s -> %s-exit1-%s"
                                % (brief, stamp, brief)))
            outs.append((stamp, refusal_out(request_id)))
            done.append("%s-exit1-%s" % (stamp, brief))
            # Restored by hand at 01:49, which is the state the directories
            # are actually in.
            queued.append(brief)
        log.append(line(lane, "01:48:09", "3 consecutive failures. Exiting "
                                          "rather than looping on a broken "
                                          "task."))
        log.append(line(lane, "01:48:09", "watcher down."))
        test.a_lane(lane, log=log, outs=outs, done=done, queued=queued)
    return test.board()


# --------------------------------------------------------------------------
# C1 - THE REAL EIGHT


class TheEightRefusalsOfTheSixteenth(unittest.TestCase, Estate):
    """Control 1. The eight that happened, classified from their own bytes."""

    def test_each_fixture_is_the_measured_713_bytes(self):
        """The reconstruction is faithful, or every assertion below is void.

        Each real `.out` was 713 bytes and this file writes the preamble once
        and each error line verbatim. If that reassembly were wrong the suite
        would be testing a fixture rather than the artifact.
        """
        self.assertEqual(len(PREAMBLE.encode("utf-8")), 559)
        for (lane, stamp), (request_id, _brief) in sorted(THE_EIGHT.items()):
            self.assertEqual(
                len(refusal_out(request_id).encode("utf-8")), 713,
                "%s %s does not reassemble to the measured size"
                % (lane, stamp))
        self.assertEqual(len(NEAR_MISS.encode("utf-8")), 709)

    def test_each_of_the_eight_is_REFUSED(self):
        data = the_night_of_the_sixteenth(self)
        seen = {}
        for row in data["lanes"]:
            for entry in row["refused"]:
                seen[(row["lane"], entry["brief"])] = entry
        self.assertEqual(len(seen), 8, sorted(seen))
        for entry in seen.values():
            self.assertEqual(entry["outcome"], lanes.O_REFUSED)
            self.assertEqual(entry["outcome_label"], "REFUSED")
            self.assertEqual(entry["status_code"], "429")
            self.assertIn("Request rejected", entry["refusal_line"])
            # The suffix the watcher wrote is kept verbatim beside the
            # outcome, because the misreport IS the suffix.
            self.assertEqual(entry["suffix"], "exit1")
            self.assertIn("-> exit1", entry["line"])

    def test_each_names_the_brief_it_consumed(self):
        """A count would not tell anybody which file to put back."""
        data = the_night_of_the_sixteenth(self)
        briefs = sorted(e["brief"] for r in data["lanes"] for e in r["refused"])
        self.assertEqual(briefs, sorted(b for _, b in THE_EIGHT.values()))

    def test_the_loss_per_lane_is_three_two_three(self):
        data = the_night_of_the_sixteenth(self)
        counts = {r["lane"]: r["refused_count"] for r in data["lanes"]}
        self.assertEqual(counts, {"glm": 3, "glm-b": 2, "glm-c": 3})

    def test_the_estate_total_is_eight(self):
        rows = the_night_of_the_sixteenth(self)["lanes"]
        self.assertEqual(sum(r["refused_count"] for r in rows), 8)

    def test_the_api_reports_the_total_and_the_per_lane_split(self):
        the_night_of_the_sixteenth(self)
        _body, data = self.page()
        self.assertEqual(data["refused_total"], 8)
        self.assertEqual(
            {e["lane"]: e["count"] for e in data["refused_by_lane"]},
            {"glm": 3, "glm-b": 2, "glm-c": 3})
        self.assertEqual(data["refused_by_date"],
                         [{"date": "2026-10-16", "count": 8}])
        self.assertEqual(data["refused_first"], "2026-10-16 01:41:36")
        self.assertEqual(data["refused_last"], "2026-10-16 01:48:09")

    def test_each_points_at_the_copy_the_watcher_made(self):
        """The copy is the brief. `Move-Item` preserved the bytes."""
        data = the_night_of_the_sixteenth(self)
        for row in data["lanes"]:
            for entry in row["refused"]:
                consumed = entry["consumed"]
                self.assertEqual(consumed["state"], lanes.PRESENT)
                self.assertEqual(
                    consumed["relative"],
                    os.path.join("queue", row["lane"], "DONE",
                                 consumed["name"]))
                self.assertTrue(consumed["name"].endswith(entry["brief"]))
                self.assertIn("-exit1-", consumed["name"])
                self.assertIsNotNone(consumed["bytes"])

    def test_the_reset_is_converted_and_says_which_clock_from(self):
        """`08:07:16` with no zone beside it is a trap, not an answer."""
        the_night_of_the_sixteenth(self)
        _body, data = self.page()
        for entry in data["refusals"]:
            reset = entry["reset"]
            self.assertEqual(reset["stated"], "2026-10-16 08:07:16")
            self.assertEqual(reset["local"], "2026-10-16 02:07:16")
            self.assertEqual(reset["delta_hours"], 6.0)
            self.assertEqual(entry["reset_from"], "UTC+08:00")
            self.assertEqual(entry["reset_to"], "UTC+02:00")

    def test_the_conversion_is_corroborated_by_a_second_clock(self):
        """Trap 6 used two clocks by hand. The same check, measured.

        The provider appends a request id whose first 14 characters are a
        timestamp on its own clock. Where the recorded offset is right, that
        lands on the watcher's DONE time plus the delta.
        """
        the_night_of_the_sixteenth(self)
        _body, data = self.page()
        self.assertEqual(data["reset_uncorroborated"], 0)
        for entry in data["refusals"]:
            check = entry["clock_check"]
            self.assertTrue(check["agrees"], entry["brief"])
            self.assertLessEqual(check["drift_seconds"], 1)

    def test_a_wrong_offset_is_caught_rather_than_believed(self):
        """The corroboration has to be able to say NO, or it says nothing."""
        self.assertEqual(
            lanes.corroborate_clock(ERROR % "20261016074136ea3a0e",
                                    datetime.datetime(2026, 10, 16, 1, 41, 36),
                                    1.0)["agrees"],
            False)

    def test_none_of_the_eight_is_still_missing_in_this_estate(self):
        """The hand restore is verified by reading the directory, not assumed."""
        data = the_night_of_the_sixteenth(self)
        for row in data["lanes"]:
            self.assertEqual(row["briefs_still_missing"], 0)
            for entry in row["refused"]:
                self.assertIs(entry["still_missing"], False)
                self.assertEqual(entry["restored"]["state"], lanes.PRESENT)


# --------------------------------------------------------------------------
# C2 - THE NEGATIVE CONTROL, WHICH IS THE ONE THAT MATTERS


class AGenuineFailureIsNotARefusal(unittest.TestCase, Estate):
    """Control 2. Both fixtures are real task outputs from `logs\\`.

    A detector that fired on every exit1 would tell the operator to restore
    briefs that really did fail - worse than the label it replaces, because
    that one loses a brief and this one would lose the record of a real
    failure and waste the re-run as well.
    """

    def a_failed_task(self, text, suffix="exit1"):
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "00:30:00", "watcher up. timeout=90m"),
            line("solo", "01:00:00", "START 0001-real-work.md"),
            line("solo", "01:20:00", "DONE  0001-real-work.md -> " + suffix),
        ], outs=[("20261016-010000", text)],
            done=["20261016-010000-%s-0001-real-work.md" % suffix])
        row = self.row("solo")
        self.assertEqual(len(row["closed_failures"]), 1)
        return row, row["closed_failures"][0]

    def test_a_real_task_report_on_an_exit1_is_an_ordinary_failure(self):
        row, entry = self.a_failed_task(REAL_REPORT)
        self.assertEqual(entry["outcome"], lanes.O_FAILED)
        self.assertEqual(entry["outcome_label"], "FAILED")
        self.assertEqual(row["refused_count"], 0)
        self.assertEqual(row["refused"], [])
        self.assertIsNone(entry["refusal_line"])

    def test_the_709_byte_near_miss_is_not_a_refusal(self):
        """Four bytes from the refusal size, same lane, same preamble."""
        row, entry = self.a_failed_task(NEAR_MISS)
        self.assertEqual(entry["outcome"], lanes.O_FAILED)
        self.assertEqual(entry["out_bytes"], 709)
        self.assertEqual(row["refused_count"], 0)

    def test_the_page_does_not_tell_the_operator_to_restore_it(self):
        """The page is where the wrong answer would do the damage."""
        self.a_failed_task(REAL_REPORT)
        body, data = self.page()
        self.assertEqual(data["refused_total"], 0)
        self.assertNotIn("STILL MISSING", body)
        self.assertNotIn("Request rejected", body)
        self.assertIn("None in the window this page read", body)

    def test_a_refusal_line_on_top_of_real_work_is_a_failure(self):
        """The fail-closed half, and it is the half that costs least wrong.

        A task that did its work and was refused on its last call DID run.
        Calling it a refusal would send somebody to restore a brief whose
        work is already on disk.
        """
        _row, entry = self.a_failed_task(
            REAL_REPORT + ERROR % "20261016074136ea3a0e14ec6e4bf9")
        self.assertEqual(entry["outcome"], lanes.O_FAILED)
        self.assertTrue(entry["refusal_line_but_also_output"])
        # The line is still returned. The stricter reading hides nothing.
        self.assertIn("Request rejected", entry["refusal_line"])

    def test_output_past_the_read_cap_counts_as_output(self):
        """A file longer than the cap carries work by construction."""
        found = lanes.classify_output(refusal_out("2026101607413600000000"),
                                      truncated=True)
        self.assertEqual(found["outcome"], lanes.O_FAILED)
        self.assertTrue(found["refusal_line_but_also_output"])


# --------------------------------------------------------------------------
# C3 - PROVE THE DETECTOR CAN FAIL, IN BOTH DIRECTIONS


class TheDetectorCanFail(unittest.TestCase, Estate):
    """Control 3. Blind the content match and watch the controls go red.

    `0080` found two of this page's own controls that could not fail either
    way, so this is run rather than reasoned about. A guard that cannot fail
    is watching something else.
    """

    def setUp(self):
        self.original = lanes._REFUSAL
        self.addCleanup(setattr, lanes, "_REFUSAL", self.original)

    def _refusals(self, text):
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "00:30:00", "watcher up. timeout=90m"),
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1"),
        ], outs=[("20261016-010000", text)])
        return self.row("solo")["closed_failures"][0]["outcome"]

    def test_blinded_to_always_match_the_negative_control_goes_red(self):
        """If the match always succeeds, a real report reads as a refusal."""
        # Unblinded first, so the control is known to be green before it is
        # broken - a red that was already red proves nothing.
        self.assertEqual(self._refusals(REAL_REPORT), lanes.O_FAILED)
        lanes._REFUSAL = re.compile(r"()")
        self.assertEqual(self._refusals(REAL_REPORT), lanes.O_REFUSED)

    def test_blinded_to_never_match_the_eight_go_red(self):
        """If the match never succeeds, the eight stop being refusals."""
        refusal = refusal_out("20261016074136ea3a0e14ec6e4bf9")
        self.assertEqual(self._refusals(refusal), lanes.O_REFUSED)
        lanes._REFUSAL = re.compile(r"(?!)()")
        # MEASURED, and it is not the answer predicted: with the match blinded
        # the error line is no longer a refusal line, so it counts as the
        # task's OWN OUTPUT and the outcome is `failed`. What this control
        # watches is that it stops being REFUSED, and it does.
        self.assertEqual(self._refusals(refusal), lanes.O_FAILED)


# --------------------------------------------------------------------------
# FAIL CLOSED


class AFailureNobodyCanReadIsNotAFailure(unittest.TestCase, Estate):
    """UNKNOWN never becomes a refusal and never becomes an ordinary failure."""

    def an_out(self, text, suffix="exit1", stamp="20261016-010000"):
        self.an_estate()
        outs = [] if text is lanes else [(stamp, text)]
        self.a_lane("solo", log=[
            line("solo", "00:30:00", "watcher up. timeout=90m"),
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> " + suffix),
        ], outs=outs)
        row = self.row("solo")
        return row, row["closed_failures"][0]

    def test_an_absent_out_is_UNKNOWN(self):
        row, entry = self.an_out(lanes)          # no `.out` written at all
        self.assertEqual(entry["outcome"], lanes.O_UNKNOWN)
        self.assertEqual(entry["out_state"], lanes.ABSENT)
        self.assertEqual(row["refused_count"], 0)
        self.assertEqual(row["unclassifiable_failures"], 1)

    def test_an_unreadable_out_is_UNKNOWN(self):
        _row, entry = self.an_out(None)          # a directory in its place
        self.assertEqual(entry["outcome"], lanes.O_UNKNOWN)
        self.assertEqual(entry["out_state"], lanes.UNREADABLE)

    def test_a_zero_byte_out_on_a_CLOSED_task_is_UNKNOWN(self):
        """The file fills at the end, so 0 bytes on a closed task is a loss."""
        _row, entry = self.an_out("")
        self.assertEqual(entry["outcome"], lanes.O_UNKNOWN)
        self.assertEqual(entry["out_state"], lanes.EMPTY)
        self.assertEqual(entry["out_bytes"], 0)

    def test_a_preamble_only_out_is_UNKNOWN_and_not_a_refusal(self):
        """559 bytes of harness notices and not one line of work or error."""
        _row, entry = self.an_out(PREAMBLE)
        self.assertEqual(entry["outcome"], lanes.O_UNKNOWN)
        self.assertEqual(entry["out_bytes"], 559)

    def test_the_page_says_a_zero_is_a_zero_among_what_could_be_read(self):
        self.an_out(lanes)
        body, data = self.page()
        self.assertEqual(data["refused_total"], 0)
        self.assertEqual(data["unclassifiable_failures"], 1)
        self.assertIn("could NOT be classified", body)
        self.assertIn("UNKNOWN is not zero", body)

    def test_a_refusal_with_no_reset_states_reset_UNKNOWN(self):
        text = PREAMBLE + "API Error: Request rejected (429) [1308][busy]\n"
        _row, entry = self.an_out(text)
        self.assertEqual(entry["outcome"], lanes.O_REFUSED)
        self.assertIsNone(entry["reset"]["stated"])
        self.assertIsNone(entry["reset"]["local"])
        body, _data = self.page()
        self.assertIn("this refusal states no reset time", body)
        # And the number that must never appear: five hours after anything.
        self.assertIn("NOT computed from the first failure plus", body)

    def test_an_unmeasurable_local_offset_refuses_to_convert(self):
        refusal = refusal_out("20261016074136ea3a0e14ec6e4bf9")
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1")],
            outs=[("20261016-010000", refusal)])
        original = lanes.local_utc_offset_hours
        lanes.local_utc_offset_hours = lambda _when: None
        self.addCleanup(setattr, lanes, "local_utc_offset_hours", original)
        entry = self.row("solo", offset=None)["closed_failures"][0]
        self.assertEqual(entry["outcome"], lanes.O_REFUSED)
        self.assertEqual(entry["reset"]["stated"], "2026-10-16 08:07:16")
        self.assertIsNone(entry["reset"]["local"])

    def test_an_unreadable_queue_never_proves_a_brief_missing(self):
        """That would send somebody to restore a file that is already there."""
        self.assertIsNone(lanes.still_missing(
            "x.md", [], [], lanes.UNREADABLE, lanes.PRESENT))
        self.assertIsNone(lanes.still_missing(
            "x.md", [], [], lanes.PRESENT, lanes.UNREADABLE))
        self.assertIs(lanes.still_missing(
            "x.md", [], [], lanes.PRESENT, lanes.PRESENT), True)


class NothingCheapDecidesThis(unittest.TestCase, Estate):
    """Not the exit code, not the size, not the lane, not a run of failures."""

    def _classify(self, text, suffix="exit1", lane="solo", extra=()):
        self.an_estate()
        log = [line(lane, "00:30:00", "watcher up. timeout=90m")]
        for clock, brief, done_suffix in extra:
            log.append(line(lane, clock, "START " + brief))
            log.append(line(lane, clock, "DONE  %s -> %s"
                            % (brief, done_suffix)))
        log += [line(lane, "01:00:00", "START 0009.md"),
                line(lane, "01:20:00", "DONE  0009.md -> " + suffix)]
        outs = [("20261016-010000", text)]
        for clock, _brief, _s in extra:
            outs.append((("2026101600" + clock[:2] + clock[3:5]
                          + clock[6:8])[:8] + "-" + clock.replace(":", ""),
                         REAL_REPORT))
        self.a_lane(lane, log=log, outs=outs)
        return self.row(lane)["closed_failures"][-1]["outcome"]

    def test_the_same_bytes_under_a_different_suffix_are_still_a_refusal(self):
        """`exit1` is not the signal. The content is."""
        refusal = refusal_out("20261016074136ea3a0e14ec6e4bf9")
        for suffix in ("exit1", "exit2", "exit", "NOWORK", "TIMEOUT"):
            self.assertEqual(self._classify(refusal, suffix),
                             lanes.O_REFUSED, suffix)

    def test_a_real_report_under_every_failure_suffix_is_still_a_failure(self):
        for suffix in ("exit1", "exit2", "exit", "NOWORK", "TIMEOUT"):
            self.assertEqual(self._classify(REAL_REPORT, suffix),
                             lanes.O_FAILED, suffix)

    def test_a_713_byte_report_is_not_a_refusal(self):
        """The size is in the display. It is not in the predicate.

        Padded to exactly the measured refusal size with the task's own prose,
        so a detector keyed on 713 bytes would fire.
        """
        padded = NEAR_MISS.rstrip("\n") + " " * (713 - 709) + "\n"
        self.assertEqual(len(padded.encode("utf-8")), 713)
        self.assertEqual(self._classify(padded), lanes.O_FAILED)

    def test_an_exit0_task_is_not_opened_at_all(self):
        """Scoped to failures, and the scope is the same either way.

        A completion whose output happens to hold a refusal line is not
        classified here, which is the gap the page states rather than hides.
        """
        self.an_estate()
        refusal = refusal_out("20261016074136ea3a0e14ec6e4bf9")
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit0")],
            outs=[("20261016-010000", refusal)])
        row = self.row("solo")
        self.assertEqual(row["closed_failures"], [])
        self.assertEqual(row["refused_count"], 0)
        body, _data = self.page()
        self.assertIn("a refusal that exited 0", body)

    def test_three_failures_in_a_row_do_not_make_a_refusal(self):
        """The watcher's own guard line is a hint, never the verdict."""
        self.an_estate()
        log = [line("solo", "00:30:00", "watcher up. timeout=90m")]
        outs = []
        for index, clock in enumerate(("01:00:00", "01:10:00", "01:20:00")):
            brief = "000%d.md" % index
            stamp = "20261016-01%d000" % index
            log += [line("solo", clock, "START " + brief),
                    line("solo", clock, "DONE  %s -> exit1" % brief)]
            outs.append((stamp, REAL_REPORT))
        log.append(line("solo", "01:21:00", "3 consecutive failures. Exiting "
                                            "rather than looping on a broken "
                                            "task."))
        self.a_lane("solo", log=log, outs=outs)
        row = self.row("solo")
        self.assertEqual(row["refused_count"], 0)
        self.assertEqual([e["outcome"] for e in row["closed_failures"]],
                         [lanes.O_FAILED] * 3)
        # The guard is still reported - as the mitigation it is.
        self.assertEqual(row["failure_guard"]["failures"], 3)
        body, _data = self.page()
        self.assertIn("it is a HINT", body)


# --------------------------------------------------------------------------
# THE JOIN


class TheJoinIsAnAuthorityNotAGuess(unittest.TestCase, Estate):
    """Which `.out` belongs to which brief, and on whose word."""

    def test_the_MOVED_line_is_the_authority_when_the_watcher_wrote_one(self):
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1"),
            line("solo", "01:20:00",
                 "MOVED 0001.md -> 20261016-005959-exit1-0001.md")],
            outs=[("20261016-005959",
                   refusal_out("20261016070000ab"))])
        entry = self.row("solo")["closed_failures"][0]
        self.assertEqual(entry["out_name"], "task-solo-20261016-005959.out")
        self.assertIn("MOVED", entry["out_join"])

    def test_without_one_the_START_stamp_is_used_and_says_so(self):
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1")],
            outs=[("20261016-010000",
                   refusal_out("20261016070000ab"))])
        entry = self.row("solo")["closed_failures"][0]
        self.assertEqual(entry["out_name"], "task-solo-20261016-010000.out")
        self.assertIn("START line", entry["out_join"])

    def test_a_stamp_one_second_after_the_START_still_joins(self):
        """The only disagreement the watcher's code allows is a second."""
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1")],
            outs=[("20261016-010001",
                   refusal_out("20261016070000ab"))])
        entry = self.row("solo")["closed_failures"][0]
        self.assertEqual(entry["out_name"], "task-solo-20261016-010001.out")

    def test_a_MOVED_line_naming_a_missing_out_is_UNKNOWN(self):
        """It does NOT fall through to the clock: that joins the wrong file."""
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1"),
            line("solo", "01:20:00",
                 "MOVED 0001.md -> 20261016-030303-exit1-0001.md")],
            outs=[("20261016-010000",
                   refusal_out("20261016070000ab"))])
        entry = self.row("solo")["closed_failures"][0]
        self.assertIsNone(entry["out_name"])
        self.assertEqual(entry["outcome"], lanes.O_UNKNOWN)
        self.assertIn("no `.out` with that stamp", entry["out_join_why"])

    def test_the_window_cannot_reach_the_next_task(self):
        """The watcher sleeps 5s between tasks, so the bound is what matters."""
        self.assertLess(lanes.OUT_JOIN_TOLERANCE_SECONDS, 5)
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:10:00", "DONE  0001.md -> exit1"),
            line("solo", "01:10:05", "START 0002.md"),
            line("solo", "01:20:00", "DONE  0002.md -> exit0")],
            outs=[("20261016-011005",
                   refusal_out("20261016070000ab"))])
        first = self.row("solo")["closed_failures"][0]
        # 0002's output is 5s past 0001's START... and 0001's own START is
        # 01:00:00, so nothing is within the window of it. The point is that
        # 0001 is NOT handed 0002's refusal.
        self.assertIsNone(first["out_name"])
        self.assertEqual(first["outcome"], lanes.O_UNKNOWN)

    def test_two_outs_inside_the_window_are_AMBIGUOUS(self):
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1")],
            outs=[("20261016-010000", refusal_out("20261016070000ab")),
                  ("20261016-010001", REAL_REPORT)])
        entry = self.row("solo")["closed_failures"][0]
        self.assertEqual(entry["outcome"], lanes.O_UNKNOWN)
        self.assertEqual(len(entry["out_ambiguous"]), 2)

    def test_a_MOVED_line_for_another_task_is_not_borrowed(self):
        """A MOVED line belongs to the DONE immediately above it."""
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:10:00", "DONE  0001.md -> exit1"),
            line("solo", "01:10:05", "START 0002.md"),
            line("solo", "01:20:00", "DONE  0002.md -> exit1"),
            line("solo", "01:20:00",
                 "MOVED 0002.md -> 20261016-011005-exit1-0002.md")],
            outs=[("20261016-011005",
                   refusal_out("20261016070000ab"))])
        rows = self.row("solo")["closed_failures"]
        self.assertEqual(rows[0]["brief"], "0001.md")
        self.assertIsNone(rows[0]["out_name"])
        self.assertEqual(rows[1]["out_name"], "task-solo-20261016-011005.out")

    def test_a_brief_RUN_TWICE_does_not_borrow_the_second_stamp(self):
        """The case the forward scan exists for, and the one that is coming.

        A MUTATION SURVIVED HERE AND THIS TEST IS WHY IT EXISTS. The first
        version of this class only checked that a MOVED line for a DIFFERENT
        brief was not borrowed - and the task-name match answers that on its
        own, so removing the "stop at the next START or DONE" guard changed
        nothing and the guard was unwatched. The guard is only load-bearing
        when the SAME brief name appears twice, which is precisely the state
        the estate is in now: all eight consumed briefs were restored by hand
        and will run again under their original names. Without the stop, the
        FIRST run's DONE reaches forward past the second START and takes the
        SECOND run's stamp - and then reads the second run's output as the
        evidence for the first run's verdict.
        """
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:10:00", "DONE  0001.md -> exit1"),
            line("solo", "01:10:00",
                 "MOVED 0001.md -> 20261016-010000-exit1-0001.md"),
            line("solo", "01:10:05", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1"),
            line("solo", "01:20:00",
                 "MOVED 0001.md -> 20261016-011005-exit1-0001.md")],
            outs=[("20261016-010000", REAL_REPORT),
                  ("20261016-011005",
                   refusal_out("20261016071005ab"))])
        rows = self.row("solo")["closed_failures"]
        self.assertEqual(len(rows), 2)
        # Each run gets its OWN output, so each gets its own outcome. Sharing
        # the second stamp would make the first run read REFUSED as well.
        self.assertEqual(rows[0]["out_name"], "task-solo-20261016-010000.out")
        self.assertEqual(rows[0]["outcome"], lanes.O_FAILED)
        self.assertEqual(rows[1]["out_name"], "task-solo-20261016-011005.out")
        self.assertEqual(rows[1]["outcome"], lanes.O_REFUSED)

    def test_the_stamp_comes_from_a_MOVED_line_naming_THIS_brief(self):
        """The other half of the same join, watched separately.

        The forward scan and the task-name match are two guards and either
        one alone lets a stamp be borrowed. This one fires where the names
        differ and the scan would not have stopped.
        """
        self.assertIsNone(lanes._moved_stamp(
            [{"kind": "done", "task": "0001.md"},
             {"kind": "moved", "task": "0002.md",
              "stamp": "20261016-011005"}], 0, "0001.md"))
        self.assertEqual(lanes._moved_stamp(
            [{"kind": "done", "task": "0001.md"},
             {"kind": "moved", "task": "0001.md",
              "stamp": "20261016-011005"}], 0, "0001.md"),
            "20261016-011005")

    def test_a_DONE_with_no_START_is_not_joined_to_anything(self):
        """The shape a truncated log tail produces."""
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:20:00", "DONE  0001.md -> exit1")],
            outs=[("20261016-010000",
                   refusal_out("20261016070000ab"))])
        entry = self.row("solo")["closed_failures"][0]
        self.assertIsNone(entry["out_name"])
        self.assertEqual(entry["outcome"], lanes.O_UNKNOWN)
        self.assertIn("no START line is paired", entry["out_join_why"])


# --------------------------------------------------------------------------
# THE CONSUMED BRIEF


class TheConsumedBriefIsReportedAndNotMoved(unittest.TestCase, Estate):
    """The repair is a person's. This page names the file and stops."""

    def a_refusal(self, queued=(), inflight=(), done=True, **kwargs):
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1")],
            outs=[("20261016-010000",
                   refusal_out("20261016070000ab"))],
            done=["20261016-010000-exit1-0001.md"] if done else [],
            queued=queued, inflight=inflight, **kwargs)
        return self.row("solo")["closed_failures"][0]

    def test_a_brief_nobody_put_back_is_reported_STILL_MISSING(self):
        entry = self.a_refusal()
        self.assertIs(entry["still_missing"], True)
        body, data = self.page()
        self.assertEqual(data["briefs_still_missing"], 1)
        self.assertIn("STILL MISSING", body)
        self.assertIn("0001.md", body)

    def test_a_brief_back_in_the_queue_is_not(self):
        entry = self.a_refusal(queued=["0001.md"])
        self.assertIs(entry["still_missing"], False)
        self.assertEqual(entry["restored"]["state"], lanes.PRESENT)
        self.assertEqual(entry["restored"]["relative"],
                         os.path.join("queue", "solo", "0001.md"))

    def test_a_brief_a_watcher_has_already_claimed_is_not_missing(self):
        entry = self.a_refusal(inflight=["0001.md"])
        self.assertIs(entry["still_missing"], False)
        self.assertEqual(entry["restored"]["relative"],
                         os.path.join("queue", "solo", "RUNNING", "0001.md"))

    def test_an_unreadable_RUNNING_folder_makes_it_UNKNOWN(self):
        entry = self.a_refusal(unreadable_running=True)
        self.assertIsNone(entry["still_missing"])
        _body, data = self.page()
        self.assertEqual(data["briefs_missing_unknown"], 1)

    def test_a_copy_that_is_not_in_DONE_is_reported_gone(self):
        """A DONE line is not evidence the file arrived: the move can fail."""
        entry = self.a_refusal(done=False)
        self.assertEqual(entry["consumed"]["state"], lanes.ABSENT)
        body, _data = self.page()
        self.assertIn("copy GONE", body)

    def test_reading_the_board_changes_nothing_on_disk(self):
        """Read-only, measured rather than claimed."""
        self.a_refusal(queued=["0001.md"])
        before = self._snapshot()
        for _ in range(3):
            self.board()
            self.page()
        self.assertEqual(self._snapshot(), before)

    def _snapshot(self):
        found = {}
        for base, dirs, names in os.walk(self.root):
            dirs.sort()
            for name in sorted(names):
                path = os.path.join(base, name)
                with open(path, "rb") as handle:
                    found[os.path.relpath(path, self.root)] = hashlib.md5(
                        handle.read()).hexdigest()
        return found

    def test_it_opens_no_socket(self):
        """A dashboard that reached the network would be a different thing."""
        self.a_refusal()
        original = socket.socket

        def refuse(*_a, **_k):
            raise AssertionError("the refusal reader opened a socket")

        socket.socket = refuse
        try:
            self.board()
        finally:
            socket.socket = original


# --------------------------------------------------------------------------
# THREE STATES, KEPT APART


class RefusedIsNotFailingAndNotDown(unittest.TestCase, Estate):
    """Each needs a different thing from a person, so each keeps its word."""

    def test_a_refused_task_in_a_live_lane_leaves_the_verdict_RUNNING(self):
        """The lane is fine. The brief is gone. Two separate facts."""
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "00:30:00", "watcher up. timeout=90m"),
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1"),
            line("solo", "01:20:05", "START 0002.md")],
            outs=[("20261016-010000",
                   refusal_out("20261016070000ab"))])
        row = self.row("solo", now=datetime.datetime(2026, 10, 16, 1, 25, 0))
        self.assertEqual(row["verdict"], lanes.V_RUNNING)
        self.assertEqual(row["refused_count"], 1)

    def test_the_outcome_words_are_not_the_verdict_words(self):
        """Two vocabularies, deliberately, so neither absorbs the other."""
        self.assertEqual(
            set(lanes.OUTCOME_TEXT) & set(lanes.VERDICT_TEXT),
            {lanes.O_UNKNOWN},
            "the only word the two glossaries may share is UNKNOWN")
        self.assertNotIn(lanes.O_REFUSED, lanes.VERDICT_TEXT)
        for _label, implies in lanes.OUTCOME_TEXT.values():
            self.assertTrue(implies.strip())

    def test_every_outcome_the_reader_can_produce_has_words_for_it(self):
        """A fourth outcome must not render as one of these three."""
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1")],
            outs=[("20261016-010000", REAL_REPORT)])
        for entry in self.row("solo")["closed_failures"]:
            self.assertIn(entry["outcome"], lanes.OUTCOME_TEXT)
            self.assertIsNotNone(entry["outcome_label"])

    def test_the_glossary_the_page_renders_comes_from_the_reader(self):
        self.an_estate()
        self.a_lane("solo", log=[line("solo", "01:00:00", "START 0001.md")])
        body, data = self.page()
        self.assertEqual([e["outcome"] for e in data["outcome_glossary"]],
                         sorted(lanes.OUTCOME_TEXT))
        for _key, (label, _why) in lanes.OUTCOME_TEXT.items():
            self.assertIn(label, body)


# --------------------------------------------------------------------------
# THE MITIGATION


class TheGuardThatBoundedItIsVisible(unittest.TestCase, Estate):
    """It is the only reason the loss stopped at nine and not the queue."""

    def test_the_exiting_rather_than_looping_line_is_shown(self):
        the_night_of_the_sixteenth(self)
        body, data = self.page()
        self.assertEqual(len(data["failure_guards"]), 3)
        self.assertIn("Exiting rather than looping on a broken task", body)
        self.assertIn("The guard that bounded this", body)
        for entry in data["failure_guards"]:
            self.assertEqual(entry["failures"], 3)
            self.assertEqual(entry["at"], "2026-10-16 01:48:09")

    def test_a_refusal_with_no_guard_line_says_nothing_bounded_it(self):
        """An absent mitigation is reported as an absent mitigation."""
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1")],
            outs=[("20261016-010000",
                   refusal_out("20261016070000ab"))])
        body, data = self.page()
        self.assertEqual(data["failure_guards"], [])
        self.assertIn("Nothing bounded the loss", body)

    def test_the_guard_line_carries_its_own_date(self):
        """An old guard line in a running lane says nothing about today."""
        self.an_estate()
        self.a_lane("solo", log=[
            line("solo", "02:35:30", "3 consecutive failures. Exiting rather "
                                     "than looping on a broken task.",
                 day="2026-10-15"),
            line("solo", "01:00:00", "START 0001.md"),
            line("solo", "01:20:00", "DONE  0001.md -> exit1")],
            outs=[("20261016-010000",
                   refusal_out("20261016070000ab"))])
        body, data = self.page()
        self.assertEqual(data["failure_guards"][0]["at"],
                         "2026-10-15 02:35:30")
        self.assertIn("2026-10-15 02:35:30", body)
        self.assertIn("is an OLD record in the log tail", body)


# --------------------------------------------------------------------------
# THE PAGE


class ThePageAnswersTheQuestionThatCostTheMost(unittest.TestCase, Estate):
    """What a person reads, and what it tells them to do."""

    def test_it_names_each_brief_its_copy_and_the_line_that_lied(self):
        the_night_of_the_sixteenth(self)
        body, _data = self.page()
        for (lane, stamp), (_rid, brief) in THE_EIGHT.items():
            self.assertIn(brief, body, brief)
            self.assertIn("%s-exit1-%s" % (stamp, brief), body)
            self.assertIn("task-%s-%s.out" % (lane, stamp), body)
        self.assertIn("DONE  0067b-save-sweep.md -&gt; exit1", body)

    def test_it_gives_the_reset_on_both_clocks(self):
        the_night_of_the_sixteenth(self)
        body, _data = self.page()
        self.assertIn("2026-10-16 02:07:16", body)
        self.assertIn("2026-10-16 08:07:16", body)
        self.assertIn("UTC+08:00", body)
        self.assertIn("UTC+02:00", body)
        self.assertIn("corroborated", body)

    def test_it_counts_per_lane_and_for_the_estate(self):
        the_night_of_the_sixteenth(self)
        body, _data = self.page()
        self.assertIn("glm 3, glm-b 2, glm-c 3", body)
        self.assertIn("briefs lost to a refusal", body)
        self.assertIn("2026-10-16: 8", body)

    def test_the_verdict_sits_beside_the_line_the_watcher_wrote(self):
        """Where the misreport was read is where the answer belongs."""
        the_night_of_the_sixteenth(self)
        body, _data = self.page()
        done = body.index("DONE  0073-the-zero-that-means-unknown.md")
        self.assertIn("REFUSED", body[done:done + 1200])

    def test_it_says_the_size_is_not_the_test(self):
        the_night_of_the_sixteenth(self)
        body, _data = self.page()
        self.assertIn("713 bytes", body)
        self.assertIn("NOT part of the test", body)
        self.assertIn("559", body)

    def test_it_says_nothing_here_moves_a_file(self):
        the_night_of_the_sixteenth(self)
        body, _data = self.page()
        self.assertIn("Nothing here moves a file", body)
        self.assertIn("restarting a lane", body)

    def test_the_whole_page_renders_for_the_real_shaped_estate(self):
        the_night_of_the_sixteenth(self)
        body, _data = self.page()
        self.assertGreater(len(body), 20000)
        # A row the renderer could not read would print the word None where a
        # value belongs. Scoped to the refusal panel, because the sentence
        # "None in the window this page read" is deliberate prose elsewhere.
        panel = body[body.index("Briefs consumed by a provider refusal"):]
        self.assertNotIn(">None<", panel)
        self.assertNotIn("None bytes", panel)


if __name__ == "__main__":
    unittest.main()
