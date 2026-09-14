#!/usr/bin/env python3
"""A real endpoint behind the existing seam, and no half-configured state.

`src/llm.py` defined the interface and shipped two offline implementations -
`NoModel`, which refuses, and `ScriptedModel`, which plays canned answers. There
was no transport to anything, so `LLM_API_KEY` had been declared in `config.py`
and read by nothing, and no record in the estate carried a generated step.

`OpenAICompatibleModel` speaks `/chat/completions`, which OpenRouter, OpenAI
itself and most local servers implement, so the vendor is three environment
variables rather than a code change. Proven live on 2026-09-11 against
OpenRouter: a completion in 0.7s.

Three properties this file exists to hold:

**All three variables or nothing.** A key with no endpoint is not a model.
`configured()` is the whole answer and `why_not()` names what is missing, so a
half-set environment fails with a sentence rather than a connection error.

**A credential never has to exist for tests to run.** Everything below either
constructs the adapter with explicit arguments or patches the transport, so the
offline harness stays honest: `providers.request` is the single HTTP seam, and
that is what `tests/offline.py` watches.

**Failure is loud.** A non-2xx, a body of the wrong shape, or an empty
completion raises `ModelError`. Returning "" would be parsed as invalid JSON,
retried three times by `ask`, and reported as a schema failure - sending the
reader to the wrong problem entirely.
"""
import unittest
from unittest import mock

from src import llm, providers

BASE = "https://endpoint.test/v1"


def a_model(**over):
    fields = {"key": "not-a-real-key", "model": "vendor/model",
              "base": BASE}
    fields.update(over)
    return llm.OpenAICompatibleModel(**fields)


def a_response(text="hello", **usage):
    return (200, {"model": "vendor/model",
                  "choices": [{"message": {"content": text}}],
                  "usage": usage or {"total_tokens": 12}})


class ConfiguredMeansAllThree(unittest.TestCase):

    def test_all_three_present(self):
        self.assertTrue(a_model().configured())

    def test_a_key_with_no_endpoint_is_not_a_model(self):
        found = a_model(base="")
        self.assertFalse(found.configured())
        self.assertIn("LLM_BASE_URL", found.why_not())

    def test_an_endpoint_with_no_key_is_not_a_model(self):
        found = a_model(key="")
        self.assertFalse(found.configured())
        self.assertIn("LLM_API_KEY", found.why_not())

    def test_an_endpoint_with_no_model_named_is_not_a_model(self):
        found = a_model(model="")
        self.assertFalse(found.configured())
        self.assertIn("LLM_MODEL", found.why_not())

    def test_an_unconfigured_model_refuses_before_any_request(self):
        with mock.patch.object(providers, "request") as sent:
            with self.assertRaises(llm.ModelError):
                a_model(base="").complete("anything")
        self.assertFalse(sent.called, "it tried to call an endpoint it lacks")

    def test_from_env_falls_back_to_nomodel(self):
        """So a credential sitting in the environment never silently turns a
        dry run into a paid one - a caller still has to pass a model."""
        with mock.patch.object(providers, "load_env", return_value={}), \
             mock.patch("os.path.isfile", return_value=False), \
             mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsInstance(llm.from_env(), llm.NoModel)


class ACompletionComesBackAsText(unittest.TestCase):

    def test_the_message_content_is_returned(self):
        with mock.patch.object(providers, "request", return_value=a_response("ok")):
            self.assertEqual(a_model().complete("hi"), "ok")

    def test_it_posts_to_the_chat_completions_path(self):
        with mock.patch.object(providers, "request",
                               return_value=a_response()) as sent:
            a_model().complete("hi")
        method, url = sent.call_args[0][0], sent.call_args[0][1]
        self.assertEqual(method, "POST")
        self.assertEqual(url, f"{BASE}/chat/completions")

    def test_the_prompt_travels_as_a_user_message(self):
        with mock.patch.object(providers, "request",
                               return_value=a_response()) as sent:
            a_model().complete("the prompt")
        body = sent.call_args[0][3]
        self.assertEqual(body["messages"], [{"role": "user",
                                             "content": "the prompt"}])
        self.assertEqual(body["model"], "vendor/model")

    def test_usage_is_recorded_without_the_credential(self):
        with mock.patch.object(providers, "request",
                               return_value=a_response(total_tokens=42,
                                                       prompt_tokens=30)):
            model = a_model()
            model.complete("hi")
        call = model.calls[0]
        self.assertEqual(call["total_tokens"], 42)
        self.assertEqual(call["prompt_tokens"], 30)
        self.assertNotIn("key", call)
        self.assertNotIn("not-a-real-key", str(call))

    def test_a_reported_cost_is_kept_and_an_absent_one_is_not_invented(self):
        """An endpoint that reports a charge is recorded; one that does not
        leaves the field absent, because absent is UNKNOWN and not zero."""
        with mock.patch.object(providers, "request",
                               return_value=a_response(cost=0.0004)):
            priced = a_model()
            priced.complete("hi")
        self.assertEqual(priced.calls[0]["cost"], 0.0004)
        with mock.patch.object(providers, "request", return_value=a_response()):
            silent = a_model()
            silent.complete("hi")
        self.assertNotIn("cost", silent.calls[0])


class FailureIsLoud(unittest.TestCase):

    def raises(self, response):
        with mock.patch.object(providers, "request", return_value=response):
            with self.assertRaises(llm.ModelError) as caught:
                a_model().complete("hi")
        return str(caught.exception)

    def test_a_non_2xx_raises_with_the_status(self):
        said = self.raises((402, {"error": {"message": "Insufficient credits"}}))
        self.assertIn("402", said)

    def test_a_body_that_is_not_an_object_raises(self):
        self.assertIn("not an object", self.raises((200, "a string")))

    def test_no_choices_raises(self):
        self.assertIn("no `choices`", self.raises((200, {"choices": []})))

    def test_an_empty_completion_raises_rather_than_returning_nothing(self):
        said = self.raises((200, {"choices": [{"message": {"content": "  "}}]}))
        self.assertIn("empty completion", said)

    def test_a_transport_exception_is_redacted(self):
        """An HTTP library quotes the request back, Authorization header and
        all. `providers.redact` is why that cannot reach a log."""
        boom = RuntimeError("failed sending Authorization: Bearer sekrit-value")
        with mock.patch.object(providers, "request", side_effect=boom):
            with self.assertRaises(llm.ModelError) as caught:
                a_model().complete("hi")
        self.assertNotIn("sekrit-value", str(caught.exception))


class TheSeamIsUnchanged(unittest.TestCase):
    """`ask` and every caller talk to `complete(prompt) -> str`. A new
    implementation that did not fit would be a second model layer."""

    def test_it_satisfies_the_same_contract_as_the_stubs(self):
        for model in (llm.NoModel(), llm.ScriptedModel("x"), a_model()):
            self.assertTrue(callable(getattr(model, "complete", None)))
            self.assertTrue(getattr(model, "name", None))

    def test_ask_drives_it_like_any_other_model(self):
        """The whole point of fitting the seam: `ask` validates, retries and
        feeds errors back without knowing which implementation it holds."""
        answer = '{"note": "hello, worth a word?"}'
        with mock.patch.object(providers, "request",
                               return_value=a_response(answer)):
            data, attempts, errors = llm.ask(a_model(), "linkedin_note",
                                             "prompt")
        self.assertEqual(data["note"], "hello, worth a word?")
        self.assertEqual(attempts, 1)
        self.assertEqual(errors, [])

    def test_ask_retries_a_bad_answer_and_feeds_the_error_back(self):
        """Two responses: the first unusable, the second correct. The retry
        loop is the reason a flaky endpoint is survivable."""
        bad = a_response("not json at all")
        good = a_response('{"note": "second time"}')
        with mock.patch.object(providers, "request", side_effect=[bad, good]):
            data, attempts, errors = llm.ask(a_model(), "linkedin_note",
                                             "prompt")
        self.assertEqual(data["note"], "second time")
        self.assertEqual(attempts, 2)
        self.assertTrue(errors, "the first failure was not fed back")


if __name__ == "__main__":
    unittest.main()
