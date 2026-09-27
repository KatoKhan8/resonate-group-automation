"""Branch state is an artifact. A held claim is the only liveness authority.

WHAT THESE TESTS ENCODE. On 2026-09-27 the pool reported ZERO ready tasks for
hours while twelve workers polled an empty queue and `pool.sh` fired
`ready tasks (0) below the floor of 6` every sweep. Nothing was broken in the
workers. `claim_task.py` hid a task whenever ANY branch had moved its task file
past master's stage with a newer commit, which conflated three different facts:

    a worker is working on this now        - true only of a held claim
    a finished result exists on a branch   - 114 tasks, an integration backlog
    a worker died and left RUNNING behind  - 13 tasks, silently unreachable

Measured that morning: 134 of 143 TODO tasks excluded, 0 ready. TASK-328,
TASK-387 and TASK-397 were open CRITICALs precisely because a dead run had left
RUNNING on a branch and nothing could ever pick them up again.

Two proxies are specifically rejected here, because both were tried and both
lie. A claim's recorded pid is the pid of the CLAIMING process, not the worker
(`claim_task.reap`'s own docstring), so a pid check reports every live claim as
dead. And commit freshness is not worker liveness either - a slow task and a
dead one look identical.

Each test below names the incident it prevents. Every assertion is on the
VERDICT returned by the real functions; the only things stubbed are the three
seams that read git, so the classification logic under test is the real one.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "scripts"))

import claim_task as ct


MASTER_TS = 1000
NEWER = 2000
OLDER = 500


def _todo(task_id, name="thing"):
    return "docs/qwen-tasks/TODO/%s-%s.md" % (task_id, name)


class ReadinessIsNotInferred(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="claimtask-")
        for sub in ("docs/qwen-tasks/TODO", "docs/qwen-tasks/DONE",
                    "work/claims"):
            os.makedirs(os.path.join(self.tmp, sub), exist_ok=True)

        self._saved = (ct.MAIN_REPO, ct.CLAIMS, ct.REGISTRY,
                       ct._task_files_on, ct._master_touch_times,
                       ct._branch_touch_times, ct._branch_cache_path)
        ct.MAIN_REPO = self.tmp
        ct.CLAIMS = os.path.join(self.tmp, "work", "claims")
        ct.REGISTRY = os.path.join(self.tmp, "docs", "state",
                                  "TASK-REGISTRY.json")
        # A per-test cache file, so one test's classification can never be
        # served to another and the refs fingerprint is irrelevant here.
        ct._branch_cache_path = lambda: os.path.join(
            self.tmp, "work", ".cache.json")

        self.master_files = {}
        self.branch_times = {}
        ct._task_files_on = lambda ref: dict(self.master_files)
        ct._master_touch_times = lambda: {
            path: MASTER_TS for _tid, (_st, path) in self.master_files.items()}
        ct._branch_touch_times = lambda: dict(self.branch_times)

    def tearDown(self):
        (ct.MAIN_REPO, ct.CLAIMS, ct.REGISTRY, ct._task_files_on,
         ct._master_touch_times, ct._branch_touch_times,
         ct._branch_cache_path) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- helpers

    def add_task(self, task_id, header=""):
        """A task file in master's TODO, and master's view of it."""
        path = _todo(task_id)
        full = os.path.join(self.tmp, path.replace("/", os.sep))
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(header + "\n# %s\n\nbody\n" % task_id)
        self.master_files[task_id] = ("TODO", path)
        return path

    def branch_says(self, task_id, branch, stage, ts=NEWER):
        self.branch_times.setdefault(task_id, {})[branch] = (stage, ts)

    def ready_ids(self):
        awaiting, _rec, _stale = ct.classification()
        return {tid for _p, tid, _f in
                ct.ready_tasks(active_on_branch=set(awaiting))}

    # ----------------------------------------------------------------- tests

    def test_A_a_dead_run_left_RUNNING_and_the_task_is_recoverable(self):
        """A) TODO + branch says RUNNING + no claim -> READY / RECOVERABLE.

        The TASK-328 / 387 / 397 incident: the worker died, RUNNING stayed on
        the branch, and the task became permanently unreachable.
        """
        self.add_task("TASK-700")
        self.branch_says("TASK-700", "qwen-worker-2-r9", "RUNNING")

        awaiting, recoverable, _stale = ct.classification()
        self.assertNotIn("TASK-700", awaiting,
                         "RUNNING is not a finished result")
        self.assertIn("TASK-700", recoverable,
                      "a branch saying RUNNING with no claim is a dead run")
        self.assertIn("TASK-700", self.ready_ids(),
                      "a recoverable task must be dispatchable again")

    def test_B_a_held_claim_keeps_the_task_out_of_the_queue(self):
        """B) TODO + branch says RUNNING + a HELD CLAIM -> NOT READY.

        The 2026-09-15 incident: six workers took one task. A claim is the one
        positive evidence of active work and it still has to hold.
        """
        self.add_task("TASK-701")
        self.branch_says("TASK-701", "qwen-worker-3-r9", "RUNNING")
        self.assertIn("TASK-701", self.ready_ids())      # before the claim

        self.assertEqual(ct.claim("TASK-701", "resonate-qwen-3"), ct.CLAIM_OK)
        self.assertNotIn("TASK-701", self.ready_ids(),
                         "a held claim must keep the task out of the queue")

    def test_C_a_finished_result_on_a_branch_is_never_redispatched(self):
        """C) branch REVIEW or DONE, newer than master -> awaiting integration.

        114 such results existed unmerged. Handing the implementation out again
        duplicates finished work; merging it is the actual job.
        """
        self.add_task("TASK-702")
        self.branch_says("TASK-702", "qwen-worker-9-r9", "REVIEW")
        self.add_task("TASK-703")
        self.branch_says("TASK-703", "qwen-worker-2-r9", "DONE")

        awaiting, recoverable, _stale = ct.classification()
        for tid in ("TASK-702", "TASK-703"):
            self.assertIn(tid, awaiting)
            self.assertNotIn(tid, recoverable)
            self.assertNotIn(tid, self.ready_ids(),
                             "%s has a result; it must not be redispatched" % tid)

    def test_C2_a_result_on_one_branch_beats_RUNNING_on_another(self):
        """C) precedence. The overnight double dispatches produced exactly this
        shape: one branch finished while another still said RUNNING. The
        finished result must win, or the work is done twice."""
        self.add_task("TASK-704")
        self.branch_says("TASK-704", "qwen-worker-6-r80", "RUNNING", ts=NEWER)
        self.branch_says("TASK-704", "qwen-worker-2-r9", "REVIEW", ts=NEWER + 1)

        awaiting, recoverable, _stale = ct.classification()
        self.assertIn("TASK-704", awaiting)
        self.assertNotIn("TASK-704", recoverable)
        self.assertNotIn("TASK-704", self.ready_ids())

    def test_C3_a_blocked_branch_stage_is_a_returned_verdict(self):
        """C) a branch copy in BLOCKED/ is a RESULT, not a dead run.

        Operator decision 2026-09-27. For a GLM verification task, moving the
        file into `BLOCKED/` IS the answer it was dispatched to produce.
        Recovering it would redispatch verification that already returned -
        the same error as redispatching a REVIEW result, wearing a different
        directory name. TASK-410 is the live example: its BLOCKED state is its
        verdict.

        This is safe precisely because it does not touch the prohibition:
        HEADER IS INSTRUCTION, STAGE IS ARTIFACT. `STATUS: BLOCKED` in the
        header is what forbids dispatch, tests D and E pin it, and it is
        evaluated independently of anything a branch says.
        """
        self.add_task("TASK-707")
        self.branch_says("TASK-707", "qwen-worker-3-r9", "BLOCKED")

        awaiting, recoverable, _stale = ct.classification()
        self.assertIn("TASK-707", awaiting,
                      "a BLOCKED branch stage is a produced verdict")
        self.assertNotIn("TASK-707", recoverable,
                         "a returned verdict is not a dead run")
        self.assertNotIn("TASK-707", self.ready_ids(),
                         "verification that already answered must not be "
                         "dispatched again")

    def test_C4_blocked_quota_is_still_an_abandoned_run(self):
        """The counterpart, and why the match must stay exact. A worker stopped
        by a quota produced NOTHING, so BLOCKED_QUOTA is an abandoned run and
        its task stays recoverable. If this ever starts behaving like BLOCKED,
        quota-stopped work becomes permanently unreachable."""
        self.add_task("TASK-708")
        self.branch_says("TASK-708", "qwen-worker-5-r58", "BLOCKED_QUOTA")

        awaiting, recoverable, _stale = ct.classification()
        self.assertNotIn("TASK-708", awaiting)
        self.assertIn("TASK-708", recoverable)
        self.assertIn("TASK-708", self.ready_ids())

    def test_D_a_blocked_header_beats_every_branch(self):
        """D) STATUS: BLOCKED -> NEVER READY, whatever any branch says.

        The header on master is the authority. A branch cannot unblock a task
        by having an older copy of it, and recovery must not reach past a
        deliberate block.
        """
        self.add_task("TASK-705", header="PRIORITY: P0\nSTATUS: BLOCKED")
        self.branch_says("TASK-705", "qwen-worker-4-r9", "RUNNING")

        _aw, recoverable, _st = ct.classification()
        self.assertIn("TASK-705", recoverable,
                      "the branch classification still describes it")
        self.assertNotIn("TASK-705", self.ready_ids(),
                         "a BLOCKED header must outrank recovery")

    def test_E_task_309_is_never_dispatchable(self):
        """E) TASK-309 specifically. It was dispatched twice against an explicit
        operator prohibition before the header check existed, and the
        readiness change must not reopen that door.

        THE BRANCH SHAPE HERE IS DELIBERATE AND WAS CORRECTED. The first
        version of this test also gave 309 a branch in DONE, which made it
        AWAITING INTEGRATION - so removing the BLOCKED check entirely left the
        test passing, because a different guard was doing the work. Mutation
        testing caught that. 309 now gets ONLY a RUNNING branch, which is the
        recoverable shape that WOULD otherwise be dispatchable, so the header
        is the single thing standing between it and the queue.
        """
        self.add_task("TASK-309", header="PRIORITY: P0\nSTATUS: BLOCKED")
        self.branch_says("TASK-309", "qwen-worker-2-r9", "RUNNING")

        _aw, recoverable, _st = ct.classification()
        self.assertIn("TASK-309", recoverable,
                      "fixture must be the otherwise-dispatchable shape, or "
                      "this test cannot prove the header is what blocks it")
        self.assertNotIn("TASK-309", self.ready_ids())
        # And through the real dispatch entry point, not only the helper.
        awaiting, _rec, _st = ct.classification()
        self.assertNotIn("TASK-309",
                         {t for _p, t, _f in
                          ct.ready_tasks(active_on_branch=set(awaiting))})

    def test_E2_a_forbidden_task_stays_blocked_even_with_a_finished_branch(self):
        """E) the other shape: a branch that claims 309 is DONE must not make it
        dispatchable either, and must not be read as permission to proceed."""
        self.add_task("TASK-309", header="PRIORITY: P0\nSTATUS: BLOCKED")
        self.branch_says("TASK-309", "qwen-worker-5-r9", "DONE", ts=NEWER + 5)
        self.assertNotIn("TASK-309", self.ready_ids())

    def test_F_reap_refuses_because_a_claim_pid_is_not_worker_liveness(self):
        """F) pid dead while the worker is alive -> MUST NOT REAP.

        The claim records the pid of the process that WROTE the claim. Claude
        claims on a worker's behalf and that process exits immediately, so
        every live claim looks dead. An automatic reap would release all of
        them and hand every task to a second worker.
        """
        self.add_task("TASK-706")
        self.assertEqual(ct.claim("TASK-706", "resonate-qwen-7"), ct.CLAIM_OK)
        path = os.path.join(ct.CLAIMS, "TASK-706.claim")
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        payload["pid"] = 999999999          # certainly not running
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ct.reap()

        self.assertEqual(rc, ct.CLAIM_ERROR, "reap must refuse")
        self.assertTrue(os.path.exists(path),
                        "reap released a claim; a dead pid is not a dead worker")
        self.assertNotIn("TASK-706", self.ready_ids(),
                         "the claim still holds the task")


class TheStatusOutputIsAParsingContract(unittest.TestCase):
    """pool.sh and pool_watchdog.sh PARSE `--status`. Breaking its shape stops
    dispatch silently, which is worse than a crash.

    Four contracts, each with a named consumer:
      pool.sh busy() / watchdog busy_count()   grep the whole output for
                                               " <worker> ", so a worker name
                                               must appear ONLY in the claims
                                               block.
      pool.sh next_ready()                     awk: after the first line
                                               matching /^ready/, the first
                                               line matching /^  P[0-4]/.
      watchdog release_stale_claims()          reads /^  TASK-/ straight after
                                               "claims held" and stops at the
                                               first line that is not.
      pool.sh + watchdog ready_count()         grep the exact string
                                               "ready (unclaimed, deps met): N".
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="claimtask-status-")
        for sub in ("docs/qwen-tasks/TODO", "docs/qwen-tasks/DONE",
                    "work/claims"):
            os.makedirs(os.path.join(self.tmp, sub), exist_ok=True)
        self._saved = (ct.MAIN_REPO, ct.CLAIMS, ct.REGISTRY,
                       ct._task_files_on, ct._master_touch_times,
                       ct._branch_touch_times, ct._branch_cache_path, sys.argv)
        ct.MAIN_REPO = self.tmp
        ct.CLAIMS = os.path.join(self.tmp, "work", "claims")
        ct.REGISTRY = os.path.join(self.tmp, "docs", "state", "reg.json")
        ct._branch_cache_path = lambda: os.path.join(self.tmp, "work", "c.json")

        master = {}
        for tid in ("TASK-710", "TASK-711", "TASK-712"):
            path = _todo(tid)
            with open(os.path.join(self.tmp, path.replace("/", os.sep)),
                      "w", encoding="utf-8") as fh:
                fh.write("PRIORITY: P0\n\n# %s\n" % tid)
            master[tid] = ("TODO", path)
        ct._task_files_on = lambda ref: dict(master)
        ct._master_touch_times = lambda: {p: MASTER_TS
                                          for _t, (_s, p) in master.items()}
        # 710 recoverable, 711 awaiting integration, 712 plain ready.
        ct._branch_touch_times = lambda: {
            "TASK-710": {"qwen-worker-2-r9": ("RUNNING", NEWER)},
            "TASK-711": {"qwen-worker-9-r9": ("REVIEW", NEWER)},
        }
        ct.claim("TASK-712", "resonate-qwen-11")

    def tearDown(self):
        (ct.MAIN_REPO, ct.CLAIMS, ct.REGISTRY, ct._task_files_on,
         ct._master_touch_times, ct._branch_touch_times,
         ct._branch_cache_path, sys.argv) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def status_text(self):
        sys.argv = ["claim_task.py", "--status"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ct.main()
        return buf.getvalue()

    def test_the_ready_count_line_is_byte_exact(self):
        """Two callers grep this exact string. A reword silently zeroes it."""
        import re
        out = self.status_text()
        self.assertTrue(
            re.search(r"^ready \(unclaimed, deps met\): \d+$", out, re.M),
            "the ready-count line changed shape:\n%s" % out)

    def test_only_the_claims_block_contains_a_worker_name(self):
        """busy() greps the WHOLE output for " <worker> ". A worker name
        anywhere else marks an idle worker busy and it is never dispatched."""
        out = self.status_text()
        lines = out.splitlines()
        claim_lines = [l for l in lines if l.startswith("  TASK-")]
        others = [l for l in lines if l not in claim_lines]
        for line in others:
            self.assertNotIn(" resonate-qwen-11 ", " %s " % line,
                             "worker name outside the claims block: %r" % line)

    def test_nothing_after_the_ready_block_looks_like_a_ready_entry(self):
        """next_ready() takes the first /^  P[0-4]/ line after /^ready/.
        A later line of that shape would be dispatched as if it were ready."""
        out = self.status_text().splitlines()
        idx = next(i for i, l in enumerate(out) if l.startswith("ready "))
        ready_block, tail, in_ready = [], [], True
        for line in out[idx + 1:]:
            if in_ready and line.startswith("  P"):
                ready_block.append(line)
            else:
                in_ready = False
                tail.append(line)
        import re
        for line in tail:
            self.assertIsNone(re.match(r"^  P[0-4]", line),
                              "line after the ready block parses as ready: %r"
                              % line)

    def test_claim_lines_are_not_interrupted_before_the_ready_line(self):
        """release_stale_claims() stops at the first line after "claims held"
        that does not start with "  TASK-". Anything inserted there truncates
        the watchdog's view of held claims."""
        out = self.status_text().splitlines()
        i = next(i for i, l in enumerate(out) if l.startswith("claims held"))
        seen_claim = False
        for line in out[i + 1:]:
            if line.startswith("  TASK-"):
                seen_claim = True
                continue
            self.assertTrue(line.startswith("ready "),
                            "expected the ready line after the claims block, "
                            "got %r" % line)
            break
        self.assertTrue(seen_claim, "the fixture should hold one claim")

    def test_the_integration_backlog_is_reported_not_subtracted(self):
        """The 114 unmerged results were invisible. Silence is what cost the
        night; the count has to be on the report."""
        out = self.status_text()
        self.assertIn("awaiting integration", out)
        self.assertIn("TASK-711", out)
        self.assertIn("recoverable", out)
        self.assertIn("TASK-710", out)


if __name__ == "__main__":
    unittest.main()
