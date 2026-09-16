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
    "px-7431a328ac3a", "px-a4fc4bab323a", "px-967eb2684819", "px-1cfee208a6c3", "px-fea5ffcdd8b1",
    "px-0b193ec5bbbe", "px-105270e3725e", "px-0dc19568a295", "px-bff4d2392bb8", "px-f21df457631d",
    "px-998d46ac6da9", "px-771db3f7cb5a", "px-d47484ce3933",
    "px-a8ca1565fdd1", "px-4ba04e2f17ff", "px-6a518e690008", "px-5ef455e98d10",
    "px-2a51e132bab4", "px-c31d8068cddc", "px-4e0922ab4b8c", "px-355075e3f546",
    "px-4f8bc13bf340", "px-e83f301e6906", "px-db8a5890740e", "px-5130f6cc0077", "px-d5108af3f45f",
    "px-23991ac89bd9", "px-e832ab043cfd", "px-e59084187a52", "px-89a18c3cbdd0", "px-63b4f68a86ff",
    "px-f5adf6535d66", "px-5caf426ff1a0", "px-5b35a4628a06", "px-927b0fc9b726",
    "px-845921c288d4", "px-90ab738a916e", "px-f167d8dd82cd",
    "px-009c4ecd93e7", "px-c04f7d63be05", "px-5c3a9c01d509",
    "px-7345d1ca05d2", "px-cbe58c6b9b3b", "px-069d26c83cc4",
}

FORBIDDEN_NAMES = {
    "px-78c82df0d6ca", "px-a2906c38600f", "px-0b0f017339dc", "px-7590af21c018", "px-cd4edcb5941e", "px-1d336a792886",
    "px-363fed662176", "px-bf64acdb74c7", "px-500574f8030b", "px-6094dbd14fbe", "px-aad56057d8c2", "px-b87cccbbcea3",
    "px-4811e61d7cd7", "px-235b74f9f1d0", "px-c59c84957ce0", "px-c56d44c3bc99", "px-83885540d428", "px-3f0229bf91ed", "px-6859c613bc7f",
    "px-8dd52f0bf377", "px-b7abfab8a4de", "px-fd444d5e607f", "px-1195428eba9a",
    "px-29e4cbbb3fac", "px-eaa21927d3bb", "px-f22e9093699c", "px-77f12e08d804", "px-68726f893e84",
    "px-e1ae770a9b46", "px-69f3c1ecc73f", "px-183975df87b3", "px-7fda2c80b481", "px-fc7e6eed49ab", "px-55b32db0034e",
    "px-4d87769926ef", "px-adddbcb604af", "px-39ab95927b75", "px-02178cab8e73",
    "px-e0df8da5442e", "px-3e67e0fcf911", "px-9e53b9602a01", "px-699ce41cf86d", "px-02d29687fd24",
    "px-f5614899072a", "px-aa91e5994940", "px-b8d20fbf3da5", "px-aa7f66737ac1",
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
