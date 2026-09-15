#!/usr/bin/env python3
"""TASK-133: how much more qualified inventory is actually reachable?

Answers four questions against the queue snapshot:
  1. What would verification of the 21 unverified cost?
  2. What is in the 300 records that is NOT yet a contact?
  3. Which other cohorts sit just under the line?
  4. LINKEDIN REACHABILITY - how many carry a usable LinkedIn URL?
"""
import json
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

SNAPSHOT = Path("work/queue.snapshot.jsonl")

# Verification costs from src/enrich.py COSTS dict
VERIFY_COSTS = {
    "contactout": 1,    # email-verifier
    "deliverable": 1,   # deliverable-verify
    "reoon": 1,         # reoon-verify
}


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


def has_linkedin(contact):
    """Does this contact have a usable LinkedIn URL/slug?"""
    li = contact.get("linkedin")
    if not li:
        return False
    li = str(li).strip()
    if not li:
        return False
    # Must look like a LinkedIn identifier (slug or full URL)
    return bool(li)


def contact_verification_state(contact):
    """Return the verification state of a contact.
    
    Returns one of:
      'verified_sendable' - verdict=valid/verified and sendable=True
      'verified_unsendable' - verified but sendable=False (invalid, etc.)
      'unknown' - no verdict or verdict=unknown
      'accept_all_uncleared' - accept_all domain, not cleared
      'held' - held for some reason
      'no_email' - no email address at all
    """
    email = contact.get("email")
    if not email:
        return "no_email"
    
    sendable = contact.get("sendable", False)
    verdict = contact.get("verdict")
    verification = contact.get("verification") or {}
    state = verification.get("state")
    
    if sendable and state == "verified":
        return "verified_sendable"
    
    if state == "verified" and not sendable:
        return "verified_unsendable"
    
    # Check for accept_all
    reoon = contact.get("reoon") or {}
    if reoon.get("is_catch_all"):
        if not sendable:
            return "accept_all_uncleared"
    
    if state == "unknown" or state is None:
        if verdict == "unknown":
            return "unknown"
        if verdict == "held":
            return "held"
        return "unknown"
    
    if state == "invalid":
        return "verified_unsendable"
    
    return "unknown"


def persona_of(contact):
    return contact.get("persona") or None


def main():
    records = load_records()
    total_records = len(records)
    
    # Split: dropped vs not-dropped
    dropped = [r for r in records if r.get("drop_reason") is not None]
    active = [r for r in records if r.get("drop_reason") is None]
    
    print(f"=" * 70)
    print(f"TASK-133: INVENTORY CEILING ANALYSIS")
    print(f"Snapshot: {SNAPSHOT}")
    print(f"=" * 70)
    print(f"\nTotal records: {total_records}")
    print(f"Active (not dropped): {len(active)}")
    print(f"Dropped: {len(dropped)}")
    
    # Drop reasons
    drop_reasons = Counter(r.get("drop_reason") for r in dropped)
    print(f"\nDrop reasons:")
    for reason, count in drop_reasons.most_common():
        print(f"  {reason}: {count}")
    
    # ---------------------------------------------------------------
    # ALL contacts (primary + excluded) across active records
    # ---------------------------------------------------------------
    all_contacts = []
    for rec in active:
        for c in rec.get("contacts", []):
            all_contacts.append((rec, c, "primary"))
        for c in rec.get("excluded", []):
            all_contacts.append((rec, c, "excluded"))
    
    primary_contacts = [(r, c) for r, c, kind in all_contacts if kind == "primary"]
    excluded_contacts = [(r, c) for r, c, kind in all_contacts if kind == "excluded"]
    
    print(f"\n--- CONTACT INVENTORY ---")
    print(f"Primary contacts across {len(active)} active records: {len(primary_contacts)}")
    print(f"Excluded contacts (not a persona): {len(excluded_contacts)}")
    
    # ---------------------------------------------------------------
    # QUESTION 4 FIRST: LINKEDIN REACHABILITY
    # ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"QUESTION 4: LINKEDIN REACHABILITY")
    print(f"{'=' * 70}")
    
    # Among primary contacts
    primary_with_li = [(r, c) for r, c in primary_contacts if has_linkedin(c)]
    primary_without_li = [(r, c) for r, c in primary_contacts if not has_linkedin(c)]
    
    print(f"\nPrimary contacts with LinkedIn URL: {len(primary_with_li)}")
    print(f"Primary contacts without LinkedIn URL: {len(primary_without_li)}")
    
    # Break down by verification state AND LinkedIn
    li_by_vstate = defaultdict(int)
    no_li_by_vstate = defaultdict(int)
    for r, c in primary_contacts:
        vs = contact_verification_state(c)
        if has_linkedin(c):
            li_by_vstate[vs] += 1
        else:
            no_li_by_vstate[vs] += 1
    
    print(f"\nLinkedIn reachability by verification state:")
    all_states = sorted(set(list(li_by_vstate.keys()) + list(no_li_by_vstate.keys())))
    print(f"  {'State':<25} {'Has LI':>8} {'No LI':>8} {'Total':>8}")
    print(f"  {'-' * 53}")
    for state in all_states:
        has = li_by_vstate.get(state, 0)
        no = no_li_by_vstate.get(state, 0)
        print(f"  {state:<25} {has:>8} {no:>8} {has + no:>8}")
    
    # LinkedIn reachability among economic_buyers specifically
    eb_with_li = [(r, c) for r, c in primary_contacts 
                  if persona_of(c) == "economic_buyer" and has_linkedin(c)]
    eb_without_li = [(r, c) for r, c in primary_contacts 
                     if persona_of(c) == "economic_buyer" and not has_linkedin(c)]
    eb_total = len([c for _, c in primary_contacts if persona_of(c) == "economic_buyer"])
    
    print(f"\nEconomic buyers:")
    print(f"  Total: {eb_total}")
    print(f"  With LinkedIn: {len(eb_with_li)}")
    print(f"  Without LinkedIn: {len(eb_without_li)}")
    
    # LinkedIn across ALL personas
    print(f"\nLinkedIn reachability by persona:")
    persona_li = defaultdict(lambda: {"with_li": 0, "no_li": 0, "total": 0})
    for r, c in primary_contacts:
        p = persona_of(c) or "(no persona)"
        persona_li[p]["total"] += 1
        if has_linkedin(c):
            persona_li[p]["with_li"] += 1
        else:
            persona_li[p]["no_li"] += 1
    
    for persona, counts in sorted(persona_li.items(), 
                                   key=lambda x: x[1]["with_li"], reverse=True):
        print(f"  {persona:<25} with LI: {counts['with_li']:>4}  "
              f"no LI: {counts['no_li']:>4}  total: {counts['total']:>4}")
    
    # LinkedIn-reachable cohort: any primary contact with a LinkedIn URL,
    # regardless of email verification
    li_reachable = [(r, c) for r, c in primary_contacts if has_linkedin(c)]
    li_reachable_eb = [(r, c) for r, c in li_reachable if persona_of(c) == "economic_buyer"]
    li_reachable_founder = [(r, c) for r, c in li_reachable if persona_of(c) == "founder"]
    
    print(f"\nLINKEDIN-REACHABLE INVENTORY (the number that matters for HeyReach):")
    print(f"  All primary contacts with LinkedIn: {len(li_reachable)}")
    print(f"  Of those, economic_buyer: {len(li_reachable_eb)}")
    print(f"  Of those, founder: {len(li_reachable_founder)}")
    
    # Also check excluded contacts for LinkedIn
    excluded_with_li = [(r, c) for r, c in excluded_contacts if has_linkedin(c)]
    print(f"\n  Excluded contacts with LinkedIn: {len(excluded_with_li)}")
    print(f"  (These are real people at real companies, just not the target persona)")
    
    # ---------------------------------------------------------------
    # QUESTION 1: VERIFICATION COST FOR THE 21
    # ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"QUESTION 1: VERIFICATION COST FOR UNVERIFIED CONTACTS")
    print(f"{'=' * 70}")
    
    # Find contacts that are NOT verified_sendable but HAVE an email
    unverified_with_email = []
    for r, c in primary_contacts:
        email = c.get("email")
        if not email:
            continue
        vs = contact_verification_state(c)
        if vs != "verified_sendable":
            unverified_with_email.append((r, c, vs))
    
    print(f"\nPrimary contacts with email but NOT verified_sendable: "
          f"{len(unverified_with_email)}")
    
    # Break down by verification state
    uv_by_state = Counter(vs for _, _, vs in unverified_with_email)
    print(f"\nBreakdown by state:")
    for state, count in uv_by_state.most_common():
        print(f"  {state}: {count}")
    
    # Cost analysis
    # The waterfall: ContactOut (1 credit) -> Deliverable (1 credit) -> Reoon (1 credit)
    # For 'unknown': ContactOut first, likely needs Deliverable as second opinion
    # For 'accept_all_uncleared': may need all three, and may still not resolve
    print(f"\nCOST ESTIMATE:")
    print(f"  Verification waterfall: ContactOut (1) -> Deliverable (1) -> Reoon (1)")
    print(f"  Maximum cost per address: 3 credits")
    
    unknown_count = uv_by_state.get("unknown", 0)
    accept_all_count = uv_by_state.get("accept_all_uncleared", 0)
    held_count = uv_by_state.get("held", 0)
    other_count = len(unverified_with_email) - unknown_count - accept_all_count - held_count
    
    print(f"\n  'unknown' addresses: {unknown_count}")
    print(f"    - ContactOut re-verify: 1 credit each = {unknown_count} credits")
    print(f"    - If still unknown, Deliverable second opinion: +{unknown_count} credits")
    print(f"    - Expected cost: {unknown_count}-{unknown_count * 2} credits")
    print(f"    - Expected recovery: MODERATE - these were never definitively answered")
    
    print(f"\n  'accept_all_uncleared' addresses: {accept_all_count}")
    print(f"    - Accept-all domains may NEVER resolve to a definite verdict")
    print(f"    - Full waterfall (3 providers): {accept_all_count * 3} credits max")
    print(f"    - Expected recovery: LOW - accept-all is a domain property,")
    print(f"      not a per-address one. Re-spending is likely waste.")
    
    print(f"\n  'held' addresses: {held_count}")
    print(f"    - Held contacts have a structural issue, not a verification one")
    print(f"    - Spending on verification will not resolve the hold")
    
    if other_count > 0:
        print(f"\n  Other states: {other_count}")
        print(f"    - Cost: {other_count}-{other_count * 3} credits depending on state")
    
    total_min = unknown_count + accept_all_count + other_count
    total_max = unknown_count * 2 + accept_all_count * 3 + other_count * 3
    print(f"\n  TOTAL ESTIMATED COST: {total_min}-{total_max} credits")
    print(f"  (For comparison: decision-makers costs {2} credits per profile)")
    
    # ---------------------------------------------------------------
    # QUESTION 2: WHAT IS IN THE 300 RECORDS THAT IS NOT A CONTACT?
    # ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"QUESTION 2: RECORDS WITHOUT CONTACTS")
    print(f"{'=' * 70}")
    
    # For each active record, count contacts and check enrichment state
    records_with_contacts = []
    records_without_contacts = []
    
    for rec in active:
        primaries = rec.get("contacts", [])
        excluded = rec.get("excluded", [])
        total_c = len(primaries) + len(excluded)
        
        if total_c == 0:
            records_without_contacts.append(rec)
        else:
            records_with_contacts.append(rec)
    
    print(f"\nActive records with at least one contact: {len(records_with_contacts)}")
    print(f"Active records with NO contacts at all: {len(records_without_contacts)}")
    
    # Why no contacts? Check the log and enrichment state
    no_contact_reasons = defaultdict(int)
    no_contact_records = []
    
    for rec in records_without_contacts:
        log = rec.get("log", [])
        log_steps = [e.get("step") for e in log]
        log_notes = [e.get("note", "") for e in log]
        
        # Check if discovery was attempted
        has_enrich = "enrich" in log_steps
        has_queued = "queued" in log_steps
        has_icp = "icp" in log_steps
        
        # Check for specific reasons
        has_no_people = any("people-count: 0" in n for n in log_notes)
        has_unstaffed = any("unstaffed" in n.lower() for n in log_notes)
        has_no_target = any("no target persona" in n.lower() for n in log_notes)
        has_no_person_level = any("no person-level call" in n for n in log_notes)
        has_decision_makers = any("decision-makers" in n for n in log_notes)
        
        # Check company facts
        cf = rec.get("company_facts") or {}
        emp = cf.get("employees")
        icp_flags = cf.get("icp_flags", [])
        has_icp_flag = len(icp_flags) > 0
        
        # Check diagnosis
        diagnosis = rec.get("diagnosis")
        
        if has_no_people:
            no_contact_reasons["people-count was 0 (domain unstaffed)"] += 1
        elif has_no_person_level and not has_decision_makers:
            no_contact_reasons["ICP not passed; no person-level call made"] += 1
        elif has_enrich and not has_decision_makers:
            no_contact_reasons["enriched but no decision-makers returned"] += 1
        elif not has_enrich and has_queued:
            no_contact_reasons["still queued; enrichment never ran"] += 1
        elif not has_enrich and not has_queued:
            no_contact_reasons["no enrichment attempted"] += 1
        else:
            no_contact_reasons["other (check log)"] += 1
        
        no_contact_records.append({
            "id": rec.get("id"),
            "domain": rec.get("domain"),
            "has_enrich": has_enrich,
            "has_queued": has_queued,
            "has_icp": has_icp,
            "employees": emp,
            "icp_flags": icp_flags,
            "diagnosis": diagnosis,
            "log_steps": log_steps,
        })
    
    print(f"\nWhy {len(records_without_contacts)} records have no contacts:")
    for reason, count in sorted(no_contact_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")
    
    # How many have never had person-discovery?
    never_discovered = sum(1 for r in no_contact_records 
                          if not r["has_enrich"] or 
                          "decision-makers" not in str(r["log_steps"]))
    print(f"\nRecords that never had person-discovery run: {never_discovered}")
    print(f"Records that had discovery but got nobody: "
          f"{len(records_without_contacts) - never_discovered}")
    
    # ICP status of contactless records
    icp_blocked = sum(1 for r in no_contact_records if r["icp_flags"])
    print(f"\nOf contactless records:")
    print(f"  With ICP flags (did not pass ICP): {icp_blocked}")
    print(f"  Without ICP flags (passed or not yet judged): "
          f"{len(records_without_contacts) - icp_blocked}")
    
    # ---------------------------------------------------------------
    # QUESTION 3: WHICH COHORTS SIT JUST UNDER THE LINE?
    # ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"QUESTION 3: COHORT SIZES BY PERSONA")
    print(f"{'=' * 70}")
    
    # By persona, with verification state
    persona_counts = defaultdict(lambda: defaultdict(int))
    for r, c in primary_contacts:
        p = persona_of(c) or "(no persona)"
        vs = contact_verification_state(c)
        persona_counts[p][vs] += 1
        persona_counts[p]["_total"] += 1
    
    print(f"\nPersona cohorts by verification state:")
    print(f"  {'Persona':<25} {'Sendable':>10} {'Unsendable':>12} "
          f"{'Unknown':>8} {'AcceptAll':>10} {'Held':>6} {'Total':>7}")
    print(f"  {'-' * 82}")
    
    for persona, states in sorted(persona_counts.items(),
                                   key=lambda x: x[1].get("_total", 0),
                                   reverse=True):
        total = states.get("_total", 0)
        sendable = states.get("verified_sendable", 0)
        unsendable = states.get("verified_unsendable", 0)
        unknown = states.get("unknown", 0)
        accept_all = states.get("accept_all_uncleared", 0)
        held = states.get("held", 0)
        no_email = states.get("no_email", 0)
        print(f"  {persona:<25} {sendable:>10} {unsendable:>12} "
              f"{unknown:>8} {accept_all:>10} {held:>6} {total:>7}")
        if no_email:
            print(f"    (also {no_email} with no email at all)")
    
    # With verification recovery, what could reach 50?
    print(f"\nWith verification recovery (unknown -> sendable):")
    for persona, states in sorted(persona_counts.items(),
                                   key=lambda x: x[1].get("_total", 0),
                                   reverse=True):
        sendable = states.get("verified_sendable", 0)
        unknown = states.get("unknown", 0)
        potential = sendable + unknown
        gap_to_50 = max(0, 50 - potential)
        marker = " <-- could reach 50" if gap_to_50 == 0 and potential >= 50 else ""
        if potential > sendable:
            print(f"  {persona:<25} {sendable:>4} + {unknown:>4} unknown = "
                  f"{potential:>4} potential"
                  f"{' (gap to 50: ' + str(gap_to_50) + ')' if gap_to_50 > 0 else marker}")
    
    # ---------------------------------------------------------------
    # COMBINED FUNNEL
    # ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"COMPLETE FUNNEL: 300 RECORDS TO REACHABLE LEADS")
    print(f"{'=' * 70}")
    
    # Record-level funnel
    print(f"\nRecord-level:")
    print(f"  Total records: {total_records}")
    print(f"  Dropped: {len(dropped)}")
    print(f"  Active: {len(active)}")
    print(f"  Active with contacts: {len(records_with_contacts)}")
    print(f"  Active without contacts: {len(records_without_contacts)}")
    
    # Contact-level funnel
    print(f"\nContact-level (primary contacts only):")
    print(f"  Total primary contacts: {len(primary_contacts)}")
    
    with_email = [(r, c) for r, c in primary_contacts if c.get("email")]
    without_email = [(r, c) for r, c in primary_contacts if not c.get("email")]
    print(f"  With email address: {len(with_email)}")
    print(f"  Without email address: {len(without_email)}")
    
    with_li = [(r, c) for r, c in primary_contacts if has_linkedin(c)]
    print(f"  With LinkedIn URL: {len(with_li)}")
    
    verified_sendable = [(r, c) for r, c in primary_contacts 
                         if contact_verification_state(c) == "verified_sendable"]
    print(f"  Verified + sendable: {len(verified_sendable)}")
    
    # By persona for verified+sendable
    vs_by_persona = Counter(persona_of(c) for _, c in verified_sendable)
    print(f"\n  Verified+sendable by persona:")
    for persona, count in vs_by_persona.most_common():
        print(f"    {persona or '(no persona)'}: {count}")
    
    # LinkedIn-reachable by persona
    li_by_persona = Counter(persona_of(c) for _, c in li_reachable)
    print(f"\n  LinkedIn-reachable by persona:")
    for persona, count in li_by_persona.most_common():
        print(f"    {persona or '(no persona)'}: {count}")
    
    # ---------------------------------------------------------------
    # THE BOTTOM LINE
    # ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"THE BOTTOM LINE")
    print(f"{'=' * 70}")
    
    eb_sendable = len([(r, c) for r, c in verified_sendable 
                       if persona_of(c) == "economic_buyer"])
    eb_li = len(li_reachable_eb)
    
    print(f"\nEmail-reachable economic_buyers: {eb_sendable}")
    print(f"LinkedIn-reachable economic_buyers: {eb_li}")
    print(f"\nThe LinkedIn number is {'LARGER' if eb_li > eb_sendable else 'NOT larger'} "
          f"than the email number.")
    
    if eb_li > eb_sendable:
        print(f"\nThe LinkedIn channel opens up {eb_li - eb_sendable} additional "
              f"economic_buyers that email verification cannot reach.")
        print(f"The email verification ceiling matters LESS if LinkedIn is the "
              f"primary channel.")
    
    # Total LinkedIn-reachable across all personas
    total_li_reachable = len(li_reachable)
    total_verified_sendable = len(verified_sendable)
    print(f"\nTotal LinkedIn-reachable (all personas): {total_li_reachable}")
    print(f"Total email-verified sendable (all personas): {total_verified_sendable}")


if __name__ == "__main__":
    main()
