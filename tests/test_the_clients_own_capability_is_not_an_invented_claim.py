#!/usr/bin/env python3
"""The approved ladder required naming a capability the copy lint refused.

MEASURED 2026-09-30, and it is why no canary could be written.

`copylint.SPECIFIC_RES` treats a capitalised multi-word name as something
"a model invents when it has no pack to lean on". That is right for a
prospect's customer, office or product. It is wrong for the CLIENT's own
capabilities, which are named in the operator-approved offer library, carry
their own licensed `page_text`, and will NEVER appear in the prospect's pack.

    "Report Intelligence answers a question about your own data."
        -> untraceable_company_claim

and Offer A's rung 4 is literally "Report Intelligence as mechanism, only if
it strengthens the angle". So the approved ladder demanded a step that the
approved copy lint refused, on every account, forever. Rachele's `em4` was
refused ten times across two models.

"Productive" alone passed, being a single word, which is why this survived.

THE SECOND HALF OF THE SAME INVESTIGATION. Probing that wall turned up a hole
pointing the other way: a customer outcome credited to a NAMED organisation
cleared BOTH gates.

    "One agency reduced overruns by 20% after switching."   REFUSED
    "Our customers see margin improve within a quarter."    REFUSED
    "Acme Corp cut costs by 30% with Productive."           PASSED
    "We helped Acme Corp cut costs by 30%."                 PASSED

Naming the customer made the claim more believable and less detectable. Both
halves are here because they are one finding: the gates could not tell the
client's licensed name from an invented one, in either direction.
"""
import unittest
from unittest import mock

from src import claims, copylint, offers

LICENSED = ("Report Intelligence", "Project Summary")

PACK = [{"snippet": "AZoNetwork runs email marketing, content and webinar "
                    "services across its network of science sites."}]

OPENER = ("Your site describes AZoNetwork as running email marketing, "
          "content and webinar services across its network.")


def _lead(sentence, licensed=LICENSED):
    pack = {"facts": list(PACK)}
    if licensed is not None:
        pack["licensed_names"] = tuple(licensed)
    return {"id": "ck",
            "steps": ([{"subject": "s1", "body": OPENER + " " + sentence}]
                      + [{"subject": "s%d" % i,
                          "body": "A neutral filler sentence for step %d." % i}
                         for i in range(2, 6)]),
            "ps": {}, "linkedin": {}, "pack": pack}


def _refused(sentence, licensed=LICENSED):
    report = copylint.check_batch([_lead(sentence, licensed)])
    return "ck" in (report["offenders"].get("untraceable_company_claim") or ())


class TheClientsOwnNameIsNotAnInvention(unittest.TestCase):
    def test_the_licensed_capability_passes(self):
        self.assertFalse(
            _refused("Report Intelligence answers a question about your own "
                     "data."),
            "the approved ladder's rung 4 is refused by the approved lint")

    def test_and_is_refused_when_it_is_not_declared(self):
        """THE CONTROL. Without it the test above passes for any sentence."""
        self.assertTrue(
            _refused("Report Intelligence answers a question about your own "
                     "data.", licensed=None),
            "an undeclared capitalised name stopped being a specific")


class NOTHING_ELSE_IS_EXEMPT(unittest.TestCase):
    """The exemption is the declared names and nothing near them."""

    def test_an_undeclared_capitalised_name_is_still_refused(self):
        self.assertTrue(
            _refused("Margin Wizard answers a question about your own data."))

    def test_an_invented_figure_is_still_refused(self):
        self.assertTrue(
            _refused("Your team of 4,200 people runs those campaigns."))

    def test_a_near_miss_on_the_licensed_name_is_still_refused(self):
        """Not a prefix match, not a fuzzy one: the name or nothing."""
        self.assertTrue(
            _refused("Report Intelligence Pro answers a question about your "
                     "own data."),
            "a name that merely contains a licensed one was exempted")


class ANamedCustomerOutcomeIsStillAClaim(unittest.TestCase):
    """The hole the same investigation found, pointing the other way."""

    REC = {"id": "r1", "company": "AZoNetwork", "domain": "azonetwork.com",
           "company_facts": {}, "contacts": [], "research": []}

    def _check(self, text):
        return claims.check(text, self.REC, {"name": "Ian B"})

    def test_a_named_customer_outcome_is_refused(self):
        for text in (
                "Acme Corp cut costs by 30% with Productive.",
                "We helped Acme Corp cut costs by 30%.",
                "Brand IQ reduced overruns after switching to Productive."):
            with self.subTest(text=text):
                self.assertTrue(self._check(text),
                                "a fabricated case study cleared the gate")

    def test_a_capability_description_is_not_an_outcome(self):
        """THE NEGATIVE CONTROL, and the one that matters most here.

        If this goes red the branch is refusing the product description the
        whole offer is built on, and every draft holds.
        """
        for text in (
                "Productive shows margin while the work is still running.",
                "Report Intelligence answers a question about your own data.",
                "Project Summary gives a recap without digging through "
                "updates.",
                "Productive connects budgets, time tracking and resourcing."):
            with self.subTest(text=text):
                self.assertEqual([], self._check(text))

    def test_a_question_is_not_an_outcome(self):
        self.assertEqual(
            [], self._check("How do you see a project's margin before it "
                            "closes?"))

    def test_the_prospects_own_name_is_not_a_third_party(self):
        """Reported by the rules about THEM, never as somebody else's case
        study. A refusal for the wrong reason sends a reviewer to the wrong
        place."""
        self.assertEqual(
            [], claims._named_third_party_outcomes(
                "AZoNetwork improved its margin last year.",
                exclude=claims._prospect_names(self.REC, None)))

    def test_a_single_capitalised_word_is_not_read_as_an_organisation(self):
        """Sentence-initial capitals are not names. This cost eleven false
        refusals on TASK-921's matrices before it was bounded."""
        for text in ("Would better margin visibility improve resource "
                     "decisions?",
                     "Agencies track utilisation."):
            with self.subTest(text=text):
                self.assertEqual(
                    [], claims._named_third_party_outcomes(text))

    def test_the_refusal_is_evidence_sensitive(self):
        """Every rule here disappears when the evidence licenses it. A
        refusal that survives licensed evidence is a vocabulary filter."""
        text = "Acme Corp cut costs by 30% with Productive."
        self.assertTrue(self._check(text))
        with mock.patch.object(offers, "missing", return_value=[]):
            self.assertEqual(
                [], self._check(text),
                "the refusal survived evidence that licenses the claim")


class TheSEQUENCEGateKnowsThemToo(unittest.TestCase):
    """The same exemption, at the other call site.

    `sequencegate` reuses `copylint.untraceable` - deliberately, so there are
    not two definitions of "specific" - but built its own pack with only
    `facts`. So the batch lint learned the client's names and the sequence
    gate did not, and `claims_supported` refused `em4` - THE ONE STEP OFFER
    A'S LADDER REQUIRES NAMING THE CAPABILITY AT. Measured 2026-09-30: ten of
    ten attempts, and the contact's last remaining blocker.
    """

    FACTS = [{"text": "Hook is a creative production agency named Ad Age "
                      "Small Agency of the Year."}]
    EMAILS = {
        "em1": "margin visibility while the work is still running for Hook",
        "em2": "quote versus burn on a project",
        "em3": "resource decisions that move margin",
        "em4": "Report Intelligence answers a question about your own data "
               "without a report being built first",
        "em5": "reframe and close the loop here",
    }

    def _claims_failures(self, emails=None, offer=True):
        from src import offers as offers_mod, sequencegate

        verdict = sequencegate.check(
            {"emails": emails or self.EMAILS}, facts=self.FACTS,
            offer=(offers_mod.load().get("OFFER-A-ECONOMIC-BUYER")
                   if offer else None),
            messaging_rules=offers_mod.messaging_rules())
        return [f.get("step") for f in (verdict.get("failures") or ())
                if f.get("check") == "claims_supported"]

    def test_the_licensed_name_passes_the_sequence_gate(self):
        self.assertEqual([], self._claims_failures(),
                         "the gate refused the rung the ladder requires")

    def test_with_no_offer_there_is_no_exemption(self):
        """THE CONTROL. The names come from the offer or not at all."""
        self.assertEqual(["em4"], self._claims_failures(offer=False))

    def test_an_undeclared_capitalised_name_is_still_refused(self):
        emails = dict(self.EMAILS,
                      em4="Margin Wizard answers a question about your own "
                          "data without a report being built")
        self.assertEqual(["em4"], self._claims_failures(emails))


if __name__ == "__main__":
    unittest.main()
