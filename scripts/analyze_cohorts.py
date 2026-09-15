#!/usr/bin/env python3
"""Analyze queue snapshot for cohort inventory - TASK-096."""
import json
import hashlib
from collections import defaultdict, Counter
from pathlib import Path

def load_records(path):
    records = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def hash_id(value):
    """Hash identifier to avoid PII leakage."""
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]

def get_field(record, path, default=None):
    """Safely get nested field."""
    keys = path.split('.')
    val = record
    for key in keys:
        if isinstance(val, dict):
            val = val.get(key, default)
        else:
            return default
    return val

def extract_contacts(records):
    """Extract all contacts from records with parent record context."""
    contacts = []
    for record in records:
        # Skip dropped records
        if record.get('drop_reason') is not None:
            continue
        
        record_context = {
            'record_id': record.get('id'),
            'company': record.get('company'),
            'domain': record.get('domain'),
            'industry': get_field(record, 'company_facts.industry'),
            'headcount': get_field(record, 'company_facts.employees'),
            'employee_range': get_field(record, 'company_facts.employee_range'),
            'revenue': get_field(record, 'company_facts.revenue'),
        }
        
        for contact in record.get('contacts', []):
            contact_data = {
                **record_context,
                'contact_key': contact.get('key'),
                'name': contact.get('name'),
                'title': contact.get('title'),
                'email': contact.get('email'),
                'persona': contact.get('persona'),
                'angle': contact.get('angle'),
                'specialties': contact.get('specialties', []),
                'sendable': contact.get('sendable', False),
                'verdict': contact.get('verdict'),
            }
            contacts.append(contact_data)
    
    return contacts

def analyze_coverage(contacts):
    """Analyze field coverage for cohort grouping."""
    print(f"=== COVERAGE ANALYSIS ===")
    print(f"Total contacts (from not-dropped records): {len(contacts)}")
    print()
    
    # Fields to check
    fields = {
        'name': lambda c: bool(c.get('name')),
        'title': lambda c: bool(c.get('title')),
        'company': lambda c: bool(c.get('company')),
        'domain': lambda c: bool(c.get('domain')),
        'email': lambda c: bool(c.get('email')),
        'persona': lambda c: bool(c.get('persona')),
        'angle': lambda c: bool(c.get('angle')),
        'specialties': lambda c: bool(c.get('specialties')),
        'industry': lambda c: bool(c.get('industry')),
        'headcount': lambda c: c.get('headcount') is not None,
        'employee_range': lambda c: bool(c.get('employee_range')),
        'revenue': lambda c: bool(c.get('revenue')),
        'sendable': lambda c: c.get('sendable') == True,
    }
    
    print("FIELD COVERAGE (contacts from not-dropped records):")
    print(f"{'Field':<20} {'Count':>8} {'%':>8}")
    print("-" * 40)
    
    coverage = {}
    for field_name, check_fn in fields.items():
        count = sum(1 for c in contacts if check_fn(c))
        pct = (count / len(contacts) * 100) if contacts else 0
        coverage[field_name] = (count, pct)
        print(f"{field_name:<20} {count:>8} {pct:>7.1f}%")
    
    print()
    return coverage

def analyze_cohorts(contacts):
    """Identify candidate cohorts based on available signals."""
    print(f"=== COHORT ANALYSIS ===")
    print(f"Analyzing {len(contacts)} contacts")
    print()
    
    # Filter to contacts with email (required for outreach)
    with_email = [c for c in contacts if c.get('email')]
    print(f"Contacts with email: {len(with_email)}")
    print()
    
    cohorts = []
    
    # 1. Persona-based cohorts
    print("--- PERSONA COHORTS ---")
    persona_counts = Counter(c.get('persona') for c in with_email if c.get('persona'))
    for persona, count in persona_counts.most_common():
        print(f"  {persona}: {count}")
        cohorts.append({
            'signal': 'persona',
            'value': persona,
            'count': count,
            'qualification': f"persona == '{persona}' AND email IS NOT NULL",
            'exclusion': 'drop_reason IS NOT NULL OR email IS NULL'
        })
    print()
    
    # 2. Industry-based cohorts
    print("--- INDUSTRY COHORTS ---")
    industry_counts = Counter()
    for c in with_email:
        ind = c.get('industry')
        if ind:
            industry_counts[ind] += 1
    
    for industry, count in industry_counts.most_common():
        print(f"  {industry}: {count}")
        if count >= 5:
            cohorts.append({
                'signal': 'industry',
                'value': industry,
                'count': count,
                'qualification': f"company_facts.industry == '{industry}' AND email IS NOT NULL",
                'exclusion': 'drop_reason IS NOT NULL OR email IS NULL'
            })
    print()
    
    # 3. Angle-based cohorts
    print("--- ANGLE COHORTS ---")
    angle_counts = Counter()
    for c in with_email:
        angle = c.get('angle')
        if angle:
            angle_counts[angle] += 1
    
    for angle, count in angle_counts.most_common():
        print(f"  {angle}: {count}")
        if count >= 5:
            cohorts.append({
                'signal': 'angle',
                'value': angle,
                'count': count,
                'qualification': f"angle == '{angle}' AND email IS NOT NULL",
                'exclusion': 'drop_reason IS NOT NULL OR email IS NULL'
            })
    print()
    
    # 4. Specialties-based cohorts
    print("--- SPECIALTIES COHORTS ---")
    specialty_counts = Counter()
    for c in with_email:
        specs = c.get('specialties')
        if specs and isinstance(specs, list):
            for spec in specs:
                specialty_counts[spec] += 1
    
    for spec, count in specialty_counts.most_common(15):
        print(f"  {spec}: {count}")
        if count >= 5:
            cohorts.append({
                'signal': 'specialty',
                'value': spec,
                'count': count,
                'qualification': f"'{spec}' IN specialties AND email IS NOT NULL",
                'exclusion': 'drop_reason IS NOT NULL OR email IS NULL'
            })
    print()
    
    # 5. Headcount/size-based cohorts
    print("--- COMPANY SIZE COHORTS ---")
    size_counts = Counter()
    for c in with_email:
        emp_range = c.get('employee_range')
        if emp_range:
            size_counts[emp_range] += 1
    
    for size, count in size_counts.most_common():
        print(f"  {size}: {count}")
        if count >= 5:
            cohorts.append({
                'signal': 'company_size',
                'value': size,
                'count': count,
                'qualification': f"company_facts.employee_range == '{size}' AND email IS NOT NULL",
                'exclusion': 'drop_reason IS NOT NULL OR email IS NULL OR employee_range IS NULL'
            })
    print()
    
    # 6. Combined cohorts (persona + industry)
    print("--- COMBINED COHORTS (persona + industry) ---")
    combined_counts = Counter()
    for c in with_email:
        persona = c.get('persona')
        industry = c.get('industry')
        if persona and industry:
            combined_counts[(persona, industry)] += 1
    
    for (persona, industry), count in combined_counts.most_common(10):
        print(f"  {persona} + {industry}: {count}")
        if count >= 5:
            cohorts.append({
                'signal': 'persona_industry',
                'value': f"{persona} | {industry}",
                'count': count,
                'qualification': f"persona == '{persona}' AND company_facts.industry == '{industry}' AND email IS NOT NULL",
                'exclusion': 'drop_reason IS NOT NULL OR email IS NULL'
            })
    print()
    
    # 7. Combined cohorts (angle + industry)
    print("--- COMBINED COHORTS (angle + industry) ---")
    angle_industry_counts = Counter()
    for c in with_email:
        angle = c.get('angle')
        industry = c.get('industry')
        if angle and industry:
            angle_industry_counts[(angle, industry)] += 1
    
    for (angle, industry), count in angle_industry_counts.most_common(10):
        print(f"  {angle} + {industry}: {count}")
        if count >= 5:
            cohorts.append({
                'signal': 'angle_industry',
                'value': f"{angle} | {industry}",
                'count': count,
                'qualification': f"angle == '{angle}' AND company_facts.industry == '{industry}' AND email IS NOT NULL",
                'exclusion': 'drop_reason IS NOT NULL OR email IS NULL'
            })
    print()
    
    return cohorts

def verdict(cohorts):
    """Honest verdict on cohort sizes."""
    print("=== HONEST VERDICT ===")
    
    # Sort by count
    sorted_cohorts = sorted(cohorts, key=lambda c: c['count'], reverse=True)
    
    # Count cohorts by size threshold
    ge_50 = [c for c in sorted_cohorts if c['count'] >= 50]
    ge_25 = [c for c in sorted_cohorts if c['count'] >= 25]
    ge_10 = [c for c in sorted_cohorts if c['count'] >= 10]
    
    print(f"Cohorts with >= 50 leads: {len(ge_50)}")
    if ge_50:
        for c in ge_50[:5]:
            print(f"  - {c['signal']}: {c['value']} ({c['count']} leads)")
    print()
    
    print(f"Cohorts with >= 25 leads: {len(ge_25)}")
    if ge_25:
        for c in ge_25[:10]:
            print(f"  - {c['signal']}: {c['value']} ({c['count']} leads)")
    print()
    
    print(f"Cohorts with >= 10 leads: {len(ge_10)}")
    if ge_10:
        for c in ge_10[:15]:
            print(f"  - {c['signal']}: {c['value']} ({c['count']} leads)")
    print()
    
    if not ge_50:
        largest = sorted_cohorts[0] if sorted_cohorts else None
        if largest:
            print(f"Largest honest cohort: {largest['signal']} = {largest['value']} ({largest['count']} leads)")
            print(f"To reach 50: need {50 - largest['count']} more leads via discovery, enrichment, or merge with compatible cohort")
    print()
    
    return sorted_cohorts

def main():
    snapshot_path = Path('work/queue.snapshot.jsonl')
    if not snapshot_path.exists():
        print(f"ERROR: {snapshot_path} not found")
        return
    
    records = load_records(snapshot_path)
    contacts = extract_contacts(records)
    coverage = analyze_coverage(contacts)
    cohorts = analyze_cohorts(contacts)
    sorted_cohorts = verdict(cohorts)
    
    # Output top cohorts for report
    print("=== TOP 20 COHORTS FOR REPORT ===")
    for i, c in enumerate(sorted_cohorts[:20], 1):
        print(f"{i}. {c['signal']}={c['value']}: {c['count']} leads")
        print(f"   Qualification: {c['qualification']}")
        print(f"   Exclusion: {c['exclusion']}")
        print()

if __name__ == '__main__':
    main()
