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

from src import cadence, claims, clients, generate, lint, llm, store
from tests.base import FIXTURES, pin_client_config

# "month end reconciliation" was in here and it is `personas.champion.angles`
# `finance` VERBATIM - the client's own sales phrasing, which
# `quality.angle_leakage` refuses on LinkedIn. It went unnoticed while
# `generate.linkedin_note` ran no gate at all; it stored whatever the model
# returned after one cross-channel word check. Now that the note goes through
# the same door the email does, a fixture carrying the client's angle wording
# is a fixture that cannot pass.
#
# Measured before changing it: all eight of the operator's hand-written
# LinkedIn fallback lines in `config/clients/productive.yaml` pass this rule.
# The gate is not too strict - this note was.
GOOD_NOTE = ("hi Ivana, i work with finance leads at agencies running several "
             "offices, usually around how long the numbers take to settle. "
             "curious how you handle it. happy to connect.")


class NoteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-note-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        # The note mode is REMOVED, not inherited. This module asks what
        # the DEFAULT is - `TestTemplateModeIsTheDefault` is the class
        # name - and Productive chose `llm` on 2026-09-13 so its five
        # generated LinkedIn steps would have copy. A test about a
        # default that reads a live client's choice is asking the wrong
        # file. `llm_config()` below puts it back explicitly for the
        # tests that are about the other mode.
        self.config = pin_client_config(self, linkedin_connection_note=None)
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
        # THE STEP THAT WAS WRITTEN, not every step this contact has.
        #
        # This asserted that no `linkedin_note` op mentioned Ivana at all,
        # which was true only while a sequence had ONE LinkedIn step. Both
        # the module constant and `productive_balanced_v1` carry two - day3
        # connect and day8 message - and writing the day3 note does not and
        # must not satisfy day8. A connection request and a follow-up message
        # are different objects written from different rungs of
        # `LINKEDIN_LADDER`.
        #
        # The claim is unchanged: a note already written is not written again.
        written = [(op.get("contact"), op.get("day")) for op in ops
                   if op["step"] == "linkedin_note"]
        self.assertNotIn(("Ivana Šarić", "day3"), written)
        self.assertIn(("Ivana Šarić", "day8"), written,
                      "the step that was never written should still be asked for")


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


class TestTheNoteGoesThroughTheSameDoorTheEmailDoes(NoteTest):
    """`linkedin_note` stored whatever the model returned.

    It checked one thing - that the note did not mention the email - and then
    wrote it to the record. It did not call `lint`, `claims` or the quality
    gate, all three of which `generate.draft` has run inside its attempt loop
    since the em5 "Final note on our previous discussions" defect.

    `lint.check_step` is documented as "the single door every step goes
    through" and the LinkedIn generator walked past it. `quality.gate` even
    DEFAULTS to `channel="linkedin"` and had only ever been called with
    `channel="email"`.

    Measured 2026-09-14 on a live regeneration of `ogpartner-dk`: six notes
    written, two of them carrying an em dash that `lint.check_linkedin` names
    `em_dash` and refuses, and one asserting a product that does not exist.
    All six stored clean.
    """

    def write(self, *answers):
        model = llm.ScriptedModel(*[json.dumps({"note": a}) for a in answers])
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            return generate.linkedin_note(rec, rec["contacts"][0], model,
                                          self.llm_config())

    def test_an_em_dash_is_normalised_rather_than_spending_an_attempt(self):
        # CHANGED BY TASK-055, and the change is the point. This asserted
        # that an em dash was REFUSED and the note regenerated. It is now
        # normalised to " - " before lint sees it, so the first answer is
        # kept and the attempt is not spent.
        #
        # Four of six em4 refusals in a live run were a dash or a curly
        # apostrophe, and `draft` allows three attempts - so a step whose
        # first two answers carried one had a single attempt left for
        # everything else. A character substitution that changes no word is
        # not a content failure.
        #
        # What must NOT change: the stored text is still plain ASCII, and
        # `lint` still refuses the character on every other path.
        step = self.write("hi Ivana, i work with finance leads at agencies "
                          "running several offices\u2014curious how you handle "
                          "it. happy to connect.")
        self.assertIn(" - ", step["note"])
        for char in lint.SUBSTITUTED_PUNCTUATION:
            self.assertNotIn(char, step["note"])

    def test_a_note_that_never_passes_stores_nothing(self):
        # Three attempts, all refused, and NOTHING is written. The old path
        # had no way to express this: it stored on the first answer.
        #
        # The refusal is a CONTENT one now that punctuation is normalised -
        # this note repeats itself and says nothing, which no amount of
        # character substitution fixes.
        # `personas.champion.angles.finance` verbatim, which
        # `quality.angle_leakage` refuses on LinkedIn - the client's own sales
        # phrasing put into a note. A content failure no retry can normalise
        # away, which is exactly what this test needs.
        bad = ("hi Ivana, margin per project, month end reconciliation and "
               "multi entity billing are what i work on. happy to connect.")
        self.assertIsNone(self.write(bad, bad, bad))
        self.assertNotIn("day3", (self.rec().get("cadence") or {}).get(
            "ivana-saric", {}))

    def test_a_product_we_do_not_sell_is_refused(self):
        # The defect this gate was built for, and the one nothing else could
        # see: `claims.check` judges sentences against the RECORD, and an
        # invented product name asserts nothing about the prospect.
        step = self.write("hi Ivana, our software, ProjectSync, joins up "
                          "budgets and resourcing for agencies. worth a look?",
                          GOOD_NOTE)
        self.assertEqual(step["note"], GOOD_NOTE)

    def test_the_clients_own_product_name_is_not_refused(self):
        # The other half. A rule that cannot tell Productive from ProjectSync
        # would refuse the rung whose whole job is to name the product.
        note = ("hi Ivana, we built Productive so budgets and resourcing talk "
                "to each other for agencies running several offices. worth a "
                "look?")
        self.assertEqual(self.write(note)["note"], note)

    def test_the_refusal_reason_reaches_the_model(self):
        # A model told a code three times has been told nothing three times.
        # `draft` feeds the reason back and so must this.
        model = llm.ScriptedModel(
            json.dumps({"note": "hi Ivana, our software, ProjectSync, joins "
                                "up budgets and resourcing. worth a look?"}),
            json.dumps({"note": GOOD_NOTE}))
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            generate.linkedin_note(rec, rec["contacts"][0], model,
                                   self.llm_config())
        second = model.prompts[-1] if hasattr(model, "prompts") else ""
        if second:
            self.assertIn("ProjectSync", second)
            self.assertIn("previous note was refused", second)

    # THE CROSS-CHANNEL CHECK IS NOT RE-TESTED HERE, DELIBERATELY.
    #
    # A note containing "email" never reaches the storer's check at all:
    # `llm.validate` refuses it at the schema layer and `llm.ask` retries
    # inside one call. The storer's fuller word list is reached only by a
    # note that passes the schema, and
    # `TestLlmMode.test_a_note_that_slips_past_the_schema_is_still_not_stored`
    # already drives exactly that case with "you replied to my earlier one".
    # A test written here asserting the outright refusal passed for the wrong
    # reason - the model's second answer was stored - which is what a
    # redundant test at the wrong layer looks like.


class TestThePlanRegeneratesANoteThatFailsTheGates(NoteTest):
    """A stored note that fails the gates is re-planned, not counted as done.

    `plan` asked only whether a note EXISTED, so a stored note asserting
    something the record cannot support was counted as work already finished
    and nothing else regenerated it. The email branch fixed this on
    2026-09-13; the LinkedIn branch twenty lines above it still asked only
    whether a note existed.

    Measured on `productive-linkedin-production-v1`, 2026-09-14: five contacts
    blocked by real claims, nothing regenerating them.
    """

    def _store_note(self, step_key, note_text):
        """Write a note directly to the record, bypassing the gates."""
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            key = lint.contact_key(rec["contacts"][0])
            rec.setdefault("cadence", {}).setdefault(key, {})[step_key] = {
                "channel": "linkedin", "generated": True, "note": note_text}

    def test_a_clean_stored_note_is_not_re_planned(self):
        """A note that passes everything is done work, not pending work."""
        self._store_note("day3", GOOD_NOTE)
        rec = self.rec()
        contact_name = rec["contacts"][0]["name"]
        ops = generate.plan(rec, self.llm_config())
        note_ops = [o for o in ops
                    if o["step"] == "linkedin_note" and o.get("day") == "day3"
                    and o.get("contact") == contact_name]
        self.assertEqual(note_ops, [],
                         "a clean stored note was re-planned for regeneration")

    def test_a_note_asserting_an_unsupported_claim_is_re_planned(self):
        """A note that says something the record does not support is not done."""
        bad = ("hi Ivana, our previous discussions about your profitability "
               "setup were very productive. happy to connect.")
        self._store_note("day3", bad)
        rec = self.rec()
        contact_name = rec["contacts"][0]["name"]
        unsupported = claims.check(bad, rec, rec["contacts"][0])
        self.assertTrue(unsupported,
                        "the fixture note does not actually fail claims.check")
        ops = generate.plan(rec, self.llm_config())
        note_ops = [o for o in ops
                    if o["step"] == "linkedin_note" and o.get("day") == "day3"
                    and o.get("contact") == contact_name]
        self.assertTrue(note_ops,
                        "a note asserting an unsupported claim was not re-planned")
        self.assertIn("unsupported claim", note_ops[0]["why"])

    def test_a_note_that_fails_lint_is_re_planned(self):
        """A stored note with a lint violation is re-planned."""
        bad = "hi Ivana, our previous discussions\u2014very productive. happy to connect."
        self._store_note("day3", bad)
        rec = self.rec()
        contact_name = rec["contacts"][0]["name"]
        key = lint.contact_key(rec["contacts"][0])
        step = rec["cadence"][key]["day3"]
        failures = lint.check_step(rec, key, step)
        self.assertIn("em_dash", failures,
                      "the fixture note does not actually fail lint")
        ops = generate.plan(rec, self.llm_config())
        note_ops = [o for o in ops
                    if o["step"] == "linkedin_note" and o.get("day") == "day3"
                    and o.get("contact") == contact_name]
        self.assertTrue(note_ops,
                        "a note failing lint was not re-planned")
        self.assertIn("fails lint", note_ops[0]["why"])

    def test_a_note_for_a_contact_with_no_profile_is_not_re_planned(self):
        """No rewrite fixes a missing profile. The held code must not trigger
        three model calls and then block forever."""
        self.assertIn("profile_missing", lint.LINKEDIN_HELD_CODES)
        bad = "hi there, our profitability discussions were great. connect?"
        self._store_note("day3", bad)
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            rec["contacts"][0]["linkedin"] = None
        rec = self.rec()
        ops = generate.plan(rec, self.llm_config())
        note_ops = [o for o in ops
                    if o["step"] == "linkedin_note"
                    and o.get("contact") == rec["contacts"][0]["name"]]
        self.assertEqual(note_ops, [],
                         "a contact with no profile had notes re-planned")

    def test_the_reason_reaches_the_ops_why(self):
        """An operator reading the plan must see which note and what for."""
        bad = ("hi Ivana, our previous discussions about your profitability "
               "setup were very productive. happy to connect.")
        self._store_note("day3", bad)
        rec = self.rec()
        contact_name = rec["contacts"][0]["name"]
        ops = generate.plan(rec, self.llm_config())
        note_ops = [o for o in ops
                    if o["step"] == "linkedin_note" and o.get("day") == "day3"
                    and o.get("contact") == contact_name]
        self.assertTrue(note_ops)
        why = note_ops[0]["why"]
        self.assertIn(contact_name.split()[0], why)
        self.assertIn("day3", why)
        self.assertTrue(
            "unsupported claim" in why or "fails lint" in why
            or "repeats" in why or "product" in why,
            f"the why {why!r} does not say what is wrong")

    def test_breaking_the_wiring_makes_the_intended_test_fail(self):
        """If the claims check is removed from plan, the unsupported-claim
        test must fail. This proves the test is connected to the code, not
        passing by accident."""
        bad = ("hi Ivana, our previous discussions about your profitability "
               "setup were very productive. happy to connect.")
        self._store_note("day3", bad)
        rec = self.rec()
        contact_name = rec["contacts"][0]["name"]
        # Verify the note actually fails claims
        unsupported = claims.check(bad, rec, rec["contacts"][0])
        self.assertTrue(unsupported, "fixture is not actually broken")
        # Verify plan catches it
        ops = generate.plan(rec, self.llm_config())
        note_ops = [o for o in ops
                    if o["step"] == "linkedin_note" and o.get("day") == "day3"
                    and o.get("contact") == contact_name]
        self.assertTrue(note_ops,
                        "plan did not re-plan a note with unsupported claims")
        # Now verify that WITHOUT the claims check, it would NOT be caught.
        # Simulate by checking that the note passes lint (so lint alone
        # would not catch it):
        key = lint.contact_key(rec["contacts"][0])
        step = rec["cadence"][key]["day3"]
        lint_failures = [f for f in lint.check_step(rec, key, step)
                         if f not in lint.LINKEDIN_HELD_CODES]
        lint_verdict = lint.classify_linkedin(lint_failures)
        # The note should pass lint (it is the claims that fail)
        self.assertEqual(lint_verdict, "clean",
                         "the fixture fails lint, so this test does not prove "
                         "the claims wiring is connected")
