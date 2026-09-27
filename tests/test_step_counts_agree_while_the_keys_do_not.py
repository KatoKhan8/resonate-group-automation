#!/usr/bin/env python3
"""Tests for scripts/qa/check_campaign_bison.py (TASK-296).

The title pins the defect that drove the whole check: step COUNTS can
agree while the step KEYS do not.  {1, 2, 3} and {1, 2, 4} both have
length 3 but are different sets, and a half-applied sequence change
reads as complete through a count comparison.

Every constructed failure is shown firing with its message.
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.providers import bison, set_transport, reset_transport
from tests.fakebison import FakeBison

from scripts.qa.check_campaign_bison import (
    run,
    extract_template_variables,
    diff_step_keys,
    rule_step_count_matches,
    rule_templates_use_only_carried_variables,
    rule_sender_attached_and_connected,
    rule_no_settled_blank_rows,
    rule_not_paused,
    rule_campaign_exists,
    rule_schedule_and_limits_set,
    rule_id_matches,
)


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class _Base(unittest.TestCase):
    """Shared setup: temp dir, FakeBison, env overrides."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="qa_bison_test_")
        self.campaigns_file = os.path.join(self.tmpdir, "campaigns.jsonl")

        self._orig = {}
        for k in ("CAMPAIGNS", "BISON_KEY"):
            self._orig[k] = os.environ.get(k)

        os.environ["CAMPAIGNS"] = self.campaigns_file
        os.environ["BISON_KEY"] = "test-key"

        self.fb = FakeBison(workspace=10, name="PRODUCTIVE")
        set_transport(self.fb)

    def tearDown(self):
        reset_transport()
        for k, v in self._orig.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _campaign_row(self, bison_id, cadence_steps=3, **kw):
        row = {
            "campaign_id": f"camp-{bison_id}",
            "client": "test",
            "status": "running",
            "bison_campaign_id": bison_id,
            "cadence_steps": cadence_steps,
            "pause": None,
        }
        row.update(kw)
        return row

    def _setup_campaign(self, bison_id, n_steps=3, status="active",
                        schedule=True, sender_ids=None,
                        sender_statuses=None, queue_rows=None):
        """Put a campaign into FakeBison with steps, schedule, senders."""
        self.fb.campaigns[bison_id] = {
            "id": bison_id, "name": f"Test Campaign {bison_id}",
            "status": status,
            "max_emails_per_day": 50,
            "max_new_leads_per_day": 10,
        }
        self.fb.members.setdefault(bison_id, [])

        if n_steps > 0:
            steps = []
            for i in range(1, n_steps + 1):
                steps.append({
                    "id": 4000 + i,
                    "order": i,
                    "email_subject": f"{{SUBJECT_{i}}}",
                    "email_body": f"<p>{{BODY_{i}}}</p>",
                    "wait_in_days": 3,
                    "active": True,
                    "thread_reply": i > 1,
                })
            self.fb.sequences[bison_id] = steps

        if schedule:
            self.fb.schedules[bison_id] = {
                "id": 1,
                "days": ["monday", "tuesday", "wednesday",
                         "thursday", "friday"],
                "start_time": "09:00:00",
                "end_time": "17:00:00",
                "timezone": "Europe/London",
            }

        if sender_ids is not None:
            self.fb.senders[bison_id] = sender_ids

        if queue_rows is not None:
            self.fb.queue[bison_id] = queue_rows

        return bison_id


# ============================================= the title defect: counts vs keys

class TestDiffStepKeys(unittest.TestCase):
    """The comparison that drove the whole check.

    ``len(a) == len(b)`` compares equal while the sets differ.  The set
    diff in both directions catches the half-applied change.
    """

    def test_identical_sets(self):
        only_a, only_b = diff_step_keys({1, 2, 3}, {1, 2, 3})
        self.assertEqual(only_a, [])
        self.assertEqual(only_b, [])

    def test_same_count_different_keys(self):
        """THE DEFECT.  3 == 3 but the keys are different."""
        only_a, only_b = diff_step_keys({1, 2, 4}, {1, 2, 3})
        self.assertIn(4, only_a)
        self.assertIn(3, only_b)

    def test_same_count_different_keys_reversed(self):
        only_a, only_b = diff_step_keys({1, 2, 3}, {1, 2, 4})
        self.assertIn(3, only_a)
        self.assertIn(4, only_b)

    def test_subset(self):
        only_a, only_b = diff_step_keys({1, 2}, {1, 2, 3})
        self.assertEqual(only_a, [])
        self.assertEqual(only_b, [3])

    def test_superset(self):
        only_a, only_b = diff_step_keys({1, 2, 3, 4}, {1, 2, 3})
        self.assertEqual(only_a, [4])
        self.assertEqual(only_b, [])

    def test_empty_both(self):
        only_a, only_b = diff_step_keys(set(), set())
        self.assertEqual(only_a, [])
        self.assertEqual(only_b, [])

    def test_completely_different_same_size(self):
        """Three vs three with zero overlap."""
        only_a, only_b = diff_step_keys({1, 2, 3}, {4, 5, 6})
        self.assertEqual(sorted(only_a), [1, 2, 3])
        self.assertEqual(sorted(only_b), [4, 5, 6])


class TestStepCountMatchesWhileKeysDoNot(_Base):
    """The constructed failure the task requires:

    provider step count equals stored cadence_steps, but the step KEYS
    differ.  The count comparison passes; the set diff catches it.
    """

    def test_count_matches_but_keys_differ(self):
        cid = self._setup_campaign(502, n_steps=3)
        # Rewrite step orders to {1, 2, 4} — count is still 3
        steps = self.fb.sequences[cid]
        steps[2]["order"] = 4

        _write_jsonl(self.campaigns_file,
                     [self._campaign_row(cid, cadence_steps=3)])

        result = rule_step_count_matches(
            cid,
            self._campaign_row(cid, cadence_steps=3),
            {"steps": bison.sequence_steps(cid)})

        self.assertFalse(result["pass"])
        self.assertEqual(result["stored_cadence_steps"], 3)
        self.assertEqual(result["provider_step_count"], 3)
        self.assertIn(4, result["provider_step_keys"])
        self.assertIn(3, result["only_in_stored"])
        self.assertIn(4, result["only_in_provider"])

    def test_matching_keys_pass(self):
        cid = self._setup_campaign(502, n_steps=3)
        _write_jsonl(self.campaigns_file,
                     [self._campaign_row(cid, cadence_steps=3)])

        result = rule_step_count_matches(
            cid,
            self._campaign_row(cid, cadence_steps=3),
            {"steps": bison.sequence_steps(cid)})

        self.assertTrue(result["pass"])
        self.assertEqual(result["provider_step_keys"], [1, 2, 3])
        self.assertEqual(result["only_in_provider"], [])
        self.assertEqual(result["only_in_stored"], [])

    def test_four_step_campaign_matches(self):
        cid = self._setup_campaign(502, n_steps=4)
        _write_jsonl(self.campaigns_file,
                     [self._campaign_row(cid, cadence_steps=4)])

        result = rule_step_count_matches(
            cid,
            self._campaign_row(cid, cadence_steps=4),
            {"steps": bison.sequence_steps(cid)})

        self.assertTrue(result["pass"])
        self.assertEqual(result["stored_cadence_steps"], 4)
        self.assertEqual(result["provider_step_keys"], [1, 2, 3, 4])

    def test_eleven_three_step_campaigns_are_correct(self):
        """Under Option A, 485-500 (eleven) hold three and are correct."""
        for cid in range(485, 496):
            self._setup_campaign(cid, n_steps=3)
        rows = [self._campaign_row(c, cadence_steps=3)
                for c in range(485, 496)]
        _write_jsonl(self.campaigns_file, rows)

        for cid in range(485, 496):
            result = rule_step_count_matches(
                cid,
                self._campaign_row(cid, cadence_steps=3),
                {"steps": bison.sequence_steps(cid)})
            self.assertTrue(
                result["pass"],
                f"campaign {cid} should pass (three-step is correct)")

    def test_count_match_keys_mismatch_message_names_both_sides(self):
        cid = self._setup_campaign(502, n_steps=3)
        steps = self.fb.sequences[cid]
        steps[2]["order"] = 4

        result = rule_step_count_matches(
            cid,
            self._campaign_row(cid, cadence_steps=3),
            {"steps": bison.sequence_steps(cid)})

        detail = result["detail"]
        self.assertIn("stored=3", detail)
        self.assertIn("only_provider", detail)
        self.assertIn("only_stored", detail)


# ========================================= template variables, both directions

class TestExtractTemplateVariables(unittest.TestCase):

    def test_single_variable(self):
        self.assertEqual(extract_template_variables("{BODY_1}"),
                         {"body_1"})

    def test_multiple_variables(self):
        self.assertEqual(
            extract_template_variables(
                "Hello {FIRST_NAME}, re: {SUBJECT_1}"),
            {"first_name", "subject_1"})

    def test_double_brace_syntax(self):
        self.assertEqual(extract_template_variables("{{BODY_1}}"),
                         {"body_1"})

    def test_empty_text(self):
        self.assertEqual(extract_template_variables(""), set())
        self.assertEqual(extract_template_variables(None), set())

    def test_no_variables(self):
        self.assertEqual(extract_template_variables("plain text"), set())


class TestTemplateVariables(_Base):

    def test_matching_variables_pass(self):
        cid = self._setup_campaign(502, n_steps=3)
        lid = self.fb.add_lead("test@example.com")
        self.fb.members[cid] = [lid]
        self.fb.leads[lid]["custom_variables"] = [
            {"name": "body_1", "value": "Hello"},
            {"name": "subject_1", "value": "Test"},
            {"name": "body_2", "value": "Follow up"},
            {"name": "subject_2", "value": "Re: Test"},
            {"name": "body_3", "value": "Final"},
            {"name": "subject_3", "value": "Re: Test"},
        ]

        steps = bison.sequence_steps(cid)
        lead_ids = bison.campaign_lead_ids(cid)
        result = rule_templates_use_only_carried_variables(
            cid, {},
            {"steps": steps, "lead_ids": lead_ids})

        self.assertTrue(result["pass"])
        self.assertEqual(result["only_in_templates"], [])
        self.assertEqual(result["only_in_leads"], [])

    def test_template_names_variable_lead_lacks(self):
        cid = self._setup_campaign(502, n_steps=1)
        self.fb.sequences[cid] = [{
            "id": 4001, "order": 1,
            "email_subject": "{SUBJECT_1}",
            "email_body": "<p>{BODY_9}</p>",
            "wait_in_days": 3, "active": True,
            "thread_reply": False,
        }]
        lid = self.fb.add_lead("test@example.com")
        self.fb.members[cid] = [lid]
        self.fb.leads[lid]["custom_variables"] = [
            {"name": "body_1", "value": "Hello"},
            {"name": "subject_1", "value": "Test"},
        ]

        steps = bison.sequence_steps(cid)
        lead_ids = bison.campaign_lead_ids(cid)
        result = rule_templates_use_only_carried_variables(
            cid, {},
            {"steps": steps, "lead_ids": lead_ids})

        self.assertFalse(result["pass"])
        self.assertIn("body_9", result["only_in_templates"])

    def test_lead_carries_variable_no_template_names(self):
        cid = self._setup_campaign(502, n_steps=1)
        lid = self.fb.add_lead("test@example.com")
        self.fb.members[cid] = [lid]
        self.fb.leads[lid]["custom_variables"] = [
            {"name": "body_1", "value": "Hello"},
            {"name": "subject_1", "value": "Test"},
            {"name": "wasted_var", "value": "unused"},
        ]

        steps = bison.sequence_steps(cid)
        lead_ids = bison.campaign_lead_ids(cid)
        result = rule_templates_use_only_carried_variables(
            cid, {},
            {"steps": steps, "lead_ids": lead_ids})

        self.assertFalse(result["pass"])
        self.assertIn("wasted_var", result["only_in_leads"])

    def test_both_directions_reported(self):
        cid = self._setup_campaign(502, n_steps=1)
        self.fb.sequences[cid] = [{
            "id": 4001, "order": 1,
            "email_subject": "{SUBJECT_1}",
            "email_body": "<p>{GAP_VAR}</p>",
            "wait_in_days": 3, "active": True,
            "thread_reply": False,
        }]
        lid = self.fb.add_lead("test@example.com")
        self.fb.members[cid] = [lid]
        self.fb.leads[lid]["custom_variables"] = [
            {"name": "body_1", "value": "x"},
            {"name": "subject_1", "value": "y"},
            {"name": "extra_var", "value": "z"},
        ]

        steps = bison.sequence_steps(cid)
        lead_ids = bison.campaign_lead_ids(cid)
        result = rule_templates_use_only_carried_variables(
            cid, {},
            {"steps": steps, "lead_ids": lead_ids})

        self.assertFalse(result["pass"])
        self.assertIn("gap_var", result["only_in_templates"])
        self.assertIn("extra_var", result["only_in_leads"])


# ========================================= sender attached and connected

class TestSenderStatus(_Base):

    def test_no_senders_fails(self):
        cid = self._setup_campaign(502, sender_ids=[])
        result = rule_sender_attached_and_connected(
            cid, {}, {"sender_ids": [], "sender_objects": []})
        self.assertFalse(result["pass"])
        self.assertIn("no senders", result["detail"])

    def test_connected_sender_passes(self):
        cid = self._setup_campaign(502, sender_ids=[100])
        senders = [{"id": 100, "status": "connected", "email": "a@b.com"}]
        result = rule_sender_attached_and_connected(
            cid, {},
            {"sender_ids": [100], "sender_objects": senders})
        self.assertTrue(result["pass"])
        self.assertEqual(result["connected_count"], 1)
        self.assertTrue(result["workspace_asserted"])

    def test_attached_but_disconnected_fails(self):
        cid = self._setup_campaign(502, sender_ids=[100])
        senders = [{"id": 100, "status": "disconnected",
                     "email": "a@b.com"}]
        result = rule_sender_attached_and_connected(
            cid, {},
            {"sender_ids": [100], "sender_objects": senders})
        self.assertFalse(result["pass"])
        self.assertEqual(result["connected_count"], 0)
        self.assertIn("0 connected", result["detail"])

    def test_mixed_connected_and_disconnected(self):
        cid = self._setup_campaign(502, sender_ids=[100, 200])
        senders = [
            {"id": 100, "status": "connected", "email": "a@b.com"},
            {"id": 200, "status": "disconnected", "email": "c@d.com"},
        ]
        result = rule_sender_attached_and_connected(
            cid, {},
            {"sender_ids": [100, 200], "sender_objects": senders})
        self.assertTrue(result["pass"])
        self.assertEqual(result["attached_count"], 2)
        self.assertEqual(result["connected_count"], 1)


# ========================================= no settled blank rows

class TestNoSettledBlankRows(_Base):

    def test_zero_rows_is_vacuous(self):
        cid = self._setup_campaign(502, queue_rows=[])
        result = rule_no_settled_blank_rows(
            cid, {}, {"scheduled_emails": []})
        self.assertFalse(result["pass"])
        self.assertTrue(result["vacuous"])
        self.assertIn("VACUOUS", result["detail"])

    def test_settled_blank_detected(self):
        cid = self._setup_campaign(502, queue_rows=[])
        rows = [
            {"id": 1001, "status": "stopped",
             "email_subject": "",
             "email_body": "<p></p>",
             "lead": {"id": 200},
             "sequence_step_id": 4001,
             "thread_reply": False},
        ]
        result = rule_no_settled_blank_rows(
            cid, {}, {"scheduled_emails": rows})
        self.assertFalse(result["pass"])
        self.assertFalse(result["vacuous"])
        self.assertEqual(result["settled_blank_count"], 1)
        self.assertIn(1001, result["settled_blank_row_ids"])

    def test_clean_rows_pass(self):
        cid = self._setup_campaign(502, queue_rows=[])
        rows = [
            {"id": 1001, "status": "scheduled",
             "email_subject": "Hello",
             "email_body": "<p>World</p>",
             "lead": {"id": 200},
             "sequence_step_id": 4001,
             "thread_reply": False},
        ]
        result = rule_no_settled_blank_rows(
            cid, {}, {"scheduled_emails": rows})
        self.assertTrue(result["pass"])
        self.assertEqual(result["settled_blank_count"], 0)

    def test_none_scheduled_is_not_vacuous_but_unconfirmed(self):
        """When the queue could not be read, the result says so."""
        result = rule_no_settled_blank_rows(
            502, {}, {"scheduled_emails": None})
        self.assertFalse(result["pass"])
        self.assertFalse(result.get("vacuous", False))
        self.assertIn("could not read", result["detail"])

    def test_pending_blank_not_counted_as_settled(self):
        cid = self._setup_campaign(502, queue_rows=[])
        rows = [
            {"id": 1001, "status": "scheduled",
             "email_subject": "",
             "email_body": "<p></p>",
             "lead": {"id": 200},
             "sequence_step_id": 4001,
             "thread_reply": False},
        ]
        result = rule_no_settled_blank_rows(
            cid, {}, {"scheduled_emails": rows})
        # Pending blank: not settled, so the rule PASSES
        self.assertTrue(result["pass"])
        self.assertEqual(result["settled_blank_count"], 0)
        self.assertEqual(result["pending_blank_count"], 1)


# ========================================= not paused

class TestNotPaused(_Base):

    def test_active_campaign_passes(self):
        cid = self._setup_campaign(502, status="active")
        result = rule_not_paused(
            cid,
            {"pause": None},
            {"campaign_data": {"status": "active"}})
        self.assertTrue(result["pass"])

    def test_paused_unexpected_fails(self):
        cid = self._setup_campaign(502, status="paused")
        result = rule_not_paused(
            cid,
            {"pause": None},
            {"campaign_data": {"status": "paused"}})
        self.assertFalse(result["pass"])
        self.assertIn("paused", result["detail"])

    def test_expected_pause_passes(self):
        cid = self._setup_campaign(502, status="paused")
        result = rule_not_paused(
            cid,
            {"pause": {"reason": "operator request",
                        "at": "2026-09-25T00:00:00Z"}},
            {"campaign_data": {"status": "paused"}})
        self.assertTrue(result["pass"])

    def test_registry_says_paused_provider_says_active(self):
        result = rule_not_paused(
            502,
            {"pause": {"reason": "freeze"}},
            {"campaign_data": {"status": "active"}})
        self.assertFalse(result["pass"])
        self.assertIn("registry says paused", result["detail"])


# ========================================= campaign exists

class TestCampaignExists(_Base):

    def test_existing_campaign_passes(self):
        cid = self._setup_campaign(502)
        result = rule_campaign_exists(cid, {}, {})
        self.assertTrue(result["pass"])

    def test_missing_campaign_fails(self):
        result = rule_campaign_exists(999, {}, {})
        self.assertFalse(result["pass"])


# ========================================= schedule and limits

class TestScheduleAndLimits(_Base):

    def test_full_schedule_passes(self):
        cid = self._setup_campaign(502)
        result = rule_schedule_and_limits_set(
            cid, {},
            {"schedule": bison.schedule(cid),
             "campaign_data": self.fb.campaigns[cid]})
        self.assertTrue(result["pass"])

    def test_no_schedule_fails(self):
        cid = self._setup_campaign(502, schedule=False)
        result = rule_schedule_and_limits_set(
            cid, {},
            {"schedule": bison.schedule(cid),
             "campaign_data": self.fb.campaigns[cid]})
        self.assertFalse(result["pass"])
        self.assertIn("no schedule", result["detail"])

    def test_no_limits_fails(self):
        cid = self._setup_campaign(502)
        self.fb.campaigns[cid]["max_emails_per_day"] = None
        result = rule_schedule_and_limits_set(
            cid, {},
            {"schedule": bison.schedule(cid),
             "campaign_data": self.fb.campaigns[cid]})
        self.assertFalse(result["pass"])
        self.assertIn("daily email limit", result["detail"])


# ========================================= id matches registry

class TestIdMatches(_Base):

    def test_matching_id_passes(self):
        row = self._campaign_row(502)
        result = rule_id_matches(502, row, {})
        self.assertTrue(result["pass"])

    def test_mismatched_id_fails(self):
        row = self._campaign_row(502)
        result = rule_id_matches(999, row, {})
        self.assertFalse(result["pass"])

    def test_no_bison_id_fails(self):
        result = rule_id_matches(502, {"campaign_id": "x"}, {})
        self.assertFalse(result["pass"])


# ========================================= full run, exit codes

class TestFullRun(_Base):

    def test_all_pass(self):
        """Full run with all rules.  FakeBison's sender-emails route
        returns ``{"id": s}`` without a status field, so the connected
        check cannot pass through the fake - that rule is verified by
        unit tests with mock sender objects instead."""
        cid = self._setup_campaign(
            502, sender_ids=[100],
            queue_rows=[{
                "id": 9001, "status": "scheduled",
                "email_subject": "Hello", "email_body": "<p>World</p>",
                "lead": {"id": 200}, "sequence_step_id": 4001,
                "thread_reply": False,
            }])
        lid = self.fb.add_lead("test@example.com")
        self.fb.members[cid] = [lid]
        self.fb.leads[lid]["custom_variables"] = [
            {"name": v, "value": f"val-{v}"}
            for v in ("subject_1", "subject_2", "subject_3",
                      "body_1", "body_2", "body_3")
        ]
        _write_jsonl(self.campaigns_file,
                     [self._campaign_row(cid, cadence_steps=3)])

        result = run(workspaces=self.tmpdir, campaign_ids=[502])
        self.assertEqual(result["subjects"], 1)
        per = result["per_campaign"][502]
        # Six of eight rules pass through FakeBison; sender status fails
        # because the fake serves no status field (tested by unit tests).
        expected_pass = {
            "campaign_exists", "step_count_matches",
            "templates_use_only_carried_variables",
            "schedule_and_limits_set", "no_settled_blank_rows",
            "not_paused", "id_matches_our_registry",
        }
        for rule_name in expected_pass:
            self.assertNotIn(
                rule_name, per["failed_rules"],
                f"{rule_name} should pass but failed: "
                f"{per['rules'].get(rule_name)}")

    def test_fail_exit_code(self):
        cid = self._setup_campaign(502, status="paused")
        _write_jsonl(self.campaigns_file,
                     [self._campaign_row(cid, cadence_steps=3)])

        result = run(workspaces=self.tmpdir, campaign_ids=[502])
        self.assertEqual(result["verdict"], "FAIL")
        self.assertTrue(result["refused"])

    def test_no_campaigns_vacuous(self):
        _write_jsonl(self.campaigns_file,
                     [self._campaign_row(502, cadence_steps=3)])
        result = run(workspaces=self.tmpdir, campaign_ids=[])
        self.assertEqual(result["verdict"], "VACUOUS")
        self.assertEqual(result["subjects"], 0)

    def test_multiple_campaigns_ordered_by_id(self):
        for cid in [503, 485, 502]:
            self._setup_campaign(cid, n_steps=3)
        rows = [self._campaign_row(c, cadence_steps=3)
                for c in [503, 485, 502]]
        _write_jsonl(self.campaigns_file, rows)

        result = run(workspaces=self.tmpdir,
                     campaign_ids=[503, 485, 502])
        ids = list(result["per_campaign"].keys())
        self.assertEqual(ids, [485, 502, 503])

    def test_arithmetic_closes(self):
        """clean + |union(offenders)| == subjects."""
        for cid in [502, 503]:
            self._setup_campaign(cid, n_steps=3)
        # 503 is paused unexpectedly -> will fail not_paused
        self.fb.campaigns[503]["status"] = "paused"
        rows = [self._campaign_row(c, cadence_steps=3)
                for c in [502, 503]]
        _write_jsonl(self.campaigns_file, rows)

        result = run(workspaces=self.tmpdir,
                     campaign_ids=[502, 503])
        all_offenders = set()
        for ids in result["offenders"].values():
            all_offenders |= set(ids)
        self.assertEqual(
            result["clean"] + len(all_offenders),
            result["subjects"])

    def test_all_rule_keys_present_in_counts_and_offenders(self):
        """Every key in counts/offenders exists in rules, and vice versa."""
        cid = self._setup_campaign(502, n_steps=3)
        _write_jsonl(self.campaigns_file,
                     [self._campaign_row(cid, cadence_steps=3)])

        result = run(workspaces=self.tmpdir, campaign_ids=[502])
        for key in result["counts"]:
            self.assertIn(key, result["rules"])
        for key in result["offenders"]:
            self.assertIn(key, result["rules"])
        for key in result["rules"]:
            self.assertIn(key, result["counts"])
            self.assertIn(key, result["offenders"])

    def test_evidence_covers_provider_reads_and_files(self):
        cid = self._setup_campaign(502, n_steps=3)
        _write_jsonl(self.campaigns_file,
                     [self._campaign_row(cid, cadence_steps=3)])

        result = run(workspaces=self.tmpdir, campaign_ids=[502])
        evidence = result["evidence"]
        self.assertTrue(len(evidence["provider_reads"]) > 0)
        self.assertTrue(len(evidence["files_read"]) > 0)
        self.assertFalse(evidence["provider_reads_skipped"])
        fr = evidence["files_read"][0]
        self.assertIn("mtime", fr)
        self.assertIn("rows", fr)
        self.assertIn("path", fr)

    def test_missing_workspaces_errors(self):
        with self.assertRaises(FileNotFoundError):
            run(workspaces="/nonexistent/path")


# ========================================= the constructed failures

class TestConstructedFailures(_Base):
    """One constructed failure per rule, shown firing with its message."""

    def test_campaign_exists_fires(self):
        result = rule_campaign_exists(999, {}, {})
        self.assertFalse(result["pass"])
        self.assertIn("provider read failed", result["detail"])

    def test_step_keys_differ_fires(self):
        cid = self._setup_campaign(502, n_steps=3)
        self.fb.sequences[cid][2]["order"] = 4
        result = rule_step_count_matches(
            cid,
            self._campaign_row(cid, cadence_steps=3),
            {"steps": bison.sequence_steps(cid)})
        self.assertFalse(result["pass"])
        self.assertIn("4", str(result["only_in_provider"]))
        self.assertIn("3", str(result["only_in_stored"]))

    def test_template_variable_gap_fires(self):
        cid = self._setup_campaign(502, n_steps=1)
        self.fb.sequences[cid] = [{
            "id": 4001, "order": 1,
            "email_subject": "{SUBJECT_1}",
            "email_body": "<p>{MISSING_VAR}</p>",
            "wait_in_days": 3, "active": True,
            "thread_reply": False,
        }]
        lid = self.fb.add_lead("test@example.com")
        self.fb.members[cid] = [lid]
        self.fb.leads[lid]["custom_variables"] = [
            {"name": "body_1", "value": "x"},
            {"name": "subject_1", "value": "y"},
        ]
        result = rule_templates_use_only_carried_variables(
            cid, {},
            {"steps": bison.sequence_steps(cid),
             "lead_ids": bison.campaign_lead_ids(cid)})
        self.assertFalse(result["pass"])
        self.assertIn("missing_var", result["only_in_templates"])

    def test_sender_disconnected_fires(self):
        result = rule_sender_attached_and_connected(
            502, {},
            {"sender_ids": [100],
             "sender_objects": [
                 {"id": 100, "status": "disconnected"}]})
        self.assertFalse(result["pass"])
        self.assertEqual(result["connected_count"], 0)

    def test_no_schedule_fires(self):
        result = rule_schedule_and_limits_set(
            502, {}, {"schedule": {}, "campaign_data": {}})
        self.assertFalse(result["pass"])
        self.assertIn("no schedule", result["detail"])

    def test_settled_blank_fires(self):
        rows = [
            {"id": 1001, "status": "stopped",
             "email_subject": "", "email_body": "<p></p>",
             "lead": {"id": 200}, "sequence_step_id": 4001,
             "thread_reply": False},
        ]
        result = rule_no_settled_blank_rows(
            502, {}, {"scheduled_emails": rows})
        self.assertFalse(result["pass"])
        self.assertIn(1001, result["settled_blank_row_ids"])

    def test_unexpected_pause_fires(self):
        result = rule_not_paused(
            502, {"pause": None},
            {"campaign_data": {"status": "paused"}})
        self.assertFalse(result["pass"])
        self.assertIn("paused", result["detail"])

    def test_id_mismatch_fires(self):
        result = rule_id_matches(
            999, {"bison_campaign_id": 502}, {})
        self.assertFalse(result["pass"])
        self.assertIn("502", result["detail"])
        self.assertIn("999", result["detail"])


if __name__ == "__main__":
    unittest.main()
