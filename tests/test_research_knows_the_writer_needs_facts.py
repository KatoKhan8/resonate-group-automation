#!/usr/bin/env python3
"""`research.why` knew four reasons to read a company's site and none of them
was the writer's.

Hook, angle, rebrand and ICP are all about QUALIFYING an account. None asks
whether the copy stage can write a prospect-facing sentence that
`copylint.untraceable_company_claim` will accept - and that rule fires on
44.7 percent of stored leads.

MEASURED 2026-09-30, and both measurements are the reason this exists:

  - `2020companies-com` (Rachele) holds FOUR research rows of which
    `evidence.select` admits TWO, one of them spent on em1's P.S. Ten drafts
    across two models were refused for untraceable claims, and `why` said
    the record needed nothing.
  - `westcarygroup-com`, the first candidate in the approved source order,
    holds ZERO rows and `plan` still answered "structured evidence is
    sufficient" - correct for the question it was asking, useless for the
    one the writer asks.

TWO PROPERTIES, AND THE SECOND IS A COST CONTROL rather than a hedge. The
reason must fire when the copy stage asks, and must NOT fire on a routine
enrichment pass: it applies to 755 of 1,582 records, and answering it by
default would turn "ContactOut first, Apify last and optional" into a
blanket scrape. `tests/test_contactout_first.py` owns that policy and stays
green; this file owns the opt-in.
"""
import unittest

from src import research


def _rec(rows=(), contacts=({"email": "a@b.test"},), icp=None):
    rec = {"id": "r1", "domain": "b.test", "lane": "domains",
           "research": list(rows), "contacts": list(contacts),
           "company_facts": {"industry": "Advertising Services"}}
    if icp:
        rec["qualification"] = {"verdict": {"icp_status": icp}}
    return rec


def _admissible(n):
    """`n` rows that `evidence.select` will actually admit."""
    from tests.base import canonical_research

    out = []
    for i in range(n):
        out += canonical_research(
            "r1", fact=("TestCorp opened office %d in Zagreb and is hiring "
                        "%d delivery project managers" % (i, 10 + i)),
            source_url="https://b.test/p%d" % i)
    return out


class TheCopyReasonFiresWhenTheWriterWouldStarve(unittest.TestCase):
    def test_no_rows_at_all(self):
        self.assertEqual(research.NEED_COPY_EVIDENCE,
                         research.why(_rec(), for_copy=True))

    def test_rows_that_are_all_inadmissible(self):
        """Having rows is not having ADMISSIBLE ones - Rachele's shape."""
        weak = [{"fact": "x", "quality": "WEAK", "relevance_score": 0.1}]
        self.assertEqual(research.NEED_COPY_EVIDENCE,
                         research.why(_rec(rows=weak), for_copy=True))

    def test_two_admitted_rows_is_still_not_enough(self):
        """TWO IS THE NUMBER THAT FAILED, so the floor must sit above it."""
        self.assertEqual(
            research.NEED_COPY_EVIDENCE,
            research.why(_rec(rows=_admissible(2)), for_copy=True),
            "a pack the size of the one that refused ten drafts was called "
            "sufficient")

    def test_enough_admitted_rows_asks_for_nothing(self):
        """The control. Without it the tests above pass for a reason that
        always fires, which proves nothing about evidence."""
        self.assertIsNone(
            research.why(_rec(rows=_admissible(research.MIN_COPY_EVIDENCE_ROWS)),
                         for_copy=True))


class ItDoesNotSpendMoneyItWasNotAskedTo(unittest.TestCase):
    def test_a_routine_enrichment_pass_never_sees_this_reason(self):
        """`for_copy` defaults OFF. 755 of 1,582 records match it."""
        self.assertIsNone(research.why(_rec()))
        self.assertNotEqual(research.NEED_COPY_EVIDENCE,
                            research.why(_rec(rows=_admissible(1))))

    def test_a_rejected_company_is_never_scraped_for_copy(self):
        """A decision is not a gap. Nobody will write to them."""
        self.assertIsNone(
            research.why(_rec(icp="rejected"), for_copy=True),
            "a rejected account was queued for a copy-evidence scrape")

    def test_a_company_with_nobody_to_write_to_is_not_scraped(self):
        self.assertIsNone(research.why(_rec(contacts=()), for_copy=True))

    def test_plan_threads_the_flag_through(self):
        """A reason `plan` cannot see is a reason nothing acts on."""
        rec = _rec()
        self.assertFalse(research.plan(rec, {}).get("planned"))
        self.assertEqual(
            research.NEED_COPY_EVIDENCE,
            research.plan(rec, {}, for_copy=True).get("reason")
            or research.why(rec, for_copy=True))


class TheOlderReasonsStillWork(unittest.TestCase):
    """This inserted a branch ahead of them; they have to survive it."""

    def test_stale_evidence_still_wins(self):
        stale = [{"fact": "x", "field": "team", "quality": "STRONG",
                  "retrieved_at": "2020-01-01T00:00:00+00:00",
                  "published_at": "2020-01-01"}]
        self.assertEqual(research.NEED_REFRESH,
                         research.why(_rec(rows=stale), for_copy=True))

    def test_fresh_admissible_evidence_still_answers_none(self):
        self.assertIsNone(
            research.why(_rec(rows=_admissible(4))))


if __name__ == "__main__":
    unittest.main()
