#!/usr/bin/env python3
"""Fetch and store the Productive case-study pages.

TASK-365. The operator's rule: copy may name a case study and quote only
what the page itself states. The lint traces every case-study claim to the
stored page text and refuses anything not on it.

This script retrieves each study's individual page, extracts the readable
text, and stores it under ``docs/evidence/case-studies/`` as one JSON file
per study. The directory is tracked in git so that any clone has the
evidence the lint needs.

Usage::

    python scripts/fetch_case_studies.py

Read-only HTTP, no credentials, no cookies. Respects robots.txt.
"""
import datetime
import hashlib
import json
import os
import re
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from src.webfetch import (
    USER_AGENT, fetch, host_of, readable_text, robots_allows, settings,
)

try:
    import yaml
except ImportError:
    yaml = None

OUT_DIR = os.path.join(REPO_ROOT, "docs", "evidence", "case-studies")

#: The individual story URLs discovered on https://productive.io/customer-stories/
#: on 2026-09-26. Each key matches the evidence key in productive-offers.yaml.
STUDY_URLS = {
    "infinum": "https://productive.io/customer-stories/resource-planning-for-350-people-using-productive/",
    "makerstreet": "https://productive.io/customer-stories/productive-serves-makerstreet-as-a-single-source-of-truth/",
    "dotcontrol": "https://productive.io/customer-stories/dotcontrol-digital-agency-increased-their-forecasted-utilization-with-productive/",
    "hike_one": "https://productive.io/customer-stories/hike-one-has-control-over-their-data-and-growth-with-productive/",
    "saffron": "https://productive.io/customer-stories/saffron-clarity-business/",
    "bicg": "https://productive.io/customer-stories/bicg-360-degree-view-business/",
    "porsche_digital_croatia": "https://productive.io/customer-stories/how-productive-supports-the-rapid-growth-of-porsche-digital-croatia/",
    "tandem_x_visuals": "https://productive.io/customer-stories/productive-is-tandem-x-visuals-one-stop-shop-for-managing-work/",
    "flatline_agency": "https://productive.io/customer-stories/from-tool-overload-to-control-how-flatline-agency-simplified-operations/",
    "donq": "https://productive.io/customer-stories/donq-growing-in-complexity-with-full-operational-control/",
    "medico_digital": "https://productive.io/customer-stories/how-medico-digital-is-putting-ai-to-work-across-the-agency/",
}

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def _redact(text):
    """Remove email addresses. Nothing else needs redacting on public pages."""
    return _EMAIL_RE.sub("[email redacted]", text)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()


def _load_config():
    """Read the evidence block from productive-offers.yaml."""
    config_path = os.path.join(REPO_ROOT, "config", "clients",
                               "productive-offers.yaml")
    if yaml is None:
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {e.get("name", k): {**e, "_key": k}
            for k, e in (data.get("evidence") or {}).items()}


def fetch_one(key, url, conf):
    """Fetch one case-study page. Returns a dict with stored fields."""
    domain = host_of(url)
    timestamp = _now()

    if not robots_allows(url, domain, conf):
        return {
            "study_key": key,
            "url": url,
            "retrieved_at": timestamp,
            "status": "BLOCKED_BY_ROBOTS",
            "page_text": "",
            "content_hash": "",
            "chars": 0,
        }

    outcome, status, markup, size = fetch(url, domain, conf)
    if outcome != "HTTP_SUCCESS":
        return {
            "study_key": key,
            "url": url,
            "retrieved_at": timestamp,
            "status": outcome,
            "page_text": "",
            "content_hash": "",
            "chars": 0,
            "http_status": status,
        }

    raw_text = readable_text(markup, 50000)
    text = _redact(raw_text)
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    return {
        "study_key": key,
        "url": url,
        "retrieved_at": timestamp,
        "status": "OK",
        "page_text": text,
        "content_hash": content_hash,
        "chars": len(text),
        "http_status": status,
    }


def main():
    conf = settings()
    os.makedirs(OUT_DIR, exist_ok=True)

    results = []
    for key, url in sorted(STUDY_URLS.items()):
        print(f"Fetching {key}: {url}")
        result = fetch_one(key, url, conf)
        results.append(result)

        out_path = os.path.join(OUT_DIR, f"{key}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        status = result["status"]
        chars = result["chars"]
        h = result["content_hash"]
        print(f"  -> {status}  chars={chars}  hash={h}")
        time.sleep(1)

    print()
    print("=" * 72)
    print(f"{'Study':<28} {'Status':<18} {'Chars':>7}  {'Hash':<16}  URL")
    print("-" * 72)
    for r in results:
        print(f"{r['study_key']:<28} {r['status']:<18} {r['chars']:>7}  "
              f"{r['content_hash']:<16}  {r['url']}")

    ok = sum(1 for r in results if r["status"] == "OK")
    print(f"\n{ok} of {len(results)} fetched OK.")
    failed = [r for r in results if r["status"] != "OK"]
    if failed:
        print("UNRETRIEVED:")
        for r in failed:
            print(f"  {r['study_key']}: {r['status']}")


if __name__ == "__main__":
    main()
