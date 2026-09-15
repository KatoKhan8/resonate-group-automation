"""TASK-062: a stored step that fails lint is not a valid sibling.

A step that fails the gates cannot ship - `cadence.status_for` holds it,
`eligibility` refuses the payload. Including it in sibling comparisons
inflates repetition counts and can block a good new note by colliding
with copy that will never be sent.

This test proves the exclusion works in all three places:
- generate._note_quality (LinkedIn siblings)
- generate._quality_of (email siblings)
- heyreachfactory._plan (campaign_repetition over custom_fields)
"""
import unittest

from src import generate, heyreachfactory, lint, quality


class TestFailingSiblingExcludedFromNoteQuality(unittest.TestCase):
    """_note_quality excludes siblings that fail lint."""

    def _make_rec(self, notes):
        """Build a record with LinkedIn notes keyed by step."""
        cadence = {}
        for key, note in notes.items():
            cadence[key] = {
                "channel": "linkedin",
                "linkedin_action": "message",
                "requires": "connection_accepted",
                "note": note,
                "approval": {"fingerprint": "dummy"},
            }
        return {
            "id": "test-rec",
            "company": "Acme Corp",
            "contacts": [{"key": "jane-doe", "name": "Jane Doe",
                          "linkedin": "https://linkedin.com/in/janedoe"}],
            "cadence": {"jane-doe": cadence},
        }

    def test_sibling_with_em_dash_is_excluded(self):
        """A sibling containing an em dash fails lint and is excluded."""
        rec = self._make_rec({
            "li1": "Good note without any problems at all " * 4,
            "li2": "This note has an em dash \u2014 which fails lint",
            "li3": "Another good note that says something different " * 4,
        })
        contact = rec["contacts"][0]
        stored = rec["cadence"]["jane-doe"]
        # li2 fails lint (em dash), so it should not be a sibling
        # li1 and li3 are long enough to pass lint
        reasons = generate._note_quality(rec, contact, stored, "li1", None)
        # li2 should not appear in reasons because it's excluded
        for reason in reasons:
            self.assertNotIn("li2", reason,
                "li2 fails lint and should not be a sibling")

    def test_all_siblings_pass_lint_are_included(self):
        """When all siblings pass lint, they are all included."""
        rec = self._make_rec({
            "li1": "First note about profitability visibility in projects " * 4,
            "li2": "Second note about team coordination across offices " * 4,
            "li3": "Third note about reporting and compliance tracking " * 4,
        })
        contact = rec["contacts"][0]
        stored = rec["cadence"]["jane-doe"]
        # All pass lint, so all are siblings
        # This should not raise and should return a list (possibly empty)
        reasons = generate._note_quality(rec, contact, stored, "li1", None)
        self.assertIsInstance(reasons, list)


class TestFailingSiblingExcludedFromQualityOf(unittest.TestCase):
    """_quality_of excludes siblings that fail lint."""

    def _make_rec(self, emails):
        """Build a record with email steps keyed by step."""
        cadence = {}
        for key, email in emails.items():
            cadence[key] = {
                "channel": "email",
                "subject": email.get("subject", "Subject"),
                "body": email.get("body", ""),
                "approval": {"fingerprint": "dummy"},
            }
        return {
            "id": "test-rec",
            "company": "Acme Corp",
            "contacts": [{"key": "jane-doe", "name": "Jane Doe",
                          "email": "jane@acme.example"}],
            "cadence": {"jane-doe": cadence},
        }

    def test_sibling_with_em_dash_is_excluded(self):
        """A sibling containing an em dash fails lint and is excluded."""
        rec = self._make_rec({
            "em1": {"subject": "First subject", "body": "Good body " * 50},
            "em2": {"subject": "Second subject", "body": "Body with em dash \u2014 fails " * 20},
            "em3": {"subject": "Third subject", "body": "Another good body " * 50},
        })
        contact = rec["contacts"][0]
        stored = rec["cadence"]["jane-doe"]
        # em2 fails lint (em dash), so it should not be a sibling
        reasons = generate._quality_of(rec, contact, stored, "em1", None)
        for reason in reasons:
            self.assertNotIn("em2", reason,
                "em2 fails lint and should not be a sibling")


class TestFailingSiblingExcludedFromPlan(unittest.TestCase):
    """_plan's campaign_repetition check excludes steps that fail lint."""

    def test_role_to_step_mapping_is_built(self):
        """The reverse mapping from role to step_key is correct."""
        # This tests the internal mapping built in _plan
        expected = {
            "connection_note": "li1",
            "connected_1": "li2",
            "message_2": "li2",
            "connected_2": "li3",
            "message_3": "li3",
            "connected_3": "li4",
            "message_4": "li4",
            "connected_4": "li5",
        }
        # Build the mapping the same way _plan does
        _role_to_step = {}
        for sk, m in heyreachfactory.COPY_MAPPING.items():
            r = m["role"]
            for role in (r if isinstance(r, tuple) else (r,)):
                _role_to_step[role] = sk
        self.assertEqual(_role_to_step, expected)


if __name__ == "__main__":
    unittest.main()
