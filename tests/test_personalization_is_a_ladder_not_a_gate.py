#!/usr/bin/env python3
"""Missing personalization selects a weaker ANGLE. It never discards an account.

OPERATOR DECISION, Zvonimir, 2026-09-30:

    Lack of deep account-specific personalization is NOT, by itself, a reason
    to HELD an otherwise qualified prospect... NO PERSONALIZATION FACT != NO
    SAFE COPY. Do NOT weaken factual claim safety. Do NOT invent prospect
    facts.

Both halves are tested here, and the second half is the one that matters:
every level is an instruction about WHICH TRUTHFUL ANGLE to reach for, and
none of them licenses a single claim. A level 4 draft that invents a prospect
fact is refused exactly as a level 1 draft would be.

Before this, one line in `scripts/canary_candidate_walk.py` turned
`research.NEED_COPY_EVIDENCE` straight into HELD - so an ICP-qualified
account with a verified contact was discarded for having nothing interesting
to say about it. Measured across the estate afterwards: 54 accounts at level
1, 1,191 at level 2, and 336 with no level at all.
"""
import unittest
from unittest import mock

from src import claims, copylint, evidence as ev, personalization as pz
from src import research


def _admissible(n, record_id="r1"):
    from tests.base import canonical_research

    out = []
    for i in range(n):
        out += canonical_research(
            record_id,
            fact=("TestCorp opened office %d in Zagreb and is hiring %d "
                  "delivery project managers" % (i, 10 + i)),
            source_url="https://b.test/p%d" % i)
    return out


def _rec(rows=(), facts=None, icp="qualified"):
    return {"id": "r1", "domain": "b.test", "client": "productive",
            "research": list(rows), "company_facts": dict(facts or {}),
            "qualification": {"verdict": {"icp_status": icp}},
            "contacts": []}


PERSONA = {"key": "c1", "email": "a@b.test", "persona": "economic_buyer"}
NO_PERSONA = {"key": "c1", "email": "a@b.test"}


class TheLadderPicksTheStrongestTruthfulAngle(unittest.TestCase):
    def test_1_strong_evidence_is_level_1(self):
        rec = _rec(rows=_admissible(research.MIN_COPY_EVIDENCE_ROWS))
        self.assertEqual(pz.LEVEL_ACCOUNT_FACT, pz.level_for(rec, PERSONA))

    def test_2_no_deep_personalization_but_usable_context_is_level_2(self):
        rec = _rec(facts={"industry": "Advertising Services",
                          "employees": 40})
        self.assertEqual(pz.LEVEL_ACCOUNT_CONTEXT, pz.level_for(rec, PERSONA))

    def test_3_no_context_but_a_known_persona_is_level_3(self):
        rec = _rec()
        self.assertEqual(pz.LEVEL_PERSONA, pz.level_for(rec, PERSONA))

    def test_4_no_persona_but_a_qualified_account_is_level_4(self):
        rec = _rec()
        self.assertEqual(pz.LEVEL_ICP, pz.level_for(rec, NO_PERSONA))

    def test_10_missing_personalization_alone_never_means_no_level(self):
        """The decision, stated as one assertion.

        An account with NO research, NO structured context and NO persona is
        still writable when it is ICP-qualified.
        """
        rec = _rec()
        self.assertIsNot(pz.LEVEL_NONE, pz.level_for(rec, NO_PERSONA))

    def test_a_rejected_account_still_has_no_level(self):
        """HELD stays correct for a real eligibility failure."""
        self.assertIs(pz.LEVEL_NONE,
                      pz.level_for(_rec(icp="rejected"), PERSONA))

    def test_an_unqualified_account_with_nobody_known_has_no_level(self):
        self.assertIs(pz.LEVEL_NONE,
                      pz.level_for(_rec(icp="review"), NO_PERSONA))


class NoLevelLicensesAnything(unittest.TestCase):
    """The half that must not move. A level chooses an angle, never a claim."""

    REC = {"id": "r1", "company": "Acme Agency", "domain": "b.test",
           "company_facts": {}, "contacts": [], "research": []}

    def test_5_an_unsupported_prospect_claim_still_refuses_at_every_level(self):
        text = "Your team of 4,200 people is losing margin on fixed-fee work."
        for level in (pz.LEVEL_ACCOUNT_FACT, pz.LEVEL_ACCOUNT_CONTEXT,
                      pz.LEVEL_PERSONA, pz.LEVEL_ICP):
            with self.subTest(level=level):
                self.assertTrue(
                    claims.check(text, self.REC, PERSONA),
                    "a level licensed an invented prospect claim")

    def test_6_second_brain_may_license_a_productive_side_statement(self):
        self.assertEqual(
            [], claims.check(
                "Productive brings budgets, time tracking and resourcing "
                "together.", self.REC, PERSONA))

    def test_7_second_brain_may_not_license_a_prospect_side_claim(self):
        self.assertTrue(
            claims.check("Your team is struggling to connect budgets, time "
                         "tracking and resourcing.", self.REC, PERSONA),
            "Productive knowledge licensed a claim about the PROSPECT")

    def test_a_question_is_safe_at_a_weak_level(self):
        """The shape the ladder tells the writer to use when it knows little."""
        self.assertEqual(
            [], claims.check(
                "How are you currently tracking project margin during the "
                "month rather than after projects close?", self.REC, PERSONA))

    def test_the_evidence_thresholds_did_not_move(self):
        self.assertEqual(0.65, ev.MIN_RELEVANCE)
        self.assertEqual(("strong", "medium"), tuple(ev.USABLE))
        self.assertEqual(3, research.MIN_COPY_EVIDENCE_ROWS)

    def test_an_untraceable_company_claim_still_refuses(self):
        lead = {"id": "ck",
                "steps": [{"subject": "s",
                           "body": "Your team of 4,200 people runs those "
                                   "campaigns across 12 offices."}]
                         + [{"subject": "s%d" % i, "body": "Filler %d." % i}
                            for i in range(2, 6)],
                "ps": {}, "linkedin": {}, "pack": {"facts": []}}
        report = copylint.check_batch([lead])
        self.assertIn("ck",
                      report["offenders"].get("untraceable_company_claim") or ())


class ExclusionAndSuppressionAreUntouched(unittest.TestCase):
    """8 and 9. A ladder about ANGLES must not reach eligibility."""

    def test_8_operator_exclusion_still_refuses(self):
        from src import eligibility

        rec = {"id": "r1", "client": "productive", "domain": "b.test",
               "contacts": [PERSONA], "operator_excluded": True}
        with mock.patch.object(eligibility, "_suppressed",
                               return_value="operator excluded"):
            self.assertTrue(
                [r for r in eligibility.must_not_contact(rec, PERSONA) if r])

    def test_9_an_unsubscribe_still_refuses(self):
        from src import channels

        rec = {"id": "r1", "client": "productive", "domain": "b.test",
               "contacts": [PERSONA],
               "events": [{"type": "email_unsubscribed", "channel": "email",
                           "contact": "c1"}]}
        ok, why = channels.email_verdict(rec, PERSONA)
        self.assertFalse(ok, "an unsubscribed contact was writable")


class TheWriterIsToldWhichRungItIsOn(unittest.TestCase):
    """A level nothing reads would be a level that changes nothing."""

    def test_every_level_describes_itself(self):
        for level in (pz.LEVEL_ACCOUNT_FACT, pz.LEVEL_ACCOUNT_CONTEXT,
                      pz.LEVEL_PERSONA, pz.LEVEL_ICP):
            with self.subTest(level=level):
                said = pz.describe(level)
                self.assertTrue(said and "LEVEL" in said)

    def test_the_weak_levels_forbid_manufacturing_a_fact(self):
        for level in (pz.LEVEL_ACCOUNT_CONTEXT, pz.LEVEL_PERSONA,
                      pz.LEVEL_ICP):
            with self.subTest(level=level):
                said = pz.describe(level).lower()
                self.assertIn("question", said)
                self.assertTrue("do not" in said)


if __name__ == "__main__":
    unittest.main()
