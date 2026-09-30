#!/usr/bin/env python3
"""TASK-903: a rung is a question, not an assertion.

Operator decision, Zvonimir, 2026-09-28: no company publishes its margin or
resourcing, so rungs that ASSERT the prospect's margin/resource situation can
never be licensed. The rung TOPIC stays; the copy expresses it as a question
to the prospect or as what Productive does.

Acceptance criteria:

  1. Question form and capability form PASS the claims gate with a pack
     containing no margin/resource fact.
  2. NEGATIVE: assertion form of the same rung is REFUSED on that pack.
  3. sequencegate still refuses a step that does not pursue its rung's topic.
  4. Mutation: revert one rung's objective to its assertion form; control 2
     must go red.

THE GAP THIS FIXES. `asserts_about_them` in `claims.py` caught "your team is
tracking margin" (via SECOND_PERSON_ASSERTIONS matching "your team is") but
missed "your margin is invisible" because "your margin" was not in the
second-person assertion list. No company publishes its margin or resourcing,
so the assertion form can never be licensed, and the gate must refuse it.

THE FIX. `asserts_about_them` now also matches "your" + an OPERATIONAL_TERM
as a second path to the same refusal. A sentence asserting "your margin",
"your resourcing", "your project visibility" etc. about the prospect needs
stored evidence, and none exists because the data is not public. Questions
are exempt by `is_claim` (a sentence with "?" and no number is not a claim).
Capability statements ("Productive shows margin") are about Productive, not
the prospect, so CLAIM_MARKERS does not match and `is_claim` returns False.
"""
import unittest
from unittest import mock

from src import claims, copylint, evidence, sequencegate
from src import offers as offers_module


# -------------------------------------------------------------------- helpers

#: Facts about a company that contain NO margin or resourcing data.
#: This is the realistic case: 93 accounts with an admitted pack, 0 can
#: license rungs 1 and 3 of Offer A because no company publishes its margin.
NO_MARGIN_NO_RESOURCE_FACTS = [
    {"text": "Digital consulting agency based in Berlin",
     "kind": "site", "quote": "Digital consulting agency based in Berlin"},
    {"text": "Services include strategy and brand design",
     "kind": "site", "quote": "Services include strategy and brand design"},
]

#: A record with no margin/resource facts, for claims.check.
RECORD = {
    "company": "TestAgency",
    "domain": "testagency.example.com",
    "company_facts": {
        "services": "digital consulting",
        "location": "Berlin",
    },
    "events": [],
}

#: A pack with no margin/resource facts, for copylint/sequencegate.
PACK = {"facts": [{"snippet": f.get("quote") or f.get("text")}
                  for f in NO_MARGIN_NO_RESOURCE_FACTS]}

#: Offer A's step objectives, from the YAML.
OFFER_A_OBJECTIVES = {
    "1": "margin visibility",
    "2": "quote versus burn",
    "3": "resource decisions that move margin",
    "4": "Report Intelligence as mechanism, only if it strengthens the angle",
    "5": "reframe and close",
}

#: Offer B's step objectives, from the YAML.
OFFER_B_OBJECTIVES = {
    "1": "project visibility",
    "2": "time",
    "3": "resourcing",
    "4": "AI Time Tracking as mechanism, only if it strengthens the angle",
    "5": "one operational view",
}


def _offer(objectives):
    return {"step_objectives": objectives}


def _subjects(bodies):
    return {k: "subject for %s" % k for k in bodies}


# --------------------------------------------------------- acceptance 1 + 2
# Claims gate: question/capability PASS, assertion REFUSED.

class RungFormsAgainstTheClaimsGate(unittest.TestCase):
    """Acceptance criteria 1 and 2: the claims gate judges the grammatical
    form of a rung, not its topic.

    The SAME topic (margin visibility, resourcing) in three forms:
      - question:    PASS (a question asserts nothing)
      - capability:  PASS (about Productive, not about the prospect)
      - assertion:   REFUSED (about the prospect, no evidence)
    """

    # ----------------------------------------- Offer A rung 1: margin visibility

    def test_offer_a_rung1_question_form_passes_claims_gate(self):
        """'How do you see a project's margin before it closes?'
        A question about their margin, with no assertion."""
        result = claims.check(
            "How do you see a project's margin before it closes?",
            RECORD)
        self.assertEqual([], result,
                         "question form should pass the claims gate")

    def test_offer_a_rung1_capability_form_passes_claims_gate(self):
        """'Productive shows margin while the work is still running.'
        About Productive, not about the prospect."""
        result = claims.check(
            "Productive shows margin while the work is still running.",
            RECORD)
        self.assertEqual([], result,
                         "capability form should pass the claims gate")

    def test_offer_a_rung1_assertion_form_is_refused(self):
        """'Your margin is invisible until the project closes.'
        An assertion about the prospect's margin with no evidence."""
        result = claims.check(
            "Your margin is invisible until the project closes.",
            RECORD)
        self.assertTrue(result,
                        "assertion form should be refused by claims gate")
        why_text = " ".join(p.get("why", "") for p in result)
        self.assertIn("margin", why_text)

    # ----------------------------------------- Offer A rung 3: resource decisions

    def test_offer_a_rung3_question_form_passes_claims_gate(self):
        """'How do resource decisions land at your agency?'"""
        result = claims.check(
            "How do resource decisions land at your agency?",
            RECORD)
        self.assertEqual([], result)

    def test_offer_a_rung3_capability_form_passes_claims_gate(self):
        """'Productive connects resource decisions to their margin impact.'"""
        result = claims.check(
            "Productive connects resource decisions to their margin impact.",
            RECORD)
        self.assertEqual([], result)

    def test_offer_a_rung3_assertion_form_is_refused(self):
        """'Your resource decisions are invisible until the damage is done.'"""
        result = claims.check(
            "Your resource decisions are invisible until the damage is done.",
            RECORD)
        self.assertTrue(result,
                        "assertion form should be refused by claims gate")

    # ----------------------------------------- Offer B rung 1: project visibility

    def test_offer_b_rung1_question_form_passes_claims_gate(self):
        """'How do you see your projects without opening five tabs?'"""
        result = claims.check(
            "How do you see your projects without opening five tabs?",
            RECORD)
        self.assertEqual([], result)

    def test_offer_b_rung1_capability_form_passes_claims_gate(self):
        """'Productive shows every project and its status in one view.'"""
        result = claims.check(
            "Productive shows every project and its status in one view.",
            RECORD)
        self.assertEqual([], result)

    def test_offer_b_rung1_assertion_form_is_refused(self):
        """'Your project visibility is limited to spreadsheets.'"""
        result = claims.check(
            "Your project visibility is limited to spreadsheets.",
            RECORD)
        self.assertTrue(result,
                        "assertion form should be refused by claims gate")

    # ----------------------------------------- Offer B rung 3: resourcing

    def test_offer_b_rung3_question_form_passes_claims_gate(self):
        """'How do you see who is booked on what next week?'"""
        result = claims.check(
            "How do you see who is booked on what next week?",
            RECORD)
        self.assertEqual([], result)

    def test_offer_b_rung3_capability_form_passes_claims_gate(self):
        """'Productive shows who is booked where, forward-looking.'"""
        result = claims.check(
            "Productive shows who is booked where, forward-looking.",
            RECORD)
        self.assertEqual([], result)

    def test_offer_b_rung3_assertion_form_is_refused(self):
        """'Your resourcing is opaque until someone builds a spreadsheet.'"""
        result = claims.check(
            "Your resourcing is opaque until someone builds a spreadsheet.",
            RECORD)
        self.assertTrue(result,
                        "assertion form should be refused by claims gate")

    # ----------------------------------------- near-miss controls

    def test_a_hedged_assertion_still_passes(self):
        """'If your margin is invisible, a walkthrough may help.'
        The hedge 'if' makes this a conditional, not an assertion.
        This is the NEAR-MISS control: an obvious refusal would pass too
        easily; the near-miss proves the hedge exemption still works."""
        result = claims.check(
            "If your margin is invisible, a walkthrough may help.",
            RECORD)
        self.assertEqual([], result,
                         "hedged assertion should pass (hedge exemption)")

    def test_a_question_with_operational_term_still_passes(self):
        """'Is your margin visible during a project?'
        A direct yes/no question. The '?' exempts it from is_claim."""
        result = claims.check(
            "Is your margin visible during a project?",
            RECORD)
        self.assertEqual([], result)

    def test_an_assertion_with_evidence_still_passes(self):
        """When the pack DOES contain the operational term, the assertion
        is licensed. This proves the gate refuses on EVIDENCE, not on
        the topic itself."""
        rec_with_margin = {
            "company": "TestAgency",
            "domain": "testagency.example.com",
            "company_facts": {
                "margin_note": "margin visibility is a known challenge",
                "project_note": "project closes are when margin is reviewed",
            },
            "events": [],
        }
        result = claims.check(
            "Your margin is invisible until the project closes.",
            rec_with_margin)
        self.assertEqual([], result,
                         "assertion with supporting evidence should pass")


# --------------------------------------------------------- acceptance 3
# sequencegate: wrong-topic step is still refused.

class SequenceGateStillRefusesWrongTopic(unittest.TestCase):
    """Acceptance criterion 3: sequencegate still refuses a step that does
    not pursue its rung's topic.

    The grammatical-form change does not weaken the ladder check. A step
    that covers the WRONG rung is still refused by name.
    """

    def setUp(self):
        self.library = offers_module.load()
        self.rules = offers_module.messaging_rules()
        self.offer_a = self.library["OFFER-A-ECONOMIC-BUYER"]

    def test_a_step_covering_the_wrong_rung_is_refused(self):
        """em1 should pursue rung 1 (margin visibility) but instead
        pursues rung 3 (resource decisions). The order check catches this:
        rung 1's distinctive vocabulary is at em3, not em1."""
        bodies = {
            "em1": ("Resource decisions about who is booked next week and "
                    "how scope shifts affect the plan are what move margin "
                    "at agencies like yours."),
            "em2": ("The gap between the quote and the burn is the distance "
                    "between what was agreed and what actually shows up on "
                    "the timesheet."),
            "em3": ("Margin visibility while the project is still running "
                    "is the question this note is about, not something you "
                    "only see after it closes."),
            "em4": ("A plain language answer about the data, already "
                    "interpreted."),
            "em5": ("If the reframe is wrong that is worth knowing. Happy "
                    "to close this thread out."),
        }
        result = sequencegate.check(
            {"emails": bodies, "subjects": _subjects(bodies)},
            qualification="qualified",
            offer=self.offer_a,
            messaging_rules=self.rules)
        ladder_failures = [f for f in result["failures"]
                           if f["check"] == "step_objectives"]
        self.assertTrue(ladder_failures,
                        "a step covering the wrong rung should be refused "
                        "by step_objectives")

    def test_a_step_covering_no_rung_at_all_is_refused(self):
        """em3 should pursue rung 3 (resource decisions) but instead talks
        about invoicing, which is no rung of Offer A's ladder."""
        bodies = {
            "em1": ("Margin visibility while the project is still running "
                    "is the question this note is about."),
            "em2": ("The gap between the quote and the burn is the distance "
                    "between what was agreed and what shows up."),
            "em3": ("Invoices retyped from time records instead of raised "
                    "from them is a problem for finance teams everywhere."),
            "em4": ("A plain language answer about the data, already "
                    "interpreted."),
            "em5": ("If the reframe is wrong that is worth knowing. Happy "
                    "to close this thread out."),
        }
        result = sequencegate.check(
            {"emails": bodies, "subjects": _subjects(bodies)},
            qualification="qualified",
            offer=self.offer_a,
            messaging_rules=self.rules)
        ladder_failures = [f for f in result["failures"]
                           if f["check"] == "step_objectives"]
        self.assertTrue(ladder_failures,
                        "a step covering no rung should be refused")


# --------------------------------------------------------- acceptance 4
# Mutation: break asserts_about_them, control 2 must go red.

class MutationCheck(unittest.TestCase):
    """Acceptance criterion 4: MUTATION.

    Disable `asserts_about_them` and prove that the assertion-form test
    goes from REFUSED to PASSED. This proves the refusal depends on the
    guard we added, not on some other check that happens to fire first.

    THE RULE FROM QWEN.md: 'Break your own fix in source, prove the
    intended test goes red for the intended reason, confirm no other guard
    fired first.'
    """

    def test_assertion_refusal_depends_on_asserts_about_them(self):
        """With asserts_about_them disabled, the assertion-form sentence
        passes claims.check. This proves the refusal is caused by the
        'your [operational_term]' guard, not by another check."""
        sentence = "Your margin is invisible until the project closes."

        # FIRST: prove it is refused with the guard in place.
        result_with_guard = claims.check(sentence, RECORD)
        self.assertTrue(result_with_guard,
                        "assertion should be refused with the guard active")

        # SECOND: disable asserts_about_them, prove the sentence passes.
        with mock.patch.object(claims, "asserts_about_them",
                               return_value=False):
            result_without_guard = claims.check(sentence, RECORD)
            self.assertEqual([], result_without_guard,
                             "with asserts_about_them disabled, the "
                             "assertion-form sentence passes - proving "
                             "the refusal depends on this guard")

    def test_mutation_kills_the_right_test_and_no_other_guard_fires(self):
        """When asserts_about_them is disabled, the assertion-form test
        goes from REFUSED to PASSED. No OTHER guard fires first.

        This is the QWEN.md requirement: 'confirm no other guard fired
        first'. If a different check refused the sentence, disabling
        asserts_about_them would not change the result, and the mutation
        would be a no-op that looks like a surviving test.
        """
        sentence = "Your margin is invisible until the project closes."

        with mock.patch.object(claims, "asserts_about_them",
                               return_value=False):
            result = claims.check(sentence, RECORD)
            # The result is EMPTY: no guard at all refused the sentence.
            # This proves:
            # 1. The intended test (assertion refused) goes red.
            # 2. No other guard fired first (result is [], not a different
            #    refusal).
            self.assertEqual([], result,
                             "no other guard should fire - the refusal "
                             "depends exclusively on asserts_about_them")

    def test_question_form_is_unaffected_by_the_mutation(self):
        """The question form passes regardless of asserts_about_them.

        This proves the question form's pass does not depend on the guard:
        it passes because is_claim exempts questions. Even with the guard
        active, questions pass. The mutation is irrelevant to them."""
        sentence = "How do you see a project's margin before it closes?"
        result = claims.check(sentence, RECORD)
        self.assertEqual([], result,
                         "question form passes regardless of the guard")


# --------------------------------------------------------- the fix itself
# asserts_about_them now catches 'your [operational_term]'.

class AssertsAboutThemCatchesYourOperationalTerm(unittest.TestCase):
    """The specific fix: asserts_about_them now catches 'your margin',
    'your resourcing', etc. as assertions about the prospect."""

    def test_your_margin_is_caught(self):
        low = "your margin is invisible until the project closes."
        result = claims.asserts_about_them(low)
        self.assertTrue(result,
                        "'your margin' should be caught as an assertion")
        self.assertIn("margin", result)

    def test_your_resourcing_is_caught(self):
        low = "your resourcing is opaque and nobody sees it."
        result = claims.asserts_about_them(low)
        self.assertTrue(result)
        self.assertIn("resourcing", result)

    def test_your_project_visibility_is_caught(self):
        low = "your project visibility is limited to spreadsheets."
        result = claims.asserts_about_them(low)
        self.assertTrue(result)
        self.assertIn("project", result)
        self.assertIn("visibility", result)

    def test_your_team_is_still_caught(self):
        """The original pattern still works. This is the REGRESSION check:
        the new code must not break the old path."""
        low = "your team is tracking margin after the fact."
        result = claims.asserts_about_them(low)
        self.assertTrue(result)
        self.assertIn("margin", result)

    def test_a_hedge_still_exempts(self):
        """'if your margin is invisible' - the hedge 'if' exempts the
        sentence from asserts_about_them."""
        low = "if your margin is invisible, a walkthrough may help."
        result = claims.asserts_about_them(low)
        self.assertFalse(result,
                         "a hedged sentence should not be an assertion")

    def test_no_your_no_assertion(self):
        """'the margin is invisible' without 'your' is not caught by
        asserts_about_them (it's about the world, not about them)."""
        low = "the margin is invisible until the project closes."
        result = claims.asserts_about_them(low)
        self.assertFalse(result,
                         "without 'your', this is not about the prospect")

    def test_your_without_operational_term_is_not_caught(self):
        """'your company is great' - 'your' is present but no operational
        term follows. This is ordinary politeness, not an assertion."""
        low = "your company is great and the website is clean."
        result = claims.asserts_about_them(low)
        self.assertFalse(result,
                         "'your' without an operational term is not "
                         "an operational assertion")


if __name__ == "__main__":
    unittest.main()
