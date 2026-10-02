#!/usr/bin/env python3
"""A model answer that does not parse costs ONE attempt, never the round.

MEASURED 2026-10-01, the canary record, round 3 of three:

    JSONDecodeError: Expecting ',' delimiter: line 1 column 2811 (char 2810)

`json.JSONDecodeError` is a `ValueError`; `ValueError` is deliberately not in
`PIPELINE_DEFECTS`; so it fell to `_process_contact`'s bottom `except Exception`,
which set `hold_kind="error"`, emptied the sequences and RETURNED. One cut-off
answer therefore destroyed the whole round - the attempts already spent and the
attempts still owed - and the operator spent a generation round learning nothing.
The writer's answer is eleven messages of JSON on a single line. A model stopping
early is an ordinary event.

THE NEGATIVE CONTROL IS RECORDED RATHER THAN SIMULATED, because it cannot be run
from inside this file: the behaviour before the fix was measured directly by
reverting `src/generate_campaign.py` to master `10a38310` and running the same
probe, which gave `writer_calls=1 attempts=0 hold_kind='error'`. With the fix the
identical probe gives `writer_calls=10 attempts=10 hold_kind='copy_refused'`.
`test_a_truncated_first_answer_does_not_end_the_round` asserts the half of that
which only the fix can produce - more than one writer call - so it would have
failed before and passes after.

NOTHING IS LOOSENED, and the last two classes are what says so: an unparseable
answer is never stored, and an answer that PARSES but carries the wrong types is
still a pipeline defect that stops the run.
"""
import json
import unittest

from src import generate_campaign as gc

#: One answer that satisfies every stage of the pipeline that is not the writer.
#: Each stage reads only its own keys, so a union walks ICP, extract, hypothesis
#: and match with no network and no scripted ordering to keep in step.
STAGES = {"is_agency": True, "what_they_actually_are": "an agency",
          "facts": [{"text": "Acme builds software.",
                     "quote": "Acme builds software.",
                     "source_url": "https://acme.test/about"}],
          "hypothesis": "h", "qualification": "QUALIFIED",
          "hypothesis_basis": "b", "role_family": "operations",
          "capability_key": "project_management", "angle": "operations",
          "what_changes": "one operational view"}

#: A draft that PARSES and is refused by the gates. Deliberately poor: these
#: tests are about what the loop does with an unparseable answer, so the drafts
#: must never accidentally pass and end the loop early.
POOR = {"emails": {k: "short body" for k in
                   ("em1", "em2", "em3", "em4", "em5")},
        "subject": "a", "subject_alt": "b", "subject_breakup": "c",
        "linkedin": {}, "ps": {}}

#: THE CANARY'S OWN FAILURE SHAPE: braces present, the middle unparseable, so
#: `_parse_json` gets past its `find("{")`/`rfind("}")` guard and `json.loads`
#: raises `JSONDecodeError: Expecting ',' delimiter`. A payload with no closing
#: brace raises a plain `ValueError` instead and is covered separately.
TRUNCATED_MID = '{"emails": {"em1": "a" "em2": "b"}, "subject": "s"}'

#: A response cut off before the closing brace, which is what a token limit
#: actually produces.
CUT_OFF = json.dumps(POOR)[:120]


class Scripted:
    """Answers the non-writer stages, and the writer from a script."""

    def __init__(self, writer_answers):
        self.writer_answers = list(writer_answers)
        self.writer_calls = 0
        self.prompts = []

    def complete(self, prompt, temperature=0, client=None, config=None):
        self.prompts.append(prompt)
        if "THE PLAN. Write to it." not in prompt:
            return json.dumps(STAGES)
        self.writer_calls += 1
        idx = min(self.writer_calls - 1, len(self.writer_answers) - 1)
        return self.writer_answers[idx]


def run_contact(writer_answers):
    offer = gc._select_offers("productive", "champion")["OFFER-B-OPERATIONS"]
    model = Scripted(writer_answers)
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


class TestOneBadAnswerIsOneAttempt(unittest.TestCase):
    def test_a_truncated_first_answer_does_not_end_the_round(self):
        """The half only the fix can produce: the writer is asked again.

        Before the fix this returned after the FIRST writer call with
        `hold_kind="error"`. Measured on master 10a38310.
        """
        model, result = run_contact([TRUNCATED_MID, json.dumps(POOR)])
        self.assertGreater(model.writer_calls, 1)
        self.assertEqual(model.writer_calls, gc.MAX_WRITER_ATTEMPTS)
        self.assertEqual(result.get("gate_attempts"), gc.MAX_WRITER_ATTEMPTS)
        self.assertNotEqual(result.get("hold_kind"), "error")

    def test_the_bad_answer_is_counted_as_its_own_refusal(self):
        model, result = run_contact([TRUNCATED_MID, json.dumps(POOR)])
        rejections = result.get("gate_rejections") or []
        self.assertEqual(len(rejections), gc.MAX_WRITER_ATTEMPTS)
        self.assertIn("not valid JSON", rejections[0])
        # And the reason it gives the writer is actionable, not a code.
        self.assertIn("ONE JSON object", rejections[0])

    def test_the_reason_reaches_the_next_prompt(self):
        """A refusal the writer is never told is an attempt spent on nothing."""
        model, _ = run_contact([TRUNCATED_MID, json.dumps(POOR)])
        writer_prompts = [p for p in model.prompts
                          if "THE PLAN. Write to it." in p]
        self.assertGreaterEqual(len(writer_prompts), 2)
        self.assertIn("not valid JSON", writer_prompts[1])

    def test_a_response_cut_off_before_the_closing_brace_behaves_the_same(self):
        model, result = run_contact([CUT_OFF, json.dumps(POOR)])
        self.assertEqual(model.writer_calls, gc.MAX_WRITER_ATTEMPTS)
        self.assertNotEqual(result.get("hold_kind"), "error")
        self.assertIn("not valid JSON",
                      (result.get("gate_rejections") or [""])[0])

    def test_every_answer_unparseable_holds_copy_refused_not_error(self):
        """Exhaustion goes through the loop's own `else`, not a second path."""
        model, result = run_contact([TRUNCATED_MID])
        self.assertEqual(model.writer_calls, gc.MAX_WRITER_ATTEMPTS)
        self.assertEqual(result.get("hold_kind"), "copy_refused")
        self.assertIn("not valid JSON", str(result.get("held")))
        self.assertEqual(result.get("sequences"), {})
        self.assertEqual(result.get("subjects"), {})


class TestNothingIsLoosened(unittest.TestCase):
    def test_an_unparseable_answer_stores_no_copy(self):
        """There is no half-populated draft for a later gate to accept."""
        _, result = run_contact([TRUNCATED_MID])
        self.assertEqual(result.get("sequences"), {})

    def test_a_clean_round_records_no_json_refusal(self):
        """The control: the new branch does not fire on a parseable answer."""
        _, result = run_contact([json.dumps(POOR)])
        for reason in result.get("gate_rejections") or []:
            self.assertNotIn("not valid JSON", reason)
        self.assertEqual(result.get("hold_kind"), "copy_refused")

    def test_an_answer_that_parses_to_the_wrong_types_still_stops_the_run(self):
        """`PIPELINE_DEFECTS` is untouched: a shape fault is a defect, not a hold."""
        with self.assertRaises(gc.CampaignPipelineError):
            run_contact(['{"emails": "not a dict", "subject": "s"}'])


class TestThePersonalizationLadderReachesTheWriter(unittest.TestCase):
    """It never had, and a bare `except Exception` is why.

    `_process_contact` read `personalization.level_for(account, contact)` and had
    no `account` parameter at all, so every call raised `NameError: name
    'account' is not defined` and the handler below it swallowed the lot.
    `plan_data["personalization_level"]` was therefore never set on any contact
    of any run. MEASURED 2026-10-01 by rendering the real writer prompt for
    the canary record: the plan block carried
    `offer_step_objectives` and no `personalization_level`.

    It matters because `WRITER_SYSTEM` says the plan carries that field and to
    OBEY IT, and that at levels 2 to 4 the writer has no facts worth opening on
    and must ask a question instead of manufacturing an icebreaker. The canary is
    level 3 with zero research rows.
    """

    def _writer_prompt(self):
        model, _ = run_contact([json.dumps(POOR)])
        return next(p for p in model.prompts if "THE PLAN. Write to it." in p)

    def test_the_plan_the_writer_reads_carries_a_personalization_level(self):
        self.assertIn("personalization_level", self._writer_prompt())

    def test_it_carries_a_real_level_and_not_an_empty_string(self):
        prompt = self._writer_prompt()
        self.assertRegex(prompt, r"LEVEL [1-4]")


class TestTheWriterIsToldItsOwnRungWords(unittest.TestCase):
    """`step_objectives` on em3 and em5 was the dominant canary refusal.

    The diagnosis, measured on the canary record with offer
    `OFFER-B-OPERATIONS`: the objective DOES reach the model, it IS satisfiable
    alongside every other rule, and the gate is NOT stricter than the objective.
    What was missing is that every worked example in `WRITER_SYSTEM` is OFFER A's
    ladder ("rung 5 reads 'reframe and close'", "rung 3 ('resource decisions that
    move margin')") while the offer selected for persona `champion` is OFFER B,
    whose rungs are "project visibility", "time", "resourcing", an AI mechanism
    and "one operational view". The instructions named one ladder and the plan
    carried another.
    """

    def _block(self):
        from src import copystages, generate_campaign
        offer = generate_campaign._select_offers(
            "productive", "champion")["OFFER-B-OPERATIONS"]
        return copystages.step_objective_block(
            offer.get("step_objectives"),
            sorted(offer.get("ai_capabilities") or {}),
            offer.get("thread_reply_rungs") or ())

    # THE INSTRUCTION LINE, NOT THE WORD. These two asserted `"resourcing" in
    # block` and `"operational" in block`, and BOTH PASSED WITH THE INSTRUCTION
    # DELETED: the block also prints each rung as `em3  rung 3: "resourcing"`,
    # so the bare word is there whether or not the writer is ever told to use
    # it. MEASURED 2026-10-01: replacing the whole
    # `SAY AT LEAST ONE OF THESE WORDS, LITERALLY: ...` line with "pursue the
    # rung in your own words" left this class green on 3 of its 4 word tests.
    # The DEMAND is what has to be asserted, so the demand is what is matched.
    def test_it_names_the_literal_word_em3_must_carry(self):
        self.assertIn("SAY AT LEAST ONE OF THESE WORDS, LITERALLY: resourcing",
                      self._block())

    def test_it_names_the_literal_words_em5_must_carry(self):
        self.assertIn(
            "SAY AT LEAST ONE OF THESE WORDS, LITERALLY: operational, view",
            self._block())

    def test_it_does_not_hand_offer_as_rungs_to_offer_bs_writer(self):
        block = self._block()
        for offer_a_word in ("reframe", "quote versus burn", "margin"):
            self.assertNotIn(offer_a_word, block)

    def test_the_words_come_from_the_gates_own_reader(self):
        """Prompt and gate share one authority, so they cannot drift.

        Asserted by EFFECT: a made-up objective is rendered with exactly the
        content words `sequencegate` would require of it, stopwords dropped.
        """
        from src import copystages, sequencegate
        block = copystages.step_objective_block({"1": "one of the widgets"})
        self.assertIn("widgets", block)
        # "one" and "of" and "the" are stopwords to the gate, so demanding them
        # would be demanding something the gate does not check.
        self.assertEqual(sequencegate._content_words("one of the widgets"),
                         {"widgets"})
        self.assertNotIn("LITERALLY: one", block)

    def test_a_conditional_ai_rung_is_never_demanded(self):
        """Rung 4 names an AI capability. `sequencegate` warns, never refuses."""
        block = self._block()
        self.assertIn("CONDITIONAL", block)
        self.assertNotIn("LITERALLY: AI", block)

    def test_an_offer_with_no_ladder_gets_no_invented_one(self):
        from src import copystages
        self.assertEqual(copystages.step_objective_block(None), "")
        self.assertEqual(copystages.step_objective_block({}), "")

    def test_the_block_reaches_the_prompt_the_model_receives(self):
        prompt = next(p for p in run_contact([json.dumps(POOR)])[0].prompts
                      if "THE PLAN. Write to it." in p)
        self.assertIn("THE PLAN'S OWN LADDER", prompt)
        self.assertIn("resourcing", prompt)
        self.assertIn("operational, view", prompt)


if __name__ == "__main__":
    unittest.main()
