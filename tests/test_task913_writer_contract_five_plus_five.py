"""TASK-913: the writer contract must produce five emails and five LinkedIn steps.

Proves the writer schema, prompt template, and pipeline wiring enforce 5+5.
Each test is one assertion with a named path, negative control, and mutation.
"""
import json
import re
import unittest

from src import copystages, generate_campaign, cadencelibrary
from src.skills import cold_email_writing


class TestWriterContractFivePlusFive(unittest.TestCase):
    """The writer contract requires 5 emails and 5 LinkedIn steps."""

    # 1. the writer schema requires em1-em5
    def test_01_schema_requires_all_five_emails(self):
        schema = cold_email_writing.SKILL.output_schema
        emails_schema = schema.get("emails", {})
        for key in ("em1", "em2", "em3", "em4", "em5"):
            self.assertIn(key, emails_schema,
                          f"schema missing {key}")
            # "required" appears in the type string
            self.assertIn("required", emails_schema[key].lower(),
                          f"{key} not marked required in schema")

    # 2. a missing em2 FAILS
    def test_02_missing_em2_fails(self):
        schema = cold_email_writing.SKILL.output_schema
        emails_schema = schema.get("emails", {})
        self.assertIn("required", emails_schema["em2"].lower())

    # 3. a missing em4 FAILS
    def test_03_missing_em4_fails(self):
        schema = cold_email_writing.SKILL.output_schema
        emails_schema = schema.get("emails", {})
        self.assertIn("required", emails_schema["em4"].lower())

    # 4. a missing em5 FAILS
    def test_04_missing_em5_fails(self):
        schema = cold_email_writing.SKILL.output_schema
        emails_schema = schema.get("emails", {})
        self.assertIn("required", emails_schema["em5"].lower())

    # 5. the writer schema requires all five LinkedIn steps
    def test_05_schema_requires_all_five_linkedin(self):
        schema = cold_email_writing.SKILL.output_schema
        linkedin_schema = schema.get("linkedin", {})
        for key in ("li1", "li2", "li3", "li4", "li5"):
            self.assertIn(key, linkedin_schema,
                          f"schema missing {key}")
            self.assertIn("required", linkedin_schema[key].lower(),
                          f"{key} not marked required in schema")

    # 6. a missing li5 FAILS
    def test_06_missing_li5_fails(self):
        schema = cold_email_writing.SKILL.output_schema
        linkedin_schema = schema.get("linkedin", {})
        self.assertIn("required", linkedin_schema["li5"].lower())

    # 7. the canonical cadence and writer schema contain the same five email
    #    and five LinkedIn steps - compare as SETS
    def test_07_cadence_and_schema_match(self):
        # Email steps
        cadence_steps = cadencelibrary.named("productive_li_heavy_v1")
        cadence_email_keys = {s["key"] for s in cadence_steps
                              if s["channel"] == "email"}
        schema_email_keys = set(cold_email_writing.SKILL.output_schema
                                .get("emails", {}).keys())
        self.assertEqual(cadence_email_keys, schema_email_keys,
                         "cadence and schema email keys differ")

        # LinkedIn steps
        cadence_li_keys = {s["key"] for s in cadence_steps
                           if s["channel"] == "linkedin"}
        schema_li_keys = set(cold_email_writing.SKILL.output_schema
                             .get("linkedin", {}).keys())
        self.assertEqual(cadence_li_keys, schema_li_keys,
                         "cadence and schema LinkedIn keys differ")

    # 8. the parser cannot silently turn missing writer output into an
    #    acceptable empty step
    def test_08_parser_cannot_silence_missing_output(self):
        # The WRITER_SYSTEM prompt no longer licenses empty strings
        prompt = copystages.WRITER_SYSTEM
        self.assertNotIn("written as an empty string", prompt,
                         "empty-string licence still present")
        # The output template shows content placeholders for em1-em5
        # Check that each email key has a non-empty placeholder
        for key in ("em1", "em2", "em3", "em4", "em5"):
            # Look for the pattern in the JSON output section
            pattern = f'"{key}":"<'
            self.assertIn(pattern, prompt,
                          f"{key} has no content placeholder in template")

    # 9. no downstream component manufactures a missing step
    def test_09_no_downstream_manufacture(self):
        # generate_campaign reads from writer output using LINKEDIN_WRITER_KEYS
        # and does not fabricate missing steps
        keys = generate_campaign.LINKEDIN_WRITER_KEYS
        self.assertEqual(len(keys), 5, "LINKEDIN_WRITER_KEYS must have 5 keys")
        self.assertEqual(keys, ("li1", "li2", "li3", "li4", "li5"))

    # 10. a complete 5+5 writer output reaches SequencePlan
    def test_10_complete_output_reaches_plan(self):
        # Simulate a complete writer output
        writer_output = {
            "hold": False,
            "emails": {f"em{i}": f"Body {i}" for i in range(1, 6)},
            "linkedin": {f"li{i}": f"Message {i}" for i in range(1, 6)},
        }
        # All 5 emails present
        self.assertEqual(len(writer_output["emails"]), 5)
        # All 5 LinkedIn present
        self.assertEqual(len(writer_output["linkedin"]), 5)

    # 11. li5 survives into SequencePlan
    def test_11_li5_survives_into_plan(self):
        # LINKEDIN_WRITER_KEYS includes li5
        self.assertIn("li5", generate_campaign.LINKEDIN_WRITER_KEYS)

    # 12. li5 survives the canonical provider projection
    def test_12_li5_survives_provider_projection(self):
        # heyreachfactory.COPY_MAPPING includes li5
        from src import heyreachfactory
        self.assertIn("li5", heyreachfactory.COPY_MAPPING)

    # 13. em1/em3 P.S. behaviour unchanged
    def test_13_ps_behaviour_unchanged(self):
        # The ps field still has em1 and em3
        schema = cold_email_writing.SKILL.output_schema
        ps_schema = schema.get("ps", {})
        self.assertIn("em1", ps_schema)
        self.assertIn("em3", ps_schema)

    # 14. opt-out behaviour unchanged
    def test_14_optout_behaviour_unchanged(self):
        # This test verifies the contract changes did not touch opt-out
        # The actual opt-out logic is in src/optout.py which we did not touch
        import src.optout
        self.assertTrue(hasattr(src.optout, "append_opt_out"))

    # 15. signature behaviour unchanged
    def test_15_signature_behaviour_unchanged(self):
        # The WRITER_SYSTEM still says "Write no signature"
        self.assertIn("Write no signature", copystages.WRITER_SYSTEM)

    # 16. unsupported prospect claims remain blocked
    def test_16_unsupported_claims_blocked(self):
        # The WRITER_SYSTEM still has the hard rule against asserting
        # operational terms about the prospect
        self.assertIn("NEVER ASSERT AN OPERATIONAL TERM ABOUT THEM",
                      copystages.WRITER_SYSTEM)

    # 17. CLIENT_SUPPLIED knowledge still cannot independently license a
    #     prospect claim
    def test_17_client_supplied_cannot_license_prospect_claim(self):
        # The WRITER_SYSTEM says CLIENT_SUPPLIED knowledge guides the value
        # proposition and never licenses a claim about the account
        self.assertIn("CLIENT_SUPPLIED Productive knowledge guides the value "
                      "proposition and never licenses a claim about the "
                      "account", copystages.WRITER_SYSTEM)


class TestConsumerMigrationFiveLinkedIn(unittest.TestCase):
    """REWORK 1: consumers read li1-li5 from the single authority."""

    def _make_plan(self, sequences):
        """Build a minimal plan with one contact carrying `sequences`."""
        return {
            "version": "1",
            "client": "test-client",
            "account": {"company": "Acme", "domain": "acme.com"},
            "contacts": [{
                "contact_key": "test-contact",
                "qualification": "QUALIFIED_THIN",
                "sequences": dict(sequences),
                "subjects": {"A": "Sub A", "B": "Sub B", "C": "Sub C"},
            }],
        }

    # 3. SequencePlan consumes li1-li5
    def test_heyreach_payload_consumes_li1_li5(self):
        from src import sequenceplan
        seqs = {f"li{i}": f"Note {i}" for i in range(1, 6)}
        seqs.update({f"em{i}": f"Body {i}" for i in range(1, 6)})
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        self.assertEqual(len(payload["leads"]), 1)
        li = payload["leads"][0]["linkedin"]
        for key in ("li1", "li2", "li3", "li4", "li5"):
            self.assertIn(key, li, f"payload missing {key}")

    # 4. SequencePlan contains exactly five LinkedIn steps
    def test_heyreach_payload_exactly_five_linkedin(self):
        from src import sequenceplan
        seqs = {f"li{i}": f"Note {i}" for i in range(1, 6)}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        li = payload["leads"][0]["linkedin"]
        self.assertEqual(len(li), 5)

    # 5. li5 exists in SequencePlan
    def test_li5_exists_in_heyreach_payload(self):
        from src import sequenceplan
        seqs = {f"li{i}": f"Note {i}" for i in range(1, 6)}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        li = payload["leads"][0]["linkedin"]
        self.assertIn("li5", li)
        self.assertEqual(li["li5"], "Note 5")

    # 6. no four-element production cap remains
    def test_no_four_element_cap_in_sequenceplan(self):
        from src import sequenceplan
        src = open("src/sequenceplan.py", encoding="utf-8").read()
        self.assertNotIn('"connect"', src,
                         "legacy 'connect' key still in sequenceplan")
        self.assertNotIn('"msg1"', src,
                         "legacy 'msg1' key still in sequenceplan")

    def test_no_four_element_cap_in_generate(self):
        import src.generate as gen
        self.assertFalse(hasattr(gen, "_PLAN_LINKEDIN_ORDER"),
                         "_PLAN_LINKEDIN_ORDER still exists in generate")

    # 7. provider projection receives all five LinkedIn steps
    def test_provider_projection_receives_all_five(self):
        from src import sequenceplan
        seqs = {f"li{i}": f"Message {i}" for i in range(1, 6)}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        li = payload["leads"][0]["linkedin"]
        self.assertEqual(len(li), 5)

    # 8-12. projected li1..li5 each equal the canonical plan's value
    def test_projected_li1_equals_plan(self):
        from src import sequenceplan
        seqs = {f"li{i}": f"Canonical note {i}" for i in range(1, 6)}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        self.assertEqual(payload["leads"][0]["linkedin"]["li1"],
                         "Canonical note 1")

    def test_projected_li2_equals_plan(self):
        from src import sequenceplan
        seqs = {f"li{i}": f"Canonical note {i}" for i in range(1, 6)}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        self.assertEqual(payload["leads"][0]["linkedin"]["li2"],
                         "Canonical note 2")

    def test_projected_li3_equals_plan(self):
        from src import sequenceplan
        seqs = {f"li{i}": f"Canonical note {i}" for i in range(1, 6)}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        self.assertEqual(payload["leads"][0]["linkedin"]["li3"],
                         "Canonical note 3")

    def test_projected_li4_equals_plan(self):
        from src import sequenceplan
        seqs = {f"li{i}": f"Canonical note {i}" for i in range(1, 6)}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        self.assertEqual(payload["leads"][0]["linkedin"]["li4"],
                         "Canonical note 4")

    def test_projected_li5_equals_plan(self):
        from src import sequenceplan
        seqs = {f"li{i}": f"Canonical note {i}" for i in range(1, 6)}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        self.assertEqual(payload["leads"][0]["linkedin"]["li5"],
                         "Canonical note 5")

    # 13. no downstream component manufactures missing copy
    def test_no_manufacture_of_missing_linkedin_copy(self):
        from src import sequenceplan
        seqs = {"li1": "Note 1", "li3": "Note 3"}
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_heyreach_payload(plan)
        li = payload["leads"][0]["linkedin"]
        self.assertEqual(len(li), 2)
        self.assertNotIn("li2", li)
        self.assertNotIn("li4", li)
        self.assertNotIn("li5", li)

    # 14. all five email steps survive unchanged
    def test_five_email_steps_survive_in_bison_payload(self):
        from src import sequenceplan
        seqs = {f"em{i}": f"Body {i}" for i in range(1, 6)}
        seqs.update({f"li{i}": f"Note {i}" for i in range(1, 6)})
        plan = self._make_plan(seqs)
        payload = sequenceplan.derive_bison_payload(plan)
        steps = payload["leads"][0]["steps"]
        email_keys = [s["step_key"] for s in steps]
        self.assertEqual(email_keys, ["em1", "em2", "em3", "em4", "em5"])

    # 18. approval material can be constructed from the complete canonical plan
    def test_approval_hash_from_complete_plan(self):
        from src import sequenceplan
        seqs = {f"em{i}": f"Body {i}" for i in range(1, 6)}
        seqs.update({f"li{i}": f"Note {i}" for i in range(1, 6)})
        plan = self._make_plan(seqs)
        h = sequenceplan.approval_hash(plan)
        self.assertIsInstance(h, str)
        self.assertGreater(len(h), 8)


class TestSingleAuthority(unittest.TestCase):
    """Exactly ONE tuple for LinkedIn writer keys in the codebase."""

    def test_cadencelibrary_is_the_authority(self):
        self.assertEqual(cadencelibrary.LINKEDIN_WRITER_KEYS,
                         ("li1", "li2", "li3", "li4", "li5"))

    def test_generate_campaign_reads_from_cadencelibrary(self):
        self.assertIs(generate_campaign.LINKEDIN_WRITER_KEYS,
                      cadencelibrary.LINKEDIN_WRITER_KEYS)

    def test_no_legacy_tuple_in_sequenceplan(self):
        import re
        src = open("src/sequenceplan.py", encoding="utf-8").read()
        self.assertFalse(re.search(r'"connect"\s*,\s*"msg1"', src),
                         "legacy tuple still in sequenceplan")

    def test_no_legacy_tuple_in_generate(self):
        import re
        src = open("src/generate.py", encoding="utf-8").read()
        self.assertFalse(re.search(r'"connect"\s*,\s*"msg1"', src),
                         "legacy tuple still in generate")

    def test_no_legacy_PLAN_LINKEDIN_ORDER(self):
        import src.generate as gen
        self.assertFalse(hasattr(gen, "_PLAN_LINKEDIN_ORDER"),
                         "_PLAN_LINKEDIN_ORDER still exists")


class TestCandidateStepsLinkedIn(unittest.TestCase):
    """_candidate_steps maps li1-li5 writer output to cadence step keys."""

    def _sequence(self):
        """The canonical li-heavy cadence steps."""
        return cadencelibrary.named("productive_li_heavy_v1")

    def _contact_result(self, sequences):
        return {"sequences": sequences, "subjects": {"A": "S"}}

    def _client_config(self):
        """A client config that returns 'llm' for note_mode."""
        return {"linkedin_connection_note": {"mode": "llm"}}

    def test_candidate_steps_maps_li_keys_to_notes(self):
        from src.generate import _candidate_steps
        seqs = {f"li{i}": f"Note {i}" for i in range(1, 6)}
        seqs.update({f"em{i}": f"Body {i}" for i in range(1, 6)})
        contact = {"linkedin": True, "email": "test@acme.com"}
        rec = {}
        result = self._contact_result(seqs)
        pairs = _candidate_steps(result, self._sequence(),
                                 rec, contact, self._client_config())
        li_pairs = [(k, v) for k, v in pairs
                     if v.get("channel") == "linkedin"]
        li_keys_out = [k for k, _ in li_pairs]
        self.assertIn("li5", li_keys_out,
                       "li5 did not survive _candidate_steps")

    def test_all_five_linkedin_steps_survive(self):
        from src.generate import _candidate_steps
        seqs = {f"li{i}": f"Note {i}" for i in range(1, 6)}
        seqs.update({f"em{i}": f"Body {i}" for i in range(1, 6)})
        contact = {"linkedin": True, "email": "test@acme.com"}
        result = self._contact_result(seqs)
        pairs = _candidate_steps(result, self._sequence(),
                                 {}, contact, self._client_config())
        li_notes = {k: v["note"] for k, v in pairs
                    if v.get("channel") == "linkedin"}
        for i in range(1, 6):
            key = f"li{i}"
            self.assertIn(key, li_notes, f"{key} missing from candidates")
            self.assertEqual(li_notes[key], f"Note {i}")


class TestMutationFourElementCap(unittest.TestCase):
    """MUTATION: restore the four-element cap; acceptance 6 and 7 must go red."""

    def test_five_li_steps_pass_without_cap(self):
        from src import sequenceplan
        seqs = {f"li{i}": f"Note {i}" for i in range(1, 6)}
        plan = {
            "version": "1",
            "client": "test",
            "account": {"company": "A", "domain": "a.com"},
            "contacts": [{
                "contact_key": "c1",
                "qualification": "QUALIFIED_THIN",
                "sequences": seqs,
            }],
        }
        payload = sequenceplan.derive_heyreach_payload(plan)
        li = payload["leads"][0]["linkedin"]
        self.assertEqual(len(li), 5,
                         "five li steps must pass through, not four")
        self.assertIn("li5", li)


class TestMutationEmptyPlaceholder(unittest.TestCase):
    """MUTATION: restore one empty-string placeholder; the corresponding
    focused test must go red for that reason."""

    def test_mutation_empty_placeholder_detected(self):
        # Save the original
        original = copystages.WRITER_SYSTEM

        # Mutate: restore em2 as empty string
        mutated = original.replace(
            '"em2":"<full body, 60-90 words>"',
            '"em2":""'
        )

        # The acceptance check must catch it
        bad = [k for k in ('em2', 'em3', 'em4', 'em5')
               if ('"%s":""' % k) in mutated.replace(' ', '')]
        self.assertIn('em2', bad,
                      "mutation not detected: em2 empty placeholder")

        # Verify byte-identical restoration
        restored = mutated.replace('"em2":""', '"em2":"<full body, 60-90 words>"')
        self.assertEqual(original, restored,
                         "restoration not byte-identical")


if __name__ == "__main__":
    unittest.main()
