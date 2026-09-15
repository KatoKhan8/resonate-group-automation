#!/usr/bin/env python3
"""TASK-112: Measure enrichment quality across the queue snapshot.

Reads work/queue.snapshot.jsonl and reports per-field coverage, correctness,
staleness, and a verdict per field. No provider calls. Read-only.
"""
import json
import hashlib
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

SNAPSHOT = "work/queue.snapshot.jsonl"
NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def hash_id(s):
    """Hash an identifier so no PII appears in the report."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def first_contact(rec):
    """The primary contact, or the first one."""
    contacts = rec.get("contacts") or []
    for c in contacts:
        if c.get("primary"):
            return c
    return contacts[0] if contacts else None


def parse_ts(ts_str):
    """Parse an ISO timestamp to a datetime, or None."""
    if not ts_str:
        return None
    try:
        ts_str = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return None


def age_days(ts_str):
    """Days since timestamp, or None."""
    dt = parse_ts(ts_str)
    if dt is None:
        return None
    return (NOW - dt).days


def main():
    records = load_records()
    n = len(records)
    print(f"# Enrichment Quality Measurement")
    print(f"# Snapshot: {SNAPSHOT}")
    print(f"# Records: {n}")
    print(f"# Date: 2026-09-15")
    print()

    # ---- STATE DISTRIBUTION ----
    states = Counter(r.get("state") for r in records)
    print(f"## State distribution")
    for s, c in states.most_common():
        print(f"  {s}: {c}")
    print()

    # Non-dropped records
    non_dropped = [r for r in records if r.get("state") != "dropped"]
    dropped = [r for r in records if r.get("state") == "dropped"]
    print(f"Non-dropped: {len(non_dropped)}, Dropped: {len(dropped)}")
    print()

    # ---- CONTACT-LEVEL FIELDS ----
    # Count total contacts
    all_contacts = []
    for r in records:
        for c in r.get("contacts") or []:
            all_contacts.append((r, c))
    total_contacts = len(all_contacts)
    print(f"## Contact-level fields (n={total_contacts} contacts across {n} records)")
    print()

    # Coverage: first_name (from name), title, email, linkedin, persona, angle,
    #           verdict, sendable, email_source
    contact_fields = {
        "name": lambda c: c.get("name"),
        "title": lambda c: c.get("title"),
        "email": lambda c: c.get("email"),
        "linkedin": lambda c: c.get("linkedin"),
        "persona": lambda c: c.get("persona"),
        "angle": lambda c: c.get("angle"),
        "verdict": lambda c: c.get("verdict"),
        "sendable": lambda c: c.get("sendable"),
        "email_source": lambda c: c.get("email_source"),
    }

    for field_name, getter in contact_fields.items():
        present = sum(1 for _, c in all_contacts if getter(c))
        pct = 100.0 * present / total_contacts if total_contacts else 0
        print(f"  {field_name}: {present}/{total_contacts} ({pct:.1f}%)")
    print()

    # Verdict distribution
    verdicts = Counter(c.get("verdict") for _, c in all_contacts)
    print(f"  Verdict distribution:")
    for v, cnt in verdicts.most_common():
        print(f"    {v}: {cnt}")
    print()

    # ---- COMPANY-LEVEL FIELDS ----
    print(f"## Company-level fields (n={n} records)")
    print()

    company_fields = {
        "domain": lambda r: r.get("domain"),
        "company": lambda r: r.get("company"),
        "company_facts.industry": lambda r: (r.get("company_facts") or {}).get("industry"),
        "company_facts.employee_range": lambda r: (r.get("company_facts") or {}).get("employee_range"),
        "company_facts.employees": lambda r: (r.get("company_facts") or {}).get("employees"),
        "company_facts.headcount_signal": lambda r: (r.get("company_facts") or {}).get("headcount_signal"),
        "company_facts.revenue": lambda r: (r.get("company_facts") or {}).get("revenue"),
        "company_facts.linkedin": lambda r: (r.get("company_facts") or {}).get("linkedin"),
        "company_facts.offices": lambda r: (r.get("company_facts") or {}).get("offices"),
        "company_facts.specialties": lambda r: (r.get("company_facts") or {}).get("specialties"),
        "company_facts.research_outcome": lambda r: (r.get("company_facts") or {}).get("research_outcome"),
        "company_facts.recovered_from": lambda r: (r.get("company_facts") or {}).get("recovered_from"),
    }

    for field_name, getter in company_fields.items():
        present = sum(1 for r in records if getter(r))
        pct = 100.0 * present / n if n else 0
        print(f"  {field_name}: {present}/{n} ({pct:.1f}%)")
    print()

    # ---- QUALIFICATION / SEGMENT FIELDS ----
    print(f"## Qualification / Segment fields (n={n} records)")
    print()

    seg_fields = {
        "segment.vertical": lambda r: (r.get("qualification") or {}).get("segment", {}).get("vertical"),
        "segment.subvertical": lambda r: (r.get("qualification") or {}).get("segment", {}).get("subvertical"),
        "segment.industry": lambda r: (r.get("qualification") or {}).get("segment", {}).get("industry"),
        "segment.country": lambda r: (r.get("qualification") or {}).get("segment", {}).get("country"),
        "segment.country_code": lambda r: (r.get("qualification") or {}).get("segment", {}).get("country_code"),
        "segment.region": lambda r: (r.get("qualification") or {}).get("segment", {}).get("region"),
        "segment.timezone": lambda r: (r.get("qualification") or {}).get("segment", {}).get("timezone"),
        "segment.timezone_confidence": lambda r: (r.get("qualification") or {}).get("segment", {}).get("timezone_confidence"),
        "segment.business_model": lambda r: (r.get("qualification") or {}).get("segment", {}).get("business_model"),
        "segment.company_maturity": lambda r: (r.get("qualification") or {}).get("segment", {}).get("company_maturity"),
        "segment.delivery_model": lambda r: (r.get("qualification") or {}).get("segment", {}).get("delivery_model"),
        "segment.employee_band": lambda r: (r.get("qualification") or {}).get("segment", {}).get("employee_band"),
        "segment.employees": lambda r: (r.get("qualification") or {}).get("segment", {}).get("employees"),
    }

    for field_name, getter in seg_fields.items():
        present = sum(1 for r in records if getter(r))
        pct = 100.0 * present / n if n else 0
        print(f"  {field_name}: {present}/{n} ({pct:.1f}%)")
    print()

    # Qualification verdict
    verdict_present = sum(1 for r in records if (r.get("qualification") or {}).get("verdict"))
    print(f"  qualification.verdict: {verdict_present}/{n} ({100.0*verdict_present/n:.1f}%)")

    # ICP status
    icp_statuses = Counter()
    for r in records:
        v = (r.get("qualification") or {}).get("verdict") or {}
        icp_statuses[v.get("icp_status", "MISSING")] += 1
    print(f"  ICP status distribution:")
    for s, cnt in icp_statuses.most_common():
        print(f"    {s}: {cnt}")
    print()

    # ---- MESSAGING / ANGLES ----
    print(f"## Messaging fields (n={n} records)")
    print()
    msg_fields = {
        "messaging.vertical": lambda r: (r.get("qualification") or {}).get("messaging", {}).get("vertical"),
        "messaging.recommended_angles": lambda r: (r.get("qualification") or {}).get("messaging", {}).get("recommended_angles"),
        "messaging.relevant_pain_categories": lambda r: (r.get("qualification") or {}).get("messaging", {}).get("relevant_pain_categories"),
    }
    for field_name, getter in msg_fields.items():
        present = sum(1 for r in records if getter(r))
        pct = 100.0 * present / n if n else 0
        print(f"  {field_name}: {present}/{n} ({pct:.1f}%)")
    print()

    # ---- CORRECTNESS CHECKS ----
    print(f"## Correctness checks")
    print()

    # 1. Headcount: employees vs employee_range disagreements
    hc_disagree = 0
    hc_details = []
    for r in records:
        cf = r.get("company_facts") or {}
        emp = cf.get("employees")
        erange = cf.get("employee_range")
        if emp is not None and erange:
            # Parse range like "11-50 employees" or "51-200"
            range_str = str(erange).replace(" employees", "").strip()
            parts = range_str.split("-")
            if len(parts) == 2:
                try:
                    lo, hi = int(parts[0]), int(parts[1])
                    if emp < lo or emp > hi:
                        hc_disagree += 1
                        hc_details.append((r.get("id"), emp, erange))
                except ValueError:
                    pass
    print(f"  Headcount employees vs employee_range disagreements: {hc_disagree}/{n}")
    if hc_details:
        print(f"  Examples (hashed IDs):")
        for rid, emp, erange in hc_details[:10]:
            print(f"    {hash_id(rid)}: employees={emp}, range={erange}")
    print()

    # 2. headcount_signal vs employees
    hs_conflicts = 0
    hs_details = []
    for r in records:
        cf = r.get("company_facts") or {}
        hs = cf.get("headcount_signal")
        emp = cf.get("employees")
        if hs is not None and emp is not None:
            # headcount_signal should be roughly consistent with employees
            # Allow 20% tolerance
            if emp > 0 and abs(hs - emp) / emp > 0.5:
                hs_conflicts += 1
                hs_details.append((r.get("id"), hs, emp))
    print(f"  headcount_signal vs employees (>50% divergence): {hs_conflicts}/{n}")
    if hs_details:
        print(f"  Examples (hashed IDs):")
        for rid, hs, emp in hs_details[:10]:
            print(f"    {hash_id(rid)}: headcount_signal={hs}, employees={emp}")
    print()

    # 3. Domain vs company name: is company just a domain string?
    company_is_domain = 0
    for r in records:
        company = (r.get("company") or "").strip().lower()
        domain = (r.get("domain") or "").strip().lower()
        if company and domain and (company == domain or company == domain.replace(".", "") or
                                    domain.startswith(company) or company in domain):
            company_is_domain += 1
    print(f"  company field is actually a domain string: {company_is_domain}/{n}")
    print()

    # 4. Email domain vs record domain
    email_domain_mismatch = 0
    email_mismatch_details = []
    for r, c in all_contacts:
        email = c.get("email") or ""
        rec_domain = (r.get("domain") or "").lower()
        cf = r.get("company_facts") or {}
        mail_domain = (cf.get("email_domain") or "").lower()
        if "@" in email:
            addr_domain = email.split("@")[-1].lower()
            if addr_domain != rec_domain and (not mail_domain or addr_domain != mail_domain):
                email_domain_mismatch += 1
                email_mismatch_details.append((r.get("id"), c.get("key"), addr_domain, rec_domain))
    print(f"  Contact email domain != record domain: {email_domain_mismatch}/{total_contacts}")
    if email_mismatch_details:
        print(f"  Examples (hashed IDs):")
        for rid, ckey, edom, rdom in email_mismatch_details[:10]:
            print(f"    {hash_id(rid)}/{hash_id(ckey or '')}: email@{edom}, record={rdom}")
    print()

    # 5. Industry value check: are there empty/placeholder values?
    industry_values = Counter()
    for r in records:
        cf = r.get("company_facts") or {}
        ind = cf.get("industry")
        if ind:
            industry_values[ind] += 1
    print(f"  Industry value distribution (top 15):")
    for ind, cnt in industry_values.most_common(15):
        print(f"    {ind}: {cnt}")
    print()

    # 6. Segment vertical vs company_facts industry: agreement?
    vert_industry_agree = 0
    vert_industry_disagree = 0
    vert_industry_missing = 0
    for r in records:
        seg = (r.get("qualification") or {}).get("segment") or {}
        cf = r.get("company_facts") or {}
        vertical = seg.get("vertical")
        industry = cf.get("industry")
        if not vertical or not industry:
            vert_industry_missing += 1
        elif vertical.lower() != industry.lower():
            # They are different fields but should be related
            vert_industry_disagree += 1
        else:
            vert_industry_agree += 1
    print(f"  segment.vertical vs company_facts.industry:")
    print(f"    exact match: {vert_industry_agree}")
    print(f"    different (expected - different granularity): {vert_industry_disagree}")
    print(f"    one or both missing: {vert_industry_missing}")
    print()

    # 7. Timezone: is it guessed or evidenced?
    tz_source_dist = Counter()
    tz_conf_dist = Counter()
    for r in records:
        seg = (r.get("qualification") or {}).get("segment") or {}
        tz = seg.get("timezone")
        tz_src = seg.get("timezone_source")
        tz_conf = seg.get("timezone_confidence")
        if tz:
            tz_source_dist[tz_src or "UNKNOWN"] += 1
            tz_conf_dist[tz_conf or "UNKNOWN"] += 1
    print(f"  Timezone source distribution (only records WITH timezone):")
    for s, cnt in tz_source_dist.most_common():
        print(f"    {s}: {cnt}")
    print(f"  Timezone confidence distribution:")
    for c, cnt in tz_conf_dist.most_common():
        print(f"    {c}: {cnt}")
    print()

    # 8. Research quality distribution
    research_quality = Counter()
    research_freshness = Counter()
    total_research = 0
    for r in records:
        for res in r.get("research") or []:
            total_research += 1
            research_quality[res.get("quality", "UNKNOWN")] += 1
            research_freshness[res.get("freshness_bucket", "UNKNOWN")] += 1
    print(f"  Research items: {total_research} across {n} records")
    print(f"  Research quality distribution:")
    for q, cnt in research_quality.most_common():
        print(f"    {q}: {cnt}")
    print(f"  Research freshness distribution:")
    for fb, cnt in research_freshness.most_common():
        print(f"    {fb}: {cnt}")
    print()

    # 9. Recovery / provenance: how old is the evidence?
    recovery_ages = []
    for r in records:
        cf = r.get("company_facts") or {}
        rf = cf.get("recovered_from")
        if rf and isinstance(rf, dict):
            orig_ts = rf.get("original_timestamp")
            if orig_ts:
                ad = age_days(orig_ts)
                if ad is not None:
                    recovery_ages.append(ad)
    if recovery_ages:
        recovery_ages.sort()
        print(f"  Recovery original_timestamp ages (days):")
        print(f"    min: {recovery_ages[0]}, median: {recovery_ages[len(recovery_ages)//2]}, max: {recovery_ages[-1]}")
        print(f"    n={len(recovery_ages)}")
    print()

    # 10. Waterfall: what stages actually ran?
    waterfall_stages = Counter()
    for r in records:
        for w in r.get("waterfall") or []:
            call = w.get("call", "unknown")
            waterfall_stages[call] += 1
    print(f"  Waterfall calls recorded (total entries):")
    for call, cnt in waterfall_stages.most_common():
        print(f"    {call}: {cnt}")
    print()

    # 11. Enrichment stage status
    enrich_status = Counter()
    for r in records:
        stages = r.get("stages") or {}
        enrich = stages.get("enrich") or {}
        enrich_status[enrich.get("status", "UNKNOWN")] += 1
    print(f"  Enrich stage status:")
    for s, cnt in enrich_status.most_common():
        print(f"    {s}: {cnt}")
    print()

    # 12. Contact angle vs persona agreement
    angle_persona_agree = 0
    angle_persona_disagree = 0
    angle_values = Counter()
    persona_values = Counter()
    for _, c in all_contacts:
        angle = c.get("angle")
        persona = c.get("persona")
        if angle:
            angle_values[angle] += 1
        if persona:
            persona_values[persona] += 1
        if angle and persona:
            if angle == persona:
                angle_persona_agree += 1
            else:
                angle_persona_disagree += 1
    print(f"  Contact angle values:")
    for a, cnt in angle_values.most_common():
        print(f"    {a}: {cnt}")
    print(f"  Contact persona values:")
    for p, cnt in persona_values.most_common():
        print(f"    {p}: {cnt}")
    print(f"  angle == persona: {angle_persona_agree}, different: {angle_persona_disagree}")
    print()

    # 13. Specialties coverage and depth
    spec_counts = []
    for r in records:
        cf = r.get("company_facts") or {}
        specs = cf.get("specialties")
        if specs and isinstance(specs, list):
            spec_counts.append(len(specs))
        else:
            spec_counts.append(0)
    with_specs = sum(1 for s in spec_counts if s > 0)
    print(f"  Specialties: {with_specs}/{n} records have at least one ({100.0*with_specs/n:.1f}%)")
    if spec_counts:
        non_zero = [s for s in spec_counts if s > 0]
        if non_zero:
            print(f"    When present: min={min(non_zero)}, median={sorted(non_zero)[len(non_zero)//2]}, max={max(non_zero)}")
    print()

    # 14. Verification / sendable breakdown
    sendable_true = sum(1 for _, c in all_contacts if c.get("sendable"))
    sendable_false = total_contacts - sendable_true
    print(f"  Sendable: {sendable_true}/{total_contacts}, Not sendable: {sendable_false}")
    print()

    # 15. Contact count per record
    contact_counts = Counter(len(r.get("contacts") or []) for r in records)
    print(f"  Contacts per record distribution:")
    for cnt, num in sorted(contact_counts.items()):
        print(f"    {cnt} contacts: {num} records")
    print()

    # 16. ICP tier distribution
    icp_tiers = Counter()
    for r in records:
        v = (r.get("qualification") or {}).get("verdict") or {}
        icp_tiers[v.get("icp_tier", "MISSING")] += 1
    print(f"  ICP tier distribution:")
    for t, cnt in icp_tiers.most_common():
        print(f"    {t}: {cnt}")
    print()

    # 17. Employee range: what values appear?
    erange_values = Counter()
    for r in records:
        cf = r.get("company_facts") or {}
        er = cf.get("employee_range")
        if er:
            erange_values[er] += 1
    print(f"  employee_range values:")
    for er, cnt in erange_values.most_common():
        print(f"    {er}: {cnt}")
    print()

    # 18. Staleness: waterfall timestamps
    waterfall_ages = []
    for r in records:
        for w in r.get("waterfall") or []:
            at = w.get("at")
            if at:
                ad = age_days(at)
                if ad is not None:
                    waterfall_ages.append(ad)
    if waterfall_ages:
        waterfall_ages.sort()
        print(f"  Waterfall entry ages (days):")
        print(f"    min: {waterfall_ages[0]}, median: {waterfall_ages[len(waterfall_ages)//2]}, max: {waterfall_ages[-1]}")
        print(f"    n={len(waterfall_ages)}")
    print()

    # 19. Qualification scored_at ages
    qual_ages = []
    for r in records:
        v = (r.get("qualification") or {}).get("verdict") or {}
        at = v.get("scored_at")
        if at:
            ad = age_days(at)
            if ad is not None:
                qual_ages.append(ad)
    if qual_ages:
        qual_ages.sort()
        print(f"  Qualification scored_at ages (days):")
        print(f"    min: {qual_ages[0]}, median: {qual_ages[len(qual_ages)//2]}, max: {qual_ages[-1]}")
        print(f"    n={len(qual_ages)}")
    print()

    # 20. Revenue field: what values?
    revenue_values = Counter()
    for r in records:
        cf = r.get("company_facts") or {}
        rev = cf.get("revenue")
        if rev:
            revenue_values[rev] += 1
    print(f"  Revenue values (top 15):")
    for rev, cnt in revenue_values.most_common(15):
        print(f"    {rev}: {cnt}")
    print()

    # 21. ICP flags: what do they say?
    icp_flag_examples = []
    for r in records:
        cf = r.get("company_facts") or {}
        flags = cf.get("icp_flags")
        if flags and isinstance(flags, list):
            for f in flags:
                icp_flag_examples.append(f)
    print(f"  ICP flags: {len(icp_flag_examples)} total flags across records")
    flag_counter = Counter(icp_flag_examples)
    print(f"  Top ICP flags:")
    for f, cnt in flag_counter.most_common(10):
        print(f"    {f}: {cnt}")
    print()

    # 22. Check for contradictions: company_facts.employees vs segment.employees
    seg_emp_disagree = 0
    for r in records:
        cf = r.get("company_facts") or {}
        seg = (r.get("qualification") or {}).get("segment") or {}
        cf_emp = cf.get("employees")
        seg_emp = seg.get("employees")
        if cf_emp is not None and seg_emp is not None and cf_emp != seg_emp:
            seg_emp_disagree += 1
    print(f"  company_facts.employees vs segment.employees disagreements: {seg_emp_disagree}/{n}")
    print()

    # 23. MX check coverage
    mx_present = 0
    mx_statuses = Counter()
    for _, c in all_contacts:
        mx = c.get("mx")
        if mx:
            mx_present += 1
            mx_statuses[mx.get("status", "UNKNOWN")] += 1
    print(f"  MX check present: {mx_present}/{total_contacts}")
    print(f"  MX status distribution:")
    for s, cnt in mx_statuses.most_common():
        print(f"    {s}: {cnt}")
    print()

    # 24. Reoon coverage
    reoon_present = 0
    for _, c in all_contacts:
        if c.get("reoon"):
            reoon_present += 1
    print(f"  Reoon check present: {reoon_present}/{total_contacts}")
    print()

    # 25. Verification state coverage
    verif_present = 0
    verif_states = Counter()
    for _, c in all_contacts:
        v = c.get("verification")
        if v:
            verif_present += 1
            verif_states[v.get("state", "UNKNOWN")] += 1
    print(f"  Verification block present: {verif_present}/{total_contacts}")
    print(f"  Verification state distribution:")
    for s, cnt in verif_states.most_common():
        print(f"    {s}: {cnt}")
    print()


if __name__ == "__main__":
    main()
