"""A Qwen worker never holds the machine-wide suite lock.

OPERATOR RULE, 2026-10-03, after it cost a merge gate 45 minutes.
`qwen-worker-10-r9` had been waiting in the FIFO queue since 21:55 and took
the lock the instant a merge-gate run released it at 22:19:46. The
integration gate - the only thing standing between four reviewed branches
and master - went behind a full suite the worker did not need, because Qwen
measures PER MODULE.

The rule is a REFUSAL rather than a lower queue priority. A worker that
queues politely still takes the lock eventually; a worker that is refused
goes and does the per-module measurement it should have done.
"""
import importlib.util
import json
import os
import tempfile
import unittest


def _run_suite():
    """Load `scripts/run_suite.py` as a module, the way the gate's tests do."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "scripts", "run_suite.py")
    spec = importlib.util.spec_from_file_location("run_suite_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AQwenBranchIsRefused(unittest.TestCase):
    def setUp(self):
        self.rs = _run_suite()

    def test_the_worker_branch_that_actually_took_it_is_refused(self):
        """The real branch from the real incident, by name."""
        reason = self.rs.refuse_qwen_lock("qwen-worker-10-r9", cwd=r"C:/elsewhere")
        self.assertIsNotNone(reason)
        self.assertIn("qwen-worker-10-r9", reason)

    def test_every_worker_in_the_pool_is_refused(self):
        for n in ("qwen-worker-r9", "qwen-worker-2-r9", "qwen-worker-12-r59",
                  "qwen-worker-7-r9-task544"):
            with self.subTest(n):
                self.assertIsNotNone(
                    self.rs.refuse_qwen_lock(n, cwd=r"C:/elsewhere"),
                    f"{n} was allowed to take the machine-wide suite lock")

    def test_a_detached_head_in_a_qwen_worktree_is_refused(self):
        """A worker on a detached HEAD has no `qwen-` branch to match.

        Without this route the branch check is trivially evaded by the most
        ordinary thing a worker does - checking out a SHA.
        """
        reason = self.rs.refuse_qwen_lock(
            "HEAD", cwd=r"C:/Users/Zvonimir/Desktop/resonate-qwen-10")
        self.assertIsNotNone(reason)
        self.assertIn("resonate-qwen-10", reason)

    def test_a_task_claimed_by_a_qwen_worker_is_refused(self):
        """The operator's third route: the TASK carries the Qwen claim."""
        with tempfile.TemporaryDirectory() as root:
            claims = os.path.join(root, "work", "claims")
            os.makedirs(claims)
            with open(os.path.join(claims, "TASK-397.claim"), "w",
                      encoding="utf-8") as fh:
                json.dump({"task": "TASK-397", "worker": "qwen-worker-10",
                           "pid": 1, "claimed_at": "2026-10-03T22:00:00"}, fh)
            reason = self.rs.refuse_qwen_lock(
                "task-397-seat-cap", cwd=r"C:/elsewhere", root=root)
            self.assertIsNotNone(reason)
            self.assertIn("TASK-397", reason)

    def test_an_unreadable_claim_is_not_read_as_not_qwen(self):
        """Invariant 0. An unreadable authority is UNKNOWN, never a pass."""
        with tempfile.TemporaryDirectory() as root:
            claims = os.path.join(root, "work", "claims")
            os.makedirs(claims)
            with open(os.path.join(claims, "TASK-500.claim"), "w",
                      encoding="utf-8") as fh:
                fh.write("{ this is not json")
            self.assertIsNotNone(
                self.rs.refuse_qwen_lock("task-500-x", cwd=r"C:/elsewhere",
                                         root=root),
                "an unreadable claim was treated as evidence of NOT Qwen")


class TheRefusalDoesNotCatchEverybody(unittest.TestCase):
    """THE CONTROLS. A guard that refuses every caller serialises nothing."""

    def setUp(self):
        self.rs = _run_suite()

    def test_master_may_take_the_lock(self):
        self.assertIsNone(self.rs.refuse_qwen_lock("master", cwd=r"C:/elsewhere"))

    def test_a_merge_gate_branch_may_take_the_lock(self):
        for n in ("task-integration-2026-10-03",
                  "task-1004-positive-replies-reach-a-human",
                  "task-copy-exemplars"):
            with self.subTest(n):
                self.assertIsNone(
                    self.rs.refuse_qwen_lock(n, cwd=r"C:/elsewhere"),
                    f"{n} is a gate branch and was refused the lock")

    def test_a_claim_held_by_a_human_track_does_not_refuse(self):
        with tempfile.TemporaryDirectory() as root:
            claims = os.path.join(root, "work", "claims")
            os.makedirs(claims)
            with open(os.path.join(claims, "TASK-397.claim"), "w",
                      encoding="utf-8") as fh:
                json.dump({"task": "TASK-397", "worker": "claude-lane-a",
                           "pid": 1, "claimed_at": "x"}, fh)
            self.assertIsNone(
                self.rs.refuse_qwen_lock("task-397-seat-cap",
                                         cwd=r"C:/elsewhere", root=root))

    def test_an_unrelated_qwen_claim_does_not_refuse_another_branch(self):
        """A Qwen claim on SOME task must not block every other branch."""
        with tempfile.TemporaryDirectory() as root:
            claims = os.path.join(root, "work", "claims")
            os.makedirs(claims)
            with open(os.path.join(claims, "TASK-397.claim"), "w",
                      encoding="utf-8") as fh:
                json.dump({"task": "TASK-397", "worker": "qwen-worker-10",
                           "pid": 1, "claimed_at": "x"}, fh)
            self.assertIsNone(
                self.rs.refuse_qwen_lock("task-integration-2026-10-03",
                                         cwd=r"C:/elsewhere", root=root))


class TheRefusalSaysWhy(unittest.TestCase):
    """A silent refusal is indistinguishable from a worker that never ran."""

    def setUp(self):
        self.rs = _run_suite()

    def test_it_names_the_reason_and_the_alternative(self):
        said = []
        self.rs._refuse_and_say("branch 'qwen-worker-10-r9' is a Qwen worker "
                                "branch", say=said.append)
        blob = "\n".join(said).lower()
        self.assertIn("qwen", blob)
        self.assertIn("per module", blob)
        self.assertIn("--no-lock", blob)
        self.assertIn("qwen-worker-10-r9", blob,
                      "the refusal does not say which caller it refused")


class TheMutation(unittest.TestCase):
    """THE OPERATOR'S REQUIRED TEST: remove the check and Qwen takes the lock.

    A guard is only proven by its absence. Without this, `refuse_qwen_lock`
    could be rewired to return None for everything and every assertion above
    that expects a refusal would still be the only thing failing - which is
    the same as having no idea whether the guard is load-bearing in `main`.
    """

    def test_main_consults_the_refusal_before_acquiring(self):
        """`main` must call the guard, not merely define it.

        Asserted on the SOURCE of `main` rather than by running it, because
        running `main` takes the real machine-wide lock. This is the one
        place in this module where reading the text is the honest test: the
        question is whether one function calls another.
        """
        import inspect
        rs = _run_suite()
        src = inspect.getsource(rs.main)
        self.assertIn("refuse_qwen_lock", src,
                      "main() never consults the guard, so a Qwen branch "
                      "reaches suitelock.acquire and takes the lock")
        self.assertLess(
            src.index("refuse_qwen_lock"), src.index("suitelock.acquire"),
            "the guard is consulted AFTER the lock is acquired, which is "
            "the same as not consulting it")


if __name__ == "__main__":
    unittest.main()
