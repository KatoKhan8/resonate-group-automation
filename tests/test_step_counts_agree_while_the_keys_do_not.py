"""Step counts agree while the keys do not.

TASK-296. The step_count_matches rule diffs step KEYS as sets in both
directions, not step counts. len(a) == len(b) passes while the sets differ;
a half-applied change reads as complete through a count comparison.

This test constructs one campaign whose provider step count is right and
whose step keys are wrong, and shows the set diff catching it.

Every constructed failure, one per rule, is demonstrated here.
"""
import json
import os
import shutil
import tempfile
import unittest

# Ensure project root is on path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))

import sys
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.qa import check_campaign_bison as check


# ----------------------------------------------------------- fake bison

class FakeBison:
    """A fake bison module for testing. No provider calls."""

    def __init__(self):
        self._campaigns = {}
        self._steps = {}
        self._schedules = {}
        self._senders = {}
        self._scheduled_emails = {}
        self._leads = {}
        self._lead_ids = {}
        self._custom_vars = {}
        self._workspace = {"id": 10, "name": "Productive"}
        self._sender_inventory = {}

    def campaign(self, cid):
        if cid in self._campaigns:
            return self._campaigns[cid]
        raise Exception(f"campaign {cid} not found")

    def sequence_steps(self, cid):
        return self._steps.get(cid, [])

    def schedule(self, cid):
        return self._schedules.get(cid, {})

    def campaign_senders(self, cid):
        return self._senders.get(cid, [])

    def sender_emails(self, expect_workspace=None):
        return list(self._sender_inventory.values()), {"total": len(self._sender_inventory)}

    def scheduled_emails(self, cid):
        return self._scheduled_emails.get(cid, [])

    def campaign_lead_ids(self, cid):
        return self._lead_ids.get(cid, [])

    def lead(self, lid):
        return self._leads.get(lid, {})

    def variables_of(self, lead):
        """Mirror of bison.variables_of."""
        return {v.get("name"): v.get("value")
                for v in (lead or {}).get("custom_variables") or []
                if isinstance(v, dict)}

    def custom_variables(self):
        return self._custom_vars

    def bound_workspace(self):
        return self._workspace


# ----------------------------------------------------------- helpers

def _make_work_dir(campaign_rows):
    """Create a temp dir with campaigns.jsonl."""
    tmpdir = tempfile.mkdtemp(prefix="qa_test_")
    path = os.path.join(tmpdir, "campaigns.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for row in campaign_rows:
            fh.write(json.dumps(row) + "\n")
    return tmpdir


def _good_campaign_row(cid, bison_id, cadence_steps):
    return {
        "campaign_id": cid,
        "bison_campaign_id": bison_id,
        "cadence_steps": cadence_steps,
        "status": "running",
        "launch": {"state": "launched"},
    }


def _fake_bison_good(bison_id, cadence_steps):
    """A FakeBison configured for a passing campaign."""
    fb = FakeBison()
    fb._campaigns[bison_id] = {"id": bison_id, "status": "active"}

    steps = []
    for i, cs in enumerate(cadence_steps, start=1):
        key = cs.get("key", f"em{i}") if isinstance(cs, dict) else f"em{i}"
        steps.append({
            "id": 1000 + i,
            "order": i,
            "email_subject": "{SUBJECT_" + str(i) + "}",
            "email_body": "<p>{BODY_" + str(i) + "}</p>",
            "wait_in_days": 3,
            "active": True,
            "thread_reply": i > 1,
        })
    fb._steps[bison_id] = steps

    fb._schedules[bison_id] = {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "start_time": "09:00",
        "end_time": "17:00",
        "timezone": "Europe/Zagreb",
    }

    sender_id = 2736
    fb._senders[bison_id] = [sender_id]
    fb._sender_inventory[sender_id] = {
        "id": sender_id, "email": "anna@productive.test",
        "status": "connected",
    }

    fb._scheduled_emails[bison_id] = [
        {"id": 9001, "lead": {"id": 50001}, "sequence_step_id": 1001,
         "email_subject": "Hello Acme", "email_body": "<p>Real body</p>",
         "status": "scheduled", "thread_reply": False},
    ]

    lead_id = 50001
    fb._lead_ids[bison_id] = [lead_id]
    fb._leads[lead_id] = {
        "id": lead_id,
        "custom_variables": [
            {"name": "subject_1", "value": "Hello Acme"},
            {"name": "body_1", "value": "Real body"},
            {"name": "record_id", "value": "acme"},
            {"name": "contact_key", "value": "john"},
        ],
    }
    fb._custom_vars = {"subject_1": 1, "body_1": 2, "record_id": 3,
                       "contact_key": 4}
    return fb


# =========================================================== THE TESTS

class TestStepCountsAgreeWhileKeysDoNot(unittest.TestCase):
    """The central test: counts match, keys do not, set diff catches it."""

    def test_count_matches_but_keys_differ_is_caught_by_set_diff(self):
        """Three steps on both sides, but different keys.

        Stored: em1, em2, em3
        Provider: em1, em2, em4  (same count, different key)

        A count comparison passes. The set diff catches it.
        """
        cadence = [{"key": "em1"}, {"key": "em2"}, {"key": "em3"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])

        try:
            fb = _fake_bison_good(485, cadence)
            # Override the provider steps to have em4 instead of em3
            # (order 3 -> em3 on stored side, but we relabel to em4)
            fb._steps[485][2]["order"] = 4  # third step has order=4

            result = check.run(
                phase="pre_push",
                campaigns=[485],
                workspaces=work,
                live_reads=True,
                bison_module=fb,
            )

            per = result["per_campaign"][0]
            self.assertEqual(
                per["verdicts"]["step_count_matches"], "FAIL",
                "step_count_matches must FAIL when keys differ even if "
                "counts match")
            offender = per["offenders"]["step_count_matches"][0]
            self.assertIn("only_in_stored", offender)
            self.assertIn("em3", offender)
            self.assertIn("only_in_provider", offender)
            self.assertIn("em4", offender)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_matching_keys_pass(self):
        """Same keys on both sides: PASS."""
        cadence = [{"key": "em1"}, {"key": "em2"}, {"key": "em3"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])

        try:
            fb = _fake_bison_good(485, cadence)
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(per["verdicts"]["step_count_matches"], "PASS")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_four_step_campaign_passes(self):
        """A new four-step campaign with matching keys: PASS."""
        cadence = [{"key": "em1"}, {"key": "em2"}, {"key": "em3"},
                    {"key": "em4"}]
        row = _good_campaign_row("c2", 502, cadence)
        work = _make_work_dir([row])

        try:
            fb = _fake_bison_good(502, cadence)
            result = check.run(
                phase="pre_push", campaigns=[502], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(per["verdicts"]["step_count_matches"], "PASS")
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestCampaignExists(unittest.TestCase):
    """Rule 1: campaign exists by ID at the provider."""

    def test_missing_campaign_fails(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 999, cadence)
        work = _make_work_dir([row])
        try:
            fb = FakeBison()
            # No campaign registered -> raises
            result = check.run(
                phase="pre_push", campaigns=[999], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(per["verdicts"]["campaign_exists"], "UNCONFIRMED")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_existing_campaign_passes(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(per["verdicts"]["campaign_exists"], "PASS")
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestSenderAttachedAndConnected(unittest.TestCase):
    """Rule 4: attached is not connected."""

    def test_attached_but_disconnected_fails(self):
        """A sender that is attached but not Connected is a FAIL."""
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            # Override sender status to disconnected
            fb._sender_inventory[2736]["status"] = "disconnected"
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(
                per["verdicts"]["sender_attached_and_connected"], "FAIL")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_no_senders_fails(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            fb._senders[485] = []
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(
                per["verdicts"]["sender_attached_and_connected"], "FAIL")
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestScheduleAndLimitsSet(unittest.TestCase):
    """Rule 5: schedule and limits must be set."""

    def test_empty_schedule_fails(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            fb._schedules[485] = {}
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(
                per["verdicts"]["schedule_and_limits_set"], "FAIL")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_partial_schedule_fails(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            fb._schedules[485] = {"days": ["monday"]}  # missing start/end/tz
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(
                per["verdicts"]["schedule_and_limits_set"], "FAIL")
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestNoSettledBlankRows(unittest.TestCase):
    """Rule 6: zero settled blank rows."""

    def test_settled_blank_rows_fail(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            fb._scheduled_emails[485] = [
                {"id": 9001, "lead": {"id": 50001},
                 "sequence_step_id": 1001,
                 "email_subject": "", "email_body": "<p></p>",
                 "status": "stopped", "thread_reply": False},
            ]
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(
                per["verdicts"]["no_settled_blank_rows"], "FAIL")
            self.assertIn("9001", per["offenders"]["no_settled_blank_rows"][0])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_zero_scheduled_rows_is_vacuous(self):
        """Zero scheduled rows is VACUOUS, not PASS."""
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            fb._scheduled_emails[485] = []
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(
                per["verdicts"]["no_settled_blank_rows"], "VACUOUS")
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestNotPaused(unittest.TestCase):
    """Rule 7: campaign is not paused."""

    def test_paused_campaign_fails(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            fb._campaigns[485]["status"] = "paused"
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(per["verdicts"]["not_paused"], "FAIL")
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestIdMatchesRegistry(unittest.TestCase):
    """Rule 8: provider id matches campaigns.jsonl."""

    def test_unregistered_campaign_fails(self):
        row = _good_campaign_row("c1", 485, [{"key": "em1"}])
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, [{"key": "em1"}])
            # Check a campaign id not in the registry
            fb._campaigns[999] = {"id": 999, "status": "active"}
            result = check.run(
                phase="pre_push", campaigns=[999], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(
                per["verdicts"]["id_matches_our_registry"], "FAIL")
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestTemplateVariables(unittest.TestCase):
    """Rule 3: templates use only carried variables, both directions."""

    def test_template_names_variable_no_lead_carries(self):
        """Template references {BODY_5} but no lead carries body_5."""
        cadence = [{"key": "em1"}, {"key": "em2"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            # Add a step that references BODY_5
            fb._steps[485].append({
                "id": 1003, "order": 3,
                "email_subject": "{SUBJECT_5}",
                "email_body": "<p>{BODY_5}</p>",
                "wait_in_days": 3, "active": True, "thread_reply": True,
            })
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            per = result["per_campaign"][0]
            self.assertEqual(
                per["verdicts"]["templates_use_only_carried_variables"], "FAIL")
            offender = per["offenders"]["templates_use_only_carried_variables"][0]
            self.assertIn("BODY_5", offender)
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestExitCodes(unittest.TestCase):
    """Exit codes per the QA contract."""

    def test_pass_exits_zero(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            self.assertEqual(check._exit_code(result), 0)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_fail_exits_one(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            fb._campaigns[485]["status"] = "paused"
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            self.assertEqual(check._exit_code(result), 1)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_vacuous_exits_two(self):
        """subjects == 0 exits 2."""
        work = _make_work_dir([])
        try:
            fb = FakeBison()
            result = check.run(
                phase="pre_push", campaigns=None, workspaces=work,
                live_reads=True, bison_module=fb)
            self.assertEqual(check._exit_code(result), 2)
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestArithmeticCloses(unittest.TestCase):
    """clean + |offenders union| == subjects."""

    def test_arithmetic_closes_on_all_pass(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            subjects = result["subjects"]
            clean = result["clean"]
            all_offending = set()
            for ids in result["offenders"].values():
                all_offending.update(ids)
            self.assertEqual(clean + len(all_offending), subjects)
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestMultipleCampaigns(unittest.TestCase):
    """Multiple campaigns checked, ordered by provider id numerically."""

    def test_ordered_by_provider_id(self):
        cadence3 = [{"key": "em1"}, {"key": "em2"}, {"key": "em3"}]
        cadence4 = [{"key": "em1"}, {"key": "em2"}, {"key": "em3"},
                     {"key": "em4"}]
        rows = [
            _good_campaign_row("c1", 502, cadence4),
            _good_campaign_row("c2", 485, cadence3),
            _good_campaign_row("c3", 490, cadence3),
        ]
        work = _make_work_dir(rows)
        try:
            fb = FakeBison()
            for cid, cadence in [(502, cadence4), (485, cadence3),
                                  (490, cadence3)]:
                fb._campaigns[cid] = {"id": cid, "status": "active"}
                steps = []
                for i in range(len(cadence)):
                    steps.append({
                        "id": 1000 + i, "order": i + 1,
                        "email_subject": "{SUBJECT_" + str(i + 1) + "}",
                        "email_body": "<p>{BODY_" + str(i + 1) + "}</p>",
                        "wait_in_days": 3, "active": True,
                        "thread_reply": i > 0,
                    })
                fb._steps[cid] = steps
                fb._schedules[cid] = {
                    "days": ["monday"], "start_time": "09:00",
                    "end_time": "17:00", "timezone": "Europe/Zagreb"}
                fb._senders[cid] = [2736]
                fb._sender_inventory[2736] = {
                    "id": 2736, "status": "connected"}
                fb._scheduled_emails[cid] = [
                    {"id": 9001, "lead": {"id": 50001},
                     "email_subject": "Hi", "email_body": "<p>body</p>",
                     "status": "scheduled", "thread_reply": False}]
                fb._lead_ids[cid] = [50001]
                fb._leads[50001] = {
                    "id": 50001,
                    "custom_variables": [
                        {"name": "subject_1", "value": "Hi"},
                        {"name": "body_1", "value": "body"}]}
            fb._custom_vars = {"subject_1": 1, "body_1": 2}

            result = check.run(
                phase="pre_push", campaigns=[502, 485, 490],
                workspaces=work, live_reads=True, bison_module=fb)

            ids = [p["campaign_id"] for p in result["per_campaign"]]
            self.assertEqual(ids, [485, 490, 502],
                             "campaigns must be ordered by provider id "
                             "numerically")
        finally:
            shutil.rmtree(work, ignore_errors=True)


class TestRulesKeysConsistent(unittest.TestCase):
    """Every key in counts/offenders exists in rules, and vice versa."""

    def test_rules_keys_consistent(self):
        cadence = [{"key": "em1"}]
        row = _good_campaign_row("c1", 485, cadence)
        work = _make_work_dir([row])
        try:
            fb = _fake_bison_good(485, cadence)
            result = check.run(
                phase="pre_push", campaigns=[485], workspaces=work,
                live_reads=True, bison_module=fb)
            rule_keys = set(result["rules"].keys())
            count_keys = set(result["counts"].keys())
            offender_keys = set(result["offenders"].keys())
            self.assertEqual(rule_keys, count_keys)
            self.assertEqual(rule_keys, offender_keys)
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
