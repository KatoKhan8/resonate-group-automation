"""A lead whose copy was approved but never written is named, not passed.

`compare_bison`'s per-lead comparison has two failure directions. A lead
whose variables DIFFER is covered (the tampering tests). A lead who is
MISSING entirely - approved here, absent from the provider's campaign
members - is not: that is the half-staged state, and it is the exact shape
of the 09-23 incident's cause, words that were never written being treated
as though they were.

The set comparison does catch the absence today, but it cannot say WHAT is
missing - only that the sets differ. The copy gate names the contact by
hashed email and says the copy is MISSING at provider. That name is the
difference between a report somebody can act on and one they have to
re-derive; and it is the branch that survives any future loosening of the
set comparison (heyreach's staging flow already compares lead_set
directionally, so the precedent exists in this file).

If the copy gate skipped leads it cannot find at the provider, the missing
name would disappear from every readback while the incident's shape - a
lead approved here and silent there - stayed exactly as dangerous.
"""
import unittest

from src import campaigns, configdiff, store
from tests.test_compare_bison import CID, CONFIG, _Base


class AnAbsentLeadsCopyIsNamedNotPassed(_Base):

    def test_an_approved_lead_absent_at_the_provider_is_named(self):
        self._setup_provider_match()
        # Bob was approved here but never staged at the provider: the
        # campaign's members hold Alice only. Whatever else this readback
        # reports, it must name Bob's missing copy - the one entry that
        # says WHO is absent, which the set mismatches never do.
        self.fb.members[501] = self.fb.members[501][:1]

        readback = configdiff.compare_bison(
            campaigns.require(CID, list(campaigns.load())),
            recs=list(store.load()), config=CONFIG, expect_workspace=10)

        bob = configdiff._hash_email("bob@example.org")
        self.assertIn(
            f"lead_copy:{bob}: MISSING at provider",
            list(readback.failures),
            "an approved lead absent at the provider passed the copy gate "
            f"without being named; failures were: {readback.failures}")


if __name__ == "__main__":
    unittest.main()
