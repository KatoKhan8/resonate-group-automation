"""The day 3 connection note: template or written, the client chooses.

BUILD-SPEC section 7 marks the note as generated; section 8 defines no prompt
for it. Rather than choose silently, both strategies exist and the client config
selects. Template is the default because it costs nothing and cannot wander.

No live model is called here, in either mode.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import cadence, clients, generate, llm, store
from tests.base import FIXTURES

GOOD_NOTE = ("hi Ivana, i work with finance leads at multi office agencies on "
             "month end reconciliation. curious how you handle it. happy to connect.")


class NoteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-note-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.config = clients.load("productive")
        generate.reset_model_calls()

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)
        generate.reset_model_calls()

    def llm_config(self):
        config = clients.load("productive")
        config["linkedin_connection_note"] = {"mode": "llm"}
        return config

    def rec(self, rid="meridian"):
        return store.get(rid)

    def contact(self, key="ivana-saric"):
        return next(c for c in self.rec()["contacts"] if c["key"] == key)

    def day3(self, config=None):
        return cadence.build(self.rec(), config or self.config)[
            "contacts"]["ivana-saric"]["day3"]


class TestTemplateModeIsTheDefault(NoteTest):
    def test_the_default_mode_is_template(self):
        self.assertEqual(clients.linkedin_note_mode(self.config), "template")

    def test_the_note_is_rendered_from_the_template(self):
        step = self.day3()
        self.assertFalse(step["generated"])
        self.assertEqual(step["template"], "linkedin_intro")
        self.assertNotIn("{", step["note"])

    def test_template_mode_asks_the_model_for_nothing(self):
        ops = generate.plan(self.rec(), self.config)
        self.assertNotIn("linkedin_note", [o["step"] for o in ops])

    def test_the_template_note_never_mentions_the_email(self):
        note = self.day3()["note"].lower()
        for word in generate.NOTE_MUST_NOT_MENTION:
            self.assertNotIn(word, note)

    def test_template_mode_costs_no_model_calls(self):
        generate.run(model=llm.ScriptedModel(), live=False)
        self.assertEqual(generate.model_calls, {})


class TestLlmMode(NoteTest):
    def test_the_mode_is_read_from_the_client_config(self):
        self.assertEqual(clients.linkedin_note_mode(self.llm_config()), "llm")

    def test_llm_mode_plans_a_note_for_a_contact_with_a_profile(self):
        ops = generate.plan(self.rec(), self.llm_config())
        note_ops = [o for o in ops if o["step"] == "linkedin_note"]
        self.assertTrue(note_ops)
        self.assertEqual(note_ops[0]["day"], "day3")
        self.assertTrue(note_ops[0]["why"])

    def test_a_written_note_is_stored_and_used_by_the_cadence(self):
        model = llm.ScriptedModel(json.dumps({"note": GOOD_NOTE}))
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            generate.linkedin_note(rec, rec["contacts"][0], model, self.llm_config())
        step = self.day3(self.llm_config())
        self.assertTrue(step["generated"])
        self.assertEqual(step["note"], GOOD_NOTE)
        self.assertNotIn("template", step)

    def test_a_written_note_is_counted_for_cost(self):
        model = llm.ScriptedModel(json.dumps({"note": GOOD_NOTE}))
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            generate.linkedin_note(rec, rec["contacts"][0], model, self.llm_config())
        self.assertEqual(generate.model_calls.get("linkedin_note"), 1)

    def test_a_note_that_is_too_long_is_rejected_and_retried(self):
        model = llm.ScriptedModel(json.dumps({"note": "x" * 400}),
                                  json.dumps({"note": GOOD_NOTE}))
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            step = generate.linkedin_note(rec, rec["contacts"][0], model,
                                          self.llm_config())
        self.assertEqual(step["note"], GOOD_NOTE)
        self.assertEqual(len(model.prompts), 2)

    def test_a_note_that_mentions_the_email_is_rejected(self):
        with self.assertRaises(llm.SchemaError) as e:
            llm.validate("linkedin_note", {"note": "following up on my email below"})
        self.assertIn("never references the email", str(e.exception))

    def test_a_note_that_slips_past_the_schema_is_still_not_stored(self):
        """Belt and braces: the storer checks the wording too."""
        # passes the schema word list, caught by the fuller cadence list
        sneaky = "hi there, you replied to my earlier one, happy to connect"
        model = llm.ScriptedModel(json.dumps({"note": sneaky}))
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            result = generate.linkedin_note(rec, rec["contacts"][0], model,
                                            self.llm_config())
            self.assertIsNone(result)
            self.assertNotIn("generated", rec["cadence"]["ivana-saric"].get("day3", {}))

    def test_an_empty_note_is_rejected(self):
        with self.assertRaises(llm.SchemaError):
            llm.validate("linkedin_note", {"note": "   "})

    def test_the_prompt_carries_the_contract_and_fences_the_record(self):
        prompt = generate.render_prompt("linkedin_note", self.rec(),
                                        self.contact(), self.llm_config())
        self.assertIn("# linkedin_note", prompt)
        self.assertIn("Under 300 characters", prompt)
        self.assertIn(llm.BEGIN, prompt)

    def test_the_prompt_does_not_carry_the_email_draft(self):
        prompt = generate.render_prompt("linkedin_note", self.rec(),
                                        self.contact(), self.llm_config())
        body = self.rec()["cadence"]["ivana-saric"]["day1"]["body"]
        self.assertNotIn(body[:40], prompt)

    def test_a_contact_with_no_profile_is_never_asked_for(self):
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            for contact in rec["contacts"]:
                contact["linkedin"] = None
        ops = generate.plan(self.rec(), self.llm_config())
        self.assertEqual([o for o in ops if o["step"] == "linkedin_note"], [])

    def test_an_existing_written_note_is_not_rewritten(self):
        model = llm.ScriptedModel(json.dumps({"note": GOOD_NOTE}))
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            generate.linkedin_note(rec, rec["contacts"][0], model, self.llm_config())
        ops = generate.plan(self.rec(), self.llm_config())
        for op in ops:
            self.assertNotEqual((op["step"], op.get("contact")),
                                ("linkedin_note", "Ivana Šarić"))


class TestModeIsValidated(NoteTest):
    def test_an_unknown_mode_is_refused_rather_than_defaulted(self):
        config = clients.load("productive")
        config["linkedin_connection_note"] = {"mode": "carrier pigeon"}
        with self.assertRaises(clients.ConfigError):
            clients.linkedin_note_mode(config)

    def test_both_modes_produce_a_note_that_passes_the_cross_channel_check(self):
        template_steps = cadence.build(self.rec(), self.config)["contacts"]["ivana-saric"]
        self.assertEqual(cadence.cross_channel_leaks(template_steps), [])

        model = llm.ScriptedModel(json.dumps({"note": GOOD_NOTE}))
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            generate.linkedin_note(rec, rec["contacts"][0], model, self.llm_config())
        llm_steps = cadence.build(self.rec(), self.llm_config())["contacts"]["ivana-saric"]
        self.assertEqual(cadence.cross_channel_leaks(llm_steps), [])


if __name__ == "__main__":
    unittest.main()
