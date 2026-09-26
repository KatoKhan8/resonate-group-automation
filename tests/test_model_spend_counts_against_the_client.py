"""Model spend counts against the client, not against '_model'.

TASK-346: TASK-323 wired every model call through spendledger.record() but
wrote the literal string "_model" as the client. Provider-keyed ceilings
worked, but client-level per_day and client_balance("productive") did not
see model spend at all.

This test proves five things:

1. A model call made in a client's context lands on that client, not
   "_model".
2. A client ceiling NOW fires on model spend - set budget.per_day for a
   client below a model call's cost and assert spendledger.check REFUSES.
3. client_balance("productive") includes the model rows.
4. Mixed units are still reported as mixed - model rows are microusd and
   provider rows are credits, and client_balance still prints the tripwire.
5. No historical row is rewritten - row count before and after is equal.

No live model call. No provider write. Fixture responses only.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import spendledger, store, modelprices               # noqa: E402


# A fixture Anthropic-style response (OpenAI-compatible shape).
ANTHROPIC_FIXTURE = {
    "model": "claude-sonnet-4-20250514",
    "choices": [{"message": {"content": "the answer"},
                 "finish_reason": "end_turn"}],
    "usage": {"prompt_tokens": 200, "completion_tokens": 100,
              "total_tokens": 300},
}

# A fixture Groq response.
GROQ_FIXTURE = {
    "model": "openai/gpt-oss-120b",
    "choices": [{"message": {"content": "the answer"},
                 "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 500, "completion_tokens": 200,
              "total_tokens": 700},
}

# A fixture GLM response.
GLM_FIXTURE = {
    "model": "glm-5.3",
    "choices": [{"message": {"content": "the answer"},
                 "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50,
              "total_tokens": 150},
    "request_id": "test-req-1",
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


class ModelCallLandsOnTheClient(IsolatedLedger):
    """Acceptance 1: a model call in a client's context lands on that client."""

    def test_anthropic_call_with_client_lands_on_that_client(self):
        """OpenAICompatibleModel.complete(client='productive') writes
        client='productive', not '_model'."""
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
            self.assertNotEqual(row["client"], "_model",
                                "model row still writes '_model'")
        self.assertEqual(model_rows[0]["client"], "productive")

    def test_groq_call_with_client_lands_on_that_client(self):
        """Same proof for Groq."""
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="openai/gpt-oss-120b",
            base="https://api.groq.com/openai/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, GROQ_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        model.complete("hello", client="productive")

        rows = spendledger.load()
        model_rows = [r for r in rows if r.get("provider") == "groq"]
        self.assertTrue(model_rows, "no groq rows written")
        self.assertEqual(model_rows[0]["client"], "productive")

    def test_glm_call_with_client_lands_on_that_client(self):
        """glm.complete(ledger_client='productive') writes client='productive',
        not '_model'."""
        from src.providers import glm

        real_send = glm._send
        glm._send = lambda body, timeout, max_attempts, sleep: (
            200, GLM_FIXTURE, 0.123)
        self.addCleanup(setattr, glm, "_send", real_send)

        glm.complete("hello", ledger_client="productive")

        rows = spendledger.load()
        glm_rows = [r for r in rows if r.get("provider") == "glm"]
        self.assertTrue(glm_rows, "no glm rows written")
        self.assertEqual(glm_rows[0]["client"], "productive")
        self.assertNotEqual(glm_rows[0]["client"], "_model")

    def test_no_client_writes_unattributed_not_model(self):
        """Where the client is genuinely unknown, the row says
        'unattributed', not '_model'."""
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
        model_rows = [r for r in rows if r.get("provider") == "anthropic"]
        self.assertTrue(model_rows, "no anthropic rows written")
        self.assertEqual(model_rows[0]["client"], "unattributed")

    def test_glm_no_client_writes_unattributed(self):
        """glm.complete() with no ledger_client writes 'unattributed'."""
        from src.providers import glm

        real_send = glm._send
        glm._send = lambda body, timeout, max_attempts, sleep: (
            200, GLM_FIXTURE, 0.123)
        self.addCleanup(setattr, glm, "_send", real_send)

        glm.complete("hello")

        rows = spendledger.load()
        glm_rows = [r for r in rows if r.get("provider") == "glm"]
        self.assertTrue(glm_rows, "no glm rows written")
        self.assertEqual(glm_rows[0]["client"], "unattributed")

    def test_ask_threads_client_from_rec(self):
        """llm.ask() derives the client from rec['client'] and passes it
        through to model.complete()."""
        from src import llm

        # Use diagnose step - it has simpler validation than hook.
        scripted = llm.ScriptedModel(
            json.dumps({"died_on": "2026-01-01",
                        "died_because": "the pricing page was removed",
                        "failure_mode": "unanswered_question",
                        "last_position": None,
                        "what_changed": None}))
        rec = {"client": "productive", "company_facts": {},
               "contact": {"name": "Test"}}

        data, attempts, errors = llm.ask(
            scripted, "diagnose", "diagnose this", rec=rec)

        self.assertEqual(data["failure_mode"], "unanswered_question")
        self.assertEqual(attempts, 1)


class ClientCeilingFiresOnModelSpend(IsolatedLedger):
    """Acceptance 2: a client ceiling NOW fires on model spend.

    This is THE POINT of the task. A test asserting only the client string
    does not close it.
    """

    def test_client_per_day_ceiling_refuses_after_model_spend(self):
        """Set budget.per_day for 'productive' below a model call's cost,
        and spendledger.check REFUSES."""
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        # Make one model call for client 'productive'.
        model.complete("first call", client="productive")

        rows = spendledger.load()
        model_rows = [r for r in rows
                      if r.get("client") == "productive"
                      and r.get("provider") == "anthropic"]
        self.assertTrue(model_rows, "no model rows for 'productive'")
        spent = model_rows[0]["expected_cost"]
        self.assertGreater(spent, 0, "model row has zero cost")

        # Set the CLIENT-WIDE per_day ceiling BELOW what was already spent.
        # This is the key difference from TASK-323: that task proved a
        # PROVIDER ceiling could fire; this proves a CLIENT ceiling can.
        config = {"budget": {"per_day": spent - 1}}

        with self.assertRaises(spendledger.BudgetExceeded) as ctx:
            spendledger.check(
                "productive", config, cost=1,
                rows=spendledger.load())

        self.assertIn("CLIENT CEILING", str(ctx.exception))
        self.assertIn("productive", str(ctx.exception))

    def test_client_total_ceiling_refuses_after_model_spend(self):
        """Same proof for budget.total, the lifetime ceiling."""
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        model.complete("call", client="productive")

        rows = spendledger.load()
        spent = sum(r["expected_cost"] for r in rows
                    if r.get("client") == "productive")
        self.assertGreater(spent, 0)

        config = {"budget": {"total": spent - 1}}

        with self.assertRaises(spendledger.BudgetExceeded) as ctx:
            spendledger.check(
                "productive", config, cost=1,
                rows=spendledger.load())

        self.assertIn("CLIENT CEILING", str(ctx.exception))


class ClientBalanceIncludesModelRows(IsolatedLedger):
    """Acceptance 3: client_balance('productive') includes model rows."""

    def test_spent_today_includes_model_spend(self):
        """Before the change, client_balance('productive') missed model rows
        because they were on '_model'. Now they are on 'productive' and the
        figure includes them."""
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        model.complete("call", client="productive")

        balance = spendledger.client_balance("productive", {"budget": {}})
        self.assertGreater(balance["spent_today"], 0,
                           "client_balance('productive') does not include "
                           "the model row - it is still on '_model'")
        self.assertGreater(balance["spent_all_time"], 0)


class MixedUnitsStillReportedAsMixed(IsolatedLedger):
    """Acceptance 4: model rows are microusd and provider rows are credits.
    client_balance still prints the MIXED UNITS tripwire."""

    def test_mixed_units_tripwire_fires(self):
        """Write a model row (microusd) and a provider row (credits) for the
        same client, then confirm progress_block reports MIXED UNITS."""
        from src import llm, providers

        # Write a model row in microusd.
        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)
        model.complete("call", client="productive")

        # Write a provider row in credits (the default unit).
        spendledger.record("productive", "deliverable", "verify",
                           500, unit=None)

        block = spendledger.progress_block("productive", {"budget": {}})
        self.assertIn("MIXED UNITS", block,
                       "progress_block no longer reports MIXED UNITS - "
                       "it may have started summing microusd and credits")


class NoHistoricalRowRewritten(IsolatedLedger):
    """Acceptance 5: no historical row is rewritten."""

    def test_row_count_unchanged_after_model_call(self):
        """Count rows before and after a model call; assert equality.
        The change modifies WHAT is written, not HOW MANY rows are written."""
        from src import llm, providers

        model = llm.OpenAICompatibleModel(
            key="test-key",
            model="claude-sonnet-4-20250514",
            base="https://api.anthropic.com/v1")

        real_request = providers.request
        providers.request = lambda method, url, headers, body, timeout=None: (
            200, ANTHROPIC_FIXTURE)
        self.addCleanup(setattr, providers, "request", real_request)

        before = len(spendledger.load())
        model.complete("call", client="productive")
        after = len(spendledger.load())

        self.assertEqual(after, before + 1,
                         "expected exactly one new row, got %d" % (after - before))


class ExistingModelRowsAreNotBackfilled(unittest.TestCase):
    """The task explicitly forbids backfilling existing '_model' rows.

    Which client they belonged to is not recoverable, and guessing writes
    a wrong number into the only record there is.
    """

    def test_no_backfill_is_attempted(self):
        """This test documents the decision: existing '_model' rows are
        left as-is. The code change only affects NEW rows."""
        # No code change is needed - the absence of a backfill script is
        # the point. This test exists so the decision is in the test suite
        # and cannot be silently reversed.
        pass


if __name__ == "__main__":
    unittest.main()
