"""The batch pipeline's refusals, each one a failure that already happened.

Every test here breaks a guard deliberately and asserts that the INTENDED
guard fired, with the intended message - not merely that something raised.
A test that accepts any exception passes when a typo raises NameError, which
is how a guard gets deleted and the suite stays green.
"""
import os
import tempfile
import unittest

from src import batchpipeline as bp
from src import store

from . import base


def row(email="a@one.test", domain="one.test", title="Chief Executive Officer",
        location="New York, New York, United States",
        industry="Marketing & Advertising", **over):
    # THE DEFAULT ROW CARRIES A SUPPLIER LINKEDIN URL, because every one of
    # the 12,407 real rows does. A fixture without one would let the LinkedIn
    # gate pass for the wrong reason - "no URL" instead of "no DISCOVERED
    # URL" - and the tests would stop describing the file they are about.
    r = {"email": email, "domain": domain, "title": title,
         "location": location, "industry": industry,
         "first_name": "A", "last_name": "B", "company": "C",
         "linkedin": "https://www.linkedin.com/in/aaaaaaaaaaaa",
         "provenance": {"approval_snapshot": "SNAP-2026-09-07"}}
    r.update(over)
    return r


def manifest_for(rows, config, batch=1, of=1):
    industries = bp.industries_of(rows)
    return bp.new_manifest("t", batch, of, bp.pair_key(rows[0], config),
                           bp.measure(rows), "productive",
                           {"rows_total": len(rows)},
                           industries=industries,
                           merged=len(industries) > 1)


NY = "New York, New York, United States"
LA = "Los Angeles, California, United States"


class StageCounting(base.QueueTest):
    """A stage that returned nothing is not a stage that is through."""

    def setUp(self):
        super().setUp()
        self.config = base.fixture_config()
        self.rows = [row(email=f"p{i}@one.test") for i in range(4)]
        self.manifest = manifest_for(self.rows, self.config)

    def test_an_empty_stage_recorded_done_is_refused(self):
        with self.assertRaises(bp.StageEmpty) as caught:
            bp.record_stage(self.manifest, bp.QUALIFY, bp.DONE,
                            attempted=4, produced=0,
                            counted_from="a sweep that found nothing")
        self.assertIn("returned nothing to count", str(caught.exception))

    def test_an_empty_stage_may_be_recorded_empty(self):
        entry = bp.record_stage(self.manifest, bp.QUALIFY, bp.EMPTY,
                                attempted=4, produced=0)
        self.assertEqual(entry["status"], bp.EMPTY)
        # And `empty` is NOT counted as progress through the stage.
        self.assertIsNone(bp.percent_through(self.manifest, bp.QUALIFY))

    def test_a_stage_that_attempted_nothing_may_be_done(self):
        """Nothing to do is different from doing nothing, and stays `done`."""
        entry = bp.record_stage(self.manifest, bp.DISCOVERY, bp.DONE,
                                attempted=0, produced=0)
        self.assertEqual(entry["status"], bp.DONE)

    def test_a_count_without_a_readback_is_refused(self):
        with self.assertRaises(bp.PipelineError) as caught:
            bp.record_stage(self.manifest, bp.QUALIFY, bp.DONE,
                            attempted=4, produced=4, counted_from=None)
        self.assertIn("counted_from", str(caught.exception))

    def test_producing_more_than_the_denominator_is_refused(self):
        with self.assertRaises(bp.PipelineError) as caught:
            bp.record_stage(self.manifest, bp.QUALIFY, bp.DONE,
                            attempted=4, produced=9, counted_from="nine rows")
        self.assertIn("counting different things", str(caught.exception))

    def test_an_unnamed_denominator_is_refused(self):
        with self.assertRaises(bp.UnknownDenominator) as caught:
            bp.record_stage(self.manifest, bp.QUALIFY, bp.DONE,
                            attempted=4, produced=4, counted_from="x",
                            denominator_override="vibes")
        self.assertIn("not a named", str(caught.exception))

    def test_a_denominator_with_no_value_is_refused(self):
        """render is measured against contacts_verified, unknown until then."""
        self.manifest["denominators"]["contacts_verified"] = None
        with self.assertRaises(bp.UnknownDenominator) as caught:
            bp.record_stage(self.manifest, bp.RENDER, bp.DONE,
                            attempted=1, produced=1, counted_from="x")
        self.assertIn("not a measurement", str(caught.exception))

    def test_a_finished_stage_becomes_the_next_stages_denominator(self):
        bp.record_stage(self.manifest, bp.VERIFY, bp.DONE, attempted=4,
                        produced=3, counted_from="3 sendable in the journal")
        self.assertEqual(self.manifest["denominators"]["contacts_verified"], 3)
        self.assertEqual(
            self.manifest["stages"][bp.RENDER]["denominator_value"], 3)


class Homogeneity(base.QueueTest):
    """A mixed batch does not map onto a cohort campaign."""

    def setUp(self):
        super().setUp()
        self.config = base.fixture_config()

    def test_a_batch_mixing_geo_is_refused(self):
        with self.assertRaises(bp.MixedBatch) as caught:
            bp.assert_homogeneous([row(location=NY), row(location=LA)],
                                  self.config)
        self.assertIn("never merge", str(caught.exception))

    def test_a_batch_mixing_persona_is_refused(self):
        rows = [row(title="Chief Executive Officer"),
                row(title="Head of Delivery")]
        personas = {bp.persona_of(r, self.config) for r in rows}
        self.assertEqual(len(personas), 2, "fixture must span two personas")
        with self.assertRaises(bp.MixedBatch):
            bp.assert_homogeneous(rows, self.config)

    def test_a_batch_mixing_industry_is_allowed(self):
        """Industry is the ONE dimension the operator lets merge."""
        rows = [row(industry="Marketing & Advertising"),
                row(industry="Computer Software")]
        self.assertIsNotNone(bp.assert_homogeneous(rows, self.config))

    def test_every_planned_batch_is_pinned_on_geo_and_persona(self):
        rows = ([row(location=NY)] * 60 + [row(location=LA)] * 60
                + [row(location="United States")] * 60)
        batches, _held = bp.plan_slices(rows, self.config, size=1000)
        self.assertTrue(batches)
        for spec in batches:
            bp.assert_homogeneous([rows[i] for i in spec["indexes"]],
                                  self.config)          # raises if not

    def test_an_unplaceable_location_is_its_own_slice_not_folded_in(self):
        """"United States" with no city and no state is not US East."""
        placed, _ = bp.geo_zone(row(location=NY), self.config)
        bare, _ = bp.geo_zone(row(location="United States"), self.config)
        self.assertEqual(placed, "US East")
        self.assertEqual(bare, bp.UNZONED)
        self.assertNotEqual(placed, bare)

    def test_the_merge_rule_does_not_licence_folding_unzoned_into_placed(self):
        """Geo is pinned, so a merge can never move an unzoned row."""
        rows = [row(location=NY)] * 60 + [row(location="United States")] * 60
        batches, _held = bp.plan_slices(rows, self.config, size=1000)
        zones = [bp.geo_zone(rows[spec["indexes"][0]], self.config)[0]
                 for spec in batches]
        self.assertIn("US East", zones)
        self.assertIn(bp.UNZONED, zones)
        for spec in batches:
            found = {bp.geo_zone(rows[i], self.config)[0]
                     for i in spec["indexes"]}
            self.assertEqual(len(found), 1)

    def test_a_state_is_matched_on_whole_tokens(self):
        """A substring test puts a New Yorker in the Central zone."""
        self.assertEqual(bp.us_state_in("Dallas-Fort Worth Metroplex, Texas"),
                         "texas")
        # "ok" (Oklahoma) must not match inside "Brooklyn".
        self.assertIsNone(bp.us_state_in("Brooklyn"))

    def test_a_batch_never_exceeds_the_requested_size(self):
        rows = [row(location=NY)] * 250
        batches, _held = bp.plan_slices(rows, self.config, size=100)
        self.assertTrue(batches)
        for spec in batches:
            self.assertLessEqual(len(spec["indexes"]), 100)


class TheOperatorSlicingRule(base.QueueTest):
    """Geo+persona pinned, industry merges under 200, never a cohort under 50."""

    def setUp(self):
        super().setUp()
        self.config = base.fixture_config()

    def test_an_industry_at_or_above_the_threshold_keeps_its_own_batch(self):
        rows = ([row(industry="Marketing & Advertising", location=NY)]
                * bp.MERGE_INDUSTRY_BELOW
                + [row(industry="Computer Software", location=NY)] * 60)
        batches, _held = bp.plan_slices(rows, self.config, size=1000)
        solo = [b for b in batches if not b["merged_industries"]]
        self.assertTrue(solo, "a 200-row industry must not be merged away")
        self.assertEqual(len(solo[0]["indexes"]), bp.MERGE_INDUSTRY_BELOW)

    def test_industries_below_the_threshold_merge_together(self):
        rows = ([row(industry="Computer Software", location=NY)] * 60
                + [row(industry="Consumer Goods", location=NY)] * 60)
        batches, _held = bp.plan_slices(rows, self.config, size=1000)
        self.assertEqual(len(batches), 1)
        self.assertTrue(batches[0]["merged_industries"])

    def test_a_batch_under_fifty_is_never_emitted(self):
        rows = [row(location=NY)] * 20
        batches, held = bp.plan_slices(rows, self.config, size=1000)
        self.assertEqual(batches, [])
        self.assertEqual(sum(len(h["indexes"]) for h in held), 20)

    def test_assert_emittable_refuses_a_short_batch(self):
        with self.assertRaises(bp.TooSmallToEmit) as caught:
            bp.assert_emittable([row()] * (bp.MIN_COHORT - 1))
        self.assertIn("reservoir", str(caught.exception))

    def test_the_reservoir_drains_into_a_batch_of_the_same_pair(self):
        """Under 50 after merging joins the pair's existing batch."""
        rows = ([row(industry="Marketing & Advertising", location=NY)] * 300
                + [row(industry="Computer Software", location=NY)] * 10)
        batches, held = bp.plan_slices(rows, self.config, size=1000)
        self.assertEqual(held, [], "the pair had a batch to drain into")
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]["indexes"]), 310)
        self.assertTrue(batches[0]["merged_industries"])

    def test_no_contact_is_lost_between_batches_and_reservoir(self):
        rows = ([row(location=NY)] * 300 + [row(location=LA)] * 10
                + [row(industry="Computer Software", location=NY)] * 7)
        batches, held = bp.plan_slices(rows, self.config, size=1000)
        placed = sum(len(b["indexes"]) for b in batches)
        waiting = sum(len(h["indexes"]) for h in held)
        self.assertEqual(placed + waiting, len(rows))

    def test_every_emitted_batch_clears_the_floor(self):
        rows = ([row(location=NY)] * 300 + [row(location=LA)] * 10
                + [row(location="United States")] * 5)
        batches, _held = bp.plan_slices(rows, self.config, size=1000)
        for spec in batches:
            self.assertGreaterEqual(len(spec["indexes"]), bp.MIN_COHORT)


class TheCampaignTag(base.QueueTest):
    """A reader must see the mix from the campaign name, without opening it."""

    def setUp(self):
        super().setUp()
        self.config = base.fixture_config()

    def test_every_merged_industry_appears_in_the_tag(self):
        tag = bp.campaign_tag("US East", "economic_buyer",
                              ["Marketing & Advertising", "Computer Software",
                               "Real Estate"])
        for fragment in ("marketing-and-advertising", "computer-software",
                         "real-estate"):
            self.assertIn(fragment, tag)

    def test_the_tag_does_not_hide_the_mix_behind_a_count(self):
        tag = bp.campaign_tag("US East", "champion",
                              ["Marketing & Advertising", "Computer Software"])
        self.assertNotIn("mixed", tag)
        self.assertNotIn("multi", tag)

    def test_a_drifted_tag_is_refused_structurally(self):
        rows = [row(industry="Marketing & Advertising"),
                row(industry="Computer Software")]
        m = manifest_for(rows, self.config)
        self.assertEqual(bp.structural_redaction_check(m), [])
        m["slice"]["campaign_tag"] = "us-east__economic-buyer__marketing"
        self.assertTrue(any("campaign_tag" in p["path"]
                            for p in bp.structural_redaction_check(m)))

    def test_the_merged_flag_cannot_disagree_with_the_industries(self):
        rows = [row(industry="Marketing & Advertising")]
        m = manifest_for(rows, self.config)
        m["slice"]["merged_industries"] = True
        self.assertTrue(any("merged_industries" in p["path"]
                            for p in bp.structural_redaction_check(m)))


class TheLinkedInGate(base.QueueTest):
    """A supplier URL is not a discovered one, and all 12,407 rows have one."""

    def _discovered(self, **over):
        r = row(**over)
        r["linkedin_discovery"] = {"provider": "contactout",
                                   "url": r["linkedin"]}
        return r

    def _in_excluded_cohort(self, campaign_id=495, **over):
        r = row(**over)
        r["provider_read"] = {"memberships": [{"campaign_id": campaign_id,
                                               "status": "stopped"}]}
        return r

    def test_a_supplier_url_does_not_satisfy_the_gate(self):
        """THE TRAP. Every row in the file already has a linkedin.com URL."""
        rows = [row(linkedin="https://www.linkedin.com/in/someone")]
        self.assertEqual(bp.linkedin_source(rows[0]),
                         bp.LINKEDIN_FROM_SUPPLIER)
        self.assertFalse(bp.linkedin_ready(rows[0]))
        gate = bp.linkedin_gate(rows)
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["supplier_url_only"], 1)
        self.assertEqual(gate["discovered_by_contactout"], 0)

    def test_a_discovered_url_satisfies_the_gate(self):
        rows = [self._discovered()]
        self.assertEqual(bp.linkedin_source(rows[0]),
                         bp.LINKEDIN_FROM_DISCOVERY)
        gate = bp.linkedin_gate(rows)
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["discovered_by_contactout"], 1)

    def test_the_491_to_498_cohort_is_permanently_excluded(self):
        for campaign_id in (491, 495, 498):
            r = self._in_excluded_cohort(campaign_id)
            self.assertTrue(bp.linkedin_excluded(r), campaign_id)
            self.assertTrue(bp.linkedin_ready(r),
                            "an excluded row waits for nothing")

    def test_a_campaign_outside_the_range_is_not_excluded(self):
        for campaign_id in (352, 490, 499):
            self.assertFalse(
                bp.linkedin_excluded(self._in_excluded_cohort(campaign_id)),
                campaign_id)

    def test_an_excluded_row_does_not_block_the_gate(self):
        gate = bp.linkedin_gate([self._in_excluded_cohort(),
                                 self._discovered()])
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["permanently_excluded_491_498"], 1)
        self.assertEqual(gate["eligible"], 1)

    def test_one_supplier_row_fails_the_whole_batch(self):
        gate = bp.linkedin_gate([self._discovered() for _ in range(9)]
                                + [row()])
        self.assertFalse(gate["passed"])

    def test_the_eligible_denominator_excludes_the_491_cohort(self):
        rows = [self._in_excluded_cohort(), row(), row()]
        self.assertEqual(bp.measure(rows)["contacts_linkedin_eligible"], 2)


class Budget(base.QueueTest):
    """Reserve before asking, halt at a ceiling, never raise one."""

    def setUp(self):
        super().setUp()
        self.config = {"budget": {"per_day": 1000, "per_run": 200,
                                  "total": 5000}}
        self.rows = [{"client": "productive", "day": bp.spendledger.today(),
                      "provider": "reoon", "expected_cost": 900}]

    def test_the_tighter_of_per_day_and_total_is_the_one_named(self):
        room = bp.headroom("productive", self.config, rows=self.rows)
        self.assertEqual(room["binding"], "per_day")
        self.assertEqual(room["available"], 100)
        self.assertEqual(room["remaining"]["total"], 4100)

    def test_sizing_never_exceeds_the_binding_ceiling(self):
        got, why = bp.size_against_ledger(1000, 2, "productive", self.config,
                                          rows=self.rows)
        self.assertEqual(got, 50)                 # 100 credits / 2 per unit
        self.assertIn("per_day", why)

    def test_per_run_binds_when_it_is_tighter_even_though_check_ignores_it(self):
        rows = [{"client": "productive", "day": bp.spendledger.today(),
                 "provider": "reoon", "expected_cost": 0}]
        got, why = bp.size_against_ledger(1000, 2, "productive", self.config,
                                          rows=rows)
        self.assertEqual(got, 100)                # per_run 200 / 2, not 500
        self.assertIn("per_run", why)
        self.assertIn("does NOT enforce", why)

    def test_an_exhausted_ceiling_returns_zero_and_not_one_more(self):
        rows = [{"client": "productive", "day": bp.spendledger.today(),
                 "provider": "reoon", "expected_cost": 1000}]
        got, _ = bp.size_against_ledger(1000, 2, "productive", self.config,
                                        rows=rows)
        self.assertEqual(got, 0)

    def test_headroom_reports_per_run_as_unenforced(self):
        room = bp.headroom("productive", self.config, rows=self.rows)
        self.assertFalse(room["per_run_enforced_by_check"])

    def test_an_empty_ledger_refuses_paid_work(self):
        """The worktree hazard: an empty ledger is not a spent-nothing one."""
        with self.assertRaises(bp.LedgerNotCredible) as caught:
            bp.size_against_ledger(10, 2, "productive", self.config, rows=[])
        self.assertIn("worktree", str(caught.exception))

    def test_another_clients_spend_does_not_fund_this_one(self):
        rows = [{"client": "someone-else", "day": bp.spendledger.today(),
                 "provider": "reoon", "expected_cost": 900}]
        with self.assertRaises(bp.LedgerNotCredible):
            bp.size_against_ledger(10, 2, "productive", self.config, rows=rows)


class TheVerificationSeam(base.QueueTest):
    """Blocked is an answer. Falling back to the declined order is not."""

    def test_cheapverifier_is_reported_not_live_while_lane_q_builds_it(self):
        seam = bp.verification_seam()
        self.assertIn("live", seam)
        if not seam["live"]:
            self.assertTrue(seam["reason"],
                            "a not-live seam must say why, not just say no")

    def test_the_seam_names_the_module_it_asks_for(self):
        self.assertEqual(bp.CHEAPVERIFIER_MODULE, "src.providers.cheapverifier")


class TheETA(base.QueueTest):
    """An ETA from the stages that happen to be quick is worse than none."""

    def setUp(self):
        super().setUp()
        self.config = base.fixture_config()
        self.rows = [row(email=f"p{i}@one.test") for i in range(4)]

    def _manifest(self):
        return manifest_for(self.rows, self.config)

    def test_a_blocked_stage_makes_the_eta_unmeasurable(self):
        m = self._manifest()
        bp.record_stage(m, bp.QUALIFY, bp.DONE, attempted=4, produced=4,
                        counted_from="four rows",
                        started_at="2026-09-25T10:00:00+00:00",
                        ended_at="2026-09-25T10:00:10+00:00")
        bp.record_stage(m, bp.VERIFY, bp.BLOCKED, blocked_on="cheapverifier")
        eta = bp.eta_for_file([m], 12407)
        self.assertFalse(eta["measurable"])
        self.assertIn("verification", eta["blocked_stages"])

    def test_no_completed_stage_means_no_rate_is_invented(self):
        eta = bp.eta_for_file([self._manifest()], 12407)
        self.assertFalse(eta["measurable"])

    def test_a_rate_is_measured_and_not_assumed(self):
        m = self._manifest()
        bp.record_stage(m, bp.QUALIFY, bp.DONE, attempted=4, produced=4,
                        counted_from="four rows",
                        started_at="2026-09-25T10:00:00+00:00",
                        ended_at="2026-09-25T11:00:00+00:00")
        self.assertAlmostEqual(bp.measured_rate([m], bp.QUALIFY), 4.0)
        self.assertIsNone(bp.measured_rate([m], bp.PACKS))

    def test_funding_eta_names_whether_the_lifetime_ceiling_covers_it(self):
        m = self._manifest()
        room = bp.headroom("productive",
                           {"budget": {"per_day": 15000, "total": 50000}},
                           rows=[{"client": "productive",
                                  "day": bp.spendledger.today(),
                                  "provider": "reoon",
                                  "expected_cost": 18809}])
        fund = bp.funding_eta([m], room)
        self.assertTrue(fund["measurable"])
        self.assertEqual(fund["credits_needed"],
                         4 * bp.CREDITS_PER_ADDRESS_ASKED)
        self.assertTrue(fund["lifetime_ceiling_covers_it"])


class ProviderConfirmedOnly(base.QueueTest):
    """Null is not zero, and our own counter is never the answer."""

    def setUp(self):
        super().setUp()
        self.config = base.fixture_config()
        self.rows = [row(email=f"p{i}@one.test") for i in range(4)]

    def test_pushed_and_sent_start_null_not_zero(self):
        m = manifest_for(self.rows, self.config)
        self.assertIsNone(m["provider_confirmed"]["pushed"])
        self.assertIsNone(m["provider_confirmed"]["sent"])

    def test_the_progress_block_does_not_turn_null_into_zero(self):
        restore = store.use_directory(tempfile.mkdtemp(prefix="rga-bp-"))
        self.addCleanup(restore)
        bp.save(manifest_for(self.rows, self.config))
        block = bp.progress("t", config=self.config, ledger=[])
        self.assertIsNone(block["leads"]["pushed_provider_confirmed"])
        self.assertIsNone(block["leads"]["sent_provider_confirmed"])


class Redaction(base.QueueTest):
    """Self-tested against every value, not against a pattern."""

    def test_a_planted_value_is_found(self):
        rows = [row(email="planted@example.test", company="Planted Co")]
        found = bp.redaction_selftest("a report mentioning Planted Co", rows)
        self.assertTrue(found)
        self.assertEqual(found[0]["field"], "company")

    def test_a_clean_artefact_reports_clean(self):
        rows = [row(email="planted@example.test", company="Planted Co")]
        self.assertEqual(bp.redaction_selftest("1,000 contacts, 981 domains",
                                               rows), [])

    def test_an_email_shaped_string_is_caught_even_if_not_in_the_rows(self):
        found = bp.redaction_selftest("write to someone@elsewhere.test",
                                      [row()])
        self.assertTrue(any(f["kind"] == "email-shaped string" for f in found))

    def test_the_manifest_carries_no_identifier(self):
        rows = [row(email="planted@example.test", company="Planted Co",
                    domain="planted.test")]
        import json
        m = manifest_for(rows, base.fixture_config())
        self.assertEqual(bp.leaks(bp.redaction_selftest(json.dumps(m), rows)),
                         [])

    def test_a_name_that_is_an_ordinary_word_is_review_and_not_leak(self):
        """`group` is a surname and also a word in `industry_group`.

        Reporting that as a leak makes the filter noise nobody reads;
        dropping it silently makes the filter agree with you. It is REVIEW.
        """
        rows = [row(last_name="Group")]
        found = bp.redaction_selftest('the key is "industry_group"', rows)
        self.assertTrue(found)
        self.assertEqual(found[0]["verdict"], bp.REVIEW)
        self.assertEqual(bp.leaks(found), [])

    def test_an_identifier_is_a_leak_at_any_length(self):
        rows = [row(email="p@x.test", domain="x.test")]
        found = bp.leaks(bp.redaction_selftest("crawled x.test today", rows))
        self.assertTrue(found)
        self.assertEqual(found[0]["verdict"], bp.LEAK)

    def test_a_name_is_matched_on_whole_tokens_not_substrings(self):
        """`Ross` inside `across` is not a match; `Ross` alone is."""
        rows = [row(last_name="Ross")]
        self.assertEqual(bp.redaction_selftest("counted across the batch",
                                               rows), [])
        self.assertTrue(bp.redaction_selftest("counted by Ross", rows))


class StructuralRedaction(base.QueueTest):
    """The stronger argument: a closed vocabulary, not a value search."""

    def setUp(self):
        super().setUp()
        self.config = base.fixture_config()
        self.rows = [row(email=f"p{i}@one.test") for i in range(4)]

    def test_a_clean_manifest_has_no_structural_problem(self):
        m = manifest_for(self.rows, self.config)
        self.assertEqual(bp.structural_redaction_check(m), [])

    def test_a_field_the_format_grew_later_fails_closed(self):
        m = manifest_for(self.rows, self.config)
        m["source"]["someone_added_this"] = "one.test"
        problems = bp.structural_redaction_check(m)
        self.assertTrue(problems)
        self.assertIn("someone_added_this", problems[0]["path"])

    def test_a_geo_zone_outside_the_vocabulary_is_refused(self):
        m = manifest_for(self.rows, self.config)
        m["slice"]["geo_zone"] = "Some Company Ltd"
        m["slice"]["label"] = bp.slice_label(
            (m["slice"]["geo_zone"], m["slice"]["industry_group"],
             m["slice"]["persona"]))
        self.assertTrue(any("geo_zone" in p["path"]
                            for p in bp.structural_redaction_check(m)))

    def test_a_label_that_drifted_from_its_fields_is_refused(self):
        m = manifest_for(self.rows, self.config)
        m["slice"]["label"] = "something somebody typed"
        self.assertTrue(any("label" in p["path"]
                            for p in bp.structural_redaction_check(m)))


if __name__ == "__main__":
    unittest.main()
