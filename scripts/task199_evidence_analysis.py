#!/usr/bin/env python3
"""TASK-199: what check_evidence requires, and what the 20 blocked records hold.

Analyses:
1. Exact specification of check_evidence requirements
2. The 20 generation-blocked records: what facts DO they hold?
3. What ICP needs vs what check_evidence needs - field-level comparison
4. How did 20 records reach verified with no usable research?
"""
import hashlib
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import icpstructural, clients, segments


def load_snapshot(path):
    recs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def hash_id(rec_id):
    return hashlib.sha256(str(rec_id).encode()).hexdigest()[:12]


def usable_research(rec):
    return [r for r in (rec.get("research") or [])
            if isinstance(r, dict)
            and r.get("quality") in ("medium", "strong")]


def all_research(rec):
    return [r for r in (rec.get("research") or []) if isinstance(r, dict)]


def company_facts_summary(rec):
    """What company_facts keys are populated?"""
    facts = rec.get("company_facts") or {}
    populated = {}
    for key in ("name", "employees", "employee_range", "revenue", "founded",
                "industry", "offices", "specialties", "notable", "stack",
                "headcount", "headcount_signal", "email_domain"):
        val = facts.get(key)
        if val not in (None, "", [], {}):
            populated[key] = val
    return populated


def fact_pool_size(rec):
    """How many strings does fact_strings produce for this record?"""
    from src.llm import fact_strings
    return len(fact_strings(rec))


def main():
    snapshot = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
    if not os.path.exists(snapshot):
        alt = os.path.join(ROOT, "..", "resonate-group-automation",
                           "work", "queue.snapshot.jsonl")
        if os.path.exists(alt):
            snapshot = alt
        else:
            print("ERROR: no queue.snapshot.jsonl found")
            sys.exit(1)

    recs = load_snapshot(snapshot)
    config = clients.load("productive")

    # --- The 20 generation-blocked records ---
    blocked = [r for r in recs
               if r.get("state") in ("verified", "held")
               and len(usable_research(r)) == 0]

    print("=" * 72)
    print("GENERATION-BLOCKED RECORDS (verified/held, 0 usable research)")
    print("=" * 72)
    print(f"Count: {len(blocked)}")
    print()

    for rec in blocked:
        hid = hash_id(rec["id"])
        cf = company_facts_summary(rec)
        all_res = all_research(rec)
        pool = fact_pool_size(rec)
        struct = icpstructural.structural(rec, config)
        contacts = rec.get("contacts") or []
        sendable = [c for c in contacts if c.get("sendable")]

        print(f"  {hid}  {rec['id'][:30]:30s}  state={rec.get('state')}")
        print(f"    company_facts keys: {list(cf.keys())}")
        print(f"    industry: {cf.get('industry', 'NONE')}")
        print(f"    offices: {cf.get('offices', 'NONE')}")
        print(f"    employees: {cf.get('employees', 'NONE')}  "
              f"range: {cf.get('employee_range', 'NONE')}")
        print(f"    research rows: {len(all_res)} total, "
              f"{len(usable_research(rec))} usable")
        if all_res:
            for r in all_res:
                q = r.get("quality", "?")
                f_text = (r.get("fact") or "")[:60]
                print(f"      quality={q}  field={r.get('field', '?')}  "
                      f"fact={f_text!r}")
        print(f"    fact_strings pool: {pool} strings")
        print(f"    ICP verdict: {struct['verdict']}  "
              f"unknown: {struct.get('unknown_criteria', [])}")
        print(f"    contacts: {len(contacts)} total, "
              f"{len(sendable)} sendable")
        print()

    # --- What ICP needs vs what check_evidence needs ---
    print("=" * 72)
    print("ICP vs CHECK_EVIDENCE: WHAT EACH NEEDS")
    print("=" * 72)
    print()
    print("ICP structural criteria (from icpstructural.py):")
    print("  geography:    country from segment.country, segment.country_code,")
    print("                or company_facts.offices (ISO code in last token)")
    print("  company_type: vertical from segment.vertical, or")
    print("                company_facts.industry")
    print("  employees:    from company_facts.headcount, employee_range,")
    print("                employees, headcount_signal, segment.employees")
    print("  services:     segment.business_model")
    print("  tracks_time:  phrases in company_facts text")
    print()
    print("check_evidence (from llm.py):")
    print("  Requires: model produces evidence[] list for persona_angle")
    print("  Each item must be traceable to fact_strings(rec)")
    print("  fact_strings walks: company, domain, context, signal,")
    print("    company_facts (all values), contacts, sizing, research[].fact")
    print("  Traceability: every adjacent content-word pair in the claim")
    print("    must be adjacent in ONE fact string; every number must")
    print("    appear in some fact")
    print()
    print("FIELDS THAT SERVE BOTH:")
    print("  company_facts.industry    -> ICP company_type + fact pool")
    print("  company_facts.offices     -> ICP geography + fact pool")
    print("  company_facts.employees   -> ICP employees + fact pool")
    print("  company_facts.specialties -> fact pool only")
    print("  company_facts.notable     -> fact pool only")
    print("  research[].fact           -> fact pool only (ICP does not")
    print("                              read research rows directly)")
    print()
    print("FIELDS THAT SERVE ONLY ICP:")
    print("  segment.country/country_code -> geography (not in fact pool)")
    print("  segment.business_model       -> services, tracks_time")
    print("  segment.vertical             -> company_type")
    print()
    print("FIELDS THAT SERVE ONLY CHECK_EVIDENCE:")
    print("  research[].fact -> traceable claims (ICP ignores research)")
    print()
    print("CONCLUSION: company_facts serves both gates. A record with")
    print("populated company_facts (industry, offices, employees) can pass")
    print("ICP AND provide a fact pool for check_evidence. But research rows")
    print("are ONLY useful for check_evidence, not ICP. And ICP's geography")
    print("criterion reads office ISO codes, which are in company_facts but")
    print("are not the kind of specific claim persona_angle would cite.")
    print()

    # --- How did records reach verified with no research? ---
    print("=" * 72)
    print("HOW 20 RECORDS REACHED VERIFIED WITH NO USABLE RESEARCH")
    print("=" * 72)
    print()
    print("The pipeline: queued -> enriched -> verified -> drafted -> ...")
    print()
    print("Verification (enrich.outcome) checks:")
    print("  any(c.get('sendable') for c in contacts)")
    print("  -> returns 'verified' if ANY contact has sendable=True")
    print()
    print("It does NOT check:")
    print("  - whether research rows exist")
    print("  - whether company_facts has industry/offices")
    print("  - whether ICP verdict is qualified")
    print("  - whether fact_strings has enough material for traceability")
    print()
    print("So a record reaches verified when:")
    print("  1. ContactOut/Blitz found people at the domain")
    print("  2. Email verification passed (deliverable/reoon)")
    print("  3. At least one contact is sendable")
    print()
    print("Person credits spent: decision-makers (10 credits) + ")
    print("  email-verifier (1 credit) per contact")
    print("Evidence gathered: possibly zero research rows")
    print()
    print("THIS IS THE ORDERING DEFECT:")
    print("  Person credits are spent BEFORE the evidence that licenses")
    print("  copy is gathered. A record can be verified (contacts found)")
    print("  while having nothing to write about.")
    print()

    # Count how many verified records have research vs not
    verified = [r for r in recs if r.get("state") in ("verified", "held")]
    with_research = [r for r in verified if len(usable_research(r)) > 0]
    without_research = [r for r in verified if len(usable_research(r)) == 0]

    print(f"Total verified/held records: {len(verified)}")
    print(f"  With usable research:      {len(with_research)}")
    print(f"  Without usable research:   {len(without_research)}")
    print()

    # How many verified records have sufficient company_facts for ICP?
    qualified_verified = [r for r in verified
                          if icpstructural.structural(r, config)["verdict"]
                          in ("icp_pass", "icp_pass_with_uncertainty")]
    print(f"Verified with ICP qualified: {len(qualified_verified)}")
    print(f"Verified without ICP qualified: {len(verified) - len(qualified_verified)}")


if __name__ == "__main__":
    main()
