#!/usr/bin/env python3
"""A funnel number that cannot say what it is out of is not a measurement.

`report.funnel` gives raw counts and is right to - it is the campaign screen.
What nothing could answer was "of the two hundred that entered, how many should
have reached here, and where did the rest go", which is the question a
promotion decision actually rests on.

Two failures this module is built not to have:

  - A RATE ACROSS TWO UNITS. The first version divided people by companies and
    printed "people_found 3 of 2 = 150.0%". That is a ratio with two different
    denominators wearing a percent sign, and it is the exact shape of the
    `conversionRate` in a reference implementation that silently fell as its
    corpus grew.
  - MISSING READ AS ZERO. "No campaign has been staged" and "staging is not
    built" are different facts and only one of them is a funnel result.
"""
import unittest

from src import funnel


def rec(rid, **over):
    r = {"id": rid, "client": "productive", "domain": rid + ".test",
         "company": rid.title(), "company_facts": {}, "contacts": [],
         "research": [], "events": [], "log": [], "cadence": {}}
    r.update(over)
    return r


def qualified(rid, contacts=(), **over):
    return rec(rid, company_facts={"name": rid, "employees": 30},
               qualification={"verdict": {
                   "icp_status": "qualified", "icp_confidence": "high",
                   "positive_signals": [{"dimension": "agency_fit"}],
                   "negative_signals": []}},
               contacts=list(contacts), **over)


def person(key, email=None, linkedin=None, confirmations=0):
    return {"key": key, "email": email, "linkedin": linkedin,
            "verification": {"confirmation_count": confirmations}}


def stage(measured, name):
    return next(s for s in measured["stages"] if s["stage"] == name)


class ARateNeverCrossesUnits(unittest.TestCase):

    def test_people_per_company_is_a_ratio_not_a_percentage(self):
        recs = [qualified("acme", [person("a"), person("b"), person("c")]),
                qualified("borealis", [])]
        got = stage(funnel.measure(recs), "people_found")
        self.assertIsNone(got["rate"], "people were divided by companies")
        self.assertEqual(got["per"], 1.5)
        self.assertEqual(got["per_label"], "people per records")

    def test_a_same_unit_transition_does_get_a_rate(self):
        recs = [qualified("acme", [person("a", email="a@acme.test")]),
                qualified("borealis", [person("b")])]
        got = stage(funnel.measure(recs), "emails_found")
        self.assertEqual(got["rate"], 0.5)
        self.assertEqual(got["lost"], 1)

    def test_every_stage_declares_its_unit_and_its_denominator(self):
        """The contract, asserted as a property of the table."""
        for name, of, unit, eligible, truth in funnel.STAGES:
            self.assertIn(unit, (funnel.RECORDS, funnel.PEOPLE, funnel.ACTIONS),
                          name)
            self.assertTrue(eligible and truth, name)
            if of is not None:
                self.assertIn(of, funnel.UNIT_OF, f"{name} names {of}")

    def test_the_entry_stage_has_no_rate_at_all(self):
        got = stage(funnel.measure([rec("acme")]), "input_domains")
        self.assertIsNone(got["rate"])
        self.assertIsNone(got["per"])


class MissingIsNotZero(unittest.TestCase):

    def test_an_unbuilt_stage_reports_missing(self):
        got = stage(funnel.measure([rec("acme")]), "readback_verified")
        self.assertIs(got["count"], funnel.MISSING)

    def test_missing_produces_no_rate_and_no_loss(self):
        got = stage(funnel.measure([rec("acme")]), "meeting")
        self.assertIsNone(got["rate"])
        self.assertIsNone(got["lost"])

    def test_a_built_stage_with_nothing_in_it_reports_zero(self):
        """Zero and MISSING must not be the same cell."""
        got = stage(funnel.measure([rec("acme")]), "qualified")
        self.assertEqual(got["count"], 0)
        self.assertIsNot(got["count"], funnel.MISSING)


class AttritionNamesOneDominantReason(unittest.TestCase):

    def reason(self, record):
        return funnel.attrition([record])["per_record"][record["id"]]

    def test_a_domain_that_returned_nothing(self):
        self.assertEqual(self.reason(rec("dead")), funnel.NO_COMPANY_DATA)

    def test_a_free_headcount_probe_alone_is_not_company_data(self):
        """Every domain gets it, so it cannot mean the lookup succeeded."""
        self.assertEqual(
            self.reason(rec("thin", company_facts={"headcount_signal": 9})),
            funnel.NO_COMPANY_DATA)

    def test_a_correct_rejection_is_good_attrition(self):
        r = rec("tiny", company_facts={"name": "Tiny", "employees": 4},
                qualification={"verdict": {
                    "icp_status": "rejected",
                    "negative_signals": [{"dimension": "employee_count"}],
                    "positive_signals": []}})
        self.assertEqual(self.reason(r), funnel.ICP_REJECT)
        self.assertIn(funnel.ICP_REJECT, funnel.GOOD)

    def test_a_qualified_company_with_nobody_found(self):
        self.assertEqual(self.reason(qualified("acme")), funnel.NO_PERSON)

    def test_the_first_blocker_wins_not_the_last(self):
        """A qualified company with no person is NO_PERSON, not NO_EMAIL.

        Buying an address for somebody nobody found is not the next question,
        and a table that said NO_EMAIL would send the reader to the wrong fix.
        """
        self.assertEqual(self.reason(qualified("acme", [])), funnel.NO_PERSON)

    def test_a_person_with_one_confirmation_is_a_verification_failure(self):
        r = qualified("acme", [person("a", email="a@acme.test",
                                      linkedin="https://x.test/in/a",
                                      confirmations=1)])
        self.assertEqual(self.reason(r), funnel.EMAIL_VERIFY_FAILED)

    def test_a_fully_ready_record_is_ready(self):
        r = qualified("acme", [person("a", email="a@acme.test",
                                      linkedin="https://x.test/in/a",
                                      confirmations=2)])
        self.assertEqual(self.reason(r), funnel.READY)

    def test_good_and_software_partition_the_whole_cohort(self):
        recs = [rec("dead"), qualified("acme"),
                rec("tiny", company_facts={"name": "T", "employees": 4},
                    qualification={"verdict": {"icp_status": "rejected",
                                               "negative_signals": [{}],
                                               "positive_signals": []}})]
        got = funnel.attrition(recs)
        self.assertEqual(sum(got["good"].values())
                         + sum(got["software"].values()), len(recs))
        self.assertEqual(set(got["good"]) & set(got["software"]), set())


if __name__ == "__main__":
    unittest.main()
