"""
TASK-140: Cohort coherence analysis.
Measures distributions of candidate grouping dimensions across eligible contacts,
cross-tabs the densest, and proposes named cohorts.

Reads work/queue.snapshot.jsonl (read-only). Writes nothing to work/.
"""

import json
import sys
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

def get_eligible_contacts(records):
    """Return list of (record, contact) tuples for eligible contacts."""
    eligible = []
    for r in records:
        for c in r.get("contacts", []):
            if is_eligible_contact(c):
                eligible.append((r, c))
    return eligible

def extract_dimensions(eligible):
    """Extract candidate grouping dimensions for each eligible contact."""
    rows = []
    for r, c in eligible:
        cf = r.get("company_facts", {})
        row = {
            "record_id": r["id"],
            "contact_key": c.get("key", ""),
            "contact_name": c.get("name", ""),
            "client": r.get("client", ""),
            "company": r.get("company", ""),
            "domain": r.get("domain", ""),
            "industry": cf.get("industry", ""),
            "employee_range": cf.get("employee_range", ""),
            "employees": cf.get("employees"),
            "persona": c.get("persona", ""),
            "angle": c.get("angle", ""),
            "title": c.get("title", ""),
            "recovered_from": cf.get("recovered_from", {}).get("source_type", ""),
            "research_outcome": cf.get("research_outcome", ""),
            "icp_flags": cf.get("icp_flags", []),
            "signal": r.get("signal", ""),
            "context": r.get("context", ""),
            "state": r.get("state", ""),
            "offices": cf.get("offices", []),
            "revenue": cf.get("revenue", ""),
            "headcount_signal": cf.get("headcount_signal"),
        }
        rows.append(row)
    return rows

def distribution(rows, key):
    """Count distribution of a dimension, including nulls."""
    vals = Counter()
    nulls = 0
    for row in rows:
        v = row.get(key)
        if v is None or v == "" or v == []:
            nulls += 1
        elif isinstance(v, list):
            for item in v:
                vals[item] += 1
        else:
            vals[v] += 1
    return vals, nulls

def cross_tab(rows, key1, key2):
    """Cross-tabulate two dimensions."""
    ct = Counter()
    for row in rows:
        v1 = row.get(key1) or "(null)"
        v2 = row.get(key2) or "(null)"
        if isinstance(v1, list):
            v1 = ", ".join(v1) if v1 else "(null)"
        if isinstance(v2, list):
            v2 = ", ".join(v2) if v2 else "(null)"
        ct[(v1, v2)] += 1
    return ct

def main():
    records = load_records()
    eligible = get_eligible_contacts(records)
    rows = extract_dimensions(eligible)

    print(f"=== TASK-140 COHORT ANALYSIS ===")
    print(f"Total records: {len(records)}")
    print(f"Eligible contacts: {len(eligible)}")
    print()

    # 1. Distribution of each candidate dimension
    dimensions = [
        "client", "industry", "employee_range", "persona", "angle",
        "research_outcome", "state", "recovered_from", "signal"
    ]

    print("=== DIMENSION DISTRIBUTIONS ===\n")
    for dim in dimensions:
        vals, nulls = distribution(rows, dim)
        print(f"--- {dim} ---")
        print(f"  Distinct values: {len(vals)}, Nulls/empty: {nulls}/{len(rows)} ({100*nulls/len(rows):.1f}%)")
        for v, count in vals.most_common(20):
            print(f"  {v!r}: {count} ({100*count/len(rows):.1f}%)")
        print()

    # 2. Employee count distribution (numeric)
    print("--- employees (numeric) ---")
    emp_vals = [r["employees"] for r in rows if r["employees"] is not None]
    emp_nulls = len(rows) - len(emp_vals)
    print(f"  Non-null: {len(emp_vals)}, Nulls: {emp_nulls}")
    if emp_vals:
        import statistics
        print(f"  Min: {min(emp_vals)}, Max: {max(emp_vals)}, Median: {statistics.median(emp_vals):.0f}, Mean: {statistics.mean(emp_vals):.1f}")
        # Bucketize
        buckets = Counter()
        for e in emp_vals:
            if e < 20:
                buckets["<20"] += 1
            elif e < 50:
                buckets["20-49"] += 1
            elif e < 200:
                buckets["50-199"] += 1
            elif e < 500:
                buckets["200-499"] += 1
            elif e < 1000:
                buckets["500-999"] += 1
            else:
                buckets["1000+"] += 1
        for b in ["<20", "20-49", "50-199", "200-499", "500-999", "1000+"]:
            print(f"  {b}: {buckets.get(b, 0)}")
    print()

    # 3. Revenue distribution
    print("--- revenue ---")
    rev_vals = Counter()
    rev_nulls = 0
    for r in rows:
        rev = r.get("revenue", "")
        if not rev:
            rev_nulls += 1
        else:
            rev_vals[rev] += 1
    print(f"  Distinct values: {len(rev_vals)}, Nulls: {rev_nulls}")
    for v, count in rev_vals.most_common(15):
        print(f"  {v!r}: {count}")
    print()

    # 4. Cross-tabs of densest dimensions
    print("=== CROSS-TABS ===\n")

    # Industry x Persona
    print("--- industry x persona ---")
    ct = cross_tab(rows, "industry", "persona")
    for (ind, per), count in ct.most_common(30):
        print(f"  {ind!r} x {per!r}: {count}")
    print()

    # Industry x Angle
    print("--- industry x angle ---")
    ct = cross_tab(rows, "industry", "angle")
    for (ind, ang), count in ct.most_common(30):
        print(f"  {ind!r} x {ang!r}: {count}")
    print()

    # Employee range x Persona
    print("--- employee_range x persona ---")
    ct = cross_tab(rows, "employee_range", "persona")
    for (er, per), count in ct.most_common(30):
        print(f"  {er!r} x {per!r}: {count}")
    print()

    # Client x Persona
    print("--- client x persona ---")
    ct = cross_tab(rows, "client", "persona")
    for (cl, per), count in ct.most_common(30):
        print(f"  {cl!r} x {per!r}: {count}")
    print()

    # Client x Industry
    print("--- client x industry ---")
    ct = cross_tab(rows, "client", "industry")
    for (cl, ind), count in ct.most_common(30):
        print(f"  {cl!r} x {ind!r}: {count}")
    print()

    # Client x employee_range
    print("--- client x employee_range ---")
    ct = cross_tab(rows, "client", "employee_range")
    for (cl, er), count in ct.most_common(30):
        print(f"  {cl!r} x {er!r}: {count}")
    print()

    # 5. ICP flags analysis
    print("=== ICP FLAGS ===")
    icp_counter = Counter()
    for r in rows:
        flags = r.get("icp_flags", [])
        if flags:
            for f in flags:
                icp_counter[f] += 1
        else:
            icp_counter["(no flags)"] += 1
    for f, count in icp_counter.most_common(20):
        print(f"  {f!r}: {count}")
    print()

    # 6. Signal and context fields
    print("=== SIGNAL / CONTEXT ===")
    sig_vals, sig_nulls = distribution(rows, "signal")
    ctx_vals, ctx_nulls = distribution(rows, "context")
    print(f"  signal: {len(sig_vals)} distinct, {sig_nulls} nulls")
    for v, count in sig_vals.most_common(10):
        print(f"    {v!r}: {count}")
    print(f"  context: {len(ctx_vals)} distinct, {ctx_nulls} nulls")
    for v, count in ctx_vals.most_common(10):
        print(f"    {v!r}: {count}")
    print()

    # 7. Title analysis - what roles are present
    print("=== TITLES ===")
    titles = Counter()
    for r in rows:
        t = r.get("title", "")
        if t:
            titles[t] += 1
        else:
            titles["(null)"] += 1
    for t, count in titles.most_common(40):
        print(f"  {t!r}: {count}")
    print()

    # 8. Geography - office locations
    print("=== GEOGRAPHY (offices) ===")
    geo_counter = Counter()
    geo_nulls = 0
    for r in rows:
        offices = r.get("offices", [])
        if offices:
            for o in offices:
                # Extract country from office string (last part typically)
                parts = [p.strip() for p in o.split(",")]
                if parts:
                    country = parts[-1].strip()
                    geo_counter[country] += 1
        else:
            geo_nulls += 1
    print(f"  Records with offices: {len(rows) - geo_nulls}, without: {geo_nulls}")
    for g, count in geo_counter.most_common(20):
        print(f"  {g!r}: {count}")
    print()

    # 9. headcount_signal (from company_facts)
    print("=== HEADCOUNT SIGNAL ===")
    hs_vals = [r["headcount_signal"] for r in rows if r["headcount_signal"] is not None]
    hs_nulls = len(rows) - len(hs_vals)
    print(f"  Non-null: {len(hs_vals)}, Nulls: {hs_nulls}")
    if hs_vals:
        hs_buckets = Counter()
        for h in hs_vals:
            if h < 20:
                hs_buckets["<20"] += 1
            elif h < 50:
                hs_buckets["20-49"] += 1
            elif h < 200:
                hs_buckets["50-199"] += 1
            else:
                hs_buckets["200+"] += 1
        for b in ["<20", "20-49", "50-199", "200+"]:
            print(f"  {b}: {hs_buckets.get(b, 0)}")
    print()

    # 10. Per-client breakdown (the client is the most fundamental grouping)
    print("=== PER-CLIENT ELIGIBLE CONTACT COUNTS ===")
    client_counts = Counter()
    for r in rows:
        client_counts[r["client"]] += 1
    for cl, count in client_counts.most_common():
        print(f"  {cl}: {count}")
    print()

    # 11. Persona x Title - what titles map to what personas
    print("=== PERSONA x TITLE (sample) ===")
    persona_titles = defaultdict(Counter)
    for r in rows:
        p = r.get("persona") or "(null)"
        t = r.get("title") or "(null)"
        persona_titles[p][t] += 1
    for p in sorted(persona_titles.keys()):
        print(f"  Persona: {p}")
        for t, count in persona_titles[p].most_common(10):
            print(f"    {t}: {count}")
    print()

    # 12. Angle distribution detail
    print("=== ANGLE DETAIL ===")
    angle_vals, angle_nulls = distribution(rows, "angle")
    print(f"  Distinct: {len(angle_vals)}, Nulls: {angle_nulls}")
    for a, count in angle_vals.most_common():
        print(f"  {a!r}: {count}")
    print()

    # 13. Company size buckets by client
    print("=== COMPANY SIZE BY CLIENT ===")
    client_size = defaultdict(lambda: Counter())
    for r in rows:
        emp = r.get("employees")
        if emp is not None:
            if emp < 20:
                bucket = "<20"
            elif emp < 50:
                bucket = "20-49"
            elif emp < 200:
                bucket = "50-199"
            elif emp < 500:
                bucket = "200-499"
            else:
                bucket = "500+"
        else:
            bucket = "(unknown)"
        client_size[r["client"]][bucket] += 1
    for cl in sorted(client_size.keys()):
        print(f"  {cl}:")
        for b in ["<20", "20-49", "50-199", "200-499", "500+", "(unknown)"]:
            if client_size[cl][b]:
                print(f"    {b}: {client_size[cl][b]}")
    print()

    # 14. Industry by client
    print("=== INDUSTRY BY CLIENT ===")
    client_ind = defaultdict(Counter)
    for r in rows:
        ind = r.get("industry") or "(null)"
        client_ind[r["client"]][ind] += 1
    for cl in sorted(client_ind.keys()):
        print(f"  {cl}:")
        for ind, count in client_ind[cl].most_common(10):
            print(f"    {ind}: {count}")
    print()

if __name__ == "__main__":
    main()
