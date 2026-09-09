"""Resumability: what happens when a 5,000-domain run stops in the middle.

The four properties this file exists to hold, all of them about the second run
rather than the first:

1. A resumed job does no work twice.
2. One bad record is recorded and skipped; the batch continues.
3. A batch that is bad throughout aborts instead of burning through 5,000.
4. A step that can spend money refuses to start without an explicit budget.

The cursor is matched by **identity, not index**. A batch that grew between
slices would shift every index, and a resume that trusted an index would either
redo work or skip it - and skipping it silently is worse, because nothing looks
wrong afterwards.
"""
import os
import shutil
import tempfile
import unittest

from src import jobs, store


class JobTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-jobs-")
        self._prev = {k: os.environ.get(k)
                      for k in ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES",
                                "AUDIT")}
        store.use_directory(os.path.join(self.tmp, "work"))
        self.items = [{"id": f"r{i:03d}"} for i in range(250)]

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def job(self, kind=jobs.ICP_CLASSIFY, **kw):
        return jobs.append(jobs.new(kind, client="demo", batch="b",
                                    total=len(self.items), **kw))


class Resume(JobTest):

    def test_a_resumed_job_redoes_at_most_the_item_it_died_on(self):
        """A crash loses one record, not a batch.

        Not *zero* records: the item that was in flight when the process died
        is retried, because the cursor advances after the work returns and a
        job cannot know whether an interrupted call finished. Redoing one is
        the honest cost of not skipping one, and skipping one silently is far
        worse - nothing would look wrong afterwards.
        """
        touched = []

        def work(item):
            touched.append(item["id"])
            if len(touched) == 60:
                raise KeyboardInterrupt("the process died here")

        job = self.job()
        with self.assertRaises(KeyboardInterrupt):
            jobs.run_step(job, self.items, work, slice_size=1000)
        first = list(touched)
        self.assertEqual(len(first), 60)
        self.assertEqual(job["cursor"], "r058")

        touched.clear()
        jobs.run_step(job, self.items, lambda i: touched.append(i["id"]),
                      slice_size=1000)
        repeated = sorted(set(first) & set(touched))
        self.assertEqual(repeated, ["r059"], "only the in-flight item repeats")
        self.assertEqual(sorted(set(first) | set(touched)),
                         sorted(i["id"] for i in self.items),
                         "between the two runs, every item was handled")

    def test_the_cursor_is_matched_by_identity_not_position(self):
        """A batch that grew between slices must not shift the resume point."""
        done = []
        job = self.job()
        jobs.run_step(job, self.items, lambda i: done.append(i["id"]),
                      slice_size=100)
        self.assertEqual(job["cursor"], "r099")
        self.assertEqual(job["status"], jobs.RUNNING)

        # Somebody prepends fifty new records before the resume.
        grown = [{"id": f"new{i:03d}"} for i in range(50)] + self.items
        done.clear()
        jobs.run_step(job, grown, lambda i: done.append(i["id"]),
                      slice_size=1000)
        self.assertNotIn("r050", done, "an index-based resume would redo this")
        self.assertIn("r100", done)
        self.assertEqual(done[0], "r100")

    def test_a_cursor_that_is_no_longer_in_the_batch_starts_over(self):
        """The queue wins over the cursor when they disagree.

        The cursor exists to avoid redoing work, not to decide whether work is
        needed. If it names something that is gone, the honest move is to walk
        the batch that actually exists rather than to guess a position in it.
        """
        job = self.job()
        job["cursor"] = "a-record-from-a-previous-life"
        done = []
        jobs.run_step(job, self.items[:10], lambda i: done.append(i["id"]))
        self.assertEqual(len(done), 10)


class Failure(JobTest):

    def test_one_bad_record_is_recorded_and_skipped(self):
        def work(item):
            if item["id"] in ("r003", "r007"):
                raise ValueError("this record is malformed")

        job = self.job()
        result = jobs.run_step(job, self.items, work, slice_size=1000)
        self.assertEqual(result["failed"], 2)
        # Completed, not failed: two malformed records out of 250 is a batch
        # that ran. `completed_with_holds` means something else - a record
        # deliberately held for a human - and conflating the two would lose
        # the distinction an operator triages by.
        self.assertEqual(result["status"], jobs.COMPLETED)
        self.assertEqual(sorted(f["id"] for f in result["failures"]),
                         ["r003", "r007"])
        # And the reason travels, because "2 failed" without a why is a
        # number somebody has to reproduce by hand.
        self.assertIn("malformed", result["failures"][0]["error"])

    def test_a_batch_that_is_bad_throughout_aborts_early(self):
        """Twenty failures in twenty records is not a bad record, it is a bad
        run - a wrong config, a dead provider, a mis-parsed file. Continuing
        through 5,000 of them is how a mistake becomes an invoice."""
        seen = []

        def work(item):
            seen.append(item["id"])
            raise ValueError("everything is broken")

        job = self.job()
        jobs.run_step(job, self.items, work, slice_size=1000)
        self.assertLessEqual(len(seen), jobs.MIN_FAILURES_BEFORE_ABORT + 1)
        self.assertEqual(job["status"], jobs.FAILED)
        self.assertIn("problem with the batch", job["error"])

    def test_a_low_failure_rate_over_a_long_batch_does_not_abort(self):
        def work(item):
            if item["id"].endswith("7"):
                raise ValueError("occasional")

        job = self.job()
        result = jobs.run_step(job, self.items, work, slice_size=1000)
        self.assertEqual(result["status"], jobs.COMPLETED)
        self.assertEqual(result["failed"], 25)


class Spending(JobTest):

    def test_a_step_that_can_spend_refuses_without_a_budget(self):
        """Not a warning. The call raises before the first item is touched.

        `CLAUDE.md` is explicit: costs are real, cap before you fan out. A
        default budget would be a number nobody chose being spent on 5,000
        companies.
        """
        for kind in jobs.SPENDING_TYPES:
            job = self.job(kind)
            self.assertTrue(job["spends"])
            with self.assertRaises(jobs.JobError) as caught:
                jobs.run_step(job, self.items, lambda i: None)
            self.assertIn("budget", str(caught.exception))

    def test_a_step_that_cannot_spend_needs_no_budget(self):
        job = self.job(jobs.ICP_CLASSIFY)
        self.assertFalse(job["spends"])
        self.assertEqual(jobs.run_step(job, self.items[:5],
                                       lambda i: None)["processed"], 5)

    def test_a_budget_stops_the_run_when_it_is_exhausted(self):
        spent = []
        job = self.job(jobs.ENRICH)
        result = jobs.run_step(job, self.items,
                               lambda i: spent.append(i["id"]), budget=10,
                               slice_size=1000)
        self.assertEqual(len(spent), 10)
        self.assertEqual(result["spent"], 10)
        self.assertEqual(result["status"], jobs.RUNNING)
        self.assertLess(result["processed"], len(self.items))

        # Raising the budget continues from the cursor rather than starting
        # over, and does not re-spend on what was already done.
        jobs.run_step(job, self.items, lambda i: spent.append(i["id"]),
                      budget=25, slice_size=1000)
        self.assertEqual(len(spent), 25)
        self.assertEqual(len(set(spent)), 25)


class Bookkeeping(JobTest):

    def test_a_job_is_scoped_to_a_client(self):
        self.job()
        jobs.append(jobs.new(jobs.ICP_CLASSIFY, client="other", batch="b",
                             total=1))
        self.assertEqual(len(jobs.for_client("demo")), 1)

    def test_the_summary_counts_what_an_operator_asks_about(self):
        job = self.job()
        jobs.run_step(job, self.items[:5], lambda i: None)
        summary = jobs.summarise(jobs.for_client("demo"))
        for key in ("jobs", "active", "failed", "with_holds"):
            self.assertIn(key, summary)
