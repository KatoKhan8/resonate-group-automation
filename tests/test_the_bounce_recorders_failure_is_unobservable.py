#!/usr/bin/env python3
"""TASK-0220. The bounce recorder can fail forever and nothing looks wrong.

## THE CHAIN, AND THE TWO SILENCES ON IT

`scripts/bison_watch_loop.py` builds the only production caller of
`leadobserve.record_bounces`:

    scripts/bison_watch_loop.py:641   on_queue = _bounce_recorder(
    scripts/bison_watch_loop.py:647   current = snapshot(
    scripts/bison_watch_loop.py:189   on_queue(queue)
    scripts/bison_watch_loop.py:598   out = leadobserve.record_bounces(
    scripts/bison_watch_loop.py:601   emit(f"BOUNCE-RECORD-FAILED ...

Every line above was opened and read in this tree; 641 is measured here and
not carried over, which matters because TASK-0180 wrote 643 and TASK-0210
could not verify it - that task's boundary forbade reading a monitor loop and
this one permits it.

On failure `record()` emits one line and RETURNS. `snapshot()` finishes
normally, so the loop reaches its unconditional beat:

    scripts/bison_watch_loop.py:663   watchsink.beat("bison", ...,
                                                    state=current)

with **no note**. And `supervisor.witnesses()` reads a heartbeat's `epoch`
and the pid and nothing else, so the watcher reports **UP**.

## WHAT IS PINNED HERE

* **C1** a planted READER of `BOUNCE-RECORD-FAILED` is found by the same
  search that reports zero readers in the estate - and the same search
  narrowed to `src/` does NOT find it, which is how a search that can see
  nothing is told from a codebase with nothing to see
* **C2** with `record_bounces` raising, the only file that changes is the
  append-only event log that no production reader consults, and the beat
  still supports UP
* **C3** the proposed emission makes C2's assertion fail - so C2's detector
  can detect something - **and the supervisor's verdict is STILL UP**, which
  is the finding: nothing reads a note either

Nothing here runs the watcher loop, calls a provider, or writes outside a
temporary directory. `confirm_email_touches` is never called in any form.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import leadobserve, supervisor, watchsink               # noqa: E402

LOOP = os.path.join(ROOT, "scripts", "bison_watch_loop.py")
NEEDLE = "BOUNCE-RECORD-FAILED"


def load_loop():
    """Import the watch loop WITHOUT running it.

    `load_env` is called inside `main`, not at import, and the module's only
    top-level statements are imports and two constants - checked by reading
    it. So an import reaches no credential file and no provider.
    """
    spec = importlib.util.spec_from_file_location("_bison_watch_loop", LOOP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bwl = load_loop()


def search(roots, needle=NEEDLE, suffixes=(".py", ".md", ".txt", ".json",
                                           ".jsonl", ".cfg", ".toml", ".yml",
                                           ".service", ".timer", ".sh")):
    """Every line holding `needle` under `roots`. One place, so C1 can blind
    it.

    Binary files and `.git` are skipped and that is REPORTED by the caller
    rather than silently assumed harmless - a stale `.pyc` holding the string
    is a fact about a build, not a reader.
    """
    hits = []
    for root in roots:
        if os.path.isfile(root):
            walk = [(os.path.dirname(root), [], [os.path.basename(root)])]
        else:
            walk = os.walk(root)
        for folder, dirs, files in walk:
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for name in files:
                if suffixes and not name.endswith(tuple(suffixes)):
                    continue
                path = os.path.join(folder, name)
                try:
                    with io.open(path, encoding="utf-8",
                                 errors="replace") as handle:
                        for number, line in enumerate(handle, 1):
                            if needle in line:
                                hits.append((path, number, line.strip()))
                except OSError:
                    continue
    return hits


class C1ThePlantedReaderIsFound(unittest.TestCase):
    """Failure family 5: an instrument that sees nothing reports clean."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-0220-reader-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.planted = os.path.join(self.tmp, "fixture_reader.py")
        with io.open(self.planted, "w", encoding="utf-8",
                     newline="\n") as handle:
            handle.write(
                "# A PLANTED READER, for TASK-0220 control 1.\n"
                "def halt_if_the_recorder_failed(lines):\n"
                "    for line in lines:\n"
                "        if \"%s\" in line:\n"
                "            return \"HALT\"\n"
                "    return None\n" % NEEDLE)

    def test_the_planted_reader_is_found(self):
        hits = search([self.tmp])
        self.assertEqual(1, len(hits), hits)
        self.assertEqual(self.planted, hits[0][0])

    def test_the_same_search_narrowed_to_src_does_not_find_it(self):
        """C1 PROVEN ABLE TO FAIL. The fixture does not sit in `src/`, so a
        search narrowed there finds nothing - which is exactly what a broken
        search looks like, and the only way to tell them apart is to have
        one planted reader whose absence is a measurement."""
        narrowed = search([os.path.join(ROOT, "src")])
        self.assertEqual([], [h for h in narrowed if h[0] == self.planted])

    def test_the_estate_search_finds_the_writer_and_no_reader(self):
        """The §1 answer, re-measured by the same function the controls
        blind.

        THE SEARCH FINDS ITSELF, and that is excluded by name rather than by
        a filter that might also exclude a real reader: this file quotes the
        writer line in its own docstring, and the first version of this test
        counted that quotation as a second writer.
        """
        hits = search([os.path.join(ROOT, "src"),
                       os.path.join(ROOT, "scripts"),
                       os.path.join(ROOT, "tests")])
        mine = os.path.abspath(__file__)
        others = [h for h in hits if os.path.abspath(h[0]) != mine]
        # ONE hit in the whole of src/, scripts/ and tests/ once this file is
        # set aside, and it is the writer.
        self.assertEqual(1, len(others), others)
        self.assertTrue(others[0][0].endswith("bison_watch_loop.py"))
        self.assertEqual(601, others[0][1])
        self.assertIn("emit(", others[0][2])
        # AND NOTHING IN `src/` AT ALL, which is where a gate would live.
        self.assertEqual([], search([os.path.join(ROOT, "src")]))


class C2APlantedFailureIsInvisible(unittest.TestCase):
    """`record_bounces` raises. Nothing a reader consults moves."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-0220-fail-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state = os.path.join(self.tmp, "work")
        os.makedirs(self.state, exist_ok=True)
        self._queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = os.path.join(self.state, "queue.jsonl")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._queue

    def expected_changes(self):
        """The two paths this poll touches, RESOLVED not typed.

        `heartbeat/` versus `heartbeats/` cost one red test, and the
        separator is a backslash here - so both come from the module that
        owns them.
        """
        return sorted(
            os.path.relpath(p, self.state) for p in
            (watchsink.heartbeat_path("bison", 487),
             watchsink.events_path("bison", 487)))

    def beat_path(self):
        return watchsink.heartbeat_path("bison", 487)

    def files(self):
        """Every file under the fixture, with size and mtime_ns."""
        out = {}
        for folder, _dirs, names in os.walk(self.state):
            for name in names:
                path = os.path.join(folder, name)
                stat = os.stat(path)
                out[os.path.relpath(path, self.state)] = (stat.st_size,
                                                          stat.st_mtime_ns)
        return out

    def run_one_poll(self, recorder=None):
        """One poll's worth of the loop's own code, with the recorder failing.

        NOT the loop: no `while True`, no sleep, no provider read. The two
        things the loop does per poll, in the loop's order - the recorder it
        built (reached from inside `snapshot` at `:189`), then the
        unconditional beat at `:663`.

        THE ORDER IS THE WHOLE POINT. `watchsink.beat` rewrites the
        heartbeat file, so anything the recorder put in a beat of its own is
        gone by the time this returns. That is what refuted the first
        version of the proposal.
        """
        emitted = []
        emit = watchsink.emitter("bison", campaign=487)

        def capture(line):
            emitted.append(line)
            emit(line)

        def boom(*a, **kw):
            raise RuntimeError("planted: the provider read failed")

        record = (recorder or bwl._bounce_recorder)(487, capture)
        with mock.patch.object(leadobserve, "record_bounces", boom):
            record([{"scheduled_email_id": 1, "state": "bounced"}])
        state = {"status": "paused", "leads": 10, "emails_sent": 6,
                 "queue_rows": 0, "sent_rows": 0, "bounced": 0, "replied": 0}
        # THE LOOP'S OWN BEAT, with the note the proposal would have it
        # carry. `getattr` because the unmodified recorder has no holder -
        # which is exactly the difference the proposal makes.
        failures = list(getattr(record, "failures", ()))
        watchsink.beat("bison", campaign=487, state=state,
                       note=(failures[-1] if failures else None))
        return emitted

    def test_the_failure_is_emitted_and_swallowed(self):
        emitted = self.run_one_poll()
        self.assertEqual(1, len(emitted))
        self.assertTrue(emitted[0].startswith(NEEDLE))
        self.assertIn("RuntimeError", emitted[0])

    def test_the_only_file_that_changes_is_the_log_nobody_reads(self):
        """THE BRIEF ASKED FOR "no file changes" AND THAT IS NOT QUITE TRUE -
        so the assertion is the true one, which is stronger. The event log
        DOES change: one appended line. Nothing in `src/` or `scripts/`
        reads it (`watchsink.events()` has no production caller, and
        `check_readback` reads only the LAST line into a display field). The
        set of files that changed is exactly that log plus the beat, and the
        beat's content carries no sign of the failure - which the next test
        measures."""
        before = self.files()
        self.run_one_poll()
        after = self.files()
        changed = sorted(k for k in set(before) | set(after)
                         if before.get(k) != after.get(k))
        self.assertEqual(self.expected_changes(), changed)

    def test_the_beat_carries_no_note_and_still_supports_up(self):
        """The whole defect in one assertion. `witnesses()` reads `epoch` and
        the pid; a beat written after a failed recorder is indistinguishable
        from one written after a clean poll."""
        self.run_one_poll()
        beat = json.load(io.open(self.beat_path(), encoding="utf-8"))
        self.assertNotIn("note", beat)
        self.assertEqual(487, beat["campaign"])
        verdict = self.verdict_for(beat)
        self.assertEqual("UP", verdict["status"], verdict)

    def verdict_for(self, beat, state_age=0):
        """`supervisor.witnesses()` against a planted monitor and this beat.

        The pid in the beat is this process, which IS alive, and the state
        file is written now - so both witnesses are as favourable as they
        can be. That is the point: the failure cannot make this verdict
        worse, because nothing in it reads what failed.

        `state_age` backdates the state file. Without it a stale beat reads
        STARTING - "process up, no beat yet, started recently" - which is
        right, and was not the verdict the control first expected.
        """
        state_dir = os.path.join(self.tmp, "monitor-state")
        os.makedirs(state_dir, exist_ok=True)
        state_file = os.path.join(state_dir, "bison_watch_487.json")
        with io.open(state_file, "w", encoding="utf-8",
                     newline="\n") as handle:
            json.dump({"pid": os.getpid()}, handle)
        if state_age:
            when = time.time() - state_age
            os.utime(state_file, (when, when))
        # `module` IS REQUIRED - `witnesses()` reads `mon["module"]` when it
        # builds its row, and a monitor dict without it raises KeyError. The
        # value is the one `supervisor`'s own table uses at :230.
        mon = {"name": "bison_watch_487", "interval": 180,
               "module": "scripts.bison_watch_loop",
               "heartbeat": {"source": "bison", "campaign": 487}}
        return supervisor.witnesses(mon, booted_at=time.time() - 3600,
                                    state_dir=state_dir)

    def test_the_control_on_that_verdict(self):
        """Without this, UP above could be a verdict that is always UP. A
        beat older than 2x the interval must read DOWN, so the UP is about
        the beat being fresh and not about the check being vacuous."""
        self.run_one_poll()
        path = self.beat_path()
        beat = json.load(io.open(path, encoding="utf-8"))
        beat["epoch"] = int(time.time()) - 5000
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(beat, handle)
        # 1200s: older than the 180s interval, so NOT "started recently",
        # and younger than the planted 3600s boot, so the state file does
        # not predate the boot - which reads UNKNOWN, measured. Both ends of
        # that window matter and neither was obvious.
        verdict = self.verdict_for(beat, state_age=1200)
        # THE WITNESS, AND THEN THE VERDICT IT PRODUCES. Asserting only the
        # verdict would pass if a different branch answered.
        self.assertFalse(verdict["witness_heartbeat"], verdict)
        self.assertEqual("DOWN", verdict["status"], verdict)
        self.assertIn("no fresh beat", verdict["why"])


class C3TheProposalMakesItVisibleAndStillChangesNoVerdict(
        C2APlantedFailureIsInvisible):
    """The proposed emission, IN THE FIXTURE ONLY. The monitor loop is not
    touched - this task may read it and may not change it."""

    def proposed_recorder(self, provider_id, emit):
        """`_bounce_recorder` with the one proposed line added.

        The proposal: on failure, BEAT WITH A NOTE, exactly as the
        READ-ERROR path at `scripts/bison_watch_loop.py:656` already does -
        *"Beat anyway, with the reason. Alive-and-blind is a different
        incident from alive-and-nothing-changed and must not read as it."*
        """
        # THE REAL RECORDER SWALLOWS, so the proposal cannot be expressed by
        # catching its exception from outside - there is none to catch. It
        # has to observe the EMISSION.
        #
        # AND IT CANNOT BEAT ITSELF. The first version of this did, and C3
        # measured the note gone: the recorder runs inside `snapshot` at
        # `:189` and the loop beats unconditionally at `:663`, and
        # `watchsink.beat` REWRITES the file. So the recorder records its
        # failure in a holder and the LOOP'S OWN BEAT carries it - which is
        # the two-line change proposed, in the loop, where it belongs.
        def proposed(queue):
            seen = []

            def watched_emit(line):
                seen.append(line)
                emit(line)
            inner = bwl._bounce_recorder(provider_id, watched_emit)
            inner(queue)
            proposed.failures = [line for line in seen
                                 if line.startswith(NEEDLE)]
        proposed.failures = []
        return proposed

    def test_the_proposal_makes_c2s_assertion_fail(self):
        """C3. The beat now carries the note, so the assertion in
        `test_the_beat_carries_no_note_and_still_supports_up` is false - and
        a detector that can be made to fire is a detector.

        THIS TEST FAILED ON ITS FIRST RUN and the proposal was what was
        wrong. See `proposed_recorder`: a note written by the recorder is
        overwritten by the loop's own beat 0 lines later. The repair is a
        holder plus a `note=` at `:663`.
        """
        self.run_one_poll(recorder=self.proposed_recorder)
        beat = json.load(io.open(self.beat_path(), encoding="utf-8"))
        self.assertIn("note", beat)
        self.assertTrue(beat["note"].startswith(NEEDLE))

    def test_and_the_supervisor_still_says_up_which_is_the_finding(self):
        """THE HALF THE BRIEF DID NOT ASK FOR. `witnesses()` reads `epoch`
        and the pid. A note changes no verdict anywhere, so the emission
        half of the repair makes the failure LEGIBLE TO A HUMAN WHO LOOKS
        and does not make it visible to the system. The second half of the
        recommendation exists for this reason."""
        self.run_one_poll(recorder=self.proposed_recorder)
        beat = json.load(io.open(self.beat_path(), encoding="utf-8"))
        self.assertIn("note", beat)
        self.assertEqual("UP", self.verdict_for(beat)["status"])

    # The two inherited tests that must now FAIL are overridden to assert the
    # opposite, so this class does not silently re-run C2's assertions
    # against C3's fixture and report them as passing.
    def test_the_beat_carries_no_note_and_still_supports_up(self):
        self.skipTest("C2's assertion; C3 asserts its inverse above")

    def test_the_only_file_that_changes_is_the_log_nobody_reads(self):
        self.skipTest("C2's assertion; the same files change under C3")

    def test_the_failure_is_emitted_and_swallowed(self):
        """Still true under the proposal, and it has to be: the repair adds
        a signal, it does not change what the recorder does on failure.
        That distinction is what makes it an emission change rather than a
        gate."""
        emitted = self.run_one_poll(recorder=self.proposed_recorder)
        self.assertTrue(any(line.startswith(NEEDLE) for line in emitted))


class NothingReadsTheNoteOrTheLog(unittest.TestCase):
    """§1's "a grep is not a read", asserted on the code rather than argued."""

    def test_the_supervisors_verdict_never_reads_a_note(self):
        import inspect
        source = inspect.getsource(supervisor.witnesses)
        self.assertNotIn("note", source)
        self.assertIn("epoch", source)

    def test_watchsink_events_has_no_production_caller(self):
        """The only reader of the event log, and only tests call it."""
        callers = search([os.path.join(ROOT, "src"),
                          os.path.join(ROOT, "scripts")],
                         needle="watchsink.events(")
        self.assertEqual([], callers)

    def test_the_one_production_reader_of_the_log_takes_only_the_last_line(
            self):
        """`scripts/qa/check_readback.py` reads the log's LAST line into a
        display field. Two reasons it cannot see this failure: it searches
        for nothing, and one later emission pushes the line off the end."""
        path = os.path.join(ROOT, "scripts", "qa", "check_readback.py")
        text = io.open(path, encoding="utf-8").read()
        self.assertIn("return lines[-1].strip() if lines else None", text)
        self.assertIn('"log_last_line": log_last_line', text)
        self.assertNotIn(NEEDLE, text)

    def test_the_read_error_path_does_beat_with_a_note(self):
        """TASK-0180's asymmetry, confirmed and quoted - and now bounded:
        the note is real, and no verdict reads it."""
        text = io.open(LOOP, encoding="utf-8").read()
        self.assertIn('note=f"READ-ERROR {errors}x {type(exc).__name__}"',
                      text)
        self.assertIn("Beat anyway, with the reason", text)

    def test_the_cited_lines_are_the_lines(self):
        """Measured, not typed. TASK-0180 wrote 643 for the first of these
        and it is 641; TASK-0210 could not check it because its boundary
        forbade reading a monitor loop, and this task's permits it."""
        lines = io.open(LOOP, encoding="utf-8").read().split("\n")
        self.assertIn("on_queue = _bounce_recorder(watched, emit)", lines[640])
        self.assertIn("current = snapshot(watched, on_queue=on_queue)",
                      lines[646])
        self.assertIn("leadobserve.record_bounces(provider_id", lines[597])
        self.assertIn(NEEDLE, lines[600])
        self.assertIn(
            'watchsink.beat("bison", campaign=watched, state=current)',
            lines[662])


class AnUnrecordedBounceReadsCleanNotUnknown(unittest.TestCase):
    """§3's direction, measured on the gate that reads what the recorder
    writes. This is the one that can reach a prospect."""

    def test_the_bounce_gate_answers_false_when_the_event_is_absent(self):
        from src import channels, events
        contact = {"key": "c-1", "email": "someone@example.invalid"}
        recorded = {"events": [{"type": events.EMAIL_BOUNCED,
                                "contact": "c-1"}]}
        self.assertTrue(channels._bounced(recorded, contact))
        # AND THE DIRECTION OF THE ERROR: with the event missing - which is
        # exactly what an unrecorded bounce looks like - the gate says "has
        # not bounced", not "I do not know".
        self.assertFalse(channels._bounced({"events": []}, contact))
        self.assertFalse(channels._bounced({}, contact))

    def test_the_preflight_rule_that_reads_it_is_one_of_the_queue_rules(self):
        from src import preflight
        rule = [r for r in preflight.RULES
                if r["name"] == "bounce_history"][0]
        self.assertEqual(("queue",), rule["needs"])
        self.assertTrue(rule["needs_record"])
        self.assertIn("channels._bounced", rule["decides"])
        # So in a main-checkout run, with the queue POPULATED and the record
        # supplied, this rule IS asked - and an unrecorded bounce makes it
        # answer PASS rather than UNKNOWN.
        self.assertIn("bounce_history", preflight.RULE_NAMES)


if __name__ == "__main__":
    unittest.main()
