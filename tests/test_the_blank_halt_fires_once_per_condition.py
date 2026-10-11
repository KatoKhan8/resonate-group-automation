"""The blank-content halt fires once per CONDITION, not once per cycle.

OPERATOR DECISION 2026-10-12.
`docs/state/OPERATOR-STOP-481-BLANK-HALT-2026-10-12.md`.

## The defect, measured, not imagined

EmailBison campaign 481 holds ONE scheduled row with an empty subject. The
watcher polls every 180s, the halt finds the row every time, and its response
is to pause the campaign - which was ALREADY paused, so nothing changed and
the next cycle found the same row again.

`work/provider-writes.jsonl`, counted 2026-10-12: **1410 rows of
`bison.pause` 481, every one `accepted`, by `bison_watch_loop`**, from
2026-09-25T16:04:38Z to 2026-10-11T23:11:52Z.

THE FIXTURE BELOW IS THAT ROW. Read out of the operator's own
`work/heartbeat/bison-481.json` at 2026-10-11T23:11:52Z:

    campaign 481   status paused   10 queue rows   0 sent
    pending blank  row 22364357  lead 203709  step 4730
                   status sending_paused   faults [("subject", "EMPTY")]

and reproduced here by running `emptyrender.scan` over a row of that shape
rather than by hand-writing the scan's output, so the fixture cannot drift
away from what the predicate actually produces. The body is a SHAPE - the live
row renders a real prospect's employer - because what these tests turn on is
which fields are empty, never whose name is in them.

## What each test holds down, and the control that proves it can fail

* same condition twice -> exactly ONE provider write attempt, and the second
  cycle still records the detection. CONTROL: the same two cycles with the
  memory thrown away between them write TWICE, which is the pre-fix behaviour
  and proves the counter can reach two.
* a NEW blank row -> fires AGAIN. This is the control on the idempotency
  itself: "never fires twice" would pass the test above and fail here.
* an un-pause with the same row still there -> fires AGAIN, because the
  campaign status is part of the condition key.
* a pause that REFUSES still alerts. The halt's docstring has been explicit
  since 2026-09-23 that the alert is sent either way; the idempotency must not
  have quietly made the alert conditional on the write. CONTROL: the same
  recorder is asserted EMPTY for a campaign with nothing pending, so a passing
  assertion is not an assertion against a recorder that always answers yes.
* the memory resolves to the MAIN checkout, and a RELATIVE answer from git is
  refused rather than resolved against the cwd.

NO PROVIDER CALLS AND NO NETWORK: `providerwrites.perform` is stubbed in every
test that reaches it, and the store is redirected with `store.use_directory`,
so the notification rows and heartbeats these write land in a temp directory.
The memory itself is addressed by `dir_path`, and the one test that does NOT
pass it asserts the production path rather than writing to it.
"""

import importlib.util
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import blankhalt, emptyrender, notify, providerwrites, store  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Campaign 481's blank row, as the provider recorded it. See the docstring.
BLANK_481 = {
    "id": 22364357, "sequence_step_id": 4730, "status": "sending_paused",
    "thread_reply": False, "email_subject": "",
    "email_body": "<p>Example Agency Ltd, the teams I work with that look "
                  "most like you tend to arrive at the same place.</p>",
    "lead": {"id": 203709},
}

#: A SECOND blank row, for the "a new blank row fires again" case. Same shape,
#: a different row and a different step, because that is what a new blank
#: actually looks like: the provider queues another message.
BLANK_SECOND = dict(BLANK_481, id=22364999, sequence_step_id=4731)


def load_watcher(name):
    """The watch loop, loaded from its path the way the fleet runs it."""
    path = os.path.join(ROOT, "scripts", "bison_watch_loop.py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(status, rows):
    """A watcher snapshot carrying the blank-content scan, as `snapshot` builds
    it: the scan runs on the queue rows already in hand.
    """
    return {"status": status, "queue_rows": len(rows), "sent_rows": 0,
            "blanks": emptyrender.scan(rows)}


class Harness(unittest.TestCase):
    """One temp store, one stubbed provider door, one call counter."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-blank-halt-once-")
        self.addCleanup(store.use_directory(self.tmp))
        self.assertTrue(
            store.queue_path().startswith(os.path.abspath(self.tmp)),
            "the store was not redirected, so this test would write the "
            "operator's real monitor state")
        self.memory = os.path.join(self.tmp, "blank-halt")
        self.watcher = load_watcher("blw_once_%d" % id(self))
        self.writes = []
        self.real_perform = providerwrites.perform
        self.addCleanup(self._restore_perform)
        providerwrites.perform = self._perform
        self.lines = []

    def _restore_perform(self):
        providerwrites.perform = self.real_perform

    def _perform(self, operation, **kw):
        """Stand in for the one door. NOTHING leaves this process.

        Records the attempt - which is what "exactly one provider write" is
        counted on - and answers the way `perform` does on success, with the
        read-back the halt keys its memory on.
        """
        self.writes.append({"operation": operation,
                            "campaign": kw.get("campaign"),
                            "step": kw.get("step")})
        return {"operation": operation, "class": "accepted",
                "readback": {"status": "paused"}}

    def refusing_perform(self, exc=None):
        """A door that refuses. The killswitch and the ownership guard both
        arrive here as an exception out of `perform`."""
        def _refuse(operation, **kw):
            self.writes.append({"operation": operation,
                                "campaign": kw.get("campaign")})
            raise (exc or providerwrites.WriteRefused(
                "no RESONATE_PROVIDER_WRITES and no allow_writes() scope"))
        return _refuse

    def cycle(self, status="paused", rows=(BLANK_481,), memory=None):
        """One poll of the loop's halt, against this fixture."""
        return self.watcher._halt_on_blank_content(
            481, snapshot(status, list(rows)), self.lines.append,
            dir_path=self.memory if memory is None else memory)

    def alerts(self):
        """The blank-content notifications planned, from the isolated store."""
        return [r for r in notify.load()
                if r.get("type") == notify.CAMPAIGN_BLANK_CONTENT]

    def memory_row(self, campaign=481):
        return blankhalt.load(campaign, self.memory)


class TheSameConditionIsAnsweredOnce(Harness):
    """The 481 loop, as a test. 1410 writes become one."""

    def test_the_same_condition_twice_is_one_provider_write(self):
        self.assertTrue(self.cycle())
        self.assertTrue(self.cycle())
        self.assertEqual(
            len(self.writes), 1,
            "the same condition was written to the provider twice: %r"
            % (self.writes,))
        self.assertEqual(self.writes[0]["operation"],
                         providerwrites.EMAIL_PAUSE)
        self.assertEqual(self.writes[0]["step"], "blank_content_halt")

    def test_the_second_cycle_still_records_the_detection(self):
        self.cycle()
        first = dict(self.memory_row())
        self.cycle()
        again = self.memory_row()
        self.assertEqual(again["condition"], first["condition"])
        self.assertEqual(first["seen"], 1)
        self.assertEqual(again["seen"], 2, "the repeat cycle recorded nothing")
        self.assertEqual(again["fired_at"], first["fired_at"],
                         "a repeat must not look like a second firing")
        self.assertEqual(again["pending_rows"], 1)

    def test_the_second_cycle_reports_the_fault_in_the_heartbeat(self):
        """Still DETECTING is reported where a per-poll fact belongs.

        The event log gets one line per condition on purpose, so the signal
        that says "the blank row is still there, right now" has to be in the
        file that is rewritten every poll.
        """
        self.cycle()
        self.cycle()
        beat = [b for b in watch_beats() if b.get("campaign") == 481]
        self.assertEqual(len(beat), 1)
        note = str(beat[0].get("note"))
        self.assertIn("STILL PRESENT", note)
        self.assertIn("22364357", str(beat[0]["state"]["blanks"]),
                      "the heartbeat lost the state it is read for")

    def test_the_second_cycle_does_not_re_alert(self):
        self.cycle()
        self.cycle()
        self.assertEqual(len(self.alerts()), 1,
                         "the same condition raised two CRITICALs")

    def test_the_second_cycle_emits_no_second_halt_line(self):
        self.cycle()
        self.cycle()
        halts = [l for l in self.lines if l.startswith("BLANK-CONTENT 481")]
        self.assertEqual(len(halts), 1, self.lines)

    # ----------------------------------------------------- positive control

    def test_CONTROL_without_the_memory_the_same_condition_writes_twice(self):
        """The pre-fix behaviour, reproduced, and the proof this can fail.

        Two cycles of the IDENTICAL condition, each given its own empty
        memory - which is exactly what a per-worktree or per-restart memory
        would be - write to the provider twice. If this ever reports one, the
        counter above is measuring nothing and the test that asserts ONE is
        green for the wrong reason.
        """
        self.cycle(memory=os.path.join(self.tmp, "one"))
        self.cycle(memory=os.path.join(self.tmp, "two"))
        self.assertEqual(len(self.writes), 2)

    def test_CONTROL_a_clean_campaign_neither_writes_nor_alerts(self):
        """And the recorders can be empty, so a non-empty one means something."""
        clean = dict(BLANK_481, email_subject="A real subject")
        self.assertFalse(self.cycle(rows=[clean]))
        self.assertEqual(self.writes, [])
        self.assertEqual(self.alerts(), [])
        self.assertEqual(self.memory_row(), {})


class ANewConditionFiresAgain(Harness):
    """The control on the idempotency itself: it is not "never twice"."""

    def test_a_new_blank_row_fires_again(self):
        self.assertTrue(self.cycle())
        self.assertTrue(self.cycle(rows=[BLANK_481, BLANK_SECOND]))
        self.assertEqual(
            len(self.writes), 2,
            "a NEW blank row did not halt - the memory is suppressing a "
            "condition nobody has responded to")
        self.assertEqual(len(self.alerts()), 2)

    def test_the_new_row_is_a_different_condition_key(self):
        one = blankhalt.condition_key(
            481, "paused", emptyrender.scan([BLANK_481])["pending"])
        two = blankhalt.condition_key(
            481, "paused",
            emptyrender.scan([BLANK_481, BLANK_SECOND])["pending"])
        self.assertNotEqual(one, two)

    def test_an_unpause_with_the_same_row_fires_again(self):
        """The campaign status is in the key, and this is why.

        A blank row on a PAUSED campaign is contained and the pause is a
        no-op. The same row on an ACTIVE campaign is about to be sent, and the
        pause is a real action that must be taken.
        """
        self.cycle(status="paused")
        self.cycle(status="active")
        self.assertEqual(len(self.writes), 2, self.writes)

    def test_a_row_that_gains_a_fault_fires_again(self):
        """`subject/EMPTY` is not `subject/EMPTY + body/EMPTY`."""
        self.cycle()
        worse = dict(BLANK_481, email_body="<p></p>")
        self.cycle(rows=[worse])
        self.assertEqual(len(self.writes), 2)

    def test_a_successful_pause_does_not_make_itself_a_new_condition(self):
        """The memory is keyed on the status the pause LEAVES.

        An ACTIVE campaign is paused by the first cycle, so the second cycle
        reads `paused` - and keying the memory on the status that was OBSERVED
        would make that a new condition and buy one extra no-op pause per
        incident.
        """
        self.cycle(status="active")
        self.cycle(status="paused")
        self.assertEqual(len(self.writes), 1, self.writes)

    def test_the_fingerprint_ignores_the_order_the_provider_returns(self):
        self.assertEqual(
            blankhalt.fingerprint(
                emptyrender.scan([BLANK_481, BLANK_SECOND])["pending"]),
            blankhalt.fingerprint(
                emptyrender.scan([BLANK_SECOND, BLANK_481])["pending"]))


class ARefusedPauseStillAlerts(Harness):
    """The property that was explicit before this change and survives it."""

    def test_a_refused_pause_still_alerts(self):
        providerwrites.perform = self.refusing_perform()
        self.assertTrue(self.cycle())
        self.assertEqual(len(self.writes), 1, "the pause was never attempted")
        alerts = self.alerts()
        self.assertEqual(len(alerts), 1, "a refused pause swallowed the alert")
        self.assertTrue(
            str(alerts[0]["payload"]["campaign_paused"]).startswith("NO"),
            alerts[0]["payload"])
        self.assertTrue(any(l.startswith("BLANK-CONTENT-HALT-REFUSED")
                            for l in self.lines), self.lines)

    def test_a_refused_pause_is_not_retried_every_cycle_either(self):
        """Once per condition applies to the ATTEMPT, not to the success.

        A refusal that re-attempted every 180s would be the same loop with a
        different outcome word in the ledger.
        """
        providerwrites.perform = self.refusing_perform()
        self.cycle()
        self.cycle()
        self.assertEqual(len(self.writes), 1, self.writes)
        self.assertEqual(len(self.alerts()), 1)

    def test_an_alert_that_recorded_nothing_is_retried_without_a_pause(self):
        """The two halves of the response are remembered separately.

        If the notification layer recorded NOTHING - not even a failure row -
        the finding is not in any durable place, so the next cycle must alert
        again. It must not pause again: the campaign was already halted for
        this very condition.
        """
        real = notify.notify
        self.addCleanup(setattr, notify, "notify", real)
        notify.notify = lambda *_a, **_k: None
        self.cycle()
        self.assertEqual(len(self.writes), 1)
        self.assertFalse(self.memory_row()["alerted"])
        self.assertTrue(any(l.startswith("BLANK-CONTENT-ALERT-NOT-PLANNED")
                            for l in self.lines), self.lines)

        notify.notify = real
        self.cycle()
        self.assertEqual(len(self.writes), 1,
                         "retrying the ALERT re-paused the campaign")
        self.assertEqual(len(self.alerts()), 1)
        self.assertTrue(self.memory_row()["alerted"])
        self.assertTrue(any(l.startswith("BLANK-CONTENT-ALERT-RETRY")
                            for l in self.lines), self.lines)

    def test_the_alert_names_the_campaign_and_the_condition(self):
        """One notification row per condition rather than one FOREVER.

        MEASURED 2026-10-12: this call passed no `ids`, so every blank-content
        finding there will ever be shared one notification id. The operator's
        store holds exactly one `campaign_blank_content` row - raised for
        campaign 497 on 2026-09-23 - and 481's 1410 firings all collapsed onto
        it and planned nothing.
        """
        self.cycle()
        ids = self.alerts()[0]["ids"]
        self.assertEqual(ids["campaign_id"], "481")
        self.assertTrue(ids["condition"].startswith("481|paused|"))

    def test_a_different_campaign_gets_its_own_alert(self):
        """What the missing ids cost: a second campaign could never alert."""
        self.cycle()
        self.watcher._halt_on_blank_content(
            497, snapshot("active", [BLANK_481]), self.lines.append,
            dir_path=self.memory)
        self.assertEqual(len(self.alerts()), 2)


class TheMemoryIsNotPerWorktree(unittest.TestCase):
    """The reason this is not in `work/` beside the queue.

    `work/` is gitignored, so every worktree has its own and a memory kept
    there would be empty after any restart from another tree - which would
    restore the 1410-write loop while looking fixed.
    """

    def setUp(self):
        store.reset_main_work_cache()
        self.addCleanup(store.reset_main_work_cache)

    def test_the_memory_resolves_to_the_main_checkout(self):
        main = store.main_checkout_work()
        self.assertIsNotNone(main, "git could not answer from this tree")
        self.assertTrue(os.path.isabs(main))
        self.assertEqual(blankhalt.directory(),
                         os.path.join(main, blankhalt.DIRNAME))
        self.assertFalse(blankhalt.is_tree_local())

    def test_it_is_the_same_answer_from_a_worktree_as_from_the_main_tree(self):
        """The property that matters, asserted where it can actually fail.

        This suite runs from a worktree in the merge gate, so
        `store.PRODUCTION_WORK` - which resolves against the tree this module
        was imported from - is the WRONG answer, and the test says so out loud
        when the two differ.
        """
        this_tree = os.path.abspath(store.PRODUCTION_WORK)
        resolved = os.path.dirname(blankhalt.directory())
        if os.path.normcase(this_tree) != os.path.normcase(resolved):
            self.assertNotIn(".claude", resolved,
                             "the memory resolved into a worktree")
        self.assertEqual(os.path.basename(resolved), "work")

    def answer_git(self, value):
        """Make `git rev-parse` answer `value`, at the boundary it answers at.

        The refusal under test lives where the ANSWER ARRIVES -
        `store._git_common_dir` - so it has to be exercised through that
        subprocess call and not by stubbing the function that contains it.
        Stubbing `_git_common_dir` itself would have proved the opposite of
        what it looked like: `main_checkout_work` calls `abspath` on whatever
        that returns, so a stub handing it a relative path IS resolved against
        the cwd. Found by this test failing the first time it was run.

        `store.subprocess` is rebound, not the stdlib module, so nothing
        outside this module's view of it is touched.
        """
        real = store.subprocess
        self.addCleanup(setattr, store, "subprocess", real)

        class _Git:
            @staticmethod
            def run(*_a, **_k):
                # The trailing newline is what git actually emits, and
                # `_git_common_dir` strips it. A stub that answered without
                # one would be testing a cleaner world than the real reader
                # lives in.
                return types.SimpleNamespace(
                    returncode=0, stdout=value + os.linesep, stderr="")

        store.subprocess = _Git
        store.reset_main_work_cache()

    def test_a_relative_answer_from_git_is_refused(self):
        """`abspath` on a relative answer would resolve it against the cwd -
        from a worktree, that worktree - which is the per-tree memory this
        resolution exists to avoid. So a relative answer is refused.
        """
        self.answer_git(os.path.join("relative", ".git"))
        self.assertIsNone(store._git_common_dir())
        self.assertIsNone(store.main_checkout_work())
        self.assertTrue(blankhalt.is_tree_local())
        self.assertEqual(blankhalt.directory(),
                         os.path.join(store.PRODUCTION_WORK,
                                      blankhalt.DIRNAME))

    def test_CONTROL_an_absolute_answer_is_used(self):
        """So the refusal above is not a reader that always answers None."""
        invented = os.path.join(os.path.abspath(os.sep), "elsewhere", ".git")
        self.answer_git(invented)
        self.assertEqual(store._git_common_dir(), invented)
        self.assertEqual(
            blankhalt.directory(),
            os.path.join(os.path.dirname(invented), "work",
                         blankhalt.DIRNAME))

    def test_one_file_per_campaign(self):
        """Nine of these watchers run at once, one process each. Two processes
        appending to one file under `work/` lose rows on Windows - measured in
        `src/watchsink.py`, 193 lines where 240 were written.
        """
        self.assertNotEqual(blankhalt.path(481), blankhalt.path(489))
        self.assertTrue(blankhalt.path(481).endswith("bison-481.json"))
        with self.assertRaises(ValueError):
            blankhalt.path("")


class TheMemoryCannotTurnTheControlOff(Harness):
    """Every failure of the memory makes the halt LOUDER, never quieter."""

    def test_an_unreadable_memory_fires(self):
        os.makedirs(self.memory, exist_ok=True)
        with open(blankhalt.path(481, self.memory), "w",
                  encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertTrue(self.cycle())
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(len(self.alerts()), 1)

    def test_a_memory_that_cannot_be_written_fires_again_and_says_so(self):
        """A directory where the file belongs. The write fails every cycle, so
        every cycle halts and alerts - noisy, never silent.
        """
        os.makedirs(blankhalt.path(481, self.memory), exist_ok=True)
        self.assertTrue(self.cycle())
        self.assertTrue(any(l.startswith("BLANK-HALT-MEMORY-UNWRITABLE")
                            for l in self.lines), self.lines)
        self.cycle()
        self.assertEqual(len(self.writes), 2)

    def test_the_memory_carries_no_prospect_identifier(self):
        """It is read by whoever is debugging the monitor. A row id and a step
        id are provider bookkeeping; a lead id is a person.
        """
        self.cycle()
        self.assertNotIn("203709", str(self.memory_row()))

    def test_the_halt_still_refuses_to_act_on_an_already_sent_blank(self):
        """Unchanged, and asserted here because this change must not have
        widened WHICH rows halt."""
        sent = dict(BLANK_481, status="sent")
        self.assertFalse(self.cycle(rows=[sent]))
        self.assertEqual(self.writes, [])

    def test_an_unreadable_queue_is_not_a_clean_bill_of_health(self):
        """`blanks` is None when the queue could not be read. Nothing is
        recorded and nothing is suppressed."""
        self.assertFalse(self.watcher._halt_on_blank_content(
            481, {"status": "paused", "blanks": None}, self.lines.append,
            dir_path=self.memory))
        self.assertEqual(self.memory_row(), {})


def watch_beats():
    """The heartbeats written into the isolated store."""
    from src import watchsink
    return watchsink.heartbeats()


if __name__ == "__main__":
    unittest.main()
