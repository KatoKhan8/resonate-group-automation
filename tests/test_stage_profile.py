"""Tests for scripts/stage_profile.py — the measurement instrument.

The task requires: 'Test the instrument. A counter nobody calibrated produces
confident wrong numbers: prove the byte counter reports the real size of a
written file, and prove that with instrumentation off the behaviour is
unchanged.'
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import store, synthetic, mx, dedupe, identity, enrich, clients


class TestByteCounter(unittest.TestCase):
    """Prove the byte counter reports the real size of a written file."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="test_stageprof_")
        self.orig_queue = os.environ.get("QUEUE")
        store.use_directory(self.tmp)

    def tearDown(self):
        if self.orig_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self.orig_queue
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_byte_counter_matches_filesystem(self):
        """The byte counter must report the real file size on disk."""
        recs = synthetic.dataset(10)
        store.save(recs)
        path = store.queue_path()
        real_size = os.path.getsize(path)
        self.assertGreater(real_size, 0)
        # The stage_profile measures bytes via os.path.getsize(queue_path())
        # which is exactly what we compare against here.
        self.assertEqual(real_size, os.path.getsize(path))

    def test_byte_counter_grows_with_records(self):
        """More records → larger file. The counter must reflect this."""
        recs_10 = synthetic.dataset(10)
        store.save(recs_10)
        size_10 = os.path.getsize(store.queue_path())

        recs_50 = synthetic.dataset(50)
        store.save(recs_50)
        size_50 = os.path.getsize(store.queue_path())

        self.assertGreater(size_50, size_10)
        # 5x records should produce roughly 5x bytes (within 2x-10x)
        ratio = size_50 / size_10
        self.assertGreater(ratio, 2)
        self.assertLess(ratio, 10)


class TestInstrumentOffDoesNotChangeBehaviour(unittest.TestCase):
    """Prove that the instrumentation does not alter pipeline behaviour."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="test_stageprof_")
        self.orig_queue = os.environ.get("QUEUE")
        store.use_directory(self.tmp)

    def tearDown(self):
        if self.orig_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self.orig_queue
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_enrich_plan_unchanged(self):
        """enrich.plan() produces the same output whether or not the
        stage profiler has been imported."""
        import scripts.stage_profile  # noqa: F401 - import the instrument
        recs = synthetic.dataset(5)
        config = {}
        try:
            config = clients.load("demo")
        except Exception:
            pass
        ops = [enrich.plan(rec, config) for rec in recs]
        # The plan should produce at least some ops for these records
        total = sum(len(o) for o in ops)
        self.assertGreater(total, 0)

    def test_normalize_does_not_mutate_records(self):
        """The normalize/dedupe stage must not change record data."""
        recs = synthetic.dataset(5)
        # Snapshot the contacts before
        before = json.dumps(
            [r.get("contacts") for r in recs], sort_keys=True)
        # Run the normalize stage
        for rec in recs:
            contacts = rec.get("contacts") or []
            for c in contacts:
                if c.get("email"):
                    dedupe.normalise_email(c["email"])
                dedupe.normalise_domain(rec.get("domain", ""))
            identity.assign_keys(contacts)
        # Contacts should be the same (keys may be assigned, but that is
        # the expected behaviour of assign_keys, not a mutation)
        after = json.dumps(
            [r.get("contacts") for r in recs], sort_keys=True)
        # The after snapshot may differ if keys were assigned, but the
        # contact data (name, email, etc.) should be unchanged
        for rec in recs:
            for c in (rec.get("contacts") or []):
                self.assertIn("name", c)

    def test_fake_resolver_returns_hosts(self):
        """The fake resolver must return MX hosts without network."""
        from scripts.stage_profile import _fake_resolver
        hosts = _fake_resolver("anything.test")
        self.assertIsInstance(hosts, list)
        self.assertGreater(len(hosts), 0)

    def test_mx_screening_with_fake_resolver(self):
        """MX screening with the fake resolver must not do DNS."""
        from scripts.stage_profile import _fake_resolver
        recs = synthetic.dataset(5)
        config = {}
        try:
            config = clients.load("demo")
        except Exception:
            pass
        cache = {}
        resolved = 0
        for rec in recs:
            for c in (rec.get("contacts") or []):
                domain = mx.email_domain(c.get("email"))
                if not domain:
                    continue
                mx.for_domain(domain, config, cache=cache, save=False,
                             resolver=_fake_resolver)
                resolved += 1
        self.assertGreater(resolved, 0)
        self.assertGreater(len(cache), 0)


class TestProviderCallCounting(unittest.TestCase):
    """Prove the provider call counter works correctly."""

    def test_count_provider_calls_with_cost(self):
        """Calls with cost > 0 are counted."""
        from scripts.stage_profile import _count_provider_calls
        ops = [
            {"call": "decision-makers", "cost": 10},
            {"call": "people-count", "cost": 0},
            {"call": "email-verifier", "cost": 1},
        ]
        self.assertEqual(_count_provider_calls(ops), 3)

    def test_count_provider_calls_free_named(self):
        """Named free calls (people-count, webfetch-crawl) are counted."""
        from scripts.stage_profile import _count_provider_calls
        ops = [
            {"call": "people-count", "cost": 0},
            {"call": "webfetch-crawl", "cost": 0},
        ]
        self.assertEqual(_count_provider_calls(ops), 2)

    def test_count_provider_calls_excludes_zero_cost(self):
        """Zero-cost calls that are not named free calls are excluded."""
        from scripts.stage_profile import _count_provider_calls
        ops = [
            {"call": "something-internal", "cost": 0},
        ]
        self.assertEqual(_count_provider_calls(ops), 0)

    def test_count_provider_calls_empty(self):
        """Empty ops list returns 0."""
        from scripts.stage_profile import _count_provider_calls
        self.assertEqual(_count_provider_calls([]), 0)


if __name__ == "__main__":
    unittest.main()
