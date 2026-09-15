#!/usr/bin/env python3
"""TASK-154 deep dive: why don't 326 no-evidence records trigger why()?
And details on the 23 that do need research.
"""
import json
import os
import sys
import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import research, evidence as ev, segments, icp

SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
TODAY = datetime.datetime(2026, 9, 15, tzinfo=datetime.timezone.utc)


def load_snapshot():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main():
    records = load_snapshot()

    # Categorise the 343 no-evidence records by WHY they don't need research
    no_evidence = []
    for rec in records:
        if not research.existing_evidence(rec):
            no_evidence.append(rec)

    print(f"Records with no evidence: {len(no_evidence)}")
    print()

    # For each, determine why why() returns None
    reasons_no_fire = {
        "has_structured_facts": 0,
        "cold_with_hook": 0,
        "domains_with_angle": 0,
        "no_rebrand_signal": 0,
        "icp_qualified_or_rejected": 0,
        "lane_not_cold_or_domains": 0,
    }

    details = []
    for rec in no_evidence:
        rid = rec["id"]
        lane = rec.get("lane", "")
        facts = research.structured_evidence(rec)
        hook = rec.get("hook")
        contacts = rec.get("contacts") or []
        has_angle = all(c.get("angle") for c in contacts) if contacts else True
        mail_domain = (rec.get("company_facts") or {}).get("email_domain")
        qual = rec.get("qualification") or {}
        verdict_obj = qual.get("verdict") or {}
        verdict = verdict_obj.get("verdict")
        icp_status = verdict_obj.get("icp_status")

        reason = research.why(rec, today=TODAY)

        # Determine why it doesn't fire
        why_not = []
        if facts.get("notable") or facts.get("specialties"):
            why_not.append("has_structured_notable_or_specialties")
        if lane == "cold" and hook:
            why_not.append("cold_with_hook")
        if lane == "domains" and (facts.get("specialties") or facts.get("industry")):
            why_not.append("domains_has_specialties_or_industry")
        if lane == "domains" and has_angle:
            why_not.append("domains_all_contacts_have_angle")
        if mail_domain and mail_domain != rec.get("domain") and not facts.get("name"):
            why_not.append("rebrand_signal")
        if icp_status in ("qualified", "rejected"):
            why_not.append(f"icp_{icp_status}")
        if icp_status in ("review", "unknown") and not research.icp_prose_missing(rec):
            why_not.append("icp_prose_present")
        if lane not in ("cold", "domains"):
            why_not.append(f"lane_is_{lane}")

        if not why_not:
            why_not.append("UNCLASSIFIED")

        details.append({
            "id": rid,
            "lane": lane,
            "verdict": verdict,
            "icp_status": icp_status,
            "structured_facts_keys": sorted(facts.keys()),
            "why_not": why_not,
            "domain": rec.get("domain", ""),
            "company": rec.get("company", ""),
        })

    # Summarise
    why_not_counts = {}
    for d in details:
        for w in d["why_not"]:
            why_not_counts[w] = why_not_counts.get(w, 0) + 1

    print("Why 326 no-evidence records do NOT trigger why():")
    for w, c in sorted(why_not_counts.items(), key=lambda x: -x[1]):
        print(f"  {w}: {c}")
    print()

    # Lane breakdown of no-evidence records
    lane_counts = {}
    for rec in no_evidence:
        lane = rec.get("lane", "unknown")
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
    print("No-evidence records by lane:")
    for lane, c in sorted(lane_counts.items(), key=lambda x: -x[1]):
        print(f"  {lane}: {c}")
    print()

    # ICP verdict breakdown of no-evidence records
    verdict_counts = {}
    for rec in no_evidence:
        qual = rec.get("qualification") or {}
        verdict_obj = qual.get("verdict") or {}
        verdict = verdict_obj.get("verdict") or "none"
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
    print("No-evidence records by ICP verdict:")
    for v, c in sorted(verdict_counts.items(), key=lambda x: -x[1]):
        print(f"  {v}: {c}")
    print()

    # ---- The 23 that DO need research: details ----
    print("=" * 70)
    print("THE 23 RECORDS THAT NEED RESEARCH - DETAILS")
    print("=" * 70)

    needs = []
    for rec in records:
        reason = research.why(rec, today=TODAY)
        stale = research.stale_evidence(rec, today=TODAY)
        if reason or stale:
            qual = rec.get("qualification") or {}
            verdict_obj = qual.get("verdict") or {}
            needs.append({
                "id": rec["id"],
                "domain": rec.get("domain", ""),
                "company": rec.get("company", ""),
                "lane": rec.get("lane", ""),
                "reason": reason,
                "stale_fields": [e.get("field") for e in stale],
                "icp_verdict": verdict_obj.get("verdict") or "none",
                "icp_status": verdict_obj.get("icp_status") or "none",
                "existing_rows": len(rec.get("research") or []),
                "state": rec.get("state", ""),
            })

    for n in needs:
        print(f"  {n['id']:40s} domain={n['domain']:30s} reason={n['reason'] or 'STALE':50s} "
              f"icp={n['icp_verdict']} stale_fields={n['stale_fields']} "
              f"existing_rows={n['existing_rows']} state={n['state']}")

    print()

    # Free vs paid split analysis
    # We can't know without probing, but we can note domains for the worklist
    print("=" * 70)
    print("DOMAINS TO PROBE (up to 5 for reachability)")
    print("=" * 70)
    # Pick 5 from the actionable worklist - prioritise ICP-relevant ones
    # All 23 have no verdict, so pick 5 with ICP-dimension need first
    icp_needs = [n for n in needs if n["reason"] == research.NEED_ICP_EVIDENCE]
    stale_needs = [n for n in needs if n["reason"] == research.NEED_REFRESH]

    print(f"ICP-dimension needs: {len(icp_needs)}")
    for n in icp_needs[:3]:
        print(f"  {n['id']:40s} {n['domain']}")
    print(f"Stale refresh needs: {len(stale_needs)}")
    for n in stale_needs[:2]:
        print(f"  {n['id']:40s} {n['domain']}")

    # Select 5 domains to probe
    probe_domains = []
    for n in icp_needs[:3]:
        probe_domains.append(n["domain"])
    for n in stale_needs[:2]:
        probe_domains.append(n["domain"])
    probe_domains = probe_domains[:5]

    print()
    print(f"Selected domains for reachability probe: {probe_domains}")

    # Output for the reachability probe script
    output = {
        "probe_domains": probe_domains,
        "needs": needs,
    }
    output_path = os.path.join(ROOT, "scripts", "task154_probe.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Probe details written to: {output_path}")


if __name__ == "__main__":
    main()
