"""Regeneration must not delete the approval it replaces.

## The two halves of approval semantics

**The binding half already worked.** `approval.is_approved` compares the
stored fingerprint against the CURRENT content, so regenerated copy can never
inherit an old verdict - change one character and the approval lapses. A
verdict belongs to the exact words it was given to. That invariant is not new
and is not what this file fixes.

**The evidence half did not.** Regeneration replaced the step dict wholesale
at three call sites, so the outgoing `approval` was simply gone. Measured on
the live estate on 2026-09-15, comparing a pre-regeneration backup:

    steps approved before regeneration   169
    approval record still present         97
    approval record GONE                  72

Seventy-two audit records deleted, silently, by a run that reported itself as
regenerating copy - and recoverable only because a backup happened to exist.

A lapsed verdict is still evidence. It says a person looked at this position,
on this date, and said yes to words that no longer exist. The live `approval`
field is correctly ABSENT on new copy - it is unapproved and must be read
again - and the old record belongs in `approval_history`.

These assert on returned state, not on source text.
"""

import unittest

from src import approval, generate


def _rec():
    return {
        "id": "test-record",
        "cadence": {
            "pat": {
                "li1": {
                    "channel": "linkedin",
                    "note": "the words a person approved",
                    "approval": {"by": "a-person", "at": "2026-09-13T21:00:00+00:00",
                                 "fingerprint": None},
                }
            }
        },
    }


def _seal(rec):
    """Give the stored approval the fingerprint of its own copy."""
    step = rec["cadence"]["pat"]["li1"]
    step["approval"]["fingerprint"] = approval.fingerprint(step)
    return rec


class TheVerdictBindsToExactContent(unittest.TestCase):
    """The half that already worked, pinned so it keeps working."""

    def test_an_untouched_step_is_approved(self):
        rec = _seal(_rec())
        self.assertTrue(approval.is_approved(rec, "pat", "li1"))

    def test_one_changed_character_lapses_the_approval(self):
        rec = _seal(_rec())
        rec["cadence"]["pat"]["li1"]["note"] += "."
        self.assertFalse(approval.is_approved(rec, "pat", "li1"))


class ALapsedVerdictIsKeptAsEvidence(unittest.TestCase):

    def test_regeneration_moves_the_approval_into_history(self):
        rec = _seal(_rec())
        was = dict(rec["cadence"]["pat"]["li1"]["approval"])
        generate.store_step(rec, "pat", "li1",
                            {"channel": "linkedin", "note": "freshly generated words"})
        step = rec["cadence"]["pat"]["li1"]
        # The new copy is UNAPPROVED - it must be read again.
        self.assertIsNone(step.get("approval"))
        # And the old verdict survives as evidence.
        hist = step.get("approval_history") or []
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["by"], was["by"])
        self.assertEqual(hist[0]["at"], was["at"])
        self.assertEqual(hist[0]["approved_content_fingerprint"], was["fingerprint"])
        self.assertEqual(hist[0]["superseded_by"], "regeneration")

    def test_history_accumulates_across_successive_regenerations(self):
        """Two regenerations must leave two records, not one.

        The first version of this kept only the most recent, which loses the
        earliest human decision - usually the one somebody wants to find.
        """
        rec = _seal(_rec())
        generate.store_step(rec, "pat", "li1",
                            {"channel": "linkedin", "note": "second words",
                             "approval": {"by": "b", "at": "2026-09-14T00:00:00+00:00",
                                          "fingerprint": "x"}})
        generate.store_step(rec, "pat", "li1",
                            {"channel": "linkedin", "note": "third words"})
        hist = rec["cadence"]["pat"]["li1"].get("approval_history") or []
        self.assertEqual(len(hist), 2)
        self.assertEqual([h["by"] for h in hist], ["a-person", "b"])

    def test_a_step_that_was_never_approved_gains_no_history(self):
        # Absence of evidence is not evidence, and an empty history key would
        # imply somebody once looked.
        rec = {"id": "r", "cadence": {"pat": {"li1": {"channel": "linkedin",
                                                      "note": "never approved"}}}}
        generate.store_step(rec, "pat", "li1",
                            {"channel": "linkedin", "note": "regenerated"})
        self.assertNotIn("approval_history", rec["cadence"]["pat"]["li1"])

    def test_writing_a_brand_new_step_is_unaffected(self):
        rec = {"id": "r", "cadence": {}}
        generate.store_step(rec, "pat", "li1",
                            {"channel": "linkedin", "note": "first ever"})
        self.assertEqual(rec["cadence"]["pat"]["li1"]["note"], "first ever")
        self.assertNotIn("approval_history", rec["cadence"]["pat"]["li1"])


if __name__ == "__main__":
    unittest.main()
