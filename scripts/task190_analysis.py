#!/usr/bin/env python3
"""TASK-190: How many of the 66 review records can be resolved from free data?

Measures every free source of geography and company_type evidence against the
66 review records and the 250 unprocessed records. No paid calls.

  py -3 -m scripts.task190_analysis
"""
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ------------------------------------------------------------------ constants

SNAPSHOT = "work/queue.snapshot.jsonl"

# The client's geography include list (from config, normalized to lowercase)
INCLUDE_GEOS = {
    'united kingdom', 'ireland', 'netherlands', 'germany', 'france',
    'nordics', 'sweden', 'norway', 'denmark', 'finland', 'belgium', 'austria',
    'switzerland', 'spain', 'italy', 'portugal', 'poland', 'australia',
    'new zealand', 'united states', 'canada',
    # Also individual countries that map to included regions
    'cyprus', 'malta', 'greece',   # Southern Europe, often targeted
}

EXCLUDE_GEOS = {
    'india', 'pakistan', 'united arab emirates', 'bangladesh',
    'sri lanka', 'philippines', 'indonesia', 'vietnam', 'thailand', 'malaysia',
    'china', 'singapore', 'hong kong', 'japan', 'south korea', 'taiwan',
}

# ISO 3166-1 alpha-2 to country name (lowercase)
ISO_TO_NAME = {
    'GB': 'united kingdom', 'UK': 'united kingdom', 'IE': 'ireland',
    'NL': 'netherlands', 'DE': 'germany', 'FR': 'france', 'SE': 'sweden',
    'NO': 'norway', 'DK': 'denmark', 'FI': 'finland', 'BE': 'belgium',
    'AT': 'austria', 'CH': 'switzerland', 'ES': 'spain', 'IT': 'italy',
    'PT': 'portugal', 'PL': 'poland', 'AU': 'australia',
    'NZ': 'new zealand', 'US': 'united states', 'CA': 'canada',
    'IN': 'india', 'PK': 'pakistan', 'AE': 'united arab emirates',
    'BD': 'bangladesh', 'LK': 'sri lanka', 'PH': 'philippines',
    'ID': 'indonesia', 'VN': 'vietnam', 'TH': 'thailand', 'MY': 'malaysia',
    'CN': 'china', 'SG': 'singapore', 'HK': 'hong kong', 'JP': 'japan',
    'KR': 'south korea', 'TW': 'taiwan',
    'UA': 'ukraine', 'CY': 'cyprus', 'AR': 'argentina', 'CZ': 'czech republic',
    'JO': 'jordan', 'SI': 'slovenia', 'LT': 'lithuania', 'EE': 'estonia',
    'ZA': 'south africa', 'RS': 'serbia', 'RU': 'russia', 'SS': 'south sudan',
    'HR': 'croatia', 'RO': 'romania', 'HU': 'hungary', 'MT': 'malta',
    'GR': 'greece',
}

# Unambiguous country-code TLDs -> ISO code
CCTLD_TO_ISO = {
    'uk': 'GB', 'gb': 'GB', 'ie': 'IE', 'nl': 'NL', 'de': 'DE', 'fr': 'FR',
    'se': 'SE', 'no': 'NO', 'dk': 'DK', 'fi': 'FI', 'be': 'BE', 'at': 'AT',
    'ch': 'CH', 'es': 'ES', 'it': 'IT', 'pt': 'PT', 'pl': 'PL', 'au': 'AU',
    'nz': 'NZ', 'ca': 'CA', 'us': 'US',
    'si': 'SI', 'lt': 'LT', 'ee': 'EE', 'lv': 'LV', 'hr': 'HR', 'ro': 'RO',
    'hu': 'HU', 'cz': 'CZ', 'sk': 'SK', 'bg': 'BG', 'rs': 'RS', 'ua': 'UA',
    'cy': 'CY', 'mt': 'MT', 'gr': 'GR',
    'jp': 'JP', 'kr': 'KR', 'in': 'IN',
}

# Agency industry keywords from icpstructural.AGENCY_INDUSTRY
AGENCY_INDUSTRY_KEYWORDS = (
    'advertising', 'marketing', 'design', 'public relations',
    'graphic design', 'media production', 'software',
    'information technology', 'web', 'digital', 'branding', 'creative',
    'communications',
)

# Vertical signals from segments.py
VERTICAL_SIGNALS = [
    ('SEO', ('seo', 'search engine optimisation', 'search engine optimization',
             'organic search', 'link building', 'technical seo')),
    ('Performance Marketing Agency', ('performance marketing', 'paid media',
             'ppc', 'paid search', 'paid social', 'google ads', 'media buying',
             'demand generation')),
    ('PR / Communications Agency', ('public relations', 'communications agency',
             'press office', 'media relations', 'corporate communications')),
    ('Design / UX Agency', ('ux', 'user experience', 'ui design',
             'product design', 'design studio', 'interaction design',
             'usability')),
    ('Software Development Agency', ('software development', 'software house',
             'web development', 'custom software', 'app development',
             'mobile development', 'development agency', 'engineering services',
             'devops')),
    ('Product Development Agency', ('product development', 'product studio',
             'product agency', 'mvp development', 'digital product')),
    ('Creative / Branding Agency', ('branding', 'brand strategy',
             'creative agency', 'advertising', 'creative studio',
             'campaign creative', 'art direction')),
    ('Digital Marketing Agency', ('digital marketing', 'marketing agency',
             'content marketing', 'social media marketing', 'email marketing',
             'inbound marketing', 'growth agency')),
    ('Architecture / Engineering', ('architecture', 'architects',
             'civil engineering', 'structural engineering', 'surveying',
             'engineering consultancy')),
    ('Consulting', ('consultancy', 'consulting', 'advisory',
             'management consulting', 'strategy consulting',
             'business transformation')),
    ('Professional Services', ('professional services', 'accountancy',
             'accounting firm', 'law firm', 'legal services',
             'recruitment agency', 'staffing')),
]


# --------------------------------------------------------------- helpers

def load_records():
    review, unprocessed, qualified, rejected = [], [], [], []
    with open(SNAPSHOT, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            qual = rec.get('qualification') or {}
            verdict = qual.get('verdict') or {}
            status = verdict.get('icp_status', 'none')
            if status == 'review':
                review.append(rec)
            elif status == 'qualified':
                qualified.append(rec)
            elif status == 'rejected':
                rejected.append(rec)
            else:
                unprocessed.append(rec)
    return review, unprocessed, qualified, rejected


def office_country(rec):
    """(country_name, source) from office ISO codes, or (None, None)."""
    facts = rec.get('company_facts') or {}
    for line in facts.get('offices') or ():
        token = str(line).strip().rstrip('.').split(',')[-1].strip().upper()
        if token in ISO_TO_NAME:
            return ISO_TO_NAME[token], 'company_facts.offices'
    return None, None


def tld_country(domain):
    """(country_name, 'tld') from a ccTLD, or (None, None)."""
    if '.' not in domain:
        return None, None
    tld = domain.rsplit('.', 1)[-1].lower()
    if tld in CCTLD_TO_ISO:
        return ISO_TO_NAME.get(CCTLD_TO_ISO[tld]), 'tld'
    return None, None


def geo_resolves(country):
    """Does this country name resolve the geography criterion?"""
    if country is None:
        return False
    c = country.lower()
    return c in INCLUDE_GEOS or c in EXCLUDE_GEOS


def company_type_from_industry(industry):
    """Does this industry string pass the company_type criterion?"""
    if not industry or industry.lower() == 'unknown':
        return False
    return any(kw in industry.lower() for kw in AGENCY_INDUSTRY_KEYWORDS)


def vertical_signals_in_text(text):
    """Which verticals does this text signal?"""
    text = text.lower()
    found = []
    for vname, keywords in VERTICAL_SIGNALS:
        for kw in keywords:
            if kw in text:
                found.append((vname, kw))
                break
    return found


def gather_all_text(rec):
    """All text available on a record: facts + research."""
    facts = rec.get('company_facts') or {}
    parts = [
        str(facts.get('industry') or ''),
        str(facts.get('description') or ''),
        str(facts.get('tagline') or ''),
    ]
    for s in facts.get('specialties') or []:
        parts.append(str(s))
    for s in facts.get('services') or []:
        parts.append(str(s))
    for item in rec.get('research') or []:
        parts.append(str(item.get('fact') or ''))
    return ' '.join(parts)


def domain_keywords(domain):
    """Extract meaningful words from a domain name."""
    name = domain.split('.')[0]
    for sep in ('-', '.', '_'):
        name = name.replace(sep, ' ')
    return name.lower().split()


# --------------------------------------------------------------- main analysis

def main():
    review, unprocessed, qualified, rejected = load_records()
    print(f"Snapshot: {len(review) + len(unprocessed) + len(qualified) + len(rejected)} records")
    print(f"  qualified: {len(qualified)}, review: {len(review)}, "
          f"rejected: {len(rejected)}, unprocessed: {len(unprocessed)}")
    print()

    # ============================================= 66 REVIEW RECORDS
    print("=" * 70)
    print("66 REVIEW RECORDS: FREE GEOGRAPHY RESOLUTION")
    print("=" * 70)

    geo_already_pass = 0
    geo_resolved_by_offices = 0
    geo_resolved_by_tld = 0
    geo_still_unknown = 0
    geo_details = []

    for rec in review:
        domain = rec.get('domain', '')
        qual = rec.get('qualification') or {}
        verdict = qual.get('verdict') or {}
        structural = verdict.get('structural') or {}
        criteria = structural.get('criteria') or {}
        geo_status = criteria.get('geography', {}).get('status', 'unknown')

        off_country, off_source = office_country(rec)
        tld_cc, tld_source = tld_country(domain)

        if geo_status == 'pass':
            geo_already_pass += 1
            geo_details.append({
                'domain': domain, 'current': 'pass',
                'office': off_country, 'tld': tld_cc,
                'new_source': None,
            })
            continue

        # Try offices first (provider data, higher reliability)
        if off_country and geo_resolves(off_country):
            geo_resolved_by_offices += 1
            geo_details.append({
                'domain': domain, 'current': geo_status,
                'office': off_country, 'tld': tld_cc,
                'new_source': 'offices',
            })
            continue

        # Then TLD (structural fact about the domain registration)
        if tld_cc and geo_resolves(tld_cc):
            geo_resolved_by_tld += 1
            geo_details.append({
                'domain': domain, 'current': geo_status,
                'office': off_country, 'tld': tld_cc,
                'new_source': 'tld',
            })
            continue

        geo_still_unknown += 1
        geo_details.append({
            'domain': domain, 'current': geo_status,
            'office': off_country, 'tld': tld_cc,
            'new_source': None,
        })

    print(f"  Already PASS:            {geo_already_pass}")
    print(f"  Resolved by offices:     {geo_resolved_by_offices}")
    print(f"  Resolved by TLD:         {geo_resolved_by_tld}")
    print(f"  Total newly resolvable:  {geo_resolved_by_offices + geo_resolved_by_tld}")
    print(f"  Still unknown:           {geo_still_unknown}")
    print(f"  Total PASS after free:   {geo_already_pass + geo_resolved_by_offices + geo_resolved_by_tld}")
    print()

    # Breakdown of still-unknown
    print("  Still unknown breakdown:")
    has_office_not_in_list = 0
    has_office_excluded = 0
    has_tld_not_in_list = 0
    no_data_at_all = 0
    for d in geo_details:
        if d['current'] != 'pass' and d['new_source'] is None:
            if d['office'] and d['office'] not in INCLUDE_GEOS and d['office'] not in EXCLUDE_GEOS:
                has_office_not_in_list += 1
            elif d['office'] and d['office'] in EXCLUDE_GEOS:
                has_office_excluded += 1
            elif d['tld'] and d['tld'] not in INCLUDE_GEOS and d['tld'] not in EXCLUDE_GEOS:
                has_tld_not_in_list += 1
            elif d['office'] is None and d['tld'] is None:
                no_data_at_all += 1
            else:
                # Has office or TLD but not matching
                if d['office']:
                    has_office_not_in_list += 1
                elif d['tld']:
                    has_tld_not_in_list += 1
    print(f"    Office country not on include/exclude list: {has_office_not_in_list}")
    print(f"    Office country on exclude list:             {has_office_excluded}")
    print(f"    TLD country not on include/exclude list:    {has_tld_not_in_list}")
    print(f"    No geography data at all:                   {no_data_at_all}")
    print()

    # ============================================= COMPANY TYPE
    print("=" * 70)
    print("66 REVIEW RECORDS: FREE COMPANY TYPE RESOLUTION")
    print("=" * 70)

    ct_already_pass = 0
    ct_resolved_by_industry = 0
    ct_resolved_by_research = 0
    ct_resolved_by_domain = 0
    ct_still_unknown = 0
    ct_details = []

    for rec in review:
        domain = rec.get('domain', '')
        facts = rec.get('company_facts') or {}
        qual = rec.get('qualification') or {}
        verdict = qual.get('verdict') or {}
        structural = verdict.get('structural') or {}
        criteria = structural.get('criteria') or {}
        ct_status = criteria.get('company_type', {}).get('status', 'unknown')

        industry = facts.get('industry', '')
        seg = qual.get('segment') or {}
        vertical = seg.get('vertical', '')

        if ct_status == 'pass':
            ct_already_pass += 1
            ct_details.append({
                'domain': domain, 'current': 'pass',
                'new_source': None,
            })
            continue

        # Source 1: existing industry string (already checked by icpstructural)
        if company_type_from_industry(industry):
            ct_resolved_by_industry += 1
            ct_details.append({
                'domain': domain, 'current': ct_status,
                'new_source': 'industry',
            })
            continue

        # Source 2: vertical signals in research text
        all_text = gather_all_text(rec)
        signals = vertical_signals_in_text(all_text)
        if signals:
            ct_resolved_by_research += 1
            ct_details.append({
                'domain': domain, 'current': ct_status,
                'new_source': 'research_text',
                'signals': signals,
            })
            continue

        # Source 3: keywords in domain name
        dkws = domain_keywords(domain)
        domain_match = False
        for kw in dkws:
            if any(aki in kw for aki in AGENCY_INDUSTRY_KEYWORDS):
                domain_match = True
                break
        if domain_match:
            ct_resolved_by_domain += 1
            ct_details.append({
                'domain': domain, 'current': ct_status,
                'new_source': 'domain_name',
            })
            continue

        ct_still_unknown += 1
        ct_details.append({
            'domain': domain, 'current': ct_status,
            'new_source': None,
        })

    print(f"  Already PASS:              {ct_already_pass}")
    print(f"  Resolved by industry:      {ct_resolved_by_industry}")
    print(f"  Resolved by research text: {ct_resolved_by_research}")
    print(f"  Resolved by domain name:   {ct_resolved_by_domain}")
    print(f"  Total newly resolvable:    {ct_resolved_by_industry + ct_resolved_by_research + ct_resolved_by_domain}")
    print(f"  Still unknown:             {ct_still_unknown}")
    print(f"  Total PASS after free:     {ct_already_pass + ct_resolved_by_industry + ct_resolved_by_research + ct_resolved_by_domain}")
    print()

    # ============================================= COMBINED YIELD
    print("=" * 70)
    print("COMBINED FREE YIELD: 66 REVIEW RECORDS")
    print("=" * 70)

    # For each record, can BOTH defining criteria now PASS?
    both_pass = 0
    geo_only = 0
    ct_only = 0
    neither = 0

    for i, rec in enumerate(review):
        gd = geo_details[i]
        cd = ct_details[i]

        geo_now_pass = (gd['current'] == 'pass' or gd['new_source'] is not None)
        ct_now_pass = (cd['current'] == 'pass' or cd['new_source'] is not None)

        if geo_now_pass and ct_now_pass:
            both_pass += 1
        elif geo_now_pass:
            geo_only += 1
        elif ct_now_pass:
            ct_only += 1
        else:
            neither += 1

    print(f"  Both defining criteria PASS:  {both_pass} -> qualified")
    print(f"  Only geography PASS:          {geo_only} -> still blocked on company_type")
    print(f"  Only company_type PASS:       {ct_only} -> still blocked on geography")
    print(f"  Neither PASS:                 {neither} -> still blocked on both")
    print(f"  Total reaching qualified:     {both_pass} of 66")
    print(f"  Still needing purchase:       {66 - both_pass} of 66")
    print()

    # ============================================= 250 UNPROCESSED
    print("=" * 70)
    print("250 UNPROCESSED RECORDS: TLD GEOGRAPHY YIELD")
    print("=" * 70)

    tld_resolves_included = 0
    tld_resolves_excluded = 0
    tld_resolves_not_on_list = 0
    tld_ambiguous = 0

    tld_country_counts = {}
    for rec in unprocessed:
        domain = rec.get('domain', '')
        cc, _ = tld_country(domain)
        if cc:
            c = cc.lower()
            tld_country_counts[c] = tld_country_counts.get(c, 0) + 1
            if c in INCLUDE_GEOS:
                tld_resolves_included += 1
            elif c in EXCLUDE_GEOS:
                tld_resolves_excluded += 1
            else:
                tld_resolves_not_on_list += 1
        else:
            tld_ambiguous += 1

    print(f"  TLD resolves to included country: {tld_resolves_included}")
    print(f"  TLD resolves to excluded country: {tld_resolves_excluded}")
    print(f"  TLD resolves but not on any list: {tld_resolves_not_on_list}")
    print(f"  TLD ambiguous (.com, .io, etc):   {tld_ambiguous}")
    print()
    if tld_country_counts:
        print("  Countries resolved by TLD:")
        for country, count in sorted(tld_country_counts.items(), key=lambda x: -x[1]):
            print(f"    {country}: {count}")
    print()

    # ============================================= RELIABILITY
    print("=" * 70)
    print("RELIABILITY ASSESSMENT")
    print("=" * 70)
    print()
    print("  Source                    Reliability   Notes")
    print("  ------------------------  -----------   ----------------------------")
    print("  company_facts.offices     HIGH          Provider data with ISO codes")
    print("  ccTLD                     HIGH          Domain registration is legal")
    print("  research text verticals   MEDIUM        Already seen by classifier;")
    print("                                        weak signals it could not use")
    print("  domain name keywords      LOW-MEDIUM    'advertising' in domain is")
    print("                                        strong; 'digital' is weaker")
    print()
    print("  KEY CONSTRAINT: Inference may only move UNKNOWN to PASS, never")
    print("  UNKNOWN to FAIL. A wrong inference that fails a criterion turns")
    print("  a good company into icp_fail, and FAIL on any criterion is")
    print("  terminal for qualification.")


if __name__ == '__main__':
    main()
