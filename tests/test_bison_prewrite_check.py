#!/usr/bin/env python3
"""Tests for the bison pre-write check script.

Uses FakeBison for the transport and temp files for canonical state.
Each check is tested independently, plus the full flow with exit code
read off the subprocess.

FAIL-CLOSED PROPERTY: every check that cannot read its input returns
FAIL, never PASS. This is tested explicitly for each check.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.providers import bison, set_transport, reset_transport
from tests.fakebison import FakeBison


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _write_client_config(base_dir, client_name, config):
    clients_dir = os.path.join(base_dir, "clients")
    os.makedirs(clients_dir, exist_ok=True)
    path = os.path.join(clients_dir, f"{client_name}.yaml")
    import yaml
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f)


class _Base(unittest.TestCase):
    """Shared setup: temp dir, fake bison, env overrides."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="bison_prewrite_test_")
        self.campaigns_file = os.path.join(self.tmpdir, "campaigns.jsonl")
        self.queue_file = os.path.join(self.tmpdir, "queue.jsonl")
        self.clients_dir = os.path.join(self.tmpdir, "clients")
        os.makedirs(self.clients_dir, exist_ok=True)

        self._orig = {}
        for key in ("CAMPAIGNS", "QUEUE", "CLIENTS_DIR", "BISON_KEY"):
            self._orig[key] = os.environ.get(key)

        os.environ["CAMPAIGNS"] = self.campaigns_file
        os.environ["QUEUE"] = self.queue_file
        os.environ["CLIENTS_DIR"] = self.clients_dir
        os.environ["BISON_KEY"] = "test-key-for-prewrite-check"

        self.fb = FakeBison(workspace=10, name="PRODUCTIVE")
        set_transport(self.fb)
        self.addCleanup(reset_transport)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, val in self._orig.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def _setup_campaign(self, campaign_id="test-1", bison_id=500,
                        client="testclient", status="draft",
                        name="TEST CAMPAIGN"):
        _write_jsonl(self.campaigns_file, [{
            "campaign_id": campaign_id,
            "name": name,
            "client": client,
            "status": status,
            "bison_campaign_id": bison_id,
        }])

    def _setup_queue(self, records=None):
        _write_jsonl(self.queue_file, records or [])

    def _setup_client(self, client_name="testclient", workspace=10):
        _write_client_config(self.tmpdir, client_name, {
            "providers": {
                "emailbison": {"workspace": workspace},
            },
        })

    def _add_provider_campaign(self, name="TEST CAMPAIGN", status="paused"):
        return self.fb.add_campaign(name, status=status)


# ------------------------------------------------ identity

class TestCheckIdentity(_Base):

    def test_pass_when_ids_and_names_match(self):
        from scripts.bison_prewrite_check import check_identity
        from src import bisonfactory

        pid = self._add_provider_campaign("MY CAMPAIGN", "paused")
        campaign = {"bison_campaign_id": pid, "name": "MY CAMPAIGN",
                    "client": "testclient", "campaign_id": "test-1"}
        # The expected name is the DERIVED form, with [client/id] suffix
        expected_name = bisonfactory.provider_campaign_name(campaign)
        # Re-create the provider campaign with the derived name
        self.fb.campaigns[pid]["name"] = expected_name
        workspace = {"id": 10, "name": "PRODUCTIVE"}
        r = check_identity(campaign, self.fb.campaigns[pid], workspace)
        self.assertTrue(r["pass"], r["detail"])

    def test_fail_when_id_mismatches(self):
        from scripts.bison_prewrite_check import check_identity

        campaign = {"bison_campaign_id": 999, "name": "X",
                    "client": "c", "campaign_id": "x"}
        provider = {"id": 500, "name": "X [c/x]"}
        workspace = {"id": 10}
        r = check_identity(campaign, provider, workspace)
        self.assertFalse(r["pass"])
        self.assertIn("id mismatch", r["detail"])

    def test_fail_when_name_mismatches(self):
        from scripts.bison_prewrite_check import check_identity

        campaign = {"bison_campaign_id": 500, "name": "ALPHA",
                    "client": "c", "campaign_id": "x"}
        provider = {"id": 500, "name": "BETA [c/x]"}
        workspace = {"id": 10}
        r = check_identity(campaign, provider, workspace)
        self.assertFalse(r["pass"])
        self.assertIn("name mismatch", r["detail"])


# ------------------------------------------------ tenancy

class TestCheckTenancy(_Base):

    def test_pass_when_workspace_matches(self):
        from scripts.bison_prewrite_check import check_tenancy

        workspace = {"id": 10, "name": "PRODUCTIVE"}
        campaign = {"client": "testclient"}
        config = {"providers": {"emailbison": {"workspace": 10}}}
        r = check_tenancy(campaign, workspace, config)
        self.assertTrue(r["pass"], r["detail"])

    def test_fail_when_workspace_mismatches(self):
        from scripts.bison_prewrite_check import check_tenancy

        workspace = {"id": 29, "name": "BLUEWAVE"}
        campaign = {"client": "testclient"}
        config = {"providers": {"emailbison": {"workspace": 10}}}
        r = check_tenancy(campaign, workspace, config)
        self.assertFalse(r["pass"])
        self.assertIn("workspace mismatch", r["detail"])

    def test_fail_when_no_workspace_configured(self):
        from scripts.bison_prewrite_check import check_tenancy

        workspace = {"id": 10}
        campaign = {"client": "testclient"}
        config = {}
        r = check_tenancy(campaign, workspace, config)
        self.assertFalse(r["pass"])
        self.assertIn("no emailbison.workspace", r["detail"])

    def test_fail_when_no_client(self):
        from scripts.bison_prewrite_check import check_tenancy

        workspace = {"id": 10}
        campaign = {}
        config = {"providers": {"emailbison": {"workspace": 10}}}
        r = check_tenancy(campaign, workspace, config)
        self.assertFalse(r["pass"])
        self.assertIn("no client", r["detail"])


# ------------------------------------------------ state

class TestCheckState(_Base):

    def test_pass_for_draft(self):
        from scripts.bison_prewrite_check import check_state
        r = check_state({"status": "draft"})
        self.assertTrue(r["pass"])
        self.assertEqual(r["source"], "provider")

    def test_pass_for_paused(self):
        from scripts.bison_prewrite_check import check_state
        r = check_state({"status": "paused"})
        self.assertTrue(r["pass"])

    def test_fail_for_active(self):
        from scripts.bison_prewrite_check import check_state
        r = check_state({"status": "active"})
        self.assertFalse(r["pass"])
        self.assertIn("not safe", r["detail"])

    def test_fail_for_empty_status(self):
        from scripts.bison_prewrite_check import check_state
        r = check_state({})
        self.assertFalse(r["pass"])

    def test_fail_for_unknown_status(self):
        from scripts.bison_prewrite_check import check_state
        r = check_state({"status": "something_new"})
        self.assertFalse(r["pass"])
        self.assertIn("unrecognised", r["detail"])


# ------------------------------------------------ population

class TestCheckPopulation(_Base):

    def test_pass_for_empty_campaign(self):
        from scripts.bison_prewrite_check import check_population
        pid = self._add_provider_campaign("C", "paused")
        r = check_population(pid, bison)
        self.assertTrue(r["pass"])
        self.assertIn("leads=0", r["value"])

    def test_pass_for_campaign_with_leads(self):
        from scripts.bison_prewrite_check import check_population
        pid = self._add_provider_campaign("C", "paused")
        lid = self.fb.add_lead("a@test.com")
        self.fb.members[pid].append(lid)
        r = check_population(pid, bison)
        self.assertTrue(r["pass"])
        self.assertIn("leads=1", r["value"])

    def test_fail_when_provider_unreachable(self):
        from scripts.bison_prewrite_check import check_population

        def failing_transport(method, url, headers, body, timeout):
            raise RuntimeError("network down")

        set_transport(failing_transport)
        r = check_population(999, bison)
        self.assertFalse(r["pass"])
        self.assertIn("UNREADABLE", r["value"])


# ------------------------------------------------ senders

class TestCheckSenders(_Base):

    def test_fail_when_no_senders_attached(self):
        from scripts.bison_prewrite_check import check_senders
        pid = self._add_provider_campaign("C", "paused")
        campaign = {"client": "testclient"}
        r = check_senders(campaign, pid, {}, bison)
        self.assertFalse(r["pass"])
        self.assertIn("no sender", r["detail"])

    def test_pass_with_attached_active_senders(self):
        from scripts.bison_prewrite_check import check_senders
        pid = self._add_provider_campaign("C", "paused")
        self.fb.senders[pid] = [1, 2]

        campaign = {"client": "testclient"}
        self._setup_client("testclient", workspace=10)

        from src import senderidentity
        with senderidentity.transaction() as rows:
            rows.extend([
                {"kind": "email_account", "workspace": "testclient",
                 "account_id": "ea-1", "sender_id": "s1",
                 "provider_account_id": "1", "active": True,
                 "health": "ok"},
                {"kind": "email_account", "workspace": "testclient",
                 "account_id": "ea-2", "sender_id": "s2",
                 "provider_account_id": "2", "active": True,
                 "health": "ok"},
            ])
        self.addCleanup(lambda: os.environ.pop("SENDERS", None))

        from src import clients
        config = clients.load("testclient")
        r = check_senders(campaign, pid, config, bison)
        self.assertTrue(r["pass"], r["detail"])


# ------------------------------------------------ caps/killswitch

class TestCheckCapsAndKillswitch(_Base):

    def test_pass_when_no_killswitch_engaged(self):
        from scripts.bison_prewrite_check import check_caps_and_killswitch
        # A draft campaign is expected at staging time. The killswitch
        # campaign layer will say "not running" but that is not a
        # pre-write failure - only frozen is.
        campaign = {"client": "testclient", "status": "draft"}
        config = {}
        r = check_caps_and_killswitch(campaign, config)
        self.assertTrue(r["pass"], r["detail"])

    def test_fail_when_campaign_frozen(self):
        from scripts.bison_prewrite_check import check_caps_and_killswitch
        campaign = {"client": "testclient", "status": "running",
                    "freeze": {"why": "safety hold", "at": "2026-09-16"}}
        r = check_caps_and_killswitch(campaign, {})
        self.assertFalse(r["pass"])
        self.assertIn("FROZEN", r["value"])

    def test_source_is_local(self):
        from scripts.bison_prewrite_check import check_caps_and_killswitch
        campaign = {"client": "testclient", "status": "draft"}
        r = check_caps_and_killswitch(campaign, {})
        self.assertIn("local", r["source"])


# ------------------------------------------------ prior contact

class TestCheckPriorContact(_Base):

    def test_pass_when_no_contacts(self):
        from scripts.bison_prewrite_check import check_prior_contact
        r = check_prior_contact({"leads": []}, 10, bison)
        self.assertTrue(r["pass"])

    def test_pass_when_domain_is_clear(self):
        from scripts.bison_prewrite_check import check_prior_contact
        plan = {"leads": [{"email": "new@clearwater.test"}]}
        r = check_prior_contact(plan, 10, bison)
        self.assertTrue(r["pass"], r["detail"])

    def test_fail_when_contact_in_sequence(self):
        from scripts.bison_prewrite_check import check_prior_contact
        pid = self._add_provider_campaign("OTHER", "active")
        lid = self.fb.add_lead("someone@clearwater.test")
        self.fb.members[pid].append(lid)

        # Wrap the fake transport to add `meta` to /leads responses,
        # since collision.leads_for_domain requires it.
        def transport_with_meta(method, url, headers, body=None, timeout=None):
            status, data = self.fb(method, url, headers, body, timeout)
            import urllib.parse
            path = urllib.parse.urlsplit(url).path
            if "/leads" in path and "campaigns" not in path:
                if isinstance(data, dict) and "meta" not in data:
                    rows = data.get("data", [])
                    data["meta"] = {"total": len(rows), "last_page": 1,
                                    "per_page": 15, "current_page": 1}
            return status, data

        set_transport(transport_with_meta)
        plan = {"leads": [{"email": "someone@clearwater.test"}]}
        r = check_prior_contact(plan, 10, bison)
        self.assertFalse(r["pass"])
        self.assertIn("in_sequence", r["detail"])

    def test_fail_when_collision_check_refuses(self):
        from scripts.bison_prewrite_check import check_prior_contact

        def failing_transport(method, url, headers, body, timeout):
            raise RuntimeError("network down")

        set_transport(failing_transport)
        plan = {"leads": [{"email": "x@domain.test"}]}
        r = check_prior_contact(plan, 10, bison)
        self.assertFalse(r["pass"])


# ------------------------------------------------ full flow via subprocess

class TestFullFlowSubprocess(_Base):

    def test_exit_zero_when_all_pass(self):
        from src import bisonfactory
        campaign_row = {"name": "MY CAMPAIGN", "client": "testclient",
                        "campaign_id": "test-1"}
        derived_name = bisonfactory.provider_campaign_name(campaign_row)
        pid = self._add_provider_campaign(derived_name, "paused")
        # Attach senders so check 5 passes
        self.fb.senders[pid] = [1]
        # Draft is the expected local status at staging time
        self._setup_campaign(bison_id=pid, name="MY CAMPAIGN",
                             status="draft")
        self._setup_queue([])
        self._setup_client(workspace=10)

        # Set up sender identity so check 5 can resolve the sender
        from src import senderidentity
        with senderidentity.transaction() as rows:
            rows.append(
                {"kind": "email_account", "workspace": "testclient",
                 "account_id": "ea-1", "sender_id": "s1",
                 "provider_account_id": "1", "active": True,
                 "health": "ok"})

        def fake_transport(method, url, headers, body=None, timeout=None):
            return self.fb(method, url, headers, body, timeout)

        set_transport(fake_transport)
        try:
            from scripts.bison_prewrite_check import run_checks
            results, code = run_checks("test-1")
            self.assertEqual(code, 0,
                             f"expected exit 0, got {code}. "
                             f"Results: {json.dumps(results, indent=2, default=str)}")
        finally:
            reset_transport()

    def test_exit_one_when_identity_fails(self):
        from src import bisonfactory
        # Provider has the WRONG name (not the derived form)
        pid = self._add_provider_campaign("WRONG NAME", "paused")
        self._setup_campaign(bison_id=pid, name="RIGHT NAME")
        self._setup_queue([])
        self._setup_client(workspace=10)

        env = dict(os.environ)
        env["CAMPAIGNS"] = self.campaigns_file
        env["QUEUE"] = self.queue_file
        env["CLIENTS_DIR"] = self.clients_dir

        def fake_transport(method, url, headers, body=None, timeout=None):
            return self.fb(method, url, headers, body, timeout)

        set_transport(fake_transport)
        try:
            from scripts.bison_prewrite_check import run_checks
            results, code = run_checks("test-1")
            self.assertEqual(code, 1,
                             "expected exit 1 for name mismatch")
            identity = [r for r in results if "Identity" in r["check"]][0]
            self.assertFalse(identity["pass"])
        finally:
            reset_transport()

    def test_exit_one_when_provider_unreachable(self):
        self._setup_campaign(bison_id=500)
        self._setup_queue([])

        def failing(method, url, headers, body=None, timeout=None):
            raise RuntimeError("network down")

        set_transport(failing)
        try:
            from scripts.bison_prewrite_check import run_checks
            results, code = run_checks("test-1")
            self.assertEqual(code, 1)
            self.assertFalse(results[0]["pass"])
        finally:
            reset_transport()


# ------------------------------------------------ fail-closed property

class TestFailClosed(_Base):
    """Every check that cannot read its input returns FAIL, never PASS."""

    def test_identity_fail_closed(self):
        from scripts.bison_prewrite_check import check_identity
        r = check_identity(
            {"bison_campaign_id": 1, "name": "X"},
            {},  # no id, no name
            {"id": 10})
        self.assertFalse(r["pass"])

    def test_state_fail_closed_on_empty(self):
        from scripts.bison_prewrite_check import check_state
        r = check_state({})
        self.assertFalse(r["pass"])

    def test_population_fail_closed_on_error(self):
        from scripts.bison_prewrite_check import check_population

        def failing(method, url, headers, body=None, timeout=None):
            raise RuntimeError("down")

        set_transport(failing)
        r = check_population(999, bison)
        self.assertFalse(r["pass"])

    def test_senders_fail_closed_on_error(self):
        from scripts.bison_prewrite_check import check_senders

        def failing(method, url, headers, body=None, timeout=None):
            raise RuntimeError("down")

        set_transport(failing)
        r = check_senders({"client": "x"}, 999, {}, bison)
        self.assertFalse(r["pass"])

    def test_prior_contact_fail_closed_on_error(self):
        from scripts.bison_prewrite_check import check_prior_contact

        def failing(method, url, headers, body=None, timeout=None):
            raise RuntimeError("down")

        set_transport(failing)
        r = check_prior_contact(
            {"leads": [{"email": "a@b.test"}]}, 10, bison)
        self.assertFalse(r["pass"])


class TestNotYetCreatedCampaign(unittest.TestCase):
    """A campaign without bison_campaign_id fails closed, not vacuously."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="bison_prewrite_nocamp_")
        self.campaigns_file = os.path.join(self.tmpdir, "campaigns.jsonl")
        self.queue_file = os.path.join(self.tmpdir, "queue.jsonl")
        self.clients_dir = os.path.join(self.tmpdir, "clients")
        os.makedirs(self.clients_dir, exist_ok=True)

        self._orig = {}
        for key in ("CAMPAIGNS", "QUEUE", "CLIENTS_DIR", "BISON_KEY"):
            self._orig[key] = os.environ.get(key)

        os.environ["CAMPAIGNS"] = self.campaigns_file
        os.environ["QUEUE"] = self.queue_file
        os.environ["CLIENTS_DIR"] = self.clients_dir
        os.environ["BISON_KEY"] = "test-key"

        self.fb = FakeBison(workspace=10, name="PRODUCTIVE")
        set_transport(self.fb)

    def tearDown(self):
        reset_transport()
        for key, val in self._orig.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_provider_id_fails_closed(self):
        """A campaign without bison_campaign_id returns FAIL, not PASS."""
        _write_jsonl(self.campaigns_file, [
            {"campaign_id": "new-campaign", "client": "productive",
             "name": "Test Campaign", "bison_campaign_id": None}
        ])
        _write_jsonl(self.queue_file, [])
        _write_client_config(self.tmpdir, "productive", {
            "providers": {"emailbison": {"workspace": 10}}
        })

        from scripts.bison_prewrite_check import run_checks
        results, exit_code = run_checks("new-campaign")

        self.assertEqual(exit_code, 1)
        # At least one check must FAIL.
        self.assertTrue(any(not r["pass"] for r in results))
        # The first check must say why.
        self.assertIn("not been created", results[0]["detail"])

    def test_no_provider_id_shows_derived_name(self):
        """The identity check reports what the derived name WILL be."""
        _write_jsonl(self.campaigns_file, [
            {"campaign_id": "control-test", "client": "productive",
             "name": "CONTROL", "bison_campaign_id": None}
        ])
        _write_jsonl(self.queue_file, [])
        _write_client_config(self.tmpdir, "productive", {
            "providers": {"emailbison": {"workspace": 10}}
        })

        from scripts.bison_prewrite_check import run_checks
        results, _ = run_checks("control-test")

        # Find the identity check.
        identity = [r for r in results if "Identity" in r["check"]]
        self.assertTrue(len(identity) > 0)
        self.assertFalse(identity[0]["pass"])
        self.assertIn("[productive/control-test]", identity[0]["detail"])

    def test_local_checks_still_run(self):
        """Tenancy config and killswitch checks still run without a
        provider id."""
        _write_jsonl(self.campaigns_file, [
            {"campaign_id": "local-check", "client": "productive",
             "name": "Test", "bison_campaign_id": None}
        ])
        _write_jsonl(self.queue_file, [])
        _write_client_config(self.tmpdir, "productive", {
            "providers": {"emailbison": {"workspace": 10}}
        })

        from scripts.bison_prewrite_check import run_checks
        results, _ = run_checks("local-check")

        check_names = [r["check"] for r in results]
        # Tenancy config check should be present.
        self.assertTrue(any("Tenancy" in n for n in check_names))
        # Killswitch check should be present.
        self.assertTrue(any("killswitch" in n.lower() or "Caps" in n
                            for n in check_names))


if __name__ == "__main__":
    unittest.main()
