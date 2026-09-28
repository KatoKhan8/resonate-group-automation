"""Changing valid upstream information changes the downstream output.

TASK-369, acceptance #1 and #2. This is THE test that closes the task.

Directive section 4: "Changing valid upstream information changes the
intended downstream production context/output through the real production
entrypoint."

Test 1 (positive): change one approved Second Brain fact, call generate()
through the real entrypoint, assert the SequencePlan differs in the place
that fact belongs. Then change it back and assert the output returns.

Test 2 (negative): change a fact that is NOT approved (INFERRED), assert
the prospect-facing output does NOT change. If both changes move the output,
the pipeline is passing unapproved material to prospects.
"""
import json
import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (generate_campaign, llm, offers as offers_mod,
                 sequenceplan, campaignstrategy, secondbrain)


# ---------------------------------------------------------------------------
# The same fact-aware model from the entrypoint test.
# ---------------------------------------------------------------------------

class _FactAwareModel:
    """Produces stage-appropriate JSON, incorporating input facts."""

    name = "fact-aware-test"

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
            # The extract prompt uses ### [N] label format for source blocks
            sources = []
            for m in re.finditer(r"###\s+\[(\d+)\]\s+(\w+)\s*\n(.+)", prompt):
                sources.append({
                    "text": m.group(3).strip()[:120],
                    "quote": m.group(3).strip()[:120],
                    "source_index": int(m.group(1)),
                    "kind": m.group(2),
                    "confidence": 0.9,
                })
            if not sources:
                sources = [{"text": "TestCorp is a digital marketing agency",
                            "quote": "TestCorp", "source_index": 1,
                            "kind": "site", "confidence": 0.9}]
            return json.dumps({
                "facts": sources,
                "angle": "margin_visible_late",
                "angle_reason": "facts suggest margin issues",
                "company_hook": sources[0]["text"],
                "usable": bool(sources),
                "why_this_lead": "test",
            })

        if "propose one operational problem" in lower:
            facts = self._extract_facts(prompt)
            context = self._extract_br_context(prompt)
            fact_text = facts[0]["text"] if facts else "unknown"
            return json.dumps({
                "signal_strength": "strong",
                "signal": fact_text,
                "business_model": "agency",
                "operational_complexity": "multi-team",
                "role_family": "executive",
                "hypothesis": ("margin invisible until month-end, "
                               "context: %s, basis: %s"
                               % (context, fact_text)),
                "hypothesis_basis": fact_text,
                "qualification": "QUALIFIED_RICH",
                "confidence": 0.85,
            })

        if "choose one productive capability" in lower:
            # Extract the hypothesis from the prompt to make the capability
            # depend on it. The hypothesis flows: SB fact -> hypothesis ->
            # match -> capability sentence -> writer output.
            hyp_text = ""
            for m in re.finditer(r"Hypothesis:\s*(.+?)(?:\n|$)", prompt):
                hyp_text = m.group(1).strip()[:80]
                break
            return json.dumps({
                "capability_key": "profitability",
                "why_this_one": "matches: %s" % hyp_text[:40],
                "what_changes": "margin visible given: %s" % hyp_text[:40],
                "runner_up": "budgeting",
                "confidence": 0.8,
            })

        if "plan a nine message" in lower:
            return json.dumps({
                "emails": {
                    "em1": {"objective": "open", "angle": "margin",
                            "proof": "research", "cta": "question"},
                    "em2": {"objective": "insight", "angle": "utilisation",
                            "proof": "product", "cta": "resource"},
                    "em3": {"objective": "workflow", "angle": "budget",
                            "proof": "product", "cta": "meeting"},
                    "em4": {"objective": "benchmark", "angle": "reporting",
                            "proof": "experience", "cta": "call"},
                    "em5": {"objective": "close", "angle": "exit",
                            "proof": "none", "cta": "reply"},
                },
                "linkedin": {
                    "connect": {"objective": "relevance", "angle": "fact",
                                "cta": "none"},
                    "msg1": {"objective": "intro", "angle": "fact",
                             "cta": "question", "must_not_repeat": "em1"},
                    "msg2": {"objective": "capability", "angle": "product",
                             "cta": "ask", "must_not_repeat": "em2"},
                    "msg3": {"objective": "close", "angle": "exit",
                             "cta": "none", "must_not_repeat": "em3"},
                },
                "dropped": [],
                "repetition_check": "distinct angles",
            })

        if "write cold outreach" in lower:
            facts = self._extract_facts(prompt)
            first_fact = facts[0]["text"] if facts else "your work"
            # Extract the hypothesis from the plan JSON in the prompt.
            # The plan includes the hypothesis from the match stage.
            hyp_in_plan = ""
            plan_match = re.search(r'"hypothesis":\s*"([^"]+)"', prompt)
            if plan_match:
                hyp_in_plan = plan_match.group(1)[:200]
            what_changes = ""
            wc_match = re.search(r'"what_changes":\s*"([^"]+)"', prompt)
            if wc_match:
                what_changes = wc_match.group(1)[:200]
            return json.dumps({
                "hold": False, "hold_reason": None,
                "subject": "your agency visibility",
                "subject_alt": "project margin timing",
                # NOT "closing the loop", AND NOT BECAUSE THE PHRASE IS WRONG.
                #
                # `copylint.FINALITY_RE` matches "closing the loop", and
                # TASK-378 pools all five subjects into `non_final`:
                #
                #     non_final = bodies[:-1] + [subjects, extra]
                #
                # The last BODY is exempt - it IS the last step - but the last
                # SUBJECT is not, because the subjects go in whole. So a
                # finality phrase in em5's subject is reported as
                # `finality_before_last_step` even though em5 IS the last step.
                # Measured directly, with both controls: finality in the last
                # body is exempt, finality in the last subject REFUSES, an
                # early subject correctly fires, and a clean lead passes.
                #
                # That is a PRE-EXISTING false positive in `copylint`, not
                # something this branch caused. It was invisible on master
                # because nothing read `check_batch`'s verdict; TASK-400 makes
                # the verdict act, so it surfaced here - the same shape as the
                # two blockers handoff section 9 records, a pre-existing problem
                # that became visible once a gate could run. `copyprompts` ASKS
                # the model for exactly this ("em5 ... breakup, subject C -
                # short, three or four words"), so it will refuse real leads
                # too. Reported as its own finding and NOT fixed here, because
                # fixing it means changing a lint rule and this branch may not.
                #
                # This fixture therefore uses a short breakup subject asserting
                # no finality, which also matches `copyprompts`' own instruction
                # (short, no hook, no question). The test is about a verified
                # fact reaching the copy; the subject is not what it is about,
                # and pinning it keeps a refusal it is not testing out of the
                # way. Falsifiability re-proved after the change: making em1
                # ignore the fact fails the test, with both sides non-empty.
                "subject_breakup": "the margin question",
                # REAL SENTENCES, BECAUSE THE GATES NOW READ THEM.
                # TASK-400 rework 3 makes `copylint`'s verdict act on the
                # writer's output: a refused set is regenerated and then refused
                # outright, which emptied `sequences` and made both sides of this
                # comparison the empty string. The stubs here were refused for
                # `empty_sentence` and `unrendered_variable` - `{firstName}` is
                # exactly the merge field that rule exists to catch, and shipping
                # it is launch blocker 6. em1 still carries the fact, the
                # hypothesis and what_changes, which is what makes this a real
                # observation of control 4 rather than a coincidence.
                "emails": {
                    "em1": ("The reason I am writing: %s. The pattern I would "
                            "expect from that is %s, and what would change is "
                            "%s. Is any of that actually true where you sit, or "
                            "is the reporting side already solved?"
                            % (first_fact, hyp_in_plan, what_changes)),
                    "em2": (
                        "Utilisation follows the same pattern as the margin "
                        "question. Most teams find out who was busy after the "
                        "month has closed rather than while there is still time "
                        "to move somebody. How do you see it today?"),
                    "em3": (
                        "The budget view works on committed hours rather than "
                        "invoiced ones, so an overrun shows up in the week it "
                        "starts. What would have to be true for that to be "
                        "useful rather than one more report?"),
                    "em4": (
                        "One observation from teams of a similar shape. The "
                        "ones that see margin early are not working harder at "
                        "reporting, they have stopped waiting for the close. "
                        "Which decision would you want to take sooner?"),
                    "em5": (
                        "If none of this is a priority, say so and I will close "
                        "the file. If it is, the one thing worth knowing is "
                        "where your current answer comes from and how much "
                        "reconstruction sits behind it."),
                },
                "ps": {
                    "em1": "Asked because the headcount is on your own site.",
                    "em3": "The reporting side is useful on its own.",
                },
                "ps_variant": "ps_fact",
                "linkedin": {
                    "connect": ("Reading about how the team is set up. No "
                                "pitch, happy to follow along."),
                    "msg1": ("The question I keep asking is when project margin "
                             "becomes visible. While the work runs, or once the "
                             "invoice is drafted?"),
                    "msg2": ("The profitability module addresses that side of "
                             "it, and I wrote by email about the same thing."),
                    "msg3": ("No pressure at all. If this is not a priority I "
                             "will leave it with you."),
                },
                "facts_used": {"em1": 1},
                "confidence": 0.85,
                "why_this_lead": "strong facts",
            })

        return json.dumps({"error": "unknown stage"})

    def _extract_facts(self, prompt):
        # Find the facts section. The hypothesis prompt says "Verified facts:"
        # and the writer prompt says "Facts you may use:". Only extract facts
        # from that section, not from numbered lists in the system prompt.
        facts_start = len(prompt)
        for marker in ("Facts you may use:", "Verified facts:"):
            idx = prompt.find(marker)
            if idx != -1 and idx < facts_start:
                facts_start = idx

        facts_section = prompt[facts_start:]
        facts = []
        for m in re.finditer(r"(\d+)\.\s+\[([^\]]*)\]\s+(.+)", facts_section):
            facts.append({
                "text": m.group(3).strip(),
                "quote": m.group(3).strip(),
                "source_index": int(m.group(1)),
                "kind": m.group(2).strip(),
                "confidence": 0.9,
            })
        if not facts:
            for m in re.finditer(r"(\d+)\.\s+(.+)", facts_section):
                text = m.group(2).strip()
                if len(text) > 15:
                    facts.append({
                        "text": text, "quote": text,
                        "source_index": int(m.group(1)),
                        "kind": "site", "confidence": 0.9,
                    })
        return facts[:5]

    def _extract_br_context(self, prompt):
        """Extract the Second Brain context block from the prompt."""
        marker = "Additional context from our own data:"
        idx = prompt.find(marker)
        if idx == -1:
            return ""
        start = idx + len(marker)
        rest = prompt[start:].strip()
        # Take until the next blank line or end of prompt
        end = rest.find("\n\n")
        if end == -1:
            return rest[:100]
        return rest[:end].strip()[:100]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _approved_offer():
    return {
        "OFFER-PM-001": {
            "capability": "project_management",
            "segment": "all",
            "persona": "champion",
            "business_problem": "spreadsheets",
            "value_proposition": "one place",
            "concrete_deliverable": "single view",
            "cta": "see it",
            "approval_status": "approved",
            "campaigns": [],
        }
    }


def _client_config():
    return {
        "name": "productive",
        "domain": "productive.test",
        "cadence": "default",
        "product": {
            "capabilities": {
                "project_management": "projects in one place",
                "time_tracking": "time linked to project",
                "budgeting": "budget burn visibility",
                "resource_planning": "who is booked next",
                "billing": "invoices from time",
                "profitability": "margin while project runs",
            },
        },
        "sender": {"name": "Ivan", "role": "founder",
                   "company": "Productive",
                   "works_on": "project profitability"},
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
            {"label": "role", "url": "https://testcorp.test/careers",
             "text": "TestCorp opened a London office in 2024"},
        ],
    }


def _contacts():
    return [{
        "email": "jane@testcorp.test",
        "first_name": "Jane",
        "title": "CEO",
        "contact_key": "jane@testcorp.test",
        "sender_name": "Ivan",
        "linkedin": "https://linkedin.com/in/janedoe",
    }]


# ---------------------------------------------------------------------------
# Acceptance #1: changing an approved fact changes the output.
# ---------------------------------------------------------------------------

class TestChangingApprovedFactChangesOutput(unittest.TestCase):
    """THE SECTION 4 TEST.

    Change one approved Second Brain fact, call generate() through the real
    entrypoint, assert the plan differs. Change it back, assert it returns.
    """

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    @mock.patch.object(secondbrain, "for_task")
    def test_changing_verified_fact_changes_plan(self, mock_br, _mock_offers):
        campaignstrategy.clear_cache()

        # First run: fact A is verified
        mock_br.return_value = {
            "profile": [{"text": "ALPHA: Productive shows project margin in real time",
                         "source": "config/clients/productive.yaml product.name",
                         "verified": True}],
            "customers": [],
            "messaging": [],
            "offers": [],
        }
        model_a = _FactAwareModel()
        plan_a = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model_a)

        # Second run: fact B replaces fact A
        campaignstrategy.clear_cache()
        mock_br.return_value = {
            "profile": [{"text": "BETA: Productive tracks utilisation across teams",
                         "source": "config/clients/productive.yaml product.name",
                         "verified": True}],
            "customers": [],
            "messaging": [],
            "offers": [],
        }
        model_b = _FactAwareModel()
        plan_b = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model_b)

        # The plans MUST differ. The verified fact flows into the hypothesis
        # stage via business_context, which changes the hypothesis, which
        # changes the writer output.
        contact_a = plan_a["contacts"][0]
        contact_b = plan_b["contacts"][0]

        # The hypothesis should differ because the Second Brain context changed
        hyp_a = (contact_a.get("hypothesis") or {}).get("hypothesis", "")
        hyp_b = (contact_b.get("hypothesis") or {}).get("hypothesis", "")
        self.assertNotEqual(
            hyp_a, hyp_b,
            "hypothesis did not change when verified fact changed. "
            "hyp_a=%r, hyp_b=%r" % (hyp_a[:80], hyp_b[:80]))

        # The email body should differ because it incorporates the hypothesis
        em1_a = contact_a.get("sequences", {}).get("em1", "")
        em1_b = contact_b.get("sequences", {}).get("em1", "")
        self.assertNotEqual(
            em1_a, em1_b,
            "email body did not change when verified fact changed")

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    @mock.patch.object(secondbrain, "for_task")
    def test_changing_back_returns_output(self, mock_br, _mock_offers):
        """Change a fact, then change it back. The output must return."""
        campaignstrategy.clear_cache()

        original_br = {
            "profile": [{"text": "ALPHA: Productive shows project margin in real time",
                         "source": "config/clients/productive.yaml product.name",
                         "verified": True}],
            "customers": [], "messaging": [], "offers": [],
        }
        mock_br.return_value = original_br
        model_1 = _FactAwareModel()
        plan_1 = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model_1)

        # Change the fact
        campaignstrategy.clear_cache()
        mock_br.return_value = {
            "profile": [{"text": "BETA: CHANGED FACT entirely different",
                         "source": "config/clients/productive.yaml product.name",
                         "verified": True}],
            "customers": [], "messaging": [], "offers": [],
        }
        model_2 = _FactAwareModel()
        plan_2 = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model_2)

        # Change it back
        campaignstrategy.clear_cache()
        mock_br.return_value = original_br
        model_3 = _FactAwareModel()
        plan_3 = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model_3)

        hyp_1 = (plan_1["contacts"][0].get("hypothesis") or {}).get(
            "hypothesis", "")
        hyp_3 = (plan_3["contacts"][0].get("hypothesis") or {}).get(
            "hypothesis", "")
        self.assertEqual(
            hyp_1, hyp_3,
            "hypothesis did not return when fact was restored. "
            "hyp_1=%r, hyp_3=%r" % (hyp_1[:80], hyp_3[:80]))


# ---------------------------------------------------------------------------
# Acceptance #2: changing an UNAPPROVED fact does NOT change output.
# ---------------------------------------------------------------------------

class TestUnapprovedFactDoesNotChangeOutput(unittest.TestCase):
    """Negative control.

    Change a fact that is NOT verified (INFERRED), assert the prospect-facing
    output does NOT change. If it does, the pipeline passes unapproved
    material to prospects - a P0.
    """

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    @mock.patch.object(secondbrain, "for_task")
    def test_unverified_fact_does_not_change_prospect_output(
            self, mock_br, _mock_offers):
        campaignstrategy.clear_cache()

        # First run: fact is NOT verified
        mock_br.return_value = {
            "profile": [{"text": "ALPHA: Productive is the best tool ever",
                         "source": "config/clients/productive.yaml product.name",
                         "verified": False}],
            "customers": [], "messaging": [], "offers": [],
        }
        model_a = _FactAwareModel()
        plan_a = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model_a)

        # Second run: different unverified fact
        campaignstrategy.clear_cache()
        mock_br.return_value = {
            "profile": [{"text": "BETA: Productive was founded in 2015",
                         "source": "config/clients/productive.yaml product.name",
                         "verified": False}],
            "customers": [], "messaging": [], "offers": [],
        }
        model_b = _FactAwareModel()
        plan_b = generate_campaign.generate(
            _client_config(), _account(), _contacts(), model=model_b)

        contact_a = plan_a["contacts"][0]
        contact_b = plan_b["contacts"][0]

        # The prospect-facing email body must NOT change
        em1_a = contact_a.get("sequences", {}).get("em1", "")
        em1_b = contact_b.get("sequences", {}).get("em1", "")
        self.assertEqual(
            em1_a, em1_b,
            "P0: prospect-facing output changed when an UNVERIFIED fact "
            "changed. The pipeline is passing unapproved material to "
            "prospects. em1_a=%r, em1_b=%r" % (em1_a[:80], em1_b[:80]))

        # The hypothesis must NOT change either
        hyp_a = (contact_a.get("hypothesis") or {}).get("hypothesis", "")
        hyp_b = (contact_b.get("hypothesis") or {}).get("hypothesis", "")
        self.assertEqual(
            hyp_a, hyp_b,
            "P0: hypothesis changed when an UNVERIFIED fact changed. "
            "hyp_a=%r, hyp_b=%r" % (hyp_a[:80], hyp_b[:80]))


if __name__ == "__main__":
    unittest.main()
