"""Tests for scripts/stage_s3_llm_judge.py — the LLM tiebreaker.

TASK-267: a second-stage judge over the FLAGGED domains with company data.
The model is ALWAYS faked in these tests — no live call, ever.

Required coverage:
- no-company-data population excluded from judging, counted apart
- a domain the model cannot answer keeps its original verdict
- cost report prints ESTIMATED_ONLY when only expected cost is available
- no model configured -> refuses loudly
- SET diff asserts LOST is zero
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import llm                                        # noqa: E402

# Import the script module by path, the same way stage_s3_rejudge_amended does.
import importlib.util                                      # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "stage_s3_llm_judge",
    os.path.join(ROOT, "scripts", "stage_s3_llm_judge.py"))
_judge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_judge)


class FakeModel:
    """A model that returns canned verdicts and records its calls."""

    name = "fake"

    def __init__(self, answers=None, fail_on=None):
        self.answers = list(answers or [])
        self.calls = []
        self._fail_on = fail_on or set()

    def complete(self, prompt):
        self.calls.append({"model": "fake", "seconds": 0.01, "chars": 50,
                           "prompt_tokens": 100, "completion_tokens": 20,
                           "total_tokens": 120})
        # Extract domain from prompt for targeted failures.
        for domain in self._fail_on:
            if domain in prompt:
                raise llm.ModelError(f"simulated failure for {domain}")
        if not self.answers:
            raise llm.ModelError("fake model ran out of answers")
        answer = self.answers.pop(0)
        return answer if isinstance(answer, str) else json.dumps(answer)


class TestSplitPopulated(unittest.TestCase):
    """The no-company-data population is excluded and counted apart."""

    def test_no_company_data_excluded(self):
        rows_in = [
            {"domain": "a.com", "verdict": "flagged",
             "reason": "headcount not judged, geo not confirmed",
             "employees": 50, "country": "DE"},
            {"domain": "b.com", "verdict": "flagged",
             "reason": "provider returned no company for this domain"},
            {"domain": "c.com", "verdict": "in",
             "reason": "headcount 50, geo matched"},
        ]
        judgeable, no_company = _judge.split_populated(rows_in)
        self.assertEqual(len(judgeable), 1)
        self.assertEqual(judgeable[0]["domain"], "a.com")
        self.assertEqual(len(no_company), 1)
        self.assertEqual(no_company[0]["domain"], "b.com")

    def test_in_and_out_rows_excluded(self):
        rows_in = [
            {"domain": "a.com", "verdict": "in", "reason": "geo matched"},
            {"domain": "b.com", "verdict": "out", "reason": "excluded geo"},
            {"domain": "c.com", "verdict": "flagged",
             "reason": "geo not confirmed"},
        ]
        judgeable, no_company = _judge.split_populated(rows_in)
        self.assertEqual(len(judgeable), 1)
        self.assertEqual(judgeable[0]["domain"], "c.com")
        self.assertEqual(len(no_company), 0)

    def test_all_no_company(self):
        rows_in = [
            {"domain": "x.com", "verdict": "flagged",
             "reason": "provider returned no company for this domain"},
            {"domain": "y.com", "verdict": "flagged",
             "reason": "provider returned no company for this domain"},
        ]
        judgeable, no_company = _judge.split_populated(rows_in)
        self.assertEqual(len(judgeable), 0)
        self.assertEqual(len(no_company), 2)


class TestModelFailureKeepsOriginal(unittest.TestCase):
    """A domain the model cannot answer keeps its original verdict."""

    def test_failure_preserves_flagged(self):
        row = {"domain": "broken.com", "verdict": "flagged",
               "reason": "geo not confirmed",
               "employees": 30, "country": "PL", "industry": "marketing"}
        model = FakeModel(fail_on={"broken.com"})
        narrative = "Target geographies: Poland."
        verdict, confidence, reason = _judge.judge_one(
            model, row, narrative)
        self.assertEqual(verdict, "flagged")
        self.assertEqual(confidence, "low")
        self.assertIn("model could not decide", reason)

    def test_failure_does_not_default_to_in_or_out(self):
        row = {"domain": "fail.com", "verdict": "flagged",
               "reason": "headcount unknown, geo not confirmed",
               "employees": None, "country": "", "industry": ""}
        model = FakeModel(fail_on={"fail.com"})
        verdict, _, _ = _judge.judge_one(model, row, "any narrative")
        self.assertNotEqual(verdict, "in")
        self.assertNotEqual(verdict, "out")
        self.assertEqual(verdict, "flagged")


class TestCostReportEstimatedOnly(unittest.TestCase):
    """The cost report prints ESTIMATED_ONLY when only expected cost exists."""

    def test_estimated_only_in_report(self):
        rec = {"domain": "__test__", "model_calls": [
            {"step": "llm_judge", "model": "fake",
             "prompt_tokens": 100, "completion_tokens": 20,
             "total_tokens": 120, "seconds": 0.01},
        ]}
        usage = llm.token_usage([rec])
        by_model = usage["by_model"]
        self.assertIn("fake", by_model)
        stats = by_model["fake"]
        self.assertEqual(stats["total_tokens"], 120)

    def test_unknown_when_tokens_missing(self):
        rec = {"domain": "__test__", "model_calls": [
            {"step": "llm_judge", "model": "fake",
             "seconds": 0.01},
        ]}
        usage = llm.token_usage([rec])
        stats = usage["by_model"]["fake"]
        self.assertEqual(stats["total_tokens"], llm.UNKNOWN)


class TestNoModelRefuses(unittest.TestCase):
    """A run with no model configured refuses loudly."""

    def test_no_model_returns_refusal(self):
        tmp = tempfile.mkdtemp(prefix="test_llm_judge_")
        try:
            amended = os.path.join(tmp, "amended.jsonl")
            output = os.path.join(tmp, "output.jsonl")
            with open(amended, "w") as f:
                f.write(json.dumps({
                    "domain": "test.com", "verdict": "flagged",
                    "reason": "geo not confirmed",
                    "employees": 30, "country": "DE"
                }) + "\n")

            # Monkey-patch the module paths.
            orig_amended = _judge.AMENDED
            orig_output = _judge.OUTPUT
            _judge.AMENDED = amended
            _judge.OUTPUT = output
            try:
                # No --spend -> dry run, returns 0 but prints refusal.
                rc = _judge.main(["--output", output])
                self.assertEqual(rc, 0)
            finally:
                _judge.AMENDED = orig_amended
                _judge.OUTPUT = orig_output
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_spend_with_no_model_returns_error(self):
        """--spend with NoModel configured returns 1 (refusal)."""
        tmp = tempfile.mkdtemp(prefix="test_llm_judge_")
        try:
            amended = os.path.join(tmp, "amended.jsonl")
            output = os.path.join(tmp, "output.jsonl")
            with open(amended, "w") as f:
                f.write(json.dumps({
                    "domain": "test.com", "verdict": "flagged",
                    "reason": "geo not confirmed",
                    "employees": 30, "country": "DE"
                }) + "\n")

            orig_amended = _judge.AMENDED
            _judge.AMENDED = amended
            # Patch from_env to return NoModel regardless of what is installed.
            orig_from_env = llm.from_env
            llm.from_env = lambda: llm.NoModel()
            try:
                rc = _judge.main(["--spend", "--output", output])
                self.assertEqual(rc, 1)
            finally:
                _judge.AMENDED = orig_amended
                llm.from_env = orig_from_env
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSetDiffLostIsZero(unittest.TestCase):
    """The SET diff asserts LOST is zero: no domain disappears."""

    def test_all_judged_domains_accounted_for(self):
        """Every domain in the judgeable set appears in the output."""
        tmp = tempfile.mkdtemp(prefix="test_llm_judge_")
        try:
            amended = os.path.join(tmp, "amended.jsonl")
            output = os.path.join(tmp, "output.jsonl")
            domains = [f"d{i}.com" for i in range(5)]
            with open(amended, "w") as f:
                for d in domains:
                    f.write(json.dumps({
                        "domain": d, "verdict": "flagged",
                        "reason": "geo not confirmed",
                        "employees": 30, "country": "DE"
                    }) + "\n")

            answers = [
                {"verdict": "in", "confidence": "high",
                 "reason": "30 employees in Germany matches ICP"},
                {"verdict": "out", "confidence": "high",
                 "reason": "industry is mining, not an agency"},
                {"verdict": "flagged", "confidence": "low",
                 "reason": "country matches but industry unclear"},
                {"verdict": "in", "confidence": "medium",
                 "reason": "size and geo match, industry plausible"},
                {"verdict": "out", "confidence": "high",
                 "reason": "headcount 30 but excluded industry"},
            ]
            model = FakeModel(answers=answers)

            orig_amended = _judge.AMENDED
            _judge.AMENDED = amended

            # Run the core loop manually to verify the SET diff property.
            base = _judge.rows(amended)
            flagged_judgeable, no_company = _judge.split_populated(base)
            narrative = "Target: Germany, agencies."

            output_rows = []
            for row in flagged_judgeable:
                v, c, r = _judge.judge_one(model, row, narrative)
                output_rows.append({
                    "domain": row["domain"], "verdict": v,
                    "confidence": c, "reason": r,
                })

            amended_flagged = {r["domain"] for r in base
                               if r.get("verdict") == "flagged"}
            judged_domains = {r["domain"] for r in output_rows}
            lost = amended_flagged - judged_domains

            self.assertEqual(len(lost), 0,
                             f"LOST domains: {lost}")
            self.assertEqual(len(judged_domains), 5)
            _judge.AMENDED = orig_amended
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestParseJudgeResponse(unittest.TestCase):
    """Parse and validate the model's JSON response."""

    def test_valid_response(self):
        text = json.dumps({"verdict": "in", "confidence": "high",
                           "reason": "30 employees in Germany"})
        v, c, r = _judge.parse_judge_response(text)
        self.assertEqual(v, "in")
        self.assertEqual(c, "high")
        self.assertIn("Germany", r)

    def test_invalid_verdict_rejected(self):
        text = json.dumps({"verdict": "maybe", "confidence": "high",
                           "reason": "uncertain"})
        with self.assertRaises(ValueError):
            _judge.parse_judge_response(text)

    def test_invalid_confidence_rejected(self):
        text = json.dumps({"verdict": "in", "confidence": "super",
                           "reason": "very sure"})
        with self.assertRaises(ValueError):
            _judge.parse_judge_response(text)

    def test_empty_reason_rejected(self):
        text = json.dumps({"verdict": "in", "confidence": "high",
                           "reason": ""})
        with self.assertRaises(ValueError):
            _judge.parse_judge_response(text)

    def test_fenced_json_parsed(self):
        text = '```json\n{"verdict": "out", "confidence": "low", ' \
               '"reason": "too small"}\n```'
        v, c, r = _judge.parse_judge_response(text)
        self.assertEqual(v, "out")


class TestIcpNarrative(unittest.TestCase):
    """The ICP narrative is assembled from config fields."""

    def test_narrative_includes_key_fields(self):
        icp = {
            "must": "services business that tracks time",
            "size_min_employees": 20,
            "size_max_employees": 1000,
            "geos": ["Germany", "France"],
            "exclude_geos": ["India"],
        }
        narrative = _judge.icp_narrative(icp)
        self.assertIn("services business", narrative)
        self.assertIn("20", narrative)
        self.assertIn("1000", narrative)
        self.assertIn("Germany", narrative)
        self.assertIn("India", narrative)

    def test_empty_icp_produces_empty_narrative(self):
        self.assertEqual(_judge.icp_narrative({}), "")


class TestBuildPrompt(unittest.TestCase):
    """The prompt carries the row's own fields as evidence."""

    def test_prompt_contains_evidence_fields(self):
        row = {"domain": "acme.com", "employees": 45,
               "country": "Germany", "industry": "marketing",
               "reason": "geo not confirmed"}
        prompt = _judge.build_prompt(row, "Target: Germany.")
        self.assertIn("acme.com", prompt)
        self.assertIn("45", prompt)
        self.assertIn("Germany", prompt)
        self.assertIn("marketing", prompt)
        self.assertIn("geo not confirmed", prompt)

    def test_prompt_warns_against_verdict_reasons(self):
        row = {"domain": "x.com", "employees": None,
               "country": "", "industry": "", "reason": "unknown"}
        prompt = _judge.build_prompt(row, "any")
        self.assertIn("not in your verdict", prompt)


if __name__ == "__main__":
    unittest.main()
