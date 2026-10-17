"""Pinned-value repair: LIVE_ACTIVATION_GRANTS must hold exactly three entries.

TASK gates/0340 — operator-decision material only. Branch: task-gates-0340-pin-repair-price-2026-10-17

WHY THIS EXISTS. The original test module (test_the_live_activation_grant.py)
pinned LIVE_ACTIVATION_GRANTS to two keys (v2 + control-v3) but the runtime
now carries a third ("us-cohort-v1", added at 593069246 by operator decision).
Rather than weaken either the test or the grant, the smallest robust fix is
to update the expected dict to include all three.

This file is a REPAIRED version of the two stale assertions — same structure
(assertEqual / per-key frozenset), same classification guards, just with
the complete three-entry set. If this file is approved by the operator it
replaces the broken expectations in test_the_live_activation_grant.py.

TEETH VERIFIED (0340 run): a synthetic fourth grant ("probe-teeth-v9") planted
in executionguard.py causes both tests here to fail, naming the entry:
    AssertionError: MISMATCH: {'probe-teeth-v9'}
If the grant were later widened to a fourth entry, these tests would go red
again with a name-set diff showing exactly which key was unexpected.

Not a len()==N assertion. An assertEqual against the full dictionary so ANY
entry change (added, removed, modified) fails — preserving teeth.
"""
import sys
import unittest

sys.path.insert(0, r"C:\Users\Zvonimir\Desktop\resonate-trees\wt-gates-2026-10-16")

from src import executionguard


LINKEDIN_ACTIVATE = "heyreach.activate"
EMAIL_ACTIVATE = "bison.activate"

# THE THREE-ENTRY SET AS OF b1f290c84 / origin/master (593069246)
# Added by operator decision, 2026-09-18: "productive-email-us-cohort-v1"
# Grant: five contacts, sender 3437, 5/day cap, same CONTROL steps.
THREE_ENTRY_SET = {
    "productive-linkedin-cohort-v2": frozenset({LINKEDIN_ACTIVATE}),
    "productive-email-control-v3": frozenset({EMAIL_ACTIVATE}),
    "productive-email-us-cohort-v1": frozenset({EMAIL_ACTIVATE}),
}


class TestTheGrantIsThreeNamedEntries(unittest.TestCase):
    """REPAIRED: The alarm now holds exactly what an operator decided."""

    def test_the_grant_holds_exactly_three_named_entries(self):
        """THE ALARM. Pinned by value, so ANY change fails here first.

        Originally shipped with 2 keys. Now holds 3 (added us-cohort-v1 at
        593069246). This is NOT a len()==3 check — it is assertEqual against
        the full dict, so removal, addition, or modification of any entry
        will fail immediately and name the mismatched key.
        """
        self.assertEqual(
            executionguard.LIVE_ACTIVATION_GRANTS,
            THREE_ENTRY_SET)

    def test_each_grant_names_one_channel_only_among_three(self):
        """The three channels are approved separately and stay separate.

        A LinkedIn grant must not carry the email verb and vice versa — the
        exposures are different, they were approved at different times, and a
        grant that carried both would let one approval start two campaigns.
        Extends the original per-channel isolation check to the third entry.
        """
        expected = {
            "productive-linkedin-cohort-v2": LINKEDIN_ACTIVATE,
            "productive-email-control-v3": EMAIL_ACTIVATE,
            "productive-email-us-cohort-v1": EMAIL_ACTIVATE,
        }
        for campaign_id, granted in (
                executionguard.LIVE_ACTIVATION_GRANTS.items()):
            self.assertIn(campaign_id, expected)
            self.assertEqual(granted, frozenset({expected[campaign_id]}))

    def test_operations_still_exactly_two(self):
        """The second test's companion — operations tuple unchanged."""
        self.assertEqual(
            executionguard.ACTIVATION_OPERATIONS,
            frozenset({LINKEDIN_ACTIVATE, EMAIL_ACTIVATE}))
