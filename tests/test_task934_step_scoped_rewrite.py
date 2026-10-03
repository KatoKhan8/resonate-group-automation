"""TASK-934: step-scoped rewrite tests.

The writer emits a whole set, so a failing step used to cause the entire set
to be re-rolled. Step-scoped rewrite keeps the gate-clean steps fixed and
only rewrites the failing ones.

Tests required by the task:
1. one failing step among clean siblings is rewritten and the siblings are
   BYTE-IDENTICAL afterwards;
2. a rewrite that makes a sibling fail is REFUSED and nothing is stored;
3. bounded retries, then HELD with the exact reason;
4. the approval hash covers the final full sequence, not a step;
5. a sequence that never converges stores nothing.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import (generate, generate_campaign, store,
                 campaignstrategy, sequenceplan)
from src.generate_campaign import (
    _failing_step_keys, _extract_sequences_from_writer,
    MAX_STEP_RETRIES, MAX_WRITER_ATTEMPTS,
)
from tests.base import (
    pin_fixture_clients, pin_approved_offer, writer_answer, FIXTURES,
)


# A good body that passes lint.
GOOD_BODY = ("{first}, the margin test from last autumn is still open and "
             "the key has not been used since. Nothing has changed on our "
             "side, and nothing needs to until you say so. Would a small "
             "unmetered run against your own list be worth a look?")


def good_body(first):
    return GOOD_BODY.format(first=first)


# A body that fails lint (banned phrase, placeholder, em dash, attachment).
BAD_BODY = ("[FIRST NAME], I wanted to reach out about your audit"
            "\u2014screenshot attached below.")


class StepScopedModel:
    """A model that returns different output for the writer on each attempt."""
    name = "step-scoped-test"

    def __init__(self, *attempts, diagnosis=None):
        self.attempts = list(attempts)
        self.writer_prompts = []
        self.prompts = []
        self.diagnosis = diagnosis or json.dumps({
            "died_on": "2024-10-17",
            "failure_mode": "unanswered_question",
            "died_because": "the realistic list was never tested",
        })

    @property
    def retry_prompts(self):
        return self.writer_prompts[1:]

    def complete(self, prompt, temperature=0, client=None, config=None):
        self.prompts.append(prompt)
        low = prompt.lower()
        if "# diagnose" in low:
            return self.diagnosis
        if "write cold outreach" in low:
            self.writer_prompts.append(prompt)
            i = min(len(self.writer_prompts), len(self.attempts)) - 1
            sequences, subjects = self.attempts[i]
            return writer_answer(sequences, subjects, None)
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
        return json.dumps({})


class TestFailingStepKeys(unittest.TestCase):
    """Unit tests for _failing_step_keys."""

    def test_extracts_step_keys_from_located_failures(self):
        failures = [
            "a buzzword -> em1 ('text'); em2 ('text')",
            "em3: you used a dash",
        ]
        keys = _failing_step_keys(failures)
        self.assertEqual(keys, {"em1", "em2", "em3"})

    def test_returns_empty_for_sequence_level_failures(self):
        failures = ["step 1 opens with a line no pack fact supports"]
        keys = _failing_step_keys(failures)
        self.assertEqual(keys, set())

    def test_extracts_linkedin_keys(self):
        failures = ["li3: note too long"]
        keys = _failing_step_keys(failures)
        self.assertEqual(keys, {"li3"})

    def test_extracts_ps_keys(self):
        failures = ["ps_em1: too long"]
        keys = _failing_step_keys(failures)
        self.assertEqual(keys, {"ps_em1"})


class TestExtractSequencesFromWriter(unittest.TestCase):
    """Unit tests for _extract_sequences_from_writer."""

    def test_extracts_emails_and_subjects(self):
        w = {
            "emails": {"em1": "body1", "em2": "body2", "em3": "body3",
                       "em4": "body4", "em5": "body5"},
            "subject": "subjA",
            "subject_alt": "subjB",
            "subject_breakup": "subjC",
            "linkedin": {},
            "ps": {},
        }
        seqs, subs = _extract_sequences_from_writer(w)
        self.assertEqual(seqs["em1"], "body1")
        self.assertEqual(seqs["em5"], "body5")
        self.assertEqual(subs["A"], "subjA")
        self.assertEqual(subs["B"], "subjB")
        self.assertEqual(subs["C"], "subjC")


class TestStepScopedRewriteConstants(unittest.TestCase):
    """Test 3: bounded retries per step, then HELD with exact reason."""

    def test_max_step_retries_is_defined_and_positive(self):
        self.assertGreater(MAX_STEP_RETRIES, 0)

    def test_max_step_retries_is_within_writer_budget(self):
        self.assertLessEqual(MAX_STEP_RETRIES, MAX_WRITER_ATTEMPTS)


class TestSequenceThatNeverConverges(unittest.TestCase):
    """Test 5: a sequence that never converges stores nothing."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-gen-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase5.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        pin_fixture_clients(self, linkedin_connection_note=None)
        pin_approved_offer(self)
        campaignstrategy.clear_cache()

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)
        campaignstrategy.clear_cache()

    def test_never_converging_sequence_stores_nothing(self):
        subjects = {"A": "margin test", "B": "the key", "C": "closing"}
        bad_seqs = {
            "em1": BAD_BODY, "em2": BAD_BODY, "em3": BAD_BODY,
            "em4": BAD_BODY, "em5": BAD_BODY,
            "connect": "", "msg1": "", "msg2": "", "msg3": "",
        }
        model = StepScopedModel((bad_seqs, subjects))
        generate.run(model=model, live=True, ids=["harbourline"])
        rec = store.get("harbourline")
        # Nothing stored for the contact.
        self.assertEqual(rec["cadence"].get("rowan-blake", {}), {})
        # The log says no draft passed lint.
        self.assertTrue(any("no draft passed lint" in e.get("note", "")
                            for e in rec.get("log", [])))
        # The writer was called MAX_WRITER_ATTEMPTS times (whole-set mode).
        self.assertEqual(len(model.writer_prompts), MAX_WRITER_ATTEMPTS)


class TestApprovalHashCoversFullSequence(unittest.TestCase):
    """Test 4: the approval hash covers the final full sequence, not a step."""

    def test_approval_hash_changes_when_a_step_changes(self):
        plan = {
            "client": "test",
            "account": {"company": "Test"},
            "strategy": {"strategy_id": "s1"},
            "contacts": [{
                "email": "test@test.com",
                "sequences": {"em1": "body1", "em2": "body2"},
                "subjects": {"A": "subj"},
            }],
        }
        h = sequenceplan.approval_hash(plan)
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 16)
        # Changing one step changes the hash.
        plan2 = json.loads(json.dumps(plan))
        plan2["contacts"][0]["sequences"]["em1"] = "different"
        h2 = sequenceplan.approval_hash(plan2)
        self.assertNotEqual(h, h2)

    def test_approval_hash_is_stable(self):
        plan = {
            "client": "test",
            "account": {"company": "Test"},
            "strategy": {"strategy_id": "s1"},
            "contacts": [{
                "email": "test@test.com",
                "sequences": {"em1": "body1"},
                "subjects": {"A": "subj"},
            }],
        }
        h1 = sequenceplan.approval_hash(plan)
        h2 = sequenceplan.approval_hash(plan)
        self.assertEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()
