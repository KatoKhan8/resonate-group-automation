#!/usr/bin/env python3
"""TASK-078: Analyze the regenerated copy for specific defects.

Reads work/queue.jsonl and reports:
1. Before-and-after counts for each defect named in the task
2. Per-contact verdict on the six questions
3. Which sequences actually regenerated vs which are stale

ZERO provider calls. ZERO writes. Read-only everywhere.
"""
import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def load_queue():
    path = os.path.join(PROJECT_ROOT, "work", "queue.jsonl")
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def load_campaigns():
    path = os.path.join(PROJECT_ROOT, "work", "campaigns.jsonl")
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def analyze_linkedin(rec):
    """Analyze LinkedIn copy for one record."""
    cadence = rec.get("cadence", {})
    results = []
    
    for contact_key, steps in cadence.items():
        contact_result = {
            "contact": contact_key,
            "domain": rec.get("domain"),
            "company": rec.get("company"),
            "steps": {},
            "names_productive": False,
            "says_who_writing": False,
            "i_noticed_count": 0,
            "has_generated": False,
        }
        
        for step_key in ["li1", "li2", "li3", "li4", "li5", "li6"]:
            step = steps.get(step_key, {})
            note = step.get("note", "")
            generated = step.get("generated", False)
            
            if not note:
                continue
            
            contact_result["has_generated"] = contact_result["has_generated"] or generated
            contact_result["steps"][step_key] = {
                "note": note,
                "generated": generated,
            }
            
            # Check defects
            if "productive" in note.lower():
                contact_result["names_productive"] = True
            
            # Says who is writing - check for name/company indicators
            # li1 should say who is writing per the new ladder
            if step_key == "li1":
                # Look for "i work with", "i'm", "my name", etc.
                if re.search(r'\b(i work|i\'m|i am|my name)\b', note.lower()):
                    contact_result["says_who_writing"] = True
            
            # "I noticed" openers
            if re.search(r'\bi noticed\b', note.lower()):
                contact_result["i_noticed_count"] += 1
        
        results.append(contact_result)
    
    return results

def analyze_email(rec):
    """Analyze email copy for one record."""
    cadence = rec.get("cadence", {})
    results = []
    
    for contact_key, steps in cadence.items():
        contact_result = {
            "contact": contact_key,
            "domain": rec.get("domain"),
            "company": rec.get("company"),
            "steps": {},
            "names_productive": False,
            "says_who_writing": False,
            "i_noticed_count": 0,
            "has_generated": False,
            "identical_subjects": [],
            "fabricated_history": [],
        }
        
        subjects_seen = {}
        
        for step_key in ["em1", "em2", "em3", "em4", "em5"]:
            step = steps.get(step_key, {})
            body = step.get("body", "")
            subject = step.get("subject", "")
            generated = step.get("generated", False)
            
            if not body:
                continue
            
            contact_result["has_generated"] = contact_result["has_generated"] or generated
            contact_result["steps"][step_key] = {
                "body": body,
                "subject": subject,
                "generated": generated,
            }
            
            # Check defects
            if "productive" in body.lower() or "productive" in subject.lower():
                contact_result["names_productive"] = True
            
            # Says who is writing
            if re.search(r'\b(i work|i\'m|i am|my name|from)\b', body.lower()):
                contact_result["says_who_writing"] = True
            
            # "I noticed" openers
            if re.search(r'\bi noticed\b', body.lower()):
                contact_result["i_noticed_count"] += 1
            
            # Track subjects for identical check
            if subject:
                if subject not in subjects_seen:
                    subjects_seen[subject] = []
                subjects_seen[subject].append(step_key)
            
            # Fabricated history - "our previous discussions" with prior_contact False
            if re.search(r'\b(previous discussions|our conversation|we spoke|we talked)\b', body.lower()):
                events = rec.get("events", [])
                prior_contact = any(e.get("type") == "contact" for e in events)
                if not prior_contact:
                    contact_result["fabricated_history"].append(step_key)
        
        # Check for identical subjects
        for subject, steps_list in subjects_seen.items():
            if len(steps_list) >= 2:
                contact_result["identical_subjects"].append({
                    "subject": subject,
                    "steps": steps_list,
                })
        
        results.append(contact_result)
    
    return results

def main():
    recs = load_queue()
    campaigns = load_campaigns()
    
    # Find the productive campaign
    campaign = None
    for c in campaigns:
        if c.get("campaign_id") == "productive-linkedin-production-v1":
            campaign = c
            break
    
    if not campaign:
        print("ERROR: productive-linkedin-production-v1 not found")
        return
    
    record_ids = campaign.get("record_ids", [])
    campaign_recs = [r for r in recs if r.get("id") in record_ids]
    
    print("=" * 80)
    print("  TASK-078: ANALYSIS OF REGENERATED COPY")
    print("=" * 80)
    print(f"  Campaign: {campaign.get('id')}")
    print(f"  Records: {len(campaign_recs)}")
    print()
    
    # Aggregate counts
    li_total = 0
    li_names_productive = 0
    li_says_who = 0
    li_i_noticed = 0
    li_has_generated = 0
    
    em_total = 0
    em_names_productive = 0
    em_says_who = 0
    em_i_noticed = 0
    em_has_generated = 0
    em_identical_subjects = 0
    em_fabricated_history = 0
    
    # Per-sequence counts
    li_sequences_with_productive = 0
    li_sequences_total = 0
    
    for rec in campaign_recs:
        li_results = analyze_linkedin(rec)
        em_results = analyze_email(rec)
        
        for lr in li_results:
            if lr["has_generated"]:
                li_has_generated += 1
                li_sequences_total += 1
                if lr["names_productive"]:
                    li_names_productive += 1
                    li_sequences_with_productive += 1
                if lr["says_who_writing"]:
                    li_says_who += 1
                li_i_noticed += lr["i_noticed_count"]
        
        for er in em_results:
            if er["has_generated"]:
                em_has_generated += 1
                if er["names_productive"]:
                    em_names_productive += 1
                if er["says_who_writing"]:
                    em_says_who += 1
                em_i_noticed += er["i_noticed_count"]
                em_identical_subjects += len(er["identical_subjects"])
                em_fabricated_history += len(er["fabricated_history"])
    
    print("-" * 80)
    print("  AGGREGATE COUNTS")
    print("-" * 80)
    print()
    print("  LINKEDIN:")
    print(f"    contacts with generated copy:     {li_has_generated}")
    print(f"    names Productive:                 {li_names_productive} ({100*li_names_productive/max(1,li_has_generated):.0f}%)")
    print(f"    li1 says who is writing:          {li_says_who} ({100*li_says_who/max(1,li_has_generated):.0f}%)")
    print(f"    'i noticed' openers:              {li_i_noticed}")
    print(f"    per-sequence names Productive:    {li_sequences_with_productive} of {li_sequences_total} ({100*li_sequences_with_productive/max(1,li_sequences_total):.0f}%)")
    print()
    print("  EMAIL:")
    print(f"    contacts with generated copy:     {em_has_generated}")
    print(f"    names Productive:                 {em_names_productive} ({100*em_names_productive/max(1,em_has_generated):.0f}%)")
    print(f"    says who is writing:              {em_says_who} ({100*em_says_who/max(1,em_has_generated):.0f}%)")
    print(f"    'i noticed' openers:              {em_i_noticed}")
    print(f"    identical subjects (2+ steps):    {em_identical_subjects}")
    print(f"    fabricated history:               {em_fabricated_history}")
    print()
    
    # Now show specific examples
    print("-" * 80)
    print("  EXAMPLES: SEQUENCES THAT REGENERATED")
    print("-" * 80)
    print()
    
    # ogpartner-dk/jacob-faertz is the example from the task
    for rec in campaign_recs:
        if rec.get("id") == "ogpartner-dk":
            li_results = analyze_linkedin(rec)
            for lr in li_results:
                if lr["contact"] == "jacob-faertz":
                    print(f"  {rec.get('domain')}/{lr['contact']}")
                    print(f"  Company: {rec.get('company')}")
                    print(f"  Names Productive: {lr['names_productive']}")
                    print(f"  li1 says who: {lr['says_who_writing']}")
                    print()
                    for step_key in ["li1", "li2", "li3", "li4", "li5", "li6"]:
                        step = lr["steps"].get(step_key, {})
                        if step:
                            print(f"    {step_key}: {step['note']}")
                    print()
    
    # Find other sequences that regenerated
    print("-" * 80)
    print("  OTHER SEQUENCES WITH GENERATED COPY")
    print("-" * 80)
    print()
    
    for rec in campaign_recs:
        li_results = analyze_linkedin(rec)
        for lr in li_results:
            if lr["has_generated"] and lr["contact"] != "jacob-faertz":
                print(f"  {rec.get('domain')}/{lr['contact']}")
                print(f"    Names Productive: {lr['names_productive']}")
                print(f"    li1 says who: {lr['says_who_writing']}")
                print(f"    'i noticed': {lr['i_noticed_count']}")
                # Show li1 and li4 (product rung)
                li1 = lr["steps"].get("li1", {})
                li4 = lr["steps"].get("li4", {})
                if li1:
                    print(f"    li1: {li1['note'][:120]}...")
                if li4:
                    print(f"    li4: {li4['note'][:120]}...")
                print()

if __name__ == "__main__":
    main()
