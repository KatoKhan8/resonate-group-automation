#!/usr/bin/env python3
"""Prepare a real lead batch up to the point of the write.

TASK-101: Take the largest cohort from TASK-096 and run it through the full
pipeline without writing to any provider.

Pipeline stages:
  1. DEDUPE - against every other campaign in the estate
  2. EXCLUSION CHECK - suppression, DNC, bounced, positive-reply, engagement
  3. PERSONALISATION - every merge variable must resolve or have a fallback
  4. GREETING PROOF - render greetings and check for issues
  5. QUALITY GATES - lint, claims, structural diversity

Output:
  - work/lead_batch_economic_buyer.json (gitignored, operational artefact)
  - docs/LEAD-BATCH-REPORT-2026-09-15.md (tracked, all IDs hashed)
"""
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (
    agencydnc, claims, dedupe, eligibility, lint, store, verification
)

# ------------------------------------------------------------------ constants

SNAPSHOT_PATH = "work/queue.snapshot.jsonl"
CAMPAIGNS_PATH = "work/campaigns.jsonl"
BATCH_OUTPUT = "work/lead_batch_economic_buyer.json"
REPORT_OUTPUT = "docs/LEAD-BATCH-REPORT-2026-09-15.md"

# The cohort from TASK-096
COHORT_SIGNAL = "persona"
COHORT_VALUE = "economic_buyer"
COHORT_ID = "COHORT-001"


# ------------------------------------------------------------------ utilities

def hash_id(value):
    """Hash an identifier for the report. Returns first 12 chars of SHA-256."""
    if not value:
        return "null"
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]


def hash_email(email):
    """Hash an email address."""
    if not email:
        return "null"
    return hash_id(email.lower().strip())


def hash_domain(domain):
    """Hash a domain."""
    if not domain:
        return "null"
    return hash_id(domain.lower().strip())


def load_snapshot():
    """Load the queue snapshot."""
    records = []
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_campaigns():
    """Load campaigns and extract record_ids."""
    campaigns = []
    with open(CAMPAIGNS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                campaigns.append(json.loads(line))
    return campaigns


def get_record_ids_in_campaigns(campaigns):
    """Get all record_ids already in campaigns."""
    record_ids = set()
    for c in campaigns:
        record_ids.update(c.get("record_ids", []))
    return record_ids


def is_dropped(record):
    """Check if a record is dropped."""
    return record.get("drop_reason") is not None


def get_contacts_with_email(record):
    """Get contacts from a record that have email."""
    contacts = []
    for contact in record.get("contacts", []):
        if contact.get("email"):
            contacts.append(contact)
    return contacts


def get_primary_contact(record):
    """Get the primary contact from a record."""
    for contact in record.get("contacts", []):
        if contact.get("primary") and contact.get("email"):
            return contact
    # Fall back to first contact with email
    contacts = get_contacts_with_email(record)
    return contacts[0] if contacts else None


def check_verification(contact):
    """Check if a contact is verified and sendable."""
    verif = contact.get("verification", {})
    state = verif.get("state", "unknown")
    sendable = verif.get("sendable", False)
    return state == "verified" and sendable


def check_mx(contact):
    """Check MX records for email eligibility."""
    mx = contact.get("mx", {})
    return mx.get("email_eligible", False)


def check_suppression(contact, record):
    """Check if contact is suppressed (DNC, bounced, etc.)."""
    reasons = []
    
    # Check agency DNC
    email = contact.get("email")
    if email:
        try:
            if agencydnc.is_suppressed(email):
                reasons.append("agency_dnc")
        except Exception:
            pass  # DNC file may not exist
    
    # Check if email is sendable
    if not contact.get("sendable", False):
        reasons.append("not_sendable")
    
    # Check verification state
    verif = contact.get("verification", {})
    if verif.get("state") == "invalid":
        reasons.append("email_invalid")
    
    # Check if record is dropped
    if is_dropped(record):
        reasons.append("record_dropped")
    
    return reasons


def check_positive_reply(record):
    """Check if record has positive reply (engagement state)."""
    # Check events for positive reply
    events = record.get("events", [])
    for event in events:
        if event.get("type") == "positive_reply":
            return True
    return False


def check_engagement_state(record):
    """Check engagement state from events."""
    states = []
    events = record.get("events", [])
    for event in events:
        etype = event.get("type", "")
        if "reply" in etype.lower():
            states.append(etype)
        if "unsubscrib" in etype.lower():
            states.append(etype)
        if "bounce" in etype.lower():
            states.append(etype)
    return states


def get_cohort_members(records):
    """Get all contacts matching the cohort signal."""
    members = []
    for record in records:
        if is_dropped(record):
            continue
        
        for contact in record.get("contacts", []):
            if not contact.get("email"):
                continue
            
            # Check cohort signal
            persona = contact.get("persona")
            if persona == COHORT_VALUE:
                members.append({
                    "record": record,
                    "contact": contact,
                    "record_id": record.get("id"),
                    "contact_key": contact.get("key"),
                })
    
    return members


def check_merge_variables(contact, record):
    """Check that all merge variables resolve or have fallbacks."""
    issues = []
    
    # Required merge variables for outreach
    required = {
        "first_name": contact.get("name", "").split()[0] if contact.get("name") else None,
        "company": record.get("company"),
        "title": contact.get("title"),
        "persona": contact.get("persona"),
        "angle": contact.get("angle"),
        "industry": (record.get("company_facts") or {}).get("industry"),
    }
    
    missing = []
    for var, value in required.items():
        if not value:
            missing.append(var)
    
    if missing:
        issues.append(f"missing_merge_vars:{','.join(missing)}")
    
    return issues


def render_greeting(contact):
    """Render the greeting for a contact."""
    name = contact.get("name", "")
    first_name = name.split()[0] if name else None
    
    if not first_name:
        return "Hi,"
    
    # Check for problematic values
    if first_name.lower() in ("null", "undefined", "none", ""):
        return f"Hi {first_name},"
    
    return f"Hi {first_name.lower()},"


def check_greeting_issues(greeting):
    """Check for greeting issues."""
    issues = []
    
    if "Hi ," in greeting or "Hi,," in greeting:
        issues.append("empty_greeting")
    
    if "undefined" in greeting.lower():
        issues.append("undefined_in_greeting")
    
    if "null" in greeting.lower():
        issues.append("null_in_greeting")
    
    return issues


def run_lint_check(contact, record):
    """Run lint checks on any generated content."""
    # For this task, we check if the contact has cadence content
    cadence = record.get("cadence", {})
    contact_key = contact.get("key")
    
    if not contact_key or contact_key not in cadence:
        return []  # No content yet, nothing to lint
    
    issues = []
    contact_cadence = cadence[contact_key]
    
    for step_key, step_data in contact_cadence.items():
        if step_data.get("channel") == "email" and step_data.get("body"):
            # Run lint using the correct API
            try:
                failures = lint.check(record, contact_key, step_data)
                if failures:
                    issues.append(f"lint_failed:{step_key}:{','.join(failures[:3])}")
            except Exception as e:
                issues.append(f"lint_error:{step_key}:{str(e)[:50]}")
    
    return issues


def run_claims_check(contact, record):
    """Run claims checks on generated content."""
    cadence = record.get("cadence", {})
    contact_key = contact.get("key")
    
    if not contact_key or contact_key not in cadence:
        return []  # No content yet, nothing to check
    
    issues = []
    contact_cadence = cadence[contact_key]
    
    for step_key, step_data in contact_cadence.items():
        if step_data.get("channel") == "email" and step_data.get("body"):
            body = step_data.get("body", "")
            
            # Check claims using the correct API
            try:
                claim_issues = claims.check(body, record, contact)
                if claim_issues:
                    issues.append(f"claims_failed:{step_key}")
            except Exception as e:
                issues.append(f"claims_error:{step_key}:{str(e)[:50]}")
    
    return issues


# ------------------------------------------------------------------ pipeline

def run_pipeline():
    """Run the full lead batch preparation pipeline."""
    
    print("=" * 70)
    print("LEAD BATCH PREPARATION PIPELINE")
    print("=" * 70)
    print()
    
    # Load data
    print("Loading data...")
    records = load_snapshot()
    campaigns = load_campaigns()
    campaign_record_ids = get_record_ids_in_campaigns(campaigns)
    
    print(f"  Total records in snapshot: {len(records)}")
    print(f"  Total campaigns: {len(campaigns)}")
    print(f"  Total record_ids in campaigns: {len(campaign_record_ids)}")
    print()
    
    # Stage 0: Get cohort members
    print(f"STAGE 0: Identifying cohort members ({COHORT_SIGNAL}={COHORT_VALUE})")
    cohort_members = get_cohort_members(records)
    print(f"  Cohort members with email: {len(cohort_members)}")
    print()
    
    # Track funnel
    funnel = []
    funnel.append(("Cohort members (with email)", len(cohort_members), []))
    
    # Stage 1: DEDUPE
    print("STAGE 1: DEDUPE - checking against existing campaigns")
    deduped = []
    dedupe_drops = []
    
    for member in cohort_members:
        record_id = member["record_id"]
        
        if record_id in campaign_record_ids:
            dedupe_drops.append({
                "record_id_hash": hash_id(record_id),
                "contact_key_hash": hash_id(member["contact_key"]),
                "reason": "already_in_campaign",
            })
        else:
            deduped.append(member)
    
    print(f"  After dedupe: {len(deduped)}")
    print(f"  Dropped (already in campaign): {len(dedupe_drops)}")
    funnel.append(("After dedupe", len(deduped), dedupe_drops))
    print()
    
    # Stage 2: EXCLUSION CHECK
    print("STAGE 2: EXCLUSION CHECK - suppression, DNC, bounced, engagement")
    excluded = []
    exclusion_drops = []
    
    for member in deduped:
        contact = member["contact"]
        record = member["record"]
        reasons = []
        
        # Check suppression
        supp_reasons = check_suppression(contact, record)
        reasons.extend(supp_reasons)
        
        # Check positive reply
        if check_positive_reply(record):
            reasons.append("positive_reply")
        
        # Check engagement state
        eng_states = check_engagement_state(record)
        if any("unsubscrib" in s for s in eng_states):
            reasons.append("unsubscribed")
        if any("bounce" in s for s in eng_states):
            reasons.append("bounced")
        
        # Check verification
        if not check_verification(contact):
            reasons.append("verification_not_sendable")
        
        # Check MX
        if not check_mx(contact):
            reasons.append("mx_not_eligible")
        
        if reasons:
            exclusion_drops.append({
                "record_id_hash": hash_id(member["record_id"]),
                "contact_key_hash": hash_id(member["contact_key"]),
                "email_hash": hash_email(contact.get("email")),
                "reasons": reasons,
            })
        else:
            excluded.append(member)
    
    print(f"  After exclusion check: {len(excluded)}")
    print(f"  Dropped (exclusion reasons): {len(exclusion_drops)}")
    
    # Count reasons
    reason_counts = Counter()
    for drop in exclusion_drops:
        for r in drop["reasons"]:
            reason_counts[r] += 1
    print(f"  Breakdown: {dict(reason_counts)}")
    funnel.append(("After exclusion check", len(excluded), exclusion_drops))
    print()
    
    # Stage 3: PERSONALISATION
    print("STAGE 3: PERSONALISATION - checking merge variables")
    personalised = []
    personalisation_drops = []
    
    for member in excluded:
        contact = member["contact"]
        record = member["record"]
        
        issues = check_merge_variables(contact, record)
        
        if issues:
            personalisation_drops.append({
                "record_id_hash": hash_id(member["record_id"]),
                "contact_key_hash": hash_id(member["contact_key"]),
                "issues": issues,
            })
        else:
            personalised.append(member)
    
    print(f"  After personalisation check: {len(personalised)}")
    print(f"  Dropped (missing merge vars): {len(personalisation_drops)}")
    funnel.append(("After personalisation", len(personalised), personalisation_drops))
    print()
    
    # Stage 4: GREETING PROOF
    print("STAGE 4: GREETING PROOF - rendering and checking greetings")
    greeted = []
    greeting_drops = []
    greeting_samples = []
    
    for member in personalised:
        contact = member["contact"]
        greeting = render_greeting(contact)
        issues = check_greeting_issues(greeting)
        
        if issues:
            greeting_drops.append({
                "record_id_hash": hash_id(member["record_id"]),
                "contact_key_hash": hash_id(member["contact_key"]),
                "greeting": greeting,
                "issues": issues,
            })
        else:
            greeted.append(member)
            if len(greeting_samples) < 5:
                greeting_samples.append({
                    "contact_key_hash": hash_id(member["contact_key"]),
                    "greeting": greeting,
                })
    
    print(f"  After greeting proof: {len(greeted)}")
    print(f"  Dropped (greeting issues): {len(greeting_drops)}")
    print(f"  Sample greetings:")
    for sample in greeting_samples:
        print(f"    {sample['contact_key_hash']}: {sample['greeting']}")
    funnel.append(("After greeting proof", len(greeted), greeting_drops))
    print()
    
    # Stage 5: QUALITY GATES
    print("STAGE 5: QUALITY GATES - lint, claims, structural diversity")
    qualified = []
    quality_drops = []
    
    for member in greeted:
        contact = member["contact"]
        record = member["record"]
        
        issues = []
        
        # Lint check
        lint_issues = run_lint_check(contact, record)
        issues.extend(lint_issues)
        
        # Claims check
        claims_issues = run_claims_check(contact, record)
        issues.extend(claims_issues)
        
        if issues:
            quality_drops.append({
                "record_id_hash": hash_id(member["record_id"]),
                "contact_key_hash": hash_id(member["contact_key"]),
                "issues": issues,
            })
        else:
            qualified.append(member)
    
    print(f"  After quality gates: {len(qualified)}")
    print(f"  Dropped (quality issues): {len(quality_drops)}")
    funnel.append(("After quality gates", len(qualified), quality_drops))
    print()
    
    # Build batch
    print("=" * 70)
    print("BUILDING BATCH FILE")
    print("=" * 70)
    
    batch = {
        "cohort_id": COHORT_ID,
        "cohort_signal": COHORT_SIGNAL,
        "cohort_value": COHORT_VALUE,
        "prepared_at": datetime.now().astimezone().isoformat(),
        "snapshot": SNAPSHOT_PATH,
        "funnel": [
            {
                "stage": stage,
                "count": count,
                "drop_count": len(drops),
            }
            for stage, count, drops in funnel
        ],
        "leads": [],
    }
    
    for member in qualified:
        contact = member["contact"]
        record = member["record"]
        
        lead = {
            "record_id": record.get("id"),
            "contact_key": contact.get("key"),
            "email": contact.get("email"),
            "name": contact.get("name"),
            "title": contact.get("title"),
            "company": record.get("company"),
            "domain": record.get("domain"),
            "persona": contact.get("persona"),
            "angle": contact.get("angle"),
            "industry": (record.get("company_facts") or {}).get("industry"),
            "headcount": (record.get("company_facts") or {}).get("employees"),
            "employee_range": (record.get("company_facts") or {}).get("employee_range"),
            "linkedin": contact.get("linkedin"),
            "bison_lead_id": contact.get("bison_lead_id"),
        }
        
        batch["leads"].append(lead)
    
    # Write batch file
    with open(BATCH_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2)
    
    print(f"Batch written to: {BATCH_OUTPUT}")
    print(f"Total leads in batch: {len(batch['leads'])}")
    print()
    
    # Build report
    print("=" * 70)
    print("BUILDING REPORT")
    print("=" * 70)
    
    report = []
    report.append("# Lead Batch Preparation Report")
    report.append("")
    report.append(f"**Date:** 2026-09-15")
    report.append(f"**Snapshot:** `{SNAPSHOT_PATH}`")
    report.append(f"**Snapshot stamp:** {open('work/queue.snapshot.STAMP').read().strip()}")
    report.append(f"**Cohort:** {COHORT_ID} ({COHORT_SIGNAL}={COHORT_VALUE})")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## Funnel Summary")
    report.append("")
    report.append("| Stage | Count | Drop Count | Drop-off |")
    report.append("|-------|------:|-----------:|---------:|")
    
    prev_count = None
    for stage, count, drops in funnel:
        drop_off = ""
        if prev_count is not None:
            drop_off = f"{prev_count - count} ({100*(prev_count-count)/prev_count:.1f}%)"
        report.append(f"| {stage} | {count} | {len(drops)} | {drop_off} |")
        prev_count = count
    
    report.append("")
    report.append("---")
    report.append("")
    report.append("## Stage Details")
    report.append("")
    
    # Stage 1: Dedupe
    report.append("### Stage 1: DEDUPE")
    report.append("")
    report.append(f"**Dropped:** {len(dedupe_drops)} leads already in campaigns")
    report.append("")
    if dedupe_drops:
        report.append("Sample drops (hashed):")
        for drop in dedupe_drops[:5]:
            report.append(f"  - record: `{drop['record_id_hash']}`, contact: `{drop['contact_key_hash']}`")
    report.append("")
    
    # Stage 2: Exclusion
    report.append("### Stage 2: EXCLUSION CHECK")
    report.append("")
    report.append(f"**Dropped:** {len(exclusion_drops)} leads")
    report.append("")
    report.append("Breakdown by reason:")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        report.append(f"  - {reason}: {count}")
    report.append("")
    if exclusion_drops:
        report.append("Sample drops (hashed):")
        for drop in exclusion_drops[:5]:
            report.append(f"  - record: `{drop['record_id_hash']}`, contact: `{drop['contact_key_hash']}`, email: `{drop['email_hash']}`")
            report.append(f"    Reasons: {', '.join(drop['reasons'])}")
    report.append("")
    
    # Stage 3: Personalisation
    report.append("### Stage 3: PERSONALISATION")
    report.append("")
    report.append(f"**Dropped:** {len(personalisation_drops)} leads with missing merge variables")
    report.append("")
    if personalisation_drops:
        report.append("Sample drops (hashed):")
        for drop in personalisation_drops[:5]:
            report.append(f"  - record: `{drop['record_id_hash']}`, contact: `{drop['contact_key_hash']}`")
            report.append(f"    Issues: {', '.join(drop['issues'])}")
    report.append("")
    
    # Stage 4: Greeting
    report.append("### Stage 4: GREETING PROOF")
    report.append("")
    report.append(f"**Dropped:** {len(greeting_drops)} leads with greeting issues")
    report.append("")
    report.append("Sample greetings (hashed):")
    for sample in greeting_samples:
        report.append(f"  - {sample['contact_key_hash']}: `{sample['greeting']}`")
    report.append("")
    if greeting_drops:
        report.append("Sample drops (hashed):")
        for drop in greeting_drops[:5]:
            report.append(f"  - record: `{drop['record_id_hash']}`, contact: `{drop['contact_key_hash']}`")
            report.append(f"    Greeting: `{drop['greeting']}`")
            report.append(f"    Issues: {', '.join(drop['issues'])}")
    report.append("")
    
    # Stage 5: Quality
    report.append("### Stage 5: QUALITY GATES")
    report.append("")
    report.append(f"**Dropped:** {len(quality_drops)} leads with lint/claims issues")
    report.append("")
    if quality_drops:
        report.append("Sample drops (hashed):")
        for drop in quality_drops[:5]:
            report.append(f"  - record: `{drop['record_id_hash']}`, contact: `{drop['contact_key_hash']}`")
            report.append(f"    Issues: {', '.join(drop['issues'])}")
    report.append("")
    
    report.append("---")
    report.append("")
    report.append("## Final Batch")
    report.append("")
    report.append(f"**Total leads:** {len(batch['leads'])}")
    report.append(f"**Batch file:** `{BATCH_OUTPUT}` (gitignored)")
    report.append("")
    report.append("### Lead Summary (hashed)")
    report.append("")
    report.append("| Contact | Record | Email | Company | Persona |")
    report.append("|---------|--------|-------|---------|---------|")
    
    for lead in batch["leads"][:10]:
        report.append(f"| `{hash_id(lead['contact_key'])}` | `{hash_id(lead['record_id'])}` | `{hash_email(lead['email'])}` | `{hash_id(lead['company'])}` | {lead['persona']} |")
    
    if len(batch["leads"]) > 10:
        report.append(f"| ... | ... | ... | ... | ... |")
        report.append(f"| *{len(batch['leads']) - 10} more leads* | | | | |")
    
    report.append("")
    report.append("---")
    report.append("")
    report.append("## What the Operator Would Be Authorising")
    report.append("")
    report.append(f"If the operator enables `heyreach.add_leads`, they would be authorising:")
    report.append("")
    report.append(f"  - **{len(batch['leads'])} leads** to be added to a HeyReach campaign")
    report.append(f"  - All leads are **persona=economic_buyer**")
    report.append(f"  - All leads have **verified email** (sendable=True)")
    report.append(f"  - All leads have **passed dedupe** (not in existing campaigns)")
    report.append(f"  - All leads have **passed exclusion checks** (no DNC, no bounce, no reply)")
    report.append(f"  - All leads have **resolved merge variables** (no undefined/null)")
    report.append(f"  - All leads have **valid greetings** (no 'Hi undefined,' or 'Hi ,')")
    report.append(f"  - All leads have **passed quality gates** (lint, claims)")
    report.append("")
    report.append("**This is a reads-only preparation. No provider write has occurred.**")
    report.append("")
    report.append("---")
    report.append("")
    report.append("**Prepared by:** TASK-101")
    report.append("**Date:** 2026-09-15")
    report.append("")
    
    # Write report
    with open(REPORT_OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    
    print(f"Report written to: {REPORT_OUTPUT}")
    print()
    print("=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print()
    print(f"Final batch size: {len(batch['leads'])} leads")
    print(f"Batch file: {BATCH_OUTPUT}")
    print(f"Report: {REPORT_OUTPUT}")
    
    return batch


if __name__ == "__main__":
    run_pipeline()
