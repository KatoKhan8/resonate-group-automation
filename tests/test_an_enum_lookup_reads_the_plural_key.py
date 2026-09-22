"""AI Ark's lookup tools answer under the PLURAL catalogue name.

`_lookup` tried "results", "items", the SINGULAR catalogue name and "data",
and the live tools answer under `locations`, `industries` and `technologies`.
So every lookup returned `[]`, `_guard_enums` then refused every enum value as
"not returned by its lookup", and every enum-filtered search was unreachable.

Nightly sourcing is where that surfaced: it catches ProviderError around its
paged search and breaks, so an unusable `companyLocation` read as "the
provider has no companies" and the stage reported zero with no error at all.
"""
import unittest
from unittest import mock

from src.providers import aiark
from src.providers import ProviderError


class TheLookupReadsThePluralKey(unittest.TestCase):

    def setUp(self):
        aiark.reset_validated()

    def _lookup_returning(self, payload, term="United Kingdom"):
        with mock.patch.object(aiark, "call_tool", return_value=payload):
            return aiark.location_search(term)

    def test_the_live_shape_is_read(self):
        """The exact body location_search returned on 2026-09-22."""
        out = self._lookup_returning(
            {"matched": 4, "total": 5101,
             "locations": ["United States", "United Kingdom"]})
        self.assertEqual(out, ["United States", "United Kingdom"])

    def test_industries_and_technologies_are_plural_too(self):
        aiark.reset_validated()
        with mock.patch.object(aiark, "call_tool",
                               return_value={"industries": ["software"]}):
            self.assertEqual(aiark.industry_search("software"), ["software"])
        with mock.patch.object(aiark, "call_tool",
                               return_value={"technologies": ["hubspot"]}):
            self.assertEqual(aiark.technology_search("hubspot"), ["hubspot"])

    def test_a_looked_up_value_then_passes_the_enum_guard(self):
        """The whole point: the lookup is what licenses the search filter."""
        self._lookup_returning({"locations": ["United Kingdom"]})
        aiark._guard_enums({"companyLocation": "United Kingdom"})   # no raise

    def test_an_unlooked_value_still_refuses(self):
        """The guard is not weakened by the fix."""
        with self.assertRaises(aiark.EnumNotLookedUp):
            aiark._guard_enums({"companyLocation": "Atlantis"})

    def test_an_unknown_shape_raises_rather_than_reading_as_empty(self):
        """A 200 whose body this does not understand is a contract change.

        Returning [] for it is exactly what hid the defect: an empty catalogue
        and a renamed key are indistinguishable to every caller.
        """
        with self.assertRaises(ProviderError):
            self._lookup_returning({"matched": 4, "total": 5101,
                                    "somethingElse": ["United Kingdom"]})

    def test_the_older_shapes_still_work(self):
        """`results` and a list of dicts with `name` are still accepted."""
        self.assertEqual(
            self._lookup_returning({"results": [{"name": "United Kingdom"}]}),
            ["United Kingdom"])


if __name__ == "__main__":
    unittest.main()
