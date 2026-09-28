"""The entrypoint loads its skills at runtime, not by import alone.

TASK-375. TASK-369 built the entrypoint and the five skills, but the
entrypoint called the raw copyprompts/copystages constants directly,
bypassing the skill layer. This test proves the skill layer is connected:

1. Monkeypatch a skill's procedure text and prove generate()'s model calls
   carry the patched text — a test that only imports the skill and calls it
   directly proves the skill works, not that the entrypoint uses it.
2. Every one of the five skills has at least one skills.load() call inside
   src/generate_campaign.py.
"""
import json
import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (generate_campaign, llm, offers as offers_mod,
                 campaignstrategy, skills)


# ---------------------------------------------------------------------------
# A recording model that returns valid JSON for every stage.
# ---------------------------------------------------------------------------

class _RecordingModel:
    """Records every prompt; returns stage-appropriate JSON."""

    name = "recording-test"

    def __init__(self):
        self.calls = []

    def complete(self, prompt, temperature=0, client=None, config=None):
        self.calls.append(prompt)
        lower = prompt.lower()

        if "services agency" in lower and "is this company" in lower:
            return json.dumps({
                "is_agency": True, "confidence": 0.9,
                "evidence": "digital marketing agency",
            })

        if "extract verifiable facts" in lower:
            return json.dumps({
                "facts": [
                    {"text": "TestCorp is a digital marketing agency",
                     "quote": "digital marketing agency",
                     "source_index": 1, "kind": "site", "confidence": 0.9},
                    {"text": "TestCorp runs client projects on retainer",
                     "quote": "client projects on retainer",
                     "source_index": 2, "kind": "site", "confidence": 0.9},
                    {"text": "TestCorp opened a London office in 2024",
                     "quote": "London office in 2024",
                     "source_index": 1, "kind": "post", "confidence": 0.85},
                ],
                "angle": "margin_visible_late",
                "company_hook": "TestCorp is a digital marketing agency",
                "usable": True,
            })

        if "propose one operational problem" in lower:
            return json.dumps({
                "signal_strength": "strong",
                "signal": "marketing agency",
                "business_model": "agency running client projects",
                "operational_complexity": "multi-team delivery",
                "role_family": "executive",
                "hypothesis": "margin invisible until month-end",
                "hypothesis_basis": "client projects on retainer",
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
                    "em1": {"objective": "open", "angle": "margin",
                            "proof": "research", "cta": "question"},
                },
                "linkedin": {
                    "connect": {"objective": "relevance", "angle": "fact",
                                "cta": "none"},
                },
                "dropped": [],
                "repetition_check": "ok",
            })

        if "write cold outreach" in lower:
            return json.dumps({
                "hold": False, "hold_reason": None,
                "subject": "your agency visibility",
                "subject_alt": "project margin timing",
                "subject_breakup": "closing the loop",
                "emails": {
                    "em1": "noticed your agency. quick question?",
                    "em2": "the pattern extends.",
                    "em3": "here is how it works.",
                    "em4": "one benchmark.",
                    "em5": "short close.",
                },
                "ps": {"em1": "also noticed growth.", "em3": "reporting."},
                "ps_variant": "ps_fact",
                "linkedin": {
                    "connect": "saw your work",
                    "msg1": "hi, I am with Productive. quick question?",
                    "msg2": "the profitability module.",
                    "msg3": "no pressure.",
                },
                "facts_used": {"em1": 1, "ps_em1": 2},
                "confidence": 0.85,
            })

        return json.dumps({"error": "unrecognised stage"})


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


def _account():
    return {
        "company": "TestCorp",
        "domain": "testcorp.test",
        "persona": "champion",
        "segment": "test",
        "sources": [
            {"label": "site", "url": "https://testcorp.test/about",
             "text": "TestCorp is a digital marketing agency with 40 people"},
            {"label": "post", "url": "https://linkedin.com/testcorp",
             "text": "TestCorp runs client projects on retainer"},
        ],
    }


def _contacts():
    return [{
        "email": "jane@testcorp.test",
        "first_name": "Jane",
        "last_name": "Doe",
        "title": "CEO",
        "contact_key": "jane@testcorp.test",
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
                "profitability": "see project margin while it runs",
            },
        },
        "sender": {"name": "Ivan", "role": "founder",
                   "company": "Productive",
                   "works_on": "project profitability for agencies"},
    }


# ---------------------------------------------------------------------------
# Tests: downstream effect, not import
# ---------------------------------------------------------------------------

class TestSkillProcedureFlowsToModel(unittest.TestCase):
    """Monkeypatch a skill's procedure and prove generate() carries it.

    This is the acceptance criterion: a test that only imports the skill
    and calls it directly proves the skill works, not that the entrypoint
    uses it. We prove the entrypoint uses it by changing the skill's
    procedure and observing the model's prompt change.
    """

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_signal_verification_procedure_reaches_the_model(self, _mo):
        """Patch signal_verification's procedure; prove the model sees it."""
        campaignstrategy.clear_cache()
        skill = skills.load("signal_verification")
        original_procedure = skill.procedure

        sentinel = "SIGNAL_VERIFICATION_SENTINEL_7f3a"
        patched_procedure = sentinel + "\n" + original_procedure

        object.__setattr__(skill, "procedure", patched_procedure)
        try:
            model = _RecordingModel()
            generate_campaign.generate(
                _client_config(), _account(), _contacts(), model=model)

            sentinel_seen = any(
                sentinel in call for call in model.calls
            )
            self.assertTrue(
                sentinel_seen,
                "the patched signal_verification procedure did not reach "
                "the model — the entrypoint is not using the skill"
            )
        finally:
            object.__setattr__(skill, "procedure", original_procedure)

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_cold_email_writing_procedure_reaches_the_model(self, _mo):
        """Patch cold_email_writing's procedure; prove the model sees it."""
        campaignstrategy.clear_cache()
        skill = skills.load("cold_email_writing")
        original_procedure = skill.procedure

        sentinel = "COLD_EMAIL_SENTINEL_9b2e"
        patched_procedure = sentinel + "\n" + original_procedure

        object.__setattr__(skill, "procedure", patched_procedure)
        try:
            model = _RecordingModel()
            generate_campaign.generate(
                _client_config(), _account(), _contacts(), model=model)

            sentinel_seen = any(
                sentinel in call for call in model.calls
            )
            self.assertTrue(
                sentinel_seen,
                "the patched cold_email_writing procedure did not reach "
                "the model — the entrypoint is not using the skill"
            )
        finally:
            object.__setattr__(skill, "procedure", original_procedure)

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_campaign_strategy_procedure_reaches_the_model(self, _mo):
        """Patch campaign_strategy's procedure; prove the model sees it."""
        campaignstrategy.clear_cache()
        skill = skills.load("campaign_strategy")
        original_procedure = skill.procedure

        sentinel = "STRATEGY_SENTINEL_4d1c"
        patched_procedure = sentinel + "\n" + original_procedure

        object.__setattr__(skill, "procedure", patched_procedure)
        try:
            model = _RecordingModel()
            generate_campaign.generate(
                _client_config(), _account(), _contacts(), model=model)

            sentinel_seen = any(
                sentinel in call for call in model.calls
            )
            self.assertTrue(
                sentinel_seen,
                "the patched campaign_strategy procedure did not reach "
                "the model — the entrypoint is not using the skill"
            )
        finally:
            object.__setattr__(skill, "procedure", original_procedure)

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_account_research_procedure_reaches_the_model(self, _mo):
        """Patch account_research's procedure; prove the model sees it."""
        campaignstrategy.clear_cache()
        skill = skills.load("account_research")
        original_procedure = skill.procedure

        sentinel = "ACCOUNT_RESEARCH_SENTINEL_6e8f"
        patched_procedure = sentinel + "\n" + original_procedure

        object.__setattr__(skill, "procedure", patched_procedure)
        try:
            model = _RecordingModel()
            generate_campaign.generate(
                _client_config(), _account(), _contacts(), model=model)

            sentinel_seen = any(
                sentinel in call for call in model.calls
            )
            self.assertTrue(
                sentinel_seen,
                "the patched account_research procedure did not reach "
                "the model — the entrypoint is not using the skill"
            )
        finally:
            object.__setattr__(skill, "procedure", original_procedure)

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_linkedin_writing_loaded_and_shares_writer_prompt(self, _mo):
        """linkedin_writing is loaded and shares WRITER_SYSTEM with
        cold_email_writing. Both skills wrap the same prompt; the entrypoint
        loads both so neither is disconnected. The monkeypatch test for
        cold_email_writing proves the shared prompt reaches the model."""
        campaignstrategy.clear_cache()
        email_skill = skills.load("cold_email_writing")
        linkedin_skill = skills.load("linkedin_writing")

        self.assertEqual(
            email_skill.procedure, linkedin_skill.procedure,
            "cold_email_writing and linkedin_writing should share "
            "WRITER_SYSTEM"
        )

        model = _RecordingModel()
        generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model)

        writer_calls = [
            c for c in model.calls if "write cold outreach" in c.lower()
        ]
        self.assertTrue(
            writer_calls,
            "no writer call found — the entrypoint did not call the writer"
        )


class TestAllFiveSkillsHaveCallers(unittest.TestCase):
    """Acceptance #2: every skill has at least one caller in generate_campaign."""

    def test_all_five_skills_loaded_in_entrypoint(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src",
                            "generate_campaign.py")
        with open(path) as f:
            source = f.read()

        expected_skills = [
            "signal_verification",
            "account_research",
            "campaign_strategy",
            "cold_email_writing",
            "linkedin_writing",
        ]
        for skill_name in expected_skills:
            pattern = 'skills.load("%s")' % skill_name
            self.assertIn(
                pattern, source,
                "skill %r has no caller in generate_campaign.py — "
                "expected %s" % (skill_name, pattern)
            )


if __name__ == "__main__":
    unittest.main()
