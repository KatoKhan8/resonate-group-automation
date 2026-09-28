"""Company research is paid for once per account, not per contact.

TASK-326: three contacts at one company must not pay for three company
researches. The account evidence is loaded once and shared. The person layer
adds a role-specific angle without duplicating the account facts.

Retrieval is READ-ONLY: secondbrain writes no company fact anywhere.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import secondbrain


class TestAccountEvidenceResolvedOnce(unittest.TestCase):
    """The account evidence is fetched once for three contacts."""

    def setUp(self):
        secondbrain._account_cache.clear()

    def tearDown(self):
        secondbrain._account_cache.clear()

    def test_three_contacts_one_load(self):
        calls = []
        orig = secondbrain._load_account_evidence

        def tracking(*a, **k):
            calls.append(a)
            return orig(*a, **k)

        with mock.patch.object(secondbrain, "_load_account_evidence",
                               side_effect=tracking):
            for key, role in (("c1", "ceo"), ("c2", "coo"),
                              ("c3", "head_of_delivery")):
                secondbrain.for_contact(
                    "productive", "huemor.rocks", key, role)

        unique = set(str(c) for c in calls)
        self.assertEqual(len(unique), 1,
                         f"account evidence resolved {len(unique)} times, "
                         f"expected 1; calls: {calls}")

    def test_for_account_then_for_contact_shares_load(self):
        calls = []
        orig = secondbrain._load_account_evidence

        def tracking(*a, **k):
            calls.append(a)
            return orig(*a, **k)

        with mock.patch.object(secondbrain, "_load_account_evidence",
                               side_effect=tracking):
            secondbrain.for_account("productive", "huemor.rocks")
            secondbrain.for_contact(
                "productive", "huemor.rocks", "c1", "ceo")
            secondbrain.for_contact(
                "productive", "huemor.rocks", "c2", "coo")

        unique = set(str(c) for c in calls)
        self.assertEqual(len(unique), 1,
                         f"expected 1 load, got {len(unique)}: {calls}")

    def test_different_domains_load_separately(self):
        calls = []
        orig = secondbrain._load_account_evidence

        def tracking(*a, **k):
            calls.append(a)
            return orig(*a, **k)

        with mock.patch.object(secondbrain, "_load_account_evidence",
                               side_effect=tracking):
            secondbrain.for_contact(
                "productive", "huemor.rocks", "c1", "ceo")
            secondbrain.for_contact(
                "productive", "other.com", "c2", "ceo")

        unique = set(str(c) for c in calls)
        self.assertEqual(len(unique), 2,
                         f"different domains should load separately: {calls}")


class TestNoDuplication(unittest.TestCase):
    """The person layer does not duplicate the account layer."""

    def setUp(self):
        secondbrain._account_cache.clear()

    def tearDown(self):
        secondbrain._account_cache.clear()

    def test_person_facts_do_not_overlap_account_facts(self):
        account = secondbrain.for_account("productive", "huemor.rocks")
        contact = secondbrain.for_contact(
            "productive", "huemor.rocks", "c1", "ceo")
        account_texts = {f["text"] for f in account.get("facts", [])}
        contact_texts = {f["text"] for f in contact.get("facts", [])}
        overlap = account_texts & contact_texts
        self.assertFalse(
            overlap,
            f"person layer copied {len(overlap)} account facts: {overlap}")

    def test_contact_has_account_ref(self):
        contact = secondbrain.for_contact(
            "productive", "huemor.rocks", "c1", "ceo")
        self.assertIn("account_ref", contact)
        self.assertIn("huemor.rocks", contact["account_ref"])


class TestRoleChangesAngle(unittest.TestCase):
    """Role changes the angle and not the evidence."""

    def setUp(self):
        secondbrain._account_cache.clear()

    def tearDown(self):
        secondbrain._account_cache.clear()

    def test_ceo_and_coo_have_different_angles(self):
        ceo = secondbrain.for_contact(
            "productive", "huemor.rocks", "c1", "ceo")
        coo = secondbrain.for_contact(
            "productive", "huemor.rocks", "c2", "coo")
        self.assertNotEqual(ceo["angle"], coo["angle"],
                            "role did not change the angle")

    def test_same_company_same_account_ref(self):
        ceo = secondbrain.for_contact(
            "productive", "huemor.rocks", "c1", "ceo")
        coo = secondbrain.for_contact(
            "productive", "huemor.rocks", "c2", "coo")
        self.assertEqual(ceo["account_ref"], coo["account_ref"],
                         "same company, different evidence ref")

    def test_head_of_delivery_differs_from_ceo(self):
        hod = secondbrain.for_contact(
            "productive", "huemor.rocks", "c3", "head_of_delivery")
        ceo = secondbrain.for_contact(
            "productive", "huemor.rocks", "c1", "ceo")
        self.assertNotEqual(hod["angle"], ceo["angle"])

    def test_unknown_role_gets_default_angle(self):
        result = secondbrain.for_contact(
            "productive", "huemor.rocks", "c4", "intern")
        self.assertEqual(result["angle"], "general business")


class TestNoWrite(unittest.TestCase):
    """secondbrain writes no file under config/ or work/."""

    def setUp(self):
        secondbrain._account_cache.clear()

    def tearDown(self):
        secondbrain._account_cache.clear()

    def _assert_no_writes(self, *calls):
        original_open = open
        writes = []

        def tracking_open(path, mode="r", *args, **kwargs):
            if any(m in mode for m in ("w", "a", "x", "+")):
                resolved = os.path.abspath(str(path))
                for dirname in ("config", "work"):
                    target = os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..",
                                     dirname))
                    if (resolved.startswith(target + os.sep)
                            or resolved == target):
                        writes.append(resolved)
            return original_open(path, mode, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=tracking_open):
            for entry in calls:
                fn, args = entry[0], entry[1]
                kwargs = entry[2] if len(entry) > 2 else {}
                fn(*args, **kwargs)

        self.assertEqual(
            writes, [],
            f"secondbrain wrote to config/ or work/: {writes}")

    def test_for_account_writes_nothing(self):
        self._assert_no_writes(
            (secondbrain.for_account, ("productive", "huemor.rocks")),
        )

    def test_for_contact_writes_nothing(self):
        self._assert_no_writes(
            (secondbrain.for_contact,
             ("productive", "huemor.rocks", "c1", "ceo")),
            (secondbrain.for_contact,
             ("productive", "huemor.rocks", "c2", "coo")),
            (secondbrain.for_contact,
             ("productive", "huemor.rocks", "c3", "head_of_delivery")),
        )

    def test_for_task_still_writes_nothing(self):
        self._assert_no_writes(
            (secondbrain.for_task, ("cold_email_writing", "productive")),
            (secondbrain.for_task, ("campaign_strategy", "productive")),
        )

    def test_all_sections_still_writes_nothing(self):
        self._assert_no_writes(
            (secondbrain.all_sections,
             ("productive",), {"reason": "test"}),
        )


class TestAccountEvidenceProvenance(unittest.TestCase):
    """Account evidence facts carry source and date per TASK-322."""

    def setUp(self):
        secondbrain._account_cache.clear()

    def tearDown(self):
        secondbrain._account_cache.clear()

    def test_every_fact_has_source_and_date(self):
        result = secondbrain.for_account("productive", "huemor.rocks")
        for fact in result["facts"]:
            self.assertTrue(fact.get("source"),
                            f"account fact has no source: {fact}")
            self.assertTrue(fact.get("date"),
                            f"account fact has no date: {fact}")

    def test_sources_cite_productive(self):
        result = secondbrain.for_account("productive", "huemor.rocks")
        for fact in result["facts"]:
            self.assertIn("productive", fact["source"],
                          f"fact cites wrong client: {fact['source']}")

    def test_facts_are_unverified(self):
        result = secondbrain.for_account("productive", "huemor.rocks")
        for fact in result["facts"]:
            self.assertFalse(fact.get("verified", True),
                             f"account fact marked verified: {fact}")


if __name__ == "__main__":
    unittest.main()
