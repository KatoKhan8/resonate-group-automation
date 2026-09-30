#!/usr/bin/env python3
"""Free-crawled evidence was retained unscored, so none of it could be used.

`research._from_the_site_itself` built each retained page from
`webfetch._page` and added two fields: `record_id` and `retrieved_at`. Its
comment said `_page` "already returns the evidence shape". It returns the
SHAPE and not the SCORE - no `quality`, no `relevance_score` - and
`evidence.select` admits only rows whose `quality` is in `USABLE`.

So every row the free crawler ever retained was inadmissible. Gathered,
stored, counted in `len(rec["research"])`, and unable to reach a prompt. It
looked like evidence at every point except the one that matters.

MEASURED 2026-09-30, researching eight accounts in the operator's approved
source order:

    rows 0 -> 2, 0 -> 3, 0 -> 4 ...   admitted stayed 0 on seven of eight

Every new row carried `quality=None, relevance_score=None`. The single
account that gained an admitted row got it from the PAID Apify leg. Rescoring
two of the rejected rows through `evidence.make` returns `medium` at 0.70,
comfortably over `MIN_RELEVANCE` 0.65 - the evidence was usable all along and
the scorer was never called on it.

THE BAR IS NOT TOUCHED BY THIS. `MIN_RELEVANCE` and `USABLE` are unchanged;
a row that scores WEAK is still dropped. The only change is that the free
leg's rows are now SCORED, by the same `evidence.make` the paid leg uses,
rather than arriving with no score and failing by default.
"""
import unittest

from src import evidence as ev, research, webfetch


BODY = ("CG Life is an integrated agency for life sciences. The team works "
        "with biotech and pharmaceutical companies on launches, and has "
        "opened a second office while hiring 12 delivery project managers "
        "across its accounts.")


class APageThatIsRetainedIsScored(unittest.TestCase):
    def test_webfetch_itself_does_not_score(self):
        """The premise, asserted rather than assumed.

        If `_page` ever starts scoring, the fix below becomes redundant and
        this test says so instead of quietly passing.
        """
        page = webfetch._page("https://cglife.com/", "about", 200,
                              "<html><body>%s</body></html>" % BODY,
                              {"max_text_chars_per_page": 4000})
        self.assertIsNone(page.get("quality"))
        self.assertIsNone(page.get("relevance_score"))

    def test_evidence_make_scores_the_same_text(self):
        """And the scorer admits it, so the row was never the problem."""
        scored = ev.make(fact=BODY, source_url="https://cglife.com/",
                         source_type="local_http", provider="local_http",
                         record_id="cglife-com")
        self.assertIn(scored["quality"], ev.USABLE)
        self.assertGreaterEqual(scored["relevance_score"], ev.MIN_RELEVANCE)

    def test_an_unscored_row_is_admitted_by_nothing(self):
        """Why an unscored row is not a harmless omission."""
        unscored = webfetch._page("https://cglife.com/", "about", 200,
                                  "<html><body>%s</body></html>" % BODY,
                                  {"max_text_chars_per_page": 4000})
        self.assertEqual([], list(ev.select([unscored]) or ()),
                         "an unscored row reached a prompt")

    def test_a_scored_row_is_admitted(self):
        """THE CONTROL. Without it the test above passes for a filter that
        admits nothing at all."""
        scored = ev.make(fact=BODY, source_url="https://cglife.com/",
                         source_type="local_http", provider="local_http",
                         record_id="cglife-com")
        self.assertEqual(1, len(list(ev.select([scored]) or ())))


class TheBarIsUnchanged(unittest.TestCase):
    def test_a_weak_page_is_still_dropped(self):
        """Scoring the free leg is not admitting the free leg."""
        thin = ev.make(fact="Home About Contact Careers Privacy Cookies",
                       source_url="https://cglife.com/",
                       source_type="local_http", provider="local_http",
                       record_id="cglife-com")
        self.assertNotIn(thin["quality"], ev.USABLE)
        self.assertEqual([], list(ev.select([thin]) or ()))

    def test_the_thresholds_are_what_they_were(self):
        self.assertEqual(0.65, ev.MIN_RELEVANCE)
        self.assertEqual(("strong", "medium"), tuple(ev.USABLE))


class ProvenanceSurvivesTheScoring(unittest.TestCase):
    """The original code avoided re-mapping to keep the hash. It must stay."""

    def test_the_free_legs_own_fields_are_merged_back(self):
        page = webfetch._page("https://cglife.com/about/", "about", 200,
                              "<html><body>%s</body></html>" % BODY,
                              {"max_text_chars_per_page": 4000})
        scored = ev.make(fact=page["fact"], source_url=page["source_url"],
                         source_type="local_http", provider="local_http",
                         record_id="cglife-com")
        merged = dict(scored, **{k: v for k, v in page.items()
                                 if k in ("content_hash", "http_status",
                                          "chars", "field")})
        for field in ("content_hash", "http_status", "chars", "field"):
            self.assertEqual(page[field], merged[field], field)
        for field in ("quality", "relevance_score", "source_url", "provider"):
            self.assertIsNotNone(merged[field], field)


class TheFixIsOnTheRealPath(unittest.TestCase):
    """A scorer nothing calls is the defect this file is about.

    Driven through `_from_the_site_itself` with the fetch stubbed, and
    asserted on the ROWS IT WROTE onto the record - not on the source text.
    Searching source for `ev.make(` would pass on a comment.
    """

    def setUp(self):
        research.crawl_cache_clear()
        self.addCleanup(research.crawl_cache_clear)
        # The persisted layer answers before the fetch and would hand back
        # somebody else's cached rows for this domain.
        self._persisted = research._persisted_cache
        research._persisted_cache = {}
        self.addCleanup(
            setattr, research, "_persisted_cache", self._persisted)

    def test_the_rows_it_writes_onto_the_record_are_scored(self):
        from src import webfetch as wf

        page = wf._page("https://cglife.test/about", "about", 200,
                        "<html><body>%s</body></html>" % BODY,
                        {"max_text_chars_per_page": 4000})
        real = wf.research
        wf.research = lambda domain, config=None, now=None: {
            "outcome": "ok", "pages": [page],
            "retrieved_at": "2026-09-30T00:00:00+00:00"}
        self.addCleanup(setattr, wf, "research", real)

        rec = {"id": "cglife-test", "domain": "cglife.test", "research": []}
        out = research._from_the_site_itself(rec, {})
        self.assertTrue(out, "the free leg retained nothing to score")
        for row in out:
            self.assertIsNotNone(row.get("quality"), row.get("source_url"))
            self.assertIsNotNone(row.get("relevance_score"))
        self.assertTrue(
            list(ev.select(out) or ()),
            "the free leg's own rows are still admitted by nothing")


if __name__ == "__main__":
    unittest.main()
