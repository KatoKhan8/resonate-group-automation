"""GATE 1. The review file: where it reads from, and where it may be written.

Two properties, and each of them is the whole point of one half of the file.

**IT READS THE PROVIDER.** A review file built from our own render proves
that our render is our render. The push that caused the incident rendered
nothing - it POSTed string literals - so a file generated locally would
have shown copy that was never sent and missed copy that was.

**IT NEVER LEAVES `work/`.** It carries real recipients. `work/` is
gitignored; `docs/` is committed and pushed to GitHub. The filter is
self-tested here against every path somebody would reach for, and against
a `..` that spells its way back out.
"""
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree

from src import copyprovenance, reviewfile, store

CONFIG = {"cadence": "productive_li_heavy_v1", "name": "productive"}

#: A provider snapshot in the exact shape `scripts/copy_snapshot.py`
#: writes: the four reads, as EmailBison answers them.
SNAPSHOT = {
    "provider_campaign_id": "999",
    "campaign": {"id": 999, "name": "TEST", "status": "paused"},
    "senders": [4280, 4281],
    "sender_pool": [
        {"id": 4280, "name": "Dana Whitfield", "email": "k@example.test"},
        {"id": 4281, "name": "Owen Marsh", "email": "b@example.test"},
    ],
    "sequence": [
        {"id": 700, "order": 1, "email_subject": "{SUBJECT_1}",
         "email_body": "<p>{BODY_1}</p>", "thread_reply": False},
        {"id": 701, "order": 2, "email_subject": "Re: {SUBJECT_1}",
         "email_body": "<p>{BODY_2}</p>", "thread_reply": True},
    ],
    "leads": [
        {"id": 1, "email": "rhett@northwind.test", "first_name": "Rhett",
         "company": "Northwind", "custom_variables": [
             {"name": "record_id", "value": "northwind.test"},
             {"name": "subject_1", "value": "quick question about Northwind"},
             {"name": "body_1", "value":
              "Hi Rhett, I was reading the Northwind site this week and the "
              "line about check out a few of our case studies is what made "
              "me write.\n\nI work with agency founders.\n\nZvonimir"},
             {"name": "body_2", "value": "Following up.\n\nZvonimir"}]},
        {"id": 2, "email": "scott@eastwind.test", "first_name": "Scott",
         "company": "Eastwind", "custom_variables": [
             {"name": "record_id", "value": "eastwind.test"},
             {"name": "subject_1", "value": "margin"},
             {"name": "body_1", "value": "Scott, your site says margin is "
              "known at the end of the month.\n\nIs that how it works?"}]},
    ],
    "queue": [
        # Lead 1, step 1: the provider has ALREADY rendered this one, and
        # what it holds differs from the lead's variables. The review file
        # must print the queue's words, not ours.
        {"id": 90, "sequence_step_id": 700, "status": "sent",
         "sent_at": "2026-09-25T09:00:00Z", "scheduled_date": "2026-09-25",
         "email_subject": "quick question about Northwind",
         # THE PROVIDER'S OWN HTML, and deliberately not byte-identical to
         # the lead's stored variables: the review file must print THESE.
         # A generator that rendered our side would print the other ones
         # and nobody would be able to tell the difference.
         "email_body": "<p>Hi Rhett, I was reading the Northwind site this "
                       "week and the line about check out a few of our case "
                       "studies is what made me write.<br><br>I work with "
                       "agency founders.<br><br>Zvonimir</p>",
         "sender_email": {"id": 4280, "name": "Dana Whitfield",
                          "email": "k@example.test"},
         "lead": {"id": 1}},
    ],
}

#: The research pack for one of those leads, with one quotable sentence and
#: a menu.
PACKS = {
    "northwind.test": {"domain": "northwind.test", "facts": [
        {"fact_id": "aaaa1111", "kind": "site_page",
         "source_url": "https://northwind.test/",
         "snippet": "Home About Services check out a few of our case "
                    "studies Contact us"}]},
    "eastwind.test": {"domain": "eastwind.test", "facts": [
        {"fact_id": "bbbb2222", "kind": "site_page",
         "source_url": "https://eastwind.test/",
         "snippet": "Scott, your site says margin is known at the end of "
                    "the month. We help agencies see it sooner."}]},
}


class ItReadsTheProvider(unittest.TestCase):

    def setUp(self):
        self.rows = reviewfile.rows(SNAPSHOT, packs=PACKS, config=CONFIG,
                                    client="productive")

    def test_the_queue_wins_over_anything_we_would_render(self):
        step = [s for s in self.rows[0]["steps"] if s["order"] == 1][0]
        self.assertEqual(step["source"], "provider_queue")
        self.assertIn("<br><br>", step["body"],
                      "this must be the provider's own HTML, not our render")

    def test_a_step_with_no_queue_row_is_still_provider_truth(self):
        # The stored sequence template filled from the lead's STORED
        # variables. Two provider reads, not one of ours.
        step = [s for s in self.rows[0]["steps"] if s["order"] == 2][0]
        self.assertEqual(step["source"], "provider_rendered")
        self.assertIn("Following up", step["body"])

    def test_the_sender_name_comes_off_the_queue_row(self):
        self.assertEqual(self.rows[0]["sender_name"], "Dana Whitfield")
        self.assertEqual(self.rows[0]["sender_mailbox"], "k@example.test")

    def test_an_unbound_lead_names_the_pool_rather_than_guessing_one(self):
        self.assertIn("NOT BOUND YET", self.rows[1]["sender_name"])
        self.assertIn("Owen Marsh", self.rows[1]["sender_name"])

    def test_a_step_with_no_copy_says_so_rather_than_printing_nothing(self):
        # Lead 2 carries no `body_2`, so step 2 renders `{BODY_2}`.
        row = self.rows[1]
        self.assertIn("unresolved merge field", " ".join(row["gate2_reasons"]))

    def test_the_pack_fact_and_its_source_url_are_printed(self):
        row = self.rows[0]
        self.assertEqual(row["pack_fact"],
                         "check out a few of our case studies")
        self.assertEqual(row["pack_fact_source_url"], "https://northwind.test/")

    def test_a_lead_quoting_navigation_is_held(self):
        self.assertEqual(self.rows[0]["verdict"], "HOLD")
        self.assertFalse(self.rows[0]["gate3_ok"])

    def test_the_incident_copy_is_named_by_gate_two(self):
        why = " ".join(self.rows[0]["gate2_reasons"])
        self.assertIn("refused term", why)
        self.assertIn("mailbox belongs to", why)


class ItMayNotLeaveWork(unittest.TestCase):
    """The redaction filter, self-tested against every path somebody would
    reach for. Checked BEFORE the first byte, not after.

    These run WITHOUT isolating the store on purpose: the paths under test
    are the production ones, and what is asserted is that they are refused.
    """

    def test_docs_is_refused_by_name(self):
        with self.assertRaises(reviewfile.ReviewRefused) as caught:
            reviewfile.refuse_outside_work(
                os.path.join(reviewfile.root(), "docs", "review.xlsx"))
        self.assertIn("docs/", str(caught.exception))

    def test_every_committed_directory_is_refused(self):
        for name in ("docs", "src", "tests", "scripts", "batches", "config",
                     "benchmarks", "prompts", "."):
            with self.subTest(directory=name):
                with self.assertRaises(reviewfile.ReviewRefused):
                    reviewfile.refuse_outside_work(
                        os.path.join(reviewfile.root(), name, "review.xlsx"))

    def test_a_traversal_back_out_of_work_is_refused(self):
        with self.assertRaises(reviewfile.ReviewRefused):
            reviewfile.refuse_outside_work(
                os.path.join(reviewfile.root(), "work", "..", "docs", "r.xlsx"))

    def test_a_directory_merely_starting_with_work_is_refused(self):
        with self.assertRaises(reviewfile.ReviewRefused):
            reviewfile.refuse_outside_work(
                os.path.join(reviewfile.root(), "workspace-notes", "r.xlsx"))

    def test_somewhere_else_entirely_is_refused(self):
        with self.assertRaises(reviewfile.ReviewRefused):
            reviewfile.refuse_outside_work(
                os.path.join(tempfile.gettempdir(), "review.xlsx"))

    def test_the_real_work_directory_is_refused_to_a_TEST(self):
        # The other barrier, pointing the other way. In production this path
        # is the only allowed one; under test it is the real client state
        # directory and writing a review file there puts 1,465 real
        # recipients beside the live queue.
        with self.assertRaises(store.ProductionStateUnderTest):
            reviewfile.refuse_outside_work(
                os.path.join(reviewfile.root(), "work", "review", "r.xlsx"))

    def test_an_isolated_state_directory_is_allowed(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        self.addCleanup(store.use_directory(tmp))
        reviewfile.refuse_outside_work(os.path.join(tmp, "review", "r.xlsx"))
        self.assertTrue(reviewfile.out_dir().startswith(
            os.path.realpath(tmp)))

    def test_work_is_gitignored(self):
        # The filter's whole premise. If this ever stops being true the
        # refusal above protects nothing.
        with open(os.path.join(reviewfile.root(), ".gitignore"),
                  encoding="utf-8") as f:
            patterns = {l.strip().rstrip("/") for l in f}
        self.assertIn("work", patterns)


class TheFilesItActuallyWrites(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(store.use_directory(self.tmp))
        self.dir = os.path.join(self.tmp, "review")
        self.rows = reviewfile.rows(SNAPSHOT, packs=PACKS, config=CONFIG,
                                    client="productive")

    def test_both_files_are_written_under_the_state_directory(self):
        result = reviewfile.write("999", self.rows, directory=self.dir,
                                  date="2026-09-25")
        allowed = reviewfile.work_dir()
        for key in ("xlsx", "html"):
            self.assertTrue(os.path.exists(result[key]))
            self.assertTrue(os.path.realpath(result[key]).startswith(allowed))

    def test_the_default_location_is_review_beside_the_queue(self):
        result = reviewfile.write("999", self.rows, date="2026-09-25")
        self.assertEqual(os.path.dirname(os.path.realpath(result["xlsx"])),
                         os.path.realpath(reviewfile.out_dir()))

    def test_the_html_carries_the_words_the_provider_holds(self):
        result = reviewfile.write("999", self.rows, directory=self.dir,
                                  date="2026-09-25")
        with open(result["html"], encoding="utf-8") as f:
            page = f.read()
        self.assertIn("check out a few of our case studies", page)
        self.assertIn("https://northwind.test/", page)
        self.assertIn("Dana Whitfield", page)

    def test_a_formula_in_a_company_name_is_not_executable(self):
        rows = list(self.rows)
        rows[0] = dict(rows[0], company="=cmd|' /C calc'!A0")
        result = reviewfile.write("999", rows, directory=self.dir,
                                  date="2026-09-25")
        # Read the sheet part out of the ZIP with the standard library:
        # a test that needed openpyxl to check a file written without it
        # would be testing that two libraries agree.
        with zipfile.ZipFile(result["xlsx"]) as book:
            sheet = book.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("&#39;=cmd|&#39; /C calc&#39;!A0".replace("&#39;", "'"),
                      sheet.replace("&quot;", '"'))
        self.assertNotIn(">=cmd", sheet,
                         "the cell starts with = and a spreadsheet would "
                         "evaluate it")

    def test_the_workbook_is_a_readable_archive(self):
        result = reviewfile.write("999", self.rows, directory=self.dir,
                                  date="2026-09-25")
        with zipfile.ZipFile(result["xlsx"]) as book:
            self.assertIsNone(book.testzip())
            names = set(book.namelist())
            for part in ("[Content_Types].xml", "_rels/.rels",
                         "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
                         "xl/styles.xml", "xl/worksheets/sheet1.xml"):
                self.assertIn(part, names)
            for part in names:
                # Well-formed, every part. A ZIP of broken XML opens as a
                # ZIP and not as a spreadsheet.
                ElementTree.fromstring(book.read(part))

    def test_writing_to_docs_raises_before_any_file_appears(self):
        target = os.path.join(reviewfile.root(), "docs",
                              "review-selftest-%d" % os.getpid())
        with self.assertRaises(reviewfile.ReviewRefused):
            reviewfile.write("999", self.rows, directory=target,
                             date="2026-09-25")
        self.assertFalse(os.path.exists(target),
                         "the refusal landed after the directory was made")


class TheSnapshotFeedsTheGenerator(unittest.TestCase):
    """Existence is not function. A snapshot key nobody reads is a provider
    read nobody uses, and a key the generator reads that the snapshot never
    writes is a column that is silently always empty. Both directions are
    checked by running one against the other on a stubbed transport."""

    def setUp(self):
        import scripts.copy_snapshot as snap
        from src.providers import bison
        self.snap = snap
        self.bison = bison
        # ONE SEAM, NOT FIVE STUBS. Every read in `snapshot` goes through
        # `providers.request`, so the whole thing - the paged walks and
        # their refusals included - runs for real against a page table.
        # Stubbing `bison.campaign_leads` instead would have tested that a
        # stub returns what a stub was given.
        self.pages = {
            "/campaigns/999": {"data": SNAPSHOT["campaign"]},
            "/campaigns/999/sender-emails": {
                "data": SNAPSHOT["sender_pool"],
                "meta": {"total": 2, "last_page": 1}},
            "/campaigns/999/leads": {
                "data": SNAPSHOT["leads"],
                "meta": {"total": 2, "last_page": 1}},
            "/campaigns/999/scheduled-emails": {
                "data": SNAPSHOT["queue"],
                "meta": {"total": 1, "last_page": 1}},
            "/campaigns/999/sequence-steps": {"data": SNAPSHOT["sequence"]},
        }

        def fake_request(_method, url, _headers=None, *_a, **_kw):
            path = url.split("/api", 1)[1].split("?")[0]
            return 200, self.pages[path]

        # `bison.request` for the paged walks, `providers.request` for the
        # single campaign read inside `reviewfile.snapshot`. Both resolve
        # their name from the module at call time, so both have to move.
        from src import providers
        for module in (bison, providers):
            self.addCleanup(setattr, module, "request", module.request)
            module.request = fake_request
        # No credential is read. A test that needed one would be a test
        # that could reach a real client estate.
        self.addCleanup(setattr, bison, "headers", bison.headers)
        bison.headers = lambda: {"Authorization": "Bearer x"}

    def test_what_the_snapshot_writes_is_what_the_generator_consumes(self):
        built = self.snap.snapshot("999")
        rows = reviewfile.rows(built, packs=PACKS, config=CONFIG,
                               client="productive")
        self.assertEqual(len(rows), 2)
        # The mailbox OWNER's name - the field the signature gate compares
        # against - has to survive the round trip, and it only exists
        # because the snapshot reads the pool rather than the id list.
        self.assertEqual(rows[0]["sender_name"], "Dana Whitfield")
        self.assertIn("Owen Marsh", rows[1]["sender_name"])

    def test_a_short_read_is_refused_rather_than_reported_as_complete(self):
        # The provider says the campaign holds two leads and answers with
        # none. A snapshot that reported that as an empty campaign would
        # make an unaudited campaign look clean, which is the failure this
        # whole lane exists about.
        self.pages["/campaigns/999/leads"] = {
            "data": [], "meta": {"total": 2, "last_page": 1}}
        with self.assertRaises(self.bison.PartialInventory) as caught:
            self.snap.snapshot("999")
        self.assertIn("partial", str(caught.exception).lower())


class EveryPushProducesOne(unittest.TestCase):
    """Existence is not function. A generator nothing calls is a generator
    that will not be there the next time somebody pushes 690 leads."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(store.use_directory(self.tmp))
        from src import providers
        from src.providers import bison
        for name, value in (
                ("campaign_senders", lambda _c: SNAPSHOT["senders"]),
                ("campaign_sender_emails", lambda _c: SNAPSHOT["sender_pool"]),
                ("sequence_steps", lambda _c: SNAPSHOT["sequence"]),
                ("campaign_leads", lambda _c, **_k: SNAPSHOT["leads"]),
                ("scheduled_emails", lambda _c, **_k: SNAPSHOT["queue"]),
                ("headers", lambda: {"Authorization": "Bearer x"})):
            self.addCleanup(setattr, bison, name, getattr(bison, name))
            setattr(bison, name, value)
        # The campaign row is the one read `snapshot` takes directly.
        self.addCleanup(setattr, providers, "request", providers.request)
        providers.request = (
            lambda _m, _u, _h=None, *_a, **_k: (200, {"data": SNAPSHOT["campaign"]}))

    def test_staging_builds_the_file_from_the_provider_readback(self):
        from src import bisonfactory
        result = bisonfactory._review_file(
            "999", {"campaign_id": "test-cohort", "client": "productive"},
            CONFIG, {})
        self.assertNotIn("error", result, result)
        self.assertTrue(os.path.exists(result["xlsx"]))
        with open(result["html"], encoding="utf-8") as f:
            page = f.read()
        self.assertIn("Dana Whitfield", page)
        self.assertIn("check out a few of our case studies", page)

    def test_a_reporting_failure_does_not_abort_a_stage_that_succeeded(self):
        from src import bisonfactory
        from src.providers import bison
        bison.scheduled_emails = lambda _c, **_k: (_ for _ in ()).throw(
            RuntimeError("the queue route is down"))
        result = bisonfactory._review_file(
            "999", {"campaign_id": "test-cohort", "client": "productive"},
            CONFIG, {})
        # Reported, not raised: the leads are staged either way, and an
        # operator reading this knows there is no file to approve from.
        self.assertIn("the queue route is down", result["error"])


if __name__ == "__main__":
    unittest.main()
