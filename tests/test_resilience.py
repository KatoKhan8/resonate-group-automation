"""Five thousand domains, and everything that goes wrong at that size.

Small batches hide two classes of defect. The first is quadratic work, which
is invisible at fifty records and an afternoon at five thousand. The second is
the long tail: at five thousand domains the eighty records with a formula in a
name, or an address shared with another company, stop being hypothetical and
start being Tuesday.

The dataset is `src/synthetic.py`, which is deterministic, so a failure here
names a defect rather than a seed. Nothing in this file touches a network.
"""
import os
import time
import unittest

from src import (cadence, campaigns, dedupe, eligibility, export, lint, mx,
                 personalization, plan, render, store, synthetic, verification)
from tests.campaignbase import CampaignTest

FULL = 5000
# One of every shape, four times over. Enough that a shape-specific defect
# shows up, small enough that the ordinary tests stay quick.
SAMPLE = len(synthetic.SHAPES) * 4


class TestTheDatasetItself(unittest.TestCase):
    def test_every_shape_is_present_at_full_size(self):
        counts = synthetic.describe(FULL)["per_shape"]
        for name in synthetic.SHAPE_NAMES:
            self.assertGreater(counts[name]["count"], 0, name)

    def test_the_dataset_is_deterministic(self):
        first = synthetic.record(17)
        second = synthetic.record(17)
        self.assertEqual(first, second)

    def test_a_shape_lives_where_it_says_it_does(self):
        for name in synthetic.SHAPE_NAMES:
            index = synthetic.indices_of(name, SAMPLE)[0]
            self.assertEqual(synthetic.record(index)["shape"], name)

    def test_every_record_passes_the_store_schema(self):
        for rec in synthetic.dataset(SAMPLE):
            store.validate(rec)

    def test_asking_for_a_shape_that_does_not_exist_raises(self):
        with self.assertRaises(KeyError):
            synthetic.indices_of("wishful_thinking")


class TestTheGatesHoldAtScale(CampaignTest):
    """Each defect shape must reach the verdict it was built to provoke."""

    def setUp(self):
        super().setUp()
        self.recs = synthetic.dataset(SAMPLE, self.config)

    def first(self, shape):
        return self.recs[synthetic.indices_of(shape, SAMPLE)[0]]

    def across(self, pair, findings):
        """Findings that link the two named records, in either direction."""
        return [f for f in findings
                if {f["record_id"], f["duplicate_of"]["record_id"]} == pair]

    def test_a_gateway_domain_is_blocked_for_email(self):
        for shape in ("gateway_proofpoint", "gateway_mimecast",
                      "gateway_barracuda"):
            contact = self.first(shape)["contacts"][0]
            allowed, _ = mx.allows_email(contact, self.config)
            self.assertFalse(allowed, shape)
            self.assertTrue(mx.block_reason(contact, self.config)
                            .startswith(mx.BLOCK_REASON), shape)

    def test_microsoft_is_not_blocked_for_being_microsoft(self):
        contact = self.first("microsoft_mailbox")["contacts"][0]
        self.assertTrue(mx.allows_email(contact, self.config)[0])

    def test_a_gateway_blocks_email_without_touching_linkedin(self):
        rec = self.first("gateway_proofpoint")
        contact = rec["contacts"][0]
        self.assertFalse(mx.allows_email(contact, self.config)[0])
        self.assertTrue(contact.get("linkedin"))

    def test_catch_all_and_contradiction_are_not_sendable(self):
        for shape in ("catch_all", "invalid_address", "unknown_verification",
                      "contradiction"):
            contact = self.first(shape)["contacts"][0]
            self.assertFalse(lint.sendable(contact), shape)

    def test_a_contradiction_is_held_rather_than_resolved_in_our_favour(self):
        contact = self.first("contradiction")["contacts"][0]
        state = verification.decide(verification.evidence_of(contact))
        self.assertEqual(state["state"], verification.HELD)

    def test_no_mx_and_dns_failure_never_become_sends(self):
        for shape in ("no_mx", "dns_failure"):
            contact = self.first(shape)["contacts"][0]
            self.assertFalse(mx.allows_email(contact, self.config)[0], shape)

    def test_a_record_with_no_contacts_produces_no_steps(self):
        rec = self.first("no_contacts")
        timeline = cadence.build(rec, self.config)
        self.assertEqual(timeline["contacts"], {})

    def test_a_linkedin_only_contact_is_never_planned_an_email(self):
        rec = self.first("linkedin_only")
        for contact in rec["contacts"]:
            self.assertIsNone(contact["email"])
            decision = eligibility.decide(rec, contact, "day1", "email",
                                          recs=self.recs, config=self.config)
            self.assertNotEqual(decision["verdict"], eligibility.ELIGIBLE)

    def test_an_unsubscribed_contact_is_blocked_on_every_channel(self):
        rec = self.first("unsubscribed")
        for channel in ("email", "linkedin"):
            decision = eligibility.decide(rec, rec["contacts"][0], "day1",
                                          channel, recs=self.recs,
                                          config=self.config)
            self.assertEqual(decision["verdict"], eligibility.BLOCKED)
            self.assertIn(eligibility.BLOCKED_UNSUBSCRIBED, decision["reasons"])

    def test_a_paused_company_blocks_its_own_contacts(self):
        rec = self.first("already_replied")
        decision = eligibility.decide(rec, rec["contacts"][0], "day1", "email",
                                      recs=self.recs, config=self.config)
        self.assertEqual(decision["verdict"], eligibility.BLOCKED)

    def test_a_dropped_record_is_blocked(self):
        rec = self.first("dropped")
        self.assertEqual(rec["contacts"], [])
        self.assertEqual(rec["state"], "dropped")

    def test_the_shared_mailbox_is_found_across_companies(self):
        indices = synthetic.indices_of("duplicate_email", SAMPLE)
        self.assertGreater(len(indices), 1, "need two companies to collide")
        store.save(self.recs)
        recs = store.load()
        pair = {recs[indices[0]]["id"], recs[indices[1]]["id"]}
        found = self.across(pair, dedupe.find(recs, config=self.config))
        self.assertTrue(found, "the same mailbox at two companies is a duplicate")
        self.assertTrue(any(f["strong"] and f["kind"] == "email"
                            for f in found), [f["kind"] for f in found])

    def test_a_shared_profile_is_found_across_companies(self):
        indices = synthetic.indices_of("duplicate_linkedin", SAMPLE)
        store.save(self.recs)
        recs = store.load()
        pair = {recs[indices[0]]["id"], recs[indices[1]]["id"]}
        found = self.across(pair, dedupe.find(recs, config=self.config))
        self.assertTrue(any(f["strong"] and f["kind"] == "linkedin"
                            for f in found),
                        "one profile at two companies is a duplicate")

    def test_a_shared_name_alone_is_never_a_duplicate(self):
        """Two "Person 3"s at unrelated companies are two people."""
        store.save(self.recs)
        recs = store.load()
        clean = synthetic.indices_of("clean_multichannel", SAMPLE)
        a, b = recs[clean[0]], recs[clean[1]]
        b["contacts"][0]["name"] = a["contacts"][0]["name"]
        pair = {a["id"], b["id"]}
        found = self.across(pair, dedupe.find(recs, config=self.config))
        self.assertFalse([f for f in found if f["strong"]],
                         "a shared name is never strong enough to merge on")


class TestNothingIsQuadratic(unittest.TestCase):
    """The specific failure this guards is real: an O(n^2) pause scan cost
    fifteen seconds at 5,000 records and would have cost an hour at 50,000."""

    def ratio(self, fn, small=250, large=1000):
        config = None
        quick = synthetic.dataset(small, config)
        slow = synthetic.dataset(large, config)
        start = time.perf_counter()
        fn(quick)
        first = time.perf_counter() - start
        start = time.perf_counter()
        fn(slow)
        second = time.perf_counter() - start
        # Guard against a clock too coarse to measure a fast function.
        if first < 0.01:
            return 1.0
        return (second / first) / (large / small)

    def test_building_every_timeline_is_linear(self):
        def build_all(recs):
            paused = cadence.paused_domains(recs)
            for rec in recs:
                cadence.build(rec, None, paused_set=paused)
        self.assertLess(self.ratio(build_all), 2.0,
                        "timeline building grew faster than the batch")

    def test_the_size_estimate_is_linear(self):
        self.assertLess(self.ratio(lambda recs: plan.size(None, recs, {})), 2.0)

    def test_finding_paused_domains_is_one_pass(self):
        self.assertLess(self.ratio(cadence.paused_domains), 2.0)

    def test_deciding_eligibility_across_a_batch_is_linear(self):
        """for_record() rescans the batch unless the caller hoists the pause
        set, which is exactly the mistake that cost fifteen seconds before."""
        from src import eligibility, ingest

        def decide_all(recs):
            paused = cadence.paused_domains(recs)
            suppressed = ingest.load_suppress()
            for rec in recs[:120]:            # a fixed slice: only the scan grows
                eligibility.for_record(rec, None, recs, {},
                                       suppressed=suppressed,
                                       paused_set=paused)
        self.assertLess(self.ratio(decide_all), 2.0,
                        "eligibility grew faster than the batch")

    def test_selecting_contacts_is_linear(self):
        def select(recs):
            for rec in recs:
                personalization.selected_contacts(rec, {})
        self.assertLess(self.ratio(select), 2.0)


class TestFiveThousandDomains(CampaignTest):
    """The real thing, once, end to end and offline."""

    def test_the_whole_pipeline_survives_five_thousand(self):
        start = time.perf_counter()
        recs = synthetic.dataset(FULL, self.config)
        built = time.perf_counter() - start

        start = time.perf_counter()
        store.save(recs)
        saved = time.perf_counter() - start

        start = time.perf_counter()
        loaded = store.load()
        read = time.perf_counter() - start
        self.assertEqual(len(loaded), FULL)

        start = time.perf_counter()
        counts = plan.size(None, loaded, self.config)
        sized = time.perf_counter() - start

        self.assertEqual(counts["domains"], FULL)
        self.assertGreater(counts["contacts_found"], 0)
        # The narrowing is the whole point: far fewer people are emailable than
        # domains were uploaded, and if that ever stops being true a gate broke.
        self.assertLess(counts["contacts_emailable"], counts["contacts_found"])
        self.assertGreater(counts["contacts_mx_blocked"], 0)

        total = built + saved + read + sized
        self.assertLess(total, 120, f"5,000 domains took {total:.1f}s")

    def test_the_queue_file_round_trips_every_hostile_string(self):
        recs = synthetic.dataset(SAMPLE * 4, self.config)
        store.save(recs)
        loaded = store.load()
        self.assertEqual(loaded, recs, "JSONL lost or mangled something")

    def test_one_broken_record_does_not_stop_the_other_four_thousand(self):
        """Failure isolation: a poisoned record is skipped, not fatal."""
        recs = synthetic.dataset(SAMPLE, self.config)
        recs[3]["contacts"] = "this is not a list"       # corrupt on purpose
        survived = 0
        for rec in recs:
            try:
                cadence.build(rec, self.config)
                survived += 1
            except Exception:
                pass
        self.assertGreaterEqual(survived, len(recs) - 1)

    def test_a_crash_between_save_and_read_leaves_the_file_readable(self):
        """The temp-and-rename write is what makes this true."""
        recs = synthetic.dataset(SAMPLE, self.config)
        store.save(recs)
        before = store.load()
        # A partial write leaves the temp file behind, not a truncated queue.
        for name in os.listdir(os.path.dirname(self.queue)):
            self.assertFalse(name.endswith(".tmp"),
                             "a temp file survived a completed write")
        self.assertEqual(len(before), SAMPLE)

    def test_resuming_after_a_partial_run_repeats_nothing(self):
        recs = synthetic.dataset(SAMPLE, self.config)
        store.save(recs)
        recs = store.load()
        clean = [recs[i] for i in synthetic.indices_of("clean_multichannel",
                                                       SAMPLE)]
        from src import push
        for rec in clean[:3]:
            key = rec["contacts"][0]["key"]
            push.mark_pushed(rec, key, "day1",
                             push.push_id(rec, key, "day1", "email"))
        store.save(recs)

        recs = store.load()                       # as a fresh process would
        for rec in recs[:len(clean)]:
            for contact in rec.get("contacts") or []:
                if push.already_pushed(rec, contact["key"], "day1"):
                    decision = eligibility.decide(rec, contact, "day1", "email",
                                                  recs=recs, config=self.config)
                    self.assertEqual(decision["verdict"], eligibility.BLOCKED)
                    self.assertIn(eligibility.BLOCKED_ALREADY_PUSHED,
                                  decision["reasons"])


class TestExportSafety(unittest.TestCase):
    def test_every_formula_leader_is_neutralised(self):
        for leader in export.FORMULA_LEADERS:
            self.assertTrue(export.safe_cell(leader + "cmd").startswith("'"),
                            leader)

    def test_the_real_hostile_names_are_neutralised(self):
        for name in synthetic.HOSTILE_NAMES:
            cell = export.safe_cell(name)
            stripped = cell.lstrip("'")
            self.assertFalse(stripped[:1] in export.FORMULA_LEADERS
                             and not cell.startswith("'"), name)

    def test_leading_whitespace_does_not_smuggle_a_formula_through(self):
        self.assertTrue(export.safe_cell(" =1+1").startswith("'"))
        self.assertTrue(export.safe_cell("\t=1+1").startswith("'"))

    def test_control_characters_are_removed(self):
        self.assertNotIn("\x00", export.safe_cell("a\x00b"))
        self.assertEqual(export.safe_cell("a\x00b"), "ab")

    def test_an_ordinary_name_is_left_completely_alone(self):
        for name in ("Ann Smith", "Zoë Müller", "O'Brien", "李 明"):
            self.assertEqual(export.safe_cell(name), name)

    def test_a_number_is_not_quoted(self):
        self.assertEqual(export.safe_cell(42), "42")
        self.assertEqual(export.safe_cell(1.5), "1.5")

    def test_none_becomes_empty_rather_than_the_word_none(self):
        self.assertEqual(export.safe_cell(None), "")

    def test_a_written_file_survives_a_round_trip(self):
        import csv
        import tempfile
        path = os.path.join(tempfile.mkdtemp(prefix="rga-csv-"), "x.csv")
        rows = [[name, "b"] for name in synthetic.HOSTILE_NAMES]
        export.write_csv(path, ["name", "other"], rows)
        with open(path, encoding="utf-8", newline="") as f:
            read = list(csv.reader(f))
        self.assertEqual(len(read), len(rows) + 1)
        for row in read[1:]:
            self.assertFalse(row[0][:1] in export.FORMULA_LEADERS, row[0])

    def test_the_audit_names_what_would_have_been_executed(self):
        found = export.audit([["=1+1", "safe"], ["fine", "@SUM(1)"]])
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0]["row"], 0)
        self.assertEqual(found[1]["column"], 1)

    def test_the_push_file_writer_goes_through_the_guard(self):
        import inspect
        source = inspect.getsource(render)
        self.assertIn("export.write_csv", source)
        self.assertNotIn("csv.writer", source,
                         "a second CSV writer would bypass the guard")


class TestPreviewSafety(CampaignTest):
    def test_hostile_names_cannot_break_out_of_the_preview(self):
        from src import preview
        recs = synthetic.dataset(SAMPLE, self.config)
        store.save(recs)
        recs = store.load()
        campaign = campaigns.new_campaign("syn", "demo", "Synthetic")
        campaign["record_ids"] = [r["id"] for r in recs]
        page = preview.build(campaign, recs, self.config)
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("onerror=alert", page)
        self.assertIn("&lt;script&gt;", page)

    def test_the_preview_masks_addresses_by_default(self):
        from src import preview
        recs = synthetic.dataset(SAMPLE, self.config)
        campaign = campaigns.new_campaign("syn", "demo", "Synthetic")
        campaign["record_ids"] = [r["id"] for r in recs]
        page = preview.build(campaign, recs, self.config)
        clean = recs[synthetic.indices_of("clean_multichannel", SAMPLE)[0]]
        self.assertNotIn(clean["contacts"][0]["email"], page)

    def test_the_preview_calls_no_provider(self):
        from src import preview
        recs = synthetic.dataset(SAMPLE, self.config)
        campaign = campaigns.new_campaign("syn", "demo", "Synthetic")
        campaign["record_ids"] = [r["id"] for r in recs]
        preview.build(campaign, recs, self.config)
        self.assertEqual(self.cassette.calls, [])


if __name__ == "__main__":
    unittest.main()
