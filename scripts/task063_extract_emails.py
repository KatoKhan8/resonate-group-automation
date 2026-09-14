#!/usr/bin/env python3
"""TASK-063: Extract the five email steps for human reading.

Reads from work/queue.jsonl through src/store.py (the only safe path).
No provider call. No write to work/. Read-only.
"""
import sys
import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import store, claims

EMAIL_KEYS = ["em1", "em2", "em3", "em4", "em5"]


def sanitise_company(domain):
    """A readable label from the domain, no real company name."""
    return domain.replace(".com", "").replace(".ie", "").replace(".dk", "")\
                 .replace("-", " ").title()


def sanitise_name(contact_key):
    """First name only, from the contact key."""
    parts = contact_key.split("-")
    return parts[0].title() if parts else "?"


def extract(rec, contact_key):
    """Extract the five email steps for one contact."""
    cadence = (rec.get("cadence") or {}).get(contact_key) or {}
    contact = None
    for c in rec.get("contacts") or []:
        if c.get("key") == contact_key:
            contact = c
            break
    contact = contact or {}

    result = {
        "record_id": rec.get("id"),
        "contact_key": contact_key,
        "domain": rec.get("domain", "?"),
        "title": contact.get("title", "?"),
        "persona": contact.get("persona", "?"),
        "angle": contact.get("angle", "?"),
        "verdict": contact.get("verdict", "?"),
        "prior_contact": contact.get("prior_contact", False),
        "company_facts": rec.get("company_facts") or {},
        "steps": {},
    }

    for key in EMAIL_KEYS:
        step = cadence.get(key) or {}
        result["steps"][key] = {
            "subject": step.get("subject", "(no subject)"),
            "body": step.get("body", "(no body)"),
            "generated": step.get("generated", False),
            "has_approval": bool(step.get("approval")),
            "channel": step.get("channel", "?"),
        }

    return result


def check_claims(rec, contact_key):
    """Run claims.check on each step and report findings."""
    cadence = (rec.get("cadence") or {}).get(contact_key) or {}
    contact = None
    for c in rec.get("contacts") or []:
        if c.get("key") == contact_key:
            contact = c
            break
    contact = contact or {}

    findings = {}
    for key in EMAIL_KEYS:
        step = cadence.get(key) or {}
        text = f"{step.get('subject', '')} {step.get('body', '')}"
        problems = claims.check(text, rec, contact) or []
        if problems:
            findings[key] = problems
    return findings


def main():
    recs = store.load()

    # Find all records with all five email steps
    complete = []
    for rec in recs:
        for contact in rec.get("contacts") or []:
            key = contact.get("key")
            cadence = (rec.get("cadence") or {}).get(key) or {}
            if all(k in cadence for k in EMAIL_KEYS):
                complete.append((rec, key))

    print(f"# TASK-063: FIVE-STEP EMAIL READ")
    print(f"# Total records with all 5 email steps: {len(complete)}")
    print(f"# Reading the first 10 for human review")
    print()

    for i, (rec, ck) in enumerate(complete[:10]):
        data = extract(rec, ck)
        claim_findings = check_claims(rec, ck)

        print("=" * 78)
        print(f"RECORD {i+1}: {data['record_id']} / {ck}")
        print(f"  Domain: {data['domain']}")
        print(f"  Title: {data['title']}")
        print(f"  Persona: {data['persona']}")
        print(f"  Angle: {data['angle']}")
        print(f"  Verdict: {data['verdict']}")
        print(f"  Prior contact: {data['prior_contact']}")
        facts = data['company_facts']
        if facts:
            print(f"  Company: {facts.get('name', '?')}")
            print(f"  Industry: {facts.get('industry', '?')}")
            print(f"  Employees: {facts.get('employees', '?')}")
        print()

        for key in EMAIL_KEYS:
            step = data['steps'][key]
            print(f"  --- {key} (generated={step['generated']}, "
                  f"approved={step['has_approval']}) ---")
            print(f"  Subject: {step['subject']}")
            print(f"  Body:")
            for line in (step['body'] or '').splitlines():
                print(f"    {line}")
            if key in claim_findings:
                print(f"  *** CLAIMS ISSUES:")
                for p in claim_findings[key]:
                    print(f"    - {p.get('why', '?')}: {p.get('phrase', '?')}")
            print()

        print()


if __name__ == "__main__":
    main()
