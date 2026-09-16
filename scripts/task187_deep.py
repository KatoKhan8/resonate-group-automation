#!/usr/bin/env python3
"""TASK-187 deep dive: unprocessed records, review records, and reachability."""
import json
import sys
from collections import Counter

SNAPSHOT = "work/queue.snapshot.jsonl"


def load():
    with open(SNAPSHOT, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main():
    recs = load()

    # --- 1. The 250 unprocessed records: what data do they carry? ---
    unprocessed = [r for r in recs if not (r.get("qualification") or {}).get("verdict")]
    print(f"=== UNPROCESSED RECORDS: {len(unprocessed)} ===")

    # Do they have company_facts?
    has_facts = sum(1 for r in unprocessed if r.get("company_facts"))
    has_industry = sum(1 for r in unprocessed
                       if (r.get("company_facts") or {}).get("industry"))
    has_offices = sum(1 for r in unprocessed
                      if (r.get("company_facts") or {}).get("offices"))
    has_employees = sum(1 for r in unprocessed
                        if (r.get("company_facts") or {}).get("employees"))
    has_emp_range = sum(1 for r in unprocessed
                        if (r.get("company_facts") or {}).get("employee_range"))
    has_headcount = sum(1 for r in unprocessed
                        if (r.get("company_facts") or {}).get("headcount"))
    has_revenue = sum(1 for r in unprocessed
                      if (r.get("company_facts") or {}).get("revenue"))
    has_business_model = sum(1 for r in unprocessed
                             if (r.get("company_facts") or {}).get("business_model"))
    has_website_text = sum(1 for r in unprocessed
                           if (r.get("company_facts") or {}).get("website_text"))
    has_description = sum(1 for r in unprocessed
                          if (r.get("company_facts") or {}).get("description"))

    print(f"  Have company_facts at all: {has_facts}")
    print(f"  Have industry: {has_industry}")
    print(f"  Have offices: {has_offices}")
    print(f"  Have employees (exact): {has_employees}")
    print(f"  Have employee_range: {has_emp_range}")
    print(f"  Have headcount (resolved): {has_headcount}")
    print(f"  Have revenue: {has_revenue}")
    print(f"  Have business_model: {has_business_model}")
    print(f"  Have website_text: {has_website_text}")
    print(f"  Have description: {has_description}")

    # Check what waterfall calls they have
    call_dist = Counter()
    for r in unprocessed:
        wf = r.get("waterfall") or []
        for step in wf:
            call_dist[step.get("call", "unknown")] += 1
    print(f"\n  Waterfall calls on unprocessed records:")
    for k, v in call_dist.most_common():
        print(f"    {k}: {v}")

    # --- 2. Review records: what blocks them? ---
    review_recs = [r for r in recs if (r.get("qualification") or {}).get(
        "verdict", {}).get("icp_status") == "review"]
    print(f"\n=== REVIEW RECORDS: {len(review_recs)} ===")

    # For each review record, what combination of unknowns blocks it?
    review_combos = Counter()
    for r in review_recs:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        criteria = s.get("criteria") or {}
        unknowns = tuple(sorted(
            name for name in ("geography", "company_type", "services_business",
                              "employees", "tracks_time")
            if (criteria.get(name) or {}).get("status") == "unknown"
        ))
        fails = tuple(sorted(
            name for name in ("geography", "company_type", "services_business",
                              "employees", "tracks_time")
            if (criteria.get(name) or {}).get("status") == "fail"
        ))
        review_combos[(fails, unknowns)] += 1

    print("  (fails, unknowns) combinations:")
    for (fails, unknowns), count in review_combos.most_common():
        print(f"    {count:3d}x  fails={fails or 'none'}, unknowns={unknowns}")

    # Can any review record be fixed by resolving tracks_time alone?
    tt_only = 0
    for r in review_recs:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        criteria = s.get("criteria") or {}
        unknowns = [name for name in ("geography", "company_type",
                                       "services_business", "employees",
                                       "tracks_time")
                    if (criteria.get(name) or {}).get("status") == "unknown"]
        fails = [name for name in ("geography", "company_type",
                                    "services_business", "employees",
                                    "tracks_time")
                 if (criteria.get(name) or {}).get("status") == "fail"]
        if not fails and unknowns == ["tracks_time"]:
            tt_only += 1
    print(f"\n  Review records blocked ONLY by tracks_time: {tt_only}")

    # What about defining criteria?
    defining_blocked = 0
    for r in review_recs:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        criteria = s.get("criteria") or {}
        geo = (criteria.get("geography") or {}).get("status")
        ct = (criteria.get("company_type") or {}).get("status")
        if geo != "pass" or ct != "pass":
            defining_blocked += 1
    print(f"  Review records where defining criteria not both PASS: "
          f"{defining_blocked}")

    # --- 3. How many records have billing/time phrases in website text? ---
    TIME_EVIDENCE = ("billable", "timesheet", "time tracking", "time-tracking",
                     "hourly rate", "per hour", "utilisation", "utilization",
                     "chargeable", "logged hours", "retainer", "day rate",
                     "time and materials")

    has_time_evidence = 0
    for r in recs:
        facts = r.get("company_facts") or {}
        text_parts = [
            str(facts.get("industry") or "").lower(),
            str(facts.get("description") or "").lower(),
            str(facts.get("tagline") or "").lower(),
        ]
        for s in (facts.get("specialties") or []):
            text_parts.append(str(s).lower())
        for s in (facts.get("services") or []):
            text_parts.append(str(s).lower())
        text = " ".join(text_parts)
        if any(phrase in text for phrase in TIME_EVIDENCE):
            has_time_evidence += 1
    print(f"\n=== RECORDS WITH TIME-EVIDENCE PHRASES IN STRUCTURED TEXT: "
          f"{has_time_evidence} ===")

    # Among qualified records, how many have time evidence?
    qualified = [r for r in recs if (r.get("qualification") or {}).get(
        "verdict", {}).get("icp_status") == "qualified"]
    q_with_time = 0
    for r in qualified:
        facts = r.get("company_facts") or {}
        text_parts = [
            str(facts.get("industry") or "").lower(),
            str(facts.get("description") or "").lower(),
            str(facts.get("tagline") or "").lower(),
        ]
        for s in (facts.get("specialties") or []):
            text_parts.append(str(s).lower())
        for s in (facts.get("services") or []):
            text_parts.append(str(s).lower())
        text = " ".join(text_parts)
        if any(phrase in text for phrase in TIME_EVIDENCE):
            q_with_time += 1
    print(f"  Among qualified: {q_with_time}")

    # --- 4. The real reachability question ---
    # For the 300 processed records: how many are qualified, and how many
    # COULD be qualified if tracks_time were resolved?
    processed = [r for r in recs if (r.get("qualification") or {}).get("verdict")]
    print(f"\n=== REACHABILITY SUMMARY (processed: {len(processed)}) ===")

    # Current state
    current_qualified = sum(1 for r in processed if (r.get("qualification") or {}).get("verdict", {}).get("icp_status") == "qualified")
    current_review = sum(1 for r in processed if (r.get("qualification") or {}).get("verdict", {}).get("icp_status") == "review")
    current_rejected = sum(1 for r in processed if (r.get("qualification") or {}).get("verdict", {}).get("icp_status") == "rejected")
    print(f"  Currently qualified: {current_qualified}")
    print(f"  Currently review: {current_review}")
    print(f"  Currently rejected: {current_rejected}")

    # What if tracks_time were PASS for all records where it is UNKNOWN?
    # Re-derive the verdict
    PASSING = ("pass", "pass_with_tolerance", "not_required")
    DEFINING = ("geography", "company_type")

    would_be_qualified = 0
    would_be_review = 0
    would_be_rejected = 0
    newly_qualified = 0

    for r in processed:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        criteria = dict(s.get("criteria") or {})

        # Simulate tracks_time = pass
        tt = criteria.get("tracks_time") or {}
        if tt.get("status") == "unknown":
            criteria["tracks_time"] = dict(tt)
            criteria["tracks_time"]["status"] = "pass"

        statuses = {name: (ans.get("status") or "missing")
                    for name, ans in criteria.items()}

        if "fail" in statuses.values():
            would_be_rejected += 1
        elif all(s in PASSING for s in statuses.values()):
            would_be_qualified += 1
            if (q.get("verdict") or {}).get("icp_status") != "qualified":
                newly_qualified += 1
        elif all(statuses.get(name) in PASSING for name in DEFINING):
            would_be_qualified += 1
            if (q.get("verdict") or {}).get("icp_status") != "qualified":
                newly_qualified += 1
        else:
            would_be_review += 1

    print(f"\n  If tracks_time were PASS for all UNKNOWN records:")
    print(f"    Would be qualified: {would_be_qualified}")
    print(f"    Would be review: {would_be_review}")
    print(f"    Would be rejected: {would_be_rejected}")
    print(f"    Newly qualified (were review): {newly_qualified}")

    # What if ALL unknowns were resolved to PASS (the theoretical maximum)?
    max_qualified = 0
    for r in processed:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        criteria = dict(s.get("criteria") or {})

        statuses = {}
        for name, ans in criteria.items():
            st = ans.get("status", "missing")
            if st == "unknown":
                st = "pass"  # optimistically resolve
            statuses[name] = st

        if "fail" in statuses.values():
            pass
        elif all(s in PASSING for s in statuses.values()):
            max_qualified += 1
        elif all(statuses.get(name) in PASSING for name in DEFINING):
            max_qualified += 1

    print(f"\n  If ALL unknowns were resolved to PASS (theoretical max):")
    print(f"    Would be qualified: {max_qualified}")
    print(f"    (The rest have at least one FAIL that no resolution fixes)")

    # --- 5. What about the 250 unprocessed? ---
    # Can we simulate what their criteria would be with current data?
    print(f"\n=== UNPROCESSED RECORDS: SIMULATED CRITERIA ===")

    # We need to understand what segments.classify would say
    # For now, just check what raw data they have
    has_any_location = 0
    has_any_type = 0
    has_any_size = 0
    has_any_model = 0

    for r in unprocessed:
        facts = r.get("company_facts") or {}
        seg = r.get("segment") or {}

        # Location
        country = seg.get("country") or ""
        code = seg.get("country_code") or ""
        offices = facts.get("offices") or []
        if country or code or offices:
            has_any_location += 1

        # Type
        industry = facts.get("industry") or ""
        vertical = seg.get("vertical") or ""
        if industry or vertical:
            has_any_type += 1

        # Size
        emps = facts.get("employees")
        emp_range = facts.get("employee_range")
        hc = facts.get("headcount")
        if emps or emp_range or hc:
            has_any_size += 1

        # Business model
        bm = seg.get("business_model") or facts.get("business_model") or ""
        if bm:
            has_any_model += 1

    print(f"  Have location data: {has_any_location}")
    print(f"  Have type/industry data: {has_any_type}")
    print(f"  Have size data: {has_any_size}")
    print(f"  Have business model: {has_any_model}")

    # --- 6. The 6 records with tracks_time = pass ---
    print(f"\n=== RECORDS WITH tracks_time = PASS ===")
    tt_pass = []
    for r in recs:
        q = r.get("qualification") or {}
        s = (q.get("verdict") or {}).get("structural") or {}
        criteria = s.get("criteria") or {}
        tt = (criteria.get("tracks_time") or {}).get("status")
        if tt == "pass":
            tt_pass.append(r)
    print(f"  Count: {len(tt_pass)}")
    for r in tt_pass[:10]:
        q = r.get("qualification") or {}
        v = q.get("verdict") or {}
        s = v.get("structural") or {}
        criteria = s.get("criteria") or {}
        print(f"  {r.get('domain')}: status={v.get('icp_status')}, "
              f"struct={s.get('verdict')}")
        for name in ("geography", "company_type", "services_business",
                      "employees", "tracks_time"):
            ans = criteria.get(name) or {}
            print(f"    {name}: {ans.get('status')}")


if __name__ == "__main__":
    main()
