"""Batch processing from a browser, and everything it refuses to run.

`src/jobs.py` already has its own tests for the cursor, the budget and the
failure rate. What this file holds is the web layer's half of the bargain:
one slice per request, a resume point that survives, and a hard refusal on
every step that could spend money - by a table, not by the absence of a button.
"""
from src import jobs, store
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"
REVIEWER = "review@productive.test"
VIEWER = "client@productive.test"
ADMIN = "admin@productive.test"


class ThePageRenders(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)

    def test_it_renders(self):
        status, body, _ = self.session.get("/jobs")
        self.assertEqual(status, 200)
        self.assertIn("Batch processing", body)

    def test_it_names_what_it_will_not_run_rather_than_hiding_it(self):
        """"There is no button" and "that would spend money" are different
        things for an operator to be looking at."""
        _, body, _ = self.session.get("/jobs")
        for spending in ("enrich", "verify", "research", "personalize"):
            self.assertIn(spending, body)
        self.assertIn("paid", body)

    def test_it_explains_why_one_request_is_one_slice(self):
        _, body, _ = self.session.get("/jobs")
        self.assertIn("one slice", body.lower())
        self.assertIn("cursor", body.lower())


class RunningOne(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)
        self._jobs = [dict(j) for j in jobs.load()]

    def tearDown(self):
        jobs.save(self._jobs)

    def run_slice(self, batch="uk-digital", job_type=jobs.ICP_CLASSIFY,
                  **extra):
        fields = {"csrf": self.session.csrf("/jobs"), "job_type": job_type,
                  "batch": batch}
        fields.update(extra)
        return self.session.post("/jobs/run", fields)

    def test_one_request_runs_one_slice_and_records_a_cursor(self):
        status, body, _ = self.run_slice()
        self.assertEqual(status, 200)
        mine = [j for j in jobs.load() if j["client"] == "productive"]
        self.assertTrue(mine, "no job was created")
        job = mine[-1]
        self.assertEqual(job["type"], jobs.ICP_CLASSIFY)
        self.assertEqual(job["batch"], "uk-digital")
        self.assertEqual(job["slices"], 1)
        self.assertIsNotNone(job["cursor"])
        self.assertFalse(job["spends"])

    def test_clicking_the_same_job_again_does_not_redo_the_work(self):
        """The cursor is what makes a second click continue rather than repeat.

        The demo batches are smaller than one slice, so a single click
        finishes them - which makes this the observable half of the same
        property: the job is done, and asking again does not process a record
        twice.
        """
        self.run_slice()
        job = [j for j in jobs.load() if j["client"] == "productive"][-1]
        processed = job["processed"]
        self.assertEqual(processed, len(
            [r for r in store.load() if r.get("batch") == "uk-digital"]))

        self.run_slice(job_id=job["id"])
        again = jobs.get(job["id"])
        self.assertEqual(again["processed"], processed,
                         "a second click reprocessed records already done")

    def test_a_terminal_job_stays_terminal(self):
        self.run_slice()
        job = [j for j in jobs.load() if j["client"] == "productive"][-1]
        self.assertIn(job["status"], jobs.TERMINAL)
        self.run_slice(job_id=job["id"])
        self.assertEqual(jobs.get(job["id"])["status"], job["status"])

    def test_a_finished_job_leaves_the_whole_batch_qualified(self):
        self.run_slice()
        job = [j for j in jobs.load() if j["client"] == "productive"][-1]
        self.assertIn(job["status"], jobs.TERMINAL)
        rows = [r for r in store.load() if r.get("batch") == "uk-digital"]
        self.assertTrue(rows)
        for rec in rows:
            self.assertTrue((rec.get("qualification") or {}).get("verdict"),
                            f"{rec['id']} came out of the job unqualified")

    def test_running_is_written_to_the_audit_log(self):
        self.run_slice()
        admin = self.signin(ADMIN)
        _, log, _ = admin.get("/audit")
        self.assertIn("job.ran", log)

    def test_a_job_can_be_stopped(self):
        """Every demo batch fits in one slice, so the job is made here.

        Running one and hoping it is still in flight would be a test that
        passes by accident on a slow machine and skips on a fast one.
        """
        queued = jobs.new(jobs.ICP_CLASSIFY, "productive", batch="uk-digital",
                          total=999, created_by=OPERATOR)
        jobs.append(queued)
        status, _, _ = self.session.post("/jobs/cancel", {
            "csrf": self.session.csrf("/jobs"), "job_id": queued["id"]})
        self.assertEqual(status, 200)
        stopped = jobs.get(queued["id"])
        self.assertEqual(stopped["status"], jobs.CANCELLED)
        self.assertIn(OPERATOR, stopped["error"])

    def test_stopping_is_written_to_the_audit_log(self):
        queued = jobs.new(jobs.ICP_CLASSIFY, "productive", batch="uk-digital",
                          total=999, created_by=OPERATOR)
        jobs.append(queued)
        self.session.post("/jobs/cancel", {
            "csrf": self.session.csrf("/jobs"), "job_id": queued["id"]})
        admin = self.signin(ADMIN)
        _, log, _ = admin.get("/audit")
        self.assertIn("job.cancelled", log)

    def test_a_batch_with_no_records_here_is_refused(self):
        status, body, _ = self.run_slice(batch="not-a-batch")
        self.assertEqual(status, 400)
        self.assertIn("no records", body)

    def test_running_without_a_csrf_token_is_refused(self):
        status, _, _ = self.session.post("/jobs/run", {
            "job_type": jobs.ICP_CLASSIFY, "batch": "uk-digital"})
        self.assertEqual(status, 403)
        self.assertEqual([j for j in jobs.load()
                          if j["client"] == "productive"], [])


class NothingThatSpendsWillRun(WebTest):
    """The refusal is structural. It is not the absence of a button."""

    def setUp(self):
        self.session = self.signin(OPERATOR)
        self._jobs = [dict(j) for j in jobs.load()]

    def tearDown(self):
        jobs.save(self._jobs)

    def test_every_spending_job_type_is_refused_by_name(self):
        for job_type in jobs.SPENDING_TYPES:
            status, body, _ = self.session.post("/jobs/run", {
                "csrf": self.session.csrf("/jobs"), "job_type": job_type,
                "batch": "uk-digital"})
            self.assertEqual(status, 400, job_type)
            self.assertIn("spend", body, job_type)
            self.assertEqual(
                [j for j in jobs.load() if j.get("type") == job_type], [],
                f"a {job_type} job was created")

    def test_a_type_this_screen_does_not_run_is_refused_with_a_reason(self):
        for job_type in (jobs.RENDER, jobs.INGEST, jobs.PREPARE_CAMPAIGN):
            status, body, _ = self.session.post("/jobs/run", {
                "csrf": self.session.csrf("/jobs"), "job_type": job_type,
                "batch": "uk-digital"})
            self.assertEqual(status, 400, job_type)
            self.assertIn("not runnable from here", body, job_type)

    def test_an_invented_job_type_is_refused(self):
        status, body, _ = self.session.post("/jobs/run", {
            "csrf": self.session.csrf("/jobs"),
            "job_type": "spend_everything", "batch": "uk-digital"})
        self.assertEqual(status, 400)
        self.assertEqual(jobs.load(), self._jobs)

    def test_no_job_the_web_layer_creates_can_spend(self):
        self.session.post("/jobs/run", {
            "csrf": self.session.csrf("/jobs"),
            "job_type": jobs.ICP_CLASSIFY, "batch": "uk-digital"})
        for job in jobs.load():
            if job.get("client") == "productive":
                self.assertFalse(job["spends"])
                self.assertIsNone(job["budget"])
                self.assertEqual(job["spent"], 0)


class WhoMayRun(WebTest):

    def test_a_viewer_cannot_see_the_page(self):
        self.assertEqual(self.signin(VIEWER).get("/jobs")[0], 403)

    def test_a_reviewer_can_read_it_but_cannot_run(self):
        """`batch.run` belongs to the people who run the machine."""
        reviewer = self.signin(REVIEWER)
        status, body, _ = reviewer.get("/jobs")
        self.assertEqual(status, 200)
        self.assertIn("not run anything", body)

        status, _, _ = reviewer.post("/jobs/run", {
            "csrf": reviewer.csrf("/jobs"), "job_type": jobs.ICP_CLASSIFY,
            "batch": "uk-digital"})
        self.assertEqual(status, 403)


class JobsCannotCrossAWorkspace(WebTest):

    def setUp(self):
        self._jobs = [dict(j) for j in jobs.load()]

    def tearDown(self):
        jobs.save(self._jobs)

    def test_another_workspaces_batch_is_refused(self):
        session = self.signin(OPERATOR)
        status, body, _ = session.post("/jobs/run", {
            "csrf": session.csrf("/jobs"), "job_type": jobs.ICP_CLASSIFY,
            "batch": "apac-recruiting"})
        self.assertEqual(status, 400)
        self.assertIn("no records", body)

    def test_another_workspaces_job_id_is_not_found(self):
        theirs = jobs.new(jobs.ICP_CLASSIFY, "contactout",
                          batch="apac-recruiting", total=3)
        jobs.append(theirs)
        session = self.signin(OPERATOR)
        status, _, _ = session.post("/jobs/cancel", {
            "csrf": session.csrf("/jobs"), "job_id": theirs["id"]})
        self.assertEqual(status, 404)
        self.assertEqual(jobs.get(theirs["id"])["status"], jobs.QUEUED)

    def test_the_list_shows_only_this_workspaces_jobs(self):
        theirs = jobs.new(jobs.ICP_CLASSIFY, "contactout",
                          batch="apac-recruiting", total=3)
        jobs.append(theirs)
        session = self.signin(OPERATOR)
        _, body, _ = session.get("/jobs")
        self.assertNotIn(theirs["id"], body)
