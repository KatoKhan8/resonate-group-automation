"""Personalisation quality: five components, one documented rule, no mystery.

The failure mode being guarded against is an opaque score. So the tests here
insist that each component moves for a reason you can name, that the band
follows the written rule rather than a weighting nobody can reconstruct, and
that a stored claim of quality with no evidence behind it is called out rather
than believed.
"""
import unittest

from src import evidence, quality, synthetic
from tests.campaignbase import CampaignTest


class QualityTest(CampaignTest):
    def rec_with(self, *facts, hook="runs delivery across several teams",
                 title="Operations Manager"):
        rec = {"id": "acme", "client": "demo", "domain": "acme.test",
               "company": "Acme", "hook": hook, "research": list(facts)}
        contact = {"key": "acme-c0", "name": "Ann", "title": title,
                   "persona": "champion", "angle": "ops",
                   "personalization": {
                       "selected_evidence_ids": [f["evidence_id"]
                                                 for f in facts]}}
        rec["contacts"] = [contact]
        return rec, contact

    def fact(self, subject=evidence.COMPANY, published_at="2026-08-20",
             source_type="careers_page", url="https://acme.test/careers",
             text=None, contact_key=None):
        return evidence.make(
            text or ("Acme is hiring a delivery manager to improve "
                     "utilisation across the team."),
            url, source_type, "apify", "acme", contact_key=contact_key,
            subject=subject, published_at=published_at, persona="operations",
            angle_words=["utilisation", "capacity"],
            authored_by_person=subject == evidence.PERSON,
            today=synthetic.TODAY)


class TestTheComponents(QualityTest):
    def test_there_are_five_and_they_are_named(self):
        self.assertEqual(len(quality.COMPONENTS), 5)
        rec, contact = self.rec_with(self.fact())
        components = quality.components_for(rec, contact, self.config)
        self.assertEqual(sorted(components), sorted(quality.COMPONENTS))

    def test_every_component_is_between_zero_and_one(self):
        rec, contact = self.rec_with(self.fact())
        for name, value in quality.components_for(rec, contact,
                                                  self.config).items():
            self.assertGreaterEqual(value, 0.0, name)
            self.assertLessEqual(value, 1.0, name)

    def test_industry_and_headcount_alone_are_not_company_specificity(self):
        rec, contact = self.rec_with()
        components = quality.components_for(rec, contact, self.config)
        self.assertLessEqual(components["company_specificity"], 0.25)

    def test_a_dated_attributable_fact_raises_company_specificity(self):
        rec, contact = self.rec_with(self.fact())
        self.assertEqual(
            quality.components_for(rec, contact,
                                   self.config)["company_specificity"], 1.0)

    def test_an_undated_fact_scores_lower_than_a_dated_one(self):
        dated, contact_a = self.rec_with(self.fact())
        undated, contact_b = self.rec_with(self.fact(published_at=None))
        self.assertGreater(
            quality.components_for(dated, contact_a,
                                   self.config)["company_specificity"],
            quality.components_for(undated, contact_b,
                                   self.config)["company_specificity"])

    def test_a_title_is_the_floor_for_person_specificity_not_zero(self):
        """Naming the floor is what stops anyone inventing a LinkedIn post."""
        rec, contact = self.rec_with(self.fact())
        self.assertEqual(
            quality.components_for(rec, contact,
                                   self.config)["person_specificity"], 0.3)

    def test_no_title_and_no_person_evidence_is_zero(self):
        rec, contact = self.rec_with(self.fact(), title=None)
        self.assertEqual(
            quality.components_for(rec, contact,
                                   self.config)["person_specificity"], 0.0)

    def test_person_evidence_beats_a_title(self):
        rec, contact = self.rec_with(
            self.fact(subject=evidence.PERSON, contact_key="acme-c0",
                      text="Ann spoke about capacity planning at a conference."))
        self.assertGreaterEqual(
            quality.components_for(rec, contact,
                                   self.config)["person_specificity"], 0.7)

    def test_old_evidence_scores_lower_on_recency(self):
        fresh, contact_a = self.rec_with(self.fact())
        stale, contact_b = self.rec_with(self.fact(published_at="2019-01-01"))
        self.assertGreater(
            quality.components_for(fresh, contact_a,
                                   self.config)["evidence_recency"],
            quality.components_for(stale, contact_b,
                                   self.config)["evidence_recency"])

    def test_reliability_uses_the_vocabulary_the_code_actually_writes(self):
        """A table scoring names nothing writes would score nothing."""
        for source in quality.SOURCE_RELIABILITY:
            self.assertIsInstance(quality.SOURCE_RELIABILITY[source], float)
        rec, contact = self.rec_with(self.fact(source_type="apify"))
        self.assertGreater(
            quality.components_for(rec, contact,
                                   self.config)["evidence_reliability"], 0.0)

    def test_an_unknown_source_is_not_treated_as_reliable(self):
        rec, contact = self.rec_with(self.fact(source_type="some_new_thing"))
        self.assertEqual(
            quality.components_for(rec, contact,
                                   self.config)["evidence_reliability"],
            quality.DEFAULT_RELIABILITY)

    def test_no_evidence_puts_every_evidence_component_at_zero(self):
        rec, contact = self.rec_with()
        components = quality.components_for(rec, contact, self.config)
        for name in ("evidence_recency", "evidence_reliability",
                     "persona_relevance"):
            self.assertEqual(components[name], 0.0, name)


class TestTheBand(QualityTest):
    def test_the_three_bands_are_ordered(self):
        self.assertEqual(quality.BANDS, ("low", "medium", "high"))
        self.assertLess(quality.BAND_ORDER["low"], quality.BAND_ORDER["high"])

    def test_a_specific_recent_relevant_fact_is_high(self):
        rec, contact = self.rec_with(self.fact())
        self.assertEqual(quality.assess(rec, contact, self.config)["band"],
                         quality.HIGH)

    def test_nothing_specific_is_low_however_good_anything_else_is(self):
        rec, contact = self.rec_with(hook=None)
        components = quality.components_for(rec, contact, self.config)
        self.assertEqual(components["company_specificity"], 0.0)
        self.assertEqual(quality.band_for(components), quality.LOW)

    def test_the_band_follows_the_written_rule_not_an_average(self):
        """Every component perfect except specificity still fails."""
        components = {name: 1.0 for name in quality.COMPONENTS}
        components["company_specificity"] = 0.0
        self.assertEqual(quality.band_for(components), quality.LOW)

    def test_stale_but_specific_evidence_lands_in_the_middle(self):
        rec, contact = self.rec_with(self.fact(published_at="2025-01-01"))
        band = quality.assess(rec, contact, self.config)["band"]
        self.assertEqual(band, quality.MEDIUM)

    def test_every_band_comes_with_a_sentence(self):
        for components in ({name: 1.0 for name in quality.COMPONENTS},
                           {name: 0.5 for name in quality.COMPONENTS},
                           {name: 0.0 for name in quality.COMPONENTS}):
            band = quality.band_for(components)
            self.assertTrue(quality.why(components, band))

    def test_the_sentence_names_the_weakest_component_when_it_is_not_high(self):
        components = {name: 1.0 for name in quality.COMPONENTS}
        components["evidence_recency"] = 0.1
        band = quality.band_for(components)
        self.assertIn("evidence_recency", quality.why(components, band))


class TestThePolicy(QualityTest):
    def policy(self, **block):
        return {"personalization": {"quality": block}}

    def test_the_default_holds_nothing(self):
        rec, contact = self.rec_with(hook=None)
        result = quality.assess(rec, contact, self.config)
        self.assertEqual(result["band"], quality.LOW)
        self.assertFalse(result["held"])

    def test_a_minimum_band_holds_what_falls_below_it(self):
        rec, contact = self.rec_with(hook=None)
        result = quality.assess(rec, contact, self.policy(minimum_band="high"))
        self.assertFalse(result["meets_minimum"])
        self.assertTrue(result["held"])

    def test_what_meets_the_minimum_is_not_held(self):
        rec, contact = self.rec_with(self.fact())
        result = quality.assess(rec, contact, self.policy(minimum_band="high"))
        self.assertTrue(result["meets_minimum"])
        self.assertFalse(result["held"])

    def test_holding_can_be_switched_off_without_changing_the_band(self):
        rec, contact = self.rec_with(hook=None)
        result = quality.assess(rec, contact,
                                self.policy(minimum_band="high",
                                            hold_below_minimum=False))
        self.assertFalse(result["meets_minimum"])
        self.assertFalse(result["held"])

    def test_an_unknown_band_name_is_ignored_rather_than_obeyed(self):
        settings = quality.settings(self.policy(minimum_band="excellent"))
        self.assertEqual(settings["minimum_band"], quality.LOW)


class TestContradictionsAreCalledOut(QualityTest):
    def test_a_claim_of_quality_with_no_evidence_is_flagged(self):
        rec, contact = self.rec_with()
        contact["personalization"]["quality"] = "strong"
        result = quality.assess(rec, contact, self.config)
        self.assertTrue(result["warnings"])
        self.assertIn("selected no evidence", result["warnings"][0])

    def test_the_claim_is_not_counted_towards_the_band(self):
        rec, contact = self.rec_with(hook=None)
        contact["personalization"]["quality"] = "strong"
        self.assertEqual(quality.assess(rec, contact, self.config)["band"],
                         quality.LOW)

    def test_evidence_that_no_longer_exists_is_flagged(self):
        rec, contact = self.rec_with(self.fact())
        contact["personalization"]["selected_evidence_ids"].append("gone")
        result = quality.assess(rec, contact, self.config)
        self.assertTrue(any("no longer exist" in w for w in result["warnings"]))


class TestTheDistribution(QualityTest):
    def test_it_counts_every_band_and_the_weakest_component(self):
        recs = synthetic.dataset(56, self.config)
        result = quality.distribution(recs, self.config)
        self.assertEqual(sum(result["bands"].values()), result["contacts"])
        self.assertEqual(sum(result["weakest_component"].values()),
                         result["contacts"])

    def test_shares_are_none_rather_than_zero_with_nothing_to_divide(self):
        result = quality.distribution([], self.config)
        for band in quality.BANDS:
            self.assertIsNone(result["share"][band])

    def test_the_synthetic_dataset_is_internally_consistent(self):
        """It claimed strong personalisation with no evidence until this
        module found it. Keeping the check stops it coming back."""
        recs = synthetic.dataset(56, self.config)
        self.assertEqual(quality.distribution(recs, self.config)["warnings"], 0)

    def test_it_calls_no_provider(self):
        quality.distribution(synthetic.dataset(28, self.config), self.config)
        self.assertEqual(self.cassette.calls, [])


if __name__ == "__main__":
    unittest.main()
