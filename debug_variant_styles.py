#!/usr/bin/env python3
"""Debug: print raw variant data to see what styles are actually being used."""
import json
import sys
from src import variantgen, llm, cadencelibrary

FIXTURE_RECORD = {
    "id": "test-debug",
    "lane": "domains",
    "client": "productive",
    "company": "Acme Agency",
    "domain": "acme.test",
    "context": "",
    "signal": "",
    "company_facts": {
        "name": "Acme Agency",
        "industry": "Marketing & Advertising",
        "employees": 25,
        "employee_range": "11-50 employees",
        "research_outcome": "HTTP_SUCCESS",
    },
    "contacts": [{
        "name": "Anna Smith",
        "title": "Founder",
        "linkedin": "annasmith",
        "email": "anna@acme.test",
        "email_source": "provider",
        "persona": "economic_buyer",
        "angle": "founder",
        "verdict": "valid",
        "sendable": True,
        "primary": True,
        "key": "anna-smith",
    }],
    "diagnosis": {"died_on": None, "died_because": None, "failure_mode": None, "last_position": None},
    "hook": "Agencies your size rebuild utilisation reports by hand every Monday morning.",
    "sizing": {"employees": 25},
    "excluded": [],
    "cadence": {},
    "log": [],
    "events": [],
}

def main():
    model = llm.from_env()
    contact = FIXTURE_RECORD["contacts"][0]
    sequence = cadencelibrary.PRODUCTIVE_LI_HEAVY_V1

    result = variantgen.build_variant_set(
        FIXTURE_RECORD, contact, "linkedin", "li2",
        sequence=sequence, config=None,
        llm_ask=llm.ask, model=model)

    print("RAW VARIANT DATA:")
    print("=" * 80)
    for i, v in enumerate(result.get("variants", []), 1):
        print(f"\nVariant {i}:")
        print(f"  style: {v.get('style')}")
        print(f"  approach: {v.get('approach')}")
        body = v.get('body') or v.get('note') or v.get('subject') or ''
        print(f"  body: {body[:100] if body else '(empty)'}")

    print("\n\nMAPPING CHECK:")
    print("=" * 80)
    print("APPROACH_TO_STYLE for linkedin_message:")
    for approach, style in variantgen.APPROACH_TO_STYLE.get("linkedin_message", {}).items():
        print(f"  {approach:20s} -> {style}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
