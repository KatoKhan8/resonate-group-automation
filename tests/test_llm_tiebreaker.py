"""TASK-267: the LLM tiebreaker for FLAGGED domains.

Tests the script module at `scripts/stage_s3_llm_tiebreaker.py`. The model is
ALWAYS faked - no live call in tests. Covers:

- No-company-data population excluded and counted apart
- Domain the model cannot answer keeps its original verdict
- Cost report prints ESTIMATED_ONLY when only expected cost is available
- No model configured refuses loudly
- SET diff asserts LOST is zero
- Reason must be grounded in evidence, not a verdict restatement (TASK-272)
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

from src import llm


def _load_tiebreaker_module():
    """Load the script module without importing it as a package."""
    script = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          "scripts", "stage_s3_llm_tiebreaker.py")
    spec = importlib.util.spec_from_file_location("tiebreaker", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeModel:
    """A model that returns scripted answers and records calls."""
    name = "fake"

    def __init__(self, answers=None):
        self.answers = list(answers or [])
        self.calls = []
        self._call_count = 0

    def complete(self, prompt, temperature=0, client=None, config=None):
        self._call_count += 1
        self.calls.append({
            "model": "fake-model",
            "seconds": 0.1,
            "chars": 100,
            "prompt_tokens": 200,
            "completion_tokens": 50,
            "total_tokens": 250,
        })
        if not self.answers:
            raise llm.ModelError("fake model out of answers")
        ans = self.answers.pop(0)
        if isinstance(ans, Exception):
            raise ans
        return ans if isinstance(ans, str) else json.dumps(ans)


class TestIsJudgeable(unittest.TestCase):
    """The no-company-data population is excluded from judging."""

    def setUp(self):
        self.mod = _load_tiebreaker_module()

    def test_flagged_with_evidence_is_judgeable(self):
        row = {"verdict": "flagged",
               "reason": "headcount not judged (2026-09-22 amendment), "
                         "geo not confirmed",
               "domain": "example.test"}
        self.assertTrue(self.mod.is_judgeable(row))

    def test_no_company_data_is_not_judgeable(self):
        row = {"verdict": "flagged",
               "reason": "provider returned no company for this domain",
               "domain": "empty.test"}
        self.assertFalse(self.mod.is_judgeable(row))

    def test_in_verdict_is_not_judgeable(self):
        row = {"verdict": "in", "reason": "headcount 50, geo matched",
               "domain": "good.test"}
        self.assertFalse(self.mod.is_judgeable(row))

    def test_out_verdict_is_not_judgeable(self):
        row = {"verdict": "out", "reason": "excluded geo: India",
               "domain": "bad.test"}
        self.assertFalse(self.mod.is_judgeable(row))


class TestParseResponse(unittest.TestCase):
    """The model's answer must be strict JSON with the right shape."""

    def setUp(self):
        self.mod = _load_tiebreaker_module()

    def test_valid_response(self):
        text = json.dumps({"verdict": "in", "confidence": "high",
                           "reason": "50 employees in Germany, marketing agency"})
        data, err = self.mod.parse_response(text)
        self.assertIsNone(err)
        self.assertEqual(data["verdict"], "in")
        self.assertEqual(data["confidence"], "high")

    def test_fenced_json(self):
        text = '```json\n{"verdict": "out", "confidence": "low",\n "reason": "too small"}\n```'
        data, err = self.mod.parse_response(text)
        self.assertIsNone(err)
        self.assertEqual(data["verdict"], "out")

    def test_invalid_verdict_rejected(self):
        text = json.dumps({"verdict": "maybe", "confidence": "high",
                           "reason": "unsure"})
        data, err = self.mod.parse_response(text)
        self.assertIsNotNone(err)
        self.assertIn("verdict", err)

    def test_invalid_confidence_rejected(self):
        text = json.dumps({"verdict": "in", "confidence": "certain",
                           "reason": "fits"})
        data, err = self.mod.parse_response(text)
        self.assertIsNotNone(err)
        self.assertIn("confidence", err)

    def test_empty_reason_rejected(self):
        text = json.dumps({"verdict": "in", "confidence": "high",
                           "reason": ""})
        data, err = self.mod.parse_response(text)
        self.assertIsNotNone(err)
        self.assertIn("reason", err)

    def test_invalid_json_rejected(self):
        data, err = self.mod.parse_response("not json at all")
        self.assertIsNotNone(err)
        self.assertIn("invalid JSON", err)


class TestValidateReason(unittest.TestCase):
    """TASK-272: reason must be grounded in evidence, not a verdict restatement."""

    def setUp(self):
        self.mod = _load_tiebreaker_module()

    def test_tautological_in_reason_rejected(self):
        data = {"verdict": "in", "confidence": "high",
                "reason": "fits the criteria"}
        row = {"domain": "test.test", "employees": 50}
        valid, err = self.mod.validate_reason(data, row)
        self.assertFalse(valid)

    def test_tautological_out_reason_rejected(self):
        data = {"verdict": "out", "confidence": "high",
                "reason": "does not fit"}
        row = {"domain": "test.test", "employees": 5}
        valid, err = self.mod.validate_reason(data, row)
        self.assertFalse(valid)

    def test_grounded_reason_accepted(self):
        data = {"verdict": "in", "confidence": "medium",
                "reason": "50-person marketing agency in Germany fits the "
                          "agency-focused ICP"}
        row = {"domain": "test.test", "employees": 50,
               "country": "Germany", "industry": "Marketing"}
        valid, err = self.mod.validate_reason(data, row)
        self.assertTrue(valid)


class TestCostReport(unittest.TestCase):
    """Cost report prints ESTIMATED_ONLY when only expected cost is available."""

    def setUp(self):
        self.mod = _load_tiebreaker_module()

    def test_estimated_only_when_calls_present(self):
        model = FakeModel(answers=[
            {"verdict": "in", "confidence": "high",
             "reason": "50 employees in Germany"}
        ])
        model.complete("test prompt")
        report = self.mod.cost_report(model, 1)
        self.assertEqual(report["status"], "ESTIMATED_ONLY")
        self.assertEqual(report["calls"], 1)
        self.assertEqual(report["total_tokens"], 250)

    def test_no_calls_made(self):
        model = FakeModel()
        report = self.mod.cost_report(model, 0)
        self.assertEqual(report["status"], "NO_CALLS_MADE")

    def test_unknown_tokens_when_missing(self):
        model = FakeModel()
        model.calls.append({
            "model": "fake", "seconds": 0.1, "chars": 50,
        })
        report = self.mod.cost_report(model, 1)
        self.assertEqual(report["status"], "ESTIMATED_ONLY")
        self.assertEqual(report["total_tokens"], llm.UNKNOWN)


class TestNoModelRefuses(unittest.TestCase):
    """A run with no model configured refuses loudly rather than silently
    judging nothing."""

    def setUp(self):
        self.mod = _load_tiebreaker_module()
        self._tmpdir = tempfile.mkdtemp(prefix="tiebreaker-test-")
        self._amended = os.path.join(self._tmpdir, "amended.jsonl")
        self._output = os.path.join(self._tmpdir, "tiebreaker.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_journal(self, rows):
        with open(self._amended, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_no_model_with_live_refuses(self):
        self._write_journal([
            {"domain": "a.test", "verdict": "flagged",
             "reason": "headcount not judged, geo not confirmed",
             "employees": 50, "country": "Germany",
             "industry": "Marketing"},
        ])
        orig_amended = self.mod.AMENDED
        orig_output = self.mod.OUTPUT
        self.mod.AMENDED = self._amended
        self.mod.OUTPUT = self._output
        real_from_env = llm.from_env
        try:
            llm.from_env = lambda: llm.NoModel()
            rc = self.mod.main(["--live"])
            self.assertEqual(rc, 1)
        finally:
            llm.from_env = real_from_env
            self.mod.AMENDED = orig_amended
            self.mod.OUTPUT = orig_output

    def test_dry_run_does_not_call_model(self):
        self._write_journal([
            {"domain": "a.test", "verdict": "flagged",
             "reason": "headcount not judged, geo not confirmed",
             "employees": 50, "country": "Germany",
             "industry": "Marketing"},
        ])
        orig_amended = self.mod.AMENDED
        orig_output = self.mod.OUTPUT
        self.mod.AMENDED = self._amended
        self.mod.OUTPUT = self._output
        try:
            rc = self.mod.main([])
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(self._output))
        finally:
            self.mod.AMENDED = orig_amended
            self.mod.OUTPUT = orig_output


class TestSetDiffLostIsZero(unittest.TestCase):
    """The SET diff asserts LOST is zero: the tiebreaker does not invent
    domains that were not in the FLAGGED judgeable set."""

    def setUp(self):
        self.mod = _load_tiebreaker_module()

    def test_no_lost_when_tiebreaker_stays_within_flagged(self):
        all_rows = [
            {"domain": "a.test", "verdict": "flagged",
             "reason": "headcount not judged, geo not confirmed"},
            {"domain": "b.test", "verdict": "in",
             "reason": "headcount 50, geo matched"},
            {"domain": "c.test", "verdict": "flagged",
             "reason": "provider returned no company for this domain"},
        ]
        tiebreaker = {
            "a.test": {"domain": "a.test", "verdict": "in"},
        }
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.mod._print_set_diff(all_rows, tiebreaker, no_company_count=1)
        output = buf.getvalue()
        self.assertIn("LOST (must be zero)", output)
        self.assertIn("0", output.split("LOST (must be zero)")[1][:20])

    def test_lost_detected_when_tiebreaker_judges_non_flagged(self):
        all_rows = [
            {"domain": "a.test", "verdict": "flagged",
             "reason": "headcount not judged, geo not confirmed"},
        ]
        tiebreaker = {
            "a.test": {"domain": "a.test", "verdict": "in"},
            "z.test": {"domain": "z.test", "verdict": "out"},
        }
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.mod._print_set_diff(all_rows, tiebreaker, no_company_count=0)
        output = buf.getvalue()
        lost_line = [l for l in output.split("\n")
                     if "LOST" in l][0]
        self.assertNotIn("0", lost_line.split("LOST (must be zero)")[1][:5].strip())


class TestModelFailureKeepsOriginal(unittest.TestCase):
    """A domain the model does not answer for keeps its original verdict
    rather than defaulting to one."""

    def setUp(self):
        self.mod = _load_tiebreaker_module()
        self._tmpdir = tempfile.mkdtemp(prefix="tiebreaker-test-")
        self._amended = os.path.join(self._tmpdir, "amended.jsonl")
        self._output = os.path.join(self._tmpdir, "tiebreaker.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_journal(self, rows):
        with open(self._amended, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_model_error_keeps_original_verdict(self):
        """When the model raises ModelError, the domain is NOT written to
        the tiebreaker journal - it keeps its FLAGGED verdict."""
        self._write_journal([
            {"domain": "fail.test", "verdict": "flagged",
             "reason": "headcount not judged, geo not confirmed",
             "employees": 50, "country": "Germany",
             "industry": "Marketing"},
        ])
        orig_amended = self.mod.AMENDED
        orig_output = self.mod.OUTPUT
        self.mod.AMENDED = self._amended
        self.mod.OUTPUT = self._output

        real_from_env = llm.from_env
        model = FakeModel(answers=[llm.ModelError("upstream timeout")])
        try:
            llm.from_env = lambda: model
            rc = self.mod.main(["--live"])
            self.assertEqual(rc, 0)
            decided = self.mod.decided()
            self.assertNotIn("fail.test", decided)
        finally:
            llm.from_env = real_from_env
            self.mod.AMENDED = orig_amended
            self.mod.OUTPUT = orig_output

    def test_model_unavailable_keeps_original_verdict(self):
        """ModelUnavailable is a fact about us, not the record."""
        self._write_journal([
            {"domain": "unavail.test", "verdict": "flagged",
             "reason": "headcount not judged, geo not confirmed",
             "employees": 30, "country": "France",
             "industry": "Software"},
        ])
        orig_amended = self.mod.AMENDED
        orig_output = self.mod.OUTPUT
        self.mod.AMENDED = self._amended
        self.mod.OUTPUT = self._output

        real_from_env = llm.from_env
        model = FakeModel(answers=[llm.ModelUnavailable("429 rate limit")])
        try:
            llm.from_env = lambda: model
            rc = self.mod.main(["--live"])
            self.assertEqual(rc, 0)
            decided = self.mod.decided()
            self.assertNotIn("unavail.test", decided)
        finally:
            llm.from_env = real_from_env
            self.mod.AMENDED = orig_amended
            self.mod.OUTPUT = orig_output


class TestNoCompanyDataExcluded(unittest.TestCase):
    """The no-company-data population is excluded from judging and counted
    apart in the output."""

    def setUp(self):
        self.mod = _load_tiebreaker_module()
        self._tmpdir = tempfile.mkdtemp(prefix="tiebreaker-test-")
        self._amended = os.path.join(self._tmpdir, "amended.jsonl")
        self._output = os.path.join(self._tmpdir, "tiebreaker.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_journal(self, rows):
        with open(self._amended, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_no_company_domain_never_judged(self):
        """A domain with 'provider returned no company' is never sent to
        the model, even with --live."""
        self._write_journal([
            {"domain": "empty.test", "verdict": "flagged",
             "reason": "provider returned no company for this domain",
             "employees": None, "country": None, "industry": None},
            {"domain": "real.test", "verdict": "flagged",
             "reason": "headcount not judged, geo not confirmed",
             "employees": 40, "country": "Poland",
             "industry": "Marketing"},
        ])
        orig_amended = self.mod.AMENDED
        orig_output = self.mod.OUTPUT
        self.mod.AMENDED = self._amended
        self.mod.OUTPUT = self._output

        real_from_env = llm.from_env
        model = FakeModel(answers=[
            {"verdict": "in", "confidence": "medium",
             "reason": "40-person marketing agency in Poland"}
        ])
        try:
            llm.from_env = lambda: model
            rc = self.mod.main(["--live"])
            self.assertEqual(rc, 0)
            decided = self.mod.decided()
            self.assertNotIn("empty.test", decided)
            self.assertIn("real.test", decided)
            self.assertEqual(model._call_count, 1)
        finally:
            llm.from_env = real_from_env
            self.mod.AMENDED = orig_amended
            self.mod.OUTPUT = orig_output


if __name__ == "__main__":
    unittest.main()
