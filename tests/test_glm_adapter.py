"""Z.AI / GLM worker adapter tests.

Every test drives a hand-written stub through `providers.set_transport`. No
test reaches a real endpoint, spends a token, or touches a production path:
`ProviderTest` additionally booby-traps `urllib.request.urlopen`, so a route
around the seam fails loudly rather than quietly costing money.

The subject is the classification, not the happy path. An adapter that answers
is easy; an adapter that can tell a rate limit from an exhausted plan, and a
timeout from a refusal, is the part a worker pool would be built on top of.

`FAKE_KEY` is a string invented here. The real credential is never read by
this file, and `TestGlmKeepsTheKey` asserts that nothing the adapter produces
- a result, a repr, a log line, an exception - can carry one.
"""
import json
import logging
import unittest

from src import providers
from src.providers import glm
from tests.base import ProviderTest

FAKE_KEY = "zai-fake-key-for-tests-only-0123456789"
BASE = "https://api.example.invalid/api/coding/paas/v4"


def answer(content="OK", model="glm-5.3", finish="stop", usage=True):
    """One well-formed chat completion, shaped as the endpoint really shapes
    it (measured 2026-09-17: `reasoning_content` alongside `content`, counts
    nested under `*_tokens_details`)."""
    body = {
        "id": "20260917162406c9ababf03a334264",
        "request_id": "20260917162406c9ababf03a334264",
        "model": model,
        "object": "chat.completion",
        "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": content,
                                 "reasoning_content": "thinking"}}],
    }
    if usage:
        body["usage"] = {"prompt_tokens": 17, "completion_tokens": 29,
                         "total_tokens": 46,
                         "completion_tokens_details": {"reasoning_tokens": 26},
                         "prompt_tokens_details": {"cached_tokens": 0}}
    return body


def error(code, message):
    return {"error": {"code": str(code), "message": message}}


class Stub:
    """Plays a scripted list of outcomes, one per call.

    An entry is either `(status, body)` or an exception instance, which is
    raised. The last entry repeats, so a test that wants "fails twice then
    works" writes exactly that and a test that wants "always 429" writes one
    line.
    """

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


class GlmTest(ProviderTest):
    def setUp(self):
        super().setUp()
        self.env = {glm.ENV_KEY: FAKE_KEY, glm.ENV_BASE: BASE,
                    glm.ENV_MODEL: "glm-5.3"}
        import os
        self._saved = {k: os.environ.get(k) for k in self.env}
        self.addCleanup(self._restore_env, self._saved)
        os.environ.update(self.env)
        self.slept = []

    def play(self, *script):
        stub = Stub(*script)
        providers.set_transport(stub)         # ProviderTest resets it for us
        self.stub = stub
        return stub

    def sleep(self, seconds):
        self.slept.append(seconds)


class TestGlmSucceeds(GlmTest):
    def test_the_request_is_bounded_and_addressed_to_chat_completions(self):
        self.play()
        glm.complete("do the thing")
        call = self.stub.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["url"], BASE + "/chat/completions")
        self.assertEqual(call["body"]["model"], "glm-5.3")
        self.assertEqual(call["body"]["max_tokens"], glm.DEFAULT_MAX_TOKENS)
        self.assertFalse(call["body"]["stream"])
        self.assertEqual(call["body"]["messages"],
                         [{"role": "user", "content": "do the thing"}])
        self.assertLessEqual(call["timeout"], glm.GLM_TIMEOUT)

    def test_a_max_token_limit_is_always_sent_and_clamped(self):
        self.play()
        glm.complete("hi", max_tokens=10 ** 9)
        self.assertEqual(self.stub.calls[0]["body"]["max_tokens"],
                         glm.MAX_TOKENS_CAP)

    def test_a_system_turn_comes_first(self):
        self.play()
        glm.complete("hi", system="you are terse")
        self.assertEqual([m["role"] for m in self.stub.calls[0]["body"]["messages"]],
                         ["system", "user"])

    def test_the_result_is_trimmed_to_the_named_fields(self):
        self.play()
        r = glm.complete("hi")
        self.assertEqual(set(r), set(glm.RESPONSE_FIELDS))
        self.assertEqual(r["content"], "OK")
        self.assertEqual(r["finish_reason"], "stop")
        self.assertNotIn("reasoning_content", json.dumps(r))

    def test_usage_is_recorded(self):
        self.play()
        u = glm.complete("hi")["usage"]
        self.assertEqual(u["prompt_tokens"], 17)
        self.assertEqual(u["completion_tokens"], 29)
        self.assertEqual(u["total_tokens"], 46)
        self.assertEqual(u["reasoning_tokens"], 26)
        self.assertEqual(u["cached_tokens"], 0)

    def test_a_usage_the_api_omitted_is_none_and_not_zero(self):
        """Missing evidence is never positive evidence. A zero here would be
        a claim that the call was free."""
        self.play((200, answer(usage=False)))
        u = glm.complete("hi")["usage"]
        self.assertEqual(set(u.values()), {None})

    def test_the_model_that_answered_is_reported_not_the_one_requested(self):
        """The Coding Plan endpoint remaps ids: glm-4.6 is served by
        glm-5.3-flash. Recording only the request would report a flash model
        as the frontier one."""
        self.play((200, answer(model="glm-5.3-flash")))
        r = glm.complete("hi", model="glm-4.6")
        self.assertEqual(r["requested_model"], "glm-4.6")
        self.assertEqual(r["model"], "glm-5.3-flash")


class TestGlmRefusesBeforeSpending(GlmTest):
    def test_an_oversized_context_is_refused_rather_than_truncated(self):
        self.play()
        with self.assertRaises(ValueError) as ctx:
            glm.complete("x" * (glm.MAX_PROMPT_CHARS + 1))
        self.assertIn("exceeds the bound", str(ctx.exception))
        self.assertEqual(self.stub.calls, [])

    def test_a_model_outside_the_allowlist_is_refused_without_a_call(self):
        self.play()
        with self.assertRaises(ValueError):
            glm.complete("hi", model="gpt-9")
        self.assertEqual(self.stub.calls, [])

    def test_an_empty_prompt_is_refused(self):
        self.play()
        with self.assertRaises(ValueError):
            glm.complete("   ")
        self.assertEqual(self.stub.calls, [])

    def test_a_missing_key_is_named_and_costs_no_call(self):
        import os
        os.environ.pop(glm.ENV_KEY, None)
        self.play()
        with self.assertRaises(providers.MissingKey) as ctx:
            glm.complete("hi")
        self.assertIn(glm.ENV_KEY, str(ctx.exception))
        self.assertEqual(self.stub.calls, [])


class TestGlmClassifiesFailure(GlmTest):
    def assertClassified(self, exc, classification):
        self.assertEqual(exc.classification, classification)
        self.assertIn(classification, glm.CLASSIFICATIONS)

    def test_auth_failure_is_auth_and_is_never_retried(self):
        self.play((401, error(401, "token expired or incorrect")))
        with self.assertRaises(glm.GlmAuthFailed) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertClassified(ctx.exception, "auth")
        self.assertEqual(len(self.stub.calls), 1)
        self.assertEqual(self.slept, [])

    def test_a_validation_error_is_not_retried_either(self):
        self.play((400, error(1211, "Unknown Model, please check the model code.")))
        with self.assertRaises(glm.GlmInvalidRequest) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertClassified(ctx.exception, "invalid_request")
        self.assertEqual(len(self.stub.calls), 1)

    def test_a_rate_limit_is_retried_and_then_succeeds(self):
        self.play((429, error(1302, "API request rate exceeds limit")),
                  (200, answer()))
        r = glm.complete("hi", sleep=self.sleep)
        self.assertEqual(r["content"], "OK")
        self.assertEqual(len(self.stub.calls), 2)
        self.assertEqual(self.slept, [glm.BACKOFF_BASE])

    def test_a_rate_limit_that_never_clears_is_raised_not_swallowed(self):
        self.play((429, error(1302, "API request rate exceeds limit")))
        with self.assertRaises(glm.GlmRateLimited) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertClassified(ctx.exception, "rate_limit")
        self.assertEqual(len(self.stub.calls), glm.MAX_RETRIES + 1)
        self.assertEqual(self.slept, [glm.BACKOFF_BASE, glm.BACKOFF_BASE * 2])

    def test_an_exhausted_plan_is_quota_and_is_not_retried(self):
        """A 429 is a pace problem only while there is budget. Retrying an
        empty plan burns the caller's timeout for a certain failure, so the
        two share a status code and must not share a class."""
        self.play((429, error(1113, "Insufficient balance, please recharge")))
        with self.assertRaises(glm.GlmQuotaExhausted) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertClassified(ctx.exception, "quota")
        self.assertEqual(len(self.stub.calls), 1)
        self.assertEqual(self.slept, [])

    def test_quota_and_rate_limit_are_different_classes(self):
        self.assertNotEqual(glm.GlmQuotaExhausted.classification,
                            glm.GlmRateLimited.classification)
        self.assertFalse(issubclass(glm.GlmQuotaExhausted, glm.GlmRateLimited))
        self.assertFalse(issubclass(glm.GlmRateLimited, glm.GlmQuotaExhausted))

    def test_a_server_fault_is_retried_and_then_classified(self):
        self.play((503, {"error": {"code": "503", "message": "upstream"}}))
        with self.assertRaises(glm.GlmServerError) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertClassified(ctx.exception, "server_error")
        self.assertEqual(len(self.stub.calls), glm.MAX_RETRIES + 1)

    def test_a_timeout_is_its_own_class_and_is_retried(self):
        self.play(providers.ProviderError("TimeoutError: timed out"))
        with self.assertRaises(glm.GlmTimeout) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertClassified(ctx.exception, "timeout")
        self.assertEqual(len(self.stub.calls), glm.MAX_RETRIES + 1)

    def test_a_timeout_that_clears_returns_the_answer(self):
        self.play(providers.ProviderError("TimeoutError: timed out"),
                  (200, answer()))
        self.assertEqual(glm.complete("hi", sleep=self.sleep)["content"], "OK")

    def test_a_connection_failure_is_transport_not_timeout(self):
        self.play(providers.ProviderError("URLError: <urlopen error "
                                          "[Errno 11001] getaddrinfo failed>"))
        with self.assertRaises(glm.GlmTransportError) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertClassified(ctx.exception, "transport")

    def test_an_unrecognised_failure_stays_unknown_and_is_still_raised(self):
        """No bare `except` returning a default. Confusion is named."""
        self.play(ValueError("something nobody anticipated"))
        with self.assertRaises(glm.GlmUnknownFailure) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertClassified(ctx.exception, "unknown")
        self.assertEqual(len(self.stub.calls), 1)

    def test_every_failure_class_is_a_provider_error(self):
        for cls in (glm.GlmAuthFailed, glm.GlmQuotaExhausted,
                    glm.GlmRateLimited, glm.GlmInvalidRequest,
                    glm.GlmServerError, glm.GlmTimeout, glm.GlmTransportError,
                    glm.GlmMalformedResponse, glm.GlmUnknownFailure):
            self.assertTrue(issubclass(cls, glm.GlmError))
            self.assertTrue(issubclass(cls, providers.ProviderError))

    def test_the_classifications_are_all_distinct(self):
        seen = [glm.GlmAuthFailed, glm.GlmQuotaExhausted, glm.GlmRateLimited,
                glm.GlmInvalidRequest, glm.GlmServerError, glm.GlmTimeout,
                glm.GlmTransportError, glm.GlmMalformedResponse,
                glm.GlmUnknownFailure]
        values = [c.classification for c in seen]
        self.assertEqual(len(values), len(set(values)))
        self.assertEqual(set(values), set(glm.CLASSIFICATIONS))


class TestGlmMalformedResponse(GlmTest):
    def test_a_body_that_is_not_an_object(self):
        self.play((200, "this is not json"))
        with self.assertRaises(glm.GlmMalformedResponse) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertEqual(ctx.exception.classification, "malformed_response")

    def test_a_body_with_no_choices(self):
        self.play((200, {"model": "glm-5.3", "object": "chat.completion"}))
        with self.assertRaises(glm.GlmMalformedResponse):
            glm.complete("hi", sleep=self.sleep)

    def test_an_empty_completion_is_refused_rather_than_returned(self):
        """Returning '' would be read one layer up as a bad ANSWER instead of
        no answer, and retried as a schema failure."""
        self.play((200, answer(content="", finish="length")))
        with self.assertRaises(glm.GlmMalformedResponse) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertIn("length", str(ctx.exception))

    def test_a_malformed_body_is_not_retried(self):
        self.play((200, {"choices": []}))
        with self.assertRaises(glm.GlmMalformedResponse):
            glm.complete("hi", sleep=self.sleep)
        self.assertEqual(len(self.stub.calls), 1)
        self.assertEqual(self.slept, [])


class TestGlmKeepsTheKey(GlmTest):
    """The credential may reach the Authorization header and nowhere else."""

    def test_the_key_is_sent_as_a_bearer_token(self):
        self.play()
        glm.complete("hi")
        self.assertEqual(self.stub.calls[0]["headers"]["Authorization"],
                         f"Bearer {FAKE_KEY}")

    def test_the_result_carries_no_key(self):
        self.play()
        r = glm.complete("hi")
        self.assertNotIn(FAKE_KEY, repr(r))
        self.assertNotIn(FAKE_KEY, str(r))
        self.assertNotIn(FAKE_KEY, json.dumps(r))

    def test_an_error_body_that_echoes_the_key_is_redacted(self):
        """The failure mode this exists for: a gateway quotes the request it
        rejected, Authorization header and all, and the adapter puts that
        into an exception somebody pastes into a ticket."""
        self.play((401, error(401, f"rejected request with "
                                   f"Authorization: Bearer {FAKE_KEY}")))
        with self.assertRaises(glm.GlmAuthFailed) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertNotIn(FAKE_KEY, str(ctx.exception))
        self.assertNotIn(FAKE_KEY, repr(ctx.exception))

    def test_a_transport_error_quoting_the_key_is_redacted(self):
        self.play(providers.ProviderError(
            f"URLError: <urlopen error api_key={FAKE_KEY}>"))
        with self.assertRaises(glm.GlmTransportError) as ctx:
            glm.complete("hi", sleep=self.sleep)
        self.assertNotIn(FAKE_KEY, str(ctx.exception))

    def test_a_log_line_carrying_the_failure_carries_no_key(self):
        self.play((401, error(401, f"Bearer {FAKE_KEY} is not valid")))
        logger = logging.getLogger("tests.glm")
        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(self.format(record))

        handler = Capture()
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        try:
            glm.complete("hi", sleep=self.sleep)
        except glm.GlmError as e:
            logger.error("glm call failed: %s", e)
        self.assertTrue(records)
        for line in records:
            self.assertNotIn(FAKE_KEY, line)

    def test_the_health_check_note_carries_no_key(self):
        self.play((401, error(401, f"Bearer {FAKE_KEY} rejected")))
        r = glm.check(live=True)
        self.assertFalse(r["ok"])
        self.assertEqual(r["classification"], "auth")
        self.assertNotIn(FAKE_KEY, json.dumps(r))

    def test_no_module_attribute_holds_the_key(self):
        """Nothing caches the credential: it is read at call time and dropped.
        A cached key is what turns one careless repr into a leak."""
        self.play()
        glm.complete("hi")
        for name in dir(glm):
            self.assertNotIn(FAKE_KEY, repr(getattr(glm, name, None)))


class TestGlmCheck(GlmTest):
    def test_the_default_check_makes_no_call(self):
        self.play()
        r = glm.check()
        self.assertTrue(r["skipped"])
        self.assertIsNone(r["ok"])
        self.assertEqual(self.stub.calls, [])

    def test_a_live_check_reports_which_model_served(self):
        self.play((200, answer(model="glm-5.3-flash")))
        r = glm.check(live=True)
        self.assertTrue(r["ok"])
        self.assertIn("served glm-5.3-flash", r["note"])

    def test_a_missing_key_is_reported_by_name_and_makes_no_call(self):
        import os
        os.environ.pop(glm.ENV_KEY, None)
        self.play()
        r = glm.check()
        self.assertFalse(r["ok"])
        self.assertIn(glm.ENV_KEY, r["note"])
        self.assertEqual(self.stub.calls, [])


class TestGlmDrift(GlmTest):
    """A stubbed suite cannot notice the provider changing underneath it.
    These pin the two things a live change would break silently."""

    def test_the_endpoint_path_is_pinned(self):
        self.play()
        glm.complete("hi")
        self.assertTrue(self.stub.calls[0]["url"].endswith("/chat/completions"))

    def test_the_default_base_is_the_coding_plan_root(self):
        self.assertIn("/api/coding/", glm.BASE_DEFAULT)

    def test_no_rate_limit_headers_were_observed(self):
        """Probed 2026-09-17: the endpoint returns no budget headers at all.
        If that changes, the adapter should start reading them - and this
        constant is where a reader finds out it was measured, not forgotten."""
        self.assertEqual(glm.RATE_LIMIT_HEADERS_OBSERVED, ())


if __name__ == "__main__":
    unittest.main()
