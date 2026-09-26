"""A demotion carries its own expiry and stops applying after it.

BUGGIE finding M5, 2026-09-26: `WARNING_RULES` demoted `step1_without_pack_fact`
from refuse to warn under an operator directive "explicitly time-boxed to
2026-09-28", with no date check and no automatic reversion. After the deadline
the rule kept warning instead of refusing, silently, until a human remembered
to edit the frozenset.

The fix: demotions are data, not a hardcoded `if` on today's date. Each demotion
is `(rule, until_date, why, who_granted)` and stops applying the day after its
deadline. The next demotion is recorded the same way and is equally visible.

## WHAT THIS TEST PROVES

1. Before the expiry date, the rule warns (does not refuse).
2. After the expiry date, the rule REFUSES. This is the whole point.
3. A real lint call at a date sees the correct behaviour - not a table lookup,
   but an actual `check_batch` call that refuses after expiry.
4. The expiry is mechanical: no human has to remember to edit anything.
"""
import unittest

from src import copylint


class ADemotionCarriesItsOwnExpiry(unittest.TestCase):
    """The demotion table is data, and the expiry is evaluated at call time."""

    def test_before_expiry_the_rule_warns(self):
        """On 2026-09-27, the demotion is still active."""
        rules = copylint.warning_rules(today='2026-09-27')
        self.assertIn('step1_without_pack_fact', rules)

    def test_on_expiry_date_the_rule_still_warns(self):
        """On 2026-09-28, the demotion is still active (through the date)."""
        rules = copylint.warning_rules(today='2026-09-28')
        self.assertIn('step1_without_pack_fact', rules)

    def test_after_expiry_the_rule_is_absent(self):
        """On 2026-09-29, the demotion has expired and the rule reverts to refusing."""
        rules = copylint.warning_rules(today='2026-09-29')
        self.assertNotIn('step1_without_pack_fact', rules,
                         'demotion survived its own deadline')

    def test_the_expiry_is_data_not_a_hardcoded_if(self):
        """DEMOTIONS is a tuple of (rule, until_date, why, who_granted).
        The next demotion is recorded the same way."""
        self.assertIsInstance(copylint.DEMOTIONS, tuple)
        for entry in copylint.DEMOTIONS:
            self.assertEqual(len(entry), 4,
                             'each demotion is (rule, until_date, why, who_granted)')
            rule, until, why, who = entry
            self.assertIsInstance(rule, str)
            self.assertIsInstance(until, str)
            self.assertRegex(until, r'^\d{4}-\d{2}-\d{2}$')
            self.assertIsInstance(why, str)
            self.assertIsInstance(who, str)


class ARealLintCallSeesTheExpiry(unittest.TestCase):
    """Not a table lookup - an actual check_batch call at a date."""

    def _lead_with_no_pack(self):
        """A lead that fires step1_without_pack_fact and no other rule."""
        return {
            'id': 'test-1',
            'steps': [
                {'body': 'Writing about your team.'},
                {'body': 'Step 2 body with enough length to be real.'},
                {'body': 'Step 3 body with enough length to be real.'},
                {'body': 'Step 4 body with enough length to be real.'},
                {'body': 'Step 5 body with enough length to be real.'},
            ]
        }

    def test_before_expiry_the_batch_warns_not_refuses(self):
        lead = self._lead_with_no_pack()
        report = copylint.check_batch([lead], packs={}, today='2026-09-27')
        self.assertFalse(report['refused'],
                         'before expiry, step1_without_pack_fact warns, does not refuse')
        self.assertEqual(report['warned'], 1)
        self.assertIn('step1_without_pack_fact', report['warning_rules'])

    def test_after_expiry_the_batch_refuses(self):
        """THIS IS THE WHOLE POINT. After 2026-09-28, the rule reverts to refusing."""
        lead = self._lead_with_no_pack()
        report = copylint.check_batch([lead], packs={}, today='2026-09-29')
        self.assertTrue(report['refused'],
                        'after expiry, step1_without_pack_fact REFUSES - '
                        'the demotion has expired and the rule is back to its normal state')
        self.assertEqual(report['warned'], 0)
        self.assertNotIn('step1_without_pack_fact', report['warning_rules'])

    def test_the_counts_are_the_same_both_ways(self):
        """The rule fires in both cases; only the verdict changes."""
        lead = self._lead_with_no_pack()
        before = copylint.check_batch([lead], packs={}, today='2026-09-27')
        after = copylint.check_batch([lead], packs={}, today='2026-09-29')
        self.assertEqual(before['counts']['step1_without_pack_fact'], 1)
        self.assertEqual(after['counts']['step1_without_pack_fact'], 1)
        self.assertEqual(before['counts'], after['counts'],
                         'the rule fires identically; only refused/warned differs')


class TheWarningRulesFunctionIsTheEntryPoints(unittest.TestCase):
    """warning_rules(today=...) is the public API, not WARNING_RULES."""

    def test_warning_rules_accepts_a_date_string(self):
        rules = copylint.warning_rules(today='2026-09-27')
        self.assertIsInstance(rules, frozenset)

    def test_warning_rules_defaults_to_today_when_omitted(self):
        """Omitting today uses the current date. We cannot assert the value
        without knowing today, but we can assert it returns a frozenset."""
        rules = copylint.warning_rules()
        self.assertIsInstance(rules, frozenset)

    def test_an_expired_demotion_is_absent_from_the_set(self):
        """A demotion that has passed its deadline is not in the set."""
        rules = copylint.warning_rules(today='2030-01-01')
        self.assertEqual(rules, frozenset(),
                         'all current demotions have expired by 2030')


if __name__ == "__main__":
    unittest.main()
