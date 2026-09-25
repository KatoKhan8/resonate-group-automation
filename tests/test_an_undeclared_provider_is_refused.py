"""An undeclared provider is REFUSED. It is never silently allowed.

OPERATOR DECISION, 2026-09-25: "Undeclared provider = check() refuses, never
silently allows; a test asserts that."

WHY THIS IS THE DANGEROUS DIRECTION TO GET WRONG.

Both failures are real and only one is safe. A ceiling that refuses a provider
nobody declared stops a feature loudly - that happened to `aiark`'s contact
fallback and `blitz`'s headcount lookup, and five green end-to-end tests went
red within the hour, which is how it was found. A ceiling that ALLOWS a
provider nobody declared spends the client's money with no bound at all and
nothing goes red, ever.

So the refusal is deliberate and this test exists to keep it deliberate. If a
future change makes an unknown provider fall through to "no ceiling applies",
this is the test that must fail.

THE DISTINCTION THAT MAKES IT WORKABLE.

`unlimited` is a DECLARATION. `blitz` carries `total: unlimited` because the
operator decided no ceiling applies to it, and that is a different statement
from a provider nobody has thought about. Both produce `None` caps, so the
caps alone cannot tell them apart - `provider_names()` is what does.
"""
import unittest

from src import clients, spendledger


class AnUndeclaredProviderIsRefused(unittest.TestCase):

    def setUp(self):
        self.config = clients.load("productive")

    # -- the declarations themselves -------------------------------------

    def test_every_model_provider_is_declared(self):
        declared = set(spendledger.provider_names(self.config))
        for provider in ("anthropic", "groq", "openrouter"):
            with self.subTest(provider=provider):
                self.assertIn(provider, declared)

    def test_model_ceilings_are_denominated_in_micro_dollars(self):
        # A number here is not credits and must never be summed with one.
        for provider in ("anthropic", "groq", "openrouter"):
            with self.subTest(provider=provider):
                self.assertEqual(spendledger.unit_for(provider), "microusd")

    def test_the_declared_daily_ceilings_are_the_operators_numbers(self):
        expected = {"anthropic": 50_000_000,   # $50
                    "groq": 10_000_000,        # $10
                    "openrouter": 20_000_000}  # $20
        for provider, per_day in expected.items():
            with self.subTest(provider=provider):
                caps = spendledger.provider_caps(self.config, provider)
                self.assertEqual(caps["per_day"], per_day)

    # -- the refusal -----------------------------------------------------

    def test_check_refuses_a_provider_nobody_declared(self):
        with self.assertRaises(Exception) as caught:
            spendledger.check(client="productive", config=self.config,
                              cost=1, provider="a-provider-nobody-declared")
        # Not merely "it raised": it must raise ABOUT the missing ceiling,
        # not about a budget being exceeded or a malformed argument.
        self.assertIn("ceiling", str(caught.exception).lower())

    def test_the_refusal_names_a_missing_ceiling_specifically(self):
        # `MissingCeiling` SUBCLASSES `BudgetExceeded` deliberately, so the
        # 27 existing `except BudgetExceeded` sites keep catching it. The
        # distinction that matters is the type, not the absence of a base.
        self.assertTrue(issubclass(spendledger.MissingCeiling,
                                   spendledger.BudgetExceeded))
        with self.assertRaises(spendledger.MissingCeiling):
            spendledger.check(client="productive", config=self.config,
                              cost=1, provider="still-not-declared")

    @unittest.skip(
        "CONFLICTS WITH A DELIBERATE, TESTED DECISION - operator to settle. "
        "The operator's wording is 'undeclared provider = check() refuses, "
        "never silently allows'. But `test_a_free_call_is_not_refused_for_"
        "want_of_a_ceiling` asserts the opposite for zero-cost calls, on the "
        "reasoning that a free probe (people-count) is what DECIDES whether "
        "to buy, and refusing it disables the free-first waterfall. Making "
        "this pass breaks five existing tests. Left skipped and visible "
        "rather than silently dropped, or silently overriding a decision "
        "somebody made on purpose.")
    def test_a_zero_cost_call_is_refused_too(self):
        with self.assertRaises(spendledger.MissingCeiling):
            spendledger.check(client="productive", config=self.config,
                              cost=0, provider="free-but-undeclared")

    # -- declared-unlimited is NOT undeclared ----------------------------

    def test_declared_unlimited_is_allowed(self):
        # blitz carries `total: unlimited` because the operator decided no
        # ceiling applies. That must keep working.
        spendledger.check(client="productive", config=self.config,
                          cost=1, provider="blitz")

    def test_unlimited_and_undeclared_are_distinguishable(self):
        # Their CAPS are identical - all None - so anything reasoning from
        # caps alone cannot tell a decision from an oversight.
        declared = set(spendledger.provider_names(self.config))
        self.assertIn("blitz", declared)
        self.assertNotIn("a-provider-nobody-declared", declared)

        blitz = spendledger.provider_caps(self.config, "blitz")
        unknown = spendledger.provider_caps(self.config, "nobody")
        self.assertEqual(blitz["total"], unknown["total"])  # both None

    def test_a_declared_provider_with_a_real_ceiling_is_allowed_under_it(self):
        spendledger.check(client="productive", config=self.config,
                          cost=1, provider="anthropic")


if __name__ == "__main__":
    unittest.main()
