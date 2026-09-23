"""The 2026-09-22 headcount amendment: what it removes, and what it must not.

`docs/OPERATOR-AUTHORIZATION-2026-09-22-BOUNCE-DENOMINATOR-AND-HEADCOUNT.md`
section D removes the headcount criterion for ONE snapshot. The scope line is
the point of the authorisation: `config/clients/productive.yaml` is not
edited and the 20+ floor still applies everywhere else. So the tests that
matter are the ones that would catch the amendment leaking.
"""

import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "stage_s3_icp", os.path.join(ROOT, "scripts", "stage_s3_icp.py"))
s3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s3)

ICP = {"size_min_employees": 20, "size_max_employees": None,
       "geos": ["United Kingdom", "United States", "Nordics"],
       "exclude_geos": ["India"]}


class TheAmendmentRemovesHeadcountAndNothingElse(unittest.TestCase):

    def test_a_small_company_in_a_named_geo_moves_from_out_to_in(self):
        info = {"domain": "x.com", "employees": 3, "country": "United States"}
        self.assertEqual(s3.judge(info, ICP)[0], "out")
        self.assertEqual(s3.judge(info, ICP, headcount=False)[0], "in")

    def test_unknown_headcount_stops_being_flagged(self):
        """This is most of what the amendment actually recovers."""
        info = {"domain": "x.com", "employees": None, "country": "United States"}
        self.assertEqual(s3.judge(info, ICP)[0], "flagged")
        self.assertEqual(s3.judge(info, ICP, headcount=False)[0], "in")

    def test_unknown_country_stays_flagged(self):
        """The authorisation says so in as many words."""
        info = {"domain": "x.com", "employees": 500, "country": ""}
        self.assertEqual(s3.judge(info, ICP, headcount=False)[0], "flagged")

    def test_an_excluded_geo_is_still_out(self):
        info = {"domain": "x.com", "employees": 500, "country": "India"}
        self.assertEqual(s3.judge(info, ICP, headcount=False), 
                         ("out", "excluded geo: India"))

    def test_a_geo_outside_the_list_is_flagged_not_dropped(self):
        """65% of this file turns on exactly this: flag_dont_drop."""
        info = {"domain": "x.com", "employees": 500, "country": "Canada"}
        verdict, reason = s3.judge(info, ICP, headcount=False)
        self.assertEqual(verdict, "flagged")
        self.assertIn("geo not confirmed", reason)

    def test_the_reason_names_the_amendment(self):
        """A verdict nobody can trace back to an authorisation is a liability."""
        info = {"domain": "x.com", "employees": 3, "country": "United States"}
        self.assertIn("amendment", s3.judge(info, ICP, headcount=False)[1])

    def test_the_default_is_unamended(self):
        """A caller that forgets the flag must get the 20+ floor, not the
        amendment. The amendment is opt-in or it is a config edit."""
        info = {"domain": "x.com", "employees": 3, "country": "United States"}
        self.assertEqual(s3.judge(info, ICP)[0], "out")

    def test_the_amendment_names_the_one_snapshot_it_is_bound_to(self):
        self.assertEqual(s3.HEADCOUNT_AMENDMENT, "PRODUCTIVE-2026-09-07")


if __name__ == "__main__":
    unittest.main()
