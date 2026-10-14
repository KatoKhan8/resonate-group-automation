"""The C11c controls must MEASURE, and must be able to fail.

A control that cannot fail certifies nothing, which is the defect this whole
branch exists to chase: a check that reports a number while reading the wrong
input. So every control here is paired with a mutation that is required to
flip its verdict, and the safety-critical one - the spend ledger - is paired
with a proof that it never touched production state.
"""
import datetime
import importlib.util
import inspect
import io
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_controls():
    spec = importlib.util.spec_from_file_location(
        "clockcontrols", os.path.join(ROOT, "scripts", "clockcontrols.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CC = _load_controls()


class TheSimulatedDateCannotCollideWithTheRealOne(unittest.TestCase):
    """A DIFFER result must not be the calendar agreeing by accident."""

    def test_the_simulated_date_is_not_today(self):
        self.assertNotEqual(CC.SIMULATED_DATE,
                            datetime.date.today().isoformat())

    def test_the_simulated_date_is_years_away(self):
        simulated = datetime.date.fromisoformat(CC.SIMULATED_DATE)
        self.assertGreater(abs((simulated - datetime.date.today()).days), 90)


class Row7TheSpendLedgerStampsTwoCalendars(unittest.TestCase):
    """The measured defect: `at` simulated, `day` real, in ONE row."""

    def setUp(self):
        self.result = CC.spendledger_day_control()

    def test_at_moves_with_the_simulated_clock(self):
        self.assertTrue(self.result["at_is_simulated"],
                        "store.now is the only BUSINESS_CLOCK_SEAM; `at` "
                        "must follow it")

    def test_day_stays_on_the_real_calendar(self):
        self.assertFalse(self.result["day_is_simulated"])

    def test_one_row_carries_two_calendars(self):
        self.assertTrue(self.result["same_row_two_calendars"])

    def test_record_cannot_be_told_the_day(self):
        """The reason this is not an injectability finding.

        Every READER of the ledger takes `day=`. The WRITER does not, so no
        caller can correct the stamp from outside.
        """
        self.assertFalse(self.result["record_accepts_day"])
        self.assertTrue(all(self.result["injectable_readers"].values()))

    def test_the_control_flips_when_the_day_source_is_patched(self):
        """THE MUTATION. Patch `today()` to the simulated date and the
        disagreement must disappear - otherwise this control is measuring
        something other than the day source."""
        from src import sandboxclock, spendledger

        original = spendledger.today
        spendledger.today = lambda now=None: CC.SIMULATED_DATE
        try:
            with CC._isolated_ledger():
                undo = sandboxclock.install(CC._FakeClock(CC.SIMULATED_ISO))
                try:
                    row = spendledger.record("clockcontrol", "none", "probe",
                                             0, run_id="clockcontrol")
                finally:
                    undo()
        finally:
            spendledger.today = original

        self.assertEqual(row["day"], CC.SIMULATED_DATE)
        self.assertTrue(str(row["at"]).startswith(CC.SIMULATED_DATE))

    def test_the_control_did_not_write_production_state(self):
        """The one test here that is about safety rather than about clocks.

        `spendledger.record()` builds its own append and the module's own
        comment records 19 rows of fabricated spend reaching a client's real
        ledger the one time a test skipped isolation. Fabricated spend is
        worse than a wrong report, because `check()` reads it to refuse the
        NEXT paid call.
        """
        from src import spendledger

        self.assertIsNone(os.environ.get("SPEND_LEDGER"),
                          "the isolation context must restore the "
                          "environment it borrowed")
        production = spendledger.path()
        self.assertNotIn("clockctl-", production)
        if os.path.exists(production):
            rows = [line for line in
                    io.open(production, encoding="utf-8").read().splitlines()
                    if line.strip()]
            for line in rows:
                self.assertNotIn("clockcontrol", line,
                                 "a control row reached the real ledger")


class Row4ReadbackFreshnessIsLiveAndInjectable(unittest.TestCase):

    def setUp(self):
        self.result = CC.readback_freshness_control()

    def test_it_agrees_when_injected(self):
        self.assertTrue(self.result["agrees_when_injected"])

    def test_it_differs_when_not_injected(self):
        self.assertTrue(self.result["differs_when_not_injected"])

    def test_the_two_answers_are_actually_opposite(self):
        self.assertTrue(self.result["answer_injected"])
        self.assertFalse(self.result["answer_not_injected"])

    def test_the_control_collapses_when_the_stamp_is_undatable(self):
        """THE MUTATION. An unparseable stamp returns False on BOTH
        calendars, so the control stops discriminating - proof that the
        DIFFER above came from the clock and not from the plumbing."""
        from src import executionguard

        self.assertFalse(executionguard.readback_is_fresh("not-a-date"))
        self.assertFalse(executionguard.readback_is_fresh(
            "not-a-date",
            now=datetime.datetime.fromisoformat(CC.SIMULATED_ISO)))


class Row8CopylintDemotionsExpireOnAClock(unittest.TestCase):

    def setUp(self):
        self.result = CC.copylint_demotion_control()

    def test_it_agrees_when_injected(self):
        self.assertTrue(self.result["agrees_when_injected"])

    def test_it_differs_when_not_injected(self):
        self.assertTrue(self.result["differs_when_not_injected"])

    def test_the_demotion_is_already_expired_on_the_real_calendar(self):
        """Why the two answers differ: the only demotion expired 2026-09-28.
        Stated as a measurement so a future DEMOTIONS edit fails this test
        loudly rather than making the control silently vacuous."""
        self.assertEqual(self.result["answer_not_injected"], [])
        self.assertNotEqual(self.result["answer_injected"], [])

    def test_the_control_goes_vacuous_with_a_date_past_every_expiry(self):
        """THE MUTATION. Injected far enough forward, both answers are empty
        and the control proves nothing - so the DIFFER must come from the
        chosen date and not from the function."""
        from src import copylint

        self.assertEqual(sorted(copylint.warning_rules("2099-01-01")), [])


class Row1TheInjectionPointExistsButIsNotForwarded(unittest.TestCase):

    def setUp(self):
        self.result = CC.quality_injection_gap_control()

    def test_the_two_lower_levels_are_injectable(self):
        self.assertTrue(self.result["age_days_accepts_today"])
        self.assertTrue(self.result["_selected_accepts_today"])

    def test_assess_has_no_date_parameter_at_all(self):
        self.assertFalse(self.result["assess_accepts_today"])
        self.assertEqual(self.result["assess_params"],
                         ["rec", "contact", "config"])

    def test_a_grep_for_today_equals_would_have_been_misleading(self):
        """Every call site passes `today` POSITIONALLY, so a grep for
        `today=` finds zero and reads as "nobody injects" - which is the
        wrong conclusion. Asserted on the signature, never on source text."""
        from src import evidence
        parameters = list(inspect.signature(evidence.age_days).parameters)
        self.assertEqual(parameters, ["published_at", "today"])


class Rows56AuthorizeInjectsButReachabilityIsTheQuestion(unittest.TestCase):

    def setUp(self):
        self.result = CC.authorize_injection_control()

    def test_authorize_takes_now_keyword_only(self):
        self.assertTrue(self.result["accepts_now"])
        self.assertTrue(self.result["now_is_keyword_only"])

    def test_the_sandbox_runner_names_none_of_these_modules(self):
        """Reachability, measured on the runner's own text for the ONE thing
        a grep is legitimate for: whether a name appears at all. A name that
        is absent cannot be called directly, which is a weaker claim than
        "never executed" and is reported as such."""
        with io.open(os.path.join(ROOT, "scripts", "sandbox_run.py"),
                     encoding="utf-8") as handle:
            source = handle.read()
        for name in ("executionguard", "spendledger", "authorize("):
            self.assertNotIn(name, source)


class TheReachabilityReaderDiscriminates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = CC.sandbox_reachability()

    def test_positive_controls_are_all_loaded(self):
        self.assertTrue(all(self.result["positive_controls"].values()),
                        self.result["positive_controls"])

    def test_the_negative_control_is_absent(self):
        self.assertTrue(self.result["negative_control_absent"])

    def test_it_reports_a_mix_rather_than_everything(self):
        """If every module came back LOADED the reader would be a constant."""
        values = list(self.result["loaded"].values())
        self.assertIn(True, values)
        self.assertIn(False, values)

    def test_heyreachfactory_the_only_src_caller_of_authorize_is_not_loaded(self):
        self.assertFalse(self.result["loaded"]["src.heyreachfactory"])

    def test_loaded_is_not_claimed_to_be_executed(self):
        """C11e is unimplemented and the report must not imply otherwise."""
        self.assertNotIn("executed", json.dumps(self.result).lower())

    def test_it_is_not_order_dependent(self):
        """REGRESSION. The first version of this reader diffed `sys.modules`
        inside the test process, so once another control had imported
        `src.evidence` the delta came back empty and every module read as
        "not loaded" - the positive controls failed and the reader was
        silently measuring history instead of imports.

        Here the contamination is created DELIBERATELY first, by importing
        the very modules the reader asks about, and the reader must still
        give the same answer.
        """
        import src.evidence          # noqa: F401  - contamination, on purpose
        import src.quality           # noqa: F401
        import src.spendledger       # noqa: F401

        again = CC.sandbox_reachability()
        self.assertTrue(all(again["positive_controls"].values()),
                        again["positive_controls"])
        self.assertEqual(again["loaded"], self.result["loaded"])


class TheWholeReportRunsAndStaysSerialisable(unittest.TestCase):

    def test_run_all_produces_every_control(self):
        report = CC.run_all()
        for name, _ in CC.CONTROLS:
            self.assertIn(name, report)
        json.dumps(report, default=str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
