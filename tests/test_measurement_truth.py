"""Measurement that is real, or says it is not.

The 5,000-domain benchmark is instructed to measure first and optimise from
nothing else. That is only safe if every counter it reads is produced by the
thing it claims to count. Two were not:

  - `waterfall.counters()` computed seven policy counters for no production
    caller; its only callers were four assertions in this suite's sibling
    `test_contactout_fallback_semantics.py`.
  - `CONTACTOUT_CACHE_HITS` defaulted to 0 and had no producer anywhere.
    `grep -c cache src/providers/contactout.py` returns 0: there is no
    ContactOut cache, so 0 was not a low hit rate, it was a measurement of
    something that does not happen.

These tests hold both halves of each: the counter moves when the thing it
counts happens, it does not move when it does not, and a number that cannot
be derived reports UNKNOWN rather than 0.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import enrich, llm, run, store, waterfall
from tests.base import FIXTURES, ProviderTest, qualify_everything


# --------------------------------------------------------------- fake adapters
#
# Shaped exactly like the two real ones, and only in the respect under test:
# what each appends to `self.calls`. `OpenAICompatibleModel.complete` appends
# the three token counts when the endpoint reports `usage`; `QwenCliModel`
# appends model, seconds and chars and nothing else, because the CLI returns
# text and there is no usage object to read.

class UsageReportingModel:
    """An OpenAI-compatible adapter's `calls` row: tokens included."""

    name = "openai-compatible"

    def __init__(self, *answers, tokens=(100, 40)):
        self.answers = list(answers)
        self.calls = []
        self._tokens = tokens

    def complete(self, prompt, temperature=0):
        if not self.answers:
            raise llm.ModelError("fake model ran out of answers")
        answer = self.answers.pop(0)
        text = answer if isinstance(answer, str) else json.dumps(answer)
        prompt_tokens, completion_tokens = self._tokens
        self.calls.append({
            "model": "fake-model-v1",
            "seconds": 0.5,
            "chars": len(text),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        })
        return text


class NoUsageModel:
    """`QwenCliModel`'s `calls` row: seconds and chars, never a token count."""

    name = "qwen-cli"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def complete(self, prompt, temperature=0):
        if not self.answers:
            raise llm.ModelError("fake model ran out of answers")
        answer = self.answers.pop(0)
        text = answer if isinstance(answer, str) else json.dumps(answer)
        self.calls.append({"model": "qwen-cli", "seconds": 2.0,
                           "chars": len(text)})
        return text


# `draft` is the step used throughout: its schema is shape-only, so these
# tests measure the usage recorder rather than the traceability gates that
# `hook` and `persona_angle` apply when `rec` is passed.
DRAFT = {"subject": "five offices, one finance function",
         "body": "A body long enough to be a real draft. " * 6}


class TokenUsageIsRecordedWhenItHappens(unittest.TestCase):
    """`llm.ask` writes what the call cost onto the record it was asked for."""

    def test_a_reporting_adapter_writes_one_row_per_call(self):
        rec = {"id": "acme", "company_facts": {"name": "Acme"}}
        model = UsageReportingModel(DRAFT)
        llm.ask(model, "draft", "prompt", rec=rec, extra_check=lambda d: None)
        rows = rec["model_calls"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["step"], "draft")
        self.assertEqual(rows[0]["model"], "fake-model-v1")
        self.assertEqual(rows[0]["prompt_tokens"], 100)
        self.assertEqual(rows[0]["completion_tokens"], 40)
        self.assertEqual(rows[0]["total_tokens"], 140)
        self.assertEqual(rows[0]["seconds"], 0.5)

    def test_every_attempt_is_recorded_not_only_the_one_that_validated(self):
        """A rejected answer is billed exactly like an accepted one."""
        rec = {"id": "acme", "company_facts": {"name": "Acme"}}
        model = UsageReportingModel("not json at all", DRAFT)
        llm.ask(model, "draft", "prompt", rec=rec, extra_check=lambda d: None)
        self.assertEqual(len(rec["model_calls"]), 2)
        self.assertEqual(sum(r["total_tokens"] for r in rec["model_calls"]), 280)

    def test_a_field_the_adapter_did_not_report_is_absent_not_zero(self):
        rec = {"id": "acme"}
        model = NoUsageModel(DRAFT)
        llm.ask(model, "draft", "prompt", rec=rec, extra_check=lambda d: None)
        row = rec["model_calls"][0]
        self.assertEqual(row["seconds"], 2.0)
        self.assertNotIn("total_tokens", row)
        self.assertNotIn("prompt_tokens", row)


class TokenUsageIsNotRecordedWhenItDoesNotHappen(unittest.TestCase):
    """The other half. A counter that moves when nothing happened is worse."""

    def test_no_record_means_no_row_anywhere(self):
        model = UsageReportingModel(DRAFT)
        llm.ask(model, "draft", "prompt", rec=None, extra_check=lambda d: None)
        self.assertEqual(model.calls and len(model.calls), 1)   # the call happened

    def test_an_adapter_that_reports_nothing_writes_nothing(self):
        """`ScriptedModel` has no `calls` at all. Silence, not a zero row."""
        rec = {"id": "acme"}
        llm.ask(llm.ScriptedModel(json.dumps(DRAFT)), "draft", "prompt", rec=rec,
                extra_check=lambda d: None)
        self.assertNotIn("model_calls", rec)

    def test_a_stale_row_is_never_attributed_to_a_call_that_reported_none(self):
        """The mark is the whole point.

        `calls[-1]` would have re-attributed the previous call's tokens to a
        call that reported nothing, which is how a counter invents data.
        """
        rec = {"id": "acme"}
        model = UsageReportingModel(DRAFT)
        llm.ask(model, "draft", "prompt", rec=rec, extra_check=lambda d: None)
        self.assertEqual(len(rec["model_calls"]), 1)

        # A second ask whose adapter appends nothing this time.
        model.answers = [DRAFT]
        model.complete = lambda prompt, temperature=0: json.dumps(DRAFT)
        llm.ask(model, "draft", "prompt", rec=rec, extra_check=lambda d: None)
        self.assertEqual(len(rec["model_calls"]), 1,
                         "a call that reported no usage must add no row")

    def test_an_adapter_whose_calls_is_not_a_usage_list_is_ignored(self):
        """Regression. `calls` is not a reserved name.

        `tests/test_e2e.py`'s `E2EModel.calls` is an INTEGER call counter. An
        earlier version of `usage_mark` called `len()` on it, raised
        `TypeError` inside `ask` - which is not a `SchemaError`, so it escaped
        the retry loop - and failed the generate step for every record in the
        batch. Caught by `test_e2e`; held here so it stays caught.
        """
        class IntCounterModel:
            name = "e2e"

            def __init__(self):
                self.calls = 0

            def complete(self, prompt, temperature=0):
                self.calls += 1
                return json.dumps(DRAFT)

        rec = {"id": "acme"}
        model = IntCounterModel()
        # TWICE. The counter starts at 0, and `0 or ()` is `()` - so a single
        # call would slip past the broken version and this test would pass
        # against the bug it exists to catch. It is the SECOND `usage_mark`,
        # reading a truthy 1, that raises. `test_e2e` failed on record two.
        for _ in range(2):
            data, attempt, errors = llm.ask(model, "draft", "prompt", rec=rec)
        self.assertEqual(data["subject"], DRAFT["subject"])
        self.assertEqual(model.calls, 2)
        self.assertNotIn("model_calls", rec)

    def test_a_non_dict_row_is_skipped_rather_than_recorded(self):
        class OddRowModel:
            name = "odd"

            def __init__(self):
                self.calls = []

            def complete(self, prompt, temperature=0):
                self.calls.append("a string, not a usage row")
                return json.dumps(DRAFT)

        rec = {"id": "acme"}
        llm.ask(OddRowModel(), "draft", "prompt", rec=rec)
        self.assertEqual(rec.get("model_calls", []), [])

    def test_a_refused_call_adds_no_row(self):
        """`NoModel` raises before anything is spent."""
        rec = {"id": "acme"}
        with self.assertRaises(llm.NoModelConfigured):
            llm.ask(llm.NoModel(), "draft", "prompt", rec=rec)
        self.assertNotIn("model_calls", rec)


class AMetricThatCannotBeDerivedReportsUnknown(unittest.TestCase):
    """UNKNOWN is never silently a number. This repository's convention."""

    def test_cache_hits_are_unknown_because_there_is_no_cache(self):
        """The named gap. No producer exists, so 0 would be a false claim.

        A benchmark reading 0 here would compute CACHE_HIT_RATE = 0% and
        believe it, when the truth is that no cache was ever consulted.
        """
        c = waterfall.counters([])
        self.assertEqual(c["CONTACTOUT_CACHE_HITS"], waterfall.UNKNOWN)
        self.assertNotEqual(c["CONTACTOUT_CACHE_HITS"], 0)

    def test_a_real_producer_would_report_its_real_number(self):
        """UNKNOWN is the default, not a refusal to ever count."""
        self.assertEqual(waterfall.counters([], cache_hits=42)
                         ["CONTACTOUT_CACHE_HITS"], 42)
        self.assertEqual(waterfall.counters([], cache_hits=0)
                         ["CONTACTOUT_CACHE_HITS"], 0,
                         "a producer that measured zero hits may say zero")

    def test_tokens_are_unknown_for_a_model_that_reports_none(self):
        """The Qwen lane. Not merely unwired - unobtainable from the CLI."""
        rec = {"id": "acme"}
        llm.ask(NoUsageModel(DRAFT), "draft", "prompt", rec=rec,
                extra_check=lambda d: None)
        usage = llm.token_usage([rec])
        qwen = usage["by_model"]["qwen-cli"]
        self.assertEqual(qwen["calls"], 1)
        self.assertEqual(qwen["calls_missing_tokens"], 1)
        self.assertEqual(qwen["total_tokens"], llm.UNKNOWN)
        self.assertEqual(qwen["per_domain"], llm.UNKNOWN)
        self.assertEqual(usage["tokens_per_domain"], llm.UNKNOWN)

    def test_a_partial_measurement_does_not_masquerade_as_a_total(self):
        """One model measured, one not. The run total stays UNKNOWN.

        The measured part is not discarded - it is reported under a name that
        says it is a part.
        """
        rec = {"id": "acme"}
        llm.ask(UsageReportingModel(DRAFT), "draft", "p", rec=rec,
                extra_check=lambda d: None)
        llm.ask(NoUsageModel(DRAFT), "draft", "p", rec=rec,
                extra_check=lambda d: None)
        usage = llm.token_usage([rec])
        self.assertEqual(usage["by_model"]["fake-model-v1"]["total_tokens"], 140)
        self.assertEqual(usage["by_model"]["qwen-cli"]["total_tokens"],
                         llm.UNKNOWN)
        self.assertEqual(usage["tokens_per_domain"], llm.UNKNOWN)
        self.assertEqual(usage["by_model"]["qwen-cli"]["measured_total_tokens"],
                         0)

    def test_a_run_with_no_model_call_has_unknown_tokens_per_domain_not_zero(self):
        """0.0 would read as "the model was free" rather than "nobody asked"."""
        usage = llm.token_usage([{"id": "a"}, {"id": "b"}])
        self.assertEqual(usage["domains"], 2)
        self.assertEqual(usage["domains_with_model_calls"], 0)
        self.assertEqual(usage["tokens_per_domain"], llm.UNKNOWN)

    def test_a_complete_measurement_is_a_number(self):
        """UNKNOWN must be earned, not the answer to everything."""
        recs = [{"id": "a"}, {"id": "b"}]
        for rec in recs:
            llm.ask(UsageReportingModel(DRAFT), "draft", "p", rec=rec,
                    extra_check=lambda d: None)
        usage = llm.token_usage(recs)
        self.assertEqual(usage["tokens_per_domain"], 140.0)
        self.assertEqual(usage["by_model"]["fake-model-v1"]["per_domain"], 140.0)


class TheLedgerCountersCountTheLedger(unittest.TestCase):
    """`waterfall.counters` moves on a real row and not otherwise."""

    def test_a_contactout_step_increments_contactout_calls(self):
        rec = {"id": "test"}
        waterfall.record_step(rec, "people_discovery", waterfall.CONTACTOUT,
                              "people-count")
        self.assertEqual(waterfall.counters([rec])["CONTACTOUT_CALLS"], 1)

    def test_a_record_with_no_ledger_increments_nothing(self):
        c = waterfall.counters([{"id": "test"}])
        self.assertEqual(c["CONTACTOUT_CALLS"], 0)
        self.assertEqual(c["OTHER_PROVIDER_ESCALATIONS"], 0)
        self.assertEqual(c["CONTACTOUT_CONFIRMED_MISSES"], 0)

    def test_a_contactout_step_is_not_counted_as_an_escalation(self):
        """The thing it does not count. A primary call is not a fallback."""
        rec = {"id": "test"}
        waterfall.record_step(rec, "people_discovery", waterfall.CONTACTOUT,
                              "people-count")
        c = waterfall.counters([rec])
        self.assertEqual(c["OTHER_PROVIDER_ESCALATIONS"], 0)
        self.assertEqual(c["escalation_reasons"], [])

    def test_a_fallback_increments_the_escalation_and_carries_its_reason(self):
        rec = {"id": "test"}
        waterfall.record_step(rec, "people_discovery", waterfall.CONTACTOUT,
                              "people-count")
        waterfall.record_step(rec, "people_discovery", waterfall.AIARK,
                              "aiark-people-search",
                              reason=enrich.CONTACTOUT_NO_PEOPLE)
        c = waterfall.counters([rec])
        self.assertEqual(c["CONTACTOUT_CONFIRMED_MISSES"], 1)
        self.assertEqual(c["OTHER_PROVIDER_ESCALATIONS"], 1)
        self.assertEqual(c["escalation_reasons"][0]["reason"],
                         enrich.CONTACTOUT_NO_PEOPLE)


class TheCountersHaveAProductionCaller(ProviderTest):
    """The other named gap: seven correct counters that nothing computed.

    Asserted on what `run.run` RETURNS, not on the text of `src/run.py`.
    A source-text test would pass on a comment mentioning `counters`.
    """

    fixture = "phase4.jsonl"

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="rga-measure-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, self.fixture), self.queue)
        self._prev = os.environ.get("QUEUE"), os.environ.get("OUT")
        os.environ["QUEUE"], os.environ["OUT"] = self.queue, self.out
        qualify_everything()

    def tearDown(self):
        for name, value in zip(("QUEUE", "OUT"), self._prev):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def test_a_dry_run_reports_the_seven_policy_counters(self):
        report = run.run(stages=("enrich",))
        self.assertIn("counters", report,
                      "the run report must carry the routing policy counters")
        for name in ("CONTACTOUT_CALLS", "CONTACTOUT_CACHE_HITS",
                     "CONTACTOUT_CONFIRMED_MISSES", "CONTACTOUT_ERRORS",
                     "CRAWLER_CALLS", "GROK_ESCALATIONS",
                     "OTHER_PROVIDER_ESCALATIONS"):
            self.assertIn(name, report["counters"])

    def test_the_run_report_says_cache_hits_are_unknown(self):
        report = run.run(stages=("enrich",))
        self.assertEqual(report["counters"]["CONTACTOUT_CACHE_HITS"],
                         waterfall.UNKNOWN)

    def test_a_dry_run_reports_token_usage(self):
        report = run.run(stages=("enrich",))
        self.assertIn("tokens", report)
        self.assertEqual(report["tokens"]["tokens_per_domain"], llm.UNKNOWN,
                         "no model ran, so tokens per domain is not 0")

    def test_the_counters_agree_with_the_ledger_they_are_derived_from(self):
        """No second counter store. The ledger is the only source."""
        report = run.run(stages=("enrich",))
        recs = store.load()
        from_ledger = sum(1 for r in recs for row in waterfall.ledger(r)
                          if row.get("provider") == waterfall.CONTACTOUT)
        self.assertEqual(report["counters"]["CONTACTOUT_CALLS"], from_ledger)


if __name__ == "__main__":
    unittest.main()
