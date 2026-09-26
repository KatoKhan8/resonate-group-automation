"""Tests for the v2 copy engine stage runner.

Each test uses mocked model calls (no real API keys needed) and verifies:
- The stage runner calls stages in order A-H
- JSON parsing handles fences, literal newlines, and truncation
- The gate result is carried through
- Output shapes are correct
- Held leads stop the pipeline at the right stage
- The batch-level capability check fires
"""
import json
import unittest

from src import copyengine, copystages, copyprompts, sequencegate


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _lead(**kw):
    base = {"name": "Jane Doe", "first": "Jane", "last": "Doe",
            "title": "CEO", "email": "jane@acme.com",
            "company": "Acme Agency", "domain": "acme.com",
            "sender_name": "Ivan", "sender_email": "ivan@productive.test",
            "linkedin": "https://linkedin.com/in/janedoe"}
    base.update(kw)
    return base


def _sources():
    return [
        {"label": "site", "url": "https://acme.com/about",
         "text": "Acme is a 30-person digital marketing agency in London "
                 "specialising in performance marketing for B2B tech clients. "
                 "We recently opened a second office in Manchester."},
        {"label": "role", "url": "https://acme.com/careers/ops-lead",
         "text": "Head of Operations - own our delivery pipeline across "
                 "three service lines. Reporting to the COO."},
        {"label": "post", "url": "https://linkedin.com/posts/acme-123",
         "text": "Excited to announce we have signed three new enterprise "
                 "clients this quarter, doubling our managed spend."},
    ]


def _config():
    return {
        "product": {
            "name": "Productive",
            "what_it_is": "one place for budgets, time tracking, resourcing "
                          "and invoicing",
            "capabilities": {
                "project_management": "projects, tasks and delivery in one place",
                "time_tracking": "time booked against the project and budget",
                "budgeting": "what a project was quoted at and what it burned",
                "resource_planning": "who is booked on what next week",
                "billing": "invoices raised from time and budget",
                "profitability": "margin per project while it is running",
            },
        },
    }


def _icp_response(is_agency=True, confidence=0.9):
    return json.dumps({
        "is_agency": is_agency,
        "confidence": confidence,
        "evidence": "digital marketing agency",
        "what_they_actually_are": None if is_agency else "software product",
    })


def _extract_response(usable=True, n_facts=3):
    facts = [
        {"text": "Acme is a 30-person digital marketing agency in London.",
         "quote": "30-person digital marketing agency in London",
         "source_index": 1, "kind": "site", "confidence": 0.9},
        {"text": "They recently opened a second office in Manchester.",
         "quote": "opened a second office in Manchester",
         "source_index": 1, "kind": "site", "confidence": 0.85},
        {"text": "Acme signed three new enterprise clients this quarter.",
         "quote": "signed three new enterprise clients this quarter",
         "source_index": 3, "kind": "post", "confidence": 0.9},
    ]
    return json.dumps({
        "facts": facts[:n_facts],
        "angle": "growth_without_systems",
        "angle_reason": "rapid client growth suggests scaling pressure",
        "company_hook": "Acme is a growing London agency expanding north.",
        "usable": usable,
        "why_this_lead": "growing agency with scaling operations",
    })


def _hypothesis_response(qualification="QUALIFIED_RICH"):
    return json.dumps({
        "signal_strength": "strong",
        "signal": "signed three new enterprise clients",
        "business_model": "performance marketing retainers for B2B tech",
        "operational_complexity": "30 people across two offices, scaling fast",
        "role_family": "executive",
        "hypothesis": "agencies growing this fast often find that project "
                      "margin becomes visible only after the month closes",
        "hypothesis_basis": "rapid enterprise client growth",
        "qualification": qualification,
        "confidence": 0.8,
    })


def _match_response(cap_key="profitability"):
    return json.dumps({
        "capability_key": cap_key,
        "why_this_one": "margin visibility matters most at this growth stage",
        "what_changes": "you see project margin while the work runs",
        "runner_up": "resource_planning",
        "confidence": 0.75,
    })


def _strategy_response():
    return json.dumps({
        "emails": {
            "em1": {"objective": "open with the growth signal",
                    "angle": "scaling fast, margin visibility lags",
                    "proof": "three new enterprise clients",
                    "cta": "discovery: do you track margin in real time?"},
            "em2": {"objective": "adjacent problem: resourcing",
                    "angle": "who is booked on what",
                    "proof": "two offices, three service lines",
                    "cta": "qualification: dedicated platform or mix?"},
            "em3": {"objective": "concrete product workflow",
                    "angle": "budget burn visible during delivery",
                    "proof": "product capability",
                    "cta": "resource: useful if I sent an example?"},
            "em4": {"objective": "a practical observation",
                    "angle": "month-end reconciliation pain",
                    "proof": "common pattern at this size",
                    "cta": "meeting: open to a quick look?"},
            "em5": {"objective": "short close",
                    "angle": "clean exit or real reason to reply",
                    "proof": "none",
                    "cta": "reply or pass"},
        },
        "linkedin": {
            "connect": {"objective": "relevance, no pitch",
                        "angle": "growth signal", "cta": ""},
            "msg1": {"objective": "who is writing, why them",
                     "angle": "same fact as em1",
                     "cta": "one question",
                     "must_not_repeat": "em1"},
            "msg2": {"objective": "capability + email cross-ref",
                     "angle": "margin visibility",
                     "cta": "soft ask",
                     "must_not_repeat": "em3"},
            "msg3": {"objective": "short close",
                     "angle": "leave door open", "cta": ""},
        },
        "dropped": [],
        "repetition_check": "em4 uses month-end reconciliation, "
                            "em2 used resourcing visibility",
    })


def _writer_response(has_linkedin=True):
    li = {
        "connect": "hi, saw acme is growing fast with the manchester office "
                   "and three new enterprise clients. would be good to connect.",
        "msg1": "Hi {firstName}, I'm Ivan at Productive. We help agencies see "
                "project margin while the work runs. Noticed Acme's growth and "
                "curious how you track margin across two offices today?",
        "msg2": "The thing we built is real-time margin visibility per project. "
                "I also sent you an email about this, so the two channels read "
                "as one person. Worth a look?",
        "msg3": "Happy to leave it here if the timing is wrong. Door's open.",
    } if has_linkedin else {
        "connect": "", "msg1": "", "msg2": "", "msg3": "",
    }
    return json.dumps({
        "hold": False,
        "hold_reason": None,
        "subject": "your manchester office and three new clients",
        "subject_alt": "acme's enterprise growth this quarter",
        "subject_breakup": "quick note",
        "emails": {
            "em1": "Hi Jane,\n\nSaw Acme signed three new enterprise clients "
                   "this quarter. Agencies growing that fast often find project "
                   "margin becomes visible only after the month closes.\n\n"
                   "Productive shows margin per project while it runs, so you "
                   "can act before the month ends rather than after.\n\n"
                   "Do you currently track margin in real time or after "
                   "delivery?",
            "em2": "The other thing growing agencies hit is knowing who is "
                   "booked on what. With two offices and three service lines, "
                   "that picture gets complicated fast.\n\nIs resourcing "
                   "visibility something you have solved, or does it still "
                   "involve spreadsheets?",
            "em3": "One workflow that agencies your size find useful: open a "
                   "project, see the quoted budget, see what has burned so "
                   "far, and see the margin, all on one screen while the "
                   "work is running.\n\nWould it be useful if I sent an "
                   "example of how that looks?",
            "em4": "Most agencies I speak to find that month-end "
                   "reconciliation takes days because the finance view and "
                   "the delivery view disagree. If that resonates, a quick "
                   "look might save real time.\n\nOpen to a quick look?",
            "em5": "Jane, I will leave it here. If the timing is wrong, no "
                   "pressure at all. If there is someone else who owns this, "
                   "happy for a pointer.\n\nAll the best.",
        },
        "ps": {
            "em1": "Also noticed the Manchester opening, congrats on the "
                   "expansion.",
            "em3": "The budgeting module does the quote-to-burn tracking "
                   "without any setup.",
        },
        "ps_variant": "ps_fact",
        "linkedin": li,
        "facts_used": {"em1": 3, "ps_em1": 2, "em3": 0},
        "confidence": 0.8,
        "why_this_lead": "fast-growing agency with scaling operations",
    })


def _make_groq_fn(responses):
    """Return a groq_fn that returns canned responses in order."""
    call_count = [0]

    def fn(system, user):
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(responses):
            return responses[idx]
        return "{}"
    return fn


def _make_sonnet_fn(response):
    """Return a sonnet_fn that returns a canned response."""
    def fn(system, user):
        return response
    return fn


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

class TestJsonParsing(unittest.TestCase):
    """JSON parsing handles fences, newlines and truncation."""

    def test_bare_json(self):
        result = copyengine._as_json('{"a": 1}')
        self.assertEqual(result, {"a": 1})

    def test_fenced_json(self):
        result = copyengine._as_json('```json\n{"a": 1}\n```')
        self.assertEqual(result, {"a": 1})

    def test_json_with_prose(self):
        result = copyengine._as_json('Here is the result:\n{"a": 1}\nDone.')
        self.assertEqual(result, {"a": 1})

    def test_literal_newlines_in_strings(self):
        raw = '{"text": "line one\nline two"}'
        result = copyengine._as_json(raw)
        self.assertEqual(result["text"], "line one\nline two")

    def test_truncation_raises(self):
        # Has { and } but is still invalid JSON (truncated mid-array)
        with self.assertRaises(ValueError) as ctx:
            copyengine._as_json('{"a": 1, "b": [1, 2,}')
        self.assertIn("truncated", str(ctx.exception).lower())

    def test_no_json_raises(self):
        with self.assertRaises(ValueError) as ctx:
            copyengine._as_json("no json here at all")
        self.assertIn("no JSON", str(ctx.exception))


class TestRoleFamily(unittest.TestCase):
    """Role family mapping from job titles."""

    def test_finance(self):
        self.assertEqual(copyengine._role_family("CFO"), "finance")
        self.assertEqual(copyengine._role_family("Head of Finance"), "finance")

    def test_delivery(self):
        self.assertEqual(copyengine._role_family("Project Manager"), "delivery")
        self.assertEqual(copyengine._role_family("Design Director"), "delivery")

    def test_operations(self):
        self.assertEqual(copyengine._role_family("COO"), "operations")
        self.assertEqual(copyengine._role_family("Head of Resourcing"),
                         "operations")

    def test_executive_default(self):
        self.assertEqual(copyengine._role_family("CEO"), "executive")
        self.assertEqual(copyengine._role_family("Founder"), "executive")
        self.assertEqual(copyengine._role_family(""), "executive")


class TestStageRunner(unittest.TestCase):
    """The full pipeline, stages A to H, with mocked model calls."""

    def test_full_pipeline_qualifed_rich(self):
        """A qualified lead runs all eight stages and produces output."""
        groq_fn = _make_groq_fn([
            _icp_response(True),
            _extract_response(True, 3),
            _hypothesis_response("QUALIFIED_RICH"),
            _match_response("profitability"),
            _strategy_response(),
        ])
        sonnet_fn = _make_sonnet_fn(_writer_response(True))

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        self.assertIsNone(result["error"])
        self.assertIsNone(result["held"])
        self.assertEqual(result["qualification"], "QUALIFIED_RICH")
        self.assertIsNotNone(result["written"])
        self.assertIsNotNone(result["gate"])
        self.assertIsNotNone(result["output"])
        self.assertIn("emailbison", result["output"])
        self.assertIn("heyreach", result["output"])

    def test_email_output_has_five_steps(self):
        """The output has exactly five email steps."""
        groq_fn = _make_groq_fn([
            _icp_response(True),
            _extract_response(True, 3),
            _hypothesis_response("QUALIFIED_RICH"),
            _match_response("budgeting"),
            _strategy_response(),
        ])
        sonnet_fn = _make_sonnet_fn(_writer_response(True))

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        steps = result["output"]["emailbison"]["steps"]
        self.assertEqual(len(steps), 5)
        keys = [s["key"] for s in steps]
        self.assertEqual(keys, ["em1", "em2", "em3", "em4", "em5"])

    def test_three_threads(self):
        """The three-thread cadence is correct: A, A, B, B, C."""
        groq_fn = _make_groq_fn([
            _icp_response(True),
            _extract_response(True, 3),
            _hypothesis_response("QUALIFIED_RICH"),
            _match_response("resource_planning"),
            _strategy_response(),
        ])
        sonnet_fn = _make_sonnet_fn(_writer_response(True))

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        steps = result["output"]["emailbison"]["steps"]
        threads = [s["thread"] for s in steps]
        self.assertEqual(threads, ["A", "A", "B", "B", "C"])

    def test_replies_are_marked(self):
        """em2 and em4 are thread replies."""
        groq_fn = _make_groq_fn([
            _icp_response(True),
            _extract_response(True, 3),
            _hypothesis_response("QUALIFIED_RICH"),
            _match_response("profitability"),
            _strategy_response(),
        ])
        sonnet_fn = _make_sonnet_fn(_writer_response(True))

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        steps = result["output"]["emailbison"]["steps"]
        replies = {s["key"]: s["thread_reply"] for s in steps}
        self.assertFalse(replies["em1"])
        self.assertTrue(replies["em2"])
        self.assertFalse(replies["em3"])
        self.assertTrue(replies["em4"])
        self.assertFalse(replies["em5"])

    def test_not_agency_holds(self):
        """A non-agency is held at stage A."""
        groq_fn = _make_groq_fn([
            _icp_response(False, 0.9),
        ])
        sonnet_fn = _make_sonnet_fn("{}")

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        self.assertEqual(result["qualification"], "UNQUALIFIED")
        self.assertIn("not an agency", result["held"])
        self.assertIsNone(result["written"])

    def test_no_usable_facts_holds(self):
        """No usable facts holds at stage B."""
        groq_fn = _make_groq_fn([
            _icp_response(True),
            _extract_response(usable=False, n_facts=1),
        ])
        sonnet_fn = _make_sonnet_fn("{}")

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        self.assertIn("no usable fact", result["held"])
        self.assertIsNone(result["written"])

    def test_insufficient_holds(self):
        """INSUFFICIENT qualification holds at stage C."""
        groq_fn = _make_groq_fn([
            _icp_response(True),
            _extract_response(True, 3),
            _hypothesis_response("INSUFFICIENT"),
        ])
        sonnet_fn = _make_sonnet_fn("{}")

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        self.assertEqual(result["qualification"], "INSUFFICIENT")
        self.assertIsNotNone(result["held"])
        self.assertIsNone(result["written"])

    def test_writer_hold(self):
        """The writer can hold a lead."""
        groq_fn = _make_groq_fn([
            _icp_response(True),
            _extract_response(True, 3),
            _hypothesis_response("QUALIFIED_RICH"),
            _match_response("profitability"),
            _strategy_response(),
        ])
        hold_response = json.dumps({
            "hold": True,
            "hold_reason": "no real fact to open with",
            "subject": "", "subject_alt": "", "subject_breakup": "",
            "emails": {}, "ps": {}, "linkedin": {},
        })
        sonnet_fn = _make_sonnet_fn(hold_response)

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        self.assertIn("writer held", result["held"])
        self.assertIsNone(result["written"])

    def test_no_linkedin_produces_empty_steps(self):
        """A lead without LinkedIn gets empty LinkedIn messages."""
        groq_fn = _make_groq_fn([
            _icp_response(True),
            _extract_response(True, 3),
            _hypothesis_response("QUALIFIED_RICH"),
            _match_response("profitability"),
            _strategy_response(),
        ])
        sonnet_fn = _make_sonnet_fn(_writer_response(has_linkedin=False))

        result = copyengine.run_lead(
            _lead(linkedin=None), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        li_steps = result["output"]["heyreach"]["steps"]
        self.assertEqual(len(li_steps), 0)

    def test_stage_error_recorded(self):
        """An error in a stage is recorded, not swallowed."""
        def bad_groq(system, user):
            raise RuntimeError("connection refused")

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=bad_groq, sonnet_fn=lambda s, u: "{}")

        self.assertIsNotNone(result["error"])
        self.assertIn("stage A", result["error"])

    def test_ps_on_em1_and_em3(self):
        """P.S. lines appear on em1 and em3."""
        groq_fn = _make_groq_fn([
            _icp_response(True),
            _extract_response(True, 3),
            _hypothesis_response("QUALIFIED_RICH"),
            _match_response("profitability"),
            _strategy_response(),
        ])
        sonnet_fn = _make_sonnet_fn(_writer_response(True))

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        steps = result["output"]["emailbison"]["steps"]
        ps_map = {s["key"]: s.get("ps", "") for s in steps}
        self.assertTrue(ps_map["em1"], "em1 should have a P.S.")
        self.assertFalse(ps_map["em2"], "em2 should not have a P.S.")
        self.assertTrue(ps_map["em3"], "em3 should have a P.S.")
        self.assertFalse(ps_map["em4"], "em4 should not have a P.S.")
        self.assertFalse(ps_map["em5"], "em5 should not have a P.S.")

    def test_qualified_thin_sends(self):
        """QUALIFIED_THIN is a sending qualification, not a hold."""
        groq_fn = _make_groq_fn([
            _icp_response(True),
            _extract_response(True, 3),
            _hypothesis_response("QUALIFIED_THIN"),
            _match_response("profitability"),
            _strategy_response(),
        ])
        sonnet_fn = _make_sonnet_fn(_writer_response(True))

        result = copyengine.run_lead(
            _lead(), _sources(), _config(),
            groq_fn=groq_fn, sonnet_fn=sonnet_fn)

        self.assertEqual(result["qualification"], "QUALIFIED_THIN")
        self.assertIsNone(result["held"])
        self.assertIsNotNone(result["written"])


class TestBatchCapabilityCheck(unittest.TestCase):
    """The batch-level check fires when stage D defaults."""

    def test_distinct_capabilities_counts(self):
        """distinct_capabilities counts unique caps across a batch."""
        results = [
            {"capability": {"capability_key": "profitability"}},
            {"capability": {"capability_key": "budgeting"}},
            {"capability": {"capability_key": "profitability"}},
            {"capability": {"capability_key": "resource_planning"}},
        ]
        self.assertEqual(copyengine.distinct_capabilities(results), 3)

    def test_single_capability_is_one(self):
        """All the same capability counts as 1."""
        results = [
            {"capability": {"capability_key": "profitability"}},
            {"capability": {"capability_key": "profitability"}},
            {"capability": {"capability_key": "profitability"}},
        ]
        self.assertEqual(copyengine.distinct_capabilities(results), 1)

    def test_case_insensitive(self):
        """Profitability and profitability are the same."""
        results = [
            {"capability": {"capability_key": "Profitability"}},
            {"capability": {"capability_key": "profitability"}},
        ]
        self.assertEqual(copyengine.distinct_capabilities(results), 1)


class TestAcceptanceCommand(unittest.TestCase):
    """The acceptance command from the task spec."""

    def test_gate_refuses_repetition(self):
        """The gate refuses when em2 repeats em1's argument."""
        body = ("project margin visibility is the core challenge for "
                "growing agencies with multiple service lines")
        result = sequencegate.check(
            {"emails": {"em1": body, "em2": body},
             "linkedin": {}, "ps": {}, "subjects": {}},
            qualification="QUALIFIED_RICH")
        self.assertFalse(result["passed"])
        steps = [f["step"] for f in result["failures"]]
        self.assertIn("em2", steps)

    def test_gate_refuses_empty_sequence(self):
        """The exact acceptance command from the task."""
        result = sequencegate.check(
            {"emails": {"em1": "a", "em2": "a"},
             "linkedin": {}, "ps": {}, "subjects": {}})
        # No qualification supplied: the gate refuses absence
        self.assertFalse(result["passed"])


class TestCleanNav(unittest.TestCase):
    """Navigation chrome stripping."""

    def test_strips_nav(self):
        text = "Login About Services Contact We are a great agency."
        cleaned = copyengine._clean_nav(text)
        self.assertNotIn("Login About", cleaned)
        self.assertIn("great agency", cleaned)

    def test_truncates_to_limit(self):
        text = "x" * 5000
        cleaned = copyengine._clean_nav(text, limit=100)
        self.assertEqual(len(cleaned), 100)


class TestAssetsAvailable(unittest.TestCase):
    """Assets reported to the strategy stage."""

    def test_with_capabilities(self):
        config = _config()
        assets = copyengine._assets_available(config)
        self.assertIn("project_management", assets)
        self.assertIn("productive", assets.lower())

    def test_empty_config(self):
        assets = copyengine._assets_available({})
        self.assertIn("no assets", assets)


if __name__ == "__main__":
    unittest.main()
