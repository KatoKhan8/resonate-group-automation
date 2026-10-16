# TASK 0073. A zero that means "free" and a zero that means "nobody priced
# this" were the same number in the ledger, and 58% of one bill read as free.
#
# `modelprices.cost_micro_usd` returned 0 for every model absent from
# config/model-prices.yaml. Downstream, that zero compounded three times: the
# hold was reserved at 0, the MissingCeiling guard was skipped (it fires only
# `if cost > 0`), and the settle wrote a row that `report()` summed into a
# confident total. qwen found `claude-opus-5` absent from the yaml; the same
# shape exists one file over in `waterfall.entry`, where a call name missing
# from `enrich.COSTS` silently ledgered 0.
#
# Three states, and only one of them is a zero:
#
#     priced          -> the figure
#     declared free   -> 0, because an entry says 0/0 with a source
#     unpriced        -> UNKNOWN, never 0
#
# These tests are born red at 9748854b2, where the third state does not
# exist: `modelprices.UNKNOWN`, `is_unknown` and `DELIBERATELY_UNPRICED`
# raise AttributeError and every priced-marker assertion fails on a missing
# key. Each fails for its own named reason - the sentinel does not exist, the
# row is not marked, the total is not tainted - which is the state the fix
# has to produce, not a side effect of a collection error.
import tempfile
import unittest

from src import modelprices, spendledger, store


# The models this codebase actually names, priced or not, frozen from the
# grep of 2026-10-16 (src/, scripts/ and the non-stub test fixtures; the
# yaml carries seven of them, the other three are declared below). Regenerate
# with:
#
#   grep -rhoE '"[a-z0-9][a-z0-9./_-]+"' src scripts tests |
#       sort -u    # then keep the model ids by hand
#
# Deliberately NOT here: the stub ids tests invented to be unknown
# (m, stub-model, fake-model-v1, probe-stub, some-local-model,
# totally-unknown-model-xyz, vendor/model, qwen-cli, spy). Pricing those
# would defeat the very tests that use them.
MODELS_IN_USE = (
    "glm-5.3",
    "glm-5.3-flash",
    "claude-sonnet-4-20250514",
    "anthropic/claude-sonnet-4",
    "claude-3-5-sonnet-20241022",
    # The slug OPENROUTER_FIXTURE echoes back (tests/
    # test_model_spend_counts_against_the_client.py). The dated twin
    # claude-3-5-sonnet-20241022 is priced; mapping an undated slug onto a
    # dated snapshot is exactly the guess the yaml's alias comment refuses,
    # so the slug stays unpriced until somebody sources it.
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    # grok-4.6: named by task166/task182 and tests/test_xai_adapter; no
    # in-repo source carries its rates.
    "grok-4.6",
    # claude-opus-5: the model qwen found running through 58% of one bill
    # with no yaml entry at all. The regression test below exists for it.
    "claude-opus-5",
)

USAGE = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}


class IsolatedLedger(unittest.TestCase):
    """A disposable ledger, a fresh run, no holds carried between tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-task0073-")
        self.addCleanup(store.use_directory(self.tmp))
        spendledger._HOLDS.clear()
        self.addCleanup(spendledger._HOLDS.clear)
        self.run_id = spendledger.new_run(f"test-{id(self)}")
        modelprices.reload()


# ------------------------------------------------- state one: priced -> figure

class TheThreeStates(IsolatedLedger):

    def test_a_priced_model_costs_its_figure(self):
        # glm-5.3 is 0.40 in / 1.60 out per 1M (config/model-prices.yaml,
        # as_of 2026-09-26). 1M + 1M tokens is exactly $2.00 = 2,000,000
        # microusd - a figure with no rounding to hide behind.
        cost = modelprices.cost_micro_usd("glm-5.3", USAGE)
        self.assertEqual(cost, 2_000_000)

    def test_a_declared_free_model_costs_an_explicit_zero(self):
        # A 0/0 entry with a source is a DECISION that the call is free,
        # not an absence. It must stay a priced zero so it can never be
        # confused with an unpriced one.
        modelprices._PRICES = {
            "declared-free-test-model": {
                "input_per_1m": 0, "output_per_1m": 0,
                "source": "declared free for this test",
                "as_of": "2026-10-16"}}
        self.addCleanup(lambda: setattr(modelprices, "_PRICES", None))
        cost = modelprices.cost_micro_usd(
            "declared-free-test-model", USAGE)
        self.assertEqual(cost, 0)
        self.assertIsInstance(cost, int)
        self.assertFalse(modelprices.is_unknown(cost))

    def test_an_unpriced_model_is_unknown_not_zero(self):
        # claude-opus-5 is DELIBERATELY_UNPRICED (no sourcable rate in this
        # repository); totally-unknown-model-xyz is simply absent. Both are
        # the same third state, and neither is a number.
        for model in ("claude-opus-5", "totally-unknown-model-xyz"):
            cost = modelprices.cost_micro_usd(model, USAGE)
            self.assertIs(cost, modelprices.UNKNOWN,
                          f"{model} priced as {cost!r}")
            self.assertTrue(modelprices.is_unknown(cost))
            self.assertNotEqual(cost, 0)

    def test_the_unknown_sentinel_refuses_to_be_summed_quietly(self):
        # The whole defect was arithmetic that never noticed it was adding
        # nothing. UNKNOWN therefore refuses arithmetic: a caller that
        # tries to sum it fails loudly rather than confidently wrong.
        unknown = modelprices.UNKNOWN
        self.assertEqual(repr(unknown), "UNKNOWN")
        self.assertTrue(bool(unknown))     # an unknown is an answer, not a shrug
        with self.assertRaises(TypeError):
            unknown + 0
        with self.assertRaises(TypeError):
            int(unknown)


# ------------------------------------------ the regression the brief asked for

class TheRegression(IsolatedLedger):

    def test_the_regression_a_model_id_in_use_is_priced_or_declared_unpriced(
            self):
        # This is the test that would have caught `claude-opus-5` running
        # through most of a bill with no yaml entry: every model id the
        # codebase names must either carry a price or be declared
        # unpriced BY NAME. A new model that slips into the code without
        # either fails here first, before it can ledger silent zeros.
        self.assertIn("claude-opus-5", modelprices.DELIBERATELY_UNPRICED)
        for model in MODELS_IN_USE:
            priced = modelprices.price_for(model) is not None
            declared = model in modelprices.DELIBERATELY_UNPRICED
            self.assertTrue(priced or declared,
                            f"{model} is neither priced nor declared "
                            f"unpriced - add a sourced entry to "
                            f"config/model-prices.yaml or a reason to "
                            f"modelprices.DELIBERATELY_UNPRICED")


# --------------------------------------------- the llm seam: rows and refusals

class TheLlmSeam(IsolatedLedger):

    def _complete(self, model, config, fixture=None):
        """Drive llm.complete offline; return (rows, provider_called)."""
        from src import llm, providers

        body_model = (fixture or {}).get("model") or model
        answer = fixture or {
            "model": body_model,
            "choices": [{"message": {"content": "the answer"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                      "total_tokens": 150},
        }
        seen = []

        def fake_request(method, url, headers, body, timeout=None):
            seen.append(body.get("model"))
            return 200, answer

        real_request = providers.request
        providers.request = fake_request
        self.addCleanup(setattr, providers, "request", real_request)

        llm.OpenAICompatibleModel(
            key="test-key", model=model,
            base="https://api.anthropic.com/v1").complete(
                "hello", config=config)
        return spendledger.load(), seen

    def test_a_caller_that_silently_treats_unknown_as_zero_fails(self):
        # THE NAMED TEST. If any caller on the reserve/settle path flattens
        # UNKNOWN back to a bare zero, the row loses its priced=False
        # marker and this fails by name. A row that says nothing is the
        # defect surviving the fix.
        unlimited = {"budget": {"total": spendledger.UNLIMITED}}
        rows, seen = self._complete("totally-unknown-model-xyz", unlimited)
        self.assertEqual(seen, ["totally-unknown-model-xyz"])
        row = [r for r in rows if r.get("provider") == "anthropic"][0]
        self.assertEqual(row["expected_cost"], 0)      # the floor, and only that
        self.assertIsInstance(row["expected_cost"], int)
        self.assertIs(row.get("priced"), False)
        self.assertIsNone(row.get("usd_estimate"))
        self.assertEqual(row.get("rate_source"), "unknown")
        self.assertEqual(row.get("unit"), "microusd")

    def test_a_finite_ceiling_refuses_an_unpriced_call_before_the_provider(
            self):
        # Operator decision, 2026-09-28 (task425): "the run starts only
        # after a dollar total is verified non-zero on a test call". A
        # ceiling checked against an UNKNOWN cost is not a ceiling - the
        # arithmetic cannot refuse anything - so the call refuses instead.
        # UnpricedCall rides BudgetExceeded so no caller needs new wiring.
        finite = {"budget": {"total": 10_000_000}}
        with self.assertRaises(spendledger.BudgetExceeded) as caught:
            self._complete("totally-unknown-model-xyz", finite)
        self.assertIsInstance(caught.exception, spendledger.UnpricedCall)

    def test_an_unlimited_budget_writes_the_row_and_marks_it(self):
        # `unlimited` is a DECISION, written in the config, so the call
        # proceeds - and the row it writes says priced=False, so the total
        # downstream can tell this zero from a free one.
        unlimited = {"budget": {"total": spendledger.UNLIMITED}}
        rows, _ = self._complete("claude-opus-5", unlimited)
        row = [r for r in rows if r.get("provider") == "anthropic"][0]
        self.assertEqual(row["expected_cost"], 0)
        self.assertIs(row.get("priced"), False)

    def test_the_glm_adapter_settles_an_unpriced_model_without_dying(self):
        # src/providers/glm.py is out of bounds for this lane: it may not
        # be read and it may not be changed. Whatever it does internally,
        # a model it cannot price must still settle into a marked row
        # rather than crash or ledger a confident zero. Driven by emptying
        # the price table, so glm's OWN model - whatever it is - becomes
        # unpriced; the conversion has to happen inside the ledger seam
        # (reserve/settle/record accept UNKNOWN), because the adapter will
        # never be edited to do it.
        from src.providers import glm

        modelprices._PRICES = {}
        self.addCleanup(lambda: setattr(modelprices, "_PRICES", None))

        real_send = glm._send
        glm._send = lambda body, timeout, max_attempts, sleep: (
            200, {
                "model": "glm-5.3",
                "choices": [{"message": {"content": "the answer"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                          "total_tokens": 150},
            }, 0.1)
        self.addCleanup(setattr, glm, "_send", real_send)

        glm.complete("hello", ledger_client="productive",
                     config={"budget": {"total": spendledger.UNLIMITED}})

        rows = [r for r in spendledger.load()
                if r.get("provider") == "glm"]
        self.assertTrue(rows, "glm wrote no ledger row")
        for row in rows:
            self.assertEqual(row["expected_cost"], 0)
            self.assertIs(
                row.get("priced"), False,
                f"glm settled an unpriced call as a bare zero: {row}")
            self.assertIsNone(row.get("usd_estimate"))


# ------------------------------------------------ totals: fail closed, floors

class TheTotals(IsolatedLedger):

    ROW = {"client": "t", "provider": "glm", "call": "complete:glm-5.3",
           "day": "2026-10-16", "at": "2026-10-16T00:00:00Z",
           "unit": "microusd"}

    def test_a_report_total_containing_an_unpriced_row_is_unknown_with_a_floor(
            self):
        rows = [
            dict(self.ROW, expected_cost=1000, run_id="r1"),
            dict(self.ROW, expected_cost=2000, run_id="r1"),
            dict(self.ROW, expected_cost=0, run_id="r1", priced=False),
        ]
        out = spendledger.report(client="t", rows=rows)
        # The total is a tripwire, the known part is a floor and is LABELLED
        # a floor - the same shape the MIXED UNITS tripwire already uses.
        self.assertEqual(out["expected_total"],
                         "UNKNOWN TOTAL - a floor, not a total")
        self.assertEqual(out["expected_floor"], 3000)
        self.assertEqual(out["unpriced_rows"], 1)
        self.assertEqual(out["by_provider"]["glm"],
                         "UNKNOWN TOTAL - a floor, not a total")

    def test_a_report_of_only_priced_rows_is_unchanged(self):
        rows = [dict(self.ROW, expected_cost=1000, run_id="r1"),
                dict(self.ROW, expected_cost=2000, run_id="r1")]
        out = spendledger.report(client="t", rows=rows)
        self.assertEqual(out["expected_total"], 3000)
        self.assertEqual(out["expected_floor"], 3000)
        self.assertEqual(out["unpriced_rows"], 0)
        self.assertEqual(out["by_provider"]["glm"], 3000)


# --------------------------------------------- the waterfall has the same shape

class TheWaterfall(IsolatedLedger):

    def test_the_waterfall_does_not_ledger_an_unknown_call_as_free(self):
        from src import waterfall

        unknown_call = waterfall.entry(
            "company", "contactout", "no-such-call-name")
        self.assertEqual(unknown_call["expected_cost"], 0)
        self.assertIs(unknown_call.get("priced"), False)

        # apify-research is IN enrich.COSTS at 0 and IN enrich.UNPRICED:
        # billed in compute units, so the zero is explicitly not a free.
        unpriced_known = waterfall.entry(
            "company", "apify", "apify-research")
        self.assertEqual(unpriced_known["expected_cost"], 0)
        self.assertIs(unpriced_known.get("priced"), False)

        # webfetch-crawl is IN COSTS at 0 and NOT in UNPRICED: declared
        # free. Its row carries no marker at all, like every priced row.
        declared_free = waterfall.entry(
            "company", "webfetch", "webfetch-crawl")
        self.assertEqual(declared_free["expected_cost"], 0)
        self.assertIsNone(declared_free.get("priced"))

        priced = waterfall.entry("company", "contactout", "email-verifier")
        self.assertEqual(priced["expected_cost"], 1)
        self.assertIsNone(priced.get("priced"))

        rec = {"waterfall": [unknown_call, unpriced_known,
                             declared_free, priced]}
        summary = waterfall.spend(rec)
        self.assertEqual(summary["expected"], 1)       # the floor
        self.assertEqual(summary["unpriced_calls"], 2)
        self.assertEqual(summary["expected_is"], "floor")
        self.assertEqual(
            summary["by_provider"]["contactout"]["unpriced"], 1)


# ------------------------------------------------- costs.py keeps its floor honest

class TheCostsBuckets(IsolatedLedger):

    def test_costs_expected_by_provider_counts_its_unpriced_floor(self):
        from src import costs

        records = [{"waterfall": [
            {"provider": "contactout", "call": "email-verifier",
             "expected_cost": 1, "at": "2026-10-16T00:00:00Z"},
            {"provider": "contactout", "call": "a-call-nobody-priced",
             "expected_cost": 0, "priced": False,
             "at": "2026-10-16T00:00:00Z"},
        ]}]
        out = costs.expected_by_provider(records)
        bucket = out["contactout"]
        self.assertEqual(bucket["expected"], 1)        # the floor
        self.assertEqual(bucket["unpriced"], 1)
        self.assertEqual(bucket["by_call"]["a-call-nobody-priced"]
                         ["unpriced"], 1)


if __name__ == "__main__":
    unittest.main()
