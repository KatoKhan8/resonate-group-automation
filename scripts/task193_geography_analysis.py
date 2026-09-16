#!/usr/bin/env python3
"""TASK-193: Analyze office data and geography verdicts.

The question: company-info returned office locations for 25 records, but
geography stayed UNKNOWN. Why? Is it a defect or design?

This script:
1. Reads the snapshot and extracts office data from company_facts
2. Traces what resolve_country() would return for each record
3. Traces what _geography() would return
4. Counts how many records have offices outside the include list
5. Identifies the code path that produces UNKNOWN instead of FAIL
"""
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import icpstructural, clients, segments

SNAPSHOT = Path(__file__).parent.parent / "work" / "queue.snapshot.jsonl"
TASK185_RESULTS = Path(__file__).parent / "task185_results.json"


def load_snapshot():
    """Load all records from the snapshot."""
    records = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def load_task185_results():
    """Load TASK-185's per-record results if available."""
    if not TASK185_RESULTS.exists():
        return None
    with open(TASK185_RESULTS, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_record(rec, config):
    """Trace the geography code path for one record."""
    rules = icpstructural.settings(config)
    segment = segments.classify(rec, config)
    
    # What does resolve_country return?
    country, source = icpstructural.resolve_country(rec, segment)
    
    # What does _geography return?
    geo_answer = icpstructural._geography(rec, segment, rules)
    
    # What offices are on the record?
    offices = (rec.get("company_facts") or {}).get("offices") or []
    
    # Extract ISO codes from office lines
    office_countries = []
    for line in offices:
        token = str(line).strip().rstrip(".").split(",")[-1].strip().upper()
        if token in icpstructural.ISO_TO_NAME:
            office_countries.append({
                "iso": token,
                "name": icpstructural.ISO_TO_NAME[token],
                "line": line
            })
    
    return {
        "record_id": rec.get("id"),
        "domain": rec.get("domain"),
        "state": rec.get("state"),
        "offices": offices,
        "office_countries": office_countries,
        "resolved_country": country,
        "resolved_source": source,
        "geography_status": geo_answer["status"],
        "geography_why": geo_answer["why"],
        "geography_source": geo_answer.get("source"),
        "include_geos": list(rules["include_geos"]),
        "exclude_geos": list(rules["exclude_geos"]),
    }


def main():
    # Force UTF-8 output
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 80)
    print("TASK-193: Geography Verdict Analysis")
    print("=" * 80)
    print()
    
    records = load_snapshot()
    print(f"Loaded {len(records)} records from snapshot")
    print()
    
    # Load config
    config = clients.load("productive")
    rules = icpstructural.settings(config)
    
    print("Client geography rules:")
    print(f"  Include list: {rules['include_geos']}")
    print(f"  Exclude list: {rules['exclude_geos']}")
    print()
    
    # Analyze all records
    analyses = []
    for rec in records:
        analysis = analyze_record(rec, config)
        analyses.append(analysis)
    
    # Count records with office data
    with_offices = [a for a in analyses if a["offices"]]
    print(f"Records with office data: {len(with_offices)} of {len(records)}")
    print()
    
    # Count records where offices resolved to a country
    with_resolved_country = [a for a in with_offices if a["resolved_country"]]
    print(f"Records where offices resolved to a country: {len(with_resolved_country)}")
    print()
    
    # Break down by geography status
    status_counts = {}
    for a in analyses:
        status = a["geography_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("Geography status breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    print()
    
    # Focus on records with offices but UNKNOWN geography
    unknown_with_offices = [
        a for a in with_offices
        if a["geography_status"] == icpstructural.UNKNOWN
    ]
    
    print(f"Records with offices but UNKNOWN geography: {len(unknown_with_offices)}")
    print()
    
    if unknown_with_offices:
        print("Sample records (first 10):")
        print("-" * 80)
        for a in unknown_with_offices[:10]:
            print(f"Record: {a['record_id']}")
            print(f"  Domain: {a['domain']}")
            print(f"  State: {a['state']}")
            print(f"  Offices: {a['offices']}")
            print(f"  Office countries: {[c['name'] for c in a['office_countries']]}")
            print(f"  Resolved country: {a['resolved_country']}")
            print(f"  Resolved source: {a['resolved_source']}")
            print(f"  Geography status: {a['geography_status']}")
            print(f"  Geography why: {a['geography_why']}")
            print()
    
    # Count countries that appear in offices but are not on include list
    country_counts = {}
    for a in with_offices:
        for c in a["office_countries"]:
            name = c["name"]
            country_counts[name] = country_counts.get(name, 0) + 1
    
    print("Countries appearing in office data:")
    for country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
        on_include = country.lower() in [g.lower() for g in rules["include_geos"]]
        on_exclude = country.lower() in [g.lower() for g in rules["exclude_geos"]]
        marker = "✓ INCLUDE" if on_include else ("✗ EXCLUDE" if on_exclude else "? NEITHER")
        print(f"  {country}: {count} records [{marker}]")
    print()
    
    # Count how many records would FAIL if office data could produce FAIL
    # A record would FAIL if ALL its offices are outside the include list
    would_fail = []
    for a in with_offices:
        if not a["office_countries"]:
            continue
        # Check if any office is in the include list
        any_in_include = any(
            c["name"].lower() in [g.lower() for g in rules["include_geos"]]
            for c in a["office_countries"]
        )
        if not any_in_include:
            would_fail.append(a)
    
    print(f"Records that would FAIL if office data could produce FAIL:")
    print(f"  {len(would_fail)} of {len(records)} total records")
    print(f"  {len(would_fail)} of {len(with_offices)} records with office data")
    print()
    
    # Break down by state
    state_counts = {}
    for a in would_fail:
        state = a["state"]
        state_counts[state] = state_counts.get(state, 0) + 1
    
    print("Breakdown by current state:")
    for state, count in sorted(state_counts.items()):
        print(f"  {state}: {count}")
    print()
    
    # Check TASK-185 results if available
    task185 = load_task185_results()
    if task185:
        print("=" * 80)
        print("TASK-185 Round 2 records (25 records with company-info data)")
        print("=" * 80)
        print()
        
        # Find the 25 records TASK-185 processed
        task185_domains = set()
        if isinstance(task185, list):
            task185_domains = {r.get("domain") for r in task185 if r.get("domain")}
        elif isinstance(task185, dict) and "results" in task185:
            task185_domains = {r.get("domain") for r in task185["results"] if r.get("domain")}
        
        if task185_domains:
            task185_analyses = [a for a in analyses if a["domain"] in task185_domains]
            print(f"Found {len(task185_analyses)} of 25 TASK-185 records in snapshot")
            print()
            
            # Show what happened to each
            for a in task185_analyses:
                if a["office_countries"]:
                    print(f"Domain: {a['domain']}")
                    print(f"  Offices: {a['offices']}")
                    print(f"  Countries: {[c['name'] for c in a['office_countries']]}")
                    print(f"  Geography: {a['geography_status']} - {a['geography_why']}")
                    print()
    
    print("=" * 80)
    print("CODE PATH ANALYSIS")
    print("=" * 80)
    print()
    print("The code path in icpstructural.py:")
    print()
    print("1. resolve_country(rec, segment) at lines 165-175:")
    print("   - Checks segment.country first")
    print("   - Then segment.country_code")
    print("   - Then iterates company_facts.offices")
    print("   - Extracts last token (ISO code) from each office line")
    print("   - Returns (country_name, source) or (None, None)")
    print()
    print("2. _geography(rec, segment, rules) at lines 291-313:")
    print("   - Lines 298-301: If country in EXCLUDE list -> FAIL")
    print("   - Lines 302-305: If country in INCLUDE list -> PASS")
    print("   - Lines 306-309: If no country found -> UNKNOWN")
    print("   - Lines 310-313: If country found but NOT on either list -> UNKNOWN")
    print("     with message: 'is on neither list, so it is unestablished")
    print("     rather than excluded'")
    print()
    print("VERDICT: This is a DESIGN DECISION, not a defect.")
    print()
    print("The code deliberately treats 'country not on include list' as UNKNOWN")
    print("rather than FAIL. The reasoning is in the module docstring:")
    print()
    print("  'UNKNOWN is not FAIL, and that is the whole point'")
    print("  'A criterion this system could not establish leaves the company")
    print("   eligible with uncertainty. Only affirmative evidence of a")
    print("   violation fails it.'")
    print()
    print("  'FAIL     we know this company does not fit'")
    print("  'UNKNOWN  we could not establish it'")
    print()
    print("The code also notes:")
    print("  'location_why: no usable location evidence is not evidence of")
    print("   being in an excluded country'")
    print()
    print("So a company with offices in Ukraine (not on include list) is")
    print("treated as 'geography unestablished' not 'geography excluded'.")
    print()
    print("=" * 80)
    print("DEFECT OR DESIGN?")
    print("=" * 80)
    print()
    print("DESIGN. The code is doing exactly what it was designed to do.")
    print()
    print("The rationale is that an office list may be incomplete, a company")
    print("headquartered outside the include list may still deliver inside it,")
    print("and a single office in Cyprus may be a holding company.")
    print()
    print("The system prefers to leave the company eligible with uncertainty")
    print("rather than reject it on partial or inferred data.")
    print()
    print("This is consistent with the rule from TASK-190: 'an inference may")
    print("move a criterion from UNKNOWN to PASS and never to FAIL' - though")
    print("TASK-190 is about free evidence, the principle is the same.")
    print()
    print("=" * 80)
    print("COUNT: WHAT IS IT WORTH?")
    print("=" * 80)
    print()
    print(f"If office data were allowed to produce FAIL:")
    print(f"  {len(would_fail)} records would be cleanly rejected")
    print(f"  of {len(records)} total records")
    print()
    
    # Break down by state for the would-fail records
    review_would_fail = [a for a in would_fail if a["state"] == "icp_review"]
    print(f"Of those {len(would_fail)} records:")
    print(f"  {len(review_would_fail)} are currently in icp_review")
    print(f"  These would move from icp_review to icp_fail")
    print()
    
    # Show the countries that would cause rejection
    print("Countries that would cause rejection (not on include list):")
    reject_countries = {}
    for a in would_fail:
        for c in a["office_countries"]:
            name = c["name"]
            reject_countries[name] = reject_countries.get(name, 0) + 1
    
    for country, count in sorted(reject_countries.items(), key=lambda x: -x[1]):
        print(f"  {country}: {count} records")
    print()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("1. The code path: resolve_country() reads company_facts.offices,")
    print("   extracts ISO codes, and _geography() uses the resolved country.")
    print()
    print("2. Defect or design: DESIGN. The code deliberately treats 'country")
    print("   not on include list' as UNKNOWN, not FAIL.")
    print()
    print("3. Which of the four discard shapes: N/A - this is not a discard,")
    print("   it is a deliberate choice to leave the criterion UNKNOWN.")
    print()
    print(f"4. Count: {len(would_fail)} records would FAIL if office data could")
    print(f"   produce FAIL. Of those, {len(review_would_fail)} are currently")
    print(f"   in icp_review and would move to icp_fail.")
    print()
    print("5. Not fixed in this task, as instructed. A change that lets a")
    print("   criterion produce FAIL from inferred or partial data can reject")
    print("   a good company permanently, and icp_fail is terminal.")
    print()
    print("6. How this differs from TLD inference producing FAIL: it does not.")
    print("   The principle is the same - an inference may move a criterion")
    print("   from UNKNOWN to PASS and never to FAIL. Office data is inference")
    print("   (the company has an office there, but may operate elsewhere),")
    print("   just like a TLD is inference (the domain is .ua, but the company")
    print("   may operate elsewhere).")
    print()


if __name__ == "__main__":
    main()
