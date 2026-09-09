"""Five fictional companies, five different evidence situations, one campaign.

    A  recent expansion          -> the expansion is the opening
    B  the CFO wrote something   -> the person's own words are the opening
    C  a hiring signal           -> the hiring angle
    D  nothing public at all     -> verified company fact plus persona pain
    E  only irrelevant content   -> the irrelevant thing is refused, and D's
                                    fallback is used instead

Written as one walk because the interesting property is comparative: the same
pipeline has to reach five different conclusions from five different inputs,
and reach the *cautious* one twice.
"""
import unittest

from src import claims, demo, evidence, personalization, preview
from tests.campaignbase import CampaignTest


class TestFiveSituations(CampaignTest):
    def setUp(self):
        super().setUp()
        self.campaign, self.recs, self.cfg = demo.build(self.config)
        self.by_id = {r["id"]: r for r in self.recs}

    def decision(self, record_id):
        rec = self.by_id[record_id]
        contact = personalization.selected_contacts(rec, self.cfg)[0]
        return rec, contact, (contact.get("personalization")
                              or personalization.decide(rec, contact, self.cfg))

    # ------------------------------------------------------------------ A

    def test_a_recent_expansion_becomes_the_opening(self):
        rec, _, decision = self.decision("northwind")
        # MEDIUM rather than STRONG, and that is the model being honest: the
        # expansion is fresh, specific and checkable, but it does not touch
        # this client's angle vocabulary, so it earns an opener rather than a
        # claim about their pain.
        self.assertIn(decision["quality"], evidence.USABLE)
        self.assertIn("Vienna", decision["primary_signal"])
        self.assertEqual(decision["freshness"], evidence.HIGH)
        self.assertEqual(decision["source"], "company_announcement")
        self.assertEqual(decision["level"], evidence.LEVEL_RECENT)

    def test_the_expansion_scores_as_a_company_change(self):
        rec, _, decision = self.decision("northwind")
        entry = next(e for e in rec["research"]
                     if e["evidence_id"] == decision["selected_evidence_ids"][0])
        self.assertTrue(any("company change" in r
                            for r in entry["relevance_reasons"]))

    def test_the_expansion_claim_is_supported(self):
        rec, contact, decision = self.decision("northwind")
        chosen = [e for e in rec["research"]
                  if e["evidence_id"] in decision["selected_evidence_ids"]]
        step = rec["cadence"][contact["key"]]["day1"]
        self.assertEqual(claims.verify(step, rec, contact, chosen), [])

    # ------------------------------------------------------------------ B

    def test_a_person_authored_post_wins_over_the_company_page(self):
        rec, contact, decision = self.decision("belmont")
        self.assertEqual(decision["quality"], evidence.STRONG)
        self.assertIn("reconciliation", decision["primary_signal"])
        chosen = next(e for e in rec["research"]
                      if e["evidence_id"] == decision["selected_evidence_ids"][0])
        self.assertEqual(chosen["subject"], evidence.PERSON)
        self.assertTrue(chosen["authored_by_person"])

    def test_the_person_signal_is_attributed_to_that_person(self):
        rec, contact, decision = self.decision("belmont")
        chosen = next(e for e in rec["research"]
                      if e["evidence_id"] == decision["selected_evidence_ids"][0])
        self.assertEqual(chosen["contact_key"], contact["key"])

    # ------------------------------------------------------------------ C

    def test_a_hiring_signal_becomes_the_hiring_angle(self):
        rec, _, decision = self.decision("caldera")
        self.assertEqual(decision["quality"], evidence.STRONG)
        self.assertIn("hiring", decision["primary_signal"].lower())
        self.assertEqual(decision["source"], "careers_page")

    # ------------------------------------------------------------------ D

    def test_no_signal_falls_back_rather_than_inventing_one(self):
        rec, _, decision = self.decision("driftwood")
        self.assertEqual(decision["quality"], "none")
        self.assertEqual(decision["selected_evidence_ids"], [])
        self.assertIn("persona", decision["reason"])
        self.assertIsNone(decision["primary_signal"])

    def test_the_fallback_message_still_passes_claim_validation(self):
        rec, contact, _ = self.decision("driftwood")
        step = rec["cadence"][contact["key"]]["day1"]
        self.assertEqual(claims.verify(step, rec, contact, []), [])

    # ------------------------------------------------------------------ E

    def test_irrelevant_public_content_is_refused(self):
        rec, _, decision = self.decision("evergreen")
        self.assertEqual(decision["quality"], "none")
        self.assertEqual(decision["selected_evidence_ids"], [])

    def test_the_irrelevant_evidence_was_scored_and_rejected_not_ignored(self):
        rec = self.by_id["evergreen"]
        self.assertTrue(rec["research"], "it was collected")
        self.assertEqual(rec["research"][0]["quality"], evidence.UNUSABLE)

    def test_the_holiday_post_never_reaches_a_message(self):
        rec, contact, _ = self.decision("evergreen")
        step = rec["cadence"][contact["key"]]["day1"]
        body = step.get("body") or ""
        for phrase in ("Happy holidays", "Grateful", "wonderful"):
            self.assertNotIn(phrase, body, phrase)

    # ------------------------------------------------------- no hallucination

    def test_no_message_asserts_anything_unsupported(self):
        problems = []
        for rec in self.recs:
            for contact in personalization.selected_contacts(rec, self.cfg):
                decision = contact.get("personalization") or {}
                chosen = [e for e in rec.get("research") or []
                          if e["evidence_id"] in
                          (decision.get("selected_evidence_ids") or [])]
                for key, step in (rec.get("cadence") or {}).get(
                        contact["key"], {}).items():
                    if key == "day15" and rec["id"] == "evergreen":
                        continue          # the deliberate lint failure
                    problems.extend(claims.verify(step, rec, contact, chosen))
        self.assertEqual(problems, [], problems[:2])

    def test_the_two_cautious_outcomes_are_genuinely_cautious(self):
        """D and E must land in the same place: no invented signal."""
        _, _, d = self.decision("driftwood")
        _, _, e = self.decision("evergreen")
        self.assertEqual(d["quality"], e["quality"])
        self.assertEqual(d["selected_evidence_ids"], e["selected_evidence_ids"])

    def test_the_preview_shows_all_five_conclusions(self):
        html = preview.build(self.campaign, self.recs, self.cfg)
        self.assertIn("Vienna", html)
        self.assertIn("reconciliation", html)
        self.assertIn("hiring", html.lower())
        self.assertIn("no usable evidence", html)

    def test_nothing_called_a_provider(self):
        self.assertEqual(self.cassette.calls, [])


if __name__ == "__main__":
    unittest.main()
