#!/usr/bin/env python3
"""The cadence lands in all four places, or it lands nowhere.

2026-09-25. `breakup` is retired and Productive sends em1..em5, with em3
now RUNG 3 - the step that names the product.
Four files have to agree about that and `bisonfactory` refuses when they do
not - with a message that names the keys but not the FILE the wrong keys came
from, which is why the half-applied state cost an evening.

WHAT THIS ASSERTS IS THE EFFECT, NOT THE TEXT. Every test below either builds
a provider sequence through `bisonfactory._sequence_steps` - the function that
does the refusing - or reads a value off the sequence it built. None of them
greps a source file, so none of them fails when somebody writes a comment.

THE REGRESSION EACH ONE CATCHES, stated so it can be checked by breaking it:

  * put `em3` back in `email_sequence.steps`, or take `em4`/`em5` out of
    `CADENCE_STEPS`, and `test_the_config_and_the_builder_agree` goes red
    with the real refusal;
  * shorten `thread_reply_pattern` back to three entries and
    `test_the_pattern_has_one_entry_per_step` goes red - the last step
    silently becomes a new thread, which is the shape the 2026-09-16
    invariant exists to refuse;
  * set the final `wait_in_days` to 0 and `test_the_final_wait_is_one` goes
    red. Campaign 485 was created and left holding zero steps by exactly
    that value.
"""
import os
import unittest

import yaml

from src import bisonfactory, clients
from src.bisonfactory import FactoryRefused


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _builder_cadence_steps():
    """`CADENCE_STEPS` out of `scripts/batch1_build.py`.

    Loaded by path rather than imported as a package: `scripts/` is not one,
    and the module inserts the repo root on `sys.path` at import time, which
    is harmless but is a side effect a test should not depend on ordering.
    """
    import importlib.util

    path = os.path.join(ROOT, "scripts", "batch1_build.py")
    spec = importlib.util.spec_from_file_location("batch1_build_under_test",
                                                  path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CADENCE_STEPS, module.STEP_KEYS


def _email_sequence():
    """Productive's `email_sequence`, read the way the factory reads it."""
    return (clients.load("productive") or {}).get("email_sequence") or {}


class TheCadenceAgreesEverywhere(unittest.TestCase):

    def setUp(self):
        self.cadence_steps, self.step_keys = _builder_cadence_steps()
        self.configured = _email_sequence()

    # ---------------------------------------------------------------- keys

    def test_the_config_and_the_builder_agree(self):
        """The whole coupling, asserted through the thing that refuses.

        `_sequence_steps` is the only code that compares the two halves, so
        calling it is the assertion. A mismatch raises `FactoryRefused` and
        this fails with the provider's own reason attached.
        """
        try:
            sequence = bisonfactory._sequence_steps(self.configured,
                                                    self.cadence_steps)
        except FactoryRefused as refusal:
            self.fail(
                "the client config and scripts/batch1_build.py CADENCE_STEPS "
                "disagree, so every stage against a batch-1 campaign refuses: "
                f"{refusal}")
        self.assertEqual([s["step_key"] for s in sequence],
                         ["em1", "em2", "em3", "em4", "em5"])

    def test_no_step_claims_to_be_the_last_one(self):
        """`breakup` is retired, asserted by its SENTENCE not by its name.

        Not a style point. `breakup` says "I will leave it here", and any
        step after it makes that sentence false on every send - a claim about
        our own conduct that nothing on the send path can catch, because
        `claims.py` reads claims about the PROSPECT and `outreachclaims` has
        no consumer there.

        Asserted on the rendered bodies rather than on the template NAME,
        because renaming a template would not change what a prospect reads.
        `em3` is now rung 3 and is checked to be present, since the key was
        `breakup`'s until 2026-09-25 and silently losing it would shorten the
        cadence with nothing saying so.
        """
        sequence = bisonfactory._sequence_steps(self.configured,
                                                self.cadence_steps)
        by_key = {s["step_key"]: s for s in sequence}
        self.assertIn("em3", by_key)
        for step in sequence:
            self.assertNotIn("leave it here", step["email_body"].lower())

    def test_the_builder_approves_every_step_the_sequence_will_send(self):
        """`STEP_KEYS` is what gets approved; the sequence is what gets sent.

        A step in the sequence and not in `STEP_KEYS` is staged with no
        approved copy, which `_ensure_leads` refuses - after the campaign
        exists. A step approved and never sent is wasted work. They are the
        same set or one of those two things is true.
        """
        sequence = bisonfactory._sequence_steps(self.configured,
                                                self.cadence_steps)
        self.assertEqual(set(self.step_keys),
                         {s["step_key"] for s in sequence})

    # ------------------------------------------------------------ threading

    def test_the_pattern_has_one_entry_per_step(self):
        """`thread_reply_pattern` is read POSITIONALLY, one bool per step.

        Too short and the steps past its end default to False - a new thread
        with no subject of its own. Too long and it describes a sequence this
        config does not declare.
        """
        pattern = self.configured.get("thread_reply_pattern")
        self.assertEqual(len(pattern), len(self.cadence_steps))

    def test_only_the_opener_opens_a_thread(self):
        """Asserted on the BUILT sequence, not on the configured list.

        This is what the provider is told. The 2026-09-16 invariant - operator
        verified in the EmailBison UI - is that only the opener owns a
        subject, so every follow-up is a thread reply.
        """
        sequence = bisonfactory._sequence_steps(self.configured,
                                                self.cadence_steps)
        self.assertFalse(sequence[0]["thread_reply"])
        for step in sequence[1:]:
            self.assertTrue(
                step["thread_reply"],
                f"{step['step_key']} opens a new thread. Every follow-up must "
                "be a thread reply while the opener owns the only subject")

    def test_no_second_subject_variable_is_referenced(self):
        """There is exactly one subject variable, and it is `SUBJECT_1`.

        em4 was drafted to open a second thread carrying `{SUBJECT_2}`. The
        threading invariant refuses that shape, so no `subject_2` is
        generated, approved or sent. If this ever changes it is a change to
        `bisonfactory`, and this test is where that decision is recorded.
        """
        sequence = bisonfactory._sequence_steps(self.configured,
                                                self.cadence_steps)
        opener = sequence[0]["email_subject"]
        for step in sequence:
            self.assertEqual(step["email_subject"], opener)

    # ---------------------------------------------------------------- waits

    def test_the_final_wait_is_one(self):
        """1, never 0.

        `wait_in_days` is the wait AFTER a step, so the final one has no
        successor and is checked against nothing - MEASURED, not assumed:
        bumping each of the first four by one makes `_sequence_steps` refuse,
        and bumping the terminal one does not. That is exactly how a 0
        survives review. The provider rejects 0: campaign 485 was created and
        `set_sequence` raised, leaving it holding zero steps.
        """
        sequence = bisonfactory._sequence_steps(self.configured,
                                                self.cadence_steps)
        self.assertEqual(sequence[-1]["wait_in_days"], 1)
        self.assertNotEqual(sequence[-1]["wait_in_days"], 0)

    def test_every_other_wait_reproduces_the_cadence_gap(self):
        """The declared delays are the cadence's own gaps.

        `_sequence_steps` already refuses a mismatch; this states the
        expected numbers so a silent change to the DAYS - which would move
        both sides together and refuse nothing - still shows up.
        """
        sequence = bisonfactory._sequence_steps(self.configured,
                                                self.cadence_steps)
        days = {s["key"]: s["day"] for s in self.cadence_steps}
        self.assertEqual(days, {"em1": 1, "em2": 4, "em3": 8, "em4": 12,
                                "em5": 21})
        self.assertEqual([s["wait_in_days"] for s in sequence],
                         [3, 4, 4, 9, 1])

    # ------------------------------------------------------- the copy slots

    def test_the_variable_numbers_are_positions_not_step_keys(self):
        """em4 reads BODY_3 and em5 reads BODY_4, and that is not a typo.

        `_variables_for` numbers the per-lead copy variables by POSITION in
        the sequence. The step KEYS jump from em2 to em4 because em3 was
        retired, so the two numbering schemes deliberately disagree. Writing
        `{BODY_4}` against em4 because the key says 4 would send em5's words
        as the third email.
        """
        sequence = bisonfactory._sequence_steps(self.configured,
                                                self.cadence_steps)
        by_key = {s["step_key"]: s["email_body"] for s in sequence}
        for position, step in enumerate(sequence, start=1):
            self.assertIn("{BODY_%d}" % position, step["email_body"])
        # At FIVE steps position and key coincide. They did NOT at four, when
        # em4 was the third step and read {BODY_3}. Asserting the rule
        # (position) rather than the coincidence (key).
        self.assertIn("{BODY_3}", by_key["em3"])
        self.assertIn("{BODY_5}", by_key["em5"])

    def test_every_lead_variable_the_template_reads_is_written(self):
        """The payload carries a value for every merge field the steps name.

        A step whose variable is absent renders as nothing: the campaign
        stages, the sequence reads back correctly, and a real person receives
        an email with no subject and no body. So the set of `{NAME}` fields
        the sequence references and the set of variables `_variables_for`
        writes are compared directly.
        """
        import re

        sequence = bisonfactory._sequence_steps(self.configured,
                                                self.cadence_steps)
        referenced = set()
        for step in sequence:
            for field in (step["email_subject"], step["email_body"]):
                referenced.update(m.lower() for m in
                                  re.findall(r"\{([A-Z_0-9]+)\}", field))
        lead = {"record_id": "rec", "contact_key": "who",
                "copy": [{"step_key": s["step_key"], "subject": "S",
                          "body": "a body for " + s["step_key"]}
                         for s in sequence]}
        written = {v["name"]: v["value"] for v in bisonfactory._variables_for(
            lead, {"client": "productive"}, sequence=sequence)}
        self.assertEqual(referenced - set(written), set())
        # And the ones that carry prospect-facing words are not empty.
        for name in referenced:
            if name.startswith("body_") or name == "subject_1":
                self.assertTrue(
                    str(written[name]).strip(),
                    f"{name} is empty, so that step sends a blank email")

    def test_a_threaded_follow_up_leaks_no_subject(self):
        """Follow-up subjects go to the provider empty, and stay empty.

        Two mechanisms have to agree: `_variables_for` writes them empty and
        `_stale_clearances` clears any left over from a non-threaded era. A
        value written by one and contradicted by the other lands in the same
        PATCH twice and whichever the provider applies last wins.
        """
        sequence = bisonfactory._sequence_steps(self.configured,
                                                self.cadence_steps)
        lead = {"record_id": "rec", "contact_key": "who",
                "copy": [{"step_key": s["step_key"], "subject": "S" + s["step_key"],
                          "body": "b"} for s in sequence]}
        written = {v["name"]: v["value"] for v in bisonfactory._variables_for(
            lead, {"client": "productive"}, sequence=sequence)}
        cleared = {v["name"]: v["value"]
                   for v in bisonfactory._stale_clearances(sequence)}
        for position in range(2, len(sequence) + 1):
            name = f"subject_{position}"
            self.assertEqual(written.get(name, ""), "")
        for name, value in written.items():
            if name in cleared:
                self.assertEqual(
                    value, cleared[name],
                    f"{name} is written as {value!r} and cleared to "
                    f"{cleared[name]!r} in the same payload")


    def test_the_comparator_expects_what_the_writer_writes(self):
        """`configdiff` is the activation preflight and mirrors the writer.

        `_expected_lead_variables` reimplements `_variables_for`'s naming and
        its threaded-subject rule. Two implementations of one fact drift, and
        when they drift the campaign is staged correctly and then REFUSED at
        activation for carrying exactly what it was told to carry - which is
        the shape of the bug that put `record_id`/`contact_key`/`client` in
        the diff. Five steps is a length neither has been run at, so they are
        compared here rather than assumed to still agree.

        `_expected_lead_variables` drops empty values by design, so the
        comparison is over the NON-EMPTY entries of each side.
        """
        from src import configdiff

        sequence = bisonfactory._sequence_steps(self.configured,
                                                self.cadence_steps)
        copy = [{"step_key": s["step_key"], "subject": "subject for " + s["step_key"],
                 "body": "body for " + s["step_key"]} for s in sequence]
        lead = {"record_id": "rec", "contact_key": "who", "copy": copy}
        attribution = {"record_id": "rec", "contact_key": "who",
                       "client": "productive"}
        written = {v["name"]: v["value"] for v in bisonfactory._variables_for(
            lead, {"client": "productive"}, sequence=sequence)}
        expected = configdiff._expected_lead_variables(
            copy, sequence, attribution=attribution)
        self.assertEqual({k: v for k, v in written.items() if v},
                         {k: v for k, v in expected.items() if v})


class RungThreeNamesTheClientsProductAndNotOurs(unittest.TestCase):
    """`{our_company}` and `{capability}` resolve from the CLIENT's config.

    Rung 3's job is to name the product and one capability. The trap it was
    written around is that `cadence.TEMPLATES` is shared by every client, so
    a literal product name in there would make one client's rung 3 name
    another client's product. Lane D refused to write it inline for exactly
    that reason and these tests are what keeps the refusal true.
    """

    def setUp(self):
        from src import cadence

        self.cadence = cadence
        self.config = clients.load("productive")

    def test_no_shared_template_hardcodes_the_product_name(self):
        """The name appears in no template body or subject, for any client.

        Asserted over the WHOLE register rather than over rung 3, because the
        next template to name a product is the one nobody reviews.
        """
        name = (self.config.get("product") or {}).get("name")
        self.assertTrue(name, "the client config declares no product.name")
        for key, template in self.cadence.TEMPLATES.items():
            for field, text in template.items():
                self.assertNotIn(
                    name.lower(), str(text).lower(),
                    f"TEMPLATES[{key!r}].{field} hardcodes {name!r}; every "
                    f"other client's copy would then name it too")

    def test_both_variables_resolve_for_every_persona(self):
        """And to the client's own unedited sentence, not a paraphrase.

        EVERY ASSERTION HERE IS AGAINST A NON-EMPTY VALUE FIRST. An earlier
        version compared `words.get("capability")` with
        `capabilities.get(key)` and nothing else, so a persona pointed at a
        capability key that does not exist compared `None` with `None` and
        PASSED - a validator agreeing with itself about a configuration that
        would hold every rung-3 step. Found by pointing a persona at
        `not_a_real_capability` and watching this test stay green.
        """
        product = self.config.get("product") or {}
        capabilities = product.get("capabilities") or {}
        by_persona = product.get(
            self.cadence.CAPABILITY_BY_PERSONA_KEY) or {}
        self.assertTrue(by_persona, "no capability_by_persona configured")
        for persona, raw in by_persona.items():
            keys = raw if isinstance(raw, list) else [raw]
            primary = keys[0]
            self.assertIn(
                primary, capabilities,
                f"persona {persona!r} names capability {primary!r}, which "
                f"product.capabilities does not define")
            words = self.cadence.product_words({"persona": persona},
                                               self.config)
            self.assertTrue(words.get("our_company"))
            self.assertTrue(
                words.get("capability"),
                f"persona {persona!r} resolves no capability sentence")
            self.assertEqual(words["our_company"], product.get("name"))
            self.assertEqual(words["capability"], capabilities[primary])
            order = words.get("capability_order")
            self.assertIsInstance(order, list)
            self.assertEqual(len(order), len(keys))
            for k, sentence in zip(keys, order):
                self.assertEqual(sentence, capabilities[k])

    def test_rung_three_renders_for_every_persona(self):
        """The real template, through the real renderer, with no gap left."""
        for persona in ("economic_buyer", "champion"):
            template = self.cadence.TEMPLATES[f"rung3_{persona}"]
            values = {"first_name": "Ada", "company": "Ninefields",
                      "angle_word": "budget burn"}
            values.update(self.cadence.product_words({"persona": persona},
                                                     self.config))
            out = self.cadence.render(template, values)
            for field, text in out.items():
                self.assertNotIn("{", text, f"{persona}.{field} left a gap")
                self.assertTrue(text.strip())

    def test_an_unresolvable_capability_HOLDS_the_step(self):
        """Fail closed: held, never a paragraph reading ".".

        A persona with no configured capability must make `render` raise, not
        interpolate an empty string. An empty `{capability}` would ship a
        lone full stop to a real person and every readback would agree the
        campaign was correct - which is the blank-render incident exactly.
        """
        words = self.cadence.product_words({"persona": "nobody"}, self.config)
        self.assertNotIn("capability", words)
        values = {"first_name": "Ada", "company": "Ninefields",
                  "angle_word": "budget burn"}
        values.update(words)
        with self.assertRaises(self.cadence.CadenceError):
            self.cadence.render(self.cadence.TEMPLATES["rung3_champion"],
                                values)

    def test_the_capability_map_is_not_nested_in_a_persona(self):
        """Where it lives is load-bearing, not tidiness.

        `web/api.save_persona` rebuilds a persona as exactly `titles`,
        `cap_per_domain` and `angles`. A capability kept inside a persona
        would be dropped the first time somebody edited that persona in the
        product, and the failure would be silent: rung 3 held, the cadence
        quietly one step shorter. `angle_labels` sits client-wide for the
        same reason.
        """
        for persona, block in clients.personas(self.config).items():
            self.assertNotIn(
                self.cadence.CAPABILITY_BY_PERSONA_KEY, block or {},
                f"persona {persona!r} carries the capability map; "
                f"save_persona would drop it")
        self.assertIn(self.cadence.CAPABILITY_BY_PERSONA_KEY,
                      self.config.get("product") or {})


class TheYamlIsTheSourceOfThoseKeys(unittest.TestCase):
    """`clients.load` may overlay defaults, so the file itself is checked too.

    Only for the two facts an overlay could invent: that the steps block
    names these five keys and nothing else, and that the pattern is a list of
    five booleans. Everything else is asserted against the built sequence.
    """

    def test_the_file_declares_exactly_these_five_steps(self):
        path = os.path.join(ROOT, "config", "clients", "productive.yaml")
        with open(path, encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        block = raw["email_sequence"]["steps"]
        self.assertEqual(sorted(block), ["em1", "em2", "em3", "em4", "em5"])
        self.assertEqual([block[k]["order"]
                          for k in ("em1", "em2", "em3", "em4", "em5")],
                         [1, 2, 3, 4, 5])
        pattern = raw["email_sequence"]["thread_reply_pattern"]
        self.assertEqual(len(pattern), 5)
        self.assertTrue(all(isinstance(v, bool) for v in pattern))


if __name__ == "__main__":
    unittest.main()
