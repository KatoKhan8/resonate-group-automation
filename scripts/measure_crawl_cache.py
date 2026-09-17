#!/usr/bin/env python3
"""TASK-221: Measure crawl cache persistence across two passes.

Reports over two consecutive passes across overlapping synthetic cohorts:
    CRAWLS_PASS_1  CRAWLS_PASS_2  CACHE_HITS  HIT_RATE  CRAWLS_AVOIDED

Second pass over the SAME domains must show a hit rate near 1.0 and
near-zero crawls. A second pass over DISJOINT domains must show a hit
rate near 0.
"""
import datetime
import os
import sys
import tempfile
import shutil
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import research, store


def _make_record(id, domain):
    return {"id": id, "domain": domain, "research": [], "events": [],
            "log": []}


def _fake_research(domain, config):
    return {
        "outcome": "HTTP_SUCCESS",
        "pages": [
            {"source_url": f"https://{domain}/about",
             "field": "about",
             "fact": f"We are {domain}, a software company.",
             "provider": "local_http",
             "content_hash": "abc123",
             "http_status": 200,
             "chars": 500,
             "retrieved_at": store.now()},
        ],
        "retrieved_at": store.now(),
    }


def run_pass(domains, crawl_fn):
    """Run one pass over the given domains. Returns (crawls, hits)."""
    crawls = 0
    hits = 0
    for i, domain in enumerate(domains):
        rec = _make_record(f"rec-{domain}-{i}", domain)
        with patch("src.webfetch.research", side_effect=crawl_fn) as mock:
            result = research._from_the_site_itself(rec, {})
            if mock.call_count > 0:
                crawls += 1
            else:
                hits += 1
    return crawls, hits


def measure_same_domains():
    """Two passes over the SAME domains: hit rate should be near 1.0."""
    tmpdir = tempfile.mkdtemp(prefix="rga-measure-same-")
    try:
        store.use_directory(tmpdir)
        research.flush_crawl_cache()
        research.crawl_cache_clear()
        research._reset_persisted_cache()

        domains = [f"company-{i}.test" for i in range(10)]

        crawls_1, hits_1 = run_pass(domains, _fake_research)
        # Simulate new pass
        research.flush_crawl_cache()
        research.crawl_cache_clear()
        research._reset_persisted_cache()
        crawls_2, hits_2 = run_pass(domains, _fake_research)

        total_pass_2 = crawls_2 + hits_2
        hit_rate = hits_2 / total_pass_2 if total_pass_2 > 0 else 0.0
        avoided = crawls_1 - crawls_2

        print("=== SAME DOMAINS (overlap) ===")
        print(f"  CRAWLS_PASS_1:  {crawls_1}")
        print(f"  CRAWLS_PASS_2:  {crawls_2}")
        print(f"  CACHE_HITS:     {hits_2}")
        print(f"  HIT_RATE:       {hit_rate:.2f}")
        print(f"  CRAWLS_AVOIDED: {avoided}")
        print()
        return hit_rate
    finally:
        research.flush_crawl_cache()
        research.crawl_cache_clear()
        research._reset_persisted_cache()
        shutil.rmtree(tmpdir, ignore_errors=True)


def measure_disjoint_domains():
    """Two passes over DISJOINT domains: hit rate should be near 0."""
    tmpdir = tempfile.mkdtemp(prefix="rga-measure-disjoint-")
    try:
        store.use_directory(tmpdir)
        research.flush_crawl_cache()
        research.crawl_cache_clear()
        research._reset_persisted_cache()

        domains_1 = [f"alpha-{i}.test" for i in range(10)]
        domains_2 = [f"beta-{i}.test" for i in range(10)]

        crawls_1, hits_1 = run_pass(domains_1, _fake_research)
        # Simulate new pass
        research.flush_crawl_cache()
        research.crawl_cache_clear()
        research._reset_persisted_cache()
        crawls_2, hits_2 = run_pass(domains_2, _fake_research)

        total_pass_2 = crawls_2 + hits_2
        hit_rate = hits_2 / total_pass_2 if total_pass_2 > 0 else 0.0

        print("=== DISJOINT DOMAINS ===")
        print(f"  CRAWLS_PASS_1:  {crawls_1}")
        print(f"  CRAWLS_PASS_2:  {crawls_2}")
        print(f"  CACHE_HITS:     {hits_2}")
        print(f"  HIT_RATE:       {hit_rate:.2f}")
        print(f"  CRAWLS_AVOIDED: {crawls_1 - crawls_2}")
        print()
        return hit_rate
    finally:
        research.flush_crawl_cache()
        research.crawl_cache_clear()
        research._reset_persisted_cache()
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    print("TASK-221: Crawl cache persistence measurement")
    print("=" * 50)
    print()

    same_rate = measure_same_domains()
    disjoint_rate = measure_disjoint_domains()

    print("=" * 50)
    ok = True
    if same_rate < 0.9:
        print(f"FAIL: same-domain hit rate {same_rate:.2f} < 0.9")
        ok = False
    else:
        print(f"PASS: same-domain hit rate {same_rate:.2f} >= 0.9")

    if disjoint_rate > 0.1:
        print(f"FAIL: disjoint-domain hit rate {disjoint_rate:.2f} > 0.1")
        ok = False
    else:
        print(f"PASS: disjoint-domain hit rate {disjoint_rate:.2f} <= 0.1")

    if ok:
        print("\nAll measurements pass.")
    else:
        print("\nSome measurements FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
