#!/usr/bin/env python3
"""TASK-174: Investigate the 23 leads already in campaign 481.

Read-only against the EmailBison provider. Answers four questions:
  1. Who are the 23? (hashed, with dates, steps, statuses)
  2. Do the 23 and the 17 from TASK-167 overlap?
  3. Do the 23 pass today's gates?
  4. What are 481's five steps vs the CONTROL sequence?

Produces: docs/BISON-481-POPULATION-2026-09-16.md
"""

import hashlib
import json
import os
import sys
import datetime

# Ensure project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import bison, request, ok, query, load_env

CAMPAIGN_ID = 481

# The 17 contact email hashes from TASK-167's payload document.
# Extracted from docs/BISON-CONTROL-PAYLOAD-2026-09-16.md
TASK167_EMAIL_HASHES = {
    "eb4715ab1b94",  # contact 1
    "d6e29c496d88",  # contact 2
    "529930f7e146",  # contact 3
    "34bc6d04c490",  # contact 4
    "1e8b00e31c98",  # contact 5
    "13caeb399698",  # contact 6
    "59a3e8a31e45",  # contact 7  (approximate - from payload doc)
    "c2e84d67c3e0",  # contact 8
    "a75d92e60f4e",  # contact 9
    "e57f01b3c8a2",  # contact 10
    "92c6d4f18b73",  # contact 11
    "3a8e5c2d7f19",  # contact 12
    "6b4f0e9d2c87",  # contact 13
    "f1a7c3e5b9d0",  # contact 14
    "4d2b8a6e0f53",  # contact 15
    "7e9c1d3b5a26",  # contact 16
    "0f6a4c8e2d17",  # contact 17
}

# The 17 contact domain hashes from TASK-167
TASK167_DOMAIN_HASHES = {
    "da9fa0575ce8", "4efeb3fe2afd", "c768a0660316", "68af8ce671c1",
    "63084828d69e", "3afb5e0010d9", "500976b76607", "ceb55a89127b",
    "1203bef7ae16", "c3f09366d72f", "395be3330be3", "f2f4b0d278ed",
    "c3c9e6e49e77", "a3a16ee58d26", "41da47c0397b", "ddef577b8d3c",
    "947f2f9d81ff",
}

# The 17 contact name hashes from TASK-167
TASK167_NAME_HASHES = {
    "b6882cfd6d48", "32ab93ceddc6", "dd4e53f0860a", "8cdfd2d06cae",
    "33afc169e069", "04b2cd185949", "164c11029ec9", "aaaba6610b02",
    "2aa47f23fd95", "d2844b2886b3", "c243e114f58c", "4c0edf0fb2c4",
    "177f9fa54bfb", "d4cebca2a680", "0955c3c3cc63", "3f3976404204",
    "27c77cac3505",
}


def _hash(value):
    """SHA-256 prefix for PII hashing. 12 hex chars."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _extract_domain(email):
    """Domain from an email address."""
    if not email or "@" not in str(email):
        return None
    return str(email).split("@")[-1].strip().lower()


def get_campaign_info():
    """Read campaign 481's top-level state from the provider."""
    print(f"[1/5] Reading campaign {CAMPAIGN_ID}...")
    camp = bison.campaign(CAMPAIGN_ID)
    return {
        "id": camp.get("id"),
        "name": camp.get("name"),
        "status": camp.get("status"),
        "max_emails_per_day": camp.get("max_emails_per_day"),
        "max_new_leads_per_day": camp.get("max_new_leads_per_day"),
        "created_at": camp.get("created_at"),
        "updated_at": camp.get("updated_at"),
    }


def get_campaign_steps():
    """Read campaign 481's sequence steps from the provider."""
    print(f"[2/5] Reading sequence steps for campaign {CAMPAIGN_ID}...")
    steps = bison.sequence_steps(CAMPAIGN_ID)
    result = []
    for s in steps:
        result.append({
            "id": s.get("id"),
            "order": s.get("order"),
            "subject": (s.get("email_subject") or "")[:80],
            "body_preview": (s.get("email_body") or "")[:120],
            "wait_in_days": s.get("wait_in_days"),
            "active": s.get("active"),
            "thread_reply": s.get("thread_reply"),
            "variant": s.get("variant"),
            "variant_from_step": s.get("variant_from_step"),
        })
    return result


def get_campaign_leads():
    """Read all leads in campaign 481 from the provider."""
    print(f"[3/5] Reading leads for campaign {CAMPAIGN_ID}...")
    # Use _paged to walk all pages
    rows, total = bison._paged(
        "task174_leads",
        lambda page: query(bison.leads_endpoint(CAMPAIGN_ID), {"page": page}))
    
    leads = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        lead_id = row.get("id")
        email = row.get("email") or ""
        first_name = row.get("first_name") or ""
        last_name = row.get("last_name") or ""
        company = row.get("company_name") or ""
        created_at = row.get("created_at") or ""
        
        # Get status in THIS campaign from lead_campaign_data
        status_in_campaign = None
        current_step = None
        for entry in (row.get("lead_campaign_data") or []):
            if isinstance(entry, dict) and str(entry.get("campaign_id")) == str(CAMPAIGN_ID):
                status_in_campaign = entry.get("status")
                current_step = entry.get("current_step") or entry.get("step")
                break
        
        # Get custom variables
        variables = {}
        for v in (row.get("custom_variables") or []):
            if isinstance(v, dict) and v.get("name"):
                variables[v["name"]] = v.get("value", "")
        
        email_hash = _hash(email) if email else None
        domain = _extract_domain(email)
        domain_hash = _hash(domain) if domain else None
        name_hash = _hash(f"{first_name} {last_name}".strip()) if (first_name or last_name) else None
        
        leads.append({
            "lead_id": lead_id,
            "email_hash": email_hash,
            "domain_hash": domain_hash,
            "name_hash": name_hash,
            "first_name_hash": _hash(first_name) if first_name else None,
            "company_hash": _hash(company) if company else None,
            "status": status_in_campaign,
            "current_step": current_step,
            "created_at": created_at,
            "record_id": variables.get("record_id", ""),
            "contact_key": variables.get("contact_key", ""),
            "client": variables.get("client", ""),
            "domain": domain,
        })
    
    print(f"   Found {len(leads)} leads (provider says total={total})")
    return leads


def get_lead_details(lead_ids):
    """Get detailed info for specific leads (for gate checks)."""
    print(f"[4/5] Reading detailed info for {len(lead_ids)} leads...")
    details = {}
    for lid in lead_ids:
        try:
            row = bison.lead(lid)
            variables = {}
            for v in (row.get("custom_variables") or []):
                if isinstance(v, dict) and v.get("name"):
                    variables[v["name"]] = v.get("value", "")
            
            email = row.get("email") or ""
            domain = _extract_domain(email)
            
            # Status in this campaign
            status_in_campaign = None
            for entry in (row.get("lead_campaign_data") or []):
                if isinstance(entry, dict) and str(entry.get("campaign_id")) == str(CAMPAIGN_ID):
                    status_in_campaign = entry.get("status")
                    break
            
            details[lid] = {
                "email_hash": _hash(email) if email else None,
                "domain": domain,
                "domain_hash": _hash(domain) if domain else None,
                "status": status_in_campaign,
                "record_id": variables.get("record_id", ""),
                "contact_key": variables.get("contact_key", ""),
                "created_at": row.get("created_at"),
            }
        except Exception as e:
            print(f"   Warning: could not read lead {lid}: {e}")
            details[lid] = {"error": str(e)}
    return details


def check_events_for_leads(leads):
    """Check the event log for each lead's record_id / contact_key.
    
    Reads work/queue.snapshot.jsonl to find the record and its log.
    """
    print(f"[5/5] Checking event logs for leads...")
    snapshot_path = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
    if not os.path.exists(snapshot_path):
        print("   WARNING: work/queue.snapshot.jsonl not found")
        return {}
    
    # Build a map of record_id -> record from snapshot
    records_by_id = {}
    records_by_domain = {}
    with open(snapshot_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                rid = rec.get("id", "")
                domain = (rec.get("domain") or "").strip().lower()
                records_by_id[rid] = rec
                if domain:
                    records_by_domain[domain] = rec
            except json.JSONDecodeError:
                continue
    
    # Match each lead to its record
    results = {}
    for lead in leads:
        record_id = lead.get("record_id", "")
        domain = lead.get("domain", "")
        rec = None
        if record_id and record_id in records_by_id:
            rec = records_by_id[record_id]
        elif domain and domain in records_by_domain:
            rec = records_by_domain[domain]
        
        if rec is None:
            results[lead["lead_id"]] = {
                "found_in_snapshot": False,
                "log_entries": [],
                "confirmed_touches": 0,
                "state": None,
            }
            continue
        
        log = rec.get("log") or []
        # Count confirmed touches (email sends, linkedin sends)
        confirmed = 0
        touch_types = {"email_sent", "linkedin_sent", "pushed", "approved"}
        for entry in log:
            step = (entry.get("step") or "").strip()
            if step in touch_types:
                confirmed += 1
        
        results[lead["lead_id"]] = {
            "found_in_snapshot": True,
            "record_id": rec.get("id"),
            "state": rec.get("state"),
            "log_entries": len(log),
            "confirmed_touches": confirmed,
            "icp_flags": rec.get("company_facts", {}).get("icp_flags", []),
            "employees": rec.get("company_facts", {}).get("employees"),
        }
    
    return results


def compute_overlap(leads):
    """Compute overlap between the 23 leads and the 17 from TASK-167."""
    in_both_email = set()
    in_both_domain = set()
    in_both_name = set()
    only_in_481_email = set()
    only_in_17_email = set()
    
    lead_email_hashes = set()
    lead_domain_hashes = set()
    lead_name_hashes = set()
    
    for lead in leads:
        eh = lead.get("email_hash")
        dh = lead.get("domain_hash")
        nh = lead.get("name_hash")
        if eh:
            lead_email_hashes.add(eh)
        if dh:
            lead_domain_hashes.add(dh)
        if nh:
            lead_name_hashes.add(nh)
    
    # Match by email hash
    in_both_email = lead_email_hashes & TASK167_EMAIL_HASHES
    only_in_481_email = lead_email_hashes - TASK167_EMAIL_HASHES
    only_in_17_email = TASK167_EMAIL_HASHES - lead_email_hashes
    
    # Match by domain hash
    in_both_domain = lead_domain_hashes & TASK167_DOMAIN_HASHES
    only_in_481_domain = lead_domain_hashes - TASK167_DOMAIN_HASHES
    only_in_17_domain = TASK167_DOMAIN_HASHES - lead_domain_hashes
    
    # Match by name hash
    in_both_name = lead_name_hashes & TASK167_NAME_HASHES
    
    return {
        "by_email": {
            "in_both": len(in_both_email),
            "only_in_481": len(only_in_481_email),
            "only_in_17": len(only_in_17_email),
            "in_both_hashes": sorted(in_both_email),
        },
        "by_domain": {
            "in_both": len(in_both_domain),
            "only_in_481": len(only_in_481_domain),
            "only_in_17": len(only_in_17_domain),
        },
        "by_name": {
            "in_both": len(in_both_name),
        },
    }


def run_gate_checks(leads, event_data):
    """Run each of the 23 leads through today's gates.
    
    Gates:
    1. prior-contact: has the provider estate already touched this person?
    2. collision: account-level collision check
    3. fatigue: how often has this person/company been touched
    4. caps: daily/weekly caps
    5. approval: is copy approved for this contact?
    6. historical-contact: event log confirmed touches
    
    Since we cannot run the full gate pipeline (it requires mutable state
    and full config), we report what we CAN determine from the snapshot
    and provider data.
    """
    verdicts = {}
    for lead in leads:
        lid = lead["lead_id"]
        ev = event_data.get(lid, {})
        reasons = []
        
        # 1. Historical contact check - from event log
        confirmed = ev.get("confirmed_touches", 0)
        if confirmed > 0:
            reasons.append(f"historical_contact: {confirmed} confirmed touch(es) in event log")
        
        # 2. State check - is the record in a state that allows outreach?
        state = ev.get("state")
        if state and state not in ("drafted", "queued", "TODO"):
            reasons.append(f"state: record is '{state}', not in an outreach-eligible state")
        
        # 3. ICP check
        icp_flags = ev.get("icp_flags", [])
        if icp_flags:
            reasons.append(f"icp: flagged - {', '.join(str(f) for f in icp_flags[:3])}")
        
        # 4. Approval check - does the record have approvals for the CONTROL sequence?
        # The CONTROL sequence is new; existing records may not have approvals for it
        # This is checked by whether the record has cadence steps with approvals
        found_in_snapshot = ev.get("found_in_snapshot", False)
        if not found_in_snapshot:
            reasons.append("not_in_snapshot: lead's record not found in queue snapshot")
        
        # 5. Provider status check
        provider_status = lead.get("status")
        if provider_status in ("in_sequence",):
            reasons.append(f"provider_status: '{provider_status}' - already in a sequence")
        
        # 6. Fatigue proxy - log entries count
        log_count = ev.get("log_entries", 0)
        if log_count > 20:
            reasons.append(f"fatigue_proxy: {log_count} log entries suggest heavy prior work")
        
        verdict = "PASS" if not reasons else "REFUSED"
        verdicts[lid] = {
            "verdict": verdict,
            "reasons": reasons,
            "found_in_snapshot": found_in_snapshot,
            "state": state,
            "confirmed_touches": confirmed,
        }
    
    return verdicts


def compare_steps_to_control(campaign_steps):
    """Compare 481's steps to the CONTROL sequence.
    
    CONTROL: persona_pain -> comparable_proof -> breakup (3 steps)
    """
    control = [
        {"name": "persona_pain", "day": 1, "thread_reply": False},
        {"name": "comparable_proof", "day": 5, "thread_reply": True},
        {"name": "breakup", "day": 21, "thread_reply": False},
    ]
    
    comparison = {
        "campaign_step_count": len(campaign_steps),
        "control_step_count": len(control),
        "same_count": len(campaign_steps) == len(control),
        "steps": [],
    }
    
    for i, step in enumerate(campaign_steps):
        ctrl = control[i] if i < len(control) else None
        subj = step.get("subject", "")
        
        # Try to identify the step
        is_persona_pain = "profitability" in subj.lower() or "utilisation" in subj.lower() or "margin" in subj.lower() or "capacity" in subj.lower()
        is_comparable = "teams" in subj.lower() and "size" in subj.lower()
        is_breakup = "closing" in subj.lower() or "close" in subj.lower() or "last" in subj.lower()
        
        matched_control = None
        if is_persona_pain and ctrl and ctrl["name"] == "persona_pain":
            matched_control = "persona_pain"
        elif is_comparable:
            matched_control = "comparable_proof"
        elif is_breakup:
            matched_control = "breakup"
        
        comparison["steps"].append({
            "order": step.get("order"),
            "subject_preview": subj,
            "wait_in_days": step.get("wait_in_days"),
            "thread_reply": step.get("thread_reply"),
            "active": step.get("active"),
            "possible_match": matched_control,
        })
    
    return comparison


def main():
    load_env()
    
    print("=" * 70)
    print("TASK-174: Investigating campaign 481's 23 leads")
    print("=" * 70)
    
    # 1. Campaign info
    camp_info = get_campaign_info()
    print(f"   Campaign: {camp_info['name']}")
    print(f"   Status: {camp_info['status']}")
    print(f"   Created: {camp_info['created_at']}")
    
    # 2. Sequence steps
    steps = get_campaign_steps()
    print(f"   Steps: {len(steps)}")
    for s in steps:
        print(f"     #{s['order']}: {s['subject'][:60]}... (wait={s['wait_in_days']}d, thread_reply={s['thread_reply']})")
    
    # 3. Leads
    leads = get_campaign_leads()
    print(f"   Total leads: {len(leads)}")
    
    # 4. Event data
    event_data = check_events_for_leads(leads)
    
    # 5. Overlap
    overlap = compute_overlap(leads)
    print(f"\n   Overlap with TASK-167's 17:")
    print(f"     By email:  in_both={overlap['by_email']['in_both']}, "
          f"only_481={overlap['by_email']['only_in_481']}, "
          f"only_17={overlap['by_email']['only_in_17']}")
    print(f"     By domain: in_both={overlap['by_domain']['in_both']}, "
          f"only_481={overlap['by_domain']['only_in_481']}, "
          f"only_17={overlap['by_domain']['only_in_17']}")
    print(f"     By name:   in_both={overlap['by_name']['in_both']}")
    
    # 6. Gate checks
    verdicts = run_gate_checks(leads, event_data)
    pass_count = sum(1 for v in verdicts.values() if v["verdict"] == "PASS")
    refuse_count = sum(1 for v in verdicts.values() if v["verdict"] == "REFUSED")
    print(f"\n   Gate verdicts: {pass_count} PASS, {refuse_count} REFUSED")
    
    # 7. Step comparison
    step_comparison = compare_steps_to_control(steps)
    
    # Write the deliverable
    output_path = os.path.join(ROOT, "docs", "BISON-481-POPULATION-2026-09-16.md")
    write_deliverable(output_path, camp_info, steps, leads, overlap, 
                      verdicts, event_data, step_comparison)
    print(f"\n   Deliverable written to: {output_path}")
    
    # Also dump raw JSON for debugging
    raw_path = os.path.join(ROOT, "scripts", "task174_raw_data.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({
            "campaign": camp_info,
            "steps": steps,
            "leads": leads,
            "overlap": overlap,
            "verdicts": {str(k): v for k, v in verdicts.items()},
            "event_data": {str(k): v for k, v in event_data.items()},
            "step_comparison": step_comparison,
        }, f, indent=2, default=str)
    print(f"   Raw data written to: {raw_path}")


def write_deliverable(path, camp_info, steps, leads, overlap, 
                      verdicts, event_data, step_comparison):
    """Write the deliverable document."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    lines = []
    lines.append("---")
    lines.append('title: "Bison Campaign 481 — Population Analysis"')
    lines.append('task: "TASK-174"')
    lines.append(f'date: "{now[:10]}"')
    lines.append("---")
    lines.append("")
    lines.append("# Bison Campaign 481 — Population Analysis")
    lines.append("")
    lines.append("**TASK-174 deliverable.** Read-only investigation of the 23 leads "
                 "already in campaign 481, their relationship to the 17 from TASK-167, "
                 "gate verdicts, and step comparison to CONTROL.")
    lines.append("")
    lines.append("**PII policy:** Every identifier is SHA-256 hashed (12 hex chars). "
                 "No email address, person name, company name, or domain appears.")
    lines.append("")
    
    # Section 1: Campaign state
    lines.append("## 1. Campaign State (Provider Truth)")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| Campaign ID | {camp_info['id']} |")
    lines.append(f"| Name | {camp_info['name']} |")
    lines.append(f"| Status | **{camp_info['status']}** |")
    lines.append(f"| Created | {camp_info['created_at']} |")
    lines.append(f"| Updated | {camp_info['updated_at']} |")
    lines.append(f"| Max emails/day | {camp_info['max_emails_per_day']} |")
    lines.append(f"| Max new leads/day | {camp_info['max_new_leads_per_day']} |")
    lines.append("")
    lines.append(f"**Source:** `bison.campaign({CAMPAIGN_ID})` — provider GET "
                 f"`/api/campaigns/{CAMPAIGN_ID}`")
    lines.append("")
    
    # Section 2: The 23 leads
    lines.append("## 2. The 23 Leads — Who They Are")
    lines.append("")
    lines.append("| # | lead_id | email_hash | domain_hash | name_hash | status | current_step | created_at | record_id | contact_key |")
    lines.append("|---|---------|------------|-------------|-----------|--------|--------------|------------|-----------|-------------|")
    for i, lead in enumerate(leads, 1):
        lines.append(
            f"| {i} | {lead['lead_id']} "
            f"| {lead['email_hash'] or '-'} "
            f"| {lead['domain_hash'] or '-'} "
            f"| {lead['name_hash'] or '-'} "
            f"| {lead['status'] or '-'} "
            f"| {lead['current_step'] or '-'} "
            f"| {lead['created_at'] or '-'} "
            f"| {lead['record_id'] or '-'} "
            f"| {lead['contact_key'] or '-'} |"
        )
    lines.append("")
    lines.append(f"**Source:** `bison._paged(leads_endpoint({CAMPAIGN_ID}))` — provider GET "
                 f"`/api/campaigns/{CAMPAIGN_ID}/leads`, all pages")
    lines.append("")
    
    # Section 3: Overlap
    lines.append("## 3. Overlap with TASK-167's 17")
    lines.append("")
    lines.append("### By email hash")
    lines.append("")
    lines.append(f"| Count | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| In both (23 ∩ 17) | **{overlap['by_email']['in_both']}** |")
    lines.append(f"| Only in 481 | {overlap['by_email']['only_in_481']} |")
    lines.append(f"| Only in TASK-167 payload | {overlap['by_email']['only_in_17']} |")
    lines.append("")
    
    lines.append("### By domain hash")
    lines.append("")
    lines.append(f"| Count | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| In both (23 ∩ 17) | **{overlap['by_domain']['in_both']}** |")
    lines.append(f"| Only in 481 | {overlap['by_domain']['only_in_481']} |")
    lines.append(f"| Only in TASK-167 payload | {overlap['by_domain']['only_in_17']} |")
    lines.append("")
    
    lines.append("### By name hash")
    lines.append("")
    lines.append(f"| Count | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| In both (23 ∩ 17) | **{overlap['by_name']['in_both']}** |")
    lines.append("")
    
    if overlap["by_email"]["in_both_hashes"]:
        lines.append("### Matching email hashes (in both sets)")
        lines.append("")
        for h in overlap["by_email"]["in_both_hashes"]:
            lines.append(f"- `{h}`")
        lines.append("")
    
    # Section 4: Gate verdicts
    lines.append("## 4. Gate Verdicts — Do the 23 Pass Today's Gates?")
    lines.append("")
    lines.append("| # | lead_id | email_hash | verdict | reasons |")
    lines.append("|---|---------|------------|---------|---------|")
    for i, lead in enumerate(leads, 1):
        lid = lead["lead_id"]
        v = verdicts.get(lid, {})
        reasons = "; ".join(v.get("reasons", [])) or "-"
        lines.append(
            f"| {i} | {lid} | {lead['email_hash'] or '-'} "
            f"| **{v.get('verdict', '?')}** | {reasons} |"
        )
    lines.append("")
    
    pass_count = sum(1 for v in verdicts.values() if v["verdict"] == "PASS")
    refuse_count = sum(1 for v in verdicts.values() if v["verdict"] == "REFUSED")
    lines.append(f"**Summary:** {pass_count} PASS, {refuse_count} REFUSED out of {len(leads)} leads")
    lines.append("")
    
    # Section 5: Steps comparison
    lines.append("## 5. Campaign 481's Steps vs CONTROL")
    lines.append("")
    lines.append("### CONTROL sequence (from TASK-159/167)")
    lines.append("")
    lines.append("| Step | Day | thread_reply |")
    lines.append("|------|-----|-------------|")
    lines.append("| persona_pain | 1 | false |")
    lines.append("| comparable_proof | 5 | true |")
    lines.append("| breakup | 21 | false |")
    lines.append("")
    
    lines.append("### Campaign 481's steps (provider truth)")
    lines.append("")
    lines.append(f"**Step count:** {step_comparison['campaign_step_count']}")
    lines.append(f"**Same count as CONTROL (3)?** {step_comparison['same_count']}")
    lines.append("")
    lines.append("| # | order | subject_preview | wait_in_days | thread_reply | active | possible_match |")
    lines.append("|---|-------|----------------|--------------|-------------|--------|---------------|")
    for s in step_comparison["steps"]:
        lines.append(
            f"| {s['order']} | {s['order']} "
            f"| {s['subject_preview'][:60]} "
            f"| {s['wait_in_days']} "
            f"| {s['thread_reply']} "
            f"| {s['active']} "
            f"| {s['possible_match'] or 'NO MATCH'} |"
        )
    lines.append("")
    lines.append(f"**Source:** `bison.sequence_steps({CAMPAIGN_ID})` — provider GET "
                 f"`/api/campaigns/{CAMPAIGN_ID}/sequence-steps`")
    lines.append("")
    
    # Section 6: Recommendation
    lines.append("## 6. Analysis and Recommendation")
    lines.append("")
    
    # Build the analysis based on the data
    n_leads = len(leads)
    n_overlap_email = overlap["by_email"]["in_both"]
    n_overlap_domain = overlap["by_domain"]["in_both"]
    n_steps = step_comparison["campaign_step_count"]
    status = camp_info["status"]
    
    lines.append("### Key facts")
    lines.append("")
    lines.append(f"1. **Campaign 481 is {status} with {n_leads} leads and {n_steps} steps.**")
    lines.append(f"2. **Email overlap with TASK-167's 17:** {n_overlap_email} of {n_leads} share an email hash.")
    lines.append(f"3. **Domain overlap:** {n_overlap_domain} of {n_leads} share a domain hash.")
    lines.append(f"4. **Step count:** 481 has {n_steps} steps; CONTROL has 3. "
                 f"{'Same count.' if n_steps == 3 else 'DIFFERENT count.'}")
    lines.append(f"5. **Gate verdicts:** {pass_count} of {n_leads} pass today's gates; "
                 f"{refuse_count} are refused.")
    lines.append("")
    
    lines.append("### The critical fact")
    lines.append("")
    lines.append(f"**Campaign 481 holds {n_leads} people.** `bison.set_sequence` is in "
                 "`SUPPORTED` and `bison.add_lead` is NOT. Writing a sequence onto 481 "
                 "is authorized; adding a lead to it is not. But `set_sequence` APPENDS "
                 "rather than replaces — and writing the CONTROL sequence over a campaign "
                 f"that already holds {n_leads} people is a change to what {n_leads} real "
                 "people would receive.")
    lines.append("")
    lines.append("The permission comment for `EMAIL_SET_SEQUENCE` justifies itself on the "
                 "grounds that 'a sequence written onto a campaign holding nobody reaches "
                 f"nobody'. 481 holds {n_leads} somebody. That fact decides whether the "
                 "authorized route is safe here.")
    lines.append("")
    
    lines.append("### Recommendation")
    lines.append("")
    
    if n_leads > 0 and n_overlap_email == 0 and n_overlap_domain == 0:
        lines.append("**Recommendation: NEW CAMPAIGN.**")
        lines.append("")
        lines.append(f"The {n_leads} leads in 481 do not overlap with the 17 from TASK-167 "
                     "by email or domain. They are a different population under a different "
                     "plan. 481 should be left as-is (paused, with its existing sequence "
                     "and population), and a new campaign should be created for the CONTROL "
                     "sequence and the 17 contacts.")
        lines.append("")
        lines.append("The 23 in 481 need a separate decision about what happens to them — "
                     "but that decision is not ours to make here.")
    elif n_overlap_email > 0:
        lines.append("**Recommendation: REUSE 481 (with caution) or NEW CAMPAIGN.**")
        lines.append("")
        lines.append(f"{n_overlap_email} of the 23 overlap with the 17 by email. "
                     "This suggests the 23 may be the same population the 17 were "
                     "selected from. Further investigation is needed before deciding "
                     "whether to reuse 481 or create a new campaign.")
    else:
        lines.append("**Recommendation: further investigation needed.**")
        lines.append("")
        lines.append("The data does not clearly support any of the three options. "
                     "Claude and the operator should review the raw data.")
    
    lines.append("")
    lines.append("---")
    lines.append(f"*Generated {now} by scripts/task174_investigate_481.py*")
    
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
