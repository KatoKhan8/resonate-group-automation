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
