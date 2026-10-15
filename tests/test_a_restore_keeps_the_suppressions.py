"""TASK-0050 - a restore that loses suppression reads as a clean estate.

The 0040 audit of the backup path closed with one gap named as the cheapest
thing on the page to fix:

    no drill of any kind asserts that restored SUPPRESSION state is loadable.
    A restore that loses suppression reads as a clean estate and re-contacts
    people who opted out.

This file is the assertion. `scripts/suppression_restore_drill.py` is the
drill; everything here either exercises it on a fixture estate or proves it
can go red - which is the half that matters, because four controls in this
repository have already been found unable to fail and the usual mechanism is
a guard nobody called.

## THREE MUTATIONS, AND THEY ARE NOT THE SAME MUTATION

  1. The opt-out row is dropped from the restored queue. The crude loss.
  2. The row comes back and its `unsubscribed` flag does not. Same file
     count, same member names, and a person who asked to be left alone is
     ALLOW again. This is the shape of the failure the task names.
  3. `agency-dnc.jsonl` does not come back while `queue.jsonl` does. The
     queue parses, its record count is unchanged, both of its histograms are
     unchanged - so `scripts/restore_drill.py` passes this - and somebody who
     told Resonate directly to stop is contactable again.

The fourth test in that group is the control for the comparison itself: a
mutation that leaves the BLOCK COUNT identical and changes WHO is in it. A
count-based drill passes it. This one names both rows.

## NO PRODUCTION STATE

Every test builds its own estate under `tempfile.mkdtemp` and passes it as
`--state-dir`. Nothing reads or writes the real `work/`, and one test asserts
that the drill refuses a source directory that is production state.
"""
import copy
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import agencydnc, store, suppression       # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "suppression_restore_drill.py")


def _drill_module():
    """The drill imported, so its functions can be asserted on directly.

    The command line is exercised too - `TheDrillRunsFromTheCommandLine` -
    but a report object is what the comparisons here need, and asserting on
    printed text would make these tests fail when somebody rewords a line.
    """
    spec = importlib.util.spec_from_file_location("suppression_drill", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: The fixture estate. Every verdict below is derived from these rows by
#: `src/suppression.py` rather than asserted from a table, but the INTENT of
#: each row is named here so a change in the module shows up as a test that
#: disagrees with its own fixture rather than one that silently moves.
#:
#: `@*.test` is RFC 2606 reserved. No address here can reach anybody.
RECORDS = [
    # ALLOW. Nothing argues against them, and the touch snapshot is clean.
    {"id": "r-001", "domain": "allow.test", "state": "queued",
     "contacts": [{"key": "c-allow", "email": "ok@allow.test"}]},
    # BLOCK, because this person OPTED OUT. The named victim of the failure
    # this whole file exists to catch.
    {"id": "r-002", "domain": "optout.test", "state": "queued",
     "contacts": [{"key": "c-optout", "email": "gone@optout.test",
                   "unsubscribed": True}]},
    # BLOCK. The contact was stopped.
    {"id": "r-003", "domain": "stopped.test", "state": "queued",
     "contacts": [{"key": "c-stopped", "email": "halt@stopped.test",
                   "stopped": True}]},
    # BLOCK account-wide, with nothing on the contact itself.
    {"id": "r-004", "domain": "acct.test", "state": "queued",
     "suppression": {"unsubscribed": True},
     "contacts": [{"key": "c-acct", "email": "anyone@acct.test"}]},
    # BLOCK from the agency do-not-contact index - a SECOND file in `work/`,
    # and the one `scripts/restore_drill.py` never opens.
    {"id": "r-005", "domain": "dnc.test", "state": "queued",
     "contacts": [{"key": "c-dnc", "email": "listed@dnc.test"}]},
    # HOLD. In an active sequence somewhere, per the touch snapshot.
    {"id": "r-006", "domain": "hold.test", "state": "queued",
     "contacts": [{"key": "c-hold", "email": "busy@hold.test"}]},
    # HOLD. No touch history supplied at all - UNKNOWN is not a pass.
    {"id": "r-007", "domain": "unknown.test", "state": "queued",
     "contacts": [{"key": "c-unknown", "email": "silent@unknown.test"}]},
]

#: Deliberately NOT in `work/` and deliberately constant across both
#: censuses: the provider's touch history is not in the archive, so holding
#: it fixed is what makes the restored state the only variable. `r-007` is
#: absent on purpose.
TOUCHES = {
    "r-001::c-allow": {"total_sends": 0, "last_touch_at": None,
                       "active_sequence": False},
    "r-002::c-optout": {"total_sends": 2, "last_touch_at": None,
                        "active_sequence": False},
    "r-003::c-stopped": {"total_sends": 1, "last_touch_at": None,
                         "active_sequence": False},
    "r-004::c-acct": {"total_sends": 1, "last_touch_at": None,
                      "active_sequence": False},
    "r-005::c-dnc": {"total_sends": 1, "last_touch_at": None,
                     "active_sequence": False},
    "r-006::c-hold": {"total_sends": 1, "last_touch_at": None,
                      "active_sequence": True},
}

OPT_OUT = "r-002::c-optout"
AGENCY_DNC = "r-005::c-dnc"
CLEAN = "r-001::c-allow"


class _Estate(unittest.TestCase):
    """A fixture `work/` holding ALLOW, HOLD and BLOCK rows."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-suppression-restore-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.state = os.path.join(self.tmp, "work")
        self.into = os.path.join(self.tmp, "backups")
        os.makedirs(self.state)
        self.drill = _drill_module()
        self._write_estate(RECORDS)

    def _write_estate(self, records):
        put_back = store.use_directory(self.state)
        try:
            self._write_rows(store.queue_path(), records)
            self._write_rows(os.path.join(self.state, "campaigns.jsonl"),
                             [{"campaign_id": "c-497", "state": "paused"}])
            # Goes through `agencydnc.add` rather than a hand-written line, so
            # the fixture cannot disagree with the fingerprinting the lookup
            # uses. The plaintext address is never stored by it.
            agencydnc.add("email", "listed@dnc.test",
                          reason=agencydnc.REQUESTED)
        finally:
            put_back()

    @staticmethod
    def _write_rows(path, rows):
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    def _restored(self):
        """Back up and restore for real, and keep the tree to mutate."""
        report, restored = self.drill.run(self.state, into=self.into,
                                          touches=TOUCHES, keep=True)
        self.addCleanup(shutil.rmtree, restored, ignore_errors=True)
        return report, restored

    def _recompare(self, restored):
        report, _ = self.drill.run(self.state, restored=restored,
                                   touches=TOUCHES)
        return report

    @staticmethod
    def _rewrite_restored_queue(restored, records):
        path = os.path.join(restored, "queue.jsonl")
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            for row in records:
                fh.write(json.dumps(row) + "\n")


class TheFixtureHoldsAllThreeVerdicts(_Estate):
    """If the fixture drifts to all-BLOCK or all-HOLD the drill below stops
    proving what it says it proves, so the shape is asserted first."""

    def test_the_source_census_holds_allow_hold_and_block(self):
        members, _asked = self.drill.census(self.state, TOUCHES)
        actions = {name: m.enrol for name, m in members.items()}
        self.assertEqual(suppression.ALLOW, actions[CLEAN])
        self.assertEqual(suppression.HOLD, actions["r-006::c-hold"])
        self.assertEqual(suppression.BLOCK, actions[OPT_OUT])
        self.assertEqual({suppression.ALLOW, suppression.HOLD,
                          suppression.BLOCK}, set(actions.values()))

    def test_the_opt_out_row_is_blocked_because_the_person_opted_out(self):
        """Not merely BLOCK - BLOCK for the opt-out reason. A row that blocked
        for some other reason would satisfy a verdict assertion while the
        opt-out itself had been lost."""
        members, _asked = self.drill.census(self.state, TOUCHES)
        from src import eligibility
        self.assertIn(eligibility.BLOCKED_UNSUBSCRIBED,
                      members[OPT_OUT].eligibility_reasons)

    def test_suppression_was_asked_about_every_member_at_both_scopes(self):
        """`consultations()` exists so a test can tell "it refused" from "it
        was never reached"."""
        members, asked = self.drill.census(self.state, TOUCHES)
        self.assertEqual(2 * len(members), len(asked))
        asked_names = {"%s::%s" % (rec_id, key) for rec_id, key, _a in asked}
        self.assertEqual(set(members), asked_names)


class ARestoreKeepsTheSuppressions(_Estate):

    def test_the_drill_passes_on_a_healthy_backup_and_restore(self):
        report, _restored = self._restored()
        self.assertTrue(report.ok, "\n".join(report.lines(verbose=True)))
        self.assertEqual([], report.lost_blocks)
        self.assertEqual([], report.changed)
        self.assertEqual([], report.refusals)

    def test_every_block_row_comes_back_BY_NAME(self):
        """By set, never by count. Three censuses can hold the same number of
        BLOCK rows and be three different sets of people."""
        report, _restored = self._restored()
        self.assertEqual(set(report.before_blocks), set(report.after_blocks))
        self.assertIn(OPT_OUT, report.after_blocks)
        self.assertIn(AGENCY_DNC, report.after_blocks)

    def test_the_restored_state_gives_the_same_verdict_for_each_member(self):
        """The question neither existing drill asks: not "did the bytes come
        back" but "does src/suppression.py still refuse the same people"."""
        _report, restored = self._restored()
        before, _ = self.drill.census(self.state, TOUCHES)
        after, _ = self.drill.census(restored, TOUCHES)
        self.assertEqual(set(before), set(after))
        for name in sorted(before):
            self.assertEqual(before[name].verdicts, after[name].verdicts,
                             "the verdict for %s changed across the restore"
                             % name)

    def test_the_restored_tree_is_loadable_at_all(self):
        """An unreadable restore is not a pass. `store.load()` is asked of the
        restored directory, not of the live one."""
        _report, restored = self._restored()
        put_back = store.use_directory(restored)
        try:
            ids = [r.get("id") for r in store.load()]
        finally:
            put_back()
        self.assertEqual([r["id"] for r in RECORDS], ids)


class TheDrillGoesRedWhenSuppressionIsLost(_Estate):
    """The half that matters. A drill that cannot fail is worse than none,
    because it is believed."""

    def test_dropping_the_opt_out_row_fails_and_names_it(self):
        _report, restored = self._restored()
        self._rewrite_restored_queue(
            restored, [r for r in RECORDS if r["id"] != "r-002"])
        report = self._recompare(restored)
        self.assertFalse(report.ok)
        self.assertEqual([OPT_OUT], report.lost_blocks)
        self.assertIn(OPT_OUT, report.lost_members)
        self.assertNotIn(OPT_OUT, report.after_blocks)

    def test_a_row_that_comes_back_without_its_opt_out_flag_fails_and_names_it(self):
        """SAME file count, SAME member names, and a person who asked to be
        left alone is ALLOW again. This is the failure the task names, and a
        drill comparing only which members exist would pass it."""
        _report, restored = self._restored()
        mutated = copy.deepcopy(RECORDS)
        for rec in mutated:
            if rec["id"] == "r-002":
                rec["contacts"][0].pop("unsubscribed")
        self._rewrite_restored_queue(restored, mutated)
        report = self._recompare(restored)
        self.assertFalse(report.ok)
        self.assertEqual([], report.lost_members,
                         "every member still exists; only the verdict moved")
        self.assertEqual([OPT_OUT], [n for n, _b, _a in report.changed])
        self.assertEqual([OPT_OUT], [n for n, _b, _a in report.weakened])

    def test_the_agency_dnc_index_not_coming_back_fails_and_names_the_row(self):
        """`queue.jsonl` is intact, so its record count and both of
        `scripts/restore_drill.py`'s histograms are unchanged and that drill
        passes. A second file in `work/` holds the suppression and it is
        gone."""
        _report, restored = self._restored()
        os.unlink(os.path.join(restored, "agency-dnc.jsonl"))
        report = self._recompare(restored)
        self.assertFalse(report.ok)
        self.assertEqual([], report.lost_members)
        self.assertEqual([AGENCY_DNC], [n for n, _b, _a in report.weakened])

    def test_a_mutation_that_keeps_the_count_still_fails(self):
        """THE CONTROL FOR THE COMPARISON ITSELF. One BLOCK row loses its
        suppression and a different row gains one, so the BLOCK COUNT is
        identical before and after - and the set is not. Three finished
        suites in this repository each reported exactly 231 failing names and
        one of them was a different 231."""
        _report, restored = self._restored()
        mutated = copy.deepcopy(RECORDS)
        for rec in mutated:
            if rec["id"] == "r-002":
                rec["contacts"][0].pop("unsubscribed")
            if rec["id"] == "r-001":
                rec["contacts"][0]["stopped"] = True
        self._rewrite_restored_queue(restored, mutated)
        report = self._recompare(restored)
        self.assertEqual(len(report.before_blocks), len(report.after_blocks),
                         "a count-based comparison sees no difference here")
        self.assertNotEqual(set(report.before_blocks),
                            set(report.after_blocks))
        self.assertFalse(report.ok)
        self.assertEqual([CLEAN, OPT_OUT],
                         sorted(n for n, _b, _a in report.changed))
        self.assertEqual([OPT_OUT], [n for n, _b, _a in report.weakened])


class TheDrillRefusesRatherThanPassingVacuously(_Estate):

    def test_an_empty_census_is_refused(self):
        """A drill over nobody cannot fail."""
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        self._write_rows(os.path.join(empty, "queue.jsonl"), [])
        report, _ = self.drill.run(empty, into=os.path.join(self.tmp, "b2"),
                                   touches=TOUCHES)
        self.assertFalse(report.ok)
        self.assertTrue(any("empty" in r for r in report.refusals),
                        report.refusals)

    def test_a_census_with_no_block_rows_is_refused(self):
        """There is no suppression to lose, so a pass proves nothing about
        suppression. This is the vacuous green the task is guarding against."""
        clean = os.path.join(self.tmp, "clean")
        os.makedirs(clean)
        self._write_rows(os.path.join(clean, "queue.jsonl"),
                         [r for r in RECORDS
                          if r["id"] in ("r-001", "r-006", "r-007")])
        report, _ = self.drill.run(clean, into=os.path.join(self.tmp, "b3"),
                                   touches=TOUCHES)
        self.assertFalse(report.ok)
        self.assertTrue(any("no BLOCK row" in r for r in report.refusals),
                        report.refusals)

    def test_unknown_is_not_a_pass_being_off_is_refused(self):
        """Every verdict collected would then answer a different question
        from the one the report puts a name on."""
        original = suppression.UNKNOWN_IS_NOT_A_PASS
        suppression.UNKNOWN_IS_NOT_A_PASS = False
        self.addCleanup(setattr, suppression, "UNKNOWN_IS_NOT_A_PASS",
                        original)
        report, _ = self._restored()
        self.assertFalse(report.ok)
        self.assertTrue(any("UNKNOWN_IS_NOT_A_PASS" in r
                            for r in report.refusals), report.refusals)

    def test_a_census_that_did_not_ask_suppression_is_refused(self):
        """Asserted on `compare` directly, which is the function the drill
        calls - a guard aimed next to the thing it guards is not a guard.
        A verdict nobody asked for is not a refusal, and the shape that
        produces it is an early return that skipped `_verdict`."""
        members, asked = self.drill.census(self.state, TOUCHES)
        full = self.drill.compare(members, members, asked, asked)
        self.assertEqual([], full.refusals)
        short = self.drill.compare(members, members, asked[:-1], asked)
        self.assertFalse(short.ok)
        self.assertTrue(any("asked" in r for r in short.refusals),
                        short.refusals)

    def test_a_census_cannot_hold_two_members_with_one_name(self):
        """A comparison by name is only a comparison if the names are
        unique - otherwise one row silently stands in for the other."""
        collide = os.path.join(self.tmp, "collide")
        os.makedirs(collide)
        self._write_rows(os.path.join(collide, "queue.jsonl"), [
            {"id": "r-dup", "domain": "dup.test", "state": "queued",
             "contacts": [{"key": "c", "email": "a@dup.test"},
                          {"key": "c", "email": "b@dup.test"}]}])
        with self.assertRaises(SystemExit) as caught:
            self.drill.census(collide, TOUCHES)
        self.assertIn("r-dup::c", str(caught.exception))


class TheDrillWillNotTouchProductionState(_Estate):

    def test_production_work_is_refused_as_a_source(self):
        protected = store.protected_directories()
        self.assertTrue(protected, "the barrier knows of no protected "
                                   "directory, so this test cannot fail")
        with self.assertRaises(SystemExit) as caught:
            self.drill.run(protected[0], into=self.into)
        self.assertIn("production state", str(caught.exception))

    def test_the_source_directory_is_not_written(self):
        before = sorted(os.listdir(self.state))
        digests = {name: os.path.getsize(os.path.join(self.state, name))
                   for name in before}
        self._restored()
        self.assertEqual(before, sorted(os.listdir(self.state)))
        self.assertEqual(digests,
                         {name: os.path.getsize(os.path.join(self.state, name))
                          for name in sorted(os.listdir(self.state))})

    def test_the_store_is_pointed_back_after_a_census(self):
        """A census leaves the process pointed where it found it, absence
        included - otherwise the next thing in the suite writes into a deleted
        temp directory."""
        before = os.environ.get("QUEUE")
        self.drill.census(self.state, TOUCHES)
        self.assertEqual(before, os.environ.get("QUEUE"))


class TheDrillRunsFromTheCommandLine(_Estate):
    """The operator runs this as a command, not as a test."""

    def _run(self, *args):
        return subprocess.run([sys.executable, SCRIPT] + list(args),
                              cwd=ROOT, capture_output=True, text=True)

    def test_a_healthy_estate_exits_zero_and_says_so(self):
        touches = os.path.join(self.tmp, "touches.json")
        with io.open(touches, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(TOUCHES, fh)
        proc = self._run("--state-dir", self.state, "--into", self.into,
                         "--touches", touches)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("SUPPRESSION RESTORE DRILL PASSED", proc.stdout)

    def test_no_email_address_is_ever_printed(self):
        """This is meant to be runnable against a real archive, and a real
        archive is prospect PII. Members are named `<rec_id>::<contact_key>`
        and the address is used only for the agency index lookup."""
        touches = os.path.join(self.tmp, "touches.json")
        with io.open(touches, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(TOUCHES, fh)
        proc = self._run("--state-dir", self.state, "--into", self.into,
                         "--touches", touches, "-v")
        printed = proc.stdout + proc.stderr
        for record in RECORDS:
            for contact in record["contacts"]:
                self.assertNotIn(contact["email"], printed)
        self.assertIn(OPT_OUT, printed, "the member name IS printed, so this "
                                        "test is not passing on an empty "
                                        "report")


if __name__ == "__main__":
    unittest.main()
