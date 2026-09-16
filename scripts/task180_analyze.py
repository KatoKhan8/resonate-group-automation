#!/usr/bin/env python3
"""TASK-180: Measure what evidence the 316 records carry per structural criterion.

Reads the snapshot (the only queue file available in this worktree) and
evaluates each record against the five structural criteria in icpstructural.py.
Reports per-criterion UNKNOWN/PASS/FAIL counts and what would need to change
to move records from review to a verdict.

IMPORTANT: The snapshot is stale (550 records vs live 300). This script
measures what IS on the records, not what the live pipeline produced.
"""
import json
import os
import sys
import hashlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import icpstructural, clients, segments

SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")

def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def hash_id(rec):
    return hashlib.sha256(rec.get("id", "").encode()).hexdigest()[:12]

def hash_domain(rec):
    return hashlib.sha256(rec.get("domain", "").encode()).hexdigest()[:12]

def analyze_criteria(rec, config):
    """Run structural analysis and return per-criterion detail."""
    segment = segments.classify(rec, config)
    rules = icpstructural.settings(config)
    
    criteria = {
        "geography": icpstructural._geography(rec, segment, rules),
        "company_type": icpstructural._company_type(rec, segment, rules),
        "services_business": icpstructural._services_business(segment, rules),
        "employees": icpstructural._employees(rec, segment, rules),
        "tracks_time": icpstructural._tracks_time(rec, segment, rules),
    }
    verdict = icpstructural.verdict_of(criteria)
    
    return {
        "id_hash": hash_id(rec),
        "domain_hash": hash_domain(rec),
        "state": rec.get("state"),
        "verdict": verdict,
        "criteria": {name: {
            "status": ans["status"],
            "source": ans.get("source"),
            "why": ans.get("why", "")[:120],
        } for name, ans in criteria.items()},
        "has_research": bool(rec.get("research")),
        "research_count": len(rec.get("research") or []),
        "has_company_facts": bool(rec.get("company_facts")),
        "research_outcome": (rec.get("company_facts") or {}).get("research_outcome"),
    }

def main():
    records = load_records()
    config = clients.load("productive")
    
    print(f"Snapshot: {SNAPSHOT}")
    print(f"Total records: {len(records)}")
    
    # Filter to domains lane, productive client
    domains = [r for r in records 
               if r.get("lane") == "domains" and r.get("client") == "productive"]
    print(f"Domains/productive: {len(domains)}")
    
    # Analyze all
    results = [analyze_criteria(r, config) for r in domains]
    
    # Count verdicts
    verdicts = {}
    for r in results:
        v = r["verdict"]
        verdicts[v] = verdicts.get(v, 0) + 1
    
    print(f"\n=== VERDICT DISTRIBUTION ===")
    for v in ("icp_pass", "icp_pass_with_uncertainty", "icp_review", "icp_fail"):
        print(f"  {v:35s} {verdicts.get(v, 0):5d}")
    
    # Per-criterion status counts
    print(f"\n=== PER-CRITERION STATUS ===")
    criteria_names = ("geography", "company_type", "services_business", 
                      "employees", "tracks_time")
    for cname in criteria_names:
        counts = {}
        sources = {}
        for r in results:
            c = r["criteria"][cname]
            s = c["status"]
            counts[s] = counts.get(s, 0) + 1
            src = c.get("source") or "none"
            sources[src] = sources.get(src, 0) + 1
        print(f"\n  {cname}:")
        for s in ("pass", "pass_with_tolerance", "fail", "unknown", "not_required"):
            if s in counts:
                print(f"    {s:25s} {counts[s]:5d}")
        print(f"    sources:")
        for src, n in sorted(sources.items(), key=lambda x: -x[1])[:8]:
            print(f"      {src:45s} {n:5d}")
    
    # Records in review: what UNKNOWN criteria do they have?
    review_recs = [r for r in results if r["verdict"] == "icp_review"]
    print(f"\n=== REVIEW RECORDS: UNKNOWN CRITERIA COMBOS ===")
    combos = {}
    for r in review_recs:
        unknowns = tuple(sorted(
            name for name, c in r["criteria"].items() 
            if c["status"] == "unknown"
        ))
        combos[unknowns] = combos.get(unknowns, 0) + 1
    for combo, n in sorted(combos.items(), key=lambda x: -x[1]):
        print(f"  {str(combo):70s} {n:5d}")
    
    # Evidence analysis
    print(f"\n=== EVIDENCE PRESENCE ===")
    with_research = sum(1 for r in results if r["has_research"])
    with_facts = sum(1 for r in results if r["has_company_facts"])
    with_outcome = sum(1 for r in results if r["research_outcome"])
    outcomes = {}
    for r in results:
        o = r["research_outcome"]
        if o:
            outcomes[o] = outcomes.get(o, 0) + 1
    print(f"  With research items: {with_research}")
    print(f"  With company_facts:  {with_facts}")
    print(f"  With research_outcome: {with_outcome}")
    for o, n in sorted(outcomes.items(), key=lambda x: -x[1]):
        print(f"    {o:30s} {n:5d}")
    
    # What would move review records?
    print(f"\n=== WHAT WOULD MOVE REVIEW RECORDS ===")
    # For each review record, which criteria are UNKNOWN and what could resolve them
    for cname in criteria_names:
        unknown_in_review = [
            r for r in review_recs 
            if r["criteria"][cname]["status"] == "unknown"
        ]
        print(f"\n  {cname}: {len(unknown_in_review)} review records have this UNKNOWN")
        # What sources are missing?
        source_gaps = {}
        for r in unknown_in_review:
            why = r["criteria"][cname].get("why", "")[:80]
            source_gaps[why] = source_gaps.get(why, 0) + 1
        for why, n in sorted(source_gaps.items(), key=lambda x: -x[1])[:5]:
            print(f"    {why:80s} {n:5d}")
    
    # Records that COULD pass if evidence arrived
    print(f"\n=== PROJECTION: IF ALL UNKNOWN BECAME PASS ===")
    could_pass = 0
    for r in review_recs:
        has_fail = any(c["status"] == "fail" for c in r["criteria"].values())
        if not has_fail:
            could_pass += 1
    print(f"  Review records with no FAIL (could pass with evidence): {could_pass}")
    print(f"  Review records with a FAIL (evidence cannot help): "
          f"{len(review_recs) - could_pass}")
    
    # Records with existing evidence that STILL got review
    print(f"\n=== RECORDS WITH EVIDENCE STILL IN REVIEW ===")
    evidence_review = [r for r in review_recs if r["has_research"] or r["has_company_facts"]]
    print(f"  Count: {len(evidence_review)}")
    for r in evidence_review[:10]:
        unknowns = [name for name, c in r["criteria"].items() 
                    if c["status"] == "unknown"]
        print(f"    {r['id_hash']} research={r['research_count']} "
              f"outcome={r['research_outcome']} unknowns={unknowns}")

if __name__ == "__main__":
    main()
