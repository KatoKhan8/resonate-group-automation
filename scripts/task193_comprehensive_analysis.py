#!/usr/bin/env python3
"""TASK-193: Comprehensive analysis - what if we fixed both issues?"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import icpstructural, clients, segments

SNAPSHOT = Path(__file__).parent.parent / "work" / "queue.snapshot.jsonl"

# Missing ISO codes that appear in the data
MISSING_ISO = {
    "CZ": "Czech Republic",
    "GR": "Greece",
    "CY": "Cyprus",
    "RS": "Serbia",
    "SS": "South Sudan",
    "UA": "Ukraine",
    "AR": "Argentina",
    "HU": "Hungary",
    "JO": "Jordan",
    "SI": "Slovenia",
    "LT": "Lithuania",
    "EE": "Estonia",
    "ZA": "South Africa",
    "MC": "Monaco",
    "RU": "Russia",
    "TN": "Tunisia",
    "MX": "Mexico",
}


def load_snapshot():
    records = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def resolve_country_extended(rec, segment):
    """Like resolve_country but with the missing ISO codes added."""
    if segment.get("country"):
        return segment["country"], "segment.country"
    code = str(segment.get("country_code") or "").strip().upper()
    extended_iso = {**icpstructural.ISO_TO_NAME, **MISSING_ISO}
    if code in extended_iso:
        return extended_iso[code], "segment.country_code"
    for line in (rec.get("company_facts") or {}).get("offices") or ():
        token = str(line).strip().rstrip(".").split(",")[-1].strip().upper()
        if token in extended_iso:
            return extended_iso[token], "company_facts.offices"
    return None, None


def geography_with_extended_iso(rec, segment, rules):
    """What geography would return with extended ISO map."""
    include = {icpstructural._norm(g) for g in rules["include_geos"]}
    exclude = {icpstructural._norm(g) for g in rules["exclude_geos"]}
    if not include and not exclude:
        return "not_required"
    
    country, source = resolve_country_extended(rec, segment)
    region = segment.get("region")
    
    pairs = ((country, source), (region, "segment.region"))
    for label, where in pairs:
        if label and icpstructural._norm(label) in exclude:
            return "fail"
    for label, where in pairs:
        if label and icpstructural._norm(label) in include:
            return "pass"
    if not country and not icpstructural._norm(region):
        return "unknown"
    return "unknown"


def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 80)
    print("TASK-193: Comprehensive Analysis")
    print("=" * 80)
    print()
    
    records = load_snapshot()
    config = clients.load("productive")
    rules = icpstructural.settings(config)
    
    print("SCENARIO 1: Current state (as-is)")
    print("-" * 80)
    
    current_status = {}
    for rec in records:
        segment = segments.classify(rec, config)
        geo = icpstructural._geography(rec, segment, rules)
        status = geo["status"]
        current_status[status] = current_status.get(status, 0) + 1
    
    print(f"  PASS: {current_status.get('pass', 0)}")
    print(f"  FAIL: {current_status.get('fail', 0)}")
    print(f"  UNKNOWN: {current_status.get('unknown', 0)}")
    print()
    
    print("SCENARIO 2: With missing ISO codes added (but still design=UNKNOWN)")
    print("-" * 80)
    
    extended_status = {}
    extended_details = []
    for rec in records:
        segment = segments.classify(rec, config)
        geo = geography_with_extended_iso(rec, segment, rules)
        extended_status[geo] = extended_status.get(geo, 0) + 1
        
        # Track records that would be UNKNOWN with country resolved
        if geo == "unknown":
            country, source = resolve_country_extended(rec, segment)
            if country and source == "company_facts.offices":
                offices = (rec.get("company_facts") or {}).get("offices") or []
                extended_details.append({
                    "id": rec.get("id"),
                    "domain": rec.get("domain"),
                    "state": rec.get("state"),
                    "country": country,
                    "offices": offices[:2],  # First 2 offices
                })
    
    print(f"  PASS: {extended_status.get('pass', 0)}")
    print(f"  FAIL: {extended_status.get('fail', 0)}")
    print(f"  UNKNOWN: {extended_status.get('unknown', 0)}")
    print()
    
    print("SCENARIO 3: With missing ISO codes AND office data can produce FAIL")
    print("-" * 80)
    print()
    print("This is the hypothetical: if we changed the design to allow office")
    print("data to produce FAIL when the country is not on the include list.")
    print()
    
    # Count records that would FAIL
    would_fail = []
    for rec in records:
        segment = segments.classify(rec, config)
        country, source = resolve_country_extended(rec, segment)
        
        if not country:
            continue
        
        include = {icpstructural._norm(g) for g in rules["include_geos"]}
        exclude = {icpstructural._norm(g) for g in rules["exclude_geos"]}
        
        # Already FAIL on exclude list
        if icpstructural._norm(country) in exclude:
            would_fail.append({
                "id": rec.get("id"),
                "domain": rec.get("domain"),
                "state": rec.get("state"),
                "country": country,
                "reason": "on exclude list",
            })
            continue
        
        # Would FAIL if not on include list (the hypothetical change)
        if icpstructural._norm(country) not in include:
            would_fail.append({
                "id": rec.get("id"),
                "domain": rec.get("domain"),
                "state": rec.get("state"),
                "country": country,
                "reason": "not on include list",
            })
    
    print(f"Records that would FAIL: {len(would_fail)} of {len(records)}")
    print()
    
    # Break down by state
    state_counts = {}
    for r in would_fail:
        state = r["state"]
        state_counts[state] = state_counts.get(state, 0) + 1
    
    print("Breakdown by current state:")
    for state, count in sorted(state_counts.items()):
        print(f"  {state}: {count}")
    print()
    
    # Breakdown by reason
    reason_counts = {}
    for r in would_fail:
        reason = r["reason"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    
    print("Breakdown by reason:")
    for reason, count in sorted(reason_counts.items()):
        print(f"  {reason}: {count}")
    print()
    
    # Show the records in icp_review that would FAIL
    review_would_fail = [r for r in would_fail if r["state"] == "icp_review"]
    print(f"Records in icp_review that would move to icp_fail: {len(review_would_fail)}")
    print()
    
    if review_would_fail:
        print("Details:")
        for r in review_would_fail[:20]:  # First 20
            print(f"  {r['domain']}: {r['country']} ({r['reason']})")
        if len(review_would_fail) > 20:
            print(f"  ... and {len(review_would_fail) - 20} more")
        print()
    
    # Country breakdown
    country_counts = {}
    for r in would_fail:
        country = r["country"]
        country_counts[country] = country_counts.get(country, 0) + 1
    
    print("Countries that would cause rejection:")
    for country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
        print(f"  {country}: {count} records")
    print()
    
    print("=" * 80)
    print("FINDINGS")
    print("=" * 80)
    print()
    print("1. TWO ISSUES, NOT ONE:")
    print()
    print("   a) 17 ISO codes are missing from ISO_TO_NAME, affecting 21 records.")
    print("      These include UA (Ukraine), CY (Cyprus), RU (Russia), GR (Greece),")
    print("      CZ (Czech Republic), and others. Offices in these countries don't")
    print("      resolve to a country at all.")
    print()
    print("   b) The design decision: even when a country IS resolved, if it's not")
    print("      on the include list, geography returns UNKNOWN, not FAIL.")
    print()
    print("2. THE COUNT:")
    print()
    print(f"   If both issues were fixed (ISO codes added AND office data could")
    print(f"   produce FAIL):")
    print(f"     {len(would_fail)} records would FAIL")
    print(f"     {len(review_would_fail)} of those are in icp_review")
    print(f"     {state_counts.get('dropped', 0)} are already dropped")
    print(f"     {state_counts.get('queued', 0)} are in queued state")
    print()
    print("3. DEFECT OR DESIGN?")
    print()
    print("   The UNKNOWN-for-non-include-list behavior is DESIGN, not defect.")
    print("   The missing ISO codes are a DATA GAP, not a design decision.")
    print()
    print("4. WHICH OF THE FOUR DISCARD SHAPES (if it were a defect)?")
    print()
    print("   The office data IS written to company_facts.offices.")
    print("   The criterion DOES read it (resolve_country iterates offices).")
    print("   The ISO code extraction FAILS for 17 codes not in ISO_TO_NAME.")
    print("   So it's the third shape: 'written in a shape it could not parse' -")
    print("   the ISO code is there, but the map doesn't know it.")
    print()
    print("5. HOW THIS DIFFERS FROM TLD INFERENCE PRODUCING FAIL:")
    print()
    print("   It does not differ. The principle is the same:")
    print("   'an inference may move a criterion from UNKNOWN to PASS and never")
    print("   to FAIL'. Office data is inference (the company has an office there,")
    print("   but may operate elsewhere), just like a TLD is inference (the domain")
    print("   is .ua, but the company may operate elsewhere).")
    print()
    print("   The difference is that office data is MORE concrete than a TLD -")
    print("   a physical office is a stronger signal than a domain registration.")
    print("   But the principle still applies: a company with an office in Ukraine")
    print("   may still deliver services in Germany, and rejecting it permanently")
    print("   on the strength of one office record is the risk the design avoids.")
    print()


if __name__ == "__main__":
    main()
