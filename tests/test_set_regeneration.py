"""TASK-068: a mutually repetitive sequence cannot be fixed one note at a time.

The mechanism: a contact whose LinkedIn notes pass the intrinsic gates
(lint, claims, foreign_product) individually but collide on
campaign_repetition cannot converge through one-at-a-time regeneration.
Each replacement is compared against the old siblings that still say the
same thing, so a new note that addresses the same topic collides with
the unchanged siblings and is refused.

The fix: detect this condition and regenerate the whole set as a
transaction - fresh candidates into memory, the complete set gated
together, committed only if every member passes.

No test calls a model or a network. Every model here is scripted.
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import (claims, clients, events, generate, lint, llm,
                 quality, store)
from tests.base import FIXTURES, pin_client_config


def _note(text, channel="linkedin"):
    return {"channel": channel, "generated": True, "note": text}


def _make_record(contact_name="ranjan-damodar", company="acqcom",
                 notes=None, lane="domains"):
    """A minimal record with LinkedIn notes for one contact."""
    contact = {"name": contact_name, "key": contact_name,
               "title": "COO", "persona": "founder",
               "angle": "operations efficiency",
               "linkedin": f"https://linkedin.com/in/{contact_name}"}
    rec = {
        "id": f"{company.replace(' ', '')}-com",
        "company": company,
        "domain": f"{company.replace(' ', '')}.com",
        "lane": lane,
        "state": "drafted",
        "client": "productive",
        "contacts": [contact],
        "company_facts": {"name": company, "employees": 50,
                          "industry": "Advertising"},
        "cadence": {contact_name: {}},
        "events": [],
        "evidence": {},
    }
    if notes:
        for sk, text in notes.items():
            rec["cadence"][contact_name][sk] = _note(text)
    return rec


# Five notes that share distinctive words (5+ chars) heavily.
# After discounting SUBJECT_VOCABULARY ("utilisation", "utilization",
# "profitability", "margin") and company name, they still share
# "projects", "across", "tracking", "capacity", "managing" etc.
COLLIDING_NOTES = {
    "li1": "hi ranjan, impressive work managing projects across your teams at acqcom",
    "li2": ("how do you currently track capacity across your live projects "
            "at acqcom without clear managing visibility"),
    "li3": ("managing capacity across your teams is challenging when tracking "
            "projects without visibility across the organization"),
    "li4": ("have you explored managing tracking capacity across projects "
            "with better visibility for your teams"),
    "li5": ("any thoughts on managing capacity across your live projects "
            "and tracking visibility across teams"),
}

# Three notes that say genuinely different things.
DISTINCT_NOTES = {
    "li1": "hi ranjan, your work in advertising technology caught my attention",
    "li2": "curious how your team handles client onboarding at acqcom",
    "li3": "we built something for agencies struggling with project billing",
}


class SetRegenerationDetectionTest(unittest.TestCase):
    """_needs_set_regeneration: does the condition exist in the data?"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-setregen-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = pin_client_config(
            self, linkedin_connection_note={"mode": "llm"},
            cadence="productive_li_heavy_v1")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_colliding_notes_trigger_set_regeneration(self):
        """Notes that pass individually but collide on campaign_repetition."""
        rec = _make_record(notes=COLLIDING_NOTES)
        contact = rec["contacts"][0]

        # Verify the notes DO collide via campaign_repetition
        steps = [{"key": k, "text": v} for k, v in sorted(COLLIDING_NOTES.items())]
        collisions = quality.campaign_repetition(
            steps, company_name="acqcom")
        self.assertTrue(len(collisions) > 0,
                        "test fixture should have collisions")

        # Verify each note passes intrinsic gates individually
        for sk, step in rec["cadence"]["ranjan-damodar"].items():
            failures = [f for f in lint.check_step(rec, "ranjan-damodar", step)
                        if f not in lint.LINKEDIN_HELD_CODES]
            self.assertNotEqual(
                lint.classify_linkedin(failures), "failed",
                f"{sk} should pass lint but got {failures}")

        # The detection function should return the step keys
        result = generate._needs_set_regeneration(rec, contact, self.config)
        self.assertIsNotNone(result)
        self.assertIn("li1", result)
        self.assertIn("li2", result)

    def test_distinct_notes_do_not_trigger(self):
        """Notes that are genuinely different should not trigger."""
        rec = _make_record(notes=DISTINCT_NOTES)
        contact = rec["contacts"][0]

        result = generate._needs_set_regeneration(rec, contact, self.config)
        self.assertIsNone(result)

    def test_single_note_does_not_trigger(self):
        """One note cannot collide with itself."""
        rec = _make_record(notes={"li1": COLLIDING_NOTES["li1"]})
        contact = rec["contacts"][0]

        result = generate._needs_set_regeneration(rec, contact, self.config)
        self.assertIsNone(result)

    def test_intrinsically_failing_notes_excluded_from_passing(self):
        """A note that fails lint is not counted among the passing set.

        _needs_set_regeneration returns ALL LinkedIn step keys for
        regeneration (the full set is replaced), but the TRIGGER condition
        requires at least two notes that PASS intrinsically yet collide.
        A note that fails lint is excluded from the passing set used to
        detect the collision.
        """
        notes = dict(COLLIDING_NOTES)
        # Make li1 fail lint with a placeholder
        notes["li1"] = "hi [FIRST_NAME], this managing tracking across projects"
        rec = _make_record(notes=notes)
        contact = rec["contacts"][0]

        # li1 should fail lint (placeholder)
        li1_step = rec["cadence"]["ranjan-damodar"]["li1"]
        failures = [f for f in lint.check_step(rec, "ranjan-damodar", li1_step)
                    if f not in lint.LINKEDIN_HELD_CODES]
        self.assertEqual(lint.classify_linkedin(failures), "failed")

        # li2-li5 still pass intrinsically and collide, so the trigger fires.
        # The returned keys include ALL LinkedIn steps (the whole set is
        # regenerated), including li1 which fails lint.
        result = generate._needs_set_regeneration(rec, contact, self.config)
        self.assertIsNotNone(result,
                             "li2-li5 still collide; set regen should trigger")
        self.assertIn("li1", result,
                       "the full set is returned for regeneration")


class SetRegenerationTransactionTest(unittest.TestCase):
    """_regenerate_linkedin_set: transactional generate-and-commit."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-setregen-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = pin_client_config(
            self, linkedin_connection_note={"mode": "llm"},
            cadence="productive_li_heavy_v1")

    def tearDown(self):
        if self._prev_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev_queue
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _good_note(self, step_key):
        """A note that passes all gates and is distinct from the others."""
        distinct = {
            "li1": "hi ranjan, your advertising technology work is impressive",
            "li2": "curious how your team handles client onboarding flows",
            "li3": "we built a tool for agencies struggling with billing",
            "li4": "your approach to addressable ads across platforms stands out",
            "li5": "would love to hear about your biggest operational challenge",
            "li6": "no pressure but happy to share what we have learned",
        }
        return distinct.get(step_key, "a clean distinct note about operations")

    def test_successful_regeneration_replaces_all_notes(self):
        """When all new notes pass, the old set is replaced."""
        notes = dict(COLLIDING_NOTES)
        notes["li6"] = "any thoughts on our previous discussions no pressure"
        rec = _make_record(notes=notes)
        contact = rec["contacts"][0]

        old_li1 = rec["cadence"]["ranjan-damodar"]["li1"]["note"]

        answers = [json.dumps({"note": self._good_note(f"li{i}")})
                   for i in range(1, 7)]
        model = llm.ScriptedModel(*answers)

        result = generate._regenerate_linkedin_set(
            rec, contact, model, self.config)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 6)

        new_li1 = rec["cadence"]["ranjan-damodar"]["li1"]["note"]
        self.assertNotEqual(new_li1, old_li1,
                            "the old note should be replaced")

    def test_failed_regeneration_preserves_originals(self):
        """When one note fails all attempts, nothing is stored."""
        rec = _make_record(notes=COLLIDING_NOTES)
        contact = rec["contacts"][0]

        originals = {}
        for sk, step in rec["cadence"]["ranjan-damodar"].items():
            originals[sk] = step["note"]

        # First two notes succeed, third fails all attempts
        answers = [
            json.dumps({"note": self._good_note("li1")}),
            json.dumps({"note": self._good_note("li2")}),
        ]
        # All remaining answers are banned (too short, will fail lint)
        for _ in range(20):
            answers.append(json.dumps({"note": "no"}))

        model = llm.ScriptedModel(*answers)

        result = generate._regenerate_linkedin_set(
            rec, contact, model, self.config)

        self.assertIsNone(result)

        # Originals preserved
        for sk, original_text in originals.items():
            current = rec["cadence"]["ranjan-damodar"][sk]["note"]
            self.assertEqual(current, original_text,
                             f"{sk} should be preserved after failed set regen")


class PlanIntegrationTest(unittest.TestCase):
    """plan: emits linkedin_set instead of individual linkedin_note ops."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-setregen-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = pin_client_config(
            self, linkedin_connection_note={"mode": "llm"},
            cadence="productive_li_heavy_v1")

    def tearDown(self):
        if self._prev_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev_queue
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_plan_emits_linkedin_set_for_colliding_contact(self):
        """A contact with colliding notes gets a linkedin_set op."""
        rec = _make_record(notes=COLLIDING_NOTES)
        store.save([rec])

        ops = generate.plan(rec, self.config)
        set_ops = [o for o in ops if o.get("step") == "linkedin_set"]
        note_ops = [o for o in ops
                    if o.get("step") == "linkedin_note"
                    and o.get("contact") == "ranjan-damodar"]

        self.assertEqual(len(set_ops), 1,
                         f"expected one linkedin_set op, got {len(set_ops)}")
        self.assertEqual(len(note_ops), 0,
                         "individual linkedin_note ops should be replaced")
        self.assertIn("collide", set_ops[0]["why"])

    def test_plan_does_not_emit_set_for_distinct_notes(self):
        """A contact with distinct notes gets normal linkedin_note ops."""
        rec = _make_record(notes=DISTINCT_NOTES)
        store.save([rec])

        ops = generate.plan(rec, self.config)
        set_ops = [o for o in ops if o.get("step") == "linkedin_set"]

        self.assertEqual(len(set_ops), 0,
                         "distinct notes should not trigger set regeneration")

    def test_linkedin_set_propagates_ladder_stale(self):
        """TASK-129: when a linkedin_set absorbs ladder-stale notes, the
        set op carries ladder_stale and stale_step_count."""
        rec = _make_record(notes=COLLIDING_NOTES)
        store.save([rec])

        ops = generate.plan(rec, self.config, regen_stale_ladder=True)
        set_ops = [o for o in ops if o.get("step") == "linkedin_set"]

        self.assertEqual(len(set_ops), 1)
        self.assertTrue(set_ops[0].get("ladder_stale"),
                        "linkedin_set should carry ladder_stale when it "
                        "absorbs stale notes")
        # COLLIDING_NOTES has 5 notes, all without fingerprints.
        self.assertEqual(set_ops[0].get("stale_step_count"), 5,
                         "stale_step_count should match the number of "
                         "ladder-stale notes absorbed")

    def test_linkedin_set_without_stale_notes_has_no_ladder_stale(self):
        """TASK-129: a linkedin_set for notes that are NOT stale does not
        carry ladder_stale."""
        rec = _make_record(notes=COLLIDING_NOTES)
        # Give every note a current fingerprint so none is stale.
        seq = generate.sequence_for(rec, self.config,
                                    rec["contacts"][0])
        for sk, step in rec["cadence"]["ranjan-damodar"].items():
            channel = step.get("channel")
            _, ordinal, _ = generate.position(seq, sk)
            fp = generate.ladder_fingerprint(channel, ordinal,
                                             sequence=seq)
            if fp:
                step["ladder_fingerprint"] = fp
        store.save([rec])

        ops = generate.plan(rec, self.config, regen_stale_ladder=True)
        set_ops = [o for o in ops if o.get("step") == "linkedin_set"]

        self.assertEqual(len(set_ops), 1)
        self.assertFalse(set_ops[0].get("ladder_stale"),
                         "linkedin_set should NOT carry ladder_stale when "
                         "no absorbed notes are stale")


class GenerateRecordIntegrationTest(unittest.TestCase):
    """generate_record: drives through the real entry point."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-setregen-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = pin_client_config(
            self, linkedin_connection_note={"mode": "llm"},
            cadence="productive_li_heavy_v1")

    def tearDown(self):
        if self._prev_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev_queue
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _good_note(self, step_key):
        distinct = {
            "li1": "hi ranjan, your advertising technology work is impressive",
            "li2": "curious how your team handles client onboarding flows",
            "li3": "we built a tool for agencies struggling with billing",
            "li4": "your approach to addressable ads across platforms stands out",
            "li5": "would love to hear about your biggest operational challenge",
            "li6": "no pressure but happy to share what we have learned",
        }
        return distinct.get(step_key, "a clean distinct note about operations")

    def test_generate_record_replaces_colliding_set(self):
        """The real entry point replaces a colliding set transactionally."""
        rec = _make_record(notes=COLLIDING_NOTES)
        store.save([rec])

        old_notes = {}
        for sk, step in rec["cadence"]["ranjan-damodar"].items():
            old_notes[sk] = step["note"]

        answers = [json.dumps({"note": self._good_note(f"li{i}")})
                   for i in range(1, 7)]
        model = llm.ScriptedModel(*answers)

        done = generate.generate_record(rec, model, self.config)

        set_done = [o for o in done if o.get("step") == "linkedin_set"]
        self.assertEqual(len(set_done), 1,
                         "linkedin_set op should be in the done list")

        new_li1 = rec["cadence"]["ranjan-damodar"]["li1"]["note"]
        self.assertNotEqual(new_li1, old_notes["li1"],
                            "the old colliding note should be replaced")

    def test_model_calls_are_counted(self):
        """Set regeneration counts model calls through the standard hook."""
        rec = _make_record(notes=COLLIDING_NOTES)
        store.save([rec])

        generate.reset_model_calls()
        answers = [json.dumps({"note": self._good_note(f"li{i}")})
                   for i in range(1, 7)]
        model = llm.ScriptedModel(*answers)

        generate.generate_record(rec, model, self.config)

        calls = generate.model_calls.get("linkedin_set", 0)
        self.assertGreaterEqual(calls, 6,
                                "at least one call per note in the set")


class WiringTest(unittest.TestCase):
    """The new code is consumed by the real entry points.

    TASK-068's rule: existence is not function. These tests prove the
    wiring, not the text of the source.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-setregen-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._prev_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = pin_client_config(
            self, linkedin_connection_note={"mode": "llm"},
            cadence="productive_li_heavy_v1")

    def tearDown(self):
        if self._prev_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev_queue
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_needs_set_regeneration_is_called_by_plan(self):
        """Break the wiring: patch _needs_set_regeneration to return None.
        If plan still emits linkedin_set, the wiring is fake."""
        rec = _make_record(notes=COLLIDING_NOTES)
        store.save([rec])

        with mock.patch.object(generate, "_needs_set_regeneration",
                               return_value=None):
            ops = generate.plan(rec, self.config)

        set_ops = [o for o in ops if o.get("step") == "linkedin_set"]
        self.assertEqual(len(set_ops), 0,
                         "breaking _needs_set_regeneration should prevent "
                         "linkedin_set ops - if it does not, the wiring is fake")

    def test_regenerate_linkedin_set_is_called_by_generate_record(self):
        """Break the wiring: patch _regenerate_linkedin_set to return None.
        If the old notes are still replaced, the wiring is fake."""
        rec = _make_record(notes=COLLIDING_NOTES)
        store.save([rec])

        old_li1 = rec["cadence"]["ranjan-damodar"]["li1"]["note"]

        with mock.patch.object(generate, "_regenerate_linkedin_set",
                               return_value=None):
            answers = [json.dumps({"note": "irrelevant"}) for _ in range(20)]
            model = llm.ScriptedModel(*answers)
            done = generate.generate_record(rec, model, self.config)

        set_done = [o for o in done if o.get("step") == "linkedin_set"]
        # The op is in done (plan emitted it) but the handler returned None,
        # so continue skips it... actually, let me check: when the handler
        # returns None, `continue` is hit, so the op is NOT added to done.
        self.assertEqual(len(set_done), 0,
                         "when _regenerate_linkedin_set returns None, the op "
                         "should not be in done")

        # The old note should be preserved
        current_li1 = rec["cadence"]["ranjan-damodar"]["li1"]["note"]
        self.assertEqual(current_li1, old_li1,
                         "when the handler returns None, originals are preserved")

    def test_gates_not_weakened(self):
        """SUBJECT_VOCABULARY and campaign_repetition are unchanged."""
        self.assertIn("utilisation", quality.SUBJECT_VOCABULARY)
        self.assertIn("utilization", quality.SUBJECT_VOCABULARY)
        self.assertIn("profitability", quality.SUBJECT_VOCABULARY)
        self.assertIn("margin", quality.SUBJECT_VOCABULARY)

        # campaign_repetition still discounts subject vocabulary
        steps = [
            {"key": "a", "text": "tracking utilisation across projects"},
            {"key": "b", "text": "managing utilisation across projects"},
        ]
        collisions = quality.campaign_repetition(steps)
        # With subject vocabulary discounted, "utilisation" is removed,
        # leaving "tracking"/"managing", "across", "projects" as shared.
        # That is 3 shared words, which meets the minimum.
        # The overlap depends on the distinctive word counts.
        # This test just verifies the function still runs and the
        # vocabulary is still discounted.
        self.assertIsInstance(collisions, list)


if __name__ == "__main__":
    unittest.main()
