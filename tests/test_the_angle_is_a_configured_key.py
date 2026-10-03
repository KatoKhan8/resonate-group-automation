"""The angle the model picks has to be an angle the client configured.

TWO HALVES OF ONE DEFECT, both measured on 2026-10-01.

THE PROMPT NEVER SHOWED THE LIST. `generate.context_for` set
`block["angles"] = client.get("angles")` and no client config has a top-level
`angles` key - `config/clients/productive.yaml` keeps them under
`personas.<persona>.angles`, which is exactly what `clients.angles_for`
returns. The rendered `persona_angle` prompt therefore ended `"angles": null`
while its own contract told the model the angle "must be one of the angles
configured for that persona", and the model answered
`{"angle": null, "evidence": []}` every time.

NOTHING ENFORCED THE ANSWER. `llm.validate("persona_angle")` checked only that
`evidence` was a non-empty list. Over all 1,584 production records 872
contacts carry an angle and only 83 hold an actual angle KEY: 490 hold
`profitability visible on Monday not two weeks late`, which is the DESCRIPTION
of `economic_buyer.founder`; 297 more hold four other descriptions; one holds
`economic_buyer`, which is a PERSONA; one holds `growth`, which is not a key at
any level. `scratch/measure_angles.py` reproduces the count.

The negative controls are the point of this module. A rule that refused
everything would satisfy (b), (c) and (d) on its own, so
`test_a_configured_angle_with_traceable_evidence_passes` is what makes them
mean anything - and it also proves the production path really passes the
angles, because `check_angle` refuses when they are absent.

THIS MODULE READS THE LIVE CLIENT CONFIG ON PURPOSE. `tests/base.fixture_config`
says a test that IS about the live config should load it and say why: the
assertion here is that the FOUR REAL champion angles and the THREE REAL
economic_buyer angles reach the prompt, and a pinned invention would prove
nothing about the client this runs for. Only the cadence is pinned, which this
module is not about.
"""
import json
import os
import shutil
import tempfile
import unittest

from src import clients, generate, llm, store
from tests.base import (FIXTURES, install_fixture, pin_approved_offer, pin_fixture_clients)

#: The angle the champion persona configures that the fixture contact holds.
CONFIGURED = "finance"

#: What 490 real records hold in `angle` instead of a key: the DESCRIPTION of
#: `economic_buyer.founder`, copied out of the config verbatim.
A_DESCRIPTION = "profitability visible on Monday not two weeks late"

#: What one real record holds: a PERSONA name, not an angle at any level.
A_PERSONA = "economic_buyer"

#: What one real record holds: a word that is not a key anywhere in the config.
NOT_A_KEY = "growth"


class AngleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-angle-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        install_fixture("phase5.jsonl", self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        # Real angles, pinned cadence. See the module docstring.
        self.config = pin_fixture_clients(self, linkedin_connection_note=None)
        pin_approved_offer(self)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self):
        return store.get("meridian")

    def champion(self):
        contact = self.rec()["contacts"][0]
        self.assertEqual(contact["persona"], "champion")
        return contact

    def angles(self, persona="champion"):
        return clients.angles_for(self.config, persona)


class TestThePromptCarriesThePersonasAngles(AngleTest):
    """(a) Asserted on the RENDERED PROMPT, never on the source of the
    function - a test that greps `generate.py` for `angles_for` passes while
    the value reaching the model is still null."""

    def test_a_champion_is_shown_all_four_champion_angles(self):
        prompt = generate.render_prompt(
            "persona_angle", self.rec(), self.champion(), self.config)
        for key in ("finance", "delivery", "operations", "resource_management"):
            self.assertIn(key, prompt, key)
        # The hole itself: the old code rendered the literal `"angles": null`.
        self.assertNotIn('"angles": null', prompt)

    def test_an_economic_buyer_is_shown_the_economic_buyer_angles(self):
        rec = self.rec()
        contact = dict(rec["contacts"][0], persona="economic_buyer",
                       title="Chief Executive Officer")
        rec["contacts"] = [contact]
        prompt = generate.render_prompt("persona_angle", rec, contact,
                                        self.config)
        for key in ("founder", "finance", "operations"):
            self.assertIn(key, prompt, key)
        self.assertNotIn('"angles": null', prompt)

    def test_the_two_personas_are_not_shown_the_same_list(self):
        """`resource_management` is a champion angle and not a buyer one. Shown
        to a CEO it would license copy about who is booked next week."""
        rec = self.rec()
        buyer = dict(rec["contacts"][0], persona="economic_buyer")
        rec["contacts"] = [buyer]
        self.assertNotIn(
            "resource_management",
            generate.render_prompt("persona_angle", rec, buyer, self.config))


class TestAnUnconfiguredAngleIsRefused(AngleTest):
    """(b), (c), (d) - the negative controls."""

    def refusal(self, angle, persona="champion"):
        with self.assertRaises(llm.SchemaError) as e:
            llm.validate("persona_angle",
                         {"angle": angle, "evidence": ["Zagreb HR"]},
                         self.angles(persona))
        return str(e.exception)

    def test_a_word_that_is_no_angle_key_is_refused_and_named(self):
        why = self.refusal(NOT_A_KEY)
        self.assertIn(NOT_A_KEY, why)
        self.assertIn("not a configured angle key", why)

    def test_a_champion_angle_is_refused_for_an_economic_buyer(self):
        """Configured for SOME persona is not configured for THIS one."""
        why = self.refusal("resource_management", persona="economic_buyer")
        self.assertIn("resource_management", why)
        self.assertIn("founder", why)       # names what it would have accepted

    def test_the_description_490_records_hold_is_refused(self):
        why = self.refusal(A_DESCRIPTION, persona="economic_buyer")
        self.assertIn(A_DESCRIPTION, why)
        self.assertIn("not a configured angle key", why)

    def test_a_persona_name_as_the_angle_is_refused(self):
        why = self.refusal(A_PERSONA, persona="economic_buyer")
        self.assertIn(A_PERSONA, why)

    def test_a_null_angle_is_refused(self):
        """What the model actually answered on every attempt."""
        self.assertIn("empty", self.refusal(None))

    def test_angles_that_were_not_supplied_are_a_refusal_not_a_pass(self):
        """ABSENT IS NOT 'ANYTHING GOES'. A caller that cannot say which
        angles are configured gets a refusal, so the old behaviour cannot
        return by somebody forgetting an argument."""
        with self.assertRaises(llm.SchemaError) as e:
            llm.validate("persona_angle",
                         {"angle": CONFIGURED, "evidence": ["Zagreb HR"]})
        self.assertIn("not supplied", str(e.exception))

    def test_a_persona_configuring_no_angles_refuses_every_angle(self):
        """`personas.default_angle` returns None here and lint holds the
        contact. A model's guess must not overrule that."""
        with self.assertRaises(llm.SchemaError) as e:
            llm.validate("persona_angle",
                         {"angle": CONFIGURED, "evidence": ["Zagreb HR"]}, {})
        self.assertIn("configures no angles", str(e.exception))

    def test_the_production_path_refuses_and_stores_nothing(self):
        """The gate is wired into `generate.persona_angle`, not only callable.
        Three bad answers hold the contact rather than storing a description."""
        answer = json.dumps({"angle": A_DESCRIPTION,
                             "evidence": ["Zagreb HR"]})
        rec, contact = self.rec(), None
        contact = rec["contacts"][0]
        with self.assertRaises(llm.SchemaError):
            generate.persona_angle(rec, contact, llm.ScriptedModel(*[answer] * 4))
        self.assertNotEqual(contact.get("angle"), A_DESCRIPTION)
        self.assertNotIn("evidence", rec)


class TestAConfiguredAngleStillPasses(AngleTest):
    """(e) - without this the refusals above could be a rule that refuses
    everything, and the production path could be passing no angles at all."""

    def test_a_configured_key_with_traceable_evidence_validates(self):
        data = llm.validate(
            "persona_angle",
            {"angle": CONFIGURED, "evidence": ["Zagreb HR"]},
            self.angles())
        self.assertEqual(data["angle"], CONFIGURED)

    def test_every_configured_key_for_the_persona_is_accepted(self):
        for key in self.angles():
            data = llm.validate("persona_angle",
                                {"angle": key, "evidence": ["Zagreb HR"]},
                                self.angles())
            self.assertEqual(data["angle"], key)

    def test_the_production_path_stores_the_key_and_its_evidence(self):
        answer = json.dumps({"angle": CONFIGURED, "evidence": ["Zagreb HR"]})
        rec = self.rec()
        contact = rec["contacts"][0]
        generate.persona_angle(rec, contact, llm.ScriptedModel(answer))
        self.assertEqual(contact["angle"], CONFIGURED)
        self.assertEqual(rec["evidence"][lint_key(contact)], ["Zagreb HR"])

    def test_case_is_canonicalised_to_the_configured_key(self):
        """A model answering `Finance` meant the key. Refusing it would buy a
        model call to learn nothing, and what is STORED is the exact key."""
        data = llm.validate("persona_angle",
                            {"angle": " Finance ", "evidence": ["Zagreb HR"]},
                            self.angles())
        self.assertEqual(data["angle"], CONFIGURED)


class TestTheEvidenceGatesSurvive(AngleTest):
    """(f) - the new rule did not displace the ones already there."""

    def test_evidence_must_still_be_a_non_empty_list(self):
        for evidence in ([], "Zagreb HR", None):
            with self.assertRaises(llm.SchemaError) as e:
                llm.validate("persona_angle",
                             {"angle": CONFIGURED, "evidence": evidence},
                             self.angles())
            self.assertIn("non-empty list", str(e.exception), repr(evidence))

    def test_traceable_still_refuses_our_own_config_cited_back_at_us(self):
        """The angle PHRASE is our words about our product, not a fact about
        their company, and `fact_strings` never carried it. Citing it as the
        reason this person gets this angle must stay refused."""
        rec = self.rec()
        phrase = self.angles()[CONFIGURED]
        self.assertFalse(llm.traceable(phrase, llm.fact_strings(rec)))
        with self.assertRaises(llm.SchemaError) as e:
            llm.check_evidence([phrase], rec)
        self.assertIn("not traceable", str(e.exception))

    def test_traceable_still_refuses_an_invented_fact(self):
        rec = self.rec()
        self.assertFalse(
            llm.traceable("Meridian raised a Series B in March",
                          llm.fact_strings(rec)))

    def test_traceable_still_accepts_a_real_fact(self):
        self.assertTrue(llm.traceable("Zagreb HR", llm.fact_strings(self.rec())))

    def test_a_configured_angle_with_invented_evidence_is_still_refused(self):
        """Both gates, on the production path: the angle is right and the
        evidence is not, and the step must not store either."""
        answer = json.dumps({"angle": CONFIGURED,
                             "evidence": ["they are opening an office in Tokyo"]})
        rec = self.rec()
        with self.assertRaises(llm.SchemaError):
            generate.persona_angle(rec, rec["contacts"][0],
                                   llm.ScriptedModel(*[answer] * 4))
        self.assertNotIn("evidence", rec)


def lint_key(contact):
    from src import lint

    return lint.contact_key(contact)


if __name__ == "__main__":
    unittest.main()
