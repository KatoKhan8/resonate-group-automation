"""One canonical scale for where evidence came from.

The failure this guards against is a table that scores names nothing writes
while the names that are written fall through to the default - a confident
number about nothing. So these tests start from what the code actually emits
and work back to the table, rather than the other way round.

The second failure is subtler: reliability quietly becoming a way to promote
weak evidence. It must never be able to lift a band on its own, and quantity
of unrecognised sources must never add up to reliability.
"""
import unittest

from src import demo, evidence, quality, synthetic
from src.providers import apify
from tests.campaignbase import CampaignTest


def item(source_type, field=None, **extra):
    row = {"source_type": source_type}
    if field is not None:
        row["field"] = field
    row.update(extra)
    return row


class TestEverySourceTheSystemEmitsIsScored(unittest.TestCase):
    def test_every_crawl_page_kind_resolves_to_a_canonical_kind(self):
        """apify.SOURCES is what a live crawl can come back as."""
        for field in apify.SOURCES:
            resolved = quality.canonical_source(item("apify", field))
            self.assertIn(resolved, quality.CANONICAL_RELIABILITY,
                          f"{field} falls through to unknown")

    def test_the_crawl_field_list_matches_the_provider(self):
        """If apify grows a source, this fails rather than silently defaulting."""
        self.assertEqual(set(quality.CRAWL_FIELDS), set(apify.SOURCES))

    def test_every_source_type_the_demo_emits_is_scored(self):
        for rows in demo.SIGNALS.values():
            for row in rows:
                source_type = row[1]
                self.assertIn(quality.canonical_source(item(source_type)),
                              quality.CANONICAL_RELIABILITY, source_type)

    def test_every_source_type_the_synthetic_dataset_emits_is_scored(self):
        for rec in synthetic.dataset(len(synthetic.SHAPES)):
            for row in rec.get("research") or []:
                self.assertIn(quality.canonical_source(row),
                              quality.CANONICAL_RELIABILITY,
                              row.get("source_type"))

    def test_the_alias_table_only_points_at_canonical_kinds(self):
        for alias, kind in quality.SOURCE_ALIASES.items():
            self.assertIn(kind, quality.CANONICAL_RELIABILITY,
                          f"{alias} aliases a kind that has no score")

    def test_no_alias_shadows_a_canonical_name(self):
        """Two scales for one concept is how they drift apart."""
        overlap = set(quality.SOURCE_ALIASES) & set(quality.CANONICAL_RELIABILITY)
        self.assertEqual(overlap, set())

    def test_known_sources_lists_both_vocabularies(self):
        known = quality.known_sources()
        for name in ("careers", "careers_page", "company_announcement",
                     "public_post", "apify"):
            self.assertIn(name, known, name)


class TestTheIntendedScores(unittest.TestCase):
    def test_company_announcement_is_first_party_and_dated(self):
        """The case that started this: a company announcing its own news."""
        self.assertEqual(quality.reliability_of(item("company_announcement")),
                         0.95)

    def test_a_careers_page_scores_the_same_by_either_name(self):
        self.assertEqual(quality.reliability_of(item("careers_page")),
                         quality.reliability_of(item("apify", "careers")))

    def test_first_party_dated_sources_outrank_standing_content(self):
        dated = min(quality.reliability_of(item(name)) for name in
                    ("careers_page", "company_announcement", "press_release"))
        standing = max(quality.reliability_of(item(name)) for name in
                       ("about_page", "team_page", "homepage"))
        self.assertGreater(dated, standing)

    def test_standing_company_content_still_outranks_unknown(self):
        for name in ("about_page", "team_page", "homepage"):
            self.assertGreater(quality.reliability_of(item(name)),
                               quality.DEFAULT_RELIABILITY, name)

    def test_person_authored_content_is_attributable(self):
        for name in ("public_post", "interview", "conference"):
            self.assertGreaterEqual(quality.reliability_of(item(name)), 0.8,
                                    name)

    def test_structured_provider_data_is_dependable_but_not_specific(self):
        """Paid for and reliable; never enough on its own to feel written."""
        self.assertLess(quality.reliability_of(item("provider_structured")),
                        quality.reliability_of(item("careers_page")))
        self.assertGreater(quality.reliability_of(item("provider_structured")),
                           quality.DEFAULT_RELIABILITY)

    def test_a_crawl_is_scored_by_the_page_not_by_the_crawl(self):
        careers = quality.reliability_of(item("apify", "careers"))
        homepage = quality.reliability_of(item("apify", "company_website"))
        self.assertGreater(careers, homepage,
                           "'apify' says how we fetched it, not how good it is")


class TestTheUnknownStaysConservative(unittest.TestCase):
    def test_an_unrecognised_source_type_gets_the_default(self):
        for name in ("some_new_thing", "chatgpt_said_so", "", None):
            self.assertEqual(quality.reliability_of(item(name)),
                             quality.DEFAULT_RELIABILITY, repr(name))

    def test_an_unrecognised_crawl_field_gets_the_default(self):
        self.assertEqual(quality.reliability_of(item("apify", "instagram")),
                         quality.DEFAULT_RELIABILITY)

    def test_a_missing_source_type_is_unknown_rather_than_assumed(self):
        self.assertEqual(quality.canonical_source({}), quality.UNKNOWN_SOURCE)

    def test_the_default_sits_below_the_threshold_that_counts_as_present(self):
        """Structural, not incidental: unknown-sourced evidence must not be
        able to reach even the middle band on reliability alone."""
        self.assertLess(quality.DEFAULT_RELIABILITY, quality.PRESENT)

    def test_quantity_of_unknown_sources_does_not_manufacture_reliability(self):
        """Six unrecognised pages saying the same thing are six unrecognised
        pages. Without the corroboration floor this scored 0.55."""
        chosen = [item("mystery") for _ in range(6)]
        self.assertEqual(quality.evidence_reliability(chosen),
                         quality.DEFAULT_RELIABILITY)

    def test_recognised_sources_do_corroborate(self):
        one = quality.evidence_reliability([item("about_page")])
        three = quality.evidence_reliability([item("about_page")] * 3)
        self.assertGreater(three, one)

    def test_an_unknown_source_never_corroborates_a_known_one(self):
        known = quality.evidence_reliability([item("careers_page")])
        padded = quality.evidence_reliability(
            [item("careers_page")] + [item("mystery")] * 4)
        self.assertEqual(known, padded)


class TestReliabilityCannotPromoteWeakEvidence(CampaignTest):
    """The rule the whole table is subordinate to.

    Changing a source's score must not be able to turn evidence that supports
    nothing into high-quality personalisation. Specificity, recency and
    relevance are separate components for exactly this reason.
    """

    def contact_with(self, *facts):
        rec = {"id": "acme", "client": "demo", "domain": "acme.test",
               "company": "Acme", "hook": None, "research": list(facts)}
        contact = {"key": "c0", "name": "Ann", "title": "Operations Manager",
                   "persona": "champion", "angle": "ops",
                   "personalization": {"selected_evidence_ids":
                                       [f["evidence_id"] for f in facts]}}
        rec["contacts"] = [contact]
        return rec, contact

    def fact(self, source_type, text="Acme is hiring a delivery manager to "
                                     "improve utilisation across the team.",
             published_at="2026-08-20"):
        return evidence.make(text, "https://acme.test/x", source_type, "apify",
                             "acme", published_at=published_at,
                             persona="operations",
                             angle_words=["utilisation", "capacity"],
                             today=synthetic.TODAY)

    def test_a_perfect_source_cannot_rescue_missing_specificity(self):
        components = {name: 0.0 for name in quality.COMPONENTS}
        components["evidence_reliability"] = 1.0
        self.assertEqual(quality.band_for(components), quality.LOW)

    def test_a_perfect_source_cannot_rescue_stale_irrelevant_evidence(self):
        rec, contact = self.contact_with(
            self.fact("company_announcement",
                      text="Acme was founded in 1998 by two brothers.",
                      published_at="2015-01-01"))
        result = quality.assess(rec, contact, self.config)
        self.assertNotEqual(result["band"], quality.HIGH)

    def raise_unknown_to_perfect(self, rec, contact):
        """Score the record with every unknown source treated as flawless.

        This is the change the table makes possible, simulated: somebody
        decides an unrecognised source is trustworthy. What must survive it is
        that evidence with nothing behind it stays low.
        """
        original = dict(quality.CANONICAL_RELIABILITY)
        try:
            quality.CANONICAL_RELIABILITY[quality.UNKNOWN_SOURCE] = 1.0
            return quality.assess(rec, contact, self.config)
        finally:
            quality.CANONICAL_RELIABILITY.clear()
            quality.CANONICAL_RELIABILITY.update(original)

    def test_raising_a_score_cannot_rescue_undated_evidence(self):
        rec, contact = self.contact_with(
            self.fact("mystery_source", published_at=None))
        self.assertNotEqual(self.raise_unknown_to_perfect(rec, contact)["band"],
                            quality.HIGH)

    def test_raising_a_score_cannot_rescue_stale_evidence(self):
        rec, contact = self.contact_with(
            self.fact("mystery_source", published_at="2015-01-01"))
        self.assertNotEqual(self.raise_unknown_to_perfect(rec, contact)["band"],
                            quality.HIGH)

    def test_raising_a_score_cannot_rescue_irrelevant_evidence(self):
        rec, contact = self.contact_with(
            self.fact("mystery_source",
                      text="Acme was founded in 1998 by two brothers."))
        self.assertNotEqual(self.raise_unknown_to_perfect(rec, contact)["band"],
                            quality.HIGH)

    def test_raising_a_score_cannot_rescue_evidence_with_no_source_url(self):
        fact = self.fact("mystery_source")
        fact["source_url"] = None
        rec, contact = self.contact_with(fact)
        self.assertNotEqual(self.raise_unknown_to_perfect(rec, contact)["band"],
                            quality.HIGH)

    def test_recency_relevance_and_reliability_each_gate_the_top_band(self):
        for name in ("evidence_recency", "persona_relevance",
                     "evidence_reliability"):
            components = {n: 1.0 for n in quality.COMPONENTS}
            components[name] = 0.1
            self.assertNotEqual(quality.band_for(components), quality.HIGH,
                                f"{name} at 0.1 still reached HIGH")

    def test_a_strong_person_fact_substitutes_for_a_company_fact(self):
        """Deliberate: a message built on something true about this person is
        personalised whether or not there is also a company fact."""
        components = {n: 1.0 for n in quality.COMPONENTS}
        components["company_specificity"] = 0.1
        self.assertEqual(quality.band_for(components), quality.HIGH)

    def test_but_nothing_specific_at_all_still_caps_at_low(self):
        components = {n: 1.0 for n in quality.COMPONENTS}
        components["company_specificity"] = 0.0
        self.assertEqual(quality.band_for(components), quality.LOW)

    def test_high_still_requires_every_component_not_just_the_source(self):
        rec, contact = self.contact_with(self.fact("careers_page"))
        result = quality.assess(rec, contact, self.config)
        self.assertEqual(result["band"], quality.HIGH)
        for name in ("company_specificity", "evidence_recency",
                     "persona_relevance", "evidence_reliability"):
            self.assertGreaterEqual(result["components"][name],
                                    quality.STRONG_ENOUGH, name)

    def test_the_demo_announcement_now_scores_as_first_party(self):
        """The card that prompted this: Northwind's own Vienna announcement."""
        campaign, recs, config = demo.build(self.config)
        northwind = next(r for r in recs if r["id"] == "northwind")
        result = quality.for_record(northwind, config)[0]
        self.assertEqual(result["components"]["evidence_reliability"], 0.95)
        self.assertEqual(result["band"], quality.MEDIUM)
        self.assertIn("person_specificity", result["why"])


if __name__ == "__main__":
    unittest.main()
