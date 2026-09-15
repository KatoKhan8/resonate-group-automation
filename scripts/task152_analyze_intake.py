#!/usr/bin/env python3
"""TASK-152: Measure the intake pipeline's real cost and rate per stage.

Reads work/queue.snapshot.jsonl (read-only) and produces per-stage counts,
terminal states with reasons, per-record costs, and a 250-batch projection.
"""
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
STAMP_FILE = os.path.join(ROOT, "work", "queue.snapshot.STAMP")


def load_stamp():
    with open(STAMP_FILE, encoding="utf-8") as f:
        return f.read().strip()


def load_records():
    records = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def count_log_steps(rec):
    """Count occurrences of each step in the record's log."""
    steps = Counter()
    for entry in (rec.get("log") or []):
        steps[entry.get("step", "unknown")] += 1
    return steps


def count_provider_calls(rec):
    """Count provider-level calls from verification results and enrich log."""
    calls = Counter()
    for contact in (rec.get("contacts") or []):
        # Verification providers
        verif = contact.get("verification") or {}
        for result_key, result_val in (verif.get("results") or {}).items():
            calls[f"verify:{result_key}"] += 1
        # MX check
        if contact.get("mx"):
            calls["mx_check"] += 1
    return calls


def count_model_calls(rec):
    """Count model (LLM) calls from log steps that are known model stages."""
    model_steps = {"draft", "linkedin_note", "reply_draft"}
    model_count = 0
    model_details = Counter()
    for entry in (rec.get("log") or []):
        step = entry.get("step", "")
        if step in model_steps:
            attempts = entry.get("attempts", 1)
            model_count += attempts
            model_details[step] += attempts
    return model_count, model_details


def count_enrich_provider_calls(rec):
    """Count enrichment-stage provider calls from the log."""
    enrich_calls = Counter()
    for entry in (rec.get("log") or []):
        step = entry.get("step", "")
        note = entry.get("note", "")
        if step == "enrich":
            # Parse the note for call type
            if "people-count" in note:
                enrich_calls["people-count"] += 1
            elif "decision-makers" in note:
                enrich_calls["decision-makers"] += 1
            elif "provider call" in note:
                enrich_calls["provider-calls-misc"] += 1
        elif step == "people-count":
            enrich_calls["people-count"] += 1
        elif step == "decision-makers":
            enrich_calls["decision-makers"] += 1
    return enrich_calls


def has_qualification(rec):
    """Whether the record has been through qualify."""
    return bool(rec.get("qualification"))


def has_contacts(rec):
    """Whether the record has any contacts."""
    return bool(rec.get("contacts"))


def has_verified_contacts(rec):
    """Whether the record has at least one verified+sendable contact."""
    for c in (rec.get("contacts") or []):
        v = c.get("verification") or {}
        if v.get("state") == "verified" and c.get("sendable"):
            return True
    return False


def has_cadence(rec):
    """Whether the record has a cadence (drafted messages)."""
    return bool(rec.get("cadence"))


def has_approvals(rec):
    """Whether the record has approved messages."""
    for entry in (rec.get("log") or []):
        if entry.get("step") == "approved":
            return True
    return False


def get_icp_status(rec):
    """Get ICP verdict status from qualification."""
    q = rec.get("qualification") or {}
    verdict = q.get("verdict") or {}
    return verdict.get("icp_status", "not_processed")


def get_icp_tier(rec):
    q = rec.get("qualification") or {}
    verdict = q.get("verdict") or {}
    return verdict.get("icp_tier", "unknown")


def get_drop_reason(rec):
    return rec.get("drop_reason") or ""


def get_company_facts(rec):
    return rec.get("company_facts") or {}


def count_contacts_total(rec):
    return len(rec.get("contacts") or [])


def count_contacts_excluded(rec):
    return len(rec.get("excluded") or [])


def main():
    stamp = load_stamp()
    records = load_records()
    n = len(records)

    print(f"SNAPSHOT: {stamp}")
    print(f"TOTAL RECORDS: {n}")
    print()

    # ---- 1. STATE DISTRIBUTION ----
    print("=" * 60)
    print("1. STATE DISTRIBUTION")
    print("=" * 60)
    state_counts = Counter(r.get("state", "unknown") for r in records)
    for state, count in state_counts.most_common():
        print(f"  {state:<16} {count:>5}  ({100*count/n:.1f}%)")
    print()

    # ---- 2. TERMINAL STATES AND DROP REASONS ----
    print("=" * 60)
    print("2. TERMINAL STATES AND DROP REASONS")
    print("=" * 60)
    dropped = [r for r in records if r.get("state") == "dropped"]
    drop_reasons = Counter(get_drop_reason(r) for r in dropped)
    print(f"  Total dropped: {len(dropped)}")
    for reason, count in drop_reasons.most_common():
        print(f"    {reason:<60} {count:>4}")
    print()

    held = [r for r in records if r.get("state") == "held"]
    print(f"  Total held: {len(held)}")
    # Check why held records are held
    for r in held[:5]:
        log_steps = count_log_steps(r)
        print(f"    {r['id']}: steps={dict(log_steps)}, "
              f"contacts={count_contacts_total(r)}, "
              f"verified={has_verified_contacts(r)}")
    print()

    # ---- 3. PIPELINE STAGE PROGRESSION ----
    print("=" * 60)
    print("3. PIPELINE STAGE PROGRESSION")
    print("=" * 60)

    # Stage markers
    has_ingested = n  # all records were ingested
    has_qualified = sum(1 for r in records if has_qualification(r))
    has_enriched = sum(1 for r in records if count_log_steps(r).get("enrich", 0) > 0
                       or count_log_steps(r).get("people-count", 0) > 0)
    has_verified = sum(1 for r in records if count_log_steps(r).get("verify", 0) > 0
                       or count_log_steps(r).get("verified", 0) > 0)
    has_drafts = sum(1 for r in records if count_log_steps(r).get("draft", 0) > 0)
    has_li_notes = sum(1 for r in records if count_log_steps(r).get("linkedin_note", 0) > 0)
    has_approved = sum(1 for r in records if has_approvals(r))

    print(f"  Ingested:          {has_ingested:>5}")
    print(f"  Qualified:         {has_qualified:>5}  ({100*has_qualified/n:.1f}%)")
    print(f"  Enriched:          {has_enriched:>5}  ({100*has_enriched/n:.1f}%)")
    print(f"  Verified:          {has_verified:>5}  ({100*has_verified/n:.1f}%)")
    print(f"  Drafted:           {has_drafts:>5}  ({100*has_drafts/n:.1f}%)")
    print(f"  LinkedIn notes:    {has_li_notes:>5}  ({100*has_li_notes/n:.1f}%)")
    print(f"  Approved:          {has_approved:>5}  ({100*has_approved/n:.1f}%)")
    print()

    # ---- 4. ICP VERDICT DISTRIBUTION ----
    print("=" * 60)
    print("4. ICP VERDICT DISTRIBUTION (among qualified)")
    print("=" * 60)
    qualified = [r for r in records if has_qualification(r)]
    icp_status = Counter(get_icp_status(r) for r in qualified)
    icp_tier = Counter(get_icp_tier(r) for r in qualified)
    print("  ICP Status:")
    for status, count in icp_status.most_common():
        print(f"    {status:<20} {count:>5}")
    print("  ICP Tier:")
    for tier, count in icp_tier.most_common():
        print(f"    {tier:<20} {count:>5}")
    print()

    # ---- 5. PER-RECORD PROVIDER COSTS ----
    print("=" * 60)
    print("5. PROVIDER COSTS (from verification results)")
    print("=" * 60)

    # Cost per verification provider call (from src/enrich.py COSTS)
    VERIFY_COSTS = {
        "contactout": 3,   # email-verifier
        "deliverable": 1,  # deliverable-verify
        "reoon": 1,        # reoon-verify
    }

    total_verify_credits = 0
    verify_provider_counts = Counter()
    records_with_verify = 0
    for r in records:
        rec_credits = 0
        for c in (r.get("contacts") or []):
            verif = c.get("verification") or {}
            for provider_name in (verif.get("results") or {}).keys():
                verify_provider_counts[provider_name] += 1
                rec_credits += VERIFY_COSTS.get(provider_name, 0)
        if rec_credits > 0:
            records_with_verify += 1
            total_verify_credits += rec_credits

    print(f"  Records with verification calls: {records_with_verify}")
    print(f"  Total verification credits spent: {total_verify_credits}")
    print(f"  Average per verified record: {total_verify_credits/max(records_with_verify,1):.1f}")
    print("  By provider:")
    for prov, count in verify_provider_counts.most_common():
        print(f"    {prov:<20} {count:>5} calls  x{VERIFY_COSTS.get(prov, '?')} cr = {count*VERIFY_COSTS.get(prov, 0)} cr")
    print()

    # ---- 6. PEOPLE DISCOVERY COSTS ----
    print("=" * 60)
    print("6. PEOPLE DISCOVERY (from log)")
    print("=" * 60)

    people_count_records = sum(1 for r in records
                               if count_log_steps(r).get("people-count", 0) > 0
                               or any("people-count" in (e.get("note", ""))
                                      for e in (r.get("log") or [])
                                      if e.get("step") == "enrich"))
    dm_records = sum(1 for r in records
                     if count_log_steps(r).get("decision-makers", 0) > 0
                     or any("decision-makers" in (e.get("note", ""))
                            for e in (r.get("log") or [])
                            if e.get("step") == "enrich"))

    # Count people-count notes
    pc_notes = Counter()
    dm_notes = Counter()
    for r in records:
        for e in (r.get("log") or []):
            if e.get("step") == "enrich":
                note = e.get("note", "")
                if "people-count" in note:
                    pc_notes["calls"] += 1
                elif "decision-makers" in note:
                    dm_notes["calls"] += 1

    print(f"  Records with people-count: {people_count_records}")
    print(f"  Records with decision-makers: {dm_records}")
    print(f"  Total people-count log entries: {pc_notes.get('calls', 0)}")
    print(f"  Total decision-makers log entries: {dm_notes.get('calls', 0)}")
    print(f"  people-count cost: 0 credits (free)")
    print(f"  decision-makers cost: 10 credits per call (5 profiles x 2)")
    print(f"  Total DM credits: {dm_notes.get('calls', 0) * 10}")
    print()

    # ---- 7. MODEL CALLS ----
    print("=" * 60)
    print("7. MODEL CALLS (LLM)")
    print("=" * 60)

    total_model_calls = 0
    total_model_details = Counter()
    records_with_model = 0
    model_calls_per_record = []
    for r in records:
        mc, details = count_model_calls(r)
        if mc > 0:
            records_with_model += 1
            total_model_calls += mc
            for k, v in details.items():
                total_model_details[k] += v
            model_calls_per_record.append(mc)

    print(f"  Records with model calls: {records_with_model}")
    print(f"  Total model calls (incl retries): {total_model_calls}")
    if model_calls_per_record:
        print(f"  Average per record (that has any): {sum(model_calls_per_record)/len(model_calls_per_record):.1f}")
        print(f"  Min: {min(model_calls_per_record)}, Max: {max(model_calls_per_record)}")
    print("  By step:")
    for step, count in total_model_details.most_common():
        print(f"    {step:<20} {count:>5}")
    print()

    # ---- 8. WHERE RECORDS STOP ----
    print("=" * 60)
    print("8. WHERE RECORDS STOP - FUNNEL ANALYSIS")
    print("=" * 60)

    # Categorise each record by where it halted
    stops = Counter()
    stop_details = defaultdict(Counter)
    for r in records:
        state = r.get("state", "unknown")
        steps = count_log_steps(r)
        qual = has_qualification(r)
        icp = get_icp_status(r)

        if state == "dropped":
            reason = get_drop_reason(r)
            if "ICP" in reason or "icp" in reason.lower() or "rejected" in reason.lower():
                stops["dropped:ICP gate"] += 1
            elif "suppressed" in reason:
                stops["dropped:suppressed"] += 1
            elif "no contact" in reason.lower() or "no person" in reason.lower():
                stops["dropped:no contacts found"] += 1
            else:
                stops[f"dropped:{reason[:50]}"] += 1
        elif state == "held":
            stops["held"] += 1
        elif state == "queued" and qual and icp == "rejected":
            stops["queued:ICP rejected (not yet dropped)"] += 1
        elif state == "queued" and qual and icp in ("review", "unknown"):
            stops["queued:needs review"] += 1
        elif state == "queued" and qual:
            stops["queued:qualified, awaiting enrich"] += 1
        elif state == "queued" and not qual:
            stops["queued:not yet qualified"] += 1
        elif state == "enriched":
            stops["enriched:awaiting verify"] += 1
        elif state == "verified" and not steps.get("draft"):
            stops["verified:awaiting draft"] += 1
        elif state == "drafted":
            stops["drafted:awaiting approval"] += 1
        elif state == "approved":
            stops["approved:ready to send"] += 1
        elif state == "pushed":
            stops["pushed:sent"] += 1
        else:
            stops[f"other:{state}"] += 1

    for stop, count in stops.most_common():
        print(f"  {stop:<55} {count:>5}")
    print()

    # ---- 9. CONTACT STATS ----
    print("=" * 60)
    print("9. CONTACT STATISTICS")
    print("=" * 60)
    total_contacts = sum(count_contacts_total(r) for r in records)
    total_excluded = sum(count_contacts_excluded(r) for r in records)
    total_sendable = sum(1 for r in records for c in (r.get("contacts") or [])
                         if c.get("sendable"))
    records_with_contacts = sum(1 for r in records if count_contacts_total(r) > 0)
    records_with_sendable = sum(1 for r in records
                                if any(c.get("sendable") for c in (r.get("contacts") or [])))
    print(f"  Records with any contacts: {records_with_contacts}")
    print(f"  Records with sendable contacts: {records_with_sendable}")
    print(f"  Total contacts: {total_contacts}")
    print(f"  Total excluded contacts: {total_excluded}")
    print(f"  Total sendable contacts: {total_sendable}")
    if records_with_contacts:
        print(f"  Avg contacts per record (with contacts): {total_contacts/records_with_contacts:.1f}")
    print()

    # ---- 10. COST PROJECTION FOR 250 BATCH ----
    print("=" * 60)
    print("10. COST PROJECTION: 250-ACCOUNT BATCH")
    print("=" * 60)

    # Derived from the 550 actual records
    # What fraction of records reach each stage?
    frac_qualified = has_qualified / n
    frac_enriched = has_enriched / n
    frac_verified = has_verified / n
    frac_drafts = has_drafts / n
    frac_approved = has_approved / n

    # Average costs per record that reaches each stage
    avg_verify_per_enriched = total_verify_credits / max(has_enriched, 1)
    avg_model_per_draft = total_model_calls / max(records_with_model, 1)

    # Credits per record (all 550)
    total_credits_all = total_verify_credits + dm_notes.get("calls", 0) * 10
    avg_credits_per_record = total_credits_all / n

    # Projected for 250
    proj = 250
    print(f"  Based on {n} records in snapshot ({stamp})")
    print()
    print(f"  Expected to qualify:       {int(proj * frac_qualified):>5}  ({frac_qualified*100:.1f}%)")
    print(f"  Expected to enrich:        {int(proj * frac_enriched):>5}  ({frac_enriched*100:.1f}%)")
    print(f"  Expected to verify:        {int(proj * frac_verified):>5}  ({frac_verified*100:.1f}%)")
    print(f"  Expected to draft:         {int(proj * frac_drafts):>5}  ({frac_drafts*100:.1f}%)")
    print(f"  Expected to approve:       {int(proj * frac_approved):>5}  ({frac_approved*100:.1f}%)")
    print()
    print(f"  Provider credits (verify): {proj * avg_verify_per_enriched:.0f}")
    print(f"  Provider credits (DM):     {proj * (dm_notes.get('calls',0)/n) * 10:.0f}")
    print(f"  Total provider credits:    {proj * avg_credits_per_record:.0f}")
    print(f"  Model calls:               {proj * (total_model_calls/n):.0f}")
    print()
    print(f"  Average provider credits per record (all {n}): {avg_credits_per_record:.2f}")
    print(f"  Average model calls per record (all {n}): {total_model_calls/n:.2f}")
    print()

    # ---- 11. DETERMINISTIC vs MODEL STAGES ----
    print("=" * 60)
    print("11. DETERMINISTIC vs MODEL STAGES")
    print("=" * 60)
    stages = [
        ("ingest", "deterministic", "CSV parse, domain normalise, dedupe, suppress check"),
        ("qualify/segments.classify", "deterministic", "Rule-based vertical/region/size from company_facts"),
        ("qualify/icp.score", "deterministic", "12-dimension rule-based ICP scoring from company_facts"),
        ("qualify/routing.plan", "deterministic", "Persona routing from segment + verdict"),
        ("qualify/strategy.for_company", "deterministic", "Messaging angles from segment + verdict"),
        ("qualify/dmplan.for_company", "deterministic", "Cost plan from verdict + persona plan"),
        ("enrich/people-count", "deterministic+provider", "Free ContactOut call, counts profiles"),
        ("enrich/decision-makers", "provider", "ContactOut paid search for DMs"),
        ("enrich/company-info", "provider", "ContactOut/Blitz company data fallback"),
        ("enrich/aiark-search", "provider", "AI Ark people search fallback"),
        ("verify/email", "provider", "ContactOut+Reoon+Deliverable email verification"),
        ("verify/mx", "deterministic+provider", "MX record lookup, provider classification"),
        ("draft/linkedin_note", "MODEL", "LLM generates connection request note"),
        ("draft/email", "MODEL", "LLM generates email body + subject"),
        ("lint", "deterministic", "Rule-based checks on generated drafts"),
        ("approve", "human", "Claude reviews and approves drafts"),
    ]
    for stage, kind, desc in stages:
        print(f"  {stage:<35} {kind:<25} {desc}")
    print()

    # ---- 12. ICP REJECTION DETAIL ----
    print("=" * 60)
    print("12. ICP REJECTION DETAIL")
    print("=" * 60)
    rejected = [r for r in records if get_icp_status(r) == "rejected"]
    print(f"  Records with ICP rejected verdict: {len(rejected)}")

    # Why rejected? Look at company_facts for common reasons
    reject_reasons = Counter()
    for r in rejected:
        facts = get_company_facts(r)
        flags = facts.get("icp_flags") or []
        for flag in flags:
            reject_reasons[flag] += 1
        if not flags:
            # Check the log for ICP notes
            for e in (r.get("log") or []):
                if e.get("step") == "icp":
                    reject_reasons[e.get("note", "unknown")[:80]] += 1

    print("  Rejection reasons (from icp_flags and log):")
    for reason, count in reject_reasons.most_common(15):
        print(f"    {reason:<70} {count:>4}")
    print()

    # ---- 13. BATCH SIZE RECOMMENDATION ----
    print("=" * 60)
    print("13. RECOMMENDED NEXT BATCH SIZE")
    print("=" * 60)
    # How many of the 20,944 are left?
    remaining_pool = 20944 - n
    print(f"  Total pool: 20,944 domains")
    print(f"  Already in queue: {n}")
    print(f"  Remaining unqueued: {remaining_pool}")
    print()

    # Yield analysis: of the 550, how many become sendable?
    sendable_count = records_with_sendable
    approved_count = sum(1 for r in records if r.get("state") in ("approved", "pushed"))
    print(f"  Yield from {n} records:")
    print(f"    Sendable contacts found: {sendable_count} ({100*sendable_count/n:.1f}%)")
    print(f"    Approved for sending:    {approved_count} ({100*approved_count/n:.1f}%)")
    print()

    # Cost to process 250
    cost_250 = 250 * avg_credits_per_record
    model_250 = 250 * (total_model_calls / n)
    print(f"  Projected cost for 250 batch:")
    print(f"    Provider credits: {cost_250:.0f}")
    print(f"    Model calls: {model_250:.0f}")
    print(f"    Expected sendable: {250 * sendable_count / n:.0f}")
    print(f"    Expected approved: {250 * approved_count / n:.0f}")
    print()

    # Recommendation
    # The constraint is credits and model calls; the yield determines value
    yield_rate = sendable_count / n if n else 0
    if yield_rate > 0:
        batch_for_50_sendable = 50 / yield_rate
        batch_for_100_sendable = 100 / yield_rate
    else:
        batch_for_50_sendable = float('inf')
        batch_for_100_sendable = float('inf')

    print(f"  To get ~50 sendable contacts:  {batch_for_50_sendable:.0f} records")
    print(f"  To get ~100 sendable contacts: {batch_for_100_sendable:.0f} records")
    print(f"  Credits for 250 batch: {cost_250:.0f}")
    print(f"  Credits for 500 batch: {500 * avg_credits_per_record:.0f}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
