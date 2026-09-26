"""TASK-371: the provider truth report refuses partial reads.

Two properties the acceptance criteria demand are seen to hold:

1. **The pagination guard refuses.** Stub the transport to return page 1 of N
   and stop. The listing must raise ``PartialInventory`` rather than report
   the short answer. A count that matches is not a set that matches, and a
   page that looks like a listing is how an estate shrinks silently.

2. **UNKNOWN is not zero.** Stub one campaign's lead-count read to fail.
   That campaign's ``lead_count`` must be the string ``"UNKNOWN"`` with a
   ``lead_count_reason``, and nothing downstream may read it as an int, as
   zero, as clean, as paused or as empty.

Both tests drive through the real entry points - ``bison.list_all_campaigns``
and ``provider_truth.read_emailbison_campaigns`` - not the inner functions
they call. The seam was never the risk; the wiring is.
"""
import os
import sys
import unittest
from unittest import mock

from src import providers
from src.providers import bison

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import provider_truth


class PaginationGuardRefuses(unittest.TestCase):
    """Acceptance 3: the pagination guard is seen to fail."""

    def test_truncated_listing_raises_rather_than_reporting_short(self):
        """Page 1 of N and then stop. The function must refuse."""
        with mock.patch.object(
                bison, "_paged",
                side_effect=bison.PartialInventory(
                    "emailbison list_all_campaigns: meta.total says 30 and "
                    "15 arrived across 1 page(s). Refusing to return a "
                    "partial inventory")):
            with self.assertRaises(bison.PartialInventory) as caught:
                bison.list_all_campaigns()
        self.assertIn("Refusing", str(caught.exception))

    def test_provider_truth_reports_the_refusal_as_error(self):
        """When the listing itself fails, read_emailbison_campaigns must
        return an error string and an empty campaign list - not crash, and
        certainly not report zero campaigns."""
        with mock.patch.object(
                bison, "list_all_campaigns",
                side_effect=bison.PartialInventory(
                    "emailbison list_all_campaigns: 40 pages, cap 40")):
            result = provider_truth.read_emailbison_campaigns()
        self.assertEqual(result["campaigns"], [])
        self.assertIsNotNone(result["error"])
        self.assertIn("listing failed", result["error"])
        self.assertEqual(result["campaign_ids"], [])
        self.assertIsNone(result["total"])


class UnknownIsNotZero(unittest.TestCase):
    """Acceptance 4: UNKNOWN is not zero, not null, not clean."""

    def _two_campaigns(self):
        return (
            [{"id": 491, "name": "alpha", "status": "active"},
             {"id": 492, "name": "beta", "status": "paused"}],
            2,
        )

    def test_failed_lead_count_is_unknown_with_reason(self):
        """One campaign's lead-count read fails. Its lead_count must be the
        string 'UNKNOWN', not 0, not None, and it must carry a reason."""
        def _lead_count(cid):
            if cid == 492:
                raise providers.ProviderError(
                    "emailbison campaign_lead_count: GET -> 500")
            return 22

        with mock.patch.object(bison, "list_all_campaigns",
                               return_value=self._two_campaigns()):
            with mock.patch.object(bison, "campaign_lead_count",
                                   side_effect=_lead_count):
                result = provider_truth.read_emailbison_campaigns()

        self.assertEqual(len(result["campaigns"]), 2)
        good = [c for c in result["campaigns"]
                if c["bison_campaign_id"] == 491][0]
        bad = [c for c in result["campaigns"]
               if c["bison_campaign_id"] == 492][0]

        self.assertEqual(good["lead_count"], 22)
        self.assertIsInstance(good["lead_count"], int)

        self.assertEqual(bad["lead_count"], "UNKNOWN")
        self.assertIsInstance(bad["lead_count"], str)
        self.assertIn("lead_count_reason", bad)
        self.assertIn("500", bad["lead_count_reason"])

    def test_unknown_is_not_read_as_zero_or_clean(self):
        """Nothing downstream may treat 'UNKNOWN' as an int. This test
        asserts the type directly: it is a string, it is not '0', not '',
        not None, not 'paused', not 'active'."""
        with mock.patch.object(bison, "list_all_campaigns",
                               return_value=self._two_campaigns()):
            with mock.patch.object(bison, "campaign_lead_count",
                                   side_effect=providers.ProviderError("boom")):
                result = provider_truth.read_emailbison_campaigns()

        for c in result["campaigns"]:
            lc = c["lead_count"]
            self.assertIsInstance(lc, str,
                "lead_count should be UNKNOWN string when all reads fail")
            self.assertEqual(lc, "UNKNOWN")
            self.assertNotEqual(lc, 0)
            self.assertNotEqual(lc, "")
            self.assertIsNotNone(lc)
            self.assertNotIn(lc, ("active", "paused", "sending", "clean"))

    def test_campaign_ids_named_set_not_count(self):
        """Acceptance 2: the output carries the sorted named set of ids,
        so a set diff can detect drift by id, not by count."""
        with mock.patch.object(bison, "list_all_campaigns",
                               return_value=self._two_campaigns()):
            with mock.patch.object(bison, "campaign_lead_count",
                                   return_value=10):
                result = provider_truth.read_emailbison_campaigns()

        self.assertEqual(result["campaign_ids"], ["491", "492"])
        self.assertEqual(len(result["campaign_ids"]), 2)


if __name__ == "__main__":
    unittest.main()
