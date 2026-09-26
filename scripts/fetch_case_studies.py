#!/usr/bin/env python3
"""TASK-365: fetch and store the public case-study pages from productive.io.

Read-only HTTP, no credentials, no cookies.  Each study's individual page
is fetched (not the index), the visible text is extracted, and the result
is stored under work/evidence/case-studies/ as one JSON file per study.

Each stored file carries:
  - study_key       the key from productive-offers.yaml
  - name            the display name
  - url             the actual page URL fetched
  - retrieved_at    ISO-8601 timestamp
  - content_hash    SHA-256 of the stored text, so a re-fetch can detect change
  - char_count      len(text)
  - text            the extracted visible text

The index page (https://productive.io/customer-stories/) is fetched first
to discover the individual story URLs.  If a study has no distinct page,
the file records UNRETRIEVED with a reason.

Nothing under work/ is committed.  This script and the tests are.
"""
import hashlib
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, "work", "evidence", "case-studies")

INDEX_URL = "https://productive.io/customer-stories/"

STUDY_URLS = {
    "infinum":
        "https://productive.io/customer-stories/"
        "resource-planning-for-350-people-using-productive/",
    "makerstreet":
        "https://productive.io/customer-stories/"
        "productive-serves-makerstreet-as-a-single-source-of-truth/",
    "dotcontrol":
        "https://productive.io/customer-stories/"
        "dotcontrol-digital-agency-increased-their-forecasted-utilization"
        "-with-productive/",
    "hike_one":
        "https://productive.io/customer-stories/"
        "hike-one-has-control-over-their-data-and-growth-with-productive/",
    "saffron":
        "https://productive.io/customer-stories/saffron-clarity-business/",
    "bicg":
        "https://productive.io/customer-stories/bicg-360-degree-view-business/",
    "porsche_digital_croatia":
        "https://productive.io/customer-stories/"
        "how-productive-supports-the-rapid-growth-of-porsche-digital-croatia/",
    "tandem_x_visuals":
        "https://productive.io/customer-stories/"
        "productive-is-tandem-x-visuals-one-stop-shop-for-managing-work/",
    "flatline_agency":
        "https://productive.io/customer-stories/"
        "from-tool-overload-to-control-how-flatline-agency-simplified"
        "-operations/",
    "donq":
        "https://productive.io/customer-stories/"
        "donq-growing-in-complexity-with-full-operational-control/",
    "medico_digital":
        "https://productive.io/customer-stories/"
        "how-medico-digital-is-putting-ai-to-work-across-the-agency/",
}

STUDY_NAMES = {
    "infinum": "Infinum",
    "makerstreet": "Makerstreet",
    "dotcontrol": "DotControl",
    "hike_one": "Hike One",
    "saffron": "Saffron",
    "bicg": "BICG",
    "porsche_digital_croatia": "Porsche Digital Croatia",
    "tandem_x_visuals": "Tandem X Visuals",
    "flatline_agency": "Flatline Agency",
    "donq": "DonQ",
    "medico_digital": "Medico Digital",
}

_USER_AGENT = "ResonateOS-CaseStudyFetch/1.0 (research; read-only)"


def _fetch_html(url):
    """GET a URL, return the decoded body as a string.  Raise on non-2xx."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


_STRIP_TAGS = re.compile(r"<(?:script|style|noscript)[^>]*>.*?</\1>",
                         re.S | re.I)
_STRIP_SELF_CLOSE = re.compile(
    r"<(?:script|style|noscript)[^>]*/>", re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")
_BLANK = re.compile(r"\n{3,}")


def extract_text(html):
    """Strip tags and scripts, return visible text."""
    text = _STRIP_TAGS.sub("", html)
    text = _STRIP_SELF_CLOSE.sub("", text)
    text = _TAG.sub(" ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&#39;", "'").replace("&quot;", '"')
    text = _WS.sub(" ", text)
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    text = _BLANK.sub("\n\n", text)
    return text.strip()


def fetch_one(key):
    """Fetch one study page.  Return the stored-record dict."""
    url = STUDY_URLS[key]
    now = datetime.now(timezone.utc).isoformat()
    print("  fetching %s -> %s" % (key, url))
    try:
        html = _fetch_html(url)
    except (urllib.error.URLError, OSError) as exc:
        print("    FAILED: %s" % exc)
        return {
            "study_key": key,
            "name": STUDY_NAMES[key],
            "url": url,
            "retrieved_at": now,
            "status": "UNRETRIEVED",
            "reason": str(exc),
            "content_hash": None,
            "char_count": 0,
            "text": "",
        }
    text = extract_text(html)
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print("    ok: %d chars, hash %s" % (len(text), h[:16]))
    return {
        "study_key": key,
        "name": STUDY_NAMES[key],
        "url": url,
        "retrieved_at": now,
        "status": "OK",
        "content_hash": h,
        "char_count": len(text),
        "text": text,
    }


def load_study(key):
    """Load a stored study from disk.  Return None if absent."""
    path = os.path.join(OUT_DIR, "%s.json" % key)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_studies():
    """Return {key: record} for every stored study."""
    out = {}
    if not os.path.isdir(OUT_DIR):
        return out
    for fn in sorted(os.listdir(OUT_DIR)):
        if fn.endswith(".json"):
            key = fn[:-5]
            rec = load_study(key)
            if rec:
                out[key] = rec
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Fetching %d case studies from productive.io" % len(STUDY_URLS))
    print("Output directory: %s" % OUT_DIR)
    print()

    results = []
    for key in sorted(STUDY_URLS):
        rec = fetch_one(key)
        results.append(rec)
        path = os.path.join(OUT_DIR, "%s.json" % key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 78)
    print("%-25s %-10s %8s  %s" % ("study", "status", "chars", "hash"))
    print("-" * 78)
    for rec in results:
        h = (rec["content_hash"] or "")[:16]
        print("%-25s %-10s %8d  %s"
              % (rec["study_key"], rec["status"],
                 rec["char_count"], h))
    ok = sum(1 for r in results if r["status"] == "OK")
    print("-" * 78)
    print("%d of %d fetched successfully" % (ok, len(results)))
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
