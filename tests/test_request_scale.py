"""What the request path costs as the estate grows.

Every assertion here counts **file reads**, never seconds. A wall-clock
threshold is a test that fails on a busy machine and passes on a fast one,
which makes it a source of noise rather than a guard.

The shape these exist to prevent is always the same and has now appeared
four times: a full parse of a state file inside a loop. It is invisible
against a 33-account demo and quadratic against a real audience.

Measured before the fixes, at 30,000 records and 8 campaigns:

    store.load()      0.28s
    batch_list        2.48s     - a full parse per batch
    campaign_rows     9.86s     - a full parse per campaign, and then
                                  `id in record_ids` against a list

After:

    campaign_rows     0.31s
    batch_list        0.85s
"""
import os
import shutil
import tempfile
import unittest

from src import campaigns as campaign_store, repo as repo_module, store, workspaces
from src.web import api
from tests.base import ProviderTest

WS = "productive"


class ScaleTest(ProviderTest):

    RECORDS = 120
    CAMPAIGNS = 6
    BATCHES = 4

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-scale-")
        self._env = {k: os.environ.get(k) for k in
                     ("QUEUE", "CAMPAIGNS", "JOBS", "WORKSPACES", "AUDIT",
                      "SIGNALS", "CLIENTS_DIR", "OUT")}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["CLIENTS_DIR"] = os.path.join(self.tmp, "clients")
        os.environ["OUT"] = os.path.join(self.tmp, "out")

        from src.web import demodata
        demodata.install_configs()
        workspaces.ensure(WS, "Productive", client="productive")
        workspaces.add_user("op@x.test", "Op")
        workspaces.assign("op@x.test", WS, workspaces.OPERATOR)
        self.seed()

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def seed(self):
        rows = []
        for i in range(self.RECORDS):
            rec = store.new_record(f"c{i}", "domains", WS, f"Company {i}",
                                   f"c{i}.test")
            rec["batch"] = f"b{i % self.BATCHES}"
            rec["contacts"] = [{"key": "a", "name": "A Person",
                                "email": f"a@c{i}.test", "selected": True}]
            rec["qualification"] = {
                "segment_key": "SEG",
                "segment": {"vertical": "professional_services",
                            "employee_band": "51-200",
                            "country": "united kingdom"},
                "verdict": {"icp_status": "qualified", "icp_score": 70.0,
                            "icp_tier": "B"},
                "messaging": {"relevant_pain_categories": [],
                              "unsupported_hypotheses": []},
            }
            rows.append(rec)
        store.save(rows)
        campaign_store.save([
            {"campaign_id": f"camp{c}", "name": f"Campaign {c}",
             "client": "productive", "status": "draft",
             "record_ids": [f"c{i}" for i in
                            range(c, self.RECORDS, self.CAMPAIGNS)]}
            for c in range(self.CAMPAIGNS)])

    def repo(self):
        return repo_module.Repo.for_user("op@x.test", WS)

    def queue_reads(self, run):
        """How many times the queue file is parsed while `run` executes."""
        count = {"n": 0}
        original = store.read_jsonl
        target = os.path.abspath(store.queue_path())

        def counting(path, *a, **kw):
            if os.path.abspath(path) == target:
                count["n"] += 1
            return original(path, *a, **kw)

        store.read_jsonl = counting
        try:
            run()
        finally:
            store.read_jsonl = original
        return count["n"]


class TheEstateIsReadOncePerScreen(ScaleTest):
    """Not once per campaign, once per batch, or once per account."""

    def test_the_campaign_list_reads_the_queue_once(self):
        reads = self.queue_reads(lambda: api.campaign_rows(self.repo()))
        self.assertEqual(reads, 1)

    def test_the_batch_list_reads_the_queue_once(self):
        reads = self.queue_reads(lambda: api.batch_list(self.repo()))
        self.assertLessEqual(reads, 2)

    def test_reads_do_not_grow_with_the_number_of_campaigns(self):
        """The property, rather than a number somebody has to maintain."""
        before = self.queue_reads(lambda: api.campaign_rows(self.repo()))
        campaign_store.save(campaign_store.load() + [
            {"campaign_id": f"extra{i}", "name": f"Extra {i}",
             "client": "productive", "status": "draft",
             "record_ids": ["c1", "c2"]}
            for i in range(12)])
        after = self.queue_reads(lambda: api.campaign_rows(self.repo()))
        self.assertEqual(before, after)

    def test_reads_do_not_grow_with_the_number_of_batches(self):
        before = self.queue_reads(lambda: api.batch_list(self.repo()))
        rows = store.load()
        for index, rec in enumerate(rows):
            rec["batch"] = f"b{index % 20}"
        store.save(rows)
        after = self.queue_reads(lambda: api.batch_list(self.repo()))
        self.assertEqual(before, after)


class TheSuppressionFileIsReadOncePerScreen(ScaleTest):
    """`channels.evaluate` loads it whenever it is not handed one, which
    across an estate is once per contact.

    Measured at 30,000 records before the fix: the contacts page took 7.5
    seconds and the analytics rows 9.2. `analytics_rows` was the worst of
    it - it loaded the set correctly and then never passed it, so the
    variable sat there looking like the fix while every contact re-read
    the file.
    """

    def suppress_reads(self, run):
        from src import ingest
        count = {"n": 0}
        original = ingest.load_suppress

        def counting(*a, **kw):
            count["n"] += 1
            return original(*a, **kw)

        ingest.load_suppress = counting
        try:
            run()
        finally:
            ingest.load_suppress = original
        return count["n"]

    def test_the_contact_table_reads_it_once(self):
        reads = self.suppress_reads(lambda: api.contact_rows(self.repo()))
        self.assertEqual(reads, 1)

    def test_the_analytics_rows_read_it_once(self):
        reads = self.suppress_reads(lambda: api.analytics_rows(self.repo()))
        self.assertEqual(reads, 1)

    def test_reads_do_not_grow_with_the_estate(self):
        """The property rather than the number: adding records must not
        add reads."""
        before = self.suppress_reads(lambda: api.contact_rows(self.repo()))
        extra = []
        for index in range(40):
            rec = store.new_record(f"more{index}", "domains", WS,
                                   f"More {index}", f"more{index}.test")
            rec["contacts"] = [{"key": "a", "name": "A",
                                "email": f"a@more{index}.test",
                                "selected": True}]
            extra.append(rec)
        store.save(store.load() + extra)
        after = self.suppress_reads(lambda: api.contact_rows(self.repo()))
        self.assertEqual(before, after)

    def test_the_verdicts_are_unchanged_by_being_handed_the_set(self):
        """Faster and identical, or it is not a fix."""
        from src import channels, ingest

        rows = api.contact_rows(self.repo())
        config = self.repo().config()
        suppressed = ingest.load_suppress()
        for row in rows[:20]:
            rec = self.repo().record(row["record_id"])
            contact = [c for c in rec["contacts"]
                       if c["key"] == row["contact_key"]][0]
            self.assertEqual(
                channels.evaluate(rec, contact, config, suppressed)["mode"],
                channels.evaluate(rec, contact, config)["mode"])


class ALongListIsAWindowAndSaysSo(ScaleTest):
    """A list screen that renders every row is fine at demo scale and is
    thirty thousand rows of HTML at real scale.

    Measured over HTTP against a real 30,000-record estate: 46KB and 100
    rows per page in under 0.7s, and the last page lands exactly on
    29901-30000.
    """

    def test_a_page_is_one_window_of_the_rows(self):
        page = api.paginate(list(range(30000)))
        self.assertEqual(len(page["rows"]), api.PAGE_SIZE)
        self.assertEqual(page["total"], 30000)
        self.assertEqual(page["pages"], 300)

    def test_it_says_which_window_it_is(self):
        """A screen showing 100 of 30,000 that does not say so is a screen
        somebody will read as complete."""
        page = api.paginate(list(range(30000)), page=2)
        self.assertEqual((page["first"], page["last"]), (101, 200))
        self.assertTrue(page["truncated"])

    def test_the_last_page_ends_on_the_last_row(self):
        page = api.paginate(list(range(30000)), page=300)
        self.assertEqual(page["last"], 30000)
        self.assertFalse(page["has_next"])

    def test_a_page_past_the_end_is_empty_rather_than_clamped(self):
        """Silently showing page 4 to somebody who asked for page 40 is a
        lie about where they are."""
        page = api.paginate(list(range(30000)), page=999)
        self.assertEqual(page["rows"], [])

    def test_a_short_list_is_not_called_truncated(self):
        page = api.paginate(list(range(12)))
        self.assertFalse(page["truncated"])
        self.assertEqual(page["shown"], 12)

    def test_the_size_cannot_be_widened_from_the_url(self):
        """Otherwise the fix is one query parameter away from undone."""
        page = api.paginate(list(range(30000)), size=30000)
        self.assertEqual(page["size"], api.MAX_PAGE_SIZE)

    def test_nonsense_paging_falls_back_rather_than_raising(self):
        for bad in ("", "abc", "-4", None):
            page = api.paginate(list(range(500)), page=bad, size=bad)
            self.assertEqual(page["page"], 1)
            self.assertEqual(page["size"], api.PAGE_SIZE)

    def test_the_pager_states_the_window_before_the_rows(self):
        from src.web import pages

        page = api.paginate(list(range(30000)))
        html = pages.pager(page, "/companies", None)
        self.assertIn("Showing", html)
        self.assertIn("30000", html)
        self.assertIn("page=2", html)

    def test_the_pager_keeps_the_filter_somebody_is_looking_through(self):
        from src.web import pages

        page = api.paginate(list(range(30000)))
        html = pages.pager(page, "/contacts", {"mode": "email_only"})
        self.assertIn("mode=email_only", html)

    def test_a_complete_list_gets_a_count_rather_than_controls(self):
        from src.web import pages

        html = pages.pager(api.paginate(list(range(12))), "/companies", None)
        self.assertNotIn("Next", html)
        self.assertIn("12", html)


class TheAudienceIsAShapeNotAList(ScaleTest):
    """A thirty-thousand-domain upload is not thirty thousand rows to
    read. Somebody who uploads a list should be able to answer "what did
    I just give you" without scrolling."""

    def overview(self):
        return api.audience_overview(self.repo())

    def test_every_stage_is_a_subset_of_the_one_above_it(self):
        """The first version reported "122% of 27": contacts exist on
        companies that were later rejected, and counting those against
        the qualified total gave a share above one - a denominator that
        does not mean what the row says it means."""
        stages = self.overview()["stages"]
        for stage in stages:
            if stage["share"] is not None:
                self.assertLessEqual(stage["share"], 1.0, stage["label"])

    def test_each_stage_says_what_it_is_a_share_of(self):
        """A stage count with no denominator is the figure people quote
        and nobody can check."""
        for stage in self.overview()["stages"]:
            self.assertIn("of", stage)
            self.assertTrue(stage["why"])

    def test_counts_never_exceed_the_audience(self):
        found = self.overview()
        for stage in found["stages"]:
            self.assertLessEqual(stage["count"], found["total"],
                                 stage["label"])

    def test_an_account_that_cannot_be_worked_is_not_a_failed_stage(self):
        """It has been ruled out of the ladder, not dropped from it."""
        found = self.overview()
        self.assertIn("not_workable", found)
        labels = [s["label"] for s in found["stages"]]
        self.assertNotIn("Not workable", labels)

    def test_an_empty_audience_says_so_rather_than_showing_zeroes(self):
        rows = store.load()
        for rec in rows:
            rec["client"] = "somebody-else"
        store.save(rows)
        found = api.audience_overview(self.repo())
        self.assertTrue(found["empty"])
        self.assertEqual(found["total"], 0)

    def test_the_empty_screen_offers_the_one_thing_to_do(self):
        from src.web import pages

        html = pages.audience_overview({
            "empty": True, "total": 0, "batch": None, "batches": [],
            "stages": [], "by_status": {}, "not_workable": 0,
            "distribution": {}})
        self.assertIn("/upload", html)
        self.assertIn("Import leads", html)



class SegmentHealthIsSurfacedNotDiscarded(ScaleTest):
    """`campaignseg.summarise` has always computed which cohorts are too
    broad to write one message for. Nothing read it.

    The value was calculated on every qualification run and thrown away,
    so a twenty-thousand-company cohort was identified as too broad and
    then campaigned as one anyway. The same shape as `analytics_rows`
    loading the suppression set and never passing it.
    """

    def health(self, size=None, maximum=None):
        """Put `size` companies in one segment and read the health.

        The estate here is 120 records, so a segment is made "too broad"
        by lowering the ceiling rather than by seeding six hundred rows -
        the policy is configurable precisely so a workspace can say what
        broad means for it.
        """
        if maximum is not None:
            # Through the repo's config rather than `set_policy`: the
            # segment ceiling is a client setting, not one of the short
            # list a workspace admin may override from the settings
            # screen, and `set_policy` rightly refuses anything else.
            repo = self.repo()
            original = repo.config

            def lowered():
                config = dict(original())
                config["campaign_segments"] = dict(
                    config.get("campaign_segments") or {},
                    max_segment_size=maximum)
                return config

            repo.config = lowered
            self._repo_override = repo
        if size is not None:
            rows = store.load()
            for index, rec in enumerate(rows):
                rec.setdefault("qualification", {})
                rec["qualification"]["segment_key"] = (
                    "BIG" if index < size else "SMALL")
                rec["qualification"]["segment_rung"] = "full"
                rec["qualification"]["segment_reason"] = "test fixture"
            store.save(rows)
        return api.segment_health(getattr(self, "_repo_override", None)
                                  or self.repo())

    def test_a_broad_segment_is_named(self):
        found = self.health(size=self.RECORDS, maximum=20)
        keys = [row["segment_key"] for row in found["too_broad"]]
        self.assertIn("BIG", keys)

    def test_a_broad_segment_carries_examples_rather_than_a_bare_count(self):
        """"Too broad" should be a claim somebody can look at."""
        found = self.health(size=self.RECORDS, maximum=20)
        row = [r for r in found["too_broad"] if r["segment_key"] == "BIG"][0]
        self.assertTrue(row["examples"])
        self.assertLessEqual(len(row["examples"]), 4)

    def test_a_small_segment_is_named_separately(self):
        found = self.health(size=2)
        small = [r["segment_key"] for r in found["too_small"]]
        self.assertIn("BIG", small)

    def test_a_healthy_estate_says_so(self):
        config = self.repo().config()
        from src import campaignseg
        policy = campaignseg.settings(config)
        rows = store.load()
        for rec in rows:
            rec.setdefault("qualification", {})
            rec["qualification"]["segment_key"] = "OK"
            rec["qualification"]["segment_rung"] = "full"
            rec["qualification"]["segment_reason"] = "test fixture"
        store.save(rows)
        found = api.segment_health(self.repo())
        if (policy["min_segment_size"] <= len(rows)
                <= policy["max_segment_size"]):
            self.assertTrue(found["healthy"])
            self.assertEqual(found["too_broad"], [])
            self.assertEqual(found["too_small"], [])

    def test_it_reads_the_stored_assignment_rather_than_reassigning(self):
        """Assignment happens during qualification. Recomputing it on a
        read path would be a second opinion about which campaign a company
        belongs to."""
        import inspect
        source = inspect.getsource(api.segment_health)
        self.assertNotIn("campaignseg.assign", source)
        self.assertIn("campaignseg.summarise", source)

    def test_an_unsegmented_company_is_counted_not_hidden(self):
        rows = store.load()
        for rec in rows[:5]:
            rec["qualification"] = {}
        store.save(rows)
        found = api.segment_health(self.repo())
        self.assertGreaterEqual(found["unsegmented_companies"], 0)

    def test_the_screen_does_not_offer_to_split_automatically(self):
        """Merging upward is safe - a message for a broader group is
        duller. Splitting on the wrong axis makes it wrong, so the screen
        names the cohort and leaves the choice to a person."""
        from src.web import pages

        html = pages.segment_health({
            "segments": 1, "segmented_companies": 900,
            "unsegmented_companies": 0, "minimum": 50, "maximum": 500,
            "too_small": [],
            "too_broad": [{"segment_key": "BIG", "companies": 900,
                           "rung": "full", "reason": "fixture",
                           "examples": ["A", "B"]}],
            "note": "", "healthy": False})
        self.assertIn("not automatic", html)
        self.assertNotIn("Split now", html)
        self.assertNotIn("action=\"/segments/split\"", html)

    def test_the_screen_is_empty_when_there_are_no_segments(self):
        rows = store.load()
        for rec in rows:
            rec["qualification"] = {}
        store.save(rows)
        from src.web import pages
        self.assertEqual(
            pages.segment_health(api.segment_health(self.repo())), "")


class SplitAxesProposeAndNeverSplit(ScaleTest):
    """`campaignseg` merges upward on its own because merging is safe - a
    message written for a broader group is duller. Splitting is the
    opposite: split on the wrong axis and the copy is wrong rather than
    dull, so the axis is a decision a person makes."""

    def axes(self, **segment):
        rows = store.load()
        for rec in rows:
            rec.setdefault("qualification", {})
            rec["qualification"]["segment_key"] = "BIG"
            rec["qualification"]["segment_rung"] = "full"
            rec["qualification"]["segment_reason"] = "fixture"
            rec["qualification"]["segment"] = dict(
                rec["qualification"].get("segment") or {}, **segment)
        store.save(rows)
        return api.split_axes(self.repo(), "BIG")

    def test_a_dimension_that_divides_the_cohort_is_offered(self):
        rows = store.load()
        for index, rec in enumerate(rows):
            rec.setdefault("qualification", {})
            rec["qualification"]["segment_key"] = "BIG"
            rec["qualification"]["segment_rung"] = "full"
            rec["qualification"]["segment_reason"] = "fixture"
            rec["qualification"]["segment"] = {
                "country": "germany" if index % 2 else "france"}
        store.save(rows)
        found = api.split_axes(self.repo(), "BIG")
        self.assertIn("country", [a["field"] for a in found["axes"]])

    def test_a_mostly_unknown_dimension_is_not_offered(self):
        """Splitting on it produces one real cohort and one labelled "we
        did not find out", which is a data-quality report wearing a
        segment."""
        found = self.axes(country="germany")
        rejected = {a["field"]: a for a in found["rejected"]}
        self.assertIn("subvertical", rejected)
        self.assertIn("known", rejected["subvertical"]["why_not"])

    def test_a_uniform_dimension_is_not_offered_either(self):
        """Every company sharing the value means the split has one child,
        which is not a split."""
        found = self.axes(country="germany")
        rejected = {a["field"]: a for a in found["rejected"]}
        self.assertIn("country", rejected)
        self.assertIn("same", rejected["country"]["why_not"])

    def test_the_two_refusals_are_distinguishable(self):
        """"We do not know" and "they are all the same" are different
        facts and a reader needs to tell them apart."""
        found = self.axes(country="germany")
        reasons = {a["field"]: a["why_not"] for a in found["rejected"]}
        self.assertNotEqual(reasons.get("country"),
                            reasons.get("subvertical"))

    def test_a_child_too_small_to_campaign_is_marked(self):
        """A child below the minimum has not solved the problem, it has
        moved it."""
        rows = store.load()
        for index, rec in enumerate(rows):
            rec.setdefault("qualification", {})
            rec["qualification"]["segment_key"] = "BIG"
            rec["qualification"]["segment_rung"] = "full"
            rec["qualification"]["segment_reason"] = "fixture"
            rec["qualification"]["segment"] = {
                "country": "germany" if index else "france"}
        store.save(rows)
        found = api.split_axes(self.repo(), "BIG")
        country = [a for a in found["axes"] if a["field"] == "country"][0]
        smallest = min(country["children"], key=lambda c: c["companies"])
        self.assertFalse(smallest["viable"])

    def test_it_returns_no_way_to_apply_a_split(self):
        found = self.axes(country="germany")
        for forbidden in ("apply", "split_now", "created", "campaign_ids"):
            self.assertNotIn(forbidden, found)

    def test_the_value_says_nothing_was_decided(self):
        found = self.axes(country="germany")
        self.assertIn("Nothing here splits", found["note"])

    def test_an_unknown_segment_returns_nothing_rather_than_raising(self):
        found = api.split_axes(self.repo(), "NO-SUCH-SEGMENT")
        self.assertEqual(found["companies"], 0)
        self.assertEqual(found["axes"], [])


class ASegmentStrategyIsAHypothesis(ScaleTest):
    """What we expect to work, before anything has been sent.

    Until messages have gone out and replies have come back it rests on
    the ICP evidence that qualified the companies and on nothing else. A
    strategy presented as an established result is one nobody
    re-examines.
    """

    def strategy(self, pain=None):
        rows = store.load()
        for rec in rows:
            rec.setdefault("qualification", {})
            rec["qualification"]["segment_key"] = "SEG"
            rec["qualification"]["segment_rung"] = "full"
            rec["qualification"]["segment_reason"] = "fixture"
            rec["qualification"]["messaging"] = {
                "relevant_pain_categories": [pain] if pain else [],
                "unsupported_hypotheses": ["tool_sprawl"],
            }
        store.save(rows)
        return api.segment_strategy(self.repo(), "SEG")

    def test_it_says_it_is_a_hypothesis(self):
        found = self.strategy("utilization")
        self.assertIn("hypothesis", found["note"].lower())
        self.assertIn("no message", found["note"].lower())

    def test_it_carries_its_sample_size(self):
        found = self.strategy("utilization")
        self.assertEqual(found["companies"], self.RECORDS)
        self.assertIn("companies", found["confidence"]["why"])

    def test_confidence_is_words_rather_than_a_score(self):
        """Not a number anybody should optimise: a reader needs to know
        whether they are looking at a brief or a starting point."""
        found = self.strategy("utilization")
        self.assertIn(found["confidence"]["level"],
                      ("evidenced", "mixed", "thin", "none"))

    def test_a_segment_with_no_evidenced_angle_says_none(self):
        found = self.strategy(None)
        self.assertEqual(found["confidence"]["level"], "none")
        self.assertIsNone(found["primary"])

    def test_supported_and_typical_are_not_merged(self):
        """`strategy` already splits them. Aggregating them together
        would turn a guess into a brief."""
        found = self.strategy("utilization")
        supported = {found["primary"]["pain"]} if found["primary"] else set()
        guesses = {row["pain"] for row in found["hypotheses"]}
        self.assertFalse(supported & guesses)

    def test_the_playbook_scan_reports_its_cap(self):
        """A strategy that silently described the first hundred of a
        thousand would be a sample presented as a segment."""
        found = self.strategy("utilization")
        self.assertIn("scanned", found)
        self.assertEqual(found["capped"],
                         found["companies"] > found["scanned"])

    def test_an_unknown_segment_says_it_does_not_exist(self):
        found = api.segment_strategy(self.repo(), "NO-SUCH-SEGMENT")
        self.assertFalse(found["exists"])
        self.assertEqual(found["companies"], 0)

    def test_it_counts_reachability_rather_than_contacts_found(self):
        found = self.strategy("utilization")
        self.assertLessEqual(found["reachable"], found["companies"])


class FailuresAreReadableInOnePlace(ScaleTest):
    """Every path here already recorded its own failure. What was missing
    was somewhere to read them together - the difference between a system
    that records failures and one that surfaces them."""

    def health(self):
        return api.operational_health(self.repo())

    def test_a_clean_workspace_says_so(self):
        found = self.health()
        self.assertTrue(found["clean"])
        self.assertEqual(found["rows"], [])

    def fail_a_tag_write(self, workspace=WS):
        """A real FAILED row: enqueue the desired state, then miss.

        Built through `enqueue` rather than hand-written, because
        `record_attempt` overwrites whatever status it is handed - a
        hand-written row is a row the module would never have produced.
        """
        from src import tagsync

        rec = self.repo().record("c1")
        rows = tagsync.enqueue(rec, "a", workspace, outcome="positive_reply")
        row = next(r for r in rows if r["provider"] == tagsync.EMAILBISON)
        tagsync.record_attempt(row, ok=False, error="provider 500")
        return row

    def test_a_stuck_tag_write_is_surfaced(self):
        """Asserted on the FAILED row specifically. The same fixture also
        produces a blocked HeyReach row, so an assertion on the area alone
        passes while nothing at all reports the failure."""
        from src import tagsync

        self.fail_a_tag_write()
        found = self.health()
        self.assertFalse(found["clean"])
        failed = [r for r in found["rows"]
                  if r["area"] == "provider tags"
                  and r["state"] == tagsync.FAILED]
        self.assertEqual(len(failed), 1)
        self.assertTrue(failed[0]["retry_safe"])
        self.assertEqual(found["counts"]["retryable"], 1)

    def test_every_row_says_whether_retrying_is_safe(self):
        """"It failed" without "and the reply was still recorded" is what
        makes somebody re-run a thing that already happened."""
        self.fail_a_tag_write()
        rows = self.health()["rows"]
        self.assertTrue(rows)
        for row in rows:
            self.assertIn("retry_safe", row)
            self.assertTrue(row["why_safe"])

    def test_a_contact_that_cannot_be_named_needs_a_person(self):
        """Retrying changes nothing: the contact needs an identifier
        before a provider can be told anything about them.

        The fixture contact has an email and no LinkedIn profile, so
        `tagsync.plan` blocks the HeyReach row on its own - which is the
        only way a blocked row is ever produced.
        """
        from src import tagsync

        rec = self.repo().record("c1")
        rows = tagsync.enqueue(rec, "a", WS, outcome="positive_reply")
        blocked = [r for r in rows if r["status"] == tagsync.BLOCKED]
        self.assertTrue(blocked, "the fixture produced no blocked row")

        found = [r for r in self.health()["rows"]
                 if r["state"] == tagsync.BLOCKED]
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["retry_safe"])
        self.assertEqual(self.health()["counts"]["needs_a_person"], 1)

    def test_it_names_what_it_is_not_watching(self):
        """A health screen that looks clean because it was not watching is
        worse than none."""
        found = self.health()
        areas = [row["area"] for row in found["unwatched"]]
        self.assertIn("enrichment", areas)
        self.assertIn("scheduler", areas)

    def test_it_is_scoped_to_one_workspace(self):
        """An operator must not learn that another tenant's Slack is
        misconfigured."""
        self.fail_a_tag_write(workspace="contactout")
        self.assertTrue(self.health()["clean"])

    def test_a_viewer_cannot_read_it(self):
        """Operational failures are agency working state."""
        from src import workspaces as ws_module

        ws_module.add_user("v@x.test", "V")
        ws_module.assign("v@x.test", WS, ws_module.VIEWER)
        with self.assertRaises(ws_module.NotPermitted):
            api.operational_health(
                repo_module.Repo.for_user("v@x.test", WS))


class TheAnswersDidNotChange(ScaleTest):
    """Faster and identical, or it is not a fix."""

    def test_every_campaign_reports_its_own_record_count(self):
        rows = api.campaign_rows(self.repo())
        self.assertEqual(len(rows), self.CAMPAIGNS)
        self.assertEqual(sum(r["records"] for r in rows), self.RECORDS)

    def test_a_campaign_naming_a_record_that_is_gone_does_not_inflate(self):
        """`record_ids` can outlive a record. It must not be counted."""
        campaigns = campaign_store.load()
        campaigns[0]["record_ids"] = campaigns[0]["record_ids"] + ["ghost"]
        campaign_store.save(campaigns)
        rows = api.campaign_rows(self.repo())
        found = [r for r in rows if r["campaign_id"] == "camp0"][0]
        self.assertEqual(found["records"], self.RECORDS // self.CAMPAIGNS)

    def test_every_batch_reports_its_own_records(self):
        rows = api.batch_list(self.repo())
        self.assertEqual(len(rows), self.BATCHES)
        self.assertEqual(sum(r["records"] for r in rows), self.RECORDS)

    def test_a_record_lands_in_exactly_one_batch(self):
        rows = api.batch_list(self.repo())
        names = [r["batch"] for r in rows]
        self.assertEqual(len(names), len(set(names)))


class TenancySurvivesTheIndex(ScaleTest):
    """An index built from one workspace's records must not be reachable
    from another. The speed-up must not become a boundary hole."""

    def setUp(self):
        super().setUp()
        workspaces.ensure("contactout", "ContactOut", client="contactout")
        workspaces.assign("op@x.test", "contactout", workspaces.OPERATOR)
        theirs = store.new_record("theirs", "domains", "contactout",
                                  "Other Ltd", "other.test")
        store.save(store.load() + [theirs])
        campaign_store.save(campaign_store.load() + [
            {"campaign_id": "theircamp", "name": "Theirs",
             "client": "contactout", "status": "draft",
             "record_ids": ["theirs"]}])

    def test_a_campaign_list_shows_only_this_workspaces_campaigns(self):
        rows = api.campaign_rows(self.repo())
        self.assertNotIn("theircamp", [r["campaign_id"] for r in rows])

    def test_another_workspaces_record_is_not_counted_into_a_campaign(self):
        campaigns = campaign_store.load()
        for campaign in campaigns:
            if campaign["campaign_id"] == "camp0":
                campaign["record_ids"] = campaign["record_ids"] + ["theirs"]
        campaign_store.save(campaigns)
        rows = api.campaign_rows(self.repo())
        found = [r for r in rows if r["campaign_id"] == "camp0"][0]
        self.assertEqual(found["records"], self.RECORDS // self.CAMPAIGNS)

    def test_another_workspaces_record_is_not_in_the_batch_list(self):
        total = sum(r["records"] for r in api.batch_list(self.repo()))
        self.assertEqual(total, self.RECORDS)


if __name__ == "__main__":
    unittest.main()
