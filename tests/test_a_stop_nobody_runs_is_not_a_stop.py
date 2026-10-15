#!/usr/bin/env python3
"""TASK-0160. The standing stops are run on a schedule, and a pass that did
not happen is visible as a hole in a file rather than as silence.

## THE DEFECT, RE-MEASURED BEFORE ANY OF THIS WAS WRITTEN

TASK-0140 repaired `scripts/bounce_stop_7day.py` and then said the thing that
outlives the repair: **nobody runs it.** Re-derived at `495fb3206` by grepping
the whole tree for all three check names - no service, timer, monitor, systemd
unit, tmux generator, `start_monitors.py` entry, loop under `scripts/` or
watcher invokes any of them. `bounce_stop_7day` and `hard_stop_check` were both
added 2026-09-22 and had been uninvoked for 24 days; `queue_wall_check` was
added 2026-10-16 01:10 and was born the same way.

## WHAT IS ASSERTED HERE, AND WHY EACH ONE IS NOT DECORATION

  THE WIRING        the runner is in the ONE monitor table, its heartbeat is
                    the file the loop actually beats to, and nothing else in
                    the tree invokes the three checks. A second caller is how
                    "one runner" becomes three again.

  THE CLASSIFIER    the exit code decides, and an exit code this runner does
                    not know is BLIND. An unread answer must never be a pass.

  THE GAP           an empty record is NEVER, a stale record is OPEN, a hole
                    is MISSED, an unparseable line is DAMAGED. This is the
                    third control and the one the other two cannot stand in
                    for: without it the runner is clean because it never ran.

  THE SENTENCE      0140's own line - "every rate is UNDEFINED and UNDEFINED
                    is not a pass" - travels through the runner, into the
                    journal row, UNCHANGED. Summarising it into a green tick
                    is the loss this task exists to prevent.

  THE CONTROLS      three planted inputs with known answers, run every pass,
                    and a deliberately broken instrument is caught by them.
                    A check that has never been seen to fail is not evidence
                    that nothing is wrong.

  THE CHANNEL       a STOP's notification carries counts and never an
                    address, even when the check summary it came from does -
                    `notify._status_payload` does not look inside a list, and
                    its refusal is swallowed by `notify.notify` into a FAILED
                    row, so a payload carrying one would silently stop being
                    a notification.

NO PROVIDER CALL AND NO NETWORK ANYWHERE IN THIS FILE. The checks are injected
as fakes; the controls drive the real `bounce_stop_7day.run` over a planted
`rows_source`, which is why that seam exists. `bison.scheduled_emails` is
patched to raise in the pass test, so a single provider call would fail it.
"""
import ast
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import notify, stopwatchdog, store, supervisor           # noqa: E402

LOOP = os.path.join(ROOT, "scripts", "stop_watchdog_loop.py")

#: 0140's own sentence for the estate as it stands today, quoted exactly.
#: If the runner ever paraphrases it, `TheSentenceTravelsVerbatim` fails.
UNDEFINED_SENTENCE = (
    "7-DAY BOUNCE STOP: 0 PASS, 0 STOP, 0 BLIND - no mailbox sent for us in "
    "7d across 10 campaigns read whole, so every rate is UNDEFINED and "
    "UNDEFINED is not a pass.")


def _loop():
    """The loop, loaded by path. `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location("_stop_watchdog_loop", LOOP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake(name, exit_code, summary):
    """A check table row plus the adapter that answers for it.

    Returns `(check, install)`. `install` patches `stopwatchdog.ADAPTERS` so
    the row answers without loading or running anything.
    """
    check = {"name": name, "script": os.path.join("scripts", "noop.py"),
             "entry": "run", "about": "a planted check", "reads": "nothing",
             "added": "never"}
    return check, (name, exit_code, summary)


def _install(fakes):
    """Patch `load` and `ADAPTERS` so a list of `_fake` rows can be run."""
    adapters = dict(stopwatchdog.ADAPTERS)
    names = {name for name, _c, _s in fakes}
    for name, code, summary in fakes:
        adapters[name] = (lambda module, _c=code, _s=summary, **kw:
                          (_c, _s, {}))
    real_load = stopwatchdog.load

    def load(check):
        """FALLS BACK TO THE REAL LOADER for anything not planted.

        A fake `load` that answered for every check broke the CONTROLS,
        which drive the real `bounce_stop_7day` - and the symptom was
        `controls_ok` False in a test about provider calls, which names
        neither cause. Measured while writing this file.
        """
        if check["name"] in names:
            return object()
        return real_load(check)

    return [mock.patch.object(stopwatchdog, "load", load),
            mock.patch.object(stopwatchdog, "ADAPTERS", adapters)]


class _Patched:
    def __init__(self, patches):
        self.patches = patches

    def __enter__(self):
        for patch in self.patches:
            patch.start()
        return self

    def __exit__(self, *exc):
        for patch in reversed(self.patches):
            patch.stop()
        return False


class _Isolated(unittest.TestCase):
    """Every state file in a temporary directory, restored afterwards."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-0160-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(store.use_directory(os.path.join(self.tmp, "work")))
        self.journal = os.path.join(self.tmp, "journal.jsonl")


# --------------------------------------------------------------- the wiring


class TheRunnerIsInTheOneTable(unittest.TestCase):
    """A script in no table is a script nothing starts, and `--status`
    cannot report a monitor that is not declared as missing. That is the
    `weekly_report` finding and this is the same shape one step on."""

    def test_the_monitor_is_declared_exactly_once(self):
        rows = [m for m in supervisor.STATIC_MONITORS
                if m["name"] == "stop_watchdog"]
        self.assertEqual(1, len(rows), "stop_watchdog is not in the one table")
        self.assertEqual("scripts.stop_watchdog_loop", rows[0]["module"])

    def test_the_declared_heartbeat_is_the_file_the_loop_actually_writes(self):
        """The `46474c6c` defect, which has already cost this estate twice.

        A declared beat that names a file nothing writes makes
        `cold_start --verify` poll a path forever and report the monitor down.
        Read from the loop's SOURCE rather than imported, because importing
        it pulls in `src.notify` and the provider package.
        """
        with io.open(LOOP, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), LOOP)
        found = [node.value.value for node in ast.walk(tree)
                 if isinstance(node, ast.Assign)
                 and isinstance(node.value, ast.Constant)
                 for target in node.targets
                 if isinstance(target, ast.Name) and target.id == "WATCHER"]
        self.assertEqual(["stop-watchdog"], found)
        row, = [m for m in supervisor.STATIC_MONITORS
                if m["name"] == "stop_watchdog"]
        self.assertTrue(supervisor.heartbeat_file(row).endswith(
            "stop-watchdog.json"))

    def test_the_beat_is_more_frequent_than_the_staleness_limit(self):
        """A monitor whose beat is slower than `STALE_SECONDS` reads DOWN
        between passes, and `start_monitors.py --live` is then free to start
        a SECOND one beside the first - the two-Slack-clients failure, with
        two watchdogs instead."""
        starter = importlib.util.spec_from_file_location(
            "_start_monitors", os.path.join(ROOT, "scripts",
                                            "start_monitors.py"))
        module = importlib.util.module_from_spec(starter)
        starter.loader.exec_module(module)
        row, = [m for m in supervisor.STATIC_MONITORS
                if m["name"] == "stop_watchdog"]
        self.assertLess(row["interval"], module.STALE_SECONDS)
        loop = _loop()
        self.assertLess(loop.DEFAULT_INTERVAL, module.STALE_SECONDS)
        self.assertGreater(loop.DEFAULT_EVERY, loop.DEFAULT_INTERVAL,
                           "the pass cadence must be the slower of the two")

    def test_every_declared_check_resolves_to_a_real_entry_point(self):
        """The table is a declaration, so it is checked. A path that does not
        exist, or an entry function that was renamed, would otherwise be a
        BLIND on every pass for ever - which is survivable but silent."""
        for check in stopwatchdog.CHECKS:
            with self.subTest(check=check["name"]):
                module = stopwatchdog.load(check)
                self.assertTrue(hasattr(module, check["entry"]),
                                "%s has no %s" % (check["script"],
                                                  check["entry"]))
                self.assertIn(check["name"], stopwatchdog.ADAPTERS)

    def test_the_three_checks_have_exactly_one_caller(self):
        """ONE RUNNER, NOT THREE. Asserted on code with comments and
        docstrings stripped, the way `test_nothing_writes_to_a_provider`
        does, because every one of these names appears in prose all over the
        tree and a text search over raw files is a test that fails when
        somebody writes a sentence.
        """
        names = [os.path.basename(c["script"])[:-3]
                 for c in stopwatchdog.CHECKS]
        allowed = {"src/stopwatchdog.py"}
        allowed |= {"scripts/%s.py" % n for n in names}
        offenders = {}
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in
                       ("__pycache__", ".git", "work", "node_modules",
                        "venv", ".venv", ".claude", "tests", "docs")]
            for name in files:
                if not name.endswith(".py"):
                    continue
                full = os.path.join(base, name)
                rel = os.path.relpath(full, ROOT).replace("\\", "/")
                if rel in allowed:
                    continue
                code = _stripped(full)
                hits = [n for n in names if n in code]
                if hits:
                    offenders[rel] = hits
        self.assertEqual(
            {}, offenders,
            "a second caller of the standing stops: %r. One runner means one "
            "schedule, one record and one place a gap shows." % (offenders,))


def _stripped(path):
    """The file with docstrings and comments removed."""
    import re
    text = io.open(path, encoding="utf-8").read()
    text = re.sub(r'("""|\'\'\')(?:.|\n)*?\1', "", text, flags=re.MULTILINE)
    return "\n".join(line.split("#")[0] for line in text.splitlines())


# ----------------------------------------------------------- the classifier


class TheExitCodeDecidesAndAnUnknownOneIsBlind(unittest.TestCase):

    def test_the_three_known_codes(self):
        self.assertEqual(stopwatchdog.PASS, stopwatchdog.classify(0))
        self.assertEqual(stopwatchdog.STOP, stopwatchdog.classify(1))
        self.assertEqual(stopwatchdog.BLIND, stopwatchdog.classify(2))

    def test_an_unknown_code_is_blind_and_never_pass(self):
        """FAIL CLOSED ON THE DEFAULT, and this is the mutation that matters.

        `3`, `None` from a function that returned nothing, `-1` from a killed
        child, `"0"` from a code that came back as text. Every one of them is
        an answer this runner has not understood, and the one thing an
        unread answer must never become is a pass.
        """
        # `True` is in this list deliberately: `True == 1` in Python, so a
        # boolean in an exit-code slot would read as a tripped STOP by
        # arithmetic accident and `False` as a clean PASS.
        for code in (3, -1, None, "0", "", 1.5, True, False):
            with self.subTest(code=code):
                verdict = stopwatchdog.classify(code)
                self.assertNotEqual(stopwatchdog.PASS, verdict,
                                    "exit %r was read as a pass" % (code,))
                self.assertEqual(stopwatchdog.BLIND, verdict)

    def test_stop_and_blind_are_not_the_same_exit_code(self):
        """The distinction `bounce_stop_7day` repaired one level down: a
        reader keyed on the status must be able to tell a tripped stop from a
        check that never managed to run."""
        self.assertEqual(0, stopwatchdog.EXIT[stopwatchdog.PASS])
        self.assertEqual(1, stopwatchdog.EXIT[stopwatchdog.STOP])
        self.assertEqual(2, stopwatchdog.EXIT[stopwatchdog.BLIND])
        self.assertEqual(3, len(set(stopwatchdog.EXIT.values())))


# ------------------------------------------------------------------- gaps


class AMissingPassIsAHoleAndNotSilence(unittest.TestCase):
    """THE THIRD CONTROL, as assertions. Without this the runner is the B7
    instrument again: clean because nothing ever asked it anything."""

    EVERY = 3600
    BASE = 1_760_000_000

    def rows(self, *offsets):
        return [{"epoch": self.BASE + o, "at": "t+%d" % o} for o in offsets]

    def test_an_empty_record_is_never_and_not_no_gaps(self):
        found = stopwatchdog.gaps([], every=self.EVERY, now=self.BASE)
        self.assertEqual([stopwatchdog.NEVER], [g["kind"] for g in found])
        self.assertIn("not a clean one", found[0]["why"])

    def test_a_continuous_record_has_no_gap(self):
        rows = self.rows(0, 3600, 7200)
        self.assertEqual([], stopwatchdog.gaps(rows, every=self.EVERY,
                                               now=self.BASE + 7200))

    def test_one_late_pass_inside_the_tolerance_is_not_a_gap(self):
        """Pins `GAP_FACTOR`. A single missed pass is a slow provider read or
        a machine asleep for a minute; two in a row is the scheduler. A
        version that called one pass a gap would cry wolf, and a guard that
        cries wolf gets switched off."""
        rows = self.rows(0, 7000)
        self.assertEqual([], stopwatchdog.gaps(rows, every=self.EVERY,
                                               now=self.BASE + 7000))

    def test_a_hole_between_two_attempts_is_missed_with_a_count(self):
        rows = self.rows(0, 3600, 3600 * 5)
        found = stopwatchdog.gaps(rows, every=self.EVERY,
                                  now=self.BASE + 3600 * 5)
        self.assertEqual([stopwatchdog.MISSED], [g["kind"] for g in found])
        self.assertEqual(3, found[0]["missed"])

    def test_a_stale_record_is_an_open_gap_because_it_is_the_live_one(self):
        """The one that says the scheduler is not firing NOW, rather than
        that it once stuttered. This is the condition that would have been
        true for 24 days."""
        rows = self.rows(0)
        found = stopwatchdog.gaps(rows, every=self.EVERY,
                                  now=self.BASE + 3600 * 24 * 24)
        self.assertEqual([stopwatchdog.OPEN], [g["kind"] for g in found])
        self.assertIn("NOT firing now", found[0]["why"])

    def test_a_cadence_of_zero_is_refused_rather_than_divided_by(self):
        for every in (0, -1):
            with self.subTest(every=every):
                with self.assertRaises(ValueError):
                    stopwatchdog.gaps(self.rows(0), every=every)


class ADamagedRecordIsReportedAndNotSkipped(_Isolated):

    def test_a_line_that_will_not_parse_is_a_damaged_gap(self):
        """Dropping it would restore exactly the silence this file removes:
        a record whose continuity cannot be proven must not read continuous.
        """
        stopwatchdog.record_attempt({"epoch": 100, "at": "a"},
                                    path=self.journal)
        with open(self.journal, "a", encoding="utf-8") as handle:
            handle.write("{not json at all\n")
        stopwatchdog.record_attempt({"epoch": 200, "at": "b"},
                                    path=self.journal)
        rows = stopwatchdog.attempts(path=self.journal)
        self.assertEqual(3, len(rows))
        kinds = [g["kind"] for g in
                 stopwatchdog.gaps(rows, every=100, now=200)]
        self.assertIn(stopwatchdog.DAMAGED, kinds)

    def test_a_row_without_a_numeric_epoch_is_damaged_not_dropped(self):
        with open(self.journal, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": "no epoch here"}) + "\n")
        rows = stopwatchdog.attempts(path=self.journal)
        self.assertEqual(1, len(rows))
        self.assertIsNone(rows[0]["epoch"])
        self.assertEqual([stopwatchdog.DAMAGED, stopwatchdog.NEVER],
                         [g["kind"] for g in
                          stopwatchdog.gaps(rows, every=100, now=1)])


class TheRecordIsAppendedAndMovesWithTheState(_Isolated):

    def test_two_attempts_are_two_rows(self):
        """APPEND, NOT REPLACE. A rewritten file answers "what happened last
        time" and can never answer "did the schedule hold"."""
        stopwatchdog.record_attempt({"epoch": 1}, path=self.journal)
        stopwatchdog.record_attempt({"epoch": 2}, path=self.journal)
        self.assertEqual([1, 2], [r["epoch"] for r in
                                  stopwatchdog.attempts(path=self.journal)])

    def test_the_journal_moves_with_use_directory(self):
        self.assertEqual(
            os.path.abspath(os.path.join(self.tmp, "work")),
            os.path.dirname(os.path.abspath(stopwatchdog.journal_path())))

    def test_attempts_is_oldest_first_whatever_order_the_file_holds(self):
        for epoch in (300, 100, 200):
            stopwatchdog.record_attempt({"epoch": epoch}, path=self.journal)
        self.assertEqual([100, 200, 300],
                         [r["epoch"] for r in
                          stopwatchdog.attempts(path=self.journal)])

    def test_a_missing_file_is_no_attempts_and_not_an_error(self):
        self.assertEqual([], stopwatchdog.attempts(
            path=os.path.join(self.tmp, "never-written.jsonl")))


# -------------------------------------------------------------- the assessment


class TheAssessmentNeverLetsANumberDisappear(unittest.TestCase):

    EVERY = 3600
    NOW = 1_760_000_000

    def good_record(self):
        return [{"epoch": self.NOW - 1800, "at": "recent"}]

    def held(self):
        return [{"control": "c%d" % i, "ok": True, "planted": "",
                 "expected": [], "observed": []} for i in range(3)]

    def check(self, verdict, code, summary="a sentence"):
        return {"name": "check_%s" % verdict.lower(), "verdict": verdict,
                "exit_code": code, "summary": summary, "about": ""}

    def assess(self, results, rows=None, controls=None):
        return stopwatchdog.assess(
            results, self.good_record() if rows is None else rows,
            self.EVERY, now=self.NOW,
            control_rows=self.held() if controls is None else controls)

    def test_everything_clean_is_a_pass(self):
        out = self.assess([self.check(stopwatchdog.PASS, 0)])
        self.assertEqual(stopwatchdog.PASS, out["verdict"])
        self.assertEqual(0, out["exit_code"])

    def test_a_stop_wins_the_headline_and_the_blind_is_still_in_the_sentence(
            self):
        """`bounce_stop_7day._summary` learnt this one level down: an
        unreadable campaign beside a stopped mailbox produced no blinded
        mailbox and therefore no BLIND in its own line. Same disappearance,
        one level up."""
        out = self.assess([self.check(stopwatchdog.STOP, 1),
                           self.check(stopwatchdog.BLIND, 2),
                           self.check(stopwatchdog.PASS, 0)])
        self.assertEqual(stopwatchdog.STOP, out["verdict"])
        self.assertEqual(1, out["exit_code"])
        self.assertIn("1 STOP", out["summary"])
        self.assertIn("1 BLIND", out["summary"])
        self.assertIn("1 PASS", out["summary"])
        self.assertIn("1 check(s) BLIND", out["why"])

    def test_a_gap_alone_is_blind_even_when_every_check_passed(self):
        """THE WHOLE TASK, in one assertion. Three green checks over a record
        with a hole in it is not a green estate - it is an estate whose gate
        was not asked."""
        stale = [{"epoch": self.NOW - 3600 * 24 * 24, "at": "old"}]
        out = self.assess([self.check(stopwatchdog.PASS, 0)], rows=stale)
        self.assertEqual(stopwatchdog.BLIND, out["verdict"])
        self.assertEqual(2, out["exit_code"])
        self.assertIn("gap(s) in the record", out["why"])
        self.assertIn("OPEN", out["summary"])

    def test_an_empty_record_is_blind_not_pass(self):
        out = self.assess([self.check(stopwatchdog.PASS, 0)], rows=[])
        self.assertEqual(stopwatchdog.BLIND, out["verdict"])
        self.assertIn("NEVER", out["summary"])

    def test_a_control_that_did_not_hold_makes_the_whole_pass_blind(self):
        """An instrument that cannot be shown to fail is not evidence that
        nothing is wrong, so a pass whose controls did not hold proves
        nothing and says so."""
        broken = self.held()
        broken[1]["ok"] = False
        out = self.assess([self.check(stopwatchdog.PASS, 0)],
                          controls=broken)
        self.assertEqual(stopwatchdog.BLIND, out["verdict"])
        self.assertFalse(out["controls_ok"])
        self.assertIn("DID NOT HOLD", out["why"])
        self.assertIn("controls 2/3 held", out["summary"])

    def test_no_check_at_all_is_blind_and_never_pass(self):
        out = self.assess([])
        self.assertEqual(stopwatchdog.BLIND, out["verdict"])
        self.assertIn("no check ran at all", out["why"])

    def test_the_summary_is_never_a_tick(self):
        """All three words with their numbers, whichever verdict won. The
        failure this task is about is a number disappearing into a greener
        one."""
        for results in ([self.check(stopwatchdog.PASS, 0)],
                        [self.check(stopwatchdog.STOP, 1)],
                        [self.check(stopwatchdog.BLIND, 2)]):
            out = self.assess(results)
            for word in ("STOP", "PASS", "BLIND", "gap(s)", "controls"):
                self.assertIn(word, out["summary"])


class TheSentenceTravelsVerbatim(_Isolated):
    """0140's line today is `0 PASS, 0 STOP, 0 BLIND ... every rate is
    UNDEFINED and UNDEFINED is not a pass.` The runner must carry that
    through unchanged rather than summarising it into a green tick."""

    def test_the_checks_own_sentence_survives_the_runner(self):
        check, fake = _fake("bounce_stop_7day", 0, UNDEFINED_SENTENCE)
        with _Patched(_install([fake])):
            rows = stopwatchdog.run_checks(checks=[check])
        self.assertEqual(UNDEFINED_SENTENCE, rows[0]["summary"])
        out = stopwatchdog.assess(rows, [{"epoch": 10, "at": "x"}], 100,
                                  now=20, control_rows=[])
        self.assertEqual(UNDEFINED_SENTENCE, out["checks"][0]["summary"])

    def test_the_sentence_reaches_the_journal_row_unchanged(self):
        check, fake = _fake("bounce_stop_7day", 0, UNDEFINED_SENTENCE)
        loop = _loop()
        with _Patched(_install([fake])):
            loop.tick(every=100, now=1000, force=True, checks=[check],
                      journal=self.journal, with_controls=False,
                      announce_stop=False, out=lambda text: None)
        written = stopwatchdog.attempts(path=self.journal)
        self.assertEqual(1, len(written))
        self.assertEqual(UNDEFINED_SENTENCE,
                         written[0]["checks"][0]["summary"])

    def test_undefined_is_not_printed_as_a_pass(self):
        """The sentence says PASS nowhere about a mailbox, and the runner
        must not supply one. 0 PASS of 0 mailboxes is not a clean estate."""
        self.assertIn("UNDEFINED is not a pass", UNDEFINED_SENTENCE)
        self.assertIn("0 PASS, 0 STOP, 0 BLIND", UNDEFINED_SENTENCE)


# ---------------------------------------------------------------- the loop


class ATickRecordsItsAttempt(_Isolated):

    def test_a_pass_writes_exactly_one_row(self):
        check, fake = _fake("c", 0, "clean")
        loop = _loop()
        with _Patched(_install([fake])):
            loop.tick(every=100, now=1000, force=True, checks=[check],
                      journal=self.journal, with_controls=False,
                      announce_stop=False, out=lambda t: None)
        self.assertEqual(1, len(stopwatchdog.attempts(path=self.journal)))

    def test_a_tick_that_is_not_due_writes_no_row(self):
        """THE JOURNAL IS A RECORD OF ATTEMPTS AT THE SCHEDULE, not of
        wake-ups. Padding it with every beat would make a gap unfindable,
        which is the one thing it exists to show."""
        check, fake = _fake("c", 0, "clean")
        loop = _loop()
        with _Patched(_install([fake])):
            first = loop.tick(every=3600, now=1000, force=True,
                              checks=[check], journal=self.journal,
                              with_controls=False, announce_stop=False,
                              out=lambda t: None)
            second = loop.tick(every=3600, now=1060, checks=[check],
                               journal=self.journal, with_controls=False,
                               announce_stop=False, out=lambda t: None)
        self.assertIsNotNone(first)
        self.assertIsNone(second, "a tick ran a pass that was not due")
        self.assertEqual(1, len(stopwatchdog.attempts(path=self.journal)))

    def test_a_pass_is_due_again_once_the_cadence_has_elapsed(self):
        check, fake = _fake("c", 0, "clean")
        loop = _loop()
        with _Patched(_install([fake])):
            loop.tick(every=3600, now=1000, force=True, checks=[check],
                      journal=self.journal, with_controls=False,
                      announce_stop=False, out=lambda t: None)
            again = loop.tick(every=3600, now=1000 + 3600, checks=[check],
                              journal=self.journal, with_controls=False,
                              announce_stop=False, out=lambda t: None)
        self.assertIsNotNone(again)
        self.assertEqual(2, len(stopwatchdog.attempts(path=self.journal)))

    def test_the_first_ever_tick_is_due(self):
        loop = _loop()
        self.assertEqual((True, None), loop.due([], 3600, now=0))

    def test_the_attempt_is_recorded_before_anything_else_can_fail(self):
        """ORDER MATTERS. A printer into a closed pipe, a notification that
        raises, a Slack transport that is down - none of them may cost the
        record of the attempt, because the record is what makes the NEXT
        missing pass visible."""
        check, fake = _fake("c", 0, "clean")
        loop = _loop()

        def explode(text):
            raise RuntimeError("the pipe is closed")

        with _Patched(_install([fake])):
            with self.assertRaises(RuntimeError):
                loop.tick(every=100, now=1000, force=True, checks=[check],
                          journal=self.journal, with_controls=False,
                          announce_stop=False, out=explode)
        self.assertEqual(1, len(stopwatchdog.attempts(path=self.journal)),
                         "the attempt was lost because printing failed")

    def test_a_check_that_raises_is_blind_and_the_others_still_run(self):
        """The runner's catch is broad where the checks' are narrow, and the
        direction is what makes it safe: BLIND clears nobody, so a bug is
        loud and non-zero rather than invisible and green."""
        def boom(module, **kw):
            raise KeyError("a bug in our own code")

        good, fake = _fake("good", 0, "clean")
        bad, _ = _fake("bad", 0, "never reached")
        adapters = dict(stopwatchdog.ADAPTERS)
        adapters["good"] = lambda module, **kw: (0, "clean", {})
        adapters["bad"] = boom
        with _Patched([
                mock.patch.object(stopwatchdog, "load", lambda c: object()),
                mock.patch.object(stopwatchdog, "ADAPTERS", adapters)]):
            rows = stopwatchdog.run_checks(checks=[bad, good])
        self.assertEqual([stopwatchdog.BLIND, stopwatchdog.PASS],
                         [r["verdict"] for r in rows])
        self.assertEqual("KeyError", rows[0]["error"])
        self.assertEqual(2, rows[0]["exit_code"])
        self.assertIn("KeyError", rows[0]["summary"])


class TheRecordCanBeReadWithoutRunningAnything(_Isolated):

    def test_status_on_an_empty_record_exits_blind(self):
        loop = _loop()
        lines = []
        code = loop.status(every=3600, now=0, journal=self.journal,
                           out=lines.append)
        self.assertEqual(stopwatchdog.EXIT_BLIND, code)
        self.assertIn("NO ATTEMPT HAS EVER BEEN RECORDED",
                      "\n".join(lines))

    def test_status_reports_the_open_gap_and_exits_non_zero(self):
        stopwatchdog.record_attempt(
            {"epoch": 1000, "at": "then", "verdict": "PASS", "exit_code": 0,
             "summary": "clean"}, path=self.journal)
        loop = _loop()
        lines = []
        code = loop.status(every=3600, now=1000 + 3600 * 24 * 24,
                           journal=self.journal, out=lines.append)
        self.assertEqual(stopwatchdog.EXIT_BLIND, code)
        self.assertIn("GAP OPEN", "\n".join(lines))


# ------------------------------------------------------------- the controls


class TheControlsProveTheInstrumentCanStillFail(unittest.TestCase):
    """Three planted inputs with known answers, run on every pass, costing no
    provider call. `bison.scheduled_emails` is never reached because controls
    1 and 2 go through `bounce_stop_7day.run`'s `rows_source` seam."""

    def test_there_are_three_and_they_all_hold_today(self):
        with mock.patch("src.providers.bison.scheduled_emails",
                        side_effect=AssertionError("a control called the "
                                                   "provider")):
            rows = stopwatchdog.controls()
        self.assertEqual(3, len(rows))
        for row in rows:
            with self.subTest(control=row["control"]):
                self.assertTrue(row["ok"], "%s: expected %r observed %r"
                                % (row["control"], row["expected"],
                                   row["observed"]))

    def test_control_one_is_a_real_stop_from_the_real_check(self):
        rows = stopwatchdog.controls()
        self.assertIn("STOP", rows[0]["control"])
        self.assertEqual([stopwatchdog.STOP, 1], rows[0]["observed"])

    def test_control_two_is_blind_with_a_non_zero_exit(self):
        rows = stopwatchdog.controls()
        self.assertIn("unreadable", rows[1]["control"])
        self.assertEqual([stopwatchdog.BLIND, 2], rows[1]["observed"])
        self.assertNotEqual(0, rows[1]["observed"][1])

    def test_control_three_is_the_gap_the_other_two_cannot_show(self):
        rows = stopwatchdog.controls()
        self.assertIn("gap", rows[2]["control"])
        self.assertEqual([[stopwatchdog.MISSED], [stopwatchdog.NEVER]],
                         rows[2]["observed"])

    def test_a_broken_instrument_is_caught_by_its_own_control(self):
        """THE CONTROL THAT PROVES IT CAN FAIL. The threshold is moved so a
        4% mailbox no longer trips, which is the exact silent weakening a
        control exists for, and control 1 must notice."""
        real_load = stopwatchdog.load

        def weakened(check):
            module = real_load(check)
            if check["name"] == "bounce_stop_7day":
                module.THRESHOLD = 99.0
            return module

        with mock.patch.object(stopwatchdog, "load", weakened):
            rows = stopwatchdog.controls()
        self.assertFalse(rows[0]["ok"], "a 99% threshold passed control 1")
        # CLEAR, not PASS: the observed pair is the bounce stop's OWN
        # vocabulary, carried through rather than translated, which is also
        # the proof that control 1 really ran that script and not a stand-in.
        self.assertEqual(["CLEAR", 0], rows[0]["observed"])
        # A PASSING CHECK AND A CONTINUOUS RECORD, so the failed control is
        # the ONLY thing that can make this BLIND.
        #
        # THE MUTATION PROOF CAUGHT THIS TEST BEING WRONG. It first passed
        # `[]` for the checks and `assess`'s `not results` guard answered
        # BLIND on its own, so deleting `or bad_controls` from the verdict
        # rule left this green - a different guard firing first, which is the
        # trap CLAUDE.md names. M3 now reddens both tests.
        clean = [{"name": "c", "verdict": stopwatchdog.PASS, "exit_code": 0,
                  "summary": "clean", "about": ""}]
        out = stopwatchdog.assess(clean, [{"epoch": 100, "at": "x"}], 100,
                                  now=150, control_rows=rows)
        self.assertEqual([], out["gaps"])
        self.assertEqual(stopwatchdog.BLIND, out["verdict"])
        self.assertIn("DID NOT HOLD", out["why"])

    def test_a_broken_gap_rule_is_caught_by_control_three(self):
        """The same, for the rule the other two cannot see. A `gaps` that
        answered "no gaps" to everything is the 24-day silence restored, and
        this is what notices."""
        with mock.patch.object(stopwatchdog, "gaps",
                               lambda *a, **k: []):
            rows = stopwatchdog.controls()
        self.assertFalse(rows[2]["ok"])
        self.assertEqual([[], []], rows[2]["observed"])


# ---------------------------------------------------------- the notification


class AStopIsAnnouncedAndCarriesNoAddress(_Isolated):

    def stop_assessment(self, summary):
        check = {"name": "hard_stop_check", "verdict": stopwatchdog.STOP,
                 "exit_code": 1, "summary": summary, "about": ""}
        return stopwatchdog.assess([check], [{"epoch": 10, "at": "x"}], 100,
                                   now=20, control_rows=[])

    def test_a_stop_plans_a_critical_notification(self):
        """`notify.STATUS_HARD_STOP` has been in the routing table as
        CRITICAL since 2026-09-21 with NOTHING in the repository raising it.
        This loop is its first producer - a second declared-and-unused
        instrument found while fixing the first."""
        self.assertEqual((notify.STATUS, notify.CRITICAL),
                         notify.route(notify.STATUS_HARD_STOP))
        loop = _loop()
        row = loop.announce(self.stop_assessment("1 mailbox tripped"))
        self.assertIsNotNone(row)
        self.assertEqual(notify.STATUS_HARD_STOP, row["type"])
        self.assertEqual(notify.CRITICAL, row["severity"])

    def test_nothing_is_announced_when_nothing_stopped(self):
        """A BLIND is in the journal, the log and the supervisor's view. A
        CRITICAL for every unreadable campaign is how a critical channel
        stops being read."""
        loop = _loop()
        clean = stopwatchdog.assess(
            [{"name": "c", "verdict": stopwatchdog.BLIND, "exit_code": 2,
              "summary": "could not read", "about": ""}],
            [{"epoch": 10, "at": "x"}], 100, now=20, control_rows=[])
        self.assertIsNone(loop.announce(clean))

    def test_the_payload_carries_no_address_even_when_the_check_does(self):
        """`hard_stop_check` reports mailboxes BY EMAIL ADDRESS, and
        `_status_payload` does not look inside a LIST - so forwarding the
        check rows would carry every stopped mailbox into the channel the
        whole team reads, past a guard that was watching strings.
        """
        loop = _loop()
        # Reserved domains only - `tests/test_fixture_hygiene` walks this
        # file's bytes and a real domain here would be a real leak in the
        # test that exists to stop one.
        leaky = ("HARD STOP bounce 4.0% (4/100) on sender@example.test "
                 "and a second on other@other.invalid")
        row = loop.announce(self.stop_assessment(leaky))
        blob = json.dumps(row["payload"], default=str)
        self.assertNotIn("@", blob,
                         "an address reached the status payload: %s" % blob)
        self.assertEqual(1, row["payload"]["checks_stopped"])
        self.assertIn("hard_stop_check", row["payload"]["stopped_checks"])

    def test_the_notification_was_not_swallowed_into_a_failed_row(self):
        """`notify.notify` cannot raise into its caller, so a refused payload
        becomes a FAILED row and silently stops being a notification. The
        only way to know the payload was accepted is to read the status
        back."""
        loop = _loop()
        row = loop.announce(self.stop_assessment("1 check stopped"))
        self.assertNotEqual(notify.FAILED, row["status"])
        self.assertIsNone(row["last_error"])

    def test_a_second_stop_in_a_new_hour_is_its_own_notification(self):
        """`notification_id` is deterministic, so without a per-pass
        discriminator the second STOP of the week would be a no-op against
        the first and the operator would be told once and never again."""
        import datetime
        loop = _loop()
        first = loop.announce(
            self.stop_assessment("s"),
            at=datetime.datetime(2026, 10, 16, 9, 0,
                                 tzinfo=datetime.timezone.utc))
        later = loop.announce(
            self.stop_assessment("s"),
            at=datetime.datetime(2026, 10, 16, 10, 0,
                                 tzinfo=datetime.timezone.utc))
        self.assertNotEqual(first["id"], later["id"])


class NothingHereTouchesAProvider(_Isolated):
    """A scheduled pass over injected checks, with the provider seam armed to
    raise. One call would fail this."""

    def test_a_full_pass_with_controls_makes_no_provider_call(self):
        check, fake = _fake("c", 0, "clean")
        loop = _loop()
        with mock.patch("src.providers.bison.scheduled_emails",
                        side_effect=AssertionError("provider called")), \
                mock.patch("src.providers.bison.campaign",
                           side_effect=AssertionError("provider called")):
            with _Patched(_install([fake])):
                out = loop.tick(every=100, now=1000, force=True,
                                checks=[check], journal=self.journal,
                                with_controls=True, announce_stop=False,
                                out=lambda t: None)
        self.assertTrue(out["controls_ok"])
        self.assertEqual(3, len(out["controls"]))


if __name__ == "__main__":
    unittest.main()
