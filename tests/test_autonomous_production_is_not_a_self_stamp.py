#!/usr/bin/env python3
"""The autonomous production authority ships copy nobody read, and is still
not the system approving itself.

OPERATOR DECISION, Zvonimir, 2026-09-30: the 48-hour autonomous production
authorization covers NEW prospect-facing copy the operator has not personally
read, provided it is generated through the canonical path and passes every
required gate. Fifty-company batches cannot be hand-read, so the ramp needs
this; refusing it was what stopped production.

`src/approval.py` was written against the opposite failure - 84 approvals
stamped `by: "claude"`, 83 of them on `generated: true` steps whose words
never move, so a self-stamp stayed current forever. That module's whole point
is that a bare token is not an identity anybody can be held to.

So this file exists to hold BOTH truths at once, and every test here is about
the line between them:

  - the autonomous stamp CERTIFIES, because an operator authorized the window;
  - it is never PERSONALLY REVIEWED, because no person read the artifact;
  - `claude`, `qwen`, `glm`, `system`, `unknown` are refused exactly as
    before, so this is not the old hole under a new name;
  - a BARE `autonomous-production`, or one with invented provenance, is
    refused - otherwise the decision would hand every future caller a
    one-word self-approval;
  - and it EXPIRES, reverting with no human action, which is the property
    that keeps an authorization from outliving the decision behind it.

The staging test is the one that matters most: a predicate nothing consumes
proves nothing, and this repository's recurring defect is exactly that.
"""
import unittest

from src import approval, bisonfactory

LIVE = "2026-09-30"          # inside the authorized window
AFTER = "2026-10-02"         # past every window in the table


def _step(by, body="Hello Ada, a body that does not matter here.",
          subject="a subject"):
    step = {"channel": "email", "subject": subject, "body": body}
    step["approval"] = {"by": by, "at": "2026-09-30T00:00:00Z",
                        "fingerprint": approval.fingerprint(step)}
    return step


class TheStampIsAccountableWithoutBeingRead(unittest.TestCase):
    def test_the_canonical_stamp_certifies(self):
        self.assertTrue(
            approval.is_accountable_approver(approval.autonomous_stamp(LIVE),
                                             on=LIVE))

    def test_and_says_in_its_own_words_that_nobody_read_it(self):
        """The provenance is the point, so it is asserted rather than assumed."""
        stamp = approval.autonomous_stamp(LIVE).lower()
        self.assertIn("did not", stamp)
        self.assertIn("personally review", stamp)
        self.assertIn("operator", stamp)
        self.assertIn("expires", stamp)

    def test_it_is_never_a_personal_review(self):
        self.assertFalse(
            approval.personally_reviewed(approval.autonomous_stamp(LIVE)))

    def test_a_person_still_registers_as_one(self):
        for who in ("beslic.zvonimir@gmail.com (operator)", "operator",
                    "operator-control-arm"):
            with self.subTest(who=who):
                self.assertTrue(approval.personally_reviewed(who))
                self.assertTrue(approval.is_accountable_approver(who))


class TheOldHoleIsStillClosed(unittest.TestCase):
    """If any of these passes, the 2026-09-17 defect is back."""

    def test_a_machine_name_is_refused(self):
        for who in ("claude", "qwen", "glm", "system", "unknown", "", None):
            with self.subTest(who=who):
                self.assertFalse(approval.is_accountable_approver(who),
                                 "a bare machine token certified copy")
                self.assertFalse(approval.personally_reviewed(who))

    def test_a_bare_autonomous_token_is_refused(self):
        """Without the provenance it is a one-word self-approval."""
        self.assertFalse(
            approval.is_accountable_approver("autonomous-production",
                                             on=LIVE))

    def test_invented_provenance_is_refused(self):
        for who in ("autonomous-production (i said so)",
                    "autonomous-production (operator approved everything)",
                    "autonomous-production (Zvonimir personally reviewed it)"):
            with self.subTest(who=who):
                self.assertFalse(
                    approval.is_accountable_approver(who, on=LIVE),
                    "provenance nobody recorded was accepted")


class TheWindowCloses(unittest.TestCase):
    def test_there_is_a_live_window_today(self):
        self.assertIsNotNone(approval.autonomous_window(LIVE))

    def test_and_none_after_it_expires(self):
        self.assertIsNone(approval.autonomous_window(AFTER))
        self.assertIsNone(approval.autonomous_stamp(AFTER))

    def test_the_stamp_stops_certifying_when_the_window_does(self):
        """It reverts with NO human action, which is the whole point."""
        stamp = approval.autonomous_stamp(LIVE)
        self.assertTrue(approval.is_accountable_approver(stamp, on=LIVE))
        self.assertFalse(approval.is_accountable_approver(stamp, on=AFTER),
                         "an expired authorization still certified copy")


class StagingActuallyConsultsIt(unittest.TestCase):
    """A predicate nothing reads proves nothing. This is the consumer."""

    def test_a_step_approved_autonomously_certifies_at_staging(self):
        entry = bisonfactory._certified_copy(
            _step(approval.autonomous_stamp(LIVE)), "em1")
        self.assertIsNotNone(
            entry, "staging refused copy the operator's window authorizes")
        self.assertEqual("em1", entry["step_key"])

    def test_a_machine_stamped_step_is_still_refused_at_staging(self):
        self.assertIsNone(bisonfactory._certified_copy(_step("claude"), "em1"),
                          "staging accepted a self-stamp")

    def test_edited_words_are_still_refused_at_staging(self):
        """The window authorizes the PATH, never a licence to edit after."""
        step = _step(approval.autonomous_stamp(LIVE))
        step["body"] = step["body"] + " and one more sentence nobody approved."
        self.assertIsNone(bisonfactory._certified_copy(step, "em1"),
                          "the fingerprint stopped covering the words and "
                          "staging took them anyway")


if __name__ == "__main__":
    unittest.main()
