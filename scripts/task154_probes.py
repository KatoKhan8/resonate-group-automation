#!/usr/bin/env python3
"""TASK-154: Reachability probes for 5 selected domains.

Uses webfetch.research() - the free leg - to check whether these sites
can be reached and what they return. No Apify, no model calls.

Five domains chosen:
1. australo.org      - ICP dimension need, state=queued
2. hotmail.fi        - ICP dimension need, state=queued (looks like email domain)
3. tateshvili.com    - ICP dimension need, state=queued
4. 22visioncg.com    - stale team evidence, state=dropped
5. 30lines.com       - stale team evidence, state=dropped
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import webfetch

DOMAINS = [
    ("australo.org", "ICP dimension need, queued"),
    ("hotmail.fi", "ICP dimension need, queued - likely email domain"),
    ("tateshvili.com", "ICP dimension need, queued"),
    ("22visioncg.com", "Stale team evidence, dropped"),
    ("30lines.com", "Stale team evidence, dropped"),
]


def probe(domain, note):
    print(f"\n{'='*60}")
    print(f"Domain: {domain}")
    print(f"Note: {note}")
    print(f"{'='*60}")
    try:
        result = webfetch.research(domain)
    except Exception as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")
        return {"domain": domain, "error": str(e)}

    outcome = result.get("outcome")
    pages = result.get("pages", [])
    stats = result.get("stats", {})
    fallback = result.get("fallback_worthy", False)

    print(f"  Outcome: {outcome}")
    print(f"  Pages kept: {len(pages)}")
    print(f"  Fallback-worthy: {fallback}")
    print(f"  Requests: {stats.get('requests', 0)}")
    print(f"  Bytes: {stats.get('bytes', 0)}")
    print(f"  Seconds: {stats.get('seconds', 0)}")
    print(f"  Outcomes: {stats.get('outcomes', [])}")

    for i, page in enumerate(pages):
        print(f"  Page {i+1}:")
        print(f"    URL: {page.get('source_url')}")
        print(f"    Field: {page.get('field')}")
        print(f"    Chars: {page.get('chars')}")
        print(f"    HTTP: {page.get('http_status')}")
        # Show first 200 chars of fact
        fact = (page.get("fact") or "")[:200]
        print(f"    Fact preview: {fact}...")

    return {
        "domain": domain,
        "note": note,
        "outcome": outcome,
        "pages_kept": len(pages),
        "fallback_worthy": fallback,
        "requests": stats.get("requests", 0),
        "bytes": stats.get("bytes", 0),
        "seconds": stats.get("seconds", 0),
        "outcomes": stats.get("outcomes", []),
        "page_fields": [p.get("field") for p in pages],
    }


def main():
    results = []
    for domain, note in DOMAINS:
        r = probe(domain, note)
        results.append(r)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"  {r['domain']:30s} outcome={r.get('outcome','ERROR'):25s} "
              f"pages={r.get('pages_kept',0)} "
              f"fallback={r.get('fallback_worthy',False)} "
              f"seconds={r.get('seconds',0)}")

    # Count free-leg likely sufficiency
    success = sum(1 for r in results if r.get("outcome") == "HTTP_SUCCESS" and r.get("pages_kept", 0) > 0)
    fallback = sum(1 for r in results if r.get("fallback_worthy"))
    print(f"\nFree leg succeeded: {success}/5")
    print(f"Would need paid fallback: {fallback}/5")

    # Write results
    output_path = os.path.join(ROOT, "scripts", "task154_probe_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {output_path}")


if __name__ == "__main__":
    main()
