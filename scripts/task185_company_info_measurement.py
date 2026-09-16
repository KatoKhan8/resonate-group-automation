#!/usr/bin/env python3
"""TASK-185: company-info on 25 records, comparable with TASK-183's Grok.

Two rounds:
  Round 1 (done): 25 records with NO company_facts at all.
                   ContactOut returned null for all 25. 0 credits charged.
  Round 2 (this): 25 records in icp_review that already carry SOME
                   company_facts (from people-count). ContactOut returns
                   data for these. This measures whether a SECOND call
                   resolves the criteria the first missed.

Usage:
    py -3 scripts/task185_company_info_measurement.py
"""
import hashlib
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import contactout
from src import icpstructural, clients, segments, store

SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
OUTPUT = os.path.join(ROOT, "scripts", "task185_results.json")


def hash_id(value):
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()[:16]


def load_snapshot():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def get_structural_verdict(rec, config):
    segment = segments.classify(rec, config)
    return icpstructural.structural(rec, config, segment=segment)


def pick_25_with_data(records, config):
    """Pick 25 icp_review records that already have SOME company_facts.

    These are records where ContactOut's people-count already returned
    something, so company-info is likely to return data too. The question
    is whether it returns NEW data that resolves UNKNOWN criteria.
    """
    candidates = []
    for rec in records:
        qual = rec.get("qualification") or {}
        verdict_block = qual.get("verdict") or {}
        structural = verdict_block.get("structural") or {}
        if structural.get("verdict") != "icp_review":
            continue
        facts = rec.get("company_facts") or {}
        has_industry = bool(facts.get("industry")
                            and facts["industry"] != "UNKNOWN")
        has_offices = bool(facts.get("offices"))
        has_employees = bool(
            facts.get("employees")
            and isinstance(facts.get("employees"), int)
            and facts["employees"] > 0)
        if not (has_industry or has_offices or has_employees):
            continue
        candidates.append(rec)

    candidates.sort(key=lambda r: r.get("id", ""))
    return candidates[:25]


def merge_company_info(rec, info):
    """Merge ContactOut company-info fields into company_facts.

    Only fills fields that are absent or empty. Does not overwrite existing
    evidence. Adds provenance.
    """
    facts = rec.setdefault("company_facts", {})
    now = store.now()
    merged = {}

    field_map = {
        "industry": "industry",
        "employees": "employees",
        "revenue": "revenue",
        "founded": "founded",
        "linkedin": "linkedin",
        "name": "name",
        "domain": "domain",
    }
    for info_key, fact_key in field_map.items():
        value = info.get(info_key)
        if value and not facts.get(fact_key):
            facts[fact_key] = value
            merged[fact_key] = value

    if info.get("offices") and not facts.get("offices"):
        facts["offices"] = info["offices"]
        merged["offices"] = info["offices"]

    if info.get("specialties") and not facts.get("specialties"):
        facts["specialties"] = info["specialties"]
        merged["specialties"] = info["specialties"]

    if info.get("stack") and not facts.get("stack"):
        facts["stack"] = info["stack"]
        merged["stack"] = info["stack"]

    # Also update employees if ContactOut returns a HIGHER value
    # (the existing one might be a band lower bound)
    new_emp = info.get("employees")
    if (isinstance(new_emp, int) and new_emp > 0
            and isinstance(facts.get("employees"), int)
            and new_emp > facts["employees"]):
        merged["employees_upgraded"] = (facts["employees"], new_emp)
        facts["employees"] = new_emp

    provenance = facts.setdefault("company_info_provenance", {})
    provenance["provider"] = "contactout"
    provenance["call"] = "company-information-from-domain"
    provenance["retrieved_at"] = now
    provenance["fields_merged"] = list(merged.keys())

    return merged


def main():
    print("TASK-185: company-info measurement (Round 2)")
    print("Records with existing company_facts, measuring NEW data")
    print("=" * 60)

    config = clients.load("productive")
    records = load_snapshot()
    print(f"Loaded {len(records)} records from snapshot")

    sample = pick_25_with_data(records, config)
    print(f"Selected {len(sample)} icp_review records with existing company_facts")

    # Record BEFORE state.
    before = []
    for rec in sample:
        result = get_structural_verdict(rec, config)
        before.append({
            "id": rec["id"],
            "domain": rec["domain"],
            "verdict": result["verdict"],
            "unknown_criteria": result["unknown_criteria"],
            "criteria": {k: v["status"] for k, v in result["criteria"].items()},
        })

    print(f"\nBEFORE state:")
    verdict_counts = {}
    for b in before:
        v = b["verdict"]
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    for v, c in sorted(verdict_counts.items()):
        print(f"  {v}: {c}")

    # Buy company-info for each.
    print(f"\nBuying company-info for {len(sample)} domains...")
    results = []
    credits_spent = 0
    errors = 0

    for i, rec in enumerate(sample):
        domain = rec["domain"]
        hashed = hash_id(rec["id"])
        print(f"  [{i+1}/{len(sample)}] {hashed} ({domain[:30]})", end=" ")

        try:
            info = contactout.company_info(domain)
            merged = merge_company_info(rec, info)
            credits_spent += 1
            fields = list(merged.keys())
            if fields:
                print(f"-> NEW: {fields}")
            else:
                print(f"-> no new fields")
        except Exception as e:
            errors += 1
            merged = {}
            print(f"-> ERROR: {e}")

        after_result = get_structural_verdict(rec, config)

        results.append({
            "id_hash": hashed,
            "domain_hash": hash_id(domain),
            "domain": domain,
            "before_verdict": before[i]["verdict"],
            "before_unknown": before[i]["unknown_criteria"],
            "before_criteria": before[i]["criteria"],
            "after_verdict": after_result["verdict"],
            "after_unknown": after_result["unknown_criteria"],
            "after_criteria": {k: v["status"]
                               for k, v in after_result["criteria"].items()},
            "fields_merged": list(merged.keys()),
            "moved": before[i]["verdict"] != after_result["verdict"],
        })

        time.sleep(0.15)

    # Report.
    print(f"\n{'=' * 60}")
    print(f"RESULTS")
    print(f"{'=' * 60}")
    print(f"Credits spent: {credits_spent}")
    print(f"Errors: {errors}")

    moved_to_qualified = 0
    moved_to_rejected = 0
    stayed_review = 0
    moved_details = []

    for r in results:
        bv = r["before_verdict"]
        av = r["after_verdict"]
        if bv == "icp_review" and av in ("icp_pass", "icp_pass_with_uncertainty"):
            moved_to_qualified += 1
            moved_details.append(r)
        elif bv == "icp_review" and av == "icp_fail":
            moved_to_rejected += 1
            moved_details.append(r)
        elif bv == "icp_review" and av == "icp_review":
            stayed_review += 1

    criteria_resolved = {}
    for criterion in ("geography", "company_type", "services_business",
                      "employees", "tracks_time"):
        resolved = 0
        for r in results:
            if r["before_criteria"].get(criterion) == "unknown":
                if r["after_criteria"].get(criterion) != "unknown":
                    resolved += 1
        criteria_resolved[criterion] = resolved

    total_verdicts = moved_to_qualified + moved_to_rejected
    cost_per_verdict = credits_spent / total_verdicts if total_verdicts else None

    print(f"\nMovement:")
    print(f"  review -> qualified: {moved_to_qualified}")
    print(f"  review -> rejected:  {moved_to_rejected}")
    print(f"  stayed review:       {stayed_review}")

    print(f"\nPer-criterion UNKNOWN resolution:")
    for criterion, count in criteria_resolved.items():
        print(f"  {criterion}: {count}/25 went from UNKNOWN to a value")

    print(f"\nCost per verdict:")
    print(f"  Credits spent: {credits_spent}")
    print(f"  Records that reached a verdict: {total_verdicts}")
    if cost_per_verdict:
        print(f"  Cost per verdict: {cost_per_verdict:.1f} credits")
    else:
        print(f"  Cost per verdict: N/A (no records reached a verdict)")

    if moved_details:
        print(f"\nMoved records:")
        for r in moved_details:
            print(f"  {r['domain']}: {r['before_verdict']} -> {r['after_verdict']}")
            print(f"    before unknown: {r['before_unknown']}")
            print(f"    after unknown:  {r['after_unknown']}")
            print(f"    fields merged:  {r['fields_merged']}")

    # verdict_of analysis
    print(f"\nverdict_of analysis:")
    print(f"  Does verdict_of require all five to PASS?")
    print(f"  No. The rules are:")
    print(f"    - Any FAIL -> icp_fail")
    print(f"    - All PASSING -> icp_pass")
    print(f"    - DEFINING (geography + company_type) both PASSING -> icp_pass_with_uncertainty")
    print(f"    - Otherwise -> icp_review")

    # Round 1 results (from earlier run)
    round1 = {
        "description": "25 records with NO company_facts at all",
        "credits_charged": 0,
        "contactout_returned_data": 0,
        "movement": {
            "review_to_qualified": 0,
            "review_to_rejected": 0,
            "stayed_review": 25,
        },
        "per_criterion_resolution": {
            "geography": 0, "company_type": 0, "services_business": 0,
            "employees": 0, "tracks_time": 0,
        },
    }

    output = {
        "task": "TASK-185",
        "measurement": "company-info (ContactOut) on 25+25 review records",
        "snapshot_stamp": "2026-09-15T17:52:12+00:00 from master cf23154 550 records",
        "round1_no_evidence": round1,
        "round2_with_existing_evidence": {
            "credits_spent": credits_spent,
            "errors": errors,
            "movement": {
                "review_to_qualified": moved_to_qualified,
                "review_to_rejected": moved_to_rejected,
                "stayed_review": stayed_review,
            },
            "per_criterion_resolution": criteria_resolved,
            "cost_per_verdict_credits": cost_per_verdict,
        },
        "verdict_of_requires_all_five": False,
        "verdict_of_rules": {
            "any_FAIL": "icp_fail",
            "all_PASSING": "icp_pass",
            "defining_PASSING": "icp_pass_with_uncertainty",
            "otherwise": "icp_review",
        },
        "results": results,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to {OUTPUT}")

    return output


if __name__ == "__main__":
    main()
