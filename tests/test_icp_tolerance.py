"""An ICP describes who a product is for. It is not a fence with a guard on it.

`min_employees` was both. A company one person under it took the full
`too_small` penalty on the `employee_count` dimension, which is decisive, and
was rejected outright - while the company one person above it was scored
normally and reached a human. Nothing about a services business changes
between nine people and ten, so a rule that says otherwise is describing its
own arithmetic rather than the market.

Inside the tolerance band the penalty still applies, because the company
really is smaller than the target and that is worth points. What it stops
doing is ending the conversation.

Two things this must not become. It is not a way to make more companies
qualify: the band is a fixed fraction stated once, and the tests below use
synthetic sizes rather than the sizes of any real batch. And it does not
touch a hard exclusion - a SaaS company is not a services business at any
headcount, and no amount of tolerance changes that.
"""
import unittest

from src import icp, store

AGENCY = {"industry": "Marketing and Advertising",
          "specialties": ["digital marketing agency", "brand strategy"],
          "offices": [{"city": "Leeds"}, {"city": "York"}]}


def company(**facts):
    rec = store.new_record("t1", "domains", "demo", "T", "t.test")
    rec["company_facts"] = dict(AGENCY, **facts)
    return rec


def verdict(**facts):
    return icp.score(company(**facts), None)


class TheBandIsAroundTheBoundary(unittest.TestCase):

    def test_the_band_is_a_fraction_of_the_boundary(self):
        low, high = icp.soft_band(20)
        self.assertEqual((low, high), (14.0, 26.0))

    def test_a_boundary_of_none_has_no_band(self):
        self.assertEqual(icp.soft_band(None), (None, None))

    def test_the_tolerance_is_stated_once(self):
        """A number that appears twice is a number that will differ twice."""
        self.assertEqual(icp.SOFT_TOLERANCE, 0.30)


class JustUnderIsNotOut(unittest.TestCase):
    """Default `min_employees` is 10, so the band runs from 7."""

    def test_well_below_the_floor_is_still_a_clear_no(self):
        v = verdict(employees=3)
        self.assertEqual(v["icp_status"], icp.REJECTED)
        self.assertEqual(v["icp_grade"], icp.CLEAR_NON_ICP)

    def test_inside_the_band_is_not_rejected(self):
        for size in (7, 8, 9):
            v = verdict(employees=size)
            self.assertNotEqual(v["icp_status"], icp.REJECTED, size)
            self.assertNotEqual(v["icp_grade"], icp.CLEAR_NON_ICP, size)

    def test_inside_the_band_still_costs_points(self):
        """Tolerated is not free: the company really is under the target."""
        near = verdict(employees=9)
        over = verdict(employees=20)
        self.assertLess(near["icp_score"], over["icp_score"])
        self.assertTrue([s for s in near["negative_signals"]
                         if s["dimension"] == "employee_count_soft"])

    def test_the_soft_miss_is_not_a_decisive_dimension(self):
        """The whole mechanism: the penalty lands somewhere non-fatal."""
        near = verdict(employees=9)
        self.assertEqual(icp._decisive(near["negative_signals"]), [])

    def test_and_the_hard_miss_still_is(self):
        far = verdict(employees=3)
        self.assertTrue(icp._decisive(far["negative_signals"]))


class ToleranceDoesNotReachAHardExclusion(unittest.TestCase):

    def test_a_product_business_is_out_at_any_size(self):
        for size in (9, 40, 400):
            rec = store.new_record("t1", "domains", "demo", "T", "t.test")
            rec["company_facts"] = {
                "industry": "Software as a Service", "employees": size,
                "specialties": ["saas platform", "pricing plans"]}
            v = icp.score(rec, None)
            self.assertEqual(v["icp_grade"], icp.CLEAR_NON_ICP, size)

    def test_the_ceiling_gets_the_same_tolerance_and_no_more(self):
        near = verdict(employees=6000)          # inside 5000 +30%
        far = verdict(employees=9000)           # outside it
        near_penalty = [s for s in near["negative_signals"]
                        if s["dimension"] == "unsuitable_enterprise"][0]
        far_penalty = [s for s in far["negative_signals"]
                       if s["dimension"] == "unsuitable_enterprise"][0]
        self.assertGreater(near_penalty["weight"], far_penalty["weight"])


class MissingIsNotNegative(unittest.TestCase):

    def test_an_unknown_headcount_is_not_a_small_one(self):
        v = verdict()
        self.assertEqual([s for s in v["negative_signals"]
                          if "employee" in s["dimension"]], [])
        self.assertNotEqual(v["icp_grade"], icp.CLEAR_NON_ICP)

    def test_it_costs_confidence_rather_than_score(self):
        self.assertIn("employee count unknown", verdict()["missing_evidence"])


class GradeSaysFitNotPermission(unittest.TestCase):

    def test_every_grade_is_one_of_the_five(self):
        for size in (3, 9, 25, 120, 400):
            self.assertIn(verdict(employees=size)["icp_grade"], icp.GRADES)

    def test_a_decisive_negative_is_always_clear_non_icp(self):
        self.assertEqual(verdict(employees=2)["icp_grade"], icp.CLEAR_NON_ICP)

    def test_grade_is_reported_separately_from_status(self):
        """A company can be held for want of evidence and still be a fit."""
        v = verdict(employees=25)
        self.assertEqual(v["icp_status"], icp.REVIEW)
        self.assertNotEqual(v["icp_grade"], icp.CLEAR_NON_ICP)


if __name__ == "__main__":
    unittest.main()
