#!/usr/bin/env python3
"""Tests for the TASK-040 provider pagination benchmark.

Validates:
- Request count model is correct (pages_for, campaign_lead_walk, etc.)
- Synthetic reply rows have the shape the local processing path expects
- The local processing measurement produces valid numbers
- The model's key invariant: provider requests dominate local compute
"""
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmarks.provider_pagination import (
    pages_for,
    campaign_lead_walk_requests,
    reply_feed_walk_requests,
    sender_inventory_requests,
    collision_check_requests_per_domain,
    membership_check_requests,
    reply_to_step_join_requests,
    full_campaign_audit_requests,
    _fake_reply_row,
    _fake_page,
    measure_local_page_processing,
    measure_store_transaction_at_size,
    measure_refuse_history_loss_at_size,
    PAGE_SIZE,
)


class TestPagesFor(unittest.TestCase):
    """The pagination math is the foundation of every request count."""

    def test_zero_is_zero(self):
        self.assertEqual(pages_for(0), 0)

    def test_exact_page(self):
        # 15 rows at 15/page = 1 page
        self.assertEqual(pages_for(15), 1)

    def test_one_over(self):
        # 16 rows at 15/page = 2 pages
        self.assertEqual(pages_for(16), 2)

    def test_campaign_352(self):
        # 95,000 at 15/page = 6334 pages
        self.assertEqual(pages_for(95000), math.ceil(95000 / 15))
        self.assertEqual(pages_for(95000), 6334)

    def test_one_row_is_one_page(self):
        self.assertEqual(pages_for(1), 1)


class TestRequestCounts(unittest.TestCase):
    """Each operation's request count matches the pagination model."""

    def test_campaign_lead_walk(self):
        # 100 leads at 15/page = 7 pages
        self.assertEqual(campaign_lead_walk_requests(100), 7)
        # 15 leads = 1 page
        self.assertEqual(campaign_lead_walk_requests(15), 1)

    def test_reply_feed_walk(self):
        self.assertEqual(reply_feed_walk_requests(100), 7)
        self.assertEqual(reply_feed_walk_requests(15), 1)

    def test_sender_inventory(self):
        # 225 senders at 15/page = 15 pages
        self.assertEqual(sender_inventory_requests(225), 15)

    def test_collision_check_capped(self):
        # A domain search returning 500 matches is capped at 200 (BROAD_MATCH)
        # 200 at 15/page = 14 pages
        self.assertEqual(collision_check_requests_per_domain(50000, 0.01),
                         pages_for(200))

    def test_membership_check_is_one_per_lead(self):
        self.assertEqual(membership_check_requests(10), 10)
        self.assertEqual(membership_check_requests(1), 1)

    def test_reply_to_step_join_is_one_per_reply(self):
        self.assertEqual(reply_to_step_join_requests(2000), 2000)

    def test_full_audit_components(self):
        # Full audit = lead walk + reply walk + sender walk + reply join
        n_leads, n_replies, n_senders = 100, 50, 30
        expected = (campaign_lead_walk_requests(n_leads)
                    + reply_feed_walk_requests(n_replies)
                    + sender_inventory_requests(n_senders)
                    + reply_to_step_join_requests(n_replies))
        self.assertEqual(
            full_campaign_audit_requests(n_leads, n_replies, n_senders),
            expected)


class TestFakeReplyRow(unittest.TestCase):
    """Synthetic reply rows must have the shape the local path expects."""

    def test_has_custom_variables(self):
        row = _fake_reply_row(0)
        custom = {v["name"]: v["value"]
                  for v in row["custom_variables"]
                  if isinstance(v, dict)}
        self.assertIn("record_id", custom)
        self.assertIn("contact_key", custom)

    def test_has_type_and_folder(self):
        row = _fake_reply_row(0)
        self.assertEqual(row["type"], "reply")
        self.assertEqual(row["folder"], "inbox")

    def test_has_timestamp(self):
        row = _fake_reply_row(42)
        self.assertIn("2026", row["created_at"])

    def test_classifies_as_reply(self):
        from src.providers.bison import classify_reply_row
        row = _fake_reply_row(0)
        self.assertEqual(classify_reply_row(row), "reply")


class TestFakePage(unittest.TestCase):
    """A page is a list of rows of the right size."""

    def test_default_size(self):
        page = _fake_page()
        self.assertEqual(len(page), PAGE_SIZE)

    def test_custom_size(self):
        page = _fake_page(5, start=100)
        self.assertEqual(len(page), 5)
        # Start offset is reflected in the row ids
        self.assertEqual(page[0]["id"], 10000 + 100)


class TestLocalMeasurements(unittest.TestCase):
    """The local measurements produce valid numbers."""

    def test_page_processing_returns_valid(self):
        result = measure_local_page_processing(n_pages=10, page_size=PAGE_SIZE)
        self.assertEqual(result["n_pages"], 10)
        self.assertEqual(result["total_rows"], 10 * PAGE_SIZE)
        self.assertGreater(result["seconds"], 0)
        self.assertGreater(result["seconds_per_page"], 0)
        self.assertGreater(result["seconds_per_row"], 0)
        # All rows should be processed as events
        self.assertEqual(result["events_processed"], 10 * PAGE_SIZE)

    def test_transaction_at_300(self):
        result = measure_store_transaction_at_size(300)
        self.assertEqual(result["estate_size"], 300)
        self.assertGreater(result["transaction_seconds"], 0)
        # At 300 records, a transaction should be well under 1 second
        self.assertLess(result["transaction_seconds"], 5.0)

    def test_refuse_history_loss_at_300(self):
        result = measure_refuse_history_loss_at_size(300)
        self.assertEqual(result["estate_size"], 300)
        self.assertGreater(result["refuse_history_loss_seconds"], 0)


class TestModelInvariant(unittest.TestCase):
    """The key claim: provider requests dominate local compute at scale."""

    def test_provider_dominates_at_352_scale(self):
        """At campaign 352 scale, provider requests >> local compute."""
        n_leads = 13500
        n_replies = 2000
        n_senders = 225
        latency = 0.25  # typical API

        # Provider cost
        provider_reqs = full_campaign_audit_requests(
            n_leads, n_replies, n_senders)
        provider_wall = provider_reqs * (latency + 0.008)

        # Local cost: process 2000 replies + 2000 transactions at 300 records
        pp = measure_local_page_processing(n_pages=200, page_size=PAGE_SIZE)
        local_reply = pp["seconds_per_row"] * n_replies

        txn = measure_store_transaction_at_size(300)
        local_txn = txn["transaction_seconds"] * n_replies

        local_total = local_reply + local_txn

        # Provider should be significantly slower.  The exact ratio depends
        # on machine speed and estate size, but at campaign 352 scale the
        # provider's sequential HTTP requests always dominate local compute.
        # 5x is a conservative threshold that holds across machines.
        ratio = provider_wall / max(local_total, 0.001)
        self.assertGreater(ratio, 5,
                           f"provider wall {provider_wall:.0f}s should be "
                           f">> local wall {local_total:.1f}s, "
                           f"ratio was {ratio:.0f}x")


if __name__ == "__main__":
    unittest.main()
