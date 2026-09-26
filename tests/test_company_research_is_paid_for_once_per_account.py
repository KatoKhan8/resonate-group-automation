"""Company research is fetched once per account and reused across contacts.

TASK-326: three contacts at one company must not pay for three company
researches. The account evidence is loaded once, cached, and the person
layer references it without copying.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import secondbrain


def _clear_cache():
    secondbrain._account_evidence_cache.clear()


class TestAccountEvidenceFetchedOnce(unittest.TestCase):
    """Account evidence is resolved once for multiple contacts."""

    def setUp(self):
        _clear_cache()

    def tearDown(self):
        _clear_cache()

    def test_three_contacts_one_load(self):
        calls = []
        orig = secondbrain._load_account_evidence

        def spy(*a, **k):
            calls.append(a)
            return orig(*a, **k)

        with mock.patch.object(secondbrain, "_load_account_evidence",
                               side_effect=spy):
            for k, r in (('c1', 'ceo'), ('c2', 'coo'),
                         ('c3', 'head_of_delivery')):
                secondbrain.for_contact('productive', 'huemor.rocks', k, r)

        unique = set(map(str, calls))
        self.assertEqual(len(unique), 1,
                         f"account evidence resolved {len(unique)} times, "
                         f"expected 1: {calls}")

    def test_for_account_returns_same_as_for_contact_reference(self):
        acct = secondbrain.for_account('productive', 'huemor.rocks')
        contact = secondbrain.for_contact(
            'productive', 'huemor.rocks', 'c1', 'ceo')
        self.assertEqual(acct['domain'], 'huemor.rocks')
        self.assertEqual(contact['account_ref'], 'productive:huemor.rocks')

    def test_different_domains_are_separate(self):
        _clear_cache()
        secondbrain.for_account('productive', 'huemor.rocks')
        secondbrain.for_account('productive', 'example.com')
        self.assertEqual(len(secondbrain._account_evidence_cache), 2)


class TestNoDuplication(unittest.TestCase):
    """Person layer does not copy account facts."""

    def setUp(self):
        _clear_cache()

    def tearDown(self):
        _clear_cache()

    def test_no_fact_overlap(self):
        acct = secondbrain.for_account('productive', 'huemor.rocks')
        contact = secondbrain.for_contact(
            'productive', 'huemor.rocks', 'c1', 'ceo')
        acct_vals = {f['value'] for f in acct.get('facts', [])}
        contact_vals = {f['value'] for f in contact.get('facts', [])}
        overlap = acct_vals & contact_vals
        self.assertFalse(
            overlap,
            f"person layer copied {len(overlap)} account facts: {overlap}")

    def test_account_has_facts(self):
        acct = secondbrain.for_account('productive', 'huemor.rocks')
        self.assertTrue(len(acct['facts']) > 0,
                        "account evidence should have at least one fact")

    def test_contact_facts_are_empty(self):
        contact = secondbrain.for_contact(
            'productive', 'huemor.rocks', 'c1', 'ceo')
        self.assertEqual(contact['facts'], [],
                         "person layer carries no facts of its own")


class TestRoleShapesAngle(unittest.TestCase):
    """Role changes the angle, not the evidence."""

    def setUp(self):
        _clear_cache()

    def tearDown(self):
        _clear_cache()

    def test_ceo_and_coo_differ(self):
        x = secondbrain.for_contact(
            'productive', 'huemor.rocks', 'c1', 'ceo')
        y = secondbrain.for_contact(
            'productive', 'huemor.rocks', 'c2', 'coo')
        self.assertNotEqual(x['angle'], y['angle'],
                            "role did not change the angle")

    def test_same_account_ref(self):
        x = secondbrain.for_contact(
            'productive', 'huemor.rocks', 'c1', 'ceo')
        y = secondbrain.for_contact(
            'productive', 'huemor.rocks', 'c2', 'coo')
        self.assertEqual(x['account_ref'], y['account_ref'],
                         "same company, different evidence ref")

    def test_head_of_delivery_differs_from_ceo(self):
        x = secondbrain.for_contact(
            'productive', 'huemor.rocks', 'c1', 'ceo')
        z = secondbrain.for_contact(
            'productive', 'huemor.rocks', 'c3', 'head_of_delivery')
        self.assertNotEqual(x['angle'], z['angle'])

    def test_unknown_role_gets_generic_angle(self):
        w = secondbrain.for_contact(
            'productive', 'huemor.rocks', 'c4', 'intern')
        self.assertIn('intern', w['angle'])


class TestProvenanceStillHolds(unittest.TestCase):
    """TASK-322's provenance guard still holds after account-scoped retrieval."""

    def setUp(self):
        _clear_cache()

    def tearDown(self):
        _clear_cache()

    def test_account_facts_have_source_and_date(self):
        acct = secondbrain.for_account('productive', 'huemor.rocks')
        for fact in acct['facts']:
            self.assertTrue(fact.get('source'),
                            f"account fact has no source: {fact}")
            self.assertTrue(fact.get('date'),
                            f"account fact has no date: {fact}")

    def test_account_facts_cite_correct_client(self):
        acct = secondbrain.for_account('productive', 'huemor.rocks')
        for fact in acct['facts']:
            self.assertIn('productive', fact['source'],
                          f"fact cites wrong client: {fact['source']}")

    def test_account_facts_are_unverified(self):
        acct = secondbrain.for_account('productive', 'huemor.rocks')
        for fact in acct['facts']:
            self.assertFalse(fact.get('verified', True),
                             f"fact marked verified but nothing verified it")


class TestNoWrite(unittest.TestCase):
    """secondbrain writes no file under config/ or work/."""

    def setUp(self):
        _clear_cache()

    def tearDown(self):
        _clear_cache()

    def test_no_write_to_config_or_work(self):
        original_open = open
        writes = []

        def tracking_open(path, mode="r", *args, **kwargs):
            if any(m in mode for m in ("w", "a", "x", "+")):
                resolved = os.path.abspath(str(path))
                root = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), ".."))
                for subdir in ("config", "work"):
                    target = os.path.join(root, subdir)
                    if (resolved.startswith(target + os.sep)
                            or resolved == target):
                        writes.append(resolved)
            return original_open(path, mode, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=tracking_open):
            secondbrain.for_account("productive", "huemor.rocks")
            secondbrain.for_contact(
                "productive", "huemor.rocks", "c1", "ceo")
            secondbrain.for_task("cold_email_writing", "productive")
            secondbrain.all_sections("productive", reason="test")

        self.assertEqual(writes, [],
                         f"secondbrain wrote to protected dir: {writes}")


class TestExistingForTaskUnchanged(unittest.TestCase):
    """The existing for_task API still works after account-scoped additions."""

    def test_for_task_still_returns_text_key(self):
        result = secondbrain.for_task("cold_email_writing", "productive")
        for section, facts in result.items():
            for fact in facts:
                self.assertIn("text", fact,
                              f"for_task fact lost its 'text' key in "
                              f"{section}")

    def test_for_task_sections_unchanged(self):
        result = secondbrain.for_task("cold_email_writing", "productive")
        expected = {"profile", "customers", "messaging", "offers"}
        self.assertEqual(set(result.keys()), expected)


if __name__ == "__main__":
    unittest.main()
