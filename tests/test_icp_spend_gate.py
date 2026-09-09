"""Company first. No paid person-level call before an explicit ICP verdict.

CLAUDE.md: "No paid person-level call before a company reaches an explicit ICP
verdict, and rejected, review and unknown all mean zero person credits."

Nothing enforced it. `enrich` imported neither `icp` nor `dmplan`, and
`enrich.run` selects on `state in ("queued","enriched")` alone - so a company
a human had explicitly marked `rejected` was planned and charged for
`decision-makers`, ten credits, exactly like a qualified one. So was a company
nobody had assessed at all. Over a thirty thousand domain universe that is
three hundred thousand credits of person-level calls on companies with no
verdict behind them.

`dmplan.may_enrich` calls itself "the single gate" and had no caller on any
path that spends; its only production caller is a screen that renders the
answer. This is the gate on the path that spends.
"""
import unittest

from src import dmplan, enrich, icp, qualify, store


def company(rid="gate01"):
    rec = store.new_record(rid, "domains", "demo", "Gate Co", f"{rid}.test")
    rec["state"] = "queued"
    return rec


def with_verdict(rec, status):
    """The minimum a record needs to carry an explicit verdict.

    Written directly rather than scored, because what is under test is what
    the gate does with a verdict, not how `icp.score` arrives at one.
    """
    rec["qualification"] = {"inputs_fingerprint": "pinned-for-this-test",
                            "at": store.now(),
                            "verdict": {"icp_status": status}}
    return rec


class NoPersonCreditWithoutAVerdict(unittest.TestCase):

    def spent_on(self, rec, cap=1000):
        budget = enrich.Budget(cap=cap)
        done = enrich.enrich_record(rec, budget, live=False, log=[])
        return [op["call"] for op in done], budget.spent

    def person_calls(self, calls):
        return [c for c in calls if c in enrich.PERSON_LEVEL]

    # ------------------------------------------------ the four verdicts

    def test_rejected_buys_no_person_credit(self):
        calls, _ = self.spent_on(with_verdict(company(), icp.REJECTED))
        self.assertEqual(self.person_calls(calls), [])

    def test_review_buys_no_person_credit(self):
        calls, _ = self.spent_on(with_verdict(company(), icp.REVIEW))
        self.assertEqual(self.person_calls(calls), [])

    def test_unknown_buys_no_person_credit(self):
        calls, _ = self.spent_on(with_verdict(company(), icp.UNKNOWN))
        self.assertEqual(self.person_calls(calls), [])

    def test_no_verdict_at_all_buys_no_person_credit(self):
        """The commonest case: a fresh import nobody has assessed."""
        rec = company()
        self.assertEqual(qualify.state_of(rec), dmplan.NOT_PROCESSED)
        calls, _ = self.spent_on(rec)
        self.assertEqual(self.person_calls(calls), [])

    def test_qualified_may_proceed(self):
        """Otherwise the gate is not a gate, it is an off switch."""
        calls, _ = self.spent_on(with_verdict(company(), icp.QUALIFIED))
        self.assertIn("decision-makers", calls)

    # ------------------------------------------- and the verdict stays reachable

    def test_company_level_work_is_never_gated(self):
        """Company-level calls are what *produce* the verdict. Gating those
        would not make the gate strict, it would make it permanent."""
        calls, _ = self.spent_on(with_verdict(company(), icp.REJECTED))
        self.assertIn("people-count", calls)

    def test_a_rejected_company_still_learns_who_it_is(self):
        calls, _ = self.spent_on(with_verdict(company(), icp.REJECTED))
        self.assertIn("company-information-from-domain", calls)

    # ------------------------------------------------------- adversarial

    def test_qualified_at_planning_but_rejected_before_execution_is_blocked(self):
        """The gate must be asked at the spend, not at the plan.

        A plan is a forecast made earlier, possibly by a different process. If
        the only check happened there, a rejection recorded in between would
        be spent straight through.
        """
        rec = with_verdict(company(), icp.QUALIFIED)
        planned = [op["call"] for op in enrich.plan(rec)]
        self.assertIn("decision-makers", planned)

        with_verdict(rec, icp.REJECTED)          # a human says no, in between
        calls, _ = self.spent_on(rec)
        self.assertEqual(self.person_calls(calls), [])

    def test_a_human_rejection_outranks_a_qualified_verdict(self):
        rec = with_verdict(company(), icp.QUALIFIED)
        rec["qualification"]["human_review"] = {
            "decision": qualify.REJECT, "by": "ops@demo.test",
            "at": store.now(),
            "inputs_fingerprint": "pinned-for-this-test"}
        self.assertEqual(qualify.state_of(rec), dmplan.REJECTED)
        calls, _ = self.spent_on(rec)
        self.assertEqual(self.person_calls(calls), [])

    # ----------------------------------------------- and it says why

    def test_the_refusal_is_recorded_against_the_record(self):
        rec = with_verdict(company(), icp.REJECTED)
        self.spent_on(rec)
        skipped = [e for e in rec.get("events") or []
                   if e.get("type") == "provider_call_skipped"
                   and "icp" in str(e.get("reason"))]
        self.assertTrue(skipped, "a refusal nobody can audit is not a control")

    def test_a_rejected_company_is_not_dropped_for_the_wrong_reason(self):
        """It drops - that decision is final - but under the true reason."""
        rec = with_verdict(company(), icp.REJECTED)
        self.spent_on(rec)
        self.assertEqual(rec["state"], "dropped")
        self.assertEqual(rec["drop_reason"], enrich.ICP_REJECTED)

    def test_a_company_still_awaiting_a_verdict_is_not_dropped_at_all(self):
        rec = company()
        self.spent_on(rec)
        self.assertNotEqual(rec["state"], "dropped")
        self.assertIsNone(rec.get("drop_reason"))
        self.assertTrue(enrich.person_level_pending(rec))


class TheForecastIsTheNumberYouSizeACapAgainst(unittest.TestCase):
    """`plan()` never asked the gate, so it promised what `spend()` refuses.

    For a domain-only company with no verdict it forecast `decision-makers` as
    expected spend - ten credits that cannot happen - and filed the one credit
    that *does* happen under "maximum", because it was described as
    conditional on a call that can no longer run. Over fifty domains that is a
    forecast of 500 expected against a real exposure of 50, and an operator
    sizing `--cap` from it is sizing it against fiction.
    """

    def calls_and_exposure(self, rec):
        ops = enrich.plan(rec)
        return [o["call"] for o in ops], enrich.exposure(ops)

    def test_no_person_level_call_is_forecast_without_a_verdict(self):
        calls, _ = self.calls_and_exposure(company())
        self.assertEqual([c for c in calls if c in enrich.PERSON_LEVEL], [])

    def test_the_forecast_is_what_the_run_actually_spends(self):
        rec = company()
        _, exposure = self.calls_and_exposure(rec)
        budget = enrich.Budget(cap=1000)
        enrich.enrich_record(rec, budget, live=False, log=[])
        self.assertEqual(exposure["expected"], budget.spent)

    def test_the_real_credit_is_expected_not_merely_possible(self):
        _, exposure = self.calls_and_exposure(company())
        self.assertEqual(exposure["expected"], exposure["maximum"])

    def test_a_qualified_company_is_still_forecast_the_person_call(self):
        calls, _ = self.calls_and_exposure(
            with_verdict(company(), icp.QUALIFIED))
        self.assertIn("decision-makers", calls)


class ACallIsBoughtOnce(unittest.TestCase):
    """A deferred company is no longer dropped, so it comes back every pass.

    That is correct - it is waiting for a verdict, not disqualified - but the
    rebrand check was re-bought each time, one credit per company per run for
    an answer already sitting on the record.
    """

    def passes(self, rec, count=3):
        spent = []
        for _ in range(count):
            budget = enrich.Budget(cap=1000)
            enrich.enrich_record(rec, budget, live=False, log=[])
            spent.append(budget.spent)
        return spent

    def test_the_rebrand_check_is_not_bought_on_every_pass(self):
        self.assertEqual(self.passes(company()), [1, 0, 0])

    def test_the_ledger_is_what_remembers_it(self):
        rec = company()
        self.passes(rec, count=1)
        self.assertTrue(enrich.already_bought(
            rec, "company-information-from-domain"))

    def test_a_record_that_never_bought_it_is_not_blocked(self):
        self.assertFalse(enrich.already_bought(
            company(), "company-information-from-domain"))


if __name__ == "__main__":
    unittest.main()
