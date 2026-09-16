#!/usr/bin/env python3
"""TASK-187 final: tracks_time fails, dmplan gate, and the real answer."""
import json
from collections import Counter

SNAPSHOT = "work/queue.snapshot.jsonl"


def load():
    with open(SNAPSHOT, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main():
    recs = load()

    # --- 1. The 6 tracks_time = fail records ---
    print("=== TRACKS_TIME = FAIL RECORDS ===")
    for r in recs:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        criteria = s.get("criteria") or {}
        tt = criteria.get("tracks_time") or {}
        if tt.get("status") == "fail":
            v = q.get("verdict") or {}
            print(f"  {r.get('domain')}: icp_status={v.get('icp_status')}")
            bm = (r.get("segment") or {}).get("business_model") or \
                 (r.get("company_facts") or {}).get("business_model")
            print(f"    business_model: {bm}")
            print(f"    why: {tt.get('why', '')[:120]}")

    # --- 2. How did the 113 qualified records get qualified? ---
    # All are icp_pass_with_uncertainty. The DEFINING criteria are geography
    # and company_type. Both must be PASSING. tracks_time is UNKNOWN on all.
    # This is BY DESIGN: the code says icp_pass_with_uncertainty maps to
    # QUALIFIED.
    print("\n=== THE QUALIFICATION PATH ===")
    print("All 113 qualified records reached QUALIFIED via")
    print("icp_pass_with_uncertainty, NOT icp_pass.")
    print()
    print("verdict_of() rule:")
    print("  1. Any FAIL -> icp_fail -> REJECTED")
    print("  2. All five PASSING -> icp_pass -> QUALIFIED")
    print("  3. DEFINING (geography, company_type) both PASSING")
    print("     -> icp_pass_with_uncertainty -> QUALIFIED")
    print("  4. Otherwise -> icp_review -> REVIEW")
    print()
    print("FROM_STRUCTURAL mapping:")
    print("  icp_pass              -> qualified")
    print("  icp_pass_with_uncertainty -> qualified")
    print("  icp_review            -> review")
    print("  icp_fail              -> rejected")
    print()
    print("So tracks_time=UNKNOWN does NOT prevent qualification.")
    print("It prevents icp_pass (the pure form) but NOT qualification.")

    # --- 3. What is the real gate to person-credit spend? ---
    print("\n=== THE REAL GATE TO PERSON CREDITS ===")
    print("enrich.person_level_allowed() calls qualify.state_of(rec)")
    print("state_of returns QUALIFIED when icp_status == 'qualified'")
    print("Allowed states: (dmplan.QUALIFIED, dmplan.DM_APPROVED)")
    print()
    print("Since icp_pass_with_uncertainty -> qualified,")
    print("113 records ARE eligible for person-credit spend RIGHT NOW.")

    # --- 4. How many of the 250 unprocessed can EVER be reached? ---
    print("\n=== THE 250 UNPROCESSED RECORDS ===")
    unprocessed = [r for r in recs if not (r.get("qualification") or {}).get("verdict")]
    print(f"  Count: {len(unprocessed)}")
    print(f"  Have company_facts: 0")
    print(f"  Have ANY data beyond domain: 0")
    print()
    print("  These records are blank slates. Every criterion is unanswerable")
    print("  from current data. They need:")
    print("    - company-info (domain) for industry, employees, location")
    print("    - website text for business model, time evidence")
    print("    - headcount resolution for employee floor")
    print()
    print("  Even after full enrichment, each criterion could resolve to")
    print("  PASS, UNKNOWN or FAIL. The theoretical maximum qualified is")
    print("  250 (if every record happened to pass every criterion), but")
    print("  the PRACTICAL maximum depends on what the data says.")

    # --- 5. The complete answer ---
    print("\n" + "=" * 60)
    print("COMPLETE ANSWER")
    print("=" * 60)
    print()
    print("Q1: Is icp_pass reachable at all?")
    print()
    print("  YES, but it is NOT the gate to anything.")
    print()
    print("  The code defines two qualifying states:")
    print("    icp_pass:              all five criteria PASSING")
    print("    icp_pass_with_uncertainty: DEFINING two PASSING, rest not FAIL")
    print()
    print("  BOTH map to icp_status='qualified' via FROM_STRUCTURAL.")
    print("  BOTH open the gate to person-credit spend.")
    print()
    print("  In this estate, 0 of 550 records have reached icp_pass.")
    print("  113 have reached icp_pass_with_uncertainty, which is")
    print("  equally qualified for pipeline purposes.")
    print()
    print("  The reason no record has icp_pass: tracks_time is UNKNOWN")
    print("  on all 300 processed records. Zero carry billing phrases")
    print("  in their structured text. The 6 that are not UNKNOWN are")
    print("  FAIL (product/ecommerce business model), not PASS.")
    print()
    print("Q2: How many of 550 can reach qualified?")
    print()
    print("  Currently qualified: 113 (all via icp_pass_with_uncertainty)")
    print("  Currently review: 66 (all blocked by geography/company_type")
    print("    being unknown, NOT by tracks_time)")
    print("  Currently rejected: 121 (at least one FAIL)")
    print("  Unprocessed: 250 (no data at all)")
    print()
    print("  Theoretical max from processed 300 (all unknowns -> PASS): 179")
    print("  The 66 review records cannot be fixed by tracks_time alone;")
    print("  they need geography and/or company_type resolved.")
    print()
    print("Q3: What actually gates person-credit spend?")
    print()
    print("  qualify.state_of(rec) in (QUALIFIED, DM_APPROVED)")
    print("  Which requires icp_status == 'qualified'")
    print("  Which is reached by icp_pass OR icp_pass_with_uncertainty")
    print("  Which requires only geography + company_type to PASS")
    print()
    print("Q4: Is the bar unsatisfiable?")
    print()
    print("  NO. The bar IS being satisfied. 113 records are qualified.")
    print("  The bar is icp_pass_with_uncertainty, not icp_pass.")
    print("  tracks_time being UNKNOWN is by design: the code explicitly")
    print("  says 'absence of the phrase on a website is not evidence")
    print("  that the company does not track time' and routes through")
    print("  icp_pass_with_uncertainty -> qualified.")
    print()
    print("  The ACTUAL bottleneck is:")
    print("    - 250 records with zero data (need company-info enrichment)")
    print("    - 66 review records blocked on geography/company_type")
    print("      (need location evidence and vertical classification)")

    # --- 6. The options if the operator wants icp_pass (the pure form) ---
    print("\n=== IF THE OPERATOR WANTS icp_pass (PURE FORM) ===")
    print()
    print("  To move from icp_pass_with_uncertainty to icp_pass,")
    print("  tracks_time must go from UNKNOWN to PASS.")
    print()
    print("  Current state: 113 qualified, 0 with icp_pass")
    print()
    print("  Option A: Find billing phrases in existing data")
    print("    Records with billing phrases in structured text: 0")
    print("    This avenue is exhausted.")
    print()
    print("  Option B: Apify website crawl for billing language")
    print("    Would need to crawl 113 domains for phrases like")
    print("    'billable', 'timesheet', 'utilisation', etc.")
    print("    Cost: 113 Apify credits")
    print("    Effect: records that carry the phrases go to icp_pass")
    print("    Risk: agencies may not publish billing language on websites")
    print()
    print("  Option C: Job postings as evidence source")
    print("    'We hire billing managers', 'PSA experience required'")
    print("    Would need a new data source and resolver")
    print()
    print("  Option D: Accept icp_pass_with_uncertainty as the gate")
    print("    This is what the code ALREADY does.")
    print("    113 records are qualified and eligible for person spend.")
    print("    The system is working as designed.")


if __name__ == "__main__":
    main()
