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
    r = {"email": email, "domain": domain, "title": title,
         "location": location, "industry": industry,
         "first_name": "A", "last_name": "B", "company": "C",
         "provenance": {"approval_snapshot": "SNAP-2026-09-07"}}
    r.update(over)
    return r


def manifest_for(rows, config, batch=1, of=1):
    return bp.new_manifest("t", batch, of, bp.slice_key(rows[0], config),
                           bp.measure(rows), "productive",
                           {"rows_total": len(rows)})


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

    def test_a_mixed_batch_is_refused(self):
        rows = [row(location="New York, New York, United States"),
                row(location="Los Angeles, California, United States")]
        with self.assertRaises(bp.MixedBatch) as caught:
            bp.assert_homogeneous(rows, self.config)
        self.assertIn("distinct", str(caught.exception))

    def test_every_planned_batch_is_homogeneous(self):
        rows = ([row(location="New York, New York, United States")] * 3
                + [row(location="Los Angeles, California, United States")] * 2
                + [row(location="United States")] * 2)
        for spec in bp.plan_slices(rows, self.config, size=10):
            members = [rows[i] for i in spec["indexes"]]
            bp.assert_homogeneous(members, self.config)   # raises if not

    def test_an_unplaceable_location_is_its_own_slice_not_folded_in(self):
        """"United States" with no city and no state is not US East."""
        placed, _ = bp.geo_zone(row(location="New York, New York, United States"),
                                self.config)
        bare, _ = bp.geo_zone(row(location="United States"), self.config)
        self.assertEqual(placed, "US East")
        self.assertEqual(bare, bp.UNZONED)
        self.assertNotEqual(placed, bare)

    def test_a_state_is_matched_on_whole_tokens(self):
        """A substring test puts a New Yorker in the Central zone."""
        self.assertEqual(bp.us_state_in("Dallas-Fort Worth Metroplex, Texas"),
                         "texas")
        # "ok" (Oklahoma) must not match inside "Brooklyn".
        self.assertIsNone(bp.us_state_in("Brooklyn"))

    def test_a_batch_never_exceeds_the_requested_size(self):
        rows = [row(location="New York, New York, United States")] * 25
        for spec in bp.plan_slices(rows, self.config, size=10):
            self.assertLessEqual(len(spec["indexes"]), 10)


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
        self.assertEqual(bp.redaction_selftest(json.dumps(m), rows), [])


if __name__ == "__main__":
    unittest.main()
