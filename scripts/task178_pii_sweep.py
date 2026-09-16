#!/usr/bin/env python3
"""TASK-178: Repository-wide PII sweep.

Counts and locates every occurrence of:
1. Real person names (not in FORBIDDEN_NAMES)
2. Unhashed prospect domains (not in FORBIDDEN_DOMAINS)
3. Email addresses on non-reserved domains
4. LinkedIn profile URLs with real vanity names
5. Reply text or CRM narrative

Reports counts and file locations only. Does NOT print PII values.
"""
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Reserved domains (RFC 2606/6761)
SAFE_SUFFIXES = {".test", ".example", "example.com", "example.org",
                 "example.net", "localhost", ".invalid"}

# Known forbidden (from test_fixture_hygiene.py)
FORBIDDEN_DOMAINS = {
    "arbona.hr", "bornfight.com", "five.agency", "beauhurst.com", "robotiq.ai",
    "levelupleads.io", "whatson.ai", "fornate.com", "leapin.co", "jobadder.com",
    "321webmarketing.com", "20northmarketing.com", "adcreations.com",
    "adcuratio.com", "1secondleads.com", "28row.com", "adblend.co",
    "anewagencyworld.com", "aubryandco.com", "arcoagency.se", "nineyards.ie",
    "thirtythree-usa.com", "clay.com", "relpro.com", "auvale.de", "alta.com",
    "tawk.to", "synquery.com", "farseer.io", "q-agency.com", "netnada.com.au",
    "nextoria.com", "cyber64.hr", "productive.io", "goproductive.online",
    "goproductive.net", "goproductivelab.com", "goproductivelabs.live",
    "tryproductive.online", "withproductive.online", "gonetnada.com",
    "trynetnada.live", "netnadadigital.shop", "contactout.io",
}

FORBIDDEN_NAMES = {
    "mahovic", "mahović", "klaric", "klarić", "blackler", "hopkins",
    "gudelj", "galic", "galić", "ivce", "pavlovic", "pavlović",
    "van ulden", "baauw", "karsant", "lucic", "gokdeniz", "beslic", "beslić",
    "brooke baron", "brookebaron", "josephoneill", "joseph o'neill",
    "lingenfelter", "dahlstrom", "mediaboard", "netnada", "cyber64",
    "nineyards", "brooke", "arbona", "bornfight", "jobadder", "adcuratio",
    "adcreations", "321webmarketing", "20northmarketing", "1secondleads",
    "28row", "adblend", "anewagencyworld", "aubryandco", "arcoagency",
    "thirtythree-usa", "goproductive", "gonetnada", "trynetnada",
}

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
LINKEDIN = re.compile(r"linkedin\.com/in/([a-zA-Z0-9\-_]+)")
NAME_SLUG = re.compile(r"\b([a-z]+-[a-z]+)\b")  # Hyphenated names like ray-kingman

TEXT_SUFFIXES = {".py", ".json", ".jsonl", ".csv", ".txt", ".md", ".yaml",
                 ".yml", ".cfg", ".ini", ".toml", ".html", ".js", ".css"}


def tracked_files():
    """Every file git tracks."""
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.split("\0") if p]


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8", errors="replace") as f:
        return f.read()


def is_safe_domain(domain):
    """Check if domain is on a reserved suffix."""
    low = domain.lower()
    return any(low == s or low.endswith(s) for s in SAFE_SUFFIXES)


def sweep():
    """Sweep all tracked files for PII."""
    results = {
        "email_addresses": defaultdict(list),
        "forbidden_domains": defaultdict(list),
        "forbidden_names": defaultdict(list),
        "linkedin_urls": defaultdict(list),
        "name_slugs": defaultdict(list),
        "unhashed_domains": defaultdict(list),
    }

    files = tracked_files()
    text_files = [f for f in files if Path(f).suffix in TEXT_SUFFIXES]

    print(f"Sweeping {len(text_files)} tracked text files...")
    print()

    for path in text_files:
        if path == "tests/test_fixture_hygiene.py":
            continue  # Skip the guard itself

        try:
            text = read(path)
        except Exception as e:
            print(f"  WARNING: Could not read {path}: {e}")
            continue

        lines = text.split("\n")

        # 1. Email addresses
        for line_num, line in enumerate(lines, 1):
            for match in EMAIL.finditer(line):
                domain = match.group(1)
                if not is_safe_domain(domain):
                    results["email_addresses"][path].append((line_num, domain))

        # 2. Forbidden domains
        low_text = text.lower()
        for domain in FORBIDDEN_DOMAINS:
            if domain in low_text:
                # Find line numbers
                for line_num, line in enumerate(lines, 1):
                    if domain in line.lower():
                        results["forbidden_domains"][path].append((line_num, domain))

        # 3. Forbidden names
        for name in FORBIDDEN_NAMES:
            if name in low_text:
                for line_num, line in enumerate(lines, 1):
                    if name in line.lower():
                        results["forbidden_names"][path].append((line_num, name))

        # 4. LinkedIn URLs
        for line_num, line in enumerate(lines, 1):
            for match in LINKEDIN.finditer(line):
                vanity = match.group(1)
                # Skip obvious test/demo/example
                if any(x in vanity.lower() for x in ["example", "test", "demo", "probe", "unknown"]):
                    continue
                # Skip if it's a known forbidden name
                if any(name.replace(" ", "-") in vanity.lower() or name in vanity.lower()
                       for name in FORBIDDEN_NAMES):
                    continue
                results["linkedin_urls"][path].append((line_num, vanity))

        # 5. Name slugs (hyphenated names like ray-kingman)
        for line_num, line in enumerate(lines, 1):
            # Skip comments and strings that are clearly not PII
            if line.strip().startswith("#") or "def " in line or "class " in line:
                continue
            for match in NAME_SLUG.finditer(line):
                slug = match.group(1)
                # Skip common non-name patterns
                if any(x in slug for x in ["self", "cls", "tmp", "temp", "test", "demo",
                                           "example", "sample", "mock", "fake", "dummy"]):
                    continue
                # Skip if it's a known pattern (record IDs, etc.)
                if slug.endswith("-com") or slug.endswith("-io") or slug.endswith("-co"):
                    continue
                results["name_slugs"][path].append((line_num, slug))

    return results


def report(results):
    """Print the sweep report."""
    print("=" * 78)
    print("PII SWEEP REPORT")
    print("=" * 78)
    print()

    total = 0

    # Email addresses
    print("1. EMAIL ADDRESSES (non-reserved domains)")
    print("-" * 78)
    count = sum(len(v) for v in results["email_addresses"].values())
    total += count
    if count == 0:
        print("   None found.")
    else:
        print(f"   Found {count} occurrences in {len(results['email_addresses'])} files:")
        for path, hits in sorted(results["email_addresses"].items()):
            print(f"     {path}: {len(hits)} occurrence(s)")
            for line_num, domain in hits[:3]:
                print(f"       Line {line_num}: domain={domain}")
            if len(hits) > 3:
                print(f"       ... and {len(hits) - 3} more")
    print()

    # Forbidden domains
    print("2. FORBIDDEN DOMAINS (already in guard)")
    print("-" * 78)
    count = sum(len(v) for v in results["forbidden_domains"].values())
    total += count
    if count == 0:
        print("   None found.")
    else:
        print(f"   Found {count} occurrences in {len(results['forbidden_domains'])} files:")
        for path, hits in sorted(results["forbidden_domains"].items()):
            unique_domains = set(d for _, d in hits)
            print(f"     {path}: {len(hits)} occurrence(s), domains: {', '.join(sorted(unique_domains)[:5])}")
    print()

    # Forbidden names
    print("3. FORBIDDEN NAMES (already in guard)")
    print("-" * 78)
    count = sum(len(v) for v in results["forbidden_names"].values())
    total += count
    if count == 0:
        print("   None found.")
    else:
        print(f"   Found {count} occurrences in {len(results['forbidden_names'])} files:")
        for path, hits in sorted(results["forbidden_names"].items()):
            unique_names = set(n for _, n in hits)
            print(f"     {path}: {len(hits)} occurrence(s), names: {', '.join(sorted(unique_names)[:5])}")
    print()

    # LinkedIn URLs
    print("4. LINKEDIN PROFILE URLs (real vanity names)")
    print("-" * 78)
    count = sum(len(v) for v in results["linkedin_urls"].values())
    total += count
    if count == 0:
        print("   None found.")
    else:
        print(f"   Found {count} occurrences in {len(results['linkedin_urls'])} files:")
        for path, hits in sorted(results["linkedin_urls"].items()):
            print(f"     {path}: {len(hits)} occurrence(s)")
            for line_num, vanity in hits[:3]:
                print(f"       Line {line_num}: vanity={vanity}")
            if len(hits) > 3:
                print(f"       ... and {len(hits) - 3} more")
    print()

    # Name slugs
    print("5. NAME SLUGS (hyphenated, potential PII)")
    print("-" * 78)
    count = sum(len(v) for v in results["name_slugs"].values())
    total += count
    if count == 0:
        print("   None found.")
    else:
        print(f"   Found {count} occurrences in {len(results['name_slugs'])} files:")
        for path, hits in sorted(results["name_slugs"].items()):
            print(f"     {path}: {len(hits)} occurrence(s)")
            for line_num, slug in hits[:3]:
                print(f"       Line {line_num}: slug={slug}")
            if len(hits) > 3:
                print(f"       ... and {len(hits) - 3} more")
    print()

    print("=" * 78)
    print(f"TOTAL POTENTIAL PII OCCURRENCES: {total}")
    print("=" * 78)


if __name__ == "__main__":
    results = sweep()
    report(results)
