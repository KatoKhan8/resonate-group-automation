"""
TASK-140: Deep analysis - ICP flags, state, evidenced vs inferred dimensions.
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

    print(f"=== DEEP ANALYSIS: {len(eligible)} eligible contacts ===\n")

    # 1. ICP flags vs eligibility
    print("--- ICP FLAGS ON ELIGIBLE CONTACTS ---")
    flagged = 0
    under_min = 0
    geo_outside = 0
    no_flags = 0
    for r, c in eligible:
        flags = r.get("company_facts", {}).get("icp_flags", [])
        if not flags:
            no_flags += 1
        else:
            flagged += 1
            for f in flags:
                if "under the client minimum" in f:
                    under_min += 1
                if "geo outside" in f:
                    geo_outside += 1
    print(f"  No ICP flags: {no_flags}")
    print(f"  Has ICP flags: {flagged}")
    print(f"    Under client minimum (headcount): {under_min}")
    print(f"    Geo outside client markets: {geo_outside}")
    print()

    # 2. State x ICP flags
    print("--- STATE x ICP FLAGGED ---")
    state_flag = defaultdict(lambda: Counter())
    for r, c in eligible:
        flags = r.get("company_facts", {}).get("icp_flags", [])
        has_flag = "flagged" if flags else "clean"
        state_flag[r.get("state", "?")][has_flag] += 1
    for state in sorted(state_flag.keys()):
        print(f"  {state}: {dict(state_flag[state])}")
    print()

    # 3. Headcount signal vs ICP flags
    print("--- HEADCOUNT SIGNAL vs ICP FLAG ---")
    hs_vs_flag = defaultdict(lambda: Counter())
    for r, c in eligible:
        flags = r.get("company_facts", {}).get("icp_flags", [])
        has_flag = "flagged" if flags else "clean"
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
        hs_vs_flag[bucket][has_flag] += 1
    for bucket in ["<20", "20-49", "50-199", "200+", "(null)"]:
        if hs_vs_flag[bucket]:
            print(f"  {bucket}: {dict(hs_vs_flag[bucket])}")
    print()

    # 4. Angle x Persona
    print("--- ANGLE x PERSONA ---")
    ap = Counter()
    for r, c in eligible:
        a = c.get("angle") or "(null)"
        p = c.get("persona") or "(null)"
        ap[(a, p)] += 1
    for (a, p), count in ap.most_common():
        print(f"  {a} x {p}: {count}")
    print()

    # 5. Title role family classification
    print("--- TITLE ROLE FAMILY ---")
    role_families = Counter()
    for r, c in eligible:
        title = (c.get("title") or "").lower().strip()
        if any(x in title for x in ["ceo", "chief executive", "founder", "co-founder", "owner", "president"]):
            family = "CEO/Founder"
        elif any(x in title for x in ["coo", "chief operating", "head of production", "operations"]):
            family = "COO/Ops"
        elif any(x in title for x in ["cfo", "chief financial", "head of finance", "finance"]):
            family = "CFO/Finance"
        elif any(x in title for x in ["design director", "creative director"]):
            family = "Creative Director"
        elif any(x in title for x in ["managing director"]):
            family = "Managing Director"
        else:
            family = f"Other ({c.get('title', '?')})"
        role_families[family] += 1
    for fam, count in role_families.most_common():
        print(f"  {fam}: {count}")
    print()

    # 6. Geography: US vs non-US
    print("--- GEOGRAPHY: US vs NON-US ---")
    geo_split = Counter()
    for r, c in eligible:
        offices = r.get("company_facts", {}).get("offices", [])
        countries = set()
        for o in offices:
            parts = [p.strip() for p in o.split(",")]
            if parts:
                countries.add(parts[-1].strip())
        if "US" in countries:
            geo_split["US"] += 1
        else:
            geo_split["Non-US"] += 1
    for g, count in geo_split.most_common():
        print(f"  {g}: {count}")
    print()

    # 7. Non-US breakdown
    print("--- NON-US COUNTRIES ---")
    non_us = Counter()
    for r, c in eligible:
        offices = r.get("company_facts", {}).get("offices", [])
        countries = set()
        for o in offices:
            parts = [p.strip() for p in o.split(",")]
            if parts:
                countries.add(parts[-1].strip())
        if "US" not in countries:
            for co in countries:
                non_us[co] += 1
    for co, count in non_us.most_common():
        print(f"  {co}: {count}")
    print()

    # 8. Industry sub-categories
    print("--- INDUSTRY SUB-CATEGORIES ---")
    ind_counter = Counter()
    for r, c in eligible:
        ind = r.get("company_facts", {}).get("industry", "(null)")
        ind_counter[ind] += 1
    for ind, count in ind_counter.most_common():
        print(f"  {ind}: {count}")
    print()

    # 9. Research outcome: what evidence exists per record
    print("--- RESEARCH EVIDENCE ---")
    research_counts = Counter()
    for r, c in eligible:
        research = r.get("research", [])
        n = len(research)
        research_counts[n] += 1
    for n, count in sorted(research_counts.items()):
        print(f"  {n} research items: {count} records")
    print()

    # 10. Evidence quality from research
    print("--- RESEARCH QUALITY ---")
    quality_counter = Counter()
    for r, c in eligible:
        research = r.get("research", [])
        qualities = set()
        for item in research:
            q = item.get("quality", "unknown")
            qualities.add(q)
        quality_counter[", ".join(sorted(qualities))] += 1
    for q, count in quality_counter.most_common():
        print(f"  {q}: {count}")
    print()

    # 11. What does the record's diagnosis/hook/sizing contain?
    print("--- DIAGNOSIS / HOOK / SIZING ---")
    diag_present = sum(1 for r, c in eligible if r.get("diagnosis"))
    hook_present = sum(1 for r, c in eligible if r.get("hook"))
    sizing_present = sum(1 for r, c in eligible if r.get("sizing"))
    print(f"  diagnosis present: {diag_present}/{len(eligible)}")
    print(f"  hook present: {hook_present}/{len(eligible)}")
    print(f"  sizing present: {sizing_present}/{len(eligible)}")
    print()

    # 12. Cross-tab: Angle x Company size bucket
    print("--- ANGLE x COMPANY SIZE ---")
    acs = Counter()
    for r, c in eligible:
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
        acs[(a, bucket)] += 1
    for (a, b), count in acs.most_common():
        print(f"  {a} x {b}: {count}")
    print()

    # 13. Cross-tab: Angle x Geography
    print("--- ANGLE x GEO ---")
    ag = Counter()
    for r, c in eligible:
        a = c.get("angle") or "(null)"
        offices = r.get("company_facts", {}).get("offices", [])
        countries = set()
        for o in offices:
            parts = [p.strip() for p in o.split(",")]
            if parts:
                countries.add(parts[-1].strip())
        geo = "US" if "US" in countries else "Non-US"
        ag[(a, geo)] += 1
    for (a, g), count in ag.most_common():
        print(f"  {a} x {g}: {count}")
    print()

    # 14. Cross-tab: Angle x ICP flagged
    print("--- ANGLE x ICP FLAG ---")
    ai = Counter()
    for r, c in eligible:
        a = c.get("angle") or "(null)"
        flags = r.get("company_facts", {}).get("icp_flags", [])
        has_flag = "flagged" if flags else "clean"
        ai[(a, has_flag)] += 1
    for (a, f), count in ai.most_common():
        print(f"  {a} x {f}: {count}")
    print()

    # 15. State x Angle
    print("--- STATE x ANGLE ---")
    sa = Counter()
    for r, c in eligible:
        s = r.get("state", "?")
        a = c.get("angle") or "(null)"
        sa[(s, a)] += 1
    for (s, a), count in sa.most_common():
        print(f"  {s} x {a}: {count}")
    print()

    # 16. How many records per contact (multi-contact companies)?
    print("--- CONTACTS PER RECORD ---")
    cpr = Counter()
    for r, c in eligible:
        n_elig = sum(1 for cc in r.get("contacts", []) if is_eligible_contact(cc))
        cpr[n_elig] += 1
    for n, count in sorted(cpr.items()):
        print(f"  {n} eligible contact(s): {count} records")
    print()

    # 17. What is the record-level state distribution?
    print("--- RECORD STATES (all 300) ---")
    all_states = Counter()
    for r in records:
        all_states[r.get("state", "?")] += 1
    for s, count in all_states.most_common():
        print(f"  {s}: {count}")
    print()

    # 18. Dropped records - why?
    print("--- DROP REASONS (all 300) ---")
    drop_counter = Counter()
    for r in records:
        dr = r.get("drop_reason")
        if dr:
            drop_counter[dr] += 1
    for d, count in drop_counter.most_common():
        print(f"  {d}: {count}")
    no_drop = sum(1 for r in records if not r.get("drop_reason"))
    print(f"  (no drop reason): {no_drop}")
    print()

    # 19. Records with eligible contacts - what states are they in?
    print("--- RECORD STATES FOR RECORDS WITH ELIGIBLE CONTACTS ---")
    eligible_record_ids = set(r["id"] for r, c in eligible)
    rec_state = Counter()
    for r in records:
        if r["id"] in eligible_record_ids:
            rec_state[r.get("state", "?")] += 1
    for s, count in rec_state.most_common():
        print(f"  {s}: {count}")
    print()

    # 20. Angle evidenced vs inferred
    print("--- ANGLE: EVIDENCED vs INFERRED ---")
    print("  Checking if angle is derived from title (inferred) or from research (evidenced)...")
    angle_sources = defaultdict(Counter)
    for r, c in eligible:
        angle = c.get("angle") or "(null)"
        research = r.get("research", [])
        has_research = len(research) > 0
        # Check if any research item mentions the angle
        angle_in_research = False
        for item in research:
            fact = item.get("fact", "").lower()
            if angle in fact and angle != "(null)":
                angle_in_research = True
                break
        if has_research and angle_in_research:
            angle_sources[angle]["evidenced_in_research"] += 1
        elif has_research:
            angle_sources[angle]["research_but_angle_not_mentioned"] += 1
        else:
            angle_sources[angle]["no_research"] += 1
    for angle, sources in sorted(angle_sources.items()):
        print(f"  Angle '{angle}':")
        for src, count in sources.most_common():
            print(f"    {src}: {count}")
    print()

if __name__ == "__main__":
    main()
