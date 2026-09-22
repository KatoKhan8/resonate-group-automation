"""The 20k load test's generator and projection, before the benchmark runs.

TASK-255. The generator must produce records at the measured production
distribution (mean 19,819 bytes, max > 150 KB), the projection must calculate
the jsonl arm's cost without performing it, and each arm must work at small
sizes.

THESE TESTS DO NOT RUN THE BENCHMARK. They verify the pieces the benchmark
is built from. The benchmark itself is a script, not a test.
"""
import json
import os
import statistics
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from scripts.load_test_20k import (
    generate_estate,
    _project_jsonl_cost,
    _target_size,
    _synthetic_record,
    PROD_MEAN_BYTES,
    CHECKPOINT_EVERY,
    measure_jsonl,
    measure_journal,
    measure_sqlite,
)
from src import store, sqlitestore, queuejournal, run
import random


class TheGeneratorMatchesProduction(unittest.TestCase):
    """The generator's output has the measured mean within 5% and reproduces
    the tail - at least one record over 150 KB."""

    def test_mean_within_5_percent_at_1000(self):
        records, stats = generate_estate(1_000)
        self.assertTrue(
            stats["mean_within_5pct"],
            f"mean {stats['mean_bytes']:.0f} is not within 5% of "
            f"{PROD_MEAN_BYTES}")

    def test_mean_within_5_percent_at_5000(self):
        records, stats = generate_estate(5_000)
        self.assertTrue(stats["mean_within_5pct"])

    def test_at_least_one_record_over_150kb(self):
        records, stats = generate_estate(1_000)
        self.assertGreaterEqual(
            stats["tail_over_150k"], 1,
            "no record over 150 KB - the tail is not reproduced")

    def test_no_record_is_empty(self):
        records, _ = generate_estate(100)
        for r in records:
            size = len(json.dumps(r, ensure_ascii=False))
            self.assertGreater(size, 1_000,
                               f"record {r['id']} is only {size} bytes")

    def test_record_has_realistic_structure(self):
        records, _ = generate_estate(10)
        for r in records:
            self.assertIn("id", r)
            self.assertIn("contacts", r)
            self.assertIn("excluded", r)
            self.assertIn("events", r)
            self.assertIn("cadence", r)
            self.assertIn("log", r)
            self.assertIn("company_facts", r)
            self.assertIsInstance(r["contacts"], list)
            self.assertIsInstance(r["log"], list)

    def test_no_production_data_in_synthetic_records(self):
        """The generator synthesises content; it does not copy from work/."""
        records, _ = generate_estate(50)
        for r in records:
            self.assertTrue(r["domain"].endswith(".test"),
                            f"record {r['id']} has non-synthetic domain")
            for c in r.get("contacts", []):
                self.assertIn("@load", c.get("email", ""),
                              "contact email is not synthetic")


class TheProjectionIsCorrect(unittest.TestCase):
    """The jsonl arm's projection matches the math."""

    def test_projection_at_20k(self):
        proj = _project_jsonl_cost(20_000, PROD_MEAN_BYTES)
        expected_base = 20_000 * PROD_MEAN_BYTES
        expected_checkpoints = 20_000 // CHECKPOINT_EVERY
        expected_total = expected_checkpoints * expected_base

        self.assertEqual(proj["base_file_bytes"], expected_base)
        self.assertEqual(proj["checkpoints"], expected_checkpoints)
        self.assertEqual(proj["total_bytes_written"], expected_total)
        self.assertAlmostEqual(proj["total_tb_written"],
                               expected_total / 1e12, places=2)

    def test_projection_grows_quadratically(self):
        p1 = _project_jsonl_cost(1_000, PROD_MEAN_BYTES)
        p2 = _project_jsonl_cost(20_000, PROD_MEAN_BYTES)
        ratio = p2["total_bytes_written"] / p1["total_bytes_written"]
        rec_ratio = 20_000 / 1_000
        self.assertGreater(ratio, rec_ratio ** 1.8,
                           "projection should grow roughly quadratically")


class EachArmWorksAtSmallSize(unittest.TestCase):
    """Each arm produces results at a size that fits in memory and disk."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loadtest-")
        self.records, _ = generate_estate(50)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("QUEUE_JOURNAL", None)

    def test_jsonl_arm_returns_results(self):
        r = measure_jsonl(50, self.records, 1, self.tmp)
        self.assertFalse(r.get("PROJECTED"))
        self.assertFalse(r.get("REFUSED"))
        self.assertIn("total_write_s", r)
        self.assertIn("read_s", r)
        self.assertIn("bytes_written", r)
        self.assertGreater(r["bytes_written"], 0)
        self.assertGreater(r["read_s"], 0)

    def test_journal_arm_returns_results(self):
        r = measure_journal(50, self.records, 1, self.tmp)
        self.assertFalse(r.get("REFUSED"))
        self.assertIn("total_write_s", r)
        self.assertIn("read_s", r)
        self.assertIn("bytes_written", r)
        self.assertGreater(r["bytes_written"], 0)

    def test_sqlite_arm_returns_results(self):
        r = measure_sqlite(50, self.records, 1, self.tmp)
        self.assertFalse(r.get("REFUSED"))
        self.assertIn("total_write_s", r)
        self.assertIn("read_s", r)
        self.assertIn("bytes_written", r)

    def test_journal_writes_less_than_jsonl(self):
        j = measure_jsonl(50, self.records, 1, self.tmp)
        d = measure_journal(50, self.records, 1, self.tmp)
        self.assertLess(
            d["bytes_written"], j["bytes_written"],
            "journal arm should write less than whole-file arm")

    def test_read_cost_is_reported_separately(self):
        """The journal's table counted only bytes written; the read is
        'the half that is easy to miss'."""
        r = measure_jsonl(50, self.records, 1, self.tmp)
        self.assertIn("read_s", r)
        self.assertIsInstance(r["read_s"], float)


class TheDiskCheckRefusesWhenInsufficient(unittest.TestCase):
    """The jsonl arm at 20k reports its projection without performing it."""

    def test_jsonl_20k_is_projected_not_performed(self):
        records, _ = generate_estate(20_000)
        tmp = tempfile.mkdtemp(prefix="loadtest-")
        try:
            r = measure_jsonl(20_000, records, 1, tmp)
            self.assertTrue(r.get("PROJECTED"),
                            "jsonl at 20k should be projected, not performed")
            self.assertIn("projection", r)
            self.assertGreater(r["projection"]["total_tb_written"], 1.0)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


class TheBenchmarkDoesNotTouchProduction(unittest.TestCase):
    """The load test uses temp directories only."""

    def test_generator_does_not_reference_work_directory(self):
        import inspect
        from scripts import load_test_20k
        source = inspect.getsource(load_test_20k)
        self.assertNotIn("work/queue", source)
        self.assertNotIn("work\\\\queue", source)

    def test_store_restored_after_measurement(self):
        """After a measurement, the QUEUE env is restored."""
        was = os.environ.get("QUEUE")
        records, _ = generate_estate(20)
        tmp = tempfile.mkdtemp(prefix="loadtest-")
        try:
            measure_jsonl(20, records, 1, tmp)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(os.environ.get("QUEUE"), was)


if __name__ == "__main__":
    unittest.main()
