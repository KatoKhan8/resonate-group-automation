#!/usr/bin/env python3
"""TASK-133: the 12 ICP-passed contactless records - what are they?"""
import json
from pathlib import Path

SNAPSHOT = Path("work/queue.snapshot.jsonl")

def load_records():
    records = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def main():
    records = load_records()
    active = [r for r in records if r.get("drop_reason") is None]
    
    print("THE 12 ICP-PASSED RECORDS WITH NO CONTACTS")
    print("=" * 70)
    
    count = 0
    for rec in active:
        if rec.get("contacts") or rec.get("excluded"):
            continue
        
        log = rec.get("log", [])
        notes = [e.get("note", "") for e in log]
        has_people_zero = any("people-count: 0" in n for n in notes)
        icp_flags = (rec.get("company_facts") or {}).get("icp_flags", [])
        
        # Has ICP rejection?
        has_rejection = any("under the client minimum" in n or 
                          "geo outside" in n for n in notes)
        
        if not has_people_zero and not has_rejection and not icp_flags:
            count += 1
            domain = rec.get("domain", "?")
            company = rec.get("company", "?")
            emp = (rec.get("company_facts") or {}).get("employees", "?")
            emp_range = (rec.get("company_facts") or {}).get("employee_range", "?")
            industry = (rec.get("company_facts") or {}).get("industry", "?")
            
            # What enrichment happened?
            enrich_steps = [e for e in log if e.get("step") == "enrich"]
            enrich_notes = [e.get("note", "") for e in enrich_steps]
            
            print(f"\n  {count}. {company} ({domain})")
            print(f"     Industry: {industry}")
            print(f"     Employees: {emp} ({emp_range})")
            print(f"     ICP flags: {icp_flags or 'none'}")
            print(f"     Enrichment log:")
            for note in enrich_notes:
                print(f"       - {note}")
            
            # Check if people-count was run
            pc_notes = [n for n in notes if "people-count" in n]
            if pc_notes:
                print(f"     People-count: {pc_notes}")
            else:
                print(f"     People-count: not run")
    
    print(f"\n\nTotal: {count}")
    
    # Also check: what about the 46 ICP-blocked?
    print(f"\n{'=' * 70}")
    print("THE 46 ICP-BLOCKED RECORDS: BREAKDOWN")
    print("=" * 70)
    
    geo_only = 0
    size_only = 0
    both = 0
    
    for rec in active:
        if rec.get("contacts") or rec.get("excluded"):
            continue
        
        log = rec.get("log", [])
        notes = [e.get("note", "") for e in log]
        has_people_zero = any("people-count: 0" in n for n in notes)
        
        if has_people_zero:
            continue  # these are the 39 unstaffed
        
        icp_notes = [n for e in log if e.get("step") == "icp" 
                     for n in [e.get("note", "")]]
        
        has_geo = any("geo outside" in n for n in icp_notes)
        has_size = any("under the client minimum" in n for n in icp_notes)
        
        if has_geo and has_size:
            both += 1
        elif has_geo:
            geo_only += 1
        elif has_size:
            size_only += 1
    
    print(f"\n  Geo outside markets only: {geo_only}")
    print(f"  Size under minimum only: {size_only}")
    print(f"  Both geo AND size: {both}")
    print(f"  Total ICP-blocked: {geo_only + size_only + both}")

if __name__ == "__main__":
    main()
