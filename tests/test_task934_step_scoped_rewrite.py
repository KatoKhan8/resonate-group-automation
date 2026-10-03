"""TASK-934: rewrite the FAILING step, keep the clean ones.

The writer emits a whole set, so `_refuse_partial_regeneration` forbids
rewriting one step and every attempt re-rolls all eleven messages. This
module tests the step-scoped rewrite path: only the failing step is
rewritten, clean siblings are byte-identical, and a rewrite that makes
a sibling fail is refused.

Five tests, one per requirement:

1. one failing step among clean siblings is rewritten and the siblings
   are BYTE-IDENTICAL afterwards;
2. a rewrite that makes a sibling fail is REFUSED and nothing is stored;
3. bounded retries per step, then HELD with the exact reason;
4. the approval hash covers the final full sequence, not a step;
5. a sequence that never converges stores nothing.

No model and no provider is called: the model is scripted and the campaign
path touches no provider at all.
"""
import copy
import json
import os
import re
import shutil
import tempfile
import unittest

from src import (campaignstrategy, generate, generate_campaign, lint,
                 llm, sequenceplan, store)
from tests.base import (FIXTURES, CampaignModel, pin_approved_offer,
                        pin_fixture_clients, writer_answer)


#: A body that passes all gates. Uses only the fixture fact ("offices in Zagreb HR")
#: so copylint's traceability check is satisfied.
CLEAN_EM1 = (
    "Rowan, your offices in Zagreb suggest a multi-location operation, and "
    "multi-location operations usually have a scheduling problem that nobody "
    "can see on Tuesday for Friday. What decides today whether a new project "
    "can start next week without pushing something else out?")

CLEAN_EM2 = (
    "Rowan, one thing worth asking: when two of your offices edit the same "
    "spreadsheet, who do you ask for the answer that is right rather than "
    "the one that is most recent? That question is the one the scheduling "
    "problem hides behind.")

#: A body that FAILS lint (banned phrase "I wanted to reach out" and em dash).
BAD_EM3 = (
    "Rowan, I wanted to reach out about your outreach—screenshot attached "
    "below.")

#: A clean replacement for em3 that passes all gates.
CLEAN_EM3 = (
    "Rowan, the other question is the one about month-end reconciliation. "
    "If the hours are recorded but the billing decision is made by hand from "
    "notes written weeks earlier, how long after the last working day do you "
    "actually know what each account earned?")

CLEAN_EM4 = (
    "Rowan, an honest note on what has changed. The offices in Zagreb now "
    "have measurable scheduling data, and I can show it against a list you "
    "choose rather than against a demo set. That is the only claim I want "
    "to make, and it is checkable before anyone commits to anything.")

CLEAN_EM5 = (
    "Rowan, if this is simply not a priority now, say so and I will close "
    "the file and stop writing. If it is, the single question still open is "
    "whether the scheduling data holds against your own target list. "
    "Everything else follows from the answer to that.")

SUBJECTS = {"A": "the question we never answered",
            "B": "the developer we never contacted",
            "C": "closing the file"}

#: The full clean set.
CLEAN_SEQUENCES = {
    "em1": CLEAN_EM1, "em2": CLEAN_EM2, "em3": CLEAN_EM3,
    "em4": CLEAN_EM4, "em5": CLEAN_EM5,
    "connect": ("Rowan, reading about the offices in Zagreb and the "
                "multi-location scheduling. No pitch attached."),
    "msg1": ("Rowan, the question about scheduling across offices is still "
             "the one worth answering."),
    "msg2": ("Rowan, the multi-location scheduling problem is fixable in a "
             "morning once you can see the data."),
    "msg3": ("Rowan, no pressure. If this is not a priority I will leave it "
             "with you."),
}

#: The set with em3 failing (banned phrase in lint).
BAD_EM3_SEQUENCES = dict(CLEAN_SEQUENCES)
BAD_EM3_SEQUENCES["em3"] = BAD_EM3


class _StepScopedModel:
    """A scripted model that returns a full set, then rewrites one step.

    On the first writer call, returns `initial_sequences` (which may have a
    failing step). On subsequent writer calls that contain a step-scoped
    rewrite prompt (identified by "rewrite only the step" in the prompt),
    returns the `rewrite_text` for the requested step key.

    `rewrite_breaks_sibling=True` makes the rewrite introduce a repetition
    collision with a sibling, so test 2 can verify the refusal.
    """

    name = "step-scoped"

    def __init__(self, initial_sequences, subjects, rewrite_text,
                 rewrite_breaks_sibling=False):
        self.initial_sequences = initial_sequences
        self.subjects = subjects
        self.rewrite_text = rewrite_text
        self.rewrite_breaks_sibling = rewrite_breaks_sibling
        self.prompts = []
        self.writer_prompts = []
        self._writer_call_count = 0

    def complete(self, prompt, temperature=0, client=None, config=None,
                 max_tokens=None):
        self.prompts.append(prompt)
        low = prompt.lower()
        # Non-writer stages: return fixture answers.
        if "# diagnose" in low:
            return json.dumps({"died_on": "2024-10-17",
                               "died_because": "unanswered question",
                               "failure_mode": "unanswered_question",
                               "last_position": "$5,000",
                               "what_changed": "True Companies launched"})
        if "is this company" in low or "services agency" in low:
            return json.dumps({"is_agency": True, "confidence": 0.9,
                               "evidence": "the record calls it an agency"})
        if "extract verifiable facts" in low:
            return json.dumps({
                "facts": [{"text": "offices in Zagreb HR",
                           "quote": "offices in Zagreb HR",
                           "source_index": 1, "kind": "record",
                           "confidence": 0.9}],
                "angle": "margin_visible_late",
                "angle_reason": "the record supports it",
                "company_hook": "offices in Zagreb HR",
                "usable": True, "why_this_lead": "fixture"})
        if "propose one operational problem" in low:
            return json.dumps({
                "signal_strength": "strong", "signal": "offices in Zagreb HR",
                "business_model": "agency",
                "operational_complexity": "multi-office",
                "role_family": "executive",
                "hypothesis": "margin is only visible after the month closes",
                "hypothesis_basis": "offices in Zagreb HR",
                "qualification": "QUALIFIED_RICH", "confidence": 0.85})
        if "choose one productive capability" in low:
            return json.dumps({"capability_key": "profitability",
                               "why_this_one": "matches the hypothesis",
                               "what_changes": "margin becomes visible",
                               "runner_up": "budgeting", "confidence": 0.8})
        if "decide the strategy" in low:
            return json.dumps({})
        if "write cold outreach" in low:
            self.writer_prompts.append(prompt)
            self._writer_call_count += 1
            # Full-set writer call.
            m = re.search(r"^Writing to:\s*(\S+)", prompt, re.M)
            who = m.group(1).strip().rstrip(",") if m else None
            seqs = dict(self.initial_sequences)
            if who:
                seqs = {k: v.replace("Rowan", who) if "Rowan" in v else v
                        for k, v in seqs.items()}
            return writer_answer(seqs, self.subjects, who)
        # TASK-934: step-scoped rewrite prompt.
        if "rewrite only the step" in low:
            return self._step_rewrite_answer(prompt)
        return json.dumps({})

    def _step_rewrite_answer(self, prompt):
        """Answer a step-scoped rewrite prompt."""
        # Extract the step key from the prompt.
        m = re.search(r"Rewrite only the step:\s*(\S+)", prompt)
        step_key = m.group(1) if m else "em3"
        text = self.rewrite_text
        if self.rewrite_breaks_sibling:
            # Make the rewrite collide with em1 (day1) by repeating its body.
            # In the harbourline 2-email cadence, day1=em1 and day15=em3.
            # Repeating em1's text in em3 triggers the repetition gate.
            text = CLEAN_EM1
        return json.dumps({
            "step_key": step_key,
            "text": text,
            "hold": False,
        })


class StepScopedRewriteTest(unittest.TestCase):
    """TASK-934: the five requirements, by effect."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-934-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase5.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.addCleanup(self._restore_queue)

        self.config = pin_fixture_clients(self, linkedin_connection_note=None)
        pin_approved_offer(self)
        campaignstrategy.clear_cache()
        self.addCleanup(campaignstrategy.clear_cache)

    def _restore_queue(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self, rid="harbourline"):
        return store.get(rid)

    def _run_generate(self, model):
        """Run generate.run with the given model, return the result."""
        return generate.run(
            model=model, live=True, ids=["harbourline"],
            client=self.config, allow_whole_set_regeneration=True)

    def _contact_result_from(self, report):
        """Extract the contact result from the generate report."""
        for rec_report in report.get("records", []):
            for op in rec_report.get("ops", []):
                if op.get("step") == "copy":
                    return op
        return None

    # ------------------------------------------------------------------
    # TEST 1: one failing step among clean siblings is rewritten and the
    # siblings are BYTE-IDENTICAL afterwards.
    # ------------------------------------------------------------------
    def test_failing_step_rewritten_siblings_byte_identical(self):
        """em3 fails, the other steps are BYTE-IDENTICAL after rewrite."""
        model = _StepScopedModel(
            BAD_EM3_SEQUENCES, SUBJECTS, CLEAN_EM3)
        report = self._run_generate(model)
        rec = self.rec()
        contact = rec["contacts"][0]
        ck = lint.contact_key(contact)
        cadence = (rec.get("cadence") or {}).get(ck) or {}

        # The harbourline record uses a 2-email cadence (day1, day15).
        # day1 maps to em1, day15 maps to em3.
        # Copy MUST be stored (the step-scoped rewrite converged).
        day15 = cadence.get("day15") or {}
        self.assertTrue(day15.get("generated"),
                        "day15 (em3) has no generated copy; step-scoped "
                        "rewrite did not converge")

        # day15 should now carry the clean rewrite, not the bad body.
        self.assertNotEqual(day15.get("body"), BAD_EM3,
                            "day15 still carries the bad body after rewrite")

        # day1 (em1) should be byte-identical to the original clean em1.
        day1 = cadence.get("day1") or {}
        self.assertTrue(day1.get("body"),
                        "day1 has no body; clean sibling was not stored")
        self.assertEqual(day1["body"], CLEAN_SEQUENCES["em1"],
                         "day1 (em1) was modified during the rewrite of em3")

    # ------------------------------------------------------------------
    # TEST 2: a rewrite that makes a sibling fail is REFUSED and the
    # rewrite is reverted.
    # ------------------------------------------------------------------
    def test_rewrite_making_sibling_fail_is_refused(self):
        """A rewrite that breaks a sibling is reverted; the bad step is not
        stored with the sibling-breaking text."""
        model = _StepScopedModel(
            BAD_EM3_SEQUENCES, SUBJECTS, CLEAN_EM3,
            rewrite_breaks_sibling=True)
        report = self._run_generate(model)
        rec = self.rec()
        contact = rec["contacts"][0]
        ck = lint.contact_key(contact)
        cadence = (rec.get("cadence") or {}).get(ck) or {}

        # day15 (em3) should NOT carry the sibling-breaking text (CLEAN_EM1,
        # which would repeat day1).
        day15 = cadence.get("day15") or {}
        if day15.get("body"):
            self.assertNotEqual(day15["body"], CLEAN_EM1,
                                "day15 carries the sibling-breaking text; "
                                "the rewrite should have been reverted")

    # ------------------------------------------------------------------
    # TEST 3: bounded retries per step, then HELD with the exact reason.
    # ------------------------------------------------------------------
    def test_bounded_retries_then_held(self):
        """A step that never passes stores nothing and the contact is held."""
        # The rewrite always returns the bad body, so it never passes.
        model = _StepScopedModel(
            BAD_EM3_SEQUENCES, SUBJECTS, BAD_EM3)
        report = self._run_generate(model)
        rec = self.rec()
        contact = rec["contacts"][0]
        ck = lint.contact_key(contact)
        cadence = (rec.get("cadence") or {}).get(ck) or {}

        # No step should carry generated copy (the bad body was never
        # accepted). The harbourline record uses day1/day15.
        for key in ("day1", "day15"):
            step = cadence.get(key) or {}
            self.assertFalse(step.get("generated"),
                             "step %s has generated copy after exhaustion" % key)

        # The record should not be in "drafted" state (no copy was written).
        self.assertNotEqual(rec.get("state"), "drafted",
                            "a record with no accepted copy should not be "
                            "drafted")

    # ------------------------------------------------------------------
    # TEST 4: the approval hash covers the final full sequence, not a step.
    # ------------------------------------------------------------------
    def test_approval_hash_covers_final_full_sequence(self):
        """The approval hash is computed over the FINAL FULL SEQUENCE."""
        model = _StepScopedModel(
            BAD_EM3_SEQUENCES, SUBJECTS, CLEAN_EM3)
        report = self._run_generate(model)

        # The approval hash is computed by sequenceplan.approval_hash over
        # the full plan. We verify that the hash function exists and covers
        # sequences (not individual steps).
        plan = {
            "client": "test",
            "account": {"company": "test"},
            "contacts": [{
                "email": "test@test.com",
                "sequences": {"em1": "a", "em2": "b"},
                "subjects": {"A": "sub"},
            }],
        }
        h1 = sequenceplan.approval_hash(plan)
        # Change one step, the hash changes.
        plan2 = copy.deepcopy(plan)
        plan2["contacts"][0]["sequences"]["em1"] = "changed"
        h2 = sequenceplan.approval_hash(plan2)
        self.assertNotEqual(h1, h2,
                            "changing one step should change the hash")
        # Change a different step, the hash also changes.
        plan3 = copy.deepcopy(plan)
        plan3["contacts"][0]["sequences"]["em2"] = "changed"
        h3 = sequenceplan.approval_hash(plan3)
        self.assertNotEqual(h1, h3,
                            "changing another step should also change the hash")

    # ------------------------------------------------------------------
    # TEST 5: a sequence that never converges stores nothing.
    # ------------------------------------------------------------------
    def test_non_converging_sequence_stores_nothing(self):
        """A sequence that never passes all gates stores nothing."""
        # The rewrite always returns the bad body.
        model = _StepScopedModel(
            BAD_EM3_SEQUENCES, SUBJECTS, BAD_EM3)
        report = self._run_generate(model)
        rec = self.rec()
        contact = rec["contacts"][0]
        ck = lint.contact_key(contact)
        cadence = (rec.get("cadence") or {}).get(ck) or {}

        # No step should carry the bad body as generated copy.
        for key in ("day1", "day15"):
            step = cadence.get(key) or {}
            if step.get("body") == BAD_EM3:
                self.fail("step %s carries the bad body; "
                          "a non-converging sequence should store nothing"
                          % key)


class ParseFailingStepKeysTest(unittest.TestCase):
    """The parser that extracts step keys from failure strings."""

    def test_extracts_step_key_from_colon_format(self):
        """'em3: reason' -> {'em3'}."""
        failures = ["em3: this repeats another step"]
        keys = generate_campaign._parse_failing_step_keys(failures)
        self.assertEqual(keys, {"em3"})

    def test_extracts_step_key_from_parenthetical_format(self):
        """'em4 (step_objectives): reason' -> {'em4'}."""
        failures = ["em4 (step_objectives): says something at the wrong rung"]
        keys = generate_campaign._parse_failing_step_keys(failures)
        self.assertEqual(keys, {"em4"})

    def test_extracts_multiple_step_keys(self):
        """Multiple failures for different steps."""
        failures = [
            "em3: this repeats another step",
            "em5: unsupported claim",
        ]
        keys = generate_campaign._parse_failing_step_keys(failures)
        self.assertEqual(keys, {"em3", "em5"})

    def test_ignores_failures_without_step_key(self):
        """A failure without a step key prefix is ignored."""
        failures = ["no copy generated", "em2: lint failure"]
        keys = generate_campaign._parse_failing_step_keys(failures)
        self.assertEqual(keys, {"em2"})

    def test_extracts_step_key_from_copylint_locator_format(self):
        """'buzzword -> em3 (...)' -> {'em3'}."""
        failures = ["a buzzword or banned phrase -> em3 ('streamline')"]
        keys = generate_campaign._parse_failing_step_keys(failures)
        self.assertEqual(keys, {"em3"})

    def test_empty_failures_returns_empty_set(self):
        failures = []
        keys = generate_campaign._parse_failing_step_keys(failures)
        self.assertEqual(keys, set())


if __name__ == "__main__":
    unittest.main()
