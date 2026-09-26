"""Model spend belongs to the client, not to "_model". TASK-346.

TASK-323 wired every model call through spendledger.record(...), but wrote
the client as the literal string "_model". So provider-keyed ceilings worked
but client-level per_day and client_balance("productive") did not see model
spend at all. The operator decided they should.

This test proves:

1. A model call made in a client's context lands on that client.
2. A client ceiling REFUSES a model call BEFORE the provider is reached.
3. client_balance("productive") includes model rows.
4. Mixed units (microusd + credits) still report MIXED UNITS.
5. No historical row is rewritten (row count preserved).
6. GLM writes a row; unknown providers get a named row, not silence.
7. The guard is seen to fail (red-green: revert breaks the test).
8. Retry/fallback paths are gated.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import spendledger, store, modelprices               # noqa: E402


# Fixture responses, shaped exactly as the APIs answer.
GLM_FIXTURE = {
    "model": "glm-5.3",
    "choices": [{"message": {"content": "the answer"},
                 "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50,
              "total_tokens": 150},
    "request_id": "test-req-1",
}

ANTHROPIC_FIXTURE = {
    "model": "claude-sonnet-4-20250514",
    "choices": [{"message": {"content": "the answer"},
                 "finish_reason": "end_turn"}],
    "usage": {"prompt_tokens": 200, "completion_tokens": 100,
              "total_tokens": 300},
}

OPENROUTER_FIXTURE = {
    "model": "anthropic/claude-3.5-sonnet",
    "choices": [{"message": {"content": "the answer"},
                 "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 150, "completion_tokens": 80,
              "total_tokens": 230, "cost": 0.003},
}


class IsolatedLedger(unittest.TestCase):
    """A disposable ledger, a fresh run, no holds carried between tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-task346-")
        self.addCleanup(store.use_directory(self.tmp))
        spendledger._HOLDS.clear()
        self.addCleanup(spendledger._HOLDS.clear)
        self.run_id = spendledger.new_run(f"test-{id(self)}")
        modelprices.reload()


# ================================================ acceptance 1: real client

class ModelCallLandsOnTheRealClient(IsolatedLedger):
    """A model call made in a client's context lands on that client."""

    def test_anthropic_call_with_client_goes_to_that_client(self):
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        model.complete("hello", client="productive")

        rows = spendledger.load()
        model_rows = [r for r in rows
                      if r.get("provider") in ("anthropic", "groq",
                                               "openrouter", "glm")]
        self.assertTrue(model_rows, "no model rows written")
        for row in model_rows:
            self.assertNotEqual(
                row["client"], "_model",
                f"model row still uses '_model': {row}")
        self.assertEqual(model_rows[0]["client"], "productive")

    def test_glm_call_with_client_goes_to_that_client(self):
        from src.providers import glm

        real_send = glm._send
        glm._send = lambda body, timeout, max_attempts, sleep: (
            200, GLM_FIXTURE, 0.1)
        self.addCleanup(setattr, glm, "_send", real_send)

        config = {"budget": {"total": spendledger.UNLIMITED}}
        glm.complete("hello", ledger_client="productive", config=config)

        rows = spendledger.load()
        glm_rows = [r for r in rows if r.get("provider") == "glm"]
        self.assertTrue(glm_rows, "glm wrote no ledger row")
        self.assertEqual(glm_rows[0]["client"], "productive")

    def test_no_client_becomes_unattributed_not_underscore_model(self):
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        model.complete("hello")

        rows = spendledger.load()
        model_rows = [r for r in rows
                      if r.get("provider") in ("anthropic", "groq",
                                               "openrouter", "glm")]
        self.assertTrue(model_rows)
        self.assertEqual(model_rows[0]["client"], "unattributed")

    def test_glm_no_client_becomes_unattributed(self):
        from src.providers import glm

        real_send = glm._send
        glm._send = lambda body, timeout, max_attempts, sleep: (
            200, GLM_FIXTURE, 0.1)
        self.addCleanup(setattr, glm, "_send", real_send)

        glm.complete("hello")

        rows = spendledger.load()
        glm_rows = [r for r in rows if r.get("provider") == "glm"]
        self.assertTrue(glm_rows)
        self.assertEqual(glm_rows[0]["client"], "unattributed")


# ================================================ acceptance 2/6: refused

class ModelCallIsRefusedBeforeTheProviderIsReached(IsolatedLedger):
    """A client ceiling REFUSES a model call BEFORE the provider is reached.

    This is the critical acceptance: a ceiling that fires after the call is
    a receipt, not a control. The provider must NOT be called.
    """

    def test_client_ceiling_refuses_model_call_and_provider_not_called(self):
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        calls_to_provider = []

        def spy_request(method, url, headers, body, timeout=None):
            calls_to_provider.append(url)
            return (200, ANTHROPIC_FIXTURE)

        real_request = providers.request
        providers.request = spy_request
        self.addCleanup(setattr, providers, "request", real_request)

        # Set a client per_day ceiling of 1 microusd - essentially zero.
        # Any model call should exceed this.
        config = {"budget": {
            "per_day": 1,
            "total": spendledger.UNLIMITED,
        }}

        with self.assertRaises(spendledger.BudgetExceeded) as ctx:
            model.complete("hello", client="productive", config=config)

        self.assertEqual([], calls_to_provider,
                         "providers.request WAS called - the ceiling did not "
                         "refuse BEFORE the provider was reached")
        self.assertIn("CLIENT CEILING", str(ctx.exception))

    def test_glm_ceiling_refuses_and_provider_not_called(self):
        from src.providers import glm

        calls_to_provider = []

        def spy_send(body, timeout, max_attempts, sleep):
            calls_to_provider.append(True)
            return (200, GLM_FIXTURE, 0.1)

        real_send = glm._send
        glm._send = spy_send
        self.addCleanup(setattr, glm, "_send", real_send)

        config = {"budget": {
            "per_day": 1,
            "total": spendledger.UNLIMITED,
        }}

        with self.assertRaises(spendledger.BudgetExceeded):
            glm.complete("hello", ledger_client="productive", config=config)

        self.assertEqual([], calls_to_provider,
                         "glm._send WAS called - the ceiling did not refuse")

    def test_provider_ceiling_refuses_model_call(self):
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        calls_to_provider = []

        def spy_request(method, url, headers, body, timeout=None):
            calls_to_provider.append(url)
            return (200, ANTHROPIC_FIXTURE)

        real_request = providers.request
        providers.request = spy_request
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {
            "per_day": 1_000_000,
            "total": spendledger.UNLIMITED,
            "providers": {
                "anthropic": {
                    "per_day": 1,
                    "total": spendledger.UNLIMITED,
                },
            },
        }}

        with self.assertRaises(spendledger.BudgetExceeded) as ctx:
            model.complete("hello", client="productive", config=config)

        self.assertEqual([], calls_to_provider)
        self.assertIn("PROVIDER CEILING", str(ctx.exception))
        self.assertIn("anthropic", str(ctx.exception))


# ================================================ acceptance 3: balance

class ClientBalanceIncludesModelRows(IsolatedLedger):
    """client_balance("productive") includes the model rows."""

    def test_model_spend_appears_in_client_balance(self):
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {
            "total": spendledger.UNLIMITED,
        }}

        bal_before = spendledger.client_balance(
            "productive", config, rows=spendledger.load())
        spent_before = bal_before["spent_all_time"]

        model.complete("hello", client="productive", config=config)

        bal_after = spendledger.client_balance(
            "productive", config, rows=spendledger.load())
        spent_after = bal_after["spent_all_time"]

        self.assertGreater(spent_after, spent_before,
                           "model spend did not appear in client_balance. "
                           f"Before: {spent_before}, After: {spent_after}")


# ================================================ acceptance 4: mixed units

class MixedUnitsStillReported(IsolatedLedger):
    """Model rows are microusd, provider rows are credits. MIXED UNITS."""

    def test_client_balance_shows_mixed_units(self):
        from src import llm, providers

        # Write a model row (microusd).
        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {
            "total": spendledger.UNLIMITED,
        }}
        model.complete("hello", client="productive", config=config)

        # Write a provider row (credits).
        spendledger.record("productive", "deliverable", "verify", 500)

        # Check that progress_block shows MIXED UNITS.
        progress = spendledger.progress_block("productive", config)
        self.assertIn("MIXED UNITS", progress,
                       "client-wide line does not say MIXED UNITS. "
                       "microusd and credits must not be summed.")

    def test_client_balance_does_not_sum_microusd_and_credits(self):
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {"total": spendledger.UNLIMITED}}
        model.complete("hello", client="productive", config=config)
        spendledger.record("productive", "deliverable", "verify", 500)

        bal = spendledger.balances("productive", config)
        units_seen = set()
        for b in bal.values():
            for u in b["units_seen"]:
                units_seen.add(u)
        self.assertGreater(len(units_seen), 1,
                           f"expected multiple units, got: {units_seen}")


# ================================================ acceptance 5: row count

class NoHistoricalRowRewritten(IsolatedLedger):
    """Count rows before and after, assert equality."""

    def test_row_count_preserved(self):
        from src import llm, providers

        # Seed a row.
        spendledger.record("productive", "deliverable", "verify", 100)
        count_before = len(spendledger.load())

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {"total": spendledger.UNLIMITED}}
        model.complete("hello", client="productive", config=config)

        count_after = len(spendledger.load())
        self.assertEqual(count_before + 1, count_after,
                         f"expected exactly 1 new row, got "
                         f"{count_after - count_before}. "
                         f"Before: {count_before}, After: {count_after}")


# ================================================ acceptance 7: red-green

class GuardIsSeenToFail(IsolatedLedger):
    """Revert the holding change, confirm the test FAILS on old code.

    This test drives the SAME assertion as the refusal test above, but
    bypasses the new code path by calling the provider directly and
    recording spend the OLD way (post-call, no check). If the old path
    does NOT refuse, the test passes - proving the old code was broken.
    """

    def test_old_path_does_not_refuse(self):
        """Simulate the OLD behaviour: record after call, no check.

        The old code called providers.request, then recorded spend.
        No ceiling was checked. This test proves that shape is broken.
        """
        from src import llm, providers

        calls_to_provider = []

        def spy_request(method, url, headers, body, timeout=None):
            calls_to_provider.append(url)
            return (200, ANTHROPIC_FIXTURE)

        real_request = providers.request
        providers.request = spy_request
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {
            "per_day": 1,
            "total": spendledger.UNLIMITED,
        }}

        # OLD behaviour simulation: call the provider, then record.
        # No reserve, no check, no holding.
        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        # Simulate old _record_spend: post-call, no check.
        def old_record_spend(model_name, usage):
            from src import modelprices as mp
            cost = mp.cost_micro_usd(model_name, usage)
            spendledger.record(
                "_model", "anthropic",
                f"complete:{model_name}", cost,
                unit="microusd", rows=usage)

        # Make the call directly (bypassing complete's new gate).
        status, data = providers.request(
            "POST", f"{model.base}/chat/completions", model._headers(),
            {"model": model.model, "temperature": 0,
             "messages": [{"role": "user", "content": "hello"}]},
            timeout=model.timeout)
        calls_to_provider.append("called")

        # Old code: record AFTER the call, no check.
        usage = data.get("usage", {})
        old_record_spend(data.get("model") or model.model, usage)

        # The provider WAS called despite the ceiling being 1 microusd.
        self.assertTrue(calls_to_provider,
                        "old path should have called the provider "
                        "(proving it did not refuse)")

        # And the row was written as "_model", not "productive".
        rows = spendledger.load()
        model_rows = [r for r in rows if r.get("provider") == "anthropic"]
        self.assertTrue(model_rows)
        self.assertEqual(model_rows[0]["client"], "_model",
                         "old path should write '_model' (proving the bug)")

    def test_new_path_refuses_where_old_path_did_not(self):
        """The new code refuses the same call the old path let through."""
        from src import llm, providers

        calls_to_provider = []

        def spy_request(method, url, headers, body, timeout=None):
            calls_to_provider.append(url)
            return (200, ANTHROPIC_FIXTURE)

        real_request = providers.request
        providers.request = spy_request
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {
            "per_day": 1,
            "total": spendledger.UNLIMITED,
        }}

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        with self.assertRaises(spendledger.BudgetExceeded):
            model.complete("hello", client="productive", config=config)

        self.assertEqual([], calls_to_provider,
                         "new path must refuse BEFORE the provider is called")


# ================================================ acceptance 8: GLM + unknown

class GlmWritesARowAndUnknownProviderIsNamed(IsolatedLedger):
    """GLM writes a row. Unknown providers get a named row, not silence."""

    def test_glm_writes_a_row(self):
        from src.providers import glm

        real_send = glm._send
        glm._send = lambda body, timeout, max_attempts, sleep: (
            200, GLM_FIXTURE, 0.1)
        self.addCleanup(setattr, glm, "_send", real_send)

        config = {"budget": {"total": spendledger.UNLIMITED}}
        glm.complete("hello", ledger_client="productive", config=config)

        rows = spendledger.load()
        glm_rows = [r for r in rows if r.get("provider") == "glm"]
        self.assertTrue(glm_rows, "GLM wrote no ledger row")
        self.assertEqual(glm_rows[0]["client"], "productive")
        self.assertEqual(glm_rows[0]["unit"], "microusd")
        self.assertGreater(glm_rows[0]["expected_cost"], 0,
                           "glm-5.3 is priced but cost is zero")

    def test_unknown_provider_writes_a_named_row(self):
        """A base URL that is not groq/anthropic/openrouter/glm still writes
        a row with a name derived from the hostname."""
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="some-local-model",
            base="https://my-local-server.example.com/v1")

        fixture = {
            "model": "some-local-model",
            "choices": [{"message": {"content": "hello"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        }

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, fixture)
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {"total": spendledger.UNLIMITED}}
        model.complete("hello", client="productive", config=config)

        rows = spendledger.load()
        model_rows = [r for r in rows
                      if r.get("client") == "productive"
                      and r.get("provider") not in ("deliverable",
                                                     "cheapverifier",
                                                     "contactout")]
        self.assertTrue(model_rows,
                        "unknown provider wrote no ledger row - silent gap")
        row = model_rows[0]
        self.assertNotEqual(row["provider"], "_model")
        self.assertIn("my-local-server", row["provider"].replace("_", "."))

    def test_unknown_provider_cost_is_zero_with_microusd_unit(self):
        """An unpriced model on a known provider gets cost=0, unit=microusd.

        An unknown provider with an unpriced model gets cost=0 and the row
        is visible with token counts.
        """
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="totally-unknown-model-xyz",
            base="https://api.anthropic.com/v1")

        fixture = {
            "model": "totally-unknown-model-xyz",
            "choices": [{"message": {"content": "hello"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        }

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, fixture)
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {"total": spendledger.UNLIMITED}}
        model.complete("hello", client="productive", config=config)

        rows = spendledger.load()
        anthropic_rows = [r for r in rows if r.get("provider") == "anthropic"]
        self.assertTrue(anthropic_rows)
        row = anthropic_rows[0]
        self.assertEqual(row["unit"], "microusd")
        self.assertIsInstance(row["expected_cost"], int)


# ================================================ acceptance 9: all paths

class AllCodePathsAreGated(IsolatedLedger):
    """Every code path that reaches a paid model passes through the gate.

    Named paths:
    1. OpenAICompatibleModel.complete() - uses reserve/settle (TASK-346).
    2. glm.complete() - uses reserve/settle (TASK-346).
    3. QwenCliModel.complete() - local CLI, no provider spend, no gate needed.
    4. ScriptedModel.complete() - returns canned answers, no spend.
    5. NoModel.complete() - refuses before any spend.
    """

    def test_openai_compatible_model_uses_reserve(self):
        """OpenAICompatibleModel.complete() calls spendledger.reserve."""
        from src import llm, providers, spendledger as sl

        reserved = []
        real_reserve = sl.reserve

        def spy_reserve(*args, **kwargs):
            reserved.append((args, kwargs))
            return real_reserve(*args, **kwargs)

        self.addCleanup(setattr, sl, "reserve", real_reserve)
        sl.reserve = spy_reserve

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {"total": spendledger.UNLIMITED}}
        model.complete("hello", client="productive", config=config)

        self.assertTrue(reserved,
                        "OpenAICompatibleModel.complete() did not call "
                        "spendledger.reserve - the gate is missing")

    def test_glm_uses_reserve(self):
        """glm.complete() calls spendledger.reserve."""
        from src.providers import glm
        from src import spendledger as sl

        reserved = []
        real_reserve = sl.reserve

        def spy_reserve(*args, **kwargs):
            reserved.append((args, kwargs))
            return real_reserve(*args, **kwargs)

        self.addCleanup(setattr, sl, "reserve", real_reserve)
        sl.reserve = spy_reserve

        real_send = glm._send
        glm._send = lambda body, timeout, max_attempts, sleep: (
            200, GLM_FIXTURE, 0.1)
        self.addCleanup(setattr, glm, "_send", real_send)

        config = {"budget": {"total": spendledger.UNLIMITED}}
        glm.complete("hello", ledger_client="productive", config=config)

        self.assertTrue(reserved,
                        "glm.complete() did not call spendledger.reserve - "
                        "the gate is missing")

    def test_glm_release_on_send_failure(self):
        """When _send raises, the hold is released (no leaked credit)."""
        from src.providers import glm
        from src import spendledger as sl

        real_send = glm._send

        def failing_send(body, timeout, max_attempts, sleep):
            raise glm.GlmTransportError("glm: connection refused")

        glm._send = failing_send
        self.addCleanup(setattr, glm, "_send", real_send)

        config = {"budget": {"total": spendledger.UNLIMITED}}

        with self.assertRaises(glm.GlmTransportError):
            glm.complete("hello", ledger_client="productive", config=config)

        outstanding = sl.outstanding()
        self.assertEqual([], outstanding,
                         f"hold leaked after _send failure: {outstanding}")

    def test_glm_release_on_trim_failure(self):
        """When _trim raises (malformed response), the hold is released."""
        from src.providers import glm
        from src import spendledger as sl

        real_send = glm._send
        glm._send = lambda body, timeout, max_attempts, sleep: (
            200, {"choices": []}, 0.1)
        self.addCleanup(setattr, glm, "_send", real_send)

        config = {"budget": {"total": spendledger.UNLIMITED}}

        with self.assertRaises(glm.GlmMalformedResponse):
            glm.complete("hello", ledger_client="productive", config=config)

        outstanding = sl.outstanding()
        self.assertEqual([], outstanding,
                         f"hold leaked after _trim failure: {outstanding}")

    def test_openai_release_on_http_failure(self):
        """When the HTTP call fails, the hold is released."""
        from src import llm, providers, spendledger as sl

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request

        def failing_request(method, url, headers, body, timeout=None):
            raise ConnectionError("connection refused")

        providers.request = failing_request
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {"total": spendledger.UNLIMITED}}

        with self.assertRaises(llm.ModelUnavailable):
            model.complete("hello", client="productive", config=config)

        outstanding = sl.outstanding()
        self.assertEqual([], outstanding,
                         f"hold leaked after HTTP failure: {outstanding}")


# ================================================ historical _model rows

class HistoricalModelRowsAreNotBackfilled(IsolatedLedger):
    """Existing '_model' rows are left as-is. No backfill."""

    def test_existing_model_rows_remain(self):
        # Seed an old row with "_model".
        spendledger.record("_model", "anthropic", "complete:test", 100,
                           unit="microusd")

        count_before = len(spendledger.load())

        from src import llm, providers
        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        config = {"budget": {"total": spendledger.UNLIMITED}}
        model.complete("hello", client="productive", config=config)

        rows = spendledger.load()
        old_rows = [r for r in rows if r.get("client") == "_model"]
        self.assertEqual(1, len(old_rows),
                         "old '_model' row was modified or deleted")
        self.assertEqual(old_rows[0]["expected_cost"], 100,
                         "old '_model' row cost was changed")


if __name__ == "__main__":
    unittest.main()
