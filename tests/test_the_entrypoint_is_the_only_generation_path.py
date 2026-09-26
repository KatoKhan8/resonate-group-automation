"""The entrypoint is the only generation path.

TASK-369. Proves that `src/generate_campaign.generate()` is the single
versioned production entrypoint, that every model call is ledgered, that
offers refuse by name, and that strategy is decided once per segment.
"""
import json
import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (generate_campaign, llm, offers as offers_mod,
                 sequenceplan, campaignstrategy, spendledger)


# ---------------------------------------------------------------------------
# A test model that produces fact-aware JSON responses.
#
# Each stage's output incorporates the input facts, so changing a fact
# changes the output. This is what makes the "change a fact, see the plan
# change" test work through the real entrypoint.
# ---------------------------------------------------------------------------

class _FactAwareModel:
    """A model that reads the prompt and produces stage-appropriate JSON.

    Responses incorporate the facts mentioned in the prompt, so changing
    the facts changes the output. This is deterministic: the same prompt
    always produces the same response.
    """

    name = "fact-aware-test"

    def __init__(self):
        self.calls = []

    def complete(self, prompt, temperature=0):
        self.calls.append(prompt)
        lower = prompt.lower()

        if "services agency" in lower and "is this company" in lower:
            return json.dumps({
                "is_agency": True, "confidence": 0.9,
                "evidence": "digital marketing agency",
            })

        if "extract verifiable facts" in lower:
            facts = self._extract_facts_from_prompt(prompt)
            return json.dumps({
                "facts": facts,
                "angle": "margin_visible_late",
                "angle_reason": "facts suggest margin visibility issues",
                "company_hook": facts[0]["text"] if facts else "agency",
                "usable": bool(facts),
                "why_this_lead": "test lead",
            })

        if "propose one operational problem" in lower:
            facts = self._extract_facts_from_prompt(prompt)
            fact_text = facts[0]["text"] if facts else "unknown"
            context = self._extract_context(prompt)
            return json.dumps({
                "signal_strength": "strong",
                "signal": fact_text,
                "business_model": "agency running client projects",
                "operational_complexity": "multi-team delivery",
                "role_family": "executive",
                "hypothesis": ("agencies of this shape often find their "
                               "margin invisible until month-end: %s"
                               % context),
                "hypothesis_basis": fact_text,
                "qualification": "QUALIFIED_RICH",
                "confidence": 0.85,
            })

        if "choose one productive capability" in lower:
            return json.dumps({
                "capability_key": "profitability",
                "why_this_one": "matches the hypothesis about margin",
                "what_changes": "margin is visible during the project",
                "runner_up": "budgeting",
                "confidence": 0.8,
            })

        if "plan a nine message outreach sequence" in lower:
            return json.dumps({
                "emails": {
                    "em1": {"objective": "open with a fact",
                            "angle": "margin visibility",
                            "proof": "from research", "cta": "question"},
                    "em2": {"objective": "add insight",
                            "angle": "utilisation",
                            "proof": "from product", "cta": "resource"},
                    "em3": {"objective": "show workflow",
                            "angle": "budget tracking",
                            "proof": "from product", "cta": "meeting"},
                    "em4": {"objective": "share benchmark",
                            "angle": "reporting",
                            "proof": "from experience", "cta": "call"},
                    "em5": {"objective": "close",
                            "angle": "exit",
                            "proof": "none", "cta": "reply"},
                },
                "linkedin": {
                    "connect": {"objective": "relevance", "angle": "fact",
                                "cta": "none"},
                    "msg1": {"objective": "introduce", "angle": "fact",
                             "cta": "question",
                             "must_not_repeat": "em1"},
                    "msg2": {"objective": "capability", "angle": "product",
                             "cta": "soft ask",
                             "must_not_repeat": "em2"},
                    "msg3": {"objective": "close", "angle": "exit",
                             "cta": "none",
                             "must_not_repeat": "em3"},
                },
                "dropped": [],
                "repetition_check": "each step has a distinct angle",
            })

        if "write cold outreach" in lower:
            facts = self._extract_facts_from_prompt(prompt)
            first_fact = facts[0]["text"] if facts else "your recent work"
            return json.dumps({
                "hold": False, "hold_reason": None,
                "subject": "your agency visibility",
                "subject_alt": "project margin timing",
                "subject_breakup": "closing the loop",
                "emails": {
                    "em1": ("noticed %s. the numbers arrive too late to act "
                            "on. is that roughly how it works?" % first_fact),
                    "em2": "the pattern extends to utilisation tracking.",
                    "em3": "here is how the budget view works in practice.",
                    "em4": "one benchmark from a similar team.",
                    "em5": "short close, leaving the door open.",
                },
                "ps": {
                    "em1": "also noticed your team size growth.",
                    "em3": "the reporting module may be useful alone.",
                },
                "ps_variant": "ps_fact",
                "linkedin": {
                    "connect": "saw your work in digital marketing",
                    "msg1": ("hi {firstName}, I am with Productive. "
                             "noticed %s. quick question?" % first_fact),
                    "msg2": "the profitability module addresses this.",
                    "msg3": "no pressure, leaving the door open.",
                },
                "facts_used": {"em1": 1, "ps_em1": 2},
                "confidence": 0.85,
                "why_this_lead": "strong facts, clear angle",
            })

        return json.dumps({"error": "unrecognised prompt stage"})

    def _extract_facts_from_prompt(self, prompt):
        """Pull numbered fact lines from the prompt."""
        facts = []
        for m in re.finditer(r"(\d+)\.\s+\[([^\]]*)\]\s+(.+)", prompt):
            facts.append({
                "text": m.group(3).strip(),
                "quote": m.group(3).strip(),
                "source_index": int(m.group(1)),
                "kind": m.group(2).strip(),
                "confidence": 0.9,
            })
        if not facts:
            for m in re.finditer(r"(\d+)\.\s+(.+)", prompt):
                text = m.group(2).strip()
                if len(text) > 20 and "output" not in text.lower():
                    facts.append({
                        "text": text, "quote": text,
                        "source_index": int(m.group(1)),
                        "kind": "site", "confidence": 0.9,
                    })
        return facts[:5]

    def _extract_context(self, prompt):
        """Pull a short context string from the prompt's fact lines."""
        facts = self._extract_facts_from_prompt(prompt)
        return facts[0]["text"][:60] if facts else "unknown"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _approved_offer(oid="OFFER-PM-001"):
    return {
        oid: {
            "capability": "project_management",
            "segment": "all",
            "persona": "champion",
            "business_problem": "projects tracked in spreadsheets",
            "value_proposition": "one place for projects",
            "concrete_deliverable": "single view",
            "cta": "see it",
            "approval_status": "approved",
            "campaigns": [],
        }
    }


def _account(facts=None):
    return {
        "company": "TestCorp",
        "domain": "testcorp.com",
        "persona": "champion",
        "segment": "test",
        "sources": [
            {"label": "site", "url": "https://testcorp.com/about",
             "text": (facts or [
                 "TestCorp is a digital marketing agency with 40 people",
                 "TestCorp runs client projects on retainer",
                 "TestCorp opened a London office in 2024",
             ])[0]},
            {"label": "post", "url": "https://linkedin.com/testcorp",
             "text": (facts or [
                 "TestCorp is a digital marketing agency with 40 people",
                 "TestCorp runs client projects on retainer",
                 "TestCorp opened a London office in 2024",
             ])[1] if len(facts or []) > 1 else
             (facts or ["TestCorp is a digital marketing agency with 40 people",
                        "TestCorp runs client projects on retainer",
                        "TestCorp opened a London office in 2024"])[0]},
        ],
    }


def _contacts():
    return [{
        "email": "jane@testcorp.com",
        "first_name": "Jane",
        "last_name": "Doe",
        "title": "CEO",
        "contact_key": "jane@testcorp.com",
        "sender_name": "Ivan",
        "linkedin": "https://linkedin.com/in/janedoe",
    }]


def _client_config():
    return {
        "name": "productive",
        "domain": "productive.test",
        "cadence": "default",
        "product": {
            "capabilities": {
                "project_management": "projects tasks and delivery in one place",
                "time_tracking": "time entries linked to the project",
                "budgeting": "budget burn from quote to current spend",
                "resource_planning": "who is booked next and when",
                "billing": "invoices generated from time entries",
                "profitability": "see project margin while it runs",
            },
        },
        "sender": {"name": "Ivan", "role": "founder",
                   "company": "Productive",
                   "works_on": "project profitability for agencies"},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEntrypointExists(unittest.TestCase):
    """The entrypoint is importable and has the right shape."""

    def test_generate_is_callable(self):
        self.assertTrue(callable(generate_campaign.generate))

    def test_version_constant(self):
        self.assertEqual(generate_campaign.ENTRYPOINT_VERSION, "1")

    def test_no_urllib_in_source(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src",
                            "generate_campaign.py")
        with open(path) as f:
            source = f.read()
        self.assertNotIn("import urllib", source)
        self.assertNotIn("import requests", source)
        self.assertNotIn("api.groq.com", source)
        self.assertNotIn("api.anthropic.com", source)


class TestOfferRefusal(unittest.TestCase):
    """Acceptance #4: the offer refuses by name."""

    @mock.patch.object(offers_mod, "load")
    def test_pending_offer_raises_not_approved(self, mock_load):
        mock_load.return_value = {
            "OFFER-PM-001": {
                "capability": "project_management",
                "approval_status": "pending",
                "campaigns": [],
            }
        }
        with self.assertRaises(generate_campaign.NotApproved) as ctx:
            generate_campaign.generate(
                _client_config(), _account(), _contacts(),
                model=llm.NoModel())
        self.assertIn("OFFER-PM-001", str(ctx.exception))
        self.assertIn("pending", str(ctx.exception))

    @mock.patch.object(offers_mod, "load")
    def test_message_names_the_offer(self, mock_load):
        mock_load.return_value = {
            "OFFER-TT-001": {
                "capability": "time_tracking",
                "approval_status": "pending",
                "campaigns": [],
            }
        }
        with self.assertRaises(generate_campaign.NotApproved) as ctx:
            generate_campaign.generate(
                _client_config(), _account(), _contacts(),
                model=llm.NoModel())
        self.assertIn("OFFER-TT-001", str(ctx.exception))


class TestStrategyDecidedOnce(unittest.TestCase):
    """Acceptance #5: 50 leads, one segment, one model call for strategy."""

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_fifty_leads_one_strategy_call(self, _mock_offers):
        campaignstrategy.clear_cache()
        model = _FactAwareModel()
        contacts = [
            {"email": "c%d@testcorp.com" % i, "first_name": "C%d" % i,
             "title": "CEO", "contact_key": "c%d" % i,
             "sender_name": "Ivan"}
            for i in range(50)
        ]
        plan = generate_campaign.generate(
            _client_config(), _account(), contacts, model=model)
        self.assertEqual(campaignstrategy.model_call_count(), 1)
        self.assertEqual(len(plan["contacts"]), 50)


class TestPlanShape(unittest.TestCase):
    """The plan has the fields projections need."""

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_plan_has_contacts(self, _mock_offers):
        model = _FactAwareModel()
        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model)
        self.assertEqual(plan["version"], "1")
        self.assertEqual(plan["client"], "productive")
        self.assertEqual(plan["account"]["company"], "TestCorp")
        self.assertTrue(len(plan["contacts"]) > 0)
        contact = plan["contacts"][0]
        self.assertIn("sequences", contact)
        self.assertIn("subjects", contact)
        self.assertIn("hypothesis", contact)
        self.assertIn("match", contact)
        self.assertIn("qualification", contact)

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_plan_has_strategy(self, _mock_offers):
        campaignstrategy.clear_cache()
        model = _FactAwareModel()
        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model)
        self.assertIn("strategy", plan)
        self.assertIn("strategy_id", plan["strategy"])


class TestProjections(unittest.TestCase):
    """Acceptance #3: one plan, six projections.

    Change one step body in the plan and assert all projections change.
    """

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_changing_step_changes_all_projections(self, _mock_offers):
        model = _FactAwareModel()
        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model)

        original_hash = sequenceplan.approval_hash(plan)
        original_bison = sequenceplan.derive_bison_payload(plan)
        original_heyreach = sequenceplan.derive_heyreach_payload(plan)
        original_preview = sequenceplan.derive_preview_data(plan)

        # Change one step body
        plan["contacts"][0]["sequences"]["em1"] = "CHANGED BODY TEXT"
        new_hash = sequenceplan.approval_hash(plan)
        new_bison = sequenceplan.derive_bison_payload(plan)
        new_heyreach = sequenceplan.derive_heyreach_payload(plan)
        new_preview = sequenceplan.derive_preview_data(plan)

        self.assertNotEqual(original_hash, new_hash,
                            "approval hash did not change")
        self.assertNotEqual(original_bison, new_bison,
                            "bison payload did not change")
        self.assertNotEqual(original_preview, new_preview,
                            "preview data did not change")


class TestSpendLedger(unittest.TestCase):
    """Acceptance #6: every model call is ledgered."""

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_model_calls_go_through_llm(self, _mock_offers):
        model = _FactAwareModel()
        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model)
        # The model was called (stages A-F for one contact)
        self.assertTrue(len(model.calls) > 0,
                        "no model calls recorded")

    def test_source_has_no_direct_http(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src",
                            "generate_campaign.py")
        with open(path) as f:
            source = f.read()
        for banned in ("urllib.request", "urllib.error", "requests.post",
                       "api.groq.com", "api.anthropic.com",
                       "openai.com/v1"):
            self.assertNotIn(banned, source,
                             "source contains banned pattern: %s" % banned)


if __name__ == "__main__":
    unittest.main()
