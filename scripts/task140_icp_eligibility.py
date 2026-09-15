"""
TASK-140: ICP eligibility check - are flagged contacts actually campaign-ready?
Also: what does 'held' state mean?
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

    # 1. Check ICP log entries for eligible records
    print("=== ICP LOG ENTRIES FOR ELIGIBLE CONTACTS ===\n")

    eligible_records = set()
    for r in records:
        for c in r.get("contacts", []):
            if is_eligible_contact(c):
                eligible_records.add(r["id"])

    icp_notes = Counter()
    for r in records:
        if r["id"] not in eligible_records:
            continue
        for entry in r.get("log", []):
            if entry.get("step") == "icp":
                note = entry.get("note", "")
                icp_notes[note] += 1

    print("ICP log notes for records with eligible contacts:")
    for note, count in icp_notes.most_common():
        print(f"  {note!r}: {count}")
    print()

    # 2. What does 'held' mean? Check log entries for held records
    print("=== HELD RECORDS - LOG ENTRIES ===\n")
    for r in records:
        if r.get("state") != "held":
            continue
        has_eligible = any(is_eligible_contact(c) for c in r.get("contacts", []))
        if not has_eligible:
            continue
        print(f"  Record: {r['id']} ({r.get('company', '?')})")
        print(f"  ICP flags: {r.get('company_facts', {}).get('icp_flags', [])}")
        print(f"  Employees: {r.get('company_facts', {}).get('employees')}")
        print(f"  Headcount signal: {r.get('company_facts', {}).get('headcount_signal')}")
        # Last 3 log entries
        for entry in r.get("log", [])[-5:]:
            print(f"    {entry.get('step')}: {entry.get('note', '')[:100]}")
        print()

    # 3. Truly ICP-clean eligible contacts
    print("=== ICP-CLEAN ELIGIBLE CONTACTS ===\n")
    clean_eligible = []
    flagged_eligible = []
    for r in records:
        flags = r.get("company_facts", {}).get("icp_flags", [])
        for c in r.get("contacts", []):
            if is_eligible_contact(c):
                if flags:
                    flagged_eligible.append((r, c))
                else:
                    clean_eligible.append((r, c))

    print(f"ICP-clean eligible: {len(clean_eligible)}")
    print(f"ICP-flagged eligible: {len(flagged_eligible)}")
    print()

    # 4. Dimensions for clean vs flagged
    print("--- CLEAN: Angle distribution ---")
    clean_angles = Counter()
    for r, c in clean_eligible:
        clean_angles[c.get("angle") or "(null)"] += 1
    for a, count in clean_angles.most_common():
        print(f"  {a}: {count}")
    print()

    print("--- FLAGGED: Angle distribution ---")
    flagged_angles = Counter()
    for r, c in flagged_eligible:
        flagged_angles[c.get("angle") or "(null)"] += 1
    for a, count in flagged_angles.most_common():
        print(f"  {a}: {count}")
    print()

    print("--- CLEAN: Company size ---")
    clean_sizes = Counter()
    for r, c in clean_eligible:
        hs = r.get("company_facts", {}).get("headcount_signal")
        if hs is not None:
            if hs < 20:
                clean_sizes["<20"] += 1
            elif hs < 50:
                clean_sizes["20-49"] += 1
            elif hs < 200:
                clean_sizes["50-199"] += 1
            else:
                clean_sizes["200+"] += 1
    for s, count in sorted(clean_sizes.items()):
        print(f"  {s}: {count}")
    print()

    print("--- FLAGGED: Company size ---")
    flagged_sizes = Counter()
    for r, c in flagged_eligible:
        hs = r.get("company_facts", {}).get("headcount_signal")
        if hs is not None:
            if hs < 20:
                flagged_sizes["<20"] += 1
            elif hs < 50:
                flagged_sizes["20-49"] += 1
            elif hs < 200:
                flagged_sizes["50-199"] += 1
            else:
                flagged_sizes["200+"] += 1
    for s, count in sorted(flagged_sizes.items()):
        print(f"  {s}: {count}")
    print()

    print("--- CLEAN: Geography ---")
    clean_geo = Counter()
    for r, c in clean_eligible:
        offices = r.get("company_facts", {}).get("offices", [])
        countries = set()
        for o in offices:
            parts = [p.strip() for p in o.split(",")]
            if parts:
                countries.add(parts[-1].strip())
        if "US" in countries:
            clean_geo["US"] += 1
        else:
            clean_geo["Non-US"] += 1
    for g, count in clean_geo.most_common():
        print(f"  {g}: {count}")
    print()

    print("--- FLAGGED: Geography ---")
    flagged_geo = Counter()
    for r, c in flagged_eligible:
        offices = r.get("company_facts", {}).get("offices", [])
        countries = set()
        for o in offices:
            parts = [p.strip() for p in o.split(",")]
            if parts:
                countries.add(parts[-1].strip())
        if "US" in countries:
            flagged_geo["US"] += 1
        else:
            flagged_geo["Non-US"] += 1
    for g, count in flagged_geo.most_common():
        print(f"  {g}: {count}")
    print()

    # 5. Cross-tab for CLEAN contacts: Angle x Size
    print("=== CLEAN CONTACTS: ANGLE x SIZE ===")
    clean_as = Counter()
    for r, c in clean_eligible:
        a = c.get("angle") or "(null)"
        hs = r.get("company_facts", {}).get("headcount_signal")
        if hs is not None:
            if hs < 20:
                bucket = "<20"
            elif hs < 50:
                bucket = "20-49"
            elif hs < 200:
                bucket = "50-199"
            else:
                bucket = "200+"
        else:
            bucket = "(null)"
        clean_as[(a, bucket)] += 1
    for (a, b), count in clean_as.most_common():
        print(f"  {a} x {b}: {count}")
    print()

    # 6. Cross-tab for CLEAN contacts: Angle x Industry
    print("=== CLEAN CONTACTS: ANGLE x INDUSTRY ===")
    clean_ai = Counter()
    for r, c in clean_eligible:
        a = c.get("angle") or "(null)"
        ind = r.get("company_facts", {}).get("industry", "(null)")
        clean_ai[(a, ind)] += 1
    for (a, ind), count in clean_ai.most_common():
        print(f"  {a} x {ind}: {count}")
    print()

    # 7. What does the context/signal field look like for non-dropped records?
    print("=== CONTEXT/SIGNAL FOR ALL NON-DROPPED RECORDS ===")
    ctx_counter = Counter()
    sig_counter = Counter()
    for r in records:
        if r.get("state") == "dropped":
            continue
        ctx = r.get("context", "")
        sig = r.get("signal", "")
        ctx_counter["present" if ctx else "absent"] += 1
        sig_counter["present" if sig else "absent"] += 1
    print(f"  context: {dict(ctx_counter)}")
    print(f"  signal: {dict(sig_counter)}")
    print()

    # 8. Check the 'held' state - is it a deliberate hold or a pipeline stage?
    print("=== ALL HELD RECORDS (not just eligible) ===")
    held_reasons = Counter()
    for r in records:
        if r.get("state") != "held":
            continue
        # Check log for hold reason
        for entry in r.get("log", []):
            if "hold" in entry.get("step", "").lower() or "hold" in entry.get("note", "").lower():
                held_reasons[entry.get("note", "")[:80]] += 1
    for reason, count in held_reasons.most_common(10):
        print(f"  {reason}: {count}")
    print()

    # 9. What ICP flags exist across ALL non-dropped records?
    print("=== ICP FLAGS ACROSS ALL NON-DROPPED RECORDS ===")
    all_flags = Counter()
    for r in records:
        if r.get("state") == "dropped":
            continue
        flags = r.get("company_facts", {}).get("icp_flags", [])
        if flags:
            for f in flags:
                all_flags[f] += 1
        else:
            all_flags["(no flags)"] += 1
    for f, count in all_flags.most_common():
        print(f"  {f}: {count}")
    print()

if __name__ == "__main__":
    main()
