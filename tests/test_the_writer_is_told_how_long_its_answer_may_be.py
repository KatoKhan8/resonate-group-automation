#!/usr/bin/env python3
"""The writer is told how long its answer may be, and a cut-off answer says so.

TASK-942. Two defects, one cause.

THE CAUSE. `grep -c max_tokens src/generate.py` returned 0 on master and 0 on
`task-step-objectives-convergence`; so did `src/generate_campaign.py` and
`src/llm.py`. The writer was never told how long its answer may be, so the only
bound on an eleven-message JSON object was whatever default the endpoint chose.
`llm.OpenAICompatibleModel._estimate_cost` passed 4096 to the spend ledger as a
guess and the HTTP body carried no cap at all - the ledger was reserving against
a number nobody had sent.

THE SYMPTOM, MEASURED 2026-10-01 on the bigfish canary, round 3 of three:

    JSONDecodeError: Expecting ',' delimiter: line 1 column 2724

2724 characters of single-line JSON is about 680 tokens. The answer was a
PREFIX, and the round continued only because `task-step-objectives-convergence`
had already fixed the ACCOUNTING half - a truncation costs one attempt, not the
round. What it did not fix is that the writer still gets no budget, and that a
truncation is reported to the writer in the same words as an answer that
finished wrongly: "the answer was not valid JSON". Those are different failures.
Only one of them is worth asking again with the same prompt.

WHAT IS PROVEN HERE, ALL BY EFFECT AND NONE BY GREP:

* `TestTheBudgetReachesTheModel` - the budget is on the call and in the HTTP
  body. Asserted on what the seam RECEIVES while the real path runs. A test that
  grepped `src/generate_campaign.py` for "max_tokens" would pass the moment
  somebody wrote the word in a comment, and this file's own header would pass it.
* `TestATruncationIsNamedAndCostsOneAttempt` - a stub returning a deliberately
  truncated payload yields `llm.TruncatedAnswer`, is recorded as
  `gc.TRUNCATED`, and spends ONE attempt of ten.
* `TestCutOffIsToldApartFromUnusable` - the control that stops this fix from
  becoming a mask. An answer that FINISHED and is still unreadable, and an
  answer that parses cleanly and is useless, must not be called truncations.
* `TestNothingIsMasked` - `PIPELINE_DEFECTS` still stops the run, `ModelError`
  still propagates, a clean round records nothing.
* `TestTheBudgetIsDerivedNotGuessed` - the number tracks the gates' own
  ceilings, so it cannot be a round guess that drifts away from them.

THE TWO MUTATIONS, RUN 2026-10-02 in this worktree with `__pycache__` wiped
before each measurement and `git diff` confirming a byte-identical restore
afterwards. Both detected on EFFECT - an observed value, never a word in a file:

* BUDGET REMOVED. `max_tokens=WRITER_MAX_TOKENS` deleted from the writer's
  `_call_model` call, nothing else touched. 2 of 30 red:
  `test_the_writer_call_carries_the_budget` (`None != 1759` - the seam was
  handed nothing) and `test_every_retry_carries_it_too`. The wire tests stay
  green by design: they call `llm.OpenAICompatibleModel.complete` directly and
  prove the budget TRAVELS, which is a different claim from the writer SENDING
  one. Two claims, two proofs, and deleting either one of them shows up.
* CLASSIFICATION REMOVED. `_parse_json`'s `_json_unterminated` branch deleted,
  so every unreadable answer raises `llm.UnusableAnswer` exactly as before this
  task. 8 of 30 red, including `test_a_cut_off_answer_is_named_a_truncation`,
  `test_the_two_failures_are_not_described_in_the_same_words`,
  `test_a_cut_off_answer_is_not_told_to_return_valid_json` and
  `test_the_broad_handler_no_longer_answers_for_a_named_class` - while
  `test_an_answer_that_finished_wrongly_is_named_unusable` and
  `test_prose_instead_of_json_is_unusable_not_a_truncation` stayed GREEN. That
  pairing is the evidence that matters: the mutation was caught by the
  DISTINCTION disappearing, not by the parser breaking.

AND THE MEASUREMENT THAT SAYS THIS FILE WAS NEEDED. Under the second mutation
the pre-existing suite notices nothing except the one assertion this task
changed on purpose: `test_a_response_cut_off_before_the_closing_brace_costs_the_same`
in `test_a_truncated_answer_costs_one_attempt_not_the_round.py`, whose old form
asserted "not valid JSON" for a cut-off answer and therefore PASSED with the
classification deleted. The accounting half was tested; the distinction was not.

NO NETWORK IN THIS FILE. Every model here is a stub or a fixture response, and
the HTTP tests patch `providers.request`, the single HTTP seam `tests/offline.py`
watches.

THE ONE THING NO OFFLINE TEST CAN ANSWER was measured separately, 2026-10-02,
with two live calls against the configured endpoint (OpenRouter,
`openai/gpt-4.1-mini`) - model calls, never a provider write - because a budget
the endpoint REJECTS would break the writer path in production and no fixture
would notice:

    max_tokens=16, "Reply with the single word OK":
      body keys sent: ['max_tokens', 'messages', 'model', 'temperature']
      answer 'OK', usage completion_tokens=2. The key is accepted.

    max_tokens=24, asked for five 150-word emails:
      llm.TruncatedAnswer raised, "the endpoint reports finish_reason='length':
      the answer was cut off at the token budget after 91 characters".
      isinstance ValueError True, isinstance llm.ModelError False.

So the budget travels, the endpoint honours it, and a real cut-off answer comes
back named rather than as a `JSONDecodeError`.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import generate_campaign as gc                        # noqa: E402
from src import lint, llm                                      # noqa: E402

#: One answer that satisfies every stage of the pipeline that is not the writer.
#: Each stage reads only its own keys, so a union walks ICP, extract, hypothesis
#: and match with no scripted ordering to keep in step. Obviously synthetic:
#: `acme.test` is a reserved TLD and cannot be a real prospect.
STAGES = {"is_agency": True, "what_they_actually_are": "an agency",
          "facts": [{"text": "Acme builds software.",
                     "quote": "Acme builds software.",
                     "source_url": "https://acme.test/about"}],
          "hypothesis": "h", "qualification": "QUALIFIED",
          "hypothesis_basis": "b", "role_family": "operations",
          "capability_key": "project_management", "angle": "operations",
          "what_changes": "one operational view"}

#: A draft that PARSES and is refused by the gates. Deliberately poor: these
#: tests are about what the loop does with answers it cannot read, so a draft
#: must never accidentally pass and end the loop early.
POOR = {"emails": {k: "short body" for k in
                   ("em1", "em2", "em3", "em4", "em5")},
        "subject": "a", "subject_alt": "b", "subject_breakup": "c",
        "linkedin": {}, "ps": {}}

#: CUT OFF. A full answer sliced mid-string, which is exactly what a token
#: budget produces: the object opened, a string opened, and the text ended.
CUT_OFF = json.dumps(POOR)[:120]

#: FINISHED AND WRONG. Every brace balances - the model stopped where it meant
#: to - and the document is still invalid, because two values sit side by side
#: with no comma between them. `json.loads` reports "Expecting ',' delimiter",
#: the same sentence the canary's truncation produced, which is precisely why
#: the error message cannot be what tells the two apart.
FINISHED_WRONG = '{"emails": {"em1": "a" "em2": "b"}, "subject": "s"}'

#: FINISHED AND NOT JSON AT ALL.
PROSE = "I'd be happy to help with that. Which company is this for?"


class RecordingStub:
    """Answers the non-writer stages, and the writer from a script.

    Records the token budget of every call, because the only honest way to
    prove the budget is sent is to look at what the seam was handed while the
    production path ran.
    """

    name = "recording-stub"

    def __init__(self, writer_answers):
        self.writer_answers = list(writer_answers)
        self.writer_calls = 0
        self.prompts = []
        self.calls = []

    def complete(self, prompt, temperature=0, client=None, config=None,
                 max_tokens=None):
        self.prompts.append(prompt)
        is_writer = "THE PLAN. Write to it." in prompt
        self.calls.append({"writer": is_writer, "max_tokens": max_tokens})
        if not is_writer:
            return json.dumps(STAGES)
        self.writer_calls += 1
        idx = min(self.writer_calls - 1, len(self.writer_answers) - 1)
        answer = self.writer_answers[idx]
        if isinstance(answer, Exception):
            raise answer
        return answer

    @property
    def writer_budgets(self):
        return [c["max_tokens"] for c in self.calls if c["writer"]]

    @property
    def other_budgets(self):
        return [c["max_tokens"] for c in self.calls if not c["writer"]]


def run_contact(writer_answers):
    """Run the real `_process_contact` against the stub. Returns (stub, result)."""
    offer = gc._select_offers("productive", "champion")["OFFER-B-OPERATIONS"]
    model = RecordingStub(writer_answers)
    result = gc._process_contact(
        {"email": "petra@acme.test", "first_name": "Petra",
         "last_name": "Horvat", "title": "Operations Director",
         "contact_key": "petra-horvat", "linkedin": "",
         "sender_name": "Ivan Mamic"},
        "Acme", "acme.test", [],
        {"project_management": "Productive is one system for projects."},
        {"angle": "operations"}, [], {"name": "Productive"}, model,
        client_name="productive", offer=offer,
        offer_id="OFFER-B-OPERATIONS", messaging_rules=None,
        account={"company": "Acme", "domain": "acme.test",
                 "persona": "champion", "segment": "productive",
                 "sources": []})
    return model, result


class TestTheBudgetReachesTheModel(unittest.TestCase):
    """Asserted on what the call RECEIVES, by running the path."""

    def test_the_writer_call_carries_the_budget(self):
        """Before TASK-942 every one of these was `None`."""
        model, _ = run_contact([json.dumps(POOR)])
        self.assertTrue(model.writer_budgets, "the writer was never called")
        for budget in model.writer_budgets:
            self.assertEqual(gc.WRITER_MAX_TOKENS, budget)

    def test_every_retry_carries_it_too(self):
        """A budget on attempt 1 and not on attempt 7 is nine truncations."""
        model, _ = run_contact([json.dumps(POOR)])
        self.assertEqual(gc.MAX_WRITER_ATTEMPTS, len(model.writer_budgets))
        self.assertEqual({gc.WRITER_MAX_TOKENS}, set(model.writer_budgets))

    def test_the_short_stages_are_deliberately_given_none(self):
        """ICP, extract, hypothesis and match ask for a verdict, not a letter.

        Their requests are UNCHANGED by TASK-942, and that is a decision rather
        than an omission: a cap on a short answer buys nothing and can only cut
        one.
        """
        model, _ = run_contact([json.dumps(POOR)])
        self.assertTrue(model.other_budgets)
        self.assertEqual({None}, set(model.other_budgets))

    def test_the_counting_wrapper_forwards_the_budget(self):
        """`_CountedModel` wraps the model on every production run.

        A wrapper that accepted the budget and dropped it would be
        indistinguishable from never setting one.
        """
        from src import generate

        class Inner:
            name = "inner"

            def __init__(self):
                self.seen = []

            def complete(self, prompt, temperature=0, client=None,
                         config=None, max_tokens=None):
                self.seen.append(max_tokens)
                return "{}"

        inner = Inner()
        generate._CountedModel(inner).complete("hi", max_tokens=1234)
        generate._CountedModel(inner).complete("hi")
        self.assertEqual([1234, None], inner.seen)


class TestTheBudgetReachesTheWire(unittest.TestCase):
    """And into the request body, where the endpoint can read it."""

    def setUp(self):
        from src import spendledger, store
        self.tmp = tempfile.mkdtemp(prefix="rga-942-")
        self.addCleanup(store.use_directory(self.tmp))
        spendledger._HOLDS.clear()
        self.addCleanup(spendledger._HOLDS.clear)
        spendledger.new_run("test-942-%d" % id(self))

    def _model_and_bodies(self, response=None):
        from src import providers
        bodies = []
        fixture = response or {
            "model": "stub-model",
            "choices": [{"message": {"content": '{"ok": true}'},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        }

        def fake_request(method, url, headers, body, timeout=None):
            bodies.append(body)
            return 200, fixture

        real = providers.request
        providers.request = fake_request
        self.addCleanup(setattr, providers, "request", real)
        model = llm.OpenAICompatibleModel(
            key="test-key", model="stub-model",
            base="https://stub.test/v1")
        return model, bodies

    def test_the_budget_reaches_the_chat_completions_body(self):
        model, bodies = self._model_and_bodies()
        model.complete("hello", max_tokens=gc.WRITER_MAX_TOKENS)
        self.assertEqual(1, len(bodies))
        self.assertEqual(gc.WRITER_MAX_TOKENS, bodies[0].get("max_tokens"))

    def test_no_budget_means_the_key_is_absent_not_null(self):
        """Unchanged behaviour for every caller that has no opinion.

        `"max_tokens": null` is not the same request: endpoints that accept the
        key reject an explicit null.
        """
        model, bodies = self._model_and_bodies()
        model.complete("hello")
        self.assertNotIn("max_tokens", bodies[0])

    def test_the_endpoints_own_cut_off_report_is_named_a_truncation(self):
        """`finish_reason == "length"` is the authoritative witness.

        Returned as if whole before TASK-942, which is how a prefix reached
        `_parse_json` and became a `JSONDecodeError`.
        """
        model, _ = self._model_and_bodies(response={
            "model": "stub-model",
            "choices": [{"message": {"content": '{"emails": {"em1": "a'},
                         "finish_reason": "length"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1759},
        })
        with self.assertRaises(llm.TruncatedAnswer) as caught:
            model.complete("hello", max_tokens=gc.WRITER_MAX_TOKENS)
        self.assertIn("finish_reason='length'", str(caught.exception))

    def test_a_provider_truncation_is_not_a_model_error(self):
        """It must not reach `_process_contact`'s `except llm.ModelError: raise`.

        If it did, one cut-off answer would stop the whole account's run - the
        opposite of costing one attempt.
        """
        self.assertFalse(issubclass(llm.TruncatedAnswer, llm.ModelError))
        self.assertTrue(issubclass(llm.TruncatedAnswer, ValueError))
        self.assertNotIn(llm.TruncatedAnswer, gc.PIPELINE_DEFECTS)

    def test_the_tokens_are_still_paid_for(self):
        """Settled before raising: the call happened and the money went.

        A truncation that skipped the ledger would make the budget invisible to
        the spend gate exactly when it was being hit.
        """
        from src import spendledger
        before = len(spendledger.load())
        model, _ = self._model_and_bodies(response={
            "model": "stub-model",
            "choices": [{"message": {"content": '{"a'},
                         "finish_reason": "length"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1759},
        })
        with self.assertRaises(llm.TruncatedAnswer):
            model.complete("hello", max_tokens=gc.WRITER_MAX_TOKENS)
        self.assertGreater(len(spendledger.load()), before)


class TestATruncationIsNamedAndCostsOneAttempt(unittest.TestCase):

    def test_a_cut_off_answer_is_named_a_truncation(self):
        model, result = run_contact([CUT_OFF, json.dumps(POOR)])
        self.assertEqual([gc.TRUNCATED],
                         (result.get("writer_parse_refusals") or [])[:1])
        self.assertGreater(model.writer_calls, 1)

    def test_it_costs_one_attempt_and_not_the_round(self):
        model, result = run_contact([CUT_OFF, json.dumps(POOR)])
        self.assertEqual(gc.MAX_WRITER_ATTEMPTS, model.writer_calls)
        self.assertEqual(gc.MAX_WRITER_ATTEMPTS, result.get("gate_attempts"))
        self.assertNotEqual("error", result.get("hold_kind"))

    def test_a_round_of_nothing_but_truncations_is_refused_not_errored(self):
        model, result = run_contact([CUT_OFF])
        self.assertEqual(gc.MAX_WRITER_ATTEMPTS, model.writer_calls)
        self.assertEqual("copy_refused", result.get("hold_kind"))
        self.assertEqual([gc.TRUNCATED] * gc.MAX_WRITER_ATTEMPTS,
                         result.get("writer_parse_refusals"))
        self.assertEqual({}, result.get("sequences"))
        self.assertEqual({}, result.get("subjects"))

    def test_the_truncation_reason_reaches_the_next_prompt(self):
        """A refusal the writer is never told is an attempt spent on nothing."""
        model, _ = run_contact([CUT_OFF, json.dumps(POOR)])
        writer_prompts = [p for p in model.prompts
                          if "THE PLAN. Write to it." in p]
        self.assertGreaterEqual(len(writer_prompts), 2)
        self.assertIn("WAS CUT OFF", writer_prompts[1])
        self.assertIn("SHORTER", writer_prompts[1])

    def test_a_cut_off_answer_is_not_told_to_return_valid_json(self):
        """It already did. Its JSON was valid as far as it got.

        The instruction that fixes a truncation is "write less", and spending an
        attempt telling the model to do what it was already doing is the cost
        of collapsing the two classes into one sentence.
        """
        _, result = run_contact([CUT_OFF, json.dumps(POOR)])
        first = (result.get("gate_rejections") or [""])[0]
        self.assertNotIn("not valid JSON", first)
        self.assertIn("SHORTER", first)


class TestCutOffIsToldApartFromUnusable(unittest.TestCase):
    """The control. A fix that called every unreadable answer a truncation
    would pass every test above and would be a mask, not a fix."""

    def test_an_answer_that_finished_wrongly_is_named_unusable(self):
        """Balanced braces mean the model stopped where it meant to.

        `json.loads` says "Expecting ',' delimiter" here - the canary
        truncation's own words - so the classification cannot be reading the
        error message, and does not.
        """
        _, result = run_contact([FINISHED_WRONG, json.dumps(POOR)])
        self.assertEqual([gc.UNUSABLE],
                         (result.get("writer_parse_refusals") or [])[:1])

    def test_prose_instead_of_json_is_unusable_not_a_truncation(self):
        _, result = run_contact([PROSE, json.dumps(POOR)])
        self.assertEqual([gc.UNUSABLE],
                         (result.get("writer_parse_refusals") or [])[:1])

    def test_the_two_failures_are_not_described_in_the_same_words(self):
        """The whole point: the caller can tell them apart, and so can the model."""
        _, cut = run_contact([CUT_OFF, json.dumps(POOR)])
        _, wrong = run_contact([FINISHED_WRONG, json.dumps(POOR)])
        cut_reason = (cut.get("gate_rejections") or [""])[0]
        wrong_reason = (wrong.get("gate_rejections") or [""])[0]
        self.assertNotEqual(cut_reason, wrong_reason)
        self.assertIn("WAS CUT OFF", cut_reason)
        self.assertNotIn("WAS CUT OFF", wrong_reason)
        self.assertIn("not valid JSON", wrong_reason)
        self.assertNotIn("not valid JSON", cut_reason)

    def test_a_mixed_round_records_both_kinds_in_order(self):
        _, result = run_contact([CUT_OFF, FINISHED_WRONG, PROSE,
                                 json.dumps(POOR)])
        self.assertEqual([gc.TRUNCATED, gc.UNUSABLE, gc.UNUSABLE],
                         result.get("writer_parse_refusals"))

    def test_the_classifier_reads_structure_and_not_the_error_text(self):
        """Directly, on `_parse_json`, so the boundary is pinned in one place."""
        with self.assertRaises(llm.TruncatedAnswer):
            gc._parse_json('{"emails": {"em1": "half a sen')
        with self.assertRaises(llm.TruncatedAnswer):
            gc._parse_json('{"emails": {"em1": "done"}')
        with self.assertRaises(llm.UnusableAnswer):
            gc._parse_json(FINISHED_WRONG)
        with self.assertRaises(llm.UnusableAnswer):
            gc._parse_json(PROSE)
        with self.assertRaises(llm.UnusableAnswer):
            gc._parse_json('{"emails": {"em1": "a",}}')

    def test_an_escaped_quote_does_not_look_like_an_open_string(self):
        """A body ending in an escaped quote is complete, not cut off.

        The scan has to honour `\\"` or every email that quotes something would
        be reported as a truncation.
        """
        self.assertEqual({"a": 'he said "hi"'},
                         gc._parse_json(json.dumps({"a": 'he said "hi"'})))

    def test_trailing_prose_after_a_closed_object_is_not_a_truncation(self):
        self.assertEqual({"a": 1},
                         gc._parse_json('{"a": 1} Hope this helps!'))


class TestNothingIsMasked(unittest.TestCase):

    def test_an_answer_that_parses_to_the_wrong_types_still_stops_the_run(self):
        """`PIPELINE_DEFECTS` is untouched: a shape fault is a defect, not a hold."""
        with self.assertRaises(gc.CampaignPipelineError):
            run_contact(['{"emails": "not a dict", "subject": "s"}'])

    def test_valid_json_that_is_merely_useless_is_refused_by_the_gates(self):
        """NOT recorded as a truncation, and not stored either.

        An answer with none of the keys asked for parses perfectly. It is the
        gates' job to refuse it, and this says the parse classifier keeps its
        hands off: `writer_parse_refusals` is EMPTY while `hold_kind` is
        `copy_refused`.
        """
        _, result = run_contact(['{"what": "is a cold email?"}'])
        self.assertEqual([], result.get("writer_parse_refusals"))
        self.assertEqual("copy_refused", result.get("hold_kind"))
        self.assertEqual({}, result.get("sequences"))

    def test_a_model_error_still_propagates_and_is_not_spent_as_attempts(self):
        """A rate limit is a fact about us, never ten writer attempts."""
        with self.assertRaises(llm.ModelError):
            run_contact([llm.ModelUnavailable("429 from the endpoint")])

    def test_a_clean_round_records_no_parse_refusal_at_all(self):
        _, result = run_contact([json.dumps(POOR)])
        self.assertEqual([], result.get("writer_parse_refusals"))
        for reason in result.get("gate_rejections") or []:
            self.assertNotIn("WAS CUT OFF", reason)
            self.assertNotIn("not valid JSON", reason)

    def test_the_broad_handler_no_longer_answers_for_a_named_class(self):
        """An unreadable answer from a NON-writer stage is named, not "error".

        Stages A to E call `_parse_json` too, and every unreadable answer from
        them landed in the bottom `except Exception` as `hold_kind="error"` -
        the same anonymous bucket as a crash in our own code. Measured here by
        handing stage A a cut-off verdict.
        """
        class CutOffAtStageA:
            name = "cut-off-at-stage-a"

            def complete(self, prompt, temperature=0, client=None,
                         config=None, max_tokens=None):
                return '{"is_agency": tr'

        offer = gc._select_offers("productive",
                                  "champion")["OFFER-B-OPERATIONS"]
        result = gc._process_contact(
            {"email": "petra@acme.test", "first_name": "Petra",
             "last_name": "Horvat", "title": "Operations Director",
             "contact_key": "petra-horvat", "linkedin": "",
             "sender_name": "Ivan Mamic"},
            "Acme", "acme.test", [],
            {"project_management": "Productive is one system."},
            {"angle": "operations"}, [], {"name": "Productive"},
            CutOffAtStageA(), client_name="productive", offer=offer,
            offer_id="OFFER-B-OPERATIONS", messaging_rules=None,
            account={"company": "Acme", "domain": "acme.test",
                     "persona": "champion", "segment": "productive",
                     "sources": []})
        self.assertEqual("model_answer_truncated", result.get("hold_kind"))
        self.assertNotEqual("error", result.get("hold_kind"))
        self.assertEqual({}, result.get("sequences"))


class TestTheBudgetIsDerivedNotGuessed(unittest.TestCase):

    #: Measured 2026-10-02 on `work/queue.jsonl` with `cl100k_base`: the richest
    #: complete payload this pipeline has produced is `waynemedia-com` /
    #: `julia-piehler` at 3942 characters and 795 tokens - 4.96 characters per
    #: token. 4.5 is the conservative figure used below, so the assertion is
    #: harder to satisfy than reality.
    CHARS_PER_TOKEN = 4.5

    def _answer_at_every_ceiling(self):
        """The largest answer the gates would ACCEPT, built from their limits."""
        body = " ".join(["word"] * lint.MAX_WORDS)
        note = "n" * lint.NOTE_MAX_CHARS
        subject = "s" * (lint.MAX_SUBJECT - 1)
        return json.dumps({
            "subject": subject, "subject_alt": subject,
            "subject_breakup": subject,
            "emails": {k: body for k in ("em1", "em2", "em3", "em4", "em5")},
            "linkedin": {k: note for k in gc.LINKEDIN_WRITER_KEYS},
            "ps": {"em1": "p" * gc._PS_MAX_CHARS,
                   "em3": "p" * gc._PS_MAX_CHARS},
            "hold": False, "hold_reason": ""})

    def test_the_budget_covers_the_biggest_answer_a_gate_would_accept(self):
        """Otherwise the budget itself refuses copy the gates would have passed.

        This is the direction that matters: a budget below the gates' own
        ceilings would turn a legal draft into a truncation, which is a new
        defect wearing the old one's clothes.
        """
        needed = len(self._answer_at_every_ceiling()) / self.CHARS_PER_TOKEN
        self.assertGreaterEqual(gc.WRITER_MAX_TOKENS, needed)

    def test_it_is_not_absurdly_larger_than_what_is_asked_for(self):
        """A budget of 100,000 is not a budget. Twice the ceiling is the bound."""
        needed = len(self._answer_at_every_ceiling()) / self.CHARS_PER_TOKEN
        self.assertLess(gc.WRITER_MAX_TOKENS, needed * 2)

    def test_every_term_comes_from_a_contract_and_not_from_a_hand(self):
        """The arithmetic is restated against `lint`'s LIVE constants.

        Replace the derivation with a literal and this goes red; raise
        `lint.MAX_WORDS` without re-deriving and it goes red too. Which is the
        only thing that keeps the budget and the gates from drifting apart.
        """
        expected = int(
            5 * lint.MAX_WORDS * gc._TOKENS_PER_WORD
            + len(gc.LINKEDIN_WRITER_KEYS) * lint.NOTE_MAX_CHARS
            * gc._TOKENS_PER_CHAR
            + 3 * lint.MAX_SUBJECT * gc._TOKENS_PER_CHAR
            + 2 * gc._PS_MAX_CHARS * gc._TOKENS_PER_CHAR
            + gc._WRITER_JSON_SCAFFOLD_TOKENS
            + gc._FENCE_ALLOWANCE_TOKENS)
        self.assertEqual(expected, gc.WRITER_MAX_TOKENS)

    def test_it_is_not_one_of_the_numbers_a_guess_would_have_picked(self):
        self.assertNotIn(gc.WRITER_MAX_TOKENS,
                         (256, 512, 1000, 1024, 1500, 2000, 2048, 4000, 4096,
                          8000, 8192))


if __name__ == "__main__":
    unittest.main()
