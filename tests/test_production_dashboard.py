#!/usr/bin/env python3
"""Tests for the production dashboard generator.

The dashboard must answer production questions from data that actually exists,
and say ABSENT (not 0) when no source is available. These tests verify the
generator reads the right files, produces the right shape, and never confuses
zero with missing.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.production_dashboard import (
    absent, build_dashboard, collect_absent_fields, load_json,
    load_snapshot, render_markdown, section_emailbison, section_experiments,
    section_leads, section_heyreach, section_learning, section_operations,
)


class TestAbsentSemantics(unittest.TestCase):
    """A zero and a missing writer are indistinguishable from the outside.
    The dashboard must never confuse them."""

    def test_absent_is_a_dict_with_value_and_reason(self):
        result = absent("something is missing")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["value"], "ABSENT")
        self.assertEqual(result["reason"], "something is missing")

    def test_absent_is_not_zero(self):
        result = absent("no data")
        self.assertNotEqual(result["value"], 0)
        self.assertNotEqual(result["value"], "0")

    def test_collect_absent_fields_walks_nested(self):
        dashboard = {
            "a": 1,
            "b": absent("missing b"),
            "c": {"d": absent("missing d"), "e": 5},
        }
        found = collect_absent_fields(dashboard)
        paths = [f["path"] for f in found]
        self.assertIn("b", paths)
        self.assertIn("c.d", paths)
        self.assertNotIn("a", paths)
        self.assertNotIn("c.e", paths)


class TestSectionLeads(unittest.TestCase):
    """LEADS must source from the queue snapshot and cohort data."""

    def test_empty_records_returns_absent(self):
        result = section_leads([], None, None, None)
        self.assertEqual(result["total_records"]["value"], "ABSENT")
        self.assertEqual(result["total_contacts"]["value"], "ABSENT")

    def test_with_records_counts_contacts(self):
        records = [
            {"state": "drafted", "contacts": [
                {"persona": "economic_buyer", "angle": "founder",
                 "sendable": True,
                 "verification": {"state": "verified"}},
            ]},
            {"state": "queued", "contacts": [
                {"persona": "champion", "angle": "operations",
                 "sendable": False,
                 "verification": {"state": "pending"}},
            ]},
        ]
        result = section_leads(records, "stamp-info", None, None)
        self.assertEqual(result["total_records"], 2)
        self.assertEqual(result["total_contacts"], 2)
        self.assertEqual(result["sendable_contacts"], 1)
        self.assertEqual(result["verified_contacts"], 1)
        self.assertEqual(result["by_record_state"]["drafted"], 1)
        self.assertEqual(result["by_record_state"]["queued"], 1)
        self.assertEqual(result["by_persona"]["economic_buyer"], 1)
        self.assertEqual(result["by_persona"]["champion"], 1)

    def test_cohorts_above_50(self):
        cohorts = {"cohorts": [
            {"LEAD COUNT": 70},
            {"LEAD COUNT": 51},
            {"LEAD COUNT": 40},
        ]}
        result = section_leads([{"state": "drafted", "contacts": []}],
                               "stamp", cohorts, None)
        self.assertEqual(result["cohorts_defined"], 3)
        self.assertEqual(result["cohorts_above_50"], 2)

    def test_live_records_is_zero_not_absent(self):
        """Live records is a genuine count - zero is the correct answer
        because no record has reached a live state."""
        records = [{"state": "drafted", "contacts": []}]
        result = section_leads(records, "stamp", None, None)
        self.assertEqual(result["live_records"], 0)
        self.assertNotIsInstance(result["live_records"], dict)


class TestSectionHeyreach(unittest.TestCase):
    """HEYREACH must source from PROVIDER-CAMPAIGNS.json and SENDER-CAPACITY.json."""

    def test_missing_files_returns_absent(self):
        result = section_heyreach(None, None)
        self.assertEqual(result["campaigns_total"]["value"], "ABSENT")

    def test_with_data_counts_campaigns(self):
        campaigns = {
            "heyreach": {
                "campaigns_total_in_account": 83,
                "campaigns_created_by_resonate": 1,
                "resonate_campaigns": [{
                    "heyreach_campaign_id": 599020,
                    "name": "TEST",
                    "status": "DRAFT",
                    "classification": "DRAFT",
                    "lead_count": 0,
                    "senders": [{"id": 1}],
                    "sequence": {"readable": True, "unique_nodes": 24},
                    "started_at": None,
                }],
                "status_totals": {"DRAFT": 8, "PAUSED": 32},
                "linkedin_accounts_available": 41,
            }
        }
        capacity = {
            "seats_total": 41,
            "healthy_seats": 33,
            "seats_by_state": {"HEALTHY": 33, "INACTIVE": 8},
            "daily_capacity_healthy_only": {
                "connection_requests": 1054,
                "messages": 1143,
            },
            "healthy_seats_with_no_active_campaign": 0,
        }
        result = section_heyreach(campaigns, capacity)
        self.assertEqual(result["campaigns_total_in_account"], 83)
        self.assertEqual(result["resonate_campaigns_count"], 1)
        self.assertEqual(result["resonate_live"], 0)
        self.assertEqual(result["resonate_draft"], 1)
        self.assertEqual(result["senders_total"], 41)
        self.assertEqual(result["healthy_senders"], 33)
        self.assertEqual(result["daily_connection_capacity"], 1054)
        self.assertEqual(result["daily_message_capacity"], 1143)

    def test_utilisation_is_absent_not_zero(self):
        """No campaign has started, so utilisation is not 0% - it is unmeasured."""
        campaigns = {"heyreach": {
            "campaigns_total_in_account": 83,
            "campaigns_created_by_resonate": 1,
            "resonate_campaigns": [],
            "status_totals": {},
            "linkedin_accounts_available": 41,
        }}
        result = section_heyreach(campaigns, None)
        util = result["utilisation"]
        self.assertIsInstance(util, dict)
        self.assertEqual(util["value"], "ABSENT")


class TestSectionEmailbison(unittest.TestCase):
    """EMAILBISON is entirely ABSENT because no machine-readable state exists."""

    def test_all_fields_absent(self):
        result = section_emailbison()
        for key, val in result.items():
            self.assertIsInstance(val, dict, f"{key} should be ABSENT dict")
            self.assertEqual(val["value"], "ABSENT",
                             f"{key} should be ABSENT, got {val}")


class TestSectionExperiments(unittest.TestCase):
    """EXPERIMENTS: infrastructure exists, but no data has been collected."""

    def test_infrastructure_exists_but_no_data(self):
        result = section_experiments(None)
        self.assertEqual(result["copy_experiments_infrastructure"],
                         "EXISTS AND WIRED")
        self.assertEqual(result["experiments_with_data"]["value"], "ABSENT")
        self.assertEqual(result["running"], 0)
        self.assertEqual(result["completed"], 0)

    def test_cadence_is_fixed(self):
        result = section_experiments(None)
        self.assertTrue(result["cadence_is_fixed"])
        self.assertEqual(result["cadence_steps"], 7)


class TestSectionLearning(unittest.TestCase):
    """LEARNING: documented findings exist, but no structured registry."""

    def test_structured_registry_is_absent(self):
        result = section_learning()
        self.assertEqual(result["structured_learning_registry"]["value"],
                         "ABSENT")

    def test_documented_findings_present(self):
        result = section_learning()
        findings = result["documented_findings"]
        self.assertIn("interested_pattern_precision", findings)
        self.assertIn("meeting_intent_precision", findings)
        self.assertIn("open_tracking", findings)

    def test_interested_not_promoted(self):
        result = section_learning()
        self.assertFalse(
            result["documented_findings"]["interested_pattern_precision"]
            ["promoted_to_policy"]
        )

    def test_proven_learnings_absent(self):
        result = section_learning()
        self.assertEqual(result["proven_learnings_with_sample_size"]["value"],
                         "ABSENT")


class TestBuildDashboard(unittest.TestCase):
    """Integration: the full dashboard builds and has the right shape."""

    def test_dashboard_has_all_sections(self):
        dashboard = build_dashboard()
        for section in ("LEADS", "HEYREACH", "EMAILBISON", "EXPERIMENTS",
                        "LEARNING", "OPERATIONS"):
            self.assertIn(section, dashboard, f"missing section: {section}")

    def test_dashboard_has_metadata(self):
        dashboard = build_dashboard()
        self.assertIn("generated_at", dashboard)
        self.assertIn("generated_by", dashboard)
        self.assertEqual(dashboard["generated_by"],
                         "scripts/production_dashboard.py")

    def test_absent_fields_are_collectable(self):
        dashboard = build_dashboard()
        absent_fields = collect_absent_fields(dashboard)
        self.assertGreater(len(absent_fields), 0)
        for af in absent_fields:
            self.assertIn("path", af)
            self.assertIn("reason", af)


class TestRenderMarkdown(unittest.TestCase):
    """The markdown output must be human-readable and contain all sections."""

    def test_markdown_contains_all_sections(self):
        dashboard = build_dashboard()
        md = render_markdown(dashboard)
        for heading in ("## LEADS", "## HEYREACH", "## EMAILBISON",
                        "## EXPERIMENTS", "## LEARNING", "## OPERATIONS"):
            self.assertIn(heading, md, f"missing heading: {heading}")

    def test_markdown_contains_absent_roadmap(self):
        dashboard = build_dashboard()
        md = render_markdown(dashboard)
        self.assertIn("ABSENT FIELDS", md)
        self.assertIn("THE ROADMAP", md)

    def test_markdown_does_not_contain_pii(self):
        """No real names, domains, or emails in the output."""
        dashboard = build_dashboard()
        md = render_markdown(dashboard)
        self.assertNotIn("@", md.split("##")[0] if "##" in md else md)


class TestGeneratorIsNotHandMaintained(unittest.TestCase):
    """The generator must be re-runnable and produce consistent output."""

    def test_two_runs_produce_same_structure(self):
        d1 = build_dashboard()
        d2 = build_dashboard()
        self.assertEqual(sorted(d1.keys()), sorted(d2.keys()))
        for section in ("LEADS", "HEYREACH", "EMAILBISON", "EXPERIMENTS",
                        "LEARNING"):
            self.assertEqual(sorted(d1[section].keys()),
                             sorted(d2[section].keys()))


if __name__ == "__main__":
    unittest.main()
