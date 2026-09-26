"""A model call writes a priced ledger row, and a ceiling can fire.

TASK-323: model spend was invisible to the ledger. Every model call must
write a row through `spendledger.record(..., unit="microusd")`. This test
proves three things:

1. A GLM call writes a row with the correct unit and a priced cost.
2. An Anthropic call (through llm.OpenAICompatibleModel) writes a row.
3. A ceiling can NOW actually fire: set the anthropic per_day ceiling below
   the next call's cost, and `spendledger.check` REFUSES.

No live model call. No provider write. Fixture responses only.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import spendledger, store, modelprices               # noqa: E402


# A fixture GLM response, shaped exactly as the API answers.
GLM_FIXTURE = {
    "model": "glm-5.3",
    "choices": [{"message": {"content": "the answer"},
                 "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50,
              "total_tokens": 150},
    "request_id": "test-req-1",
}

# A fixture Anthropic-style response (OpenAI-compatible shape).
ANTHROPIC_FIXTURE = {
    "model": "claude-sonnet-4-20250514",
    "choices": [{"message": {"content": "the answer"},
                 "finish_reason": "end_turn"}],
    "usage": {"prompt_tokens": 200, "completion_tokens": 100,
              "total_tokens": 300},
}


class IsolatedLedger(unittest.TestCase):
    """A disposable ledger, a fresh run, no holds carried between tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-model-spend-")
        self.addCleanup(store.use_directory(self.tmp))
        spendledger._HOLDS.clear()
        self.addCleanup(spendledger._HOLDS.clear)
        self.run_id = spendledger.new_run(f"test-{id(self)}")
        modelprices.reload()


class GlmWritesALedgerRow(IsolatedLedger):

    def test_a_priced_row_is_written_after_a_fixture_call(self):
        """glm.complete() with a fixture response writes a microusd row."""
        from src.providers import glm

        # Patch _send to return the fixture without touching the wire.
        real_send = glm._send
        glm._send = lambda body, timeout, max_attempts, sleep: (
            200, GLM_FIXTURE, 0.123)
        self.addCleanup(setattr, glm, "_send", real_send)

        n0 = len(spendledger.load())
        result = glm.complete("hello", ledger_client="test-client")

        rows = spendledger.load()
        new_rows = rows[n0:]
        self.assertTrue(new_rows, "glm.complete wrote no ledger row")

        row = new_rows[0]
        self.assertEqual(row["provider"], "glm")
        self.assertEqual(row["unit"], "microusd")
        self.assertIsInstance(row["expected_cost"], int)
        self.assertGreater(row["expected_cost"], 0,
                           "glm-5.3 is priced but the row says zero")
        self.assertEqual(row["client"], "test-client")

    def test_an_unpriced_model_still_writes_a_row(self):
        """A model absent from model-prices.yaml gets cost=0, not no row."""
        from src.providers import glm

        # _record_spend is the seam. All MODELS entries are priced, so an
        # unpriced model cannot reach it through complete() - which is the
        # correct behaviour (unknown models are refused before a round trip).
        # Test the seam directly to prove the contract.
        n0 = len(spendledger.load())
        glm._record_spend("glm-99-future", {"prompt_tokens": 50,
                                             "completion_tokens": 25},
                          "test-client")

        rows = spendledger.load()
        new_rows = rows[n0:]
        self.assertTrue(new_rows, "unpriced model wrote no ledger row")
        row = new_rows[0]
        self.assertEqual(row["expected_cost"], 0)
        self.assertEqual(row["unit"], "microusd")
        self.assertEqual(row["provider"], "glm")


class AnthropicWritesALedgerRow(IsolatedLedger):

    def test_anthropic_call_writes_a_priced_row(self):
        """OpenAICompatibleModel pointed at Anthropic writes a microusd row."""
        from src import llm

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        # Patch providers.request to return the fixture.
        from src import providers
        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        n0 = len(spendledger.load())
        model.complete("hello")

        rows = spendledger.load()
        new_rows = rows[n0:]
        self.assertTrue(new_rows, "anthropic call wrote no ledger row")

        row = new_rows[0]
        self.assertEqual(row["provider"], "anthropic")
        self.assertEqual(row["unit"], "microusd")
        self.assertIsInstance(row["expected_cost"], int)
        self.assertGreater(row["expected_cost"], 0,
                           "claude-sonnet is priced but the row says zero")


class GroqWritesALedgerRow(IsolatedLedger):

    def test_groq_call_writes_a_priced_row(self):
        """OpenAICompatibleModel pointed at Groq writes a microusd row."""
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="openai/gpt-oss-120b",
            base="https://api.groq.com/openai/v1")

        fixture = {
            "model": "openai/gpt-oss-120b",
            "choices": [{"message": {"content": "the answer"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 500, "completion_tokens": 200,
                      "total_tokens": 700},
        }

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, fixture)
        self.addCleanup(setattr, providers, "request", real_request)

        n0 = len(spendledger.load())
        model.complete("hello")

        rows = spendledger.load()
        new_rows = rows[n0:]
        self.assertTrue(new_rows, "groq call wrote no ledger row")

        row = new_rows[0]
        self.assertEqual(row["provider"], "groq")
        self.assertEqual(row["unit"], "microusd")
        self.assertGreater(row["expected_cost"], 0)


class CeilingCanFire(IsolatedLedger):
    """THE POINT OF THE TASK. A ceiling can now actually fire.

    Set the anthropic per_day ceiling below the next call's cost, and
    `spendledger.check` REFUSES. A test that only asserts rows exist does
    not close this task.
    """

    def test_anthropic_ceiling_refuses_when_exceeded(self):
        """Set a $1 ceiling, spend $2 worth, check REFUSES the next call."""
        from src import llm, providers

        # Write one priced row so the ledger has spend on it.
        # claude-sonnet-4: $3/1M input, $15/1M output.
        # 200 input + 100 output = 600 + 1500 = 2100 micro-USD.
        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        model.complete("first call")

        rows = spendledger.load()
        anthropic_rows = [r for r in rows if r.get("provider") == "anthropic"]
        self.assertTrue(anthropic_rows, "no anthropic rows written")
        spent = anthropic_rows[0]["expected_cost"]
        self.assertGreater(spent, 0, "anthropic row has zero cost")

        # NOW set a ceiling BELOW what was already spent.
        # per_day = spent - 1, so the NEXT check must refuse.
        config = {"budget": {
            "per_day": 1_000_000,
            "providers": {
                "anthropic": {
                    "per_day": spent - 1,
                    "total": spendledger.UNLIMITED,
                },
            },
        }}

        # The next call should be refused by spendledger.check.
        with self.assertRaises(spendledger.BudgetExceeded) as ctx:
            spendledger.check(
                "_model", config, cost=spent,
                provider="anthropic",
                rows=spendledger.load())

        self.assertIn("PROVIDER CEILING", str(ctx.exception))
        self.assertIn("anthropic", str(ctx.exception))


class DollarsNeverReachExpectedCost(IsolatedLedger):

    def test_all_model_rows_are_microusd_with_int_cost(self):
        """No model row carries dollars in expected_cost."""
        from src.providers import glm
        from src import llm, providers

        # GLM row
        real_send = glm._send
        glm._send = lambda body, timeout, max_attempts, sleep: (
            200, GLM_FIXTURE, 0.1)
        self.addCleanup(setattr, glm, "_send", real_send)
        glm.complete("hello", ledger_client="test")

        # Anthropic row
        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-202505014",
            base="https://api.anthropic.com/v1")
        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)
        model.complete("hello")

        rows = [r for r in spendledger.load()
                if r.get("provider") in ("glm", "groq", "anthropic")]
        self.assertTrue(rows, "no model rows written")
        for row in rows:
            self.assertEqual(row.get("unit"), "microusd",
                             f"{row.get('provider')} row is not microusd")
            self.assertIsInstance(row["expected_cost"], int)
            self.assertFalse(
                0 < row["expected_cost"] < 1,
                f"dollars in expected_cost: {row['expected_cost']}")


class GlmUnitIsMicrousd(unittest.TestCase):

    def test_unit_for_glm_is_microusd(self):
        self.assertEqual(spendledger.unit_for("glm"), "microusd")

    def test_usd_estimate_for_microusd(self):
        u, rate, src = spendledger.usd_estimate(2560, "microusd")
        self.assertAlmostEqual(u, 0.00256, places=9)
        self.assertEqual(src, "unit_definition")


if __name__ == "__main__":
    unittest.main()
