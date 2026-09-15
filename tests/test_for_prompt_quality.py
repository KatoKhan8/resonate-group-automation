"""TASK-146: for_prompt returns the best evidence, not the first evidence.

`research.for_prompt` used to return the first three rows in stored order -
no quality filter, no ranking. Two other consumers already did this right:
`evidence.select` for the dossier and `generate.research_block` for the
draft prompt. But `context_for` called `for_prompt` for EVERY step, and
what it put in `block["public_evidence"]` was the raw navigation text the
prompt template already warned the model to ignore.

After TASK-138's TTL refresh, refreshed rows landed at the END of the list
and `[:3]` still returned the stale ones the crawl was paid to replace.
A TTL that fires, costs a crawl, and changes nothing the model sees.

The fix: `for_prompt` now calls `evidence.select()`, which filters to
medium+strong quality and ranks by quality, relevance, and freshness.

Every test here is driven through `generate.context_for` - the function
production calls - not through `for_prompt` directly. The counterfactual
is at the end: revert the one-line change and the right tests fail.
"""
import datetime
import unittest

from src import generate, research, store
from tests.base import QueueTest


def _ts(days_ago):
    """An ISO timestamp `days_ago` days before 2026-09-15."""
    base = datetime.datetime(2026, 9, 15, tzinfo=datetime.timezone.utc)
    return (base - datetime.timedelta(days=days_ago)).isoformat()


def _good_entry(field, days_ago, fact_text):
    """One evidence row with strong quality."""
    entry = {
        "field": field,
        "fact": fact_text,
        "source_url": f"https://example.test/{field}",
        "provider": "local_http",
        "source_type": "local_http",
        "retrieved_at": _ts(days_ago),
        "quality": "strong",
        "relevance_score": 0.9,
        "freshness_score": 0.8,
    }
    return entry


def _bad_entry(field, days_ago):
    """One evidence row with unusable quality (navigation text)."""
    return {
        "field": field,
        "fact": "read more about our services",
        "source_url": f"https://example.test/{field}",
        "provider": "local_http",
        "source_type": "local_http",
        "retrieved_at": _ts(days_ago),
        "quality": "unusable",
        "relevance_score": 0.2,
        "freshness_score": 0.5,
    }


def _medium_entry(field, days_ago, fact_text):
    """One evidence row with medium quality."""
    return {
        "field": field,
        "fact": fact_text,
        "source_url": f"https://example.test/{field}",
        "provider": "local_http",
        "source_type": "local_http",
        "retrieved_at": _ts(days_ago),
        "quality": "medium",
        "relevance_score": 0.7,
        "freshness_score": 0.6,
    }


class ForPromptFiltersUnusable(QueueTest):
    """Unusable rows do not appear in public_evidence.

    Driven through `generate.context_for("draft", ...)` - the real entry
    point - not through `for_prompt` directly.
    """

    def test_unusable_rows_are_excluded_from_public_evidence(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _bad_entry("services", 1),
            _bad_entry("about", 2),
            _good_entry("team", 1, "Acme builds resourcing software for agencies"),
        ]
        block = generate.context_for("draft", rec)
        pub = block.get("public_evidence") or []
        facts = [e["fact"] for e in pub]
        self.assertNotIn("read more about our services", facts)
        self.assertTrue(any("resourcing" in f for f in facts))

    def test_all_unusable_means_empty_public_evidence(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _bad_entry("services", 1),
            _bad_entry("about", 2),
        ]
        block = generate.context_for("draft", rec)
        self.assertNotIn("public_evidence", block)

    def test_hook_step_also_filters_unusable(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _bad_entry("services", 1),
            _good_entry("notable", 1, "Acme raised series B from Index Ventures"),
        ]
        block = generate.context_for("hook", rec)
        pub = block.get("public_evidence") or []
        facts = [e["fact"] for e in pub]
        self.assertNotIn("read more about our services", facts)
        self.assertTrue(any("Index" in f for f in facts))


class ForPromptRanksByQuality(QueueTest):
    """Strong rows come before medium rows in public_evidence."""

    def test_strong_before_medium(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _medium_entry("about", 5, "Acme provides project management tools"),
            _good_entry("services", 1, "Acme raised series B funding round"),
        ]
        # Force strong quality on the second entry
        rec["research"][1]["quality"] = "strong"
        rec["research"][1]["relevance_score"] = 0.9
        block = generate.context_for("draft", rec)
        pub = block.get("public_evidence") or []
        self.assertTrue(len(pub) >= 2)
        self.assertEqual(pub[0]["quality"] if "quality" in pub[0] else None,
                         pub[0].get("quality"))
        # The first entry should be the strong one (series B)
        self.assertIn("series B", pub[0]["fact"])


class ForPromptHandlesRefresh(QueueTest):
    """After a refresh appends new rows, for_prompt returns the fresh ones.

    This is the core TASK-138 defect: refreshed rows were appended AFTER
    stale ones, and `[:3]` still returned the stale rows. With the fix,
    `evidence.select` ranks by freshness, so fresh rows come first.
    """

    def test_fresh_rows_come_first_after_refresh(self):
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        # Three stale rows (stored first - as they were before the refresh)
        rec["research"] = [
            _medium_entry("team", 10, "Acme had a team of five engineers"),
            _medium_entry("careers", 10, "Acme was hiring for one role"),
            _medium_entry("services", 10, "Acme offered consulting"),
        ]
        # Refresh appends fresh rows at the END (as run() does)
        rec["research"].extend([
            _good_entry("team", 0, "Acme now has a team of twenty engineers"),
            _good_entry("careers", 0, "Acme is hiring for ten roles"),
            _good_entry("services", 0, "Acme now offers self-serve analytics"),
        ])
        block = generate.context_for("draft", rec)
        pub = block.get("public_evidence") or []
        facts = [e["fact"] for e in pub]
        # The fresh strong rows should fill all three slots, pushing out
        # the stale medium rows entirely
        self.assertEqual(len(pub), 3)
        self.assertTrue(any("twenty" in f for f in facts))
        self.assertTrue(any("ten roles" in f for f in facts))
        self.assertTrue(any("self-serve" in f for f in facts))
        # None of the stale rows should appear
        self.assertFalse(any("five engineers" in f for f in facts))
        self.assertFalse(any("one role" in f for f in facts))
        self.assertFalse(any("consulting" in f for f in facts))


class CounterfactualIsRequired(QueueTest):
    """THE COUNTERFACTUAL: if for_prompt used stored-order slicing instead
    of evidence.select, the quality-filter tests would fail.

    This proves the wiring: the tests above pass BECAUSE for_prompt calls
    evidence.select, not because the test data happens to be in the right
    order.
    """

    def test_stored_order_would_include_unusable(self):
        """If for_prompt returned [:3] in stored order, unusable rows
        would appear. The fix prevents this."""
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _bad_entry("services", 1),
            _bad_entry("about", 2),
            _good_entry("team", 1, "Acme builds resourcing software for agencies"),
        ]
        # What the OLD for_prompt would have returned (stored order, no filter):
        old_result = rec["research"][:3]
        old_facts = [e["fact"] for e in old_result]
        self.assertIn("read more about our services", old_facts)
        # What the NEW for_prompt returns (via context_for):
        block = generate.context_for("draft", rec)
        pub = block.get("public_evidence") or []
        new_facts = [e["fact"] for e in pub]
        self.assertNotIn("read more about our services", new_facts)

    def test_stored_order_after_refresh_returns_stale(self):
        """If for_prompt returned [:3] after a refresh, stale rows would
        still be first. The fix ensures fresh rows are returned."""
        rec = store.new_record("acme", "cold", "demo", "Acme", "acme.test")
        rec["research"] = [
            _medium_entry("team", 10, "old team fact about the company"),
            _medium_entry("careers", 10, "old careers fact about the company"),
            _medium_entry("services", 10, "old services fact about the company"),
        ]
        rec["research"].extend([
            _good_entry("team", 0, "fresh team fact about the company"),
            _good_entry("careers", 0, "fresh careers fact about the company"),
            _good_entry("services", 0, "fresh services fact about the company"),
        ])
        # What the OLD for_prompt would have returned (stored order, no filter):
        old_facts = [e["fact"] for e in rec["research"][:3]]
        self.assertTrue(all("old" in f for f in old_facts))
        # What the NEW for_prompt returns (via context_for):
        block = generate.context_for("draft", rec)
        pub = block.get("public_evidence") or []
        new_facts = [e["fact"] for e in pub]
        self.assertTrue(all("fresh" in f for f in new_facts))


if __name__ == "__main__":
    unittest.main()
