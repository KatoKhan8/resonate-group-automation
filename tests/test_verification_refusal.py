"""A vendor said "do not send to this" and two others outvoted it.

The rule this file defends is not "two vendors approved". It is that
CATCH_ALL is never an automatic PASS, and that a verifier's explicit
refusal is a fact about the address rather than a vote to be outnumbered.

What happened. `call` records Reoon's answer faithfully -
`safe_to_send: False`, `catch_all: True`, `deliverable: False` are all on
the evidence - and maps the *status* to `unknown`, because only
`is_safe_to_send is True` becomes `valid`. Nothing then read those three
fields. `negatives` in `decide` covered `invalid`, `disposable` and the
`disposable` flag, so the refusal could not register as a disagreement.
And step 4 returns VERIFIED as soon as the primary says valid, which is
*before* the catch-all branch at step 5 where
`safe_to_send is False` would have returned ACCEPT_ALL_UNCLEARED.

So the branch that refuses a catch-all was unreachable whenever the
primary was positive, and the answer for an address the deep verifier had
declined was `verified, sendable: True, disagreement: False`. Not a bug in
the catch-all rule - the catch-all rule was correct and never ran. It was
decided by the order of two `if`s.

Reachable without hand-editing anything: run one, ContactOut says valid,
one of two confirmations, held; `needs` escalates to Reoon, which refuses;
run two, Deliverable is enabled and says valid, ContactOut is skipped
because evidence exists. Two confirmations, sendable, no disagreement
reported.
"""
import unittest

from src import verification as v

AT = "2026-09-01T00:00:00+00:00"
ADDRESS = "kovac@meridian.test"


def says(provider, status, **extra):
    return dict({"provider": provider, "status": status, "address": ADDRESS,
                 "at": AT}, **extra)


VALID = lambda p: says(p, v.S_VALID)
REFUSES = says("reoon", v.S_UNKNOWN, safe_to_send=False, catch_all=True,
               deliverable=False)


class ARefusalIsNotOutvoted(unittest.TestCase):

    def decide(self, *evidence):
        return v.decide(list(evidence))

    def test_two_valids_and_one_refusal_do_not_send(self):
        """The defect."""
        out = self.decide(VALID("contactout"), REFUSES, VALID("deliverable"))
        self.assertFalse(out["sendable"])
        self.assertEqual(out["state"], v.HELD)

    def test_and_it_is_reported_as_the_disagreement_it_is(self):
        """`disagreement: False` about this was the second half of the lie.
        An operator reading the record was told the vendors agreed."""
        out = self.decide(VALID("contactout"), REFUSES, VALID("deliverable"))
        self.assertTrue(out["disagreement"])
        self.assertIn("reoon", out["reason"])

    def test_a_refusal_alone_is_still_refused(self):
        out = self.decide(REFUSES)
        self.assertFalse(out["sendable"])

    def test_deliverable_false_counts_even_without_safe_to_send(self):
        """Two separate fields carry a refusal and neither was read."""
        out = self.decide(VALID("contactout"),
                          says("reoon", v.S_UNKNOWN, deliverable=False),
                          VALID("deliverable"))
        self.assertFalse(out["sendable"])

    def test_safe_to_send_false_counts_without_the_catch_all_flag(self):
        out = self.decide(VALID("contactout"),
                          says("reoon", v.S_UNKNOWN, safe_to_send=False),
                          VALID("deliverable"))
        self.assertFalse(out["sendable"])


class WhatMustStillWork(unittest.TestCase):
    """A guard that refuses everything is not a guard, so each of these is
    the same rule read from the other side."""

    def test_two_clean_valids_are_sendable(self):
        out = v.decide([VALID("contactout"), VALID("deliverable")])
        self.assertTrue(out["sendable"])
        self.assertEqual(out["confirmation_count"], 2)

    def test_a_catch_all_the_clearer_clears_is_still_cleared(self):
        """`safe_to_send is True` is the whole point of the field. Reading
        `False` must not have made `True` unreadable."""
        out = v.decide([
            says("contactout", v.S_ACCEPT_ALL, catch_all=True),
            says("reoon", v.S_VALID, safe_to_send=True, catch_all=True)])
        self.assertIn("cleared by reoon", out["reason"])

    def test_a_missing_field_is_not_a_refusal(self):
        """`None` is "nobody said", and a provider that does not report the
        field must not be read as refusing."""
        out = v.decide([VALID("contactout"),
                        says("reoon", v.S_VALID, safe_to_send=None,
                             deliverable=None)])
        self.assertTrue(out["sendable"])

    def test_an_absent_field_is_not_a_refusal_either(self):
        out = v.decide([VALID("contactout"), VALID("reoon")])
        self.assertTrue(out["sendable"])

    def test_a_provider_that_errored_carries_no_refusal(self):
        """`S_ERROR` is evidence of nothing, in this direction too."""
        out = v.decide([
            VALID("contactout"), VALID("deliverable"),
            says("reoon", v.S_ERROR, safe_to_send=False, deliverable=False)])
        self.assertTrue(out["sendable"],
                        "a failed call must not be read as a refusal")


class TheGateRecomputes(unittest.TestCase):
    """Stored state saying otherwise changes nothing."""

    def test_a_stored_sendable_flag_does_not_survive_the_refusal(self):
        contact = {
            "email": ADDRESS, "sendable": True,
            "verification": {"state": v.VERIFIED, "sendable": True,
                             "confirmation_count": 2},
            "verification_evidence": [
                VALID("contactout"), REFUSES, VALID("deliverable")]}
        self.assertFalse(v.is_sendable(contact),
                         "is_sendable read the stored flag instead of the "
                         "evidence")


if __name__ == "__main__":
    unittest.main()
