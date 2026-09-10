#!/usr/bin/env python3
"""One canonical evidence representation, and every producer honours it.

THE DEFECT THIS PINS. `icp.confidence_components` scores `source_quality` from
`item["quality"]` and `recency` from `item["freshness_score"]`.
`apify.evidence_from_items` hand-built a nine-key dict and wrote neither, so
both scored 0.0 - "0 usable piece(s) of evidence" - about five pages that had
been retrieved perfectly well. `claims` licenses a sentence by `evidence_id`,
which was also absent, so nothing written from a scraped page could be cited.

Two producers of one record shape, and the consumers were written against the
other one. The tests below are about the CONTRACT rather than about Apify: a
third producer added next year fails them the same way.

And separately: boilerplate must not become decision evidence. A cookie policy
is not weak evidence about a company, it is not evidence about a company, and
`segments.text_of` was feeding 2,488 words of one to a vertical classifier.
"""
import unittest

from src import evidence, icp, segments
from src.providers import apify

# Every field a consumer in this repository reads off an evidence object.
CONTRACT = ("evidence_id", "fact", "source_type", "provider", "source_url",
            "published_at", "retrieved_at", "subject", "record_id",
            "age_days", "freshness_score", "freshness_bucket",
            "relevance_score", "relevance_reasons", "quality")

REAL_PAGE = ("We are a design services agency of forty-five people in Dublin. "
             "Our delivery team runs utilisation and capacity reporting across "
             "twelve concurrent client projects, and we opened a second studio "
             "in Berlin last year.")

COOKIE_POLICY = (("We use cookies. Cookie consent under GDPR means your "
                  "personal data processing requires consent. Privacy policy "
                  "cookies third party opt-out legitimate interest. ") * 12)

NAV_ONLY = "Skip to content. Main menu. Sign in. Back to top. Read more."


def items(*rows):
    """Rows as the crawler returns them. `crawl.httpStatusCode` is required:
    `ok(None)` is False, so a row that does not say it loaded is dropped."""
    out = []
    for i, (text, extra) in enumerate(rows):
        row = {"url": "https://example.test/p%d" % i, "text": text,
               "crawl": {"httpStatusCode": 200}}
        row.update(extra)
        out.append(row)
    return out


def build(rows, record_id="acme-test", angle_words=("utilisation", "capacity")):
    return apify.evidence_from_items(
        rows, "example.test", apify.DEFAULT_ACTOR, sources_by_url={},
        conf=apify.settings({}), record_id=record_id,
        angle_words=list(angle_words))


class EveryProducerEmitsTheSameShape(unittest.TestCase):

    def test_apify_evidence_carries_every_contract_field(self):
        made = build(items((REAL_PAGE, {})))
        self.assertEqual(len(made), 1)
        missing = [f for f in CONTRACT if f not in made[0]]
        self.assertEqual(missing, [],
                         "apify evidence is missing %s; a consumer reading "
                         "those gets None and scores it as zero" % (missing,))

    def test_it_matches_what_evidence_make_produces(self):
        """Field for field, not merely 'has the important ones'."""
        canonical = evidence.make(REAL_PAGE, "https://example.test/p0",
                                  "apify", "apify", "acme-test")
        made = build(items((REAL_PAGE, {})))[0]
        for field in CONTRACT:
            self.assertIn(field, made)
        # The extra keys are provenance, deliberately kept, and named here so
        # adding a third one is a decision rather than a drift.
        extra = set(made) - set(canonical)
        self.assertEqual(extra, {"actor", "field", "title"})

    def test_quality_is_a_real_verdict_not_a_missing_key(self):
        made = build(items((REAL_PAGE, {})))[0]
        self.assertIn(made["quality"],
                      (evidence.STRONG, evidence.MEDIUM_Q, evidence.WEAK))

    def test_the_evidence_id_binds_to_the_record_it_was_gathered_for(self):
        """Not stamped on afterwards. The id is DERIVED from the record."""
        one = build(items((REAL_PAGE, {})), record_id="acme-test")[0]
        two = build(items((REAL_PAGE, {})), record_id="other-test")[0]
        self.assertNotEqual(one["evidence_id"], two["evidence_id"])
        self.assertEqual(one["record_id"], "acme-test")

    def test_an_undated_page_is_unknown_rather_than_fresh(self):
        """A crawl date is when WE looked, and must not become a publish date."""
        made = build(items((REAL_PAGE, {"crawledAt": "2026-09-10"})))[0]
        self.assertIsNone(made["published_at"])
        self.assertEqual(made["freshness_bucket"], evidence.UNKNOWN)
        self.assertEqual(made["retrieved_at"], "2026-09-10")


class ConfidenceCanSeeTheEvidence(unittest.TestCase):
    """The whole point: the consumer must read a real number now."""

    def components(self, research):
        return icp.confidence_components(
            {"research": research}, scored=5, missing=["a"] * 7,
            segment={"vertical": "agency"}, thresholds={})

    def test_a_usable_page_is_counted_as_usable(self):
        got = self.components(build(items((REAL_PAGE, {}))))
        self.assertGreater(got["source_quality"]["score"], 0.0,
                           "retrieved, usable evidence still scores zero")

    def test_the_old_hand_built_shape_would_have_scored_zero(self):
        """The regression, stated as a test rather than as a memory."""
        old_shape = [{"source_type": "apify", "provider": "apify",
                      "source_url": "https://example.test/p0",
                      "fact": REAL_PAGE, "actor": "x", "field": "y"}]
        self.assertEqual(self.components(old_shape)["source_quality"]["score"],
                         0.0)


class BoilerplateIsNotEvidence(unittest.TestCase):

    def test_a_cookie_policy_is_refused(self):
        self.assertTrue(evidence.boilerplate(COOKIE_POLICY))

    def test_a_nav_menu_is_refused(self):
        self.assertTrue(evidence.boilerplate(NAV_ONLY))

    def test_an_empty_page_is_refused(self):
        self.assertTrue(evidence.boilerplate(""))
        self.assertTrue(evidence.boilerplate("   "))

    def test_a_near_empty_fact_is_refused_by_quality(self):
        """Found by a mutation, not by writing this test first.

        Removing the four-word floor from `quality` broke nothing: the only
        "empty" cases covered were "" and "   ", which `boilerplate` catches
        as empty before the floor is reached. A two-word fragment is neither
        empty nor boilerplate, and it is not a claim either.
        """
        for fragment in ("Acme grew", "hiring", "Dublin office"):
            self.assertEqual(evidence.quality(1.0, evidence.HIGH, fragment),
                             evidence.UNUSABLE, fragment)

    def test_a_password_wall_is_refused(self):
        self.assertTrue(evidence.boilerplate(
            "About Us | London | 16K Agency Please enter the password below."))

    def test_a_real_page_with_a_cookie_footer_survives(self):
        """The over-filtering failure, pinned so it cannot come back.

        An earlier version rejected any short-ish text containing one cookie
        phrase, which loses exactly the legitimate evidence this exists to
        protect.
        """
        page = "We use cookies to improve your experience. " + REAL_PAGE
        self.assertEqual(evidence.boilerplate(page), "")

    def test_a_short_specific_claim_survives(self):
        """Six words, and precisely what the system is looking for."""
        self.assertEqual(
            evidence.boilerplate("Acme opened a Vienna delivery office."), "")

    def test_quality_refuses_it_whatever_its_relevance(self):
        """Relevance must not be able to argue boilerplate back in.

        "read more about our capacity" would match an angle word.
        """
        self.assertEqual(
            evidence.quality(1.0, evidence.HIGH, COOKIE_POLICY),
            evidence.UNUSABLE)


class BoilerplateCannotClassifyACompany(unittest.TestCase):

    def rec(self, *facts):
        return {"company": "Acme", "company_facts": {},
                "research": [{"fact": f} for f in facts]}

    def test_a_policy_document_is_not_part_of_the_classifier_text(self):
        text = segments.text_of(self.rec(REAL_PAGE, COOKIE_POLICY))
        self.assertIn("utilisation", text)
        self.assertNotIn("legitimate interest", text)

    def test_evidence_marked_unusable_is_excluded_even_if_it_reads_clean(self):
        """Defence in depth: the stored verdict is honoured, not recomputed."""
        rec = {"company": "Acme", "company_facts": {},
               "research": [{"fact": REAL_PAGE, "quality": evidence.UNUSABLE}]}
        self.assertNotIn("utilisation", segments.text_of(rec))

    def test_a_real_page_still_classifies(self):
        self.assertIn("utilisation", segments.text_of(self.rec(REAL_PAGE)))


class MalformedAndForeignEvidenceIsRefused(unittest.TestCase):

    def test_a_non_dict_row_is_skipped(self):
        self.assertEqual(build(["not a dict", None, 42]), [])

    def test_a_row_with_no_text_is_skipped(self):
        self.assertEqual(build(items(("", {}))), [])

    def test_a_page_from_another_company_is_dropped(self):
        rows = [{"url": "https://someone-else.test/about", "text": REAL_PAGE,
                 "crawl": {"httpStatusCode": 200}}]
        self.assertEqual(build(rows), [])

    def test_a_page_that_did_not_load_is_dropped(self):
        rows = [{"url": "https://example.test/p0", "text": REAL_PAGE,
                 "crawl": {"httpStatusCode": 404}}]
        self.assertEqual(build(rows), [])


if __name__ == "__main__":
    unittest.main()
