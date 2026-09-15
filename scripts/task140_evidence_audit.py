"""
TASK-140: Evidence audit - what research actually says per eligible contact.
"""

import json
from collections import Counter, defaultdict

SNAPSHOT = "work/queue.snapshot.jsonl"

def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def is_eligible_contact(c):
    return c.get("sendable") and c.get("reoon") and c["reoon"].get("is_safe_to_send")

def main():
    records = load_records()
    eligible = []
    for r in records:
        for c in r.get("contacts", []):
            if is_eligible_contact(c):
                eligible.append((r, c))

    # 1. Research evidence: what subject types exist
    print("=== RESEARCH SUBJECTS ===")
    subjects = Counter()
    for r, c in eligible:
        for item in r.get("research", []):
            subjects[item.get("subject", "?")] += 1
    for s, count in subjects.most_common():
        print(f"  {s}: {count}")
    print()

    # 2. Research provider types
    print("=== RESEARCH PROVIDERS ===")
    providers = Counter()
    for r, c in eligible:
        for item in r.get("research", []):
            providers[item.get("provider", "?")] += 1
    for p, count in providers.most_common():
        print(f"  {p}: {count}")
    print()

    # 3. What does a 'strong' quality research item look like?
    print("=== STRONG QUALITY RESEARCH - SAMPLE ===")
    strong_count = 0
    for r, c in eligible:
        for item in r.get("research", []):
            if item.get("quality") == "strong":
                strong_count += 1
                if strong_count <= 5:
                    print(f"  Record: {r['id']}, Subject: {item.get('subject')}, URL: {item.get('source_url', '')[:60]}")
                    print(f"    Fact preview: {item.get('fact', '')[:150]}...")
                    print()
    print(f"  Total strong items across eligible: {strong_count}")
    print()

    # 4. How many eligible contacts have at least one strong research item?
    print("=== RECORDS WITH STRONG RESEARCH ===")
    records_with_strong = 0
    for r, c in eligible:
        has_strong = any(item.get("quality") == "strong" for item in r.get("research", []))
        if has_strong:
            records_with_strong += 1
    print(f"  Records with at least one strong item: {records_with_strong}/{len(set(r['id'] for r, c in eligible))}")
    print()

    # 5. Cadence: what steps exist for eligible contacts
    print("=== CADENCE PRESENCE ===")
    has_cadence = 0
    for r, c in eligible:
        cadence = r.get("cadence", {})
        if cadence and c.get("key") in cadence:
            has_cadence += 1
    print(f"  Contacts with cadence: {has_cadence}/{len(eligible)}")
    print()

    # 6. Log step analysis - what has happened to these contacts
    print("=== LOG STEP TYPES FOR ELIGIBLE CONTACTS ===")
    step_types = Counter()
    for r, c in eligible:
        for entry in r.get("log", []):
            step_types[entry.get("step", "?")] += 1
    for s, count in step_types.most_common():
        print(f"  {s}: {count}")
    print()

    # 7. How many have had a LinkedIn note attempt?
    print("=== LINKEDIN NOTE STATUS ===")
    li_status = Counter()
    for r, c in eligible:
        li_steps = [e for e in r.get("log", []) if e.get("step") == "linkedin_note"]
        if not li_steps:
            li_status["no LinkedIn attempts"] += 1
        else:
            last = li_steps[-1]
            note = last.get("note", "")
            if "no note passed" in note:
                li_status["LinkedIn failed gates"] += 1
            else:
                li_status["LinkedIn note stored"] += 1
    for s, count in li_status.most_common():
        print(f"  {s}: {count}")
    print()

    # 8. Draft status
    print("=== DRAFT STATUS ===")
    draft_status = Counter()
    for r, c in eligible:
        draft_steps = [e for e in r.get("log", []) if e.get("step") == "draft"]
        if not draft_steps:
            draft_status["no draft attempts"] += 1
        else:
            last = draft_steps[-1]
            note = last.get("note", "")
            if "no draft passed" in note:
                draft_status["draft failed lint"] += 1
            else:
                draft_status["draft stored"] += 1
    for s, count in draft_status.most_common():
        print(f"  {s}: {count}")
    print()

    # 9. Approval status
    print("=== APPROVAL STATUS ===")
    approval_status = Counter()
    for r, c in eligible:
        approved_steps = [e for e in r.get("log", []) if e.get("step") == "approved"]
        if approved_steps:
            approval_status["has approvals"] += 1
        else:
            approval_status["no approvals"] += 1
    for s, count in approval_status.most_common():
        print(f"  {s}: {count}")
    print()

    # 10. For the 24 ICP-clean contacts, what is their full pipeline status?
    print("=== ICP-CLEAN: PIPELINE STATUS ===")
    clean_pipeline = Counter()
    for r, c in eligible:
        flags = r.get("company_facts", {}).get("icp_flags", [])
        if flags:
            continue
        state = r.get("state", "?")
        approved_steps = [e for e in r.get("log", []) if e.get("step") == "approved"]
        has_approval = len(approved_steps) > 0
        if has_approval:
            clean_pipeline[f"{state} + approved"] += 1
        else:
            clean_pipeline[f"{state} + not approved"] += 1
    for s, count in clean_pipeline.most_common():
        print(f"  {s}: {count}")
    print()

if __name__ == "__main__":
    main()
