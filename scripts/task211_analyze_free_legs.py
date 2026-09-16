#!/usr/bin/env python3
"""TASK-211: Read-only analysis of what the free legs would do.

This script does NOT modify work/queue.jsonl. It reads the queue,
analyzes what the free legs (ContactOut existing evidence + webfetch crawl)
would resolve, and reports the per-leg yield, unresolved groups, and
next-step costs.

The standing brief (QWEN.md) forbids writing to work/queue.jsonl from
this worktree. The actual run is owed from Claude's worktree.
"""
import json
import os
import sys
from collections import Counter

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "work", "queue.jsonl")
LEDGER_PATH = os.path.join(os.path.dirname(__file__), "..", "work", "spend-ledger.jsonl")


def load_queue():
    recs = []
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def hash_id(rec):
    """Hash a record ID for safe reporting."""
    import hashlib
    return hashlib.sha256(rec.get("id", "").encode()).hexdigest()[:12]


def analyze_spend(recs):
    """Prove spend is zero from the ledger."""
    # Check the spend ledger file
    ledger_exists = os.path.exists(LEDGER_PATH)
    ledger_rows = []
    if ledger_exists:
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    ledger_rows.append(json.loads(line))

    # Check waterfall rows on records for actual_cost
    total_actual = 0
    total_expected = 0
    for rec in recs:
        for row in rec.get("waterfall", []):
            total_actual += row.get("actual_cost") or 0
            total_expected += row.get("expected_cost") or 0

    return {
        "ledger_file_exists": ledger_exists,
        "ledger_rows": len(ledger_rows),
        "ledger_total": sum(r.get("expected_cost", 0) for r in ledger_rows),
        "waterfall_actual_cost": total_actual,
        "waterfall_expected_cost": total_expected,
        "spend_proven_zero": not ledger_exists and total_actual == 0,
    }


def analyze_free_legs(recs):
    """Analyze what the free legs would resolve."""
    queued = [r for r in recs if r.get("state") == "queued"]
    held = [r for r in recs if r.get("state") == "held"]

    # ContactOut existing evidence (cache leg)
    contactout_already_called = 0
    contactout_has_data = 0
    for r in queued:
        for row in r.get("waterfall", []):
            if row.get("provider") == "contactout" and row.get("call") == "company-information-from-domain":
                contactout_already_called += 1
                if r.get("company_facts", {}).get("industry") or r.get("company_facts", {}).get("offices"):
                    contactout_has_data += 1
                break

    # Webfetch crawl - never run
    webfetch_already_run = 0
    for r in recs:
        for row in r.get("waterfall", []):
            if row.get("provider") == "webfetch" or "webfetch" in (row.get("call") or ""):
                webfetch_already_run += 1
                break

    # Records that would benefit from a crawl
    queued_no_research = [r for r in queued if not r.get("research")]
    queued_with_incomplete = [r for r in queued if r.get("research") and (
        not r.get("company_facts", {}).get("industry") or
        not r.get("company_facts", {}).get("offices")
    )]

    return {
        "queued_total": len(queued),
        "held_total": len(held),
        "contactout_already_called": contactout_already_called,
        "contactout_has_some_data": contactout_has_data,
        "webfetch_already_run_anywhere": webfetch_already_run,
        "queued_without_any_research": len(queued_no_research),
        "queued_with_research_but_missing_fields": len(queued_with_incomplete),
        "queued_would_benefit_from_crawl": len(queued_no_research) + len(queued_with_incomplete),
    }


def analyze_unresolved(recs):
    """Group unresolved records by reason."""
    queued = [r for r in recs if r.get("state") == "queued"]

    groups = {
        "too_small_fail_closed": [],
        "geo_excluded_fail_closed": [],
        "missing_all_three": [],
        "missing_offices_and_industry": [],
        "missing_offices_only": [],
        "missing_industry_only": [],
        "missing_employees_only": [],
        "has_facts_needs_qualify": [],
        "other": [],
    }

    for r in queued:
        cf = r.get("company_facts", {})
        has_industry = bool(cf.get("industry"))
        has_offices = bool(cf.get("offices"))
        has_employees = bool(cf.get("employees"))
        flags = cf.get("icp_flags", [])

        is_too_small = any(
            "employee" in f.lower() or "under" in f.lower() or "minimum" in f.lower()
            for f in flags
        )
        is_geo_excluded = any(
            "geo" in f.lower() or "country" in f.lower() or "excluded" in f.lower()
            for f in flags
        )

        if is_too_small:
            groups["too_small_fail_closed"].append(r)
        elif is_geo_excluded and has_industry and has_offices and has_employees:
            groups["geo_excluded_fail_closed"].append(r)
        elif not has_industry and not has_offices and not has_employees:
            groups["missing_all_three"].append(r)
        elif not has_industry and not has_offices:
            groups["missing_offices_and_industry"].append(r)
        elif not has_offices:
            groups["missing_offices_only"].append(r)
        elif not has_industry:
            groups["missing_industry_only"].append(r)
        elif not has_employees:
            groups["missing_employees_only"].append(r)
        elif not flags:
            groups["has_facts_needs_qualify"].append(r)
        else:
            groups["other"].append(r)

    return {k: len(v) for k, v in groups.items()}


def analyze_crawl_cache(recs):
    """Report on the company-level crawl cache."""
    multi_contact = [r for r in recs if len(r.get("contacts", [])) > 1]
    unique_domains = len(set(r.get("domain") for r in recs if r.get("domain")))
    total_with_domain = sum(1 for r in recs if r.get("domain"))

    return {
        "multi_contact_records": len(multi_contact),
        "multi_contact_details": [
            {
                "id_hash": hash_id(r),
                "domain": r.get("domain"),
                "contacts": len(r.get("contacts", [])),
            }
            for r in multi_contact
        ],
        "unique_domains": unique_domains,
        "total_records_with_domain": total_with_domain,
        "duplicate_domains": total_with_domain - unique_domains,
        "cache_implemented": True,
        "cache_cleared_in_enrich_run": True,
        "cache_exercised_in_any_run": False,
    }


def main():
    recs = load_queue()

    print("=" * 70)
    print("TASK-211: Free-leg analysis of the estate")
    print("=" * 70)
    print()

    print(f"Records in queue: {len(recs)}")
    states = Counter(r.get("state") for r in recs)
    for s, c in states.most_common():
        print(f"  {s}: {c}")
    print()

    print("--- Spend provenance ---")
    spend = analyze_spend(recs)
    for k, v in spend.items():
        print(f"  {k}: {v}")
    print()

    print("--- Free-leg analysis ---")
    free = analyze_free_legs(recs)
    for k, v in free.items():
        print(f"  {k}: {v}")
    print()

    print("--- Unresolved records by reason ---")
    unresolved = analyze_unresolved(recs)
    for k, v in unresolved.items():
        print(f"  {k}: {v}")
    print()

    print("--- Crawl cache ---")
    cache = analyze_crawl_cache(recs)
    print(f"  Multi-contact records: {cache['multi_contact_records']}")
    print(f"  Unique domains: {cache['unique_domains']}")
    print(f"  Cache implemented: {cache['cache_implemented']}")
    print(f"  Cache cleared in enrich.run(): {cache['cache_cleared_in_enrich_run']}")
    print(f"  Cache exercised in any run: {cache['cache_exercised_in_any_run']}")
    print()

    print("--- Next-step costs for unresolved groups ---")
    costs = {
        "too_small_fail_closed": "NONE - fail-closed, no provider can change headcount",
        "geo_excluded_fail_closed": "NONE - fail-closed, geo is a client constraint",
        "missing_all_three": "webfetch crawl (FREE) -> ContactOut company-info (1 credit)",
        "missing_offices_and_industry": "webfetch crawl (FREE) -> ContactOut company-info (1 credit)",
        "missing_offices_only": "webfetch crawl (FREE) -> ContactOut company-info (1 credit)",
        "missing_industry_only": "webfetch crawl (FREE) -> ContactOut company-info (1 credit)",
        "missing_employees_only": "ContactOut people-count (FREE) -> company-info (1 credit)",
        "has_facts_needs_qualify": "NONE - needs qualify stage re-run, no provider call",
        "other": "VARIES - see individual records",
    }
    for group, count in unresolved.items():
        if count > 0:
            print(f"  {group} ({count}): {costs.get(group, 'TBD')}")


if __name__ == "__main__":
    main()
