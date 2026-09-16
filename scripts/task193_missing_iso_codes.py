#!/usr/bin/env python3
"""Check which ISO codes appear in office data but are missing from ISO_TO_NAME."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import icpstructural

SNAPSHOT = Path(__file__).parent.parent / "work" / "queue.snapshot.jsonl"


def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # Load records
    records = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    
    # Extract all ISO codes from office lines
    iso_counts = {}
    for rec in records:
        offices = (rec.get("company_facts") or {}).get("offices") or []
        for line in offices:
            token = str(line).strip().rstrip(".").split(",")[-1].strip().upper()
            if token and len(token) == 2:  # Looks like an ISO code
                iso_counts[token] = iso_counts.get(token, 0) + 1
    
    print("ISO codes appearing in office data:")
    print()
    
    missing = []
    for iso, count in sorted(iso_counts.items(), key=lambda x: -x[1]):
        in_map = iso in icpstructural.ISO_TO_NAME
        status = "✓ in ISO_TO_NAME" if in_map else "✗ MISSING"
        print(f"  {iso}: {count} records [{status}]")
        if not in_map:
            missing.append((iso, count))
    
    print()
    print(f"Total ISO codes found: {len(iso_counts)}")
    print(f"Missing from ISO_TO_NAME: {len(missing)}")
    print()
    
    if missing:
        print("Missing ISO codes and their record counts:")
        for iso, count in sorted(missing, key=lambda x: -x[1]):
            print(f"  {iso}: {count} records")
        print()
        
        # Count records affected
        affected = 0
        for rec in records:
            offices = (rec.get("company_facts") or {}).get("offices") or []
            for line in offices:
                token = str(line).strip().rstrip(".").split(",")[-1].strip().upper()
                if token in [iso for iso, _ in missing]:
                    affected += 1
                    break
        
        print(f"Records with at least one office using a missing ISO code: {affected}")


if __name__ == "__main__":
    main()
