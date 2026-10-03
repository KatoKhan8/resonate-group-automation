#!/usr/bin/env python3
"""`step_objectives` on em3 and em5 is SATISFIABLE, and that is measured here.

WHY THIS MODULE EXISTS. `step_objectives` on em3 and em5 was the dominant
generation refusal on both canaries, and the standing suspicion was that the
rule is a CONTRADICTION in the spec - that it demands of those two steps
something the rest of the spec forbids, so no copy could ever satisfy both and
the retry loop could only burn attempts. If that were true, loosening the gate
would be the wrong fix and the operator would have to choose between two
authorities.

It is not true, and the proof has to be an EFFECT rather than a sentence. Until
this module existed the claim lived only in a docstring on
`copystages.step_objective_block` ("it IS satisfiable alongside every other
rule"), which is this repository's own worst habit: a measurement recorded in
prose, re-read later as if it were a gate, and never re-run.

WHAT IS ASSERTED, in both directions and for BOTH approved offers:

  - A CONTROL. Five bodies in which every non-reply, non-conditional rung's own
    step carries one word of its own objective pass `sequencegate` OUTRIGHT -
    not merely "no step_objectives failure" but `passed is True`, which is the
    "alongside every other rule" half of the claim.
  - em3 ALONE stripped of its rung's vocabulary is refused, BY NAME, on the
    coverage half - the exact failure text the generation runs recorded.
  - em5 ALONE stripped of its rung's vocabulary is refused, BY NAME, the same
    way. em3 and em5 are asserted SEPARATELY because they are two different
    rungs with two different vocabularies, and one holding while the other
    fails is the whole question.
  - THE COVERAGE AND ORDER HALVES DO NOT FIGHT. A rung's own step carrying one
    of its DISTINCTIVE words satisfies coverage and makes the order half
    structurally unable to fire for that rung, because the order failure
    requires the rung's own step to score ZERO.
  - AND `claims` DOES NOT FORBID WHAT THE LADDER DEMANDS. The sentences that
    carry rung 3's and rung 5's words are not claims about the prospect: a
    question asserts nothing, and a sentence whose subject is Productive
    asserts nothing about them. That is the one collision that could have made
    this a contradiction, and it is measured rather than argued.

THE COPY HERE IS WRITTEN, NOT GENERATED, and the company is obviously invented.
A model's output is not a fixture - it varies between runs, so a test fed with
it cannot tell a changed gate from a changed model - and a fixture copied out of
the real corpus has twice carried a live prospect's name into a commit here.
"""
import unittest

from src import claims, offers, sequencegate

#: Acme Widgets is invented. No sentence in this module comes from the corpus.
COMPANY = "Acme Widgets"

#: OFFER-A-ECONOMIC-BUYER. Rungs 2 and 4 are `thread_reply_rungs`, so only em1,
#: em3 and em5 are required to carry their own vocabulary.
#:
#:   rung 1  "margin visibility"                    em1 carries both words
#:   rung 3  "resource decisions that move margin"   em3 carries three of four
#:   rung 5  "reframe and close"                     em5 carries both
#:
#: Each of the three carries at least one word belonging to NO OTHER rung,
#: which is what takes the order half out of play.
OFFER_A_BODIES = {
    "em1": ("Acme Widgets runs several client projects at once. How much "
            "margin visibility does the team have while a project is still "
            "running, rather than after it has been invoiced?"),
    "em2": ("One follow up on that: does the number agreed at the start and "
            "the number at the end ever land in two different sheets?"),
    "em3": ("Which resource decisions move the number most at Acme Widgets? "
            "Who is booked on which piece of work next week, and what happens "
            "when a scope shifts halfway through."),
    "em4": ("Productive answers questions about your own delivery data in "
            "plain language, already interpreted, instead of a report "
            "somebody has to build first."),
    "em5": ("If the reframe here is wrong for an agency like Acme Widgets "
            "that is worth knowing, and I am happy to close this thread out."),
}

#: OFFER-B-OPERATIONS. It declares NO `thread_reply_rungs`, so every rung but
#: the conditional AI one is required - which is why this offer is measured
#: here rather than assumed to behave like Offer A.
#:
#:   rung 1  "project visibility"   rung 2  "time"   rung 3  "resourcing"
#:   rung 5  "one operational view"
OFFER_B_BODIES = {
    "em1": ("Acme Widgets runs several client projects at once. How much "
            "project visibility does the team have once two or three of them "
            "are live at the same moment?"),
    "em2": ("One follow up: where does the team book its time today, and does "
            "that land anywhere near the budget it belongs to?"),
    "em3": ("How does the team decide resourcing for next week? That is "
            "usually the question a spreadsheet answers worst."),
    "em4": ("Productive fills out time sheets from calendar events and "
            "previous entries, which is where most of the admin goes."),
    "em5": ("If one operational view of all of that is worth a look, "
            "Productive puts it in a single place. If not, happy to leave it "
            "here."),
}

#: The words each stripped step loses. EVERY form of the rung's own vocabulary,
#: because leaving one inflection behind would make the mutant pass and the
#: negative half of this module vacuous.
STRIP = {
    "OFFER-A-ECONOMIC-BUYER": {
        "em3": ("resource", "decisions", "move", "margin"),
        "em5": ("reframe", "close"),
    },
    "OFFER-B-OPERATIONS": {
        "em3": ("resourcing", "resource"),
        "em5": ("operational", "view"),
    },
}

OFFER_IDS = ("OFFER-A-ECONOMIC-BUYER", "OFFER-B-OPERATIONS")

# After TASK-367 the offer records do not carry step_objectives or
# ai_capabilities. These synthetic offers provide the spine data that
# sequencegate reads, matching the approved Offer A and Offer B structure.
_SYNTHETIC_OFFERS = {
    "OFFER-A-ECONOMIC-BUYER": {
        "persona": "economic_buyer",
        "capabilities": ["profitability", "budgeting"],
        "problem": "margin and budget position invisible until a project closes",
        "mechanism": "demo",
        "cta_link": "https://productive.io/get-started/",
        "approval_status": "pending",
        "step_objectives": {
            1: "margin visibility",
            2: "quote versus burn",
            3: "resource decisions that move margin",
            4: "Report Intelligence as mechanism, only if it strengthens the angle",
            5: "reframe and close",
        },
        "thread_reply_rungs": [2, 4],
        "ai_capabilities": {
            "Report Intelligence": {"page_text": "Ask anything about your business data."},
            "Project Summary": {"page_text": "Stay on top of every project."},
        },
    },
    "OFFER-B-OPERATIONS": {
        "persona": "champion",
        "capabilities": ["project_management", "time_tracking", "resource_planning"],
        "problem": "delivery, time and resourcing split across tools that do not talk",
        "mechanism": "free_trial",
        "cta_link": "https://productive.io/get-started/",
        "approval_status": "pending",
        "step_objectives": {
            1: "project visibility",
            2: "time",
            3: "resourcing",
            4: "AI Time Tracking as mechanism, only if it strengthens the angle",
            5: "one operational view",
        },
        "thread_reply_rungs": [],
        "ai_capabilities": {
            "AI Time Tracking": {"page_text": "Productive analyzes calendar events and fills out time sheets.", "lead": True},
            "AI Notetaker": {"page_text": "The Notetaker integrated into your workspace."},
            "Agents": {"page_text": "Your autonomous virtual assistants."},
            "Smart Search": {"page_text": "Use your own words to search."},
            "Smart Filters": {"page_text": "Use natural language prompts."},
        },
    },
}


def subjects_of(bodies):
    """One distinct subject per step, so `no_repetition` is not what fires."""
    return {key: "subject %s about %s" % (key, COMPANY) for key in bodies}


def without(bodies, step, words):
    """`bodies` with ONE step stripped of a list of words. Nothing else moves.

    The assert is not decoration. A mutation that silently changed nothing has
    shipped a green negative test in this repository before.
    """
    out = dict(bodies)
    body = out[step]
    for word in words:
        for form in (word, word.capitalize()):
            body = body.replace(form, "thing")
    assert body != out[step], "the strip changed nothing: the mutant is inert"
    out[step] = body
    return out


class TheLadderIsSatisfiableAtEm3AndEm5(unittest.TestCase):
    """Not a contradiction: copy exists that satisfies the rule and the rest."""

    def setUp(self):
        self.rules = offers.messaging_rules()
        self.offers = dict(_SYNTHETIC_OFFERS)
        self.bodies = {"OFFER-A-ECONOMIC-BUYER": OFFER_A_BODIES,
                       "OFFER-B-OPERATIONS": OFFER_B_BODIES}

    def verdict(self, offer_id, bodies):
        return sequencegate.check(
            {"emails": bodies, "subjects": subjects_of(bodies)},
            qualification="qualified", offer=self.offers[offer_id],
            messaging_rules=self.rules)

    def ladder_failures(self, verdict):
        return [f for f in verdict["failures"]
                if f["check"] == "step_objectives"]

    # THE CONTROL ---------------------------------------------------------
    def test_a_ladder_whose_steps_carry_their_own_words_passes_outright(self):
        """`passed is True`, not merely "no ladder failure".

        The contradiction claim is that `step_objectives` cannot be satisfied
        ALONGSIDE the rest, so the control has to clear the rest too. Any other
        failure here is a real finding, and naming it in the message is what
        makes that finding readable instead of a bare False.
        """
        for offer_id in OFFER_IDS:
            with self.subTest(offer=offer_id):
                verdict = self.verdict(offer_id, self.bodies[offer_id])
                self.assertTrue(
                    verdict["passed"],
                    "%s: a ladder-satisfying sequence was refused by %s"
                    % (offer_id, [(f["check"], f["step"])
                                  for f in verdict["failures"]]))
                self.assertEqual([], self.ladder_failures(verdict))

    # em3, ALONE ----------------------------------------------------------
    def test_em3_stripped_of_its_rung_is_refused_by_name(self):
        for offer_id in OFFER_IDS:
            with self.subTest(offer=offer_id):
                mutant = without(self.bodies[offer_id], "em3",
                                 STRIP[offer_id]["em3"])
                failures = self.ladder_failures(self.verdict(offer_id, mutant))
                self.assertEqual(["em3"], [f["step"] for f in failures])
                self.assertIn("pursues none of the offer's step objectives",
                              failures[0]["why"])

    # em5, ALONE, AND SEPARATELY ------------------------------------------
    def test_em5_stripped_of_its_rung_is_refused_by_name(self):
        for offer_id in OFFER_IDS:
            with self.subTest(offer=offer_id):
                mutant = without(self.bodies[offer_id], "em5",
                                 STRIP[offer_id]["em5"])
                failures = self.ladder_failures(self.verdict(offer_id, mutant))
                self.assertEqual(["em5"], [f["step"] for f in failures])
                self.assertIn("pursues none of the offer's step objectives",
                              failures[0]["why"])

    def test_one_of_them_may_fail_while_the_other_holds(self):
        """Two rungs, two vocabularies, and they are independent.

        The suspicion named em3 and em5 together. A module that only ever
        measured them together could not tell "both are impossible" from "one
        of them was never actually checked".
        """
        for offer_id in OFFER_IDS:
            with self.subTest(offer=offer_id):
                bodies = self.bodies[offer_id]
                em3_only = without(bodies, "em3", STRIP[offer_id]["em3"])
                em5_only = without(bodies, "em5", STRIP[offer_id]["em5"])
                self.assertEqual(
                    ["em3"], [f["step"] for f in
                              self.ladder_failures(
                                  self.verdict(offer_id, em3_only))])
                self.assertEqual(
                    ["em5"], [f["step"] for f in
                              self.ladder_failures(
                                  self.verdict(offer_id, em5_only))])


class TheOrderHalfCannotFireOnItsOwnStep(unittest.TestCase):
    """The two halves of the rule are not in conflict, and this is why.

    The order failure requires the rung's OWN step to score ZERO on the rung's
    distinctive vocabulary. A step carrying one distinctive word scores above
    zero, so satisfying coverage WITH a distinctive word satisfies order for
    that rung by construction.

    A rung with NO distinctive vocabulary is the other case, and it is NOT a
    hole: the gate reports it as indistinguishable and drops it from the order
    half, so there is nothing for copy to satisfy there either. MEASURED on the
    real library: `OFFER-B-OPERATIONS` rung 2 is exactly that case, because
    "time" also appears in rung 4's "AI Time Tracking as mechanism ...". It is
    asserted here rather than described, because a rung that lost its own words
    AND stayed in the order comparison would be unsatisfiable - which is the
    shape the contradiction suspicion was about.
    """

    def required_rungs(self, offer):
        objectives = {str(k): str(v) for k, v in
                      (offer.get("step_objectives") or {}).items()}
        ai_names = [str(n) for n in (offer.get("ai_capabilities") or {})]
        replies = {str(r) for r in (offer.get("thread_reply_rungs") or ())}
        appearances = {}
        for text in objectives.values():
            for stem in sequencegate._stems(text):
                appearances[stem] = appearances.get(stem, 0) + 1
        out = {}
        for rung, text in sorted(objectives.items()):
            if rung in replies or sequencegate._ai_named_in(text, ai_names):
                continue                # held to neither half of the rule
            out[rung] = (text, {s for s in sequencegate._stems(text)
                                if appearances.get(s) == 1})
        return out

    def test_a_rung_is_either_distinguishable_or_reported_as_not(self):
        """No required rung is both ordered and impossible to satisfy."""
        rules = offers.messaging_rules()
        bodies = {"OFFER-A-ECONOMIC-BUYER": OFFER_A_BODIES,
                  "OFFER-B-OPERATIONS": OFFER_B_BODIES}
        for offer_id in OFFER_IDS:
            offer = _SYNTHETIC_OFFERS[offer_id]
            verdict = sequencegate.check(
                {"emails": bodies[offer_id],
                 "subjects": subjects_of(bodies[offer_id])},
                qualification="qualified", offer=offer, messaging_rules=rules)
            unreadable = " ".join(
                w["why"] for w in verdict["warnings"]
                if w["check"] == "step_objectives"
                and "shares every word with another rung" in w["why"])
            for rung, (text, distinctive) in self.required_rungs(offer).items():
                with self.subTest(offer=offer_id, rung=rung):
                    if distinctive:
                        continue        # satisfiable: one word of its own
                    self.assertIn(
                        "rung %s" % rung, unreadable,
                        "%s rung %s (%r) has no word of its own and the gate "
                        "did not report it as indistinguishable, so it is "
                        "ordered against a vocabulary no copy can carry"
                        % (offer_id, rung, text))

    def test_offer_b_rung_2_is_the_measured_indistinguishable_case(self):
        """Pinned, so a change to either rung's words shows up as a diff.

        Not a rule, a FACT about the approved library: "time" is in rung 2 and
        in rung 4, so rung 2 has nothing of its own.
        """
        offer = _SYNTHETIC_OFFERS["OFFER-B-OPERATIONS"]
        self.assertEqual(set(), self.required_rungs(offer)["2"][1])
        self.assertTrue(self.required_rungs(offer)["3"][1])
        self.assertTrue(self.required_rungs(offer)["5"][1])


class ClaimsDoesNotForbidTheWordsTheLadderDemands(unittest.TestCase):
    """The one collision that could have made this a contradiction.

    The ladder's words are operational words, and `claims` refuses an
    operational word asserted about the prospect. Two forms carry the word and
    assert nothing - a question, and a sentence whose subject is Productive -
    and the control copy uses them. Measured through `claims` itself rather
    than through a rule restated here.
    """

    def test_the_sentences_that_carry_rung_3_and_rung_5_are_not_claims(self):
        for bodies in (OFFER_A_BODIES, OFFER_B_BODIES):
            for step in ("em3", "em5"):
                for sentence in claims.sentences(bodies[step]):
                    with self.subTest(step=step, sentence=sentence[:48]):
                        self.assertFalse(
                            claims.is_claim(sentence),
                            "%r is read as a claim about them, so the ladder's "
                            "words could not be written this way" % sentence)
                        self.assertFalse(
                            claims.customer_outcome_claim(sentence),
                            "%r is read as a customer-outcome claim"
                            % sentence)


if __name__ == "__main__":
    unittest.main()
