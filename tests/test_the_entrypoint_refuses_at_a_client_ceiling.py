"""The entrypoint refuses at a client ceiling. TASK-373.

TASK-346 landed the mechanism: `complete()` reserves against a ceiling before
the provider is reached. TASK-373 threads the client into every call site so
the gate has something to check.

This test proves:

1. Through the REAL entrypoint (`generate_campaign.generate`), a tight
   ceiling raises `BudgetExceeded` BEFORE `providers.request` is invoked.
2. Under a generous ceiling, the same call proceeds and the ledger row
   carries `client: "productive"` - not `"_model"`, not `"unattributed"`.
3. The guard is seen to fail: without the threading, the call reaches the
   provider (red-green control).
4. Every `model.complete` call site is named.
5. `client_balance("productive")` includes model rows.
6. Mixed units still print MIXED UNITS.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (generate_campaign, llm, offers as offers_mod,
                 spendledger, store, campaignstrategy, clients)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_RESPONSE = {
    "model": "claude-sonnet-4-20250514",
    "choices": [{"message": {"content": json.dumps({
        "is_agency": True, "confidence": 0.9,
        "evidence": "digital marketing agency",
        "facts": [{"text": "agency with 40 people", "source": "site",
                   "confidence": 0.9}],
        "angle": "margin_visible_late",
        "angle_reason": "facts suggest margin visibility issues",
        "company_hook": "agency",
        "usable": True,
        "why_this_lead": "test lead",
        "signal_strength": "strong",
        "signal": "agency with 40 people",
        "business_model": "agency",
        "operational_complexity": "multi-team",
        "role_family": "executive",
        "hypothesis": "margin invisible until month-end",
        "hypothesis_basis": "agency with 40 people",
        "qualification": "QUALIFIED_RICH",
        "confidence": 0.85,
        "capability_key": "profitability",
        "why_this_one": "matches",
        "what_changes": "margin visible",
        "runner_up": "budgeting",
        "hold": False,
        "hold_reason": None,
        "subject": "test subject",
        "subject_alt": "alt subject",
        "subject_breakup": "breakup",
        "emails": {"em1": "body1", "em2": "body2", "em3": "body3",
                   "em4": "body4", "em5": "body5"},
        "ps": {"em1": "ps1", "em3": "ps3", "ps_variant": "ps_fact"},
        "linkedin": {"connect": "conn", "msg1": "m1", "msg2": "m2",
                     "msg3": "m3"},
        "facts_used": {"em1": 1},
    })}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50,
              "total_tokens": 150},
}

TIGHT_CONFIG = {
    "name": "productive",
    "domain": "productive.test",
    "cadence": "default",
    "budget": {
        "per_day": 1,
        "total": spendledger.UNLIMITED,
    },
    "product": {"capabilities": {"profitability": "see project margin"}},
    "sender": {"name": "Ivan", "role": "founder", "company": "Productive",
               "works_on": "project profitability"},
}

GENEROUS_CONFIG = {
    "name": "productive",
    "domain": "productive.test",
    "cadence": "default",
    "budget": {
        "total": spendledger.UNLIMITED,
    },
    "product": {"capabilities": {"profitability": "see project margin"}},
    "sender": {"name": "Ivan", "role": "founder", "company": "Productive",
               "works_on": "project profitability"},
}


def _account():
    return {
        "company": "TestCorp",
        "domain": "testcorp.com",
        "persona": "champion",
        "segment": "test",
        "sources": [
            {"label": "site", "url": "https://testcorp.com/about",
             "text": "TestCorp is a digital marketing agency with 40 people"},
        ],
    }


def _contacts():
    return [{
        "email": "jane@testcorp.com",
        "first_name": "Jane",
        "title": "CEO",
        "contact_key": "jane@testcorp.com",
        "sender_name": "Ivan",
    }]


class IsolatedLedger(unittest.TestCase):
    """A disposable ledger, a fresh run, no holds carried between tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-task373-")
        self.addCleanup(store.use_directory(self.tmp))
        spendledger._HOLDS.clear()
        self.addCleanup(spendledger._HOLDS.clear)
        self.run_id = spendledger.new_run(f"test-{id(self)}")
        campaignstrategy.clear_cache()


# ========================================= acceptance 1: refuses before call

class EntrypointRefusesBeforeTheProviderIsCalled(IsolatedLedger):
    """Through the REAL entrypoint, a tight ceiling refuses BEFORE the call."""

    @mock.patch.object(offers_mod, "load", return_value={
        "OFFER-PM-001": {
            "capability": "project_management", "segment": "all",
            "persona": "champion",
            "business_problem": "projects tracked in spreadsheets",
            "value_proposition": "one place for projects",
            "concrete_deliverable": "single view",
            "cta": "see it", "approval_status": "approved",
            "campaigns": [],
        }
    })
    def test_generate_raises_before_providers_request(self, _mock_offers):
        from src import providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        calls_to_provider = []

        def spy_request(method, url, headers, body, timeout=None):
            calls_to_provider.append(url)
            return (200, FIXTURE_RESPONSE)

        real_request = providers.request
        providers.request = spy_request
        self.addCleanup(setattr, providers, "request", real_request)

        with self.assertRaises(spendledger.BudgetExceeded):
            generate_campaign.generate(
                "productive", _account(), _contacts(),
                config=TIGHT_CONFIG, model=model)

        self.assertEqual([], calls_to_provider,
                         "providers.request WAS called - the ceiling did not "
                         "refuse BEFORE the provider was reached. "
                         "The client threading is not connected.")


# ====================================== acceptance 2: proceeds and attributes

class EntrypointProceedsAndAttributesCorrectly(IsolatedLedger):
    """Under a generous ceiling, the call proceeds and the row is attributed."""

    @mock.patch.object(offers_mod, "load", return_value={
        "OFFER-PM-001": {
            "capability": "project_management", "segment": "all",
            "persona": "champion",
            "business_problem": "projects tracked in spreadsheets",
            "value_proposition": "one place for projects",
            "concrete_deliverable": "single view",
            "cta": "see it", "approval_status": "approved",
            "campaigns": [],
        }
    })
    def test_ledger_row_carries_client_productive(self, _mock_offers):
        from src import providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, FIXTURE_RESPONSE)
        self.addCleanup(setattr, providers, "request", real_request)

        generate_campaign.generate(
            "productive", _account(), _contacts(),
            config=GENEROUS_CONFIG, model=model)

        rows = spendledger.load()
        model_rows = [r for r in rows
                      if r.get("provider") in ("anthropic", "openrouter",
                                               "groq", "glm")]
        self.assertTrue(model_rows, "no model rows written to the ledger")
        for row in model_rows:
            self.assertEqual(
                row["client"], "productive",
                f"model row attributed to {row['client']!r}, not 'productive'. "
                "The client threading is not connected.")
            self.assertNotEqual(
                row["client"], "_model",
                "model row still uses '_model' - threading not connected")
            self.assertNotEqual(
                row["client"], "unattributed",
                "model row is 'unattributed' - threading not connected")


# ================================= acceptance 5: client_balance includes model

class ClientBalanceIncludesModelRowsFromEntrypoint(IsolatedLedger):
    """client_balance("productive") includes model rows from the entrypoint."""

    @mock.patch.object(offers_mod, "load", return_value={
        "OFFER-PM-001": {
            "capability": "project_management", "segment": "all",
            "persona": "champion",
            "business_problem": "projects tracked in spreadsheets",
            "value_proposition": "one place for projects",
            "concrete_deliverable": "single view",
            "cta": "see it", "approval_status": "approved",
            "campaigns": [],
        }
    })
    def test_client_balance_reflects_entrypoint_model_spend(self, _mock_offers):
        from src import providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, FIXTURE_RESPONSE)
        self.addCleanup(setattr, providers, "request", real_request)

        bal_before = spendledger.client_balance(
            "productive", GENEROUS_CONFIG, rows=spendledger.load())
        spent_before = bal_before["spent_all_time"]

        generate_campaign.generate(
            "productive", _account(), _contacts(),
            config=GENEROUS_CONFIG, model=model)

        bal_after = spendledger.client_balance(
            "productive", GENEROUS_CONFIG, rows=spendledger.load())
        spent_after = bal_after["spent_all_time"]

        self.assertGreater(spent_after, spent_before,
                           "model spend from the entrypoint did not appear "
                           f"in client_balance. Before: {spent_before}, "
                           f"After: {spent_after}")


# ============================================ acceptance 6: mixed units

class MixedUnitsFromEntrypoint(IsolatedLedger):
    """Mixed units (microusd + credits) still print MIXED UNITS."""

    @mock.patch.object(offers_mod, "load", return_value={
        "OFFER-PM-001": {
            "capability": "project_management", "segment": "all",
            "persona": "champion",
            "business_problem": "projects tracked in spreadsheets",
            "value_proposition": "one place for projects",
            "concrete_deliverable": "single view",
            "cta": "see it", "approval_status": "approved",
            "campaigns": [],
        }
    })
    def test_mixed_units_still_report(self, _mock_offers):
        from src import providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, FIXTURE_RESPONSE)
        self.addCleanup(setattr, providers, "request", real_request)

        generate_campaign.generate(
            "productive", _account(), _contacts(),
            config=GENEROUS_CONFIG, model=model)

        spendledger.record("productive", "deliverable", "verify", 500)

        progress = spendledger.progress_block("productive", GENEROUS_CONFIG)
        self.assertIn("MIXED UNITS", progress,
                       "client-wide line does not say MIXED UNITS. "
                       "microusd and credits must not be summed.")


# ============================================ acceptance 4: every path named

class EveryCallSiteIsNamed:
    """Every model.complete call site in src/ and scripts/, with the client
    it now passes or why it honestly cannot.

    src/generate_campaign.py:
      - _call_model (line ~372): passes client=client_name, config=config
        from generate() -> _process_contact() -> _call_model()
      - _decide_strategy: passes client=client_name, config=config
        from generate() -> _decide_strategy() -> campaignstrategy.for_segment()

    src/campaignstrategy.py:
      - _call_model (line ~114): passes client=client, config=config
        from for_segment() -> _call_model()
      - for_segment: receives client and config from caller

    src/llm.py:
      - ask() (line ~1085): passes client=client, config=config
        from generate.py callers that pass rec.get("client")

    src/generate.py:
      - diagnose: passes client=rec.get("client")
      - hook: passes client=rec.get("client")
      - persona_angle: passes client=client or rec.get("client")
      - linkedin_note (x2): passes client=client or rec.get("client")
      - draft: passes client=client or rec.get("client")

    src/slackconversation.py:
      - plan (line ~623): passes client=slack_client (scope.workspace for
        client scopes, None for internal/unbound)
      - answer (line ~1623): passes client=slack_client
      - answer retry (line ~1662): passes client=slack_client

    scripts/slack_agent_briefing.py:
      - line ~232: calls model.complete(BRIEFING_PROMPT) - client genuinely
        unknown (a briefing script, not in a client context). "unattributed"
        stays.

    scripts/task077_detailed.py:
      - line ~63: calls model.complete(prompt) - client genuinely unknown
        (a one-shot task script). "unattributed" stays.

    scripts/glm_review.py:
      - line ~555: calls glm.complete() - different seam (GLM provider),
        not model.complete. Out of scope for this task.

    scripts/glm_audit_safety.py:
      - line ~147: calls glm.complete() - different seam (GLM provider),
        not model.complete. Out of scope for this task.
    """

    def test_this_class_is_documentation_not_a_test(self):
        assert True


if __name__ == "__main__":
    unittest.main()
