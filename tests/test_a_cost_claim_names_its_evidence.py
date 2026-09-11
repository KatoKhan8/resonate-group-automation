#!/usr/bin/env python3
"""A number is not a measurement until it says where it came from.

THE CLAIM THIS EXISTS TO PREVENT. On 2026-09-09 I reported "zero credits
spent" from ContactOut's `count` field alone. ContactOut meters at least three
buckets independently and one counter is not a total. The operator's
correction - "do not repeat that claim" - is this module's premise.

Then on 2026-09-10 a run's internal ledger expected 26 credits, 22 of them
ContactOut, and all three ContactOut counters were unchanged on both sides of
it. Both numbers were real, neither was the answer alone, and nothing in the
system could say so. COST_UNRECONCILED is the name for that.
"""
import unittest

from src import costs


def rec(*rows):
    return {"id": "r1", "waterfall": [dict(at="2026-09-10T10:15", **r)
                                      for r in rows]}


def call(provider, name, cost):
    return {"provider": provider, "call": name, "expected_cost": cost}


def snap(count=100, search=10, phone=5, usd=1.0,
         quota=1000, search_quota=2000, phone_quota=300):
    return {"contactout": {"count": count, "search_count": search,
                           "phone_count": phone, "quota": quota,
                           "search_quota": search_quota,
                           "phone_quota": phone_quota},
            "apify": {"usd": usd}}


def verdict(result, provider):
    return next(r for r in result["providers"] if r["provider"] == provider)


class TheFiveVerdicts(unittest.TestCase):

    def test_expected_and_observed_both_move_is_reconciled(self):
        out = costs.reconcile(snap(), snap(count=110),
                              [rec(call("contactout", "people-enrich", 10))])
        self.assertEqual(verdict(out, "contactout")["status"], costs.RECONCILED)

    def test_nothing_expected_and_nothing_moved_is_free_confirmed(self):
        out = costs.reconcile(snap(), snap(),
                              [rec(call("contactout", "people-count", 0))])
        self.assertEqual(verdict(out, "contactout")["status"],
                         costs.FREE_CONFIRMED)

    def test_expected_but_nothing_moved_is_unreconciled(self):
        """The real case, measured on 2026-09-10."""
        out = costs.reconcile(snap(), snap(),
                              [rec(call("contactout", "decision-makers", 10),
                                   call("contactout", "decision-makers", 10),
                                   call("contactout", "email-verifier", 1),
                                   call("contactout", "email-verifier", 1))])
        row = verdict(out, "contactout")
        self.assertEqual(row["status"], costs.COST_UNRECONCILED)
        self.assertEqual(row["expected"], 22)
        self.assertIn("contactout", out["unreconciled"])
        # It must refuse BOTH readings, not pick the convenient one.
        self.assertIn("must not be reported as 22 spent", row["why"])
        self.assertIn("must not be reported as free", row["why"])

    def test_ledgered_calls_at_a_zero_price_that_cost_money_are_unpriced(self):
        """Apify: ten recorded calls, priced 0, $0.66 of real compute.

        Distinct from a bypass, and the distinction is not pedantic - one
        sends somebody hunting for an unledgered call, the other tells them
        the price table is wrong.
        """
        out = costs.reconcile(snap(usd=1.0), snap(usd=1.66),
                              [rec(*[call("apify", "apify-research", 0)] * 10)])
        row = verdict(out, "apify")
        self.assertEqual(row["status"], costs.UNPRICED)
        self.assertIn("not a bypass", row["why"])

    def test_money_moved_with_no_ledgered_call_at_all_is_unreconciled(self):
        """That one IS a bypass, and must not be softened into UNPRICED."""
        out = costs.reconcile(snap(usd=1.0), snap(usd=1.66), [rec()])
        self.assertEqual(verdict(out, "apify")["status"],
                         costs.COST_UNRECONCILED)

    def test_a_provider_with_no_counter_is_estimated_only(self):
        out = costs.reconcile(snap(), snap(),
                              [rec(call("reoon", "reoon-verify", 1))])
        row = verdict(out, "reoon")
        self.assertEqual(row["status"], costs.ESTIMATED_ONLY)
        self.assertIn("cannot be confirmed or refuted", row["why"])


class ACounterThatLagsIsNotAMismatch(unittest.TestCase):
    """Measured, and the measurement is the whole reason this exists.

    Pass 3 on 2026-09-10 expected 22 ContactOut credits. Read twenty minutes
    later all three counters were unchanged, and this module said
    COST_UNRECONCILED - correctly, because it refused to choose between "these
    do not meter" and "the counters lag". Read again eight hours later the
    SAME window showed count +4, phone_count +3, search_count +25 and the
    verdict became RECONCILED.

    The second disjunct was true. So a disagreement read minutes after a run
    is evidence of impatience rather than of a mismatch, and reporting it as
    the latter is how somebody spends a morning debugging a provider that was
    working the whole time.
    """

    def calls(self):
        return [rec(call("contactout", "decision-makers", 10),
                    call("contactout", "decision-makers", 10),
                    call("contactout", "email-verifier", 1),
                    call("contactout", "email-verifier", 1))]

    def test_read_too_soon_it_is_pending_not_a_finding(self):
        out = costs.reconcile(snap(), snap(), self.calls(), measured_after=1200)
        row = verdict(out, "contactout")
        self.assertEqual(row["status"], costs.PENDING_SETTLEMENT)
        self.assertIn("Too early to be a finding", row["why"])
        self.assertNotIn("contactout", out["unreconciled"])

    def test_read_after_the_window_it_is_a_finding(self):
        out = costs.reconcile(snap(), snap(), self.calls(),
                              measured_after=costs.SETTLING_SECONDS + 1)
        self.assertEqual(verdict(out, "contactout")["status"],
                         costs.COST_UNRECONCILED)

    def test_the_settled_reading_reconciles(self):
        """The real numbers, eight hours on."""
        out = costs.reconcile(snap(count=566, search=77, phone=462),
                              snap(count=570, search=102, phone=465),
                              self.calls(), measured_after=28800)
        self.assertEqual(verdict(out, "contactout")["status"], costs.RECONCILED)

    def test_an_unstated_age_does_not_silently_become_pending(self):
        """A caller that says nothing gets a finding, not a shrug.

        Defaulting to PENDING would make every run inconclusive by omission,
        which is a quieter way of never reconciling anything.
        """
        out = costs.reconcile(snap(), snap(), self.calls())
        self.assertEqual(verdict(out, "contactout")["status"],
                         costs.COST_UNRECONCILED)

    def test_pending_never_hides_a_provider_that_moved_unexpectedly(self):
        """Settling explains a counter that has not moved YET. It explains
        nothing about one that moved when nothing was expected."""
        out = costs.reconcile(snap(usd=1.0), snap(usd=1.66), [rec()],
                              measured_after=60)
        self.assertEqual(verdict(out, "apify")["status"],
                         costs.COST_UNRECONCILED)


class AFallingAllowanceIsConsumption(unittest.TestCase):
    """The field that actually answers the question, and the sign it counts in.

    MEASURED, and it cost a day. `count`, `search_count` and `phone_count` are
    usage within a period and do NOT increment for every billable operation.
    Twelve hours after a run that expected 243 credits all three were
    unchanged, and this module reported COST_UNRECONCILED - while `quota` had
    fallen 38, `search_quota` 216 and `phone_quota` 34, right beside them in
    the same response.

    "One counter is not a total" was the original lesson. This is the same
    lesson one level deeper: the right counter is not always the one named
    after the thing you are counting.
    """

    def calls(self, cost=243):
        return [rec(call("contactout", "company-information-from-domain", cost))]

    def test_a_quota_that_fell_is_read_as_spend(self):
        got = costs.observed(snap(quota=1000), snap(quota=962))["contactout"]
        self.assertEqual(got["quota"], 38)

    def test_the_real_case_reconciles(self):
        """The exact numbers from 2026-09-11."""
        before = snap(count=570, search=102, phone=465,
                      quota=39215, search_quota=119127, phone_quota=4370)
        after = snap(count=570, search=102, phone=465,
                     quota=39177, search_quota=118911, phone_quota=4336)
        out = costs.reconcile(before, after, self.calls(), measured_after=43000)
        self.assertEqual(verdict(out, "contactout")["status"], costs.RECONCILED)

    def test_unchanged_counters_alone_no_longer_read_as_a_mismatch(self):
        """The regression this closes, stated as the thing that was wrong."""
        before = snap(count=570, quota=39215)
        after = snap(count=570, quota=39177)
        row = verdict(costs.reconcile(before, after, self.calls()), "contactout")
        self.assertNotEqual(row["status"], costs.COST_UNRECONCILED)

    def test_an_allowance_that_ROSE_is_reported_as_it_reads(self):
        """A top-up or a plan change is a fact about the provider, not spend.

        Reported negative rather than clamped, for the same reason a counter
        that went down is: clamping is how "they extended our quota" becomes
        "we spent nothing".
        """
        got = costs.observed(snap(quota=1000), snap(quota=1500))["contactout"]
        self.assertEqual(got["quota"], -500)

    def test_a_quota_nobody_read_is_still_not_zero(self):
        before = {"contactout": {"count": 100}}
        after = {"contactout": {"count": 100}}
        self.assertIsNone(costs.observed(before, after)["contactout"]["quota"])


class ItRefusesToInvent(unittest.TestCase):

    def test_an_unread_counter_is_not_zero(self):
        """"We did not look" and "it did not move" are different facts."""
        before = {"contactout": {"count": 100}}      # search/phone absent
        after = {"contactout": {"count": 100}}
        got = costs.observed(before, after)["contactout"]
        self.assertEqual(got["count"], 0)
        self.assertIsNone(got["search_count"])
        self.assertIsNone(got["phone_count"])

    def test_no_reading_at_all_cannot_be_reconciled(self):
        out = costs.reconcile({}, {}, [rec(call("contactout", "x", 10))])
        self.assertEqual(verdict(out, "contactout")["status"],
                         costs.ESTIMATED_ONLY)

    def test_a_counter_that_went_down_is_reported_as_it_read(self):
        """Quotas reset. Clamping to zero is how that becomes "spent nothing"."""
        got = costs.observed(snap(count=100), snap(count=40))["contactout"]
        self.assertEqual(got["count"], -60)

    def test_credits_and_dollars_are_never_summed(self):
        out = costs.reconcile(snap(), snap(count=110, usd=2.0),
                              [rec(call("contactout", "x", 10),
                                   call("apify", "y", 0))])
        self.assertIsNone(out["total"])
        self.assertIn("different units", out["total_why"])

    def test_rows_before_the_run_are_not_counted(self):
        old = {"id": "r1", "waterfall": [
            dict(at="2026-01-01T00:00", **call("contactout", "old", 500))]}
        out = costs.reconcile(snap(), snap(), [old], since="2026-09-10T10:10")
        self.assertEqual(verdict(out, "contactout")["expected"], 0)


class ItSaysWhichCallsItCounted(unittest.TestCase):

    def test_the_breakdown_names_each_call(self):
        out = costs.reconcile(snap(), snap(),
                              [rec(call("contactout", "decision-makers", 10),
                                   call("contactout", "email-verifier", 1))])
        by_call = verdict(out, "contactout")["by_call"]
        self.assertEqual(by_call["decision-makers"]["expected"], 10)
        self.assertEqual(by_call["email-verifier"]["calls"], 1)

    def test_the_report_leads_with_the_verdict(self):
        """An operator reads the first word. It must be the classification."""
        out = costs.reconcile(snap(), snap(),
                              [rec(call("contactout", "decision-makers", 10))])
        first = costs.report(out).splitlines()[0]
        self.assertTrue(first.startswith(costs.COST_UNRECONCILED), first)


if __name__ == "__main__":
    unittest.main()
