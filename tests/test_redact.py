"""Tests for src/redact.py.

Assert on returned values, not source text.  No real PII appears below -
record ids use the pseudonym shape (fictional companies) and forbidden
tokens are the project's existing FORBIDDEN_NAMES list, which is already
tracked in git as infrastructure.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.redact import redact, _hash_token, RECORD_PSEUDO, FORBIDDEN_PSEUDO


class TestRedactForbiddenTokens(unittest.TestCase):
    """The forbidden-token list comes from the hygiene guard.  A forbidden
    name in report text must become a pseudonym, not survive intact."""

    def test_forbidden_name_is_replaced(self):
        result = redact("contact mahovic about the deal")
        self.assertNotIn("mahovic", result.lower())
        self.assertIn("<redacted-", result)

    def test_forbidden_domain_is_replaced(self):
        result = redact("the client at arbona.hr responded")
        self.assertNotIn("arbona.hr", result.lower())

    def test_forbidden_figure_is_replaced(self):
        result = redact("the estate has 189,683 contacts")
        self.assertNotIn("189,683", result)

    def test_case_insensitive_match(self):
        result = redact("Contact MAHOVIC about the deal")
        self.assertNotIn("mahovic", result.lower())

    def test_clean_text_unchanged(self):
        text = "40 of the 70 overlap, with 12 new records"
        self.assertEqual(redact(text, record_ids=()), text)

    def test_empty_input(self):
        self.assertEqual(redact(""), "")
        self.assertIsNone(redact(None))


class TestRedactRecordIds(unittest.TestCase):
    """Record ids use fictional companies.  No real identifier below."""

    def test_record_id_replaced(self):
        result = redact("record acme-corp was enriched",
                        record_ids=["acme-corp"])
        self.assertNotIn("acme-corp", result)
        self.assertIn("<record-", result)

    def test_stable_pseudonym(self):
        text = "acme-corp was enriched. acme-corp has 3 contacts."
        result = redact(text, record_ids=["acme-corp"])
        pseudos = [m for m in __import__("re").finditer(
            r"<record-[a-f0-9]+>", result)]
        self.assertEqual(len(pseudos), 2)
        self.assertEqual(pseudos[0].group(), pseudos[1].group())

    def test_different_ids_different_pseudonyms(self):
        text = "acme-corp and globex-inc both enriched"
        result = redact(text, record_ids=["acme-corp", "globex-inc"])
        self.assertNotIn("acme-corp", result)
        self.assertNotIn("globex-inc", result)
        pseudos = set(__import__("re").findall(r"<record-[a-f0-9]+>", result))
        self.assertEqual(len(pseudos), 2)

    def test_multiple_mentions_same_pseudonym(self):
        text = "acme-corp first. acme-corp second. acme-corp third."
        result = redact(text, record_ids=["acme-corp"])
        pseudos = __import__("re").findall(r"<record-[a-f0-9]+>", result)
        self.assertEqual(len(pseudos), 3)
        self.assertEqual(len(set(pseudos)), 1)

    def test_empty_record_ids_still_redacts_forbidden(self):
        result = redact("mahovic at acme-corp", record_ids=())
        self.assertNotIn("mahovic", result.lower())
        self.assertIn("acme-corp", result)

    def test_longer_token_wins_over_shorter(self):
        """A forbidden name that is a prefix of a record id must not corrupt
        the record-id replacement by matching first."""
        from tests.test_fixture_hygiene import FORBIDDEN_NAMES
        name = "arbona"
        self.assertIn(name, FORBIDDEN_NAMES)
        rid = "arbona-com"
        result = redact(f"record {rid} was processed", record_ids=[rid])
        self.assertNotIn(rid, result)
        self.assertNotIn(name, result.lower())
        pseudos = __import__("re").findall(r"<record-[a-f0-9]+>", result)
        self.assertEqual(len(pseudos), 1)


class TestRedactMeaningPreserved(unittest.TestCase):
    """Redaction must not destroy the numbers and structure a report needs."""

    def test_numbers_and_counts_preserved(self):
        text = "40 of the 70 overlap, with 12 new records"
        result = redact(text, record_ids=["acme-corp"])
        self.assertIn("40", result)
        self.assertIn("70", result)
        self.assertIn("12", result)

    def test_structure_preserved_with_record_id(self):
        text = "acme-corp: 5 contacts, 3 verified, 2 pending"
        result = redact(text, record_ids=["acme-corp"])
        self.assertIn("5 contacts", result)
        self.assertIn("3 verified", result)
        self.assertIn("2 pending", result)
        self.assertNotIn("acme-corp", result)

    def test_pseudonym_format_record(self):
        result = redact("acme-corp", record_ids=["acme-corp"])
        self.assertRegex(result, r"^<record-[a-f0-9]{8}>$")

    def test_pseudonym_format_forbidden(self):
        result = redact("mahovic")
        self.assertRegex(result, r"^<redacted-[a-f0-9]{8}>$")


class TestHashToken(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(_hash_token("acme-corp"), _hash_token("acme-corp"))

    def test_different_inputs_different_hashes(self):
        self.assertNotEqual(_hash_token("acme-corp"),
                            _hash_token("globex-inc"))

    def test_length(self):
        self.assertEqual(len(_hash_token("anything")), 8)


class TestRedactWiredThroughOutcomesRender(unittest.TestCase):
    """'Existence is not function' - prove outcomes.render() actually calls
    redact.  Drive through the real entry point with a known record id and
    check the rendered output does not contain it raw.

    If this test passes after someone removes the redact() call from
    outcomes.render(), the test is not testing the wiring.  To verify:
    delete the redact() call in outcomes.render() and re-run.  This test
    must fail.
    """

    def _fake_report(self):
        return {
            "client": "test",
            "at": "2026-09-15T00:00:00",
            "stages": [],
            "campaigns": [{
                "campaign_id": "test-campaign",
                "status": "active",
                "records": 1,
                "bison_campaign_id": None,
                "heyreach_campaign_id": None,
            }],
            "campaign_disagreements": [{
                "campaign_id": "test-campaign",
                "local_status": "active",
                "provider": "bison",
                "provider_status": "paused",
                "provider_observed_at": "2026-09-15",
            }],
            "senders": {
                "email_sender_count": 1,
                "seat_count": 2,
            },
            "safety": {
                "kill_switch": {"sending": False},
                "incidents": [],
                "campaigns_paused": [],
                "accounts_held": [],
            },
            "observations": {
                "actions": 0,
                "attributable": 0,
                "missing": {},
            },
            "questions": [],
            "bugs": {"why": "test"},
            "replays": {"why": "test"},
        }

    def test_render_redacts_record_ids_when_passed(self):
        """render(report, record_ids=[...]) must replace those ids in output.

        Drives through the real render() entry point.  The record id is in
        the campaign_id field, which render() formats into its output.  If
        redact() is removed from render(), this test fails because the id
        survives intact."""
        from src.outcomes import render
        sentinel = "wiring-test-id-abc123"
        report = self._fake_report()
        report["campaigns"][0]["campaign_id"] = sentinel
        output = render(report, record_ids=[sentinel])
        self.assertNotIn(sentinel, output,
                         "record id survived render() - redact() wiring "
                         "is not connected.  To verify: delete the redact() "
                         "call in outcomes.render() and re-run this test.")

    def test_render_unchanged_without_record_ids(self):
        """Without record_ids, render() still works and preserves content."""
        from src.outcomes import render
        report = self._fake_report()
        output = render(report)
        self.assertIn("test-campaign", output)
        self.assertIn("PRODUCTION RUN", output)


if __name__ == "__main__":
    unittest.main()
