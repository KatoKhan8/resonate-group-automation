#!/usr/bin/env python3
"""Matrix run D can only measure something if some claim was load-bearing.

`TASK-425` / `P0-C`. Run D's design is "remove the key evidence and the claim
must disappear or the lead must HOLD". That is a measurement only if, with the
evidence PRESENT, the copy asserts something the gates can see, and if this one
row is what licenses it.

## THE DEFECT THIS FILE EXISTS TO STOP RETURNING

The previous fixture declared its claim under test as the phrase
`retained monthly engagements`. It is not a checkable specific: no digit, no
quoted phrase, no capitalised multi-word name. So `copylint.untraceable` never
examined it, `claims.check` never examined it, the audit artifact's "exact
claim licensed" column was EMPTY for all nine messages, and removing its
research row changed nothing either gate could observe. Run D read
NOT COMPARABLE for a reason that had nothing to do with the copy engine: there
was nothing to remove.

Nothing about that was visible in the fixture. It read as a careful, heavily
documented file and its one load-bearing property was absent. So the property
is asserted here instead of described there.

## THESE RUN OFFLINE AND THEY ARE ABOUT THE REAL ACCOUNT

`task425fixture.record()` is a redacted reconstruction of `brandiq-com` built
from the stored public excerpts, because the real record lives in gitignored
`work/` and carries a real person. Every verdict asserted below was also
measured on the real record on 2026-09-28 and came back identical - licensed by
both gates with the row, refused by both without it, negative control refused
with the full pack - which is what makes an offline assertion evidence about
the account rather than about this file. `test_the_real_record_agrees` runs the
same four questions against the store when the store has it, and SKIPS rather
than passing when it does not: an unreadable authority is UNKNOWN, and UNKNOWN
is not a pass.

## WHAT IS NOT ASSERTED

That the generated copy actually USES the claim. That is a property of the
writer, it needs model calls, and it is measured by the matrix run.
**A green test here is not criterion 1.**
"""
import unittest

from src import claims, copylint, evidence, packfacts
from tests import task425fixture as fixture


def without_the_evidence_under_test(rec):
    """The same record with only the row under test removed."""
    kept = [row for row in rec.get("research") or ()
            if (row or {}).get("source_url") != fixture.EVIDENCE_UNDER_TEST]
    return dict(rec, research=kept)


class TestTheClaimUnderTestIsCheckable(unittest.TestCase):

    def test_the_declared_claim_is_a_specific_both_gates_can_see(self):
        self.assertIn(
            fixture.CLAIM_UNDER_TEST,
            copylint.specifics_in(fixture.CLAIM_UNDER_TEST),
            "CLAIM_UNDER_TEST is not a copylint specific, so no gate will "
            "ever examine it and run D cannot measure its removal. This is "
            "exactly how the previous fixture failed.")

    def test_a_phrase_with_no_figure_or_name_is_not_a_specific(self):
        """The previous claim's shape, asserted as the reason it failed."""
        self.assertEqual(
            copylint.specifics_in(
                "You run project delivery on retained monthly engagements."),
            [])

    def test_the_claim_sentence_carries_it_and_nothing_unsourced(self):
        found = copylint.specifics_in(fixture.CLAIM_SENTENCE)
        self.assertEqual(sorted(found),
                         sorted(fixture.CLAIM_TOKENS_WITHDRAWN_WITH_IT))

    def test_the_claim_appears_in_exactly_one_research_row(self):
        token = copylint._norm(fixture.CLAIM_UNDER_TEST)
        carrying = [row["source_url"] for row in fixture.RESEARCH
                    if token in copylint._norm(row["fact"])]
        self.assertEqual(carrying, [fixture.EVIDENCE_UNDER_TEST],
                         "removing one row must remove this claim's licence "
                         "and nothing else's")

    def test_every_withdrawn_token_really_is_only_in_that_row(self):
        """`copylint._traces` does a SUBSTRING search, so this is not implied.

        `ISSUE-055`, open: a short figure traces against any longer number
        containing it. Both tokens the claim sentence carries are checked, not
        just the headline one.
        """
        others = [row for row in fixture.RESEARCH
                  if row["source_url"] != fixture.EVIDENCE_UNDER_TEST]
        for token in fixture.CLAIM_TOKENS_WITHDRAWN_WITH_IT:
            for row in others:
                with self.subTest(token=token, url=row["source_url"]):
                    self.assertNotIn(token, copylint._norm(row["fact"]))


class TestTheEvidenceIsAdmitted(unittest.TestCase):

    def test_every_research_row_is_identity_admitted_for_this_account(self):
        pack, unused = packfacts.pack_for(fixture.record())
        self.assertEqual(len(pack["facts"]), len(fixture.RESEARCH))
        self.assertEqual(unused[packfacts.REFUSED], [])
        self.assertEqual(unused[packfacts.UNVERIFIABLE], [])

    def test_admission_survives_the_record_id_stamp(self):
        """The stronger of the two admissions, not the host-only one."""
        for row in fixture.research_rows():
            with self.subTest(url=row["source_url"]):
                self.assertEqual(
                    packfacts.identity_of(row, fixture.DOMAIN,
                                          record_id=fixture.RECORD_ID),
                    packfacts.ADMITTED)
                self.assertEqual(
                    packfacts.identity_of(row, fixture.DOMAIN,
                                          record_id="somebody-elses-record"),
                    packfacts.REFUSED,
                    "a row stamped with another record must be refused, or "
                    "the stamp is decorative")

    def test_the_row_carrying_the_claim_reaches_a_prompt(self):
        """`evidence.select` passes only USABLE rows. A row the writer is
        never shown cannot be used, however well it licenses."""
        rows = [r for r in fixture.research_rows()
                if r["source_url"] == fixture.EVIDENCE_UNDER_TEST]
        self.assertEqual(len(rows), 1)
        self.assertIn(rows[0]["quality"], evidence.USABLE,
                      "relevance %s" % rows[0]["relevance_score"])

    def test_no_row_carries_an_invented_publication_date(self):
        """Neither page states one, so there is none to record."""
        for row in fixture.research_rows():
            self.assertIn(row.get("published_at"), (None, ""),
                          "a publication date no page states is invented "
                          "provenance")


class TestBothGatesLicenseItAndStopWhenItGoes(unittest.TestCase):
    """The D test, constructed, in both directions, through both validators."""

    def setUp(self):
        self.rec = fixture.record()
        self.pack, _ = packfacts.pack_for(self.rec)
        self.rec_without = without_the_evidence_under_test(self.rec)
        self.pack_without, _ = packfacts.pack_for(self.rec_without)

    def test_removing_the_evidence_does_not_empty_the_pack(self):
        """Or run D would be measuring "no research at all" instead."""
        self.assertTrue(self.pack_without["facts"])
        self.assertEqual(len(self.pack_without["facts"]),
                         len(self.pack["facts"]) - 1)

    def test_copylint_licenses_the_claim_and_then_refuses_it(self):
        self.assertEqual(
            copylint.untraceable(fixture.CLAIM_SENTENCE, self.pack), [])
        self.assertEqual(
            sorted(copylint.untraceable(fixture.CLAIM_SENTENCE,
                                        self.pack_without)),
            sorted(fixture.CLAIM_TOKENS_WITHDRAWN_WITH_IT))

    def test_claims_licenses_the_claim_and_then_refuses_it(self):
        self.assertEqual(claims.check(fixture.CLAIM_SENTENCE, self.rec), [])
        refused = claims.check(fixture.CLAIM_SENTENCE, self.rec_without)
        self.assertTrue(refused)
        self.assertIn(fixture.CLAIM_UNDER_TEST,
                      " ".join(f.get("why") or "" for f in refused))

    def test_the_gates_do_not_pass_everything(self):
        """The negative control: a certification number on no page of theirs,
        in the same sentence frame, with the FULL pack present."""
        self.assertTrue(
            copylint.untraceable(fixture.INVENTED_SENTENCE, self.pack))
        self.assertTrue(claims.check(fixture.INVENTED_SENTENCE, self.rec))


class TestTheOtherMatrixVariablesAreConstructible(unittest.TestCase):

    def test_run_b_replaces_one_fact_on_the_same_page(self):
        self.assertEqual(fixture.FACT_CHANGED_B["source_url"],
                         fixture.EVIDENCE_UNDER_TEST)
        self.assertNotEqual(fixture.FACT_CHANGED_B["fact"],
                            fixture.RESEARCH[0]["fact"])

    def test_run_bs_replacement_is_itself_usable_and_admitted(self):
        rows = [fixture.FACT_CHANGED_B
                if row["source_url"] == fixture.EVIDENCE_UNDER_TEST else row
                for row in fixture.RESEARCH]
        rec = fixture.record(research=rows)
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(len(pack["facts"]), len(rows))
        self.assertEqual(unused[packfacts.REFUSED], [])
        made = [r for r in fixture.research_rows(rows=rows)
                if r["source_url"] == fixture.EVIDENCE_UNDER_TEST][0]
        self.assertIn(made["quality"], evidence.USABLE)

    def test_run_b_also_withdraws_the_claim_under_test(self):
        """Stated so the artifact cannot report B as holding it constant."""
        for token in fixture.CLAIM_TOKENS_WITHDRAWN_WITH_IT:
            self.assertNotIn(token,
                             copylint._norm(fixture.FACT_CHANGED_B["fact"]))


class TestTheRealRecordAgrees(unittest.TestCase):
    """The same four questions, against the account the estate actually holds.

    SKIPS when the store has no such record. It is deliberately not a pass:
    `work/` is gitignored, so a fresh clone cannot read the authority, and per
    invariant 0 an unreadable authority is UNKNOWN rather than green.
    """

    def setUp(self):
        self.rec = fixture.record_from_store()
        if not self.rec:
            self.skipTest("brandiq-com is not in this checkout's store; the "
                          "canonical authority is unreadable here, so the "
                          "state is UNKNOWN rather than passing")

    def test_it_is_the_account_that_was_selected(self):
        self.assertEqual((self.rec.get("domain") or "").lower(),
                         fixture.DOMAIN)

    def test_it_is_qualified_by_the_real_gate(self):
        from src import dmplan, qualify
        self.assertIn(qualify.state_of(self.rec),
                      (dmplan.QUALIFIED, dmplan.DM_APPROVED))

    def test_it_has_a_sendable_contact_for_the_matrix_to_run_on(self):
        self.assertTrue(fixture.contact_under_test(self.rec))

    def test_both_gates_license_it_and_then_refuse_it(self):
        pack, _ = packfacts.pack_for(self.rec)
        without = without_the_evidence_under_test(self.rec)
        pack_without, _ = packfacts.pack_for(without)
        self.assertTrue(pack_without["facts"], "run D must not empty the pack")
        self.assertEqual(
            copylint.untraceable(fixture.CLAIM_SENTENCE, pack), [])
        self.assertEqual(claims.check(fixture.CLAIM_SENTENCE, self.rec), [])
        self.assertTrue(
            copylint.untraceable(fixture.CLAIM_SENTENCE, pack_without))
        self.assertTrue(claims.check(fixture.CLAIM_SENTENCE, without))
        self.assertTrue(
            copylint.untraceable(fixture.INVENTED_SENTENCE, pack),
            "the negative control must be refused with the full pack")


if __name__ == "__main__":
    unittest.main()
