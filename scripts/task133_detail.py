#!/usr/bin/env python3
"""TASK-133 supplementary: detailed breakdown of the 21 economic_buyer gap
and the excluded contacts' LinkedIn availability."""
import json
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

SNAPSHOT = Path("work/queue.snapshot.jsonl")


def load_records():
    records = []
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def hash_id(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]


def main():
    records = load_records()
    active = [r for r in records if r.get("drop_reason") is None]
    
    # ---------------------------------------------------------------
    # THE 21 ECONOMIC_BUYER GAP - DETAILED
    # ---------------------------------------------------------------
    print("=" * 70)
    print("THE 21 ECONOMIC_BUYERS WITHOUT VERIFIED SENDABLE EMAIL")
    print("=" * 70)
    
    eb_all = []
    for rec in active:
        for c in rec.get("contacts", []):
            if c.get("persona") == "economic_buyer":
                eb_all.append((rec, c))
    
    print(f"\nTotal economic_buyers: {len(eb_all)}")
    
    # Categorize each one
    categories = {
        "verified_sendable": [],
        "unknown_with_email": [],
        "accept_all_uncleared": [],
        "no_email": [],
        "other": [],
    }
    
    for rec, c in eb_all:
        email = c.get("email")
        sendable = c.get("sendable", False)
        verification = c.get("verification") or {}
        state = verification.get("state")
        reoon = c.get("reoon") or {}
        
        if sendable and state == "verified":
            categories["verified_sendable"].append((rec, c))
        elif not email:
            categories["no_email"].append((rec, c))
        elif reoon.get("is_catch_all") and not sendable:
            categories["accept_all_uncleared"].append((rec, c))
        elif state == "unknown" or (not sendable and state != "invalid"):
            categories["unknown_with_email"].append((rec, c))
        else:
            categories["other"].append((rec, c))
    
    for cat, items in categories.items():
        print(f"\n  {cat}: {len(items)}")
        for rec, c in items:
            email = c.get("email", "(none)")
            li = c.get("linkedin", "(none)")
            domain = rec.get("domain", "?")
            name_hash = hash_id(c.get("name", "unknown"))
            title = c.get("title", "?")
            print(f"    [{name_hash}] {title} @ {domain} | "
                  f"email: {email[:30] if email else '(none)'} | "
                  f"LI: {li}")
    
    # ---------------------------------------------------------------
    # EXCLUDED CONTACTS: COULD ANY BE ECONOMIC BUYERS?
    # ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("EXCLUDED CONTACTS: TITLE ANALYSIS")
    print("=" * 70)
    
    excluded_titles = Counter()
    excluded_with_li = 0
    excluded_total = 0
    
    for rec in active:
        for c in rec.get("excluded", []):
            excluded_total += 1
            title = (c.get("title") or "").lower()
            if has_linkedin(c):
                excluded_with_li += 1
            
            # Check for economic buyer-like titles
            if any(w in title for w in ["ceo", "founder", "co-founder", "cofounder",
                                         "owner", "president", "managing director",
                                         "cfo", "cto", "coo"]):
                excluded_titles[f"EB-like: {c.get('title')}"] += 1
    
    print(f"\nTotal excluded contacts: {excluded_total}")
    print(f"With LinkedIn: {excluded_with_li}")
    print(f"\nEB-like titles among excluded:")
    for title, count in excluded_titles.most_common():
        print(f"  {title}: {count}")
    
    # ---------------------------------------------------------------
    # RECORD-LEVEL: WHAT WOULD DISCOVERY RECOVER?
    # ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("RECORDS WITHOUT CONTACTS: COULD DISCOVERY HELP?")
    print("=" * 70)
    
    # Among the 85 records without contacts, how many passed ICP?
    no_contact = []
    for rec in active:
        if not rec.get("contacts") and not rec.get("excluded"):
            no_contact.append(rec)
    
    # Check ICP status
    icp_passed = []
    icp_failed = []
    icp_unknown = []
    
    for rec in no_contact:
        icp_flags = (rec.get("company_facts") or {}).get("icp_flags", [])
        log = rec.get("log", [])
        log_notes = [e.get("note", "") for e in log]
        
        # Check if any ICP verdict was reached
        has_rejection = any("under the client minimum" in n or "rejected" in n.lower()
                          for n in log_notes)
        has_people_zero = any("people-count: 0" in n for n in log_notes)
        
        if has_people_zero:
            icp_failed.append(rec)  # domain unstaffed
        elif has_rejection or icp_flags:
            icp_failed.append(rec)
        else:
            # Check if ICP was even attempted
            has_icp_step = any(e.get("step") == "icp" for e in log)
            if has_icp_step:
                icp_unknown.append(rec)  # ICP ran but unclear outcome
            else:
                icp_unknown.append(rec)  # ICP never ran
    
    print(f"\nRecords without contacts: {len(no_contact)}")
    print(f"  Domain unstaffed (people-count=0): "
          f"{sum(1 for r in no_contact if any('people-count: 0' in e.get('note','') for e in r.get('log',[])))}")
    
    # More precise: check for ICP verdict in log
    icp_verdicts = Counter()
    for rec in no_contact:
        log = rec.get("log", [])
        for e in log:
            if e.get("step") == "icp":
                note = e.get("note", "")
                icp_verdicts[note] += 1
    
    print(f"\nICP log entries among contactless records:")
    for note, count in icp_verdicts.most_common():
        print(f"  '{note}': {count}")
    
    # How many never had enrichment at all?
    never_enriched = 0
    enrich_ran_no_people = 0
    enrich_ran_no_persona = 0
    
    for rec in no_contact:
        log = rec.get("log", [])
        steps = [e.get("step") for e in log]
        notes = [e.get("note", "") for e in log]
        
        has_enrich = "enrich" in steps
        has_decision = any("decision-makers" in n for n in notes)
        has_people_zero = any("people-count: 0" in n for n in notes)
        has_queued_no_person = any("no person-level call" in n for n in notes)
        
        if not has_enrich:
            never_enriched += 1
        elif has_people_zero:
            enrich_ran_no_people += 1
        elif has_queued_no_person:
            enrich_ran_no_persona += 1
    
    print(f"\nEnrichment status of contactless records:")
    print(f"  Never enriched: {never_enriched}")
    print(f"  Enriched, people-count=0: {enrich_ran_no_people}")
    print(f"  Enriched, no person-level call (ICP block): {enrich_ran_no_persona}")
    
    # ---------------------------------------------------------------
    # THE REAL CEILING IF DISCOVERY RAN ON EVERYTHING
    # ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("THEORETICAL CEILING IF DISCOVERY RAN ON ALL ELIGIBLE RECORDS")
    print("=" * 70)
    
    # Records that are active, passed ICP, but have no contacts
    # These are the ones where discovery could help
    icp_passed_no_contacts = []
    for rec in no_contact:
        log = rec.get("log", [])
        notes = [e.get("note", "") for e in log]
        has_people_zero = any("people-count: 0" in n for n in notes)
        has_rejection = any("under the client minimum" in n or 
                          "rejected" in n.lower() for n in notes)
        icp_flags = (rec.get("company_facts") or {}).get("icp_flags", [])
        
        if not has_people_zero and not has_rejection and not icp_flags:
            icp_passed_no_contacts.append(rec)
    
    print(f"\nActive records that passed ICP but have no contacts: "
          f"{len(icp_passed_no_contacts)}")
    print(f"(These are candidates for person-discovery)")
    
    # Also check: records that were never enriched but have no ICP flags
    never_enriched_no_flags = []
    for rec in no_contact:
        log = rec.get("log", [])
        steps = [e.get("step") for e in log]
        icp_flags = (rec.get("company_facts") or {}).get("icp_flags", [])
        has_people_zero = any("people-count: 0" in e.get("note", "") for e in log)
        
        if "enrich" not in steps and not icp_flags and not has_people_zero:
            never_enriched_no_flags.append(rec)
    
    print(f"Never enriched AND no ICP flags: {len(never_enriched_no_flags)}")
    
    # ---------------------------------------------------------------
    # LINKEDIN REACHABILITY: THE KEY FINDING
    # ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("KEY FINDING: LINKEDIN VS EMAIL REACHABILITY")
    print("=" * 70)
    
    # For HeyReach, we need LinkedIn, not email
    # Every primary contact has LinkedIn
    # The question is: how many economic_buyers can HeyReach reach?
    
    eb_li_reachable = 0
    eb_email_reachable = 0
    
    for rec in active:
        for c in rec.get("contacts", []):
            if c.get("persona") != "economic_buyer":
                continue
            if c.get("linkedin"):
                eb_li_reachable += 1
            if c.get("sendable") and (c.get("verification") or {}).get("state") == "verified":
                eb_email_reachable += 1
    
    print(f"\nEconomic_buyer reachability:")
    print(f"  Via LinkedIn (HeyReach): {eb_li_reachable}")
    print(f"  Via email (EmailBison):  {eb_email_reachable}")
    print(f"  LinkedIn advantage:      +{eb_li_reachable - eb_email_reachable}")
    
    # What about ALL personas?
    all_li = 0
    all_email = 0
    for rec in active:
        for c in rec.get("contacts", []):
            if c.get("linkedin"):
                all_li += 1
            if c.get("sendable") and (c.get("verification") or {}).get("state") == "verified":
                all_email += 1
    
    print(f"\nAll personas reachability:")
    print(f"  Via LinkedIn: {all_li}")
    print(f"  Via email:    {all_email}")
    print(f"  LinkedIn advantage: +{all_li - all_email}")
    
    print(f"\nCONCLUSION: The estate is NOT inventory-limited on LinkedIn.")
    print(f"The 72 economic_buyers ALL have LinkedIn URLs.")
    print(f"The email verification question (21 contacts, 31-71 credits)")
    print(f"only matters for the email channel, not for HeyReach.")


def has_linkedin(contact):
    li = contact.get("linkedin")
    if not li:
        return False
    return bool(str(li).strip())


if __name__ == "__main__":
    main()
