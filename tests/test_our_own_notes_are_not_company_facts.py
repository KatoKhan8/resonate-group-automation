#!/usr/bin/env python3
"""A grounded claim can still be a claim about us.

FOUND ONE HUMAN APPROVAL AWAY FROM A STRANGER'S INBOX. The single
campaign-ready Productive contact carried this as its generated, lint-clean,
claims-clean day1 email:

    Subject: HSMG geo flag and headcount

    The specific signal triggering this outreach is the geo outside client's
    stated markets flag.

    We failed to filter our outreach by geography, and we own that failure
    completely without excuse.

    Your headcount signal is 23.

and day15 opened "The ICP flag indicates geographic targeting outside stated
markets."

`lint.check` returned `[]`. `claims.verify` returned `[]`. Both were right by
their own rules: every sentence is grounded in evidence stored on that
record. The evidence was `company_facts.icp_flags` - our qualification
verdict about our own geographic targeting - and `company_facts.
headcount_signal`, our provider's people-count in our own vocabulary.

## Why no existing guard could catch it

The claims model asks "is this supported by the evidence". It cannot ask "is
this evidence about the company, or is it a note we wrote to ourselves",
because both live in `company_facts`. Widening lint would not help either:
the sentences are true, specific and attributable. The defect is upstream, in
what the prompt is allowed to see, and that is where it is fixed - the
allowlist in `generate.facts_block`.

The boundary: a fact a person at that company would recognise as being about
their company. `employees` yes. `icp_flags` - our verdict - no.
`headcount_signal` - our estimate, in our words, and `employees` already
carries the same number in theirs - no.
"""
import unittest

from src import generate, store

INTERNAL = ("icp_flags", "headcount_signal")


def a_record(**facts):
    rec = store.new_record("acct", "domains", "productive", "Hot Soup Group",
                           "hotsoupgroup.com")
    rec["company_facts"] = facts
    return rec


class OurOwnNotesNeverReachThePrompt(unittest.TestCase):

    def test_the_icp_flag_is_not_a_company_fact(self):
        rec = a_record(name="Hot Soup Group",
                       icp_flags=["geo outside client's stated markets"])
        self.assertNotIn("icp_flags", generate.facts_block(rec))

    def test_the_headcount_signal_is_not_either(self):
        rec = a_record(name="Hot Soup Group", headcount_signal=23)
        self.assertNotIn("headcount_signal", generate.facts_block(rec))

    def test_no_internal_field_survives_the_allowlist(self):
        """Asserted over the block rather than the constant, because what
        matters is what the model is handed."""
        rec = a_record(name="Hot Soup Group", employees=23,
                       icp_flags=["geo outside client's stated markets"],
                       headcount_signal=23, industry="Advertising Services")
        block = generate.facts_block(rec)
        for field in INTERNAL:
            self.assertNotIn(field, block, field)

    def test_and_the_prompt_context_carries_none_of_it(self):
        """The allowlist is one hop from the model. This asserts the hop."""
        rec = a_record(name="Hot Soup Group", employees=23,
                       icp_flags=["geo outside client's stated markets"],
                       headcount_signal=23)
        contact = {"name": "Hussein Samnani", "title": "CEO",
                   "persona": "founder", "angle": "operations"}
        context = generate.context_for("draft", rec, contact)
        blob = repr(context).lower()
        self.assertNotIn("icp_flag", blob)
        self.assertNotIn("headcount_signal", blob)
        self.assertNotIn("stated markets", blob,
                         "the flag's text reached the prompt by another route")


class TheRealCompanyFactsStillDo(unittest.TestCase):
    """A guard that removed the useful facts with the internal ones would be
    traded for a worse defect: nothing true left to say."""

    def setUp(self):
        self.block = generate.facts_block(a_record(
            name="Hot Soup Group", employees=23, revenue="$4.1M",
            founded=2011, industry="Advertising Services",
            offices=["Dubai, AE"], specialties=["brand", "campaign"],
            notable="worked with X", email_domain="hotsoupgroup.com",
            icp_flags=["geo outside client's stated markets"],
            headcount_signal=23))

    def test_the_headcount_survives_in_the_companys_own_vocabulary(self):
        """`employees` is the same number `headcount_signal` carried, in the
        word a person at the company would use."""
        self.assertEqual(self.block.get("employees"), 23)

    def test_every_other_company_fact_survives(self):
        for field in ("name", "revenue", "founded", "industry", "offices",
                      "specialties", "notable", "email_domain"):
            self.assertIn(field, self.block, field)

    def test_empty_values_are_still_dropped(self):
        block = generate.facts_block(a_record(name="X", revenue="",
                                              offices=[], notable=None))
        self.assertEqual(sorted(block), ["name"])


if __name__ == "__main__":
    unittest.main()
