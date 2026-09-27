"""TASK-358: CheapVerifier is registered in the email_verification waterfall.

The module existed on a branch and the waterfall did not know about it, so the
first paid call would have raised:

    WaterfallViolation: cheapverifier is not part of the email_verification waterfall

These tests prove the violation is gone, ContactOut is still first (the
product policy from PROVIDER-ROUTING-POLICY.md), and a fixture record_step
writes a ledger row the audit can see.
"""
import unittest

from src import waterfall


class TestCheapVerifierRegistration(unittest.TestCase):

    def test_cheapverifier_is_in_the_email_verification_providers(self):
        provs = [p["provider"] for p in
                 waterfall.STAGES[waterfall.EMAIL_VERIFICATION]["providers"]]
        self.assertIn(waterfall.CHEAPVERIFIER, provs)

    def test_describe_includes_cheapverifier(self):
        d = waterfall.describe()
        provs = [p["provider"] for p in
                 d[waterfall.EMAIL_VERIFICATION]["providers"]]
        self.assertIn("cheapverifier", provs)

    def test_contactout_is_still_before_cheapverifier(self):
        provs = [p["provider"] for p in
                 waterfall.STAGES[waterfall.EMAIL_VERIFICATION]["providers"]]
        co_idx = provs.index(waterfall.CONTACTOUT)
        cv_idx = provs.index(waterfall.CHEAPVERIFIER)
        self.assertLess(co_idx, cv_idx,
                        f"ContactOut at {co_idx} must precede "
                        f"CheapVerifier at {cv_idx}")

    def test_contactout_is_first_in_email_verification(self):
        self.assertEqual(
            waterfall.first_provider(waterfall.EMAIL_VERIFICATION),
            waterfall.CONTACTOUT)

    def test_cheapverifier_has_a_cost_unit(self):
        self.assertIn(waterfall.CHEAPVERIFIER, waterfall.COST_UNITS)

    def test_cheapverifier_step_is_not_a_fallback(self):
        step = waterfall.step_for(waterfall.EMAIL_VERIFICATION,
                                  waterfall.CHEAPVERIFIER,
                                  "cheapverifier-verify")
        self.assertIsNotNone(step)
        self.assertFalse(step.get("is_fallback", True),
                         "CheapVerifier is a primary-path rung, not a fallback")


class TestCheapVerifierLedger(unittest.TestCase):

    def test_record_step_does_not_raise_for_cheapverifier(self):
        rec = {"id": "test-cv-001"}
        waterfall.record_step(rec, waterfall.EMAIL_VERIFICATION,
                              waterfall.CHEAPVERIFIER, "cheapverifier-verify",
                              result="valid")
        ledger = waterfall.ledger(rec)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["provider"], waterfall.CHEAPVERIFIER)
        self.assertEqual(ledger[0]["call"], "cheapverifier-verify")

    def test_record_step_writes_a_cost_unit(self):
        rec = {"id": "test-cv-002"}
        waterfall.record_step(rec, waterfall.EMAIL_VERIFICATION,
                              waterfall.CHEAPVERIFIER, "cheapverifier-verify",
                              result="invalid")
        row = waterfall.ledger(rec)[0]
        self.assertEqual(row["cost_unit"],
                         waterfall.COST_UNITS[waterfall.CHEAPVERIFIER])

    def test_spend_sees_the_cheapverifier_row(self):
        rec = {"id": "test-cv-003"}
        waterfall.record_step(rec, waterfall.EMAIL_VERIFICATION,
                              waterfall.CHEAPVERIFIER, "cheapverifier-verify",
                              result="valid")
        s = waterfall.spend(rec)
        self.assertIn(waterfall.CHEAPVERIFIER, s["by_provider"])
        self.assertEqual(s["by_provider"][waterfall.CHEAPVERIFIER]["calls"], 1)
        self.assertEqual(s["calls"], 1)

    def test_may_fall_back_accepts_cheapverifier_as_primary(self):
        ok, why = waterfall.may_fall_back(waterfall.EMAIL_VERIFICATION,
                                          waterfall.CHEAPVERIFIER, None,
                                          "cheapverifier-verify")
        self.assertTrue(ok, why)


if __name__ == "__main__":
    unittest.main()
