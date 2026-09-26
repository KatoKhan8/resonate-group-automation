"""The cohort preamble is paid for once, not on every lead.  TASK-340.

Two cost levers, both optional per call and both OFF unless the caller asks:

1. **Prompt caching** on the stable cohort preamble.  A cached call carries
   the directive in the request body; an uncached one does not.
2. **A batch entry point** submitting many leads per request.

The measurement that is the acceptance:

1. A cached call carries the directive and an uncached one does not - assert
   on the request body actually built, not on a flag.
2. The batch entry point submits N leads in one request; assert the request
   count is 1 for N>1.
3. Correctness is unchanged: the copy produced with caching on is equivalent
   to caching off for the same input.
"""
import json
import os
import tempfile
import unittest

from src import providers
from src.providers import anthropic, glm


# --------------------------------------------------------------- fixtures

SYSTEM_PREAMBLE = (
    "You are a research assistant writing one personalised email opener per "
    "lead.  Every claim must be traceable to the record.  Never invent a "
    "fact, never mention the email in the LinkedIn note, never reference the "
    "note in the email.  Return strict JSON with the fields named in the "
    "schema.  The cohort preamble ends here."
)

LEAD_PROMPTS = [
    f"Lead 1: CTO at Acme Corp, 48 employees, hiring project managers. "
    f"Write a hook and subject line.",
    f"Lead 2: VP Eng at Brightpath, Series B, opened a Vienna office. "
    f"Write a hook and subject line.",
    f"Lead 3: Head of Design at Coral Studio, 12 people, stopped tracking "
    f"time.  Write a hook and subject line.",
]

CANNED_RESPONSE = {
    "id": "msg_test",
    "type": "message",
    "role": "assistant",
    "content": [{"type": "text",
                 "text": '{"subject":"Test","body":"Test body"}'}],
    "model": "claude-sonnet-4-20250514",
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 100, "output_tokens": 20,
              "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0},
}

GLM_RESPONSE = {
    "id": "glm_test",
    "choices": [{"message": {"role": "assistant",
                             "content": '{"subject":"Test","body":"Test body"}'},
                 "finish_reason": "stop"}],
    "model": "glm-5.3",
    "usage": {"prompt_tokens": 100, "completion_tokens": 20,
              "total_tokens": 120},
}

BATCH_RESPONSE = {
    "id": "batch_test",
    "processing_status": "ended",
    "results": [
        {"custom_id": "item-0", "type": "succeeded",
         "result": CANNED_RESPONSE},
        {"custom_id": "item-1", "type": "succeeded",
         "result": CANNED_RESPONSE},
        {"custom_id": "item-2", "type": "succeeded",
         "result": CANNED_RESPONSE},
    ],
}


class _Recorder:
    """A transport that records request bodies and returns canned responses.

    Each call appends `(method, url, headers, body, timeout)` to `calls`.
    The response is drawn from `responses` in order, or the last one if
    exhausted.
    """

    def __init__(self, responses=None):
        self.calls = []
        self._responses = list(responses or [CANNED_RESPONSE])
        self._idx = 0

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, body, timeout))
        resp = (self._responses[self._idx]
                if self._idx < len(self._responses)
                else self._responses[-1])
        self._idx += 1
        return 200, resp


# ------------------------------------- 1. cache directive in the body

class TestCacheDirectiveInBody(unittest.TestCase):
    """A cached call carries the directive; an uncached one does not."""

    def setUp(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key-for-unit-tests"
        self._tmpdir = tempfile.mkdtemp()
        self._old_env = os.environ.get("SPEND_LEDGER")
        os.environ["SPEND_LEDGER"] = os.path.join(
            self._tmpdir, "spend-ledger.jsonl")

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        if self._old_env is not None:
            os.environ["SPEND_LEDGER"] = self._old_env
        else:
            os.environ.pop("SPEND_LEDGER", None)

    def test_anthropic_uncached_has_no_cache_control(self):
        rec = _Recorder()
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        anthropic.complete("hello", system=SYSTEM_PREAMBLE, cache=False)

        self.assertEqual(len(rec.calls), 1)
        body = rec.calls[0][3]
        # System is a plain string when cache is off
        self.assertIsInstance(body.get("system"), str)
        # No cache_control anywhere in the messages
        for msg in body.get("messages", []):
            self.assertNotIn("cache_control", msg)

    def test_anthropic_cached_has_cache_control_on_system(self):
        rec = _Recorder()
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        anthropic.complete("hello", system=SYSTEM_PREAMBLE, cache=True)

        self.assertEqual(len(rec.calls), 1)
        body = rec.calls[0][3]
        # System is a list of blocks when cache is on
        system = body.get("system")
        self.assertIsInstance(system, list)
        self.assertEqual(len(system), 1)
        self.assertEqual(system[0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(system[0]["text"], SYSTEM_PREAMBLE)

    def test_anthropic_cached_without_system_marks_user_message(self):
        rec = _Recorder()
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        anthropic.complete("hello", cache=True)

        body = rec.calls[0][3]
        # No system field
        self.assertNotIn("system", body)
        # The user message carries cache_control
        msgs = body.get("messages", [])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["cache_control"], {"type": "ephemeral"})

    def test_glm_uncached_has_no_cache_directive(self):
        rec = _Recorder([GLM_RESPONSE])
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)
        os.environ["ZAI_API_KEY"] = "test-key"
        self.addCleanup(os.environ.pop, "ZAI_API_KEY", None)

        glm.complete("hello", system=SYSTEM_PREAMBLE, cache=False)

        body = rec.calls[0][3]
        self.assertNotIn("chat_template_kwargs", body)

    def test_glm_cached_has_cache_directive(self):
        rec = _Recorder([GLM_RESPONSE])
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)
        os.environ["ZAI_API_KEY"] = "test-key"
        self.addCleanup(os.environ.pop, "ZAI_API_KEY", None)

        glm.complete("hello", system=SYSTEM_PREAMBLE, cache=True)

        body = rec.calls[0][3]
        self.assertIn("chat_template_kwargs", body)
        self.assertTrue(body["chat_template_kwargs"]["enable_cache"])


# ------------------------------------- 2. batch: N leads, 1 request

class TestBatchSubmission(unittest.TestCase):
    """The batch entry point submits N leads in one request."""

    def setUp(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key-for-unit-tests"
        self._tmpdir = tempfile.mkdtemp()
        self._old_env = os.environ.get("SPEND_LEDGER")
        os.environ["SPEND_LEDGER"] = os.path.join(
            self._tmpdir, "spend-ledger.jsonl")

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        if self._old_env is not None:
            os.environ["SPEND_LEDGER"] = self._old_env
        else:
            os.environ.pop("SPEND_LEDGER", None)

    def test_batch_submits_n_items_in_one_request(self):
        # The batch create returns a batch id; the poll returns results.
        create_resp = {"id": "batch_abc123",
                       "processing_status": "in_progress"}
        rec = _Recorder([create_resp, BATCH_RESPONSE])
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        items = [{"prompt": p, "system": SYSTEM_PREAMBLE}
                 for p in LEAD_PROMPTS]
        results = anthropic.complete_batch(items, cache=True,
                                           poll_interval=0, max_polls=5)

        # The first call is the batch create.  The second is the poll.
        # Total: 2 requests, NOT 3 (one per lead).
        self.assertEqual(len(rec.calls), 2)
        # The first call is the batch create
        method, url, _, body, _ = rec.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/batches", url)
        # The body carries all N items
        self.assertEqual(len(body["requests"]), 3)
        # Each item has cache_control on its system
        for entry in body["requests"]:
            sys_blocks = entry["params"].get("system")
            self.assertIsInstance(sys_blocks, list)
            self.assertEqual(sys_blocks[0]["cache_control"],
                             {"type": "ephemeral"})
        # Results are in order
        self.assertEqual(len(results), 3)

    def test_batch_without_cache_has_no_cache_control(self):
        create_resp = {"id": "batch_abc123",
                       "processing_status": "in_progress"}
        rec = _Recorder([create_resp, BATCH_RESPONSE])
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        items = [{"prompt": p} for p in LEAD_PROMPTS]
        anthropic.complete_batch(items, cache=False,
                                 poll_interval=0, max_polls=5)

        body = rec.calls[0][3]
        for entry in body["requests"]:
            # No system field when no system is given
            self.assertNotIn("system", entry["params"])
            # No cache_control on messages
            for msg in entry["params"]["messages"]:
                self.assertNotIn("cache_control", msg)


# ------------------------------------- 3. correctness unchanged

class TestCorrectnessUnchanged(unittest.TestCase):
    """Caching does not change the output.  A cost lever that changes the
    words is a defect."""

    def setUp(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key-for-unit-tests"
        self._tmpdir = tempfile.mkdtemp()
        self._old_env = os.environ.get("SPEND_LEDGER")
        os.environ["SPEND_LEDGER"] = os.path.join(
            self._tmpdir, "spend-ledger.jsonl")

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        if self._old_env is not None:
            os.environ["SPEND_LEDGER"] = self._old_env
        else:
            os.environ.pop("SPEND_LEDGER", None)

    def test_cached_and_uncached_produce_same_content(self):
        """Same canned response for both calls; the content is identical."""
        rec = _Recorder([CANNED_RESPONSE, CANNED_RESPONSE])
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        result_off = anthropic.complete("hello", system=SYSTEM_PREAMBLE,
                                        cache=False)
        result_on = anthropic.complete("hello", system=SYSTEM_PREAMBLE,
                                       cache=True)

        self.assertEqual(result_off["content"], result_on["content"])

    def test_cached_and_uncached_send_same_prompt(self):
        """The user prompt is identical in both request bodies."""
        rec = _Recorder([CANNED_RESPONSE, CANNED_RESPONSE])
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        anthropic.complete("hello", system=SYSTEM_PREAMBLE, cache=False)
        anthropic.complete("hello", system=SYSTEM_PREAMBLE, cache=True)

        body_off = rec.calls[0][3]
        body_on = rec.calls[1][3]
        # The user message content is the same
        self.assertEqual(
            body_off["messages"][0]["content"],
            body_on["messages"][0]["content"])


# ------------------------------------- 4. ledger integration

class TestLedgerIntegration(unittest.TestCase):
    """Every call writes a ledger row, cached or not."""

    def setUp(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key-for-unit-tests"
        self._tmpdir = tempfile.mkdtemp()
        self._ledger_path = os.path.join(self._tmpdir, "spend-ledger.jsonl")
        self._old_env = os.environ.get("SPEND_LEDGER")
        os.environ["SPEND_LEDGER"] = self._ledger_path

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        if self._old_env is not None:
            os.environ["SPEND_LEDGER"] = self._old_env
        else:
            os.environ.pop("SPEND_LEDGER", None)

    def test_cached_call_writes_ledger_row(self):
        rec = _Recorder()
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        anthropic.complete("hello", system=SYSTEM_PREAMBLE, cache=True)

        with open(self._ledger_path) as f:
            rows = [json.loads(line) for line in f if line.strip()]
        self.assertTrue(len(rows) >= 1)
        self.assertEqual(rows[-1]["provider"], "anthropic")
        self.assertEqual(rows[-1]["unit"], "microusd")

    def test_uncached_call_writes_ledger_row(self):
        rec = _Recorder()
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        anthropic.complete("hello", system=SYSTEM_PREAMBLE, cache=False)

        with open(self._ledger_path) as f:
            rows = [json.loads(line) for line in f if line.strip()]
        self.assertTrue(len(rows) >= 1)
        self.assertEqual(rows[-1]["provider"], "anthropic")


# ------------------------------------- 5. OpenAI-compatible cache

class TestOpenAICompatibleCache(unittest.TestCase):
    """The OpenAI-compatible model forwards cache_control when asked."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._old_env = os.environ.get("SPEND_LEDGER")
        os.environ["SPEND_LEDGER"] = os.path.join(
            self._tmpdir, "spend-ledger.jsonl")

    def tearDown(self):
        if self._old_env is not None:
            os.environ["SPEND_LEDGER"] = self._old_env
        else:
            os.environ.pop("SPEND_LEDGER", None)

    def test_cached_call_has_cache_control_in_messages(self):
        from src.llm import OpenAICompatibleModel

        rec = _Recorder([{
            "choices": [{"message": {"content": "answer",
                                     "role": "assistant"}}],
            "model": "test-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        }])
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        model = OpenAICompatibleModel(
            key="test-key", model="test-model",
            base="https://openrouter.ai/api/v1")
        model.complete("hello", cache=True)

        body = rec.calls[0][3]
        msgs = body.get("messages", [])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["cache_control"], {"type": "ephemeral"})

    def test_uncached_call_has_no_cache_control(self):
        from src.llm import OpenAICompatibleModel

        rec = _Recorder([{
            "choices": [{"message": {"content": "answer",
                                     "role": "assistant"}}],
            "model": "test-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        }])
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        model = OpenAICompatibleModel(
            key="test-key", model="test-model",
            base="https://openrouter.ai/api/v1")
        model.complete("hello", cache=False)

        body = rec.calls[0][3]
        msgs = body.get("messages", [])
        self.assertNotIn("cache_control", msgs[0])


# ------------------------------------- 6. batch module-level entry point

class TestModuleLevelBatch(unittest.TestCase):
    """The module-level `complete_batch` delegates to the model."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._old_env = os.environ.get("SPEND_LEDGER")
        os.environ["SPEND_LEDGER"] = os.path.join(
            self._tmpdir, "spend-ledger.jsonl")

    def tearDown(self):
        if self._old_env is not None:
            os.environ["SPEND_LEDGER"] = self._old_env
        else:
            os.environ.pop("SPEND_LEDGER", None)

    def test_module_batch_delegates_to_model_complete_batch(self):
        from src import llm

        rec = _Recorder([{
            "choices": [{"message": {"content": f"answer-{i}",
                                     "role": "assistant"}}],
            "model": "test-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        } for i in range(3)])
        prev = providers.set_transport(rec)
        self.addCleanup(providers.set_transport, prev)

        model = llm.OpenAICompatibleModel(
            key="test-key", model="test-model",
            base="https://openrouter.ai/api/v1")

        results = llm.complete_batch(model, ["a", "b", "c"], cache=True)

        self.assertEqual(len(results), 3)
        # Three separate requests (OpenAI-compatible has no native batch)
        self.assertEqual(len(rec.calls), 3)
        # Each request carries cache_control
        for call in rec.calls:
            body = call[3]
            self.assertEqual(body["messages"][0]["cache_control"],
                             {"type": "ephemeral"})

    def test_module_batch_falls_back_for_plain_model(self):
        from src import llm

        class PlainModel:
            def __init__(self):
                self.calls = []
            def complete(self, prompt, temperature=0):
                self.calls.append(prompt)
                return f"echo:{prompt}"

        model = PlainModel()
        results = llm.complete_batch(model, ["x", "y"])
        self.assertEqual(results, ["echo:x", "echo:y"])


if __name__ == "__main__":
    unittest.main()
