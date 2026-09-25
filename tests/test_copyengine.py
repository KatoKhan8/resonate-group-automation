"""Tests for the v2 copy engine: stage runner, preview, and regression.

The stage runner is tested with ScriptedModel, which plays canned answers
in order. Each test constructs the right sequence of JSON answers for
stages A through H and verifies the runner's behaviour.

NO LIVE OUTREACH. No provider is called. No email is sent.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import copyengine, copypreview, sequencegate, copylint
from src.llm import ScriptedModel


# --------------------------------------------------------------------------
# FIXTURES: canned answers for each stage, in order.
# --------------------------------------------------------------------------

def _agency_answer():
    """Stage A: yes, it is an agency."""
    return {"is_agency": True, "confidence": 0.9,
            "evidence": "we are a digital marketing agency",
            "what_they_actually_are": None}


def _not_agency_answer():
    """Stage A: not an agency."""
    return {"is_agency": False, "confidence": 0.95,
            "evidence": "we sell software licenses",
            "what_they_actually_are": "software product company"}


def _extraction_answer():
    """Stage B: three real facts."""
    return {
        "facts": [
            {"text": "Digital Position opened a London office in March 2026.",
             "quote": "opened a London office in March 2026",
             "source_index": 1, "kind": "post", "confidence": 0.9},
            {"text": "They are hiring two project managers for the delivery team.",
             "quote": "hiring two project managers",
             "source_index": 2, "kind": "role", "confidence": 0.85},
            {"text": "The company runs paid media campaigns for e-commerce brands.",
             "quote": "paid media campaigns for e-commerce brands",
             "source_index": 1, "kind": "site", "confidence": 0.9},
        ],
        "angle": "growth_without_systems",
        "angle_reason": "hiring PMs while expanding to a new office",
        "company_hook": "A growing paid media agency expanding into London.",
        "usable": True,
        "why_this_lead": "Growing agency with operational complexity from expansion.",
    }


def _empty_extraction_answer():
    """Stage B: no usable facts."""
    return {"facts": [], "angle": None, "angle_reason": "",
            "company_hook": "", "usable": False,
            "why_this_lead": ""}


def _hypothesis_answer():
    """Stage C: a hypothesis."""
    return {
        "signal_strength": "strong",
        "signal": "hiring two project managers",
        "business_model": "paid media retainers for e-commerce",
        "operational_complexity": "two offices, growing delivery team",
        "role_family": "operations",
        "hypothesis": "Agencies expanding to a second office often find "
                      "that project visibility does not scale with the team.",
        "hypothesis_basis": "the London expansion and PM hiring",
        "qualification": "QUALIFIED_RICH",
        "confidence": 0.8,
    }


def _match_answer(cap_key="resource_planning"):
    """Stage D: a capability match."""
    return {
        "capability_key": cap_key,
        "why_this_one": "Expanding agencies need to see who is booked where.",
        "what_changes": "The ops lead can see next week's resourcing today.",
        "runner_up": "project_management",
        "confidence": 0.85,
    }


def _strategy_answer():
    """Stage E: the plan."""
    return {
        "emails": {
            "em1": {"objective": "Open with the London expansion fact",
                    "angle": "growth outpacing visibility",
                    "proof": "fact 1: London office", "cta": "discovery"},
            "em2": {"objective": "Introduce the resourcing angle",
                    "angle": "who is booked next week",
                    "proof": "fact 2: hiring PMs", "cta": "qualification"},
            "em3": {"objective": "Name the capability concretely",
                    "angle": "resource planning workflow",
                    "proof": "product", "cta": "resource"},
            "em4": {"objective": "A practical observation they can use alone",
                    "angle": "utilisation reporting pattern",
                    "proof": "fact 3: e-commerce", "cta": "meeting"},
            "em5": {"objective": "Short close with a clean exit",
                    "angle": "timing check",
                    "proof": "none", "cta": "meeting"},
        },
        "linkedin": {
            "connect": {"objective": "Relevance, no pitch",
                        "angle": "London expansion", "cta": ""},
            "msg1": {"objective": "Who is writing, why them",
                     "angle": "growth", "cta": "discovery",
                     "must_not_repeat": "em1"},
            "msg2": {"objective": "Capability in one line",
                     "angle": "resource planning", "cta": "resource",
                     "must_not_repeat": "em3"},
            "msg3": {"objective": "Short close",
                     "angle": "timing", "cta": "meeting",
                     "must_not_repeat": "em5"},
        },
        "dropped": [],
        "repetition_check": "em4 shifts from resourcing to utilisation reporting",
    }


def _writer_answer():
    """Stage F: the copy."""
    return {
        "hold": False, "hold_reason": None,
        "subject": "your london media hires",
        "subject_alt": "e-commerce campaigns at scale",
        "subject_breakup": "quick check",
        "emails": {
            "em1": "Saw you opened the London office. Teams expanding to a "
                   "second location often find that project visibility does "
                   "not scale with the headcount. Productive shows who is "
                   "booked on what and whether a campaign is burning to plan "
                   "while it runs. Open to a quick look?",
            "em2": "The project managers you are hiring will need to see "
                   "next week's resourcing before Monday. Most agencies we "
                   "speak to find that out at the end of a sprint rather "
                   "than the start.",
            "em3": "Resource planning in one place means the ops lead sees "
                   "the full picture: who is on what, which campaign is "
                   "over capacity, where the next hire should go. No "
                   "spreadsheets, no waiting for a report.",
            "em4": "One pattern we see in e-commerce agencies: utilisation "
                   "looks fine in aggregate but individual campaign margins "
                   "tell a different story. Worth tracking before the next "
                   "quarter starts.",
            "em5": "If the timing is off, no problem. Happy to leave it "
                   "here or point you at someone who has found this useful.",
        },
        "ps": {
            "em1": "Also noticed the e-commerce focus, which is a busy "
                   "vertical to scale in.",
            "em3": "Productive does time tracking, budgeting and "
                   "resourcing in one place.",
        },
        "ps_variant": "ps_fact",
        "linkedin": {
            "connect": "hi, saw the london expansion and thought it would "
                       "be good to connect. always interesting to watch an "
                       "agency grow into a new market.",
            "msg1": "Hi {firstName}, I'm Ivan, I work on Productive. We "
                    "help agencies see project margin and resourcing while "
                    "the work is running. The London expansion caught my "
                    "eye. How are you tracking resourcing across both "
                    "offices today?",
            "msg2": "The resource planning piece in Productive shows who is "
                    "booked on what next week. I also sent a note by email "
                    "about this, so the two channels are from the same "
                    "person. Worth a look?",
            "msg3": "Appreciate your time either way. If there is a better "
                    "person to speak with about resourcing, glad for the "
                    "introduction.",
        },
        "facts_used": {"em1": 1, "ps_em1": 3, "em2": 2, "em3": 0,
                       "em4": 3, "em5": 0},
        "confidence": 0.8,
        "why_this_lead": "Growing agency with clear operational complexity.",
    }


def _good_lead():
    """A lead fixture that should pass the full pipeline."""
    return {
        "key": "digital-position-1",
        "id": "dp-1",
        "company": "Digital Position",
        "domain": "digitalposition.com",
        "name": "Jane Smith",
        "title": "Head of Operations",
        "sender_name": "Ivan",
        "linkedin": "https://linkedin.com/in/janesmith",
        "sources": [
            {"label": "Homepage", "url": "https://digitalposition.com",
             "text": "Digital Position is a paid media agency specialising "
                     "in e-commerce. We opened our London office in March "
                     "2026 to serve European clients."},
            {"label": "Careers", "url": "https://digitalposition.com/careers",
             "text": "We are hiring two project managers for our growing "
                     "delivery team. Paid media campaigns for e-commerce "
                     "brands."},
        ],
    }


def _full_pipeline_answers(cap_key="resource_planning"):
    """The full sequence of answers for stages A through F."""
    return [
        _agency_answer(),
        _extraction_answer(),
        _hypothesis_answer(),
        _match_answer(cap_key),
        _strategy_answer(),
        _writer_answer(),
    ]


def _cheap_answers(cap_key="resource_planning"):
    """Stages A to E only (the cheap model)."""
    return _full_pipeline_answers(cap_key)[:5]


def _expensive_answer():
    """Stage F only (the expensive model)."""
    return _writer_answer()


# --------------------------------------------------------------------------
# TESTS
# --------------------------------------------------------------------------

class JsonParser(unittest.TestCase):
    """The JSON parser handles truncation, fences, and strict=False."""

    def test_valid_json_passes(self):
        data = copyengine._parse_json('{"a": 1}', "test")
        self.assertEqual(data, {"a": 1})

    def test_fenced_json_passes(self):
        data = copyengine._parse_json('```json\n{"a": 1}\n```', "test")
        self.assertEqual(data, {"a": 1})

    def test_newlines_in_strings_are_tolerated(self):
        data = copyengine._parse_json('{"a": "line1\\nline2"}', "test")
        self.assertEqual(data["a"], "line1\nline2")

    def test_truncation_is_its_own_error(self):
        long_text = '{"emails": {"em1": "' + "x" * 500
        with self.assertRaises(copyengine.TruncationError):
            copyengine._parse_json(long_text, "test")

    def test_short_bad_json_is_a_plain_error(self):
        with self.assertRaises(copyengine.StageError):
            copyengine._parse_json("not json", "test")

    def test_non_object_is_rejected(self):
        with self.assertRaises(copyengine.StageError):
            copyengine._parse_json("[1, 2, 3]", "test")


class StageAQualification(unittest.TestCase):
    """Stage A: is this company an agency?"""

    def test_not_an_agency_is_unqualified(self):
        model = ScriptedModel(_not_agency_answer())
        result = copyengine.run_stages(_good_lead(), model, model)
        self.assertEqual(result["qualification"], "UNQUALIFIED")
        self.assertTrue(result["hold"])

    def test_an_agency_continues_past_a(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        self.assertIn(result["qualification"],
                      ("QUALIFIED_RICH", "QUALIFIED_THIN"))


class StageBExtraction(unittest.TestCase):
    """Stage B: research extraction."""

    def test_no_facts_means_insufficient(self):
        model = ScriptedModel(_agency_answer(), _empty_extraction_answer())
        result = copyengine.run_stages(_good_lead(), model, model)
        self.assertEqual(result["qualification"], "INSUFFICIENT")
        self.assertTrue(result["hold"])


class StageCHypothesis(unittest.TestCase):
    """Stage C: the problem hypothesis."""

    def test_hypothesis_is_recorded(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        self.assertIn("hypothesis", result)
        self.assertTrue(len(result["hypothesis"]) > 10)

    def test_signal_strength_is_recorded(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        self.assertEqual(result["signal_strength"], "strong")


class StageDMatch(unittest.TestCase):
    """Stage D: value proposition matching. The capability must vary."""

    def test_capability_key_is_recorded(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        self.assertEqual(result["capability_key"], "resource_planning")

    def test_different_leads_can_get_different_capabilities(self):
        """Two leads with different match answers get different keys."""
        answers_1 = _full_pipeline_answers("resource_planning")
        answers_2 = _full_pipeline_answers("billing")
        cheap_1 = ScriptedModel(*answers_1)
        cheap_2 = ScriptedModel(*answers_2)
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        r1 = copyengine.run_stages(_good_lead(), cheap_1, expensive)
        expensive2 = ScriptedModel(_writer_answer(), _writer_answer())
        r2 = copyengine.run_stages(_good_lead(), cheap_2, expensive2)
        self.assertNotEqual(r1["capability_key"], r2["capability_key"])


class StageEStrategy(unittest.TestCase):
    """Stage E: the plan exists before any copy."""

    def test_plan_is_recorded(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        self.assertIn("plan", result)
        self.assertIn("emails", result["plan"])
        self.assertIn("linkedin", result["plan"])


class StageFWriter(unittest.TestCase):
    """Stage F: the copy, written by the expensive model."""

    def test_copy_has_five_emails(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        emails = result["copy"]["emails"]
        for key in ("em1", "em2", "em3", "em4", "em5"):
            self.assertIn(key, emails)
            self.assertTrue(len(emails[key]) > 10,
                            "%s is empty" % key)

    def test_copy_has_three_subjects(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        copy = result["copy"]
        self.assertTrue(copy.get("subject"))
        self.assertTrue(copy.get("subject_alt"))
        self.assertTrue(copy.get("subject_breakup"))

    def test_copy_has_linkedin_messages(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        li = result["copy"]["linkedin"]
        for key in ("connect", "msg1", "msg2", "msg3"):
            self.assertIn(key, li)
            self.assertTrue(len(li[key]) > 5)

    def test_copy_has_ps_on_em1_and_em3(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        ps = result["copy"]["ps"]
        self.assertTrue(ps.get("em1"))
        self.assertTrue(ps.get("em3"))

    def test_writer_hold_stops_the_pipeline(self):
        hold_answer = _full_pipeline_answers()
        cheap = ScriptedModel(*hold_answer)
        # The hold comes from the WRITER (stage F), which is the expensive model.
        expensive = ScriptedModel({"hold": True,
                                   "hold_reason": "no real facts to quote"})
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        self.assertTrue(result["hold"])
        self.assertNotIn("copy", result)


class StageGGate(unittest.TestCase):
    """Stage G: the sequence-level gate."""

    def test_gate_runs_on_the_sequence(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        self.assertIn("gate", result)
        self.assertIn("passed", result["gate"])
        self.assertIn("failures", result["gate"])

    def test_acceptance_command(self):
        """The acceptance command from TASK-312.

        The gate catches repetition when the content is long enough to have
        content words. Short strings like 'a' have no 4+ char words so the
        overlap function returns 0. With real-length copy the gate fires.
        """
        repeated = ("The team opened a second delivery team in Berlin and "
                    "are taking on platform work through Q4.")
        r = sequencegate.check(
            {"emails": {"em1": repeated, "em2": repeated},
             "linkedin": {}, "ps": {}, "subjects": {}})
        steps = [f["step"] for f in r["failures"]]
        self.assertTrue(steps)
        self.assertFalse(r["passed"])
        self.assertIn("em2", steps)


class StageHOutput(unittest.TestCase):
    """Stage H: EmailBison variables, HeyReach steps."""

    def test_bison_vars_have_subjects_and_bodies(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        output = result["output"]
        bv = output["bison_vars"]
        self.assertIn("subject_1", bv)
        self.assertIn("body_1", bv)
        self.assertIn("body_5", bv)
        self.assertIn("ps_1", bv)

    def test_heyreach_steps_have_four_messages(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        hs = result["output"]["heyreach_steps"]
        for key in ("connect", "msg1", "msg2", "msg3"):
            self.assertIn(key, hs)


class BatchRunner(unittest.TestCase):
    """Batch-level checks: capability diversity."""

    def test_five_leads_same_capability_is_flagged(self):
        """If every lead gets the same capability, D is defaulting."""
        leads = [_good_lead() for _ in range(5)]

        class RepeatingModel:
            """A model that replays the same answer set for each lead."""
            name = "repeating"
            def __init__(self, *answer_sets):
                self._answer_sets = list(answer_sets)
                self._n = len(answer_sets)
                self._call_count = 0
                self.prompts = []
            def complete(self, prompt):
                self.prompts.append(prompt)
                # Cycle through answers per lead: each lead gets n calls.
                idx = self._call_count % self._n
                self._call_count += 1
                answer = self._answer_sets[idx]
                return answer if isinstance(answer, str) else json.dumps(answer)

        cheap = RepeatingModel(*_cheap_answers("profitability"))
        expensive = RepeatingModel(_expensive_answer())
        results = copyengine.run_batch(
            leads, cheap, expensive,
            client_config={"product": {"capabilities": {
                "profitability": "margin per project while running"}}})
        # At least one result should carry the batch-level failure.
        batch_failures = []
        for r in results:
            for f in (r.get("gate") or {}).get("failures") or []:
                if f.get("step") == "batch":
                    batch_failures.append(f)
        self.assertTrue(batch_failures,
                        "batch-level defaulting check did not fire")

    def test_five_leads_different_capabilities_is_clean(self):
        caps = ["project_management", "time_tracking", "budgeting",
                "resource_planning", "billing"]
        leads = [_good_lead() for _ in range(5)]
        # Each lead gets a different capability via the cheap model.
        # The expensive model always returns the same writer answer.
        all_cheap = []
        for c in caps:
            all_cheap.extend(_cheap_answers(c))
        cheap = ScriptedModel(*all_cheap)
        # 5 leads, each needing 1 expensive call + possibly 1 rewrite.
        expensive = ScriptedModel(*([_expensive_answer()] * 10))
        results = copyengine.run_batch(
            leads, cheap, expensive,
            client_config={"product": {"capabilities": {
                "project_management": "projects in one place",
                "time_tracking": "time against the project",
                "budgeting": "quoted vs burned",
                "resource_planning": "who is booked on what",
                "billing": "invoices from time and budget",
            }}})
        for r in results:
            batch_failures = [
                f for f in (r.get("gate") or {}).get("failures") or []
                if f.get("step") == "batch"]
            self.assertFalse(batch_failures,
                             "batch check fired when capabilities differ")


class RoleFamilyMapping(unittest.TestCase):
    """The role family mapping for stage D."""

    def test_ceo_is_executive(self):
        self.assertEqual(copyengine._role_family_for("CEO"), "executive")

    def test_operations_manager_is_operations(self):
        self.assertEqual(copyengine._role_family_for("Operations Manager"),
                         "operations")

    def test_project_manager_is_delivery(self):
        self.assertEqual(copyengine._role_family_for("Project Manager"),
                         "delivery")

    def test_cfo_is_finance(self):
        self.assertEqual(copyengine._role_family_for("CFO"), "finance")

    def test_unknown_defaults_to_executive(self):
        self.assertEqual(copyengine._role_family_for("Ninja Rockstar"),
                         "executive")


class PsVariant(unittest.TestCase):
    """P.S. variant assignment: ps_none is retired in v2."""

    def test_ps_none_becomes_ps_fact(self):
        # Find a key that maps to ps_none in the old system.
        import hashlib
        for i in range(100):
            key = "test-key-%d" % i
            v = copyengine._ps_variant(key)
            self.assertIn(v, ("ps_fact", "ps_capability"))


class Preview(unittest.TestCase):
    """The preview renders correctly."""

    def test_render_lead_shows_hypothesis_label(self):
        result = {
            "qualification": "QUALIFIED_RICH",
            "facts": [{"text": "Opened London office.", "kind": "post"}],
            "hypothesis": "Agencies like this often find X.",
            "signal_strength": "strong",
            "business_model": "paid media retainers",
            "capability_key": "resource_planning",
            "capability_sentence": "who is booked on what",
            "why_this_capability": "Expanding agency needs visibility.",
            "copy": _writer_answer(),
            "gate": {"passed": True, "failures": [], "warnings": []},
            "plan": _strategy_answer(),
            "output": {"bison_vars": {}, "heyreach_steps": {}},
            "hold": False,
        }
        page = copypreview.render_lead(result, _good_lead())
        self.assertIn("HYPOTHESIS", page)
        self.assertIn("QUALIFIED_RICH", page)
        self.assertIn("Digital Position", page)

    def test_gate_badge_shows_passed(self):
        badge = copypreview._gate_badge(
            {"passed": True, "failures": [], "warnings": []})
        self.assertIn("PASSED", badge)

    def test_gate_badge_shows_failed(self):
        badge = copypreview._gate_badge(
            {"passed": False, "failures": [{"check": "x", "step": "em1",
                                             "why": "bad"}],
             "warnings": []})
        self.assertIn("FAILED", badge)

    def test_full_page_renders(self):
        result = {
            "qualification": "QUALIFIED_RICH",
            "facts": [{"text": "Fact one.", "kind": "site"}],
            "hypothesis": "A hypothesis.",
            "signal_strength": "strong",
            "business_model": "retainers",
            "capability_key": "budgeting",
            "capability_sentence": "quoted vs burned",
            "why_this_capability": "Fits the role.",
            "copy": _writer_answer(),
            "gate": {"passed": True, "failures": [], "warnings": []},
            "plan": _strategy_answer(),
            "output": {"bison_vars": {}, "heyreach_steps": {}},
            "hold": False,
        }
        page = copypreview.render_page([result], [_good_lead()])
        self.assertIn("<!DOCTYPE html>", page)
        self.assertIn("Digital Position", page)
        self.assertIn("Distinct capabilities", page)

    def test_write_page_creates_file(self):
        result = {
            "qualification": "QUALIFIED_THIN",
            "facts": [],
            "hypothesis": "",
            "signal_strength": "weak",
            "business_model": "",
            "capability_key": "",
            "capability_sentence": "",
            "why_this_capability": "",
            "copy": {},
            "gate": None,
            "plan": {},
            "output": {"bison_vars": {}, "heyreach_steps": {}},
            "hold": True,
            "hold_reason": "test",
        }
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "preview.html")
            copypreview.write_page(path, [result], [{"company": "Test Co"}])
            self.assertTrue(os.path.exists(path))
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Test Co", content)


class DashRule(unittest.TestCase):
    """The no-dash rule fires on the writer's output."""

    def test_a_dash_in_email_body_is_caught_by_copylint(self):
        leads = [{
            "id": "test-1",
            "steps": [{"body": "Good opening line about them.",
                       "subject": "your team"},
                      {"body": "Step 2 with a dash - in the middle."},
                      {"body": "Step 3 body."},
                      {"body": "Step 4 body."},
                      {"body": "Step 5 body."}],
            "ps": {"em1": "A P.S. line."},
            "linkedin": {},
        }]
        packs = {"test-1": {"facts": [
            {"snippet": "Good opening line about them."}]}}
        report = copylint.check_batch(leads, packs)
        self.assertIn("test-1", report["offenders"]["dash"])


class SequenceGateRegression(unittest.TestCase):
    """The sequence gate names the step that failed."""

    def test_repeated_emails_are_caught(self):
        seq = {
            "emails": {
                "em1": "Opening with a fact about the company and a "
                       "hypothesis about their operations.",
                "em2": "Opening with a fact about the company and a "
                       "hypothesis about their operations.",
                "em3": "Something different about resource planning.",
                "em4": "A different angle on utilisation.",
                "em5": "Short close.",
            },
            "linkedin": {},
            "subjects": {"a": "their team", "b": "resource planning",
                         "c": "quick check"},
            "hypothesis": "Agencies often find visibility comes late.",
            "ps": {"em1": "A fact.", "em3": "A capability."},
        }
        result = sequencegate.check(seq, facts=[{"text": "fact"}],
                                    qualification="QUALIFIED_RICH")
        # em2 repeats em1.
        steps = [f["step"] for f in result["failures"]]
        self.assertIn("em2", steps)

    def test_hypothesis_stated_as_fact_is_caught(self):
        seq = {
            "emails": {
                "em1": "I know you are losing margin on fixed fee work. "
                       "Productive can help.",
                "em2": "A different point about resourcing.",
                "em3": "Resource planning in one place.",
                "em4": "A utilisation pattern.",
                "em5": "Short close.",
            },
            "linkedin": {},
            "subjects": {"a": "your margins", "b": "planning", "c": "check"},
            "hypothesis": "Agencies often find visibility comes late.",
            "ps": {"em1": "A fact.", "em3": "A capability."},
        }
        result = sequencegate.check(seq, facts=[{"text": "margin"}],
                                    qualification="QUALIFIED_RICH")
        steps = [f["step"] for f in result["failures"]]
        self.assertIn("em1", steps)


class StageRunnerOrder(unittest.TestCase):
    """Stages run A to H in order, and the log records each one."""

    def test_stages_run_in_order(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        result = copyengine.run_stages(_good_lead(), cheap, expensive)
        stages = [entry["stage"] for entry in result["stages_log"]]
        self.assertEqual(stages, ["A", "B", "C", "D", "E", "F", "G"])

    def test_unqualified_stops_after_a(self):
        model = ScriptedModel(_not_agency_answer())
        result = copyengine.run_stages(_good_lead(), model, model)
        stages = [entry["stage"] for entry in result["stages_log"]]
        self.assertEqual(stages, ["A"])

    def test_insufficient_stops_after_b(self):
        model = ScriptedModel(_agency_answer(), _empty_extraction_answer())
        result = copyengine.run_stages(_good_lead(), model, model)
        stages = [entry["stage"] for entry in result["stages_log"]]
        self.assertEqual(stages, ["A", "B"])


class CheapVsExpensiveModel(unittest.TestCase):
    """Stages A-E use the cheap model; F uses the expensive one."""

    def test_cheap_model_gets_five_calls(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        copyengine.run_stages(_good_lead(), cheap, expensive)
        # A, B, C, D, E = 5 calls to the cheap model.
        self.assertEqual(len(cheap.prompts), 5)

    def test_expensive_model_gets_one_call(self):
        cheap = ScriptedModel(*_full_pipeline_answers())
        expensive = ScriptedModel(_writer_answer(), _writer_answer())
        copyengine.run_stages(_good_lead(), cheap, expensive)
        # F = 1 call to the expensive model (rewrite may add a second).
        self.assertGreaterEqual(len(expensive.prompts), 1)


if __name__ == "__main__":
    unittest.main()
