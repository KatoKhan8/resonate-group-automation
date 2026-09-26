"""CheapVerifier is registered in the email_verification waterfall.

TASK-358: the module existed only on an agent worktree branch and the
waterfall did not know it existed, so the first paid call would raise
WaterfallViolation. Both halves had to land together.

These tests prove:
  - the module imports and its entry point is callable
  - CheapVerifier is in the email_verification provider list
  - ContactOut is still first (the policy was not inverted)
  - a fixture record_step records a ledger row without raising
  - the fallback semantics are correct (requires a reason, refuses errors)
  - no live call is made (fixtures only)
"""
import unittest

from src import enrich, waterfall


class TestCheapVerifierImports(unittest.TestCase):
    """The module is on master and importable."""

    def test_module_imports(self):
        from src.providers import cheapverifier as cv
        self.assertTrue(hasattr(cv, "verify_single"))
        self.assertTrue(hasattr(cv, "PROVIDER"))
        self.assertEqual(cv.PROVIDER, "cheapverifier")

    def test_call_single_is_priced(self):
        self.assertIn("cheapverifier-verify", enrich.COSTS)
        self.assertEqual(enrich.COSTS["cheapverifier-verify"], 1)

    def test_call_single_is_routed_to_email_verification(self):
        self.assertIn("cheapverifier-verify", enrich.CALL_STAGE)
        self.assertEqual(enrich.CALL_STAGE["cheapverifier-verify"],
                         "email_verification")


class TestCheapVerifierInTheWaterfall(unittest.TestCase):
    """The WaterfallViolation is gone: CheapVerifier is a known provider."""

    def test_cheapverifier_in_email_verification_providers(self):
        provs = [p["provider"] for p in
                 waterfall.STAGES[waterfall.EMAIL_VERIFICATION]["providers"]]
        self.assertIn(waterfall.CHEAPVERIFIER, provs)

    def test_describe_includes_cheapverifier(self):
        d = waterfall.describe()
        provs = [p["provider"] for p in
                 d[waterfall.EMAIL_VERIFICATION]["providers"]]
        self.assertIn("cheapverifier", provs)

    def test_contactout_still_before_cheapverifier(self):
        """The operator's policy was not inverted to save money."""
        provs = [p["provider"] for p in
                 waterfall.STAGES[waterfall.EMAIL_VERIFICATION]["providers"]]
        co_idx = provs.index(waterfall.CONTACTOUT)
        cv_idx = provs.index(waterfall.CHEAPVERIFIER)
        self.assertLess(co_idx, cv_idx,
                        "ContactOut must precede CheapVerifier in "
                        "email_verification")

    def test_cheapverifier_is_a_fallback(self):
        step = waterfall.step_for(waterfall.EMAIL_VERIFICATION,
                                  waterfall.CHEAPVERIFIER,
                                  "cheapverifier-verify")
        self.assertIsNotNone(step)
        self.assertTrue(step.get("requires_reason"),
                        "CheapVerifier must require a reason to be called")

    def test_cheapverifier_cost_unit_is_named(self):
        unit = waterfall.COST_UNITS.get(waterfall.CHEAPVERIFIER, "")
        self.assertIn("cheapverifier", unit.lower(),
                      "cost unit must name the provider's credit type")


class TestCheapVerifierFallbackSemantics(unittest.TestCase):
    """The fallback refuses the wrong reasons and accepts the right ones."""

    def test_accepts_verification_inconclusive(self):
        ok, why = waterfall.may_fall_back(
            waterfall.EMAIL_VERIFICATION, waterfall.CHEAPVERIFIER,
            "verification_inconclusive")
        self.assertTrue(ok, why)

    def test_accepts_verification_contradiction(self):
        ok, why = waterfall.may_fall_back(
            waterfall.EMAIL_VERIFICATION, waterfall.CHEAPVERIFIER,
            "verification_contradiction")
        self.assertTrue(ok, why)

    def test_refuses_no_reason(self):
        ok, why = waterfall.may_fall_back(
            waterfall.EMAIL_VERIFICATION, waterfall.CHEAPVERIFIER, None)
        self.assertFalse(ok)
        self.assertIn("reason", why.lower())

    def test_refuses_transient_error(self):
        ok, why = waterfall.may_fall_back(
            waterfall.EMAIL_VERIFICATION, waterfall.CHEAPVERIFIER,
            "contactout_error")
        self.assertFalse(ok)
        self.assertIn("transient", why.lower())

    def test_refuses_timeout(self):
        ok, why = waterfall.may_fall_back(
            waterfall.EMAIL_VERIFICATION, waterfall.CHEAPVERIFIER,
            "contactout_timeout")
        self.assertFalse(ok)

    def test_require_raises_on_bad_reason(self):
        with self.assertRaises(waterfall.WaterfallViolation):
            waterfall.require(waterfall.EMAIL_VERIFICATION,
                              waterfall.CHEAPVERIFIER, None)


class TestCheapVerifierFixtureRecordStep(unittest.TestCase):
    """A fixture call records a waterfall step and a ledger row."""

    def test_record_step_does_not_raise(self):
        rec = {"id": "test-cv-fixture-001"}
        waterfall.record_step(rec, waterfall.EMAIL_VERIFICATION,
                              "contactout", "email-verifier",
                              result={"status": "accept_all"})
        waterfall.record_step(rec, waterfall.EMAIL_VERIFICATION,
                              waterfall.CHEAPVERIFIER,
                              "cheapverifier-verify",
                              reason="verification_inconclusive",
                              result={"outcome": "valid"})
        rows = waterfall.ledger(rec)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["provider"], "cheapverifier")
        self.assertEqual(rows[-1]["call"], "cheapverifier-verify")

    def test_spend_reflects_cheapverifier_call(self):
        rec = {"id": "test-cv-fixture-002"}
        waterfall.record_step(rec, waterfall.EMAIL_VERIFICATION,
                              "contactout", "email-verifier",
                              result={"status": "accept_all"})
        waterfall.record_step(rec, waterfall.EMAIL_VERIFICATION,
                              waterfall.CHEAPVERIFIER,
                              "cheapverifier-verify",
                              reason="verification_inconclusive",
                              result={"outcome": "valid"})
        s = waterfall.spend(rec)
        self.assertIn("cheapverifier", s["by_provider"])
        self.assertEqual(s["by_provider"]["cheapverifier"]["calls"], 1)
        self.assertEqual(s["expected"], 2)

    def test_audit_sees_no_problems(self):
        rec = {"id": "test-cv-fixture-003"}
        waterfall.record_step(rec, waterfall.EMAIL_VERIFICATION,
                              "contactout", "email-verifier",
                              result={"status": "accept_all"})
        waterfall.record_step(rec, waterfall.EMAIL_VERIFICATION,
                              waterfall.CHEAPVERIFIER,
                              "cheapverifier-verify",
                              reason="verification_inconclusive",
                              result={"outcome": "valid"})
        result = waterfall.audit(rec)
        self.assertEqual(result["unjustified"], [])


if __name__ == "__main__":
    unittest.main()
