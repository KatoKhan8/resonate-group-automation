"""Field-aware routing: an email does not mean the person is done.

THE DEFECT THIS CLOSES. `enrich.usable_contacts` asks "does this contact have
an email", and enrichment used the answer to decide whether ANY person-level
work was still worth doing. So a person with a work address and no LinkedIn
URL read as finished, and `blitz-domain-to-linkedin` - a call whose entire
purpose is "ContactOut gave us the company but not its LinkedIn URL" - could
never be justified, because the condition could not be stated.

That is why `CONTACTOUT_NO_COMPANY_LINKEDIN`, `CONTACTOUT_NO_EMAIL_DOMAIN` and
`CONTACTOUT_INCOMPLETE` were declared reason codes that nothing in `src/` ever
produced. The vocabulary was waiting for a per-field question.

THE SECOND DEFECT, worth as much. The order was declared in
`waterfall.STAGES` and executed by the top-to-bottom position of the
`if ... and spend(...)` statements in `enrich.enrich_record`. Two
representations of one decision, and they disagreed: the table put AI Ark
ahead of Blitz for email discovery. These tests assert the order through
`fieldplan`, which reads the table, so the table is the order rather than a
description of it.
"""
import unittest

from src import enrich, fieldplan, waterfall


def contact(key="c1", email=None, linkedin=None, name="C One"):
    return {"key": key, "name": name, "title": "COO", "email": email,
            "linkedin": linkedin, "email_source": "provider" if email else None,
            "persona": "economic_buyer"}


def record(contacts=None, facts=None, ledger=None):
    return {"id": "rec-1", "lane": "domains", "client": "productive",
            "company": "Example", "domain": "example.test", "state": "queued",
            "contacts": contacts or [], "excluded": [],
            "company_facts": facts or {}, "waterfall": list(ledger or [])}


def row(stage, provider, call):
    return {"stage": stage, "provider": provider, "call": call,
            "expected_cost": enrich.COSTS.get(call, 0), "actual_cost": None,
            "at": "2026-09-08T00:00:00+00:00"}


ASKED_CONTACTOUT = [row(waterfall.PEOPLE_DISCOVERY, "contactout",
                        "decision-makers")]


class AnEmailDoesNotSuppressALinkedInLookup(unittest.TestCase):
    """The headline invariant, in both directions."""

    def test_a_person_with_an_email_and_no_profile_still_needs_a_profile(self):
        c = contact(email="a@example.test", linkedin=None)
        rec = record([c], ledger=ASKED_CONTACTOUT)
        plan = fieldplan.plan_field(rec, "linkedin_url", c)
        self.assertEqual(plan["state"], fieldplan.MISSING_CONFIRMED)
        self.assertTrue(plan["requires_call"])

    def test_and_the_email_itself_is_reported_satisfied(self):
        c = contact(email="a@example.test", linkedin=None)
        rec = record([c], ledger=ASKED_CONTACTOUT)
        plan = fieldplan.plan_field(rec, "work_email", c)
        self.assertEqual(plan["state"], fieldplan.KNOWN)
        self.assertFalse(plan["requires_call"])
        self.assertEqual(plan["reason"], "field already satisfied")
        self.assertEqual(plan["expected_cost"], 0)

    def test_a_profile_does_not_suppress_an_email_lookup(self):
        c = contact(email=None, linkedin="in/someone")
        rec = record([c], ledger=ASKED_CONTACTOUT)
        self.assertTrue(
            fieldplan.plan_field(rec, "work_email", c)["requires_call"])
        self.assertFalse(
            fieldplan.plan_field(rec, "linkedin_url", c)["requires_call"])

    def test_a_person_with_both_needs_nothing(self):
        """Person-level only. The company fields on this fixture are genuinely
        unknown, and `gaps` covers the whole record."""
        c = contact(email="a@example.test", linkedin="in/someone")
        rec = record([c], ledger=ASKED_CONTACTOUT)
        self.assertEqual(
            [p for p in fieldplan.plan_contact(rec, c) if p["requires_call"]],
            [])

    def test_the_old_coarse_gate_would_have_said_finished(self):
        """Anchors the test against the defect rather than against the fix.

        `usable_contacts` returns the person, so every person-level block in
        `enrich_record` was skipped for them - while the profile was missing.
        """
        c = contact(email="a@example.test", linkedin=None)
        rec = record([c], ledger=ASKED_CONTACTOUT)
        self.assertEqual(len(enrich.usable_contacts(rec)), 1)
        self.assertTrue(
            fieldplan.plan_field(rec, "linkedin_url", c)["requires_call"])


class ContactOutIsFirstForEveryField(unittest.TestCase):
    def test_nothing_asked_yet_routes_to_contactout(self):
        c = contact()
        rec = record([c])
        for name in ("work_email", "linkedin_url"):
            with self.subTest(field=name):
                self.assertEqual(
                    fieldplan.plan_field(rec, name, c)["next_provider"],
                    waterfall.CONTACTOUT)

    def test_the_company_fields_route_to_contactout_first_too(self):
        rec = record()
        for name in ("company_linkedin", "email_domain"):
            with self.subTest(field=name):
                self.assertEqual(
                    fieldplan.plan_field(rec, name)["next_provider"],
                    waterfall.CONTACTOUT)

    def test_the_chain_is_the_declared_one(self):
        """Read from `waterfall`, so the table is the order, not a comment."""
        c = contact()
        rec = record([c])
        self.assertEqual(
            fieldplan.plan_field(rec, "linkedin_url", c)["fallback_chain"],
            ["contactout", "blitz", "aiark"])
        self.assertEqual(
            fieldplan.plan_field(rec, "work_email", c)["fallback_chain"],
            ["contactout", "blitz", "aiark"])


class BlitzIsSecondAndAiArkIsThird(unittest.TestCase):
    """The mandated order, asserted through the planner rather than the table.

    Before this, `email_discovery` declared AI Ark ahead of Blitz, so "Blitz
    second where ContactOut missed" was false in the one place it was written
    down.
    """

    def setUp(self):
        self.c = contact()
        self.rec = record([self.c], ledger=ASKED_CONTACTOUT)

    def test_blitz_comes_after_a_contactout_miss(self):
        plan = fieldplan.plan_field(self.rec, "work_email", self.c)
        self.assertEqual(plan["next_provider"], waterfall.BLITZ)
        self.assertEqual(plan["next_call"], "blitz-email")
        self.assertEqual(plan["reason"], enrich.CONTACTOUT_INCOMPLETE)

    def test_blitz_comes_after_a_contactout_miss_for_the_profile_too(self):
        plan = fieldplan.plan_field(self.rec, "linkedin_url", self.c)
        self.assertEqual(plan["next_provider"], waterfall.BLITZ)

    def test_aiark_only_after_blitz_has_also_missed(self):
        self.rec["waterfall"].append(
            row(waterfall.EMAIL_DISCOVERY, "blitz", "blitz-email"))
        plan = fieldplan.plan_field(self.rec, "work_email", self.c)
        self.assertEqual(plan["next_provider"], waterfall.AIARK)

    def test_nothing_is_left_once_every_provider_has_answered(self):
        self.rec["waterfall"] += [
            row(waterfall.EMAIL_DISCOVERY, "blitz", "blitz-email"),
            row(waterfall.PEOPLE_DISCOVERY, "aiark", "aiark-people-search"),
        ]
        plan = fieldplan.plan_field(self.rec, "work_email", self.c)
        self.assertFalse(plan["requires_call"])
        self.assertIn("every provider", plan["reason"])


class MissingEvidenceIsNeverPositiveEvidence(unittest.TestCase):
    """`unknown` and `missing_confirmed` are different facts about a field."""

    def test_nobody_asked_is_unknown(self):
        c = contact()
        self.assertEqual(
            fieldplan.state_of(record([c]), "linkedin_url", c),
            fieldplan.UNKNOWN)

    def test_somebody_asked_and_had_none_is_confirmed_missing(self):
        c = contact()
        rec = record([c], ledger=ASKED_CONTACTOUT)
        self.assertEqual(fieldplan.state_of(rec, "linkedin_url", c),
                         fieldplan.MISSING_CONFIRMED)

    def test_an_empty_string_is_missing_not_known(self):
        c = contact(email="")
        rec = record([c], ledger=ASKED_CONTACTOUT)
        self.assertEqual(fieldplan.state_of(rec, "work_email", c),
                         fieldplan.MISSING_CONFIRMED)


class ACallAnsweringSeveralQuestionsCountsForAllOfThem(unittest.TestCase):
    """`decision-makers` returns name, profile and address in one response.

    `enrich.CALL_STAGE` files it under `people_discovery` alone, so asking
    "has anyone been asked for this person's LinkedIn URL" by matching the
    ledger row's `stage` says no for ever - and the fallback after it would be
    bought against a question ContactOut had already answered. Matched on the
    call instead.
    """

    def test_a_people_discovery_row_satisfies_the_profile_question(self):
        rec = record([contact()], ledger=ASKED_CONTACTOUT)
        self.assertIn("contactout", fieldplan.tried(rec, waterfall.LINKEDIN_URL))

    def test_and_the_address_question(self):
        rec = record([contact()], ledger=ASKED_CONTACTOUT)
        self.assertIn("contactout",
                      fieldplan.tried(rec, waterfall.EMAIL_DISCOVERY))

    def test_so_the_next_step_is_the_fallback_not_the_primary_again(self):
        c = contact()
        rec = record([c], ledger=ASKED_CONTACTOUT)
        self.assertNotEqual(
            fieldplan.plan_field(rec, "linkedin_url", c)["next_provider"],
            waterfall.CONTACTOUT)


class AKnownCompanyFieldIsNotReBought(unittest.TestCase):
    """The measured leak: 25 of 50 records already hold a company LinkedIn.

    `enrich.already_bought` protects a record by asking whether a ledger row
    exists. Forty-seven of the fifty records have no ledger at all, so it had
    nothing to protect them with, and a re-run would buy
    `company-information-from-domain` for records whose company facts were
    already on the record. Asking the field rather than the ledger is the fix.
    """

    def test_a_stored_company_linkedin_needs_no_call(self):
        rec = record(facts={"linkedin": "https://www.linkedin.com/company/x"})
        plan = fieldplan.plan_field(rec, "company_linkedin")
        self.assertEqual(plan["state"], fieldplan.KNOWN)
        self.assertFalse(plan["requires_call"])

    def test_an_absent_company_linkedin_does(self):
        self.assertTrue(
            fieldplan.plan_field(record(facts={"industry": "x"}),
                                 "company_linkedin")["requires_call"])

    def test_the_two_company_fields_route_independently(self):
        """A known LinkedIn URL must not suppress the mail-domain question.

        They share a stage and they are different facts; `email_domain` has
        no ContactOut answer under any spelling, which is the whole reason
        `blitz-linkedin-to-domain` exists.
        """
        rec = record(facts={"linkedin": "https://www.linkedin.com/company/x"},
                     ledger=[row(waterfall.COMPANY_INFO, "contactout",
                                 "company-information-from-domain")])
        self.assertFalse(
            fieldplan.plan_field(rec, "company_linkedin")["requires_call"])
        mail = fieldplan.plan_field(rec, "email_domain")
        self.assertTrue(mail["requires_call"])
        self.assertEqual(mail["next_call"], "blitz-linkedin-to-domain")

    def test_a_fallback_for_another_field_is_walked_past(self):
        """`company_information` holds three Blitz calls for three fields.

        The one whose `requires_reason` this field cannot supply is not a
        refusal - it is somebody else's step. Returning None there made the
        mail domain unroutable.
        """
        rec = record(ledger=[row(waterfall.COMPANY_INFO, "contactout",
                                 "company-information-from-domain")])
        self.assertEqual(
            fieldplan.plan_field(rec, "email_domain")["next_call"],
            "blitz-linkedin-to-domain")
        self.assertEqual(
            fieldplan.plan_field(rec, "company_linkedin")["next_call"],
            "blitz-domain-to-linkedin")


class AFieldNothingStoresIsUnsupported(unittest.TestCase):
    """Not "missing". A call whose answer has nowhere to land is not owed."""

    def test_phone_is_unsupported(self):
        c = contact()
        plan = fieldplan.plan_field(record([c]), "phone", c)
        self.assertEqual(plan["state"], fieldplan.UNSUPPORTED)
        self.assertFalse(plan["requires_call"])
        self.assertEqual(plan["expected_cost"], 0)

    def test_it_never_appears_in_the_gaps(self):
        c = contact()
        self.assertNotIn("phone",
                         [g["field"] for g in fieldplan.gaps(record([c]))])

    def test_an_unknown_field_is_refused_rather_than_guessed(self):
        with self.assertRaises(fieldplan.UnknownField):
            fieldplan.plan_field(record(), "favourite_colour")


class TheForecastIsWhatItWouldActuallyBill(unittest.TestCase):
    """One call answers a stage's question for everybody at the company.

    Charging `decision-makers` once per person per field reported a 50-record
    estate at 382 credits when the real exposure is a fraction of that. A
    forecast that over-reports is not the safe direction - it is the number
    somebody sizes a cap against.
    """

    def test_one_call_is_charged_once_however_many_people_need_it(self):
        people = [contact("a"), contact("b"), contact("c")]
        rec = record(people)
        rows = []
        for c in people:
            rows += fieldplan.plan_contact(rec, c)
        self.assertEqual(fieldplan.cost_of(rows),
                         enrich.COSTS["decision-makers"])

    def test_two_records_are_charged_separately(self):
        a, b = record([contact("a")]), record([contact("b")])
        b["id"] = "rec-2"
        rows = fieldplan.plan_record(a) + fieldplan.plan_record(b)
        self.assertGreater(fieldplan.cost_of(rows),
                           fieldplan.cost_of(fieldplan.plan_record(a)))


class PlanningIsPure(unittest.TestCase):
    """No provider, no record write. The precedent is `TestPlanIsPure`."""

    def test_planning_does_not_change_the_record(self):
        import copy
        c = contact(email="a@example.test")
        rec = record([c], facts={"industry": "x"}, ledger=ASKED_CONTACTOUT)
        before = copy.deepcopy(rec)
        fieldplan.plan_record(rec)
        fieldplan.gaps(rec)
        self.assertEqual(rec, before)

    def test_it_holds_no_transport(self):
        import src.fieldplan as module
        self.assertFalse(hasattr(module, "requests"))
        self.assertFalse(hasattr(module, "urllib"))


if __name__ == "__main__":
    unittest.main()


class TheForecastAndTheRunAskOneQuestion(unittest.TestCase):
    """`enrich.plan` and `enrich_record` must agree about the field gate.

    They are the two halves the repository has already been bitten by twice -
    `verification.plan` against `verification.verify`, and `enrich.plan`
    against `enrich_record` - so the gate is one predicate called from both
    rather than two that happen to agree today.
    """

    def _company_info_ops(self, rec):
        return [o for o in enrich.plan(rec)
                if o["call"] == "company-information-from-domain"]

    def test_a_record_with_known_company_facts_is_forecast_at_nothing(self):
        rec = record(facts={"linkedin": "https://www.linkedin.com/company/x",
                            "industry": "Marketing", "employees": 25})
        self.assertFalse(fieldplan.company_info_is_owed(rec))
        self.assertEqual(self._company_info_ops(rec), [])

    def test_a_record_with_no_company_facts_is_forecast_and_owed(self):
        rec = record()
        self.assertTrue(fieldplan.company_info_is_owed(rec))
        self.assertTrue(self._company_info_ops(rec))

    def test_the_forecast_never_promises_a_call_the_gate_would_refuse(self):
        """The property, over every combination of the facts that matter."""
        for linkedin in (None, "https://www.linkedin.com/company/x"):
            for industry in (None, "Marketing"):
                for employees in (None, 25):
                    facts = {k: v for k, v in
                             (("linkedin", linkedin), ("industry", industry),
                              ("employees", employees)) if v}
                    rec = record(facts=facts)
                    with self.subTest(facts=facts):
                        forecast = bool(self._company_info_ops(rec))
                        owed = fieldplan.company_info_is_owed(rec)
                        self.assertEqual(forecast, owed)

    def test_a_mail_domain_alone_never_licenses_the_purchase(self):
        """The bug the `filled_by` split closes.

        ContactOut returns no mail domain under any spelling, so a predicate
        over every company field found `email_domain` permanently UNKNOWN and
        bought `company-information-from-domain` on every run, for ever.
        """
        rec = record(facts={"linkedin": "https://www.linkedin.com/company/x",
                            "industry": "Marketing", "employees": 25})
        self.assertEqual(fieldplan.state_of(rec, "email_domain"),
                         fieldplan.UNKNOWN)
        self.assertFalse(fieldplan.company_info_is_owed(rec))
