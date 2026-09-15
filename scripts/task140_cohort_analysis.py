"""
TASK-140: Cohort coherence analysis against work/queue.snapshot.jsonl

Measures distributions of candidate grouping dimensions across eligible
contacts, cross-tabs the densest dimensions, classifies evidenced vs
inferred dimensions, and proposes named cohorts.

Eligible = contacts with a LinkedIn profile on non-dropped records.
This mirrors the definition from COHORT-HEADROOM-2026-09-15.md (277 on
the live queue minus 29 prior outreach = 248), applied to the snapshot.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SNAPSHOT = Path("work/queue.snapshot.jsonl")
STAMP = Path("work/queue.snapshot.STAMP")


def load_records():
    with open(SNAPSHOT, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_stamp():
    return STAMP.read_text(encoding="utf-8").strip()


def get_eligible_contacts(records):
    """Contacts with a LinkedIn profile on non-dropped records."""
    eligible = []
    for r in records:
        if r["state"] == "dropped":
            continue
        for c in r.get("contacts", []):
            if c.get("linkedin"):
                eligible.append((r, c))
    return eligible


def extract_dimensions(records, eligible):
    """Extract all candidate grouping dimensions for each eligible contact."""
    rows = []
    for r, c in eligible:
        q = r.get("qualification", {})
        seg = q.get("segment", {})
        verdict = q.get("verdict", {})
        messaging = q.get("messaging", {})
        persona_plan = q.get("persona_plan", {})
        cf = r.get("company_facts", {})

        row = {
            "record_id": r["id"],
            "contact_key": c.get("key", ""),
            "contact_name": c.get("name", ""),
            "client": r.get("client", ""),
            "company": r.get("company", ""),
            "domain": r.get("domain", ""),
            "record_state": r["state"],
            "signal": r.get("signal", ""),
            "lane": r.get("lane", ""),

            # Contact-level
            "persona": c.get("persona"),
            "angle": c.get("angle"),
            "title": c.get("title", ""),
            "sendable": c.get("sendable", False),
            "email_verdict": c.get("verdict"),

            # Company-level from qualification
            "vertical": seg.get("vertical"),
            "subvertical": seg.get("subvertical"),
            "business_model": seg.get("business_model"),
            "company_maturity": seg.get("company_maturity"),
            "delivery_model": seg.get("delivery_model"),
            "employee_band": seg.get("employee_band"),
            "employees": seg.get("employees"),
            "country": seg.get("country"),
            "country_code": seg.get("country_code"),
            "region": seg.get("region"),
            "region_confidence": seg.get("region_confidence"),
            "city": seg.get("city"),
            "timezone": seg.get("timezone"),
            "distributed": seg.get("distributed"),
            "office_count": seg.get("office_count"),

            # ICP
            "icp_tier": verdict.get("icp_tier"),
            "icp_status": verdict.get("icp_status"),
            "icp_score": verdict.get("icp_score"),
            "icp_grade": q.get("icp_grade"),
            "icp_confidence": q.get("icp_confidence"),

            # Messaging
            "recommended_angles": tuple(messaging.get("recommended_angles", [])),
            "relevant_pain_categories": tuple(messaging.get("relevant_pain_categories", [])),

            # Persona plan
            "persona_strategy": persona_plan.get("strategy"),

            # Company facts (direct)
            "industry": cf.get("industry"),
            "employee_range": cf.get("employee_range"),
            "revenue": cf.get("revenue"),
            "headcount_signal": cf.get("headcount_signal"),

            # Signal from record
            "context": r.get("context", ""),
        }
        rows.append(row)
    return rows


def distribution(values, label):
    """Print distribution of a dimension."""
    counter = Counter(v for v in values if v is not None and v != "" and v != ())
    null_count = sum(1 for v in values if v is None or v == "" or v == ())
    distinct = len(counter)
    print(f"\n{'='*60}")
    print(f"DIMENSION: {label}")
    print(f"  Distinct values: {distinct}")
    print(f"  Null/empty: {null_count}/{len(values)} ({100*null_count/len(values):.1f}%)")
    print(f"  Coverage: {100*(len(values)-null_count)/len(values):.1f}%")
    print(f"  Distribution:")
    for val, count in counter.most_common(20):
        print(f"    {str(val):50s} {count:4d} ({100*count/len(values):.1f}%)")
    return counter, null_count


def cross_tab(rows, dim1, dim2, min_cell=3):
    """Print cross-tabulation of two dimensions."""
    c1 = Counter()
    c2 = Counter()
    joint = Counter()
    for r in rows:
        v1 = r.get(dim1)
        v2 = r.get(dim2)
        if v1 is None or v1 == "" or v1 == ():
            v1 = "(null)"
        if v2 is None or v2 == "" or v2 == ():
            v2 = "(null)"
        if isinstance(v1, (list, tuple)):
            v1 = ",".join(sorted(v1)) if v1 else "(null)"
        if isinstance(v2, (list, tuple)):
            v2 = ",".join(sorted(v2)) if v2 else "(null)"
        c1[v1] += 1
        c2[v2] += 1
        joint[(v1, v2)] += 1

    print(f"\n{'='*60}")
    print(f"CROSS-TAB: {dim1} x {dim2}")
    print(f"  Top combinations (>= {min_cell} contacts):")

    significant = [(k, v) for k, v in joint.most_common(50) if v >= min_cell]
    for (v1, v2), count in significant:
        print(f"    {dim1}={str(v1):35s} {dim2}={str(v2):30s} {count:4d}")

    return joint


def main():
    stamp = load_stamp()
    print(f"Snapshot stamp: {stamp}")
    print()

    records = load_records()
    print(f"Total records: {len(records)}")

    eligible = get_eligible_contacts(records)
    print(f"Eligible contacts (LinkedIn profile, non-dropped record): {len(eligible)}")

    # Also count sendable eligible
    sendable_eligible = [(r, c) for r, c in eligible if c.get("sendable")]
    print(f"  Of which sendable (verified email): {len(sendable_eligible)}")

    rows = extract_dimensions(records, eligible)

    # =========================================================================
    # 1. DISTRIBUTIONS OF CANDIDATE DIMENSIONS
    # =========================================================================
    print("\n" + "#"*60)
    print("# SECTION 1: DIMENSION DISTRIBUTIONS")
    print("#"*60)

    dimensions = [
        ("persona", "Persona (contact role)"),
        ("angle", "Angle (contact approach angle)"),
        ("vertical", "Vertical (company segment)"),
        ("subvertical", "Subvertical"),
        ("business_model", "Business model"),
        ("company_maturity", "Company maturity"),
        ("employee_band", "Employee band"),
        ("employee_range", "Employee range (raw)"),
        ("region", "Region"),
        ("country_code", "Country code"),
        ("city", "City"),
        ("timezone", "Timezone"),
        ("distributed", "Distributed company"),
        ("office_count", "Office count"),
        ("icp_tier", "ICP tier"),
        ("icp_status", "ICP status"),
        ("icp_confidence", "ICP confidence"),
        ("icp_grade", "ICP grade"),
        ("persona_strategy", "Persona strategy (company size-based)"),
        ("recommended_angles", "Recommended angles (tuple)"),
        ("relevant_pain_categories", "Relevant pain categories (tuple)"),
        ("industry", "Industry (raw from company facts)"),
        ("record_state", "Record state"),
        ("signal", "Signal (free text)"),
        ("lane", "Lane"),
        ("delivery_model", "Delivery model"),
    ]

    dim_results = {}
    for dim_key, dim_label in dimensions:
        values = [r.get(dim_key) for r in rows]
        counter, null_count = distribution(values, dim_label)
        dim_results[dim_key] = (counter, null_count, len(values))

    # =========================================================================
    # 2. CROSS-TABS OF DENSEST DIMENSIONS
    # =========================================================================
    print("\n" + "#"*60)
    print("# SECTION 2: CROSS-TABS")
    print("#"*60)

    # Identify the densest dimensions (highest coverage, most distinct meaningful values)
    cross_tabs = [
        ("vertical", "persona"),
        ("vertical", "employee_band"),
        ("vertical", "persona_strategy"),
        ("vertical", "region"),
        ("persona", "persona_strategy"),
        ("persona", "employee_band"),
        ("persona_strategy", "employee_band"),
        ("persona_strategy", "region"),
        ("icp_tier", "vertical"),
        ("icp_tier", "employee_band"),
        ("recommended_angles", "vertical"),
        ("relevant_pain_categories", "vertical"),
        ("relevant_pain_categories", "persona"),
        ("business_model", "vertical"),
        ("vertical", "city"),
    ]

    for d1, d2 in cross_tabs:
        cross_tab(rows, d1, d2, min_cell=2)

    # =========================================================================
    # 3. EVIDENCED vs INFERRED CLASSIFICATION
    # =========================================================================
    print("\n" + "#"*60)
    print("# SECTION 3: EVIDENCED vs INFERRED DIMENSIONS")
    print("#"*60)

    classification = {
        "vertical": {
            "type": "INFERRED",
            "source": "Classification of company website text by qualify.py",
            "evidence_base": "Company website crawl (local_http) - text is evidenced, the vertical label is classified from it",
            "can_assert_in_copy": False,
            "note": "The website text is evidence; 'Creative / Branding Agency' is a classification of that text. Copy may reference what the company does (evidenced) but should not assert the vertical label itself.",
        },
        "subvertical": {
            "type": "INFERRED",
            "source": "Further classification from website text",
            "evidence_base": "82.7% UNKNOWN - not a grouping dimension",
            "can_assert_in_copy": False,
            "note": "Too sparse to use.",
        },
        "business_model": {
            "type": "INFERRED",
            "source": "Classified from website text and industry",
            "evidence_base": "Website text + LinkedIn industry",
            "can_assert_in_copy": False,
            "note": "Agency vs product is a structural classification, not something to assert in copy.",
        },
        "persona": {
            "type": "EVIDENCED",
            "source": "ContactOut person discovery matched against persona priority list",
            "evidence_base": "Title string matched to persona category by qualify.py persona_plan",
            "can_assert_in_copy": False,
            "note": "The TITLE is evidenced (from LinkedIn). The persona label (economic_buyer, operations, etc.) is a classification of the title. Copy may reference the title but not the persona label.",
        },
        "angle": {
            "type": "EVIDENCED",
            "source": "Derived from persona classification",
            "evidence_base": "Title -> persona -> angle mapping",
            "can_assert_in_copy": False,
            "note": "Same chain as persona. The angle is a classification.",
        },
        "employee_band": {
            "type": "EVIDENCED with caveats",
            "source": "company_facts.employees (from LinkedIn or client export) banded",
            "evidence_base": "LinkedIn headcount or client export. 7 conflicts and 64 range/value disagreements across 300 records (per PRODUCTION-SCALE-POLICY.md).",
            "can_assert_in_copy": False,
            "note": "The headcount number is from LinkedIn (evidenced) but contested. The band is derived. PRODUCTION-SCALE-POLICY.md says employee_range is 19% coverage and headcount is not safe as a cohort key on contested records.",
        },
        "region": {
            "type": "EVIDENCED",
            "source": "Derived from office address in company_facts.offices",
            "evidence_base": "Office address from website or LinkedIn. Country extracted by qualify.py.",
            "can_assert_in_copy": False,
            "note": "Geography is evidenced by the office address. Region is a classification of the country.",
        },
        "country_code": {
            "type": "EVIDENCED",
            "source": "Country extracted from office address",
            "evidence_base": "Office address from website or LinkedIn",
            "can_assert_in_copy": False,
            "note": "Where the address is present, country is evidenced. Where location_why says 'no usable location evidence', it is absent.",
        },
        "city": {
            "type": "EVIDENCED",
            "source": "City extracted from office address",
            "evidence_base": "Office address from website or LinkedIn",
            "can_assert_in_copy": False,
            "note": "Present where address parsing succeeded.",
        },
        "timezone": {
            "type": "EVIDENCED where present",
            "source": "Derived from city",
            "evidence_base": "City -> timezone mapping",
            "can_assert_in_copy": False,
            "note": "A guessed timezone is worse than a missing one (AGENTS.md).",
        },
        "icp_tier": {
            "type": "INFERRED",
            "source": "Score computed by qualify.py from multiple signals",
            "evidence_base": "Composite of vertical, headcount, geography, delivery complexity, etc.",
            "can_assert_in_copy": False,
            "note": "A score, not an observable fact. Useful for filtering, not for copy.",
        },
        "icp_confidence": {
            "type": "INFERRED",
            "source": "Confidence computed by qualify.py from evidence coverage",
            "evidence_base": "Meta-measurement about evidence quality",
            "can_assert_in_copy": False,
            "note": "About the evidence, not a fact about the company.",
        },
        "persona_strategy": {
            "type": "INFERRED",
            "source": "Determined by employee_band -> strategy mapping in qualify.py",
            "evidence_base": "Band classification -> strategy rule",
            "can_assert_in_copy": False,
            "note": "A rule-based classification from headcount. founder_led vs operations_led is a system decision, not an observable fact.",
        },
        "recommended_angles": {
            "type": "INFERRED",
            "source": "Determined by vertical + evidence signals in qualify.py",
            "evidence_base": "Vertical classification + signal matching",
            "can_assert_in_copy": False,
            "note": "The ANGLES are system recommendations. The underlying signals (delivery_complexity, resource_planning_need) are evidenced from website text.",
        },
        "relevant_pain_categories": {
            "type": "INFERRED",
            "source": "Determined by vertical + evidence signals in qualify.py",
            "evidence_base": "Same as recommended_angles",
            "can_assert_in_copy": False,
            "note": "Pain categories are system classifications. The signals that fired them are evidenced.",
        },
        "signal": {
            "type": "MIXED",
            "source": "Free-text field on the record",
            "evidence_base": "Varies per record - some are from website crawl, some from client input",
            "can_assert_in_copy": False,
            "note": "Must be read per-record. Not a uniform dimension.",
        },
        "industry": {
            "type": "EVIDENCED",
            "source": "LinkedIn industry field from company enrichment",
            "evidence_base": "LinkedIn company page",
            "can_assert_in_copy": False,
            "note": "LinkedIn's own classification of the company. Evidenced but not controlled by us.",
        },
    }

    for dim, info in classification.items():
        counter, null_count, total = dim_results.get(dim, (Counter(), 0, 0))
        coverage_pct = 100 * (total - null_count) / total if total else 0
        print(f"\n  {dim}:")
        print(f"    Type: {info['type']}")
        print(f"    Coverage: {total - null_count}/{total} ({coverage_pct:.1f}%)")
        print(f"    Source: {info['source']}")
        print(f"    Can assert in copy: {info['can_assert_in_copy']}")
        print(f"    Note: {info['note']}")

    # =========================================================================
    # 4. COHORT PROPOSAL
    # =========================================================================
    print("\n" + "#"*60)
    print("# SECTION 4: COHORT PROPOSAL")
    print("#"*60)

    # Build cohort candidates from the data
    # Primary dimension: vertical (highest coverage, most meaningful)
    # Secondary: persona_strategy (derived from size), region, persona

    print("\n  --- Candidate cohort: vertical x persona_strategy ---")
    cohort_counts = Counter()
    for r in rows:
        v = r.get("vertical") or "(no vertical)"
        ps = r.get("persona_strategy") or "(no strategy)"
        cohort_counts[(v, ps)] += 1

    for (v, ps), count in cohort_counts.most_common(20):
        if count >= 2:
            print(f"    vertical={v:40s} strategy={ps:20s} {count:4d}")

    print("\n  --- Candidate cohort: vertical x employee_band ---")
    cohort_counts2 = Counter()
    for r in rows:
        v = r.get("vertical") or "(no vertical)"
        eb = r.get("employee_band") or "(no band)"
        cohort_counts2[(v, eb)] += 1

    for (v, eb), count in cohort_counts2.most_common(20):
        if count >= 2:
            print(f"    vertical={v:40s} band={eb:20s} {count:4d}")

    print("\n  --- Candidate cohort: vertical x region ---")
    cohort_counts3 = Counter()
    for r in rows:
        v = r.get("vertical") or "(no vertical)"
        reg = r.get("region") or "(no region)"
        cohort_counts3[(v, reg)] += 1

    for (v, reg), count in cohort_counts3.most_common(20):
        if count >= 2:
            print(f"    vertical={v:40s} region={reg:20s} {count:4d}")

    print("\n  --- Candidate cohort: persona x employee_band ---")
    cohort_counts4 = Counter()
    for r in rows:
        p = r.get("persona") or "(no persona)"
        eb = r.get("employee_band") or "(no band)"
        cohort_counts4[(p, eb)] += 1

    for (p, eb), count in cohort_counts4.most_common(20):
        if count >= 2:
            print(f"    persona={p:30s} band={eb:20s} {count:4d}")

    print("\n  --- Candidate cohort: relevant_pain_categories ---")
    pain_counts = Counter()
    for r in rows:
        pains = r.get("relevant_pain_categories", ())
        if pains:
            pain_counts[pains] += 1
        else:
            pain_counts["(none)"] += 1

    for pains, count in pain_counts.most_common(20):
        if count >= 2:
            print(f"    pains={str(pains):50s} {count:4d}")

    print("\n  --- Candidate cohort: persona x persona_strategy ---")
    cohort_counts5 = Counter()
    for r in rows:
        p = r.get("persona") or "(no persona)"
        ps = r.get("persona_strategy") or "(no strategy)"
        cohort_counts5[(p, ps)] += 1

    for (p, ps), count in cohort_counts5.most_common(20):
        if count >= 2:
            print(f"    persona={p:30s} strategy={ps:20s} {count:4d}")

    # =========================================================================
    # 5. SUMMARY TABLE: DIMENSION USABILITY
    # =========================================================================
    print("\n" + "#"*60)
    print("# SECTION 5: DIMENSION USABILITY SUMMARY")
    print("#"*60)

    print(f"\n  {'Dimension':<30s} {'Coverage':>10s} {'Distinct':>10s} {'Type':>12s} {'Groupable?':>12s}")
    print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*12} {'-'*12}")

    for dim_key, dim_label in dimensions:
        counter, null_count, total = dim_results.get(dim_key, (Counter(), 0, 0))
        coverage = total - null_count
        coverage_pct = 100 * coverage / total if total else 0
        distinct = len(counter)
        info = classification.get(dim_key, {})
        dim_type = info.get("type", "UNKNOWN")

        # Groupable if: coverage > 50%, distinct values 2-15, not too sparse
        groupable = "YES" if (coverage_pct > 50 and 2 <= distinct <= 15) else "NO"
        if coverage_pct < 30:
            groupable = "TOO SPARSE"
        elif distinct > 20:
            groupable = "TOO MANY"
        elif distinct <= 1:
            groupable = "NO VALUES"

        print(f"  {dim_key:<30s} {coverage_pct:>9.1f}% {distinct:>10d} {dim_type:>12s} {groupable:>12s}")


if __name__ == "__main__":
    main()
