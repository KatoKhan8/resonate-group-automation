#!/usr/bin/env python3
"""The fabrication happened on LinkedIn, and LinkedIn was the unguarded channel.

THE DEFECT. `eligibility._email_checks` runs `lint.check` and then
`claims.verify`. `_linkedin_checks` ran neither - it checked the profile, that
the note was non-empty, the dependency status, evidence age and approval, and
let the WORDS through unexamined.

The note that started all of this told a real person "you are running
utilisation at <their company>", about a company that had never said anything of the
kind. It was a LinkedIn note. The only code in the repository that would have
refused it is `executionguard`, and the routine path -
`push.heyreach_rows` -> `verify_before_payload` -> `eligibility.decide` - does
not go through it.

So the guard existed, was correct, was documented, and was wired to one of the
two channels. That is the same shape as the collision check that was hardened
on email after it read the wrong estate and left open on LinkedIn until
2026-09-10.

These tests go through `eligibility.decide`, which is the function `push.py`
actually calls, rather than through the guard that would have caught it
anyway.
"""
import unittest

from src import eligibility


def a_record(note, **over):
    """A record whose every OTHER gate passes, so the note is what decides."""
    rec = {
        "id": "acme", "client": "productive", "domain": "acme.test",
        "company": "Acme", "lane": "domains", "state": "verified",
        "company_facts": {"name": "Acme", "employees": 40,
                          "industry": "Design Services"},
        "research": [], "events": [], "log": [],
        "contacts": [{
            "key": "dana-marsh", "name": "Dana Marsh", "first_name": "Dana",
            "title": "Operations Manager", "persona": "champion",
            "angle": "ops", "sendable": True,
            "linkedin": "https://www.linkedin.com/in/dana-marsh",
            "selected_evidence_ids": [],
        }],
        "cadence": {"dana-marsh": {"day3": {
            "channel": "linkedin", "note": note, "day": 3,
            "status": "clean"}}},
    }
    rec.update(over)
    return rec


def decide(rec):
    """`decide` returns a Decision mapping, not a tuple."""
    step = rec["cadence"]["dana-marsh"]["day3"]
    got = eligibility.decide(rec, rec["contacts"][0], "day3",
                             channel="linkedin", step=step)
    return got["verdict"], got["reasons"]


class AFabricatedNoteIsRefused(unittest.TestCase):

    def test_the_exact_sentence_that_went_out(self):
        """Nothing in this record says anything about utilisation."""
        verdict, reasons = decide(a_record(
            "hi Dana, you are running utilisation at Acme. happy to connect."))
        self.assertEqual(verdict, eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_UNSUPPORTED_CLAIM, reasons)

    def test_a_fabricated_hiring_claim(self):
        verdict, reasons = decide(a_record(
            "hi Dana, saw Acme opened a second studio in Berlin last year. "
            "happy to connect."))
        self.assertEqual(verdict, eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_UNSUPPORTED_CLAIM, reasons)

    def test_a_fabricated_figure(self):
        verdict, reasons = decide(a_record(
            "hi Dana, how do you handle scheduling across your 120 "
            "designers? happy to connect."))
        self.assertEqual(verdict, eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_UNSUPPORTED_CLAIM, reasons)

    def test_the_note_is_linted_as_well(self):
        """The other half the branch was missing.

        An unsubstituted placeholder reaching a prospect is the cheapest
        possible embarrassment and lint has caught it on email since it was
        written.
        """
        verdict, reasons = decide(a_record(
            "hi {first_name}, happy to connect about your work at Acme."))
        self.assertEqual(verdict, eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_LINT, reasons)


class ANoteThatAssertsNothingStillPasses(unittest.TestCase):
    """The direction that matters just as much.

    A guard that refuses everything is not a guard, and the approved canary
    note deliberately asserts nothing about the company - it says what WE do
    and asks a question. If this test breaks, the fix has started blocking
    legitimate copy and the canary itself would be refused.
    """

    def test_a_non_asserting_note_is_not_blocked_for_its_words(self):
        verdict, reasons = decide(a_record(
            "hi Dana, i work with Design Services teams on utilisation. "
            "curious how Acme handles it at your size. happy to connect."))
        self.assertNotIn(eligibility.BLOCKED_UNSUPPORTED_CLAIM, reasons)
        self.assertNotIn(eligibility.BLOCKED_LINT, reasons)

    def test_a_claim_the_record_actually_supports_passes(self):
        rec = a_record("hi Dana, noticed Acme is in Design Services. "
                       "happy to connect.")
        verdict, reasons = decide(rec)
        self.assertNotIn(eligibility.BLOCKED_UNSUPPORTED_CLAIM, reasons)


class BothChannelsAreCheckedTheSameWay(unittest.TestCase):
    """The invariant, rather than the instance.

    Stated as a property of the two branches so that a third channel, or a
    rewrite of either, cannot quietly reintroduce the asymmetry.
    """

    def test_the_email_branch_and_the_linkedin_branch_both_claim_check(self):
        import inspect
        for name in ("_email_checks", "_linkedin_checks"):
            source = inspect.getsource(getattr(eligibility, name))
            self.assertIn("claims.verify", source,
                          f"{name} does not claim-check the copy")
            self.assertIn("lint.check", source,
                          f"{name} does not lint the copy")


if __name__ == "__main__":
    unittest.main()
