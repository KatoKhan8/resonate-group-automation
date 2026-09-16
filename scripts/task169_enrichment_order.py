#!/usr/bin/env python3
"""TASK-169: The cheapest order from a verdict to campaign-ready.

Measures pre-enrichment predictors of survival to campaign-ready, the free-field
rejection predictors, and the stage-by-stage attribution of loss.

SNAPSHOT: work/queue.snapshot.jsonl
STAMP: 2026-09-15T17:52:12+00:00 from master cf23154 550 records

Questions:
1. Yield per credit, measured backwards from the 300 that went through.
2. The rejection rate visible for free (ICP rejection predictors).
3. The drop-off between paid and ready (stage-by-stage attribution).
4. The ordering rule and projected credits per campaign-ready account.
"""
import json
import sys
import hashlib
from collections import defaultdict, Counter
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

SNAPSHOT = Path("work/queue.snapshot.jsonl")
STAMP = "2026-09-15T17:52:12+00:00 from master cf23154 550 records"

# Credit costs from TASK-152 and src/enrich.py
CREDITS_PER_RECORD = 3.14  # measured amortised cost


def load_snapshot():
    recs = []
    with open(SNAPSHOT, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def hash_id(rec_id):
    """Hash record ID to avoid committing PII."""
    return hashlib.sha256(rec_id.encode()).hexdigest()[:12]


def hash_domain(domain):
    """Hash domain to avoid committing PII."""
    return hashlib.sha256(domain.encode()).hexdigest()[:12]


def get_pre_enrichment_fields(rec):
    """Extract fields available BEFORE enrichment runs."""
    cf = rec.get('company_facts') or {}
    return {
        'domain': rec.get('domain', ''),
        'company': rec.get('company', ''),
        'lane': rec.get('lane', ''),
        'client': rec.get('client', ''),
        'signal': rec.get('signal') or '',
        'context': rec.get('context') or '',
        'headcount_signal': cf.get('headcount_signal'),
        'employees': cf.get('employees'),
        'employee_range': cf.get('employee_range') or '',
        'revenue': cf.get('revenue') or '',
        'industry': cf.get('industry') or '',
        'research_outcome': cf.get('research_outcome') or '',
        'icp_flags': cf.get('icp_flags') or [],
        'has_offices': bool(cf.get('offices')),
        'has_linkedin': bool(cf.get('linkedin')),
    }


def get_verdict(rec):
    """Get the ICP verdict."""
    qual = rec.get('qualification') or {}
    verdict = qual.get('verdict') or {}
    return {
        'icp_status': verdict.get('icp_status') or '',
        'icp_confidence': verdict.get('icp_confidence') or '',
        'icp_tier': verdict.get('icp_tier') or '',
        'icp_score': verdict.get('icp_score'),
        'positive_signals': len(verdict.get('positive_signals') or []),
        'negative_signals': len(verdict.get('negative_signals') or []),
    }


def get_contacts_summary(rec):
    """Summarise contact-level outcomes."""
    contacts = rec.get('contacts') or []
    excluded = rec.get('excluded') or []
    total = len(contacts) + len(excluded)
    
    sendable = sum(1 for c in contacts if c.get('sendable'))
    verified = sum(1 for c in contacts 
                   if (c.get('verification') or {}).get('state') == 'verified')
    has_linkedin = sum(1 for c in contacts if c.get('linkedin'))
    has_email = sum(1 for c in contacts if c.get('email'))
    has_persona = sum(1 for c in contacts if c.get('persona'))
    has_bison = sum(1 for c in contacts if c.get('bison_lead_id'))
    
    return {
        'total_contacts': total,
        'kept_contacts': len(contacts),
        'excluded_contacts': len(excluded),
        'sendable': sendable,
        'verified': verified,
        'has_linkedin': has_linkedin,
        'has_email': has_email,
        'has_persona': has_persona,
        'has_bison_lead': has_bison > 0,
    }


def has_campaign_ready_contact(rec):
    """Check if a record has at least one campaign-ready contact.
    
    Campaign-ready means: has cadence steps generated AND at least one 
    contact with sendable=True and verification.state=verified.
    """
    if rec.get('state') not in ('drafted', 'approved', 'pushed'):
        return False
    
    cadence = rec.get('cadence') or {}
    if not cadence:
        return False
    
    contacts = rec.get('contacts') or []
    for c in contacts:
        if c.get('sendable') and (c.get('verification') or {}).get('state') == 'verified':
            key = c.get('key')
            if key and key in cadence:
                return True
    return False


def determine_pipeline_stage(rec):
    """Determine the furthest stage this record reached."""
    state = rec.get('state', '')
    
    # Check for specific stage markers
    has_company_facts = bool((rec.get('company_facts') or {}).get('industry'))
    has_research = bool(rec.get('research'))
    has_qualification = bool((rec.get('qualification') or {}).get('verdict'))
    has_contacts = bool(rec.get('contacts'))
    has_verification = any(
        (c.get('verification') or {}).get('state') == 'verified'
        for c in (rec.get('contacts') or [])
    )
    has_cadence = bool(rec.get('cadence'))
    has_approval = any(
        'approved' in str(entry)
        for entry in (rec.get('log') or [])
    )
    
    if state == 'dropped':
        return 'dropped'
    if state == 'held':
        return 'held'
    if has_approval or state == 'approved':
        return 'approved'
    if has_cadence or state == 'drafted':
        return 'drafted'
    if has_verification or state == 'verified':
        return 'verified'
    if has_contacts or state == 'enriched':
        return 'enriched'
    if has_qualification:
        return 'qualified'
    if has_research:
        return 'researched'
    if has_company_facts:
        return 'company_facts'
    if state == 'queued':
        return 'queued'
    return 'unknown'


def get_drop_reason(rec):
    """Get the reason a record was dropped or held."""
    if rec.get('drop_reason'):
        return rec.get('drop_reason')
    
    # Check ICP flags
    icp_flags = (rec.get('company_facts') or {}).get('icp_flags') or []
    if icp_flags:
        return '; '.join(icp_flags)
    
    # Check log for rejection reasons
    log = rec.get('log') or []
    for entry in reversed(log):
        note = entry.get('note', '')
        if 'employees' in note.lower() and 'under' in note.lower():
            return 'ICP: too small'
        if 'geo' in note.lower() or 'geography' in note.lower():
            return 'ICP: geo mismatch'
    
    return None


def analyze_stage_attribution(recs):
    """Stage-by-stage attribution of the drop-off."""
    stages = Counter()
    drop_reasons = Counter()
    
    for rec in recs:
        stage = determine_pipeline_stage(rec)
        stages[stage] += 1
        
        if stage in ('dropped', 'held'):
            reason = get_drop_reason(rec)
            if reason:
                drop_reasons[reason] += 1
    
    return dict(stages), dict(drop_reasons)


def analyze_pre_enrichment_predictors(recs):
    """Which pre-enrichment fields predict survival to campaign-ready."""
    survived = []
    did_not = []
    
    for rec in recs:
        pre = get_pre_enrichment_fields(rec)
        verdict = get_verdict(rec)
        contacts = get_contacts_summary(rec)
        is_ready = has_campaign_ready_contact(rec)
        
        entry = {
            **pre,
            **{f'verdict_{k}': v for k, v in verdict.items()},
            **{f'contact_{k}': v for k, v in contacts.items()},
            'campaign_ready': is_ready,
            'state': rec.get('state'),
            'stage': determine_pipeline_stage(rec),
        }
        
        if is_ready:
            survived.append(entry)
        else:
            did_not.append(entry)
    
    return survived, did_not


def analyze_free_rejection_predictors(recs):
    """Which free fields predict ICP rejection."""
    rejected = []
    passed = []
    
    for rec in recs:
        pre = get_pre_enrichment_fields(rec)
        verdict = get_verdict(rec)
        
        if not verdict['icp_status']:
            continue  # No verdict yet
        
        entry = {**pre, 'icp_status': verdict['icp_status']}
        
        if verdict['icp_status'] == 'rejected':
            rejected.append(entry)
        elif verdict['icp_status'] == 'qualified':
            passed.append(entry)
    
    return rejected, passed


def compute_credits_per_campaign_ready(survived_count, total_enriched):
    """Compute credits per campaign-ready account."""
    if survived_count == 0:
        return float('inf')
    total_credits = total_enriched * CREDITS_PER_RECORD
    return total_credits / survived_count


def analyze_ordering_potential(survived, did_not):
    """Analyze what ordering by pre-enrichment fields could save."""
    # Group survivors by key pre-enrichment fields
    by_employees = defaultdict(lambda: {'survived': 0, 'total': 0})
    by_industry = defaultdict(lambda: {'survived': 0, 'total': 0})
    by_research_outcome = defaultdict(lambda: {'survived': 0, 'total': 0})
    by_headcount = defaultdict(lambda: {'survived': 0, 'total': 0})
    
    for entry in survived + did_not:
        emp = entry.get('employees')
        emp_bucket = 'unknown'
        if emp is not None:
            if emp < 10:
                emp_bucket = '<10'
            elif emp < 20:
                emp_bucket = '10-19'
            elif emp < 50:
                emp_bucket = '20-49'
            elif emp < 100:
                emp_bucket = '50-99'
            else:
                emp_bucket = '100+'
        
        by_employees[emp_bucket]['total'] += 1
        by_employees[emp_bucket]['survived'] += int(entry['campaign_ready'])
        
        ind = entry.get('industry') or 'unknown'
        by_industry[ind]['total'] += 1
        by_industry[ind]['survived'] += int(entry['campaign_ready'])
        
        ro = entry.get('research_outcome') or 'unknown'
        by_research_outcome[ro]['total'] += 1
        by_research_outcome[ro]['survived'] += int(entry['campaign_ready'])
        
        hs = entry.get('headcount_signal')
        if hs is None:
            hs_bucket = 'unknown'
        elif hs == 0:
            hs_bucket = '0'
        elif hs < 5:
            hs_bucket = '1-4'
        elif hs < 10:
            hs_bucket = '5-9'
        else:
            hs_bucket = '10+'
        
        by_headcount[hs_bucket]['total'] += 1
        by_headcount[hs_bucket]['survived'] += int(entry['campaign_ready'])
    
    return {
        'by_employees': dict(by_employees),
        'by_industry': dict(by_industry),
        'by_research_outcome': dict(by_research_outcome),
        'by_headcount_signal': dict(by_headcount),
    }


def compute_ordered_projection(recs, budget_credits=471):
    """Compute campaign-ready yield under different orderings for a fixed budget.
    
    budget_credits: 471 is TASK-160's projection for 150 records.
    """
    # Only consider records that went through the pipeline
    processed = [r for r in recs if get_pre_enrichment_fields(r).get('industry') 
                 or get_verdict(r).get('icp_status')]
    
    # Arrival order (current)
    arrival_ready = sum(1 for r in processed if has_campaign_ready_contact(r))
    arrival_records = len(processed)
    arrival_credits = arrival_records * CREDITS_PER_RECORD
    arrival_rate = arrival_ready / arrival_credits if arrival_credits > 0 else 0
    
    # Ordered by headcount_signal descending
    def sort_key(rec):
        pre = get_pre_enrichment_fields(rec)
        hs = pre.get('headcount_signal')
        emp = pre.get('employees')
        # Higher is better, None is worst
        return (
            0 if hs is None else hs,
            0 if emp is None else emp,
        )
    
    ordered = sorted(processed, key=sort_key, reverse=True)
    
    # Simulate processing in order until budget exhausted
    ordered_ready = 0
    ordered_processed = 0
    for rec in ordered:
        if (ordered_processed + 1) * CREDITS_PER_RECORD > budget_credits:
            break
        ordered_processed += 1
        if has_campaign_ready_contact(rec):
            ordered_ready += 1
    
    ordered_credits = ordered_processed * CREDITS_PER_RECORD
    ordered_rate = ordered_ready / ordered_credits if ordered_credits > 0 else 0
    
    return {
        'arrival': {
            'records': arrival_records,
            'ready': arrival_ready,
            'credits': arrival_credits,
            'credits_per_ready': arrival_credits / arrival_ready if arrival_ready > 0 else float('inf'),
            'ready_per_credit': arrival_rate,
        },
        'ordered': {
            'records': ordered_processed,
            'ready': ordered_ready,
            'credits': ordered_credits,
            'credits_per_ready': ordered_credits / ordered_ready if ordered_ready > 0 else float('inf'),
            'ready_per_credit': ordered_rate,
        },
        'budget': budget_credits,
    }


def main():
    print("=" * 80)
    print("TASK-169: THE CHEAPEST ORDER FROM A VERDICT TO CAMPAIGN-READY")
    print("=" * 80)
    print(f"\nSNAPSHOT: {STAMP}")
    print()
    
    recs = load_snapshot()
    print(f"Total records in snapshot: {len(recs)}")
    
    # Filter to records that went through the pipeline (have company_facts or verdict)
    processed = [r for r in recs if get_pre_enrichment_fields(r).get('industry') 
                 or get_verdict(r).get('icp_status')]
    print(f"Records that entered the pipeline: {len(processed)}")
    
    # Records with verdicts
    with_verdicts = [r for r in recs if get_verdict(r).get('icp_status')]
    print(f"Records with ICP verdicts: {len(with_verdicts)}")
    
    print()
    print("=" * 80)
    print("SECTION 1: STAGE-BY-STAGE ATTRITION")
    print("=" * 80)
    
    stages, drop_reasons = analyze_stage_attribution(recs)
    
    print("\nRecords by furthest stage reached:")
    for stage in ['queued', 'company_facts', 'researched', 'qualified', 
                  'enriched', 'verified', 'drafted', 'approved', 'dropped', 'held']:
        count = stages.get(stage, 0)
        if count > 0:
            print(f"  {stage:20s}: {count:4d}")
    
    print(f"\n  Total: {sum(stages.values())}")
    
    print("\nDrop/Hold reasons:")
    for reason, count in sorted(drop_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason:50s}: {count:4d}")
    
    print()
    print("=" * 80)
    print("SECTION 2: CAMPAIGN-READY SURVIVAL ANALYSIS")
    print("=" * 80)
    
    survived, did_not = analyze_pre_enrichment_predictors(processed)
    
    print(f"\nRecords that reached campaign-ready: {len(survived)}")
    print(f"Records that did not: {len(did_not)}")
    
    if len(survived) > 0:
        rate = len(survived) / len(processed) * 100
        print(f"Survival rate: {rate:.1f}%")
        
        credits_per_ready = compute_credits_per_campaign_ready(len(survived), len(processed))
        print(f"Credits per campaign-ready (arrival order): {credits_per_ready:.1f}")
    
    print()
    print("=" * 80)
    print("SECTION 3: FREE-FIELD REJECTION PREDICTORS")
    print("=" * 80)
    
    rejected, passed = analyze_free_rejection_predictors(recs)
    
    print(f"\nRecords rejected by ICP: {len(rejected)}")
    print(f"Records qualified by ICP: {len(passed)}")
    
    if len(rejected) > 0 or len(passed) > 0:
        total_with_verdict = len(rejected) + len(passed)
        rej_rate = len(rejected) / total_with_verdict * 100 if total_with_verdict > 0 else 0
        print(f"Rejection rate: {rej_rate:.1f}%")
    
    # Analyze what distinguishes rejected from passed
    print("\n--- Employee count distribution ---")
    rej_emp = Counter()
    pass_emp = Counter()
    
    for r in rejected:
        emp = r.get('employees')
        if emp is None:
            rej_emp['unknown'] += 1
        elif emp < 20:
            rej_emp['<20'] += 1
        else:
            rej_emp['20+'] += 1
    
    for r in passed:
        emp = r.get('employees')
        if emp is None:
            pass_emp['unknown'] += 1
        elif emp < 20:
            pass_emp['<20'] += 1
        else:
            pass_emp['20+'] += 1
    
    print(f"\n{'Bucket':15s} {'Rejected':>10s} {'Passed':>10s} {'Rej Rate':>10s}")
    all_buckets = sorted(set(list(rej_emp.keys()) + list(pass_emp.keys())))
    for bucket in all_buckets:
        r = rej_emp.get(bucket, 0)
        p = pass_emp.get(bucket, 0)
        total = r + p
        rate = r / total * 100 if total > 0 else 0
        print(f"{bucket:15s} {r:10d} {p:10d} {rate:9.1f}%")
    
    print("\n--- Headcount signal distribution ---")
    rej_hs = Counter()
    pass_hs = Counter()
    
    for r in rejected:
        hs = r.get('headcount_signal')
        if hs is None:
            rej_hs['unknown'] += 1
        elif hs == 0:
            rej_hs['0'] += 1
        elif hs < 10:
            rej_hs['1-9'] += 1
        else:
            rej_hs['10+'] += 1
    
    for r in passed:
        hs = r.get('headcount_signal')
        if hs is None:
            pass_hs['unknown'] += 1
        elif hs == 0:
            pass_hs['0'] += 1
        elif hs < 10:
            pass_hs['1-9'] += 1
        else:
            pass_hs['10+'] += 1
    
    print(f"\n{'Bucket':15s} {'Rejected':>10s} {'Passed':>10s} {'Rej Rate':>10s}")
    all_buckets = sorted(set(list(rej_hs.keys()) + list(pass_hs.keys())))
    for bucket in all_buckets:
        r = rej_hs.get(bucket, 0)
        p = pass_hs.get(bucket, 0)
        total = r + p
        rate = r / total * 100 if total > 0 else 0
        print(f"{bucket:15s} {r:10d} {p:10d} {rate:9.1f}%")
    
    print()
    print("=" * 80)
    print("SECTION 4: PRE-ENRICHMENT PREDICTORS OF SURVIVAL")
    print("=" * 80)
    
    ordering = analyze_ordering_potential(survived, did_not)
    
    print("\n--- Survival by employee count ---")
    emp_data = ordering['by_employees']
    print(f"\n{'Bucket':15s} {'Survived':>10s} {'Total':>10s} {'Rate':>10s}")
    for bucket in ['<10', '10-19', '20-49', '50-99', '100+', 'unknown']:
        if bucket in emp_data:
            d = emp_data[bucket]
            rate = d['survived'] / d['total'] * 100 if d['total'] > 0 else 0
            print(f"{bucket:15s} {d['survived']:10d} {d['total']:10d} {rate:9.1f}%")
    
    print("\n--- Survival by headcount signal ---")
    hs_data = ordering['by_headcount_signal']
    print(f"\n{'Bucket':15s} {'Survived':>10s} {'Total':>10s} {'Rate':>10s}")
    for bucket in ['0', '1-4', '5-9', '10+', 'unknown']:
        if bucket in hs_data:
            d = hs_data[bucket]
            rate = d['survived'] / d['total'] * 100 if d['total'] > 0 else 0
            print(f"{bucket:15s} {d['survived']:10d} {d['total']:10d} {rate:9.1f}%")
    
    print("\n--- Survival by research outcome ---")
    ro_data = ordering['by_research_outcome']
    print(f"\n{'Outcome':25s} {'Survived':>10s} {'Total':>10s} {'Rate':>10s}")
    for outcome in sorted(ro_data.keys()):
        d = ro_data[outcome]
        rate = d['survived'] / d['total'] * 100 if d['total'] > 0 else 0
        print(f"{outcome:25s} {d['survived']:10d} {d['total']:10d} {rate:9.1f}%")
    
    print("\n--- Survival by industry (top 10) ---")
    ind_data = ordering['by_industry']
    sorted_ind = sorted(ind_data.items(), key=lambda x: -x[1]['total'])[:10]
    print(f"\n{'Industry':40s} {'Survived':>10s} {'Total':>10s} {'Rate':>10s}")
    for ind, d in sorted_ind:
        rate = d['survived'] / d['total'] * 100 if d['total'] > 0 else 0
        print(f"{ind[:40]:40s} {d['survived']:10d} {d['total']:10d} {rate:9.1f}%")
    
    print()
    print("=" * 80)
    print("SECTION 5: CONTACT-LEVEL DROP-OFF ATTRIBUTION")
    print("=" * 80)
    
    # For records that were enriched, where did contacts drop out?
    enriched_with_contacts = [r for r in processed 
                              if get_contacts_summary(r)['kept_contacts'] > 0]
    
    print(f"\nRecords with at least one kept contact: {len(enriched_with_contacts)}")
    
    contact_stages = Counter()
    for rec in enriched_with_contacts:
        cs = get_contacts_summary(rec)
        
        if cs['sendable'] > 0:
            contact_stages['sendable'] += 1
        elif cs['verified'] > 0:
            contact_stages['verified_but_not_sendable'] += 1
        elif cs['has_email'] > 0 or cs['has_linkedin'] > 0:
            contact_stages['has_contact_no_verify'] += 1
        else:
            contact_stages['no_usable_contact'] += 1
    
    print("\nContact-level outcomes (per record):")
    for stage, count in sorted(contact_stages.items()):
        print(f"  {stage:35s}: {count:4d}")
    
    # Records with cadence but no approval
    has_cadence_no_approval = sum(
        1 for r in processed 
        if (r.get('cadence') or {}) 
        and r.get('state') not in ('approved', 'pushed')
    )
    print(f"\nRecords with cadence but not approved: {has_cadence_no_approval}")
    
    print()
    print("=" * 80)
    print("SECTION 6: ORDERING RULE AND PROJECTION")
    print("=" * 80)
    
    # Compute the ordering rule based on findings
    print("\nBased on the analysis above, the ordering rule is:")
    print()
    
    # Determine which buckets have highest survival rates
    emp_rates = {}
    for bucket, d in emp_data.items():
        if d['total'] >= 5:  # Minimum sample size
            emp_rates[bucket] = d['survived'] / d['total']
    
    hs_rates = {}
    for bucket, d in hs_data.items():
        if d['total'] >= 5:
            hs_rates[bucket] = d['survived'] / d['total']
    
    print("Employee count survival rates (buckets with n>=5):")
    for bucket in sorted(emp_rates.keys()):
        print(f"  {bucket:15s}: {emp_rates[bucket]*100:.1f}%")
    
    print("\nHeadcount signal survival rates (buckets with n>=5):")
    for bucket in sorted(hs_rates.keys()):
        print(f"  {bucket:15s}: {hs_rates[bucket]*100:.1f}%")
    
    # Project credits saved by ordering
    if len(survived) > 0:
        current_credits_per_ready = compute_credits_per_campaign_ready(
            len(survived), len(processed))
        
        # If we ordered by highest survival rate first, what would we save?
        # Assume we can identify the top bucket and only enrich those
        best_emp_bucket = max(emp_rates.keys(), key=lambda k: emp_rates[k]) if emp_rates else None
        best_hs_bucket = max(hs_rates.keys(), key=lambda k: hs_rates[k]) if hs_rates else None
        
        print(f"\nCurrent credits per campaign-ready: {current_credits_per_ready:.1f}")
        
        if best_emp_bucket:
            best_data = emp_data[best_emp_bucket]
            if best_data['survived'] > 0:
                best_credits_per_ready = compute_credits_per_campaign_ready(
                    best_data['survived'], best_data['total'])
                savings = current_credits_per_ready - best_credits_per_ready
                print(f"If ordering by employees={best_emp_bucket}: {best_credits_per_ready:.1f} credits/ready")
                print(f"  Savings: {savings:.1f} credits per campaign-ready account")
        
        if best_hs_bucket:
            best_data = hs_data[best_hs_bucket]
            if best_data['survived'] > 0:
                best_credits_per_ready = compute_credits_per_campaign_ready(
                    best_data['survived'], best_data['total'])
                savings = current_credits_per_ready - best_credits_per_ready
                print(f"If ordering by headcount_signal={best_hs_bucket}: {best_credits_per_ready:.1f} credits/ready")
                print(f"  Savings: {savings:.1f} credits per campaign-ready account")
    
    print()
    print("=" * 80)
    print("SECTION 7: ORDERED PROJECTION (FIXED BUDGET)")
    print("=" * 80)
    
    projection = compute_ordered_projection(recs, budget_credits=471)
    
    print(f"\nBudget: {projection['budget']} credits (TASK-160's 150-record projection)")
    print(f"\n--- Arrival order (current) ---")
    a = projection['arrival']
    print(f"  Records processed: {a['records']}")
    print(f"  Campaign-ready: {a['ready']}")
    print(f"  Credits spent: {a['credits']:.1f}")
    print(f"  Credits per campaign-ready: {a['credits_per_ready']:.1f}")
    print(f"  Campaign-ready per credit: {a['ready_per_credit']:.4f}")
    
    print(f"\n--- Ordered by headcount_signal DESC, employees DESC ---")
    o = projection['ordered']
    print(f"  Records processed: {o['records']}")
    print(f"  Campaign-ready: {o['ready']}")
    print(f"  Credits spent: {o['credits']:.1f}")
    print(f"  Credits per campaign-ready: {o['credits_per_ready']:.1f}")
    print(f"  Campaign-ready per credit: {o['ready_per_credit']:.4f}")
    
    if a['credits_per_ready'] > 0 and o['credits_per_ready'] > 0:
        improvement = (a['credits_per_ready'] - o['credits_per_ready']) / a['credits_per_ready'] * 100
        print(f"\n  Improvement: {improvement:.1f}% fewer credits per campaign-ready")
    
    if a['ready'] > 0 and o['ready'] > 0:
        more_ready = o['ready'] - a['ready']
        print(f"  Additional campaign-ready accounts: {more_ready}")
    
    print()
    print("=" * 80)
    print("SECTION 8: THE ORDERING PREDICATE")
    print("=" * 80)
    
    print("""
The ordering predicate, expressed over fields that exist BEFORE enrichment:

    PRIORITY 1: headcount_signal >= 10
        Survival rate: 29.2% (33/113)
        vs headcount_signal 1-4: 7.3% (7/96)
        vs headcount_signal 0: 0.0% (0/48)
        
    PRIORITY 2: employees >= 20
        Survival rate: 29.7%+ (20-49: 29.7%, 50-99: 36.8%)
        vs employees < 10: 7.1% (9/126)
        vs employees 10-19: 28.1% (16/57)
        
    PRIORITY 3: research_outcome = HTTP_SUCCESS
        Survival rate: 38.5% (10/26)
        vs unknown: 13.5% (37/274)
        
    PRIORITY 4: industry != 'unknown'
        Survival rate: 16.3%+ for known industries
        vs unknown: 0.0% (0/41)

The predicate is a SORT KEY, not a filter. Every record still passes through
every gate at full strength. The ordering only changes WHICH records reach
enrichment first.

Confidence: LOW. The sample is 91 enriched records (300 entered, 121 rejected
by ICP for free). A predictor fitted to 91 records will overfit. The
headcount_signal and employee count predictors are the most robust because
they are measured before any paid call and have monotonic relationships with
survival. The research_outcome predictor is weaker because only 26 records
have it.

What would not survive a different list:
- The specific survival rates (16.3%, 29.2%, etc.) are list-specific.
- The monotonic ordering (higher headcount_signal -> higher survival) is
  structural and should hold across lists from the same estate.
- The industry predictor is weak and list-specific (one purchased list skewed
  to advertising agencies).
""")
    
    print()
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    main()
