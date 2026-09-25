"""TASK-305: Groq and OpenRouter adapter tests.

These tests verify the adapters refuse correctly when credentials are absent,
validate inputs properly, and integrate with spendledger.
"""
import os
import sys
import tempfile
import unittest

# Ensure the project root is on the path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.providers import groq, openrouter, MissingKey
from src import spendledger


class TestGroqAdapter(unittest.TestCase):
    """Groq adapter tests."""

    def test_refuses_without_key(self):
        """complete() raises MissingKey when GROQ_API_KEY is absent."""
        # Ensure the key is not set
        old = os.environ.pop("GROQ_API_KEY", None)
        try:
            with self.assertRaises(MissingKey):
                groq.complete("test prompt")
        finally:
            if old:
                os.environ["GROQ_API_KEY"] = old

    def test_refuses_empty_prompt(self):
        """Empty prompt is refused, never truncated."""
        with self.assertRaises(ValueError) as ctx:
            groq.complete("")
        self.assertIn("non-empty", str(ctx.exception))

    def test_refuses_oversized_prompt(self):
        """Prompt above MAX_PROMPT_CHARS is refused."""
        big = "x" * (groq.MAX_PROMPT_CHARS + 1)
        with self.assertRaises(ValueError) as ctx:
            groq.complete(big)
        self.assertIn("exceeds the bound", str(ctx.exception))

    def test_refuses_unknown_model(self):
        """Model not in MODELS is refused."""
        with self.assertRaises(ValueError) as ctx:
            groq.complete("test", model="not-a-real-model")
        self.assertIn("not in the allowlist", str(ctx.exception))

    def test_refuses_bad_temperature(self):
        """Temperature outside 0..1 is refused."""
        with self.assertRaises(ValueError) as ctx:
            groq.complete("test", temperature=2.0)
        self.assertIn("out of range", str(ctx.exception))

    def test_refuses_bad_reasoning_effort(self):
        """Unknown reasoning_effort is refused."""
        with self.assertRaises(ValueError) as ctx:
            groq.complete("test", reasoning_effort="extreme")
        self.assertIn("not in", str(ctx.exception))

    def test_default_reasoning_effort_is_low(self):
        """Default reasoning_effort is 'low' per the task."""
        self.assertEqual(groq.DEFAULT_REASONING_EFFORT, "low")

    def test_default_model_is_gpt_oss_120b(self):
        """Default model is openai/gpt-oss-120b per the task."""
        self.assertEqual(groq.DEFAULT_MODEL, "openai/gpt-oss-120b")

    def test_base_url_is_groq(self):
        """Base URL is https://api.groq.com/openai/v1."""
        self.assertEqual(groq.BASE_DEFAULT, "https://api.groq.com/openai/v1")


class TestOpenRouterAdapter(unittest.TestCase):
    """OpenRouter adapter tests."""

    def test_refuses_without_key(self):
        """complete() raises MissingKey when both keys are absent."""
        old_or = os.environ.pop("OPENROUTER_API_KEY", None)
        old_llm = os.environ.pop("LLM_API_KEY", None)
        try:
            with self.assertRaises(MissingKey):
                openrouter.complete("test prompt")
        finally:
            if old_or:
                os.environ["OPENROUTER_API_KEY"] = old_or
            if old_llm:
                os.environ["LLM_API_KEY"] = old_llm

    def test_refuses_empty_prompt(self):
        """Empty prompt is refused."""
        # Set a dummy key so we get past the auth check
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        try:
            with self.assertRaises(ValueError) as ctx:
                openrouter.complete("")
            self.assertIn("non-empty", str(ctx.exception))
        finally:
            os.environ.pop("OPENROUTER_API_KEY", None)

    def test_default_model_is_gpt_oss_120b(self):
        """Default model matches Groq's."""
        self.assertEqual(openrouter.DEFAULT_MODEL, "openai/gpt-oss-120b")

    def test_base_url_is_openrouter(self):
        """Base URL is https://openrouter.ai/api/v1."""
        self.assertEqual(openrouter.BASE_DEFAULT, "https://openrouter.ai/api/v1")


class TestSpendledgerIntegration(unittest.TestCase):
    """Spendledger metadata tests."""

    def test_record_accepts_metadata(self):
        """spendledger.record() accepts and stores metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = os.path.join(tmpdir, "test.jsonl")
            os.environ["SPEND_LEDGER"] = ledger_path
            try:
                row = spendledger.record(
                    "test-client", "groq", "complete", 0,
                    unit="microusd",
                    metadata={
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "served_model": "openai/gpt-oss-120b",
                    }
                )
                self.assertEqual(row["prompt_tokens"], 100)
                self.assertEqual(row["completion_tokens"], 50)
                self.assertEqual(row["served_model"], "openai/gpt-oss-120b")
                self.assertEqual(row["unit"], "microusd")
                self.assertEqual(row["provider"], "groq")
                self.assertEqual(row["client"], "test-client")

                # Verify it was written to disk
                rows = spendledger.load()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["prompt_tokens"], 100)
            finally:
                os.environ.pop("SPEND_LEDGER", None)

    def test_metadata_does_not_overwrite_standard_fields(self):
        """Metadata cannot overwrite standard row fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = os.path.join(tmpdir, "test.jsonl")
            os.environ["SPEND_LEDGER"] = ledger_path
            try:
                row = spendledger.record(
                    "test-client", "groq", "complete", 0,
                    metadata={"client": "hacker", "provider": "fake"}
                )
                # Standard fields win
                self.assertEqual(row["client"], "test-client")
                self.assertEqual(row["provider"], "groq")
            finally:
                os.environ.pop("SPEND_LEDGER", None)


if __name__ == "__main__":
    unittest.main()
