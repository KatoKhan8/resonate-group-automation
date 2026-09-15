#!/usr/bin/env python3
"""The AI spend ledger records model calls durably, without leaking PII.

TASK-151. The question: "What did Productive cost us in AI today, and
which stages spent it?" The answer lives in a JSONL file beside the
provider spend ledger, with every record id hashed and no prompt
contents anywhere.

These tests verify the writer without calling a model. The writer is
a pure function of observed values — the model call already happened,
the tokens are counted, the cost is known. The writer persists that.

What these tests prove:
- Every row is valid JSON with the required fields.
- Record ids are hashed; raw ids never touch the file.
- No prompt contents appear in any row.
- Cost defaults to 0 with source "unknown" when not provided.
- OpenRouter-reported cost is preserved as-is.
- Price table estimation computes correctly.
- The report aggregates by stage and model.
- The ledger is append-only; two writes produce two rows.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.task151_ai_spend_writer import (
    estimate_cost,
    hash_record_id,
    ledger_path,
    load_ledger,
    record_call,
    report,
)


class HashRecordIdTests(unittest.TestCase):
    """Raw identifiers never touch the ledger file."""

    def test_hash_is_deterministic(self):
        self.assertEqual(hash_record_id("16kagency-com"),
                         hash_record_id("16kagency-com"))

    def test_hash_is_truncated(self):
        h = hash_record_id("some-record-id")
        self.assertEqual(len(h), 16)

    def test_hash_is_hex(self):
        h = hash_record_id("some-record-id")
        int(h, 16)

    def test_different_ids_produce_different_hashes(self):
        self.assertNotEqual(hash_record_id("record-a"),
                            hash_record_id("record-b"))

    def test_none_returns_none(self):
        self.assertIsNone(hash_record_id(None))

    def test_empty_returns_none(self):
        self.assertIsNone(hash_record_id(""))


class RecordCallTests(unittest.TestCase):
    """One row per call, appended to a JSONL file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="task151-test-")
        self.ledger = os.path.join(self.tmpdir, "ai-spend.jsonl")

    def tearDown(self):
        try:
            os.remove(self.ledger)
        except FileNotFoundError:
            pass
        os.rmdir(self.tmpdir)

    def _read_rows(self):
        with open(self.ledger, "r", encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def test_writes_valid_json(self):
        record_call(
            client="test-client", stage="draft", path=self.ledger,
            model="anthropic/claude-3.5-sonnet",
            input_tokens=100, output_tokens=50,
        )
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["client"], "test-client")
        self.assertEqual(rows[0]["stage"], "draft")

    def test_record_id_is_hashed(self):
        record_call(
            client="test-client", stage="hook", record_id="16kagency-com",
            path=self.ledger,
        )
        rows = self._read_rows()
        stored = rows[0]["record_id"]
        self.assertIsNotNone(stored)
        self.assertEqual(len(stored), 16)
        self.assertNotEqual(stored, "16kagency-com")
        self.assertEqual(stored, hash_record_id("16kagency-com"))

    def test_no_prompt_contents(self):
        """The writer never receives or writes prompt text."""
        row = record_call(
            client="test-client", stage="draft", path=self.ledger,
            model="test-model", input_tokens=100, output_tokens=50,
        )
        keys = set(row.keys())
        for forbidden in ("prompt", "prompt_text", "content", "body",
                          "subject", "note", "hook"):
            self.assertNotIn(forbidden, keys,
                             f"ledger row must not contain '{forbidden}'")

    def test_cost_defaults_to_zero_when_unknown(self):
        row = record_call(
            client="test-client", stage="draft", path=self.ledger,
        )
        self.assertEqual(row["estimated_cost"], 0)
        self.assertEqual(row["cost_source"], "unknown")

    def test_openrouter_reported_cost_preserved(self):
        row = record_call(
            client="test-client", stage="draft", path=self.ledger,
            cost=0.00891,
        )
        self.assertAlmostEqual(row["estimated_cost"], 0.00891, places=6)
        self.assertEqual(row["cost_source"], "openrouter_reported")

    def test_explicit_cost_source_overrides_default(self):
        row = record_call(
            client="test-client", stage="draft", path=self.ledger,
            cost=0.005, cost_source="price_table",
            price_table_version="openrouter-2026-09-15",
        )
        self.assertEqual(row["cost_source"], "price_table")
        self.assertEqual(row["price_table_version"], "openrouter-2026-09-15")

    def test_append_only(self):
        record_call(client="c", stage="draft", path=self.ledger)
        record_call(client="c", stage="hook", path=self.ledger)
        rows = self._read_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["stage"], "draft")
        self.assertEqual(rows[1]["stage"], "hook")

    def test_day_is_extracted_from_timestamp(self):
        row = record_call(
            client="c", stage="draft", path=self.ledger,
            at="2026-09-15T14:23:01+00:00",
        )
        self.assertEqual(row["day"], "2026-09-15")

    def test_task_defaults_to_stage(self):
        row = record_call(
            client="c", stage="draft", path=self.ledger,
        )
        self.assertEqual(row["task"], "draft")

    def test_explicit_task(self):
        row = record_call(
            client="c", stage="draft", task="generate.draft",
            path=self.ledger,
        )
        self.assertEqual(row["task"], "generate.draft")

    def test_latency_rounded(self):
        row = record_call(
            client="c", stage="draft", path=self.ledger,
            latency=2.341567,
        )
        self.assertEqual(row["latency"], 2.342)

    def test_cache_hit_derived_from_cached_tokens(self):
        row = record_call(
            client="c", stage="draft", path=self.ledger,
            cached_tokens=500,
        )
        self.assertTrue(row["cache_hit"])
        self.assertEqual(row["cached_tokens"], 500)

    def test_cache_hit_false_when_no_cached_tokens(self):
        row = record_call(
            client="c", stage="draft", path=self.ledger,
            cached_tokens=0,
        )
        self.assertFalse(row["cache_hit"])

    def test_success_and_failure(self):
        record_call(client="c", stage="draft", path=self.ledger,
                     success=True)
        record_call(client="c", stage="draft", path=self.ledger,
                     success=False)
        rows = self._read_rows()
        self.assertTrue(rows[0]["success"])
        self.assertFalse(rows[1]["success"])

    def test_prompt_version_defaults_to_v1(self):
        row = record_call(client="c", stage="draft", path=self.ledger)
        self.assertEqual(row["prompt_version"], "v1")

    def test_all_required_fields_present(self):
        row = record_call(client="c", stage="draft", path=self.ledger)
        required = {"at", "day", "client", "stage", "task", "record_id",
                     "model", "provider", "prompt_version", "input_tokens",
                     "output_tokens", "cached_tokens", "latency",
                     "retry_count", "estimated_cost", "cost_source",
                     "price_table_version", "success", "cache_hit"}
        self.assertEqual(required, set(row.keys()))


class EstimateCostTests(unittest.TestCase):
    """Price table fallback when OpenRouter does not report cost."""

    def test_basic_calculation(self):
        price = {"input_per_1m": 3.0, "output_per_1m": 15.0}
        cost = estimate_cost(1000, 500, price)
        expected = (1000 * 3.0 / 1_000_000) + (500 * 15.0 / 1_000_000)
        self.assertAlmostEqual(cost, expected, places=8)

    def test_cached_tokens(self):
        price = {"input_per_1m": 3.0, "output_per_1m": 15.0,
                 "cached_input_per_1m": 0.30}
        cost = estimate_cost(1000, 500, price, cached_tokens=800)
        expected = ((1000 * 3.0 / 1_000_000) + (500 * 15.0 / 1_000_000)
                    + (800 * 0.30 / 1_000_000))
        self.assertAlmostEqual(cost, expected, places=8)

    def test_no_price_entry_returns_none(self):
        self.assertIsNone(estimate_cost(100, 50, None))

    def test_zero_tokens(self):
        price = {"input_per_1m": 3.0, "output_per_1m": 15.0}
        self.assertAlmostEqual(estimate_cost(0, 0, price), 0.0, places=8)


class ReportTests(unittest.TestCase):
    """The headline question: what did it cost, and which stages spent it."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="task151-report-")
        self.ledger = os.path.join(self.tmpdir, "ai-spend.jsonl")

    def tearDown(self):
        try:
            os.remove(self.ledger)
        except FileNotFoundError:
            pass
        os.rmdir(self.tmpdir)

    def _seed(self, rows):
        with open(self.ledger, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    def test_empty_ledger(self):
        result = report(path=self.ledger)
        self.assertEqual(result["total_calls"], 0)
        self.assertEqual(result["total_cost_usd"], 0)

    def test_total_cost(self):
        self._seed([
            {"day": "2026-09-15", "client": "a", "stage": "draft",
             "estimated_cost": 0.01, "success": True, "model": "m1",
             "input_tokens": 100, "output_tokens": 50},
            {"day": "2026-09-15", "client": "a", "stage": "hook",
             "estimated_cost": 0.005, "success": True, "model": "m1",
             "input_tokens": 50, "output_tokens": 25},
        ])
        result = report(path=self.ledger)
        self.assertAlmostEqual(result["total_cost_usd"], 0.015, places=6)
        self.assertEqual(result["total_calls"], 2)

    def test_by_stage(self):
        self._seed([
            {"day": "2026-09-15", "client": "a", "stage": "draft",
             "estimated_cost": 0.01, "success": True, "model": "m1",
             "input_tokens": 0, "output_tokens": 0},
            {"day": "2026-09-15", "client": "a", "stage": "draft",
             "estimated_cost": 0.02, "success": True, "model": "m1",
             "input_tokens": 0, "output_tokens": 0},
            {"day": "2026-09-15", "client": "a", "stage": "hook",
             "estimated_cost": 0.005, "success": True, "model": "m1",
             "input_tokens": 0, "output_tokens": 0},
        ])
        result = report(path=self.ledger)
        self.assertAlmostEqual(result["by_stage"]["draft"], 0.03, places=6)
        self.assertAlmostEqual(result["by_stage"]["hook"], 0.005, places=6)

    def test_by_model(self):
        self._seed([
            {"day": "2026-09-15", "client": "a", "stage": "draft",
             "estimated_cost": 0.01, "success": True,
             "model": "anthropic/claude-3.5-sonnet",
             "input_tokens": 0, "output_tokens": 0},
            {"day": "2026-09-15", "client": "a", "stage": "draft",
             "estimated_cost": 0.02, "success": True,
             "model": "openai/gpt-4",
             "input_tokens": 0, "output_tokens": 0},
        ])
        result = report(path=self.ledger)
        self.assertAlmostEqual(
            result["by_model"]["anthropic/claude-3.5-sonnet"], 0.01,
            places=6)
        self.assertAlmostEqual(result["by_model"]["openai/gpt-4"], 0.02,
                               places=6)

    def test_day_filter(self):
        self._seed([
            {"day": "2026-09-15", "client": "a", "stage": "draft",
             "estimated_cost": 0.01, "success": True, "model": "m1",
             "input_tokens": 0, "output_tokens": 0},
            {"day": "2026-09-14", "client": "a", "stage": "draft",
             "estimated_cost": 0.05, "success": True, "model": "m1",
             "input_tokens": 0, "output_tokens": 0},
        ])
        result = report(day="2026-09-15", path=self.ledger)
        self.assertEqual(result["total_calls"], 1)
        self.assertAlmostEqual(result["total_cost_usd"], 0.01, places=6)

    def test_client_filter(self):
        self._seed([
            {"day": "2026-09-15", "client": "productive", "stage": "draft",
             "estimated_cost": 0.01, "success": True, "model": "m1",
             "input_tokens": 0, "output_tokens": 0},
            {"day": "2026-09-15", "client": "other", "stage": "draft",
             "estimated_cost": 0.05, "success": True, "model": "m1",
             "input_tokens": 0, "output_tokens": 0},
        ])
        result = report(client="productive", path=self.ledger)
        self.assertEqual(result["total_calls"], 1)
        self.assertAlmostEqual(result["total_cost_usd"], 0.01, places=6)

    def test_success_and_failure_counts(self):
        self._seed([
            {"day": "2026-09-15", "client": "a", "stage": "draft",
             "estimated_cost": 0.01, "success": True, "model": "m1",
             "input_tokens": 0, "output_tokens": 0},
            {"day": "2026-09-15", "client": "a", "stage": "draft",
             "estimated_cost": 0.0, "success": False, "model": "m1",
             "input_tokens": 0, "output_tokens": 0},
        ])
        result = report(path=self.ledger)
        self.assertEqual(result["successes"], 1)
        self.assertEqual(result["failures"], 1)

    def test_token_totals(self):
        self._seed([
            {"day": "2026-09-15", "client": "a", "stage": "draft",
             "estimated_cost": 0.01, "success": True, "model": "m1",
             "input_tokens": 1000, "output_tokens": 500},
            {"day": "2026-09-15", "client": "a", "stage": "hook",
             "estimated_cost": 0.005, "success": True, "model": "m1",
             "input_tokens": 200, "output_tokens": 100},
        ])
        result = report(path=self.ledger)
        self.assertEqual(result["total_input_tokens"], 1200)
        self.assertEqual(result["total_output_tokens"], 600)


class LedgerPathTests(unittest.TestCase):
    """The ledger lives beside the provider spend ledger, or in temp."""

    def test_env_var_overrides(self):
        old = os.environ.get("AI_SPEND_LEDGER")
        try:
            os.environ["AI_SPEND_LEDGER"] = "/tmp/test-ai-spend.jsonl"
            self.assertEqual(ledger_path(), "/tmp/test-ai-spend.jsonl")
        finally:
            if old is None:
                os.environ.pop("AI_SPEND_LEDGER", None)
            else:
                os.environ["AI_SPEND_LEDGER"] = old


if __name__ == "__main__":
    unittest.main()
