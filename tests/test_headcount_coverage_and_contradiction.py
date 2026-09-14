#!/usr/bin/env python3
"""TASK-037: headcount coverage, contradiction detection, and resolution.

Tests driven through the REAL entry points: `icpstructural.structural` for
the ICP verdict, `headcount.resolve` for the resolved block, and the
300-record estate from `src/companies.py` for coverage measurement.

Not isolated unit tests of headcount internals: the seam was never the risk.
The risk is that a guessed headcount reaches a prospect in a sent email, and
that is a pipeline question, not a function question.
"""
import unittest

from src import clients, companies, headcount, icpstructural, segments


CLIENT_NAME = "productive"
ESTATE_SIZE = 300


def _config():
    return clients.load(CLIENT_NAME)


def _estate(size=ESTATE_SIZE):
    return companies.dataset(size, client=CLIENT_NAME)


def _icp_employee(rec, config=None):
    """The real entry point: the ICP structural verdict for one record."""
    config = config or _config()
    segment = segments.classify(rec, config)
    result = icpstructural.structural(rec, config, segment=segment)
    return result["criteria"]["employees"]


class ContradictionIsDetectedAndRecorded(unittest.TestCase):
    """A contradiction is detected and recorded rather than silently resolved.

    Driven through `headcount.observe` (the real writer) and
    `headcount.resolve` (the real reader), then through
    `icpstructural.structural` (the real consumer).
    """

    def test_two_sources_on_opposite_sides_of_the_floor_are_a_conflict(self):
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 3
        headcount.observe(rec, "blitz-company", value=80, band="51-200",
                          config=_config())
        resolved = headcount.resolve(rec, _config())
        self.assertEqual(resolved["state"], headcount.CONFLICT)
        self.assertTrue(resolved["contradictions"])
        sources = {c["source"] for c in resolved["contradictions"]}
        self.assertIn(headcount.STORED, sources)
        self.assertIn("blitz-company", sources)

    def test_the_conflict_reaches_the_icp_verdict_as_unknown(self):
        """Not resolved silently: the criterion is UNKNOWN, never PASS or FAIL."""
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 3
        headcount.observe(rec, "blitz-company", value=80, band="51-200",
                          config=_config())
        answer = _icp_employee(rec)
        self.assertEqual(answer["status"], icpstructural.UNKNOWN)

    def test_the_conflict_never_becomes_a_pass(self):
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 3
        headcount.observe(rec, "blitz-company", value=80, band="51-200",
                          config=_config())
        answer = _icp_employee(rec)
        self.assertNotIn(answer["status"], icpstructural.PASSING)

    def test_the_conflict_never_becomes_a_fail(self):
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 3
        headcount.observe(rec, "blitz-company", value=80, band="51-200",
                          config=_config())
        answer = _icp_employee(rec)
        self.assertNotEqual(answer["status"], icpstructural.FAIL)

    def test_both_numbers_are_kept_with_who_said_them(self):
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 4
        headcount.observe(rec, "blitz-company", value=200, band="51-200",
                          config=_config())
        block = headcount.block_of(rec)
        sources = {o["source"] for o in block.get("observations", [])}
        self.assertIn(headcount.STORED, sources)
        self.assertIn("blitz-company", sources)


class UnknownStaysUnknownWhenNothingSupportsAValue(unittest.TestCase):
    """An unknown stays unknown. Missing evidence is never positive evidence."""

    def test_no_witness_at_all_is_unestablished(self):
        rec = _estate(1)[0]
        rec["company_facts"].pop("employees", None)
        rec["company_facts"].pop("headcount_signal", None)
        rec["company_facts"].pop("employee_range", None)
        resolved = headcount.resolve(rec, _config())
        self.assertEqual(resolved["state"], headcount.UNESTABLISHED)
        self.assertIsNone(resolved["value"])

    def test_the_icp_criterion_is_unknown_not_fail(self):
        rec = _estate(1)[0]
        rec["company_facts"].pop("employees", None)
        rec["company_facts"].pop("headcount_signal", None)
        rec["company_facts"].pop("employee_range", None)
        answer = _icp_employee(rec)
        self.assertEqual(answer["status"], icpstructural.UNKNOWN)

    def test_a_guessed_headcount_in_a_sent_email_is_worse_than_an_absent_one(self):
        """The personalisation variable rule: no value without coverage."""
        rec = _estate(1)[0]
        rec["company_facts"].pop("employees", None)
        rec["company_facts"].pop("headcount_signal", None)
        resolved = headcount.resolve(rec, _config())
        self.assertIsNone(resolved["value"])
        self.assertEqual(resolved["confidence"], headcount.LOW)


class TheToleranceStillAppliesExactlyAsConfigured(unittest.TestCase):
    """The tolerance is min x (1 - tolerance), derived in one place."""

    def test_the_floor_is_derived_not_hardcoded(self):
        config = _config()
        rules = icpstructural.settings(config)
        self.assertEqual(rules["effective_min_employees"],
                         rules["min_employees"] * (1.0 - rules["employee_tolerance"]))

    def test_within_tolerance_is_pass_with_tolerance(self):
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 15
        answer = _icp_employee(rec)
        self.assertEqual(answer["status"], icpstructural.PASS_WITH_TOLERANCE)

    def test_below_tolerance_is_fail(self):
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 10
        answer = _icp_employee(rec)
        self.assertEqual(answer["status"], icpstructural.FAIL)

    def test_at_minimum_is_pass(self):
        rec = _estate(1)[0]
        config = _config()
        rules = icpstructural.settings(config)
        rec["company_facts"]["employees"] = int(rules["min_employees"])
        answer = _icp_employee(rec, config)
        self.assertEqual(answer["status"], icpstructural.PASS)


class RevenueContradictionTestedWithTheMotivatingRecord(unittest.TestCase):
    """A reconciliation that would raise a record above the floor.

    The motivating record: a company with stored headcount under the floor
    but revenue of $3M+. The config says this is "a broken estimate, not a
    four-person agency".
    """

    def test_revenue_contradicts_a_small_headcount_to_unknown(self):
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 4
        rec["company_facts"]["revenue"] = "$172.7M"
        answer = _icp_employee(rec)
        self.assertEqual(answer["status"], icpstructural.UNKNOWN)

    def test_revenue_does_not_become_a_pass(self):
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 4
        rec["company_facts"]["revenue"] = "$21.1M"
        answer = _icp_employee(rec)
        self.assertNotIn(answer["status"],
                         (icpstructural.PASS, icpstructural.PASS_WITH_TOLERANCE))

    def test_revenue_does_not_invent_a_headcount(self):
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 4
        rec["company_facts"]["revenue"] = "$21.1M"
        witnesses = headcount.witnesses(rec)
        values = [w.get("value") for w in witnesses if w.get("value")]
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0], 4)


class CoverageAcrossTheEstate(unittest.TestCase):
    """Coverage as a NUMBER over the real queue, not an impression."""

    def test_coverage_is_measured_not_assumed(self):
        records = _estate()
        config = _config()
        covered = 0
        for rec in records:
            resolved = headcount.resolve(rec, config)
            if resolved["state"] in (headcount.AGREED, headcount.SINGLE_SOURCE):
                if resolved.get("value") is not None:
                    covered += 1
        self.assertEqual(covered, 272)
        self.assertEqual(len(records), 300)

    def test_unestablished_records_have_no_value(self):
        records = _estate()
        config = _config()
        for rec in records:
            resolved = headcount.resolve(rec, config)
            if resolved["state"] == headcount.UNESTABLISHED:
                self.assertIsNone(resolved["value"])

    def test_no_conflicts_in_the_synthetic_estate_without_second_opinions(self):
        """The synthetic estate has no Blitz observations, so no conflicts.

        This is the BASELINE. The real queue may have conflicts after Blitz
        runs - the architecture handles them, but the synthetic data has not
        yet exercised that path at estate scale.
        """
        records = _estate()
        config = _config()
        conflicts = sum(1 for rec in records
                        if headcount.resolve(rec, config)["state"] == headcount.CONFLICT)
        self.assertEqual(conflicts, 0)


class DeletingTheCallMakesTheTestFail(unittest.TestCase):
    """Break the wiring, not the logic.

    If `headcount.observe` is removed from the call chain, the conflict
    must not be detected - and these tests must fail.
    """

    def test_removing_observe_loses_the_conflict(self):
        """Counterfactual: without observe, the second source is absent."""
        rec = _estate(1)[0]
        rec["company_facts"]["employees"] = 3
        # DO NOT call headcount.observe - the counterfactual
        resolved = headcount.resolve(rec, _config())
        # Without the second opinion, this is SINGLE_SOURCE, not CONFLICT
        self.assertEqual(resolved["state"], headcount.SINGLE_SOURCE)
        # And the ICP criterion is FAIL (3 < 14), not UNKNOWN
        answer = _icp_employee(rec)
        self.assertEqual(answer["status"], icpstructural.FAIL)


if __name__ == "__main__":
    unittest.main()
