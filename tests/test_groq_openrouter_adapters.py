"""Groq and OpenRouter adapter tests.  TASK-305.

Every test drives a hand-written stub through `providers.set_transport`. No
test reaches a real endpoint, spends a token, or touches a production path.

The subject is the contract: same shape as glm, spend ledger integration,
explicit refusal when the fallback key is absent, and the fallback wiring.
"""
import json
import os
import unittest

from src import providers, spendledger
from src.providers import groq, openrouter
from tests.base import ProviderTest

FAKE_GROQ_KEY = "gsk-fake-key-for-tests-only-0123456789"
FAKE_OR_KEY = "sk-or-fake-key-for-tests-only-0123456789"
GROQ_BASE = "https://api.groq.com/openai/v1"
OR_BASE = "https://openrouter.ai/api/v1"


def answer(content="OK", model="openai/gpt-oss-120b", finish="stop"):
    """One well-formed chat completion, shaped as Groq returns it."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20,
                  "total_tokens": 30},
    }


class Stub:
    """Plays a scripted list of outcomes."""

    def __init__(self, *script):
        self.script = list(script) or [(200, answer())]
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url,
                           "headers": dict(headers), "body": body,
                           "timeout": timeout})
        entry = self.script[min(len(self.calls) - 1, len(self.script) - 1)]
        if isinstance(entry, BaseException):
            raise entry
        status, payload = entry
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return status, text


class GroqAdapterTest(ProviderTest):
    def setUp(self):
        super().setUp()
        self.env = {groq.ENV_KEY: FAKE_GROQ_KEY,
                    groq.ENV_BASE: GROQ_BASE,
                    groq.ENV_MODEL: "openai/gpt-oss-120b"}
        self._saved = {k: os.environ.get(k) for k in self.env}
        self.addCleanup(self._restore_env, self._saved)
        os.environ.update(self.env)

    def play(self, *script):
        stub = Stub(*script)
        providers.set_transport(stub)
        self.stub = stub
        return stub


class TestGroqSucceeds(GroqAdapterTest):
    def test_the_request_is_bounded_and_addressed_to_chat_completions(self):
        self.play()
        result = groq.complete("hello")
        self.assertEqual(result["content"], "OK")
        self.assertEqual(result["model"], "openai/gpt-oss-120b")
        self.assertEqual(result["requested_model"], "openai/gpt-oss-120b")
        call = self.stub.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertTrue(call["url"].endswith("/chat/completions"))
        self.assertIn("Bearer", call["headers"]["Authorization"])

    def test_max_tokens_is_always_sent(self):
        self.play()
        groq.complete("hello")
        body = self.stub.calls[0]["body"]
        self.assertIn("max_tokens", body)
        self.assertLessEqual(body["max_tokens"], groq.MAX_TOKENS_CAP)

    def test_prompt_above_bound_is_refused_not_truncated(self):
        self.play()
        with self.assertRaises(ValueError) as ctx:
            groq.complete("x" * (groq.MAX_PROMPT_CHARS + 1))
        self.assertIn("Refusing rather than truncating", str(ctx.exception))

    def test_unknown_model_is_refused(self):
        self.play()
        with self.assertRaises(ValueError) as ctx:
            groq.complete("hello", model="no-such-model")
        self.assertIn("not in the allowlist", str(ctx.exception))

    def test_usage_is_read_from_the_response(self):
        self.play()
        result = groq.complete("hello")
        usage = result["usage"]
        self.assertEqual(usage["prompt_tokens"], 10)
        self.assertEqual(usage["completion_tokens"], 20)
        self.assertEqual(usage["total_tokens"], 30)

    def test_empty_completion_is_refused(self):
        self.play((200, answer(content="")))
        with self.assertRaises(groq.GroqMalformedResponse):
            groq.complete("hello")


class TestGroqFailures(GroqAdapterTest):
    def test_401_is_auth_not_retried(self):
        self.play((401, {"error": {"message": "bad key"}}))
        with self.assertRaises(groq.GroqAuthFailed) as ctx:
            groq.complete("hello")
        self.assertEqual(ctx.exception.classification, "auth")
        self.assertEqual(len(self.stub.calls), 1)

    def test_429_is_rate_limit_and_retried(self):
        self.play((429, {"error": {"message": "slow down"}}),
                  (200, answer()))
        result = groq.complete("hello")
        self.assertEqual(result["content"], "OK")
        self.assertEqual(len(self.stub.calls), 2)

    def test_500_is_server_error_and_retried(self):
        self.play((500, "internal"),
                  (200, answer()))
        result = groq.complete("hello")
        self.assertEqual(result["content"], "OK")

    def test_missing_key_raises_before_the_call(self):
        os.environ.pop(groq.ENV_KEY, None)
        self.play()
        with self.assertRaises(providers.MissingKey):
            groq.complete("hello")
        self.assertEqual(len(self.stub.calls), 0)


class TestGroqLedgerIntegration(GroqAdapterTest):
    def test_a_successful_call_writes_a_ledger_row(self):
        """The spend ledger must see every call.  A call that skips the
        ledger is invisible to the spend audit."""
        self.play()
        before = len(spendledger.load())
        groq.complete("hello")
        after = len(spendledger.load())
        rows = [r for r in spendledger.load()
                if r.get("provider") == "groq"]
        self.assertGreaterEqual(len(rows), 1,
                                "no ledger row for a successful groq call")

    def test_a_failed_call_writes_no_ledger_row(self):
        """A call that never answered must not ledger spend."""
        os.environ.pop(groq.ENV_KEY, None)
        self.play()
        before = len([r for r in spendledger.load()
                      if r.get("provider") == "groq"])
        with self.assertRaises(providers.MissingKey):
            groq.complete("hello")
        after = len([r for r in spendledger.load()
                     if r.get("provider") == "groq"])
        self.assertEqual(before, after,
                         "a failed call should not write a ledger row")


class TestGroqCheck(GroqAdapterTest):
    def test_check_without_live_reports_configured(self):
        r = groq.check(live=False)
        self.assertIsNone(r["ok"])
        self.assertTrue(r.get("skipped"))
        self.assertIn("configured", r["note"])

    def test_check_without_live_reports_missing_key(self):
        os.environ.pop(groq.ENV_KEY, None)
        r = groq.check(live=False)
        self.assertFalse(r["ok"])
        self.assertIn("GROQ_API_KEY", r["note"])


# --------------------------------------------------------------- OpenRouter

class OpenRouterAdapterTest(ProviderTest):
    def setUp(self):
        super().setUp()
        self._saved_or = os.environ.get("OPENROUTER_API_KEY")
        self._saved_llm = os.environ.get("LLM_API_KEY")
        self.addCleanup(self._restore_env, {
            "OPENROUTER_API_KEY": self._saved_or,
            "LLM_API_KEY": self._saved_llm,
        })

    def play(self, *script):
        stub = Stub(*script)
        providers.set_transport(stub)
        self.stub = stub
        return stub


class TestOpenRouterRefusesWithoutKey(OpenRouterAdapterTest):
    def test_complete_raises_missing_key_when_no_credential(self):
        """The fallback REFUSES explicitly when the key is absent.  A
        fallback that quietly is not there is the failure class this
        repository keeps finding."""
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("LLM_API_KEY", None)
        self.play()
        with self.assertRaises(providers.MissingKey):
            openrouter.complete("hello")
        self.assertEqual(len(self.stub.calls), 0,
                         "no call should be made without a key")

    def test_check_reports_missing_key(self):
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("LLM_API_KEY", None)
        r = openrouter.check(live=False)
        self.assertFalse(r["ok"])
        self.assertIn("OPENROUTER_API_KEY", r["note"])


class TestOpenRouterSucceeds(OpenRouterAdapterTest):
    def test_complete_with_key_sends_the_request(self):
        os.environ["OPENROUTER_API_KEY"] = FAKE_OR_KEY
        self.play()
        result = openrouter.complete("hello")
        self.assertEqual(result["content"], "OK")
        self.assertEqual(result["model"], "openai/gpt-oss-120b")
        call = self.stub.calls[0]
        self.assertTrue(call["url"].endswith("/chat/completions"))


# --------------------------------------------------------------- Fallback

class TestFallbackWiring(OpenRouterAdapterTest):
    def test_fallback_tries_groq_first(self):
        """When Groq has a key, the fallback uses it and never reaches
        OpenRouter."""
        os.environ[groq.ENV_KEY] = FAKE_GROQ_KEY
        os.environ[groq.ENV_BASE] = GROQ_BASE
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("LLM_API_KEY", None)
        self.play()
        result = groq.fallback_complete("hello")
        self.assertEqual(result["content"], "OK")
        self.assertEqual(len(self.stub.calls), 1)

    def test_fallback_raises_when_both_keys_missing(self):
        """When Groq has no key AND OpenRouter has no key, the fallback
        raises MissingKey - it does not silently succeed."""
        os.environ.pop(groq.ENV_KEY, None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("LLM_API_KEY", None)
        self.play()
        with self.assertRaises(providers.MissingKey):
            groq.fallback_complete("hello")


if __name__ == "__main__":
    unittest.main()
