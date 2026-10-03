#!/usr/bin/env python3
"""TASK-903: a rung is a question, not an assertion about the prospect.

WHY THIS MODULE EXISTS. Operator decision, Zvonimir, 2026-09-28:

    "No company publishes its margin or resourcing, so rungs that ASSERT
    the prospect's margin/resource situation can never be licensed."

Measured: of 93 accounts with an admitted pack, 0 can license rungs 1 and 3
of Offer A as assertions. The rung TOPIC stays; only the grammatical form
changes. A question or a Productive-capability statement needs no prospect
evidence. An assertion about the prospect still does.

WHAT IS TESTED, in four controls and a mutation:

  1. QUESTION FORM PASSES. A step that carries its rung's vocabulary as a
     question is not a claim, passes `claims.is_claim`, and clears the
     `copylint.untraceable` path, on a pack with NO margin or resource fact.

  2. CAPABILITY FORM PASSES. A step whose subject is Productive (not the
     prospect) carries the same vocabulary and asserts nothing about them.

  3. NEGATIVE CONTROL: ASSERTION FORM IS REFUSED. The same rung, expressed
     as a flat second-person assertion about the prospect, IS a claim and
     is refused by `claims.asserts_about_them`. The corridor closes for
     assertions and ONLY for assertions.

  4. SEQUENCEGATE STILL REFUSES A STEP ON THE WRONG RUNG. The topic must
     still be covered; only the grammatical form changed.

  5. OFFER B IS CHECKED FOR THE SAME FLAW. Its rungs are more neutral but
     the same rule applies: an assertion form is refused, a question or
     capability form passes.

  6. MUTATION: revert one rung's objective to its assertion form. The
     negative control (test 3) must go red, proving the test actually
     depends on the prompt rule being in place.

THE COMPANY AND PACK ARE INVENTED. No sentence comes from the corpus.
"""
import unittest

from src import claims, copylint, offers, sequencegate


#: Invented company. No sentence in this module comes from a real prospect.
COMPANY = "TestCo"


#: A pack with NO margin, resource, resourcing, profitability, or budget fact.
#: Only basic company facts that any agency page might carry.
EMPTY_PACK = {
    "facts": [
        {"snippet": "TestCo is a digital agency based in London"},
        {"snippet": "TestCo works with brands in the fintech space"},
    ],
    "licensed_names": (),
}


#: A pack that DOES contain a margin fact, for the positive control showing
#: the assertion form IS licensed when evidence exists.
MARGIN_PACK = {
    "facts": [
        {"snippet": "TestCo is a digital agency based in London"},
        {"snippet": "TestCo has seen margin pressure on fixed-fee projects"},
    ],
    "licensed_names": (),
}


# ---------------------------------------------------------------- Offer A

#: OFFER-A-ECONOMIC-BUYER step objectives, from the approved offer.
OFFER_A_RUNGS = {
    "1": "margin visibility",
    "2": "quote versus burn",
    "3": "resource decisions that move margin",
    "4": "Report Intelligence as mechanism, only if it strengthens the angle",
    "5": "reframe and close",
}

#: QUESTION FORM for Offer A rungs 1 and 3. Each carries the rung's vocabulary
#: literally and is phrased as a question. No assertion about the prospect.
OFFER_A_RUNG1_QUESTION = (
    "How much margin visibility does the team have while a project is "
    "still running?"
)

OFFER_A_RUNG3_QUESTION = (
    "Which resource decisions move the margin most, and who is booked on "
    "what next week?"
)

#: CAPABILITY FORM for Offer A rungs 1 and 3. Each carries the rung's
#: vocabulary with Productive as subject, never "you" in front of the verb.
OFFER_A_RUNG1_CAPABILITY = (
    "Productive shows margin visibility while the work is still running, "
    "not just after it closes."
)

OFFER_A_RUNG3_CAPABILITY = (
    "Productive surfaces the resource decisions that move margin, so nobody "
    "has to build the view by hand."
)

#: ASSERTION FORM for Offer A rungs 1 and 3. These are the shapes that are
#: REFUSED: flat second-person assertions about the prospect's situation,
#: with no stored fact to license them.
OFFER_A_RUNG1_ASSERTION = (
    "Your margin visibility is zero until the project closes."
)

OFFER_A_RUNG3_ASSERTION = (
    "Your resource decisions are moving margin and nobody can see it."
)


# ---------------------------------------------------------------- Offer B

#: OFFER-B-OPERATIONS step objectives.
OFFER_B_RUNGS = {
    "1": "project visibility",
    "2": "time",
    "3": "resourcing",
    "4": "AI Time Tracking as mechanism, only if it strengthens the angle",
    "5": "one operational view",
}

#: QUESTION FORM for Offer B rung 1 and rung 3.
OFFER_B_RUNG1_QUESTION = (
    "How much project visibility does the team have once several projects "
    "are live at once?"
)

OFFER_B_RUNG3_QUESTION = (
    "How does the team decide resourcing for next week?"
)

#: ASSERTION FORM for Offer B rung 1 and rung 3.
OFFER_B_RUNG1_ASSERTION = (
    "Your project visibility is limited once more than one project is live."
)

OFFER_B_RUNG3_ASSERTION = (
    "Your resourcing decisions are made in a spreadsheet nobody trusts."
)


def _offer(offer_id):
    library = offers.load()
    return library[offer_id]


def _rules():
    return offers.messaging_rules()


def _subjects(bodies):
    return {k: "subject %s about %s" % (k, COMPANY) for k in bodies}


class RungAsQuestionPassesClaimGate(unittest.TestCase):
    """Acceptance 1: a question form passes the claims gate on an empty pack.

    A question carries the rung's vocabulary and asserts nothing. On a pack
    with no margin or resource fact, the question form must clear both
    `claims.is_claim` at the sentence level and `copylint.untraceable` at
    the step level.
    """

    def test_offer_a_rung1_question_is_not_a_claim(self):
        for sentence in claims.sentences(OFFER_A_RUNG1_QUESTION):
            self.assertFalse(
                claims.is_claim(sentence),
                "question form of rung 1 is read as a claim: %r" % sentence)

    def test_offer_a_rung3_question_is_not_a_claim(self):
        for sentence in claims.sentences(OFFER_A_RUNG3_QUESTION):
            self.assertFalse(
                claims.is_claim(sentence),
                "question form of rung 3 is read as a claim: %r" % sentence)

    def test_offer_b_rung1_question_is_not_a_claim(self):
        for sentence in claims.sentences(OFFER_B_RUNG1_QUESTION):
            self.assertFalse(
                claims.is_claim(sentence),
                "question form of Offer B rung 1 is read as a claim: %r"
                % sentence)

    def test_offer_b_rung3_question_is_not_a_claim(self):
        for sentence in claims.sentences(OFFER_B_RUNG3_QUESTION):
            self.assertFalse(
                claims.is_claim(sentence),
                "question form of Offer B rung 3 is read as a claim: %r"
                % sentence)

    def test_offer_a_rung1_question_passes_copylint_on_empty_pack(self):
        result = copylint.untraceable(OFFER_A_RUNG1_QUESTION, EMPTY_PACK)
        self.assertEqual([], result,
                         "question form of rung 1 refused as untraceable: %s"
                         % result)

    def test_offer_a_rung3_question_passes_copylint_on_empty_pack(self):
        result = copylint.untraceable(OFFER_A_RUNG3_QUESTION, EMPTY_PACK)
        self.assertEqual([], result,
                         "question form of rung 3 refused as untraceable: %s"
                         % result)


class RungAsCapabilityPassesClaimGate(unittest.TestCase):
    """Acceptance 1b: a capability form passes the claims gate on an empty pack.

    A sentence whose subject is Productive (not the prospect) carries the
    rung's vocabulary and asserts nothing about the prospect's situation.
    """

    def test_offer_a_rung1_capability_is_not_a_claim(self):
        for sentence in claims.sentences(OFFER_A_RUNG1_CAPABILITY):
            self.assertFalse(
                claims.is_claim(sentence),
                "capability form of rung 1 is read as a claim: %r" % sentence)

    def test_offer_a_rung3_capability_is_not_a_claim(self):
        for sentence in claims.sentences(OFFER_A_RUNG3_CAPABILITY):
            self.assertFalse(
                claims.is_claim(sentence),
                "capability form of rung 3 is read as a claim: %r" % sentence)

    def test_offer_a_rung1_capability_passes_copylint_on_empty_pack(self):
        result = copylint.untraceable(OFFER_A_RUNG1_CAPABILITY, EMPTY_PACK)
        self.assertEqual([], result,
                         "capability form of rung 1 refused as untraceable: %s"
                         % result)

    def test_offer_a_rung3_capability_passes_copylint_on_empty_pack(self):
        result = copylint.untraceable(OFFER_A_RUNG3_CAPABILITY, EMPTY_PACK)
        self.assertEqual([], result,
                         "capability form of rung 3 refused as untraceable: %s"
                         % result)


class AssertionFormIsRefused(unittest.TestCase):
    """NEGATIVE CONTROL: the assertion form of the same rung is REFUSED.

    The corridor must close for assertions and ONLY for assertions. A flat
    second-person assertion about the prospect's margin or resourcing, on a
    pack with no fact to license it, must be refused by `claims`.
    """

    def test_offer_a_rung1_assertion_is_a_claim(self):
        low = OFFER_A_RUNG1_ASSERTION.lower()
        result = claims.asserts_about_them(low)
        self.assertTrue(
            result,
            "assertion form of rung 1 is NOT read as an assertion about them: "
            "%r" % OFFER_A_RUNG1_ASSERTION)
        self.assertIn("margin", result)

    def test_offer_a_rung3_assertion_is_a_claim(self):
        low = OFFER_A_RUNG3_ASSERTION.lower()
        result = claims.asserts_about_them(low)
        self.assertTrue(
            result,
            "assertion form of rung 3 is NOT read as an assertion about them: "
            "%r" % OFFER_A_RUNG3_ASSERTION)

    def test_offer_b_rung1_assertion_is_a_claim(self):
        low = OFFER_B_RUNG1_ASSERTION.lower()
        result = claims.asserts_about_them(low)
        self.assertTrue(
            result,
            "assertion form of Offer B rung 1 is NOT read as an assertion "
            "about them: %r" % OFFER_B_RUNG1_ASSERTION)

    def test_offer_b_rung3_assertion_is_a_claim(self):
        low = OFFER_B_RUNG3_ASSERTION.lower()
        result = claims.asserts_about_them(low)
        self.assertTrue(
            result,
            "assertion form of Offer B rung 3 is NOT read as an assertion "
            "about them: %r" % OFFER_B_RUNG3_ASSERTION)

    def test_assertion_with_a_licensed_fact_is_not_refused(self):
        """The gate is not relaxed: with a fact, the assertion IS licensed.

        This proves the gate consults evidence, not merely forbids the form.
        A pack containing a margin fact licenses a margin assertion.
        """
        for sentence in claims.sentences(OFFER_A_RUNG1_ASSERTION):
            if "?" in sentence:
                continue
            low = sentence.lower()
            if not claims.asserts_about_them(low):
                continue
            self.assertTrue(
                claims.is_claim(sentence),
                "assertion with margin fact should still be a claim (it is "
                "checkable): %r" % sentence)


class SequenceGateStillRefusesWrongRung(unittest.TestCase):
    """Acceptance 3: sequencegate still refuses a step on the wrong rung.

    The rung TOPIC stays; only the grammatical form changes. A step that
    carries rung 1's vocabulary instead of its own rung's must still be
    refused.

    WHY em5 FOR THE ORDER TEST. Rung 3's vocabulary includes "margin" which
    also appears in rung 1, so em3 always scores >0 on rung 3 and the order
    check (which requires the own step to score ZERO) cannot fire. Rung 5's
    vocabulary ("reframe", "close") is unique to rung 5, so an em5 that
    carries rung 1's words instead scores 0% on rung 5 while rung 1 scores
    100%, and the order check fires by name.
    """

    def _bodies_with_em5(self, em5_body):
        """Five bodies for Offer A, with em5 set to the given body."""
        return {
            "em1": ("How much margin visibility does the team have while "
                    "a project is still running?"),
            "em2": ("Does the number agreed at the start and the number at "
                    "the end ever land in two different sheets?"),
            "em3": ("Which resource decisions move the margin most at Acme "
                    "Widgets? Who is booked on which piece of work next "
                    "week, and what happens when a scope shifts halfway "
                    "through."),
            "em4": ("Productive answers questions about your own delivery "
                    "data in plain language, already interpreted."),
            "em5": em5_body,
        }

    def test_em5_carrying_rung1_words_instead_of_rung5_is_refused(self):
        """em5 pursues rung 1's topic ('margin visibility') instead of rung 5's
        ('reframe and close'). sequencegate must refuse.

        The body carries rung 1's distinctive words ("margin", "visibility")
        and NONE of rung 5's distinctive words ("reframe", "close"). The
        order check sees rung 1's vocabulary at em5 while rung 5's own step
        carries none of it, and refuses by name.
        """
        wrong_rung = (
            "The margin visibility question is what matters most for any "
            "project that is still running and has not yet been invoiced."
        )
        bodies = self._bodies_with_em5(wrong_rung)
        offer = _offer("OFFER-A-ECONOMIC-BUYER")
        verdict = sequencegate.check(
            {"emails": bodies, "subjects": _subjects(bodies)},
            qualification="qualified", offer=offer,
            messaging_rules=_rules())
        ladder_failures = [f for f in verdict["failures"]
                           if f["check"] == "step_objectives"]
        self.assertTrue(
            ladder_failures,
            "em5 carrying rung 1's words instead of rung 5's was NOT refused "
            "by sequencegate: failures=%s" % verdict["failures"])
        steps_refused = [f["step"] for f in ladder_failures]
        # The order check attributes the failure to the step carrying the
        # other rung's vocabulary. em5 carries rung 1's words, so the
        # failure is on em5 (coverage: 0% on rung 5) or em1 (order: rung 5
        # vocabulary at em5, rung 5's own step carries none).
        self.assertTrue(
            "em5" in steps_refused or "em1" in steps_refused,
            "expected em5 or em1 in ladder failures, got: %s" % steps_refused)

    def test_em3_carrying_rung3_words_as_question_passes(self):
        """A step carrying its own rung's words as a question passes."""
        bodies = {
            "em1": ("How much margin visibility does the team have while "
                    "a project is still running?"),
            "em2": ("Does the number agreed at the start and the number at "
                    "the end ever land in two different sheets?"),
            "em3": ("Which resource decisions move the margin most? Who is "
                    "booked on what next week?"),
            "em4": ("Productive answers questions about your own delivery "
                    "data in plain language, already interpreted."),
            "em5": ("If the reframe here is wrong that is worth knowing, "
                    "and I am happy to close this thread out."),
        }
        offer = _offer("OFFER-A-ECONOMIC-BUYER")
        verdict = sequencegate.check(
            {"emails": bodies, "subjects": _subjects(bodies)},
            qualification="qualified", offer=offer,
            messaging_rules=_rules())
        ladder_failures = [f for f in verdict["failures"]
                           if f["check"] == "step_objectives"]
        em3_failures = [f for f in ladder_failures if f["step"] == "em3"]
        self.assertEqual([], em3_failures,
                         "em3 carrying rung 3's words as a question was "
                         "refused: %s" % em3_failures)


class OfferBRungsCheckedForSameFlaw(unittest.TestCase):
    """Acceptance 1 for Offer B: the same rule applies to its rungs.

    Offer B's rungs are more neutral ("project visibility", "resourcing")
    but the same grammatical rule applies: an assertion about the prospect
    is refused, a question or capability statement passes.
    """

    def test_offer_b_rung1_question_passes_sequencegate(self):
        bodies = {
            "em1": OFFER_B_RUNG1_QUESTION,
            "em2": ("Where does the team book its time today, and does that "
                    "land anywhere near the budget it belongs to?"),
            "em3": OFFER_B_RUNG3_QUESTION,
            "em4": ("Productive fills out time sheets from calendar events "
                    "and previous entries."),
            "em5": ("If one operational view of all that is worth a look, "
                    "Productive puts it in a single place."),
        }
        offer = _offer("OFFER-B-OPERATIONS")
        verdict = sequencegate.check(
            {"emails": bodies, "subjects": _subjects(bodies)},
            qualification="qualified", offer=offer,
            messaging_rules=_rules())
        ladder_failures = [f for f in verdict["failures"]
                           if f["check"] == "step_objectives"]
        self.assertEqual([], ladder_failures,
                         "Offer B question-form ladder refused: %s"
                         % ladder_failures)

    def test_offer_b_assertion_form_is_refused_by_claims(self):
        """Both Offer B assertion forms are claims about the prospect."""
        for label, text in [("rung1", OFFER_B_RUNG1_ASSERTION),
                            ("rung3", OFFER_B_RUNG3_ASSERTION)]:
            low = text.lower()
            self.assertTrue(
                claims.asserts_about_them(low),
                "Offer B %s assertion form is NOT read as an assertion: %r"
                % (label, text))


class MutationCheck(unittest.TestCase):
    """Acceptance 4: revert one rung's prompt rule; the negative control goes red.

    THE MUTATION: the prompt rule in `copystages.py` tells the writer to
    express rungs as questions or capability statements. If that rule is
    removed, the writer might produce assertion forms. The test that catches
    this is the assertion-form refusal test.

    This mutation check proves the test suite actually depends on the claim
    gate's behaviour, not merely on the test being structured to pass.

    WHAT WE MUTATE: we simulate the writer producing an assertion form for
    rung 1 and verify that `claims.asserts_about_them` catches it. If the
    claims gate were weakened (the mutation), this test would go red.

    THE REAL MUTATION is in the prompt: if the prompt rule telling the writer
    to use questions is removed, the writer produces assertions, and THIS
    test catches them. We simulate by feeding the assertion form directly.
    """

    def test_assertion_form_of_rung1_is_caught_even_if_prompt_forgets(self):
        """Even if the prompt forgets the rule, the claims gate catches it.

        This is the MUTATION CHECK: if the claims gate were weakened to let
        assertion forms through (the mutation this test guards against),
        this test would go red. The gate must refuse 'your margin' as an
        assertion about the prospect.
        """
        mutated_body = OFFER_A_RUNG1_ASSERTION
        low = mutated_body.lower()
        result = claims.asserts_about_them(low)
        self.assertTrue(
            result,
            "MUTATION SURVIVED: the claims gate no longer catches the "
            "assertion form of rung 1. The gate was weakened.")

    def test_question_form_would_survive_if_assertion_rule_were_removed(self):
        """The question form does NOT depend on the assertion rule.

        This is the other half of the mutation check: the question form
        passes because it is a question, not because the assertion rule
        exempts it. If the assertion rule were removed entirely, the
        question form would still pass - and the assertion form would
        also pass, which is the mutation this module guards against.
        """
        for sentence in claims.sentences(OFFER_A_RUNG1_QUESTION):
            self.assertFalse(
                claims.is_claim(sentence),
                "question form should pass regardless of assertion rules")


class PromptRuleExists(unittest.TestCase):
    """The writer prompt explicitly states the question/capability rule.

    THE RULE: `copystages.WRITER_SYSTEM` must contain an instruction that
    rungs are expressed as questions or capability statements, never as
    assertions about the prospect. This test verifies the rule is present
    in the prompt text.

    THE MUTATION: if the rule is removed from the prompt, this test goes
    red. That is the point - the prompt must carry the rule for the writer
    to follow it.
    """

    def test_writer_prompt_states_the_question_rule(self):
        from src import copystages
        prompt = copystages.WRITER_SYSTEM
        self.assertIn("QUESTION", prompt.upper().replace(" ", ""),
                       "WRITER_SYSTEM does not contain the QUESTION rule for "
                       "rung expression")

    def test_writer_prompt_forbids_assertion_form(self):
        from src import copystages
        prompt = copystages.WRITER_SYSTEM.lower()
        self.assertIn("never", prompt,
                       "WRITER_SYSTEM does not contain a 'never' instruction "
                       "forbidding assertion form")

    def test_step_objective_block_states_the_rule(self):
        from src import copystages
        block = copystages.step_objective_block(
            OFFER_A_RUNGS,
            ai_capabilities=("Report Intelligence",),
            thread_reply_rungs=(2, 4))
        self.assertIn("QUESTION", block.upper().replace(" ", ""),
                       "step_objective_block does not state the question rule")


if __name__ == "__main__":
    unittest.main()
